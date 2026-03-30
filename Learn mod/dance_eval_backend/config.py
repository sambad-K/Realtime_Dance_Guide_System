import os
from dotenv import load_dotenv

load_dotenv()
os.environ["FFMPEG_BIN"] = r"C:\ffmpeg\bin\ffmpeg.exe"

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    STORAGE_ROOT = os.path.join(BASE_DIR, "storage")
    UPLOAD_DIR = os.path.join(STORAGE_ROOT, "uploads")
    NORMALIZED_DIR = os.path.join(STORAGE_ROOT, "normalized")
    JOBS_DIR = os.path.join(STORAGE_ROOT, "jobs")

    TARGET_FPS = int(os.getenv("TARGET_FPS", "30"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "300"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))

    # ---- ST-GCN ----
    STGCN_CKPT = os.path.join(BASE_DIR, "checkpoints", "encoder_best.pt")
    STGCN_CKPT_PATH = STGCN_CKPT  # alias for compatibility

    STGCN_T = 100
    STGCN_V = 17
    STGCN_IN_C = 2
    STGCN_LATENT = 256

    STGCN_DEVICE = os.getenv("STGCN_DEVICE", "cpu")

    # ---- PERFORMANCE & RESOURCE LIMITS ----
    MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "100"))
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))

    # Job timeouts (in seconds)
    JOB_TIMEOUT_EXTRACT_SEC = int(os.getenv("JOB_TIMEOUT_EXTRACT_SEC", "3600"))  # 1 hour
    JOB_TIMEOUT_COMPARE_SEC = int(os.getenv("JOB_TIMEOUT_COMPARE_SEC", "600"))   # 10 min

    # Memory limits (in MB)
    STGCN_MEMORY_LIMIT_MB = int(os.getenv("STGCN_MEMORY_LIMIT_MB", "2048"))
    PROCESS_MEMORY_LIMIT_MB = int(os.getenv("PROCESS_MEMORY_LIMIT_MB", "4096"))

    # Batch processing
    MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "10"))
    BATCH_PARALLEL_EXTRACTS = int(os.getenv("BATCH_PARALLEL_EXTRACTS", "2"))

    # Downscale uploaded videos before processing to speed up pose extraction
    DOWN_SCALE_WIDTH = int(os.getenv("DOWN_SCALE_WIDTH", "640"))

    # Enable DTW on ST-GCN window embeddings (more tempo-robust)
    EMBED_DTW_ENABLED = os.getenv("EMBED_DTW_ENABLED", "1") in ("1", "true", "True")

    # Bandwidth (in frames) for banded DTW (Sakoe-Chiba). 0 or less => full DTW
    DTW_BANDWIDTH = int(os.getenv("DTW_BANDWIDTH", "50"))

    # When EMBED_DTW_ENABLED is true, only run embed-DTW if frame-DTW score < this (0-100)
    EMBED_DTW_THRESHOLD = float(os.getenv("EMBED_DTW_THRESHOLD", "60.0"))

    # Small forgiving factor for DTW scoring (0.0 = strict, 0.1 = 10% more forgiving)
    # Increased slightly to reduce harsh penalties from minor noise/tempo jitter.
    DTW_FORGIVENESS = float(os.getenv("DTW_FORGIVENESS", "0.07"))

    # ============================================================
    # ✅ NEW: SMART ST-GCN CALIBRATION (strict + reliable)
    # Goal:
    # - Same/near-same videos stay HIGH (no annoying low scores)
    # - Dissimilar videos stay LOW (no inflated similarity)
    # - Keep core pipeline intact (windowing + strict agg + motion penalty)
    # ============================================================

    # Master switch (compare.py uses this)
    STGCN_SMART_CALIBRATION = os.getenv("STGCN_SMART_CALIBRATION", "1") in ("1", "true", "True")

    # Strict shaping curve:
    # 1.0 = linear, >1 pushes mid values down (stricter), <1 makes forgiving
    # Recommended: 1.4–1.9
    STGCN_CAL_GAMMA = float(os.getenv("STGCN_CAL_GAMMA", "1.6"))

    # Spread penalty: penalizes unstable per-window similarity (common in dissimilar pairs)
    # Higher => more strict for unstable matches. Recommended: 0.25–0.45
    STGCN_CAL_SPREAD_K = float(os.getenv("STGCN_CAL_SPREAD_K", "0.35"))

    # Spread penalty floor: ensures same-video doesn’t get punished too much
    # Recommended: 0.70–0.85
    STGCN_CAL_SPREAD_FLOOR = float(os.getenv("STGCN_CAL_SPREAD_FLOOR", "0.70"))

    # Minimum anchor gap: prevents calibration collapse when anchors are too close
    # Recommended: 0.06–0.12
    STGCN_CAL_MIN_GAP = float(os.getenv("STGCN_CAL_MIN_GAP", "0.08"))

    # Seed for hard-negative shuffle (deterministic calibration)
    STGCN_CAL_SEED = int(os.getenv("STGCN_CAL_SEED", "123"))

    # Optional: Make ST-GCN influence only when clearly good
    # (compare.py uses STGCN_USE_THR; you can add it here for control)
    STGCN_USE_THR = float(os.getenv("STGCN_USE_THR", "0.80"))

    # Optional: Wrongness temporal smoothing (stabilize color flicker)
    WRONGNESS_SMOOTH_WINDOW = int(os.getenv("WRONGNESS_SMOOTH_WINDOW", "5"))

    # Optional: Allow refined DTW acceptance even if checks fail (debug-only)
    FORCE_ACCEPT_REFINED = os.getenv("FORCE_ACCEPT_REFINED", "0") in ("1", "true", "True")
