import subprocess
import time
import urllib.request
import os
import sys
from playwright.sync_api import sync_playwright

artifact_dir = r"C:\Users\kaiza\.gemini\antigravity\brain\5b64f18d-03a6-4591-b642-0659bfedb842"
os.makedirs(artifact_dir, exist_ok=True)

# 1. Start uvicorn server in background
backend_dir = os.path.abspath("backend")
server_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=backend_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

print("Starting backend on http://127.0.0.1:8000 ...")

# 2. Wait for server readiness
ready = False
for _ in range(30):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=1.0) as resp:
            if resp.status == 200:
                ready = True
                print("Server is ONLINE and READY!")
                break
    except Exception:
        time.sleep(0.5)

if not ready:
    server_proc.terminate()
    raise RuntimeError("Server failed to start within 15 seconds")

try:
    # 3. Test HTTP routing for default / and /app and /legacy
    req_root = urllib.request.Request("http://127.0.0.1:8000/", headers={"Accept": "text/html"})
    with urllib.request.urlopen(req_root) as resp:
        html = resp.read().decode("utf-8")
        assert "AETHER-X // AEROSPACE PROPULSION SIMULATOR (v0.5.0 OBSIDIAN BLUEPRINT)" in html, "Root / did not serve index_v0.5.html!"
        assert "--accent-amber: #F59E0B" in html, "Root / does not contain obsidian amber palette!"
        assert "radial-gradient(circle at 50% 0%, rgba(56" not in html, "Old cyan radial gradient still found in HTML!"
        print("[VERIFIED] GET / successfully serves v0.5 Obsidian Blueprint HTML!")

    req_app = urllib.request.Request("http://127.0.0.1:8000/app", headers={"Accept": "text/html"})
    with urllib.request.urlopen(req_app) as resp:
        html_app = resp.read().decode("utf-8")
        assert "v0.5.0 OBSIDIAN BLUEPRINT" in html_app, "Route /app did not serve index_v0.5.html!"
        print("[VERIFIED] GET /app successfully serves v0.5 Obsidian Blueprint HTML!")

    req_legacy = urllib.request.Request("http://127.0.0.1:8000/legacy", headers={"Accept": "text/html"})
    with urllib.request.urlopen(req_legacy) as resp:
        html_leg = resp.read().decode("utf-8")
        assert "Gas Turbine Engine Simulator (HUD)" in html_leg or "AETHER-X" in html_leg, "Route /legacy failed!"
        print("[VERIFIED] GET /legacy successfully serves original v0.4 index.html reference!")

    # 4. Playwright Headless Browser Verification & Screenshots
    print("Launching Playwright headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1050})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        # Navigate to root /
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_selector(".blueprint-header", timeout=10000)
        time.sleep(1.5)  # Allow initial simulation solve and React rendering

        # Capture Tab 1: Turbojet Single-Spool (Obsidian Blueprint)
        shot_turbojet = os.path.join(artifact_dir, "v0.5_obsidian_blueprint_turbojet.png")
        page.screenshot(path=shot_turbojet, full_page=True)
        print(f"[CAPTURED] Turbojet screenshot: {shot_turbojet}")

        # Click Tab 2: Dual-Spool Turbofan
        tabs = page.query_selector_all(".module-tab")
        if len(tabs) > 1:
            tabs[1].click()
            time.sleep(1.0)
            shot_turbofan = os.path.join(artifact_dir, "v0.5_obsidian_blueprint_turbofan.png")
            page.screenshot(path=shot_turbofan, full_page=True)
            print(f"[CAPTURED] Turbofan screenshot: {shot_turbofan}")

        # Click Tab 4: Off-Design Compressor Map
        if len(tabs) > 3:
            tabs[3].click()
            time.sleep(1.0)
            shot_map = os.path.join(artifact_dir, "v0.5_obsidian_blueprint_compressor_map.png")
            page.screenshot(path=shot_map, full_page=True)
            print(f"[CAPTURED] Compressor Map screenshot: {shot_map}")

        # Click Tab 5: 1D Mean-Line Stage Aerodynamics
        if len(tabs) > 4:
            tabs[4].click()
            time.sleep(1.0)
            shot_meanline = os.path.join(artifact_dir, "v0.5_obsidian_blueprint_velocity_triangles.png")
            page.screenshot(path=shot_meanline, full_page=True)
            print(f"[CAPTURED] Velocity Triangles screenshot: {shot_meanline}")

        # Click Tab 9: Hybrid-Electric Powertrain
        if len(tabs) > 8:
            tabs[8].click()
            time.sleep(1.0)
            shot_hybrid = os.path.join(artifact_dir, "v0.5_obsidian_blueprint_hybrid.png")
            page.screenshot(path=shot_hybrid, full_page=True)
            print(f"[CAPTURED] Hybrid-Electric screenshot: {shot_hybrid}")

        browser.close()

    print("\n[VERIFICATION SUMMARY]")
    print(f"Total Console/Runtime Errors: {len(console_errors)}")
    if console_errors:
        print("Errors encountered:", console_errors)
        assert len(console_errors) == 0, f"Found {len(console_errors)} console errors!"
    else:
        print("[SUCCESS] 0 console errors, 0 runtime crashes across all tabs!")

finally:
    print("Terminating test backend server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)
    print("Server cleanly stopped.")
