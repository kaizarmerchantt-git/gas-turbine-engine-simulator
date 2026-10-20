"""
physics_kernel.engine_cycle: High-Fidelity Thermodynamic Cycle Solvers for
Module 01 (Turbojet) and Module 02 (Turbofan).
Built strictly upon physics_kernel.thermo (NASA-9 polynomials) and
physics_kernel.contracts.
"""

import math
from typing import Dict, Any, Tuple, List, Optional
from physics_kernel import thermo
from physics_kernel.contracts import (
    ExecutionStatus, SolverMetadata, clamp_input
)


def solve_turbojet_cycle(
    cpr: float,
    tit_k: float,
    mass_flow_kg_s: float,
    throttle: float = 1.0,
    altitude_m: float = 0.0,
    mach: float = 0.0,
    eta_comp: float = 0.85,
    eta_turb: float = 0.88,
    eta_comb: float = 0.99,
    eta_mech: float = 0.99,
    eta_noz: float = 0.98,
    dp_burner: float = 0.03,
    lhv: float = thermo.DEFAULT_FUEL_LHV
) -> Dict[str, Any]:
    """
    Solves a single-spool turbojet thermodynamic cycle across all stations.
    Station 0: Freestream Ambient
    Station 1: Inlet lip
    Station 2: Compressor Face (Diffuser exit)
    Station 3: Compressor Exit
    Station 4: Combustor Exit / Turbine Inlet
    Station 5: Turbine Exit
    Station 8: Nozzle Throat
    Station 9: Nozzle Exit
    """
    meta = SolverMetadata(
        status=ExecutionStatus.OK,
        converged=True,
        residual_norm=0.0,
        iterations=1,
        warnings=[],
        clamped_inputs={},
        fidelity_level="cycle_0d_real_gas",
        model_version="0.5.0"
    )

    # 1. AN-2 Clamping of inputs
    cpr_eff = clamp_input("cpr", cpr, 1.1, 45.0, meta.clamped_inputs, meta.warnings)
    tit_eff = clamp_input("tit_k", tit_k, 700.0, 2400.0, meta.clamped_inputs, meta.warnings)
    throttle_eff = clamp_input("throttle", throttle, 0.05, 1.5, meta.clamped_inputs, meta.warnings)
    m_dot_air = clamp_input("mass_flow", mass_flow_kg_s, 0.5, 500.0, meta.clamped_inputs, meta.warnings)
    alt_eff = clamp_input("altitude_m", altitude_m, -500.0, 25000.0, meta.clamped_inputs, meta.warnings)
    mach_eff = clamp_input("mach", mach, 0.0, 3.5, meta.clamped_inputs, meta.warnings)

    # 2. Ambient Atmosphere (ISA)
    T_a, P_a, rho_a, a_a = thermo.isa_atmosphere(alt_eff)
    V_0 = mach_eff * a_a
    h_a = thermo.h(T_a, 0.0)
    s_a = thermo.s(T_a, P_a, 0.0)

    # Freestream Total Conditions (Station 0)
    h_t0 = h_a + 0.5 * (V_0 ** 2)
    T_t0 = thermo.T_from_h(h_t0, 0.0)
    s0_t0 = thermo.s(T_t0, 100000.0, 0.0)
    s0_a = thermo.s(T_a, 100000.0, 0.0)
    r_air = thermo.gas_constant(0.0)
    P_t0 = P_a * math.exp((s0_t0 - s0_a) / r_air)

    # 3. Inlet Diffuser (Station 2)
    # Energy is conserved in adiabatic duct: T_t2 == T_t0
    T_t2 = T_t0
    h_t2 = h_t0
    # Ram recovery MIL-E-5008B
    if mach_eff <= 1.0:
        eta_ram = 1.0
    else:
        eta_ram = 1.0 - 0.075 * ((mach_eff - 1.0) ** 1.35)
    eta_ram = max(0.60, min(1.0, eta_ram))
    P_t2 = P_t0 * eta_ram
    s_t2 = thermo.s(T_t2, P_t2, 0.0)

    # 4. Compressor (Station 3)
    P_t3 = P_t2 * cpr_eff
    T_t3, w_comp = thermo.real_compression(T_t2, P_t2, P_t3, eta_comp, far=0.0)
    s_t3 = thermo.s(T_t3, P_t3, 0.0)
    p_comp_watts = m_dot_air * w_comp

    # 5. Combustor (Station 4)
    P_t4 = P_t3 * (1.0 - dp_burner)
    # Throttled turbine inlet temperature
    # At idle throttle=0.2, T_t4 drops smoothly towards T_t3
    tit_actual = T_t3 + (tit_eff - T_t3) * min(1.0, throttle_eff)
    if throttle_eff > 1.0:
        tit_actual = tit_eff * (1.0 + 0.1 * (throttle_eff - 1.0))

    far = thermo.combustor_far_from_tit(T_t3, tit_actual, eta_comb=eta_comb, lhv=lhv)
    m_dot_fuel = far * m_dot_air
    m_dot_gas = m_dot_air + m_dot_fuel
    T_t4 = tit_actual
    h_t4 = thermo.h(T_t4, far)
    s_t4 = thermo.s(T_t4, P_t4, far)

    # 6. Turbine (Station 5)
    # Spool power conservation: W_turb * eta_mech = W_comp
    w_turb_req = w_comp / ((1.0 + far) * eta_mech)
    h_t5 = h_t4 - w_turb_req

    # Check for turbine enthalpy exhaustion / infeasibility
    if h_t5 <= thermo.h(250.0, far):
        meta.status = ExecutionStatus.INFEASIBLE
        meta.converged = False
        meta.warnings.append(f"Turbine enthalpy exhaustion: Compressor work ({w_comp/1e3:.1f} kJ/kg) exceeds available thermal expansion.")
        return {
            "status": "infeasible",
            "converged": False,
            "T": 0.0,
            "thrust_net_kN": 0.0,
            "thrust_gross_kN": 0.0,
            "ram_drag_kN": (m_dot_air * V_0) / 1000.0,
            "TSFC": 0.0,
            "TSFC_g_kNs": 0.0,
            "mdot_fuel": m_dot_fuel,
            "stations": {},
            "meta": meta.model_dump()
        }

    T_t5 = thermo.T_from_h(h_t5, far)
    # Isentropic expansion enthalpy
    h_t5s = h_t4 - (w_turb_req / eta_turb)
    T_t5s = thermo.T_from_h(h_t5s, far)
    # Pressure ratio from isentropic state
    s0_t5s = thermo.s(T_t5s, 100000.0, far)
    s0_t4 = thermo.s(T_t4, 100000.0, far)
    r_gas = thermo.gas_constant(far)
    P_t5 = P_t4 * math.exp((s0_t5s - s0_t4) / r_gas)
    s_t5 = thermo.s(T_t5, P_t5, far)

    # Check pressure feasibility
    if P_t5 < P_a:
        meta.status = ExecutionStatus.INFEASIBLE
        meta.converged = False
        meta.warnings.append(f"Turbine expansion below ambient: P_t5 ({P_t5/1e3:.1f} kPa) < P_amb ({P_a/1e3:.1f} kPa).")
        return {
            "status": "infeasible",
            "converged": False,
            "T": 0.0,
            "thrust_net_kN": 0.0,
            "thrust_gross_kN": 0.0,
            "ram_drag_kN": (m_dot_air * V_0) / 1000.0,
            "TSFC": 0.0,
            "TSFC_g_kNs": 0.0,
            "mdot_fuel": m_dot_fuel,
            "stations": {},
            "meta": meta.model_dump()
        }

    # 7. Nozzle (Station 8 / 9)
    # Adiabatic duct: T_t8 == T_t5
    T_t8 = T_t5
    P_t8 = P_t5 * 0.99  # 1% duct friction loss
    s_t8 = thermo.s(T_t8, P_t8, far)
    gamma_8 = thermo.gamma(T_t8, far)

    # Critical pressure ratio for sonic throat
    pr_crit = ((gamma_8 + 1.0) / 2.0) ** (gamma_8 / (gamma_8 - 1.0))
    p_crit = P_t8 / pr_crit

    # Choking condition
    is_choked = (P_t8 / P_a) >= pr_crit
    p_exit = p_crit if is_choked else P_a

    # Exit expansion
    T_9s = thermo.T_from_s(s_t8, p_exit, far)
    h_t8 = thermo.h(T_t8, far)
    h_9s = thermo.h(T_9s, far)
    h_9 = h_t8 - eta_noz * (h_t8 - h_9s)
    v_9_ideal = math.sqrt(max(0.0, 2.0 * (h_t8 - h_9)))
    v_9 = 0.99 * v_9_ideal  # Nozzle discharge velocity coefficient
    T_9 = thermo.T_from_h(h_t8 - 0.5 * (v_9 ** 2), far)
    rho_9 = p_exit / (r_gas * T_9)
    a_9 = math.sqrt(gamma_8 * r_gas * T_9)
    m_9 = v_9 / a_9
    area_exit = m_dot_gas / (rho_9 * v_9)

    # 8. Thrust & KPIs
    f_gross = m_dot_gas * v_9 + (p_exit - P_a) * area_exit
    f_ram = m_dot_air * V_0
    f_net = max(0.0, f_gross - f_ram)

    # TSFC: kg/(N*s) and g/(kN*s)
    if f_net > 1e-3:
        tsfc_kg_N_s = m_dot_fuel / f_net
        tsfc_g_kN_s = tsfc_kg_N_s * 1e6
        tsfc_kg_kNh = tsfc_g_kN_s * 3.6
    else:
        tsfc_kg_N_s = 0.0
        tsfc_g_kN_s = 0.0
        tsfc_kg_kNh = 0.0

    # Efficiencies
    delta_ke = 0.5 * m_dot_gas * (v_9 ** 2) - 0.5 * m_dot_air * (V_0 ** 2)
    fuel_energy = m_dot_fuel * lhv
    eta_thermal = max(0.0, min(1.0, delta_ke / fuel_energy)) if fuel_energy > 0 else 0.0
    work_thrust = f_net * V_0
    eta_propulsive = max(0.0, min(1.0, (2.0 * V_0) / (v_9 + V_0))) if (v_9 + V_0) > 0 else 0.0
    eta_overall = eta_thermal * eta_propulsive

    # 9. Format Station Dictionary
    stations = {
        "0": {"label": "Freestream", "T_K": round(T_a, 1), "P_kPa": round(P_a / 1e3, 2), "P_total_kPa": round(P_t0 / 1e3, 2), "M": round(mach_eff, 3), "V_ms": round(V_0, 1), "h_kJkg": round(h_a / 1e3, 1), "s_JkgK": round(s_a, 1)},
        "2": {"label": "Compressor Inlet", "T_K": round(T_t2, 1), "P_kPa": round(P_t2 / 1e3, 2), "M": 0.4, "V_ms": round(0.4 * a_a, 1), "h_kJkg": round(h_t2 / 1e3, 1), "s_JkgK": round(s_t2, 1)},
        "3": {"label": "Compressor Exit", "T_K": round(T_t3, 1), "P_kPa": round(P_t3 / 1e3, 2), "M": 0.25, "V_ms": 110.0, "h_kJkg": round(thermo.h(T_t3, 0.0) / 1e3, 1), "s_JkgK": round(s_t3, 1)},
        "4": {"label": "Combustor Exit / Turbine Inlet", "T_K": round(T_t4, 1), "P_kPa": round(P_t4 / 1e3, 2), "M": 0.2, "V_ms": 125.0, "h_kJkg": round(h_t4 / 1e3, 1), "s_JkgK": round(s_t4, 1)},
        "5": {"label": "Turbine Exit", "T_K": round(T_t5, 1), "P_kPa": round(P_t5 / 1e3, 2), "M": 0.45, "V_ms": 280.0, "h_kJkg": round(h_t5 / 1e3, 1), "s_JkgK": round(s_t5, 1)},
        "8": {"label": "Nozzle Throat", "T_K": round(T_t8, 1), "P_kPa": round(p_crit / 1e3, 2), "M": 1.0, "V_ms": round(a_9, 1), "h_kJkg": round(h_t8 / 1e3, 1), "s_JkgK": round(s_t8, 1)},
        "9": {"label": "Nozzle Exit", "T_K": round(T_9, 1), "P_kPa": round(p_exit / 1e3, 2), "M": round(m_9, 2), "V_ms": round(v_9, 1), "h_kJkg": round(h_9 / 1e3, 1), "s_JkgK": round(s_t8, 1)}
    }

    # Thermodynamic T-s Cycle Loop coordinates for Brayton chart
    brayton_cycle = [
        {"s": round(s_a, 1), "T": round(T_a, 1), "station": "0"},
        {"s": round(s_t2, 1), "T": round(T_t2, 1), "station": "2"},
        {"s": round(s_t3, 1), "T": round(T_t3, 1), "station": "3"},
        {"s": round(s_t4, 1), "T": round(T_t4, 1), "station": "4"},
        {"s": round(s_t5, 1), "T": round(T_t5, 1), "station": "5"},
        {"s": round(s_t8, 1), "T": round(T_9, 1), "station": "9"},
        {"s": round(s_a, 1), "T": round(T_a, 1), "station": "0"}
    ]

    return {
        "status": "ok",
        "converged": True,
        "residual_norm": 0.0,
        "iterations": 1,
        "T": round(f_net / 1e3, 3),                     # Net thrust in kN
        "thrust_net_kN": round(f_net / 1e3, 3),
        "thrust_gross_kN": round(f_gross / 1e3, 3),
        "ram_drag_kN": round(f_ram / 1e3, 3),
        "thrust_lbf": round(f_net * 0.224808943, 1),
        "specific_thrust": round(f_net / m_dot_air, 1),  # N / (kg/s)
        "mdot_air": round(m_dot_air, 3),
        "mdot_fuel": round(m_dot_fuel, 5),
        "TSFC": round(tsfc_g_kN_s, 2),
        "TSFC_g_kNs": round(tsfc_g_kN_s, 2),
        "TSFC_kg_kNh": round(tsfc_kg_kNh, 3),
        "TSFC_lbm_lbfh": round(tsfc_g_kN_s / 28.3254504, 3),
        "FAR": round(far, 5),
        "thermal_efficiency": round(eta_thermal, 4),
        "propulsive_efficiency": round(eta_propulsive, 4),
        "overall_efficiency": round(eta_overall, 4),
        "compressor_power_kW": round(p_comp_watts / 1e3, 1),
        "nozzle_exit_velocity_m_s": round(v_9, 1),
        "nozzle_exit_area_m2": round(area_exit, 4),
        "is_choked": is_choked,
        "stations": stations,
        "brayton_cycle": brayton_cycle,
        "meta": meta.model_dump()
    }


def solve_turbofan_cycle(
    cpr: float,
    fan_pr: float,
    bpr: float,
    tit_k: float,
    mass_flow_kg_s: float,
    throttle: float = 1.0,
    altitude_m: float = 0.0,
    mach: float = 0.0,
    eta_fan: float = 0.89,
    eta_comp: float = 0.88,
    eta_turb_hp: float = 0.90,
    eta_turb_lp: float = 0.91,
    eta_comb: float = 0.99,
    eta_mech: float = 0.99,
    eta_noz: float = 0.98,
    dp_burner: float = 0.03,
    lhv: float = thermo.DEFAULT_FUEL_LHV
) -> Dict[str, Any]:
    """
    Solves a dual-spool high-bypass turbofan thermodynamic cycle across all stations.
    Station 0: Freestream Ambient
    Station 2: Fan Face
    Station 13: Fan Bypass Exit
    Station 19: Bypass Nozzle Exit
    Station 25: HPC Inlet
    Station 3: HPC Exit
    Station 4: Combustor Exit / HPT Inlet
    Station 45: HPT Exit / LPT Inlet
    Station 5: LPT Exit
    Station 8: Core Nozzle Throat
    Station 9: Core Nozzle Exit
    """
    meta = SolverMetadata(
        status=ExecutionStatus.OK,
        converged=True,
        residual_norm=0.0,
        iterations=1,
        warnings=[],
        clamped_inputs={},
        fidelity_level="cycle_0d_real_gas_dual_spool",
        model_version="0.5.0"
    )

    # Clamping
    cpr_eff = clamp_input("cpr", cpr, 1.5, 40.0, meta.clamped_inputs, meta.warnings)
    fan_pr_eff = clamp_input("fan_pr", fan_pr, 1.1, 3.5, meta.clamped_inputs, meta.warnings)
    bpr_eff = clamp_input("bpr", bpr, 0.0, 20.0, meta.clamped_inputs, meta.warnings)
    tit_eff = clamp_input("tit_k", tit_k, 700.0, 2400.0, meta.clamped_inputs, meta.warnings)
    throttle_eff = clamp_input("throttle", throttle, 0.05, 1.5, meta.clamped_inputs, meta.warnings)
    m_total = clamp_input("mass_flow", mass_flow_kg_s, 1.0, 1500.0, meta.clamped_inputs, meta.warnings)
    alt_eff = clamp_input("altitude_m", altitude_m, -500.0, 25000.0, meta.clamped_inputs, meta.warnings)
    mach_eff = clamp_input("mach", mach, 0.0, 2.5, meta.clamped_inputs, meta.warnings)

    # Ambient Atmosphere
    T_a, P_a, rho_a, a_a = thermo.isa_atmosphere(alt_eff)
    V_0 = mach_eff * a_a
    h_a = thermo.h(T_a, 0.0)
    s_a = thermo.s(T_a, P_a, 0.0)

    # Total freestream
    h_t0 = h_a + 0.5 * (V_0 ** 2)
    T_t0 = thermo.T_from_h(h_t0, 0.0)
    r_air = thermo.gas_constant(0.0)
    P_t0 = P_a * math.exp((thermo.s(T_t0, 100000.0, 0.0) - thermo.s(T_a, 100000.0, 0.0)) / r_air)

    # Fan Inlet (Station 2)
    T_t2 = T_t0
    eta_ram = 1.0 if mach_eff <= 1.0 else max(0.6, 1.0 - 0.075 * ((mach_eff - 1.0) ** 1.35))
    P_t2 = P_t0 * eta_ram
    s_t2 = thermo.s(T_t2, P_t2, 0.0)

    # Fan Compression (Station 13 & 21)
    P_t13 = P_t2 * fan_pr_eff
    T_t13, w_fan = thermo.real_compression(T_t2, P_t2, P_t13, eta_fan, far=0.0)
    s_t13 = thermo.s(T_t13, P_t13, 0.0)

    # Flow splitting: Core and Bypass
    m_core = m_total / (1.0 + bpr_eff)
    m_bypass = m_total * bpr_eff / (1.0 + bpr_eff)
    p_fan_watts = m_total * w_fan

    # High Pressure Compressor (Station 3)
    P_t3 = P_t13 * cpr_eff
    T_t3, w_hpc = thermo.real_compression(T_t13, P_t13, P_t3, eta_comp, far=0.0)
    s_t3 = thermo.s(T_t3, P_t3, 0.0)
    p_hpc_watts = m_core * w_hpc

    # Overall Pressure Ratio (OPR)
    opr = P_t3 / P_t2

    # Combustor (Station 4)
    P_t4 = P_t3 * (1.0 - dp_burner)
    tit_actual = T_t3 + (tit_eff - T_t3) * min(1.0, throttle_eff)
    far = thermo.combustor_far_from_tit(T_t3, tit_actual, eta_comb=eta_comb, lhv=lhv)
    m_fuel = far * m_core
    m_core_gas = m_core + m_fuel
    T_t4 = tit_actual
    h_t4 = thermo.h(T_t4, far)
    s_t4 = thermo.s(T_t4, P_t4, far)

    # High Pressure Turbine (HPT drives HPC, Station 45)
    w_hpt_req = w_hpc / ((1.0 + far) * eta_mech)
    h_t45 = h_t4 - w_hpt_req

    if h_t45 <= thermo.h(300.0, far):
        meta.status = ExecutionStatus.INFEASIBLE
        meta.converged = False
        meta.warnings.append(f"HPT enthalpy exhausted: HPC work exceeds available HPT expansion.")
        return {"status": "infeasible", "converged": False, "T": 0.0, "thrust_net_kN": 0.0, "meta": meta.model_dump()}

    T_t45 = thermo.T_from_h(h_t45, far)
    h_t45s = h_t4 - (w_hpt_req / eta_turb_hp)
    T_t45s = thermo.T_from_h(h_t45s, far)
    r_gas = thermo.gas_constant(far)
    P_t45 = P_t4 * math.exp((thermo.s(T_t45s, 100000.0, far) - thermo.s(T_t4, 100000.0, far)) / r_gas)
    s_t45 = thermo.s(T_t45, P_t45, far)

    # Low Pressure Turbine (LPT drives Fan, Station 5)
    w_lpt_req = (m_total * w_fan) / (m_core_gas * eta_mech)
    h_t5 = h_t45 - w_lpt_req

    if h_t5 <= thermo.h(250.0, far) or P_t45 <= P_a:
        meta.status = ExecutionStatus.INFEASIBLE
        meta.converged = False
        meta.warnings.append(f"LPT enthalpy exhausted: Fan work exceeds remaining core enthalpy.")
        return {"status": "infeasible", "converged": False, "T": 0.0, "thrust_net_kN": 0.0, "meta": meta.model_dump()}

    T_t5 = thermo.T_from_h(h_t5, far)
    h_t5s = h_t45 - (w_lpt_req / eta_turb_lp)
    T_t5s = thermo.T_from_h(h_t5s, far)
    P_t5 = P_t45 * math.exp((thermo.s(T_t5s, 100000.0, far) - thermo.s(T_t45, 100000.0, far)) / r_gas)
    s_t5 = thermo.s(T_t5, P_t5, far)

    # Core Nozzle Expansion (Station 9)
    T_t8 = T_t5
    P_t8 = P_t5 * 0.99
    gamma_core = thermo.gamma(T_t8, far)
    pr_crit_core = ((gamma_core + 1.0) / 2.0) ** (gamma_core / (gamma_core - 1.0))
    p_crit_core = P_t8 / pr_crit_core
    is_core_choked = (P_t8 / P_a) >= pr_crit_core
    p_exit_core = p_crit_core if is_core_choked else P_a

    T_9s = thermo.T_from_s(s_t5, p_exit_core, far)
    h_t8 = thermo.h(T_t8, far)
    h_9 = h_t8 - eta_noz * (h_t8 - thermo.h(T_9s, far))
    v_core = 0.99 * math.sqrt(max(0.0, 2.0 * (h_t8 - h_9)))
    T_9 = thermo.T_from_h(h_t8 - 0.5 * (v_core ** 2), far)
    rho_9 = p_exit_core / (r_gas * T_9)
    a_core = m_core_gas / (rho_9 * v_core)
    f_gross_core = m_core_gas * v_core + (p_exit_core - P_a) * a_core
    f_ram_core = m_core * V_0
    f_net_core = max(0.0, f_gross_core - f_ram_core)

    # Bypass Nozzle Expansion (Station 19)
    T_t18 = T_t13
    P_t18 = P_t13 * 0.995
    gamma_byp = thermo.gamma(T_t18, 0.0)
    pr_crit_byp = ((gamma_byp + 1.0) / 2.0) ** (gamma_byp / (gamma_byp - 1.0))
    p_crit_byp = P_t18 / pr_crit_byp
    is_byp_choked = (P_t18 / P_a) >= pr_crit_byp
    p_exit_byp = p_crit_byp if is_byp_choked else P_a

    T_19s = thermo.T_from_s(s_t13, p_exit_byp, 0.0)
    h_t18 = thermo.h(T_t18, 0.0)
    h_19 = h_t18 - eta_noz * (h_t18 - thermo.h(T_19s, 0.0))
    v_byp = 0.99 * math.sqrt(max(0.0, 2.0 * (h_t18 - h_19)))
    T_19 = thermo.T_from_h(h_t18 - 0.5 * (v_byp ** 2), 0.0)
    rho_19 = p_exit_byp / (r_air * T_19)
    a_byp = m_bypass / (rho_19 * v_byp)
    f_gross_byp = m_bypass * v_byp + (p_exit_byp - P_a) * a_byp
    f_ram_byp = m_bypass * V_0
    f_net_byp = max(0.0, f_gross_byp - f_ram_byp)

    # Total Engine Performance
    f_net_total = f_net_core + f_net_byp
    f_gross_total = f_gross_core + f_gross_byp
    f_ram_total = f_ram_core + f_ram_byp

    if f_net_total > 1e-3:
        tsfc_kg_N_s = m_fuel / f_net_total
        tsfc_g_kN_s = tsfc_kg_N_s * 1e6
        tsfc_kg_kNh = tsfc_g_kN_s * 3.6
    else:
        tsfc_kg_N_s = 0.0
        tsfc_g_kN_s = 0.0
        tsfc_kg_kNh = 0.0

    delta_ke = 0.5 * m_core_gas * (v_core**2) + 0.5 * m_bypass * (v_byp**2) - 0.5 * m_total * (V_0**2)
    fuel_energy = m_fuel * lhv
    eta_thermal = max(0.0, min(1.0, delta_ke / fuel_energy)) if fuel_energy > 0 else 0.0
    eta_propulsive = max(0.0, min(1.0, (f_net_total * V_0) / delta_ke)) if delta_ke > 0 else 0.0
    eta_overall = eta_thermal * eta_propulsive

    stations = {
        "0": {"label": "Freestream", "T_K": round(T_a, 1), "P_kPa": round(P_a / 1e3, 2), "M": round(mach_eff, 3), "V_ms": round(V_0, 1)},
        "2": {"label": "Fan Inlet", "T_K": round(T_t2, 1), "P_kPa": round(P_t2 / 1e3, 2), "M": 0.5, "V_ms": round(0.5 * a_a, 1)},
        "13": {"label": "Fan Exit (Bypass)", "T_K": round(T_t13, 1), "P_kPa": round(P_t13 / 1e3, 2), "M": 0.45, "V_ms": 150.0},
        "19": {"label": "Bypass Nozzle Exit", "T_K": round(T_19, 1), "P_kPa": round(p_exit_byp / 1e3, 2), "M": round(v_byp / math.sqrt(gamma_byp * r_air * T_19), 2), "V_ms": round(v_byp, 1)},
        "3": {"label": "HPC Exit", "T_K": round(T_t3, 1), "P_kPa": round(P_t3 / 1e3, 2), "M": 0.28, "V_ms": 115.0},
        "4": {"label": "Combustor Exit / HPT Inlet", "T_K": round(T_t4, 1), "P_kPa": round(P_t4 / 1e3, 2), "M": 0.22, "V_ms": 120.0},
        "45": {"label": "HPT Exit / LPT Inlet", "T_K": round(T_t45, 1), "P_kPa": round(P_t45 / 1e3, 2), "M": 0.4, "V_ms": 250.0},
        "5": {"label": "LPT Exit / Core Exhaust", "T_K": round(T_t5, 1), "P_kPa": round(P_t5 / 1e3, 2), "M": 0.48, "V_ms": 270.0},
        "9": {"label": "Core Nozzle Exit", "T_K": round(T_9, 1), "P_kPa": round(p_exit_core / 1e3, 2), "M": round(v_core / math.sqrt(gamma_core * r_gas * T_9), 2), "V_ms": round(v_core, 1)}
    }

    return {
        "status": "ok",
        "converged": True,
        "residual_norm": 0.0,
        "iterations": 1,
        "T": round(f_net_total / 1e3, 3),
        "thrust_net_kN": round(f_net_total / 1e3, 3),
        "T_core": round(f_net_core / 1e3, 3),
        "T_byp": round(f_net_byp / 1e3, 3),
        "bypass_thrust_kN": round(f_net_byp / 1e3, 3),
        "core_thrust_kN": round(f_net_core / 1e3, 3),
        "thrust_gross_kN": round(f_gross_total / 1e3, 3),
        "ram_drag_kN": round(f_ram_total / 1e3, 3),
        "thrust_lbf": round(f_net_total * 0.224808943, 1),
        "mdot_total": round(m_total, 2),
        "mdot_core": round(m_core, 2),
        "mdot_byp": round(m_bypass, 2),
        "mdot_fuel": round(m_fuel, 5),
        "TSFC": round(tsfc_g_kN_s, 2),
        "TSFC_g_kNs": round(tsfc_g_kN_s, 2),
        "TSFC_kg_kNh": round(tsfc_kg_kNh, 3),
        "TSFC_lbm_lbfh": round(tsfc_g_kN_s / 28.3254504, 3),
        "BPR": round(bpr_eff, 2),
        "OPR": round(opr, 2),
        "FAR": round(far, 5),
        "thermal_efficiency": round(eta_thermal, 4),
        "propulsive_efficiency": round(eta_propulsive, 4),
        "overall_efficiency": round(eta_overall, 4),
        "v_core_m_s": round(v_core, 1),
        "v_byp_m_s": round(v_byp, 1),
        "stations": stations,
        "meta": meta.model_dump()
    }
