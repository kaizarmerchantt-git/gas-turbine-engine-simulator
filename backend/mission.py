"""
Gas Turbine Engine Simulator — Mission Analysis & Aircraft Integration
======================================================================
Extension 8 from Project Scope.

Integrates engine cycle fuel burn over a complete multi-phase flight mission:
- Standard 6-segment mission: Taxi-out -> Takeoff -> Climb -> Cruise -> Descent -> 45-min Loiter/Reserve
- Coupled aircraft aerodynamic drag polar: C_D = C_D0 + K * C_L^2 + C_D_wave
- Lift-weight and thrust-drag balance: L = W, T_req = (D + W*sin(gamma)) / N_eng
- Numerical integration of fuel burn: Delta W_fuel = int(mdot_fuel * dt)
- Closed-form Breguet range equation comparison
- Payload-Range envelope diagram calculation (Max Payload, Max Fuel, Ferry)
"""

import math
from typing import Dict, List, Any, Optional, Tuple
try:
    import ISA_module as ISA
except ImportError:
    from . import ISA_module as ISA


# Standard Regional Jet Aircraft Parameters (default based on E190 class)
DEFAULT_AIRCRAFT = {
    "name": "Twin-Jet Regional 100-Pax",
    "MTOW_kg": 45000.0,
    "OEW_kg": 26000.0,
    "max_payload_kg": 11500.0,
    "max_fuel_kg": 12500.0,
    "wing_area_m2": 78.0,
    "aspect_ratio": 9.2,
    "oswald_e": 0.82,
    "CD0": 0.0210,
    "n_engines": 2,
    "M_crit": 0.78,
}


def compute_drag(
    weight_N: float,
    alt_ft: float,
    mach: float,
    aircraft: Dict[str, Any] = DEFAULT_AIRCRAFT,
    climb_angle_rad: float = 0.0,
) -> Tuple[float, float, float, float]:
    """
    Computes aircraft drag, lift coefficient, and total required thrust.
    """
    rho = float(ISA.rho(alt_ft))
    T_amb = float(ISA.T(alt_ft))
    a = math.sqrt(1.4 * 287.05 * T_amb)
    V = max(10.0, mach * a)

    S = aircraft["wing_area_m2"]
    AR = aircraft["aspect_ratio"]
    e = aircraft["oswald_e"]
    CD0 = aircraft["CD0"]
    M_crit = aircraft.get("M_crit", 0.78)

    # Dynamic pressure
    q = 0.5 * rho * V * V

    # Lift equals weight in level/quasi-level flight: L = W * cos(gamma)
    L = weight_N * math.cos(climb_angle_rad)
    CL = max(0.05, min(1.4, L / (q * S))) if q > 0 else 0.5

    # Induced drag factor: K = 1 / (pi * e * AR)
    K = 1.0 / (math.pi * e * AR)
    CD_induced = K * (CL ** 2)

    # Wave drag divergence above critical Mach
    CD_wave = 25.0 * max(0.0, mach - M_crit) ** 4

    CD = CD0 + CD_induced + CD_wave
    D = q * S * CD

    # Total thrust required (includes climb component)
    T_total_req = D + weight_N * math.sin(climb_angle_rad)
    T_per_engine_N = T_total_req / aircraft["n_engines"]

    return T_per_engine_N, D, CL, CD


def run_mission_simulation(
    cruise_alt_ft: float = 35000.0,
    cruise_mach: float = 0.78,
    cruise_distance_nm: float = 1200.0,
    payload_kg: float = 9000.0,
    fuel_load_kg: Optional[float] = None,
    engine_base_tsfc: float = 16.5,  # g/(kN*s) ~= 0.58 lbm/(lbf*h)
    aircraft: Dict[str, Any] = DEFAULT_AIRCRAFT,
) -> Dict[str, Any]:
    """
    Simulates a full 6-phase flight mission.
    """
    MTOW = aircraft["MTOW_kg"]
    OEW = aircraft["OEW_kg"]
    max_payload = aircraft["max_payload_kg"]
    max_fuel = aircraft["max_fuel_kg"]

    actual_payload = min(payload_kg, max_payload)

    if fuel_load_kg is None:
        # Auto-load fuel up to MTOW or tank limit
        fuel_load_kg = min(max_fuel, MTOW - OEW - actual_payload)
    else:
        fuel_load_kg = min(fuel_load_kg, max_fuel)

    takeoff_weight_kg = OEW + actual_payload + fuel_load_kg
    if takeoff_weight_kg > MTOW:
        takeoff_weight_kg = MTOW
        fuel_load_kg = MTOW - OEW - actual_payload

    g = 9.80665
    curr_mass = takeoff_weight_kg
    curr_fuel = fuel_load_kg
    total_dist_nm = 0.0
    total_time_min = 0.0

    profile = []

    def record_step(phase, alt, mach, t_min, dist_nm, fuel_burn_step, thrust_kN, tsfc):
        nonlocal curr_mass, curr_fuel, total_dist_nm, total_time_min
        curr_fuel = max(0.0, curr_fuel - fuel_burn_step)
        curr_mass = max(OEW + actual_payload, curr_mass - fuel_burn_step)
        total_dist_nm += dist_nm
        total_time_min += t_min
        profile.append({
            "phase": phase,
            "altitude_ft": round(alt, 0),
            "mach": round(mach, 2),
            "time_min": round(total_time_min, 1),
            "distance_nm": round(total_dist_nm, 1),
            "fuel_remaining_kg": round(curr_fuel, 1),
            "fuel_burn_step_kg": round(fuel_burn_step, 1),
            "gross_weight_kg": round(curr_mass, 1),
            "thrust_per_eng_kN": round(thrust_kN, 2),
            "tsfc": round(tsfc, 2),
        })

    # 1. Taxi Out (10 min, ground idle)
    taxi_fuel_rate_kg_min = 12.0 * (aircraft["n_engines"] / 2.0)
    fuel_taxi_out = taxi_fuel_rate_kg_min * 10.0
    record_step("Taxi-Out", 0, 0.0, 10.0, 0.0, fuel_taxi_out, 3.5, 25.0)

    # 2. Takeoff & Acceleration (2 min, SLS -> 1,500 ft, M 0.25)
    T_to_req, _, _, _ = compute_drag(curr_mass * g, 500, 0.25, aircraft, climb_angle_rad=math.radians(8.0))
    T_to_kN = T_to_req / 1000.0
    # fuel rate = T_total * TSFC (TSFC in g/(kN*s) => kg/min = T_kN * tsfc * 60 / 1000 * n_eng)
    fuel_to_min = T_to_kN * engine_base_tsfc * 60.0 / 1000.0 * aircraft["n_engines"]
    fuel_to = fuel_to_min * 2.0
    dist_to = 0.25 * 340.0 * 120.0 / 1852.0  # nm
    record_step("Takeoff", 1500, 0.25, 2.0, dist_to, fuel_to, T_to_kN, engine_base_tsfc * 1.1)

    # 3. Climb (1,500 ft -> cruise_alt, M 0.35 -> cruise_mach, avg climb rate 2,000 ft/min)
    climb_dh = cruise_alt_ft - 1500.0
    t_climb_min = climb_dh / 2000.0
    climb_steps = 5
    dt_climb = t_climb_min / climb_steps
    climb_angle = math.radians(3.5)

    for i in range(1, climb_steps + 1):
        step_alt = 1500.0 + (climb_dh / climb_steps) * i
        step_mach = 0.35 + (cruise_mach - 0.35) * (i / climb_steps)
        T_climb_req, _, _, _ = compute_drag(curr_mass * g, step_alt, step_mach, aircraft, climb_angle_rad=climb_angle)
        T_climb_kN = T_climb_req / 1000.0
        step_tsfc = engine_base_tsfc * (1.0 + 0.15 * (step_alt / 35000.0))
        fuel_climb_step = (T_climb_kN * step_tsfc * 60.0 / 1000.0 * aircraft["n_engines"]) * dt_climb
        T_amb = float(ISA.T(step_alt))
        a = math.sqrt(1.4 * 287.05 * T_amb)
        V = step_mach * a
        dist_climb_step = (V * dt_climb * 60.0) / 1852.0
        record_step(f"Climb {i}/{climb_steps}", step_alt, step_mach, dt_climb, dist_climb_step, fuel_climb_step, T_climb_kN, step_tsfc)

    # 4. Cruise (Cruise at cruise_alt, cruise_mach until target distance)
    dist_already = total_dist_nm
    # Estimate descent distance ~ 3nm per 1,000 ft
    dist_descent = (cruise_alt_ft / 1000.0) * 3.0
    cruise_net_dist = max(50.0, cruise_distance_nm - dist_already - dist_descent)

    cruise_steps = 6
    dist_cruise_step = cruise_net_dist / cruise_steps

    T_amb = float(ISA.T(cruise_alt_ft))
    a = math.sqrt(1.4 * 287.05 * T_amb)
    V_cruise = cruise_mach * a
    dt_cruise_min = (dist_cruise_step * 1852.0 / V_cruise) / 60.0

    cruise_tsfc = engine_base_tsfc * 1.05

    for i in range(1, cruise_steps + 1):
        T_cruise_req, _, CL, CD = compute_drag(curr_mass * g, cruise_alt_ft, cruise_mach, aircraft, climb_angle_rad=0.0)
        T_cruise_kN = T_cruise_req / 1000.0
        fuel_cruise_step = (T_cruise_kN * cruise_tsfc * 60.0 / 1000.0 * aircraft["n_engines"]) * dt_cruise_min
        record_step(f"Cruise {i}/{cruise_steps}", cruise_alt_ft, cruise_mach, dt_cruise_min, dist_cruise_step, fuel_cruise_step, T_cruise_kN, cruise_tsfc)

    # 5. Descent (cruise_alt -> 1,500 ft, flight idle, 22 min)
    t_desc_min = 22.0
    desc_fuel_rate_kg_min = 8.0 * (aircraft["n_engines"] / 2.0)
    fuel_descent = desc_fuel_rate_kg_min * t_desc_min
    record_step("Descent", 1500, 0.40, t_desc_min, dist_descent, fuel_descent, 4.0, 18.0)

    # 6. Landing & 45-min Holding Reserve (1,500 ft, M 0.30)
    t_loiter_min = 45.0
    T_loiter_req, _, _, _ = compute_drag(curr_mass * g, 1500, 0.30, aircraft)
    T_loiter_kN = T_loiter_req / 1000.0
    fuel_loiter = (T_loiter_kN * engine_base_tsfc * 60.0 / 1000.0 * aircraft["n_engines"]) * t_loiter_min
    record_step("45-min Loiter Reserve", 1500, 0.30, t_loiter_min, 0.0, fuel_loiter, T_loiter_kN, engine_base_tsfc)

    total_trip_fuel_burned = fuel_load_kg - curr_fuel

    # Analytical Breguet range check for the cruise phase:
    # R = (V / (g * TSFC)) * (L/D) * ln(W_start / W_end)
    L_over_D_cruise = CL / CD if CD > 0 else 16.0
    # TSFC in 1/s: tsfc_kg_N_s = cruise_tsfc / 1e6
    tsfc_per_s = (cruise_tsfc / 1e6) * g
    W_start_cr = profile[1 + climb_steps]["gross_weight_kg"]
    W_end_cr = profile[1 + climb_steps + cruise_steps]["gross_weight_kg"]
    breguet_range_km = (V_cruise / tsfc_per_s) * L_over_D_cruise * math.log(W_start_cr / W_end_cr) / 1000.0
    breguet_range_nm = breguet_range_km / 1.852

    # Payload-Range Envelope (3 standard benchmark points via Breguet Integration)
    def calc_breguet_range(payload: float, fuel: float) -> float:
        w_to = OEW + payload + fuel
        # Allowances for ground ops, climb, descent, and 45-min reserve
        allowance = min(fuel * 0.35, 2500.0)
        fuel_cruise = max(0.0, fuel - allowance)
        w_start = w_to - allowance * 0.4
        w_end = max(OEW + payload + allowance * 0.6, w_start - fuel_cruise)
        if w_start <= w_end or tsfc_per_s <= 0:
            return 0.0
        return (V_cruise / tsfc_per_s) * L_over_D_cruise * math.log(w_start / w_end) / 1.852 / 1000.0

    # Point 1: Max Payload
    p1_fuel = min(max_fuel, MTOW - OEW - max_payload)
    p1_range_nm = calc_breguet_range(max_payload, p1_fuel)

    # Point 2: Full Fuel
    p2_payload = max(0.0, MTOW - OEW - max_fuel)
    p2_range_nm = calc_breguet_range(p2_payload, max_fuel)

    # Point 3: Ferry (Zero Payload, Full Fuel)
    ferry_range_nm = calc_breguet_range(0.0, max_fuel)

    payload_range_curve = [
        {"name": "Max Payload", "payload_kg": round(max_payload, 0), "range_nm": round(p1_range_nm, 0), "range_km": round(p1_range_nm * 1.852, 0)},
        {"name": "Max Fuel",    "payload_kg": round(p2_payload, 0), "range_nm": round(p2_range_nm, 0), "range_km": round(p2_range_nm * 1.852, 0)},
        {"name": "Ferry",       "payload_kg": 0.0,                   "range_nm": round(ferry_range_nm, 0), "range_km": round(ferry_range_nm * 1.852, 0)},
    ]

    cruise_tsfc = 18.0
    for ph in profile:
        if ph.get("phase") == "Cruise":
            cruise_tsfc = ph.get("TSFC_g_kNs", 18.0)
            break

    summary_dict = {
        "total_distance_nm": round(total_dist_nm, 1),
        "total_distance_km": round(total_dist_nm * 1.852, 1),
        "total_flight_time_min": round(total_time_min, 1),
        "total_flight_time_hr": round(total_time_min / 60.0, 2),
        "total_fuel_burned_kg": round(total_trip_fuel_burned, 1),
        "total_fuel_burn_kg": round(total_trip_fuel_burned, 1),
        "block_fuel_kg": round(total_trip_fuel_burned - fuel_loiter, 1),
        "fuel_remaining_kg": round(curr_fuel, 1),
        "takeoff_weight_kg": round(takeoff_weight_kg, 1),
        "landing_weight_kg": round(curr_mass, 1),
        "reserve_fuel_kg": round(fuel_loiter, 1),
        "average_cruise_TSFC": round(cruise_tsfc, 2),
        "breguet_cruise_range_km": round(breguet_range_nm * 1.852, 1),
        "breguet_cruise_range_nm": round(breguet_range_nm, 1),
        "cruise_L_over_D": round(L_over_D_cruise, 2),
    }

    return {
        "mission_summary": summary_dict,
        "summary": summary_dict,  # Frontend compatibility alias
        "payload_range_envelope": payload_range_curve,
        "current_mission_point": {
            "range_km": round(cruise_distance_nm * 1.852, 1),
            "range_nm": round(cruise_distance_nm, 1),
            "payload_kg": round(payload_kg, 1),
        },
        "flight_profile": profile,
        "phases": profile,        # Frontend compatibility alias
    }

