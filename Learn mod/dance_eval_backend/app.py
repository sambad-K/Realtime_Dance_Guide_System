import os
import uuid
import json
import time
import traceback
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from config import Config
from services.ffmpeg_utils import ensure_fps
from services.pose_extract import extract_coco17_sequence
from services.normalize import normalize_sequence_hip
from services.artifacts import save_npz, save_json
from services.compare import compare_sequences
from services.performance import (
    queue_manager, timeout_tracker, batch_manager, system_monitor,
    TimeoutPolicy, memory_profile_context
)
from services.llm import generate_verdict


# ---------------- Utils ----------------

def ensure_dirs():
    for p in [Config.STORAGE_ROOT, Config.UPLOAD_DIR, Config.NORMALIZED_DIR, Config.JOBS_DIR]:
        os.makedirs(p, exist_ok=True)

def job_file(job_id: str) -> str:
    return os.path.join(Config.JOBS_DIR, f"{job_id}.json")

def load_job(job_id: str) -> dict:
    with open(job_file(job_id), "r", encoding="utf-8") as fp:
        return json.load(fp)

def save_job(job: dict):
    job["updated_at"] = int(time.time())
    with open(job_file(job["job_id"]), "w", encoding="utf-8") as fp:
        json.dump(job, fp, indent=2)

def find_uploaded_video_path(video_id: str) -> Optional[str]:
    for fn in os.listdir(Config.UPLOAD_DIR):
        if fn.endswith(".json"):
            continue
        stem, _ = os.path.splitext(fn)
        if stem == video_id:
            return os.path.join(Config.UPLOAD_DIR, fn)
    return None


# ---------------- In-process job runner ----------------

EXECUTOR = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

# Initialize performance monitoring
timeout_tracker.policy = TimeoutPolicy(
    extract_timeout_sec=Config.JOB_TIMEOUT_EXTRACT_SEC,
    compare_timeout_sec=Config.JOB_TIMEOUT_COMPARE_SEC,
)
queue_manager.max_queue_depth = Config.MAX_QUEUE_DEPTH
queue_manager.max_concurrent = Config.MAX_CONCURRENT_JOBS


def run_extract_job(job_id: str):
    job = load_job(job_id)
    try:
        # Check timeout at start
        timeout_tracker.start_job(job_id)
        queue_manager.update_job_status(job_id, "processing")
        
        job["status"] = "processing"
        job["progress"] = 5
        save_job(job)

        video_id = job["video_id"]
        vid_path = find_uploaded_video_path(video_id)
        if not vid_path:
            raise FileNotFoundError(f"upload video not found for {video_id}")

        job["progress"] = 15
        save_job(job)

        # ensure FPS (may be no-op if already correct)
        norm_path = ensure_fps(vid_path, Config.TARGET_FPS)

        job["progress"] = 30
        save_job(job)

        seq = extract_coco17_sequence(norm_path, target_fps=Config.TARGET_FPS)

        job["progress"] = 70
        save_job(job)
        
        # Check timeout during processing
        if timeout_tracker.is_timed_out(job_id, "extract"):
            raise TimeoutError(f"Extract job exceeded {Config.JOB_TIMEOUT_EXTRACT_SEC}s timeout")

        # normalize for DTW/align
        norm = normalize_sequence_hip(seq["kpts"], seq["conf"])

        job["progress"] = 85
        save_job(job)

        out_dir = os.path.join(Config.NORMALIZED_DIR, job_id)
        os.makedirs(out_dir, exist_ok=True)

        # Save BOTH normalized and raw so DTW and ST-GCN each get best input
        save_npz(
            os.path.join(out_dir, "keypoints.npz"),
            kpts=norm["kpts_norm"],      # normalized
            conf=seq["conf"],
            kpts_raw=seq["kpts"],        # raw
        )

        save_json(os.path.join(out_dir, "meta.json"), {
            "job_id": job_id,
            "video_id": video_id,
            "fps": seq["fps"],
            "frames": int(seq["kpts"].shape[0]),
            "pipeline_version": "v1_extract_norm_localqueue",
            "notes": ["COCO-17", "hip-normalized", "confidence-kept", "raw-kept-for-stgcn"]
        })

        job["status"] = "done"
        job["progress"] = 100
        job["artifacts"] = {
            "keypoints": f"/artifacts/{job_id}/keypoints.npz",
            "meta": f"/artifacts/{job_id}/meta.json",
            "preview": f"/preview/{job_id}",
        }
        save_job(job)
        
        # Cleanup job tracking
        queue_manager.update_job_status(job_id, "done")
        timeout_tracker.finish_job(job_id)

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["trace"] = traceback.format_exc()
        save_job(job)
        queue_manager.update_job_status(job_id, "failed")
        timeout_tracker.finish_job(job_id)
        raise


def run_compare_job(job_id: str):
    job = load_job(job_id)
    try:
        # Track job start time
        timeout_tracker.start_job(job_id)
        queue_manager.update_job_status(job_id, "processing")
        
        job["status"] = "processing"
        job["progress"] = 10
        save_job(job)

        ref_job_id = job["ref_job_id"]
        user_job_id = job["user_job_id"]
        max_shift_frames = int(job.get("max_shift_frames", 90))

        ref_npz = os.path.join(Config.NORMALIZED_DIR, ref_job_id, "keypoints.npz")
        usr_npz = os.path.join(Config.NORMALIZED_DIR, user_job_id, "keypoints.npz")
        if not os.path.exists(ref_npz) or not os.path.exists(usr_npz):
            raise FileNotFoundError("Missing extracted keypoints. Run extract jobs first.")

        job["progress"] = 30
        save_job(job)

        ref = np.load(ref_npz)
        usr = np.load(usr_npz)

        # normalized (DTW/align)
        k_ref_norm = ref["kpts"].astype("float32")
        c_ref = ref["conf"].astype("float32")
        k_usr_norm = usr["kpts"].astype("float32")
        c_usr = usr["conf"].astype("float32")

        # raw (ST-GCN) - use memory profiling context
        k_ref_raw = ref["kpts_raw"].astype("float32") if "kpts_raw" in ref else k_ref_norm
        k_usr_raw = usr["kpts_raw"].astype("float32") if "kpts_raw" in usr else k_usr_norm

        job["progress"] = 60
        save_job(job)
        
        # Check timeout before expensive comparison
        if timeout_tracker.is_timed_out(job_id, "compare"):
            raise TimeoutError(f"Compare job exceeded {Config.JOB_TIMEOUT_COMPARE_SEC}s timeout")

        # Profile memory during ST-GCN embedding in compare_sequences
        with memory_profile_context("compare_sequences", Config.STGCN_MEMORY_LIMIT_MB):
            scores = compare_sequences(
                k_ref_norm, c_ref,
                k_usr_norm, c_usr,
                max_shift=max_shift_frames,
                k_ref_raw=k_ref_raw,
                k_usr_raw=k_usr_raw,
            )

        out_dir = os.path.join(Config.NORMALIZED_DIR, job_id)
        os.makedirs(out_dir, exist_ok=True)
        save_json(os.path.join(out_dir, "scores.json"), scores)

        job["status"] = "done"
        job["progress"] = 100
        job["artifacts"] = {"scores": f"/compare/{job_id}"}
        save_job(job)
        
        # Cleanup job tracking
        queue_manager.update_job_status(job_id, "done")
        timeout_tracker.finish_job(job_id)

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["trace"] = traceback.format_exc()
        save_job(job)
        queue_manager.update_job_status(job_id, "failed")
        timeout_tracker.finish_job(job_id)
        raise


# ---------------- Flask app ----------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024

app.config["CORS_HEADERS"] = "Content-Type"
# Accept requests from the dev frontend (vite) on ports 3000 and 3001 (localhost)
CORS(app, resources={r"/*": {"origins": [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]}})

ensure_dirs()


@app.get("/health")
def health():
    stats = queue_manager.get_stats()
    sys_info = system_monitor.get_process_info()
    return jsonify({
        "ok": True,
        "queue_stats": {
            "queued": stats.queued_count,
            "processing": stats.processing_count,
            "completed": stats.completed_count,
            "failed": stats.failed_count,
            "capacity_ratio": stats.capacity_ratio,
        },
        "system": {
            "rss_mb": sys_info["rss_mb"],
            "num_threads": sys_info["num_threads"],
        }
    })


@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    video_id = str(uuid.uuid4())
    ext = os.path.splitext(f.filename)[1].lower() or ".mp4"
    out_path = os.path.join(Config.UPLOAD_DIR, f"{video_id}{ext}")
    f.save(out_path)

    meta = {
        "video_id": video_id,
        "filename": f.filename,
        "stored_as": os.path.basename(out_path),
        "uploaded_at": int(time.time()),
        "kind": request.form.get("kind"),
    }
    with open(os.path.join(Config.UPLOAD_DIR, f"{video_id}.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2)

    return jsonify({"video_id": video_id})


@app.post("/jobs/extract")
def create_extract_job():
    data = request.get_json(force=True)
    video_id = data.get("video_id")
    if not video_id:
        return jsonify({"error": "video_id required"}), 400

    vid_path = find_uploaded_video_path(video_id)
    if not vid_path:
        return jsonify({"error": "uploaded video not found"}), 404

    # Check queue depth
    if not queue_manager.register_job(None):  # temp check
        queue_stats = queue_manager.get_stats()
        return jsonify({
            "error": "queue full",
            "queue_stats": {
                "queued": queue_stats.queued_count,
                "processing": queue_stats.processing_count,
            }
        }), 429  # HTTP 429 Too Many Requests

    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "type": "extract",
        "video_id": video_id,
        "status": "queued",
        "progress": 0,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    save_job(payload)
    queue_manager.register_job(job_id, "queued")

    EXECUTOR.submit(run_extract_job, job_id)
    return jsonify({"job_id": job_id})


@app.post("/jobs/compare")
def create_compare_job():
    data = request.get_json(force=True)
    ref_job_id = data.get("ref_job_id")
    user_job_id = data.get("user_job_id")
    max_shift_frames = int(data.get("max_shift_frames", 90))

    if not ref_job_id or not user_job_id:
        return jsonify({"error": "ref_job_id and user_job_id required"}), 400

    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "type": "compare",
        "ref_job_id": ref_job_id,
        "user_job_id": user_job_id,
        "max_shift_frames": max_shift_frames,
        "status": "queued",
        "progress": 0,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    save_job(payload)

    EXECUTOR.submit(run_compare_job, job_id)
    return jsonify({"job_id": job_id})


@app.get("/jobs/<job_id>")
def get_job(job_id):
    p = job_file(job_id)
    if not os.path.exists(p):
        return jsonify({"error": "job not found"}), 404
    return jsonify(load_job(job_id))


@app.get("/preview/<job_id>")
def preview(job_id):
    base = os.path.join(Config.NORMALIZED_DIR, job_id)
    npz_path = os.path.join(base, "keypoints.npz")
    if not os.path.exists(npz_path):
        return jsonify({"error": "not ready"}), 404

    data = np.load(npz_path)
    kpts = data["kpts"].astype("float32")
    conf = data["conf"].astype("float32")

    max_frames = 6000
    if kpts.shape[0] > max_frames:
        step = int(np.ceil(kpts.shape[0] / max_frames))
        kpts = kpts[::step]
        conf = conf[::step]

    return jsonify({"frames": int(kpts.shape[0]), "kpts": kpts.tolist(), "conf": conf.tolist()})


@app.get("/compare/<job_id>")
def compare_result(job_id):
    base = os.path.join(Config.NORMALIZED_DIR, job_id)
    scores_path = os.path.join(base, "scores.json")
    if not os.path.exists(scores_path):
        return jsonify({"error": "not ready"}), 404
    with open(scores_path, "r", encoding="utf-8") as fp:
        return jsonify(json.load(fp))


@app.get('/jobs/<job_id>/verdict')
def job_verdict(job_id):
    """Generate a human-friendly verdict for a compare job using the LLM.
    Expects that `scores.json` exists under normalized/<job_id>/scores.json
    """
    base = os.path.join(Config.NORMALIZED_DIR, job_id)
    scores_path = os.path.join(base, "scores.json")
    if not os.path.exists(scores_path):
        return jsonify({"error": "not ready"}), 404
    with open(scores_path, "r", encoding="utf-8") as fp:
        compare_res = json.load(fp)

    # Provide two modes: quick (default) and deep.
    # - quick: return a fast heuristic verdict immediately and ensure a background
    #   deep LLM run is scheduled to compute the full verdict.
    # - deep: if a deep verdict is ready, return it; otherwise return quick with
    #   a flag indicating deep is pending.
    mode = request.args.get("mode") or "quick"

    base = os.path.join(Config.NORMALIZED_DIR, job_id)
    quick_path = os.path.join(base, "verdict_quick.json")
    deep_path = os.path.join(base, "verdict_deep.json")
    running_flag = os.path.join(base, "verdict_in_progress")

    # Helper to compute & write quick heuristic
    def _write_quick(metrics):
        try:
            from services.llm import _heuristic_verdict, _summarize_metrics_full

            h = _heuristic_verdict(metrics)
            h["source"] = h.get("source", "heuristic")
            # remove default quick-verdict heading; don't propagate a generic note
            if "note" not in h or not h.get("note"):
                h.pop("note", None)
            tmp = quick_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(h, fp, ensure_ascii=False, indent=2)
            os.replace(tmp, quick_path)
        except Exception:
            pass

    # Background worker to compute deep verdict and persist it
    def _background_deep_run(compare_res_local):
        try:
            # create running flag
            with open(running_flag, "w", encoding="utf-8"):
                pass
            from services.llm import generate_deep_verdict_stepwise, _summarize_metrics_full

            # compute deep verdict stepwise (writes status + final into normalized dir)
            generate_deep_verdict_stepwise(compare_res_local, out_dir=base)
        except Exception as e:
            # on failure, persist an error object so frontend can surface it
            try:
                err_obj = {"error": "deep_verdict_failed", "note": str(e), "source": "internal"}
                tmp = deep_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fp:
                    json.dump(err_obj, fp, ensure_ascii=False, indent=2)
                os.replace(tmp, deep_path)
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(running_flag):
                    os.remove(running_flag)
            except Exception:
                pass

    # Summarize metrics for heuristic use
    try:
        from services.llm import _summarize_metrics_full

        metrics = _summarize_metrics_full(compare_res)
    except Exception:
        metrics = {}

    # Ensure quick verdict exists (compute and persist if missing)
    if not os.path.exists(quick_path):
        _write_quick(metrics)

    deep_status_path = os.path.join(base, "verdict_deep_status.json")
    # If deep requested and ready, return final deep verdict
    if mode == "deep" and os.path.exists(deep_path):
        try:
            with open(deep_path, "r", encoding="utf-8") as fp:
                d = json.load(fp)
                # normalize final deep response to include status/progress for frontend
                if isinstance(d, dict):
                    d = d.copy()
                    d["status"] = d.get("status", "done")
                    d["progress"] = int(d.get("progress", 100))
                return jsonify(d)
        except Exception:
            pass

    # If deep requested and currently running, return the status partials if available
    if mode == "deep" and os.path.exists(running_flag):
        try:
            if os.path.exists(deep_status_path):
                with open(deep_status_path, "r", encoding="utf-8") as fp:
                    return jsonify(json.load(fp))
        except Exception:
            pass

    # If deep not ready, ensure background job is running (start if not).
    # Clean up stale running flag files older than a threshold to avoid deadlock.
    try:
        STALE_SEC = getattr(Config, "VERDICT_STALE_SEC", 1800)
        if os.path.exists(running_flag):
            try:
                mtime = os.path.getmtime(running_flag)
                if (time.time() - mtime) > float(STALE_SEC):
                    try:
                        os.remove(running_flag)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    if not os.path.exists(running_flag) and not os.path.exists(deep_path):
        try:
            import threading

            t = threading.Thread(target=_background_deep_run, args=(compare_res,), daemon=True)
            t.start()
        except Exception:
            pass

    # Return quick verdict (and indicate deep pending when requested)
    try:
        with open(quick_path, "r", encoding="utf-8") as fp:
            q = json.load(fp)
    except Exception:
        q = {"error": "quick verdict not available"}

    if mode == "deep":
        q = q.copy()
        q["deep_ready"] = os.path.exists(deep_path)
        if not q.get("note"):
            q["note"] = "Deep verdict pending"

    return jsonify(q)


@app.get("/artifacts/<job_id>/<name>")
def get_artifact(job_id, name):
    base = os.path.join(Config.NORMALIZED_DIR, job_id)
    fpath = os.path.join(base, name)
    if not os.path.exists(fpath):
        return jsonify({"error": "artifact not found"}), 404
    return send_file(fpath, as_attachment=True)


# ============================================================================
# PERFORMANCE & MONITORING ENDPOINTS
# ============================================================================

@app.get("/monitor/queue")
def monitor_queue():
    """Get detailed queue statistics and system status."""
    try:
        stats = queue_manager.get_stats()
        sys_info = system_monitor.get_process_info()
        disk_usage = system_monitor.get_disk_usage(Config.STORAGE_ROOT)
        
        return jsonify({
            "timestamp": int(time.time()),
            "queue": {
                "queued": stats.queued_count,
                "processing": stats.processing_count,
                "completed": stats.completed_count,
                "failed": stats.failed_count,
                "capacity_ratio": stats.capacity_ratio,
                "max_depth": Config.MAX_QUEUE_DEPTH,
            },
            "system": {
                "process": {
                    "pid": sys_info["pid"],
                    "rss_mb": round(sys_info["rss_mb"], 1),
                    "vms_mb": round(sys_info["vms_mb"], 1),
                    "threads": sys_info["num_threads"],
                    "cpu_percent": round(sys_info["cpu_percent"], 1),
                },
                "disk": {
                    "total_gb": round(disk_usage["total_gb"], 1),
                    "used_gb": round(disk_usage["used_gb"], 1),
                    "free_gb": round(disk_usage["free_gb"], 1),
                    "percent": disk_usage["percent"],
                },
            }
        })
    except Exception as e:
        print(f"Error in /monitor/queue: {e}")
        print(traceback.format_exc())
        return jsonify({
            "error": str(e),
            "details": traceback.format_exc()
        }), 500


@app.post("/upload-batch")
def upload_batch():
    """
    Upload multiple videos at once and create extract jobs for each.
    Request: multipart/form-data with multiple 'files' fields.
    """
    if "files" not in request.files:
        return jsonify({"error": "files missing"}), 400
    
    files = request.files.getlist("files")
    if not files or len(files) > Config.MAX_BATCH_SIZE:
        return jsonify({
            "error": f"provide 1-{Config.MAX_BATCH_SIZE} files"
        }), 400
    
    batch_id = str(uuid.uuid4())
    batch_manager.create_batch(batch_id, [])
    
    job_ids = []
    for f in files:
        if not f.filename:
            continue
        
        try:
            # Save video
            video_id = str(uuid.uuid4())
            ext = os.path.splitext(f.filename)[1].lower() or ".mp4"
            out_path = os.path.join(Config.UPLOAD_DIR, f"{video_id}{ext}")
            f.save(out_path)
            
            # Save metadata
            meta = {
                "video_id": video_id,
                "filename": f.filename,
                "stored_as": os.path.basename(out_path),
                "uploaded_at": int(time.time()),
                "batch_id": batch_id,
            }
            with open(os.path.join(Config.UPLOAD_DIR, f"{video_id}.json"), "w", encoding="utf-8") as fp:
                json.dump(meta, fp, indent=2)
            
            # Create extract job (respecting concurrency limits)
            if queue_manager.register_job(None):
                job_id = str(uuid.uuid4())
                payload = {
                    "job_id": job_id,
                    "type": "extract",
                    "video_id": video_id,
                    "batch_id": batch_id,
                    "status": "queued",
                    "progress": 0,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
                save_job(payload)
                queue_manager.register_job(job_id, "queued")
                batch_manager.update_batch_job(batch_id, video_id, job_id)
                job_ids.append(job_id)
                
                # Submit with controlled concurrency
                EXECUTOR.submit(run_extract_job, job_id)
        except Exception as e:
            batch_manager.mark_completed(batch_id, video_id, success=False)
    
    return jsonify({
        "batch_id": batch_id,
        "submitted_jobs": len(job_ids),
        "job_ids": job_ids,
    })


@app.get("/batch/<batch_id>")
def get_batch_status(batch_id):
    """Get progress of a batch upload/extraction."""
    status = batch_manager.get_batch_status(batch_id)
    if not status:
        return jsonify({"error": "batch not found"}), 404
    return jsonify(status)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False, threaded=True)
