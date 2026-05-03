// src/App.jsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import JobPanel from "./JobPanel.jsx";
import SkeletonCanvas from "./SkeletonCanvas.jsx";
import ComparePanel from "./ComparePanel.jsx";
import Live from "./Live.jsx";
import "./test.css";
import { STORAGE_KEYS } from "../../constants/index.js";
import apiClient from "../../services/apiClient";
import { consumePracticeTransfer } from "../../utils/practiceTransfer";

export default function Test() {
  // Toggle visibility for certain result fields
  const SHOW_FINAL_SCORE = false;
  // enable frame-shift/auto-sync card when data present
  const SHOW_AUTOSYNC_SHIFT = true;
  const [refPreview, setRefPreview] = useState(null);
  const [userPreview, setUserPreview] = useState(null);

  const [refJobId, setRefJobId] = useState("");
  const [userJobId, setUserJobId] = useState("");

  const [compareResult, setCompareResult] = useState(null);
  const [compareJobId, setCompareJobId] = useState(null);
  const [frame, setFrame] = useState(0);
  const [prefillRefFile, setPrefillRefFile] = useState(null);
  const [prefillUserFile, setPrefillUserFile] = useState(null);

  // ✅ playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [speedFine, setSpeedFine] = useState(1); // slider for fine-grained speed
  const [smoothness, setSmoothness] = useState(0.6);
  const [liveLimbColors, setLiveLimbColors] = useState(null);
  const [liveRestartKey, setLiveRestartKey] = useState(0);
  const [showLive, setShowLive] = useState(false);

  const rafRef = useRef(0);
  const lastTRef = useRef(0);
  const frameFloatRef = useRef(0);
  const isPlayingRef = useRef(false);

  const BASE_FPS = 30;

  useEffect(() => {
    const transfer = consumePracticeTransfer();
    if (!transfer) {
      return;
    }

    setPrefillRefFile(transfer.referenceFile || null);
    setPrefillUserFile(transfer.userFile || null);
  }, []);

  // ✅ technical details toggle
  const [showTechDetails, setShowTechDetails] = useState(false);

  const onReady = useCallback(({ kind, jobId, preview }) => {
    if (kind === "ref") {
      setRefPreview(preview);
      setRefJobId(jobId);
    }
    if (kind === "user") {
      setUserPreview(preview);
      setUserJobId(jobId);
    }

    // reset when new preview arrives
    setCompareResult(null);
    setCompareJobId(null);
    setFrame(0);
    setIsPlaying(false);
    isPlayingRef.current = false;
    frameFloatRef.current = 0;
    setLiveLimbColors(null);
    setLiveRestartKey((v) => v + 1);

    setShowTechDetails(false);
  }, []);

  const refLen = refPreview?.kpts?.length || 0;
  const userLen = userPreview?.kpts?.length || 0;

  const maxFrames = useMemo(() => Math.max(refLen, userLen, 0), [refLen, userLen]);
  const lastFrame = useMemo(() => Math.max(0, maxFrames - 1), [maxFrames]);

  // derive FPS from compare metadata when available; fallback to BASE_FPS (video processed at 30fps)
  const fps = useMemo(() => {
    try {
      const m = compareResult?.meta || {};
      const f = m?.fps || m?.ref_fps || m?.user_fps;
      const n = Number(f);
      return Number.isFinite(n) && n > 0 ? n : BASE_FPS;
    } catch (e) {
      return BASE_FPS;
    }
  }, [compareResult]);

  const formatSeconds = (frm) => {
    const s = Number(frm) / Math.max(1e-6, Number(fps || BASE_FPS));
    return Number.isFinite(s) ? s.toFixed(2) : "0.00";
  };

  const refFrame = useMemo(() => {
    if (refLen <= 0) return 0;
    return Math.max(0, Math.min(frame, refLen - 1));
  }, [frame, refLen]);

  const userFrameAligned = useMemo(() => {
    if (userLen <= 0) return 0;

    const fallback = Math.max(0, Math.min(frame, userLen - 1));
    const map = compareResult?.align_ref_to_user;

    if (Array.isArray(map) && map.length > 0) {
      const u = map[Math.max(0, Math.min(refFrame, map.length - 1))];
      const uu = Number(u);
      if (Number.isFinite(uu)) return Math.max(0, Math.min(uu, userLen - 1));
    }
    return fallback;
  }, [compareResult, frame, refFrame, userLen]);

  // =========================
  // Playback (requestAnimationFrame)
  // =========================
  const stopPlayback = useCallback(() => {
    isPlayingRef.current = false;
    setIsPlaying(false);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    lastTRef.current = 0;
  }, []);

  const tick = useCallback(
    (tNow) => {
      if (!isPlayingRef.current) return;

      const fps = BASE_FPS * (Number(speed) || 1);
      const dt = lastTRef.current ? (tNow - lastTRef.current) / 1000 : 0;
      lastTRef.current = tNow;

      frameFloatRef.current += dt * fps;

      let next = Math.floor(frameFloatRef.current);
      if (next >= lastFrame) {
        next = lastFrame;
        frameFloatRef.current = lastFrame;
        setFrame(next);
        stopPlayback();
        return;
      }

      setFrame((prev) => (prev === next ? prev : next));

      rafRef.current = requestAnimationFrame(tick);
    },
    [BASE_FPS, lastFrame, speed, stopPlayback]
  );

  const startPlayback = useCallback(() => {
    if (maxFrames <= 0) return;
    if (isPlayingRef.current) return;

    isPlayingRef.current = true;
    setIsPlaying(true);

    frameFloatRef.current = Number(frame) || 0;
    lastTRef.current = 0;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(tick);
  }, [frame, maxFrames, tick]);

  const togglePlay = useCallback(() => {
    if (isPlayingRef.current) stopPlayback();
    else startPlayback();
  }, [startPlayback, stopPlayback]);

  const restartPlayback = useCallback(() => {
    frameFloatRef.current = 0;
    setFrame(0);
    setLiveRestartKey((v) => v + 1);
    if (isPlayingRef.current) {
      lastTRef.current = 0;
    }
  }, []);

  useEffect(() => {
    if (maxFrames <= 0) stopPlayback();
    return () => stopPlayback();
  }, [maxFrames, stopPlayback]);

  // =========================
  // Results helpers (unchanged)
  // =========================
  const fmt = (x, d = 2) => {
    const n = Number(x);
    if (!Number.isFinite(n)) return "-";
    return n.toFixed(d);
  };
  
  const baseScore = Number(compareResult?.overall_score_0_100 ?? 0);
  const finalScore = Number(compareResult?.final_score_0_100 ?? baseScore);

  const stgcn = compareResult?.stgcn_embedding || null;
  const stgcnEnabled = Boolean(stgcn?.enabled);
  const stgcnSim01 = stgcnEnabled ? Number(stgcn?.sim_0_1) : null;
  const stgcnScore100 =
    stgcnSim01 != null && Number.isFinite(stgcnSim01) ? stgcnSim01 * 100 : null;

  const dbg = stgcnEnabled ? stgcn?.debug : null;

  const winScores = Array.isArray(stgcn?.window_scores) ? stgcn.window_scores : [];
  const winCenters = Array.isArray(stgcn?.window_centers_ref) ? stgcn.window_centers_ref : [];
  const winCount = Math.min(winScores.length, winCenters.length);

  const [worstN, setWorstN] = useState(8);

  const allWindows = useMemo(() => {
    if (!winCount) return [];
    const items = [];
    for (let i = 0; i < winCount; i++) {
      items.push({ i, center: Number(winCenters[i]), score: Number(winScores[i]) });
    }
    return items;
  }, [winCenters, winCount, winScores]);

  const worstWindows = useMemo(() => {
    if (!allWindows.length) return [];
    const items = [...allWindows];
    items.sort((a, b) => (a.score ?? 0) - (b.score ?? 0));
    return items.slice(0, Math.min(worstN || 8, items.length));
  }, [allWindows, worstN]);

  const clamp01 = (x) => Math.max(0, Math.min(1, x));
  const attentionLevel =
    stgcnEnabled && stgcnSim01 != null && Number.isFinite(stgcnSim01)
      ? clamp01((1 - stgcnSim01) * 1.3)
      : 0;

  const dtwDbg = compareResult?.dtw_debug || null;

  // Save state & handler for exporting results to backend
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState(null);

  const toJsonText = (value) => {
    if (value == null) return "";
    if (typeof value === "string") return value;
    try {
      return JSON.stringify(value);
    } catch (_) {
      return String(value || "");
    }
  };

  const hasAnyVerdict = Boolean(compareResult?.verdict || compareResult?.deepVerdict);

  const saveResults = async () => {
    setSaveMessage(null);
    if (!compareResult) {
      setSaveMessage("No results to save");
      return;
    }
    setSaving(true);
    try {
      const quickVerdict = compareResult?.verdict || null;
      const finalDeepVerdict = compareResult?.deepVerdict || null;

      const bodyToSend = {
        ref_job_id: refJobId || "",
        user_job_id: userJobId || "",
        compare_job_id: compareJobId || "",
        dtw_score: Number(baseScore || 0),
        final_score: Number(finalScore || baseScore || 0),
        stgcn_score: Number(stgcnScore100 || 0),
        ai_verdict: toJsonText(quickVerdict || finalDeepVerdict),
        deep_verdict: toJsonText(finalDeepVerdict),
        windows: Array.isArray(worstWindows) ? worstWindows : [],
        window_count: Number(winCount || 0),
        payload: {
          refJobId,
          userJobId,
          compareJobId,
          dtwScore: Number(baseScore || 0),
          finalScore: Number(finalScore || baseScore || 0),
          stgcnScore100: Number(stgcnScore100 || 0),
          verdict: quickVerdict,
          deepVerdict: finalDeepVerdict,
          deepStatus: compareResult?.deepStatus || null,
          deepPartials: Array.isArray(compareResult?.deepPartials) ? compareResult.deepPartials : [],
          windows: worstWindows || [],
          windowCount: winCount || 0,
        },
        summary: {
          dtwScore: Number(baseScore || 0),
          finalScore: Number(finalScore || baseScore || 0),
          verdict: quickVerdict || finalDeepVerdict || null,
        },
      };

      console.log("[Test.saveResults] Sending payload:", JSON.stringify(bodyToSend, null, 2));

      const res = await apiClient.post(`/api/test-results/`, bodyToSend);

      console.log("[Test.saveResults] Response status:", res.status);
      console.log("[Test.saveResults] Response data:", res.data);

      if (res.status !== 201 && res.status !== 200) {
        throw new Error(res.statusText || "Save failed");
      }

      setSaveMessage(hasAnyVerdict ? "Saved ✓" : "Saved ✓ (AI verdict still processing)");
    } catch (err) {
      console.error("[Test.saveResults] Full error:", err);
      console.error("[Test.saveResults] Error response:", err?.response?.data);
      setSaveMessage(`Error: ${err?.response?.data?.detail || err.message || "save failed"}`);
    } finally {
      setSaving(false);
    }
  };

  // determine deep analysis progress (used to gate saving)
  const deepProgress = Number(
    compareResult?.deepStatus?.progress ?? (compareResult?.deepVerdict ? 100 : 0)
  );
  const deepDone = deepProgress >= 100;

  return (
    <div className="app-container">

      <main className="app-main">
        {/* ========== STEP INDICATOR ========== */}
        <div className="step-indicator">
          <div className={`step-badge ${refPreview ? "completed" : "active"}`}>1</div>
          <span className="step-arrow">→</span>
          <div className={`step-badge ${userPreview ? "completed" : refPreview ? "active" : ""}`}>
            2
          </div>
          <span className="step-arrow">→</span>
          <div className={`step-badge ${compareResult ? "completed" : userPreview ? "active" : ""}`}>
            3
          </div>
        </div>

        {/* ========== UPLOAD SECTION ========== */}
        <section className="upload-section">
          <div className={`upload-panel ${refPreview ? "active" : ""}`}>
            <div className="panel-header">
              <div className="panel-icon">📹</div>
              <div>
                <span className="panel-title">Reference Video</span>
                <span className="panel-description">Upload the ideal performance</span>
              </div>
            </div>
            <JobPanel
              kind="ref"
              label=""
              onReady={onReady}
              initialFile={prefillRefFile}
            />

          </div>

          <div className={`upload-panel ${userPreview ? "active" : ""}`}>
            <div className="panel-header">
              <div className="panel-icon">👤</div>
              <div>
                <span className="panel-title">User Video</span>
                <span className="panel-description">Upload the performance to evaluate</span>
              </div>
            </div>
            <JobPanel
              kind="user"
              label=""
              onReady={onReady}
              initialFile={prefillUserFile}
            />

          </div>
        </section>

        {/* ========== PREVIEW SECTION ========== */}
        {maxFrames > 0 && compareResult && (
          <section className="preview-section">
          

            <div className="preview-content">
              {/* Frame Control */}
              <div className="frame-control">
                <div className="frame-info">
                  <div className="frame-counter">
                    Time: <strong>{formatSeconds(frame)}s</strong> / {formatSeconds(lastFrame)}s
                    <div style={{ fontSize: 12, marginLeft: 8, color: "var(--muted)" }}>
                      ({frame}f / {lastFrame}f)
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "var(--spacing-md)" }}>
                    <span className="speed-label">Speed:</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <select
                        className="speed-selector"
                        value={speed}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          setSpeed(v);
                          setSpeedFine(v);
                        }}
                      >
                        <option value={0.25}>0.25×</option>
                        <option value={0.5}>0.5×</option>
                        <option value={0.75}>0.75×</option>
                        <option value={1}>1×</option>
                        <option value={1.25}>1.25×</option>
                        <option value={1.5}>1.5×</option>
                        <option value={2}>2×</option>
                      </select>
                      <input
                        type="range"
                        min={0.25}
                        max={3}
                        step={0.05}
                        value={speedFine}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          setSpeedFine(v);
                          setSpeed(v);
                        }}
                        title={`Playback speed: ${speedFine.toFixed(2)}x`}
                        style={{ width: '140px', maxWidth: '100%' }}
                      />
                    </div>
                  </div>
                </div>

                <input
                  type="range"
                  className="frame-slider"
                  min={0}
                  max={lastFrame}
                  value={Math.max(0, Math.min(frame, lastFrame))}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    frameFloatRef.current = v;
                    setFrame(v);
                  }}
                />

                {/* Playback Controls */}
                <div className="playback-controls">
                  <button
                    className={`control-btn primary`}
                    onClick={togglePlay}
                    disabled={maxFrames <= 0}
                    title={isPlaying ? "Pause playback" : "Start playback"}
                  >
                    <span>{isPlaying ? "⏸️" : "▶️"}</span>
                    {isPlaying ? "Pause" : "Play"}
                  </button>

                  <button
                    className="control-btn"
                    onClick={stopPlayback}
                    disabled={!isPlaying}
                    title="Stop playback"
                  >
                    <span>⏹️</span>
                    Stop
                  </button>

                  <button
                    className="control-btn"
                    onClick={restartPlayback}
                    disabled={maxFrames <= 0}
                    title="Restart playback"
                  >
                    <span>🔄</span>
                    Restart
                  </button>
                </div>
              </div>

              {/* Canvas Grid */}
              <div className="canvas-grid">
                <div className="canvas-container">
                  <label className="canvas-label">
                    <span>📊 Reference</span>
                  </label>
                  <SkeletonCanvas
                    title=""
                    kpts={refPreview?.kpts}
                    conf={refPreview?.conf}
                    frame={refFrame}
                    normalColor="#00ff00"
                    smoothness={smoothness}
                    compareResult={compareResult}
                  />
                </div>

                <div className="canvas-container">
                  <label className="canvas-label">
                    <span>📊 User</span>
                  </label>
                  <SkeletonCanvas
                    title=""
                    kpts={userPreview?.kpts}
                    conf={userPreview?.conf}
                    frame={userFrameAligned}
                    wrongnessTimeline={compareResult?.wrongness_limb_timeline || null}
                    wrongnessFrame={refFrame}
                    confThr={0.22}
                    strictness={0.77}
                    wrongWarn={0.12}
                    wrongGood={0.06}
                    maxRedLimbs={3}
                    normalColor="#00ff00"
                    attentionLevel={attentionLevel}
                    smoothness={smoothness}
                    compareResult={compareResult}
                    onLimbVisualChange={setLiveLimbColors}
                  />
                </div>
              </div>

            </div>
          </section>
        )}

        {/* Smoothness control removed — UI hidden per request (state remains) */}

        {maxFrames === 0 && (
          <section className="preview-section">
            <div className="preview-empty">
              <div className="preview-empty-icon">📹</div>
              <p>Upload both videos above and wait for processing to complete</p>
            </div>
          </section>
        )}

        {/* ========== COMPARE SECTION ========== */}
        {refJobId && userJobId && (
          <section className="compare-section">

            <ComparePanel
              refExtractJobId={refJobId}
              userExtractJobId={userJobId}
              onResult={({ compareJobId: cj, data, verdict, deepVerdict, deepStatus, deepPartials }) => {
                console.log("[Test.onResult] Called with:", { cj, data, verdict, deepVerdict, deepStatus, deepPartials });
                setCompareJobId(cj);
                const merged = Object.assign({}, data || {}, {
                  verdict: verdict || null,
                  deepVerdict: deepVerdict || null,
                  deepStatus: deepStatus || null,
                  deepPartials:
                    Array.isArray(deepPartials) && deepPartials.length
                      ? deepPartials
                      : deepStatus && Array.isArray(deepStatus.partial)
                      ? deepStatus.partial
                      : [],
                });
                console.log("[Test.onResult] Setting compareResult to:", merged);
                setCompareResult(merged);
              }}
              onJumpToFrame={(t) => {
                const tt = Math.max(0, Math.floor(Number(t) || 0));
                frameFloatRef.current = tt;
                setFrame(tt);
              }}
            />
          </section>
        )}

        {/* ========== LIVE VIDEO SECTION ========== */}
        {refPreview && userPreview && compareResult && (
          <section className="preview-section" style={{ marginTop: "var(--spacing-xl)" }}>
            {/* Live Toggle Button */}
            <div style={{
              display: "flex",
              alignItems: "center",
              marginBottom: showLive ? "var(--spacing-md)" : 0,
              gap: "var(--spacing-sm)"
            }}>
              <button
                onClick={() => setShowLive(!showLive)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 16px",
                  background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: "600",
                  letterSpacing: "0.5px",
                  boxShadow: "0 4px 12px rgba(102, 126, 234, 0.4)",
                  transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                  transform: showLive ? "translateY(0)" : "translateY(0)",
                }}
                onMouseEnter={(e) => {
                  e.target.style.boxShadow = "0 6px 16px rgba(102, 126, 234, 0.6)";
                  e.target.style.transform = "translateY(-2px)";
                }}
                onMouseLeave={(e) => {
                  e.target.style.boxShadow = "0 4px 12px rgba(102, 126, 234, 0.4)";
                  e.target.style.transform = "translateY(0)";
                }}
              >
                <span style={{
                  display: "inline-block",
                  transition: "transform 0.3s ease",
                  transform: showLive ? "rotate(180deg)" : "rotate(0deg)",
                  fontSize: "16px",
                  lineHeight: "1",
                }}>
                  ▼
                </span>
                (real view)
              </button>
            </div>

            {/* Live Content (Always Mounted, Hidden with CSS) */}
            <div style={{
              display: showLive ? "block" : "none",
              animation: showLive ? "slideDown 0.3s ease" : "none",
            }}>
              <Live
                refPreview={refPreview}
                userPreview={userPreview}
                fps={fps}
                playing={isPlaying}
                restartKey={liveRestartKey}
                limbColors={liveLimbColors}
              />
            </div>

            <style>{`
              @keyframes slideDown {
                from {
                  opacity: 0;
                  transform: translateY(-10px);
                }
                to {
                  opacity: 1;
                  transform: translateY(0);
                }
              }
            `}</style>
          </section>
        )}

        {/* ========== RESULTS SECTION ========== */}
        {compareResult && (
          <section className="results-section">
            <div className="results-header">
              <div className="results-title">
                <span>✨</span>
                Comparison Results
              </div>
            </div>

            {/* Score Cards */}
            <div className="score-grid">
              {/* DTW Score */}
              <div className="score-card">
                <div className="score-label">DTW Score</div>
                <div className="score-value">{fmt(baseScore)}</div>
                <div className="score-bar">
                  <div
                    className="score-bar-fill"
                    style={{ width: `${Math.min(100, baseScore)}%` }}
                  />
                </div>
              </div>

              {/* Final Score */}
              {SHOW_FINAL_SCORE && (
                <div className="score-card">
                  <div className="score-label">Final Score</div>
                  <div className="score-value" style={{ fontSize: "2.5rem" }}>
                    {fmt(finalScore)}
                  </div>
                  <div className="score-bar">
                    <div
                      className="score-bar-fill"
                      style={{ width: `${Math.min(100, finalScore)}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Auto Sync */}
              {SHOW_AUTOSYNC_SHIFT && (
                <div className="score-card">
                  <div className="score-label">Auto Sync Shift</div>
                  <div className="score-value">
                    {Number.isFinite(Number(compareResult?.auto_sync?.shift_frames))
                      ? `${Number(compareResult.auto_sync.shift_frames)}f`
                      : "-"}
                  </div>
                </div>
              )}

              {/* ST-GCN Similarity */}
              {stgcnEnabled && (
                <div className="score-card">
                  <div className="score-label">ST-GCN Similarity</div>
                  <div className="score-value">
                    {stgcnScore100 != null ? `${fmt(stgcnScore100)}` : "N/A"}
                  </div>
                  {stgcnScore100 != null && (
                    <div className="score-bar">
                      <div
                        className="score-bar-fill"
                        style={{ width: `${Math.min(100, stgcnScore100)}%` }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Save Results Button - Shows When Results Available */}
            {(compareResult || (refJobId && userJobId && compareJobId)) && (
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: "var(--spacing-lg)", marginBottom: "var(--spacing-lg)", alignItems: "center" }}>
                <button
                  className={`control-btn primary`}
                  onClick={saveResults}
                  disabled={saving}
                  title={saving ? "Saving…" : "Save comparison results to your profile"}
                >
                  {saving ? "Saving…" : "💾 Save Results"}
                </button>

                {saveMessage && (
                  <div style={{ color: saveMessage.startsWith("Error") ? "var(--error)" : "var(--success)", fontSize: 13 }}>
                    {saveMessage}
                  </div>
                )}
              </div>
            )}

            {/* ✅ Technical toggle button */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
              <button
                className="control-btn"
                onClick={() => setShowTechDetails((v) => !v)}
                title="Toggle technical debug details"
              >
                {showTechDetails ? "Hide technical details" : "Show technical details"}
              </button>
            </div>

            {/* ✅ Hidden technical blocks */}
            {showTechDetails && (
              <>
                {/* Debug Information */}
                {dtwDbg && (
                  <div className="debug-info">
                    <div className="debug-title">📊 DTW Debug Information</div>
                    <div className="debug-row">
                      <span className="debug-key">Valid Ratio:</span>
                      <span>{fmt(dtwDbg.align_valid_ratio, 4)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">Invalid Ratio:</span>
                      <span>{fmt(dtwDbg.align_invalid_ratio, 4)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">Collapse Ratio:</span>
                      <span>{fmt(dtwDbg.align_collapse_ratio, 4)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">DTW Distance Mean:</span>
                      <span>{fmt(dtwDbg.dtw_dist_mean, 6)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">Cosine Valid Mean:</span>
                      <span>{fmt(dtwDbg.cosine_valid_mean, 6)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">Cosine Valid P10:</span>
                      <span>{fmt(dtwDbg.cosine_valid_p10, 6)}</span>
                    </div>
                  </div>
                )}

                {/* ST-GCN Debug */}
                {stgcnEnabled && dbg && (
                  <div className="debug-info" style={{ marginTop: "var(--spacing-lg)" }}>
                    <div className="debug-title">🧠 ST-GCN Embedding Analysis</div>
                    <div className="debug-row">
                      <span className="debug-key">Cosine Similarity:</span>
                      <span>{fmt(dbg.cosine_raw ?? dbg.cosine_raw_matrix_mean, 4)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">Distance:</span>
                      <span>{fmt(dbg.dist, 4)}</span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-key">Motion Mismatch:</span>
                      <span>{fmt(dbg.motion_mismatch, 4)}</span>
                    </div>
                  </div>
                )}

                {/* Windows Analysis */}
                {winCount > 0 && (
                  <div className="windows-section">
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--spacing-md)" }}>
                      <h3 className="section-title" style={{ fontSize: "1rem", margin: 0 }}>
                        <span>🪟</span>
                        Worst Performing Windows ({worstWindows.length} of {winCount})
                      </h3>

                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <label style={{ color: "var(--text-muted)", fontSize: 13 }}>Show worst</label>
                        <input
                          type="number"
                          min={1}
                          max={Math.max(1, winCount)}
                          value={worstN}
                          onChange={(e) => {
                            const v = parseInt(e.target.value || 0, 10);
                            setWorstN(Number.isFinite(v) ? Math.max(1, Math.min(winCount, v)) : 8);
                          }}
                          style={{
                            width: 64,
                            padding: 6,
                            borderRadius: 8,
                            border: "1px solid var(--border-color)",
                            background: "transparent",
                            color: "var(--text-primary)",
                          }}
                        />
                      </div>
                    </div>

                    <div className="worst-windows-list windows-list" style={{ marginTop: "var(--spacing-md)" }}>
                      {worstWindows.map((w, i) => (
                        <div key={i} className="window-item window-item--worst">
                          <div className="window-center">Window {w.i}</div>
                          <div className="window-score">{fmt(w.score)}</div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            Center: {fmt(w.center)}f
                          </div>
                        </div>
                      ))}
                    </div>

                    <div style={{ marginTop: "var(--spacing-lg)" }}>
                      <h4 style={{ fontSize: "0.95rem", color: "var(--text-secondary)", margin: 0 }}>
                        All Windows ({allWindows.length})
                      </h4>
                      <div className="windows-list windows-list--all" style={{ marginTop: "var(--spacing-md)" }}>
                        {allWindows.map((w, i) => (
                          <div key={`all-${i}`} className="window-item window-item--all">
                            <div className="window-center">Window {w.i}</div>
                            <div className="window-score">{fmt(w.score)}</div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              Center: {fmt(w.center)}f
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

              </>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
