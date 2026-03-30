import numpy as np
import json
from services.compare import compare_sequences

T = 30
k_ref = np.zeros((T,17,2), np.float32)
k_usr = np.zeros((T,17,2), np.float32)
c_ref = np.ones((T,), np.float32)
c_usr = np.ones((T,), np.float32)
res = compare_sequences(k_ref, c_ref, k_usr, c_usr)
print(json.dumps(res.get('dtw_debug', {}), indent=2))
