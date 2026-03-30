// src/SkeletonCanvas.jsx
import { useEffect, useMemo, useRef } from "react";

// COCO-17 edges
const EDGES = [
  // head / face
  [0, 1],[0, 2],[1, 3],[2, 4],
  // connect head to shoulders for a more "neck" like look
  [0, 5],[0, 6],
  // arms
  [5, 6],[5, 7],[7, 9],[6, 8],[8, 10],
  // torso (shoulders <-> hips)
  [11, 12],[5, 11],[6, 12],[5, 6],
  // legs
  [11, 13],[13, 15],[12, 14],[14, 16],
];

// Limb groups (must match backend keys)
const LIMBS = {
  left_arm: [5, 7, 9],
  right_arm: [6, 8, 10],
  left_leg: [11, 13, 15],
  right_leg: [12, 14, 16],
  torso: [5, 6, 11, 12],
};

function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
function safeNum(x, f = 0) { const n = Number(x); return Number.isFinite(n) ? n : f; }
function smoothstep(t) { return t * t * (3 - 2 * t); }

// ---------- precomputed maps (FAST) ----------
const LIMB_FOR_JOINT = (() => {
  const out = Array(17).fill(null);
  for (const [name, idxs] of Object.entries(LIMBS)) {
    for (const i of idxs) out[i] = name;
  }
  // face/head -> treat as torso for coloring
  for (let i = 0; i <= 4; i++) out[i] = out[i] || "torso";
  return out;
})();

const EDGE_TO_LIMB = (() => {
  const m = new Map();
  const key = (a, b) => `${a},${b}`;
  for (const [name, idxs] of Object.entries(LIMBS)) {
    // connect consecutive bones in the limb chain
    for (let i = 0; i < idxs.length - 1; i++) {
      const a = idxs[i], b = idxs[i + 1];
      m.set(key(a, b), name);
      m.set(key(b, a), name);
    }
  }
  // torso extra links used in EDGES
  const torsoPairs = [
    [5,11],[11,5],[6,12],[12,6],[5,6],[6,5],[11,12],[12,11],
  ];
  for (const [a,b] of torsoPairs) m.set(key(a,b), "torso");
  return m;
})();

function percentile(arr, p) {
  if (!arr || arr.length === 0) return 0;
  const a = [...arr].sort((x, y) => x - y);
  const i = (p / 100) * (a.length - 1);
  const lo = Math.floor(i), hi = Math.ceil(i);
  if (lo === hi) return a[lo];
  return a[lo] + (a[hi] - a[lo]) * (i - lo);
}

function medianSmall(vals) {
  // vals length is tiny (<= 5). Sorting is cheap here.
  const a = vals.slice().sort((x, y) => x - y);
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

function collectAllWrongness(wrongnessTimeline) {
  const all = [];
  if (!wrongnessTimeline) return all;
  for (const k of Object.keys(LIMBS)) {
    const arr = wrongnessTimeline?.[k];
    if (Array.isArray(arr)) {
      for (const v of arr) {
        const x = Number(v);
        if (Number.isFinite(x)) all.push(x);
      }
    }
  }
  return all;
}

// Median filter around t (kills flicker)
// ✅ FIXED: clamps t to timeline length first
function limbWrongMedian(wrongnessTimeline, limbName, t, radius = 2) {
  const arr = wrongnessTimeline?.[limbName];
  if (!Array.isArray(arr) || arr.length === 0) return 0;

  const tt = Math.max(0, Math.min(t, arr.length - 1)); // ✅ critical clamp

  const a = Math.max(0, tt - radius);
  const b = Math.min(arr.length - 1, tt + radius);

  const vals = [];
  for (let i = a; i <= b; i++) {
    const v = Number(arr[i]);
    if (Number.isFinite(v)) vals.push(v);
  }
  return vals.length ? medianSmall(vals) : 0;
}

// Color helpers
function hexToRgb(hex) {
  const h = String(hex || "").replace("#", "").trim();
  if (h.length === 6) {
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16),
    ];
  }
  return [0, 255, 0];
}
function lerp(a, b, t) { return a + (b - a) * t; }
function lerpRgb(a, b, t) {
  const tt = clamp(t, 0, 1);
  return [
    Math.round(a[0] + (b[0] - a[0]) * tt),
    Math.round(a[1] + (b[1] - a[1]) * tt),
    Math.round(a[2] + (b[2] - a[2]) * tt),
  ];
}
function rgbCss([r, g, b]) { return `rgb(${r},${g},${b})`; }
function parseRgbCss(s) {
  if (!s || typeof s !== "string") return [0, 255, 0];
  const m = s.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (!m) return [0, 255, 0];
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}


export default function SkeletonCanvas({
  title = "",
  kpts,
  conf,
  frame = 0,

  wrongnessTimeline = null,

  // ✅ pass refFrame here from App.js (wrongness indexed by ref timeline)
  wrongnessFrame = null,

  confThr = 0.22,
  strictness = 1.0,
  wrongGood = 0.06,
  wrongWarn = 0.12,
  wrongBad = 0.18,
  wrongSevere = 0.26,
  maxRedLimbs = 3,
  normalColor = "#00ff00",

  attentionLevel = 0, // 0..1
  smoothness = 0.6, // 0..1, larger => smoother (slower response)
  compareResult = null,
  stgcnInfluence = 0.35, // 0..1 how much ST-GCN window scores influence limb coloring
  
  // ✅ optional callback to emit limb colors to parent (used by Live feature)
  onLimbVisualChange = null,
}) {
  const canvasRef = useRef(null);

  const GREEN = hexToRgb(normalColor || "#00ff00");
  const YELLOW = hexToRgb("#ffcc00");
  const RED = hexToRgb("#ff0000");

  const Tpose = Array.isArray(kpts) ? kpts.length : 0;
  const tPose = clamp(frame, 0, Math.max(0, Tpose - 1));

  // wrongness index is driven by wrongnessFrame (ref timeline)
  const tWrong = useMemo(() => {
    if (wrongnessFrame == null) return tPose;
    const n = Number(wrongnessFrame);
    return Number.isFinite(n) ? n : tPose;
  }, [wrongnessFrame, tPose]);

  const pts = useMemo(() => {
    const fr = Array.isArray(kpts) ? kpts[tPose] : null;
    if (!Array.isArray(fr) || fr.length !== 17) return null;
    const out = new Array(17);
    for (let i = 0; i < 17; i++) {
      const p = fr[i];
      out[i] = [safeNum(p?.[0], 0), safeNum(p?.[1], 0)];
    }
    return out;
  }, [kpts, tPose]);

  const cf = useMemo(() => {
    const fr = Array.isArray(conf) ? conf[tPose] : null;
    if (!Array.isArray(fr) || fr.length !== 17) return null;
    const out = new Array(17);
    for (let i = 0; i < 17; i++) out[i] = safeNum(fr[i], 0);
    return out;
  }, [conf, tPose]);

  const allWrongness = useMemo(() => collectAllWrongness(wrongnessTimeline), [wrongnessTimeline]);

  const STRICT = clamp(Number(strictness) || 1.0, 0.85, 1.60);
  const strictFactor = 1 / STRICT;

  const dynThr = useMemo(() => {
    if (!allWrongness.length) {
      const baseOn = Math.max(0.10, safeNum(wrongWarn, 0.12));
      const on = clamp(baseOn * strictFactor, 0.06, 0.60);
      const off = clamp(on * 0.78, 0.05, on - 1e-6);
      return { on, off };
    }

    const p70 = percentile(allWrongness, 70);
    const p85 = percentile(allWrongness, 85);
    const p95 = percentile(allWrongness, 95);
    const spread = Math.max(0, p95 - p70);

    let on = (p85 + 0.10 * spread) * strictFactor;
    on = clamp(on, 0.06, 0.60);

    let off = clamp(on * 0.78, 0.05, on - 1e-6);
    off = Math.min(off, p70 * 1.05);

    return { on, off };
  }, [allWrongness, wrongWarn, strictFactor]);

  // Read per-limb badness directly from server-provided `wrongness_limb_timeline` when available.
  // Fallback to local median filter if not provided.
  const limbBad = useMemo(() => {
    const out = {};
    const src = compareResult?.wrongness_limb_timeline;
    // Only use server-provided wrongness when a wrongnessFrame is supplied
    // (prevents coloring the reference skeleton). Fallback to local timeline otherwise.
    const useSrc = src && typeof src === "object" && wrongnessFrame != null;
    const r = 2;
    for (const limb of Object.keys(LIMBS)) {
      let v = 0;
      if (useSrc && Array.isArray(src[limb]) && src[limb].length > 0) {
        v = Number(src[limb][tWrong]);
        if (!Number.isFinite(v)) v = 0;
      } else if (wrongnessTimeline) {
        v = limbWrongMedian(wrongnessTimeline, limb, tWrong, r);
      } else {
        v = 0;
      }
      // clamp to safe range [0,2]
      v = clamp(Number.isFinite(Number(v)) ? Number(v) : 0, 0, 2);
      out[limb] = v;
    }
    return out;
  }, [compareResult?.wrongness_limb_timeline, wrongnessTimeline, tWrong]);

  // smoothing state
  const stRef = useRef(null);
  if (!stRef.current) {
    stRef.current = {};
    for (const k of Object.keys(LIMBS)) stRef.current[k] = { emaErr: 0, vis: 0 };
    // per-joint display positions for smoothing
    stRef.current.jpos = new Array(17).fill(null).map(() => ({ x: 0, y: 0, init: false }));
  }

  const limbVisual = useMemo(() => {
    if (!limbBad) return null;

    const st = stRef.current;

    // faster response
    const ERR_ALPHA = 0.55;
    const VIS_ALPHA = 0.85;

    const attn = clamp(Number(attentionLevel) || 0, 0, 1);
    const attnMul = 1 + 0.90 * attn;

    // compute ST-GCN window modifier for the current frame (1.0 = neutral)
    let stgcnFrameMod = 1.0;
    try {
      const se = compareResult?.stgcn_embedding;
      const winS = Array.isArray(se?.window_scores) ? se.window_scores : [];
      const winC = Array.isArray(se?.window_centers_ref) ? se.window_centers_ref : [];
      if (winS.length && winC.length) {
        // find nearest window center to tWrong
        let bestIdx = -1;
        let bestDist = Infinity;
        for (let wi = 0; wi < winC.length; wi++) {
          const d = Math.abs(Number(winC[wi]) - Number(tWrong));
          if (d < bestDist) {
            bestDist = d;
            bestIdx = wi;
          }
        }
        if (bestIdx >= 0) {
          const s = clamp(Number(winS[bestIdx]) || 0, 0, 1);
          // lower similarity -> increase multiplier slightly
          stgcnFrameMod = 1.0 + stgcnInfluence * (1.0 - s);
        }
      }
    } catch (e) {
      stgcnFrameMod = 1.0;
    }

    // check aligned weight for this frame (gray-out if too low)
    const alignedWeights = Array.isArray(compareResult?.aligned_timeline_weight) ? compareResult.aligned_timeline_weight : null;
    const weightAt = alignedWeights && alignedWeights.length > 0 ? safeNum(alignedWeights[tWrong], 1.0) : 1.0;
    const grayOut = weightAt < 0.2;

    for (const limb of Object.keys(LIMBS)) {
      // factor per-limb joint confidence into the raw error to reduce false positives
      const jointIdxs = LIMBS[limb] || [];
      let limbConf = 1.0;
      if (cf && Array.isArray(cf)) {
        const vals = jointIdxs.map((ii) => safeNum(cf[ii], 0));
        limbConf = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 1.0;
      }
      // map limb confidence to 0..1 where below confThr strongly reduces signal
      const confFactor = clamp((limbConf - confThr) / Math.max(1e-6, (1.0 - confThr)), 0, 1);
      // combine ST-GCN frame modifier (gentle) with attention multiplier
      // Read badness directly from server-provided timeline (clamped above in limbBad)
      const serverBad = safeNum(limbBad[limb], 0);
      const raw = serverBad * attnMul * Math.pow(confFactor, 0.6) * stgcnFrameMod;
      // If overlap weight is very low, gray-out (suppress strong red/green)
      const rawFinal = grayOut ? 0 : raw;
      st[limb].emaErr = st[limb].emaErr * (1 - ERR_ALPHA) + raw * ERR_ALPHA;
    }

    const meanErr =
      (st.left_arm.emaErr + st.right_arm.emaErr + st.left_leg.emaErr + st.right_leg.emaErr + st.torso.emaErr) / 5;

    const mismatchStrong = meanErr >= dynThr.on * 1.10;
    const redCap = mismatchStrong ? 5 : Math.max(1, maxRedLimbs);

    const ranked = Object.keys(LIMBS)
      .map((name) => ({ name, e: st[name].emaErr }))
      .sort((a, b) => b.e - a.e);

    const topSet = new Set(ranked.slice(0, redCap).map((x) => x.name));

    const out = {};
    for (const limb of Object.keys(LIMBS)) {
      const e = st[limb].emaErr;

      const denom = Math.max(1e-6, dynThr.on - dynThr.off);
      let sev = clamp((e - dynThr.off) / denom, 0, 1);
      sev = smoothstep(Math.pow(sev, 0.80));

      st[limb].vis = st[limb].vis * (1 - VIS_ALPHA) + sev * VIS_ALPHA;
      const v = clamp(st[limb].vis, 0, 1);

      // require stronger evidence or membership in topSet plus near-threshold
      let allowFullRed = false;
      if (mismatchStrong) allowFullRed = true;
      else {
        // only allow full red for limbs in the topSet and where emaErr is close to dynThr.on
        allowFullRed = topSet.has(limb) && st[limb].emaErr >= dynThr.on * 0.9;
      }
        const vFinal = allowFullRed ? v : Math.min(v, 0.62);

      let rgb;
      if (grayOut) {
        rgb = [136, 136, 136];
        out[limb] = { color: rgbCss(rgb), sev01: 0.0, err: e };
      } else {
        if (vFinal <= 0.5) rgb = lerpRgb(GREEN, YELLOW, vFinal / 0.5);
        else rgb = lerpRgb(YELLOW, RED, (vFinal - 0.5) / 0.5);
        out[limb] = { color: rgbCss(rgb), sev01: vFinal, err: e };
      }
    }

    return out;
  }, [limbBad, compareResult, attentionLevel, dynThr.on, dynThr.off, maxRedLimbs, GREEN, YELLOW, RED]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width, H = canvas.height;

    // clear
    ctx.clearRect(0, 0, W, H);
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#0f0f0f";
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "#ddd";
    ctx.font = "14px Arial";
    ctx.fillText(title, 10, 18);

    if (!pts) {
      ctx.fillStyle = "#777";
      ctx.font = "12px Arial";
      ctx.fillText("No skeleton for this frame", 10, 40);
      return;
    }

    // bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < 17; i++) {
      const x = pts[i][0], y = pts[i][1];
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }

    const pad = 0.05;
    const dx = Math.max(1e-6, maxX - minX);
    const dy = Math.max(1e-6, maxY - minY);
    minX -= dx * pad; maxX += dx * pad;
    minY -= dy * pad; maxY += dy * pad;

    const invW = 1 / Math.max(1e-6, maxX - minX);
    const invH = 1 / Math.max(1e-6, maxY - minY);

    const toXY = (p) => {
      const x = (p[0] - minX) * invW;
      const y = (p[1] - minY) * invH;
      return [x * (W - 20) + 10, y * (H - 30) + 24];
    };

    // Edges
    ctx.lineCap = "round";

    // compute display points with per-joint EMA smoothing
    const S = clamp(Number(smoothness) || 0.6, 0, 0.99);
    const jpos = stRef.current.jpos;
    const toDisplay = new Array(17);
    for (let i = 0; i < 17; i++) {
      const [dx, dy] = toXY(pts[i]);
      if (!jpos[i].init) {
        jpos[i].x = dx; jpos[i].y = dy; jpos[i].init = true;
      } else {
        // exponential smoothing toward raw position
        jpos[i].x = jpos[i].x * (1 - S) + dx * S;
        jpos[i].y = jpos[i].y * (1 - S) + dy * S;
      }
      toDisplay[i] = [jpos[i].x, jpos[i].y];
    }

    for (let ei = 0; ei < EDGES.length; ei++) {
      const a = EDGES[ei][0];
      const b = EDGES[ei][1];

      const ca = cf ? cf[a] : 1;
      const cb = cf ? cf[b] : 1;
      if (ca < confThr || cb < confThr) continue;

      const [x1, y1] = toDisplay[a];
      const [x2, y2] = toDisplay[b];

      // Determine colors for the two endpoints
      const limbA = LIMB_FOR_JOINT[a] || null;
      const limbB = LIMB_FOR_JOINT[b] || null;
      const colA = limbA && limbVisual && limbVisual[limbA] ? parseRgbCss(limbVisual[limbA].color) : GREEN;
      const colB = limbB && limbVisual && limbVisual[limbB] ? parseRgbCss(limbVisual[limbB].color) : GREEN;

      // blend colors for smooth interpolation
      const br = Math.round((colA[0] + colB[0]) / 2);
      const bg = Math.round((colA[1] + colB[1]) / 2);
      const bb = Math.round((colA[2] + colB[2]) / 2);

      // severity and confidence
      const sevA = limbA && limbVisual && limbVisual[limbA] ? clamp(limbVisual[limbA].sev01 || 0, 0, 1) : 0;
      const sevB = limbB && limbVisual && limbVisual[limbB] ? clamp(limbVisual[limbB].sev01 || 0, 0, 1) : 0;
      const avgSev = (sevA + sevB) / 2;
      const confAlpha = Math.min(ca || 1, cb || 1);

      // width and opacity reflect severity
      const baseWidth = 3;
      const edgeWidth = baseWidth + 2 * avgSev;
      const edgeAlpha = clamp(0.35 + 0.65 * avgSev, 0.25, 1.0) * confAlpha;

      ctx.save();
      ctx.globalAlpha = edgeAlpha;
      ctx.strokeStyle = `rgb(${br},${bg},${bb})`;
      ctx.lineWidth = edgeWidth;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      if (confAlpha < 0.6) ctx.setLineDash([4, 3]);
      else ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.restore();
    }

    // Joints
    for (let i = 0; i < 17; i++) {
      const ci = cf ? cf[i] : 1;
      if (ci < confThr) continue;

      const [x, y] = toDisplay[i];

      let col = rgbCss(GREEN);
      let radius = 5;
      if (wrongnessTimeline && limbVisual) {
        const limbName = LIMB_FOR_JOINT[i];
        if (limbName && limbVisual[limbName]) {
          col = limbVisual[limbName].color;
          const sev = clamp(limbVisual[limbName].sev01 || 0, 0, 1);
          radius = 3 + 3 * sev;
        }
      }

      ctx.fillStyle = col;
      ctx.globalAlpha = clamp(0.5 + 0.5 * ci, 0.3, 1);
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }
  }, [
    title, pts, cf, confThr,
    wrongnessTimeline, limbVisual,
    tPose, tWrong,
    STRICT, attentionLevel, GREEN, smoothness
  ]);

  // ✅ NEW: Emit limbVisual to parent for Live feature integration
  useEffect(() => {
    if (onLimbVisualChange && limbVisual) {
      onLimbVisualChange(limbVisual);
    }
  }, [limbVisual, onLimbVisualChange]);

  return (
    <div style={{ marginTop: 10 }}>
      <canvas
        ref={canvasRef}
        width={520}
        height={360}
        style={{
          border: "1px solid #2a2a2a",
          borderRadius: 10,
          background: "#0f0f0f",
          width: "100%",
          height: "auto",
          maxWidth: 520,
          aspectRatio: "520 / 360",
        }}
      />
    </div>
  );
}
