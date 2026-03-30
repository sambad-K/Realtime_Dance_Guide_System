import cv2
import numpy as np
import mediapipe as mp
import math
from multiprocessing import Pool, cpu_count

MP = mp.solutions.pose.PoseLandmark

# COCO-17 mapping (approx for eyes)
MP_TO_COCO = {
    0: MP.NOSE,
    1: MP.LEFT_EYE_INNER,
    2: MP.RIGHT_EYE_INNER,
    3: MP.LEFT_EAR,
    4: MP.RIGHT_EAR,
    5: MP.LEFT_SHOULDER,
    6: MP.RIGHT_SHOULDER,
    7: MP.LEFT_ELBOW,
    8: MP.RIGHT_ELBOW,
    9: MP.LEFT_WRIST,
    10: MP.RIGHT_WRIST,
    11: MP.LEFT_HIP,
    12: MP.RIGHT_HIP,
    13: MP.LEFT_KNEE,
    14: MP.RIGHT_KNEE,
    15: MP.LEFT_ANKLE,
    16: MP.RIGHT_ANKLE,
}


def _single_process_worker(video_path: str, step: int, target_width: int, src_fps: float):
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=0,
        enable_segmentation=False,
        min_detection_confidence=0.45,
        min_tracking_confidence=0.45,
    )
    cap_local = cv2.VideoCapture(video_path)
    kpts_list, conf_list = [], []
    frame_idx = 0
    while True:
        ok, frame = cap_local.read()
        if not ok:
            break
        if (frame_idx % step) != 0:
            frame_idx += 1
            continue
        h, w = frame.shape[:2]
        if target_width and w > target_width:
            scale = float(target_width) / float(w)
            nh = int(round(h * scale))
            frame = cv2.resize(frame, (target_width, nh), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        frame_k = np.zeros((17, 2), dtype=np.float32)
        frame_c = np.zeros((17,), dtype=np.float32)
        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark
            for coco_i, mp_i in MP_TO_COCO.items():
                p = lm[int(mp_i)]
                frame_k[coco_i, 0] = float(p.x)
                frame_k[coco_i, 1] = float(p.y)
                vis = getattr(p, "visibility", None)
                frame_c[coco_i] = float(vis) if vis is not None else 1.0
        kpts_list.append(frame_k)
        conf_list.append(frame_c)
        frame_idx += 1
    cap_local.release()
    pose.close()
    if not kpts_list:
        return np.zeros((0, 17, 2), dtype=np.float32), np.zeros((0, 17), dtype=np.float32), src_fps / float(max(1, step))
    return np.stack(kpts_list, axis=0), np.stack(conf_list, axis=0), float(src_fps / float(max(1, step)))


def _range_worker(args):
    # args: (video_path, start_frame, end_frame, step, target_width)
    vpath, start, end, step_w, tw = args
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=0,
        enable_segmentation=False,
        min_detection_confidence=0.45,
        min_tracking_confidence=0.45,
    )
    cap_w = cv2.VideoCapture(vpath)
    if not cap_w.isOpened():
        return []
    # seek to start frame
    cap_w.set(cv2.CAP_PROP_POS_FRAMES, float(start))
    k_out = []
    c_out = []
    idx = start
    while idx < end:
        ok, frame = cap_w.read()
        if not ok:
            break
        if (idx % step_w) != 0:
            idx += 1
            continue
        h, w = frame.shape[:2]
        if tw and w > tw:
            scale = float(tw) / float(w)
            nh = int(round(h * scale))
            frame = cv2.resize(frame, (tw, nh), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        frame_k = np.zeros((17, 2), dtype=np.float32)
        frame_c = np.zeros((17,), dtype=np.float32)
        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark
            for coco_i, mp_i in MP_TO_COCO.items():
                p = lm[int(mp_i)]
                frame_k[coco_i, 0] = float(p.x)
                frame_k[coco_i, 1] = float(p.y)
                vis = getattr(p, "visibility", None)
                frame_c[coco_i] = float(vis) if vis is not None else 1.0
        k_out.append((idx, frame_k))
        c_out.append((idx, frame_c))
        idx += 1
    cap_w.release()
    pose.close()
    # return list of (frame_idx, k, c)
    res_list = []
    for (i, kp), (j, cf) in zip(k_out, c_out):
        res_list.append((i, kp, cf))
    return res_list


def extract_coco17_sequence(video_path: str, target_fps: int = 30, target_width: int = 640, num_workers: int = None):
    """
    Extract COCO-17 keypoints from a video with optional multiprocessing.

    - `num_workers`: if None, auto-select (min(cpu_count()-1,4)). Set 1 to force single-process.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or float(target_fps)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    # compute frame skip step to approximate target_fps
    try:
        step = max(1, int(round(max(1.0, src_fps) / float(max(1, target_fps)))))
    except Exception:
        step = 1

    # decide whether to use multiprocessing
    if num_workers is None:
        if total_frames <= 0 or total_frames < 300:
            num_workers = 1
        else:
            num_workers = min(max(1, cpu_count() - 1), 4)
    else:
        num_workers = max(1, int(num_workers))

    cap.release()

    # use module-level worker `_single_process_worker` for multiprocessing safety

    # use module-level worker `_range_worker` for multiprocessing safety

    if num_workers <= 1:
        kpts, conf, fps_out = _single_process_worker(video_path, step, target_width, src_fps)
        return {"kpts": kpts, "conf": conf, "fps": float(fps_out), "frames": int(kpts.shape[0])}

    # build ranges for workers
    total = total_frames
    chunk = max(200, math.ceil(total / num_workers))
    ranges = []
    for s in range(0, total, chunk):
        e = min(total, s + chunk)
        ranges.append((s, e))

    args = [(video_path, s, e, step, target_width) for (s, e) in ranges]

    with Pool(processes=num_workers) as pool:
        parts = pool.map(_range_worker, args)

    # flatten results and sort by frame index
    items = []
    for part in parts:
        if not part:
            continue
        items.extend(part)
    if not items:
        return {"kpts": np.zeros((0, 17, 2), dtype=np.float32), "conf": np.zeros((0, 17), dtype=np.float32), "fps": float(src_fps / float(max(1, step))), "frames": 0}

    items.sort(key=lambda x: x[0])
    k_list = [it[1] for it in items]
    c_list = [it[2] for it in items]
    kpts = np.stack(k_list, axis=0)
    conf = np.stack(c_list, axis=0)
    return {"kpts": kpts, "conf": conf, "fps": float(src_fps / float(max(1, step))), "frames": int(kpts.shape[0])}
