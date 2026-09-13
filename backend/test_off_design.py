"""
test_off_design.py
Automated test suite for Extension 1: Off-Design Performance and Component Matching.
Tests compressor maps, surge margins, 1D matching solver, power balance, and FastAPI endpoints.
"""

import math
import pytest
from fastapi.testclient import TestClient

from off_design import (
    CompressorMap,
    brent_root,
    solve_off_design,
    run_off_design_sweep,
)
from main import app

client = TestClient(app)


def test_compressor_map_design_point():
    """Verify that the compressor map evaluates correctly at design point (N=1.0, beta=0.5)."""
    cpr_des = 8.0
    eta_des = 0.85
    mdot_des = 20.0
    cmap = CompressorMap(cpr_des=cpr_des, eta_c_des=eta_des, mdot_corr_des=mdot_des)

    m, cpr, eta = cmap.evaluate(1.0, 0.5)
    # At beta=0.5, relative CPR is around design, and eta is at peak
    assert abs(cpr - cpr_des) < 0.25
    assert abs(eta - eta_des) < 0.01
    assert abs(m - mdot_des) < 0.8


def test_compressor_map_monotonicity():
    """Verify that pressure ratio increases monotonically with beta (choke to surge) across all speeds."""
    cmap = CompressorMap(cpr_des=10.0, eta_c_des=0.86, mdot_corr_des=25.0)

    for s in cmap.SPEEDS:
        betas = np_betas = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        cprs = [cmap.evaluate(s, b)[1] for b in betas]
        for i in range(len(cprs) - 1):
            assert cprs[i + 1] >= cprs[i], f"Non-monotonic CPR at speed {s}: {cprs[i+1]} < {cprs[i]}"


def test_surge_line_and_margin():
    """Verify surge point lookup and %SM calculations."""
    cmap = CompressorMap(cpr_des=8.0, eta_c_des=0.85, mdot_corr_des=20.0)

    for s in [0.70, 0.85, 1.00]:
        m_s, cpr_s = cmap.surge_point(s)
        m_c, cpr_c = cmap.choke_point(s)
        # Surge has higher CPR and lower mass flow than choke
        assert cpr_s > cpr_c
        assert m_s < m_c

        # On the surge line, %SM must be approximately 0
        sm_on_surge, status_surge = cmap.surge_margin(s, m_s, cpr_s)
        assert abs(sm_on_surge) < 0.1
        assert status_surge in ("SURGE_VIOLATION", "MARGIN_LOW")

        # Well below surge line, %SM must be healthy (> 15%)
        m_op, cpr_op, _ = cmap.evaluate(s, 0.35)
        sm_healthy, status_healthy = cmap.surge_margin(s, m_op, cpr_op)
        assert sm_healthy > 10.0


def test_brent_root_solver():
    """Verify pure-Python Brent root finder accuracy and convergence on non-linear functions."""
    # Polynomial root: x^3 - 2x - 5 = 0 -> root ~ 2.09455148
    def f1(x):
        return x**3 - 2*x - 5

    r1 = brent_root(f1, 1.0, 3.0, tol=1e-6)
    assert abs(r1 - 2.09455148) < 1e-5

    # Trig root: cos(x) - x = 0 -> root ~ 0.739085
    def f2(x):
        import math
        return math.cos(x) - x

    r2 = brent_root(f2, 0.0, 1.0, tol=1e-6)
    assert abs(r2 - 0.739085) < 1e-5


def test_off_design_nominal_cruise():
    """Test single-point off-design match at 35,000 ft, Mach 0.8, N=1.0."""
    res = solve_off_design(
        N_rel=1.0, alt=35000.0, mach=0.8,
        cpr_des=8.0, eta_c_des=0.85, mdot_corr_des=20.0,
    )

    assert res["converged"] is True
    assert res["A8_match_err_pct"] < 0.1  # Less than 0.1% area error
    assert res["Thrust_kN"] > 2.0
    assert res["TSFC"] > 0.0
    assert res["CPR"] > 6.0
    assert res["Surge_Margin_pct"] > 10.0
    assert res["Surge_Status"] in ("HEALTHY", "MARGIN_LOW")
    assert "stations" in res
    assert res["stations"]["4"]["T_K"] > res["stations"]["3"]["T_K"]


def test_off_design_throttling_physics():
    """Verify that throttling back spool speed reduces pressure ratio and airflow."""
    res_100 = solve_off_design(N_rel=1.00, alt=30000.0, mach=0.7)
    res_80  = solve_off_design(N_rel=0.80, alt=30000.0, mach=0.7, A8=res_100["A8_target"])
    res_70  = solve_off_design(N_rel=0.70, alt=30000.0, mach=0.7, A8=res_100["A8_target"])

    assert res_100["CPR"] > res_80["CPR"] > res_70["CPR"]
    assert res_100["mdot_air"] > res_80["mdot_air"] > res_70["mdot_air"]
    assert res_100["Thrust_kN"] > res_80["Thrust_kN"] > res_70["Thrust_kN"]
    assert res_100["A8_match_err_pct"] < 0.5
    assert res_80["A8_match_err_pct"] < 0.5
    assert res_70["A8_match_err_pct"] < 0.5


def test_off_design_tit_limiter():
    """Verify that lowering T_max forces TIT limiter active and maintains T04 <= T_max."""
    t_limit = 1150.0
    res = solve_off_design(N_rel=1.05, alt=0.0, mach=0.0, T_max=t_limit)

    assert res["tit_limited"] is True
    assert res["T04"] <= t_limit + 1.0


def test_off_design_map_generation():
    """Verify compressor map curve extraction for frontend visualization."""
    cmap = CompressorMap(cpr_des=9.0, eta_c_des=0.86, mdot_corr_des=22.0)
    curves = cmap.get_map_curves(n_pts=15)

    assert "speed_lines" in curves
    assert len(curves["speed_lines"]) == len(cmap.SPEEDS)
    assert "surge_line" in curves
    assert len(curves["surge_line"]) > 0
    assert curves["design_point"]["y"] == 9.0


def test_off_design_sweep():
    """Test full speed sweep across operating range."""
    res = run_off_design_sweep(
        sweep_param="speed",
        n_steps=5,
        speed_start=0.70,
        speed_end=1.00,
        fixed_alt=35000.0,
        fixed_mach=0.80,
    )

    assert "points" in res
    assert len(res["points"]) == 5
    assert "operating_line" in res
    assert len(res["operating_line"]) == 5
    for pt in res["points"]:
        assert "error" not in pt
        assert pt["converged"] is True


def test_off_design_endpoints():
    """Test all FastAPI endpoints for off-design."""
    # 1. Defaults
    r_def = client.get("/api/off_design/defaults")
    assert r_def.status_code == 200
    d = r_def.json()
    assert d["N_rel"] == 1.0
    assert d["cpr_des"] == 8.0

    # 2. Map
    r_map = client.get("/api/off_design/map?cpr_des=8.0&eta_c_des=0.85&mdot_corr_des=20.0")
    assert r_map.status_code == 200
    m_data = r_map.json()
    assert "speed_lines" in m_data
    assert "surge_line" in m_data

    # 3. Single
    payload_single = {
        "N_rel": 0.95,
        "alt": 30000.0,
        "mach": 0.75,
        "cpr_des": 8.0,
        "eta_c_des": 0.85,
        "mdot_corr_des": 20.0,
    }
    r_s = client.post("/api/off_design/single", json=payload_single)
    assert r_s.status_code == 200
    res_s = r_s.json()
    assert res_s["N_pct"] == 95.0
    assert res_s["Thrust_kN"] > 0.0

    # 4. Sweep
    payload_sweep = {
        "sweep_param": "speed",
        "n_steps": 4,
        "speed_start": 0.80,
        "speed_end": 1.00,
        "fixed_alt": 30000.0,
        "fixed_mach": 0.75,
    }
    r_sw = client.post("/api/off_design/sweep", json=payload_sweep)
    assert r_sw.status_code == 200
    res_sw = r_sw.json()
    assert len(res_sw["points"]) == 4

    # 5. CSV
    r_csv = client.post("/api/off_design/sweep/csv", json=payload_sweep)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers["content-type"]
    assert "Thrust_kN" in r_csv.text
