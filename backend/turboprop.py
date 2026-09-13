"""
Gas Turbine Engine Simulator — Turboprop & Turboshaft Cycle Variant
===================================================================
Extension 4 from Project Scope.

Models a gas generator core coupled to a free power turbine (PT):
- Core compressor driven by High-Pressure Turbine (HPT): W_c = W_HPT * eta_m
- Free power turbine extracts enthalpy down to near-ambient pressure for shaft power:
  P_shaft = mdot_g * cp_t * (T045 - T05) * eta_m_PT
- Shaft power in kW, Shaft Horsepower (SHP), Torque (N*m), and Gearbox matching
- Variable-pitch propeller efficiency model eta_prop(Mach)
- Residual jet thrust F_jet from exhaust nozzle
- Total equivalent thrust F_total = F_prop + F_jet
- Equivalent Shaft Horsepower: ESHP = SHP + F_jet_lbf / 2.5
- Power Specific Fuel Consumption: PSFC [kg/(kW*h)] and [lbm/(shp*h)]
- Emissions and combustor equilibrium integration (Cantera)
"""

import math
from typing import Dict, List, Any, Optional
import cantera as ct
try:
    import ISA_module as ISA
except ImportError:
    from . import ISA_module as ISA

REACTION_MECHANISM = "nDodecane_Reitz.yaml"
PHASE_NAME = "nDodecane_IG"


def calc_turboprop_performance(
    alt: float = 15000.0,
    mach: float = 0.40,
    CPR: float = 12.0,
    TIT: float = 1400.0,
    mdot_air: float = 10.0,
    A8: float = 0.08,
    prop_diameter_m: float = 3.2,
    prop_rpm: float = 1200.0,
    eta_i: float = 0.98,
    eta_c: float = 0.85,
    eta_b: float = 0.99,
    dp_over_p: float = 0.04,
    eta_hpt: float = 0.89,
    eta_pt: float = 0.90,
    eta_mech_core: float = 0.99,
    eta_mech_pt: float = 0.98,
    eta_gearbox: float = 0.985,
    eta_noz: float = 0.95,
    prop_eff_max: float = 0.84,
    gas: Optional[ct.Solution] = None,
) -> Dict[str, Any]:
    """
    Computes complete 0D cycle analysis for a turboprop/turboshaft engine.

    Parameters:
    -----------
    alt : float
        Altitude [ft]
    mach : float
        Flight Mach number
    CPR : float
        Core compressor overall pressure ratio
    TIT : float
        Turbine Inlet Temperature (T04) [K]
    mdot_air : float
        Inlet core airflow [kg/s]
    A8 : float
        Exhaust nozzle throat area [m^2]
    prop_diameter_m : float
        Propeller diameter [m]
    prop_rpm : float
        Propeller rotational speed [RPM]
    """
    if gas is None:
        gas = ct.Solution(REACTION_MECHANISM, PHASE_NAME)

    # Ambient conditions via ICAO ISA
    T_amb = float(ISA.T(alt))
    p_amb = float(ISA.p(alt))
    rho_amb = float(ISA.rho(alt))
    a_amb = math.sqrt(1.4 * 287.05 * T_amb)
    V_inf = mach * a_amb

    # Station 0 / 1: Inlet & Ram Recovery
    gamma_c = 1.40
    cp_c = 1005.0
    R_air = 287.05

    T0_inf = T_amb * (1.0 + 0.5 * (gamma_c - 1.0) * mach * mach)
    P0_inf = p_amb * (1.0 + 0.5 * (gamma_c - 1.0) * mach * mach) ** (gamma_c / (gamma_c - 1.0))

    # Inlet total pressure recovery
    P01 = p_amb + eta_i * (P0_inf - p_amb)
    T01 = T0_inf

    # Station 2: Compressor Inlet
    T02 = T01
    P02 = P01

    # Station 3: Compressor Exit
    P03 = P02 * CPR
    T03_ideal = T02 * (CPR ** ((gamma_c - 1.0) / gamma_c))
    T03 = T02 + (T03_ideal - T02) / eta_c
    W_comp_specific = cp_c * (T03 - T02)
    W_comp_total = mdot_air * W_comp_specific  # Watts

    # Station 4: Combustor & Equilibrium Combustion
    P04 = P03 * (1.0 - dp_over_p)
    T04 = TIT

    COMP_AIR  = "O2:0.209, N2:0.787, CO2:0.004"
    COMP_FUEL = "c12h26:1"

    # Solve chemical equilibrium in Cantera
    # Find equivalence ratio to achieve T04 by resetting unburned state each iteration
    phi_low, phi_high = 0.05, 0.70
    for _ in range(20):
        phi_mid = 0.5 * (phi_low + phi_high)
        gas.TPX = T03, P04, COMP_AIR
        gas.set_equivalence_ratio(phi_mid, COMP_FUEL, COMP_AIR, basis="mole")
        gas.equilibrate("HP")
        if gas.T < T04:
            phi_low = phi_mid
        else:
            phi_high = phi_mid

    phi_sol = 0.5 * (phi_low + phi_high)
    gas.TPX = T03, P04, COMP_AIR
    gas.set_equivalence_ratio(phi_sol, COMP_FUEL, COMP_AIR, basis="mole")
    gas.equilibrate("HP")

    Z = gas.mixture_fraction(fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mass")
    FAR = Z / (1.0 - Z) if Z < 1.0 else phi_sol * 0.0683
    mdot_fuel = mdot_air * FAR / eta_b
    mdot_gas = mdot_air + mdot_fuel

    # Emissions (grams pollutant per kg fuel burned)
    X_NO = gas["NO"].X[0] if "NO" in gas.species_names else 0.0
    X_NO2 = gas["NO2"].X[0] if "NO2" in gas.species_names else 0.0
    X_CO = gas["CO"].X[0] if "CO" in gas.species_names else 0.0
    X_CO2 = gas["CO2"].X[0] if "CO2" in gas.species_names else 0.0
    MW_mix = gas.mean_molecular_weight

    conv_factor = ((1.0 + FAR) / (FAR * MW_mix)) * 1000.0 if FAR > 0 else 0.0
    EI_NOx = (X_NO * 30.01 + X_NO2 * 46.01) * conv_factor
    EI_CO  = (X_CO * 28.01) * conv_factor
    EI_CO2 = (X_CO2 * 44.01) * conv_factor

    gamma_t = 1.33
    cp_t = 1150.0

    # Station 4.5: High Pressure Turbine (Drives Compressor)
    W_hpt_required = W_comp_total / eta_mech_core
    delta_T0_hpt = W_hpt_required / (mdot_gas * cp_t)
    T045 = T04 - delta_T0_hpt
    if T045 <= 0:
        raise ValueError("Combustor enthalpy insufficient to drive core compressor")

    P045 = P04 * (1.0 - delta_T0_hpt / (eta_hpt * T04)) ** (gamma_t / (gamma_t - 1.0))

    # Station 5: Free Power Turbine (PT)
    P05_target = max(p_amb * 1.08, P045 * 0.35)
    PR_pt = P05_target / P045

    T05_ideal = T045 * (PR_pt ** ((gamma_t - 1.0) / gamma_t))
    T05 = T045 - eta_pt * (T045 - T05_ideal)
    P05 = P05_target

    # Power Turbine Shaft Power
    W_pt_fluid = mdot_gas * cp_t * (T045 - T05)
    P_shaft_gross = W_pt_fluid * eta_mech_pt
    P_shaft = P_shaft_gross * eta_gearbox  # Net delivered to propeller shaft [Watts]
    P_shaft_kW = P_shaft / 1000.0
    SHP = P_shaft / 745.69987

    # Torque: tau = P / omega
    omega_prop = 2.0 * math.pi * prop_rpm / 60.0
    torque_Nm = P_shaft / omega_prop if omega_prop > 0 else 0.0

    # Propeller Aerodynamics & Continuous Thrust via Momentum Theory
    if mach > 0.60:
        eta_prop_aero = prop_eff_max * max(0.35, 1.0 - 1.5 * (mach - 0.60) ** 2)
    else:
        eta_prop_aero = prop_eff_max * min(1.0, 0.50 + 0.50 * (mach / 0.60))

    A_disk = 0.25 * math.pi * (prop_diameter_m ** 2)
    P_prop_avail = P_shaft * eta_prop_aero

    if V_inf < 1.0:
        F_prop_N = (2.0 * rho_amb * A_disk * (P_prop_avail ** 2)) ** (1.0 / 3.0)
        eta_prop = 0.0
    else:
        # Newton-Raphson solve: F * (V_inf + sqrt(F / (2*rho*A))) = P_prop_avail
        F = (2.0 * rho_amb * A_disk * (P_prop_avail ** 2)) ** (1.0 / 3.0)
        for _ in range(12):
            v_i = math.sqrt(max(0.0, F / (2.0 * rho_amb * A_disk)))
            f_val = F * (V_inf + v_i) - P_prop_avail
            f_prime = V_inf + 1.5 * v_i
            if abs(f_prime) > 1e-6:
                F -= f_val / f_prime
        F_prop_N = max(0.0, F)
        eta_prop = (F_prop_N * V_inf) / P_shaft if P_shaft > 0 else 0.0

    F_prop_kN = F_prop_N / 1000.0

    # Exhaust Nozzle Jet Thrust (Station 8)
    PR_crit_noz = (1.0 - (1.0 / eta_noz) * (gamma_t - 1.0) / (gamma_t + 1.0)) ** (-gamma_t / (gamma_t - 1.0))
    p_crit_noz = P05 / PR_crit_noz

    if p_amb <= p_crit_noz:
        # Choked nozzle
        T8 = T05 * (2.0 / (gamma_t + 1.0))
        p8 = p_crit_noz
        rho8 = p8 / (287.05 * T8)
        V8 = math.sqrt(gamma_t * 287.05 * T8)
        F_jet_N = mdot_gas * (V8 - V_inf) + A8 * (p8 - p_amb)
    else:
        # Unchoked nozzle
        p8 = p_amb
        T8 = T05 * (1.0 - eta_noz * (1.0 - (p_amb / P05) ** ((gamma_t - 1.0) / gamma_t)))
        V8 = math.sqrt(max(0.0, 2.0 * cp_t * (T05 - T8)))
        F_jet_N = mdot_gas * (V8 - V_inf)

    F_jet_kN = max(0.0, F_jet_N / 1000.0)
    F_total_kN = F_prop_kN + F_jet_kN

    # Equivalent Shaft Horsepower: ESHP = SHP + F_jet_lbf / 2.5
    F_jet_lbf = F_jet_N / 4.44822
    ESHP = SHP + (F_jet_lbf / 2.5)

    # Power Specific Fuel Consumption (PSFC)
    mdot_fuel_kgh = mdot_fuel * 3600.0
    PSFC_kW = mdot_fuel_kgh / P_shaft_kW if P_shaft_kW > 0 else 0.0
    PSFC_shp = (mdot_fuel_kgh * 2.20462) / SHP if SHP > 0 else 0.0

    # Stations Dictionary
    stations = {
        "0": {"label": "Freestream",       "T_K": round(T_amb, 1), "P_atm": round(p_amb / 101325.0, 3)},
        "2": {"label": "Compressor Inlet", "T_K": round(T02, 1),   "P_atm": round(P02 / 101325.0, 3)},
        "3": {"label": "Compressor Exit",  "T_K": round(T03, 1),   "P_atm": round(P03 / 101325.0, 3)},
        "4": {"label": "Combustor Exit",   "T_K": round(T04, 1),   "P_atm": round(P04 / 101325.0, 3)},
        "45": {"label": "HPT Exit (GasGen)", "T_K": round(T045, 1), "P_atm": round(P045 / 101325.0, 3)},
        "5": {"label": "Power Turb Exit",  "T_K": round(T05, 1),   "P_atm": round(P05 / 101325.0, 3)},
        "8": {"label": "Exhaust Exit",     "T_K": round(T8, 1),    "P_atm": round(p8 / 101325.0, 3)},
    }

    return {
        "P_shaft_kW": round(P_shaft_kW, 1),
        "SHP": round(SHP, 1),
        "P_shaft_shp": round(SHP, 1),  # Frontend compatibility alias
        "ESHP": round(ESHP, 1),
        "torque_Nm": round(torque_Nm, 1),
        "F_prop_kN": round(F_prop_kN, 3),
        "F_jet_kN": round(F_jet_kN, 3),
        "F_total_kN": round(F_total_kN, 3),
        "propeller_thrust_N": round(F_prop_N, 1),  # Frontend compatibility alias
        "jet_thrust_N": round(F_jet_N, 1),          # Frontend compatibility alias
        "total_thrust_N": round((F_prop_N + F_jet_N), 1), # Frontend compatibility alias
        "eta_prop": round(eta_prop, 3),
        "propeller_efficiency": round(eta_prop, 3), # Frontend compatibility alias
        "PSFC_kg_kWh": round(PSFC_kW, 4),
        "PSFC_lbm_shph": round(PSFC_shp, 4),
        "mdot_air": round(mdot_air, 2),
        "mdot_fuel_kgh": round(mdot_fuel_kgh, 2),
        "mdot_fuel_kg_s": round(mdot_fuel, 5),      # Frontend compatibility alias
        "FAR": round(FAR, 5),
        "emissions": {
            "EI_NOx": round(EI_NOx, 2),
            "EI_CO": round(EI_CO, 2),
            "EI_CO2": round(EI_CO2, 1),
        },
        "stations": stations,
        "flight_conditions": {
            "altitude_ft": alt,
            "mach": mach,
            "V_inf_ms": round(V_inf, 1),
            "T_amb_K": round(T_amb, 1),
            "p_amb_kPa": round(p_amb / 1000.0, 2),
        }
    }


def run_turboprop_sweep(
    sweep_param: str = "power",
    n_steps: int = 10,
    alt_fixed: float = 15000.0,
    mach_fixed: float = 0.40,
    cpr_fixed: float = 12.0,
    tit_fixed: float = 1400.0,
    gas: Optional[ct.Solution] = None,
) -> Dict[str, Any]:
    """
    Executes parameter sweep for Turboprop across TIT/Power, altitude, or Mach.
    """
    if gas is None:
        gas = ct.Solution(REACTION_MECHANISM, PHASE_NAME)

    step_div = max(1, n_steps - 1)
    if sweep_param == "power":
        tit_vals = [1100.0 + i * (1500.0 - 1100.0) / step_div for i in range(n_steps)]
        points = []
        for tit in tit_vals:
            res = calc_turboprop_performance(
                alt=alt_fixed, mach=mach_fixed, CPR=cpr_fixed, TIT=tit, gas=gas
            )
            res["sweep_val"] = round(tit, 0)
            points.append(res)
    elif sweep_param == "altitude":
        alt_vals = [0.0 + i * (35000.0 - 0.0) / step_div for i in range(n_steps)]
        points = []
        for a in alt_vals:
            res = calc_turboprop_performance(
                alt=a, mach=mach_fixed, CPR=cpr_fixed, TIT=tit_fixed, gas=gas
            )
            res["sweep_val"] = round(a, 0)
            points.append(res)
    elif sweep_param == "mach":
        mach_vals = [0.10 + i * (0.65 - 0.10) / step_div for i in range(n_steps)]
        points = []
        for m in mach_vals:
            res = calc_turboprop_performance(
                alt=alt_fixed, mach=m, CPR=cpr_fixed, TIT=tit_fixed, gas=gas
            )
            res["sweep_val"] = round(m, 2)
            points.append(res)
    else:
        raise ValueError(f"Unsupported sweep_param: {sweep_param}")

    return {
        "sweep_param": sweep_param,
        "points": points
    }
