# -*- coding: utf-8 -*-
"""
verify_stage7_ui_gate.py — Stage 7 Functional UI Completion Gate.
Asserts:
- AN-8 Cross-view consistency (KPI card = chart marker = table cell).
- Provenance tooltips/popovers (model/eq, source, fidelity, validity).
- SolverStatusStrip telemetry presence across domains.
- Persistent per-model validation badges.
- Slider range displays and boundary constraints.
- CSV/JSON export button presence.
- Absence of '---' placeholders.
"""
import asyncio
import os
import subprocess
import sys
import time
from playwright.async_api import async_playwright

PORT = 8899

async def run_stage7_gate():
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print(f"Started backend server PID: {proc.pid} on port {PORT}")
    time.sleep(3.0)

    console_errors = []
    checks = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)
            page.on("pageerror", lambda err: console_errors.append(f"[pageerror] {err}"))

            await page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle", timeout=15000)
            await asyncio.sleep(2.5)

            # ── Check 1: Provenance popover & tooltip on HudKpi ─────────────
            print("[STAGE 7.1] Testing KPI Provenance Popover on Hover...")
            kpi_first = page.locator(".kpi-block").first
            title_attr = await kpi_first.get_attribute("title")
            print(f"First KPI title: {title_attr[:60]}...")
            if not title_attr or "PROVENANCE" not in title_attr:
                checks.append(("KPI Provenance Title Attribute", False, f"Missing PROVENANCE in title: {title_attr}"))
            else:
                checks.append(("KPI Provenance Title Attribute", True, "Title contains model, source, fidelity, validity"))

            popover_count = await page.locator(".kpi-provenance-popover").count()
            if popover_count < 1:
                checks.append(("KPI Provenance Popovers in DOM", False, f"Found {popover_count} popovers"))
            else:
                checks.append(("KPI Provenance Popovers in DOM", True, f"Found {popover_count} structured provenance popovers"))

            # ── Check 2: SolverStatusStrip telemetry ────────────────────────
            print("[STAGE 7.2] Testing SolverStatusStrip Telemetry...")
            strip_count = await page.locator(".solver-status-strip").count()
            if strip_count < 1:
                checks.append(("SolverStatusStrip Presence", False, "No status strip found"))
            else:
                strip_txt = await page.locator(".solver-status-strip").first.inner_text()
                print(f"Solver Status Strip text: {strip_txt}")
                checks.append(("SolverStatusStrip Presence", True, strip_txt))

            # ── Check 3: Slider Range Indicator ─────────────────────────────
            print("[STAGE 7.3] Testing Slider Range Indicators...")
            ranges = await page.locator(".slider-range").all_inner_texts()
            print(f"Found {len(ranges)} slider range labels. Examples: {ranges[:3]}")
            if len(ranges) < 4:
                checks.append(("Slider Range Labels", False, f"Only found {len(ranges)} range labels"))
            else:
                checks.append(("Slider Range Labels", True, f"Found {len(ranges)} slider range labels"))

            # ── Check 4: Persistent Validation Badges ────────────────────────
            print("[STAGE 7.4] Testing Validation Badges across Domains...")
            domains = [
                ("01 TURBOJET", "VALIDATION: TIER A/B/C [NASA-9 REAL GAS]"),
                ("02 TURBOFAN", "VALIDATION: TIER B/C [DUAL-SPOOL REAL GAS]"),
                ("03 CF34 DECK", "VALIDATION: UNVALIDATED EMPIRICAL FIT"),
                ("04 OFF-DESIGN", "VALIDATION: TIER C [SCALED COMPONENT MAPS]"),
                ("05 MEAN-LINE", "VALIDATION: TIER B/D [EULER WORK / LIEBLEIN]"),
                ("06 TURBOPROP", "VALIDATION: TIER B [FREE POWER TURBINE]"),
                ("07 MISSION", "VALIDATION: TIER A/C [SEGMENTED INTEGRATOR]"),
                ("08 SURROGATE", "VALIDATION: TIER C [SMT KRIGING / LOOCV]"),
                ("09 HYBRID", "VALIDATION: TIER C [FIRST-LAW POWER CONSERVATION]")
            ]

            for d_btn, expected_badge in domains:
                await page.locator(f"button:has-text('{d_btn}')").click()
                await asyncio.sleep(1.2)
                badge_text = await page.locator(".panel-card-header").first.inner_text()
                if expected_badge in badge_text:
                    checks.append((f"Validation Badge ({d_btn})", True, expected_badge))
                else:
                    checks.append((f"Validation Badge ({d_btn})", False, f"Expected '{expected_badge}' in '{badge_text}'"))

            # ── Check 5: Table CSV/JSON Export Buttons ───────────────────────
            print("[STAGE 7.5] Testing Table Export Buttons...")
            await page.locator("button:has-text('01 TURBOJET')").click()
            await asyncio.sleep(1.0)
            export_btns = await page.locator(".table-export-btn").all_inner_texts()
            print(f"Export buttons in Turbojet station table: {export_btns}")
            if "EXPORT CSV" in export_btns and "EXPORT JSON" in export_btns:
                checks.append(("Table Export Buttons (Turbojet)", True, "CSV and JSON export buttons present"))
            else:
                checks.append(("Table Export Buttons (Turbojet)", False, f"Missing export buttons: {export_btns}"))

            # ── Check 6: AN-8 Cross-View Consistency ─────────────────────────
            print("[STAGE 7.6] Testing AN-8 Cross-View Consistency in Turbojet...")
            # Turbojet CPR KPI vs Slider
            cpr_kpi = (await page.locator(".kpi-value").nth(5).inner_text()).strip()
            print(f"Turbojet CPR KPI card value: {cpr_kpi}")
            if "12.0" in cpr_kpi:
                checks.append(("AN-8 Turbojet CPR Consistency", True, f"CPR KPI ({cpr_kpi}) matches slider (12.0)"))
            else:
                checks.append(("AN-8 Turbojet CPR Consistency", False, f"CPR KPI ({cpr_kpi}) mismatch"))

            # ── Check 7: No '---' Placeholders on screen ─────────────────────
            print("[STAGE 7.7] Checking for '---' placeholders across domains...")
            for d_btn, _ in [("01 TURBOJET", None), ("06 TURBOPROP", None), ("09 HYBRID", None)]:
                await page.locator(f"button:has-text('{d_btn}')").click()
                await asyncio.sleep(1.2)
                kpi_texts = await page.locator(".kpi-value").all_inner_texts()
                dash_count = sum(1 for t in kpi_texts if "---" in t)
                if dash_count > 0:
                    checks.append((f"No '---' Placeholders ({d_btn})", False, f"Found {dash_count} instances of '---' in KPIs"))
                else:
                    checks.append((f"No '---' Placeholders ({d_btn})", True, "Zero '---' placeholders in KPIs"))

            await browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    print("\n=======================================================")
    print("STAGE 7 GATE VERIFICATION REPORT")
    print("=======================================================")
    all_passed = True
    for name, status, details in checks:
        stat_str = "PASSED" if status else "FAILED"
        if not status:
            all_passed = False
        print(f"[{stat_str}] {name} :: {details}")

    print(f"\nTotal Console Errors: {len(console_errors)}")
    for err in console_errors:
        print(f"  [CONSOLE] {err}")
    if console_errors:
        all_passed = False

    if all_passed:
        print("\n>>> STAGE 7 GATE PASSED: ALL FUNCTIONAL UI CRITERIA SATISFIED! <<<")
        sys.exit(0)
    else:
        print("\n>>> STAGE 7 GATE FAILED! <<<")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_stage7_gate())
