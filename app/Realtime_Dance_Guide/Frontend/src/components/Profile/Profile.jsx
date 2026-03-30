import React, { useMemo, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import apiClient from "../../services/apiClient";
import "./profile.css";

// --------------------
// helpers
// --------------------
function pickStableId(r) {
  return (
    r.id ||
    r._id ||
    r.result_id ||
    r.compareJobId ||
    r.compare_job_id ||
    `${r.ref_job_id || r.refJobId || "ref"}__${r.user_job_id || r.userJobId || "usr"}__${r.saved_at || r.savedAt || ""}`
  );
}

function safeParseVerdict(v) {
  if (v == null) return null;
  if (typeof v === "object") return v;
  if (typeof v !== "string") return null;

  const s = v.trim();
  if (!s) return null;

  // strict json
  try {
    return JSON.parse(s);
  } catch (_) {}

  // python dict-ish: "{'a': 1, 'b': 'x'}"
  // best-effort conversion
  try {
    const normalized = s
      .replace(/\bNone\b/g, "null")
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false")
      .replace(/'/g, '"');
    return JSON.parse(normalized);
  } catch (_) {}

  return null;
}

function fmtNum(x, digits = 2) {
  const n = Number(x);
  if (!Number.isFinite(n)) return x ?? "-";
  return n.toFixed(digits);
}

function Section({ title, children }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 900, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function BulletList({ items }) {
  if (!Array.isArray(items) || items.length === 0)
    return <div style={{ color: "var(--text-muted)" }}>-</div>;

  return (
    <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text-secondary)", lineHeight: 1.35 }}>
      {items.map((t, i) => (
        <li key={i}>{String(t)}</li>
      ))}
    </ul>
  );
}

const thStyle = {
  textAlign: "left",
  padding: "10px 10px",
  borderBottom: "1px solid rgba(255,255,255,0.12)",
  color: "var(--text-muted)",
  fontWeight: 900,
  whiteSpace: "nowrap",
};

const tdStyle = {
  padding: "10px 10px",
  borderBottom: "1px solid rgba(255,255,255,0.08)",
  color: "var(--text-secondary)",
  verticalAlign: "top",
};

function KeyMomentsTable({ moments }) {
  if (!Array.isArray(moments) || moments.length === 0)
    return <div style={{ color: "var(--text-muted)" }}>-</div>;

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr>
            <th style={thStyle}>Focus</th>
            <th style={thStyle}>Time range</th>
            <th style={thStyle}>What to fix</th>
          </tr>
        </thead>
        <tbody>
          {moments.map((m, i) => (
            <tr key={i}>
              <td style={tdStyle}>{m.focus ?? "-"}</td>
              <td style={tdStyle}>{m.time_range ?? "-"}</td>
              <td style={tdStyle}>{m.what_to_fix ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------
// main component
// --------------------
export default function Profile({ username: fallbackName }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const profile = useMemo(() => (user ? user.data || user : null), [user]);

  const name = profile?.username || profile?.first_name || fallbackName || "User";
  const email = profile?.email || "";
  const initial = name?.charAt(0)?.toUpperCase() || "U";
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 640);

  // update on resize so responsiveness adjusts when user rotates device
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 640);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const styles = {
    container: {
      fontFamily:
        "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial",
      padding: isMobile ? "1rem" : "2rem",
      color: "var(--text)",
      background: "var(--bg)",
      minHeight: "100vh",
    },
    banner: {
      height: isMobile ? 120 : 200,
      borderRadius: 12,
      backgroundImage: "linear-gradient(135deg,var(--accent), var(--accent-hover))",
      marginBottom: 18,
      boxShadow: "0 8px 26px rgba(31, 41, 51, 0.06)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "var(--text)",
      fontSize: isMobile ? 18 : 22,
      fontWeight: 700,
    },
    header: {
      display: "flex",
      gap: 20,
      alignItems: "center",
      marginBottom: 20,
      flexDirection: isMobile ? "column" : "row",
    },
    avatar: {
      width: isMobile ? 90 : 120,
      height: isMobile ? 90 : 120,
      borderRadius: "50%",
      background: "linear-gradient(180deg,var(--accent-hover), var(--accent))",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "var(--text)",
      fontSize: isMobile ? 32 : 44,
      fontWeight: 700,
      boxShadow: "0 8px 22px rgba(31, 41, 51, 0.08)",
    },
    userInfo: { display: "flex", flexDirection: "column", gap: 6 },
    name: { fontSize: isMobile ? 20 : 26, fontWeight: 800 },
    email: { color: "var(--text-muted)", fontSize: 14 },
    actions: { display: "flex", gap: 10, marginTop: isMobile ? 8 : 0 },
    btnGhost: {
      background: "transparent",
      border: "1px solid var(--border)",
      padding: "8px 12px",
      borderRadius: 8,
      cursor: "pointer",
      color: "var(--text)",
      fontWeight: 600,
    },
    btnDanger: {
      background: "rgba(239, 68, 68, 0.12)",
      border: "1px solid rgba(239, 68, 68, 0.45)",
      padding: "8px 12px",
      borderRadius: 8,
      cursor: "pointer",
      color: "var(--text)",
      fontWeight: 800,
      whiteSpace: "nowrap",
    },
    btnPrimary: {
      background: "transparent",
      border: "1px solid var(--border-color)",
      padding: "8px 12px",
      borderRadius: 8,
      cursor: "pointer",
      color: "var(--text-primary)",
      fontWeight: 800,
      whiteSpace: "nowrap",
    },
  };

  const [results, setResults] = useState([]);
  const [loadingResults, setLoadingResults] = useState(false);
  const [resultsError, setResultsError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [expandedLoading, setExpandedLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [toasts, setToasts] = useState([]);

  const pushToast = (toast) => {
    const id = Date.now() + Math.random();
    const t = { id, ...toast };
    setToasts((s) => [t, ...s]);
    if (toast.duration !== 0) {
      const dur = toast.duration || 4000;
      setTimeout(() => setToasts((s) => s.filter((x) => x.id !== id)), dur);
    }
    return id;
  };

  const clearToast = (id) => setToasts((s) => s.filter((x) => x.id !== id));

  useEffect(() => {
    let mounted = true;

    const fetchResults = async () => {
      setLoadingResults(true);
      setResultsError(null);
      try {
        const res = await apiClient.get("/api/test-results", { params: { brief: 1 } });
        const data = res.data;
        if (!mounted) return;

        const list = Array.isArray(data) ? data : [];
        setResults(list.map((r) => ({ ...r, __rid: pickStableId(r) })));
      } catch (err) {
        if (!mounted) return;
        setResultsError(err.response?.data?.detail || err.message || "Error");
      } finally {
        if (mounted) setLoadingResults(false);
      }
    };

    fetchResults();
    return () => {
      mounted = false;
    };
  }, []);

  const handleDelete = async (id) => {
    if (!id) return;
    // show confirmation toast with actions
    const toastId = pushToast({
      title: "Delete this saved result?",
      duration: 0,
      meta: { id },
    });

    // attach handlers to toast by polling (simple approach)
    const onConfirm = async () => {
      clearToast(toastId);
      setDeletingId(id);
      setResultsError(null);
      try {
        await apiClient.delete(`/api/test-results/${id}/`);
        setResults((prev) => prev.filter((x) => x.id !== id));
        if (expandedId === id) setExpandedId(null);
        pushToast({ title: "Deleted", duration: 3000 });
      } catch (e) {
        pushToast({ title: e.response?.data?.detail || e.message || "Delete failed", duration: 5000 });
      } finally {
        setDeletingId(null);
      }
    };

    const onCancel = () => {
      clearToast(toastId);
    };

    // expose simple binding via setting a temporary map entry on window (keeps patch small)
    // cleanup after short time
    window.__profile_toast_actions = window.__profile_toast_actions || {};
    window.__profile_toast_actions[toastId] = { onConfirm, onCancel };
    setTimeout(() => delete window.__profile_toast_actions[toastId], 30000);
  };

  return (
    <div style={styles.container}>
      <div style={styles.banner}>Welcome back — let's dance 🎶</div>

      <div style={styles.header}>
        <div style={styles.avatar}>{initial}</div>
        <div style={styles.userInfo}>
          <div style={styles.name}>{name}</div>
          {email && <div style={styles.email}>{email}</div>}
          <div style={styles.actions}>
            <button style={styles.btnGhost} onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>
      </div>

      <section style={{ marginTop: 20 }}>
        <h3 style={{ marginBottom: 12 }}>Saved Test Results</h3>

        {loadingResults && <div>Loading saved results…</div>}
        {resultsError && <div style={{ color: "var(--error)" }}>{resultsError}</div>}

        {!loadingResults && !resultsError && results.length === 0 && (
          <div style={{ color: "var(--text-muted)" }}>No saved results yet.</div>
        )}

        <div
          style={{
            display: "grid",
            gap: 12,
            marginTop: 12,
            gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(320px,1fr))",
          }}
        >
          {results.map((r) => {
            const rid = r.__rid;
            const serverId = r.id || null;

            const score = r.summary?.finalScore ?? r.summary?.dtwScore ?? null;
            const title = score != null ? `Score ${Number(score).toFixed(2)}` : "Saved";

            const when =
              r.saved_at || r.savedAt ? new Date(r.saved_at || r.savedAt).toLocaleString() : "";

            const dtw = r.dtw_score ?? r.summary?.dtwScore ?? "-";
            const stgcn = r.stgcn_score ?? r.summary?.stgcnScore100 ?? "-";

            // verdict for compact + badge
            const verdictObj =
              safeParseVerdict(r.ai_verdict) ||
              safeParseVerdict(r.summary?.verdict) ||
              safeParseVerdict(r.payload?.ai_verdict) ||
              null;

            const verdictSummary =
              verdictObj?.summary ||
              (typeof r.ai_verdict === "string" && r.ai_verdict.length < 140 ? r.ai_verdict : null) ||
              r.summary?.verdict ||
              "-";

            const overallBadge = verdictObj?.overall_level
              ? String(verdictObj.overall_level).toUpperCase()
              : null;

            return (
              <div key={rid} className="profile-card"
                style={{
                  background: "var(--card)",
                  padding: 12,
                  borderRadius: 12,
                  border: "1px solid var(--border-color)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: 12,
                    flexWrap: "wrap",
                    flexDirection: isMobile ? "column" : "row",
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 900 }}>{title}</div>
                    <div style={{ color: "var(--text-muted)", fontSize: 12 }}>{when}</div>
                    {/* removed Ref/User line per UX request */}

                    <div style={{ display: "flex", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
                      <div className="profile-metric">
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>DTW</div>
                        <div style={{ fontWeight: 900, fontSize: 18 }}>{fmtNum(dtw, 2)}</div>
                      </div>

                      <div className="profile-metric">
                        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>ST-GCN</div>
                        <div style={{ fontWeight: 900, fontSize: 18 }}>{fmtNum(stgcn, 2)}</div>
                      </div>

                      <div className="profile-metric-wide">
                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                          AI Verdict
                        </div>

                        {/* show EXCELLENT badge here (compact card) */}
                              {overallBadge && (
                                <div style={{ marginBottom: 8 }}>
                                  <span
                                    style={{
                                      padding: "4px 10px",
                                      borderRadius: 999,
                                      background: "var(--card)",
                                      border: "1px solid var(--border-color)",
                                      fontWeight: 900,
                                      fontSize: 12,
                                    }}
                                  >
                                    {overallBadge}
                                  </span>
                                </div>
                              )}

                        {/* compact summary only */}
                        <div style={{ fontWeight: 800, color: "var(--text-secondary)", lineHeight: 1.3 }}>
                          {String(verdictSummary).length > 220
                            ? String(verdictSummary).slice(0, 220) + "…"
                            : String(verdictSummary)}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="profile-actions">
                    <button
                      className="btn-view"
                      onClick={async () => {
                        const idKey = serverId || rid;
                        const hasPayload =
                          r.payload ||
                          r.windows ||
                          r.ai_verdict_full ||
                          (typeof r.ai_verdict === "object" && r.ai_verdict?.key_moments);

                        setModalLoading(true);
                        try {
                          if (!hasPayload) {
                            const resp = await apiClient.get(`/api/test-results/${idKey}/`);
                            const full = resp.data;
                            setResults((prev) => prev.map((it) => (it.__rid === rid ? { ...it, ...full, __rid: rid } : it)));
                            setModalData({ ...r, ...resp.data, __rid: rid });
                          } else {
                            setModalData(r);
                          }
                          setModalOpen(true);
                        } catch (e) {
                          setResultsError(e.response?.data?.detail || e.message || "Error loading result");
                        } finally {
                          setModalLoading(false);
                        }
                      }}
                    >
                      View
                    </button>

                    <button
                      className="btn-delete"
                      onClick={() => handleDelete(serverId)}
                      disabled={deletingId === serverId}
                      title="Delete saved result"
                    >
                      {deletingId === serverId ? "Deleting…" : "Delete"}
                    </button>
                  </div>
                </div>
                {/* modal view will display details instead of inline expansion */}
              </div>
            );
          })}
        </div>
      </section>

      {/* Result modal */}
      {modalOpen && modalData && (
        <div className="profile-modal" onClick={() => setModalOpen(false)}>
          <div className="profile-modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="profile-modal-close" onClick={() => setModalOpen(false)}>✕</button>
            {modalLoading ? (
              <div>Loading…</div>
            ) : (
              (() => {
                const r = modalData;
                const v =
                  safeParseVerdict(r.ai_verdict) ||
                  safeParseVerdict(r.ai_verdict_full) ||
                  safeParseVerdict(r.payload?.ai_verdict) ||
                  safeParseVerdict(r.payload?.verdict) ||
                  null;

                if (!v) {
                  return (
                    <div style={{ color: "var(--text-secondary)" }}>
                      <div style={{ fontWeight: 900, marginBottom: 6 }}>Verdict</div>
                      <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                        {typeof r.ai_verdict === "string" ? r.ai_verdict : JSON.stringify(r.ai_verdict, null, 2)}
                      </pre>
                    </div>
                  );
                }

                const summary = v.summary || "-";
                const focusPlan = v.focus_plan || [];
                const keyMoments = v.key_moments || [];
                const strengths = v.strengths || [];
                const weaknesses = v.weaknesses || [];

                const partialsFromRecord =
                  Array.isArray(r.deepPartials) && r.deepPartials.length
                    ? r.deepPartials
                    : Array.isArray(r.payload?.deepPartials) && r.payload.deepPartials.length
                    ? r.payload.deepPartials
                    : Array.isArray(r.payload?.partials) && r.payload.partials.length
                    ? r.payload.partials
                    : [];

                return (
                  <div style={{ color: "var(--text-secondary)" }}>
                    <Section title="Summary">
                      <div style={{ lineHeight: 1.4 }}>{summary}</div>
                    </Section>

                    <Section title="Focus plan">
                      <BulletList items={focusPlan} />
                    </Section>

                    <Section title="Key moments">
                      <KeyMomentsTable moments={keyMoments} />
                    </Section>

                    {partialsFromRecord.length ? (
                      <Section title="Partial deep findings">
                        <BulletList items={partialsFromRecord.map((p) => p.summary || JSON.stringify(p))} />
                      </Section>
                    ) : null}

                    <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 12 }}>
                      <Section title="Strengths">
                        <BulletList items={strengths} />
                      </Section>

                      <Section title="Weaknesses">
                        <BulletList items={weaknesses} />
                      </Section>
                    </div>
                  </div>
                );
              })()
            )}
          </div>
        </div>
      )}
      {/* Toast container rendered here */}
      <div className="profile-toaster">
        {toasts.map((t) => (
          <div className="profile-toast" key={t.id}>
            <div style={{ flex: 1 }}>{t.title}</div>
            {t.duration === 0 ? (
              <div className="toast-actions">
                <button
                  className="toast-btn toast-cancel"
                  onClick={() => window.__profile_toast_actions?.[t.id]?.onCancel?.()}
                >
                  Cancel
                </button>
                <button
                  className="toast-btn toast-confirm"
                  onClick={() => window.__profile_toast_actions?.[t.id]?.onConfirm?.()}
                >
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
