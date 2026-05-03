// src/ComparePanel.jsx
import { useEffect, useState, useMemo } from "react";
import { createCompareJob, getJob, getCompare, getVerdict, getArtifact } from "./api";

export default function ComparePanel({
  refExtractJobId,
  userExtractJobId,
  onResult,
  onJumpToFrame,
}) {
  const [compareJobId, setCompareJobId] = useState("");
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [compareData, setCompareData] = useState(null);

  // Quick verdict
  const [verdict, setVerdict] = useState(null);
  const [verdictError, setVerdictError] = useState("");
  const [verdictLoading, setVerdictLoading] = useState(false);

  // Deep verdict
  const [deepVerdict, setDeepVerdict] = useState(null);
  const [deepError, setDeepError] = useState("");
  const [deepPending, setDeepPending] = useState(false);
  const [deepStatus, setDeepStatus] = useState(null);

  // Persist partials always
  const [deepPartials, setDeepPartials] = useState([]);
  const [lastProgressAt, setLastProgressAt] = useState(null);

  // UI toggles
  const [showAllStrengths, setShowAllStrengths] = useState(false);
  const [showAllWeaknesses, setShowAllWeaknesses] = useState(false);

  useEffect(() => {
    setShowAllStrengths(false);
    setShowAllWeaknesses(false);
  }, [deepVerdict, compareJobId]);

  const hasResults = useMemo(() => Boolean(compareData), [compareData]);

  const shiftFrames = Number.isFinite(Number(compareData?.auto_sync?.shift_frames))
    ? Number(compareData.auto_sync.shift_frames)
    : Number.isFinite(Number(compareData?.shift_frames))
    ? Number(compareData.shift_frames)
    : null;

  // derive FPS from compare metadata when available; fallback to 30fps
  const fps = (() => {
    try {
      const m = compareData?.meta || {};
      const f = m?.fps || m?.ref_fps || m?.user_fps;
      const n = Number(f);
      return Number.isFinite(n) && n > 0 ? n : 30;
    } catch (e) {
      return 30;
    }
  })();

  const shiftSeconds = shiftFrames != null && Number.isFinite(Number(fps))
    ? (Number(shiftFrames) / Math.max(1e-6, Number(fps)))
    : null;

  const disabled =
    !refExtractJobId ||
    !userExtractJobId ||
    status === "processing" ||
    status === "queued";

  const mergePartialsUnique = (...lists) => {
    const out = [];
    const seen = new Set();
    for (const list of lists) {
      if (!Array.isArray(list)) continue;
      for (const p of list) {
        let key;
        if (p && (p.stage_index !== undefined && p.stage_index !== null)) key = `stage:${p.stage_index}`;
        else if (p && (p.id || p._id)) key = `id:${p.id || p._id}`;
        else {
          try {
            key = JSON.stringify(p);
          } catch (e) {
            key = String(p);
          }
        }
        if (!seen.has(key)) {
          seen.add(key);
          out.push(p);
        }
      }
    }
    return out;
  };

  const mergedPartials = useMemo(() => {
    return mergePartialsUnique(
      deepPartials,
      deepStatus?.partial,
      deepVerdict?.partial,
      verdict?.partial
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepPartials, deepStatus, deepVerdict, verdict]);

  // Keep parent in sync as verdict data arrives after compare result is already available.
  useEffect(() => {
    if (!compareJobId || !compareData) return;
    if (typeof onResult !== "function") return;

    onResult({
      compareJobId,
      data: compareData,
      verdict: verdict || null,
      deepVerdict: deepVerdict || null,
      deepStatus: deepStatus || null,
      deepPartials: mergedPartials,
    });
  }, [compareJobId, compareData, verdict, deepVerdict, deepStatus, mergedPartials, onResult]);

  async function startCompare() {
    setError("");
    setStatus("queued");
    setProgress(0);
    setCompareData(null);

    setVerdict(null);
    setVerdictError("");
    setVerdictLoading(false);

    setDeepVerdict(null);
    setDeepError("");
    setDeepPending(false);
    setDeepStatus(null);
    setDeepPartials([]);
    setLastProgressAt(null);

    if (!refExtractJobId || !userExtractJobId) {
      setError("Missing reference or user job ID");
      setStatus("failed");
      return;
    }

    try {
      console.log("[ComparePanel] Creating compare job:", { refExtractJobId, userExtractJobId });
      const r = await createCompareJob(refExtractJobId, userExtractJobId, 90);
      console.log("[ComparePanel] Got compare job response:", r);
      
      if (!r || !r.job_id) {
        throw new Error("No job_id in response: " + JSON.stringify(r));
      }
      
      setCompareJobId(r.job_id);
      setStatus("processing");
      console.log("[ComparePanel] Compare job created:", r.job_id);
    } catch (e) {
      const msg = String(e.message || e);
      console.error("[ComparePanel] Compare job creation failed:", msg);
      setError(msg);
      setStatus("failed");
    }
  }

  // Compare job polling
  useEffect(() => {
    if (!compareJobId) return;
    let alive = true;
    // throttle job polling to reduce CPU/network churn
    const POLL_MS = 2000;
    
    console.log("[ComparePanel] Starting poll for job:", compareJobId);
    
    const iv = setInterval(async () => {
      try {
        const j = await getJob(compareJobId);
        if (!alive) return;

        console.log("[ComparePanel] Job status response:", { status: j.status, progress: j.progress, error: j.error });
        
        setStatus(j.status || "unknown");
        setProgress(Number(j.progress ?? 0));

        if (j.status === "failed") {
          const errMsg = j.error || "Compare failed";
          console.error("[ComparePanel] Job failed:", errMsg);
          setError(errMsg);
          clearInterval(iv);
        }

        if (j.status === "done") {
          console.log("[ComparePanel] Job done, fetching results...");
          clearInterval(iv);
          const data = await getCompare(compareJobId);
          if (!alive) return;
          console.log("[ComparePanel] Got compare data");
          setCompareData(data);

          if (typeof onResult === "function") {
            onResult({
              compareJobId,
              data,
              verdict: verdict || null,
              deepVerdict: deepVerdict || null,
              deepStatus: deepStatus || null,
              deepPartials: mergedPartials,
            });
          }
        }
      } catch (e) {
        console.error("[ComparePanel] Polling error:", String(e?.message || e));
      }
    }, POLL_MS);

    return () => {
      alive = false;
      clearInterval(iv);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareJobId, onResult]);

  // Fetch quick verdict
  useEffect(() => {
    if (!compareData || !compareJobId) return;
    let alive = true;

    const fetchWithRetry = async () => {
      setVerdictError("");
      setVerdictLoading(true);
      try {
        const v = await getVerdict(compareJobId, 6000);
        if (!alive) return;
        setVerdict(v || null);
        // we used to mark deepPending immediately when a quick verdict
        // arrived, which caused the UI to show a "thinking..." badge
        // even before any deep analysis had started (and in some cases
        // no deep run would ever happen).  instead we wait for the
        // polling logic below to flip the flag once it actually begins
        // polling the deep endpoint.  a separate effect below will also
        // clear the flag whenever a deep verdict is obtained.
      } catch (err) {
        if (!alive) return;
        const msg = String(err?.message || err || "");
        if (msg.toLowerCase().includes("timed out")) {
          try {
            await new Promise((r) => setTimeout(r, 500));
            const v2 = await getVerdict(compareJobId, 12000);
            if (!alive) return;
            setVerdict(v2 || null);
            // same comment as above
            return;
          } catch (err2) {
            if (!alive) return;
            setVerdictError(String(err2?.message || err2));
            return;
          }
        }
        setVerdictError(msg);
      } finally {
        if (alive) setVerdictLoading(false);
      }
    };

    fetchWithRetry();
    return () => {
      alive = false;
    };
  }, [compareData, compareJobId]);

  // Deep polling
  useEffect(() => {
    if (!compareJobId || !verdict) return;
    let alive = true;
    // poll less frequently to reduce load
    const intervalMs = 6000;

    const tryFetchDeep = async () => {
      if (!alive) return;
      // whenever we actually reach out for a deep verdict we consider
      // the analysis "pending" so the UI badge can render accordingly.
      setDeepPending(true);

      try {
        const dv = await getVerdict(compareJobId, 5000, "deep");
        if (!alive) return;

        if (!dv) {
          // still no deep result; keep pending state and try again later
          setTimeout(tryFetchDeep, intervalMs);
          return;
        }

        if (dv.status === "running") {
          setDeepStatus(dv);
          if (Array.isArray(dv.partial) && dv.partial.length) {
            setDeepPartials((prev) => mergePartialsUnique(prev, dv.partial));
          }
          setDeepPending(true);
          setDeepError("");
          setLastProgressAt(Date.now());
          setTimeout(tryFetchDeep, intervalMs);
          return;
        }

        if (dv.status === "done" || dv.source || dv.error) {
          const preservedPartials = mergePartialsUnique(
            deepPartials,
            deepStatus?.partial,
            dv?.partial
          );

          const normalizedStatus =
            dv.status !== "done"
              ? { status: "done", progress: 100, partial: preservedPartials }
              : Object.assign({}, dv, { progress: 100, partial: preservedPartials });

          setDeepStatus(normalizedStatus);
          if (preservedPartials.length) setDeepPartials(preservedPartials);

          const finalPath =
            normalizedStatus && (normalizedStatus.final_path || normalizedStatus.final)
              ? normalizedStatus.final_path || normalizedStatus.final
              : null;

          // Try artifact first then endpoint
          for (let i = 0; i < 3; i++) {
            if (!alive) return;

            if (finalPath) {
              try {
                const art = await getArtifact(compareJobId, finalPath);
                if (!alive) return;
                if (art && (Array.isArray(art.strengths) || Array.isArray(art.weaknesses))) {
                  const preserved = mergePartialsUnique(
                    preservedPartials,
                    art?.partial
                  );
                  if (preserved.length) setDeepPartials(preserved);
                  setDeepVerdict(Object.assign({}, art, { partial: preserved }));
                  setDeepPending(false);
                  setDeepError("");
                  return;
                }
              } catch {
                // ignore
              }
            }

            try {
              const final = await getVerdict(compareJobId, 15000, "deep");
              if (!alive) return;
              if (final && (Array.isArray(final.strengths) || Array.isArray(final.weaknesses))) {
                const preserved = mergePartialsUnique(
                  preservedPartials,
                  final?.partial
                );
                if (preserved.length) setDeepPartials(preserved);
                setDeepVerdict(Object.assign({}, final, { partial: preserved }));
                setDeepPending(false);
                setDeepError("");
                return;
              }
            } catch {
              // ignore
            }

            await new Promise((r) => setTimeout(r, 800));
          }

          // fallback
          setDeepVerdict(Object.assign({}, dv, { partial: preservedPartials }));
          setDeepPending(false);
          setDeepError("");
          return;
        }

        setDeepPending(true);
        setTimeout(tryFetchDeep, intervalMs);
      } catch (e) {
        if (!alive) return;
        setDeepError(String(e?.message || e));
        setTimeout(tryFetchDeep, intervalMs);
      }
    };

    if (!deepVerdict) {
      // always fire the first poll after we have a quick verdict; the
      // pending flag will be toggled inside `tryFetchDeep` itself so we
      // don't need to pre‑set it above.
      tryFetchDeep();
    }

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareJobId, verdict]);

  // clear the pending indicator whenever a deep verdict finally
  // arrives.  this guards against races where some earlier async
  // operation might have flipped the flag back on after we already
  // received the result.
  useEffect(() => {
    if (deepVerdict) {
      setDeepPending(false);
    }
  }, [deepVerdict]);

  // ---------------- UI components ----------------

  const ProgressBar = ({ value = 0, label = null, showPercent = false }) => {
    const pct = Math.max(0, Math.min(100, Number(value) || 0));
    return (
      <div className="cp-bar">
        {label ? <div className="cp-bar-label">{label}</div> : null}
        <div className="cp-bar-row">
          <div className="cp-bar-track">
            <div className="cp-bar-fill" style={{ width: `${pct}%` }} />
          </div>
          {showPercent ? <div className="cp-bar-pct">{Math.round(pct)}%</div> : null}
        </div>
      </div>
    );
  };

  const CollapsibleList = ({ title, items, kind, showAll, setShowAll, maxVisible = 4 }) => {
    const arr = Array.isArray(items) ? items.filter((x) => String(x || "").trim()) : [];
    if (!arr.length) return null;

    const visible = showAll ? arr : arr.slice(0, maxVisible);
    const hiddenCount = Math.max(0, arr.length - visible.length);

    return (
      <div className="cp-list">
        <div className="cp-list-head">
          <div className="cp-list-title">{title}</div>
          <div className="cp-list-count">{arr.length}</div>
        </div>

        <div className={`cp-list-box ${kind}`}>
          <ul className="cp-ul">
            {visible.map((t, idx) => (
              <li key={`${kind}-${idx}`} className="cp-li">
                <span className="cp-li-icon">{kind === "strength" ? "✓" : "⚠"}</span>
                <span className="cp-li-text">{String(t)}</span>
              </li>
            ))}
          </ul>

          {arr.length > maxVisible ? (
            <div className="cp-list-actions">
              <button type="button" className="cp-btn" onClick={() => setShowAll((p) => !p)}>
                {showAll ? "Show less" : `Show more (${hiddenCount})`}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    );
  };

  // ---------------- render ----------------

  const d = deepVerdict || verdict;
  const partials = mergedPartials;


  const deepProgress =
    deepStatus && deepStatus.progress != null ? Number(deepStatus.progress) : deepVerdict ? 100 : null;

  const deepReadyFull = Boolean(
    deepVerdict &&
      ((deepStatus && Number(deepStatus.progress) >= 100) ||
        Number(deepVerdict.progress || 0) >= 100 ||
        String(deepVerdict.status || "").toLowerCase() === "done")
  );

  return (
    <div className="compare-panel">
      <style>{`
        /* ===========================
           Theme-adaptive CSS variables
           If your app already defines these, it will inherit.
           Otherwise, these dark-friendly fallbacks apply.
        ============================ */
        .compare-panel{
          --panel-bg: var(--app-panel-bg, rgba(255,255,255,0.06));
          --panel-bg-2: var(--app-panel-bg-2, rgba(255,255,255,0.04));
          --border: var(--app-border, rgba(255,255,255,0.10));
          --text: var(--app-text, rgba(255,255,255,0.92));
          --muted: var(--app-muted, rgba(255,255,255,0.62));
          --brand: var(--app-brand, #4f8cff);
          --good: var(--app-good, #10b981);
          --bad: var(--app-bad, #ef4444);
          --warn: var(--app-warn, #f59e0b);
          color: var(--text);
        }

        /* Card shell (NO forced white) */
        .cp-card{
          border: 1px solid var(--border);
          background: linear-gradient(180deg, var(--panel-bg), var(--panel-bg-2));
          border-radius: 16px;
          padding: 14px;
          box-shadow: 0 8px 30px rgba(0,0,0,0.25);
        }

        .cp-title{
          font-weight: 900;
          font-size: 14px;
          color: var(--text);
          margin-bottom: 10px;
        }

        .cp-muted{ color: var(--muted); }
        .cp-error{ color: var(--bad); font-weight: 900; }

        /* Progress */
        .cp-bar{ display:flex; flex-direction:column; gap:8px; }
        .cp-bar-label{ font-weight:800; color: var(--text); font-size: 13px; }
        .cp-bar-row{ display:flex; align-items:center; gap:10px; }
        .cp-bar-track{
          flex:1;
          height: 10px;
          border-radius: 999px;
          background: rgba(255,255,255,0.10);
          border: 1px solid rgba(255,255,255,0.08);
          overflow:hidden;
        }
        .cp-bar-fill{
          height: 100%;
          background: linear-gradient(90deg, var(--brand), rgba(255,255,255,0.15));
          border-radius: 999px;
        }
        .cp-bar-pct{ min-width: 50px; text-align:right; font-weight:900; color: var(--text); }

        /* Verdict card */
        .cp-verdict{
          margin-top: 12px;
          border: 1px solid var(--border);
          border-radius: 16px;
          padding: 14px;
          background: rgba(0,0,0,0.18);
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
        }
        .cp-verdict-top{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
        .cp-word{ font-size: 18px; font-weight: 1000; letter-spacing: 0.2px; }
        .cp-summary{ margin-top: 6px; color: var(--muted); font-weight: 700; }

        .cp-badge{
          font-weight: 900;
          font-size: 12px;
          padding: 6px 10px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.12);
          background: rgba(255,255,255,0.08);
          color: var(--text);
          white-space: nowrap;
        }
        .cp-badge.pending{ background: rgba(245,158,11,0.16); border-color: rgba(245,158,11,0.35); color: #ffe7b5; }
        .cp-badge.ready{ background: rgba(79,140,255,0.16); border-color: rgba(79,140,255,0.35); }

        .cp-meta{
          margin-top: 12px;
          display:flex;
          gap:12px;
          align-items:center;
          flex-wrap: wrap;
        }
        .cp-level{
          font-weight: 900;
          color: var(--text);
          display:flex;
          gap:8px;
          align-items:center;
        }
        .cp-pill{
          padding: 4px 10px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.12);
          background: rgba(255,255,255,0.06);
          font-weight: 1000;
          color: var(--text);
        }

        .cp-section{
          margin-top: 14px;
          padding-top: 12px;
          border-top: 1px solid rgba(255,255,255,0.08);
        }
        .cp-section-title{
          font-weight: 1000;
          margin-bottom: 8px;
          color: var(--text);
        }

        /* Partial list */
        .cp-ul{ margin:0; padding-left: 18px; }
        .cp-li{ margin-bottom: 7px; line-height: 1.35; color: var(--text); }
        .cp-li strong{ color: var(--text); }

        /* Strength/Weakness list blocks */
        .cp-sw{ display:flex; gap:12px; flex-wrap:wrap; align-items:stretch; }
        .cp-list{ flex:1; min-width: 280px; }
        .cp-list-head{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom: 8px; }
        .cp-list-title{ font-weight: 1000; color: var(--text); }
        .cp-list-count{ font-size: 12px; color: var(--muted); font-weight: 900; }

        .cp-list-box{
          border: 1px solid rgba(255,255,255,0.10);
          background: rgba(255,255,255,0.04);
          border-radius: 14px;
          padding: 12px;
        }
        .cp-list-box.strength{
          border-color: rgba(16,185,129,0.28);
          background: rgba(16,185,129,0.08);
        }
        .cp-list-box.weakness{
          border-color: rgba(239,68,68,0.28);
          background: rgba(239,68,68,0.08);
        }

        .cp-li-icon{
          font-weight: 1000;
          margin-right: 8px;
        }
        .cp-list-box.strength .cp-li-icon{ color: var(--good); }
        .cp-list-box.weakness .cp-li-icon{ color: var(--bad); }

        .cp-list-actions{
          display:flex;
          justify-content:flex-end;
          margin-top: 10px;
        }

        .cp-btn{
          border: 1px solid rgba(255,255,255,0.16);
          background: rgba(255,255,255,0.08);
          color: var(--text);
          padding: 8px 10px;
          border-radius: 12px;
          cursor: pointer;
          font-weight: 1000;
          font-size: 13px;
        }
        .cp-btn:hover{
          background: rgba(255,255,255,0.12);
          transform: translateY(-1px);
        }

        /* Focus Plan */
        .cp-focus-plan{
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin-top: 8px;
        }
        .cp-focus-step{
          display: flex;
          gap: 12px;
          align-items: flex-start;
          padding: 12px;
          border: 1px solid rgba(74, 144, 226, 0.3);
          background: rgba(74, 144, 226, 0.08);
          border-radius: 12px;
        }
        .cp-focus-number{
          flex-shrink: 0;
          width: 32px;
          height: 32px;
          background: linear-gradient(135deg, var(--brand), rgba(255,255,255,0.1));
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 1000;
          color: white;
          font-size: 14px;
          box-shadow: 0 4px 12px rgba(74, 144, 226, 0.2);
        }
        .cp-focus-text{
          flex: 1;
          color: var(--text);
          font-weight: 700;
          line-height: 1.4;
        }

        /* Key Moments */
        .cp-moments{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 12px;
          margin-top: 8px;
        }
        .cp-moment-card{
          border: 1px solid rgba(245, 158, 11, 0.3);
          background: rgba(245, 158, 11, 0.07);
          border-radius: 12px;
          padding: 12px;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
          transition: all 0.2s ease;
        }
        .cp-moment-card:hover{
          border-color: rgba(245, 158, 11, 0.5);
          background: rgba(245, 158, 11, 0.12);
          box-shadow: 0 4px 12px rgba(245, 158, 11, 0.15), inset 0 1px 0 rgba(255,255,255,0.05);
        }
        .cp-moment-time{
          font-weight: 1000;
          color: var(--warn);
          font-size: 13px;
          margin-bottom: 6px;
        }
        .cp-moment-focus{
          font-weight: 700;
          color: var(--text);
          margin-bottom: 6px;
          font-size: 13px;
        }
        .cp-moment-tag{
          background: rgba(245, 158, 11, 0.2);
          padding: 2px 6px;
          border-radius: 4px;
          border: 1px solid rgba(245, 158, 11, 0.3);
          font-weight: 900;
        }
        .cp-moment-fix{
          color: var(--muted);
          font-weight: 600;
          line-height: 1.35;
          font-size: 13px;
        }

      `}</style>

      <style>{`
        /* ========================
           Animated Stage Cards (Bubble Out Effect)
        ======================== */
        .cp-stages {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
          margin-top: 16px;
          perspective: 1200px;
        }

        .cp-stage-card {
          position: relative;
          background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.1));
          border: 1px solid rgba(102, 126, 234, 0.3);
          border-radius: 16px;
          padding: 16px;
          box-shadow: 0 8px 32px rgba(102, 126, 234, 0.15);
          opacity: 0;
          transform: scale(0.5) translateY(20px);
          animation: stageBubbleOut 1.2s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
          transition: all 0.3s ease;
          cursor: default;
        }

        .cp-stage-card:nth-child(1) { animation-delay: 0ms; }
        .cp-stage-card:nth-child(2) { animation-delay: 180ms; }
        .cp-stage-card:nth-child(3) { animation-delay: 360ms; }
        .cp-stage-card:nth-child(4) { animation-delay: 540ms; }
        .cp-stage-card:nth-child(5) { animation-delay: 720ms; }
        .cp-stage-card:nth-child(6) { animation-delay: 900ms; }
        .cp-stage-card:nth-child(7) { animation-delay: 1080ms; }
        .cp-stage-card:nth-child(8) { animation-delay: 1260ms; }
        .cp-stage-card:nth-child(9) { animation-delay: 1440ms; }
        .cp-stage-card:nth-child(10) { animation-delay: 1620ms; }

        .cp-stage-card:hover {
          transform: scale(1.05);
          border-color: var(--accent);
          box-shadow: 0 12px 48px rgba(56, 182, 168, 0.22);
          background: linear-gradient(135deg, rgba(56,182,168,0.12), rgba(42,157,143,0.08));
        }

        .cp-stage-badge {
          display: inline-block;
          background: var(--primary-gradient);
          color: white;
          padding: 6px 12px;
          border-radius: 999px;
          font-weight: 900;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 10px;
          box-shadow: 0 4px 12px rgba(56, 182, 168, 0.18);
        }

        .cp-stage-title {
          font-weight: 900;
          font-size: 13px;
          color: var(--text);
          margin-bottom: 8px;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .cp-stage-icon {
          font-size: 18px;
          animation: stageIconPulse 2s ease-in-out infinite;
        }

        .cp-stage-content {
          font-size: 12px;
          color: var(--muted);
          line-height: 1.4;
          word-break: break-word;
        }

        .cp-stage-complete {
          position: absolute;
          top: 10px;
          right: 10px;
          width: 24px;
          height: 24px;
          background: rgba(16, 185, 129, 0.2);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          border: 1px solid rgba(16, 185, 129, 0.4);
        }

        @keyframes stageBubbleOut {
          0% {
            opacity: 0;
            transform: scale(0.3) translateY(30px) rotateX(90deg);
          }
          50% {
            opacity: 1;
          }
          100% {
            opacity: 1;
            transform: scale(1) translateY(0) rotateX(0deg);
          }
        }

        @keyframes stageIconPulse {
          0%, 100% {
            transform: scale(1);
            opacity: 0.8;
          }
          50% {
            transform: scale(1.15);
            opacity: 1;
          }
        }
      `}</style>

      <div className="compare-heading">3) Compare</div>

      <div className="compare-action">
        <button className="calculate-btn" disabled={disabled} onClick={startCompare}>
          Calculate score
        </button>
      </div>

      <div className="compare-info" style={{ marginTop: 10 }}>
        <ProgressBar value={progress} label="Progress" showPercent />
        {error ? <div className="cp-error" style={{ marginTop: 8 }}>Error: {error}</div> : null}
      </div>

      {hasResults && (
        <div className="cp-card" style={{ marginTop: 14 }}>
          <div className="cp-title">Comparison Results</div>
          {!verdict ? (
            <div className="cp-muted" style={{ marginTop: 8 }}>
              {verdictLoading ? "AI verdict: generating…" : "AI verdict: waiting…"}
            </div>
          ) : (
            <div className="cp-verdict">
              <div className="cp-verdict-top">
                <div style={{ minWidth: 0 }}>
                  <div className="cp-word">{String(d?.overall_level || "").toUpperCase()}</div>
                  <div className="cp-summary">
                    {(d?.summary || "").split(/[\.\n]/)[0]}
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {deepVerdict ? (
                    <span className="cp-badge ready">done ✔️</span>
                  ) : deepPending ? (
                    <span className="cp-badge pending">thinking..</span>
                  ) : null}
                </div>
              </div>

{/* metadata (level/confidence removed per new requirements) */}

              {/* errors and note removed per user request */}
              {/* confidence notes removed per requirements */}

              {deepProgress != null ? (
                <div style={{ marginTop: 12 }}>
                  <ProgressBar value={deepProgress} label="Deep analysis" showPercent />
                </div>
              ) : null}

              {/* ✅ ANIMATED STAGE CARDS WITH BUBBLE-OUT EFFECT */}
              {partials.length ? (
                <div className="cp-section">
                  
                  <div className="cp-stages">
                    {partials.map((p, idx) => {
                      const stageNum = p.stage_index ?? idx;
                      const summary = String(p.summary || "Processing...").trim();
                      const icons = ["🔍", "⚖️", "🧠", "✨", "🎯"];
                      const icon = icons[stageNum % icons.length];
                      const timeRange = p.time_range || "";
                      return (
                        <div key={`part-${idx}`} className="cp-stage-card">
                          <div className="cp-stage-complete">✓</div>
                          <div className="cp-stage-badge">
                            {timeRange || `Stage ${stageNum + 1}`}
                          </div>

                          <div className="cp-stage-content">{summary}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {/* Strengths & Weaknesses */}
              {deepReadyFull && deepVerdict ? (
                (() => {
                  const strengths = Array.isArray(d?.strengths) ? d.strengths : [];
                  const weaknesses = Array.isArray(d?.weaknesses) ? d.weaknesses : [];
                  if (!strengths.length && !weaknesses.length) return null;

                  return (
                    <div className="cp-section">
                      <div className="cp-section-title">Strengths & Weaknesses</div>
                      <div className="cp-sw">
                        <CollapsibleList
                          title="Strengths"
                          items={strengths}
                          kind="strength"
                          showAll={showAllStrengths}
                          setShowAll={setShowAllStrengths}
                          maxVisible={4}
                        />
                        <CollapsibleList
                          title="Weaknesses"
                          items={weaknesses}
                          kind="weakness"
                          showAll={showAllWeaknesses}
                          setShowAll={setShowAllWeaknesses}
                          maxVisible={4}
                        />
                      </div>
                    </div>
                  );
                })()
              ) : null}

              {/* Focus Plan */}
              {deepReadyFull && deepVerdict && Array.isArray(d?.focus_plan) && d.focus_plan.length ? (
                <div className="cp-section">
                  <div className="cp-section-title">Focus Plan</div>
                  <div className="cp-focus-plan">
                    {d.focus_plan.map((step, idx) => (
                      <div key={`step-${idx}`} className="cp-focus-step">
                        <div className="cp-focus-number">{idx + 1}</div>
                        <div className="cp-focus-text">{String(step)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Key Moments */}
              {deepReadyFull && deepVerdict && Array.isArray(d?.key_moments) && d.key_moments.length ? (
                <div className="cp-section">
                  <div className="cp-section-title">Key Moments to Fix</div>
                  <div className="cp-moments">
                    {d.key_moments.map((moment, idx) => (
                      <div key={`moment-${idx}`} className="cp-moment-card">
                        <div className="cp-moment-time">{moment.time_range || "N/A"}</div>
                        <div className="cp-moment-focus">Focus: <span className="cp-moment-tag">{moment.focus}</span></div>
                        <div className="cp-moment-fix">{moment.what_to_fix}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
