"""
test_physics.py
Comprehensive physics validation and API integration test suite
for the Gas Turbine Engine Simulator.
"""

import math
import pytest
import numpy as np
from fastapi.testclient import TestClient

import ISA_module as ISA
import engine_helper as eh
from turbojet import calc_thrust, DEFAULT_ENG_PARAM, DEFAULT_ENG_PERF
from physics_turbofan import calc_turbofan, DEFAULT_TF_PARAM, DEFAULT_TF_PERF
from turbofan import interp_altMNPC, get_envelope
from main import app, _sanitize


# =============================================================================
# 1. Atmospheric Physics Tests (ISA Module)
# =============================================================================

def test_isa_sea_level():
    """Verify standard sea level values match ICAO definitions."""
    p_sl = ISA.p(0.0)
    T_sl = ISA.T(0.0)
    rho_sl = ISA.rho(0.0)

    assert math.isclose(p_sl, 101325.0, rel_tol=1e-4), f"SL pressure was {p_sl}"
    assert math.isclose(T_sl, 288.15, rel_tol=1e-4), f"SL temperature was {T_sl}"
    assert math.isclose(rho_sl, 1.225, rel_tol=1e-3), f"SL density was {rho_sl}"


def test_isa_tropopause_continuity():
    """Verify temperature and pressure are continuous across the tropopause boundary."""
    h_tropo = 36089.24  # ft
    eps = 0.05  # ft

    T_below = ISA.T(h_tropo - eps)
    T_above = ISA.T(h_tropo + eps)
    assert math.isclose(T_below, 216.65, abs_tol=0.1), f"T below tropopause was {T_below}"
    assert math.isclose(T_above, 216.65, abs_tol=0.1), f"T above tropopause was {T_above}"
    assert math.isclose(T_below, T_above, abs_tol=0.01), "Temperature jump detected at tropopause"

    p_below = ISA.p(h_tropo - eps)
    p_above = ISA.p(h_tropo + eps)
    assert math.isclose(p_below, p_above, rel_tol=1e-3), "Pressure jump detected at tropopause"


def test_isa_stratosphere_isothermal():
    """Verify stratosphere is isothermal at 216.65 K up to 65,000 ft."""
    for alt in [40000.0, 50000.0, 60000.0]:
        t = ISA.T(alt)
        assert math.isclose(t, 216.65, abs_tol=0.05), f"Altitude {alt} ft temperature was {t} K"


def test_isa_speed_conversions():
    """Verify round-trip airspeed conversions (Mach <-> Calibrated Airspeed)."""
    alt = 25000.0
    M_orig = 0.75
    Vc = ISA.M2Vc(M_orig, alt)
    M_roundtrip = ISA.Vc2M(Vc, alt)
    assert math.isclose(M_orig, M_roundtrip, rel_tol=1e-4)


# =============================================================================
# 2. Component Aerothermodynamics Tests (engine_helper)
# =============================================================================

def test_isentropic_relations():
    """Verify stagnation-static pressure and temperature functions."""
    gamma = 1.4
    M = 0.8
    Ts = 250.0
    Ps = 50000.0

    T0 = eh.get_T(Ts, gamma, M)
    P0 = eh.get_p(Ps, gamma, M)

    expected_T0 = Ts * (1.0 + 0.2 * M**2)
    expected_P0 = Ps * (1.0 + 0.2 * M**2) ** 3.5

    assert math.isclose(T0, expected_T0, rel_tol=1e-5)
    assert math.isclose(P0, expected_P0, rel_tol=1e-5)

    # Invert
    Ts_calc = eh.get_Ts(T0, gamma, M)
    Ps_calc = eh.get_ps(P0, Ts_calc, T0, gamma)
    assert math.isclose(Ts_calc, Ts, rel_tol=1e-5)
    assert math.isclose(Ps_calc, Ps, rel_tol=1e-5)


def test_choked_nozzle():
    """Verify convergent nozzle choking logic and critical pressure ratio."""
    gas = eh.ct.Solution(eh.REACTION_MECHANISM, eh.PHASE_NAME)
    gas.TPX = 800.0, 300000.0, eh.COMP_AIR
    gas_out = eh.ct.Solution(eh.REACTION_MECHANISM, eh.PHASE_NAME)

    # Ambient pressure low enough to guarantee choking
    p_amb_choked = 101325.0
    choked, mdot, M_out, F = eh.calc_nozzle(
        gas_in=gas, M_in=0.3, eta_noz=0.98,
        p_amb=p_amb_choked, A_star=0.2, V_i=100.0, gas_out=gas_out
    )
    assert choked is True
    assert math.isclose(M_out, 1.0, abs_tol=1e-4)
    assert mdot > 0.0
    assert F > 0.0


# =============================================================================
# 3. Single-Spool Turbojet Physics Tests
# =============================================================================

def test_turbojet_nominal_convergence():
    """Verify single-spool turbojet on-design convergence and performance metrics."""
    res = calc_thrust(DEFAULT_ENG_PARAM, DEFAULT_ENG_PERF, throttle_pos=1.0, alt=30000.0, M_i=0.7)

    assert res["converged"] is True
    assert res["T"] > 0.0, "Thrust must be positive"
    assert res["TSFC"] > 0.0, "TSFC must be positive"
    assert res["mdot_fuel"] > 0.0, "Fuel mass flow must be positive"
    assert res["mdot_air"] > 0.0, "Air mass flow must be positive"

    # Verify station entropy generation across compressor
    s2 = res["stations"]["2"]["s_JkgK"]
    s3 = res["stations"]["3"]["s_JkgK"]
    assert s3 > s2, "Compressor irreversibility must increase entropy (s3 > s2)"

    # Verify emissions indices exist and are positive/non-negative
    em = res["stations"]["4"]["combustion_metrics"]["emissions_EI"]
    assert "NOx" in em and "CO" in em and "CO2" in em
    assert em["CO2"] > 0.0
    assert em["NOx"] >= 0.0


def test_turbojet_tit_bisection_limiter():
    """Verify binary bisection clamps TIT strictly to T_max."""
    perf = DEFAULT_ENG_PERF.copy()
    perf["T_max"] = 1100.0  # Force throttling below nominal 1200+ K

    res = calc_thrust(DEFAULT_ENG_PARAM, perf, throttle_pos=1.0, alt=0.0, M_i=0.0)

    assert res["converged"] is True
    assert res["T_max_limited"] is True
    T4 = res["stations"]["4"]["T_K"]
    assert T4 <= 1100.5, f"TIT was {T4} K, which exceeds T_max of 1100 K"


# =============================================================================
# 4. Multi-Spool Physics Turbofan Tests
# =============================================================================

def test_physics_turbofan_nominal():
    """Verify two-spool turbofan convergence, thrust split, and BPR matching."""
    res = calc_turbofan(DEFAULT_TF_PARAM, DEFAULT_TF_PERF, throttle_pos=1.0, alt=35000.0, M_i=0.8)

    assert res["converged"] is True
    assert res["T"] > 0.0
    assert res["T_core"] > 0.0
    assert res["T_byp"] > 0.0
    assert math.isclose(res["T"], res["T_core"] + res["T_byp"], rel_tol=1e-3)

    # Verify bypass ratio matches commanded parameter
    assert math.isclose(res["BPR"], DEFAULT_TF_PARAM["BPR"], rel_tol=0.05)
    assert res["A18_calc"] > 0.0, "Required bypass nozzle area must be calculated"

    # Verify core and bypass stations are present
    st = res["stations"]
    for sid in ["a", "1", "2", "13", "21", "3", "4", "41", "5", "8", "18"]:
        assert sid in st, f"Missing station {sid} in turbofan stations dictionary"


def test_physics_turbofan_enthalpy_exhaustion_guard():
    """Verify that unphysically excessive BPR fails gracefully without crashing."""
    param = DEFAULT_TF_PARAM.copy()
    param["BPR"] = 25.0  # Extreme BPR that demands more LPT work than entering enthalpy

    res = calc_turbofan(param, DEFAULT_TF_PERF, throttle_pos=1.0, alt=35000.0, M_i=0.8)
    assert res["converged"] is False


# =============================================================================
# 5. Data-Driven Turbofan (CF34 Deck) Tests
# =============================================================================

def test_cf34_deck_interpolation():
    """Verify trilinear interpolation over the CF34 engine deck."""
    env = get_envelope()
    assert "alt_ft" in env and "MN_approx" in env and "PC" in env

    pt = interp_altMNPC(Hp=35000.0, MN=0.8, PC=1.0)
    assert "Fn" in pt
    assert "Wf" in pt
    assert pt["Fn"] > 0.0


# =============================================================================
# 6. FastAPI Backend Integration Tests
# =============================================================================

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_check(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("online", "ok")


def test_turbojet_defaults_endpoint(client):
    r = client.get("/api/turbojet/defaults")
    assert r.status_code == 200
    data = r.json()
    assert "eng_param" in data and "eng_perf" in data


def test_physics_turbofan_defaults_endpoint(client):
    r = client.get("/api/physics_turbofan/defaults")
    assert r.status_code == 200
    data = r.json()
    assert "eng_param" in data and "eng_perf" in data


def test_physics_turbofan_ts_diagram_endpoint(client):
    r = client.post("/api/physics_turbofan/ts_diagram", json={"alt": 35000, "M_i": 0.8})
    assert r.status_code == 200
    data = r.json()
    assert "points" in data
    assert len(data["points"]) == 11
    # Check that stream labels exist
    streams = {p["stream"] for p in data["points"]}
    assert "core" in streams and "bypass" in streams


def test_physics_turbofan_sweep_and_csv_endpoints(client):
    payload = {
        "sweep_param": "bpr",
        "bpr_start": 4.0,
        "bpr_end": 5.0,
        "n_steps": 3,
        "fixed_alt": 35000.0,
        "fixed_mach": 0.8,
    }
    r = client.post("/api/physics_turbofan/sweep", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["sweep_param"] == "bpr"
    assert len(data["points"]) == 3

    # CSV
    r_csv = client.post("/api/physics_turbofan/sweep/csv", json=payload)
    assert r_csv.status_code == 200
    lines = r_csv.text.strip().splitlines()
    assert len(lines) == 4  # header + 3 data rows
    assert "T_core" in lines[0] and "T_byp" in lines[0]
