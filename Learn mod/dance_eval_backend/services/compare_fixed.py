# services/compare.py
import numpy as np
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
# DTW SCORE SHAPE (mean-dist based)
# =========================
# dist_mean ~ 0.00 -> 100
# dist_mean ~ 0.10 -> ~75-85
# dist_mean ~ 0.20 -> ~55-70
# dist_mean ~ 0.35 -> ~35-50
DTW_BETA = 6.5  # higher => stricter (for mean distance)

# Robust mix: mean + p90 (punish bad segments)
DTW_MEAN_W = 0.65
DTW_ROBUST_P = 90
DTW_ROBUST_W = 0.35  # DTW_MEAN_W + DTW_ROBUST_W should be 1.0

# Final fusion weights
DTW_W = 0.76
STGCN_W = 0.24

# =========================
# DTW RELIABILITY PENALTIES (IMPORTANT)
# =========================
# If alignment is suspicious, DTW must drop.
DTW_MIN_VALID_RATIO = 0.90          # < 0.90 => penalty (safer than 0.95)
DTW_VALID_RATIO_POWER = 2.0

DTW_SHIFT_SUSPICIOUS_FRAC = 0.85    # if |shift| > 0.85*max_shift => penalty
DTW_SHIFT_POWER = 2.0

DTW_COLLAPSE_OK = 0.08              # collapse above this starts penalty
DTW_COLLAPSE_POWER = 2.0

DTW_MIN_UNIQUE_RATIO = 0.90         # < 0.90 => penalty
DTW_UNIQUE_RATIO_POWER = 2.0

# Extra anti-fake-high guard (worst 10% frames must not be terrible)
DTW_P10_GUARD_THR = 0.75
DTW_P10_GUARD_POWER = 2.0

# Frame-confidence (pose) trust in DTW scoring
DTW_FRAME_CONF_LOW = 0.10
DTW_FRAME_CONF_HIGH = 0.30
DTW_FRAME_CONF_POW = 1.0

# alignment DTW downsample cap
DTW_MAX_POINTS = 1200

# =========================
# ST-GCN STRICTNESS
# =========================
STGCN_LOW_P = 10          # percentile to use (10..30)
STGCN_LOW_P_W = 0.80      # weight on percentile
STGCN_MEAN_W = 0.20

MOTION_W = 0.42
MOTION_EPS = 1e-6
STGCN_CONF_THR = 0.20

# ST-GCN CALIBRATION
STGCN_CAL_P50 = 0.340832382440567
STGCN_CAL_P99 = 0.9059241414070129
STGCN_CAL_EPS = 1e-9


# =========================
# utils
# =========================
def _nan0(x):
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

def _safe_norm(x, axis=None, keepdims=False, eps=1e-6):
    return np.sqrt(np.sum(x * x, axis=axis, keepdims=keepdims) + eps)

def _clamp01(x: float) -> float:
    return float(np.clip(float(x), 0.0, 1.0))

def _score_from_dtw_mean(dist_mean: float) -> float:
    s = 100.0 * np.exp(-DTW_BETA * float(dist_mean))
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

def _dtw_align_map(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """
    DTW mapping ref index -> user index (for downsampled sequences).
    O(N*M) but we downsample by DTW_MAX_POINTS cap.
    """
    N, _ = X.shape
    M, _ = Y.shape

    INF = 1e15
    dp = np.full((N + 1, M + 1), INF, dtype=np.float64)
    ptr = np.zeros((N, M), dtype=np.int8)
    dp[0, 0] = 0.0

    for i in range(1, N + 1):
        xi = X[i - 1]
        for j in range(1, M + 1):
            cost = float(np.linalg.norm(xi - Y[j - 1]))
            a = dp[i - 1, j - 1]
            b = dp[i - 1, j]
            c = dp[i, j - 1]
            if a <= b and a <= c:
                dp[i, j] = cost + a
                ptr[i - 1, j - 1] = 0
            elif b <= c:
                dp[i, j] = cost + b
                ptr[i - 1, j - 1] = 1
            else:
                dp[i, j] = cost + c
                ptr[i - 1, j - 1] = 2

    # backtrack
    i, j = N - 1, M - 1
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

    # NOTE: use -1 sentinel (0 is a valid index) to avoid accidental "fill"
    ref_to_usr = np.full((N,), -1, dtype=np.int32)
    for ii, jj in path:
        ref_to_usr[ii] = int(jj)

    # forward-fill gaps with previous valid mapping
    for ii in range(1, N):
        if ref_to_usr[ii] < 0:
            ref_to_usr[ii] = ref_to_usr[ii - 1]

    # if still missing (e.g., empty path), clamp safely to 0
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
    centers = []
    if T < WIN_T:
        return np.array([], dtype=np.int32)
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
    """
    STRICT window matching (aligned).
    """
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
        if cref < 0 or cref >= len(align_ref_to_user):
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

    mean_sim = float(np.mean(per_win)) if per_win.size else 0.0
    return mean_sim, per_win.astype(np.float32), {"mode": "aligned_windows", "paired_windows": int(paired)}

def _aggregate_strict(per_win: np.ndarray) -> Tuple[float, Dict]:
    if per_win.size == 0:
        return 0.0, {"low_p": 0.0, "mean": 0.0}
    p = float(np.percentile(per_win, STGCN_LOW_P))
    m = float(np.mean(per_win))
    s = STGCN_MEAN_W * m + STGCN_LOW_P_W * p
    return float(np.clip(s, 0.0, 1.0)), {"low_p": p, "mean": m}

def _motion_mismatch(k_ref: np.ndarray, k_usr: np.ndarray, align_ref_to_user: List[int]) -> float:
    """
    Motion mismatch based on average joint speed around window centers.
    Returns value in [0..1] (higher = more mismatch).
    """
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

    Er = []
    Eu = []
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
    """
    Confidence weight per ref frame based on mean joint conf in ref+mapped user.
    Returns weights in [0..1].
    """
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
    """
    Multiply DTW score by a penalty in [0..1] based on alignment reliability.
    """
    dbg = {}

    # coverage penalty
    vr = float(np.clip(valid_ratio, 0.0, 1.0))
    if vr >= DTW_MIN_VALID_RATIO:
        p_valid = 1.0
    else:
        p_valid = (vr / max(1e-6, DTW_MIN_VALID_RATIO)) ** DTW_VALID_RATIO_POWER
    p_valid = _clamp01(p_valid)
    dbg["p_valid"] = p_valid

    # unique mapping penalty
    ur = float(np.clip(unique_ratio, 0.0, 1.0))
    if ur >= DTW_MIN_UNIQUE_RATIO:
        p_unique = 1.0
    else:
        p_unique = (ur / max(1e-6, DTW_MIN_UNIQUE_RATIO)) ** DTW_UNIQUE_RATIO_POWER
    p_unique = _clamp01(p_unique)
    dbg["p_unique"] = p_unique

    # collapse penalty
    cr = float(np.clip(collapse_ratio, 0.0, 1.0))
    if cr <= DTW_COLLAPSE_OK:
        p_collapse = 1.0
    else:
        x = 1.0 - (cr - DTW_COLLAPSE_OK) / max(1e-6, (1.0 - DTW_COLLAPSE_OK))
        p_collapse = x ** DTW_COLLAPSE_POWER
    p_collapse = _clamp01(p_collapse)
    dbg["p_collapse"] = p_collapse

    # suspicious shift penalty
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


# =========================
# main
# =========================
def compare_sequences(
    k_ref_norm: np.ndarray,
    c_ref: np.ndarray,
    k_usr_norm: np.ndarray,
    c_usr: np.ndarray,
    max_shift: int = 90,
    k_ref_raw: Optional[np.ndarray] = None,
    k_usr_raw: Optional[np.ndarray] = None,
):
    k_ref_norm = np.asarray(k_ref_norm, np.float32)
    k_usr_norm = np.asarray(k_usr_norm, np.float32)
    c_ref = np.asarray(c_ref, np.float32)
    c_usr = np.asarray(c_usr, np.float32)

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

    # ---- alignment (on normalized)
    f_ref = _frame_features(k_ref_norm)
    f_usr = _frame_features(k_usr_norm)
    f_ref_n = f_ref / np.maximum(_safe_norm(f_ref, axis=1, keepdims=True), 1e-6)
    f_usr_n = f_usr / np.maximum(_safe_norm(f_usr, axis=1, keepdims=True), 1e-6)

    # coarse shift search (overlap only)
    best_shift = 0
    best_mean = -1e9

    max_shift_eff = int(max(0, min(int(max_shift), max(T1, T2))))
    for s in range(-max_shift_eff, max_shift_eff + 1):
        if s >= 0:
            t0 = 0
            t1 = min(T1, T2 - s)
        else:
            t0 = -s
            t1 = min(T1, T2)
        if t1 - t0 < 12:
            continue
        a = f_ref_n[t0:t1]
        b = f_usr_n[t0 + s:t1 + s]
        m = float(np.mean(np.sum(a * b, axis=1)))
        if m > best_mean:
            best_mean = m
            best_shift = s

    align_ref_to_user = []
    for t in range(T1):
        u = t + best_shift
        align_ref_to_user.append(int(u) if 0 <= u < T2 else -1)

    # DTW refinement (downsampled, allows tempo differences: ref_win and usr_win can have different lengths)
    # We still score ONLY on reference frames (T1). User can be longer/shorter; extra user frames are ignored.
    if best_shift >= 0:
        ref_offset = 0
        ref_win = f_ref[0:T1]
        usr_offset = best_shift
        usr_win = f_usr[best_shift:T2]
    else:
        s = -best_shift
        ref_offset = s
        ref_win = f_ref[s:T1]
        usr_offset = 0
        usr_win = f_usr[0:T2]

    dtw_ref_dbg = {"used": False}
    if len(ref_win) >= 12 and len(usr_win) >= 12:
        # cap compute: downsample both sequences based on the larger length
        step = max(1, int(np.ceil(max(len(ref_win), len(usr_win)) / DTW_MAX_POINTS)))
        map_small = _dtw_align_map(ref_win[::step], usr_win[::step])
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

    # cosine timeline + valid mask
    # IMPORTANT: raw cosine in [-1..1] can be negative due to axis sign flips / mirroring.
    # Map to [0..1] to avoid "p10=0 -> score=0" blowups for otherwise good alignments.
    aligned_cos_raw = np.zeros((T1,), dtype=np.float32)
    aligned_cos = np.zeros((T1,), dtype=np.float32)
    valid_mask = np.zeros((T1,), dtype=np.bool_)
    for t in range(T1):
        u = align_ref_to_user[t]
        if u is None or u < 0 or u >= T2:
            aligned_cos_raw[t] = 0.0
            aligned_cos[t] = 0.0
            valid_mask[t] = False
        else:
            raw = float(np.clip(np.dot(f_ref_n[t], f_usr_n[u]), -1.0, 1.0))
            aligned_cos_raw[t] = raw
            aligned_cos[t] = float(np.clip(0.5 * (raw + 1.0), 0.0, 1.0))
            valid_mask[t] = True

    valid_count = int(np.sum(valid_mask))
    valid_ratio = float(valid_count) / float(max(1, T1))
    invalid_ratio = 1.0 - valid_ratio

    # collapse / unique stats
    valid_us = [align_ref_to_user[t] for t in range(T1) if valid_mask[t]]
    unique_user_frames = len(set(valid_us)) if valid_us else 0
    unique_ratio = float(unique_user_frames) / float(max(1, valid_count))
    collapse_ratio = float(1.0 - unique_ratio)

    # monotonicity violations (should be 0)
    mono_viol = 0
    last_u = -1
    for t in range(T1):
        u = align_ref_to_user[t]
        if u is None or u < 0:
            continue
        if last_u >= 0 and u < last_u:
            mono_viol += 1
        last_u = u

    # confidence weight per frame
    w = _frame_confidence(c_ref, c_usr, align_ref_to_user)  # [0..1]
    w = w * valid_mask.astype(np.float32)

    # longest low-confidence run
    lowconf_run = 0
    cur = 0
    for t in range(T1):
        if w[t] <= 1e-6:
            cur += 1
            lowconf_run = max(lowconf_run, cur)
        else:
            cur = 0

    effective_trusted_ratio = float(np.mean(w > 0.5)) if T1 > 0 else 0.0

    # DTW distances on valid frames
    if valid_count > 0:
        dist_per = (1.0 - aligned_cos[valid_mask]).astype(np.float32)
        dtw_dist_mean = float(np.mean(dist_per))
        dtw_dist_robust = float(np.percentile(dist_per, DTW_ROBUST_P))

        cosine_valid = aligned_cos[valid_mask].astype(np.float32)
        cosine_valid_mean = float(np.mean(cosine_valid))
        cosine_valid_min = float(np.min(cosine_valid))
        cosine_valid_p10 = float(np.percentile(cosine_valid, 10))
        cosine_valid_p50 = float(np.percentile(cosine_valid, 50))

        # trusted subset (avoid nuking score due to low-confidence frames)
        trusted_mask = valid_mask & (w > 0.5)
        trusted_count = int(np.sum(trusted_mask))
        if trusted_count > 0:
            cosine_trusted = aligned_cos[trusted_mask].astype(np.float32)
            cosine_trusted_p10 = float(np.percentile(cosine_trusted, 10))
        else:
            cosine_trusted_p10 = float(cosine_valid_p10)
    else:
        dtw_dist_mean = 1.0
        dtw_dist_robust = 1.0
        cosine_valid_mean = 0.0
        cosine_valid_min = 0.0
        cosine_valid_p10 = 0.0
        cosine_valid_p50 = 0.0
        cosine_trusted_p10 = 0.0

    # confidence-weighted mean distance
    if valid_count > 0:
        dist_all = (1.0 - aligned_cos).astype(np.float32)
        num = float(np.sum(dist_all * w))
        den = float(np.sum(w) + 1e-9)
        dtw_dist_weighted_mean = num / den
    else:
        dtw_dist_weighted_mean = 1.0

    # near0 cosine longest run (valid only)
    near0_run = 0
    cur = 0
    for t in range(T1):
        if valid_mask[t] and aligned_cos[t] <= 1e-6:
            cur += 1
            near0_run = max(near0_run, cur)
        else:
            cur = 0

    # base dist combines mean + robust tail (prevents "lucky segment match")
    dtw_dist_combo = DTW_MEAN_W * dtw_dist_weighted_mean + DTW_ROBUST_W * dtw_dist_robust
    base_score = _score_from_dtw_mean(dtw_dist_combo)

    # reliability penalty
    pen, pen_dbg = _reliability_penalty(
        valid_ratio=valid_ratio,
        unique_ratio=unique_ratio,
        collapse_ratio=collapse_ratio,
        best_shift=int(best_shift),
        max_shift=int(max_shift_eff),
    )
    overall_score = float(np.clip(base_score * pen, 0.0, 100.0))

    # EXTRA GUARD (soft): apply on TRUSTED frames only (w > 0.5), otherwise it can zero-out good alignments.
    p10_guard_factor = 1.0
    p10_guard_val = float(cosine_trusted_p10)
    if p10_guard_val < DTW_P10_GUARD_THR:
        p10_guard_factor = float((p10_guard_val / max(1e-6, DTW_P10_GUARD_THR)) ** DTW_P10_GUARD_POWER)
        p10_guard_factor = float(np.clip(p10_guard_factor, 0.0, 1.0))
        overall_score = float(np.clip(overall_score * p10_guard_factor, 0.0, 100.0))

    # limb wrongness (for coloring)
    ref_to_usr_arr = np.array([max(0, u) if u >= 0 else 0 for u in align_ref_to_user], dtype=np.int32)
    wrongness = _limb_wrongness(k_ref_norm, k_usr_norm, ref_to_usr_arr)

    # scale wrongness by confidence (so low-conf frames don't blame user)
    wrong_scale = w.astype(np.float32)  # 0..1
    for limb in wrongness.keys():
        wrongness[limb] = wrongness[limb] * wrong_scale
    wrongness_limb_timeline = {limb: arr.tolist() for limb, arr in wrongness.items()}

    # ---- ST-GCN on RAW
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

    ckpt_path = getattr(Config, "STGCN_CKPT", None) or getattr(Config, "STGCN_CKPT_PATH", None)
    if not ckpt_path:
        stgcn_err = "ST-GCN checkpoint path not set in Config (STGCN_CKPT)"
    else:
        Zr, er = stgcn_embed_sequence_windows(k_ref_raw, c_ref, ckpt_path=ckpt_path, conf_thr=STGCN_CONF_THR)
        Zu, eu = stgcn_embed_sequence_windows(k_usr_raw, c_usr, ckpt_path=ckpt_path, conf_thr=STGCN_CONF_THR)

        if Zr is None or Zu is None:
            stgcn_err = er or eu or "ST-GCN disabled"
        else:
            mean_sim, per_win, extra = _aligned_window_similarity(Zr, Zu, align_ref_to_user, T1, T2)
            agg_sim_raw, agg_dbg = _aggregate_strict(per_win)  # raw [0..1]
            agg_sim_cal = _calibrate_stgcn_cosine(agg_sim_raw)

            mm = _motion_mismatch(k_ref_raw, k_usr_raw, align_ref_to_user)
            stgcn_sim_0_1 = float(np.clip(agg_sim_cal * (1.0 - MOTION_W * mm), 0.0, 1.0))

            stgcn_window_scores = per_win.tolist()
            stgcn_window_centers_ref = _window_centers(T1).tolist()

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

            stgcn_quality = {
                "conf_thr": float(STGCN_CONF_THR),
                "ref_windows": int(getattr(Zr, "shape", [0])[0]),
                "usr_windows": int(getattr(Zu, "shape", [0])[0]),
                "ref_nan_rows": int(np.sum(~np.isfinite(np.asarray(Zr)).all(axis=1))),
                "usr_nan_rows": int(np.sum(~np.isfinite(np.asarray(Zu)).all(axis=1))),
                "win_T": int(WIN_T),
                "stride": int(STRIDE),
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
        final_score = float(DTW_W * overall_score + STGCN_W * (stgcn_sim_0_1 * 100.0))

    # DTW debug block (rich)
    dtw_debug = {
        "T_ref": int(T1),
        "T_usr": int(T2),
        "max_shift": int(max_shift_eff),

        "dtw_beta": float(DTW_BETA),
        "dtw_mean_w": float(DTW_MEAN_W),
        "dtw_robust_p": int(DTW_ROBUST_P),
        "dtw_robust_w": float(DTW_ROBUST_W),

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
        "dtw_dist_weighted_mean": float(dtw_dist_weighted_mean),
        "dtw_dist_combo": float(dtw_dist_combo),

        "dtw_score_from_combo_dist": float(base_score),
        "dtw_penalty": pen_dbg,
        "dtw_score_after_penalty": float(base_score * pen),

        "p10_guard_thr": float(DTW_P10_GUARD_THR),
        "p10_guard_power": float(DTW_P10_GUARD_POWER),
        "p10_guard_factor": float(p10_guard_factor),
        "p10_guard_used_value": float(p10_guard_val),

        "dtw_score_final": float(overall_score),

        "dtw_refinement": dtw_ref_dbg,

        "frame_conf_low": float(DTW_FRAME_CONF_LOW),
        "frame_conf_high": float(DTW_FRAME_CONF_HIGH),
        "frame_conf_pow": float(DTW_FRAME_CONF_POW),
        "lowconf_longest_run": int(lowconf_run),
        "effective_trusted_ratio": float(effective_trusted_ratio),
    }

    return {
        "overall_score_0_100": float(overall_score),
        "final_score_0_100": float(final_score),
        "shift_frames": int(best_shift),
        "auto_sync": {"shift_frames": int(best_shift)},
        "align_ref_to_user": [int(x) for x in align_ref_to_user],

        # For frontend coloring/timeline
        "wrongness_limb_timeline": wrongness_limb_timeline,
        "aligned_timeline_cosine": aligned_cos[:2000].tolist(),
        "aligned_timeline_cosine_raw": aligned_cos_raw[:2000].tolist(),
        "aligned_timeline_weight": w[:2000].tolist(),

        # DTW debug
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
