import subprocess
import os
import uuid
from core.camera_motion_analysis import analyze_camera_motion

# aceleracao sacrificada via ffmpeg (definida por variavel de ambiente)
USE_GPU = os.getenv("USE_GPU", "0") == "1"
FFMPEG_CODEC = "h264_nvenc" if USE_GPU else "libx264"
FFMPEG_HWACCEL_ARGS = ["-hwaccel", "cuda"] if USE_GPU else []



def build_highlight(video_path, selected_scenes, output_path):
    import tempfile
    temp_files = []

    print("🎬 Iniciando geração de highlight...")

    for start, end in selected_scenes:
        duration = end - start
        temp_name = os.path.join(tempfile.gettempdir(), f"clip_{uuid.uuid4().hex}.mp4")

        cam_motion, cam_instability = analyze_camera_motion(video_path, start, end)

        print(
            f"Cena {start:.2f}s → {end:.2f}s | "
            f"Motion={cam_motion:.2f} | Instab={cam_instability:.2f}"
        )

        # ❌ Descartar tremedeira forte
        if cam_instability > 3:
            print("❌ Tremedeira forte detectada — descartando cena")
            continue

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-threads", "0",
            *FFMPEG_HWACCEL_ARGS,
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
        ]

        # 🚀 Acelerar se câmera parada
        if cam_motion < 0.8 and cam_instability < 1:
            print("⚡ Cena estática — acelerando 2x")

            ffmpeg_command += [
                "-filter:v", "setpts=0.5*PTS",
                "-an",
                "-c:v", FFMPEG_CODEC,
                "-preset", "slow",   # maior qualidade
                "-crf", "18",
                temp_name
            ]
        else:
            ffmpeg_command += [
                "-c:v", FFMPEG_CODEC,
                "-preset", "slow",   # maior qualidade
                "-crf", "18",
                temp_name
            ]

        print(f"   extraindo cena para {temp_name}")
        subprocess.run(ffmpeg_command, check=True)
        temp_files.append(temp_name)

    if not temp_files:
        print("⚠ Nenhuma cena válida encontrada.")
        return

    # 2️⃣ Criar lista concat
    list_file = os.path.join(tempfile.gettempdir(), "concat_list.txt")
    with open(list_file, "w") as f:
        for file in temp_files:
            f.write(f"file '{file}'\n")

    merged_temp = os.path.join(tempfile.gettempdir(), "merged_raw.mp4")

    # 3️⃣ Concatenar
    print("🔗 Concatenando clipes intermediários")
    concat_command = [
        "ffmpeg",
        "-y",
        "-threads", "0",
        *FFMPEG_HWACCEL_ARGS,
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c:v", FFMPEG_CODEC,
        "-preset", "slow",
        "-crf", "18",
        merged_temp
    ]

    subprocess.run(concat_command, check=True)

    # 4️⃣ Aplicar LUT cinematográfica
    lut_path = "assets/luts/cinematic.cube"

    print("🎨 Aplicando LUT e finalizando")
    color_command = [
        "ffmpeg",
        "-y",
        "-threads", "0",
        *FFMPEG_HWACCEL_ARGS,
        "-i", merged_temp,
        "-vf", f"lut3d={lut_path}",
        "-c:v", FFMPEG_CODEC,
        "-preset", "slow",
        "-crf", "18",
        output_path
    ]

    subprocess.run(color_command, check=True)

    # Limpeza
    for file in temp_files:
        os.remove(file)

    os.remove(list_file)
    os.remove(merged_temp)

    print("✅ Highlight finalizado com sucesso!")


# =====================================================
# EXPORTAÇÃO VERTICAL (Instagram / Reels / TikTok)
# =====================================================

def export_vertical(input_path, output_path):
    print(f"📱 Exportando versão vertical de {input_path} → {output_path}")
    command = [
        "ffmpeg",
        "-y",
        "-threads", "0",
        *FFMPEG_HWACCEL_ARGS,
        "-i", input_path,
        "-vf", "scale=1920:-1, crop=1080:1920:(in_w-1080)/2:0",
        "-c:v", FFMPEG_CODEC,
        "-preset", "slow",
        "-crf", "18",
        output_path
    ]

    subprocess.run(command, check=True)

    print("📱 Versão vertical exportada com sucesso!")