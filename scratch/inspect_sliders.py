import asyncio
import os
import subprocess
import time
import sys
from playwright.async_api import async_playwright

PORT = 8899

async def test_slider():
    backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3.0)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
            await asyncio.sleep(1.0)
            await page.locator("button:has-text('02 TURBOFAN')").click()
            
            # Wait for station table to appear
            await page.wait_for_selector(".blueprint-table tbody tr", timeout=8000)
            stn_ids = await page.locator(".blueprint-table tbody tr td:first-child").all_inner_texts()
            print("Station IDs loaded:", stn_ids)

            kpis_before = await page.locator(".kpi-value").all_inner_texts()
            print("Before drag:", kpis_before[:4])

            # Drag BPR slider to 7.4
            slider = page.locator(".range-input").first
            await slider.evaluate("""el => {
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(el, '7.4');
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
            print("Dispatched slider change to 7.4. Waiting for debounced solve...")
            await asyncio.sleep(3.5)

            kpis_after = await page.locator(".kpi-value").all_inner_texts()
            print("After drag to 7.4:", kpis_after[:4])

            await browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(test_slider())
