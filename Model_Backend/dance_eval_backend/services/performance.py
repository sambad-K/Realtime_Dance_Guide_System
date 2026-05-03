# services/performance.py
"""
Performance monitoring, resource limits, and queue management.
- Queue depth tracking and limits
- Job timeout enforcement
- Memory profiling for ST-GCN embeddings
- Batch job status tracking
"""

import os
import time
import psutil
import threading
import functools
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# ============================================================================
# QUEUE DEPTH MONITORING
# ============================================================================

@dataclass
class QueueStats:
    """Real-time queue statistics."""
    queued_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    timestamp: float = field(default_factory=time.time)
    
    @property
    def total_active(self) -> int:
        return self.queued_count + self.processing_count
    
    @property
    def capacity_ratio(self) -> float:
        """Returns 0.0-1.0 indicating queue fullness."""
        total = self.total_active
        max_queue = 100  # reasonable default
        return min(1.0, total / max_queue)


class QueueManager:
    """Tracks job queue depth and enforces limits."""
    
    def __init__(self, max_queue_depth: int = 100, max_concurrent: int = 4):
        self.max_queue_depth = max_queue_depth
        self.max_concurrent = max_concurrent
        self.job_states: Dict[str, str] = {}  # job_id -> status
        self.lock = threading.Lock()
    
    def register_job(self, job_id: str, status: str = "queued") -> bool:
        """Register a new job. Returns False if queue is full."""
        with self.lock:
            queued = sum(1 for s in self.job_states.values() if s == "queued")
            processing = sum(1 for s in self.job_states.values() if s == "processing")
            
            if queued >= self.max_queue_depth:
                return False
            if processing >= self.max_concurrent:
                return False
            
            self.job_states[job_id] = status
            return True
    
    def update_job_status(self, job_id: str, new_status: str):
        """Update job status (queued -> processing -> done/failed)."""
        with self.lock:
            self.job_states[job_id] = new_status
    
    def get_stats(self) -> QueueStats:
        """Get current queue statistics."""
        with self.lock:
            states_list = list(self.job_states.values())
            return QueueStats(
                queued_count=sum(1 for s in states_list if s == "queued"),
                processing_count=sum(1 for s in states_list if s == "processing"),
                completed_count=sum(1 for s in states_list if s == "done"),
                failed_count=sum(1 for s in states_list if s == "failed"),
            )


# ============================================================================
# JOB TIMEOUT ENFORCEMENT
# ============================================================================

@dataclass
class TimeoutPolicy:
    """Timeout configuration for different job types."""
    extract_timeout_sec: int = 3600  # 1 hour for video extraction
    compare_timeout_sec: int = 600   # 10 minutes for comparison
    default_timeout_sec: int = 1800  # 30 minutes default


class TimeoutTracker:
    """Tracks job execution time and enforces timeouts."""
    
    def __init__(self, policy: TimeoutPolicy = None):
        self.policy = policy or TimeoutPolicy()
        self.job_start_times: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def start_job(self, job_id: str):
        """Mark job as started."""
        with self.lock:
            self.job_start_times[job_id] = time.time()
    
    def get_elapsed(self, job_id: str) -> Optional[float]:
        """Get elapsed seconds for a job. Returns None if not started."""
        with self.lock:
            start = self.job_start_times.get(job_id)
            if start is None:
                return None
            return time.time() - start
    
    def is_timed_out(self, job_id: str, job_type: str = "default") -> bool:
        """Check if job has exceeded its timeout."""
        elapsed = self.get_elapsed(job_id)
        if elapsed is None:
            return False
        
        timeout = self.policy.default_timeout_sec
        if job_type == "extract":
            timeout = self.policy.extract_timeout_sec
        elif job_type == "compare":
            timeout = self.policy.compare_timeout_sec
        
        return elapsed > timeout
    
    def finish_job(self, job_id: str):
        """Remove job from tracking (cleanup)."""
        with self.lock:
            self.job_start_times.pop(job_id, None)


# ============================================================================
# MEMORY PROFILING FOR ST-GCN EMBEDDINGS
# ============================================================================

@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: float
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory Size in MB
    process_percent: float  # % of system memory used
    
    def __str__(self) -> str:
        return f"RSS={self.rss_mb:.1f}MB VMS={self.vms_mb:.1f}MB ({self.process_percent:.1f}%)"


class MemoryMonitor:
    """Monitor memory usage for expensive operations."""
    
    def __init__(self, threshold_mb: int = 2048):
        """
        threshold_mb: warn if process uses more than this much RAM.
        """
        self.threshold_mb = threshold_mb
        self.process = psutil.Process(os.getpid())
        self.snapshots: List[MemorySnapshot] = []
    
    def snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot."""
        mem = self.process.memory_info()
        snap = MemorySnapshot(
            timestamp=time.time(),
            rss_mb=mem.rss / (1024 * 1024),
            vms_mb=mem.vms / (1024 * 1024),
            process_percent=self.process.memory_percent(),
        )
        self.snapshots.append(snap)
        return snap
    
    def is_exceeded(self) -> bool:
        """Check if current memory usage exceeds threshold."""
        snap = self.snapshot()
        return snap.rss_mb > self.threshold_mb
    
    def get_delta(self) -> Optional[float]:
        """Get memory delta since last two snapshots (in MB)."""
        if len(self.snapshots) < 2:
            return None
        return self.snapshots[-1].rss_mb - self.snapshots[-2].rss_mb
    
    def clear_snapshots(self):
        """Clear snapshot history."""
        self.snapshots.clear()


def memory_profile_context(operation_name: str, threshold_mb: int = 2048):
    """
    Decorator/context manager for memory profiling ST-GCN and heavy ops.
    
    Usage:
        with memory_profile_context("stgcn_embed", threshold_mb=2048):
            result = stgcn_embed_sequence_windows(...)
    """
    class MemoryProfiler:
        def __init__(self):
            self.monitor = MemoryMonitor(threshold_mb)
            self.peak_mb = 0
            self.warnings = []
        
        def __enter__(self):
            self.monitor.snapshot()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            snap = self.monitor.snapshot()
            delta = self.monitor.get_delta()
            
            if snap.rss_mb > self.peak_mb:
                self.peak_mb = snap.rss_mb
            
            if snap.rss_mb > threshold_mb:
                self.warnings.append(
                    f"{operation_name} exceeded memory threshold: {snap.rss_mb:.1f}MB > {threshold_mb}MB"
                )
            
            if delta and abs(delta) > 500:  # significant change
                self.warnings.append(
                    f"{operation_name} memory delta: {delta:+.1f}MB"
                )
            
            return False  # Don't suppress exceptions
    
    return MemoryProfiler()


def profile_stgcn_memory(func):
    """Decorator for profiling ST-GCN embedding functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        monitor = MemoryMonitor(threshold_mb=2048)
        monitor.snapshot()
        
        try:
            result = func(*args, **kwargs)
            monitor.snapshot()
            delta = monitor.get_delta()
            
            if monitor.is_exceeded():
                import warnings
                warnings.warn(
                    f"{func.__name__} exceeded memory threshold. "
                    f"Current: {monitor.snapshots[-1].rss_mb:.1f}MB"
                )
            
            return result
        finally:
            monitor.clear_snapshots()
    
    return wrapper


# ============================================================================
# CPU & DISK MONITORING
# ============================================================================

class SystemMonitor:
    """Monitor system resources (CPU, disk, memory)."""
    
    @staticmethod
    def get_cpu_percent(interval: float = 0.1) -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=interval)
    
    @staticmethod
    def get_disk_usage(path: str) -> Dict[str, float]:
        """Get disk usage for a path."""
        usage = psutil.disk_usage(path)
        return {
            "total_gb": usage.total / (1024**3),
            "used_gb": usage.used / (1024**3),
            "free_gb": usage.free / (1024**3),
            "percent": usage.percent,
        }
    
    @staticmethod
    def get_process_info() -> Dict[str, any]:
        """Get info about current process."""
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        return {
            "pid": proc.pid,
            "rss_mb": mem.rss / (1024 * 1024),
            "vms_mb": mem.vms / (1024 * 1024),
            "num_threads": proc.num_threads(),
            "cpu_percent": proc.cpu_percent(interval=0.1),
        }


# ============================================================================
# BATCH JOB MANAGEMENT
# ============================================================================

@dataclass
class BatchJob:
    """Batch job for parallel processing."""
    batch_id: str
    video_ids: List[str]
    created_at: float = field(default_factory=time.time)
    completed_count: int = 0
    failed_count: int = 0
    job_ids: Dict[str, str] = field(default_factory=dict)  # video_id -> job_id


class BatchJobManager:
    """Manage batch uploads and parallel extractions."""
    
    def __init__(self):
        self.batches: Dict[str, BatchJob] = {}
        self.lock = threading.Lock()
    
    def create_batch(self, batch_id: str, video_ids: List[str]) -> BatchJob:
        """Create a new batch job."""
        with self.lock:
            batch = BatchJob(batch_id=batch_id, video_ids=video_ids)
            self.batches[batch_id] = batch
            return batch
    
    def update_batch_job(self, batch_id: str, video_id: str, job_id: str):
        """Link a job to a batch."""
        with self.lock:
            if batch_id in self.batches:
                self.batches[batch_id].job_ids[video_id] = job_id
    
    def mark_completed(self, batch_id: str, video_id: str, success: bool = True):
        """Mark a video in the batch as completed."""
        with self.lock:
            if batch_id in self.batches:
                if success:
                    self.batches[batch_id].completed_count += 1
                else:
                    self.batches[batch_id].failed_count += 1
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get batch progress and status."""
        with self.lock:
            batch = self.batches.get(batch_id)
            if not batch:
                return None
            
            total = len(batch.video_ids)
            return {
                "batch_id": batch_id,
                "total_videos": total,
                "completed": batch.completed_count,
                "failed": batch.failed_count,
                "pending": total - batch.completed_count - batch.failed_count,
                "progress_percent": int(100 * (batch.completed_count + batch.failed_count) / total) if total > 0 else 0,
                "created_at": batch.created_at,
                "elapsed_sec": time.time() - batch.created_at,
            }
    
    def cleanup_batch(self, batch_id: str):
        """Remove completed batch from memory."""
        with self.lock:
            self.batches.pop(batch_id, None)


# ============================================================================
# SINGLETON INSTANCES
# ============================================================================

queue_manager = QueueManager()
timeout_tracker = TimeoutTracker()
batch_manager = BatchJobManager()
system_monitor = SystemMonitor()
