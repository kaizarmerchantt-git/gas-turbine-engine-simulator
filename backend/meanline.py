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


def solve_radial_equilibrium_free_vortex(
    r_mean: float,
    U_mean: float,
    C_a: float,
    C_theta1_mean: float,
    C_theta2_mean: float,
    r_hub: float,
    r_tip: float,
    n_radial: int = 5,
    gamma: float = 1.40,
    cp: float = 1005.0,
    T01: float = 288.15,
) -> Dict[str, Any]:
    """
    Computes Free-Vortex radial equilibrium spanwise variation across Hub, Mean, and Tip:
    - r * C_theta = const = r_mean * C_theta_mean
    - C_a(r) = const = C_a
    - U(r) = U_mean * (r / r_mean)
    """
    R_gas = cp * (gamma - 1.0) / gamma
    n_pts = max(3, n_radial)
    r_hub_safe = max(0.01, min(r_hub, r_mean * 0.95))
    r_tip_safe = max(r_mean * 1.05, r_tip)
    radii = [r_hub_safe + i * (r_tip_safe - r_hub_safe) / (n_pts - 1) for i in range(n_pts)]

    sections = []
    for r in radii:
        r_ratio = r_mean / r if r > 0 else 1.0
        U_r = U_mean * (r / r_mean) if r_mean > 0 else U_mean
        C_th1_r = C_theta1_mean * r_ratio
        C_th2_r = C_theta2_mean * r_ratio
        W_th1_r = C_th1_r - U_r
        W_th2_r = C_th2_r - U_r

        C1_r = math.hypot(C_a, C_th1_r)
        W1_r = math.hypot(C_a, W_th1_r)
        C2_r = math.hypot(C_a, C_th2_r)
        W2_r = math.hypot(C_a, W_th2_r)

        alpha1_deg = math.degrees(math.atan2(C_th1_r, C_a))
        beta1_deg = math.degrees(math.atan2(W_th1_r, C_a))
        alpha2_deg = math.degrees(math.atan2(C_th2_r, C_a))
        beta2_deg = math.degrees(math.atan2(W_th2_r, C_a))

        reaction_r = 1.0 - (C_th1_r + C_th2_r) / (2.0 * U_r) if U_r > 0 else 0.5
        de_haller_r = W2_r / W1_r if W1_r > 0 else 1.0

        T1_r = max(100.0, T01 - (C1_r ** 2) / (2.0 * cp))
        a1_r = math.sqrt(gamma * R_gas * T1_r)
        M_rel1_r = W1_r / a1_r if a1_r > 0 else 0.0

        sections.append({
            "radius_m": round(r, 4),
            "radius_mm": round(r * 1000.0, 1),
            "span_pct": round(((r - r_hub_safe) / max(1e-4, r_tip_safe - r_hub_safe)) * 100.0, 1),
            "U_ms": round(U_r, 1),
            "alpha1_deg": round(alpha1_deg, 2),
            "beta1_deg": round(beta1_deg, 2),
            "alpha2_deg": round(alpha2_deg, 2),
            "beta2_deg": round(beta2_deg, 2),
            "reaction": round(reaction_r, 3),
            "de_haller": round(de_haller_r, 3),
            "M_rel1": round(M_rel1_r, 3),
        })

    return {
        "hub": sections[0],
        "mean": sections[len(sections) // 2],
        "tip": sections[-1],
        "sections": sections,
    }


def calc_profile_and_secondary_losses(
    df_rotor: float,
    solidity: float,
    beta1_deg: float,
    beta2_deg: float,
    phi: float,
) -> Dict[str, Any]:
    """
    Computes Lieblein profile, secondary, and tip clearance aerodynamic losses.
    """
    b1_rad = math.radians(beta1_deg)
    b2_rad = math.radians(beta2_deg)
    cos_b1 = max(0.2, abs(math.cos(b1_rad)))
    cos_b2 = max(0.2, abs(math.cos(b2_rad)))

    theta_c = 0.004 / max(0.1, 1.0 - 1.17 * min(0.60, max(0.0, df_rotor)))
    omega_profile = 2.0 * theta_c * (max(0.1, solidity) / cos_b2) * ((cos_b1 / cos_b2) ** 2)

    beta_m = 0.5 * (b1_rad + b2_rad)
    cos_bm = max(0.2, abs(math.cos(beta_m)))
    cl = 2.0 * (1.0 / max(0.1, solidity)) * abs(math.tan(b1_rad) - math.tan(b2_rad)) * cos_bm
    omega_sec = 0.018 * (cl ** 2) / max(0.1, solidity)
    omega_tip = 0.5 * 0.02 * (cl ** 2) / max(0.1, solidity)
    omega_total = omega_profile + omega_sec + omega_tip

    eta_debit = min(0.15, 0.5 * omega_total * (phi ** 2) / (cos_bm ** 2))

    return {
        "omega_profile": round(omega_profile, 4),
        "omega_secondary": round(omega_sec, 4),
        "omega_tip": round(omega_tip, 4),
        "omega_total": round(omega_total, 4),
        "eta_debit": round(eta_debit, 4),
        "lift_coefficient_cl": round(cl, 3),
    }


def generate_blade_airfoil_coords(
    beta1_deg: float,
    beta2_deg: float,
    chord_mm: float = 60.0,
    max_thickness_pct: float = 10.0,
    n_pts: int = 25,
) -> Dict[str, Any]:
    """
    Generates 2D airfoil suction and pressure surface coordinates for compressor blades.
    """
    stagger_deg = 0.5 * (beta1_deg + beta2_deg)
    camber_deg = beta1_deg - beta2_deg
    stagger_rad = math.radians(stagger_deg)
    camber_rad = math.radians(camber_deg)

    x_norm = [i / max(1, n_pts - 1) for i in range(n_pts)]
    h_max = 0.25 * math.tan(0.5 * abs(camber_rad)) if abs(camber_rad) < 1.4 else 0.2
    y_c = [4.0 * h_max * x * (1.0 - x) * (1.0 if camber_deg >= 0 else -1.0) for x in x_norm]

    t_max = max_thickness_pct / 100.0
    t_half = [
        t_max * (1.4845 * math.sqrt(max(0.0, x)) - 0.63 * x - 1.758 * (x**2) + 1.4215 * (x**3) - 0.5175 * (x**4))
        if x > 0 else 0.0
        for x in x_norm
    ]

    suction = []
    pressure = []
    cos_s = math.cos(stagger_rad)
    sin_s = math.sin(stagger_rad)

    for i in range(n_pts):
        x_base = x_norm[i] * chord_mm
        y_mid = y_c[i] * chord_mm
        dy = t_half[i] * chord_mm

        xs = x_base * cos_s - (y_mid + dy) * sin_s
        ys = x_base * sin_s + (y_mid + dy) * cos_s
        suction.append({"x": round(float(xs), 2), "y": round(float(ys), 2)})

        xp = x_base * cos_s - (y_mid - dy) * sin_s
        yp = x_base * sin_s + (y_mid - dy) * cos_s
        pressure.append({"x": round(float(xp), 2), "y": round(float(yp), 2)})

    return {
        "chord_mm": chord_mm,
        "stagger_deg": round(stagger_deg, 2),
        "camber_deg": round(camber_deg, 2),
        "max_thickness_mm": round(t_max * chord_mm, 2),
        "suction_surface": suction,
        "pressure_surface": pressure,
    }


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
        "C_a": round(Ca1, 2),
        "Ca": round(Ca1, 2),
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
        "C_a": round(Ca2, 2),
        "Ca": round(Ca2, 2),
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

    # Free-Vortex Radial Equilibrium Synthesis (Hub - Mean - Tip)
    radial_dist = solve_radial_equilibrium_free_vortex(
        r_mean=r_mean,
        U_mean=U,
        C_a=C_a,
        C_theta1_mean=C_theta1,
        C_theta2_mean=C_theta2,
        r_hub=r_hub_out,
        r_tip=r_tip_out,
        n_radial=5,
        gamma=gamma,
        cp=cp,
        T01=T01,
    )

    # Lieblein Profile & Secondary Aerodynamic Losses
    loss_metrics = calc_profile_and_secondary_losses(
        df_rotor=df_rotor,
        solidity=solidity,
        beta1_deg=beta1_deg,
        beta2_deg=beta2_deg,
        phi=phi,
    )

    # 2D Blade Airfoil Coordinates Generation (Rotor mean section)
    blade_airfoil = generate_blade_airfoil_coords(
        beta1_deg=beta1_deg,
        beta2_deg=beta2_deg,
        chord_mm=60.0,
        max_thickness_pct=10.0,
        n_pts=25,
    )

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
        "radial_equilibrium": radial_dist,
        "aerodynamic_losses": loss_metrics,
        "blade_airfoil_2d": blade_airfoil,
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

    avg_psi = stages[0]["psi"] if stages else 0.0
    avg_phi = stages[0]["phi"] if stages else 0.0
    avg_reaction = stages[0]["reaction"] if stages else 0.0
    avg_pr = overall_CPR ** (1.0 / n_stages) if n_stages > 0 else 1.0

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
        "psi": round(avg_psi, 4),
        "loading_coefficient_psi": round(avg_psi, 4),
        "phi": round(avg_phi, 4),
        "flow_coefficient_phi": round(avg_phi, 4),
        "reaction": round(avg_reaction, 3),
        "degree_of_reaction_R": round(avg_reaction, 3),
        "PR_stage": round(avg_pr, 4),
        "stage_PR": round(avg_pr, 4),
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

