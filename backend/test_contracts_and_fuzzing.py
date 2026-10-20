"""
test_contracts_and_fuzzing.py — Stage 4 Contract & Fuzzing Verification Suite
Validates that every endpoint's response matches its contract and metadata schema,
invalid input returns a structured 4xx (never 500), and responses never contain NaN/Infinity in JSON.
"""

import math
import json
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def assert_clean_json_no_nan_or_inf(data):
    """Recursively assert that data contains only finite numbers and RFC 8259 valid JSON."""
    if isinstance(data, float):
        assert not math.isnan(data), f"Forbidden NaN found in JSON: {data}"
        assert not math.isinf(data), f"Forbidden Infinity found in JSON: {data}"
    elif isinstance(data, dict):
        for k, v in data.items():
            assert_clean_json_no_nan_or_inf(v)
    elif isinstance(data, (list, tuple)):
        for item in data:
            assert_clean_json_no_nan_or_inf(item)


def assert_standard_solver_metadata(data):
    """Assert standard Stage 4.1 solver telemetry exists on response."""
    assert "status" in data, f"Missing 'status' in response: {list(data.keys())}"
    assert data["status"] in ("ok", "infeasible", "error")
    assert "converged" in data
    assert "residual_norm" in data
    assert "iterations" in data
    assert "warnings" in data
    assert "clamped_inputs" in data
    assert "fidelity_level" in data
    assert "model_version" in data


# ==============================================================================
# 1. Valid Response Schema & Telemetry Contract Tests (All 9 Modules)
# ==============================================================================

def test_module01_turbojet_contract():
    r_def = client.get("/api/turbojet/defaults")
    assert r_def.status_code == 200
    defaults = r_def.json()
    assert_clean_json_no_nan_or_inf(defaults)
    
    payload = {
        "eng_param": defaults["eng_param"],
        "eng_perf": defaults["eng_perf"],
        "throttle_pos": 1.0,
        "alt": 0.0,
        "M_i": 0.0
    }
    r = client.post("/api/turbojet/single", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "T" in data or "thrust_net_kN" in data
    assert_standard_solver_metadata(data)


def test_module02_turbofan_contract():
    r_def = client.get("/api/physics_turbofan/defaults")
    assert r_def.status_code == 200
    defaults = r_def.json()
    assert_clean_json_no_nan_or_inf(defaults)
    
    payload = {
        "eng_param": defaults["eng_param"],
        "throttle_pos": 1.0,
        "alt": 0.0,
        "M_i": 0.0
    }
    r = client.post("/api/physics_turbofan/single", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "T" in data or "thrust_net_kN" in data
    assert_standard_solver_metadata(data)


def test_module03_cf34_deck_contract():
    payload = {"alt": 15000.0, "MN": 0.65, "PC": 0.85}
    r = client.post("/api/cf34/single", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "Fn" in data or "Fg" in data
    assert_standard_solver_metadata(data)


def test_module04_off_design_contract():
    r_def = client.get("/api/off_design/defaults")
    assert r_def.status_code == 200
    defaults = r_def.json()
    assert_clean_json_no_nan_or_inf(defaults)
    
    payload = {
        "N_rel": 1.0,
        "alt": 0.0,
        "mach": 0.0
    }
    r = client.post("/api/off_design/single", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "CPR" in data or "N_rel" in data
    assert_standard_solver_metadata(data)


def test_module05_meanline_compressor_contract():
    payload = {
        "U_mid": 300.0,
        "Ca": 150.0,
        "r_mean": 0.35,
        "alpha1_deg": 15.0,
        "beta2_deg": 20.0,
        "eta_stage": 0.88,
        "T01": 288.15,
        "P01": 101325.0,
        "aspect_ratio": 2.0,
        "solidity": 1.2
    }
    r = client.post("/api/meanline/compressor_stage", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "PR_stage" in data or "stage_pr" in data
    assert_standard_solver_metadata(data)


def test_module06_turboprop_contract():
    r_def = client.get("/api/turboprop/defaults")
    assert r_def.status_code == 200
    defaults = r_def.json()
    assert_clean_json_no_nan_or_inf(defaults)
    
    payload = {
        "alt": 0.0,
        "mach": 0.0,
        "CPR": 10.0,
        "TIT": 1350.0,
        "air_flow": 5.0
    }
    r = client.post("/api/turboprop/single", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "P_shaft_kW" in data or "SHP" in data
    assert_standard_solver_metadata(data)


def test_module07_mission_contract():
    payload = {
        "aircraft_type": "generic_twin",
        "cruise_alt_m": 10668.0,
        "cruise_dist_km": 2500.0
    }
    r = client.post("/api/mission/simulate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "mission_summary" in data or "flight_profile" in data
    assert_standard_solver_metadata(data)


def test_module08_surrogate_contract():
    payload = {
        "inputs": {
            "altitude_m": 10668.0,
            "mach": 0.8,
            "throttle": 1.0,
            "cpr": 14.0,
            "tit": 1450.0
        }
    }
    r = client.post("/api/surrogate/predict", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "thrust_kN" in data or "Thrust_kN" in data
    assert_standard_solver_metadata(data)


def test_module09_hybrid_contract():
    payload = {
        "hybrid_type": "parallel",
        "shaft_power_req_kW": 2500.0,
        "electrical_power_share": 0.20,
        "battery_mass_kg": 1500.0,
        "battery_specific_energy_Wh_kg": 250.0,
        "battery_soc_initial": 0.90,
        "motor_efficiency": 0.95,
        "inverter_efficiency": 0.97,
        "generator_efficiency": 0.94,
        "gearbox_efficiency": 0.98,
        "flight_duration_min": 45.0,
        "gas_turbine_eta_thermal": 0.38,
        "fuel_lhv_MJ_kg": 43.1
    }
    r = client.post("/api/hybrid/single", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert_clean_json_no_nan_or_inf(data)
    assert "shaft_power_req_kW" in data or "battery_power_kW" in data
    assert_standard_solver_metadata(data)


# ==============================================================================
# 2. Malformed-Input Fuzzing Tests (Never 500, Always Structured 4xx)
# ==============================================================================

FUZZ_CASES = [
    # Case 1: Bad JSON structure
    ("/api/turbojet/single", {"eng_param": "not_a_dict"}),
    # Case 2: Extreme unphysical bounds violating Pydantic schema
    ("/api/turbojet/single", {
        "eng_param": {"CPR": -999.0, "TIT": -100.0, "mass_flow": 0.0, "eta_comp": 99.0, "eta_turb": 0.0, "eta_comb": 0.0, "eta_mech": 0.0, "eta_noz": 0.0},
        "eng_perf": {"net_thrust": 0.0, "fuel_flow": 0.0, "tsfc": 0.0, "thermal_efficiency": 0.0},
        "throttle_pos": -5.0, "alt": 9999999.0, "M_i": 50.0
    }),
    # Case 3: Invalid type in turbofan
    ("/api/physics_turbofan/single", {"throttle_pos": "wide_open_throttle", "alt": -99999.0}),
    # Case 4: Invalid power code in CF34 deck
    ("/api/cf34/single", {"alt": -5000.0, "MN": 5.0, "PC": -0.5}),
    # Case 5: Negative speed in off-design
    ("/api/off_design/single", {"N_rel": -5.0, "alt": 999999.0}),
    # Case 6: Negative geometry in meanline
    ("/api/meanline/compressor_stage", {"U_mid": -100.0, "Ca": 0.0, "r_mean": -1.0}),
    # Case 7: Extreme Mach in turboprop
    ("/api/turboprop/single", {"mach": 25.0, "CPR": -0.1, "TIT": 50.0}),
    # Case 8: Unrecognized mission type
    ("/api/mission/simulate", {"aircraft_type": 12345, "cruise_alt_m": "high"}),
    # Case 9: Bad hybrid split
    ("/api/hybrid/single", {"hybrid_type": "unknown_hybrid", "shaft_power_req_kW": "none"})
]


@pytest.mark.parametrize("endpoint,bad_payload", FUZZ_CASES)
def test_fuzzing_endpoints_never_return_500(endpoint, bad_payload):
    """
    Fuzzing verification required by Stage 4.3:
    Every invalid/malformed request must return 400 or 422, NEVER 500,
    and the error response must be structured JSON.
    """
    r = client.post(endpoint, json=bad_payload)
    assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code} on {endpoint}: {r.text}"
    assert r.status_code != 500, f"Server returned 500 Internal Server Error on {endpoint}!"
    
    # Must be valid JSON
    try:
        err_json = r.json()
    except Exception as e:
        pytest.fail(f"Error response on {endpoint} was not valid JSON: {r.text}")
        
    assert_clean_json_no_nan_or_inf(err_json)
    assert "detail" in err_json or "error" in err_json or "status" in err_json
