import os
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.scene_detection import detect_scenes
#from core.motion_analysis import calculate_motion_score
from core.highlight_builder import (
    build_highlight, export_vertical, run_ffmpeg,
    FFMPEG_CODEC, FFMPEG_HWACCEL_ARGS, get_encoding_args
)
from core.intelligent_analysis import analyze_scene

# ------------------------------------------------------------------
# Usar configuração de encoder de highlight_builder (com fallback automático)
# ------------------------------------------------------------------

INPUT_FOLDER = "input"
NORMALIZED_FOLDER = "normalized"
OUTPUT_FOLDER = "output"

os.makedirs(NORMALIZED_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def normalize_video(input_path):
    filename = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(NORMALIZED_FOLDER, f"{filename}.mp4")

    print(f"🔄 Normalizando {input_path} → {output_path}")
    # usar todos os núcleos disponíveis e, se habilitado, HW accel
    command = [
        "ffmpeg",
        "-threads", "0",
        "-y",
        *FFMPEG_HWACCEL_ARGS,
        "-i", input_path,
        "-vf", "scale=1920:1080",
        "-r", "30",
        "-c:v", FFMPEG_CODEC,
        *get_encoding_args(FFMPEG_CODEC),
        output_path
    ]

    run_ffmpeg(command, description=f"normalizing {input_path}")
    print(f"✅ Normalização concluída: {output_path}")
    return output_path


def concatenate_all_videos(video_list, output_path):
    print(f"🧩 Concatenando {len(video_list)} vídeos em {output_path}")
    list_file = os.path.join(NORMALIZED_FOLDER, "all_videos.txt")

    with open(list_file, "w") as f:
        for video in video_list:
            f.write(f"file '{os.path.abspath(video)}'\n")

    command = [
        "ffmpeg",
        "-y",
        "-threads", "0",
        *FFMPEG_HWACCEL_ARGS,
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]

    run_ffmpeg(command, description="concatenating all videos")
    os.remove(list_file)
    print("✅ Vídeos concatenados com sucesso")


def main():
    print("Normalizando vídeos...")

    normalized_videos = []

    for file in os.listdir(INPUT_FOLDER):
        if file.lower().endswith((".mov", ".mp4")):
            input_path = os.path.join(INPUT_FOLDER, file)
            normalized = normalize_video(input_path)
            normalized_videos.append(normalized)

    print("Concatenando todos os vídeos...")
    merged_video = os.path.join(NORMALIZED_FOLDER, "merged.mp4")
    concatenate_all_videos(normalized_videos, merged_video)

    print("🔍 Detectando cenas…")
    scenes = detect_scenes(merged_video)
    print(f"⚙️ {len(scenes)} cenas encontradas")

    scored = []
    # análise em paralelo para aproveitar múltiplos cores/GPU
    with ThreadPoolExecutor() as executor:
        future_to_scene = {
            executor.submit(analyze_scene, merged_video, start, end): (start, end)
            for (start, end) in scenes
        }
        for idx, future in enumerate(as_completed(future_to_scene), start=1):
            start, end = future_to_scene[future]
            try:
                score = future.result()
            except Exception as e:
                print(f"   erro ao avaliar cena {start:.2f}-{end:.2f}: {e}")
                score = 0
            print(f"   Avaliando cena {idx}/{len(scenes)} ({start:.2f}s-{end:.2f}s) → score={score:.1f}")
            scored.append((start, end, score))
        
    scored.sort(key=lambda x: x[2], reverse=True)
    top = scored[:max(1, int(len(scored) * 0.2))]
    selected = [(s[0], s[1]) for s in top]
    print(f"✅ Selecionadas {len(selected)} cenas para highlight")

    highlight_path = os.path.join(OUTPUT_FOLDER, "highlight_horizontal.mp4")
    build_highlight(merged_video, selected, highlight_path)

    #vertical_path = os.path.join(OUTPUT_FOLDER, "highlight_tiktok_9x16.mp4")
    #export_vertical(highlight_path, vertical_path)
    print("📁 Todos os arquivos foram gerados em", OUTPUT_FOLDER)

    print("Finalizado com sucesso 🚀")


if __name__ == "__main__":
    main()


      git config --global user.email "you@example.com"
  git config --global user.name "Your Name"