// src/App.jsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import JobPanel from "./JobPanel.jsx";
import SkeletonCanvas from "./SkeletonCanvas.jsx";
import ComparePanel from "./ComparePanel.jsx";
import "./App.css";

export default function App() {
  // Toggle visibility for certain result fields
  const SHOW_FINAL_SCORE = false;
  const SHOW_AUTOSYNC_SHIFT = false;
  const [refPreview, setRefPreview] = useState(null);
  const [userPreview, setUserPreview] = useState(null);

  const [refJobId, setRefJobId] = useState("");
  const [userJobId, setUserJobId] = useState("");

  const [compareResult, setCompareResult] = useState(null);
  const [compareJobId, setCompareJobId] = useState(null);
  const [frame, setFrame] = useState(0);

  // ✅ playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [speedFine, setSpeedFine] = useState(1); // slider for fine-grained speed
  const [smoothness, setSmoothness] = useState(0.6);

  const rafRef = useRef(0);
  const lastTRef = useRef(0);
  const frameFloatRef = useRef(0);
  const isPlayingRef = useRef(false);

  const BASE_FPS = 30;

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
    setFrame(0);
    setIsPlaying(false);
    isPlayingRef.current = false;
    frameFloatRef.current = 0;
  }, []);

  const refLen = refPreview?.kpts?.length || 0;
  const userLen = userPreview?.kpts?.length || 0;

  const maxFrames = useMemo(() => Math.max(refLen, userLen, 0), [refLen, userLen]);
  const lastFrame = useMemo(() => Math.max(0, maxFrames - 1), [maxFrames]);

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

      // advance fractional frame
      frameFloatRef.current += dt * fps;

      let next = Math.floor(frameFloatRef.current);
      if (next >= lastFrame) {
        next = lastFrame;
        frameFloatRef.current = lastFrame;
        setFrame(next);
        stopPlayback();
        return;
      }

      // only update state if changed (reduces re-render pressure)
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

    // sync float with current frame
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
    if (isPlayingRef.current) {
      // continue playing smoothly from 0
      lastTRef.current = 0;
    }
  }, []);

  const handleCompareResult = useCallback(({ compareJobId: cj, data }) => {
    setCompareJobId(cj);
    setCompareResult(data);
  }, []);

  const handleJumpToFrame = useCallback((t) => {
    const tt = Math.max(0, Math.floor(Number(t) || 0));
    frameFloatRef.current = tt;
    setFrame(tt);
  }, []);

  useEffect(() => {
    if (maxFrames <= 0) stopPlayback();
    return () => stopPlayback();
  }, [maxFrames, stopPlayback]);

  // If speed changes while playing, no restart needed (rAF uses live speed)

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
    return items; // preserve original index order
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

  // (LLM verdict handled inside ComparePanel; avoid duplicate fetch/render here)

  return (
    <div className="app-container">
      {/* ========== HEADER ========== */}
      <header className="app-header">
        <h1>🎭 Dance Evaluation Studio</h1>
        <p>Compare reference and user dance videos with AI-powered skeleton analysis</p>
      </header>

      <main className="app-main">
        {/* ========== STEP INDICATOR ========== */}
        <div className="step-indicator">
          <div className={`step-badge ${refPreview ? "completed" : "active"}`}>1</div>
          <span className="step-arrow">→</span>
          <div className={`step-badge ${userPreview ? "completed" : refPreview ? "active" : ""}`}>2</div>
          <span className="step-arrow">→</span>
          <div className={`step-badge ${compareResult ? "completed" : userPreview ? "active" : ""}`}>3</div>
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
            <JobPanel kind="ref" label="" onReady={onReady} />
            {refPreview && (
              <div className="status-info">
                <div className="status-label">✓ Extracted Successfully</div>
                <div className="status-value">Job ID: {refJobId}</div>
                <div className="status-value">Frames: {refLen}</div>
              </div>
            )}
          </div>

          <div className={`upload-panel ${userPreview ? "active" : ""}`}>
            <div className="panel-header">
              <div className="panel-icon">👤</div>
              <div>
                <span className="panel-title">User Video</span>
                <span className="panel-description">Upload the performance to evaluate</span>
              </div>
            </div>
            <JobPanel kind="user" label="" onReady={onReady} />
            {userPreview && (
              <div className="status-info">
                <div className="status-label">✓ Extracted Successfully</div>
                <div className="status-value">Job ID: {userJobId}</div>
                <div className="status-value">Frames: {userLen}</div>
              </div>
            )}
          </div>
        </section>

        {/* ========== PREVIEW SECTION ========== */}
        {maxFrames > 0 && (
          <section className="preview-section">
            <h2 className="section-title">
              <span className="section-icon">👁️</span>
              Preview & Playback
            </h2>

            <div className="preview-content">
              {/* Frame Control */}
              <div className="frame-control">
                <div className="frame-info">
                  <div className="frame-counter">
                    Frame: <strong>{frame}</strong> / {lastFrame}
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
                        style={{ width: '100%', maxWidth: 140, minWidth: 80 }}
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
                    <span>📊 Reference Skeleton</span>
                    <span className="canvas-label-badge">Normalized</span>
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
                    <span>📊 User Skeleton</span>
                    <span className="canvas-label-badge">Aligned</span>
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
                  />
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Smoothness control */}
        {maxFrames > 0 && (
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
            <label style={{ fontSize: 13, whiteSpace: "nowrap" }}>Skeleton Smoothness:</label>
            <input
              type="range"
              min={0}
              max={0.95}
              step={0.01}
              value={smoothness}
              onChange={(e) => setSmoothness(parseFloat(e.target.value))}
              style={{ flex: "1 1 auto", width: '100%', maxWidth: 220, minWidth: 100 }}
            />
            <span style={{ minWidth: 36, textAlign: "right", whiteSpace: "nowrap" }}>{(smoothness).toFixed(2)}</span>
          </div>
        )}

        {maxFrames === 0 && (
          <section className="preview-section">
            <div className="preview-empty">
              <div className="preview-empty-icon">📹</div>
              <p>Upload both videos above and wait for extraction to complete</p>
            </div>
          </section>
        )}

        {/* ========== COMPARE SECTION ========== */}
        {refJobId && userJobId && (
          <section className="compare-section">
            <h2 className="section-title">
              <span className="section-icon">⚖️</span>
              Comparison Analysis
            </h2>
            <ComparePanel
              refExtractJobId={refJobId}
              userExtractJobId={userJobId}
              onResult={handleCompareResult}
              onJumpToFrame={handleJumpToFrame}
            />
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

            {/* AI verdict is shown in the Compare panel to avoid duplicate UI */}

            {/* ST-GCN Debug */}
            {stgcnEnabled && dbg && (
              <div className="debug-info" style={{ marginTop: "var(--spacing-lg)" }}>
                <div className="debug-title">🧠 ST-GCN Embedding Analysis</div>
                <div className="debug-row">
                  <span className="debug-key">Cosine Similarity:</span>
                  <span>
                    {fmt(dbg.cosine_raw ?? dbg.cosine_raw_matrix_mean, 4)}
                  </span>
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
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
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
                      style={{ width: '100%', maxWidth: 64, minWidth: 40, padding: 6, borderRadius: 8, border: "1px solid var(--border-color)", background: "transparent", color: "var(--text-primary)" }}
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
                  <h4 style={{ fontSize: "0.95rem", color: "var(--text-secondary)", margin: 0 }}>All Windows ({allWindows.length})</h4>
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
          </section>
        )}
      </main>
    </div>
  );
}
