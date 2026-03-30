# services/stgcn_embed.py
import os
import numpy as np

WIN_T = 100
STRIDE = 50

# if a window has too few valid joints, skip it
MIN_VALID_JOINT_RATIO = 0.40  # 40% of joints across frames must be valid (stricter)

_ENCODER = None
_LOADED_CKPT = None
_LAST_ERR = None


def _coco17_edges():
    return [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (0, 5), (0, 6),
        (5, 7), (7, 9),
        (6, 8), (8, 10),
        (5, 11), (6, 12),
        (11, 13), (13, 15),
        (12, 14), (14, 16),
        (11, 12),
    ]


def _build_adjacency(V=17):
    A = np.zeros((V, V), dtype=np.float32)
    for i, j in _coco17_edges():
        A[i, j] = 1.0
        A[j, i] = 1.0
    np.fill_diagonal(A, 1.0)
    D = np.sum(A, axis=1)
    D_inv = np.diag(1.0 / np.sqrt(np.maximum(D, 1e-6)))
    A = D_inv @ A @ D_inv
    return A.astype(np.float32)


def _try_import_torch():
    try:
        import torch  # noqa
        return torch, None
    except Exception as e:
        return None, f"torch import failed: {e}"


def _torch_load_any(torch, path: str, device: str):
    try:
        return torch.load(path, map_location=device, weights_only=True)
    except Exception:
        return torch.load(path, map_location=device, weights_only=False)


def _as_state_dict(obj):
    if isinstance(obj, dict) and "state_dict" in obj and isinstance(obj["state_dict"], dict):
        return obj["state_dict"]
    if isinstance(obj, dict):
        return obj
    raise ValueError("checkpoint is not a dict/state_dict")


def _clean_state_dict(sd: dict):
    return {k: v for k, v in sd.items() if k not in ("A",)}


def _is_ok_missing_key(k: str) -> bool:
    if k == "A":
        return True
    if k.startswith("fc.1.running_"):
        return True
    return False


def load_stgcn_encoder(ckpt_path: str):
    global _ENCODER, _LOADED_CKPT, _LAST_ERR

    if not ckpt_path:
        _LAST_ERR = "no ckpt_path provided"
        return None, _LAST_ERR

    ckpt_path = os.path.abspath(ckpt_path)
    if _ENCODER is not None and _LOADED_CKPT == ckpt_path:
        return _ENCODER, None

    if not os.path.exists(ckpt_path):
        _LAST_ERR = f"checkpoint not found: {ckpt_path}"
        return None, _LAST_ERR

    torch, terr = _try_import_torch()
    if torch is None:
        _LAST_ERR = terr
        return None, _LAST_ERR

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        from services.stgcn_model_def import build_model
    except Exception as e:
        _LAST_ERR = f"failed to import services.stgcn_model_def: {e}"
        return None, _LAST_ERR

    try:
        A = np.asarray(_build_adjacency(17), dtype=np.float32)
        At = torch.tensor(A, dtype=torch.float32, device=device)

        model = build_model(At, in_channels=2, latent_dim=256, V=17, dropout=0.0).to(device)
        model.eval()
        encoder = model.encoder if hasattr(model, "encoder") else model
        encoder.eval()

        obj = _torch_load_any(torch, ckpt_path, device)
        sd = _clean_state_dict(_as_state_dict(obj))

        missing, unexpected = encoder.load_state_dict(sd, strict=False)
        bad_missing = [k for k in missing if not _is_ok_missing_key(k)]
        if bad_missing:
            raise RuntimeError("checkpoint missing critical keys: " + ", ".join(bad_missing[:20]))

        _ENCODER = encoder
        _LOADED_CKPT = ckpt_path
        _LAST_ERR = None
        return _ENCODER, None

    except Exception as e:
        _ENCODER = None
        _LOADED_CKPT = None
        _LAST_ERR = f"failed to load ST-GCN checkpoint: {e}"
        return None, _LAST_ERR


# --------- NEW: window quality + normalization helpers ---------
def _valid_ratio(c_win: np.ndarray, conf_thr: float) -> float:
    m = (c_win >= conf_thr).astype(np.float32)  # (T,17)
    return float(m.mean())


def _normalize_window(k_win: np.ndarray, m_win: np.ndarray):
    """
    k_win: (T,17,2), m_win: (T,17) in {0,1}
    Normalize by per-window scale so different camera distance doesn’t collapse similarity.
    """
    k = k_win.copy().astype(np.float32)
    m = m_win.astype(np.float32)

    # compute RMS scale over valid points
    pts = k.reshape(-1, 2)
    mm = m.reshape(-1, 1)
    denom = float(mm.sum() + 1e-6)
    mean = (pts * mm).sum(axis=0) / denom
    pts = pts - mean[None, :]
    rms = np.sqrt(((pts * pts) * mm).sum() / (denom * 2.0) + 1e-6)

    k = (k - mean[None, None, :]) / float(rms)
    return k.astype(np.float32)


def _pack_window(k_win: np.ndarray, c_win: np.ndarray, conf_thr: float):
    k = np.asarray(k_win, np.float32)  # (WIN_T,17,2)
    c = np.asarray(c_win, np.float32)  # (WIN_T,17)

    if k.shape != (WIN_T, 17, 2):
        raise ValueError(f"expected k_win (WIN_T,17,2) got {k.shape}")
    if c.shape != (WIN_T, 17):
        raise ValueError(f"expected c_win (WIN_T,17) got {c.shape}")

    m = (c >= conf_thr).astype(np.float32)  # (T,17)

    # normalize BEFORE masking to avoid collapsing to near-zero
    k = np.nan_to_num(k, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    k = _normalize_window(k, m)

    # now mask invalid joints
    k = k * m[:, :, None]
    k = np.nan_to_num(k, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    x = k.transpose(2, 0, 1)[None, ...]  # (1,2,T,17)
    x = x[..., None]                     # (1,2,T,17,1)
    return x, m


def stgcn_embed_sequence_windows(
    kpts_TV2: np.ndarray,
    conf_TV: np.ndarray,
    ckpt_path: str,
    conf_thr: float = 0.2,
):
    encoder, err = load_stgcn_encoder(ckpt_path)
    if encoder is None:
        return None, err or "ST-GCN disabled"

    torch, terr = _try_import_torch()
    if torch is None:
        return None, terr

    device = "cuda" if torch.cuda.is_available() else "cpu"

    k = np.asarray(kpts_TV2, np.float32)
    c = np.asarray(conf_TV, np.float32)

    if k.ndim != 3 or k.shape[1:] != (17, 2):
        return None, f"bad kpts shape {k.shape} (need (T,17,2))"
    if c.ndim != 2 or c.shape[0] != k.shape[0] or c.shape[1] != 17:
        return None, f"bad conf shape {c.shape} (need (T,17))"

    T = int(k.shape[0])
    if T < WIN_T:
        return None, f"too few frames: {T} < WIN_T={WIN_T}"

    # collect windows first, then run batched inference for better throughput
    windows = []
    skipped = 0
    for start in range(0, T - WIN_T + 1, STRIDE):
        c_win = c[start:start + WIN_T]
        if _valid_ratio(c_win, conf_thr) < MIN_VALID_JOINT_RATIO:
            skipped += 1
            continue
        x, m = _pack_window(k[start:start + WIN_T], c_win, conf_thr)
        windows.append((x, m))

    if not windows:
        return None, f"no windows produced (skipped={skipped})"

    # batch inference
    batch_size = 32
    Z_list = []
    near_zero = 0

    # ensure encoder is on device and eval; load_stgcn_encoder already sets this, but be safe
    try:
        encoder.to(device)
        encoder.eval()
    except Exception:
        pass

    # Use torch.autocast for GPU float16 speedups when available
    use_amp = (device == "cuda")
    amp_ctx = torch.cuda.amp.autocast if hasattr(torch.cuda.amp, "autocast") else None

    for i in range(0, len(windows), batch_size):
        batch = windows[i:i + batch_size]
        batch_x = np.concatenate([b[0] for b in batch], axis=0)  # (B,2,T,17,1)
        xt = torch.from_numpy(batch_x).to(device)
        with torch.no_grad():
            if use_amp and amp_ctx is not None:
                with amp_ctx():
                    z_batch = encoder(xt).detach().float().cpu().numpy()
            else:
                z_batch = encoder(xt).detach().float().cpu().numpy()

        for z in z_batch:
            z = np.nan_to_num(z.reshape(-1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
            n = float(np.linalg.norm(z) + 1e-6)
            if n < 1e-3:
                near_zero += 1
                continue
            Z_list.append((z / n).astype(np.float32))

    if not Z_list:
        return None, f"no windows produced (skipped={skipped}, near_zero={near_zero})"

    Z = np.stack(Z_list, axis=0).astype(np.float32)
    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    return Z, None
