import numpy as np
from services.compare import compare_sequences

np.random.seed(0)
T1 = 120
T2 = 110

# synthetic pose sequences (T, 17, 2)
k_ref = np.random.rand(T1, 17, 2).astype('float32')
k_usr = np.random.rand(T2, 17, 2).astype('float32')

def normalize_k(k):
    k = k.copy().astype('float32')
    norms = np.linalg.norm(k, axis=(1, 2), keepdims=True)
    norms[norms == 0] = 1.0
    return k / norms

k_ref_n = normalize_k(k_ref)
k_usr_n = normalize_k(k_usr)

# Use per-joint confidence arrays (T,17) to exercise ST-GCN embedding code path
c_ref = np.ones((T1, 17), dtype='float32') * 0.9
c_usr = np.ones((T2, 17), dtype='float32') * 0.9

res = compare_sequences(k_ref_n, c_ref, k_usr_n, c_usr)

print('overall_score_0_100:', res.get('overall_score_0_100'))
print('final_score_0_100:', res.get('final_score_0_100'))
print('shift_frames:', res.get('shift_frames'))
print('dtw_refined_used:', res.get('dtw_debug', {}).get('refined_dtw_used'))
print('stgcn_enabled:', res.get('stgcn_embedding', {}).get('enabled'))
print('stgcn_error:', res.get('stgcn_embedding', {}).get('error'))
print('\nDTW debug summary:')
for k in ['dtw_score_final','align_valid_ratio','align_unique_ratio','align_collapse_ratio']:
    print(k, res.get('dtw_debug', {}).get(k))
