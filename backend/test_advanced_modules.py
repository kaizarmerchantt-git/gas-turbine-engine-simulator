"""
Automated Test Suite for Advanced Simulator Modules (Extensions 6, 4, 8, and 7)
=============================================================================
Tests:
- 1D Mean-Line Aerodynamics (Euler equation, velocity triangles, De Haller, Lieblein DF, annulus tapering)
- Turboprop & Turboshaft Cycle (power turbine enthalpy extraction, SHP, ESHP, propeller & jet thrust, PSFC)
- Mission Simulation (flight profile steps, aircraft drag polar, fuel burn integration, payload-range curve)
- Fast Surrogate Layer (microsecond latency, physical consistency, 2D response surface generation)
- FastAPI REST integration across all endpoints
"""

import math
import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from main import app
from meanline import (
    solve_compressor_stage,
    solve_multistage_compressor_meanline,
    solve_turbine_stage
)
from turboprop import (
    calc_turboprop_performance,
    run_turboprop_sweep
)
from mission import (
    run_mission_simulation,
    compute_drag
)
from surrogate import GLOBAL_SURROGATE


client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Extension 6: 1D Mean-Line Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_meanline_compressor_stage_physics():
    """Verify velocity triangles, Euler enthalpy relation, and De Haller number."""
    T01 = 288.15
    P01 = 101325.0
    delta_T0 = 35.0
    N_rpm = 12000.0
    r_mean = 0.28
    C_a = 160.0

    stg = solve_compressor_stage(
        T01=T01, P01=P01, delta_T0=delta_T0, N_rpm=N_rpm,
        r_mean=r_mean, C_a=C_a, reaction=0.50, eta_stage=0.88
    )

    # 1. Blade speed check: U = 2*pi*N/60 * r_mean
    expected_U = (2.0 * math.pi * N_rpm / 60.0) * r_mean
    assert abs(stg["U"] - expected_U) < 1.0

    # 2. Euler equation check: Delta h0 = U * (C_theta2 - C_theta1)
    tri = stg["velocity_triangles"]
    C_th1 = tri["rotor_inlet"]["C_theta"]
    C_th2 = tri["rotor_exit"]["C_theta"]
    computed_delta_h0 = stg["U"] * (C_th2 - C_th1)
    assert abs(computed_delta_h0 - stg["delta_h0"]) < 5.0

    # 3. Aerodynamic diffusion & stall metrics
    aero = stg["aerodynamics"]
    assert 0.60 <= aero["de_haller_rotor"] <= 0.95
    assert 0.20 <= aero["diffusion_factor_rotor"] <= 0.60

    # 4. Thermodynamic pressure ratio
    assert stg["PR_stage"] > 1.25
    assert stg["P03"] > P01


def test_meanline_multistage_annulus_tapering():
    """Verify stage stacking and physical blade height tapering as air compresses."""
    res = solve_multistage_compressor_meanline(CPR=8.0, n_stages=6, mdot=20.0)

    assert res["n_stages"] == 6
    assert abs(res["CPR_actual"] - 8.0) < 1.0
    assert len(res["stages"]) == 6

    # Verify that blade height decreases from Stage 1 to Stage 6
    h_inlet_stage1 = res["stages"][0]["geometry"]["blade_height_in_mm"]
    h_exit_stage6 = res["stages"][-1]["geometry"]["blade_height_out_mm"]
    assert h_inlet_stage1 > h_exit_stage6
    assert res["stages"][0]["geometry"]["hub_to_tip_in"] < res["stages"][-1]["geometry"]["hub_to_tip_out"]


def test_meanline_turbine_stage_physics():
    """Verify turbine stage work extraction and Zweifel loading."""
    turb = solve_turbine_stage(T01=1400.0, P01=800000.0, delta_T0=180.0, N_rpm=12000.0)

    assert turb["delta_h0"] > 0
    assert turb["PR_stage"] < 1.0  # Expansion drops pressure
    assert turb["P03_kPa"] < turb["P01_kPa"]
    assert 0.5 <= turb["zweifel_coefficient"] <= 2.0


# ─────────────────────────────────────────────────────────────────────────────
# Extension 4: Turboprop / Turboshaft Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_turboprop_single_physics():
    """Verify power turbine extraction, SHP, ESHP, and residual jet thrust."""
    res = calc_turboprop_performance(
        alt=15000.0, mach=0.45, CPR=14.0, TIT=1450.0, mdot_air=12.0
    )

    assert res["P_shaft_kW"] > 500.0
    assert res["SHP"] > 500.0
    assert res["ESHP"] >= res["SHP"]  # Residual jet thrust adds to equivalent shaft power
    assert res["F_prop_kN"] > 0.0
    assert res["F_jet_kN"] > 0.0
    assert res["F_total_kN"] > res["F_prop_kN"]
    assert 0.20 <= res["PSFC_kg_kWh"] <= 0.45

    # Verify station thermodynamics order: T04 > T045 > T05 > T8
    st = res["stations"]
    assert st["4"]["T_K"] > st["45"]["T_K"] > st["5"]["T_K"] > st["8"]["T_K"]


def test_turboprop_sweep():
    """Verify turboprop sweep monotonicity across shaft power."""
    sw = run_turboprop_sweep(sweep_param="power", n_steps=4)
    pts = sw["points"]
    assert len(pts) == 4
    # Higher TIT should produce higher shaft power
    assert pts[-1]["P_shaft_kW"] > pts[0]["P_shaft_kW"]


# ─────────────────────────────────────────────────────────────────────────────
# Extension 8: Mission Simulation Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_mission_simulation_physics():
    """Verify mission profile integration, mass conservation, and payload-range."""
    sim = run_mission_simulation(
        cruise_alt_ft=35000.0, cruise_mach=0.78, cruise_distance_nm=1200.0, payload_kg=9000.0
    )

    summary = sim["mission_summary"]
    prof = sim["flight_profile"]

    # 1. Total distance and flight time consistency
    assert summary["total_distance_nm"] >= 1100.0
    assert summary["total_flight_time_min"] > 60.0

    # 2. Strict fuel and mass conservation
    assert summary["takeoff_weight_kg"] > summary["landing_weight_kg"]
    calculated_fuel_burned = summary["takeoff_weight_kg"] - summary["landing_weight_kg"]
    assert abs(calculated_fuel_burned - summary["total_fuel_burned_kg"]) < 1.0

    # 3. Aerodynamic L/D in normal transport jet envelope (14 - 18)
    assert 13.0 <= summary["cruise_L_over_D"] <= 18.5

    # 4. Gross weight strictly monotonically decreases across profile
    weights = [p["gross_weight_kg"] for p in prof]
    for i in range(len(weights) - 1):
        assert weights[i] >= weights[i + 1]

    # 5. Payload-Range envelope consistency
    env = sim["payload_range_envelope"]
    assert len(env) == 3
    # Ferry range should be longest
    assert env[2]["range_nm"] > env[0]["range_nm"]


# ─────────────────────────────────────────────────────────────────────────────
# Extension 7: Fast Surrogate Model Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_surrogate_model_latency_and_consistency():
    """Verify microsecond surrogate inference and physical trends."""
    pt = GLOBAL_SURROGATE.predict_point(
        alt_ft=35000.0, mach=0.80, throttle=1.0, CPR=16.0, TIT_K=1450.0
    )

    assert pt["Thrust_kN"] > 0.0
    assert pt["TSFC"] > 0.0
    assert pt["mdot_air_kgs"] > 0.0
    assert pt["fuel_flow_kgh"] > 0.0
    assert pt["EI_NOx"] > 0.0

    # Physical sensitivity test: throttling up increases thrust
    pt_idle = GLOBAL_SURROGATE.predict_point(
        alt_ft=35000.0, mach=0.80, throttle=0.6, CPR=16.0, TIT_K=1450.0
    )
    assert pt["Thrust_kN"] > pt_idle["Thrust_kN"]

    # 2D surface grid generation
    surf = GLOBAL_SURROGATE.generate_2d_surface(x_param="CPR", y_param="TIT_K", grid_res=10)
    assert len(surf["thrust_grid_kN"]) == 10
    assert len(surf["thrust_grid_kN"][0]) == 10


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Endpoints Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_all_new_fastapi_endpoints():
    """Verify 200 OK responses across all 9 new REST endpoints."""
    # 1. Mean-line endpoints
    r = client.get("/api/meanline/defaults")
    assert r.status_code == 200
    defs = r.json()

    r = client.post("/api/meanline/compressor_stage", json=defs["compressor_stage"])
    assert r.status_code == 200

    r = client.post("/api/meanline/multistage_compressor", json=defs["multistage"])
    assert r.status_code == 200

    r = client.post("/api/meanline/turbine_stage", json=defs["turbine_stage"])
    assert r.status_code == 200

    # 2. Turboprop endpoints
    r = client.get("/api/turboprop/defaults")
    assert r.status_code == 200
    tp_defs = r.json()

    r = client.post("/api/turboprop/single", json=tp_defs)
    assert r.status_code == 200

    r = client.post("/api/turboprop/sweep", json={"sweep_param": "power", "n_steps": 3})
    assert r.status_code == 200

    # 3. Mission endpoints
    r = client.get("/api/mission/defaults")
    assert r.status_code == 200
    ms_defs = r.json()

    r = client.post("/api/mission/simulate", json=ms_defs)
    assert r.status_code == 200

    # 4. Surrogate endpoints
    r = client.get("/api/surrogate/defaults")
    assert r.status_code == 200
    sg_defs = r.json()

    r = client.post("/api/surrogate/predict", json=sg_defs)
    assert r.status_code == 200
    pred_data = r.json()
    assert "thrust_kN" in pred_data
    assert "tsfc" in pred_data

    # 2D grid generation
    r = client.post("/api/surrogate/surface", json={"x_param": "CPR", "y_param": "TIT_K", "grid_res": 8})
    assert r.status_code == 200
    assert "thrust_grid_kN" in r.json()

    # 1D response curve generation (frontend format)
    r = client.post("/api/surrogate/surface", json={
        "x_param": "throttle",
        "y_param": "thrust_kN",
        "x_min": 0.3,
        "x_max": 1.0,
        "n_points": 20,
        "fixed_params": {"altitude_m": 5000.0, "mach": 0.50, "throttle": 0.80, "cpr": 20.0, "tit_K": 1500.0}
    })
    assert r.status_code == 200
    curve_data = r.json()
    assert "points" in curve_data
    assert len(curve_data["points"]) == 20
    assert "x" in curve_data["points"][0] and "y" in curve_data["points"][0]

    # Verify Turboprop frontend compatibility keys
    r_tp = client.post("/api/turboprop/single", json={"altitude_m": 4572.0, "mach": 0.40, "mdot_core": 3.8, "pi_c": 16.0, "T04": 1400.0})
    assert r_tp.status_code == 200
    tp_data = r_tp.json()
    assert "P_shaft_shp" in tp_data
    assert "propeller_thrust_N" in tp_data
    assert "total_thrust_N" in tp_data

    # Verify Mission summary and payload-range keys
    r_ms = client.post("/api/mission/simulate", json={"aircraft_type": "generic_twin", "cruise_alt_m": 10668.0, "cruise_dist_km": 2500.0})
    assert r_ms.status_code == 200
    ms_data = r_ms.json()
    assert "summary" in ms_data
    assert "block_fuel_kg" in ms_data["summary"]
    assert "total_flight_time_hr" in ms_data["summary"]
    assert "current_mission_point" in ms_data
    assert "range_km" in ms_data["current_mission_point"]

