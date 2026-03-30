#!/usr/bin/env python3
import os, time, psutil, json, random, statistics
import numpy as np
from services.compare import compare_sequences

norm_dir = os.path.join(os.path.dirname(__file__), 'storage', 'normalized')
ids = [d for d in os.listdir(norm_dir) if os.path.isdir(os.path.join(norm_dir, d))]
# keep only ids that actually contain keypoints.npz
ids = [d for d in ids if os.path.exists(os.path.join(norm_dir, d, 'keypoints.npz'))]
if len(ids) < 2:
    raise SystemExit('need at least two normalized jobs in storage/normalized')

random.seed(0)
# sample up to 10 pairs (unique random pairs)
pairs = []
sample_count = min(10, max(1, len(ids)//2))
seen = set()
while len(pairs) < sample_count:
    a, b = random.sample(ids, 2)
    key = tuple(sorted([a,b]))
    if key in seen:
        continue
    seen.add(key)
    pairs.append((a,b))

results = []
proc = psutil.Process()
for ref_id, usr_id in pairs:
    ref_npz = os.path.join(norm_dir, ref_id, 'keypoints.npz')
    usr_npz = os.path.join(norm_dir, usr_id, 'keypoints.npz')
    def load_npz(p):
        d = np.load(p)
        kpts = d['kpts'].astype('float32')
        conf = d['conf'].astype('float32')
        kpts_raw = d['kpts_raw'].astype('float32') if 'kpts_raw' in d else kpts
        return kpts, conf, kpts_raw
    k_ref, c_ref, k_ref_raw = load_npz(ref_npz)
    k_usr, c_usr, k_usr_raw = load_npz(usr_npz)

    mem_before = proc.memory_info().rss/1024/1024
    t0 = time.time()
    try:
        res = compare_sequences(k_ref, c_ref, k_usr, c_usr, max_shift=90, k_ref_raw=k_ref_raw, k_usr_raw=k_usr_raw)
        ok = True
        err = None
    except Exception as e:
        res = None
        ok = False
        err = str(e)
    lat = time.time()-t0
    mem_after = proc.memory_info().rss/1024/1024
    results.append({
        'ref': ref_id,
        'usr': usr_id,
        'ok': ok,
        'error': err,
        'latency_s': lat,
        'mem_before_mb': mem_before,
        'mem_after_mb': mem_after,
        'overall_score': None if res is None else res.get('overall_score_0_100'),
        'final_score': None if res is None else res.get('final_score_0_100'),
        'stgcn_enabled': None if res is None else res.get('stgcn_embedding',{}).get('enabled'),
        'stgcn_error': None if res is None else res.get('stgcn_embedding',{}).get('error'),
        'dtw_unique_ratio': None if res is None else res.get('dtw_debug',{}).get('align_unique_ratio'),
        'dtw_valid_ratio': None if res is None else res.get('dtw_debug',{}).get('align_valid_ratio'),
    })

# summary
latencies = [r['latency_s'] for r in results if r['ok']]
final_scores = [r['final_score'] for r in results if r['ok'] and r['final_score'] is not None]
stgcn_counts = sum(1 for r in results if r.get('stgcn_enabled'))
unique_low = [r for r in results if r.get('dtw_unique_ratio') is not None and r['dtw_unique_ratio'] < 0.01]

summary = {
    'num_pairs': len(results),
    'completed': sum(1 for r in results if r['ok']),
    'latency_mean_s': statistics.mean(latencies) if latencies else None,
    'latency_ms': [round(x*1000,1) for x in latencies],
    'final_score_mean': statistics.mean(final_scores) if final_scores else None,
    'final_scores': final_scores,
    'stgcn_enabled_count': stgcn_counts,
    'dtw_unique_low_count': len(unique_low),
    'pairs': results,
}
print(json.dumps(summary, indent=2))
