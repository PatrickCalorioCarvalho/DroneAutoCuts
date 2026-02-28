import subprocess
import os
import uuid
from core.camera_motion_analysis import analyze_camera_motion

# Detectar se h264_nvenc realmente está disponível (fallback automático)
def detect_available_encoder():
    """Testa h264_nvenc com um encode de teste curto. Se falhar, usa libx264"""
    try:
        # Teste real: criar um frame dummy e tentar codificar com h264_nvenc
        # usando a entrada padrão (pipe)
        test_cmd = [
            "ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=0.1",
            "-c:v", "h264_nvenc", "-preset", "slow",
            "-f", "null", "-"
        ]
        result = subprocess.run(
            test_cmd,
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ h264_nvenc funcional — usando GPU")
            return "h264_nvenc", True
        else:
            # Mostrar stderr para debug
            if "Cannot load libnv" in result.stderr or "driver" in result.stderr.lower():
                print("⚠️  h264_nvenc detectado mas drivers NVIDIA ausentes — usando libx264 (CPU)")
            else:
                print("⚠️  h264_nvenc não funcional — usando libx264 (CPU)")
            return "libx264", False
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout testando h264_nvenc — usando libx264 (CPU)")
        return "libx264", False
    except Exception as e:
        print(f"⚠️  Erro ao detectar encoder: {e} — usando libx264")
        return "libx264", False

USE_GPU = os.getenv("USE_GPU", "0") == "1"
FFMPEG_CODEC, NVENC_AVAILABLE = detect_available_encoder() if USE_GPU else ("libx264", False)
FFMPEG_HWACCEL_ARGS = ["-hwaccel", "cuda"] if NVENC_AVAILABLE else []


def run_ffmpeg(command, description="ffmpeg", retry_hwaccel=True):
    try:
        print(f"   running: {' '.join(command)}")
        proc = subprocess.run(command, check=True, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout)
        return proc
    except subprocess.CalledProcessError as e:
        print(f"Error while {description}: returncode={e.returncode}")
        if e.stdout:
            print("--- ffmpeg stdout ---")
            print(e.stdout)
        if e.stderr:
            print("--- ffmpeg stderr ---")
            print(e.stderr)
        # attempt fallback to CPU decoding/encoding on first failure
        if retry_hwaccel:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if FFMPEG_HWACCEL_ARGS and any(x in stderr_lower for x in ["cuda_error_no_device","cu->cuinit","no cuda-capable device"]):
                print("⚠️  CUDA device unavailable during ffmpeg run; retrying without hwaccel and nvenc")
            else:
                print("⚠️  ffmpeg command failed; retrying once in CPU-only mode")
            # remove hwaccel arguments
            new_command = [arg for arg in command if arg not in FFMPEG_HWACCEL_ARGS]
            # replace nvenc codec with libx264 if present
            for i, arg in enumerate(new_command):
                if arg == "-c:v" and i+1 < len(new_command) and new_command[i+1] == "h264_nvenc":
                    new_command[i+1] = "libx264"
            return run_ffmpeg(new_command, description + " (cpu decode/encode)", retry_hwaccel=False)
        raise


def get_encoding_args(codec):
    """Retorna argumentos de encoding corretos conforme o codec"""
    if codec == "h264_nvenc":
        # NVENC não suporta -crf, usa -rc vbr (variable bitrate) com -qp (quality)
        return ["-rc", "vbr", "-cq", "18", "-preset", "slow"]
    else:
        # libx264 usa -crf (constant rate factor)
        return ["-preset", "slow", "-crf", "18"]



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
                *get_encoding_args(FFMPEG_CODEC),
                temp_name
            ]
        else:
            ffmpeg_command += [
                "-c:v", FFMPEG_CODEC,
                *get_encoding_args(FFMPEG_CODEC),
                temp_name
            ]

        print(f"   extraindo cena para {temp_name}")
        run_ffmpeg(ffmpeg_command, description=f"extracting scene {start:.2f}-{end:.2f}")
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
        *get_encoding_args(FFMPEG_CODEC),
        merged_temp
    ]

    run_ffmpeg(concat_command, description="concatenating clips")

    # 4️⃣ Aplicar LUT cinematográfica
    lut_path = "assets/luts/cinematic.cube"
    
    # Resolver caminho absoluto para LUT (funciona dentro e fora de containers)
    if not os.path.isabs(lut_path):
        lut_path = os.path.abspath(lut_path)
    
    if not os.path.exists(lut_path):
        raise FileNotFoundError(
            f"LUT file not found: {lut_path}\nCwd: {os.getcwd()}"
        )
    # quick sanity: ensure LUT file isn't obviously too small
    size = os.path.getsize(lut_path)
    if size < 1024:  # arbitrary threshold; correct LUTs are several KB
        print(f"⚠️  LUT file {lut_path} seems too small ({size} bytes), it may be corrupted")

    def lut_is_valid(path):
        """Check .cube validity by comparing entry count against LUT_3D_SIZE"""
        try:
            with open(path) as f:
                lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]
            size_line = next((l for l in lines if l.startswith('LUT_3D_SIZE')), None)
            if not size_line:
                return False
            parts = size_line.split()
            if len(parts) < 2:
                return False
            n = int(parts[1])
            # data lines are those starting with a digit (r g b)
            data = [l for l in lines if l[0].isdigit()]
            return len(data) == n**3
        except Exception:
            return False

    if not lut_is_valid(lut_path):
        print(f"⚠️  LUT file {lut_path} failed validation, skipping color grading")
        # skip LUT entirely and just copy merged_temp to output later
        bypass_lut = True
    else:
        bypass_lut = False

    if bypass_lut:
        print("🎨 Pulando aplicação de LUT (arquivo inválido)")
        # just copy/encode merged_temp to output_path
        copy_cmd = [
            "ffmpeg", "-y", "-threads", "0",
            "-i", merged_temp,
            "-c:v", FFMPEG_CODEC,
            *get_encoding_args(FFMPEG_CODEC),
            output_path
        ]
        run_ffmpeg(copy_cmd, description="finalizing without LUT")
    else:
        print("🎨 Aplicando LUT e finalizando")
        color_command = [
            "ffmpeg",
            "-y",
            "-threads", "0",
            *FFMPEG_HWACCEL_ARGS,
            "-i", merged_temp,
            "-vf", f"lut3d={lut_path}",
            "-c:v", FFMPEG_CODEC,
            *get_encoding_args(FFMPEG_CODEC),
            output_path
        ]

        try:
            run_ffmpeg(color_command, description="applying LUT and finalizing")
        except subprocess.CalledProcessError as e:
            # if LUT fails (e.g. unexpected EOF) fall back to copying/encoding without it
            print("⚠️  failed to apply LUT, proceeding without color grade")
            # simply copy merged_temp to output_path using the codec
            fallback_cmd = [
                "ffmpeg", "-y", "-threads", "0",
                "-i", merged_temp,
                "-c:v", FFMPEG_CODEC,
                *get_encoding_args(FFMPEG_CODEC),
                output_path
            ]
            run_ffmpeg(fallback_cmd, description="finalizing without LUT")

    
    # Validar arquivo não ficou vazio
    if os.path.getsize(output_path) == 0:
        raise RuntimeError(f"Output file is empty: {output_path}")
    
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Highlight finalizado com sucesso! ({file_size_mb:.1f} MB)")

    # Limpeza
    for file in temp_files:
        os.remove(file)

    os.remove(list_file)
    os.remove(merged_temp)


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
        *get_encoding_args(FFMPEG_CODEC),
        output_path
    ]

    run_ffmpeg(command, description="exporting vertical version")
    
    # Validar arquivo não ficou vazio
    if os.path.getsize(output_path) == 0:
        raise RuntimeError(f"Output file is empty: {output_path}")
    
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"📱 Versão vertical exportada com sucesso! ({file_size_mb:.1f} MB)")