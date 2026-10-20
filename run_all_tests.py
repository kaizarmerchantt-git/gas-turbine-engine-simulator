#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_all_tests.py — AETHER-X Unified Test Runner
Executes backend pytest suites, contract checks, and verification gates.
"""

import os
import sys
import subprocess
import time

def run_suite():
    proj_root = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(proj_root, "backend")

    print("=" * 70)
    print("  AETHER-X UNIFIED TEST SUITE RUNNER")
    print("=" * 70)

    t0 = time.time()
    cmd = [sys.executable, "-m", "pytest", backend_dir, "-v"]
    print(f"Executing: {' '.join(cmd)}")

    proc = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True, encoding="utf-8")
    duration = time.time() - t0

    print(proc.stdout)
    if proc.stderr:
        print("STDERR:")
        print(proc.stderr)

    status = "PASSED" if proc.returncode == 0 else "FAILED"
    print("=" * 70)
    print(f"  RESULT: {status} in {duration:.2f}s (Exit Code: {proc.returncode})")
    print("=" * 70)

    sys.exit(proc.returncode)

if __name__ == "__main__":
    run_suite()
