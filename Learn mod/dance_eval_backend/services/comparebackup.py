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
# TUNING (STRICTNESS)
# =========================
DTW_BETA = 0.02  # increase (e.g. 0.03) to make DTW stricter

DTW_W = 0.60
STGCN_W = 0.40

STGCN_LOW_P = 20
STGCN_LOW_P_W = 0.55
STGCN_MEAN_W = 0.45

MOTION_W = 0.25
MOTION_EPS = 1e-6

STGCN_CONF_THR = 0.20


# =========================
# utils
# =========================
def _nan0(x):
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def _safe_norm(x, axis=None, keepdims=False, eps=1e-6):
    return np.sqrt(np.sum(x * x, axis=axis, keepdims=keepdims) + eps)


def _score_from_dtw(dist: float) -> float:
    s = 100.0 * np.exp(-DTW_BETA * float(dist))
    return float(np.clip(s, 0.0, 100.0))


def _frame_features(k: np.ndarray) -> np.ndarray:
    """
    Alignment features: hip-relative + shoulder-axis coordinates.
    k: (T,17,2)  ->  (T, 34)
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
    Simple DTW mapping ref index -> user index on downsampled sequences.
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

    ref_to_usr = np.zeros((N,), dtype=np.int32)
    for ii, jj in path:
        ref_to_usr[ii] = jj

    for ii in range(1, N):
        if ref_to_usr[ii] == 0:
            ref_to_usr[ii] = ref_to_usr[ii - 1]

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
    for start in range(0, T - WIN_T + 1, STRIDE):
        centers.append(start + WIN_T // 2)
    return np.array(centers, dtype=np.int32)


def _l2_rows(Z: np.ndarray) -> np.ndarray:
    Z = _nan0(np.asarray(Z, np.float32))
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
    STRICT window matching:
      ref window i matches user window near mapped frame (align_ref_to_user),
      NOT a global best match across entire sequence.
    """
    Zr = _l2_rows(Zr)
    Zu = _l2_rows(Zu)

    Cr = _window_centers(T1)
    Cu = _window_centers(T2)

    # shape guard
    if Zr.shape[0] != Cr.shape[0] or Zu.shape[0] != Cu.shape[0]:
        n = min(Zr.shape[0], Zu.shape[0])
        if n <= 0:
            return 0.0, np.zeros((0,), np.float32), {"mode": "fallback_empty"}
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
        if 0 <= j < len(Cu):
            candidates.append(j)
        if 0 <= j - 1 < len(Cu):
            candidates.append(j - 1)
        if 0 <= j + 1 < len(Cu):
            candidates.append(j + 1)

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
    sr = np.linalg.norm(vr, axis=2).mean(axis=1)  # (T1-1,)
    su = np.linalg.norm(vu, axis=2).mean(axis=1)  # (T2-1,)

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
            "stgcn_embedding": {
                "enabled": False,
                "sim_0_1": None,
                "error": "too few frames",
                "debug": None,
                "window_scores": [],
                "window_centers_ref": [],
            },
        }

    # ---- alignment (on normalized)
    f_ref = _frame_features(k_ref_norm)
    f_usr = _frame_features(k_usr_norm)
    f_ref_n = f_ref / np.maximum(_safe_norm(f_ref, axis=1, keepdims=True), 1e-6)
    f_usr_n = f_usr / np.maximum(_safe_norm(f_usr, axis=1, keepdims=True), 1e-6)

    best_shift = 0
    best_mean = -1e9
    for s in range(-max_shift, max_shift + 1):
        t0 = max(0, -s)
        t1 = min(T1, T2 - s) if s >= 0 else min(T1, T2 + s)
        if t1 - t0 < 8:
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

    # DTW refinement (downsampled)
    if best_shift >= 0:
        ref_win = f_ref[0: min(T1, T2 - best_shift)]
        usr_win = f_usr[best_shift: best_shift + len(ref_win)]
        ref_offset = 0
        usr_offset = best_shift
    else:
        s = -best_shift
        ref_win = f_ref[s: min(T1, T2 + s)]
        usr_win = f_usr[0: len(ref_win)]
        ref_offset = s
        usr_offset = 0

    if len(ref_win) >= 8 and len(usr_win) >= 8:
        step = max(1, int(np.ceil(len(ref_win) / 1200)))
        map_small = _dtw_align_map(ref_win[::step], usr_win[::step])
        map_full = np.minimum(map_small.repeat(step)[: len(ref_win)], len(usr_win) - 1)
        for i in range(len(ref_win)):
            rt = ref_offset + i
            ut = usr_offset + int(map_full[i])
            if 0 <= rt < T1:
                align_ref_to_user[rt] = ut

    # cosine timeline for DTW-like dist
    aligned_cos = np.zeros((T1,), dtype=np.float32)
    for t in range(T1):
        u = align_ref_to_user[t]
        if u is None or u < 0 or u >= T2:
            aligned_cos[t] = 0.0
        else:
            aligned_cos[t] = float(np.clip(np.dot(f_ref_n[t], f_usr_n[u]), 0.0, 1.0))

    valid = aligned_cos > 0
    dtw_dist = float(np.sum(1.0 - aligned_cos[valid])) if np.any(valid) else float(T1)
    overall_score = _score_from_dtw(dtw_dist)

    # limb wrongness
    ref_to_usr_arr = np.array([max(0, u) if u >= 0 else 0 for u in align_ref_to_user], dtype=np.int32)
    wrongness = _limb_wrongness(k_ref_norm, k_usr_norm, ref_to_usr_arr)
    wrongness_limb_timeline = {limb: arr.tolist() for limb, arr in wrongness.items()}

    # ---- ST-GCN on RAW
    if k_ref_raw is None:
        k_ref_raw = k_ref_norm
    if k_usr_raw is None:
        k_usr_raw = k_usr_norm

    stgcn_sim_0_1 = None
    stgcn_err = None
    stgcn_debug = None
    stgcn_window_scores = []
    stgcn_window_centers_ref = []

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
            agg_sim, agg_dbg = _aggregate_strict(per_win)

            mm = _motion_mismatch(k_ref_raw, k_usr_raw, align_ref_to_user)
            stgcn_sim_0_1 = float(np.clip(agg_sim * (1.0 - MOTION_W * mm), 0.0, 1.0))

            stgcn_window_scores = per_win.tolist()
            stgcn_window_centers_ref = _window_centers(T1).tolist()

            # =========================
            # ✅ DEBUG (BULLETPROOF: NEVER NaN)
            # =========================
            Zr2 = _nan0(np.asarray(Zr, np.float32))
            Zu2 = _nan0(np.asarray(Zu, np.float32))

            # cosine_raw (mean of similarity matrix)
            ZrN = _l2_rows(Zr2)
            ZuN = _l2_rows(Zu2)
            C = _nan0(ZrN @ ZuN.T)
            cosine_raw = float(np.mean(C)) if C.size else 0.0
            cosine_raw = float(_nan0(cosine_raw))

            # dist (l2 between mean vectors) - bulletproof
            mr = np.mean(Zr2, axis=0).astype(np.float32)
            mu = np.mean(Zu2, axis=0).astype(np.float32)

            mr = np.nan_to_num(mr, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            mu = np.nan_to_num(mu, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

            dvec = mr - mu
            dvec = np.nan_to_num(dvec, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

            dist = float(np.linalg.norm(dvec))
            dist = float(np.nan_to_num(dist, nan=0.0, posinf=0.0, neginf=0.0))

            stgcn_debug = {
                "cosine_raw": cosine_raw,
                "dist": dist,
                "mode": extra.get("mode", "unknown"),
                "paired_windows": int(extra.get("paired_windows", 0)),
                "mean_win_sim": float(mean_sim),
                "low_p_sim": float(agg_dbg["low_p"]),
                "mean_sim": float(agg_dbg["mean"]),
                "motion_mismatch": float(mm),
                "num_ref_windows": int(Zr.shape[0]),
                "num_usr_windows": int(Zu.shape[0]),
                "ref_nan_rows": int(np.sum(~np.isfinite(Zr).all(axis=1))),
                "usr_nan_rows": int(np.sum(~np.isfinite(Zu).all(axis=1))),
            }

    # ---- fuse
    if stgcn_sim_0_1 is None:
        final_score = float(overall_score)
    else:
        final_score = float(DTW_W * overall_score + STGCN_W * (stgcn_sim_0_1 * 100.0))

    return {
        "overall_score_0_100": float(overall_score),
        "final_score_0_100": float(final_score),
        "shift_frames": int(best_shift),
        "auto_sync": {"shift_frames": int(best_shift)},
        "align_ref_to_user": [int(x) for x in align_ref_to_user],
        "wrongness_limb_timeline": wrongness_limb_timeline,
        "aligned_timeline_cosine": aligned_cos[:2000].tolist(),
        "stgcn_embedding": {
            "enabled": stgcn_sim_0_1 is not None,
            "sim_0_1": stgcn_sim_0_1,
            "error": stgcn_err if stgcn_sim_0_1 is None else None,
            "debug": stgcn_debug,
            "window_scores": stgcn_window_scores,
            "window_centers_ref": stgcn_window_centers_ref,
        },
    }




#------------------------------------------------
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
# TUNING (STRICTNESS)
# =========================
DTW_BETA = 0.025  # stricter than 0.02; try 0.02..0.035

# Final fusion weights (ST-GCN matters more now)
DTW_W = 0.60
STGCN_W = 0.40

# ST-GCN strict aggregation: punish worst parts
STGCN_LOW_P = 20          # percentile to use (10..30)
STGCN_LOW_P_W = 0.60      # weight on percentile (punish bad parts)
STGCN_MEAN_W = 0.40       # weight on mean

# Motion mismatch penalty (speed/style mismatch)
MOTION_W = 0.30           # 0..0.5 (higher => stricter)
MOTION_EPS = 1e-6

# Confidence gating for ST-GCN windows
STGCN_CONF_THR = 0.20

# alignment DTW downsample cap
DTW_MAX_POINTS = 1200


# =========================
# utils
# =========================
def _nan0(x):
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

def _safe_norm(x, axis=None, keepdims=False, eps=1e-6):
    return np.sqrt(np.sum(x * x, axis=axis, keepdims=keepdims) + eps)

def _score_from_dtw(dist: float) -> float:
    s = 100.0 * np.exp(-DTW_BETA * float(dist))
    return float(np.clip(s, 0.0, 100.0))

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

    ref_to_usr = np.zeros((N,), dtype=np.int32)
    for ii, jj in path:
        ref_to_usr[ii] = jj

    # fill zeros with previous (except at start)
    for ii in range(1, N):
        if ref_to_usr[ii] == 0:
            ref_to_usr[ii] = ref_to_usr[ii - 1]

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
    STRICT window matching:
      each ref window must match the user window near the mapped frame,
      not globally anywhere in the sequence.
    """
    Zr = _l2_rows(Zr)
    Zu = _l2_rows(Zu)

    Cr = _window_centers(T1)
    Cu = _window_centers(T2)

    # shape guard / fallback
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

        # nearest user window center (plus small neighborhood)
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
    sr = np.linalg.norm(vr, axis=2).mean(axis=1)  # (T1-1,)
    su = np.linalg.norm(vu, axis=2).mean(axis=1)  # (T2-1,)

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
            "stgcn_embedding": {
                "enabled": False,
                "sim_0_1": None,
                "error": "too few frames",
                "debug": None,
                "window_scores": [],
                "window_centers_ref": [],
            },
        }

    # ---- alignment (on normalized)
    f_ref = _frame_features(k_ref_norm)
    f_usr = _frame_features(k_usr_norm)
    f_ref_n = f_ref / np.maximum(_safe_norm(f_ref, axis=1, keepdims=True), 1e-6)
    f_usr_n = f_usr / np.maximum(_safe_norm(f_usr, axis=1, keepdims=True), 1e-6)

    # coarse shift
    best_shift = 0
    best_mean = -1e9
    for s in range(-max_shift, max_shift + 1):
        t0 = max(0, -s)
        t1 = min(T1, T2 - s) if s >= 0 else min(T1, T2 + s)
        if t1 - t0 < 8:
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

    # DTW refinement (downsampled)
    if best_shift >= 0:
        ref_win = f_ref[0: min(T1, T2 - best_shift)]
        usr_win = f_usr[best_shift: best_shift + len(ref_win)]
        ref_offset = 0
        usr_offset = best_shift
    else:
        s = -best_shift
        ref_win = f_ref[s: min(T1, T2 + s)]
        usr_win = f_usr[0: len(ref_win)]
        ref_offset = s
        usr_offset = 0

    if len(ref_win) >= 8 and len(usr_win) >= 8:
        step = max(1, int(np.ceil(len(ref_win) / DTW_MAX_POINTS)))
        map_small = _dtw_align_map(ref_win[::step], usr_win[::step])
        map_full = np.minimum(map_small.repeat(step)[: len(ref_win)], len(usr_win) - 1)
        for i in range(len(ref_win)):
            rt = ref_offset + i
            ut = usr_offset + int(map_full[i])
            if 0 <= rt < T1:
                align_ref_to_user[rt] = ut

    # cosine timeline
    aligned_cos = np.zeros((T1,), dtype=np.float32)
    for t in range(T1):
        u = align_ref_to_user[t]
        if u is None or u < 0 or u >= T2:
            aligned_cos[t] = 0.0
        else:
            aligned_cos[t] = float(np.clip(np.dot(f_ref_n[t], f_usr_n[u]), 0.0, 1.0))

    valid = aligned_cos > 0
    dtw_dist = float(np.sum(1.0 - aligned_cos[valid])) if np.any(valid) else float(T1)
    overall_score = _score_from_dtw(dtw_dist)

    # limb wrongness (for coloring etc.)
    ref_to_usr_arr = np.array([max(0, u) if u >= 0 else 0 for u in align_ref_to_user], dtype=np.int32)
    wrongness = _limb_wrongness(k_ref_norm, k_usr_norm, ref_to_usr_arr)
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
            agg_sim, agg_dbg = _aggregate_strict(per_win)

            mm = _motion_mismatch(k_ref_raw, k_usr_raw, align_ref_to_user)
            stgcn_sim_0_1 = float(np.clip(agg_sim * (1.0 - MOTION_W * mm), 0.0, 1.0))

            stgcn_window_scores = per_win.tolist()
            stgcn_window_centers_ref = _window_centers(T1).tolist()

            # ---- debug (never NaN)
            ZrN = _l2_rows(Zr)
            ZuN = _l2_rows(Zu)
            C = _nan0(ZrN @ ZuN.T)
            cosine_raw = float(np.mean(C)) if C.size else 0.0
            cosine_raw = float(_nan0(cosine_raw))

            mr = _nan0(np.mean(_nan0(Zr), axis=0).astype(np.float32))
            mu = _nan0(np.mean(_nan0(Zu), axis=0).astype(np.float32))
            dist = float(np.linalg.norm(_nan0(mr - mu)))
            dist = float(np.nan_to_num(dist, nan=0.0, posinf=0.0, neginf=0.0))

            stgcn_debug = {
                "cosine_raw": cosine_raw,
                "dist": dist,
                "mode": extra.get("mode", "unknown"),
                "paired_windows": int(extra.get("paired_windows", 0)),
                "mean_win_sim": float(mean_sim),
                "low_p_sim": float(agg_dbg["low_p"]),
                "mean_sim": float(agg_dbg["mean"]),
                "motion_mismatch": float(mm),
                "num_ref_windows": int(getattr(Zr, "shape", [0])[0]),
                "num_usr_windows": int(getattr(Zu, "shape", [0])[0]),
                "ref_nan_rows": int(np.sum(~np.isfinite(Zr).all(axis=1))),
                "usr_nan_rows": int(np.sum(~np.isfinite(Zu).all(axis=1))),
            }

    # ---- fuse
    if stgcn_sim_0_1 is None:
        final_score = float(overall_score)
    else:
        final_score = float(DTW_W * overall_score + STGCN_W * (stgcn_sim_0_1 * 100.0))

    return {
        "overall_score_0_100": float(overall_score),
        "final_score_0_100": float(final_score),
        "shift_frames": int(best_shift),
        "auto_sync": {"shift_frames": int(best_shift)},
        "align_ref_to_user": [int(x) for x in align_ref_to_user],
        "wrongness_limb_timeline": wrongness_limb_timeline,
        "aligned_timeline_cosine": aligned_cos[:2000].tolist(),
        "stgcn_embedding": {
            "enabled": stgcn_sim_0_1 is not None,
            "sim_0_1": stgcn_sim_0_1,
            "error": stgcn_err if stgcn_sim_0_1 is None else None,
            "debug": stgcn_debug,
            "window_scores": stgcn_window_scores,
            "window_centers_ref": stgcn_window_centers_ref,
        },
    }
