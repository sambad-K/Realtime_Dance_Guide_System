import json
import numpy as np
import os
import tempfile


def save_npz(path: str, **arrays):
    fixed = {k: np.asarray(v) for k, v in arrays.items()}
    np.savez_compressed(path, **fixed)


def save_json(path: str, obj: dict):
    """Atomically write JSON to `path`.

    Writes to a temporary file in the same directory then atomically replaces
    the target. Performs a best-effort fsync and falls back to a regular
    write if atomic replace fails.
    """
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass

    temp_fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix=".tmp_", dir=d or None, text=True)
        temp_fd = fd
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                # best-effort
                pass
        # atomic replace
        os.replace(temp_path, path)
    except Exception:
        # fallback: attempt simple write
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
        except Exception:
            # give up silently; caller should handle/log
            pass
    finally:
        try:
            if temp_path is not None and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        except Exception:
            pass
