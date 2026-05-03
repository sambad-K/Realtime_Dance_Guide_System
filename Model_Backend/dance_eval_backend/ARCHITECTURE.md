# Performance Optimization - Visual Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Dance Evaluation Backend                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Browser    │  │   API Call   │  │   Monitor    │  │  Batch Job   │
│   (React)    │  │   (Client)   │  │  (Dashboard) │  │  (Upload)    │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
      ↓                ↓                    ↓                ↓

        ┌─────────────────── Flask App ─────────────────┐
        │   app.py (379 lines, enhanced with monitoring) │
        └──────────────────────────────────────────────┘
              ↓          ↓           ↓          ↓
        ┌─────┴──┬──────┴──┬────────┴──┬──────┴────┐
        │         │        │           │          │
    ┌───▼──┐ ┌───▼──┐ ┌───▼──┐ ┌────▼────┐ ┌──▼────┐
    │Upload│ │Extract│ │Compare│ │Artifacts│ │Monitor│
    └──────┘ └──────┘ └──────┘ └─────────┘ └───────┘
        │         │        │           │          │
        └─────────┴────────┴───────────┴──────────┘
              ↓
    ┌─────────────────────────────────────────────┐
    │  services/performance.py (520 lines, NEW)    │
    │                                              │
    │  ┌──────────────────────────────────────┐   │
    │  │  QueueManager                        │   │
    │  │  - register_job()                    │   │
    │  │  - update_job_status()               │   │
    │  │  - get_stats() → {queued, processing}│   │
    │  └──────────────────────────────────────┘   │
    │                                              │
    │  ┌──────────────────────────────────────┐   │
    │  │  TimeoutTracker                      │   │
    │  │  - start_job()                       │   │
    │  │  - is_timed_out()                    │   │
    │  │  - finish_job()                      │   │
    │  └──────────────────────────────────────┘   │
    │                                              │
    │  ┌──────────────────────────────────────┐   │
    │  │  MemoryMonitor                       │   │
    │  │  - snapshot()                        │   │
    │  │  - get_delta()                       │   │
    │  │  - is_exceeded()                     │   │
    │  └──────────────────────────────────────┘   │
    │                                              │
    │  ┌──────────────────────────────────────┐   │
    │  │  BatchJobManager                     │   │
    │  │  - create_batch()                    │   │
    │  │  - get_batch_status()                │   │
    │  │  - mark_completed()                  │   │
    │  └──────────────────────────────────────┘   │
    │                                              │
    │  ┌──────────────────────────────────────┐   │
    │  │  SystemMonitor                       │   │
    │  │  - get_process_info()                │   │
    │  │  - get_disk_usage()                  │   │
    │  │  - get_cpu_percent()                 │   │
    │  └──────────────────────────────────────┘   │
    │                                              │
    │  ┌──────────────────────────────────────┐   │
    │  │  Decorators/Context Managers         │   │
    │  │  - @profile_stgcn_memory             │   │
    │  │  - memory_profile_context()          │   │
    │  └──────────────────────────────────────┘   │
    └─────────────────────────────────────────────┘
              ↓              ↓              ↓
        ┌─────────┐   ┌──────────┐   ┌───────────┐
        │  Pose   │   │ Normalize│   │  Compare  │
        │ Extract │   │    &     │   │   &       │
        │         │   │  Align   │   │  Score    │
        └─────────┘   └──────────┘   └───────────┘
              ↓              ↓              ↓
        ┌─────────────────────────────────────────┐
        │           Keypoints Storage              │
        │  storage/normalized/{job_id}/            │
        │   - keypoints.npz                        │
        │   - meta.json                            │
        │   - scores.json                          │
        └─────────────────────────────────────────┘
```

---

## Data Flow: Job Lifecycle with Monitoring

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT UPLOADS VIDEO                         │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ POST /upload-batch (optional, for multiple videos)              │
│                                                                  │
│ QueueManager.register_job(job_id)  ← Check capacity             │
│   ↓ If queue full: return HTTP 429                              │
│   ↓ If space: register and proceed                              │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ POST /jobs/extract                                              │
│                                                                  │
│ 1. register_job(job_id, "queued")                               │
│ 2. Submit to ThreadPoolExecutor                                 │
│ 3. Client polls: GET /jobs/{job_id}                             │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ EXTRACT JOB RUNNING (in background thread)                      │
│                                                                  │
│ timeout_tracker.start_job(job_id)                               │
│   ├─ Record job start time                                      │
│   │                                                              │
│ queue_manager.update_job_status(job_id, "processing")           │
│   ├─ Increment processing counter                               │
│   │                                                              │
│ [extract_coco17_sequence()]                                      │
│   ├─ Extract skeleton keypoints from video                       │
│   │                                                              │
│ [normalize_sequence_hip()]                                       │
│   ├─ Normalize for DTW alignment                                │
│   │                                                              │
│ if timeout_tracker.is_timed_out(job_id, "extract"):             │
│   ├─ Check elapsed time vs. JOB_TIMEOUT_EXTRACT_SEC             │
│   ├─ If exceeded: raise TimeoutError                            │
│   ├─ Job marked as "failed" with error message                  │
│   │                                                              │
│ save_npz(), save_json()                                          │
│   ├─ Save normalized and raw keypoints                          │
│   ├─ Save metadata (fps, frames, pipeline version)              │
│   │                                                              │
│ queue_manager.update_job_status(job_id, "done")                 │
│   ├─ Decrement processing, increment completed                  │
│   │                                                              │
│ timeout_tracker.finish_job(job_id)                              │
│   └─ Remove from timeout tracking                               │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ POST /jobs/compare                                              │
│                                                                  │
│ 1. Load reference and user keypoints                            │
│ 2. register_job() & start timeout tracking                      │
│ 3. Submit to ThreadPoolExecutor                                 │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ COMPARE JOB RUNNING                                             │
│                                                                  │
│ timeout_tracker.start_job(job_id)                               │
│   ├─ Record job start time                                      │
│   │                                                              │
│ if timeout_tracker.is_timed_out(job_id, "compare"):             │
│   ├─ Check elapsed time vs. JOB_TIMEOUT_COMPARE_SEC             │
│   ├─ If exceeded: raise TimeoutError                            │
│   │                                                              │
│ with memory_profile_context(...) as profiler:                   │
│   ├─ [compare_sequences()]  (includes ST-GCN embedding)         │
│   │                                                              │
│   ├─ MemoryMonitor.snapshot()  ← Before ST-GCN                 │
│   ├─ [stgcn_embed_sequence_windows()]                           │
│   ├─ MemoryMonitor.snapshot()  ← After ST-GCN                  │
│   ├─ Compute delta, warn if > STGCN_MEMORY_LIMIT_MB             │
│   │                                                              │
│ save_json(scores.json)                                          │
│   └─ Save DTW + ST-GCN scoring results                          │
│                                                                  │
│ queue_manager.update_job_status(job_id, "done")                 │
│ timeout_tracker.finish_job(job_id)                              │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT RETRIEVES RESULTS                                        │
│                                                                  │
│ GET /compare/{job_id}  → Returns scores & alignment             │
│ GET /preview/{job_id}  → Returns keypoints for visualization    │
│ GET /monitor/queue     → System stats for dashboard             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Hierarchy

```
┌────────────────────────────────────────────────────────────────┐
│               ENVIRONMENT VARIABLES                            │
│              (set before starting app.py)                      │
└────────────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────────────┐
│              config.py                                         │
│  Reads env vars with defaults:                                 │
│                                                                │
│  MAX_QUEUE_DEPTH              (default: 100)                  │
│  MAX_CONCURRENT_JOBS          (default: 4)                    │
│  JOB_TIMEOUT_EXTRACT_SEC      (default: 3600)                 │
│  JOB_TIMEOUT_COMPARE_SEC      (default: 600)                  │
│  STGCN_MEMORY_LIMIT_MB        (default: 2048)                 │
│  PROCESS_MEMORY_LIMIT_MB      (default: 4096)                 │
│  MAX_BATCH_SIZE               (default: 10)                   │
│  BATCH_PARALLEL_EXTRACTS      (default: 2)                    │
└────────────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────────────┐
│              app.py Initialization                             │
│                                                                │
│  # Configure queue manager with limits                         │
│  queue_manager.max_queue_depth = Config.MAX_QUEUE_DEPTH       │
│  queue_manager.max_concurrent = Config.MAX_CONCURRENT_JOBS    │
│                                                                │
│  # Configure timeout policy                                   │
│  timeout_tracker.policy = TimeoutPolicy(                       │
│    extract_timeout_sec=Config.JOB_TIMEOUT_EXTRACT_SEC,        │
│    compare_timeout_sec=Config.JOB_TIMEOUT_COMPARE_SEC,        │
│  )                                                             │
│                                                                │
│  # Memory profiling threshold                                 │
│  memory_profile_context(...,                                  │
│    threshold_mb=Config.STGCN_MEMORY_LIMIT_MB)                │
└────────────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────────────┐
│              Runtime Behavior                                  │
│                                                                │
│  During job execution, all limits are enforced:               │
│  - Queue depth checked before creating new jobs               │
│  - Job timeouts checked periodically                          │
│  - Memory profiling wraps ST-GCN operations                   │
│  - Concurrent jobs limited by MAX_CONCURRENT_JOBS             │
└────────────────────────────────────────────────────────────────┘
```

---

## Concurrency & Resource Limits

```
┌────────────────────────────────────────────────────────────────┐
│                 MAX_WORKERS = 2 (Thread Pool)                  │
├─────────────┬──────────────────┬──────────────────┬────────────┤
│  Worker 1   │   Worker 2       │  Worker 3        │ Queued     │
│  Executing  │   Executing      │  (if available)  │ Jobs       │
│  Extract    │   Compare        │                  │            │
│  Job #1     │   Job #2         │                  │ Job #3     │
│             │                  │                  │ Job #4     │
│             │                  │                  │ Job #5     │
└─────────────┴──────────────────┴──────────────────┴────────────┘
                ↓
    ┌───────────────────────────────────────┐
    │     QueueManager Tracking             │
    │                                       │
    │  processing_count = 2                 │
    │  queued_count = 3                     │
    │  completed_count = 47                 │
    │  failed_count = 1                     │
    │  capacity_ratio = 0.05 (5% full)      │
    │                                       │
    │  When queued = MAX_QUEUE_DEPTH:       │
    │  → Return HTTP 429 to new requests    │
    │                                       │
    │  When processing = MAX_CONCURRENT:    │
    │  → Queue new jobs until slot free     │
    └───────────────────────────────────────┘
                ↓
    ┌───────────────────────────────────────┐
    │  TimeoutTracker Monitoring            │
    │                                       │
    │  Job #1 start: 14:00:00               │
    │  Timeout check: 14:15:00 (elapsed 15m)│
    │  Limit: 3600s (60m) → OK              │
    │                                       │
    │  Job #2 start: 14:05:00               │
    │  Timeout check: 14:11:00 (elapsed 6m) │
    │  Limit: 600s (10m) → 4m remaining    │
    │                                       │
    │  If elapsed > limit: FAILED           │
    └───────────────────────────────────────┘
                ↓
    ┌───────────────────────────────────────┐
    │  MemoryMonitor (for ST-GCN)           │
    │                                       │
    │  Before ST-GCN: 512MB                 │
    │  During ST-GCN: 1800MB (peak)         │
    │  After ST-GCN: 600MB                  │
    │  Delta: +88MB (small increase)        │
    │                                       │
    │  Limit: 2048MB → OK                   │
    │  If exceeded → Log warning             │
    └───────────────────────────────────────┘
```

---

## Response Flow

```
CLIENT REQUEST
    ↓
┌─────────────────────────────┐
│ Check Queue Capacity        │
└─────────────────────────────┘
    │
    ├─ Queue full? → HTTP 429
    │
    └─ Queue OK? → Proceed
        ↓
    ┌─────────────────────────────┐
    │ Register Job                │
    └─────────────────────────────┘
        ↓
    ┌─────────────────────────────┐
    │ Submit to Thread Pool       │
    └─────────────────────────────┘
        ↓
    ┌─────────────────────────────┐
    │ Return HTTP 200             │
    │ { "job_id": "..." }         │
    └─────────────────────────────┘
        ↓
    CLIENT POLLS: GET /jobs/{job_id}
        ↓
    ┌─────────────────────────────────────────────────────┐
    │ Job Status Response                                 │
    │                                                     │
    │ Status: "queued"       → Still waiting              │
    │ Status: "processing"   → Running (progress: X%)     │
    │ Status: "done"         → Success (artifacts ready)  │
    │ Status: "failed"       → Error (see error message)  │
    │                                                     │
    │ On Timeout:                                         │
    │ Status: "failed"                                    │
    │ Error: "Extract exceeded 3600s timeout"             │
    │                                                     │
    │ On Memory Exceeded:                                 │
    │ Status: "done" (still completes)                    │
    │ Error: "Memory threshold exceeded"                  │
    └─────────────────────────────────────────────────────┘
        ↓
    RESULTS READY
        ↓
    GET /compare/{job_id}  → Final scores
    GET /preview/{job_id}  → Keypoints
    GET /artifacts/{job_id}/{name} → Download files
```

---

## Thread Safety Diagram

```
┌────────────────────────────────────────────────────────┐
│          Shared State (Protected by Locks)             │
├────────────────────────────────────────────────────────┤
│                                                        │
│  QueueManager.lock                                    │
│  ├─ job_states: Dict[str, str]                       │
│  │  {                                                 │
│  │    "job-001": "processing",                        │
│  │    "job-002": "queued",                            │
│  │    "job-003": "done",                              │
│  │  }                                                 │
│  └─ acquire() before read/write, release() after     │
│                                                        │
│  TimeoutTracker.lock                                 │
│  ├─ job_start_times: Dict[str, float]                │
│  │  {                                                 │
│  │    "job-001": 1703337600.5,                        │
│  │    "job-002": 1703337605.3,                        │
│  │  }                                                 │
│  └─ acquire() before read/write, release() after     │
│                                                        │
│  BatchJobManager.lock                                │
│  ├─ batches: Dict[str, BatchJob]                     │
│  └─ acquire() before read/write, release() after     │
│                                                        │
└────────────────────────────────────────────────────────┘

Example Thread-Safe Operation:

   Thread A                    Thread B
     ↓                           ↓
  acquire(lock)              waiting...
  update job_states
  release(lock)
                              acquire(lock)
                              read job_states
                              release(lock)

Result: Operations are serialized, no race conditions
```

---

## Monitoring Visualization

```
┌───────────────────────────────────────────────────────────────┐
│          Real-Time Dashboard (GET /monitor/queue)             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  QUEUE STATUS                  SYSTEM RESOURCES              │
│  ┌─────────────────┐           ┌───────────────────┐        │
│  │ Queued:     5   │           │ Memory:  512 MB   │        │
│  │ Processing: 2   │           │ Threads: 12       │        │
│  │ Completed:  47  │           │ CPU:     45%      │        │
│  │ Failed:     1   │           │ Disk:    50% used │        │
│  │ Capacity:   7%  │           │                   │        │
│  └─────────────────┘           └───────────────────┘        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ QUEUE DEPTH METER                                   │    │
│  │ [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 7/100         │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ JOB TIMELINE                                        │    │
│  │ Extract-001 [████████████▓░░░░░░░░░░░░] 60%        │    │
│  │ Compare-002 [██████████████████░░░░░░░░] 75%        │    │
│  │ Extract-003 [░░░░░░░░░░░░░░░░░░░░░░░░░░] 0% (Q)   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  LAST UPDATED: 14:32:45                                      │
└───────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Production Server                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Flask App (1 instance, threaded)                   │ │
│  │ - Listens on 127.0.0.1:8000                        │ │
│  │ - MAX_WORKERS = 4 (ThreadPoolExecutor)             │ │
│  └────────────────────────────────────────────────────┘ │
│                   ↓                                      │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Performance Module (in-process)                    │ │
│  │ - QueueManager (thread-safe)                       │ │
│  │ - TimeoutTracker (thread-safe)                     │ │
│  │ - MemoryMonitor (thread-safe)                      │ │
│  │ - BatchJobManager (thread-safe)                    │ │
│  │ - SystemMonitor (thread-safe)                      │ │
│  └────────────────────────────────────────────────────┘ │
│                   ↓                                      │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Storage (Local Filesystem)                         │ │
│  │ - storage/uploads/                                 │ │
│  │ - storage/normalized/                              │ │
│  │ - storage/jobs/                                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Optional Future: Add Redis for distributed queue       │
│  Optional Future: Add Prometheus for metrics export     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

**This architecture supports:**
- ✅ Real-time queue monitoring
- ✅ Job lifecycle management
- ✅ Resource limit enforcement
- ✅ Memory leak detection
- ✅ Batch job processing
- ✅ Graceful backpressure (HTTP 429)
- ✅ Thread-safe operations
- ✅ Production deployment
