import cv2
import numpy as np

def analyze_camera_motion(video_path, start, end):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start * fps))

    ret, prev_frame = cap.read()
    if not ret:
        cap.release()
        return 0, 0

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    global_motion = []
    stability_score = []

    while cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 < end:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray,
            None,
            0.5, 3, 15, 3, 5, 1.2, 0
        )

        magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        avg_motion = np.mean(magnitude)
        std_motion = np.std(magnitude)

        global_motion.append(avg_motion)
        stability_score.append(std_motion)

        prev_gray = gray

    cap.release()

    if len(global_motion) == 0:
        return 0, 0

    return np.mean(global_motion), np.mean(stability_score)