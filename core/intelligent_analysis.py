import cv2
import numpy as np
import torch
from ultralytics import YOLO
from core.camera_motion_analysis import analyze_camera_motion

# carregar YOLO uma única vez
# Forçar CPU se houver erro CUDA para evitar "no kernel image" errors
device = "cpu"  # Default para CPU (mais estável em containers)

# Tentar GPU apenas se disponível E se conseguir fazer inference
if torch.cuda.is_available():
    try:
        model = YOLO("yolov8n.pt")
        model.to("cuda")
        # Teste rápido: tentar inference em GPU
        test_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = model(test_frame, verbose=False, device="cuda")
        device = "cuda"
        print("⛩  YOLO carregado na GPU")
    except Exception as e:
        print(f"⚠️  CUDA unavailable para YOLO: {type(e).__name__}")
        print("   Continuando com YOLO na CPU")
        device = "cpu"

model = YOLO("yolov8n.pt")
model.to(device)


def sharpness_score(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def brightness_score(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)


def people_score(frame):
    results = model(frame, verbose=False, device=device)
    count = 0

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            if model.names[cls] == "person":
                count += 1

    return count


def analyze_scene(video_path, start, end):
    print(f"   → analisando cena {start:.2f}-{end:.2f}")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start * fps))

    total_score = 0
    frame_count = 0
    prev_gray = None
    motion_penalty = 0

    # pular alguns quadros para ganhar desempenho (amostragem)
    SKIP_FRAMES = 2  # analisa apenas a cada 2 quadros

    while cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 < end:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % SKIP_FRAMES != 0:
            frame_count += 1
            continue

        sharp = sharpness_score(frame)
        bright = brightness_score(frame)
        people = people_score(frame)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            motion_penalty += np.mean(diff)

        prev_gray = gray

        score = (
            sharp * 0.4 +
            bright * 0.1 +
            people * 120 
        )

        total_score += score
        frame_count += 1

    cap.release()

    if frame_count == 0:
        return 0

    avg_base_score = total_score / frame_count
    avg_motion_penalty = motion_penalty / frame_count
    cam_motion, cam_instability = analyze_camera_motion(video_path, start, end)


    instability_penalty = cam_instability * 150
    smooth_bonus = 0
    if 0.5 < cam_motion < 5 and cam_instability < 1.5:
        smooth_bonus = 200

    final_score = (
        avg_base_score
        + smooth_bonus
        - instability_penalty
        - (avg_motion_penalty * 0.2)
    )

    return final_score