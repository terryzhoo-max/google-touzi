import requests
import json

try:
    res = requests.get("http://127.0.0.1:8888/api/institutional/decision_hub", timeout=5)
    data = res.json()
    print("Global Status:", data.get("global_status"))
    print("\nL4 Compliance Details:")
    print(json.dumps(data.get("l4_compliance"), ensure_ascii=False, indent=2))
except Exception as e:
    print("Error:", e)
