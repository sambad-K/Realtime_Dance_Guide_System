import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "./Practice.module.css";
import { setPracticeTransfer } from "../../utils/practiceTransfer";
import { getPracticeSession, setPracticeSession } from "../../utils/practiceSessionStore";

export default function Practice() {
  const savedSession = getPracticeSession();
  const [referenceVideo, setReferenceVideo] = useState(savedSession?.referenceVideo ?? null);
  const [referenceVideoUrl, setReferenceVideoUrl] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const [audioOn, setAudioOn] = useState(savedSession?.audioOn ?? false);
  const [playbackSpeed, setPlaybackSpeed] = useState(savedSession?.playbackSpeed ?? "1");
  const [recordedVideoFile, setRecordedVideoFile] = useState(savedSession?.recordedVideoFile ?? null);
  const [trimmedReferenceFile, setTrimmedReferenceFile] = useState(savedSession?.trimmedReferenceFile ?? null);
  const [isPreparingReferenceClip, setIsPreparingReferenceClip] = useState(false);
  const [videoAspectRatio, setVideoAspectRatio] = useState(savedSession?.videoAspectRatio ?? "16 / 9");
  const [showAdvancedControls, setShowAdvancedControls] = useState(savedSession?.showAdvancedControls ?? false);
  const [isPracticeModalOpen, setIsPracticeModalOpen] = useState(savedSession?.isPracticeModalOpen ?? false);
  const navigate = useNavigate();

  const referenceVideoRef = useRef(null);
  const cameraVideoRef = useRef(null);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const referenceRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const referenceChunksRef = useRef([]);
  const countdownIntervalRef = useRef(null);

  useEffect(() => {
    if (!referenceVideo) {
      setReferenceVideoUrl("");
      return undefined;
    }

    const objectUrl = URL.createObjectURL(referenceVideo);
    setReferenceVideoUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [referenceVideo]);

  useEffect(() => {
    setPracticeSession({
      referenceVideo,
      recordedVideoFile,
      trimmedReferenceFile,
      videoAspectRatio,
      audioOn,
      playbackSpeed,
      showAdvancedControls,
      isPracticeModalOpen,
    });
  }, [
    referenceVideo,
    recordedVideoFile,
    trimmedReferenceFile,
    videoAspectRatio,
    audioOn,
    playbackSpeed,
    showAdvancedControls,
    isPracticeModalOpen,
  ]);

  useEffect(() => {
    return () => {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  useEffect(() => {
    if (isPracticeModalOpen && referenceVideo && !cameraOpen) {
      openCamera();
    }
  }, [isPracticeModalOpen, referenceVideo]);

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = null;
    }
  };

  const openCamera = async () => {
    setCameraError("");
    stopStream();

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: {
          facingMode: "user",
        },
      });

      streamRef.current = mediaStream;
      setCameraOpen(true);

      if (cameraVideoRef.current) {
        cameraVideoRef.current.srcObject = mediaStream;
      }
    } catch {
      setCameraError("Camera access failed. Please allow camera permission and try again.");
      setCameraOpen(false);
    }
  };

  const handleCloseCamera = () => {
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }

    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }

    if (referenceVideoRef.current) {
      referenceVideoRef.current.pause();
    }

    stopReferenceCapture();

    setCountdown(null);
    setIsRecording(false);
    stopStream();
    setCameraOpen(false);
  };

  const handleClosePracticeModal = () => {
    handleCloseCamera();
    setIsPracticeModalOpen(false);
  };

  const handleReferenceUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setReferenceVideo(file);
    setTrimmedReferenceFile(null);
    setShowAdvancedControls(false);
    setRecordedVideoFile(null);
    setIsPracticeModalOpen(true);
    await openCamera();
  };

  const startRecording = () => {
    if (!streamRef.current || isRecording) {
      return;
    }

    chunksRef.current = [];

    try {
      const recorder = new MediaRecorder(streamRef.current);
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        if (!chunksRef.current.length) {
          return;
        }
        const clipBlob = new Blob(chunksRef.current, { type: "video/webm" });
        const clipFile = new File([clipBlob], `user-recording-${Date.now()}.webm`, {
          type: "video/webm",
        });
        setRecordedVideoFile(clipFile);
      };

      recorder.start();
      setIsRecording(true);
    } catch {
      setCameraError("Recording is not supported on this browser/device.");
    }
  };

  const startReferenceCapture = () => {
    if (!referenceVideoRef.current || referenceRecorderRef.current) {
      return;
    }

    const captureStream = referenceVideoRef.current.captureStream?.();
    if (!captureStream) {
      return;
    }

    referenceChunksRef.current = [];

    try {
      const referenceRecorder = new MediaRecorder(captureStream);
      referenceRecorderRef.current = referenceRecorder;
      setIsPreparingReferenceClip(true);

      referenceRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          referenceChunksRef.current.push(event.data);
        }
      };

      referenceRecorder.onstop = () => {
        if (referenceChunksRef.current.length > 0) {
          const clipBlob = new Blob(referenceChunksRef.current, { type: "video/webm" });
          const clipFile = new File([clipBlob], `reference-clipped-${Date.now()}.webm`, {
            type: "video/webm",
          });
          setTrimmedReferenceFile(clipFile);
        }

        referenceRecorderRef.current = null;
        setIsPreparingReferenceClip(false);
      };

      referenceRecorder.start();
    } catch {
      referenceRecorderRef.current = null;
      setIsPreparingReferenceClip(false);
    }
  };

  const stopReferenceCapture = () => {
    if (!referenceRecorderRef.current) {
      return;
    }

    if (referenceRecorderRef.current.state !== "inactive") {
      referenceRecorderRef.current.stop();
    }
  };

  const handleDone = () => {
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }

    setCountdown(null);

    if (referenceVideoRef.current) {
      referenceVideoRef.current.pause();
      referenceVideoRef.current.currentTime = 0;
    }

    stopReferenceCapture();

    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }

    setIsRecording(false);
  };

  const handleReferenceComplete = () => {
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }

    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }

    stopReferenceCapture();

    setCountdown(null);
    setIsRecording(false);
    handleCloseCamera();
  };

  const handleStart = async () => {
    if (!referenceVideoRef.current || !cameraOpen || countdown !== null || isRecording) {
      return;
    }

    const referencePlayer = referenceVideoRef.current;
    referencePlayer.playbackRate = Number(playbackSpeed);
    referencePlayer.muted = !audioOn;
    referencePlayer.currentTime = 0;

    let tick = 3;
    setCountdown(tick);

    countdownIntervalRef.current = setInterval(async () => {
      tick -= 1;

      if (tick > 0) {
        setCountdown(tick);
        return;
      }

      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
      setCountdown(null);

      startRecording();
      startReferenceCapture();

      try {
        await referencePlayer.play();
      } catch {
        setCameraError("Unable to autoplay reference video. Tap video play and press Start again.");
      }
    }, 1000);
  };

  const handleSpeedChange = (event) => {
    const nextSpeed = event.target.value;
    setPlaybackSpeed(nextSpeed);
    if (referenceVideoRef.current) {
      referenceVideoRef.current.playbackRate = Number(nextSpeed);
    }
  };

  const handleReferenceMetadata = () => {
    if (!referenceVideoRef.current) {
      return;
    }

    const width = Number(referenceVideoRef.current.videoWidth || 0);
    const height = Number(referenceVideoRef.current.videoHeight || 0);
    if (!width || !height) {
      return;
    }

    const rawRatio = width / height;
    const safeRatio = Math.min(2.1, Math.max(0.65, rawRatio));
    setVideoAspectRatio(`${safeRatio} / 1`);
  };

  const handleLetsCheck = () => {
    if (!referenceVideo) {
      setCameraError("Upload a reference video first.");
      return;
    }

    if (!recordedVideoFile) {
      setCameraError("");
      return;
    }

    if (isPreparingReferenceClip) {
      setCameraError("Preparing reference clip. Please wait a moment and try again.");
      return;
    }

    setPracticeTransfer({
      referenceFile: trimmedReferenceFile || referenceVideo,
      userFile: recordedVideoFile,
    });

    navigate("/test");
  };

  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>Practice Mode</h2>

      {!referenceVideo && (
        <>
          <label htmlFor="referenceVideoUpload" className={styles.uploadLabel}>
            <span className={styles.uploadIcon}>📁</span>
            <span className={styles.uploadText}>Upload Reference Video File</span>
            <span className={styles.uploadHint}>Tap to choose a video</span>
          </label>
          <input
            type="file"
            id="referenceVideoUpload"
            accept="video/*"
            className={styles.hiddenFileInput}
            onChange={handleReferenceUpload}
          />
        </>
      )}

      {referenceVideo && (
        <p className={styles.filenameText}>
          🎥 <strong>{referenceVideo.name}</strong>
        </p>
      )}

      {cameraError && <p className={styles.errorText}>{cameraError}</p>}

      {referenceVideo && isPracticeModalOpen && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Practice Session</h3>
              <button
                type="button"
                className={styles.modalCloseButton}
                onClick={handleClosePracticeModal}
              >
                Close
              </button>
            </div>

            <div className={styles.stageBox}>
              <div className={styles.practiceStage}>
                <div className={styles.referenceShell}>
                  <h3 className={styles.panelTitle}>Reference</h3>
                  <video
                    ref={referenceVideoRef}
                    playsInline
                    className={styles.referenceVideo}
                    src={referenceVideoUrl}
                    muted={!audioOn}
                    onEnded={handleReferenceComplete}
                    onLoadedMetadata={handleReferenceMetadata}
                    style={{ aspectRatio: videoAspectRatio }}
                  />
                </div>

                <div className={styles.cameraShell}>
                  <h3 className={styles.panelTitle}>Camera</h3>
                  <video
                    ref={cameraVideoRef}
                    autoPlay
                    muted
                    playsInline
                    className={styles.cameraVideo}
                    style={{ aspectRatio: videoAspectRatio }}
                  />

                  {countdown !== null && <div className={styles.countdownBadge}>{countdown}</div>}

                  <div className={styles.cameraControls}>
                    <button type="button" className={styles.startButton} onClick={handleStart}>
                      Start
                    </button>
                    <button type="button" className={styles.doneButton} onClick={handleDone}>
                      Done
                    </button>

                    <button
                      type="button"
                      className={styles.moreToggleButton}
                      onClick={() => setShowAdvancedControls((previous) => !previous)}
                    >
                      {showAdvancedControls ? "Hide Controls" : "More Controls"}
                    </button>
                  </div>

                  {showAdvancedControls && (
                    <div className={styles.advancedControls}>
                      <button
                        type="button"
                        className={styles.audioButton}
                        onClick={() => setAudioOn((previous) => !previous)}
                      >
                        {audioOn ? "Audio On" : "Audio Off"}
                      </button>

                      <div className={styles.speedGroup}>
                        <label htmlFor="videoSpeed" className={styles.speedControl}>
                          Speed
                        </label>
                        <select
                          id="videoSpeed"
                          className={styles.speedSelect}
                          value={playbackSpeed}
                          onChange={handleSpeedChange}
                        >
                          <option value="0.5">0.5x</option>
                          <option value="0.75">0.75x</option>
                          <option value="1">1x</option>
                          <option value="1.25">1.25x</option>
                          <option value="1.5">1.5x</option>
                        </select>
                      </div>

                      <button type="button" className={styles.closeButton} onClick={handleClosePracticeModal}>
                        Close Camera
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <button type="button" className={styles.letsCheckButton} onClick={handleLetsCheck}>
              lets check
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
