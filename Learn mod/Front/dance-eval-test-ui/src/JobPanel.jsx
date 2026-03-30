import { useEffect, useRef, useState } from "react";
import { uploadVideo, createExtractJob, getJob, getPreview } from "./api";
import "./JobPanel.css";

// Toggle recording functionality during development
const ENABLE_RECORD = false;

export default function VideoJobPanel({ kind, label, onReady }) {
  const videoRef = useRef(null);
  const recorderRef = useRef(null);
  const audioRef = useRef(null);

  const [file, setFile] = useState(null);
  const [videoId, setVideoId] = useState("");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  // Camera modal states
  const [camOpen, setCamOpen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [stream, setStream] = useState(null);

  /* ================= UPLOAD LOGIC ================= */
  async function startUpload(fileToUpload = file) {
    if (!fileToUpload) return;

    setError("");
    setStatus("uploading");
    setProgress(0);

    try {
      const up = await uploadVideo(fileToUpload, kind);
      setVideoId(up.video_id);

      setStatus("queued");
      const jb = await createExtractJob(up.video_id);
      setJobId(jb.job_id);
      setStatus("processing");
    } catch (e) {
      setError(String(e.message || e));
      setStatus("failed");
    }
  }

  /* ================= JOB POLLING ================= */
  useEffect(() => {
    if (!jobId) return;
    let alive = true;

    const interval = setInterval(async () => {
      try {
        const j = await getJob(jobId);
        if (!alive) return;

        setStatus(j.status);
        setProgress(j.progress ?? 0);

        if (j.status === "failed") {
          setError(j.error || "Job failed");
          clearInterval(interval);
        }

        if (j.status === "done") {
          clearInterval(interval);
          const preview = await getPreview(jobId);
          if (!alive) return;
          onReady({ kind, jobId, preview });
        }
      } catch {}
    }, 1500);

    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [jobId, kind, onReady]);

  /* ================= CAMERA LOGIC ================= */
  function openCamera() {
    setCamOpen(true);
  }

  useEffect(() => {
    if (!camOpen) return;

    async function startCamera() {
      try {
        const s = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user" },
          audio: false,
        });
        setStream(s);
        if (videoRef.current) videoRef.current.srcObject = s;

        if (file) {
          const audioURL = URL.createObjectURL(file);
          if (audioRef.current) {
            audioRef.current.src = audioURL;
            audioRef.current.currentTime = 0;
            audioRef.current.muted = isMuted;
          }
        }
      } catch (e) {
        setError(e.message || "Camera access denied");
        setCamOpen(false);
      }
    }

    startCamera();

    return () => {
      if (stream) stream.getTracks().forEach((t) => t.stop());
      if (audioRef.current) audioRef.current.pause();
    };
  }, [camOpen, file, isMuted]);

  function closeCamera() {
    setCamOpen(false);
    setIsRecording(false);
    setCountdown(0);
    if (stream) stream.getTracks().forEach((t) => t.stop());
    setStream(null);
    if (audioRef.current) audioRef.current.pause();
  }

  function startCountdownAndRecord() {
    let c = 3;
    setCountdown(c);
    const iv = setInterval(() => {
      c -= 1;
      setCountdown(c);
      if (c === 0) {
        clearInterval(iv);
        startRecording();
      }
    }, 1000);
  }

  function startRecording() {
    if (!videoRef.current?.srcObject) return;

    const rec = new MediaRecorder(videoRef.current.srcObject, {
      mimeType: "video/webm",
    });
    recorderRef.current = rec;

    const chunks = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.start();
    setIsRecording(true);

    if (audioRef.current) {
      audioRef.current.muted = isMuted;
      audioRef.current.play();

      audioRef.current.onended = () => {
        setTimeout(() => {
          if (rec.state !== "inactive") rec.stop();
        }, 1000); // stop 1s after audio ends
      };
    }

    rec.onstop = () => {
      if (audioRef.current) audioRef.current.pause();
      const recordedFile = new File([new Blob(chunks)], "camera.webm", {
        type: "video/webm",
      });
      setFile(recordedFile);
      setIsRecording(false);
      closeCamera();
      startUpload(recordedFile); // process extraction
    };
  }

  /* ================= RENDER ================= */
  return (
    <div className="job-panel">
      {/* File Input Section */}
      <div className="file-input-wrapper">
        <input
          type="file"
          id={`file-input-${kind}`}
          accept="video/*"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="hidden-input"
        />
        <label htmlFor={`file-input-${kind}`} className="file-input-label">
          <span className="file-input-icon">📁</span>
          <span className="file-input-text">
            {file ? file.name : "Click to select or drag video here"}
          </span>
          <span className="file-input-hint">
            {file && `(${(file.size / 1024 / 1024).toFixed(1)} MB)`}
          </span>
        </label>
      </div>

      {/* Upload Button */}
      <button
        onClick={() => startUpload(file)}
        disabled={!file || status === "uploading" || status === "processing"}
        className={`upload-btn ${status === "uploading" || status === "processing" ? "loading" : ""}`}
      >
        <span className="btn-icon">
          {status === "uploading" ? "📤" : status === "processing" ? "⚙️" : "▶️"}
        </span>
        <span className="btn-text">
          {status === "uploading" ? "Uploading..." : status === "processing" ? "Processing..." : "Upload & Extract"}
        </span>
      </button>

      {/* Status Display */}
      {(status !== "idle" || jobId) && (
        <div className="status-container">
          {/* Status Badge */}
          <div className="status-badge-wrapper">
            <div className={`status-badge ${status}`}>
              <span className="status-icon">
                {status === "idle" ? "⏳" : status === "uploading" ? "📤" : status === "queued" ? "⏱️" : status === "processing" ? "⚙️" : status === "done" ? "✅" : "❌"}
              </span>
              <span className="status-text">{status.charAt(0).toUpperCase() + status.slice(1)}</span>
            </div>
          </div>

          {/* Progress Bar */}
          {(status === "uploading" || status === "processing") && (
            <div className="progress-section">
              <div className="progress-info">
                <span className="progress-label">Progress</span>
                <span className="progress-value">{progress}%</span>
              </div>
              <div className="progress-bar-container">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                <span className="progress-bar-text">{progress}%</span>
              </div>
            </div>
          )}

          {/* Job Info */}
          {jobId && (
            <div className="job-info">
              <div className="info-row">
                <span className="info-label">🆔 Job ID</span>
                <span className="info-value">{jobId}</span>
              </div>
              {videoId && (
                <div className="info-row">
                  <span className="info-label">🎬 Video ID</span>
                  <span className="info-value">{videoId}</span>
                </div>
              )}
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="error-banner">
              <span className="error-icon">⚠️</span>
              <span className="error-text">{error}</span>
            </div>
          )}
        </div>
      )}

      {/* Record Button (disabled for now) */}
      {ENABLE_RECORD && (
        <button
          onClick={openCamera}
          className="record-btn"
          title="Record video using your camera"
        >
          <span className="btn-icon">🎥</span>
          <span className="btn-text">Record Video</span>
        </button>
      )}

      {/* CAMERA POPUP */}
      {ENABLE_RECORD && camOpen && (
        <div className="camera-modal">
          <div className="camera-content">
            <div className="camera-header">
              <h3 className="camera-title">📹 Record Video</h3>
              <button onClick={closeCamera} className="camera-close">✕</button>
            </div>

            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="camera-video"
            />
            <audio ref={audioRef} hidden />

            {countdown > 0 && (
              <div className="countdown-display">
                {countdown}
              </div>
            )}

            <div className="camera-controls">
              <button
                onClick={startCountdownAndRecord}
                disabled={isRecording || countdown > 0}
                className={`camera-btn record ${isRecording || countdown > 0 ? "disabled" : ""}`}
              >
                <span>🔴</span>
                {isRecording ? "Recording..." : countdown > 0 ? "Starting..." : "Record"}
              </button>

              <button
                onClick={() => recorderRef.current?.stop()}
                disabled={!isRecording}
                className={`camera-btn stop ${!isRecording ? "disabled" : ""}`}
              >
                <span>⏹️</span>
                Stop
              </button>

              <button
                onClick={() => setIsMuted(!isMuted)}
                className={`camera-btn audio ${isMuted ? "muted" : ""}`}
              >
                <span>{isMuted ? "🔇" : "🔊"}</span>
                {isMuted ? "Unmute" : "Mute"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
