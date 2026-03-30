// src/PerformanceMonitor.jsx
/**
 * Performance Monitoring Dashboard
 * Tests queue depth, job timeouts, memory profiling, and batch uploads
 */

import React, { useState, useEffect, useCallback } from "react";
import "./PerformanceMonitor.css";

const API_BASE = "http://localhost:5000";

export default function PerformanceMonitor() {
  // Queue monitoring
  const [queueStats, setQueueStats] = useState(null);
  const [systemStats, setSystemStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);

  // Job management
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [jobHistory, setJobHistory] = useState([]);
  const [batchHistory, setBatchHistory] = useState([]);
  const [activeTab, setActiveTab] = useState("monitor");

  // Batch uploads
  const [batchJobs, setBatchJobs] = useState({});

  // Error handling
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // ============================================================
  // FETCH QUEUE & SYSTEM STATS
  // ============================================================
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/monitor/queue`);
      if (!response.ok) throw new Error("Failed to fetch stats");

      const data = await response.json();
      setQueueStats(data.queue);
      setSystemStats(data.system);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  // Auto-refresh queue stats
  useEffect(() => {
    if (!autoRefresh) return;

    fetchStats();
    const interval = setInterval(fetchStats, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchStats]);

  // ============================================================
  // BATCH UPLOAD HANDLER
  // ============================================================
  const handleBatchUpload = async (e) => {
    e.preventDefault();

    if (!selectedFiles.length) {
      setError("Please select at least one video");
      return;
    }

    if (selectedFiles.length > 10) {
      setError("Maximum 10 videos per batch");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append("files", file);
      });

      const response = await fetch(`${API_BASE}/upload-batch`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || "Upload failed");
      }

      const data = await response.json();
      const batchId = data.batch_id;

      // Add to batch history
      setBatchHistory((prev) => [
        {
          batch_id: batchId,
          submitted_jobs: data.submitted_jobs,
          job_ids: data.job_ids,
          created_at: new Date(),
          status: "processing",
          progress: 0,
        },
        ...prev,
      ]);

      // Initialize batch job tracking
      setBatchJobs((prev) => ({
        ...prev,
        [batchId]: {
          job_ids: data.job_ids,
          progress: 0,
          status: "processing",
        },
      }));

      setSuccess(
        `✓ Batch uploaded! ${data.submitted_jobs} jobs created. Batch ID: ${batchId}`
      );
      setSelectedFiles([]);

      // Start polling batch progress
      pollBatchProgress(batchId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // POLL BATCH PROGRESS
  // ============================================================
  const pollBatchProgress = (batchId) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/batch/${batchId}`);
        if (!response.ok) {
          clearInterval(pollInterval);
          return;
        }

        const data = await response.json();

        // Update batch in history
        setBatchHistory((prev) =>
          prev.map((batch) =>
            batch.batch_id === batchId
              ? {
                  ...batch,
                  progress: data.progress_percent,
                  status: data.progress_percent === 100 ? "done" : "processing",
                }
              : batch
          )
        );

        // Update batch jobs tracking
        setBatchJobs((prev) => ({
          ...prev,
          [batchId]: {
            ...prev[batchId],
            progress: data.progress_percent,
            status: data.progress_percent === 100 ? "done" : "processing",
            total_videos: data.total_videos,
            completed: data.completed,
            failed: data.failed,
            pending: data.pending,
          },
        }));

        if (data.progress_percent === 100) {
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error("Polling error:", err);
        clearInterval(pollInterval);
      }
    }, 3000);
  };

  // ============================================================
  // HEALTH CHECK
  // ============================================================
  const handleHealthCheck = async () => {
    try {
      const response = await fetch(`${API_BASE}/health`);
      const data = await response.json();
      setSuccess(`✓ Backend is healthy! ${JSON.stringify(data.ok)}`);
    } catch (err) {
      setError(`✗ Backend health check failed: ${err.message}`);
    }
  };

  // ============================================================
  // UI HELPER: Format bytes to MB
  // ============================================================
  const formatMB = (mb) => mb ? `${mb.toFixed(1)} MB` : "N/A";
  const formatPercent = (ratio) =>
    ratio !== undefined ? `${(ratio * 100).toFixed(1)}%` : "N/A";

  return (
    <div className="performance-monitor">
      {/* HEADER */}
      <header className="pm-header">
        <h1>🚀 Performance Monitor Dashboard</h1>
        <p>Real-time testing of queue, timeouts, memory, and batch processing</p>
      </header>

      {/* ALERTS */}
      {error && (
        <div className="alert alert-error">
          <span>❌ {error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}
      {success && (
        <div className="alert alert-success">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)}>×</button>
        </div>
      )}

      {/* TAB NAVIGATION */}
      <nav className="pm-tabs">
        <button
          className={`tab ${activeTab === "monitor" ? "active" : ""}`}
          onClick={() => setActiveTab("monitor")}
        >
          📊 Monitor
        </button>
        <button
          className={`tab ${activeTab === "batch" ? "active" : ""}`}
          onClick={() => setActiveTab("batch")}
        >
          📦 Batch Upload
        </button>
        <button
          className={`tab ${activeTab === "history" ? "active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          📋 History
        </button>
      </nav>

      {/* MONITOR TAB */}
      {activeTab === "monitor" && (
        <div className="tab-content">
          {/* Controls */}
          <div className="controls">
            <button
              className="btn btn-primary"
              onClick={fetchStats}
              disabled={loading}
            >
              {loading ? "Loading..." : "🔄 Refresh Now"}
            </button>
            <button
              className={`btn ${autoRefresh ? "btn-success" : "btn-secondary"}`}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              {autoRefresh ? "✓ Auto-Refresh ON" : "Auto-Refresh OFF"}
            </button>
            <button className="btn btn-info" onClick={handleHealthCheck}>
              💚 Health Check
            </button>
            <label className="refresh-label">
              Interval:
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
              >
                <option value={1000}>1s</option>
                <option value={2000}>2s</option>
                <option value={5000}>5s</option>
                <option value={10000}>10s</option>
              </select>
            </label>
          </div>

          {/* Queue Stats */}
          {queueStats && (
            <div className="grid grid-2">
              <div className="card">
                <h2>📤 Queue Status</h2>
                <div className="stat-group">
                  <div className="stat">
                    <span className="label">Queued:</span>
                    <span className="value queued">{queueStats.queued}</span>
                  </div>
                  <div className="stat">
                    <span className="label">Processing:</span>
                    <span className="value processing">
                      {queueStats.processing}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="label">Completed:</span>
                    <span className="value completed">{queueStats.completed}</span>
                  </div>
                  <div className="stat">
                    <span className="label">Failed:</span>
                    <span className="value failed">{queueStats.failed}</span>
                  </div>
                </div>

                {/* Capacity Meter */}
                <div className="capacity-meter">
                  <label>
                    Queue Capacity: {formatPercent(queueStats.capacity_ratio)}
                  </label>
                  <div className="meter-bar">
                    <div
                      className={`meter-fill ${
                        queueStats.capacity_ratio > 0.8 ? "danger" : ""
                      }`}
                      style={{
                        width: `${queueStats.capacity_ratio * 100}%`,
                      }}
                    ></div>
                  </div>
                  <small>{queueStats.queued + queueStats.processing} / {queueStats.max_depth} jobs</small>
                </div>
              </div>

              {/* System Stats */}
              {systemStats && (
                <div className="card">
                  <h2>💻 System Resources</h2>
                  <div className="stat-group">
                    <div className="stat">
                      <span className="label">Memory (RSS):</span>
                      <span className="value">
                        {formatMB(systemStats.process.rss_mb)}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="label">Memory (VMS):</span>
                      <span className="value">
                        {formatMB(systemStats.process.vms_mb)}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="label">CPU Usage:</span>
                      <span className="value">
                        {systemStats.process.cpu_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="stat">
                      <span className="label">Threads:</span>
                      <span className="value">{systemStats.process.threads}</span>
                    </div>
                  </div>

                  {/* Disk Usage */}
                  <div className="disk-usage">
                    <h3>💾 Disk Usage</h3>
                    <div className="meter-bar">
                      <div
                        className="meter-fill"
                        style={{ width: `${systemStats.disk.percent}%` }}
                      ></div>
                    </div>
                    <small>
                      {systemStats.disk.used_gb.toFixed(1)} /
                      {systemStats.disk.total_gb.toFixed(1)} GB ({systemStats.disk.percent}%)
                    </small>
                  </div>
                </div>
              )}
            </div>
          )}

          {!queueStats && !loading && (
            <div className="placeholder">
              <p>Click "Refresh Now" to load queue statistics</p>
            </div>
          )}
        </div>
      )}

      {/* BATCH UPLOAD TAB */}
      {activeTab === "batch" && (
        <div className="tab-content">
          <div className="card">
            <h2>📦 Batch Upload & Extract</h2>
            <form onSubmit={handleBatchUpload} className="upload-form">
              <div className="form-group">
                <label htmlFor="file-input">Select Videos (Max 10):</label>
                <input
                  id="file-input"
                  type="file"
                  multiple
                  accept="video/*"
                  onChange={(e) => setSelectedFiles(Array.from(e.target.files))}
                  disabled={loading}
                  className="file-input"
                />
                <small>
                  {selectedFiles.length > 0
                    ? `${selectedFiles.length} file(s) selected`
                    : "No files selected"}
                </small>
              </div>

              {selectedFiles.length > 0 && (
                <div className="selected-files">
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="file-item">
                      <span>🎬 {file.name}</span>
                      <small>{(file.size / (1024 * 1024)).toFixed(1)} MB</small>
                    </div>
                  ))}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || selectedFiles.length === 0}
              >
                {loading ? "Uploading..." : "📤 Upload & Extract Batch"}
              </button>
            </form>

            {uploadProgress > 0 && uploadProgress < 100 && (
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
                <span>{uploadProgress}%</span>
              </div>
            )}
          </div>

          {/* Active Batches */}
          {Object.keys(batchJobs).length > 0 && (
            <div className="card">
              <h3>🔄 Active Batch Jobs</h3>
              {Object.entries(batchJobs).map(([batchId, batch]) => (
                <div key={batchId} className="batch-item">
                  <div className="batch-header">
                    <span className="batch-id">Batch: {batchId.slice(0, 8)}...</span>
                    <span
                      className={`badge ${
                        batch.status === "done" ? "done" : "processing"
                      }`}
                    >
                      {batch.status}
                    </span>
                  </div>

                  <div className="batch-progress">
                    <div className="meter-bar">
                      <div
                        className="meter-fill"
                        style={{ width: `${batch.progress}%` }}
                      ></div>
                    </div>
                    <span>{batch.progress}%</span>
                  </div>

                  {batch.total_videos && (
                    <div className="batch-stats">
                      <span>
                        ✓ {batch.completed} completed • ✗ {batch.failed} failed •
                        ⏳ {batch.pending} pending / {batch.total_videos} total
                      </span>
                    </div>
                  )}

                  <div className="job-ids">
                    <small>Job IDs:</small>
                    {batch.job_ids.map((jobId, idx) => (
                      <code key={idx}>{jobId.slice(0, 8)}...</code>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* HISTORY TAB */}
      {activeTab === "history" && (
        <div className="tab-content">
          <div className="card">
            <h2>📋 Batch History</h2>
            {batchHistory.length > 0 ? (
              <div className="history-list">
                {batchHistory.map((batch) => (
                  <div key={batch.batch_id} className="history-item">
                    <div className="history-header">
                      <span className="batch-id">ID: {batch.batch_id.slice(0, 12)}...</span>
                      <span
                        className={`badge ${batch.status === "done" ? "done" : "processing"}`}
                      >
                        {batch.status}
                      </span>
                    </div>
                    <div className="history-details">
                      <span>Jobs: {batch.submitted_jobs}</span>
                      <span>Progress: {batch.progress}%</span>
                      <span>
                        Time: {batch.created_at.toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="placeholder">No batch uploads yet</p>
            )}
          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer className="pm-footer">
        <p>
          🔧 Performance Module Test Suite |{" "}
          <code>Backend: {API_BASE}</code>
        </p>
        <p>
          Features: Queue Monitoring • Job Timeouts • Memory Profiling • Batch
          Processing
        </p>
      </footer>
    </div>
  );
}
