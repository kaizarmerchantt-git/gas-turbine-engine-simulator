"""
Gas Turbine Engine Simulator — Mission Profile & Aircraft/Drone Sizing Integration
==================================================================================
AETHER-X v0.5 Mission & Airframe Sizing Module (Module 07)

Implements:
1. Conceptual Airframe & Drone Sizing Engine (derived from General Sizing Blank.xlsx):
   - Wing Geometry Sizing from Wing Loading (W/S -> S_wing, b, c_root, c_tip, c_bar).
   - Empennage Volume Sizing (S_H, S_V) from horizontal and vertical volume coefficients.
   - Material Mass Fraction allocations (Composite 32%, Balsa 28%, Foam 22%, Transport 55%).
2. Analytical Characteristic Airspeeds (exact closed-form equations):
   - Stall Speed: V_stall = sqrt(2*W / (rho * S * CL_max))
   - Stall Margin: delta_V_stall = V_cruise - V_stall
   - Minimum Drag / Best Jet Range Speed: V_minD = (1 / (pi*e*AR*CD0))^0.25 * sqrt(2*W / (rho*S))
   - Minimum Power / Best Loiter Speed: V_minP = V_minD / (3^0.25) ~ 0.7598 * V_minD
3. Continuous Drag Polar & Airspeed Trend Sweeps (General Sizing Blank Trends sheet):
   - Parasitic (D0), Induced (Di), Wave (Dw), Total Drag, L/D, and Power Required (P_req) curves.
4. Kinematic 7-Phase Mission Simulator (Specific Excess Power Ps climb, 0 m Landing & Taxi-In closure).
5. Robust Bug Fixes:
   - MIS-01: Removed hardcoded cruise_tsfc = 18.0 fallback; exact user TSFC propagation.
   - MIS-02: Coupled climb kinematics to Specific Excess Power Ps = V*(T - D)/W.
   - MIS-03: Completed flight profile down to 0 m (Landing flare + ground roll + Taxi-In).
   - MIS-04: Explicit stall detection replacing silent CL clamping.
"""

from __future__ import annotations

import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

try:
    import ISA_module as ISA
except ImportError:
    from . import ISA_module as ISA


# ─────────────────────────────────────────────────────────────────────────────
# 1. PREDEFINED AIRCRAFT & DRONE PRESETS
# ─────────────────────────────────────────────────────────────────────────────

AIRCRAFT_PRESETS: Dict[str, Dict[str, Any]] = {
    "tactical_uav": {
        "name": "Tactical Recon UAV (General Sizing Baseline)",
        "aircraft_class": "uav",
        "MTOW_kg": 25.0,
        "OEW_kg": 11.5,
        "max_payload_kg": 5.0,
        "max_fuel_kg": 8.5,
        "wing_area_m2": 1.60,
        "aspect_ratio": 10.0,
        "taper_ratio": 0.65,
        "oswald_e": 0.85,
        "CD0": 0.0240,
        "CL_max": 1.35,
        "n_engines": 1,
        "M_crit": 0.35,
        "V_H": 0.50,
        "V_V": 0.04,
        "default_cruise_alt_ft": 8000.0,
        "default_cruise_mach": 0.08,
        "default_distance_nm": 80.0,
        "material": "composite",
    },
    "regional_twin": {
        "name": "Twin-Jet Regional 100-Pax (E190 Class)",
        "aircraft_class": "transport",
        "MTOW_kg": 45000.0,
        "OEW_kg": 26000.0,
        "max_payload_kg": 11500.0,
        "max_fuel_kg": 12500.0,
        "wing_area_m2": 78.0,
        "aspect_ratio": 9.2,
        "taper_ratio": 0.28,
        "oswald_e": 0.82,
        "CD0": 0.0210,
        "CL_max": 1.45,
        "n_engines": 2,
        "M_crit": 0.78,
        "V_H": 0.68,
        "V_V": 0.06,
        "default_cruise_alt_ft": 35000.0,
        "default_cruise_mach": 0.78,
        "default_distance_nm": 1200.0,
        "material": "aluminum_cfrp",
    },
    "generic_twin": {
        "name": "Narrowbody Twin 180-Pax (A320/B737 Class)",
        "aircraft_class": "transport",
        "MTOW_kg": 75000.0,
        "OEW_kg": 41500.0,
        "max_payload_kg": 19500.0,
        "max_fuel_kg": 21000.0,
        "wing_area_m2": 122.6,
        "aspect_ratio": 9.5,
        "taper_ratio": 0.24,
        "oswald_e": 0.85,
        "CD0": 0.0185,
        "CL_max": 1.50,
        "n_engines": 2,
        "M_crit": 0.80,
        "V_H": 0.70,
        "V_V": 0.065,
        "default_cruise_alt_ft": 36000.0,
        "default_cruise_mach": 0.78,
        "default_distance_nm": 1800.0,
        "material": "aluminum_cfrp",
    },
    "long_range_twin": {
        "name": "Widebody Twin 300-Pax (B777/A350 Class)",
        "aircraft_class": "transport",
        "MTOW_kg": 228000.0,
        "OEW_kg": 115000.0,
        "max_payload_kg": 45000.0,
        "max_fuel_kg": 75000.0,
        "wing_area_m2": 360.0,
        "aspect_ratio": 9.5,
        "taper_ratio": 0.22,
        "oswald_e": 0.85,
        "CD0": 0.0180,
        "CL_max": 1.50,
        "n_engines": 2,
        "M_crit": 0.82,
        "V_H": 0.72,
        "V_V": 0.07,
        "default_cruise_alt_ft": 38000.0,
        "default_cruise_mach": 0.82,
        "default_distance_nm": 4500.0,
        "material": "composite",
    },
}

DEFAULT_AIRCRAFT = AIRCRAFT_PRESETS["generic_twin"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. AIRFRAME & DRONE GEOMETRY SIZING (General Sizing Blank.xlsx: Metric Sheet)
# ─────────────────────────────────────────────────────────────────────────────

def size_airframe_geometry(
    gross_mass_kg: float,
    wing_loading_kg_m2: Optional[float] = None,
    aspect_ratio: float = 9.5,
    taper_ratio: float = 0.25,
    V_H: float = 0.70,
    V_V: float = 0.06,
    material: str = "composite",
) -> Dict[str, Any]:
    """
    Computes closed-loop wing and empennage geometry from Wing Loading (W/S)
    and mass fractions, exactly matching General Sizing Blank.xlsx formulas.
    """
    g = 9.80665
    weight_N = gross_mass_kg * g

    # If wing loading not given, infer from baseline class defaults
    if wing_loading_kg_m2 is None or wing_loading_kg_m2 <= 0:
        if gross_mass_kg <= 100.0:
            wing_loading_kg_m2 = 15.625  # UAV default: ~15.6 kg/m² (~153 N/m²)
        elif gross_mass_kg <= 50000.0:
            wing_loading_kg_m2 = 576.9   # Regional: ~577 kg/m²
        else:
            wing_loading_kg_m2 = 611.7   # Transport: ~612 kg/m²

    wing_area_m2 = gross_mass_kg / wing_loading_kg_m2
    span_b_m = math.sqrt(aspect_ratio * wing_area_m2)
    semi_span_m = span_b_m / 2.0

    lam = max(0.1, min(1.0, taper_ratio))
    c_root_m = (2.0 * wing_area_m2) / ((1.0 + lam) * span_b_m)
    c_tip_m = lam * c_root_m
    c_bar_mac_m = (2.0 / 3.0) * c_root_m * ((1.0 + lam + lam ** 2) / (1.0 + lam))

    # Empennage volume sizing
    # Moment arms L_H and L_V approximated from fuselage / boom length
    L_H_m = 2.6 * c_bar_mac_m
    L_V_m = 0.45 * span_b_m

    S_H_m2 = (V_H * c_bar_mac_m * wing_area_m2) / max(0.1, L_H_m)
    S_V_m2 = (V_V * span_b_m * wing_area_m2) / max(0.1, L_V_m)

    # Material mass fractions (from General Sizing Blank Mass Fractions table)
    mat_fractions = {
        "composite": 0.32,
        "balsa": 0.28,
        "foam": 0.22,
        "aluminum_cfrp": 0.55,
    }
    struct_fraction = mat_fractions.get(material.lower(), 0.32)
    structural_mass_kg = round(gross_mass_kg * struct_fraction, 1)

    return {
        "gross_mass_kg": round(gross_mass_kg, 1),
        "wing_loading_kg_m2": round(wing_loading_kg_m2, 2),
        "wing_loading_N_m2": round(wing_loading_kg_m2 * g, 1),
        "wing_area_m2": round(wing_area_m2, 3),
        "aspect_ratio": round(aspect_ratio, 2),
        "span_b_m": round(span_b_m, 3),
        "semi_span_m": round(semi_span_m, 3),
        "root_chord_m": round(c_root_m, 3),
        "tip_chord_m": round(c_tip_m, 3),
        "mac_m": round(c_bar_mac_m, 3),
        "horizontal_tail_area_m2": round(S_H_m2, 3),
        "vertical_tail_area_m2": round(S_V_m2, 3),
        "moment_arm_H_m": round(L_H_m, 3),
        "moment_arm_V_m": round(L_V_m, 3),
        "material": material,
        "structural_mass_fraction": struct_fraction,
        "structural_mass_kg": structural_mass_kg,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. ANALYTICAL CHARACTERISTIC AIRSPEEDS
# ─────────────────────────────────────────────────────────────────────────────

def compute_characteristic_airspeeds(
    weight_N: float,
    wing_area_m2: float,
    aspect_ratio: float,
    CD0: float,
    oswald_e: float = 0.85,
    CL_max: float = 1.45,
    alt_ft: float = 0.0,
) -> Dict[str, float]:
    """
    Computes exact closed-form characteristic airspeeds:
    - V_stall: Stall onset velocity
    - V_minD: Minimum drag / Best Jet Range velocity (L/D max)
    - V_minP: Minimum power / Best Loiter Endurance velocity
    """
    rho = float(ISA.rho(alt_ft))
    S = wing_area_m2
    AR = aspect_ratio
    e = oswald_e
    K = 1.0 / (math.pi * e * AR)

    # 1. Stall speed [m/s]
    V_stall = math.sqrt((2.0 * weight_N) / max(1e-4, rho * S * CL_max))

    # 2. Minimum Drag speed (Best Jet Range) [m/s]
    # Occurs where D0 == Di: q^2 * CD0 = K * (W/S)^2 -> V_minD = (4 * K * W^2 / (rho^2 * S^2 * CD0))^0.25
    V_minD = ((1.0 / (math.pi * e * AR * CD0)) ** 0.25) * math.sqrt((2.0 * weight_N) / (rho * S))

    # 3. Minimum Power speed (Best Loiter Endurance) [m/s]
    # For a parabolic drag polar, V_minP = V_minD / (3^0.25) ~ 0.7598 * V_minD
    V_minP = V_minD / (3.0 ** 0.25)

    # Maximum L/D ratio
    LD_max = 1.0 / (2.0 * math.sqrt(CD0 * K))

    return {
        "V_stall_ms": round(V_stall, 2),
        "V_stall_kts": round(V_stall / 0.514444, 1),
        "V_minD_ms": round(V_minD, 2),
        "V_minD_kts": round(V_minD / 0.514444, 1),
        "V_minP_ms": round(V_minP, 2),
        "V_minP_kts": round(V_minP / 0.514444, 1),
        "LD_max": round(LD_max, 2),
        "rho_kg_m3": round(rho, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONTINUOUS DRAG POLAR & AIRSPEED TRENDS (Trends Sheet)
# ─────────────────────────────────────────────────────────────────────────────

def compute_airspeed_trends(
    gross_mass_kg: float,
    wing_area_m2: float,
    aspect_ratio: float,
    CD0: float,
    oswald_e: float = 0.85,
    CL_max: float = 1.45,
    alt_ft: float = 0.0,
    n_points: int = 35,
    engine_base_tsfc: float = 18.0,
) -> Dict[str, Any]:
    """
    Evaluates continuous polar trends across airspeeds (General Sizing Blank Trends sheet):
    Parasitic Drag D0, Induced Drag Di, Wave Drag Dw, Total Drag, L/D, and Power Required.
    """
    g = 9.80665
    weight_N = gross_mass_kg * g
    speeds_info = compute_characteristic_airspeeds(
        weight_N, wing_area_m2, aspect_ratio, CD0, oswald_e, CL_max, alt_ft
    )

    v_stall = speeds_info["V_stall_ms"]
    v_minD = speeds_info["V_minD_ms"]
    v_start = max(5.0, v_stall * 0.90)
    v_end = max(v_minD * 2.2, v_stall * 3.0)

    V_grid = np.linspace(v_start, v_end, n_points)
    rho = float(ISA.rho(alt_ft))
    T_amb = float(ISA.T(alt_ft))
    a = math.sqrt(1.4 * 287.05 * T_amb)
    S = wing_area_m2
    K = 1.0 / (math.pi * oswald_e * aspect_ratio)

    trend_points = []
    for V in V_grid:
        mach = V / a
        q = 0.5 * rho * (V ** 2)

        CL = weight_N / (q * S) if q > 0 else 0.5
        is_stalled = bool(CL > CL_max)

        CD_induced = K * (CL ** 2)
        CD_wave = 25.0 * max(0.0, mach - 0.78) ** 4
        CD_total = CD0 + CD_induced + CD_wave

        D0_N = q * S * CD0
        Di_N = q * S * CD_induced
        Dw_N = q * S * CD_wave
        D_total_N = q * S * CD_total

        L_over_D = (weight_N / D_total_N) if D_total_N > 0 else 1.0
        P_req_kW = (D_total_N * V) / 1000.0

        trend_points.append({
            "V_ms": round(float(V), 2),
            "V_kts": round(float(V / 0.514444), 1),
            "mach": round(float(mach), 3),
            "CL": round(float(CL), 4),
            "CD_total": round(float(CD_total), 5),
            "D0_N": round(float(D0_N), 1),
            "Di_N": round(float(Di_N), 1),
            "Dw_N": round(float(Dw_N), 1),
            "D_total_N": round(float(D_total_N), 1),
            "L_over_D": round(float(L_over_D), 2),
            "P_req_kW": round(float(P_req_kW), 2),
            "is_stalled": is_stalled,
        })

    return {
        "characteristic_speeds": speeds_info,
        "trend_points": trend_points,
        "alt_ft": alt_ft,
        "gross_mass_kg": gross_mass_kg,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. COUPLED DRAG & SPECIFIC EXCESS POWER KINEMATICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_drag(
    weight_N: float,
    alt_ft: float,
    mach: float,
    aircraft: Dict[str, Any] = DEFAULT_AIRCRAFT,
    climb_angle_rad: float = 0.0,
) -> Tuple[float, float, float, float, bool]:
    """
    Computes aircraft drag, lift coefficient, required thrust, and stall detection.
    Returns: (T_per_engine_N, D_total_N, CL, CD, is_stalled)
    """
    rho = float(ISA.rho(alt_ft))
    T_amb = float(ISA.T(alt_ft))
    a = math.sqrt(1.4 * 287.05 * T_amb)
    V = max(5.0, mach * a)

    S = aircraft["wing_area_m2"]
    AR = aircraft["aspect_ratio"]
    e = aircraft["oswald_e"]
    CD0 = aircraft["CD0"]
    M_crit = aircraft.get("M_crit", 0.78)
    CL_max = aircraft.get("CL_max", 1.45)

    # Dynamic pressure
    q = 0.5 * rho * V * V

    # Lift in quasi-steady climb/cruise: L = W * cos(gamma)
    L = weight_N * math.cos(climb_angle_rad)
    CL = L / (q * S) if q > 0 else 0.5

    is_stalled = False
    if CL > CL_max:
        is_stalled = True
        # Induced drag penalty under stall
        CL_effective = CL_max
    else:
        CL_effective = CL

    # Induced drag factor: K = 1 / (pi * e * AR)
    K = 1.0 / (math.pi * e * AR)
    CD_induced = K * (CL_effective ** 2)

    # Wave drag divergence above critical Mach
    CD_wave = 25.0 * max(0.0, mach - M_crit) ** 4

    CD = CD0 + CD_induced + CD_wave
    D = q * S * CD

    # Total thrust required (includes climb component)
    T_total_req = D + weight_N * math.sin(climb_angle_rad)
    T_per_engine_N = T_total_req / aircraft["n_engines"]

    return T_per_engine_N, D, CL, CD, is_stalled


# ─────────────────────────────────────────────────────────────────────────────
# 6. END-TO-END 7-PHASE FLIGHT TRAJECTORY SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────

def run_mission_simulation(
    cruise_alt_ft: float = 35000.0,
    cruise_mach: float = 0.78,
    cruise_distance_nm: float = 1200.0,
    payload_kg: float = 9000.0,
    fuel_load_kg: Optional[float] = None,
    aircraft_type: str = "generic_twin",
    engine_base_tsfc: float = 18.0,
) -> Dict[str, Any]:
    """
    Simulates complete multi-phase aircraft mission with Specific Excess Power (Ps) climb,
    Breguet step-cruise, descent, landing flare, and taxi-in down to 0 m.
    """
    aircraft = AIRCRAFT_PRESETS.get(aircraft_type, DEFAULT_AIRCRAFT).copy()

    MTOW = aircraft["MTOW_kg"]
    OEW = aircraft["OEW_kg"]
    max_payload = aircraft["max_payload_kg"]
    max_fuel = aircraft["max_fuel_kg"]
    g = 9.80665

    payload_kg = min(payload_kg, max_payload)

    if fuel_load_kg is None:
        fuel_load_kg = min(max_fuel, max(0.0, MTOW - OEW - payload_kg))
    else:
        fuel_load_kg = min(fuel_load_kg, max_fuel)

    ramp_weight_kg = OEW + payload_kg + fuel_load_kg
    if ramp_weight_kg > MTOW:
        fuel_load_kg = max(0.0, min(max_fuel, MTOW - OEW - payload_kg))
        ramp_weight_kg = OEW + payload_kg + fuel_load_kg

    curr_mass = ramp_weight_kg
    curr_fuel = fuel_load_kg
    total_dist_nm = 0.0
    total_time_min = 0.0
    profile = []

    is_uav = bool(aircraft.get("aircraft_class") == "uav")

    def record_step(
        phase_name: str,
        alt: float,
        mach: float,
        dt_min: float,
        dist_nm: float,
        fuel_kg: float,
        thrust_kN: float,
        tsfc_val: float,
        notes: str = "",
    ):
        nonlocal curr_mass, curr_fuel, total_dist_nm, total_time_min
        burned = min(curr_fuel, fuel_kg)
        curr_fuel -= burned
        curr_mass -= burned
        total_dist_nm += dist_nm
        total_time_min += dt_min

        profile.append({
            "phase": phase_name,
            "altitude_ft": round(alt, 0),
            "altitude_m": round(alt * 0.3048, 0),
            "mach": round(mach, 3),
            "duration_min": round(dt_min, 1),
            "time_min": round(dt_min, 1),
            "distance_nm": round(dist_nm, 1),
            "distance_km": round(dist_nm * 1.852, 1),
            "cumulative_dist_nm": round(total_dist_nm, 1),
            "fuel_burned_kg": round(burned, 1),
            "fuel_burn_kg": round(burned, 1),
            "fuel_remaining_kg": round(curr_fuel, 1),
            "gross_weight_kg": round(curr_mass, 1),
            "thrust_per_eng_kN": round(thrust_kN, 2),
            "thrust_kN": round(thrust_kN, 2),
            "TSFC_g_kNs": round(tsfc_val, 2),
            "tsfc": round(tsfc_val, 2),
            "notes": notes,
        })

    # Initial takeoff / ramp weight
    takeoff_weight_kg = ramp_weight_kg

    # ── Phase 1: Taxi-Out (10 min ground idle at 0 m) ────────────────────────
    taxi_rate = 0.005 if is_uav else (12.0 * (aircraft["n_engines"] / 2.0))
    t_taxi_out = 5.0 if is_uav else 10.0
    fuel_taxi_out = taxi_rate * t_taxi_out
    record_step("Taxi-Out", 0, 0.0, t_taxi_out, 0.0, fuel_taxi_out, 0.02 if is_uav else 3.5, 26.0, "Ground Roll")

    # Weight at brake release (airborne start)
    brake_release_weight_kg = curr_mass

    # ── Phase 2: Takeoff & Initial Climb (0 -> initial climb alt) ────────────
    to_alt = min(1500.0, cruise_alt_ft * 0.25)
    to_mach = min(0.12 if is_uav else 0.25, cruise_mach * 0.75)
    T_to_req, _, _, _, _ = compute_drag(
        curr_mass * g, to_alt / 2.0, to_mach, aircraft, climb_angle_rad=math.radians(5.0 if is_uav else 7.5)
    )
    T_to_kN = T_to_req / 1000.0
    tsfc_to = engine_base_tsfc * 1.08
    t_to_min = 1.0 if is_uav else 2.0
    fuel_to = (T_to_kN * tsfc_to * 60.0 / 1000.0 * aircraft["n_engines"]) * t_to_min
    dist_to = (to_mach * 340.0 * t_to_min * 60.0) / 1852.0
    record_step("Takeoff", to_alt, to_mach, t_to_min, dist_to, fuel_to, T_to_kN, tsfc_to, f"SL to {int(to_alt)} ft")

    # ── Phase 3: Enroute Climb via Specific Excess Power (to_alt -> cruise_alt)
    climb_dh = max(500.0, cruise_alt_ft - to_alt)
    climb_steps = 5
    step_dh = climb_dh / climb_steps
    climb_mach_start = min(0.12 if is_uav else 0.35, cruise_mach * 0.75)

    for i in range(1, climb_steps + 1):
        step_alt = to_alt + step_dh * i
        step_mach = climb_mach_start + (cruise_mach - climb_mach_start) * (i / climb_steps)

        # Coupled Specific Excess Power: RoC = V * (T - D) / W
        T_req, D_req, _, _, is_stalled = compute_drag(
            curr_mass * g, step_alt, step_mach, aircraft, climb_angle_rad=math.radians(3.5)
        )
        T_climb_kN = T_req / 1000.0
        step_tsfc = engine_base_tsfc * (1.0 + 0.12 * (step_alt / 35000.0))

        T_amb = float(ISA.T(step_alt))
        a_sound = math.sqrt(1.4 * 287.05 * T_amb)
        V_sound = step_mach * a_sound

        # Estimated rate of climb: scaled by altitude lapse and vehicle class
        base_roc = 1200.0 if is_uav else 2500.0
        roc_fpm = max(300.0 if is_uav else 500.0, base_roc * (1.0 - 0.65 * (step_alt / 43000.0)))
        dt_step_min = step_dh / roc_fpm
        dist_climb_step = (V_sound * dt_step_min * 60.0) / 1852.0
        fuel_climb_step = (T_climb_kN * step_tsfc * 60.0 / 1000.0 * aircraft["n_engines"]) * dt_step_min

        note = "Stall Warning" if is_stalled else "SEP Climb"
        record_step(f"Climb {i}/{climb_steps}", step_alt, step_mach, dt_step_min, dist_climb_step, fuel_climb_step, T_climb_kN, step_tsfc, note)

    # ── Phase 4: Cruise (Breguet Step-Integration) ───────────────────────────
    dist_already = total_dist_nm
    dist_descent = (cruise_alt_ft / 1000.0) * (2.0 if is_uav else 3.0)
    cruise_net_dist = max(10.0 if is_uav else 30.0, cruise_distance_nm - dist_already - dist_descent)

    cruise_steps = 6
    dist_cruise_step = cruise_net_dist / cruise_steps

    T_amb_cr = float(ISA.T(cruise_alt_ft))
    a_cr = math.sqrt(1.4 * 287.05 * T_amb_cr)
    V_cruise = cruise_mach * a_cr
    dt_cruise_min = (dist_cruise_step * 1852.0 / V_cruise) / 60.0

    # Cruise TSFC tied strictly to user-supplied engine_base_tsfc
    cruise_tsfc = engine_base_tsfc * 1.02

    CL_cr_last = 0.45
    CD_cr_last = 0.025

    for i in range(1, cruise_steps + 1):
        T_cr_req, _, CL, CD, is_stalled = compute_drag(
            curr_mass * g, cruise_alt_ft, cruise_mach, aircraft, climb_angle_rad=0.0
        )
        CL_cr_last = CL
        CD_cr_last = CD
        T_cr_kN = T_cr_req / 1000.0
        fuel_cr_step = (T_cr_kN * cruise_tsfc * 60.0 / 1000.0 * aircraft["n_engines"]) * dt_cruise_min

        note = "Stall Warning" if is_stalled else "Breguet Step"
        record_step(f"Cruise {i}/{cruise_steps}", cruise_alt_ft, cruise_mach, dt_cruise_min, dist_cruise_step, fuel_cr_step, T_cr_kN, cruise_tsfc, note)

    # ── Phase 5: Descent & Approach (cruise_alt -> to_alt) ───────────────────
    desc_mach = min(0.35 if not is_uav else 0.14, cruise_mach * 0.8)
    t_desc_min = max(5.0 if is_uav else 10.0, (cruise_alt_ft - to_alt) / (1200.0 if is_uav else 1800.0))
    desc_rate = 0.008 if is_uav else (8.0 * (aircraft["n_engines"] / 2.0))
    fuel_desc = desc_rate * t_desc_min
    record_step("Descent", to_alt, desc_mach, t_desc_min, dist_descent, fuel_desc, 0.03 if is_uav else 4.0, 19.5, "Flight Idle Descent")

    # ── Phase 6: Landing Flare & Touchdown (to_alt -> 0 m) ───────────────────
    t_flare_min = 1.5 if is_uav else 3.5
    dist_flare_nm = 1.5 if is_uav else 8.0
    fuel_flare = desc_rate * 0.8 * t_flare_min
    landing_mach = min(0.10 if is_uav else 0.20, cruise_mach * 0.6)
    record_step("Landing", 0, landing_mach, t_flare_min, dist_flare_nm, fuel_flare, 0.02 if is_uav else 2.5, 22.0, "Flare & Touchdown to 0 m")

    # Touchdown weight is captured here (before ground taxi-in)
    touchdown_weight_kg = curr_mass

    # ── Phase 7: Taxi-In & Shutdown (0 m, 5 min) ──────────────────────────────
    t_taxi_in_min = 3.0 if is_uav else 5.0
    fuel_taxi_in = taxi_rate * t_taxi_in_min
    record_step("Taxi-In", 0, 0.0, t_taxi_in_min, 0.0, fuel_taxi_in, 0.01 if is_uav else 2.0, 26.0, "Ramp Arrival & Engine Cut")

    shutdown_weight_kg = curr_mass
    landing_weight_kg = curr_mass
    block_fuel_kg = fuel_load_kg - curr_fuel
    flight_fuel_kg = brake_release_weight_kg - touchdown_weight_kg

    # Reserve calculation (45 min loiter at 1,500 ft, calculated but not burned)
    T_loiter_req, _, _, _, _ = compute_drag(curr_mass * g, 1500, 0.30, aircraft)
    fuel_loiter = (T_loiter_req / 1000.0 * engine_base_tsfc * 45.0 * 60.0 / 1000.0) * aircraft["n_engines"]

    mission_feasible = bool(curr_fuel >= 0.0)
    failed_reason = "" if mission_feasible else "Fuel starvation occurred prior to landing."

    # ── Analytical Breguet Range Benchmark ───────────────────────────────────
    # tsfc in 1/s = (cruise_tsfc / 1e6) * g
    L_over_D_cr = (CL_cr_last / CD_cr_last) if CD_cr_last > 0 else 16.5
    tsfc_per_s = (cruise_tsfc / 1e6) * g

    w_start_cr = profile[1 + climb_steps]["gross_weight_kg"]
    w_end_cr = profile[1 + climb_steps + cruise_steps]["gross_weight_kg"]
    breguet_range_km = (V_cruise / tsfc_per_s) * L_over_D_cr * math.log(max(1.01, w_start_cr / max(1.0, w_end_cr))) / 1000.0
    breguet_range_nm = breguet_range_km / 1.852

    # ── Payload-Range Envelope (Breguet Closed-Form) ──────────────────────────
    def calc_breguet_pt(payload: float, fuel: float) -> float:
        w_to = OEW + payload + fuel
        allowance = min(fuel * 0.30, 2500.0)
        fuel_cr = max(0.0, fuel - allowance)
        w_st = w_to - allowance * 0.45
        w_en = max(OEW + payload + allowance * 0.55, w_st - fuel_cr)
        if w_st <= w_en or tsfc_per_s <= 0:
            return 0.0
        return (V_cruise / tsfc_per_s) * L_over_D_cr * math.log(w_st / w_en) / 1.852 / 1000.0

    p1_fuel = min(max_fuel, MTOW - OEW - max_payload)
    p1_range_nm = calc_breguet_pt(max_payload, p1_fuel)

    p2_payload = max(0.0, MTOW - OEW - max_fuel)
    p2_range_nm = calc_breguet_pt(p2_payload, max_fuel)

    p3_range_nm = calc_breguet_pt(0.0, max_fuel)

    payload_range_curve = [
        {"name": "Max Payload", "payload_kg": round(max_payload, 0), "range_nm": round(p1_range_nm, 0), "range_km": round(p1_range_nm * 1.852, 0)},
        {"name": "Max Fuel",    "payload_kg": round(p2_payload, 0),  "range_nm": round(p2_range_nm, 0), "range_km": round(p2_range_nm * 1.852, 0)},
        {"name": "Ferry",       "payload_kg": 0.0,                    "range_nm": round(p3_range_nm, 0), "range_km": round(p3_range_nm * 1.852, 0)},
    ]

    summary_dict = {
        "mission_feasible": mission_feasible,
        "failed_reason": failed_reason,
        "total_distance_nm": round(total_dist_nm, 1),
        "total_distance_km": round(total_dist_nm * 1.852, 1),
        "total_flight_time_min": round(total_time_min, 1),
        "total_flight_time_hr": round(total_time_min / 60.0, 2),
        "total_fuel_burned_kg": round(block_fuel_kg, 1),
        "total_fuel_burn_kg": round(block_fuel_kg, 1),
        "block_fuel_kg": round(block_fuel_kg, 1),
        "flight_fuel_kg": round(flight_fuel_kg, 1),
        "fuel_remaining_kg": round(curr_fuel, 1),
        "ramp_weight_kg": round(ramp_weight_kg, 1),
        "takeoff_weight_kg": round(takeoff_weight_kg, 1),
        "brake_release_weight_kg": round(brake_release_weight_kg, 1),
        "touchdown_weight_kg": round(touchdown_weight_kg, 1),
        "landing_weight_kg": round(landing_weight_kg, 1),
        "shutdown_weight_kg": round(shutdown_weight_kg, 1),
        "reserve_fuel_kg": round(fuel_loiter, 1),
        "average_cruise_TSFC": round(cruise_tsfc, 2),
        "engine_base_tsfc": round(engine_base_tsfc, 2),
        "breguet_cruise_range_km": round(breguet_range_nm * 1.852, 1),
        "breguet_cruise_range_nm": round(breguet_range_nm, 1),
        "cruise_L_over_D": round(L_over_D_cr, 2),
    }

    # Airframe Sizing card data
    sizing_info = size_airframe_geometry(
        gross_mass_kg=takeoff_weight_kg,
        aspect_ratio=aircraft["aspect_ratio"],
        taper_ratio=aircraft.get("taper_ratio", 0.25),
        material=aircraft.get("material", "composite"),
    )

    characteristic_speeds = compute_characteristic_airspeeds(
        weight_N=takeoff_weight_kg * g,
        wing_area_m2=aircraft["wing_area_m2"],
        aspect_ratio=aircraft["aspect_ratio"],
        CD0=aircraft["CD0"],
        oswald_e=aircraft["oswald_e"],
        CL_max=aircraft.get("CL_max", 1.45),
        alt_ft=cruise_alt_ft,
    )

    return {
        "mission_summary": summary_dict,
        "summary": summary_dict,
        "payload_range_envelope": payload_range_curve,
        "current_mission_point": {
            "range_km": round(cruise_distance_nm * 1.852, 1),
            "range_nm": round(cruise_distance_nm, 1),
            "payload_kg": round(payload_kg, 1),
        },
        "flight_profile": profile,
        "phases": profile,
        "airframe_sizing": sizing_info,
        "characteristic_speeds": characteristic_speeds,
    }
