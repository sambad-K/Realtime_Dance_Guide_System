#!/usr/bin/env python3
import os, time, psutil, json
import numpy as np
from services.compare import compare_sequences

# find normalized npz files
norm_dir = os.path.join(os.path.dirname(__file__), 'storage', 'normalized')
ids = [d for d in os.listdir(norm_dir) if os.path.isdir(os.path.join(norm_dir, d))]
if len(ids) < 2:
    raise SystemExit('need at least two normalized jobs in storage/normalized')

# pick two different
ref_id = ids[0]
usr_id = ids[1] if ids[1] != ids[0] else (ids[2] if len(ids)>2 else ids[0])

ref_npz = os.path.join(norm_dir, ref_id, 'keypoints.npz')
usr_npz = os.path.join(norm_dir, usr_id, 'keypoints.npz')
print('REF', ref_npz)
print('USR', usr_npz)

def load_npz(p):
    d = np.load(p)
    kpts = d['kpts'].astype('float32')
    conf = d['conf'].astype('float32')
    kpts_raw = d['kpts_raw'].astype('float32') if 'kpts_raw' in d else kpts
    return kpts, conf, kpts_raw

k_ref, c_ref, k_ref_raw = load_npz(ref_npz)
k_usr, c_usr, k_usr_raw = load_npz(usr_npz)

proc = psutil.Process()
mem_before = proc.memory_info().rss/1024/1024
t0 = time.time()
res = compare_sequences(k_ref, c_ref, k_usr, c_usr, max_shift=90, k_ref_raw=k_ref_raw, k_usr_raw=k_usr_raw)
lat = time.time()-t0
mem_after = proc.memory_info().rss/1024/1024

out = {
    'ref_id': ref_id,
    'usr_id': usr_id,
    'latency_s': lat,
    'mem_before_mb': mem_before,
    'mem_after_mb': mem_after,
    'overall_score': res.get('overall_score_0_100'),
    'final_score': res.get('final_score_0_100'),
    'shift_frames': res.get('shift_frames'),
    'dtw_used': res.get('dtw_debug', {}).get('dtw_refinement') is not None,
    'stgcn_enabled': res.get('stgcn_embedding', {}).get('enabled'),
    'stgcn_error': res.get('stgcn_embedding', {}).get('error'),
}
print(json.dumps(out, indent=2))
print('\nDTW debug excerpt:')
print(json.dumps({k: res.get('dtw_debug', {}).get(k) for k in ['T_ref','T_usr','best_shift_frames','align_valid_ratio','align_unique_ratio','dtw_score_final']}, indent=2))
print('\nST-GCN debug excerpt:')
print(json.dumps(res.get('stgcn_embedding', {}) , indent=2)[:1000])
