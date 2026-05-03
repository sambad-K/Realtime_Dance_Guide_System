# Performance Optimization & Resource Management Guide

## Overview
This document explains the performance optimizations and resource management features added to the Dance Evaluation backend. These features help manage queue depth, enforce job timeouts, profile memory usage, and enable batch processing.

---

## 1. Queue Depth Monitoring

### What It Does
- Tracks the number of queued, processing, completed, and failed jobs in real-time
- Enforces maximum queue depth and concurrent job limits
- Prevents server overload by rejecting jobs when queue is full

### Configuration
In `config.py`:
```python
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "100"))      # Max jobs in queue
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))  # Max running jobs
```

### Usage
The queue manager automatically tracks all jobs. When creating a new job, it checks:
```
if not queue_manager.register_job(job_id, "queued"):
    return error 429 (Too Many Requests)
```

### API Endpoints
- **GET `/health`** – Quick health check with queue stats
- **GET `/monitor/queue`** – Detailed queue and system monitoring

Example `/monitor/queue` response:
```json
{
  "timestamp": 1703337600,
  "queue": {
    "queued": 5,
    "processing": 2,
    "completed": 47,
    "failed": 1,
    "capacity_ratio": 0.07,
    "max_depth": 100
  },
  "system": {
    "process": {
      "rss_mb": 512.5,
      "threads": 12,
      "cpu_percent": 45.2
    },
    "disk": {
      "total_gb": 500.0,
      "used_gb": 250.3,
      "free_gb": 249.7,
      "percent": 50.1
    }
  }
}
```

---

## 2. Job Timeout Logic

### What It Does
- Enforces maximum execution time for each job type
- Different timeouts for extract vs. compare operations
- Prevents stuck jobs from consuming resources indefinitely

### Configuration
In `config.py`:
```python
JOB_TIMEOUT_EXTRACT_SEC = int(os.getenv("JOB_TIMEOUT_EXTRACT_SEC", "3600"))  # 1 hour
JOB_TIMEOUT_COMPARE_SEC = int(os.getenv("JOB_TIMEOUT_COMPARE_SEC", "600"))   # 10 min
```

### How It Works
1. **Job Start**: When a job begins, `timeout_tracker.start_job(job_id)` records the start time
2. **Periodic Check**: During processing, `timeout_tracker.is_timed_out(job_id, "extract")` checks elapsed time
3. **Timeout Enforcement**: If timeout exceeded, job raises `TimeoutError` and status set to "failed"
4. **Cleanup**: `timeout_tracker.finish_job(job_id)` removes job from tracking

### Example in Code
```python
def run_extract_job(job_id: str):
    timeout_tracker.start_job(job_id)
    
    # ... processing ...
    
    if timeout_tracker.is_timed_out(job_id, "extract"):
        raise TimeoutError(f"Extract exceeded {Config.JOB_TIMEOUT_EXTRACT_SEC}s")
    
    # ... more processing ...
    
    timeout_tracker.finish_job(job_id)
```

---

## 3. Memory Profiling for ST-GCN Embeddings

### What It Does
- Monitors memory usage before, during, and after ST-GCN embedding operations
- Warns when memory usage exceeds configured thresholds
- Tracks memory delta between snapshots to detect leaks

### Configuration
In `config.py`:
```python
STGCN_MEMORY_LIMIT_MB = int(os.getenv("STGCN_MEMORY_LIMIT_MB", "2048"))  # 2GB
PROCESS_MEMORY_LIMIT_MB = int(os.getenv("PROCESS_MEMORY_LIMIT_MB", "4096"))  # 4GB
```

### Usage Patterns

#### Option 1: Context Manager
```python
from services.performance import memory_profile_context

with memory_profile_context("compare_sequences", threshold_mb=2048) as profiler:
    scores = compare_sequences(k_ref_norm, c_ref, k_usr_norm, c_usr, ...)
    print(f"Warnings: {profiler.warnings}")
    print(f"Peak memory: {profiler.peak_mb:.1f}MB")
```

#### Option 2: Decorator
```python
from services.performance import profile_stgcn_memory

@profile_stgcn_memory
def my_embedding_function(data):
    # Function automatically profiled
    return result
```

### Memory Monitor API
```python
from services.performance import MemoryMonitor

monitor = MemoryMonitor(threshold_mb=2048)
snap1 = monitor.snapshot()  # Take snapshot
snap2 = monitor.snapshot()  # Take another

delta = monitor.get_delta()  # Memory change in MB
exceeded = monitor.is_exceeded()  # Check if over threshold
```

### Integration in app.py
The compare endpoint now profiles the ST-GCN embedding:
```python
with memory_profile_context("compare_sequences", Config.STGCN_MEMORY_LIMIT_MB):
    scores = compare_sequences(...)
```

---

## 4. Batch Upload & Parallel Processing

### What It Does
- Upload multiple videos in one request
- Create extract jobs for all videos with controlled concurrency
- Track batch progress and completion status

### API Endpoints

#### POST `/upload-batch`
Upload multiple videos at once.

**Request:**
```bash
curl -X POST http://localhost:8000/upload-batch \
  -F "files=@video1.mp4" \
  -F "files=@video2.mp4" \
  -F "files=@video3.mp4"
```

**Response:**
```json
{
  "batch_id": "a1b2c3d4-e5f6-...",
  "submitted_jobs": 3,
  "job_ids": [
    "job-1-uuid",
    "job-2-uuid",
    "job-3-uuid"
  ]
}
```

#### GET `/batch/<batch_id>`
Check progress of a batch.

**Response:**
```json
{
  "batch_id": "a1b2c3d4-e5f6-...",
  "total_videos": 3,
  "completed": 1,
  "failed": 0,
  "pending": 2,
  "progress_percent": 33,
  "created_at": 1703337600,
  "elapsed_sec": 45
}
```

### Configuration
In `config.py`:
```python
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "10"))  # Max files per batch
BATCH_PARALLEL_EXTRACTS = int(os.getenv("BATCH_PARALLEL_EXTRACTS", "2"))  # Concurrent extracts
```

### Concurrency Control
Batch jobs respect `MAX_CONCURRENT_JOBS` limit. If queue is full, videos are queued and processed as slots become available.

---

## 5. System Monitoring

### API Endpoints

#### GET `/health` (Enhanced)
Quick health check with queue summary.

**Response:**
```json
{
  "ok": true,
  "queue_stats": {
    "queued": 5,
    "processing": 2,
    "completed": 47,
    "failed": 1,
    "capacity_ratio": 0.07
  },
  "system": {
    "rss_mb": 512.5,
    "num_threads": 12
  }
}
```

#### GET `/monitor/queue` (Detailed)
Full system and queue monitoring.

Returns CPU usage, disk usage, memory, thread count, and queue statistics.

### Programmatic Access

```python
from services.performance import system_monitor, queue_manager

# Get queue stats
stats = queue_manager.get_stats()
print(f"Queued: {stats.queued_count}, Processing: {stats.processing_count}")
print(f"Queue capacity ratio: {stats.capacity_ratio:.1%}")

# Get system info
info = system_monitor.get_process_info()
print(f"Memory: {info['rss_mb']:.1f}MB, Threads: {info['num_threads']}")

# Disk usage
disk = system_monitor.get_disk_usage("./storage")
print(f"Free disk: {disk['free_gb']:.1f}GB ({disk['percent']}% used)")
```

---

## 6. Environment Variables (Quick Reference)

```bash
# Queue management
export MAX_QUEUE_DEPTH=100
export MAX_CONCURRENT_JOBS=4

# Timeouts (seconds)
export JOB_TIMEOUT_EXTRACT_SEC=3600      # 1 hour
export JOB_TIMEOUT_COMPARE_SEC=600       # 10 minutes

# Memory limits (MB)
export STGCN_MEMORY_LIMIT_MB=2048        # 2GB for ST-GCN ops
export PROCESS_MEMORY_LIMIT_MB=4096      # 4GB total process limit

# Batch processing
export MAX_BATCH_SIZE=10
export BATCH_PARALLEL_EXTRACTS=2

# Other
export MAX_WORKERS=2
export TARGET_FPS=30
export MAX_UPLOAD_MB=300
```

---

## 7. Monitoring & Debugging

### Check Queue Status
```bash
curl http://localhost:8000/monitor/queue | jq
```

### Monitor Job Progress
```bash
curl http://localhost:8000/jobs/<job_id> | jq
```

### Monitor Batch Progress
```bash
curl http://localhost:8000/batch/<batch_id> | jq
```

### Memory Profiling Output
When a job exceeds memory threshold, a warning is logged:
```
WARNING: compare_sequences exceeded memory threshold: 2145.3MB > 2048MB
WARNING: compare_sequences memory delta: +512.5MB
```

---

## 8. Performance Tuning Recommendations

### For Small Deployments (1 CPU, 4GB RAM)
```bash
MAX_WORKERS=1
MAX_CONCURRENT_JOBS=1
MAX_QUEUE_DEPTH=20
JOB_TIMEOUT_EXTRACT_SEC=1800
STGCN_MEMORY_LIMIT_MB=1024
MAX_BATCH_SIZE=3
```

### For Medium Deployments (4 CPUs, 16GB RAM)
```bash
MAX_WORKERS=3
MAX_CONCURRENT_JOBS=3
MAX_QUEUE_DEPTH=50
JOB_TIMEOUT_EXTRACT_SEC=3600
STGCN_MEMORY_LIMIT_MB=2048
MAX_BATCH_SIZE=10
```

### For Large Deployments (8+ CPUs, 32GB+ RAM)
```bash
MAX_WORKERS=6
MAX_CONCURRENT_JOBS=6
MAX_QUEUE_DEPTH=100
JOB_TIMEOUT_EXTRACT_SEC=3600
STGCN_MEMORY_LIMIT_MB=4096
MAX_BATCH_SIZE=20
```

---

## 9. Files Modified/Created

| File | Changes |
|------|---------|
| `services/performance.py` | **NEW** – Core performance monitoring module |
| `config.py` | Added performance config parameters |
| `app.py` | Integrated queue, timeout, and memory tracking |
| `requirements.txt` | Added `psutil==6.0.0` dependency |

---

## 10. Error Handling

Jobs that timeout or exceed memory limits are marked as failed with error details:

```json
{
  "job_id": "...",
  "status": "failed",
  "error": "Extract exceeded 3600s timeout",
  "trace": "... full traceback ...",
  "updated_at": 1703337650
}
```

Queue-full errors return HTTP 429:
```json
{
  "error": "queue full",
  "queue_stats": {
    "queued": 100,
    "processing": 4
  }
}
```

---

## Summary

✅ **Queue Depth Monitoring** – Prevents overload via `/monitor/queue`  
✅ **Job Timeouts** – Configurable per job type  
✅ **Memory Profiling** – ST-GCN memory warnings  
✅ **Batch Processing** – Upload and extract multiple videos  
✅ **System Monitoring** – Real-time CPU, disk, memory, thread tracking  

All features are **thread-safe** and integrate seamlessly with the existing Flask app.
