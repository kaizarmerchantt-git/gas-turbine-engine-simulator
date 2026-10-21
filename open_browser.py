"""
open_browser.py — Synchronized browser launcher for AETHER-X
Polls the backend health check endpoint until FastAPI is ready, then opens the browser.
"""

import time
import urllib.request
import webbrowser
import sys

URL = "http://localhost:8000/"
HEALTH_URL = "http://localhost:8000/api/status"
MAX_ATTEMPTS = 40  # 20 seconds maximum wait
POLL_INTERVAL = 0.5

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1.0) as resp:
            if resp.status == 200:
                # Backend is fully ready to serve requests!
                webbrowser.open(URL)
                sys.exit(0)
    except Exception:
        time.sleep(POLL_INTERVAL)

# Fallback: attempt to open even if health check timed out
try:
    webbrowser.open(URL)
except Exception:
    pass
sys.exit(0)
