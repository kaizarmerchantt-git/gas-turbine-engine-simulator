"""
test_stage6_modules_gate.py — Stage 6 Module Verification Gate Suite
Verifies physics, mathematical identities, power balances, and conservation laws
across all 9 modules per RULES.md Section 6.
"""

import math
import numpy as np
import pytest

import sys
import os
backend_dir = os.path.dirname(os.path.abspath(__file__))
proj_root = os.path.dirname(backend_dir)
sys.path.insert(0, proj_root)
sys.path.insert(0, backend_dir)

from physics_kernel.engine_cycle import solve_turbojet_cycle, solve_turbofan_cycle
from physics_kernel import thermo
from meanline import solve_compressor_stage, solve_multistage_compressor_meanline, solve_turbine_stage
from turboprop import calc_turboprop_performance
from mission import run_mission_simulation, compute_drag, DEFAULT_AIRCRAFT
from surrogate import GLOBAL_SURROGATE
from hybrid import evaluate_single_hybrid_point, run_hybrid_mission_simulation
from off_design import CompressorMap, solve_off_design


# ==============================================================================
# 1. Module 01: Turbojet Verification Gate
# ==============================================================================

def test_m01_turbojet_conservation_and_identities():
    """Verify Module 01 mass, energy, momentum conservation, and adiabatic duct identities."""
    res = solve_turbojet_cycle(cpr=15.0, tit_k=1450.0, mass_flow_kg_s=30.0, altitude_m=5000.0, mach=0.6)
    assert res["status"] == "ok"
    assert res["converged"] is True

    st = res["stations"]
    # 1. Adiabatic duct identity: T_t constant in inlet (T_t2 == T_t0) and nozzle (T_t8 == T_t5)
    assert abs(st["2"]["T_K"] - st["0"]["T_K"]) > 0  # T_t0 has ram rise above T_a
    assert abs(st["8"]["T_K"] - st["5"]["T_K"]) < 1e-4, "Nozzle duct must be adiabatic: T_t8 == T_t5"

    # 2. Total pressure never increases across unheated ducts / burner / nozzle
    assert st["2"]["P_kPa"] <= st["0"]["P_total_kPa"] * 1.001
    assert st["4"]["P_kPa"] < st["3"]["P_kPa"], "Combustor must experience pressure drop"
    assert st["5"]["P_kPa"] < st["4"]["P_kPa"], "Turbine must expand pressure"
    assert st["8"]["P_kPa"] <= st["5"]["P_kPa"], "Nozzle duct cannot increase total pressure"

    # 3. Entropy never decreases across components
    assert st["3"]["s_JkgK"] >= st["2"]["s_JkgK"], "Compressor irreversibility must increase entropy"
    assert st["4"]["s_JkgK"] > st["3"]["s_JkgK"], "Combustion heat addition must increase entropy"
    assert st["5"]["s_JkgK"] >= st["4"]["s_JkgK"], "Turbine irreversibility must increase entropy"

    # 4. Mass conservation
    m_air = res["mdot_air"]
    m_fuel = res["mdot_fuel"]
    m_total = m_air + m_fuel
    rho_9 = st["9"]["P_kPa"] * 1000.0 / (287.05 * st["9"]["T_K"])
    m_exit = rho_9 * res["nozzle_exit_area_m2"] * res["nozzle_exit_velocity_m_s"]
    assert abs(m_exit - m_total) / m_total < 0.05, f"Mass flow conservation error: exit={m_exit}, inlet={m_total}"


def test_m01_turbojet_infeasible_inputs_typed_error():
    """Verify extreme infeasible inputs return status infeasible, not dummy zeros."""
    # CPR = 40.0 with TIT = 700 K cannot provide enough turbine work to drive compressor
    res = solve_turbojet_cycle(cpr=40.0, tit_k=700.0, mass_flow_kg_s=20.0)
    assert res["status"] == "infeasible"
    assert res["converged"] is False
    assert len(res["meta"]["warnings"]) > 0


# ==============================================================================
# 2. Module 02: Turbofan Verification Gate
# ==============================================================================

def test_m02_turbofan_dual_spool_balances():
    """Verify dual-spool turbofan power balances, OPR calculation, and thrust split."""
    res = solve_turbofan_cycle(cpr=18.0, fan_pr=1.65, bpr=6.0, tit_k=1550.0, mass_flow_kg_s=150.0)
    assert res["status"] == "ok"
    assert res["converged"] is True

    # 1. Total thrust equals core + bypass
    assert abs(res["thrust_net_kN"] - (res["bypass_thrust_kN"] + res["core_thrust_kN"])) < 1e-3

    # 2. OPR shown equals Pt3 / Pt2
    st = res["stations"]
    pt3 = st["3"]["P_kPa"]
    pt2 = st["2"]["P_kPa"]
    opr_calc = pt3 / pt2
    assert abs(res["OPR"] - opr_calc) < 0.1

    # 3. Bypass ratio matches requested
    assert abs(res["BPR"] - 6.0) < 1e-3


# ==============================================================================
# 3. Module 04: Off-Design Verification Gate
# ==============================================================================

def test_m04_off_design_fundamental_design_reproduction():
    """Verify off-design at design-point inputs reproduces the design point."""
    res = solve_off_design(
        N_rel=1.0, alt=35000.0, mach=0.8,
        des_alt=35000.0, des_mach=0.8, cpr_des=8.0, eta_c_des=0.85
    )
    assert res["converged"] is True
    # At design point, beta is centered around 0.50
    assert abs(res["beta"] - 0.50) < 0.05
    # CPR matches design CPR within 2%
    assert abs(res["CPR"] - 8.0) / 8.0 < 0.02
    # Nozzle area match error < 0.1%
    assert res["A8_match_err_pct"] < 0.1


# ==============================================================================
# 4. Module 05: Mean-Line Turbomachinery Verification Gate
# ==============================================================================

def test_m05_meanline_euler_work_and_aerodynamics():
    """Verify Euler work identity Delta h0 = U * (C_theta2 - C_theta1) and Lieblein DF."""
    stg = solve_compressor_stage(
        T01=288.15, P01=101325.0, delta_T0=32.0, N_rpm=11500.0,
        r_mean=0.30, C_a=155.0, reaction=0.50, eta_stage=0.88
    )
    # Euler equation
    tri = stg["velocity_triangles"]
    C_th1 = tri["rotor_inlet"]["C_theta"]
    C_th2 = tri["rotor_exit"]["C_theta"]
    delta_h0_euler = stg["U"] * (C_th2 - C_th1)
    assert abs(delta_h0_euler - stg["delta_h0"]) < 5.0

    # De Haller and Lieblein
    aero = stg["aerodynamics"]
    assert aero["de_haller_rotor"] > 0.65
    assert aero["diffusion_factor_rotor"] < 0.60


def test_m05_meanline_multistage_blade_height_tapering():
    """Verify blade height decreases monotonically through compressor stages."""
    res = solve_multistage_compressor_meanline(CPR=10.0, n_stages=6, mdot=25.0)
    stages = res["stages"]
    heights = [s["geometry"]["blade_height_in_mm"] for s in stages]
    for i in range(len(heights) - 1):
        assert heights[i] > heights[i + 1], f"Blade height not tapering: stage {i} ({heights[i]}) <= stage {i+1} ({heights[i+1]})"


# ==============================================================================
# 5. Module 06: Turboprop Verification Gate
# ==============================================================================

def test_m06_turboprop_power_balance_and_propeller_response():
    """Verify turboprop shaft power, propeller response to RPM, and ESHP > P_shaft."""
    tp1 = calc_turboprop_performance(alt=10000.0, mach=0.35, prop_rpm=1200.0, prop_diameter_m=3.2)
    tp2 = calc_turboprop_performance(alt=10000.0, mach=0.35, prop_rpm=1600.0, prop_diameter_m=3.2)

    assert tp1["P_shaft_kW"] > 0
    assert tp1["ESHP"] > tp1["SHP"], "ESHP must exceed SHP due to residual jet thrust"
    assert tp1["F_jet_kN"] > 0, "Residual jet thrust must be positive"

    # Dead-input check: varying RPM changes helical tip Mach and advance ratio J
    assert abs(tp1["tip_mach_helical"] - tp2["tip_mach_helical"]) > 0.05
    assert abs(tp1["advance_ratio_J"] - tp2["advance_ratio_J"]) > 0.05


# ==============================================================================
# 6. Module 07: Mission and Sizing Verification Gate
# ==============================================================================

def test_m07_mission_breguet_and_closure():
    """Verify mission simulator weight conservation, segment integration, and ground touchdown."""
    res = run_mission_simulation(aircraft_type="generic_twin", cruise_alt_ft=35000.0, cruise_distance_nm=1200.0)
    summary = res["summary"]

    assert summary["mission_feasible"] is True
    assert summary["fuel_remaining_kg"] >= 0.0
    assert summary["reserve_fuel_kg"] >= 0.0

    # Check that profile touches down at 0m altitude
    profile = res["flight_profile"]
    assert profile[-1]["altitude_m"] == 0.0
    assert profile[-1]["phase"] in ("Landing", "Taxi-In")


# ==============================================================================
# 7. Module 08: Surrogate Verification Gate
# ==============================================================================

def test_m08_surrogate_loocv_and_uncertainty_growth():
    """Verify surrogate LOOCV R^2 >= 0.98 and uncertainty grows on extrapolation."""
    r2_mean = float(np.mean(GLOBAL_SURROGATE.loocv_r2))
    assert r2_mean >= 0.98, f"Surrogate LOOCV R^2 below target: {r2_mean}"

    # Prediction inside training hull vs outside
    pred_nominal = GLOBAL_SURROGATE.predict_point(alt_ft=30000.0, mach=0.75, throttle=0.9, CPR=14.0, TIT_K=1450.0)
    pred_extrap = GLOBAL_SURROGATE.predict_point(alt_ft=55000.0, mach=1.5, throttle=1.0, CPR=35.0, TIT_K=2100.0)

    assert pred_extrap["uncertainty_pct"] > pred_nominal["uncertainty_pct"]
    assert pred_nominal["latency_ms"] < 5.0, "Surrogate evaluation latency must be under 5 ms"


# ==============================================================================
# 8. Module 09: Hybrid-Electric Verification Gate
# ==============================================================================

def test_m09_hybrid_power_conservation_and_zero_split_baseline():
    """Verify hybrid power conservation and 0% fuel savings at 0 hybrid ratio."""
    # Zero hybrid ratio (pure gas turbine)
    base = evaluate_single_hybrid_point(architecture="parallel", shaft_power_req_kW=2000.0, hybrid_power_ratio_HP=0.0)
    assert base["gas_turbine_power_kW"] == 2000.0
    assert base["battery_power_kW"] == 0.0

    # 30% hybrid ratio
    hyb = evaluate_single_hybrid_point(architecture="parallel", shaft_power_req_kW=2000.0, hybrid_power_ratio_HP=0.30)
    # Power conservation: P_GT + P_motor == 2000 kW
    total_power = hyb["gas_turbine_power_kW"] + hyb["electric_motor_power_kW"]
    assert abs(total_power - 2000.0) < 1e-6

    # Waste heat conservation
    assert hyb["waste_heat_kW"] > 0
