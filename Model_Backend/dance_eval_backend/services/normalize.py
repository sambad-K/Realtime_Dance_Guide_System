import numpy as np

# COCO-17 indices
LSH, RSH = 5, 6
LHIP, RHIP = 11, 12


def normalize_sequence_hip(
    kpts,
    conf,
    conf_thr: float = 0.2,
    anchor_smooth: float = 0.97,
    scale_smooth: float = 0.97,
    clamp_lo: float = 0.90,
    clamp_hi: float = 1.10,
):
    """
    Production-stable normalization (MID-HIP root):

    1) Anchor = mid-hip (avg of LHIP & RHIP). If hips are missing, HOLD previous anchor.
    2) Scale per frame = shoulder width (fallback hip width, fallback prev),
       clamped to [clamp_lo*median, clamp_hi*median] and EMA smoothed.
    3) Output: canonical coords (T,17,2) where mid-hip is ~ (0,0).

    Returns:
      { "kpts_norm": np.ndarray float32 (T,17,2) }
    """
    k = np.asarray(kpts, dtype=np.float32)
    c = np.asarray(conf, dtype=np.float32)

    if k.ndim != 3 or k.shape[1] != 17 or k.shape[2] != 2:
        raise ValueError(f"kpts must be (T,17,2), got {k.shape}")
    if c.ndim != 2 or c.shape[1] != 17:
        raise ValueError(f"conf must be (T,17), got {c.shape}")

    T = k.shape[0]
    k_norm = np.zeros_like(k, dtype=np.float32)

    # ---------------- baseline scale (median) ----------------
    scales = []
    for t in range(T):
        if c[t, LSH] >= conf_thr and c[t, RSH] >= conf_thr:
            scales.append(float(np.linalg.norm(k[t, LSH] - k[t, RSH])))
        elif c[t, LHIP] >= conf_thr and c[t, RHIP] >= conf_thr:
            scales.append(float(np.linalg.norm(k[t, LHIP] - k[t, RHIP])))

    base = float(np.median(scales)) if len(scales) >= 10 else 1.0
    base = max(base, 1e-6)

    s_min = clamp_lo * base
    s_max = clamp_hi * base

    # ---------------- smoothed anchor + smoothed scale ----------------
    anchor_prev = None
    scale_prev = base

    for t in range(T):
        # ---- anchor (mid-hip root) ----
        hips_ok = (
            c[t, LHIP] >= conf_thr
            and c[t, RHIP] >= conf_thr
            and np.all(np.isfinite(k[t, LHIP]))
            and np.all(np.isfinite(k[t, RHIP]))
        )

        if hips_ok:
            anchor_now = 0.5 * (k[t, LHIP] + k[t, RHIP])
        else:
            # HOLD last anchor to avoid popping; if none yet, fallback to current average (even if low conf)
            if anchor_prev is not None:
                anchor_now = anchor_prev
            else:
                anchor_now = 0.5 * (k[t, LHIP] + k[t, RHIP])

        anchor = anchor_now if anchor_prev is None else (anchor_smooth * anchor_prev + (1.0 - anchor_smooth) * anchor_now)
        anchor_prev = anchor

        # ---- per-frame scale ----
        if c[t, LSH] >= conf_thr and c[t, RSH] >= conf_thr:
            s_now = float(np.linalg.norm(k[t, LSH] - k[t, RSH]))
        elif c[t, LHIP] >= conf_thr and c[t, RHIP] >= conf_thr:
            s_now = float(np.linalg.norm(k[t, LHIP] - k[t, RHIP]))
        else:
            s_now = float(scale_prev)

        if not np.isfinite(s_now) or s_now <= 1e-6:
            s_now = float(scale_prev)

        # clamp + EMA smooth
        s_now = max(s_min, min(s_now, s_max))
        s = scale_smooth * scale_prev + (1.0 - scale_smooth) * s_now
        scale_prev = s

        # normalize
        k_norm[t] = (k[t] - anchor[None, :]) / (s + 1e-6)

    return {"kpts_norm": k_norm}
