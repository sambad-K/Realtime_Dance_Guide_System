import os
# disable embed DTW / ST-GCN for DTW-only test
os.environ['EMBED_DTW_ENABLED'] = '0'

import numpy as np
from services.compare import compare_sequences

np.random.seed(1)

T_ref = 240
# create base motion: simple circular motion per joint with different phases
def make_sequence(T, speed=1.0, noise=0.01):
    t = np.arange(T)
    k = np.zeros((T, 17, 2), dtype='float32')
    for v in range(17):
        phase = (v / 17.0) * 2.0 * np.pi
        freq = 1.0 * speed
        k[:, v, 0] = 0.5 * np.sin(2 * np.pi * freq * (t / float(T)) + phase)
        k[:, v, 1] = 0.5 * np.cos(2 * np.pi * freq * (t / float(T)) + phase)
    k += noise * np.random.randn(*k.shape).astype('float32')
    return k

# reference sequence
k_ref = make_sequence(T_ref, speed=1.0, noise=0.005)
# user sequence: slightly faster (tempo 1.1) and shifted by +8 frames
speed_usr = 1.1
T_usr = int(T_ref / speed_usr)
k_usr_base = make_sequence(T_usr, speed=speed_usr, noise=0.01)
# pad/shift user by inserting blanks at start
shift = 8
k_usr = np.concatenate([np.zeros((shift, 17, 2), dtype='float32'), k_usr_base], axis=0)

# normalize poses per-frame (mimic expected normalized inputs)
def normalize_k(k):
    k = k.astype('float32')
    norms = np.linalg.norm(k, axis=(1,2), keepdims=True)
    norms[norms == 0] = 1.0
    return k / norms

k_ref_n = normalize_k(k_ref)
k_usr_n = normalize_k(k_usr)

# confidence arrays (per-frame scalar)
c_ref = np.ones((k_ref_n.shape[0],), dtype='float32') * 0.9
c_usr = np.ones((k_usr_n.shape[0],), dtype='float32') * 0.9

res = compare_sequences(k_ref_n, c_ref, k_usr_n, c_usr, max_shift=120)

print('DTW-only test results')
print('T_ref, T_usr:', k_ref_n.shape[0], k_usr_n.shape[0])
print('best_shift_frames (reported):', res.get('dtw_debug', {}).get('best_shift_frames'))
print('final_shift_frames:', res.get('dtw_debug', {}).get('final_shift_frames'))
print('refined_dtw_used:', res.get('dtw_debug', {}).get('refined_dtw_used'))
print('overall_score_0_100:', res.get('overall_score_0_100'))
print('final_score_0_100:', res.get('final_score_0_100'))
print('align_valid_ratio:', res.get('dtw_debug', {}).get('align_valid_ratio'))
print('align_unique_ratio:', res.get('dtw_debug', {}).get('align_unique_ratio'))
print('align_collapse_ratio:', res.get('dtw_debug', {}).get('align_collapse_ratio'))
