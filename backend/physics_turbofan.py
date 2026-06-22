"""
physics_turbofan.py
Physics-based 0D cycle model for a two-spool turbofan.
"""

from __future__ import annotations
import numpy as np
import cantera as ct
from engine_helper import (
    REACTION_MECHANISM, PHASE_NAME, COMP_AIR, COMP_FUEL,
    get_gamma, get_R, get_a, get_T, get_p, get_Ts, get_ps,
    iterate_inlet, iterate_combustor,
    multi_stage_compressor, multi_stage_turbine, calc_nozzle,
)
import ISA_module as ISA



# ─────────────────────────────────────────────────────────────────────────────
# Default engine: Generic High-Bypass Turbofan (similar to CF34)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TF_PARAM: dict = {
    "A1": 1.5,            # m²  inlet capture area
    "A2": 1.5,            # m²  fan face area
    "fan_n_stages": 1,    #     number of fan stages
    "hpc_n_stages": 9,    #     number of HPC stages
    "hpt_n_stages": 1,    #     number of HPT stages
    "lpt_n_stages": 3,    #     number of LPT stages
    "A8": 0.15,           # m²  core nozzle throat area
    "BPR": 5.0,           #     bypass ratio
}

DEFAULT_TF_PERF: dict = {
    "eta_i":     0.98,    # inlet adiabatic efficiency
    "FPR":       1.6,     # Fan pressure ratio
    "eta_fan":   0.89,    # Fan isentropic efficiency
    "CPR":       18.0,    # HPC pressure ratio
    "eta_hpc":   0.85,    # HPC isentropic efficiency
    "eta_b":     0.99,    # combustor efficiency
    "dp_over_p": 0.05,    # combustor total-pressure loss fraction
    "max_f":     0.30,    # max fuel φ
    "min_f":     0.05,    # min fuel φ
    "V_nominal": 30.0,    # m/s  nominal combustor flow velocity
    "T_max":     1500.0,  # K    maximum TIT limit
    "eta_hpt":   0.88,    # HPT isentropic efficiency
    "eta_lpt":   0.90,    # LPT isentropic efficiency
    "mech_loss_hp": 0.99, # mechanical efficiency HP spool
    "mech_loss_lp": 0.99, # mechanical efficiency LP spool
    "eta_noz_core": 0.98, # core nozzle adiabatic efficiency
    "eta_noz_byp":  0.98, # bypass nozzle adiabatic efficiency
}


# ─────────────────────────────────────────────────────────────────────────────
# Core function
# ─────────────────────────────────────────────────────────────────────────────

def calc_turbofan(
    eng_param: dict,
    eng_perf: dict,
    throttle_pos: float = 1.0,
    alt: float = 0.0,
    M_i: float = 0.0,
    mdot_core_guess: float = 20.0,
) -> dict:
    try:
        return _calc_turbofan_raw(
            eng_param, eng_perf, throttle_pos, alt, M_i, mdot_core_guess
        )
    except Exception as e:
        print(f"calc_turbofan failed: {e}")
        return {
            "T_core":         0.0,
            "T_byp":          0.0,
            "T":              0.0,
            "mdot_fuel":      0.0,
            "TSFC":           float("nan"),
            "SAR":            float("nan"),
            "mdot_core":      0.0,
            "mdot_byp":       0.0,
            "BPR":            eng_param.get("BPR", 0.0) if isinstance(eng_param, dict) else 0.0,
            "A18_calc":       0.0,
            "choked_core":    False,
            "choked_byp":     False,
            "T_max_limited":  False,
            "converged":      False,
            "alt_ft":         alt,
            "Mach":           M_i,
            "throttle_pos":   throttle_pos,
            "stations":       {},
            "error_msg":      str(e),
        }

def _calc_turbofan_raw(
    eng_param: dict,
    eng_perf: dict,
    throttle_pos: float = 1.0,
    alt: float = 0.0,
    M_i: float = 0.0,
    mdot_core_guess: float = 20.0,
) -> dict:
    """
    Calculate steady-state multi-spool turbofan performance via a dual
    mass-flow convergence loop.
    """

    # ── Ambient and flight conditions ───────────────────────────────────────
    V_i   = ISA.M2Vt(M_i, alt) * ISA.kt2ms   # true airspeed [m/s]
    p_amb = ISA.p(alt)                         # static ambient pressure [Pa]
    T_amb = ISA.T(alt)                         # static ambient temperature [K]

    # ── Station initialisation ──────────────────────────────────────────────
    st = ["a", 1, 2, 13, 21, 3, 4, 41, 5, 8, 18]
    gas: dict[str | int, ct.Solution] = {}
    M:   dict[str | int, float] = {}

    for station in st:
        gas[station] = ct.Solution(REACTION_MECHANISM, PHASE_NAME)
        gas[station].X  = COMP_AIR
        gas[station].TP = T_amb, p_amb
        M[station]      = M_i

    # ── Mass-flow convergence loop ───────────────────────────────────────────
    converged   = False
    tol         = 0.1     # kg/s
    mdot_iter   = 0
    max_mdot_iter = 30    # turbofans can take a bit longer to settle
    conv_error  = False
    current_mdot_c = mdot_core_guess
    A18_calc = 0.0

    mixt_frac = 0.0
    phi = 0.0
    T_max_limited = False

    while not converged and mdot_iter <= max_mdot_iter and not conv_error:
        current_mdot_b = current_mdot_c * eng_param["BPR"]
        mdot_tot = current_mdot_c + current_mdot_b

        # ── Station a → 1 (free-stream to inlet entry) ─────────────────────
        M_calc, conv = iterate_inlet(
            mdot_tot, eng_param["A1"],
            gas["a"], 1.0, M["a"], gas[1]
        )
        if conv: M[1] = M_calc
        else: conv_error = True

        # ── Station 1 → 2 (inlet to fan face) ──────────────────────────────
        M_calc, conv = iterate_inlet(
            mdot_tot, eng_param["A2"],
            gas[1], eng_perf["eta_i"], M[1], gas[2]
        )
        if conv: M[2] = M_calc
        else: conv_error = True

        # ── Station 2 → 13 / 21 (Fan) ──────────────────────────────────────
        _, conv, w_fan_spec = multi_stage_compressor(
            gas[2], eng_param["fan_n_stages"],
            eng_perf["FPR"], eng_perf["eta_fan"],
            M[2], gas[13]
        )
        if not conv: conv_error = True
        
        M[13] = M[2]
        M[21] = M[2]
        gas[21].TPX = gas[13].T, gas[13].P, gas[13].X

        # ── BYPASS STREAM ──
        # ── Station 13 → 18 (Bypass nozzle) ────────────────────────────────
        p0_13 = get_p(gas[13].P, get_gamma(gas[13]), M[13])
        if p0_13 <= p_amb:
            choked_b, mdot_noz_b, M[18], F_b_spec, A18_calc = False, current_mdot_b, 0.0, 0.0, 0.0
        else:
            gamma_b = get_gamma(gas[13])
            R_b = get_R(gas[13])
            T0_13 = get_T(gas[13].T, gamma_b, M[13])
            pc_ratio = 1.0 / (
                1.0 - (1.0 / eng_perf["eta_noz_byp"]) * ((gamma_b - 1.0) / (gamma_b + 1.0))
            ) ** (gamma_b / (gamma_b - 1.0))
            
            if p_amb <= p0_13 / pc_ratio:
                choked_b = True
                p_18 = p0_13 / pc_ratio
                T_18 = T0_13 / ((gamma_b + 1.0) / 2.0)
                V_18 = np.sqrt(gamma_b * R_b * T_18)
                rho_18 = p_18 / (R_b * T_18)
                A18_calc = current_mdot_b / (rho_18 * V_18)
                F_b_spec = (V_18 - V_i) + (A18_calc / current_mdot_b) * (p_18 - p_amb)
                M[18] = 1.0
            else:
                choked_b = False
                p_18 = p_amb
                T_18 = T0_13 - eng_perf["eta_noz_byp"] * T0_13 * (
                    1.0 - 1.0 / (p0_13 / p_amb) ** ((gamma_b - 1.0) / gamma_b)
                )
                V_18 = np.sqrt(2.0 * gas[13].cp * (T0_13 - T_18))
                rho_18 = p_18 / (R_b * T_18)
                A18_calc = current_mdot_b / (rho_18 * V_18)
                F_b_spec = V_18 - V_i
                M[18] = V_18 / np.sqrt(gamma_b * R_b * T_18)
            
            gas[18].TP = T_18, p_18
            mdot_noz_b = current_mdot_b

        # ── CORE STREAM ──
        # ── Station 21 → 3 (HPC) ───────────────────────────────────────────
        _, conv, w_hpc_spec = multi_stage_compressor(
            gas[21], eng_param["hpc_n_stages"],
            eng_perf["CPR"], eng_perf["eta_hpc"],
            M[21], gas[3]
        )
        if not conv: conv_error = True
        M[3] = M[21]

        # ── Station 3 → 4 (Combustor with TIT limiter) ──────────────────────
        # Initial evaluation at full internal throttle (T_throttle = 1.0)
        _TIT_FLOOR = 0.5  # minimum internal throttle scalar
        phi = (eng_perf["max_f"] - eng_perf["min_f"]) * throttle_pos + eng_perf["min_f"]
        gas[4].set_equivalence_ratio(phi=phi, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole")
        mixt_frac = gas[4].mixture_fraction(fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mass")
        M_calc, conv = iterate_combustor(gas[3], eng_perf["V_nominal"], M[3], eng_perf["dp_over_p"], gas[4])
        if conv: M[4] = M_calc
        gas[4].equilibrate("HP")

        if gas[4].T > eng_perf["T_max"]:
            # Bug T1-C fix: bisect on the internal throttle scalar to find the highest
            # value that keeps TIT ≤ T_max.  Replaces the broken linear-decrement loop
            # that could exit early while the combustor was still above the limit.
            T_max_limited = True
            lo, hi = _TIT_FLOOR, 1.0
            for _bis in range(25):  # 25 iterations → precision ~1.5e-8 on [0.5, 1.0]
                mid = 0.5 * (lo + hi)
                phi_bis = (eng_perf["max_f"] - eng_perf["min_f"]) * throttle_pos * mid + eng_perf["min_f"]
                gas[4].set_equivalence_ratio(phi=phi_bis, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole")
                iterate_combustor(gas[3], eng_perf["V_nominal"], M[3], eng_perf["dp_over_p"], gas[4])
                gas[4].equilibrate("HP")
                if gas[4].T > eng_perf["T_max"]:
                    hi = mid
                else:
                    lo = mid
                if abs(gas[4].T - eng_perf["T_max"]) < 0.5:  # 0.5 K tolerance
                    break
            # Settle on the highest compliant scalar (lo is always the last T ≤ T_max)
            phi = (eng_perf["max_f"] - eng_perf["min_f"]) * throttle_pos * lo + eng_perf["min_f"]
            gas[4].set_equivalence_ratio(phi=phi, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole")
            mixt_frac = gas[4].mixture_fraction(fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mass")
            M_calc, conv = iterate_combustor(gas[3], eng_perf["V_nominal"], M[3], eng_perf["dp_over_p"], gas[4])
            if conv: M[4] = M_calc
            gas[4].equilibrate("HP")

        for i in [41, 5, 8]:
            gas[i].TPX = gas[4].T, gas[4].P, gas[4].X

        # ── Station 4 → 41 (HPT) ──────────────────────────────────────────────
        # Bug N2 fix: mdot_turb uses correct FAR = Z/(1-Z) for fuel contribution.
        _far_i    = mixt_frac / (1.0 - mixt_frac) if mixt_frac < 1.0 else 0.0
        mdot_turb = current_mdot_c + (_far_i / eng_perf["eta_b"]) * current_mdot_c
        w_hpt_spec = (w_hpc_spec * current_mdot_c) / (mdot_turb * eng_perf["mech_loss_hp"])
        
        h_avail_hp = gas[4].cp * gas[4].T
        if w_hpt_spec > h_avail_hp:
            conv_error = True
            break

        _, _ = multi_stage_turbine(
            gas[4], w_hpt_spec,
            eng_param["hpt_n_stages"], eng_perf["eta_hpt"],
            1.0, M[4], M[4], gas[41]
        )
        M[41] = M[4]

        # ── Station 41 → 5 (LPT) ───────────────────────────────────────────
        w_lpt_spec = (w_fan_spec * mdot_tot) / (mdot_turb * eng_perf["mech_loss_lp"])
        
        h_avail_lp = gas[41].cp * gas[41].T
        if w_lpt_spec > h_avail_lp:
            conv_error = True
            break

        _, _ = multi_stage_turbine(
            gas[41], w_lpt_spec,
            eng_param["lpt_n_stages"], eng_perf["eta_lpt"],
            1.0, M[41], M[41], gas[5]
        )
        M[5] = M[41]

        # ── Station 5 → 8 (Core Nozzle) ────────────────────────────────────
        p0_5 = get_p(gas[5].P, get_gamma(gas[5]), M[5])
        if p0_5 <= p_amb:
            choked_c, mdot_noz_c, M[8], F_c_spec = False, current_mdot_c * 0.9, 0.0, 0.0
        else:
            choked_c, mdot_noz_c, M[8], F_c_spec = calc_nozzle(
                gas[5], M[5], eng_perf["eta_noz_core"],
                p_amb, eng_param["A8"], V_i, gas[8]
            )

        # ── Convergence check ───────────────────────────────────────────────
        err_c = abs(mdot_noz_c - current_mdot_c)
        
        if err_c < tol:
            converged = True
        else:
            mdot_iter += 1
            alpha = 0.2
            current_mdot_c = (1.0 - alpha) * current_mdot_c + alpha * mdot_noz_c


    # ── Post-loop performance metrics ───────────────────────────────────────
    # Bug T1-A fix: FAR = Z/(1-Z), not Z.
    _far      = mixt_frac / (1.0 - mixt_frac) if mixt_frac < 1.0 else 0.0
    mdot_fuel = (_far / eng_perf["eta_b"]) * mdot_noz_c
    thrust_c_kN = F_c_spec * mdot_noz_c / 1000.0
    thrust_b_kN = F_b_spec * mdot_noz_b / 1000.0
    thrust_total_kN = thrust_c_kN + thrust_b_kN
    
    BPR = mdot_noz_b / mdot_noz_c if mdot_noz_c > 0 else 0.0

    TSFC = (mdot_fuel / thrust_total_kN) if thrust_total_kN > 0 else float("nan")
    SAR  = V_i / mdot_fuel if mdot_fuel > 0 else float("nan")

    # ── Station summary ─────────────────────────────────────────────────────
    station_labels = {
        "a": "Ambient",
        1:   "Inlet entry",
        2:   "Fan face",
        13:  "Fan exit (bypass)",
        21:  "HPC face (core)",
        3:   "HPC exit",
        4:   "Combustor exit",
        41:  "HPT exit",
        5:   "LPT exit",
        8:   "Core nozzle exit",
        18:  "Bypass nozzle exit",
    }
    
    stations = {}
    for s in st:
        stations[str(s)] = {
            "label":   station_labels[s],
            "T_K":     round(gas[s].T, 1),
            "P_Pa":    round(gas[s].P, 0),
            "P_atm":   round(gas[s].P / ct.one_atm, 3),
            "Mach":    round(M[s], 4),
            "s_JkgK":  round(gas[s].entropy_mass, 1),
            "h_Jkg":   round(gas[s].enthalpy_mass, 1),
        }

    # ── Emissions (Station 4) ───────────────────────────────────────────────
    FAR = mixt_frac / (1.0 - mixt_frac) if mixt_frac < 1.0 else 0.0
    if phi < 0.99: burn_state = "Lean Burn"
    elif phi > 1.01: burn_state = "Rich Burn"
    else: burn_state = "Balanced (Stoichiometric)"

    emissions_EI = {"NOx": 0.0, "CO": 0.0, "CO2": 0.0}
    if FAR > 0:
        gas4 = gas[4]
        MW_mix = gas4.mean_molecular_weight
        sp_dict = gas4.mole_fraction_dict()
        def calc_ei(species_name, mw_species):
            X_spec = sp_dict.get(species_name.lower(), sp_dict.get(species_name.upper(), 0.0))
            return (X_spec * mw_species) / (FAR * MW_mix) * 1000.0
        emissions_EI["NOx"] = round(calc_ei("NO", 30.01) + calc_ei("NO2", 46.01), 2)
        emissions_EI["CO"]  = round(calc_ei("CO", 28.01), 2)
        emissions_EI["CO2"] = round(calc_ei("CO2", 44.01), 2)

    stations["4"]["combustion_metrics"] = {
        "fuel_air_ratio": round(FAR, 4),
        "equivalence_ratio": round(phi, 3),
        "burn_state": burn_state,
        "emissions_EI": emissions_EI,
    }

    return {
        "T_core":         round(thrust_c_kN, 3),
        "T_byp":          round(thrust_b_kN, 3),
        "T":              round(thrust_total_kN, 3),
        "mdot_fuel":      round(mdot_fuel, 5),
        "TSFC":           round(TSFC * 3600.0, 2),
        "SAR":            round(SAR * ISA.ms2kt / 3600.0, 5),
        "mdot_core":      round(mdot_noz_c, 2),
        "mdot_byp":       round(current_mdot_b, 2),
        "BPR":            round(BPR, 2),
        "A18_calc":       round(A18_calc, 4),
        "choked_core":    bool(choked_c),
        "choked_byp":     bool(choked_b),
        "T_max_limited":  T_max_limited,
        "converged":      converged,
        "alt_ft":         alt,
        "Mach":           M_i,
        "throttle_pos":   throttle_pos,
        "stations":       stations,
    }
