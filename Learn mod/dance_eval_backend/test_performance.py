#!/usr/bin/env python3
"""
Quick test script for performance monitoring features.
Run: python test_performance.py
"""

import sys
import os
import time
import requests
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.performance import (
    queue_manager, timeout_tracker, batch_manager, system_monitor,
    MemoryMonitor, memory_profile_context, TimeoutPolicy
)

def test_queue_manager():
    """Test queue depth monitoring."""
    print("\n" + "="*60)
    print("TEST 1: Queue Manager")
    print("="*60)
    
    # Register some jobs
    job1 = "job-001"
    job2 = "job-002"
    job3 = "job-003"
    
    success = queue_manager.register_job(job1, "queued")
    print(f"Register job1: {success}")
    
    queue_manager.register_job(job2, "queued")
    queue_manager.register_job(job3, "processing")
    
    stats = queue_manager.get_stats()
    print(f"Queue stats: queued={stats.queued_count}, processing={stats.processing_count}")
    print(f"Capacity ratio: {stats.capacity_ratio:.1%}")
    print(f"Total active: {stats.total_active}")


def test_timeout_tracker():
    """Test job timeout enforcement."""
    print("\n" + "="*60)
    print("TEST 2: Timeout Tracker")
    print("="*60)
    
    policy = TimeoutPolicy(extract_timeout_sec=5, compare_timeout_sec=3)
    tracker = timeout_tracker
    tracker.policy = policy
    
    job_id = "extract-job-001"
    tracker.start_job(job_id)
    print(f"Started job: {job_id}")
    
    # Check immediately (should not be timed out)
    is_timeout = tracker.is_timed_out(job_id, "extract")
    print(f"Timed out (immediately): {is_timeout}")
    
    elapsed = tracker.get_elapsed(job_id)
    print(f"Elapsed time: {elapsed:.2f}s")
    
    # Wait a bit and check again
    time.sleep(2)
    elapsed = tracker.get_elapsed(job_id)
    print(f"Elapsed time (after 2s): {elapsed:.2f}s")
    
    tracker.finish_job(job_id)
    print(f"Job finished and cleaned up")


def test_memory_monitor():
    """Test memory profiling."""
    print("\n" + "="*60)
    print("TEST 3: Memory Monitor")
    print("="*60)
    
    monitor = MemoryMonitor(threshold_mb=5000)  # High threshold for test
    
    snap1 = monitor.snapshot()
    print(f"Snapshot 1: {snap1}")
    
    # Allocate some memory
    _ = [0] * (10**7)  # Allocate ~80MB
    
    snap2 = monitor.snapshot()
    print(f"Snapshot 2: {snap2}")
    
    delta = monitor.get_delta()
    print(f"Memory delta: {delta:+.1f}MB")
    
    exceeded = monitor.is_exceeded()
    print(f"Exceeded threshold: {exceeded}")


def test_memory_profile_context():
    """Test memory profiling context manager."""
    print("\n" + "="*60)
    print("TEST 4: Memory Profile Context")
    print("="*60)
    
    with memory_profile_context("test_operation", threshold_mb=5000) as profiler:
        # Simulate some work
        _ = [0] * (10**7)
        time.sleep(0.1)
        print(f"Operation complete. Peak: {profiler.peak_mb:.1f}MB")
        if profiler.warnings:
            print(f"Warnings: {profiler.warnings}")


def test_batch_manager():
    """Test batch job management."""
    print("\n" + "="*60)
    print("TEST 5: Batch Manager")
    print("="*60)
    
    batch_id = "batch-001"
    videos = ["video1.mp4", "video2.mp4", "video3.mp4"]
    
    batch = batch_manager.create_batch(batch_id, videos)
    print(f"Created batch: {batch_id} with {len(videos)} videos")
    
    # Simulate processing
    batch_manager.update_batch_job(batch_id, videos[0], "job-001")
    batch_manager.mark_completed(batch_id, videos[0], success=True)
    
    batch_manager.update_batch_job(batch_id, videos[1], "job-002")
    batch_manager.mark_completed(batch_id, videos[1], success=True)
    
    status = batch_manager.get_batch_status(batch_id)
    print(f"Batch status: {json.dumps(status, indent=2)}")


def test_system_monitor():
    """Test system resource monitoring."""
    print("\n" + "="*60)
    print("TEST 6: System Monitor")
    print("="*60)
    
    cpu = system_monitor.get_cpu_percent(interval=0.1)
    print(f"CPU usage: {cpu:.1f}%")
    
    disk = system_monitor.get_disk_usage(".")
    print(f"Disk usage: {json.dumps(disk, indent=2)}")
    
    proc = system_monitor.get_process_info()
    print(f"Process info: {json.dumps(proc, indent=2)}")


def test_api_integration():
    """Test API endpoints (requires running Flask server)."""
    print("\n" + "="*60)
    print("TEST 7: API Integration (requires server running)")
    print("="*60)
    
    try:
        # Test health endpoint
        resp = requests.get("http://localhost:8000/health", timeout=2)
        if resp.status_code == 200:
            print("✓ /health endpoint working")
            print(json.dumps(resp.json(), indent=2)[:200] + "...")
        
        # Test monitor queue endpoint
        resp = requests.get("http://localhost:8000/monitor/queue", timeout=2)
        if resp.status_code == 200:
            print("✓ /monitor/queue endpoint working")
            print(json.dumps(resp.json(), indent=2)[:200] + "...")
    except requests.exceptions.ConnectionError:
        print("⚠ Flask server not running on localhost:8000")
    except Exception as e:
        print(f"⚠ API test failed: {e}")


def main():
    print("\n" + "="*60)
    print("PERFORMANCE MONITORING TEST SUITE")
    print("="*60)
    
    test_queue_manager()
    test_timeout_tracker()
    test_memory_monitor()
    test_memory_profile_context()
    test_batch_manager()
    test_system_monitor()
    test_api_integration()
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
