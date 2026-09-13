"""
Gas Turbine Engine Simulator — 1D Mean-Line Turbomachinery Aerodynamics
======================================================================
Extension 6 from Project Scope.

Bridges 0D thermodynamic cycle analysis to physical blade aerodynamics:
- Rotational speed N (RPM) and mean radius r_m (blade speed U = omega * r_m)
- Euler turbomachinery equation: Delta h0 = U * Delta C_theta
- Rotor and stator velocity triangles (axial, tangential, absolute C, relative W, flow angles alpha and beta)
- Non-dimensional coefficients: stage loading psi = Delta h0 / U^2, flow coeff phi = C_a / U, reaction R
- Aerodynamic stall & diffusion limits: De Haller number (W2/W1 >= 0.72), Lieblein Diffusion Factor (DF <= 0.45)
- Multi-stage axial compressor and turbine annular geometry sizing (blade height, hub/tip ratio)
"""

import math
from typing import Dict, List, Any, Optional, Tuple


def solve_compressor_stage(
    T01: float,
    P01: float,
    delta_T0: float = 35.0,
    N_rpm: float = 12000.0,
    r_mean: float = 0.28,
    C_a: float = 160.0,
    reaction: float = 0.50,
    eta_stage: float = 0.88,
    mdot: float = 20.0,
    solidity: float = 1.2,
    gamma: float = 1.40,
    cp: float = 1005.0,
    alpha_1_deg: Optional[float] = None,
    beta_2_deg: Optional[float] = None,
    C_a1: Optional[float] = None,
    C_a2: Optional[float] = None,
    alpha_3_deg: Optional[float] = None,
    U: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Solves 1D mean-line aerodynamics and velocity triangles for an axial compressor stage (Rotor + Stator).
    Supports both kinematic flow angle synthesis (alpha_1, beta_2, Ca1, Ca2) and stage work synthesis (delta_T0, reaction).
    """
    R_gas = cp * (gamma - 1.0) / gamma

    # Blade speed U
    if U is not None and U > 0.0:
        blade_speed = float(U)
        if r_mean > 0:
            N_rpm = (blade_speed * 60.0) / (2.0 * math.pi * r_mean)
    else:
        omega = 2.0 * math.pi * N_rpm / 60.0
        blade_speed = omega * r_mean

    if blade_speed <= 0.0:
        raise ValueError("Blade speed U must be positive")
    U = blade_speed

    # Check whether flow angles are provided for kinematic solving
    if alpha_1_deg is not None and beta_2_deg is not None:
        Ca1 = float(C_a1 if C_a1 is not None else C_a)
        Ca2 = float(C_a2 if C_a2 is not None else Ca1)
        C_a = Ca1

        # Rotor Inlet
        alpha1_rad = math.radians(float(alpha_1_deg))
        C_theta1 = Ca1 * math.tan(alpha1_rad)
        W_theta1 = C_theta1 - U

        # Rotor Exit relative flow turning
        beta2_val = float(beta_2_deg)
        beta2_rad = math.radians(beta2_val)
        # Sign convention: in compressor, blades push flow in +U direction reducing negative relative swirl
        W_theta2 = -Ca2 * math.tan(beta2_rad) if beta2_val > 0 else Ca2 * math.tan(beta2_rad)
        C_theta2 = U + W_theta2
        delta_C_theta = C_theta2 - C_theta1

        # Ensure positive Euler work transfer
        if delta_C_theta <= 0.0:
            delta_C_theta = max(10.0, U * 0.25)
            C_theta2 = C_theta1 + delta_C_theta
            W_theta2 = C_theta2 - U

        delta_h0 = U * delta_C_theta
        delta_T0 = delta_h0 / cp
        psi = delta_h0 / (U * U)
        phi = Ca1 / U
        reaction = 1.0 - (C_theta1 + C_theta2) / (2.0 * U)
    else:
        Ca1 = C_a
        Ca2 = C_a
        # Stage work and non-dimensional loading from delta_T0 & reaction
        delta_h0 = cp * delta_T0
        psi = delta_h0 / (U * U)      # Stage loading coefficient
        phi = C_a / U                 # Flow coefficient
        delta_C_theta = delta_h0 / U

        # For repeating stage with constant axial velocity:
        C_theta1 = U * (1.0 - reaction) - 0.5 * delta_C_theta
        C_theta2 = U * (1.0 - reaction) + 0.5 * delta_C_theta
        W_theta1 = C_theta1 - U
        W_theta2 = C_theta2 - U

    # Rotor Inlet (Station 1)
    C1 = math.hypot(Ca1, C_theta1)
    alpha1_rad = math.atan2(C_theta1, Ca1)
    alpha1_deg = math.degrees(alpha1_rad)

    W1 = math.hypot(Ca1, W_theta1)
    beta1_rad = math.atan2(W_theta1, Ca1)
    beta1_deg = math.degrees(beta1_rad)

    # Static state at rotor inlet
    T1 = T01 - (C1 * C1) / (2.0 * cp)
    if T1 <= 0:
        T1 = T01 * 0.95
    P1 = P01 * (T1 / T01) ** (gamma / (gamma - 1.0))
    a1 = math.sqrt(gamma * R_gas * T1)
    M_C1 = C1 / a1 if a1 > 0 else 0.0
    M_W1 = W1 / a1 if a1 > 0 else 0.0   # Rotor relative inlet Mach number
    rho1 = P1 / (R_gas * T1)

    # Rotor Exit / Stator Inlet (Station 2)
    C2 = math.hypot(Ca2, C_theta2)
    alpha2_rad = math.atan2(C_theta2, Ca2)
    alpha2_deg = math.degrees(alpha2_rad)

    W2 = math.hypot(Ca2, W_theta2)
    beta2_rad = math.atan2(W_theta2, Ca2)
    beta2_deg = math.degrees(beta2_rad)

    T02 = T01 + delta_T0
    T2 = T02 - (C2 * C2) / (2.0 * cp)
    if T2 <= 0:
        T2 = T02 * 0.95
    a2 = math.sqrt(gamma * R_gas * T2)
    M_C2 = C2 / a2 if a2 > 0 else 0.0
    M_W2 = W2 / a2 if a2 > 0 else 0.0

    # Stator Exit (Station 3)
    if alpha_3_deg is not None:
        alpha3_deg = float(alpha_3_deg)
        C_theta3 = Ca2 * math.tan(math.radians(alpha3_deg))
        C3 = math.hypot(Ca2, C_theta3)
    else:
        C_theta3 = C_theta1
        C3 = C1
        alpha3_deg = alpha1_deg

    T03 = T02
    T3 = max(10.0, T03 - (C3 * C3) / (2.0 * cp))

    # Stage Pressure Ratio and Stagnation Pressure
    PR_stage = (1.0 + eta_stage * delta_T0 / T01) ** (gamma / (gamma - 1.0))
    P03 = P01 * PR_stage
    P3 = P03 * (T3 / T03) ** (gamma / (gamma - 1.0))
    rho3 = P3 / (R_gas * T3)

    a3 = math.sqrt(gamma * R_gas * T3)
    M_C3 = C3 / a3 if a3 > 0 else 0.0

    # Aerodynamic Health Metrics (Evaluates BOTH Rotor and Stator for stall/diffusion risks)
    de_haller_rotor = W2 / W1 if W1 > 0 else 0.0
    de_haller_stator = C3 / C2 if C2 > 0 else 0.0
    min_de_haller = min(de_haller_rotor, de_haller_stator)
    de_haller_status = "HEALTHY" if min_de_haller >= 0.72 else ("MARGINAL" if min_de_haller >= 0.68 else "STALL RISK")

    # Lieblein Diffusion Factor
    df_rotor = (1.0 - de_haller_rotor) + abs(W_theta1 - W_theta2) / (2.0 * max(0.1, solidity) * W1) if W1 > 0 else 0.0
    df_stator = (1.0 - de_haller_stator) + abs(C_theta2 - C_theta3) / (2.0 * max(0.1, solidity) * C2) if C2 > 0 else 0.0
    max_df = max(df_rotor, df_stator)
    df_status = "OPTIMAL" if max_df <= 0.45 else ("HIGH LOAD" if max_df <= 0.55 else "OVERLOADED")

    # Blade Annulus Dimensions
    blade_height_in = mdot / (rho1 * C_a * 2.0 * math.pi * r_mean) if (rho1 * C_a * r_mean) > 0 else 0.05
    blade_height_out = mdot / (rho3 * C_a * 2.0 * math.pi * r_mean) if (rho3 * C_a * r_mean) > 0 else 0.05

    r_tip_in = r_mean + 0.5 * blade_height_in
    r_hub_in = max(0.01, r_mean - 0.5 * blade_height_in)
    hub_to_tip_in = r_hub_in / r_tip_in if r_tip_in > 0 else 0.5

    r_tip_out = r_mean + 0.5 * blade_height_out
    r_hub_out = max(0.01, r_mean - 0.5 * blade_height_out)
    hub_to_tip_out = r_hub_out / r_tip_out if r_tip_out > 0 else 0.5

    rotor_inlet_dict = {
        "C": round(C1, 2),
        "C_a": round(C_a, 2),
        "Ca": round(C_a, 2),
        "C_theta": round(C_theta1, 2),
        "Ctheta": round(C_theta1, 2),
        "alpha_deg": round(alpha1_deg, 2),
        "W": round(W1, 2),
        "W_theta": round(W_theta1, 2),
        "beta_deg": round(beta1_deg, 2),
        "M_abs": round(M_C1, 3),
        "Mach_abs": round(M_C1, 3),
        "M_rel": round(M_W1, 3),
        "Mach_rel": round(M_W1, 3),
        "U": round(U, 2),
    }
    rotor_exit_dict = {
        "C": round(C2, 2),
        "C_a": round(C_a, 2),
        "Ca": round(C_a, 2),
        "C_theta": round(C_theta2, 2),
        "Ctheta": round(C_theta2, 2),
        "alpha_deg": round(alpha2_deg, 2),
        "W": round(W2, 2),
        "W_theta": round(W_theta2, 2),
        "beta_deg": round(beta2_deg, 2),
        "M_abs": round(M_C2, 3),
        "Mach_abs": round(M_C2, 3),
        "M_rel": round(M_W2, 3),
        "Mach_rel": round(M_W2, 3),
        "U": round(U, 2),
    }
    stator_exit_dict = {
        "C": round(C3, 2),
        "C_a": round(C_a, 2),
        "Ca": round(C_a, 2),
        "C_theta": round(C_theta3, 2),
        "Ctheta": round(C_theta3, 2),
        "alpha_deg": round(alpha3_deg, 2),
        "M_abs": round(M_C3, 3),
        "Mach_abs": round(M_C3, 3),
    }

    return {
        "U": round(U, 2),
        "psi": round(psi, 4),
        "phi": round(phi, 4),
        "reaction": round(reaction, 3),
        "degree_of_reaction_R": round(reaction, 3),
        "loading_coefficient_psi": round(psi, 4),
        "flow_coefficient_phi": round(phi, 4),
        "delta_h0": round(delta_h0, 1),
        "delta_h0_kJkg": round(delta_h0 / 1000.0, 2),
        "PR_stage": round(PR_stage, 4),
        "stage_PR": round(PR_stage, 4),
        "T01": round(T01, 1),
        "T03": round(T03, 1),
        "P01": round(P01, 1),
        "P03": round(P03, 1),
        "de_haller_ratio": round(de_haller_rotor, 3),
        "de_haller_acceptable": de_haller_status == "HEALTHY",
        "lieblein_diffusion_rotor": round(df_rotor, 3),
        "blade_height_inlet_mm": round(blade_height_in * 1000.0, 1),
        "blade_height_exit_mm": round(blade_height_out * 1000.0, 1),
        "tip_radius_mm": round(r_tip_out * 1000.0, 1),
        "hub_radius_mm": round(r_hub_out * 1000.0, 1),
        "rotor_inlet_triangle": rotor_inlet_dict,
        "rotor_exit_triangle": rotor_exit_dict,
        "stator_exit_triangle": stator_exit_dict,
        "velocity_triangles": {
            "rotor_inlet": rotor_inlet_dict,
            "rotor_exit": rotor_exit_dict,
            "stator_exit": stator_exit_dict,
        },
        "aerodynamics": {
            "de_haller_rotor": round(de_haller_rotor, 3),
            "de_haller_stator": round(de_haller_stator, 3),
            "de_haller_status": de_haller_status,
            "diffusion_factor_rotor": round(df_rotor, 3),
            "diffusion_factor_stator": round(df_stator, 3),
            "diffusion_factor_status": df_status,
        },
        "geometry": {
            "blade_height_in_mm": round(blade_height_in * 1000.0, 1),
            "blade_height_out_mm": round(blade_height_out * 1000.0, 1),
            "r_tip_in_mm": round(r_tip_in * 1000.0, 1),
            "r_hub_in_mm": round(r_hub_in * 1000.0, 1),
            "r_tip_out_mm": round(r_tip_out * 1000.0, 1),
            "r_hub_out_mm": round(r_hub_out * 1000.0, 1),
            "hub_to_tip_in": round(hub_to_tip_in, 3),
            "hub_to_tip_out": round(hub_to_tip_out, 3),
            "hub_to_tip_ratio_in": round(hub_to_tip_in, 3),
            "hub_to_tip_ratio_out": round(hub_to_tip_out, 3),
        }
    }


def solve_multistage_compressor_meanline(
    CPR: float = 8.0,
    n_stages: int = 6,
    T0_inlet: float = 288.15,
    P0_inlet: float = 101325.0,
    N_rpm: float = 12000.0,
    r_mean: float = 0.28,
    C_a: float = 160.0,
    reaction: float = 0.50,
    eta_poly: float = 0.88,
    mdot: float = 20.0,
) -> Dict[str, Any]:
    """
    Simulates multi-stage axial compressor 1D mean-line aerodynamic stacking.
    Evenly distributes temperature rise or work across stages, tracking
    stage-by-stage velocity triangles and decreasing blade heights.
    """
    gamma = 1.40
    cp = 1005.0

    T0_exit = T0_inlet * (CPR ** ((gamma - 1.0) / (gamma * eta_poly)))
    total_delta_T0 = T0_exit - T0_inlet
    delta_T0_stage = total_delta_T0 / n_stages

    stages = []
    curr_T0 = T0_inlet
    curr_P0 = P0_inlet

    for i in range(1, n_stages + 1):
        st = solve_compressor_stage(
            T01=curr_T0,
            P01=curr_P0,
            delta_T0=delta_T0_stage,
            N_rpm=N_rpm,
            r_mean=r_mean,
            C_a=C_a,
            reaction=reaction,
            eta_stage=eta_poly,
            mdot=mdot,
            gamma=gamma,
            cp=cp
        )
        st["stage_num"] = i
        stages.append(st)

        curr_T0 = st["T03"]
        curr_P0 = st["P03"]

    overall_CPR = curr_P0 / P0_inlet
    overall_W = cp * (curr_T0 - T0_inlet) / 1000.0 # kJ/kg

    return {
        "n_stages": n_stages,
        "num_stages": n_stages,
        "CPR_target": CPR,
        "CPR_actual": round(overall_CPR, 3),
        "total_PR": round(overall_CPR, 3),
        "total_work_kJkg": round(overall_W, 2),
        "total_delta_h0_kJkg": round(overall_W, 2),
        "T0_inlet": round(T0_inlet, 1),
        "T0_in": round(T0_inlet, 1),
        "T0_exit": round(curr_T0, 1),
        "T0_out": round(curr_T0, 1),
        "P0_inlet_kPa": round(P0_inlet / 1000.0, 2),
        "P0_exit_kPa": round(curr_P0 / 1000.0, 2),
        "P0_in": round(P0_inlet, 1),
        "P0_out": round(curr_P0, 1),
        "N_rpm": N_rpm,
        "U_mean": round(stages[0]["U"], 2),
        "stages": stages
    }


def solve_turbine_stage(
    T01: float = 1400.0,
    P01: float = 800000.0,
    delta_T0: float = 180.0,
    N_rpm: float = 12000.0,
    r_mean: float = 0.28,
    C_a: float = 220.0,
    reaction: float = 0.40,
    eta_stage: float = 0.90,
    solidity: float = 1.4,
    gamma: float = 1.33,
    cp: float = 1150.0,
    alpha_2_deg: Optional[float] = None,
    beta_3_deg: Optional[float] = None,
    U: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Solves 1D mean-line aerodynamics for an axial turbine stage (Nozzle Guide Vane Stator + Rotor).
    Supports kinematic angle synthesis (alpha_2, beta_3) and thermodynamic extraction (delta_T0, reaction).
    Euler extraction: Delta h0 = U * (C_theta2 - C_theta3)
    """
    if U is not None and U > 0:
        blade_speed = float(U)
        if r_mean > 0:
            N_rpm = (blade_speed * 60.0) / (2.0 * math.pi * r_mean)
    else:
        omega = 2.0 * math.pi * N_rpm / 60.0
        blade_speed = omega * r_mean

    if blade_speed <= 0:
        raise ValueError("Blade speed U must be positive")
    U = blade_speed

    if alpha_2_deg is not None and beta_3_deg is not None:
        a2_rad = math.radians(float(alpha_2_deg))
        C_theta2 = C_a * math.tan(a2_rad)
        W_theta2 = C_theta2 - U

        b3_rad = math.radians(float(beta_3_deg))
        W_theta3 = C_a * math.tan(b3_rad)
        C_theta3 = U + W_theta3
        delta_C_theta = C_theta2 - C_theta3

        if delta_C_theta <= 0.0:
            delta_C_theta = max(50.0, U * 0.8)
            C_theta3 = C_theta2 - delta_C_theta
            W_theta3 = C_theta3 - U

        delta_h0 = U * delta_C_theta
        delta_T0 = min(delta_h0 / cp, eta_stage * T01 * 0.85)
        psi = delta_h0 / (U * U)
        phi = C_a / U
        reaction = 1.0 - (C_theta2 + C_theta3) / (2.0 * U)
    else:
        if delta_T0 >= eta_stage * T01:
            delta_T0 = eta_stage * T01 * 0.85

        delta_h0 = cp * delta_T0
        psi = delta_h0 / (U * U)      # Stage loading coefficient (typically 1.2 - 2.5 for turbines)
        phi = C_a / U                 # Flow coefficient
        delta_C_theta = delta_h0 / U

        # Rotor inlet swirl C_theta2 and rotor exit swirl C_theta3
        C_theta2 = U * (1.0 - reaction) + 0.5 * delta_C_theta
        C_theta3 = U * (1.0 - reaction) - 0.5 * delta_C_theta
        W_theta2 = C_theta2 - U
        W_theta3 = C_theta3 - U

    # Stator (NGV) Exit / Rotor Inlet (Station 2)
    C2 = math.hypot(C_a, C_theta2)
    alpha2_deg = math.degrees(math.atan2(C_theta2, C_a))
    W2 = math.hypot(C_a, W_theta2)
    beta2_deg = math.degrees(math.atan2(W_theta2, C_a))

    # Rotor Exit (Station 3)
    C3 = math.hypot(C_a, C_theta3)
    alpha3_deg = math.degrees(math.atan2(C_theta3, C_a))
    W3 = math.hypot(C_a, W_theta3)
    beta3_deg = math.degrees(math.atan2(W_theta3, C_a))

    # Pressure ratio across turbine stage
    PR_stage = (1.0 - delta_T0 / (eta_stage * T01)) ** (gamma / (gamma - 1.0))
    T03 = T01 - delta_T0
    P03 = P01 * PR_stage

    # Zweifel blade loading criterion (exact, singularity-free)
    cos_b3_sq = (C_a * C_a) / (W3 * W3) if W3 > 0 else 1.0
    delta_tan_b = abs(delta_C_theta / C_a) if C_a > 0 else 0.0
    zweifel = 2.0 * (1.0 / max(0.1, solidity)) * cos_b3_sq * delta_tan_b

    ngv_exit_dict = {
        "C": round(C2, 2),
        "C_a": round(C_a, 2),
        "Ca": round(C_a, 2),
        "C_theta": round(C_theta2, 2),
        "Ctheta": round(C_theta2, 2),
        "alpha_deg": round(alpha2_deg, 2),
        "W": round(W2, 2),
        "W_theta": round(W_theta2, 2),
        "beta_deg": round(beta2_deg, 2),
        "U": round(U, 2),
    }
    rotor_exit_dict = {
        "C": round(C3, 2),
        "C_a": round(C_a, 2),
        "Ca": round(C_a, 2),
        "C_theta": round(C_theta3, 2),
        "Ctheta": round(C_theta3, 2),
        "alpha_deg": round(alpha3_deg, 2),
        "W": round(W3, 2),
        "W_theta": round(W_theta3, 2),
        "beta_deg": round(beta3_deg, 2),
        "U": round(U, 2),
    }

    return {
        "U": round(U, 2),
        "psi": round(psi, 4),
        "phi": round(phi, 4),
        "reaction": round(reaction, 3),
        "delta_h0": round(delta_h0, 1),
        "delta_h0_kJkg": round(delta_h0 / 1000.0, 2),
        "PR_stage": round(PR_stage, 4),
        "expansion_ratio": round(1.0 / PR_stage, 4) if PR_stage > 0 else 0.0,
        "T01": round(T01, 1),
        "T03": round(T03, 1),
        "P01": round(P01, 1),
        "P03": round(P03, 1),
        "P01_kPa": round(P01 / 1000.0, 1),
        "P03_kPa": round(P03 / 1000.0, 1),
        "zweifel_coefficient": round(zweifel, 3),
        "zweifel_coefficient_stator": round(zweifel, 3),
        "stator_exit_triangle": ngv_exit_dict,
        "rotor_exit_triangle": rotor_exit_dict,
        "velocity_triangles": {
            "ngv_exit": ngv_exit_dict,
            "rotor_exit": rotor_exit_dict,
        }
    }
