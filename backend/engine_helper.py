"""
engine_helper.py
Ported from the flight-test-engineering/Gas-Turbine-Propulsion repository.
Adapted for FastAPI backend use (no matplotlib, pure computation only).
Adds the missing iterate_combustor function referenced in episd_10_limit_T.ipynb.
"""

from __future__ import annotations   # BUG-6 fix: allows tuple[X,Y] on Python 3.8/3.9

import numpy as np
import cantera as ct

import ISA_module as ISA


# ─────────────────────────────────────────────────────────────────────────────
# Cantera gas-phase setup
# Fuel model: n-dodecane (representative of Jet-A) via the Reitz mechanism
# ─────────────────────────────────────────────────────────────────────────────
REACTION_MECHANISM = "nDodecane_Reitz.yaml"
PHASE_NAME         = "nDodecane_IG"          # Ideal Gas phase

COMP_AIR  = "O2:0.209, N2:0.787, CO2:0.004" # dry air mole fractions
COMP_FUEL = "c12h26:1"                        # n-dodecane fuel


# ─────────────────────────────────────────────────────────────────────────────
# Isentropic / stagnation relations
# ─────────────────────────────────────────────────────────────────────────────

def get_p(ps: float, gamma: float, M: float) -> float:
    """Stagnation pressure from static pressure, gamma and Mach number."""
    return ps * ((1.0 + ((gamma - 1.0) / 2.0) * M**2) ** (gamma / (gamma - 1.0)))


def get_T(Ts: float, gamma: float, M: float) -> float:
    """Stagnation temperature from static temperature, gamma and Mach number."""
    return Ts * (1.0 + ((gamma - 1.0) / 2.0) * M**2)


def get_Ts(T: float, gamma: float, M: float) -> float:
    """Static temperature from stagnation temperature, gamma and Mach number."""
    return T / (1.0 + ((gamma - 1.0) / 2.0) * M**2)


def get_ps(p: float, Ts: float, Tt: float, gamma: float) -> float:
    """Static pressure from stagnation pressure and temperature ratio."""
    return p * (Ts / Tt) ** (gamma / (gamma - 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# Cantera gas property helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_gamma(gas: ct.Solution) -> float:
    """Ratio of specific heats γ = Cp/Cv for the given Cantera gas object."""
    return gas.cp / gas.cv


def get_R(gas: ct.Solution) -> float:
    """Specific gas constant R = Cp - Cv for the given Cantera gas object."""
    return gas.cp - gas.cv


def get_a(gas: ct.Solution) -> float:
    """Local speed of sound for the given Cantera gas object."""
    return np.sqrt(get_R(gas) * get_gamma(gas) * gas.T)


# ─────────────────────────────────────────────────────────────────────────────
# Component models
# ─────────────────────────────────────────────────────────────────────────────

def iterate_inlet(
    mdot: float,
    A: float,
    gas_in: ct.Solution,
    eta_i: float,
    M_in: float,
    gas_out: ct.Solution,
) -> tuple[float, bool]:
    """
    Iteratively solve for the exit Mach number and gas state of an inlet section.

    Parameters
    ----------
    mdot   : mass flow [kg/s]
    A      : exit cross-sectional area [m²]
    gas_in : Cantera Solution — gas state at section entrance
    eta_i  : adiabatic efficiency of the inlet (1.0 = isentropic)
    M_in   : Mach number at section entrance
    gas_out: Cantera Solution — will be updated with exit state

    Returns
    -------
    M_out      : Mach number at exit (0 if no convergence)
    converged  : True if converged within tolerance
    """
    tol      = 0.01   # velocity convergence tolerance [m/s]
    max_iter = 100
    converged = False
    n_iter    = 0

    V_in      = M_in * get_a(gas_in)
    gamma_in  = get_gamma(gas_in)
    T_0in     = get_T(gas_in.T, gamma_in, M_in)
    p_0in     = get_p(gas_in.P, gamma_in, M_in)

    T_0out       = T_0in
    V_out_guess  = mdot / (gas_in.density * A)
    gamma_out    = gamma_in

    while not converged and n_iter <= max_iter:
        T_out = gas_in.T + (
            V_in**2 / (2.0 * gas_in.cp) - V_out_guess**2 / (2.0 * gas_out.cp)
        )
        if T_out <= 1.0 or T_out > T_0out:
            return 0.0, False
        p_0out = gas_in.P * (
            1.0 + eta_i * V_in**2 / (2.0 * gas_in.cp * gas_in.T)
        ) ** (gamma_in / (gamma_in - 1.0))
        ratio = max(T_out / T_0out, 1e-6)
        p_out = p_0out * (ratio) ** (gamma_out / (gamma_out - 1.0))
        if p_out <= 0.0:
            return 0.0, False

        gas_out.TP = T_out, p_out
        gamma_out  = get_gamma(gas_out)

        V_out       = V_out_guess
        V_out_guess = mdot / (gas_out.density * A)

        if abs(V_out - V_out_guess) < tol:
            converged = True
            M_out = V_out / get_a(gas_out)
        elif n_iter < max_iter:
            n_iter += 1
        else:
            M_out = 0.0

    return M_out, converged


def iterate_combustor(
    gas_in: ct.Solution,
    V_nominal: float,
    M_in: float,
    dp_over_p: float,
    gas_out: ct.Solution,
) -> tuple[float, bool]:
    """
    Set the static T and P at the combustor exit before the equilibrate() call.

    The combustor is modelled as:
      • A constant stagnation-temperature section (adiabatic mixing of cold
        fuel + hot compressed air before ignition).
      • A dp_over_p fractional total-pressure loss.
      • A prescribed nominal flow velocity V_nominal at exit.

    gas_out must already have its composition set (set_equivalence_ratio).
    After this function returns, the caller calls gas_out.equilibrate('HP')
    to simulate combustion at constant enthalpy and pressure.

    Parameters
    ----------
    gas_in    : Cantera Solution at compressor exit (station 3)
    V_nominal : design flow velocity inside combustor [m/s]
    M_in      : Mach number entering combustor
    dp_over_p : fractional total-pressure loss  (e.g. 0.06 = 6 %)
    gas_out   : Cantera Solution with fuel-air mixture pre-set

    Returns
    -------
    M_out     : Mach number at combustor exit
    converged : always True (non-iterative)
    """
    gamma_in = get_gamma(gas_in)
    T_0in    = get_T(gas_in.T, gamma_in, M_in)
    p_0in    = get_p(gas_in.P, gamma_in, M_in)

    # Total-pressure drop
    p_0out = p_0in * (1.0 - dp_over_p)

    # Static temperature from stagnation minus kinetic energy of V_nominal flow
    # Use the cold mixture Cp (before combustion) — conservative approximation
    T_out = T_0in - V_nominal**2 / (2.0 * gas_out.cp)

    # Static pressure from isentropic relation with current gamma
    gamma_out = get_gamma(gas_out)
    p_out = get_ps(p_0out, T_out, T_0in, gamma_out)

    # Update gas state (composition is already set by set_equivalence_ratio)
    gas_out.TP = T_out, p_out

    M_out = V_nominal / get_a(gas_out)
    return M_out, True


def multi_stage_compressor(
    gas_in: ct.Solution,
    n_stages: int,
    CPR: float,
    eta_c: float,
    M_in: float,
    gas_out: ct.Solution,
) -> tuple[list, bool, float]:
    """
    Model an axial multi-stage compressor with approximately equal temperature
    rise per stage.

    Returns
    -------
    stage_data       : list of (T_static, P_static) for each stage exit
    converged        : True if the stage-equalisation loop converged
    compressor_work  : total specific work absorbed [J/kg]
    """
    gamma_in = get_gamma(gas_in)
    T_0in    = get_T(gas_in.T, gamma_in, M_in)
    p_0in    = get_p(gas_in.P, gamma_in, M_in)

    CR_stage = CPR ** (1.0 / n_stages)

    # Pressure-rise shift: load earlier stages slightly more to equalise
    # temperature rise across all stages (matches notebook algorithm)
    stage_multiplier = np.ones(n_stages)
    shift      = 0.001
    step_shift = shift / n_stages
    center     = int(n_stages / 2)
    shifter    = np.ones(n_stages)
    for i in range(center):
        shifter[i]              = 1.0 + (center - i) * step_shift
        shifter[n_stages - i - 1] = 1.0 - (center - i) * step_shift

    converged   = False
    n_iter      = 0
    max_iter    = 5000
    prev_delta_t = 1000.0

    stages_p_out = np.zeros(n_stages)
    stages_T_out = np.zeros(n_stages)
    stage_gas    = ct.Solution(REACTION_MECHANISM, PHASE_NAME)
    stage_gas.X  = COMP_AIR

    compressor_work = 0.0

    while not converged and n_iter <= max_iter:
        stage_gas.TP = gas_in.T, gas_in.P

        for st_counter in range(n_stages):
            T_i   = stage_gas.T
            gamma = get_gamma(stage_gas)
            p0    = get_p(stage_gas.P, gamma, M_in) * CR_stage * stage_multiplier[st_counter]
            T0    = T_0in / eta_c * ((p0 / p_0in) ** ((gamma - 1.0) / gamma) - 1.0) + T_0in

            T = get_Ts(T0, gamma, M_in)
            p = get_ps(p0, T, T0, gamma)
            stage_gas.TP = T, p

            gamma = get_gamma(stage_gas)
            T     = get_Ts(T0, gamma, M_in)
            p     = get_ps(p0, T, T0, gamma)
            stage_gas.TP = T, p

            stages_p_out[st_counter] = p
            stages_T_out[st_counter] = T
            compressor_work += stage_gas.cp * (T - T_i)

            p_0in = p0
            T_0in = T0

        all_temps = np.insert(stages_T_out, 0, gas_in.T)
        max_delta_t = np.diff(all_temps).max()

        if max_delta_t < prev_delta_t and n_iter < max_iter:
            n_iter += 1
            T_0in = get_T(gas_in.T, gamma_in, M_in)
            p_0in = get_p(gas_in.P, gamma_in, M_in)
            compressor_work  = 0.0
            stage_multiplier = np.multiply(stage_multiplier, shifter)
            geom_mean = np.prod(stage_multiplier) ** (1.0 / n_stages)
            if geom_mean > 0:
                stage_multiplier /= geom_mean
            prev_delta_t     = max_delta_t
        elif n_iter >= max_iter:
            n_iter += 1
        else:
            converged = True

    gas_out.TP = T, p
    return list(zip(stages_T_out.tolist(), stages_p_out.tolist())), converged, compressor_work


def multi_stage_turbine(
    gas_in: ct.Solution,
    W_c: float,
    n_stages: int,
    eta_t: float,
    eta_m: float,
    M_in: float,
    M_out: float,
    gas_out: ct.Solution,
) -> tuple[list, float]:
    """
    Model an axial multi-stage turbine sized to supply compressor work W_c.

    Returns
    -------
    stage_data    : list of (T_static, P_static) for each stage exit
    turbine_work  : total specific work recovered [J/kg]  (negative = work out)
    """
    gamma_in = get_gamma(gas_in)
    T_0in    = get_T(gas_in.T, gamma_in, M_in)
    p_0in    = get_p(gas_in.P, gamma_in, M_in)

    T_in = get_Ts(T_0in, gamma_in, M_in)
    p_in = get_ps(p_0in, T_in, T_0in, gamma_in)

    W_per_stage  = (W_c / eta_m) / n_stages

    stages_p_out = np.zeros(n_stages)
    stages_T_out = np.zeros(n_stages)
    stage_gas    = ct.Solution(REACTION_MECHANISM, PHASE_NAME)
    stage_gas.TPX = T_in, p_in, gas_in.X

    turbine_work = 0.0

    for st_counter in range(n_stages):
        gamma  = get_gamma(stage_gas)
        T_i    = stage_gas.T
        T_0out_prime = T_0in - W_per_stage / (stage_gas.cp * eta_t)
        if T_0out_prime <= 1.0:
            raise ValueError(f"Required turbine work exceeds entering gas enthalpy (T_0in={T_0in:.1f} K).")
        p_0out       = p_0in * (T_0out_prime / T_0in) ** (gamma / (gamma - 1.0))
        T_0out       = T_0in - eta_t * (T_0in - T_0out_prime)
        if T_0out <= 1.0:
            raise ValueError(f"Turbine stage exit temperature fell below physical limits (T_0out={T_0out:.1f} K).")

        T = get_Ts(T_0out, gamma, M_out)
        p = get_ps(p_0out, T, T_0out, gamma)
        stage_gas.TP = T, p

        gamma = get_gamma(stage_gas)
        T     = get_Ts(T_0out, gamma, M_out)
        p     = get_ps(p_0out, T, T_0out, gamma)
        stage_gas.TP = T, p

        stages_p_out[st_counter] = p
        stages_T_out[st_counter] = T
        turbine_work += stage_gas.cp * (T - T_i)

        p_0in = p_0out
        T_0in = T_0out

    gas_out.TP = T, p
    return list(zip(stages_T_out.tolist(), stages_p_out.tolist())), turbine_work


def calc_nozzle(
    gas_in: ct.Solution,
    M_in: float,
    eta_noz: float,
    p_amb: float,
    A_star: float,
    V_i: float,
    gas_out: ct.Solution,
) -> tuple[bool, float, float, float]:
    """
    Convergent nozzle: determine if flow is choked and compute thrust.

    Returns
    -------
    choked  : True if nozzle throat is sonic
    mdot    : mass flow [kg/s]
    M_out   : exit Mach number
    F       : specific thrust [N·s/kg]
    """
    gamma  = get_gamma(gas_in)
    R      = get_R(gas_in)
    p0_in  = get_p(gas_in.P, gamma, M_in)
    T0_in  = get_T(gas_in.T, gamma, M_in)

    crit_term = 1.0 - (1.0 / max(eta_noz, 1e-4)) * ((gamma - 1.0) / (gamma + 1.0))
    if crit_term <= 1e-4:
        pc_ratio = 100.0  # physical choked limit guard
    else:
        pc_ratio = 1.0 / (crit_term ** (gamma / (gamma - 1.0)))

    if p_amb <= p0_in / pc_ratio:
        choked = True
        p      = p0_in / pc_ratio
        T      = T0_in / ((gamma + 1.0) / 2.0)
        V      = np.sqrt(gamma * R * T)
        rho    = p / (R * T)
        mdot   = rho * V * A_star
        F      = (V - V_i) + (A_star / mdot) * (p - p_amb)
        M_out  = 1.0
    else:
        choked = False
        p      = p_amb
        T      = T0_in - eta_noz * T0_in * (
            1.0 - 1.0 / (p0_in / p_amb) ** ((gamma - 1.0) / gamma)
        )
        # Guard: T must be < T0_in for a positive velocity; clamp if numerical drift
        T    = min(T, T0_in - 1e-6)
        if T <= 0.0:
            gas_out.TP = max(T, 1.0), p
            return False, 0.0, 0.0, 0.0
        V    = np.sqrt(2.0 * gas_in.cp * (T0_in - T))
        rho  = p / (R * T)
        mdot = rho * V * A_star
        F    = V - V_i
        M_out = V / np.sqrt(gamma * R * T)

    gas_out.TP = T, p
    return choked, mdot, M_out, F


# ─────────────────────────────────────────────────────────────────────────────
# Brayton Cycle T-s Curve Generator (True Isobaric Integration)
# ─────────────────────────────────────────────────────────────────────────────

def generate_brayton_ts_loop(stations: dict, is_turbofan: bool = False, n_isobar_pts: int = 12) -> dict:
    """
    Constructs a continuous, closed thermodynamic coordinate loop for the Brayton cycle
    with authentic logarithmic isobaric heat addition and rejection curvature.
    
    Returns:
    --------
    dict with:
      - 'core_loop': list of dicts with keys: station, label, s_JkgK, T_K, delta_s_kJkgK, P_kPa
      - 'bypass_loop': list of dicts for turbofan bypass expansion
    """
    if not stations:
        return {"core_loop": [], "bypass_loop": []}

    st_a = stations.get("a", {})
    st_1 = stations.get("1", {})
    st_2 = stations.get("2", {})
    st_3 = stations.get("3", {})
    st_4 = stations.get("4", {})
    st_5 = stations.get("5", {})
    st_8 = stations.get("8", {})

    sa = float(st_a.get("s_JkgK", 6850.0))
    Ta = float(st_a.get("T_K", 288.15))
    Pa = float(st_a.get("P_total_kPa", 101.325))

    core_loop = []

    def make_pt(s_val, t_val, sid="", lbl="", p_val=None):
        return {
            "station": sid,
            "label": lbl,
            "s_JkgK": round(float(s_val), 1),
            "T_K": round(float(t_val), 1),
            "delta_s_kJkgK": round(float(s_val - sa) / 1000.0, 4),
            "P_kPa": round(float(p_val), 2) if p_val is not None else None,
        }

    # Station a: Ambient
    core_loop.append(make_pt(sa, Ta, "a", "Ambient Freestream", Pa))

    # Station 1: Inlet entry
    if "1" in stations:
        s1 = float(st_1.get("s_JkgK", sa))
        T1 = float(st_1.get("T_K", Ta))
        core_loop.append(make_pt(s1, T1, "1", "Inlet Entry", st_1.get("P_total_kPa")))

    # Station 2: Fan / Compressor face
    s2 = float(st_2.get("s_JkgK", sa))
    T2 = float(st_2.get("T_K", Ta))
    core_loop.append(make_pt(s2, T2, "2", "Compressor Face", st_2.get("P_total_kPa")))

    # Station 21 (for turbofan): Core face
    if is_turbofan and "21" in stations:
        st_21 = stations["21"]
        s2 = float(st_21.get("s_JkgK", s2))
        T2 = float(st_21.get("T_K", T2))
        core_loop.append(make_pt(s2, T2, "21", "Core HPC Face", st_21.get("P_total_kPa")))

    # Station 3: Compressor exit
    s3 = float(st_3.get("s_JkgK", s2 + 100.0))
    T3 = float(st_3.get("T_K", T2 * 2.0))
    P3 = float(st_3.get("P_total_kPa", Pa * 8.0))

    # Intermediate points along compression (polytropic/isentropic leg 2 -> 3)
    n_comp = 4
    for i in range(1, n_comp):
        f = i / float(n_comp)
        t_i = T2 + f * (T3 - T2)
        s_i = s2 + f * (s3 - s2)
        core_loop.append(make_pt(s_i, t_i, "", f"Compression Stage {i}"))

    core_loop.append(make_pt(s3, T3, "3", "HPC Exit / Combustor Inlet", P3))

    # Station 4: Combustor exit
    s4 = float(st_4.get("s_JkgK", s3 + 1000.0))
    T4 = float(st_4.get("T_K", 1500.0))
    P4 = float(st_4.get("P_total_kPa", P3 * 0.95))

    # Isobaric Heat Addition leg (3 -> 4): T(s) = T3 * exp((s - s3)/cp)
    for i in range(1, n_isobar_pts):
        f = i / float(n_isobar_pts)
        t_i = T3 + f * (T4 - T3)
        log_ratio = np.log(max(1e-4, t_i / T3)) / max(1e-4, np.log(max(1e-4, T4 / T3)))
        s_i = s3 + (s4 - s3) * log_ratio
        core_loop.append(make_pt(s_i, t_i, "", f"Combustor Heat Addition ({int(f*100)}%)", P3))

    core_loop.append(make_pt(s4, T4, "4", "Combustor Exit / Turbine Inlet", P4))

    # Station 41 (HPT exit if turbofan)
    if is_turbofan and "41" in stations:
        st_41 = stations["41"]
        s41 = max(s4, float(st_41.get("s_JkgK", s4 + 50.0)))
        T41 = float(st_41.get("T_K", T4 * 0.8))
        core_loop.append(make_pt(s41, T41, "41", "HPT Exit", st_41.get("P_total_kPa")))
    else:
        s41 = s4

    # Station 5: Turbine exit (Second Law: expansion with irreversibilities requires s5 >= s41)
    s5 = max(s41, float(st_5.get("s_JkgK", s41 + 80.0)))
    T5 = float(st_5.get("T_K", T4 * 0.65))
    core_loop.append(make_pt(s5, T5, "5", "Turbine Exit", st_5.get("P_total_kPa")))

    # Station 8: Nozzle exit (s8 >= s5)
    s8 = max(s5, float(st_8.get("s_JkgK", s5 + 40.0)))
    T8 = float(st_8.get("T_K", T5 * 0.9))
    core_loop.append(make_pt(s8, T8, "8", "Nozzle Exit / Exhaust", st_8.get("P_total_kPa")))

    # Atmospheric Isobaric Heat Rejection leg (8 -> a): T(s) = Ta * exp((s - sa)/cp)
    for i in range(1, n_isobar_pts):
        f = i / float(n_isobar_pts)
        t_i = T8 - f * (T8 - Ta)
        log_ratio = np.log(max(1e-4, t_i / Ta)) / max(1e-4, np.log(max(1e-4, T8 / Ta)))
        s_i = sa + (s8 - sa) * log_ratio
        core_loop.append(make_pt(s_i, t_i, "", f"Atmospheric Cooling ({int(f*100)}%)", Pa))

    # Complete closure by re-attaching Station a
    core_loop.append(make_pt(sa, Ta, "a", "Ambient Closure", Pa))

    # Bypass stream for turbofan
    bypass_loop = []
    if is_turbofan and "13" in stations and "18" in stations:
        st_13 = stations["13"]
        st_18 = stations["18"]
        s13 = float(st_13.get("s_JkgK", s2 + 30.0))
        T13 = float(st_13.get("T_K", T2 * 1.2))
        s18 = float(st_18.get("s_JkgK", s13 + 20.0))
        T18 = float(st_18.get("T_K", T13 * 0.95))

        bypass_loop.append(make_pt(s2, T2, "2", "Fan Face", st_2.get("P_total_kPa")))
        bypass_loop.append(make_pt(s13, T13, "13", "Fan Duct Exit", st_13.get("P_total_kPa")))
        bypass_loop.append(make_pt(s18, T18, "18", "Bypass Nozzle Exit", st_18.get("P_total_kPa")))
        # Return to ambient
        bypass_loop.append(make_pt(sa, Ta, "a", "Ambient Re-mix", Pa))

    return {
        "core_loop": core_loop,
        "bypass_loop": bypass_loop,
    }

