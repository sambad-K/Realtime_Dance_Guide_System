# services/compare.py
# FIXED + VERSATILE DTW
# ✅ Fixes negative-shift overlap bug (real bug)
# ✅ DTW refinement handles tempo mismatch + different lengths (ref timeline is master)
# ✅ Robust tail (p90) computed on TRUSTED frames when enough; otherwise falls back to old behavior
# ✅ Frontend response shape unchanged
# ✅ ST-GCN logic unchanged (window embedding + strict aggregation + calibration + motion penalty)

import numpy as np
import os
from typing import Optional, List, Dict, Tuple

from config import Config
from services.stgcn_embed import stgcn_embed_sequence_windows, WIN_T, STRIDE

# =========================
# COCO-17 indices
# =========================
LSH, RSH = 5, 6
LEL, REL = 7, 8
LWR, RWR = 9, 10
LHIP, RHIP = 11, 12
LKN, RKN = 13, 14
LAN, RAN = 15, 16

LIMBS = {
    "left_arm": [LSH, LEL, LWR],
    "right_arm": [RSH, REL, RWR],
    "left_leg": [LHIP, LKN, LAN],
    "right_leg": [RHIP, RKN, RAN],
    "torso": [LSH, RSH, LHIP, RHIP],
}

# =========================
# DTW SCORE SHAPE
# =========================
DTW_BETA = 6.5  # higher => stricter

DTW_MEAN_W = 0.65
DTW_ROBUST_P = 90
DTW_ROBUST_W = 0.35  # DTW_MEAN_W + DTW_ROBUST_W should be 1.0

DTW_W = 0.76
# Reduce ST-GCN fusion weight so ST-GCN influences final score only when
# its quality is clearly high.
STGCN_W = 0.05

# =========================
# DTW RELIABILITY PENALTIES
# =========================
DTW_MIN_VALID_RATIO = 0.85
DTW_VALID_RATIO_POWER = 2.0

DTW_SHIFT_SUSPICIOUS_FRAC = 0.85
DTW_SHIFT_POWER = 2.0

DTW_COLLAPSE_OK = 0.08
DTW_COLLAPSE_POWER = 2.0

DTW_MIN_UNIQUE_RATIO = 0.90
DTW_UNIQUE_RATIO_POWER = 2.0

# Optional guard (kept soft)
DTW_P10_GUARD_THR = 0.60
DTW_P10_GUARD_POWER = 2.0
DTW_P10_GUARD_MIN_FACTOR = 0.60
DTW_P10_MIN_TRUSTED_FRAMES = 40

# Frame-confidence trust in DTW scoring
DTW_FRAME_CONF_LOW = 0.10
DTW_FRAME_CONF_HIGH = 0.30
DTW_FRAME_CONF_POW = 1.0

DTW_MAX_POINTS = 1200

# =========================
# ST-GCN STRICTNESS & CALIBRATION
# =========================
STGCN_LOW_P = 10
# Make low-percentile more important (stricter), and reduce mean weight.
STGCN_LOW_P_W = 0.95
STGCN_MEAN_W = 0.05
MOTION_W = 0.60
MOTION_EPS = 1e-6
# Increase confidence threshold required for ST-GCN window rows to be used.
STGCN_CONF_THR = 0.35

# ST-GCN CALIBRATION (authoritative values)
STGCN_CAL_P50 = 0.70
STGCN_CAL_P99 = 0.98
STGCN_CAL_EPS = 1e-9
# Increase gate threshold so ST-GCN only gates ON when its calibrated
# similarity is sufficiently high.
STGCN_USE_THR = 0.80  # gate threshold: require ST-GCN similarity >= this to influence colors


# =========================
# utils
# =========================
def _nan0(x):
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

def _safe_norm(x, axis=None, keepdims=False, eps=1e-6):
    return np.sqrt(np.sum(x * x, axis=axis, keepdims=keepdims) + eps)

def _clamp01(x: float) -> float:
    return float(np.clip(float(x), 0.0, 1.0))


# small helpers to reduce repetition and handle empty arrays safely
def _asf(x):
    """Shorthand for casting arrays to float32."""
    return np.asarray(x, np.float32)


def _safe_percentile(arr, q, default=0.0):
    """Compute percentile safely even when array is empty or invalid."""
    try:
        a = np.asarray(arr)
        if a.size == 0:
            return float(default)
        return np.percentile(a, q) if a.size > 0 else float(default)
    except Exception:
        return float(default)


def _temporal_smooth_1d(x: np.ndarray, win: int = 5) -> np.ndarray:
    """Simple moving-average smoothing (same length output).

    If win <= 1 or sequence too short, returns input copy.
    """
    x = np.asarray(x, dtype=np.float32)
    if win <= 1 or x.size <= 1:
        return x.copy()
    w = max(1, int(win))
    if x.size < 2:
        return x.copy()
    kernel = np.ones((w,), dtype=np.float32) / float(w)
    # use 'same' to preserve length; np.convolve works on 1d
    y = np.convolve(x, kernel, mode="same")
    return y.astype(np.float32)

def _score_from_dtw_mean(dist_mean: float) -> float:
    # Allow small forgiveness defined in Config.DTW_FORGIVENESS (fraction)
    try:
        forg = float(getattr(Config, "DTW_FORGIVENESS", 0.0))
    except Exception:
        forg = 0.0
    eff_beta = float(max(0.0, DTW_BETA * (1.0 - float(forg))))
    s = 100.0 * np.exp(-eff_beta * float(dist_mean))
    return float(np.clip(s, 0.0, 100.0))

def _calibrate_stgcn_cosine(cos_0_1: float, p50: float = STGCN_CAL_P50, p99: float = STGCN_CAL_P99) -> float:
    if cos_0_1 is None:
        return 0.0
    x = float(cos_0_1)
    if not np.isfinite(x):
        return 0.0
    denom = float(p99 - p50)
    if not np.isfinite(denom) or abs(denom) < STGCN_CAL_EPS:
        return float(np.clip(x, 0.0, 1.0))
    s = (x - p50) / (denom + STGCN_CAL_EPS)
    return float(np.clip(s, 0.0, 1.0))

def _frame_features(k: np.ndarray) -> np.ndarray:
    """
    Alignment features: hip-relative + shoulder-axis coordinates.
    k: (T,17,2) -> (T, 34)
    """
    k = np.asarray(k, np.float32)
    T, V, _ = k.shape

    hip = 0.5 * (k[:, LHIP] + k[:, RHIP])
    sh = 0.5 * (k[:, LSH] + k[:, RSH])

    axis = sh - hip
    n = _safe_norm(axis, axis=1, keepdims=True)
    axis_unit = axis / np.maximum(n, 1e-6)

    bad = (n[:, 0] < 1e-3)
    if np.any(bad):
        axis_unit[bad] = np.array([0.0, 1.0], dtype=np.float32)

    feats = []
    for v in range(V):
        dv = k[:, v] - hip
        along = np.sum(dv * axis_unit, axis=1)
        perp = dv[:, 0] * axis_unit[:, 1] - dv[:, 1] * axis_unit[:, 0]
        feats.append(along)
        feats.append(perp)

    F = np.stack(feats, axis=1).astype(np.float32)
    return _nan0(F).astype(np.float32)

def _dtw_align_map(X: np.ndarray, Y: np.ndarray, bw: Optional[int] = None) -> np.ndarray:
    """
    DTW mapping ref index -> user index (for downsampled sequences).
    """
    N = int(X.shape[0])
    M = int(Y.shape[0])
    if N <= 0 or M <= 0:
        return np.zeros((max(N, 1),), dtype=np.int32)

    INF = 1e15
    dp = np.full((N + 1, M + 1), INF, dtype=np.float64)
    ptr = np.zeros((N, M), dtype=np.int8)
    dp[0, 0] = 0.0

    # Determine band (Sakoe-Chiba). bw is half-band in indices around diagonal.
    if bw is None:
        bw_eff = int(getattr(Config, "DTW_BANDWIDTH", 0))
    else:
        bw_eff = int(bw)

    # If non-positive bandwidth -> full DTW
    full = (bw_eff <= 0)

    for i in range(1, N + 1):
        xi = X[i - 1]
        if full:
            j0 = 1
            j1 = M
        else:
            # center around diagonal: j ~= i
            j0 = max(1, i - bw_eff)
            j1 = min(M, i + bw_eff)
        for j in range(j0, j1 + 1):
            cost = float(np.linalg.norm(xi - Y[j - 1]))
            a = dp[i - 1, j - 1]
            b = dp[i - 1, j]
            c = dp[i, j - 1]
            # choose minimum predecessor
            if a <= b and a <= c:
                dp[i, j] = cost + a
                ptr[i - 1, j - 1] = 0
            elif b <= c:
                dp[i, j] = cost + b
                ptr[i - 1, j - 1] = 1
            else:
                dp[i, j] = cost + c
                ptr[i - 1, j - 1] = 2

    # backtrack: find reachable end in last row (handle banded DTW unreachable case)
    last_row = dp[N, 1 : M + 1]
    finite = np.isfinite(last_row)
    if not np.any(finite):
        # fallback diagonal mapping if band made it unreachable
        return np.clip(np.round(np.linspace(0, M - 1, N)).astype(np.int32), 0, M - 1)

    j_end = int(np.argmin(np.where(finite, last_row, INF)) + 1)
    i, j = N - 1, j_end - 1
    path = []
    while i >= 0 and j >= 0:
        path.append((i, j))
        p = ptr[i, j]
        if p == 0:
            i -= 1
            j -= 1
        elif p == 1:
            i -= 1
        else:
            j -= 1
        if i < 0 or j < 0:
            break
    path.reverse()

    # -1 sentinel (0 is valid)
    ref_to_usr = np.full((N,), -1, dtype=np.int32)
    for ii, jj in path:
        ref_to_usr[ii] = int(jj)

    for ii in range(1, N):
        if ref_to_usr[ii] < 0:
            ref_to_usr[ii] = ref_to_usr[ii - 1]

    if ref_to_usr[0] < 0:
        ref_to_usr[0] = 0

    ref_to_usr = np.maximum(ref_to_usr, 0)
    return np.clip(ref_to_usr, 0, M - 1)

def _limb_wrongness(k_ref: np.ndarray, k_usr: np.ndarray, ref_to_usr: np.ndarray):
    out = {name: np.zeros((len(k_ref),), np.float32) for name in LIMBS}
    for t in range(len(k_ref)):
        u = int(ref_to_usr[t])
        u = max(0, min(u, len(k_usr) - 1))
        for name, idxs in LIMBS.items():
            a = k_ref[t, idxs].reshape(-1).astype(np.float32)
            b = k_usr[u, idxs].reshape(-1).astype(np.float32)
            a /= (np.linalg.norm(a) + 1e-6)
            b /= (np.linalg.norm(b) + 1e-6)
            out[name][t] = float(np.clip(1.0 - float(np.dot(a, b)), 0.0, 2.0))
    return out

def _window_centers(T: int) -> np.ndarray:
    if T < WIN_T:
        return np.array([], dtype=np.int32)
    centers = []
    for start in range(0, T - WIN_T + 1, STRIDE):
        centers.append(start + WIN_T // 2)
    return np.array(centers, dtype=np.int32)

def _l2_rows(Z: np.ndarray) -> np.ndarray:
    Z = _nan0(np.asarray(Z, np.float32))
    if Z.ndim != 2 or Z.shape[0] == 0:
        return np.zeros((0, 1), np.float32)
    n = np.linalg.norm(Z, axis=1, keepdims=True) + 1e-6
    return _nan0(Z / n).astype(np.float32)

def _aligned_window_similarity(
    Zr: np.ndarray,
    Zu: np.ndarray,
    align_ref_to_user: List[int],
    T1: int,
    T2: int,
) -> Tuple[float, np.ndarray, Dict]:
    Zr = _l2_rows(Zr)
    Zu = _l2_rows(Zu)

    Cr = _window_centers(T1)
    Cu = _window_centers(T2)

    if Zr.shape[0] != Cr.shape[0] or Zu.shape[0] != Cu.shape[0]:
        n = min(Zr.shape[0], Zu.shape[0])
        if n <= 0:
            return 0.0, np.zeros((0,), np.float32), {"mode": "fallback_empty", "paired_windows": 0}
        sims = np.sum(Zr[:n] * Zu[:n], axis=1)
        sims = _nan0(np.clip(sims, 0.0, 1.0))
        return float(np.mean(sims)), sims.astype(np.float32), {"mode": "fallback_diag", "paired_windows": int(n)}

    per_win = np.zeros((len(Cr),), dtype=np.float32)
    paired = 0

    for i, cref in enumerate(Cr):
        if not (0 <= int(cref) < len(align_ref_to_user)):
            per_win[i] = 0.0
            continue

        uframe = align_ref_to_user[int(cref)]
        if uframe is None or uframe < 0:
            per_win[i] = 0.0
            continue

        j = int(np.searchsorted(Cu, uframe))
        candidates = []
        if 0 <= j < len(Cu): candidates.append(j)
        if 0 <= j - 1 < len(Cu): candidates.append(j - 1)
        if 0 <= j + 1 < len(Cu): candidates.append(j + 1)

        best = 0.0
        for jj in candidates:
            s = float(np.dot(Zr[i], Zu[jj]))
            if s > best:
                best = s

        per_win[i] = float(np.clip(best, 0.0, 1.0))
        paired += 1

    return float(np.mean(per_win)) if per_win.size else 0.0, per_win.astype(np.float32), {
        "mode": "aligned_windows", "paired_windows": int(paired)
    }

def _aggregate_strict(per_win: np.ndarray) -> Tuple[float, Dict]:
    if per_win.size == 0:
        return 0.0, {"low_p": 0.0, "mean": 0.0}
    p = float(np.percentile(per_win, STGCN_LOW_P))
    m = float(np.mean(per_win))
    s = STGCN_MEAN_W * m + STGCN_LOW_P_W * p
    return float(np.clip(s, 0.0, 1.0)), {"low_p": p, "mean": m}

def _motion_mismatch(k_ref: np.ndarray, k_usr: np.ndarray, align_ref_to_user: List[int]) -> float:
    kr = _nan0(np.asarray(k_ref, np.float32))
    ku = _nan0(np.asarray(k_usr, np.float32))
    T1 = kr.shape[0]
    T2 = ku.shape[0]
    if T1 < 3 or T2 < 3:
        return 1.0

    vr = kr[1:] - kr[:-1]
    vu = ku[1:] - ku[:-1]
    sr = np.linalg.norm(vr, axis=2).mean(axis=1)
    su = np.linalg.norm(vu, axis=2).mean(axis=1)

    centers_ref = _window_centers(T1)
    if centers_ref.size == 0:
        return 1.0

    Er, Eu = [], []
    half = WIN_T // 2

    for cref in centers_ref:
        r0 = max(0, int(cref) - half)
        r1 = min(T1 - 1, int(cref) + half)
        Er_i = float(np.mean(sr[r0:r1])) if r1 > r0 else 0.0

        uframe = align_ref_to_user[int(cref)] if 0 <= int(cref) < len(align_ref_to_user) else -1
        if uframe is None or uframe < 0:
            Eu_i = 0.0
        else:
            u0 = max(0, int(uframe) - half)
            u1 = min(T2 - 1, int(uframe) + half)
            Eu_i = float(np.mean(su[u0:u1])) if u1 > u0 else 0.0

        Er.append(Er_i)
        Eu.append(Eu_i)

    Er = np.asarray(Er, np.float32)
    Eu = np.asarray(Eu, np.float32)
    denom = (Er + Eu + MOTION_EPS)
    mm = float(np.mean(np.abs(Er - Eu) / denom)) if denom.size else 1.0
    return float(np.clip(mm, 0.0, 1.0))

def _frame_confidence(c_ref: np.ndarray, c_usr: np.ndarray, align_ref_to_user: List[int]) -> np.ndarray:
    cr = np.asarray(c_ref, np.float32)
    cu = np.asarray(c_usr, np.float32)
    T1 = int(cr.shape[0])
    w = np.zeros((T1,), np.float32)

    for t in range(T1):
        u = align_ref_to_user[t] if 0 <= t < len(align_ref_to_user) else -1
        if u is None or u < 0 or u >= int(cu.shape[0]):
            w[t] = 0.0
            continue

        rmean = float(np.mean(cr[t])) if cr.ndim == 2 else float(cr[t])
        umean = float(np.mean(cu[u])) if cu.ndim == 2 else float(cu[u])
        m = 0.5 * (rmean + umean)

        if m <= DTW_FRAME_CONF_LOW:
            ww = 0.0
        elif m >= DTW_FRAME_CONF_HIGH:
            ww = 1.0
        else:
            ww = (m - DTW_FRAME_CONF_LOW) / max(1e-6, (DTW_FRAME_CONF_HIGH - DTW_FRAME_CONF_LOW))

        ww = float(np.clip(ww, 0.0, 1.0))
        if DTW_FRAME_CONF_POW != 1.0:
            ww = float(ww ** DTW_FRAME_CONF_POW)
        w[t] = ww

    return w.astype(np.float32)

def _reliability_penalty(
    valid_ratio: float,
    unique_ratio: float,
    collapse_ratio: float,
    best_shift: int,
    max_shift: int,
) -> Tuple[float, Dict]:
    dbg = {}

    vr = float(np.clip(valid_ratio, 0.0, 1.0))
    if vr >= DTW_MIN_VALID_RATIO:
        p_valid = 1.0
    else:
        p_valid = (vr / max(1e-6, DTW_MIN_VALID_RATIO)) ** DTW_VALID_RATIO_POWER
    p_valid = _clamp01(p_valid)
    dbg["p_valid"] = p_valid

    ur = float(np.clip(unique_ratio, 0.0, 1.0))
    if ur >= DTW_MIN_UNIQUE_RATIO:
        p_unique = 1.0
    else:
        p_unique = (ur / max(1e-6, DTW_MIN_UNIQUE_RATIO)) ** DTW_UNIQUE_RATIO_POWER
    p_unique = _clamp01(p_unique)
    dbg["p_unique"] = p_unique

    cr = float(np.clip(collapse_ratio, 0.0, 1.0))
    if cr <= DTW_COLLAPSE_OK:
        p_collapse = 1.0
    else:
        x = 1.0 - (cr - DTW_COLLAPSE_OK) / max(1e-6, (1.0 - DTW_COLLAPSE_OK))
        p_collapse = x ** DTW_COLLAPSE_POWER
    p_collapse = _clamp01(p_collapse)
    dbg["p_collapse"] = p_collapse

    if max_shift <= 0:
        p_shift = 1.0
        shift_frac = 0.0
    else:
        shift_frac = abs(float(best_shift)) / float(max_shift)
        if shift_frac <= DTW_SHIFT_SUSPICIOUS_FRAC:
            p_shift = 1.0
        else:
            x = 1.0 - (shift_frac - DTW_SHIFT_SUSPICIOUS_FRAC) / max(1e-6, (1.0 - DTW_SHIFT_SUSPICIOUS_FRAC))
            p_shift = x ** DTW_SHIFT_POWER
    p_shift = _clamp01(p_shift)
    dbg["p_shift"] = p_shift
    dbg["shift_frac"] = float(shift_frac)

    p = float(np.clip(p_valid * p_unique * p_collapse * p_shift, 0.0, 1.0))
    dbg["penalty_total"] = p
    return p, dbg


def _recompute_all_from_alignment(
    align_ref_to_user: List[int],
    f_ref_n: np.ndarray,
    f_usr_n: np.ndarray,
    c_ref: np.ndarray,
    c_usr: np.ndarray,
    k_ref_norm: np.ndarray,
    k_usr_norm: np.ndarray,
    T1: int,
    T2: int,
    max_shift_eff: int,
    best_shift: int,
):
    """Recompute alignment-derived timelines, confidence weights, DTW stats and wrongness.

    Returns a dict of metrics used by the caller.
    """
    aligned_cos_raw = np.zeros((T1,), dtype=np.float32)
    aligned_cos = np.zeros((T1,), dtype=np.float32)
    valid_mask = np.zeros((T1,), dtype=np.bool_)

    for t in range(T1):
        u = align_ref_to_user[t]
        if u is None or u < 0 or u >= T2:
            valid_mask[t] = False
            aligned_cos_raw[t] = 0.0
            aligned_cos[t] = 0.0
        else:
            raw = float(np.clip(np.dot(f_ref_n[t], f_usr_n[u]), -1.0, 1.0))
            aligned_cos_raw[t] = raw
            aligned_cos[t] = float(np.clip(0.5 * (raw + 1.0), 0.0, 1.0))
            valid_mask[t] = True

    valid_count = int(np.sum(valid_mask))
    valid_ratio = float(valid_count) / float(max(1, T1))
    invalid_ratio = 1.0 - valid_ratio

    valid_us = [align_ref_to_user[t] for t in range(T1) if valid_mask[t]]
    unique_user_frames = len(set(valid_us)) if valid_us else 0
    unique_ratio = float(unique_user_frames) / float(max(1, valid_count))
    collapse_ratio = float(1.0 - unique_ratio)

    mono_viol = 0
    last_u = -1
    for t in range(T1):
        u = align_ref_to_user[t]
        if u is None or u < 0:
            continue
        if last_u >= 0 and u < last_u:
            mono_viol += 1
        last_u = u

    # confidence weights
    w = _frame_confidence(c_ref, c_usr, align_ref_to_user)
    w = w * valid_mask.astype(np.float32)

    lowconf_run = 0
    cur = 0
    for t in range(T1):
        if w[t] <= 1e-6:
            cur += 1
            lowconf_run = max(lowconf_run, cur)
        else:
            cur = 0
    effective_trusted_ratio = float(np.mean(w > 0.5)) if T1 > 0 else 0.0

    # DTW distances / stats
    if valid_count > 0:
        dist_per = (1.0 - aligned_cos[valid_mask]).astype(np.float32)
        dtw_dist_mean = float(np.mean(dist_per))

        cosine_valid = aligned_cos[valid_mask].astype(np.float32)
        cosine_valid_mean = float(np.mean(cosine_valid))
        cosine_valid_min = float(np.min(cosine_valid))
        cosine_valid_p10 = _safe_percentile(cosine_valid, 10, default=0.0)
        cosine_valid_p50 = _safe_percentile(cosine_valid, 50, default=0.0)

        trusted_mask = valid_mask & (w > 0.5)
        trusted_count = int(np.sum(trusted_mask))
        if trusted_count > 0:
            cosine_trusted = aligned_cos[trusted_mask].astype(np.float32)
            cosine_trusted_p10 = _safe_percentile(cosine_trusted, 10, default=float(cosine_valid_p10))
        else:
            cosine_trusted_p10 = float(cosine_valid_p10)

        if trusted_count >= 20:
            dist_trusted = (1.0 - aligned_cos[trusted_mask]).astype(np.float32)
            dtw_dist_robust = _safe_percentile(dist_trusted, DTW_ROBUST_P, default=1.0)
            robust_mode = "trusted"
        else:
            dtw_dist_robust = _safe_percentile(dist_per, DTW_ROBUST_P, default=1.0)
            robust_mode = "all_valid"
    else:
        dtw_dist_mean = 1.0
        dtw_dist_robust = 1.0
        robust_mode = "none"
        cosine_valid_mean = 0.0
        cosine_valid_min = 0.0
        cosine_valid_p10 = 0.0
        cosine_valid_p50 = 0.0
        trusted_count = 0
        cosine_trusted_p10 = 0.0

    if valid_count > 0:
        dist_all = (1.0 - aligned_cos).astype(np.float32)
        num = float(np.sum(dist_all * w))
        den = float(np.sum(w) + 1e-9)
        dtw_dist_weighted_mean = num / den
    else:
        dtw_dist_weighted_mean = 1.0

    # near0 run
    near0_run = 0
    cur = 0
    for t in range(T1):
        if valid_mask[t] and aligned_cos[t] <= 1e-6:
            cur += 1
            near0_run = max(near0_run, cur)
        else:
            cur = 0

    dtw_dist_combo = DTW_MEAN_W * dtw_dist_weighted_mean + DTW_ROBUST_W * dtw_dist_robust
    base_score = _score_from_dtw_mean(dtw_dist_combo)

    pen, pen_dbg = _reliability_penalty(
        valid_ratio=valid_ratio,
        unique_ratio=unique_ratio,
        collapse_ratio=collapse_ratio,
        best_shift=int(best_shift),
        max_shift=int(max_shift_eff),
    )
    overall_score = float(np.clip(base_score * pen, 0.0, 100.0))

    # soft p10 guard
    p10_guard_factor = 1.0
    p10_guard_val = float(cosine_trusted_p10) if np.isfinite(cosine_trusted_p10) else 1.0
    if trusted_count >= DTW_P10_MIN_TRUSTED_FRAMES and p10_guard_val < DTW_P10_GUARD_THR:
        p10_guard_factor = float((p10_guard_val / max(1e-6, DTW_P10_GUARD_THR)) ** DTW_P10_GUARD_POWER)
        p10_guard_factor = float(np.clip(p10_guard_factor, DTW_P10_GUARD_MIN_FACTOR, 1.0))
        overall_score = float(np.clip(overall_score * p10_guard_factor, 0.0, 100.0))

    # wrongness
    ref_to_usr_arr = np.array([max(0, u) if u >= 0 else 0 for u in align_ref_to_user], dtype=np.int32)
    wrongness = _limb_wrongness(k_ref_norm, k_usr_norm, ref_to_usr_arr)
    wrong_scale = w.astype(np.float32)
    for limb in wrongness.keys():
        wrongness[limb] = wrongness[limb] * wrong_scale
    wrongness_limb_timeline = {limb: arr.tolist() for limb, arr in wrongness.items()}

    return {
        "aligned_cos_raw": aligned_cos_raw,
        "aligned_cos": aligned_cos,
        "valid_mask": valid_mask,
        "w": w,
        "valid_count": valid_count,
        "valid_ratio": valid_ratio,
        "invalid_ratio": invalid_ratio,
        "unique_user_frames": unique_user_frames,
        "unique_ratio": unique_ratio,
        "collapse_ratio": collapse_ratio,
        "mono_viol": mono_viol,
        "near0_run": near0_run,
        "dtw_dist_mean": dtw_dist_mean,
        "dtw_dist_robust": dtw_dist_robust,
        "robust_mode": robust_mode,
        "dtw_dist_weighted_mean": dtw_dist_weighted_mean,
        "dtw_dist_combo": dtw_dist_combo,
        "base_score": base_score,
        "pen": pen,
        "pen_dbg": pen_dbg,
        "overall_score": overall_score,
        "cosine_valid_mean": cosine_valid_mean,
        "cosine_valid_min": cosine_valid_min,
        "cosine_valid_p10": cosine_valid_p10,
        "cosine_valid_p50": cosine_valid_p50,
        "trusted_count": trusted_count,
        "cosine_trusted_p10": cosine_trusted_p10,
        "p10_guard_factor": p10_guard_factor,
        "p10_guard_val": p10_guard_val,
        "wrongness_limb_timeline": wrongness_limb_timeline,
        "wrongness": wrongness,
        "wrong_scale": wrong_scale,
        "lowconf_run": lowconf_run,
        "effective_trusted_ratio": effective_trusted_ratio,
    }


# =========================
# main
# =========================
def compare_sequences(
    k_ref_norm: np.ndarray,
    c_ref: np.ndarray,
    k_usr_norm: np.ndarray,
    c_usr: np.ndarray,
    max_shift: int = 240,
    k_ref_raw: Optional[np.ndarray] = None,
    k_usr_raw: Optional[np.ndarray] = None,
):
    """Compare two pose sequences and return scoring + diagnostics.

    Uses DTW + optional ST-GCN fusion. This wrapper keeps existing
    behavior while using small helpers to reduce repetition.
    """
    k_ref_norm = _asf(k_ref_norm)
    k_usr_norm = _asf(k_usr_norm)
    c_ref = _asf(c_ref)
    c_usr = _asf(c_usr)

    T1 = int(k_ref_norm.shape[0])
    T2 = int(k_usr_norm.shape[0])

    if T1 < 2 or T2 < 2:
        return {
            "overall_score_0_100": 0.0,
            "final_score_0_100": 0.0,
            "shift_frames": 0,
            "auto_sync": {"shift_frames": 0},
            "align_ref_to_user": [-1] * max(T1, 1),
            "wrongness_limb_timeline": {k: [] for k in LIMBS.keys()},
            "aligned_timeline_cosine": [],
            "aligned_timeline_cosine_raw": [],
            "aligned_timeline_weight": [],
            "dtw_debug": {"error": "too few frames", "T_ref": T1, "T_usr": T2},
            "stgcn_embedding": {
                "enabled": False,
                "sim_0_1": None,
                "error": "too few frames",
                "debug": None,
                "window_scores": [],
                "window_centers_ref": [],
                "scores": None,
                "quality": None,
                "limb_similarity": {k: None for k in LIMBS.keys()},
            },
        }

    # ---- alignment features
    f_ref = _frame_features(k_ref_norm)
    f_usr = _frame_features(k_usr_norm)
    f_ref_n = f_ref / np.maximum(_safe_norm(f_ref, axis=1, keepdims=True), 1e-6)
    f_usr_n = f_usr / np.maximum(_safe_norm(f_usr, axis=1, keepdims=True), 1e-6)

    # ---- coarse shift search (FIXED for negative shifts)
    best_shift = 0
    best_mean = -1e9

    # limit effective max shift to avoid matching tiny overlaps
    max_shift_eff = int(max(0, min(int(max_shift), max(0, min(T1, T2) - 12))))
    for s in range(-max_shift_eff, max_shift_eff + 1):
        t0 = max(0, -s)
        t1 = min(T1, T2 - s)  # ✅ correct for both signs
        if t1 - t0 < 12:
            continue
        a = f_ref_n[t0:t1]
        b = f_usr_n[t0 + s:t1 + s]
        # compute per-frame confidence weights for this candidate alignment
        try:
            cr_seg = c_ref[t0:t1]
            cu_seg = c_usr[t0 + s : t1 + s]
            if cr_seg.ndim == 2:
                rmean = np.mean(cr_seg, axis=1)
            else:
                rmean = np.asarray(cr_seg, np.float32)
            if cu_seg.ndim == 2:
                umean = np.mean(cu_seg, axis=1)
            else:
                umean = np.asarray(cu_seg, np.float32)
            m_frame = 0.5 * (rmean + umean)
            ww = np.zeros_like(m_frame, dtype=np.float32)
            low = float(DTW_FRAME_CONF_LOW)
            high = float(DTW_FRAME_CONF_HIGH)
            span = max(1e-6, (high - low))
            ww[m_frame <= low] = 0.0
            ww[m_frame >= high] = 1.0
            mask = (m_frame > low) & (m_frame < high)
            ww[mask] = (m_frame[mask] - low) / span
            if DTW_FRAME_CONF_POW != 1.0:
                ww = ww ** float(DTW_FRAME_CONF_POW)
            weights = ww.astype(np.float32)
        except Exception:
            weights = None

        dots = np.sum(a * b, axis=1)
        if weights is None or np.sum(weights) <= 0:
            m = float(np.mean(dots))
        else:
            m = float(np.sum(dots * weights) / (np.sum(weights) + 1e-9))

        if m > best_mean:
            best_mean = m
            best_shift = s

    align_ref_to_user: List[int] = []
    for t in range(T1):
        u = t + best_shift
        align_ref_to_user.append(int(u) if 0 <= u < T2 else -1)

    # ---- DTW refinement
    # Use normalized frame-direction features for DTW refinement so DTW
    # prefers directional similarity (cosine) rather than magnitude.
    if best_shift >= 0:
        ref_offset = 0
        ref_win = f_ref_n[0:T1]
        usr_offset = best_shift
        usr_win = f_usr_n[best_shift:T2]
    else:
        s = -best_shift
        ref_offset = s
        ref_win = f_ref_n[s:T1]
        usr_offset = 0
        usr_win = f_usr_n[0:T2]

    dtw_ref_dbg = {"used": False}
    if len(ref_win) >= 12 and len(usr_win) >= 12:
        step = max(1, int(np.ceil(max(len(ref_win), len(usr_win)) / DTW_MAX_POINTS)))
        # compute effective bandwidth for the downsampled sequences
        cfg_bw = int(getattr(Config, "DTW_BANDWIDTH", 0))
        if cfg_bw > 0:
            bw_frames = cfg_bw
        else:
            # dynamic policy: proportional to longer sequence length (12% by default)
            bw_frames = max(10, int(0.12 * max(len(ref_win), len(usr_win))))
        if step > 1 and bw_frames > 0:
            bw_small = int(np.ceil(bw_frames / float(step)))
        else:
            bw_small = bw_frames
        map_small = _dtw_align_map(ref_win[::step], usr_win[::step], bw=bw_small)
        map_full = np.minimum(map_small.repeat(step)[: len(ref_win)], len(usr_win) - 1)

        for i in range(len(ref_win)):
            rt = ref_offset + i
            ut = usr_offset + int(map_full[i])
            if 0 <= rt < T1 and 0 <= ut < T2:
                align_ref_to_user[rt] = ut

        dtw_ref_dbg = {
            "used": True,
            "downsample_step": int(step),
            "ref_offset": int(ref_offset),
            "usr_offset": int(usr_offset),
            "ref_win_len": int(len(ref_win)),
            "usr_win_len": int(len(usr_win)),
        }

    # record overlap ranges for debugging (absolute indices)
    overlap_ref_start = int(ref_offset)
    overlap_ref_end = int(ref_offset + len(ref_win) - 1) if len(ref_win) > 0 else int(ref_offset)
    overlap_usr_start = int(usr_offset)
    overlap_usr_end = int(usr_offset + len(usr_win) - 1) if len(usr_win) > 0 else int(usr_offset)

    # ---- compute alignment-derived metrics using helper
    _metrics = _recompute_all_from_alignment(
        align_ref_to_user,
        f_ref_n,
        f_usr_n,
        c_ref,
        c_usr,
        k_ref_norm,
        k_usr_norm,
        T1,
        T2,
        max_shift_eff,
        best_shift,
    )

    aligned_cos_raw = _metrics["aligned_cos_raw"]
    aligned_cos = _metrics["aligned_cos"]
    valid_mask = _metrics["valid_mask"]
    w = _metrics["w"]
    valid_count = _metrics["valid_count"]
    valid_ratio = _metrics["valid_ratio"]
    invalid_ratio = _metrics["invalid_ratio"]
    unique_user_frames = _metrics["unique_user_frames"]
    unique_ratio = _metrics["unique_ratio"]
    collapse_ratio = _metrics["collapse_ratio"]
    mono_viol = _metrics["mono_viol"]
    near0_run = _metrics["near0_run"]
    dtw_dist_mean = _metrics["dtw_dist_mean"]
    dtw_dist_robust = _metrics["dtw_dist_robust"]
    robust_mode = _metrics["robust_mode"]
    dtw_dist_weighted_mean = _metrics["dtw_dist_weighted_mean"]
    dtw_dist_combo = _metrics["dtw_dist_combo"]
    base_score = _metrics["base_score"]
    pen = _metrics["pen"]
    pen_dbg = _metrics["pen_dbg"]
    overall_score = _metrics["overall_score"]
    cosine_valid_mean = _metrics["cosine_valid_mean"]
    cosine_valid_min = _metrics["cosine_valid_min"]
    cosine_valid_p10 = _metrics["cosine_valid_p10"]
    cosine_valid_p50 = _metrics["cosine_valid_p50"]
    trusted_count = _metrics["trusted_count"]
    cosine_trusted_p10 = _metrics["cosine_trusted_p10"]
    p10_guard_factor = _metrics["p10_guard_factor"]
    p10_guard_val = _metrics["p10_guard_val"]
    wrongness_limb_timeline = _metrics["wrongness_limb_timeline"]
    wrongness = _metrics["wrongness"]
    wrong_scale = _metrics["wrong_scale"]
    lowconf_run = _metrics["lowconf_run"]
    effective_trusted_ratio = _metrics["effective_trusted_ratio"]

    # wrongness already computed by helper `_recompute_all_from_alignment`
    # keep `wrongness_limb_timeline` and `wrongness` from the helper to avoid duplicate computation

    # ---- ST-GCN on RAW (unchanged)
    if k_ref_raw is None:
        k_ref_raw = k_ref_norm
    if k_usr_raw is None:
        k_usr_raw = k_usr_norm

    stgcn_sim_0_1 = None
    stgcn_err = None
    stgcn_debug = None
    stgcn_window_scores: List[float] = []
    stgcn_window_centers_ref: List[int] = []
    stgcn_scores_extra: Dict = {}
    stgcn_quality: Dict = {}
    # debug / control defaults for two-pass DTW
    remapped = 0
    refined_used = False
    refined_valid_ratio = None
    refined_unique_ratio = None
    refined_collapse_ratio = None

    ckpt_path = getattr(Config, "STGCN_CKPT", None) or getattr(Config, "STGCN_CKPT_PATH", None)
    if not ckpt_path:
        stgcn_err = "ST-GCN checkpoint path not set in Config (STGCN_CKPT)"
    else:
        # Prefer computing embeddings on the overlapping alignment region (safer for variable lengths).
        # Determine overlap slices (ref_offset/usr_offset and ref_win/usr_win were computed above)
        # If the overlap is long enough for ST-GCN windows, use the slices; otherwise fall back to full sequences.
        use_embed_dtw = bool(getattr(Config, "EMBED_DTW_ENABLED", False))
        embed_thresh = float(getattr(Config, "EMBED_DTW_THRESHOLD", 60.0))
        # adaptive: only run embed-DTW when frame-based DTW score suggests it's needed
        use_embed_dtw = use_embed_dtw and (float(overall_score) < float(embed_thresh))

        # compute overlap slices
        try:
            Lr = len(ref_win)
            Lu = len(usr_win)
        except Exception:
            Lr = T1
            Lu = T2

        stgcn_used_overlap = False
        Zr = Zu = None
        er = eu = None

        if use_embed_dtw and Lr >= WIN_T and Lu >= WIN_T:
            # overlap slices in absolute coords
            s_ref = int(ref_offset)
            s_usr = int(usr_offset)
            k_ref_slice = k_ref_raw[s_ref : s_ref + Lr]
            c_ref_slice = c_ref[s_ref : s_ref + Lr]
            k_usr_slice = k_usr_raw[s_usr : s_usr + Lu]
            c_usr_slice = c_usr[s_usr : s_usr + Lu]

            Zr, er = stgcn_embed_sequence_windows(k_ref_slice, c_ref_slice, ckpt_path=ckpt_path, conf_thr=STGCN_CONF_THR)
            Zu, eu = stgcn_embed_sequence_windows(k_usr_slice, c_usr_slice, ckpt_path=ckpt_path, conf_thr=STGCN_CONF_THR)
            if Zr is not None and Zu is not None:
                stgcn_used_overlap = True

        # if overlap path not usable, fall back to full sequences (existing behavior)
        if not stgcn_used_overlap:
            Zr, er = stgcn_embed_sequence_windows(k_ref_raw, c_ref, ckpt_path=ckpt_path, conf_thr=STGCN_CONF_THR)
            Zu, eu = stgcn_embed_sequence_windows(k_usr_raw, c_usr, ckpt_path=ckpt_path, conf_thr=STGCN_CONF_THR)

        if Zr is None or Zu is None:
            stgcn_err = er or eu or "ST-GCN disabled"
        else:
            # Optionally run DTW on ST-GCN window embeddings to produce a window-level mapping
            # which is then projected to frame-level alignments. This helps when timelines
            # differ in tempo — embeddings capture motion patterns and DTW on them is more robust.
            use_embed_dtw_now = bool(getattr(Config, "EMBED_DTW_ENABLED", False)) and (float(overall_score) < float(embed_thresh))
            if use_embed_dtw_now:
                try:
                    ZrN_tmp = _l2_rows(Zr)
                    ZuN_tmp = _l2_rows(Zu)
                    if ZrN_tmp.shape[0] > 0 and ZuN_tmp.shape[0] > 0:
                        # compute DTW map on window embeddings (downsampled windows are small)
                        # determine window-bandwidth from frame-bandwidth
                        cfg_bw = int(getattr(Config, "DTW_BANDWIDTH", 0))
                        if cfg_bw > 0:
                            bw_frames = cfg_bw
                        else:
                            bw_frames = max(10, int(0.12 * max(T1, T2)))
                        if bw_frames > 0:
                            bw_win = int(np.ceil(bw_frames / max(1, int(STRIDE))))
                        else:
                            bw_win = bw_frames
                        win_map = _dtw_align_map(ZrN_tmp, ZuN_tmp, bw=bw_win)

                        # window centers depend whether Zr/Z u were computed on overlap slices
                        if stgcn_used_overlap:
                            # centers relative to slices, convert to absolute by adding offsets
                            Cr_rel = _window_centers(len(k_ref_slice))
                            Cu_rel = _window_centers(len(k_usr_slice))
                            Cr = (Cr_rel + s_ref).astype(np.int32)
                            Cu = (Cu_rel + s_usr).astype(np.int32)
                        else:
                            Cr = _window_centers(T1)
                            Cu = _window_centers(T2)

                        if Cr.size and Cu.size:
                            # copy existing frame alignment and override centers where we have window matches
                            align_override = list(align_ref_to_user)
                            remapped = 0
                            mapped_pairs = []
                            for wi, cref in enumerate(Cr):
                                if wi < len(win_map):
                                    uwin = int(win_map[wi])
                                    if 0 <= uwin < len(Cu):
                                        uframe = int(Cu[uwin])
                                        align_override[int(cref)] = uframe
                                        remapped += 1
                                        mapped_pairs.append((int(cref), int(uframe)))

                            # baseline window similarity using override (for diagnostics)
                            mean_sim, per_win, extra = _aligned_window_similarity(Zr, Zu, align_override, T1, T2)

                            # Two-pass refinement (minimal-risk): only attempt full-resolution banded DTW
                            # if we actually remapped at least one window. Use conservative bandwidth
                            # and acceptance checks to avoid degrading alignments.
                            refined_used = False
                            refined_valid_ratio = None
                            refined_unique_ratio = None
                            refined_collapse_ratio = None
                            try:
                                if remapped > 0:
                                    # conservative global frame-bandwidth (clamped)
                                    cfg_bw2 = int(getattr(Config, "DTW_BANDWIDTH", 0))
                                    if cfg_bw2 > 0:
                                        bw_frames2 = cfg_bw2
                                    else:
                                        bw_frames2 = max(10, int(0.12 * max(T1, T2)))
                                    # clamp to avoid huge bands
                                    max_bw_cap = max(200, int(0.5 * max(T1, T2)))
                                    bw_frames2 = int(np.clip(int(bw_frames2), 1, max_bw_cap))

                                    # run banded DTW on full-resolution frame features
                                    # Run candidate DTW on normalized features as well
                                    cand_map = _dtw_align_map(f_ref_n, f_usr_n, bw=bw_frames2)

                                    # compute simple validity metrics for candidate map
                                    vc = np.sum((cand_map >= 0) & (cand_map < T2))
                                    vratio_cand = float(vc) / float(max(1, T1))
                                    unique_cand = len(set(int(x) for x in cand_map if x >= 0))
                                    uniq_ratio_cand = float(unique_cand) / float(max(1, vc)) if vc > 0 else 0.0
                                    collapse_cand = float(1.0 - uniq_ratio_cand)

                                    # acceptance heuristics: candidate shouldn't materially worsen validity
                                    valid_ok = (vratio_cand >= max(0.0, valid_ratio - 0.02))
                                    unique_ok = (uniq_ratio_cand >= max(0.0, unique_ratio - 0.02))

                                    # TEST OVERRIDE: allow forcing acceptance for debugging.
                                    # Set environment var FORCE_ACCEPT_REFINED=1 or Config.FORCE_ACCEPT_REFINED=True
                                    try:
                                        force_accept = bool(int(os.getenv("FORCE_ACCEPT_REFINED", "0")))
                                    except Exception:
                                        force_accept = False
                                    if not force_accept:
                                        force_accept = bool(getattr(Config, "FORCE_ACCEPT_REFINED", False))
                                    if force_accept:
                                        valid_ok = True
                                        unique_ok = True

                                    # check remapped centers are not wildly different
                                    center_matches = 0
                                    bw_accept = max(5, int(0.05 * max(T1, T2)))
                                    for cref, uframe in mapped_pairs:
                                        if 0 <= cref < len(cand_map):
                                            if abs(int(cand_map[cref]) - int(uframe)) <= bw_accept:
                                                center_matches += 1

                                    center_ok = (center_matches >= max(1, int(0.5 * remapped)))

                                    if valid_ok and unique_ok and center_ok:
                                        # additional monotonicity check on candidate map to avoid flat/weird maps
                                        mono_viol_cand = 0
                                        for t in range(1, T1):
                                            try:
                                                if int(cand_map[t]) < int(cand_map[t - 1]):
                                                    mono_viol_cand += 1
                                            except Exception:
                                                pass
                                        mono_ok = (mono_viol_cand <= max(0, int(0.02 * T1)))

                                        if mono_ok:
                                            # accept refined mapping
                                            align_ref_to_user = [int(x) for x in cand_map]
                                            refined_used = True
                                            refined_valid_ratio = float(vratio_cand)
                                            refined_unique_ratio = float(uniq_ratio_cand)
                                            refined_collapse_ratio = float(collapse_cand)

                                            # recompute all metrics using helper to keep a single final alignment
                                            _metrics = _recompute_all_from_alignment(
                                                align_ref_to_user,
                                                f_ref_n,
                                                f_usr_n,
                                                c_ref,
                                                c_usr,
                                                k_ref_norm,
                                                k_usr_norm,
                                                T1,
                                                T2,
                                                max_shift_eff,
                                                best_shift,
                                            )

                                            aligned_cos_raw = _metrics["aligned_cos_raw"]
                                            aligned_cos = _metrics["aligned_cos"]
                                            valid_mask = _metrics["valid_mask"]
                                            w = _metrics["w"]
                                            valid_count = _metrics["valid_count"]
                                            valid_ratio = _metrics["valid_ratio"]
                                            invalid_ratio = _metrics["invalid_ratio"]
                                            unique_user_frames = _metrics["unique_user_frames"]
                                            unique_ratio = _metrics["unique_ratio"]
                                            collapse_ratio = _metrics["collapse_ratio"]
                                            mono_viol = _metrics["mono_viol"]
                                            near0_run = _metrics["near0_run"]
                                            dtw_dist_mean = _metrics["dtw_dist_mean"]
                                            dtw_dist_robust = _metrics["dtw_dist_robust"]
                                            robust_mode = _metrics["robust_mode"]
                                            dtw_dist_weighted_mean = _metrics["dtw_dist_weighted_mean"]
                                            dtw_dist_combo = _metrics["dtw_dist_combo"]
                                            base_score = _metrics["base_score"]
                                            pen = _metrics["pen"]
                                            pen_dbg = _metrics["pen_dbg"]
                                            overall_score = _metrics["overall_score"]
                                            cosine_valid_mean = _metrics["cosine_valid_mean"]
                                            cosine_valid_min = _metrics["cosine_valid_min"]
                                            cosine_valid_p10 = _metrics["cosine_valid_p10"]
                                            cosine_valid_p50 = _metrics["cosine_valid_p50"]
                                            trusted_count = _metrics["trusted_count"]
                                            cosine_trusted_p10 = _metrics["cosine_trusted_p10"]
                                            p10_guard_factor = _metrics["p10_guard_factor"]
                                            p10_guard_val = _metrics["p10_guard_val"]
                                            wrongness_limb_timeline = _metrics["wrongness_limb_timeline"]
                                            wrongness = _metrics["wrongness"]
                                            wrong_scale = _metrics["wrong_scale"]
                                            lowconf_run = _metrics["lowconf_run"]
                                            effective_trusted_ratio = _metrics["effective_trusted_ratio"]
                            except Exception:
                                refined_used = False
                        else:
                            mean_sim, per_win, extra = _aligned_window_similarity(Zr, Zu, align_ref_to_user, T1, T2)
                    else:
                        mean_sim, per_win, extra = _aligned_window_similarity(Zr, Zu, align_ref_to_user, T1, T2)
                except Exception:
                    # fallback to frame-based alignment
                    mean_sim, per_win, extra = _aligned_window_similarity(Zr, Zu, align_ref_to_user, T1, T2)
            else:
                mean_sim, per_win, extra = _aligned_window_similarity(Zr, Zu, align_ref_to_user, T1, T2)
            agg_sim_raw, agg_dbg = _aggregate_strict(per_win)
            agg_sim_cal = _calibrate_stgcn_cosine(agg_sim_raw)

            mm = _motion_mismatch(k_ref_raw, k_usr_raw, align_ref_to_user)
            stgcn_sim_0_1 = float(np.clip(agg_sim_cal * (1.0 - MOTION_W * mm), 0.0, 1.0))

            stgcn_window_scores = per_win.tolist()
            stgcn_window_centers_ref = _window_centers(T1).tolist()

            # prepare ST-GCN quality info (used by gating below)
            stgcn_quality = {
                "conf_thr": float(STGCN_CONF_THR),
                "ref_windows": int(getattr(Zr, "shape", [0])[0]),
                "usr_windows": int(getattr(Zu, "shape", [0])[0]),
                "ref_nan_rows": int(np.sum(~np.isfinite(np.asarray(Zr)).all(axis=1))),
                "usr_nan_rows": int(np.sum(~np.isfinite(np.asarray(Zu)).all(axis=1))),
                "win_T": int(WIN_T),
                "stride": int(STRIDE),
            }

            # --- ST-GCN gating + window-based DTW wrongness smoothing (DTW remains authoritative)
            try:
                stgcn_gate_on = True
                # initial quick quality checks
                rq = int(stgcn_quality.get("ref_windows", 0)) if isinstance(stgcn_quality, dict) else 0
                uq = int(stgcn_quality.get("usr_windows", 0)) if isinstance(stgcn_quality, dict) else 0
                rn = int(stgcn_quality.get("ref_nan_rows", 0)) if isinstance(stgcn_quality, dict) else 0
                un = int(stgcn_quality.get("usr_nan_rows", 0)) if isinstance(stgcn_quality, dict) else 0

                # gate off if sim low or quality poor (too few windows or many NaN rows)
                if stgcn_sim_0_1 is None or not np.isfinite(stgcn_sim_0_1) or stgcn_sim_0_1 < float(STGCN_USE_THR):
                    stgcn_gate_on = False
                if rq <= 0 or uq <= 0:
                    stgcn_gate_on = False
                if rn >= max(1, int(0.5 * rq)) or un >= max(1, int(0.5 * uq)):
                    stgcn_gate_on = False
            except Exception:
                stgcn_gate_on = False

            # If gated ON, compute a per-frame multiplier from window scores (range [0.85,1.15])
            # High ST-GCN score -> reduce DTW wrongness a bit (forgive noise). Low score -> keep/boost wrongness.
            STGCN_MULT_MIN = 0.85
            STGCN_MULT_MAX = 1.15
            if stgcn_gate_on and len(stgcn_window_scores) and len(stgcn_window_centers_ref):
                mult_sum = np.zeros((T1,), dtype=np.float32)
                mult_cnt = np.zeros((T1,), dtype=np.float32)
                half = WIN_T // 2
                for wi, ws in enumerate(stgcn_window_scores):
                    try:
                        score = float(np.clip(ws, 0.0, 1.0))
                    except Exception:
                        score = 0.0
                    m = float(STGCN_MULT_MAX - score * (STGCN_MULT_MAX - STGCN_MULT_MIN))
                    cref = int(stgcn_window_centers_ref[wi]) if wi < len(stgcn_window_centers_ref) else None
                    if cref is None:
                        continue
                    lo = max(0, cref - half)
                    hi = min(T1, cref + half + 1)
                    mult_sum[lo:hi] += m
                    mult_cnt[lo:hi] += 1.0

                mult = np.ones((T1,), dtype=np.float32)
                mask = mult_cnt > 0
                mult[mask] = (mult_sum[mask] / mult_cnt[mask]).astype(np.float32)

                # apply multiplier to DTW wrongness (per-limb timelines) produced earlier by helper
                try:
                    for limb in wrongness.keys():
                        arr = np.asarray(wrongness[limb], dtype=np.float32)
                        arr = arr * mult
                        wrongness[limb] = arr
                        wrongness_limb_timeline[limb] = arr.tolist()
                    # also scale wrong_scale if present
                    try:
                        wrong_scale = (np.asarray(wrong_scale, np.float32) * mult).astype(np.float32)
                    except Exception:
                        pass
                except Exception:
                    # on any failure, revert to DTW-only (do not allow ST-GCN to change limb choices)
                    pass
            else:
                # ST-GCN gated off: ensure no ST-GCN influence on colors
                pass
            stgcn_scores_extra = {
                "mean_win_sim": float(mean_sim),
                "low_p": int(STGCN_LOW_P),
                "low_p_sim": float(agg_dbg["low_p"]),
                "mean_sim": float(agg_dbg["mean"]),
                "agg_sim_raw": float(agg_sim_raw),
                "agg_sim_calibrated": float(agg_sim_cal),
                "motion_mismatch": float(mm),
                "paired_windows": int(extra.get("paired_windows", 0)),
                "mode": str(extra.get("mode", "unknown")),
            }

            ZrN = _l2_rows(Zr)
            ZuN = _l2_rows(Zu)
            C = _nan0(ZrN @ ZuN.T)
            cosine_raw_mat_mean = float(np.mean(C)) if C.size else 0.0
            cosine_raw_mat_mean = float(_nan0(cosine_raw_mat_mean))

            mr = _nan0(np.mean(_nan0(Zr), axis=0).astype(np.float32))
            mu = _nan0(np.mean(_nan0(Zu), axis=0).astype(np.float32))
            dist = float(np.linalg.norm(_nan0(mr - mu)))
            dist = float(np.nan_to_num(dist, nan=0.0, posinf=0.0, neginf=0.0))

            stgcn_debug = {
                "cosine_raw_matrix_mean": cosine_raw_mat_mean,
                "cosine_raw": cosine_raw_mat_mean,
                "dist": dist,
                "mode": extra.get("mode", "unknown"),
                "paired_windows": int(extra.get("paired_windows", 0)),
                "mean_win_sim": float(mean_sim),
                "low_p_sim": float(agg_dbg["low_p"]),
                "mean_sim": float(agg_dbg["mean"]),
                "agg_sim_raw": float(agg_sim_raw),
                "calibration_p50": float(STGCN_CAL_P50),
                "calibration_p99": float(STGCN_CAL_P99),
                "agg_sim_calibrated": float(agg_sim_cal),
                "motion_mismatch": float(mm),
                "num_ref_windows": int(getattr(Zr, "shape", [0])[0]),
                "num_usr_windows": int(getattr(Zu, "shape", [0])[0]),
                "ref_nan_rows": int(np.sum(~np.isfinite(np.asarray(Zr)).all(axis=1))),
                "usr_nan_rows": int(np.sum(~np.isfinite(np.asarray(Zu)).all(axis=1))),
            }

    # ---- fuse
    if stgcn_sim_0_1 is None:
        final_score = float(overall_score)
    else:
        # Normalize fusion weights so final score scale remains 0..100
        wsum = float(DTW_W + STGCN_W)
        if wsum <= 0:
            final_score = float(overall_score)
        else:
            fused = float(DTW_W * overall_score + STGCN_W * (stgcn_sim_0_1 * 100.0))
            final_score = float(np.clip(fused / wsum, 0.0, 100.0))

    # ---- apply temporal smoothing to wrongness timelines (stabilize colors)
    try:
        smooth_win = int(getattr(Config, "WRONGNESS_SMOOTH_WINDOW", 5))
    except Exception:
        smooth_win = 5

    wrongness_limb_timeline_raw = {limb: np.asarray(arr, dtype=np.float32).copy().tolist() for limb, arr in wrongness.items()}
    if smooth_win is None:
        smooth_win = 1
    smooth_win = max(1, int(smooth_win))
    wrongness_smoothed_flag = False
    if smooth_win > 1 and isinstance(wrongness, dict):
        try:
            for limb in list(wrongness.keys()):
                arr = np.asarray(wrongness[limb], dtype=np.float32)
                if arr.size <= 1:
                    sm = arr.copy()
                else:
                    sm = _temporal_smooth_1d(arr, win=smooth_win)
                wrongness[limb] = sm.astype(np.float32)
                wrongness_limb_timeline[limb] = sm.tolist()

            try:
                if wrong_scale is not None and len(wrong_scale) > 0:
                    ws = np.asarray(wrong_scale, dtype=np.float32)
                    wrong_scale = _temporal_smooth_1d(ws, win=smooth_win).astype(np.float32)
            except Exception:
                pass

            wrongness_smoothed_flag = True
        except Exception:
            wrongness_smoothed_flag = False

    # ---- DTW debug
    # final alignment mode and output shift
    final_alignment_mode = "refined_dtw" if refined_used else "coarse_shift"
    out_shift = 0 if refined_used else int(best_shift)

    dtw_debug = {
        "T_ref": int(T1),
        "T_usr": int(T2),
        "max_shift": int(max_shift_eff),

        "best_shift_frames": int(best_shift),
        "best_shift_active_mean": float(best_mean),

        "align_valid_count": int(valid_count),
        "align_valid_ratio": float(valid_ratio),
        "align_invalid_ratio": float(invalid_ratio),

        "align_unique_user_frames": int(unique_user_frames),
        "align_unique_ratio": float(unique_ratio),
        "align_collapse_ratio": float(collapse_ratio),

        "align_monotonicity_violations": int(mono_viol),
        "align_neg_count": int(np.sum(np.asarray(align_ref_to_user, np.int32) < 0)),

        "cosine_valid_mean": float(cosine_valid_mean),
        "cosine_valid_min": float(cosine_valid_min),
        "cosine_valid_p10": float(cosine_valid_p10),
        "cosine_trusted_p10": float(cosine_trusted_p10),
        "cosine_valid_p50": float(cosine_valid_p50),
        "cosine_near0_longest_run": int(near0_run),

        "dtw_dist_mean": float(dtw_dist_mean),
        "dtw_dist_robust": float(dtw_dist_robust),
        "dtw_robust_mode": str(robust_mode),
        "dtw_dist_weighted_mean": float(dtw_dist_weighted_mean),
        "dtw_dist_combo": float(dtw_dist_combo),

        "dtw_beta": float(DTW_BETA),
        "dtw_mean_w": float(DTW_MEAN_W),
        "dtw_robust_p": int(DTW_ROBUST_P),
        "dtw_robust_w": float(DTW_ROBUST_W),

        "dtw_score_from_combo_dist": float(base_score),
        "dtw_penalty": pen_dbg,
        "dtw_score_after_penalty": float(base_score * pen),

        "p10_guard_thr": float(DTW_P10_GUARD_THR),
        "p10_guard_power": float(DTW_P10_GUARD_POWER),
        "p10_guard_factor": float(p10_guard_factor),
        "p10_guard_used_value": float(p10_guard_val),
        "p10_guard_floor": float(DTW_P10_GUARD_MIN_FACTOR),
        "p10_guard_min_trusted_frames": int(DTW_P10_MIN_TRUSTED_FRAMES),
        "trusted_count": int(trusted_count),

        "dtw_score_final": float(overall_score),
        "dtw_refinement": dtw_ref_dbg,
        "embed_used": bool(getattr(Config, "EMBED_DTW_ENABLED", False)) and (float(overall_score) < float(getattr(Config, "EMBED_DTW_THRESHOLD", 60.0))),
        "stgcn_used_overlap": bool(locals().get('stgcn_used_overlap', False)),
        "remapped_centers_count": int(locals().get('remapped', 0)),
        "refined_dtw_used": bool(locals().get('refined_used', False)),
        "refined_valid_ratio": None if locals().get('refined_valid_ratio', None) is None else float(locals().get('refined_valid_ratio')),
        "refined_unique_ratio": None if locals().get('refined_unique_ratio', None) is None else float(locals().get('refined_unique_ratio')),
        "refined_collapse_ratio": None if locals().get('refined_collapse_ratio', None) is None else float(locals().get('refined_collapse_ratio')),
        "bandwidth_frames_report": int(getattr(Config, "DTW_BANDWIDTH", 0)) if int(getattr(Config, "DTW_BANDWIDTH", 0)) > 0 else int(max(10, int(0.12 * max(T1, T2)))),
        "overlap_ref_start": int(overlap_ref_start),
        "overlap_ref_end": int(overlap_ref_end),
        "overlap_usr_start": int(overlap_usr_start),
        "overlap_usr_end": int(overlap_usr_end),

        "frame_conf_low": float(DTW_FRAME_CONF_LOW),
        "frame_conf_high": float(DTW_FRAME_CONF_HIGH),
        "frame_conf_pow": float(DTW_FRAME_CONF_POW),
        "lowconf_longest_run": int(lowconf_run),
        "effective_trusted_ratio": float(effective_trusted_ratio),
    }

    # expose final alignment mode
    dtw_debug["final_alignment_mode"] = str(final_alignment_mode)
    dtw_debug["final_shift_frames"] = int(best_shift)
    dtw_debug["out_shift_frames"] = int(out_shift)
    # smoothing diagnostics
    dtw_debug["wrongness_smoothed"] = bool(wrongness_smoothed_flag)
    dtw_debug["wrongness_smooth_window"] = int(smooth_win)

    return {
        "overall_score_0_100": float(overall_score),
        "final_score_0_100": float(final_score),
        "shift_frames": int(out_shift),
        "auto_sync": {"shift_frames": int(out_shift)},
        "align_ref_to_user": [int(x) for x in align_ref_to_user],

        "wrongness_limb_timeline": wrongness_limb_timeline,
        "aligned_timeline_cosine": aligned_cos[:2000].tolist(),
        "aligned_timeline_cosine_raw": aligned_cos_raw[:2000].tolist(),
        "aligned_timeline_weight": w[:2000].tolist(),

        "dtw_debug": dtw_debug,

        "stgcn_embedding": {
            "enabled": stgcn_sim_0_1 is not None,
            "sim_0_1": stgcn_sim_0_1,
            "error": stgcn_err if stgcn_sim_0_1 is None else None,
            "debug": stgcn_debug,

            "window_scores": stgcn_window_scores,
            "window_centers_ref": stgcn_window_centers_ref,

            "scores": stgcn_scores_extra if stgcn_sim_0_1 is not None else None,
            "quality": stgcn_quality if stgcn_sim_0_1 is not None else None,

            "limb_similarity": {
                "left_arm": None,
                "right_arm": None,
                "left_leg": None,
                "right_leg": None,
                "torso": None,
            },
        },
    }
