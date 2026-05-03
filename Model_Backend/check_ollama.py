import sys, json
sys.path.insert(0, r"d:/Major project/A. MAIN/Learn mod/dance_eval_backend")
sys.path.insert(0, r"d:/Major project/A. MAIN/Learn mod")
from services import llm

parsed, text, raw, err = llm._call_ollama('Return ONLY {"summary":"Test","strengths":[],"weaknesses":[],"recommendations":[],"confidence":50}', timeout=20)
out = {
    'parsed': parsed,
    'text_candidate': text,
    'raw': raw,
    'error': err
}
print(json.dumps(out, ensure_ascii=False, indent=2))
