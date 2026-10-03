import time
import urllib.request
for attempt in range(60):
    try:
        for url in ('http://127.0.0.1:8000/ready', 'http://127.0.0.1:5173'):
            urllib.request.urlopen(url, timeout=2)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('Services did not become ready within 60 seconds.')
