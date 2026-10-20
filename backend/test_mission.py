"""
Unit & First-Principles Verification Suite for Module 07 (Mission Profile & Drone Sizing)
========================================================================================
AETHER-X v0.5 REA Verification Suite
Validates:
1. Wing and empennage geometry derivations matching General Sizing Blank.xlsx
2. Exact analytical characteristic airspeeds (V_stall, V_minD, V_minP)
3. Parabolic drag bucket minimum where D0 == Di at V_minD
4. MIS-01 bug fix: User engine TSFC propagation (no silent 18.0 fallback)
5. 7-phase mission kinematic trajectory ending at 0 m with exact mass balance
6. Tactical UAV sizing preset from General Sizing Blank
"""

import math
import pytest
import numpy as np
from mission import (
    size_airframe_geometry,
    compute_characteristic_airspeeds,
    compute_airspeed_trends,
    compute_drag,
    run_mission_simulation,
    AIRCRAFT_PRESETS,
    DEFAULT_AIRCRAFT,
)


# =============================================================================
# 1. WING & EMPENNAGE GEOMETRY VERIFICATION (General Sizing Blank.xlsx)
# =============================================================================

def test_airframe_geometry_derivations():
    """Verify wing area, span, root/tip chords, MAC, and empennage volume sizing."""
    gross_mass = 25.0  # kg (tactical UAV)
    wl = 15.625        # kg/m²
    ar = 10.0
    taper = 0.65
    v_h = 0.50
    v_v = 0.04

    res = size_airframe_geometry(
        gross_mass_kg=gross_mass,
        wing_loading_kg_m2=wl,
        aspect_ratio=ar,
        taper_ratio=taper,
        V_H=v_h,
        V_V=v_v,
        material="composite",
    )

    expected_S = gross_mass / wl  # 25.0 / 15.625 = 1.60 m²
    expected_b = math.sqrt(ar * expected_S)  # sqrt(10.0 * 1.60) = 4.0 m
    expected_c_root = (2.0 * expected_S) / ((1.0 + taper) * expected_b)  # 3.2 / (1.65 * 4.0) = 0.4848 m
    expected_c_tip = taper * expected_c_root  # 0.3151 m
    expected_mac = (2.0 / 3.0) * expected_c_root * ((1.0 + taper + taper**2) / (1.0 + taper))

    assert res["wing_area_m2"] == pytest.approx(expected_S, rel=1e-3)
    assert res["span_b_m"] == pytest.approx(expected_b, rel=1e-3)
    assert res["root_chord_m"] == pytest.approx(expected_c_root, rel=1e-3)
    assert res["tip_chord_m"] == pytest.approx(expected_c_tip, rel=1e-3)
    assert res["mac_m"] == pytest.approx(expected_mac, rel=1e-3)

    # Empennage volume assertions: S_H and S_V must be strictly positive and proportional
    assert res["horizontal_tail_area_m2"] > 0.0
    assert res["vertical_tail_area_m2"] > 0.0
    assert res["structural_mass_fraction"] == 0.32
    assert res["structural_mass_kg"] == pytest.approx(gross_mass * 0.32, rel=1e-3)


# =============================================================================
# 2. ANALYTICAL CHARACTERISTIC AIRSPEEDS VERIFICATION
# =============================================================================

def test_characteristic_airspeeds_exact_formulas():
    """Verify V_stall, V_minD, and V_minP match exact closed-form aerodynamics."""
    weight_N = 75000.0 * 9.80665
    S = 122.6
    ar = 9.5
    cd0 = 0.0185
    e = 0.85
    cl_max = 1.50
    alt_ft = 35000.0

    res = compute_characteristic_airspeeds(
        weight_N=weight_N,
        wing_area_m2=S,
        aspect_ratio=ar,
        CD0=cd0,
        oswald_e=e,
        CL_max=cl_max,
        alt_ft=alt_ft,
    )

    rho = res["rho_kg_m3"]
    K = 1.0 / (math.pi * e * ar)

    # Theoretical formulas
    v_stall_theory = math.sqrt((2.0 * weight_N) / (rho * S * cl_max))
    v_minD_theory = ((1.0 / (math.pi * e * ar * cd0)) ** 0.25) * math.sqrt((2.0 * weight_N) / (rho * S))
    v_minP_theory = v_minD_theory / (3.0 ** 0.25)

    assert res["V_stall_ms"] == pytest.approx(v_stall_theory, rel=1e-2)
    assert res["V_minD_ms"] == pytest.approx(v_minD_theory, rel=1e-2)
    assert res["V_minP_ms"] == pytest.approx(v_minP_theory, rel=1e-2)

    # Parabolic drag polar property: V_minP / V_minD must equal 3^(-0.25) ~ 0.7598356
    speed_ratio = res["V_minP_ms"] / res["V_minD_ms"]
    assert speed_ratio == pytest.approx(3.0 ** (-0.25), rel=1e-3)

    # Maximum L/D ratio verification
    ld_max_theory = 1.0 / (2.0 * math.sqrt(cd0 * K))
    assert res["LD_max"] == pytest.approx(ld_max_theory, rel=1e-2)


# =============================================================================
# 3. DRAG BUCKET MINIMUM & POLAR CONTINUITY VERIFICATION
# =============================================================================

def test_airspeed_trends_drag_bucket():
    """Verify that in airspeed trends, total drag achieves its minimum near V_minD where D0 == Di."""
    gross_mass = 75000.0
    S = 122.6
    ar = 9.5
    cd0 = 0.0185
    alt_ft = 35000.0

    trends = compute_airspeed_trends(
        gross_mass_kg=gross_mass,
        wing_area_m2=S,
        aspect_ratio=ar,
        CD0=cd0,
        alt_ft=alt_ft,
        n_points=61,
    )

    pts = trends["trend_points"]
    char_speeds = trends["characteristic_speeds"]
    v_minD = char_speeds["V_minD_ms"]

    # Filter unstalled points
    valid_pts = [p for p in pts if not p["is_stalled"]]
    assert len(valid_pts) > 10

    # Find speed corresponding to minimum total drag
    min_drag_pt = min(valid_pts, key=lambda p: p["D_total_N"])
    assert min_drag_pt["V_ms"] == pytest.approx(v_minD, rel=0.10)

    # At minimum drag point, parasitic drag D0 and induced drag Di should be very close
    assert min_drag_pt["D0_N"] == pytest.approx(min_drag_pt["Di_N"], rel=0.15)

    # L/D maximum should align with LD_max
    max_ld_pt = max(valid_pts, key=lambda p: p["L_over_D"])
    assert max_ld_pt["L_over_D"] == pytest.approx(char_speeds["LD_max"], rel=0.05)


# =============================================================================
# 4. MIS-01 RESOLUTION: TSFC PROPAGATION TEST
# =============================================================================

def test_tsfc_propagation_no_fallback():
    """Verify that user engine TSFC propagates directly without falling back to hardcoded 18.0."""
    custom_tsfc_low = 14.2
    res_low = run_mission_simulation(
        cruise_alt_ft=35000.0,
        cruise_mach=0.78,
        cruise_distance_nm=1200.0,
        engine_base_tsfc=custom_tsfc_low,
    )

    custom_tsfc_high = 22.5
    res_high = run_mission_simulation(
        cruise_alt_ft=35000.0,
        cruise_mach=0.78,
        cruise_distance_nm=1200.0,
        engine_base_tsfc=custom_tsfc_high,
    )

    # Check cruise phases in flight profile
    cruise_steps_low = [p for p in res_low["flight_profile"] if p["phase"].startswith("Cruise")]
    cruise_steps_high = [p for p in res_high["flight_profile"] if p["phase"].startswith("Cruise")]

    assert len(cruise_steps_low) > 0
    assert len(cruise_steps_high) > 0

    # Must NOT equal 18.0
    for p in cruise_steps_low:
        assert p["TSFC_g_kNs"] != 18.0
        assert p["TSFC_g_kNs"] == pytest.approx(custom_tsfc_low * 1.02, rel=1e-2)

    for p in cruise_steps_high:
        assert p["TSFC_g_kNs"] != 18.0
        assert p["TSFC_g_kNs"] == pytest.approx(custom_tsfc_high * 1.02, rel=1e-2)

    # Total fuel burn must scale monotonically with TSFC
    burn_low = res_low["mission_summary"]["total_fuel_burned_kg"]
    burn_high = res_high["mission_summary"]["total_fuel_burned_kg"]
    assert burn_high > burn_low * 1.35


# =============================================================================
# 5. TRAJECTORY CLOSURE TO 0 M & MASS BALANCE VERIFICATION
# =============================================================================

def test_mission_trajectory_closure_and_mass_conservation():
    """Verify 7-phase mission profile reaches 0 m (Landing & Taxi-In) with exact mass conservation."""
    res = run_mission_simulation(
        cruise_alt_ft=35000.0,
        cruise_mach=0.78,
        cruise_distance_nm=1500.0,
        payload_kg=12000.0,
        aircraft_type="generic_twin",
    )

    profile = res["flight_profile"]
    summary = res["mission_summary"]

    # Verify trajectory phases
    phase_names = [p["phase"] for p in profile]
    assert phase_names[0] == "Taxi-Out"
    assert profile[0]["altitude_m"] == 0.0

    assert any(p.startswith("Climb") for p in phase_names)
    assert any(p.startswith("Cruise") for p in phase_names)
    assert "Descent" in phase_names
    assert "Landing" in phase_names
    assert "Taxi-In" in phase_names

    # Final steps must touch down and shut down at 0 m
    landing_step = next(p for p in profile if p["phase"] == "Landing")
    taxi_in_step = next(p for p in profile if p["phase"] == "Taxi-In")
    assert landing_step["altitude_m"] == 0.0
    assert taxi_in_step["altitude_m"] == 0.0

    # Mass conservation:
    # Takeoff Weight - Landing Weight == Flight Fuel Burned
    # Ramp Weight - Shutdown Weight == Block Fuel Burned == Sum of Step Fuel Burned
    tow = summary["takeoff_weight_kg"]
    lw = summary["landing_weight_kg"]
    flight_fuel = summary["flight_fuel_kg"]
    block_fuel = summary["total_fuel_burned_kg"]
    ramp_weight = summary["ramp_weight_kg"]
    shutdown_weight = summary["shutdown_weight_kg"]
    sum_fuel_steps = sum(p["fuel_burned_kg"] for p in profile)

    brake_release = summary["brake_release_weight_kg"]
    touchdown = summary["touchdown_weight_kg"]

    # Flight fuel mass conservation (airborne trajectory)
    assert brake_release - touchdown == pytest.approx(flight_fuel, abs=0.5)
    # Block fuel mass conservation (gate-to-gate total fuel)
    assert tow - lw == pytest.approx(block_fuel, abs=0.5)
    assert ramp_weight - shutdown_weight == pytest.approx(block_fuel, abs=0.5)
    assert sum_fuel_steps == pytest.approx(block_fuel, abs=0.5)

    # Airframe Sizing card data and characteristic speeds must be present
    assert "airframe_sizing" in res
    assert res["airframe_sizing"]["wing_area_m2"] > 0.0
    assert "characteristic_speeds" in res
    assert res["characteristic_speeds"]["V_stall_ms"] > 0.0


# =============================================================================
# 6. TACTICAL UAV SIZING PRESET VERIFICATION
# =============================================================================

def test_tactical_uav_mission_simulation():
    """Verify tactical UAV (General Sizing Blank baseline) executes cleanly."""
    res = run_mission_simulation(
        cruise_alt_ft=8000.0,
        cruise_mach=0.08,
        cruise_distance_nm=80.0,
        payload_kg=4.0,
        aircraft_type="tactical_uav",
        engine_base_tsfc=28.0,
    )

    summary = res["mission_summary"]
    assert summary["mission_feasible"] is True
    assert summary["takeoff_weight_kg"] <= 25.0
    assert summary["total_fuel_burned_kg"] < 5.0
    assert summary["total_distance_nm"] >= 80.0
    assert summary["cruise_L_over_D"] > 10.0
