import os
import shutil
import subprocess
from typing import Optional

import cv2
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")


def _which_ffmpeg() -> Optional[str]:
    # 1) If user explicitly sets FFMPEG_BIN in env
    env_bin = os.getenv("FFMPEG_BIN", "").strip()
    if env_bin:
        if os.path.isfile(env_bin):
            return env_bin
        # allow directory (bin folder)
        if os.path.isdir(env_bin):
            cand = os.path.join(env_bin, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            if os.path.isfile(cand):
                return cand

    # 2) PATH
    return shutil.which("ffmpeg")


def _get_fps_opencv(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    finally:
        cap.release()
    return fps


def ensure_fps(input_path: str, target_fps: int = 30, downscale_width: int = None) -> str:
    """
    Ensure constant FPS using ffmpeg if available.
    Returns a path to the FPS-normalized video (may be same as input if already good).
    Never returns non-path types.
    """
    if not isinstance(input_path, (str, os.PathLike)):
        raise TypeError(f"input_path must be a path, got {type(input_path)}")
    input_path = os.fspath(input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    target_fps = int(target_fps)
    if target_fps <= 0:
        raise ValueError(f"target_fps must be > 0, got {target_fps}")

    # If already close to target FPS and (optionally) already small enough, keep it (fast path)
    fps = _get_fps_opencv(input_path)
    if downscale_width is not None:
        try:
            cap = cv2.VideoCapture(input_path)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            cap.release()
        except Exception:
            w = 0
    else:
        w = None

    if fps > 0 and abs(fps - target_fps) < 0.25 and (downscale_width is None or (w and w <= int(downscale_width))):
        return input_path

    ffmpeg = _which_ffmpeg()
    if not ffmpeg:
        # ffmpeg missing → fallback: return original (but warn upstream by raising)
        raise RuntimeError(
            "ffmpeg not found. Install ffmpeg or set FFMPEG_BIN. "
            "Cannot guarantee constant FPS without ffmpeg."
        )

    base, ext = os.path.splitext(input_path)
    suffix = f"_fps{target_fps}"
    if downscale_width:
        suffix += f"_w{int(downscale_width)}"
    out_path = f"{base}{suffix}.mp4"

    # If output already exists, reuse it (avoid re-encoding)
    if os.path.exists(out_path):
        return out_path

    # Build filter chain
    vf_filters = []
    if downscale_width:
        # preserve aspect ratio, set width=max downscale_width, height=-2 for even
        vf_filters.append(f"scale='min({int(downscale_width)},iw)':'-2'")
    vf_filters.append(f"fps={target_fps}")
    vf = ",".join(vf_filters)

    # Fast codec settings for speed over quality
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", input_path,
        "-vf", vf,
        "-r", str(target_fps),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-movflags", "+faststart",
        out_path,
    ]

    # On Windows, subprocess list-form is safest
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr}")

    return out_path
