import os
import json
import time
import traceback
from typing import Optional

from redis import Redis
from rq import Worker, Queue

from config import Config
from services.ffmpeg_utils import ensure_fps
from services.pose_extract import extract_coco17_sequence
from services.normalize import normalize_sequence_hip
from services.artifacts import save_npz, save_json

redis_conn = Redis.from_url(Config.REDIS_URL)

def _job_file(job_id: str) -> str:
    return os.path.join(Config.JOBS_DIR, f"{job_id}.json")

def _load_job(job_id: str) -> dict:
    with open(_job_file(job_id), "r", encoding="utf-8") as fp:
        return json.load(fp)

def _save_job(job: dict):
    job["updated_at"] = int(time.time())
    with open(_job_file(job["job_id"]), "w", encoding="utf-8") as fp:
        json.dump(job, fp, indent=2)

def _find_uploaded_video_path(video_id: str) -> Optional[str]:
    for fn in os.listdir(Config.UPLOAD_DIR):
        if fn.endswith(".json"):
            continue
        stem, _ = os.path.splitext(fn)
        if stem == video_id:
            return os.path.join(Config.UPLOAD_DIR, fn)
    return None

def run_extract_job(job_id: str):
    job = _load_job(job_id)
    try:
        job["status"] = "processing"
        job["progress"] = 5
        _save_job(job)

        video_id = job["video_id"]
        vid_path = _find_uploaded_video_path(video_id)
        if not vid_path:
            raise FileNotFoundError(f"upload video not found for {video_id}")

        job["progress"] = 15
        _save_job(job)

        norm_path = ensure_fps(vid_path, Config.TARGET_FPS, downscale_width=getattr(Config, 'DOWN_SCALE_WIDTH', None))

        job["progress"] = 30
        _save_job(job)

        seq = extract_coco17_sequence(norm_path, target_fps=Config.TARGET_FPS)

        job["progress"] = 70
        _save_job(job)

        norm = normalize_sequence_hip(seq["kpts"], seq["conf"])

        job["progress"] = 85
        _save_job(job)

        out_dir = os.path.join(Config.NORMALIZED_DIR, job_id)
        os.makedirs(out_dir, exist_ok=True)

        save_npz(
            os.path.join(out_dir, "keypoints.npz"),
            kpts=norm["kpts_norm"],
            conf=seq["conf"],
            kpts_raw=seq["kpts"],
        )

        save_json(os.path.join(out_dir, "meta.json"), {
            "job_id": job_id,
            "video_id": video_id,
            "fps": seq["fps"],
            "frames": int(seq["kpts"].shape[0]),
            "pipeline_version": "v1_extract_norm",
            "notes": ["COCO-17", "hip-normalized", "confidence-kept"]
        })

        job["status"] = "done"
        job["progress"] = 100
        job["artifacts"] = {
            "keypoints": f"/artifacts/{job_id}/keypoints.npz",
            "meta": f"/artifacts/{job_id}/meta.json",
            "preview": f"/preview/{job_id}"
        }
        _save_job(job)

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["trace"] = traceback.format_exc()
        _save_job(job)
        raise

def main():
    try:
        print("=== Worker starting ===", flush=True)
        print("Redis URL:", Config.REDIS_URL, flush=True)

        # HARD check: redis reachable
        print("Redis ping:", redis_conn.ping(), flush=True)

        queue = Queue("dance-eval", connection=redis_conn)
        print("Listening on queue:", queue.name, flush=True)

        worker = Worker([queue], connection=redis_conn)
        print("Worker created. Waiting for jobs...", flush=True)

        worker.work(with_scheduler=False)

    except Exception:
        print("=== WORKER CRASHED ===", flush=True)
        print(traceback.format_exc(), flush=True)
        raise

if __name__ == "__main__":
    main()
