import urllib.request
from urllib.error import HTTPError
try:
    res = urllib.request.urlopen('http://127.0.0.1:8888/api/macro/ai_insight')
    print("SUCCESS", res.read().decode())
except HTTPError as e:
    print("HTTPError", e.code)
    print(e.read().decode())
