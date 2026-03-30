// src/ComparePanel.jsx
import { memo, useEffect, useState, useMemo, useRef } from "react";
import { createCompareJob, getVerdict, getArtifact } from "./api";

function ComparePanel({
  refExtractJobId,
  userExtractJobId,
  onResult,
  onJumpToFrame, // ✅ NEW
}) {
  // hide some fields in the compact UI
  const SHOW_FINAL_SCORE = false;
  const SHOW_AUTOSYNC = false;
  const [compareJobId, setCompareJobId] = useState("");
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  // keep a local copy of compare results for display here
  const [compareData, setCompareData] = useState(null);
  const pollWorkerRef = useRef(null);
  const onResultRef = useRef(onResult);

  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  useEffect(() => {
    const worker = new Worker(new URL("./workers/comparePollWorker.js", import.meta.url), {
      type: "module",
    });

    const onMessage = (event) => {
      const msg = event?.data || {};

      if (msg.type === "status") {
        setStatus(msg.status || "unknown");
        setProgress(msg.progress ?? 0);
        return;
      }

      if (msg.type === "failed") {
        setStatus("failed");
        setError(msg.error || "Compare failed");
        return;
      }

      if (msg.type === "done") {
        setStatus("done");
        setProgress(100);
        setCompareData(msg.data || null);

        if (typeof onResultRef.current === "function") {
          onResultRef.current({ compareJobId: msg.jobId, data: msg.data });
        }
        return;
      }

      if (msg.type === "poll-error") {
        // transient network/poll errors are shown but polling continues
        setError(String(msg.error || "Polling error"));
      }
    };

    worker.addEventListener("message", onMessage);
    pollWorkerRef.current = worker;

    return () => {
      worker.removeEventListener("message", onMessage);
      worker.terminate();
      pollWorkerRef.current = null;
    };
  }, []);

  async function startCompare() {
    setError("");
    setStatus("queued");
    setProgress(0);
    setCompareData(null);
    setVerdict(null);
    setVerdictError("");
    setDeepVerdict(null);
    setDeepError("");
    setDeepPending(false);
    setDeepStatus(null);
    setLastProgress(null);
    setLastProgressAt(null);
    try {
      const r = await createCompareJob(refExtractJobId, userExtractJobId, 90);
      setCompareJobId(r.job_id);
      setStatus("processing");
    } catch (e) {
      setError(String(e.message || e));
      setStatus("failed");
    }
  }
  useEffect(() => {
    if (!compareJobId || !pollWorkerRef.current) return;

    pollWorkerRef.current.postMessage({
      type: "start",
      jobId: compareJobId,
      intervalMs: 1200,
    });

    return () => {
      if (pollWorkerRef.current) {
        pollWorkerRef.current.postMessage({ type: "stop" });
      }
    };
  }, [compareJobId]);

  const disabled =
    !refExtractJobId ||
    !userExtractJobId ||
    status === "processing" ||
    status === "queued";

  // --------- helpers ----------
  const fmt = (x, d = 2) => {
    const n = Number(x);
    if (!Number.isFinite(n)) return "-";
    return n.toFixed(d);
  };

  const hasResults = useMemo(() => Boolean(compareData), [compareData]);

  const dtwScore = Number(compareData?.overall_score_0_100 ?? 0);
  const finalScore = Number(compareData?.final_score_0_100 ?? dtwScore);

  const shiftFrames = Number.isFinite(Number(compareData?.auto_sync?.shift_frames))
    ? Number(compareData.auto_sync.shift_frames)
    : Number.isFinite(Number(compareData?.shift_frames))
    ? Number(compareData.shift_frames)
    : null;

  const dtwDbg = compareData?.dtw_debug || null;

  // AI verdict state
  const [verdict, setVerdict] = useState(null);
  const [verdictError, setVerdictError] = useState("");
  const [verdictLoading, setVerdictLoading] = useState(false);
  const [deepVerdict, setDeepVerdict] = useState(null);
  const [deepLoading, setDeepLoading] = useState(false);
  const [deepError, setDeepError] = useState("");
  const [deepPending, setDeepPending] = useState(false);
  const [deepStatus, setDeepStatus] = useState(null);
  const [lastProgress, setLastProgress] = useState(null);
  const [lastProgressAt, setLastProgressAt] = useState(null);

  useEffect(() => {
    if (!compareData || !compareJobId) return;
    let alive = true;

    const fetchWithRetry = async () => {
      setVerdictError("");
      setVerdictLoading(true);
      try {
        // first try: short timeout
        const v = await getVerdict(compareJobId, 6000);
        if (!alive) return;
        setVerdict(v || null);
        // mark deep pending if background run likely
        setDeepPending(true);
        return;
      } catch (err) {
        if (!alive) return;
        // if timed out, try one longer attempt after short backoff
        if ((err && String(err.message || err)).toLowerCase().includes('timed out')) {
          try {
            await new Promise((r) => setTimeout(r, 500));
            const v2 = await getVerdict(compareJobId, 12000);
            if (!alive) return;
            setVerdict(v2 || null);
            return;
          } catch (err2) {
            if (!alive) return;
            setVerdictError(String(err2.message || err2));
            return;
          }
        }
        setVerdictError(String(err.message || err));
      } finally {
        if (alive) setVerdictLoading(false);
      }
    };

    fetchWithRetry();

    return () => {
      alive = false;
    };
  }, [compareData, compareJobId]);

  // Poll for deep verdict once quick verdict is present — poll until backend reports done/failed
  useEffect(() => {
    if (!compareJobId || !verdict) return;
    let alive = true;
    const intervalMs = 4000;

    const tryFetchDeep = async () => {
      if (!alive) return;
      try {
        const dv = await getVerdict(compareJobId, 5000, "deep");
        if (!alive) return;

        if (!dv) {
          setDeepPending(true);
          setTimeout(tryFetchDeep, intervalMs);
          return;
        }

        // running status -> show partials and continue polling
        if (dv.status === "running") {
          setDeepStatus(dv);
          setDeepPending(true);
          setDeepError("");
          // update last progress timestamp when progress changes
          try {
            const prog = Number(dv.progress ?? 0);
            setLastProgress((prev) => {
              if (prev !== prog) {
                setLastProgressAt(Date.now());
                return prog;
              }
              return prev;
            });
          } catch (e) {
            // ignore
          }
          setTimeout(tryFetchDeep, intervalMs);
          return;
        }

        // done or final returned -> ensure status shows 100% and accept final verdict
        if (dv.status === "done" || dv.source || dv.error) {
          const normalizedStatus = dv.status !== "done"
            ? { status: "done", progress: 100, partial: dv.partial || [] }
            : Object.assign({}, dv, { progress: 100 });
          setDeepStatus(normalizedStatus);

          // Try to fetch the final deep verdict JSON explicitly if the status lacks full details.
          const tryFetchFinal = async () => {
            try {
              // attempt a few times to let the backend settle and return the final payload
              const attempts = 3;
              const finalPath = normalizedStatus && (normalizedStatus.final_path || normalizedStatus.final) ? (normalizedStatus.final_path || normalizedStatus.final) : null;
              for (let i = 0; i < attempts; i++) {
                // first, if the status gives a final_path, try fetching the artifact directly
                if (finalPath) {
                  try {
                    const art = await getArtifact(compareJobId, finalPath);
                    if (!alive) return;
                    if (art && (Array.isArray(art.strengths) || Array.isArray(art.weaknesses) || Array.isArray(art.focus_plan) || Array.isArray(art.key_moments))) {
                      setDeepVerdict(art);
                      setDeepPending(false);
                      setDeepError("");
                      return;
                    }
                  } catch (e) {
                    // artifact may not be available yet; fall through to try getVerdict
                  }
                }

                // longer timeout for final fetch via verdict endpoint
                try {
                  const final = await getVerdict(compareJobId, 15000, "deep");
                  if (!alive) return;
                  // If we received a payload with strengths/weaknesses/focus_plan or key_moments, accept it
                  if (final && (Array.isArray(final.strengths) || Array.isArray(final.weaknesses) || Array.isArray(final.focus_plan) || Array.isArray(final.key_moments))) {
                    setDeepVerdict(final);
                    setDeepPending(false);
                    setDeepError("");
                    return;
                  }

                  // If the backend returned an interim partials-based final, only accept it
                  // when progress > 87 and the progress value has not increased for STALE_MS.
                  const STALE_MS = 90 * 1000; // 90 seconds
                  if (final && String(final.source || '').toLowerCase() === 'interim_partials') {
                    const progressVal = Number(final.progress ?? (deepStatus && deepStatus.progress) ?? 0);
                    // prefer frontend-tracked last progress timestamp; fall back to interim timestamps
                    let stalled = false;
                    if (lastProgressAt) {
                      stalled = (Date.now() - Number(lastProgressAt)) >= STALE_MS;
                    } else {
                      const interimTs = final.interim_created_at || (deepStatus && deepStatus.interim_written_at);
                      if (interimTs) {
                        stalled = ((Date.now() / 1000) - Number(interimTs)) * 1000 >= STALE_MS;
                      }
                    }
                    if (progressVal > 87 && stalled) {
                      setDeepVerdict(final);
                      setDeepPending(false);
                      setDeepError("");
                      return;
                    }
                  }
                } catch (e) {
                  // ignore and retry
                }

                // otherwise wait briefly and retry
                await new Promise((r) => setTimeout(r, 1000));
              }
            } catch (err) {
              // ignore -- we'll fall back to the status object
            }
            // fallback: use whatever the backend returned (status object or minimal final)
            setDeepVerdict(dv);
            setDeepPending(false);
            setDeepError("");
          };

          tryFetchFinal();
          return; // stop polling
        }

        // fallback: mark pending and retry
        setDeepPending(true);
        setTimeout(tryFetchDeep, intervalMs);
      } catch (e) {
        if (!alive) return;
        setDeepError(String(e.message || e));
        setTimeout(tryFetchDeep, intervalMs);
      }
    };

    // only start polling if deep not already loaded
    if (!deepVerdict && deepPending !== false) {
      tryFetchDeep();
    }

    return () => {
      alive = false;
    };
  }, [compareJobId, verdict]);

  // ST-GCN
  const stgcn = compareData?.stgcn_embedding || null;
  const stgcnEnabled = Boolean(stgcn?.enabled);
  const stgcnSim01 = stgcnEnabled ? Number(stgcn?.sim_0_1) : null;
  const stgcnScore100 =
    stgcnSim01 != null && Number.isFinite(stgcnSim01) ? stgcnSim01 * 100 : null;

  const dbg = stgcnEnabled ? stgcn?.debug : null;
  const winScores = Array.isArray(stgcn?.window_scores) ? stgcn.window_scores : [];
  const winCenters = Array.isArray(stgcn?.window_centers_ref) ? stgcn.window_centers_ref : [];
  const winCount = Math.min(winScores.length, winCenters.length);

  // ✅ per-window rows
  const windowRows = useMemo(() => {
    if (!winCount) return [];
    const rows = [];
    for (let i = 0; i < winCount; i++) {
      const s01 = Number(winScores[i]);
      const center = Number(winCenters[i]);
      rows.push({
        i,
        center: Number.isFinite(center) ? Math.floor(center) : null,
        s01: Number.isFinite(s01) ? s01 : null,
        s100: Number.isFinite(s01) ? s01 * 100 : null,
      });
    }
    return rows;
  }, [winCount, winScores, winCenters]);

  const worstWindowRows = useMemo(() => {
    if (!windowRows.length) return [];
    return [...windowRows]
      .filter((r) => r.s01 != null)
      .sort((a, b) => (a.s01 ?? 0) - (b.s01 ?? 0))
      .slice(0, Math.min(8, windowRows.length));
  }, [windowRows]);

  const jump = (centerRef) => {
    if (typeof onJumpToFrame !== "function") return;
    if (!Number.isFinite(Number(centerRef))) return;
    onJumpToFrame(Number(centerRef));
  };

  return (
    <div className="compare-panel">
      <div className="compare-heading">3) Compare</div>

      <div className="compare-action">
        <button className="calculate-btn" disabled={disabled} onClick={startCompare}>
          Calculate score
        </button>
      </div>

      <div className="compare-info">
        <div className="compare-progress-container">
          <div className="compare-progress-label">Progress</div>
          <div className="compare-progress-bar">
            <div className="compare-progress-fill" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
          </div>
          <div className="compare-progress-percent">{Math.max(0, Math.min(100, progress))}%</div>
        </div>
        {error ? <div className="error-text">Error: {error}</div> : null}
      </div>

      {hasResults ? (
        <div className="compare-results-card">
          <div className="compare-results-title">Comparison Results (from ComparePanel)</div>

          <div className="compare-results-body compact">
            {/* DTW score and ST-GCN summary intentionally hidden in compact comparison view */}
            <div className="mt-xs shift-dim">Shift: {shiftFrames != null ? `${shiftFrames} frames` : '-'}</div>

            <div className="mt-md strong">AI Verdict</div>
            <div className="mt-xs">
              {!verdict && (
                <div className="muted">AI verdict: generating…</div>
              )}

              {verdict ? (
                <div className={`verdict-card mt-sm ${deepVerdict ? 'deep-ready' : ''}`}>
                  {/** prefer deep verdict fields when available */}
                  {(() => {
                    const d = deepVerdict || verdict;
                    const partials = deepStatus && Array.isArray(deepStatus.partial) ? deepStatus.partial : [];
                    const liveConfidence = partials.length
                      ? Math.round(partials.reduce((a, b) => a + (Number(b.confidence) || 0), 0) / partials.length)
                      : (Number(d.confidence) || 0);
                    const progressValue = deepStatus && deepStatus.progress != null ? Number(deepStatus.progress) : (deepVerdict ? 100 : null);
                    const deepReadyFull = Boolean(
                      deepVerdict && (
                        (deepStatus && Number(deepStatus.progress) >= 100) ||
                        Number(deepVerdict.progress || 0) >= 100 ||
                        String(deepVerdict.status || '').toLowerCase() === 'done'
                      )
                    );

                    const verdictWord = (String(d.overall_level || '') || '').toUpperCase();
                    const oneLine = (d.summary || '').split(/[\.\n]/)[0];

                    return (
                      <>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div>
                            <div className="verdict-word" style={{ fontSize: 18, fontWeight: 700 }}>{verdictWord}</div>
                            <div className="verdict-summary muted">{oneLine}</div>
                          </div>
                          <div style={{ marginLeft: 12 }}>
                            {deepVerdict ? (
                              <span className="badge" style={{ background: '#2d7aef', color: '#fff', padding: '6px 10px', borderRadius: 999 }}>Deep Ready</span>
                            ) : deepPending ? (
                              <span className="badge" style={{ background: '#f0ad4e', color: '#111', padding: '6px 10px', borderRadius: 999 }}>Deep Pending</span>
                            ) : null}
                          </div>
                        </div>

                        <div className="mt-xs verdict-meta">
                          <div className="verdict-level">Level: <span className={`level-badge level-${String(d.overall_level || '').replace(/[^a-z0-9_-]/gi,'')}`}>{d.overall_level}</span></div>
                          <div className="verdict-confidence">
                            <div className="conf-label">Confidence: {liveConfidence}%</div>
                            <div className="conf-bar">
                              <div className="conf-bar-fill" style={{ width: `${Math.max(0, Math.min(100, liveConfidence))}%` }} />
                            </div>
                          </div>
                        </div>

                        {d.source ? <div className="mt-xs muted">Source: {d.source}{deepVerdict ? ' (deep)' : ' (quick)'}</div> : null}
                        {deepError ? <div className="mt-xs error-text">Deep error: {deepError}</div> : null}
                        {d.note ? <div className="mt-xs" style={{ color: '#f97316' }}>{d.note}</div> : null}

                        {/* show deep status progress when available */}
                        {progressValue != null ? (
                          <div className="mt-xs">
                            <div>Deep analysis: {Math.max(0, Math.min(100, progressValue))}%</div>
                            <div className="progress-bar" style={{height: 8, background: '#eee', borderRadius: 4}}>
                              <div style={{width: `${Math.max(0, Math.min(100, progressValue))}%`, height: '100%', background: '#2d7aef', borderRadius: 4}} />
                            </div>
                          </div>
                        ) : null}

                        {partials.length ? (
                          <div className="mt-sm">
                            <div className="sub-heading">Partial deep findings</div>
                            <ul>
                              {partials.map((p, idx) => (
                                <li key={`part-${idx}`}>
                                  <strong>Stage {p.stage_index ?? idx}:</strong> {p.summary ?? JSON.stringify(p)}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}

                        {/* Strengths & Weaknesses table: show after deep fully done (accept heuristic or LLM final) */}
                        {deepReadyFull && deepVerdict ? (
                          (() => {
                            const strengths = Array.isArray(d.strengths) ? d.strengths : [];
                            const weaknesses = Array.isArray(d.weaknesses) ? d.weaknesses : [];
                            const rows = Math.max(strengths.length, weaknesses.length);
                            if (!rows) return null;
                            return (
                              <div className="mt-sm">
                                <div className="sub-heading">Strengths & Weaknesses</div>
                                <div className="table-wrap">
                                  <table className="ai-sw-table">
                                    <thead>
                                      <tr>
                                        <th>Strengths</th>
                                        <th>Weaknesses</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {Array.from({ length: rows }).map((_, i) => (
                                        <tr key={`sw-${i}`}>
                                          <td>{strengths[i] ?? ''}</td>
                                          <td>{weaknesses[i] ?? ''}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            );
                          })()
                        ) : null}

                        {/* Key Moments removed as requested */}
                      </>
                    )
                  })()}

                  {/* raw deep JSON viewer removed to simplify UI */}
                </div>
              ) : null}
            </div>

            {/* compact: remove raw JSON dump to blend with main UI */}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default memo(ComparePanel);
