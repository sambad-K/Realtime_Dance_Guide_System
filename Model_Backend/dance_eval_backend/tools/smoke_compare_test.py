"""Smoke test for compare_sequences
Generates synthetic 2D keypoint sequences for COCO-17 shape and runs compare_sequences
on a matched pair and a tempo-shifted pair to ensure no crashes and output shape.
"""
import json
import sys
import types
import numpy as np

# Ensure imports that `config.py` expects are available in this test environment.
# Provide a minimal dummy `dotenv` module so `from dotenv import load_dotenv` succeeds.
if 'dotenv' not in sys.modules:
    sys.modules['dotenv'] = types.SimpleNamespace(load_dotenv=lambda *a, **k: None)

from services.compare import compare_sequences

# helper: create synthetic sequence (T,17,2) with simple sinusoidal motion
def make_synth(T=200, noise=0.01):
    V = 17
    t = np.linspace(0, 2 * np.pi, T)
    k = np.zeros((T, V, 2), dtype=np.float32)
    for v in range(V):
        phase = (v / float(V)) * 2.0
        k[:, v, 0] = 0.5 + 0.1 * np.sin(t * (1.0 + 0.02 * v) + phase)
        k[:, v, 1] = 0.5 + 0.1 * np.cos(t * (1.0 + 0.02 * v) + phase)
    k += np.random.randn(*k.shape).astype(np.float32) * noise
    # confidences
    c = np.ones((T,), dtype=np.float32)
    return k, c

# resample (tempo shift)
def tempo_resample(k, factor):
    T = k.shape[0]
    t_idx = np.linspace(0, T - 1, int(np.ceil(T / factor)))
    t_idx = np.clip(t_idx, 0, T - 1)
    ks = np.stack([np.interp(t_idx, np.arange(T), k[:, v, d]) for v in range(k.shape[1]) for d in range(2)], axis=1)
    ks = ks.reshape(len(t_idx), k.shape[1], 2)
    c = np.ones((len(t_idx),), dtype=np.float32)
    return ks.astype(np.float32), c


def run_case(name, k1, c1, k2, c2):
    print(f"--- {name} ---")
    out = compare_sequences(k_ref_norm=k1, c_ref=c1, k_usr_norm=k2, c_usr=c2)
    print(json.dumps({"overall": out.get("overall_score_0_100"), "final": out.get("final_score_0_100"), "dtw_dbg": out.get("dtw_debug", {})}, indent=2))


def main():
    k1, c1 = make_synth(200)
    k2, c2 = make_synth(200)

    # aligned
    run_case("aligned", k1, c1, k2, c2)

    # tempo-shifted (user is faster)
    k2_fast, c2f = tempo_resample(k2, factor=1.25)
    run_case("tempo_fast", k1, c1, k2_fast, c2f)

    # tempo-shifted (user slower)
    k2_slow, c2s = tempo_resample(k2, factor=0.8)
    run_case("tempo_slow", k1, c1, k2_slow, c2s)

if __name__ == '__main__':
    main()
