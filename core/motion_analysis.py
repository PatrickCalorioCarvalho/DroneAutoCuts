import cv2
import numpy as np

def calculate_motion_score(video_path, start, end):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start * fps))

    prev_frame = None
    motion_score = 0
    frame_count = 0

    while cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 < end:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_frame is not None:
            diff = cv2.absdiff(prev_frame, gray)
            motion_score += np.sum(diff)

        prev_frame = gray
        frame_count += 1

    cap.release()

    if frame_count == 0:
        return 0

    return motion_score / frame_count