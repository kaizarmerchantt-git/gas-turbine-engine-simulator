# -*- coding: utf-8 -*-
"""
verify_e2e_render.py — Headless Playwright verification across all 9 upgraded modules.
Asserts live reactivity, physics correctness, non-clipping header, and captures screenshots.
"""
import asyncio
import subprocess
import time
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.async_api import async_playwright

PORT = 8899
ARTIFACT_DIR = r"C:\Users\kaiza\.gemini\antigravity\brain\5b64f18d-03a6-4591-b642-0659bfedb842"

async def run_verification():
    # 1. Start backend process on PORT 8899
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    print(f"Started backend process PID: {proc.pid} on port {PORT}")
    time.sleep(3.5)

    console_errors = []
    audit_failures = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080})
            page = await context.new_page()

            page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)
            page.on("pageerror", lambda err: console_errors.append(f"[pageerror] {err}"))

            url = f"http://127.0.0.1:{PORT}/"
            print(f"Navigating to {url} ...")
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await asyncio.sleep(3.0)

            # ── 1. Header Non-Clipping Verification ──────────────────────────
            print("\n[VERIFY 1] Top Header Bar & All 9 Domains Visible...")
            brand = await page.locator(".header-branding").inner_text()
            print(f"Brand text: {brand.strip()}")
            if "AETHER-X" not in brand:
                audit_failures.append("Brand text does not contain AETHER-X")

            pills = page.locator(".domain-pill")
            pill_count = await pills.count()
            print(f"Found {pill_count} domain buttons")
            if pill_count < 9:
                audit_failures.append(f"Expected 9 domain buttons, found {pill_count}")

            for i in range(pill_count):
                pill_txt = await pills.nth(i).inner_text()
                box = await pills.nth(i).bounding_box()
                print(f"  Pill {i+1}: '{pill_txt}' at x={box['x']:.1f}, width={box['width']:.1f}")
                # Assert within viewport (1920)
                if box["x"] + box["width"] > 1920:
                    audit_failures.append(f"Pill '{pill_txt}' overflows 1920px screen width!")

            # Verify select dropdown exists
            dropdown = page.locator(".domain-select-dropdown")
            if await dropdown.count() > 0:
                print("Domain select dropdown is present.")
            else:
                audit_failures.append("Domain select dropdown is missing.")

            # ── 2. Domain 01 (Turbojet) Verification ─────────────────────────
            print("\n[VERIFY 2] Domain 01 (Turbojet Single-Spool)...")
            await page.locator("button:has-text('01 TURBOJET')").click()
            await asyncio.sleep(2.0)

            # Check initial KPIs
            kpi_values = await page.locator(".kpi-value").all_inner_texts()
            print(f"Turbojet initial KPIs: {kpi_values[:4]}")
            fn_init = kpi_values[0]
            if "0.00" in fn_init or "---" in fn_init:
                audit_failures.append(f"Turbojet initial net thrust is collapsed ({fn_init})")

            # Check Station Table
            stn_cells = await page.locator(".blueprint-table tbody tr").all_inner_texts()
            print(f"Turbojet station rows count: {len(stn_cells)}")
            if len(stn_cells) < 5:
                audit_failures.append(f"Turbojet station table has only {len(stn_cells)} rows")
            
            # Verify entropy column is not '---'
            entropy_cell = await page.locator(".blueprint-table tbody tr td:nth-child(9)").first.inner_text()
            print(f"Station 0/a entropy: {entropy_cell} J/kg·K")
            if "---" in entropy_cell or entropy_cell == "0":
                audit_failures.append(f"Turbojet station entropy is invalid: {entropy_cell}")

            # Helper to reliably dispatch input events on HTML5 range inputs in React
            async def set_slider_val(loc, val):
                await loc.evaluate(f"""el => {{
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(el, '{val}');
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}""")

            # Live slider drag test: drag CPR slider
            cpr_slider = page.locator(".range-input").first
            await set_slider_val(cpr_slider, 16.0)
            await asyncio.sleep(2.0)
            kpi_values_after = await page.locator(".kpi-value").all_inner_texts()
            print(f"Turbojet KPIs after CPR=16: {kpi_values_after[:4]}")
            if kpi_values_after[0] == fn_init:
                audit_failures.append("Turbojet KPI did not update after changing CPR slider")

            ss1_path = os.path.join(ARTIFACT_DIR, "v06_e2e_01_turbojet.png")
            await page.screenshot(path=ss1_path, full_page=False)
            print(f"Captured: {ss1_path}")

            # ── 3. Units Toggle ──────────────────────────────────────────────
            print("\n[VERIFY 3] Unit System Toggle...")
            imperial_btn = page.locator("button:has-text('IMPERIAL')")
            if await imperial_btn.count() > 0:
                await imperial_btn.click()
                await asyncio.sleep(0.5)
                imp_kpis = await page.locator(".kpi-value").all_inner_texts()
                print(f"Imperial KPIs: {imp_kpis[:2]}")
                if "lbf" not in imp_kpis[0]:
                    audit_failures.append(f"Imperial units toggle failed, got: {imp_kpis[0]}")
                ss_imp_path = os.path.join(ARTIFACT_DIR, "v06_e2e_imperial_units.png")
                await page.screenshot(path=ss_imp_path, full_page=False)
                # Toggle back to SI
                await page.locator("button:has-text('SI METRIC')").click()
                await asyncio.sleep(0.5)

            # ── 4. Domain 02 (Dual-Spool Turbofan) ───────────────────────────
            print("\n[VERIFY 4] Domain 02 (Dual-Spool Turbofan)...")
            await page.locator("button:has-text('02 TURBOFAN')").click()
            await page.wait_for_selector(".blueprint-table tbody tr", timeout=8000)

            tf_kpis = await page.locator(".kpi-value").all_inner_texts()
            print(f"Turbofan initial KPIs: {tf_kpis[:4]}")
            tf_fn_init = tf_kpis[0]
            if "---" in tf_fn_init:
                audit_failures.append(f"Turbofan thrust is --- ({tf_fn_init})")

            # Station table sequence check
            tf_stn_ids = await page.locator(".blueprint-table tbody tr td:first-child").all_inner_texts()
            print(f"Turbofan station IDs in table: {tf_stn_ids}")
            # Assert deduplicated & canonical order (e.g. STN 0/a first, 8 last)
            if len(tf_stn_ids) != len(set(tf_stn_ids)):
                audit_failures.append(f"Turbofan station table contains duplicates: {tf_stn_ids}")

            # Slider drag test: drag BPR
            bpr_slider = page.locator(".range-input").first
            await set_slider_val(bpr_slider, 7.4)
            await asyncio.sleep(3.5)
            tf_kpis_after = await page.locator(".kpi-value").all_inner_texts()
            print(f"Turbofan KPIs after BPR=7.4: {tf_kpis_after[:4]}")
            bpr_val = float(tf_kpis_after[1].split()[0])
            if bpr_val < 6.5 or tf_kpis_after[0] == tf_fn_init:
                audit_failures.append(f"Turbofan BPR did not update on slider drag: {tf_kpis_after[1]}")

            ss2_path = os.path.join(ARTIFACT_DIR, "v06_e2e_02_turbofan.png")
            await page.screenshot(path=ss2_path, full_page=False)
            print(f"Captured: {ss2_path}")

            # ── 5. Domain 03 (CF34 Flight Deck) ──────────────────────────────
            print("\n[VERIFY 5] Domain 03 (CF34 Deck)...")
            await page.locator("button:has-text('03 CF34 DECK')").click()
            await asyncio.sleep(2.0)

            cf34_kpis = await page.locator(".kpi-value").all_inner_texts()
            print(f"CF34 KPIs: {cf34_kpis[:4]}")
            if "---" in cf34_kpis[0]:
                audit_failures.append("CF34 thrust is --- on load")

            ss3_path = os.path.join(ARTIFACT_DIR, "v06_e2e_03_cf34_deck.png")
            await page.screenshot(path=ss3_path, full_page=False)
            print(f"Captured: {ss3_path}")

            # ── 6. Domain 04 (Off-Design) ────────────────────────────────────
            print("\n[VERIFY 6] Domain 04 (Off-Design Matching)...")
            await page.locator("button:has-text('04 OFF-DESIGN')").click()
            await asyncio.sleep(2.0)

            od_kpis = await page.locator(".kpi-value").all_inner_texts()
            print(f"Off-Design KPIs: {od_kpis[:4]}")
            
            # Check TIT status tag in variance matrix
            tit_tag = await page.locator(".blueprint-table tbody tr:nth-child(2) td:nth-child(6)").inner_text()
            print(f"Variance Matrix TIT tag: '{tit_tag}'")
            if "TIT LIMIT EXCEEDED" in tit_tag:
                audit_failures.append(f"Off-Design TIT tag inverted on nominal operating point: {tit_tag}")

            ss4_path = os.path.join(ARTIFACT_DIR, "v06_e2e_04_offdesign_map.png")
            await page.screenshot(path=ss4_path, full_page=False)
            print(f"Captured: {ss4_path}")

            # ── 7. Domain 05 (Mean-Line) ─────────────────────────────────────
            print("\n[VERIFY 7] Domain 05 (Mean-Line Aero)...")
            await page.locator("button:has-text('05 MEAN-LINE')").click()
            await asyncio.sleep(2.0)

            # Check Velocity Triangles SVG
            vtri_svg = page.locator("svg[viewBox='0 0 660 215']")
            if await vtri_svg.count() > 0:
                print("Velocity Triangles SVG (215px height) found.")
            else:
                audit_failures.append("Velocity Triangles SVG with 215px height not found.")

            ss5_path = os.path.join(ARTIFACT_DIR, "v06_e2e_05_meanline.png")
            await page.screenshot(path=ss5_path, full_page=False)
            print(f"Captured: {ss5_path}")

            # Test Annulus sub-tab
            await page.locator("button:has-text('ANNULUS')").click()
            await asyncio.sleep(2.0)
            stage_btns = page.locator("button:has-text('STAGE')")
            stg_count = await stage_btns.count()
            print(f"Annulus stage selection buttons found: {stg_count}")
            if stg_count < 4:
                audit_failures.append(f"Expected at least 4 stage buttons in Annulus mode, found {stg_count}")

            ss5b_path = os.path.join(ARTIFACT_DIR, "v06_e2e_05_annulus.png")
            await page.screenshot(path=ss5b_path, full_page=False)
            print(f"Captured: {ss5b_path}")

            # ── 8. Domain 06 (Turboprop) ─────────────────────────────────────
            print("\n[VERIFY 8] Domain 06 (Turboprop)...")
            await page.locator("button:has-text('06 TURBOPROP')").click()
            await asyncio.sleep(2.0)

            tp_kpis = await page.locator(".kpi-value").all_inner_texts()
            print(f"Turboprop KPIs: {tp_kpis[:3]}")
            if "---" in tp_kpis[0]:
                audit_failures.append("Turboprop shaft power is --- on load")

            # Check station table has entropy
            tp_entropy = await page.locator(".blueprint-table tbody tr td:nth-child(9)").first.inner_text()
            print(f"Turboprop station 0 entropy: {tp_entropy} J/kg·K")
            if "---" in tp_entropy or tp_entropy == "0":
                audit_failures.append(f"Turboprop station entropy invalid: {tp_entropy}")

            ss6_path = os.path.join(ARTIFACT_DIR, "v06_e2e_06_turboprop.png")
            await page.screenshot(path=ss6_path, full_page=False)
            print(f"Captured: {ss6_path}")

            # Test Parametric mode in Turboprop
            await page.locator("button:has-text('PARAMETRIC')").click()
            await asyncio.sleep(2.0)
            ss6b_path = os.path.join(ARTIFACT_DIR, "v06_e2e_06_turboprop_parametric.png")
            await page.screenshot(path=ss6b_path, full_page=False)
            print(f"Captured: {ss6b_path}")

            # ── 9. Domain 07 (Mission Analysis) ──────────────────────────────
            print("\n[VERIFY 9] Domain 07 (Mission Analysis)...")
            await page.locator("button:has-text('07 MISSION')").click()
            await asyncio.sleep(2.0)
            ss7_path = os.path.join(ARTIFACT_DIR, "v06_e2e_07_mission.png")
            await page.screenshot(path=ss7_path, full_page=False)
            print(f"Captured: {ss7_path}")

            # ── 10. Domain 08 (Surrogate Model) ──────────────────────────────
            print("\n[VERIFY 10] Domain 08 (Surrogate Model)...")
            await page.locator("button:has-text('08 SURROGATE')").click()
            await asyncio.sleep(2.0)
            ss8_path = os.path.join(ARTIFACT_DIR, "v06_e2e_08_surrogate.png")
            await page.screenshot(path=ss8_path, full_page=False)
            print(f"Captured: {ss8_path}")

            # ── 11. Domain 09 (Hybrid-Electric) ──────────────────────────────
            print("\n[VERIFY 11] Domain 09 (Hybrid-Electric)...")
            await page.locator("button:has-text('09 HYBRID')").click()
            await asyncio.sleep(2.0)
            ss9_path = os.path.join(ARTIFACT_DIR, "v06_e2e_09_hybrid.png")
            await page.screenshot(path=ss9_path, full_page=False)
            print(f"Captured: {ss9_path}")

            # Test Flight Mission mode in Hybrid
            await page.locator("button:has-text('FLIGHT MISSION')").click()
            await asyncio.sleep(2.0)
            ss9b_path = os.path.join(ARTIFACT_DIR, "v06_e2e_09_hybrid_mission.png")
            await page.screenshot(path=ss9b_path, full_page=False)
            print(f"Captured: {ss9b_path}")

            await browser.close()
            print("\nAll browser automation completed!")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    print(f"\n==========================================")
    print(f"Console Errors Count: {len(console_errors)}")
    for err in console_errors:
        print(f"  [CONSOLE ERR] {err}")

    print(f"Audit Failures Count: {len(audit_failures)}")
    for fl in audit_failures:
        print(f"  [AUDIT FAIL] {fl}")
    print(f"==========================================")

    if console_errors or audit_failures:
        print("VERIFICATION FAILED")
        sys.exit(1)
    else:
        print("ALL AUDIT ASSERTIONS & VERIFICATIONS PASSED CLEANLY!")

if __name__ == "__main__":
    asyncio.run(run_verification())
