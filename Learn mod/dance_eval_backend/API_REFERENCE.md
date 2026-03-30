# Dance Evaluation Backend - Complete API Reference

## Overview

Full API documentation for the Dance Evaluation backend with performance monitoring features.

---

## Core Endpoints (Existing)

### 1. Health Check
```
GET /health
```
**Enhanced with queue stats**

**Response (200):**
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

---

### 2. Upload Video
```
POST /upload
Content-Type: multipart/form-data
```

**Parameters:**
- `file` (required) – Video file (MP4, MOV, etc.)
- `kind` (optional) – "reference" or "user"

**Response (200):**
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors:**
- `400` – Missing file or empty filename
- `413` – File exceeds MAX_UPLOAD_MB

---

### 3. Create Extract Job
```
POST /jobs/extract
Content-Type: application/json
```

**Request Body:**
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (200):**
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

**Response (429) - Queue Full:**
```json
{
  "error": "queue full",
  "queue_stats": {
    "queued": 100,
    "processing": 4
  }
}
```

**Errors:**
- `400` – Missing video_id
- `404` – Video not found
- `429` – Queue is full (respects MAX_QUEUE_DEPTH)

---

### 4. Create Compare Job
```
POST /jobs/compare
Content-Type: application/json
```

**Request Body:**
```json
{
  "ref_job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "user_job_id": "550e8400-e29b-41d4-a716-446655440000",
  "max_shift_frames": 90
}
```

**Response (200):**
```json
{
  "job_id": "a1b2c3d4-e5f6-47f1-b123-456789abcdef"
}
```

**Features:**
- Memory profiling for ST-GCN embedding
- Timeout: 600s (10 min) max
- Reference timeline used as master

**Errors:**
- `400` – Missing ref_job_id or user_job_id
- `429` – Queue is full

---

### 5. Get Job Status
```
GET /jobs/<job_id>
```

**Response (200):**
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "extract",
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 70,
  "created_at": 1703337600,
  "updated_at": 1703337650,
  "error": null,
  "trace": null,
  "artifacts": null
}
```

**Status Values:**
- `"queued"` – Waiting to run
- `"processing"` – Currently executing
- `"done"` – Completed successfully
- `"failed"` – Error (see `error` field)

**On Timeout:**
```json
{
  "status": "failed",
  "error": "Extract exceeded 3600s timeout",
  "trace": "... full traceback ..."
}
```

**On Memory Exceeded:**
```json
{
  "status": "done",  // Still completes if within time
  "error": "compare_sequences exceeded memory threshold: 2145.3MB > 2048MB"
}
```

**Errors:**
- `404` – Job not found

---

### 6. Get Preview (Keypoints)
```
GET /preview/<job_id>
```

Returns skeleton keypoints and confidence scores for preview/visualization.

**Response (200):**
```json
{
  "frames": 300,
  "kpts": [
    [[x1, y1], [x2, y2], ..., [x17, y17]],
    ...
  ],
  "conf": [
    [c1, c2, ..., c17],
    ...
  ]
}
```

**Notes:**
- Returns downsampled data if > 6000 frames
- `kpts`: shape (frames, 17 joints, 2 coords)
- `conf`: shape (frames, 17) confidence scores
- COCO-17 skeleton format

**Errors:**
- `404` – Job not found or not ready

---

### 7. Get Comparison Results
```
GET /compare/<job_id>
```

Returns DTW alignment and ST-GCN similarity scores.

**Response (200):**
```json
{
  "overall_score_0_100": 85.5,
  "final_score_0_100": 82.3,
  "align_ref_to_user": [0, 1, 1, 2, 3, ...],
  "dtw_debug": {
    "dtw_cost": 156.2,
    "valid_ratio": 0.98,
    "shift_frames": 5,
    ...
  },
  "stgcn_embedding": {
    "enabled": true,
    "sim_0_1": 0.823,
    "window_scores": [0.85, 0.82, 0.81, ...],
    "window_centers_ref": [50, 100, 150, ...],
    "debug": {...}
  }
}
```

**Errors:**
- `404` – Job not found or not ready

---

### 8. Get Artifact
```
GET /artifacts/<job_id>/<name>
```

Download processed artifacts.

**Name Options:**
- `keypoints.npz` – Numpy array with kpts, conf, kpts_raw
- `meta.json` – Job metadata (fps, frames, pipeline version)
- `scores.json` – Comparison scores (same as `/compare/<job_id>`)

**Response:** File download (binary/JSON)

**Errors:**
- `404` – Artifact not found

---

## NEW: Performance & Monitoring Endpoints

### 9. Monitor Queue & System (NEW)
```
GET /monitor/queue
```

Detailed real-time monitoring of queue depth and system resources.

**Response (200):**
```json
{
  "timestamp": 1703337650,
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
      "pid": 12345,
      "rss_mb": 512.5,
      "vms_mb": 600.0,
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

**Use Cases:**
- Dashboard updates
- Auto-scaling decisions
- Capacity planning
- Alerting thresholds

---

### 10. Batch Upload (NEW)
```
POST /upload-batch
Content-Type: multipart/form-data
```

Upload multiple videos in one request with automatic parallel extraction.

**Parameters:**
- `files` (required, multiple) – Video files (up to MAX_BATCH_SIZE)

**Example:**
```bash
curl -X POST http://localhost:8000/upload-batch \
  -F "files=@video1.mp4" \
  -F "files=@video2.mp4" \
  -F "files=@video3.mp4"
```

**Response (200):**
```json
{
  "batch_id": "a1b2c3d4-e5f6-47f1-b123-456789abcdef",
  "submitted_jobs": 3,
  "job_ids": [
    "job-001-uuid",
    "job-002-uuid",
    "job-003-uuid"
  ]
}
```

**Features:**
- Automatic extract jobs created for each video
- Respects MAX_CONCURRENT_JOBS (auto-queues if needed)
- Files up to MAX_UPLOAD_MB each
- Up to MAX_BATCH_SIZE videos per request (default 10)

**Errors:**
- `400` – Missing files or too many files (> MAX_BATCH_SIZE)

---

### 11. Get Batch Status (NEW)
```
GET /batch/<batch_id>
```

Check progress of a batch upload.

**Response (200):**
```json
{
  "batch_id": "a1b2c3d4-e5f6-47f1-b123-456789abcdef",
  "total_videos": 3,
  "completed": 1,
  "failed": 0,
  "pending": 2,
  "progress_percent": 33,
  "created_at": 1703337600,
  "elapsed_sec": 45
}
```

**Progress Tracking:**
- `progress_percent` = (completed + failed) / total * 100
- Check periodically until progress_percent == 100
- Individual job status via `/jobs/<job_id>`

**Errors:**
- `404` – Batch not found

---

## Error Responses

### Standard Error Format
```json
{
  "error": "error message",
  "trace": "... full traceback (in debug mode) ..."
}
```

### HTTP Status Codes
- `200` – Success
- `400` – Bad request (missing params, invalid data)
- `404` – Resource not found
- `413` – Payload too large (file > MAX_UPLOAD_MB)
- `429` – Too many requests (queue full)
- `500` – Server error (exception in processing)

---

## Queue Behavior

### When Queue is Full
```
HTTP 429 Too Many Requests

{
  "error": "queue full",
  "queue_stats": {
    "queued": 100,
    "processing": 4
  }
}
```

**What to do:**
1. Wait for jobs to complete
2. Check progress: `GET /jobs/<job_id>`
3. Monitor queue: `GET /monitor/queue`
4. Retry after queue has space

---

## Timeout Behavior

### Extract Job Timeout
- Default: 3600 seconds (1 hour)
- Configurable: `JOB_TIMEOUT_EXTRACT_SEC`

### Compare Job Timeout
- Default: 600 seconds (10 min)
- Configurable: `JOB_TIMEOUT_COMPARE_SEC`

### What Happens on Timeout
1. Job status set to "failed"
2. Error message: `"Extract exceeded 3600s timeout"`
3. Full traceback stored
4. Job cleaned from active tracking

---

## Memory Profiling

### How Memory Profiling Works
1. ST-GCN embedding wrapped in profiling context
2. Memory snapshots taken before/after
3. Delta computed and compared to threshold
4. Warnings logged if exceeded

### Warning Example
```
WARNING: compare_sequences exceeded memory threshold: 2145.3MB > 2048MB
WARNING: compare_sequences memory delta: +512.5MB
```

### Configurable Limits
- `STGCN_MEMORY_LIMIT_MB` – Threshold for warnings (default 2048MB)
- `PROCESS_MEMORY_LIMIT_MB` – Total process limit (default 4096MB)

---

## Configuration Variables

### Queue & Concurrency
```bash
export MAX_QUEUE_DEPTH=100              # Max jobs in queue
export MAX_CONCURRENT_JOBS=4            # Max jobs running simultaneously
export MAX_WORKERS=2                    # ThreadPoolExecutor workers
```

### Timeouts
```bash
export JOB_TIMEOUT_EXTRACT_SEC=3600     # 1 hour for extraction
export JOB_TIMEOUT_COMPARE_SEC=600      # 10 min for comparison
```

### Memory
```bash
export STGCN_MEMORY_LIMIT_MB=2048       # 2GB ST-GCN limit
export PROCESS_MEMORY_LIMIT_MB=4096     # 4GB total process
```

### Batch Processing
```bash
export MAX_BATCH_SIZE=10                # Max videos per batch
export MAX_UPLOAD_MB=300                # Max file size (MB)
```

---

## Example Workflows

### Workflow 1: Single Extract & Compare
```bash
# Upload reference video
REF_ID=$(curl -s -X POST http://localhost:8000/upload \
  -F "file=@reference.mp4" \
  -F "kind=reference" | jq -r .video_id)

# Upload user video
USER_ID=$(curl -s -X POST http://localhost:8000/upload \
  -F "file=@user.mp4" \
  -F "kind=user" | jq -r .video_id)

# Create extract jobs
REF_JOB=$(curl -s -X POST http://localhost:8000/jobs/extract \
  -H "Content-Type: application/json" \
  -d "{\"video_id\": \"$REF_ID\"}" | jq -r .job_id)

USER_JOB=$(curl -s -X POST http://localhost:8000/jobs/extract \
  -H "Content-Type: application/json" \
  -d "{\"video_id\": \"$USER_ID\"}" | jq -r .job_id)

# Wait for extraction (poll)
while [ "$(curl -s http://localhost:8000/jobs/$REF_JOB | jq -r .status)" != "done" ]; do
  sleep 5
done

# Create compare job
COMPARE_JOB=$(curl -s -X POST http://localhost:8000/jobs/compare \
  -H "Content-Type: application/json" \
  -d "{
    \"ref_job_id\": \"$REF_JOB\",
    \"user_job_id\": \"$USER_JOB\",
    \"max_shift_frames\": 90
  }" | jq -r .job_id)

# Get results
curl http://localhost:8000/compare/$COMPARE_JOB | jq .final_score_0_100
```

### Workflow 2: Batch Upload
```bash
# Upload batch
BATCH_ID=$(curl -s -X POST http://localhost:8000/upload-batch \
  -F "files=@video1.mp4" \
  -F "files=@video2.mp4" \
  -F "files=@video3.mp4" | jq -r .batch_id)

# Monitor progress
while [ "$(curl -s http://localhost:8000/batch/$BATCH_ID | jq -r .progress_percent)" -lt 100 ]; do
  curl http://localhost:8000/batch/$BATCH_ID | jq '.progress_percent, .completed, .pending'
  sleep 10
done

echo "Batch complete!"
```

### Workflow 3: Real-time Monitoring
```bash
# Terminal 1: Watch queue
watch -n 1 'curl -s http://localhost:8000/monitor/queue | jq .queue'

# Terminal 2: Watch system
watch -n 1 'curl -s http://localhost:8000/monitor/queue | jq .system.process'

# Terminal 3: Do work
curl -X POST http://localhost:8000/upload-batch \
  -F "files=@video1.mp4" \
  -F "files=@video2.mp4"
```

---

## Rate Limiting & Backpressure

The system uses HTTP 429 for backpressure:

```python
if queue_manager.get_stats().capacity_ratio >= 1.0:
    return jsonify({"error": "queue full"}), 429
```

**Client Behavior:**
1. Receive 429 response
2. Check current queue: `GET /monitor/queue`
3. Wait or retry after delay
4. Exponential backoff recommended

---

## Authentication

Currently **NO authentication required**. All endpoints are public.

**Recommended for production:**
- Add JWT tokens for `/upload-batch` and `/jobs/compare`
- API key validation for critical endpoints
- Rate limiting per user/key

---

## WebSocket/SSE Enhancement (Future)

Current: Polling-based progress tracking  
Future: WebSocket for real-time updates

```javascript
// Future usage
const ws = new WebSocket('ws://localhost:8000/jobs/<job_id>');
ws.onmessage = (event) => {
  const status = JSON.parse(event.data);
  console.log(`Progress: ${status.progress}%`);
};
```

---

## API Versioning

Current version: **v1** (default)

All endpoints respond with:
```json
{
  "pipeline_version": "v1_extract_norm_localqueue",
  ...
}
```

---

## Summary Table

| Endpoint | Method | Purpose | New? |
|----------|--------|---------|------|
| `/health` | GET | Quick health check | ✓ Enhanced |
| `/upload` | POST | Single video upload | ✓ Existing |
| `/jobs/extract` | POST | Create extract job | ✓ Enhanced |
| `/jobs/compare` | POST | Create compare job | ✓ Enhanced |
| `/jobs/<id>` | GET | Job status & progress | ✓ Existing |
| `/preview/<id>` | GET | Keypoints preview | ✓ Existing |
| `/compare/<id>` | GET | Comparison results | ✓ Existing |
| `/artifacts/<id>/<name>` | GET | Download artifacts | ✓ Existing |
| `/monitor/queue` | GET | Queue + system monitoring | ✓ **NEW** |
| `/upload-batch` | POST | Batch upload | ✓ **NEW** |
| `/batch/<id>` | GET | Batch progress | ✓ **NEW** |

---

**Total Endpoints:** 11 (8 existing + 3 new)  
**Thread-Safe:** Yes  
**Backward Compatible:** Yes  
**Error Handling:** Comprehensive  
**Monitoring:** Real-time
