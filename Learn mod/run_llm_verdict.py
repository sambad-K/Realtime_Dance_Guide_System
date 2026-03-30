import sys, os, json
# ensure backend package imports work as when running from dance_eval_backend
root = r"d:/Major project/A. MAIN/Learn mod"
sys.path.insert(0, os.path.join(root, 'dance_eval_backend'))
sys.path.insert(0, root)

from services import llm

scores_path = os.path.join(root, 'dance_eval_backend', 'storage', 'normalized', 'tmp-verdict-llm-test', 'scores.json')
if not os.path.exists(scores_path):
    print(json.dumps({'error': 'scores.json not found', 'path': scores_path}, ensure_ascii=False))
    sys.exit(2)

with open(scores_path, 'r', encoding='utf-8') as f:
    compare_res = json.load(f)

out = llm.generate_verdict(compare_res)
print(json.dumps(out, ensure_ascii=False, indent=2))
