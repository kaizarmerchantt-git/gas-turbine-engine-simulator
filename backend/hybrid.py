"""
Gas Turbine Engine Simulator — Hybrid Electric Propulsion Integration
=====================================================================
Extension 5 from Project Scope.

Models hybrid electric propulsion architectures:
1. Parallel Hybrid:
   - Mechanical shaft coupling of Gas Turbine (GT) and Electric Motor (EM).
   - Degree of hybridization of power: H_P = P_motor / P_total_shaft in [0, 1].
   - GT down-sizing and throttling benefits during cruise.
2. Series Hybrid:
   - Gas Turbine operates as a constant-efficiency Turbogenerator.
   - Decoupled from propulsors; drives an electric generator to feed a DC bus.
   - Electric motors drive fans/propellers. Battery supplies peak power or absorbs charge.
3. Turboelectric (and Partial Turboelectric):
   - Mechanical decoupling without heavy batteries (M_batt = 0).
   - Generator-inverter-motor loss chain driving distributed electric fans.
4. Battery State of Charge (SoC):
   - Energy capacity E_batt [kWh] from battery mass [kg] and specific energy [Wh/kg].
   - Dynamic SoC tracking with C-rate limits and 20% minimum reserve protection.
5. Multi-Phase Mission Energy Audit:
   - 6-phase mission (Taxi, Takeoff, Climb, Cruise, Descent, Loiter).
   - Fuel burn reduction, net CO2 savings, and primary energy comparison vs conventional baseline.
6. Breakeven Trade Studies:
   - Stage length and battery technology sensitivity sweeps.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
try:
    import ISA_module as ISA
    from mission import compute_drag, DEFAULT_AIRCRAFT
except ImportError:
    from . import ISA_module as ISA
    from .mission import compute_drag, DEFAULT_AIRCRAFT


# Default electrical powertrain component efficiencies and specific powers
DEFAULT_POWERTRAIN = {
    "eta_motor": 0.95,          # Electric motor efficiency
    "eta_inverter": 0.98,       # Power electronics / inverter efficiency
    "eta_generator": 0.96,      # Generator efficiency (series / turboelectric)
    "eta_dist": 0.99,           # Cable / DC bus distribution efficiency
    "eta_batt_disch": 0.98,     # Battery internal discharge efficiency
    "eta_batt_chg": 0.95,       # Battery internal charge efficiency
    "specific_energy_Wh_kg": 250.0, # Battery specific energy density [Wh/kg]
    "motor_power_density_kW_kg": 5.0, # Electric motor power density [kW/kg]
    "inverter_power_density_kW_kg": 15.0, # Inverter power density [kW/kg]
    "generator_power_density_kW_kg": 6.0, # Generator power density [kW/kg]
    "propulsor_eta": 0.82,      # Propeller / Fan propulsive efficiency
    "base_bsfc_kg_kWh": 0.280,  # Gas turbine base Brake Specific Fuel Consumption [kg/(kW*h)]
}


def calc_bsfc(throttle_fraction: float, base_bsfc: float = 0.280) -> float:
    """
    Computes part-load Gas Turbine BSFC [kg/(kW*h)] based on typical gas turbine
    thermal efficiency degradation curves.
    At 100% rated power, BSFC is minimum. At 30% power, BSFC increases ~25-35%.
    """
    thr = max(0.15, min(1.10, throttle_fraction))
    # Quadratic part-load factor: minimum at thr=0.95-1.0
    factor = 1.0 + 0.55 * ((1.0 - thr) ** 2)
    return base_bsfc * factor


def evaluate_single_hybrid_point(
    architecture: str = "parallel",     # 'parallel', 'series', 'turboelectric'
    shaft_power_req_kW: float = 2000.0, # Total mechanical power required at propulsor [kW]
    hybrid_power_ratio_HP: float = 0.25,# H_P = P_motor / P_shaft_req (for parallel)
    battery_mass_kg: float = 1200.0,
    battery_soc: float = 0.85,          # Instantaneous State of Charge [0..1]
    powertrain: Dict[str, Any] = DEFAULT_POWERTRAIN,
    turbogen_rated_kW: Optional[float] = None, # For series hybrid
) -> Dict[str, Any]:
    """
    Evaluates instantaneous electrical and thermodynamic states at a single operating point.
    """
    arch = architecture.lower()
    eta_m = powertrain.get("eta_motor", 0.95)
    eta_inv = powertrain.get("eta_inverter", 0.98)
    eta_gen = powertrain.get("eta_generator", 0.96)
    eta_dist = powertrain.get("eta_dist", 0.99)
    eta_b_dis = powertrain.get("eta_batt_disch", 0.98)
    eta_b_chg = powertrain.get("eta_batt_chg", 0.95)
    sp_energy = powertrain.get("specific_energy_Wh_kg", 250.0)
    base_bsfc = powertrain.get("base_bsfc_kg_kWh", 0.280)

    # Battery capacity
    battery_capacity_kWh = (battery_mass_kg * sp_energy) / 1000.0

    # Low-battery protection: if SoC <= 0.20, electric boost is disabled
    effective_HP = hybrid_power_ratio_HP if battery_soc > 0.20 else 0.0

    if arch == "parallel":
        # Mechanical split on propeller/fan shaft
        P_motor_mech = shaft_power_req_kW * effective_HP
        P_gt_mech = shaft_power_req_kW - P_motor_mech

        # Electric motor electrical demand
        P_motor_elec_in = P_motor_mech / eta_m if eta_m > 0 else 0.0
        P_dc_bus_req = P_motor_elec_in / (eta_inv * eta_dist) if (eta_inv * eta_dist) > 0 else 0.0

        # Battery discharge power
        P_batt_kW = P_dc_bus_req / eta_b_dis if eta_b_dis > 0 else 0.0
        P_gen_kW = 0.0

        # Gas turbine fuel flow
        thr = P_gt_mech / max(1.0, shaft_power_req_kW)
        bsfc = calc_bsfc(thr, base_bsfc) if P_gt_mech > 0 else 0.0
        fuel_flow_kg_s = (P_gt_mech * bsfc) / 3600.0

    elif arch == "series":
        # Propulsors driven 100% by electric motors
        P_motor_mech = shaft_power_req_kW
        P_motor_elec_in = P_motor_mech / eta_m if eta_m > 0 else 0.0
        P_dc_bus_req = P_motor_elec_in / (eta_inv * eta_dist) if (eta_inv * eta_dist) > 0 else 0.0

        # Turbogenerator sized to provide baseline or cruise power
        tg_rated = turbogen_rated_kW if turbogen_rated_kW is not None else shaft_power_req_kW * 0.75
        P_gt_mech = tg_rated
        P_gen_elec = P_gt_mech * eta_gen * eta_inv

        # Power balance on DC bus
        if P_dc_bus_req > P_gen_elec and battery_soc > 0.20:
            P_batt_kW = (P_dc_bus_req - P_gen_elec) / eta_b_dis
        elif P_dc_bus_req < P_gen_elec and battery_soc < 0.98:
            P_batt_kW = -(P_gen_elec - P_dc_bus_req) * eta_b_chg
        else:
            P_gt_mech = P_dc_bus_req / (eta_gen * eta_inv)
            P_gen_elec = P_dc_bus_req
            P_batt_kW = 0.0

        P_gen_kW = P_gen_elec
        bsfc = base_bsfc
        fuel_flow_kg_s = (P_gt_mech * bsfc) / 3600.0

    elif arch == "turboelectric":
        # Direct generator to motor, zero battery
        P_batt_kW = 0.0
        battery_mass_kg = 0.0
        battery_capacity_kWh = 0.0
        P_motor_mech = shaft_power_req_kW

        overall_elec_eta = eta_m * eta_inv * eta_dist * eta_gen * eta_inv
        P_gt_mech = P_motor_mech / max(0.5, overall_elec_eta)
        P_gen_kW = P_gt_mech * eta_gen * eta_inv

        bsfc = calc_bsfc(0.85, base_bsfc)
        fuel_flow_kg_s = (P_gt_mech * bsfc) / 3600.0
    else:
        raise ValueError(f"Unknown hybrid architecture '{architecture}'. Must be parallel, series, or turboelectric.")

    # C-rate
    c_rate = abs(P_batt_kW) / max(0.1, battery_capacity_kWh) if battery_capacity_kWh > 0 else 0.0
    dSoC_dt = -P_batt_kW / (battery_capacity_kWh * 3600.0) if battery_capacity_kWh > 0 else 0.0

    # Conventional baseline comparison
    conv_bsfc = calc_bsfc(1.0, base_bsfc)
    conv_fuel_flow_kg_s = (shaft_power_req_kW * conv_bsfc) / 3600.0
    fuel_savings_pct = max(-50.0, min(100.0, (1.0 - (fuel_flow_kg_s / max(1e-6, conv_fuel_flow_kg_s))) * 100.0))

    # Weight estimation
    p_dens_mot = powertrain.get("motor_power_density_kW_kg", 5.0)
    p_dens_inv = powertrain.get("inverter_power_density_kW_kg", 15.0)
    p_dens_gen = powertrain.get("generator_power_density_kW_kg", 6.0)

    motor_mass_kg = (P_motor_mech / p_dens_mot) if arch != "turboelectric" else (shaft_power_req_kW / p_dens_mot)
    inverter_mass_kg = (P_motor_elec_in / p_dens_inv) if arch != "turboelectric" else (shaft_power_req_kW / p_dens_inv)
    generator_mass_kg = (P_gt_mech / p_dens_gen) if arch in ["series", "turboelectric"] else 0.0
    total_elec_mass_kg = battery_mass_kg + motor_mass_kg + inverter_mass_kg + generator_mass_kg

    return {
        "architecture": arch,
        "shaft_power_req_kW": shaft_power_req_kW,
        "hybrid_power_ratio_HP": effective_HP,
        "gas_turbine_power_kW": P_gt_mech,
        "electric_motor_power_kW": P_motor_mech,
        "generator_power_kW": P_gen_kW,
        "battery_power_kW": P_batt_kW,
        "battery_soc": battery_soc,
        "battery_mass_kg": battery_mass_kg,
        "battery_capacity_kWh": battery_capacity_kWh,
        "c_rate": c_rate,
        "dSoC_dt_percent_per_min": dSoC_dt * 6000.0,
        "fuel_flow_kg_s": fuel_flow_kg_s,
        "fuel_flow_kg_h": fuel_flow_kg_s * 3600.0,
        "bsfc_kg_kWh": bsfc,
        "conventional_fuel_flow_kg_h": conv_fuel_flow_kg_s * 3600.0,
        "fuel_savings_pct": fuel_savings_pct,
        "powertrain_masses": {
            "battery_kg": battery_mass_kg,
            "motor_kg": motor_mass_kg,
            "inverter_kg": inverter_mass_kg,
            "generator_kg": generator_mass_kg,
            "total_elec_sys_kg": total_elec_mass_kg,
        }
    }


def run_hybrid_mission_simulation(
    architecture: str = "parallel",
    cruise_alt_m: float = 9144.0,     # 30,000 ft
    cruise_mach: float = 0.72,
    cruise_dist_km: float = 900.0,     # ~486 nm (typical regional hybrid route)
    payload_kg: float = 6500.0,
    battery_mass_kg: float = 1800.0,
    specific_energy_Wh_kg: float = 300.0,
    takeoff_hybrid_ratio: float = 0.35, # Peak electric assist at takeoff
    climb_hybrid_ratio: float = 0.20,   # Electric climb assist
    cruise_hybrid_ratio: float = 0.05,  # Moderate/zero cruise assist
    descent_hybrid_ratio: float = 0.0,  # Zero assist or regen
    aircraft: Dict[str, Any] = DEFAULT_AIRCRAFT,
    powertrain: Dict[str, Any] = DEFAULT_POWERTRAIN,
) -> Dict[str, Any]:
    """
    Simulates a 6-phase flight mission for a hybrid electric aircraft,
    tracking fuel burn, battery SoC, CO2 emissions, and comparing directly
    against an equivalent conventional non-hybrid aircraft.
    """
    pt = dict(powertrain)
    pt["specific_energy_Wh_kg"] = specific_energy_Wh_kg

    total_capacity_kWh = (battery_mass_kg * specific_energy_Wh_kg) / 1000.0
    soc = 1.00

    p_dens_mot = pt.get("motor_power_density_kW_kg", 5.0)
    p_dens_inv = pt.get("inverter_power_density_kW_kg", 15.0)
    p_dens_gen = pt.get("generator_power_density_kW_kg", 6.0)

    takeoff_T_per_eng, _, _, _ = compute_drag(aircraft["MTOW_kg"] * 9.80665, 0.0, 0.22, aircraft, climb_angle_rad=0.08)
    peak_shaft_power_kW = (takeoff_T_per_eng * 70.0 / 1000.0) / pt.get("propulsor_eta", 0.82)
    motor_mass_kg = (peak_shaft_power_kW * takeoff_hybrid_ratio) / p_dens_mot
    inverter_mass_kg = motor_mass_kg * 0.35
    gen_mass_kg = (peak_shaft_power_kW / p_dens_gen) if architecture in ["series", "turboelectric"] else 0.0
    total_elec_mass_kg = battery_mass_kg + motor_mass_kg + inverter_mass_kg + gen_mass_kg

    conv_initial_weight = aircraft["OEW_kg"] + payload_kg + 5000.0
    hybrid_initial_weight = aircraft["OEW_kg"] + total_elec_mass_kg + payload_kg + 4000.0
    hybrid_initial_weight = min(aircraft["MTOW_kg"] * 1.05, hybrid_initial_weight)

    phase_defs = [
        {"name": "Taxi-out", "alt_m": 0.0, "mach": 0.04, "dist_km": 0.0, "time_min": 15.0, "hp": 1.0 if architecture=="parallel" else 0.5},
        {"name": "Takeoff",  "alt_m": 150.0, "mach": 0.22, "dist_km": 8.0, "time_min": 1.5, "hp": takeoff_hybrid_ratio},
        {"name": "Climb",    "alt_m": cruise_alt_m * 0.6, "mach": 0.55, "dist_km": 140.0, "time_min": 18.0, "hp": climb_hybrid_ratio},
        {"name": "Cruise",   "alt_m": cruise_alt_m, "mach": cruise_mach, "dist_km": cruise_dist_km, "time_min": None, "hp": cruise_hybrid_ratio},
        {"name": "Descent",  "alt_m": cruise_alt_m * 0.4, "mach": 0.50, "dist_km": 120.0, "time_min": 16.0, "hp": descent_hybrid_ratio},
        {"name": "Loiter (Reserves)", "alt_m": 1500.0, "mach": 0.35, "dist_km": 0.0, "time_min": 45.0, "hp": 0.0},
    ]

    current_weight_kg = hybrid_initial_weight
    conv_weight_kg = conv_initial_weight
    total_hybrid_fuel_kg = 0.0
    total_conv_fuel_kg = 0.0
    total_elec_energy_kWh = 0.0
    total_flight_time_min = 0.0
    phases_out = []

    for p_def in phase_defs:
        alt_ft = p_def["alt_m"] * 3.28084
        mach = p_def["mach"]
        hp_target = p_def["hp"]

        T_amb = float(ISA.T(alt_ft))
        a = math.sqrt(1.4 * 287.05 * T_amb)
        V_mps = max(15.0, mach * a)

        if p_def["time_min"] is not None:
            t_min = p_def["time_min"]
            d_km = (V_mps * t_min * 60.0) / 1000.0 if p_def["dist_km"] == 0.0 and p_def["name"] != "Taxi-out" else p_def["dist_km"]
        else:
            d_km = p_def["dist_km"]
            t_min = (d_km * 1000.0) / (V_mps * 60.0)

        t_sec = t_min * 60.0
        total_flight_time_min += t_min

        climb_angle = 0.035 if p_def["name"] == "Climb" else -0.025 if p_def["name"] == "Descent" else 0.0
        T_eng_N, D_tot_N, CL, CD = compute_drag(current_weight_kg * 9.80665, alt_ft, mach, aircraft, climb_angle)
        P_shaft_req_kW = (T_eng_N * V_mps / 1000.0) / pt.get("propulsor_eta", 0.82)
        P_shaft_req_kW = max(100.0, P_shaft_req_kW)

        T_conv_N, _, _, _ = compute_drag(conv_weight_kg * 9.80665, alt_ft, mach, aircraft, climb_angle)
        P_conv_shaft_kW = (T_conv_N * V_mps / 1000.0) / pt.get("propulsor_eta", 0.82)
        conv_fuel_flow = (P_conv_shaft_kW * calc_bsfc(1.0, pt["base_bsfc_kg_kWh"])) / 3600.0
        conv_phase_fuel_kg = conv_fuel_flow * t_sec
        total_conv_fuel_kg += conv_phase_fuel_kg
        conv_weight_kg -= conv_phase_fuel_kg

        pt_res = evaluate_single_hybrid_point(
            architecture=architecture,
            shaft_power_req_kW=P_shaft_req_kW,
            hybrid_power_ratio_HP=hp_target,
            battery_mass_kg=battery_mass_kg,
            battery_soc=soc,
            powertrain=pt,
        )

        avail_soc = max(0.0, soc - 0.20)
        max_avail_elec_kWh = avail_soc * total_capacity_kWh
        requested_elec_kWh = pt_res["battery_power_kW"] * (t_sec / 3600.0)

        if requested_elec_kWh > max_avail_elec_kWh and requested_elec_kWh > 0 and total_capacity_kWh > 0:
            phase_elec_kWh = max_avail_elec_kWh
            frac_electric_met = max_avail_elec_kWh / requested_elec_kWh
            unmet_motor_mech = pt_res["electric_motor_power_kW"] * (1.0 - frac_electric_met)
            addl_fuel_kg = (unmet_motor_mech * calc_bsfc(1.0, pt["base_bsfc_kg_kWh"]) / 3600.0) * t_sec
            phase_fuel_kg = (pt_res["fuel_flow_kg_s"] * frac_electric_met * t_sec) + addl_fuel_kg
            soc = 0.20
        else:
            phase_elec_kWh = requested_elec_kWh
            phase_fuel_kg = pt_res["fuel_flow_kg_s"] * t_sec
            if total_capacity_kWh > 0:
                delta_soc = phase_elec_kWh / total_capacity_kWh
                soc = max(0.20, min(1.0, soc - delta_soc))

        total_hybrid_fuel_kg += phase_fuel_kg
        total_elec_energy_kWh += max(0.0, phase_elec_kWh)
        current_weight_kg -= phase_fuel_kg

        phases_out.append({
            "phase": p_def["name"],
            "duration_min": t_min,
            "distance_km": d_km,
            "hybrid_power_ratio": pt_res["hybrid_power_ratio_HP"],
            "gt_power_kW": pt_res["gas_turbine_power_kW"],
            "motor_power_kW": pt_res["electric_motor_power_kW"],
            "battery_power_kW": pt_res["battery_power_kW"],
            "fuel_burned_kg": phase_fuel_kg,
            "elec_energy_kWh": phase_elec_kWh,
            "end_soc": soc,
            "c_rate": pt_res["c_rate"],
            "aircraft_weight_kg": current_weight_kg,
        })

    fuel_saved_kg = total_conv_fuel_kg - total_hybrid_fuel_kg
    fuel_saved_pct = (fuel_saved_kg / max(1.0, total_conv_fuel_kg)) * 100.0
    co2_saved_kg = fuel_saved_kg * 3.16

    primary_energy_hybrid_MJ = (total_hybrid_fuel_kg * 43.1) + (total_elec_energy_kWh * 3.6)
    primary_energy_conv_MJ = total_conv_fuel_kg * 43.1
    energy_saved_pct = ((primary_energy_conv_MJ - primary_energy_hybrid_MJ) / max(1.0, primary_energy_conv_MJ)) * 100.0

    return {
        "architecture": architecture,
        "aircraft_type": aircraft.get("name", "Regional Jet"),
        "mission_distance_km": cruise_dist_km + 268.0,
        "total_flight_time_min": total_flight_time_min,
        "total_flight_time_hr": total_flight_time_min / 60.0,
        "battery_mass_kg": battery_mass_kg,
        "battery_capacity_kWh": total_capacity_kWh,
        "specific_energy_Wh_kg": specific_energy_Wh_kg,
        "powertrain_hardware_mass_kg": total_elec_mass_kg,
        "summary": {
            "hybrid_fuel_burn_kg": total_hybrid_fuel_kg,
            "conventional_fuel_burn_kg": total_conv_fuel_kg,
            "fuel_saved_kg": fuel_saved_kg,
            "fuel_saved_percent": fuel_saved_pct,
            "co2_reduction_kg": co2_saved_kg,
            "electrical_energy_used_kWh": total_elec_energy_kWh,
            "final_battery_soc": soc,
            "primary_energy_hybrid_MJ": primary_energy_hybrid_MJ,
            "primary_energy_conv_MJ": primary_energy_conv_MJ,
            "energy_saved_percent": energy_saved_pct,
            "breakeven_indicator": "Favorable Fuel Savings" if fuel_saved_pct > 0 else "Battery Weight Exceeds Fuel Savings",
        },
        "phases": phases_out,
    }


def run_hybrid_trade_study(
    study_type: str = "hybrid_ratio",
    architecture: str = "parallel",
    n_points: int = 12,
    base_mission_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Performs parametric trade studies for hybrid electric aircraft sizing:
    - 'hybrid_ratio': Varies takeoff H_P from 0.0 to 0.50
    - 'specific_energy': Varies battery specific energy from 180 to 550 Wh/kg
    - 'distance': Varies cruise distance from 300 to 2000 km to identify breakeven range
    """
    kwargs = base_mission_kwargs or {}
    points = []

    if study_type == "hybrid_ratio":
        x_label = "Takeoff Hybrid Ratio (H_P)"
        hp_vals = [i * (0.50 / max(1, n_points - 1)) for i in range(n_points)]
        for hp in hp_vals:
            res = run_hybrid_mission_simulation(
                architecture=architecture,
                takeoff_hybrid_ratio=hp,
                climb_hybrid_ratio=hp * 0.6,
                **kwargs
            )
            points.append({
                "x": hp,
                "fuel_saved_percent": res["summary"]["fuel_saved_percent"],
                "fuel_burn_kg": res["summary"]["hybrid_fuel_burn_kg"],
                "elec_energy_kWh": res["summary"]["electrical_energy_used_kWh"],
                "final_soc": res["summary"]["final_battery_soc"],
            })

    elif study_type == "specific_energy":
        x_label = "Battery Specific Energy [Wh/kg]"
        e_vals = [180.0 + i * ((550.0 - 180.0) / max(1, n_points - 1)) for i in range(n_points)]
        for e_sp in e_vals:
            res = run_hybrid_mission_simulation(
                architecture=architecture,
                specific_energy_Wh_kg=e_sp,
                **kwargs
            )
            points.append({
                "x": e_sp,
                "fuel_saved_percent": res["summary"]["fuel_saved_percent"],
                "fuel_burn_kg": res["summary"]["hybrid_fuel_burn_kg"],
                "elec_energy_kWh": res["summary"]["electrical_energy_used_kWh"],
                "final_soc": res["summary"]["final_battery_soc"],
            })

    elif study_type == "distance":
        x_label = "Cruise Distance [km]"
        d_vals = [300.0 + i * ((2000.0 - 300.0) / max(1, n_points - 1)) for i in range(n_points)]
        for dist in d_vals:
            res = run_hybrid_mission_simulation(
                architecture=architecture,
                cruise_dist_km=dist,
                **kwargs
            )
            points.append({
                "x": dist,
                "fuel_saved_percent": res["summary"]["fuel_saved_percent"],
                "fuel_burn_kg": res["summary"]["hybrid_fuel_burn_kg"],
                "elec_energy_kWh": res["summary"]["electrical_energy_used_kWh"],
                "final_soc": res["summary"]["final_battery_soc"],
            })
    else:
        raise ValueError(f"Unknown study_type '{study_type}'. Must be 'hybrid_ratio', 'specific_energy', or 'distance'.")

    return {
        "study_type": study_type,
        "architecture": architecture,
        "x_label": x_label,
        "points": points,
    }
