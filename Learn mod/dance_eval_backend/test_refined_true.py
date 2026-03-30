import numpy as np
import services.compare as comp

# backup originals
_orig_embed = comp.stgcn_embed_sequence_windows
_orig_dtw = comp._dtw_align_map

# Test sequences
T1 = 200
T2 = 190

def make_seq(T):
    t = np.linspace(0, 2 * np.pi, T)
    k = np.zeros((T, 17, 2), dtype='float32')
    for v in range(17):
        phase = (v / 17.0) * 2.0 * np.pi
        k[:, v, 0] = np.sin(t * (1.0 + 0.01 * v) + phase)
        k[:, v, 1] = np.cos(t * (1.0 + 0.01 * v) + phase)
    return k

k_ref = make_seq(T1)
k_usr = make_seq(T2)

# confidences (per-joint)
c_ref = np.ones((T1, 17), dtype='float32') * 0.9
c_usr = np.ones((T2, 17), dtype='float32') * 0.9

# Monkeypatch embedding to return deterministic window embeddings
Cr = comp._window_centers(T1)
Cu = comp._window_centers(T2)
num_win_r = len(Cr)
num_win_u = len(Cu)
embed_dim = 32
Zr = np.tile(np.linspace(0.0, 1.0, embed_dim).reshape(1, -1), (num_win_r, 1)).astype('float32')
Zu = np.tile(np.linspace(0.0, 1.0, embed_dim).reshape(1, -1), (num_win_u, 1)).astype('float32')

def fake_embed(k_seq, c_seq, ckpt_path=None, conf_thr=0.2):
    # return precomputed slices depending on requested length
    L = len(k_seq)
    centers = comp._window_centers(L)
    return np.tile(np.linspace(0.0, 1.0, embed_dim).reshape(1, -1), (len(centers), 1)).astype('float32'), None

# Fake DTW align map: if small (window-level), map windows identity (or clipped);
# if called on full-resolution features, return a smooth monotonic mapping
def fake_dtw_map(X, Y, bw=None):
    N = int(X.shape[0])
    M = int(Y.shape[0])
    if N <= 0 or M <= 0:
        return np.zeros((max(N, 1),), dtype=np.int32)
    # window-level case: small N
    if N < 100 and M < 100:
        return np.clip(np.arange(N), 0, M - 1).astype(np.int32)
    # full-resolution: linear mapping from ref->usr
    return np.clip(np.round(np.linspace(0, M - 1, N)).astype(np.int32), 0, M - 1)

# apply monkeypatches
comp.stgcn_embed_sequence_windows = fake_embed
comp._dtw_align_map = fake_dtw_map

# ensure config enables embed-DTW and has ckpt path
comp.Config.STGCN_CKPT = 'dummy'
comp.Config.EMBED_DTW_ENABLED = True
comp.Config.EMBED_DTW_THRESHOLD = 100.0

# Run compare
res = comp.compare_sequences(k_ref, c_ref, k_usr, c_usr, max_shift=120)

print('refined_used:', res.get('dtw_debug', {}).get('refined_dtw_used'))
print('remapped_centers_count:', res.get('dtw_debug', {}).get('remapped_centers_count'))
print('refined_valid_ratio:', res.get('dtw_debug', {}).get('refined_valid_ratio'))
print('refined_unique_ratio:', res.get('dtw_debug', {}).get('refined_unique_ratio'))
print('refined_collapse_ratio:', res.get('dtw_debug', {}).get('refined_collapse_ratio'))
print('final_alignment_mode:', res.get('dtw_debug', {}).get('final_alignment_mode'))
print('best_shift_frames:', res.get('dtw_debug', {}).get('best_shift_frames'))
print('out_shift_frames:', res.get('dtw_debug', {}).get('out_shift_frames'))
print('overall_score_0_100:', res.get('overall_score_0_100'))
print('final_score_0_100:', res.get('final_score_0_100'))

# restore originals
comp.stgcn_embed_sequence_windows = _orig_embed
comp._dtw_align_map = _orig_dtw
