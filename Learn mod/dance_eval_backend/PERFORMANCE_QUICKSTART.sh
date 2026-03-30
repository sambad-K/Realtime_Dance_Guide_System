#!/usr/bin/env bash
# Quick-start examples for performance monitoring features

echo "==============================================="
echo "DANCE EVALUATION - PERFORMANCE OPTIMIZATION"
echo "Quick-Start Examples"
echo "==============================================="

# ============================================================
# 1. HEALTH CHECK WITH QUEUE STATS
# ============================================================
echo -e "\n\n1. HEALTH CHECK (with queue stats)"
echo "==============================================="
echo "Endpoint: GET /health"
echo ""
echo "Command:"
echo "  curl http://localhost:8000/health | jq"
echo ""
echo "Response:"
echo '  {
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
}'


# ============================================================
# 2. MONITOR QUEUE & SYSTEM
# ============================================================
echo -e "\n\n2. DETAILED QUEUE & SYSTEM MONITORING"
echo "==============================================="
echo "Endpoint: GET /monitor/queue"
echo ""
echo "Command:"
echo "  curl http://localhost:8000/monitor/queue | jq"
echo ""
echo "Response includes:"
echo "  - Queue depth (queued, processing, completed, failed)"
echo "  - Capacity ratio (0.0-1.0)"
echo "  - Process: memory (RSS/VMS), threads, CPU %"
echo "  - Disk: total, used, free, percent"


# ============================================================
# 3. SINGLE FILE UPLOAD WITH TIMEOUT ENFORCEMENT
# ============================================================
echo -e "\n\n3. UPLOAD & EXTRACT (with timeout enforcement)"
echo "==============================================="
echo "Step 1: Upload video"
echo "  curl -X POST http://localhost:8000/upload \\"
echo "    -F 'file=@dance.mp4' \\"
echo "    -F 'kind=reference' | jq .video_id"
echo ""
echo "Step 2: Create extract job (timeout: 3600s max)"
echo "  curl -X POST http://localhost:8000/jobs/extract \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"video_id\": \"<video_id>\"}' | jq .job_id"
echo ""
echo "Step 3: Check job status (timeout tracked)"
echo "  curl http://localhost:8000/jobs/<job_id> | jq"
echo ""
echo "Response includes:"
echo '  {
  "status": "processing",
  "progress": 70,
  "error": null,  // or "Extract exceeded 3600s timeout"
  "updated_at": 1703337650
}'


# ============================================================
# 4. BATCH UPLOAD (parallel processing)
# ============================================================
echo -e "\n\n4. BATCH UPLOAD (parallel processing with queue control)"
echo "==============================================="
echo "Step 1: Upload multiple videos at once"
echo "  curl -X POST http://localhost:8000/upload-batch \\"
echo "    -F 'files=@video1.mp4' \\"
echo "    -F 'files=@video2.mp4' \\"
echo "    -F 'files=@video3.mp4' | jq"
echo ""
echo "Response:"
echo '  {
  "batch_id": "a1b2c3d4-...",
  "submitted_jobs": 3,
  "job_ids": ["job-1", "job-2", "job-3"]
}'
echo ""
echo "Step 2: Check batch progress"
echo "  curl http://localhost:8000/batch/<batch_id> | jq"
echo ""
echo "Response:"
echo '  {
  "batch_id": "a1b2c3d4-...",
  "total_videos": 3,
  "completed": 1,
  "failed": 0,
  "pending": 2,
  "progress_percent": 33,
  "elapsed_sec": 45
}'
echo ""
echo "Note: Respects MAX_CONCURRENT_JOBS limit automatically"


# ============================================================
# 5. COMPARISON WITH MEMORY PROFILING
# ============================================================
echo -e "\n\n5. COMPARISON (with ST-GCN memory profiling)"
echo "==============================================="
echo "Endpoint: POST /jobs/compare"
echo ""
echo "Command:"
echo "  curl -X POST http://localhost:8000/jobs/compare \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{
  \"ref_job_id\": \"<job1>\",
  \"user_job_id\": \"<job2>\",
  \"max_shift_frames\": 90
}' | jq .job_id"
echo ""
echo "Features:"
echo "  - ST-GCN embedding wrapped in memory_profile_context()"
echo "  - Timeout: 600s (10 min) max"
echo "  - Memory limit: 2048MB default (configurable)"
echo "  - Warnings logged if memory exceeded"


# ============================================================
# 6. ENVIRONMENT CONFIGURATION
# ============================================================
echo -e "\n\n6. ENVIRONMENT VARIABLES (set before running app)"
echo "==============================================="
echo ""
echo "Queue & Concurrency:"
echo "  export MAX_QUEUE_DEPTH=100          # Max jobs in queue"
echo "  export MAX_CONCURRENT_JOBS=4        # Max jobs running"
echo ""
echo "Timeouts (seconds):"
echo "  export JOB_TIMEOUT_EXTRACT_SEC=3600 # 1 hour (videos can be large)"
echo "  export JOB_TIMEOUT_COMPARE_SEC=600  # 10 min (faster operation)"
echo ""
echo "Memory Limits (MB):"
echo "  export STGCN_MEMORY_LIMIT_MB=2048   # 2GB for ST-GCN ops"
echo "  export PROCESS_MEMORY_LIMIT_MB=4096 # 4GB total process"
echo ""
echo "Batch Processing:"
echo "  export MAX_BATCH_SIZE=10             # Max videos per batch"
echo "  export BATCH_PARALLEL_EXTRACTS=2    # (uses MAX_CONCURRENT_JOBS)"


# ============================================================
# 7. MONITORING PRESETS
# ============================================================
echo -e "\n\n7. QUICK CONFIG PRESETS"
echo "==============================================="
echo ""
echo "Small (1 CPU, 4GB):"
echo "  MAX_WORKERS=1 MAX_CONCURRENT_JOBS=1 MAX_QUEUE_DEPTH=20"
echo "  STGCN_MEMORY_LIMIT_MB=1024 MAX_BATCH_SIZE=3"
echo ""
echo "Medium (4 CPUs, 16GB):"
echo "  MAX_WORKERS=3 MAX_CONCURRENT_JOBS=3 MAX_QUEUE_DEPTH=50"
echo "  STGCN_MEMORY_LIMIT_MB=2048 MAX_BATCH_SIZE=10"
echo ""
echo "Large (8+ CPUs, 32GB):"
echo "  MAX_WORKERS=6 MAX_CONCURRENT_JOBS=6 MAX_QUEUE_DEPTH=100"
echo "  STGCN_MEMORY_LIMIT_MB=4096 MAX_BATCH_SIZE=20"


# ============================================================
# 8. PYTHON API USAGE
# ============================================================
echo -e "\n\n8. PYTHON API (in your code)"
echo "==============================================="
cat << 'EOF'

# Import performance modules
from services.performance import (
    queue_manager, timeout_tracker, batch_manager, system_monitor,
    memory_profile_context
)

# Check queue status
stats = queue_manager.get_stats()
print(f"Queue: {stats.queued_count} queued, {stats.processing_count} processing")
print(f"Capacity: {stats.capacity_ratio:.0%}")

# Manual job tracking
timeout_tracker.start_job("my-job-id")
# ... do work ...
if timeout_tracker.is_timed_out("my-job-id", "extract"):
    raise TimeoutError("Job took too long")
timeout_tracker.finish_job("my-job-id")

# Memory profiling
with memory_profile_context("my_operation", threshold_mb=2048):
    result = expensive_function()
    print(f"Completed in {time.time()}s")

# System monitoring
info = system_monitor.get_process_info()
disk = system_monitor.get_disk_usage("./storage")
print(f"Memory: {info['rss_mb']:.1f}MB")
print(f"Disk: {disk['free_gb']:.1f}GB free")

EOF


# ============================================================
# 9. PRODUCTION CHECKLIST
# ============================================================
echo -e "\n\n9. PRODUCTION DEPLOYMENT CHECKLIST"
echo "==============================================="
echo "  ☐ Install psutil: pip install psutil==6.0.0"
echo "  ☐ Set environment variables for your hardware"
echo "  ☐ Test endpoints: curl http://localhost:8000/health"
echo "  ☐ Monitor queue: curl http://localhost:8000/monitor/queue | jq"
echo "  ☐ Test batch upload with multiple files"
echo "  ☐ Verify timeouts work (upload large video, check status)"
echo "  ☐ Verify memory warnings (run memory profiling test)"
echo "  ☐ Set up log aggregation (warnings go to stdout)"
echo "  ☐ Consider Prometheus scraping /monitor/queue endpoint"
echo "  ☐ Consider auto-scaling based on queue depth"


# ============================================================
# 10. TROUBLESHOOTING
# ============================================================
echo -e "\n\n10. TROUBLESHOOTING"
echo "==============================================="
echo ""
echo "Q: Getting 'queue full' error (HTTP 429)?"
echo "A: Increase MAX_QUEUE_DEPTH or MAX_CONCURRENT_JOBS"
echo ""
echo "Q: Jobs timing out prematurely?"
echo "A: Increase JOB_TIMEOUT_EXTRACT_SEC or JOB_TIMEOUT_COMPARE_SEC"
echo ""
echo "Q: Memory warnings for ST-GCN?"
echo "A: Increase STGCN_MEMORY_LIMIT_MB (default 2048MB)"
echo ""
echo "Q: How to see memory profile output?"
echo "A: Check stdout/logs during job execution"
echo ""
echo "Q: Want to turn off timeouts?"
echo "A: Set timeout to very high value (86400 = 24 hours)"
echo ""
echo "Q: How to reset queue on restart?"
echo "A: Delete storage/jobs/*.json files"


echo -e "\n\n==============================================="
echo "For detailed docs, see: PERFORMANCE.md"
echo "===============================================\n"
