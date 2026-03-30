import requests
import sys

url = 'http://127.0.0.1:11434/api/generate'
payload = {
    'model': 'qwen2.5:7b-instruct',
    'prompt': 'Return ONLY {"ok":true}'
}
try:
    r = requests.post(url, json=payload, timeout=10)
    print('STATUS', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
except Exception as e:
    print('ERROR', e)
    sys.exit(2)
