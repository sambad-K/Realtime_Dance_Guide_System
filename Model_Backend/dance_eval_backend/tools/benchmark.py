#!/usr/bin/env python3
"""
Lightweight benchmark runner for the dance-eval pipeline.
Usage:
  python tools/benchmark.py <ref_video> <user_video>

It runs (and times):
 - ffmpeg normalization via `ensure_fps`
 - COCO-17 pose extraction via `extract_coco17_sequence`
 - ST-GCN window embedding via `stgcn_embed_sequence_windows` (if checkpoint present)
 - Full `compare_sequences` and reports overall / final score

Prints a JSON summary with timings and basic stats.
"""
import json
import os
import sys
import time
from pathlib import Path

from config import Config
from services.ffmpeg_utils import ensure_fps
from services.pose_extract import extract_coco17_sequence
from services.stgcn_embed import stgcn_embed_sequence_windows
from services.compare import compare_sequences


def time_call(fn, *a, **kw):
    t0 = time.perf_counter()
    res = fn(*a, **kw)
    t1 = time.perf_counter()
    return res, t1 - t0


def size_mb(p):
    try:
        return float(os.path.getsize(p)) / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/benchmark.py <ref_video> <user_video>")
        sys.exit(2)

    ref_vid = sys.argv[1]
    usr_vid = sys.argv[2]

    out = {
        "ref_video": ref_vid,
        "usr_video": usr_vid,
        "timings": {},
        "stats": {},
    }

    # 1) ensure fps + downscale
    try:
        norm_ref, t_ref_norm = time_call(ensure_fps, ref_vid, Config.TARGET_FPS, Config.DOWN_SCALE_WIDTH)
    except Exception as e:
        norm_ref = ref_vid
        t_ref_norm = 0.0
        out["timings"]["ref_ffmpeg_error"] = str(e)

    try:
        norm_usr, t_usr_norm = time_call(ensure_fps, usr_vid, Config.TARGET_FPS, Config.DOWN_SCALE_WIDTH)
    except Exception as e:
        norm_usr = usr_vid
        t_usr_norm = 0.0
        out["timings"]["usr_ffmpeg_error"] = str(e)

    out["timings"]["ref_ffmpeg_s"] = t_ref_norm
    out["timings"]["usr_ffmpeg_s"] = t_usr_norm
    out["stats"]["ref_size_mb"] = size_mb(norm_ref)
    out["stats"]["usr_size_mb"] = size_mb(norm_usr)

    # 2) pose extraction
    try:
        (res_ref, t_ref_extract) = time_call(
            extract_coco17_sequence, norm_ref, Config.TARGET_FPS, Config.DOWN_SCALE_WIDTH, Config.MAX_WORKERS
        )
    except Exception as e:
        print("Pose extraction (ref) failed:", e)
        raise

    try:
        (res_usr, t_usr_extract) = time_call(
            extract_coco17_sequence, norm_usr, Config.TARGET_FPS, Config.DOWN_SCALE_WIDTH, Config.MAX_WORKERS
        )
    except Exception as e:
        print("Pose extraction (usr) failed:", e)
        raise

    out["timings"]["ref_extract_s"] = t_ref_extract
    out["timings"]["usr_extract_s"] = t_usr_extract
    out["stats"]["ref_frames"] = int(res_ref.get("frames", 0))
    out["stats"]["usr_frames"] = int(res_usr.get("frames", 0))

    k_ref = res_ref.get("kpts")
    c_ref = res_ref.get("conf")
    k_usr = res_usr.get("kpts")
    c_usr = res_usr.get("conf")

    # 3) ST-GCN embeddings (optional if checkpoint present)
    ckpt = getattr(Config, "STGCN_CKPT", None) or getattr(Config, "STGCN_CKPT_PATH", None)
    z_ref = None
    z_usr = None
    if ckpt and os.path.exists(ckpt):
        try:
            (z_ref, ref_err), t_ref_stg = time_call(
                stgcn_embed_sequence_windows, k_ref, c_ref, ckpt_path=ckpt, conf_thr=0.2
            )
        except Exception as e:
            z_ref = None
            ref_err = str(e)
            t_ref_stg = 0.0
        try:
            (z_usr, usr_err), t_usr_stg = time_call(
                stgcn_embed_sequence_windows, k_usr, c_usr, ckpt_path=ckpt, conf_thr=0.2
            )
        except Exception as e:
            z_usr = None
            usr_err = str(e)
            t_usr_stg = 0.0
        out["timings"]["ref_stgcn_s"] = t_ref_stg
        out["timings"]["usr_stgcn_s"] = t_usr_stg
        out["stats"]["ref_win_count"] = int(getattr(z_ref, "shape", [0])[0]) if z_ref is not None else 0
        out["stats"]["usr_win_count"] = int(getattr(z_usr, "shape", [0])[0]) if z_usr is not None else 0
    else:
        out["timings"]["ref_stgcn_s"] = None
        out["timings"]["usr_stgcn_s"] = None

    # 4) compare
    t0 = time.perf_counter()
    result = compare_sequences(k_ref, c_ref, k_usr, c_usr)
    t1 = time.perf_counter()
    out["timings"]["compare_s"] = t1 - t0
    out["result"] = result

    print(json.dumps(out, indent=2, default=lambda o: repr(o)))


if __name__ == "__main__":
    main()
