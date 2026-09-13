"""
turbojet.py
Full port of the calc_thrust() function from episd_10_limit_T.ipynb
(flight-test-engineering/Gas-Turbine-Propulsion).

All engine parameters are passed in as dictionaries — exactly matching
the notebook's eng_param / eng_perf interface — so the defaults shown
in the notebook are preserved.
"""

from __future__ import annotations
import math
import cantera as ct
from engine_helper import (
    REACTION_MECHANISM, PHASE_NAME, COMP_AIR, COMP_FUEL,
    get_gamma, get_R, get_a, get_T, get_p, get_Ts, get_ps,
    iterate_inlet, iterate_combustor,
    multi_stage_compressor, multi_stage_turbine, calc_nozzle,
)
import ISA_module as ISA


# ─────────────────────────────────────────────────────────────────────────────
# Default engine: "Orenda" (generic single-spool turbojet from the series)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_ENG_PARAM: dict = {
    "A1": 0.30,           # m²  inlet capture area at station 1
    "A2": 0.32,           # m²  inlet exit area (compressor face, station 2)
    "comp_n_stages": 10,  #     number of compressor stages
    "turb_n_stages": 2,   #     number of turbine stages
    "A8": 0.27,           # m²  nozzle throat area
}

DEFAULT_ENG_PERF: dict = {
    "eta_i":     0.98,    # inlet adiabatic efficiency
    "CPR":       6.1,     # overall compressor pressure ratio
    "eta_c":     0.80,    # compressor isentropic stage efficiency
    "eta_b":     0.90,    # combustor efficiency
    "dp_over_p": 0.06,    # combustor total-pressure loss fraction (6%)
    "max_f":     0.25,    # max fuel — fraction of stoichiometric (swirl limit)
    "min_f":     0.125,   # min fuel — fraction of stoichiometric (stability)
    "V_nominal": 45.0,    # m/s  nominal combustor flow velocity
    "T_max":     1200.0,  # K    maximum turbine inlet temperature (TIT limit)
    "eta_t":     0.80,    # turbine isentropic stage efficiency
    "mech_loss": 0.99,    # mechanical efficiency (turbine → compressor shaft)
    "eta_noz":   0.80,    # nozzle adiabatic efficiency
}


# ─────────────────────────────────────────────────────────────────────────────
# Core function
# ─────────────────────────────────────────────────────────────────────────────

def calc_thrust(
    eng_param: dict,
    eng_perf: dict,
    throttle_pos: float = 1.0,
    alt: float = 0.0,
    M_i: float = 0.0,
    mdot_guess: float = 20.0,
) -> dict:
    """
    Calculate steady-state turbojet performance.

    Parameters
    ----------
    eng_param     : dict of physical/geometric engine parameters (see DEFAULT_ENG_PARAM)
    eng_perf      : dict of performance/design parameters     (see DEFAULT_ENG_PERF)
    throttle_pos  : throttle lever from 0.5 (idle) to 1.0 (max)
    alt           : pressure altitude [ft]
    M_i           : indicated (flight) Mach number
    mdot_guess    : initial mass-flow guess [kg/s]

    Returns
    -------
    dict with keys:
        T            [kN]             net thrust
        mdot_fuel    [kg/s]           fuel flow
        TSFC         [kg/(kN·h)]      thrust-specific fuel consumption
        SAR          [nm/kg]          specific air range
        mdot_air     [kg/s]           engine air mass flow
        T_max_limited  [bool]         True if TIT limiter was active
        stations     dict             T and P at each station
    """

    # ── Ambient and flight conditions ───────────────────────────────────────
    V_i   = ISA.M2Vt(M_i, alt) * ISA.kt2ms   # true airspeed [m/s]
    p_amb = ISA.p(alt)                         # static ambient pressure [Pa]
    T_amb = ISA.T(alt)                         # static ambient temperature [K]

    # ── Station initialisation ──────────────────────────────────────────────
    # Stations: "a"=ambient, 1=inlet entry, 2=compressor face,
    #           3=after compressor, 4=after combustor, 5=after turbine, 8=nozzle exit
    st      = ["a", 1, 2, 3, 4, 5, 8]
    gas:    dict[str | int, ct.Solution] = {}
    M:      dict[str | int, float] = {}

    for station in st:
        gas[station] = ct.Solution(REACTION_MECHANISM, PHASE_NAME)
        gas[station].X  = COMP_AIR
        gas[station].TP = T_amb, p_amb
        M[station]      = M_i

    # ── Mass-flow convergence loop ───────────────────────────────────────────
    converged   = False
    tol         = 0.1     # kg/s
    mdot_iter   = 0
    max_mdot_iter = 10
    conv_error  = False
    current_mdot = mdot_guess

    # Combustor state holders (set inside loop, used for TSFC after loop)
    mixt_frac = 0.0
    phi = 0.0
    T_max_limited = False

    # Pre-declare variables to avoid UnboundLocalError on loop failure
    mdot_noz = 0.0
    F = 0.0
    choked = False

    while not converged and mdot_iter <= max_mdot_iter and not conv_error:

        # ── Station a → 1 (free-stream to inlet entry, isentropic) ─────────
        M_calc, conv = iterate_inlet(
            current_mdot, eng_param["A1"],
            gas[st[0]], 1.0, M[st[0]], gas[st[1]]
        )
        if conv:
            M[st[1]] = M_calc
        else:
            conv_error = True
            continue   # skip remaining stations — inlet state is invalid

        # ── Station 1 → 2 (inlet with losses) ──────────────────────────────
        M_calc, conv = iterate_inlet(
            current_mdot, eng_param["A2"],
            gas[st[1]], eng_perf["eta_i"], M[st[1]], gas[st[2]]
        )
        if conv:
            M[st[2]] = M_calc
            M[st[3]] = M_calc
        else:
            conv_error = True
            continue   # skip remaining stations

        # ── Station 2 → 3 (multi-stage compressor) ─────────────────────────
        _, conv, compressor_work = multi_stage_compressor(
            gas[st[2]], eng_param["comp_n_stages"],
            eng_perf["CPR"], eng_perf["eta_c"],
            M[st[2]], gas[st[3]]
        )
        if not conv:
            conv_error = True
            continue   # skip combustor/turbine/nozzle with bad compressor state

        # ── Station 3 → 4 (combustor with TIT limiter) ─────────────────────
        _TIT_FLOOR = 0.05  # minimum internal throttle scalar (allows idle / de-throttling)
        phi = (
            (eng_perf["max_f"] - eng_perf["min_f"])
            * throttle_pos
            + eng_perf["min_f"]
        )
        gas[st[4]].set_equivalence_ratio(
            phi=phi, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole"
        )
        mixt_frac = gas[st[4]].mixture_fraction(
            fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mass"
        )

        M_calc, conv = iterate_combustor(
            gas[st[3]], eng_perf["V_nominal"],
            M[st[3]], eng_perf["dp_over_p"], gas[st[4]]
        )
        if conv:
            M[st[4]] = M_calc

        # Combust at constant H and P
        gas[st[4]].equilibrate("HP")

        if gas[st[4]].T > eng_perf["T_max"]:
            T_max_limited = True
            lo, hi = _TIT_FLOOR, 1.0
            for _bis in range(25):  # 25 iterations → precision ~1.5e-8 on [0.5, 1.0]
                mid = 0.5 * (lo + hi)
                phi_bis = (
                    (eng_perf["max_f"] - eng_perf["min_f"])
                    * throttle_pos
                    * mid
                    + eng_perf["min_f"]
                )
                gas[st[4]].set_equivalence_ratio(
                    phi=phi_bis, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole"
                )
                iterate_combustor(
                    gas[st[3]], eng_perf["V_nominal"],
                    M[st[3]], eng_perf["dp_over_p"], gas[st[4]]
                )
                gas[st[4]].equilibrate("HP")
                if gas[st[4]].T > eng_perf["T_max"]:
                    hi = mid
                else:
                    lo = mid
                if abs(gas[st[4]].T - eng_perf["T_max"]) < 0.5:
                    break

            # Settle on the highest compliant scalar (lo is always the last T ≤ T_max)
            phi = (
                (eng_perf["max_f"] - eng_perf["min_f"])
                * throttle_pos
                * lo
                + eng_perf["min_f"]
            )
            gas[st[4]].set_equivalence_ratio(
                phi=phi, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole"
            )
            mixt_frac = gas[st[4]].mixture_fraction(
                fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mass"
            )
            M_calc, conv = iterate_combustor(
                gas[st[3]], eng_perf["V_nominal"],
                M[st[3]], eng_perf["dp_over_p"], gas[st[4]]
            )
            if conv:
                M[st[4]] = M_calc
            gas[st[4]].equilibrate("HP")

        # Propagate burned-gas composition to downstream stations
        for i in st[5:]:
            gas[i].TPX = gas[st[4]].T, gas[st[4]].P, gas[st[4]].X

        # ── Station 4 → 5 (multi-stage turbine) ────────────────────────────
        M[st[5]] = M[st[4]]
        # Bug T1-A fix: FAR = Z/(1-Z), not Z. Using Z directly understated fuel flow by ~3-5%.
        _far_i    = mixt_frac / (1.0 - mixt_frac) if mixt_frac < 1.0 else 0.0
        mdot_fuel = (_far_i / eng_perf["eta_b"]) * current_mdot
        mdot_turb = current_mdot + mdot_fuel
        w_t_spec = (compressor_work * current_mdot) / (mdot_turb * eng_perf["mech_loss"])
        try:
            _, _ = multi_stage_turbine(
                gas[st[4]], w_t_spec,
                eng_param["turb_n_stages"], eng_perf["eta_t"],
                1.0, M[st[4]], M[st[5]], gas[st[5]]
            )
        except ValueError:
            conv_error = True
            break

        # ── Station 5 → 8 (nozzle) ─────────────────────────────────────────
        choked, mdot_noz, M[st[6]], F = calc_nozzle(
            gas[st[5]], M[st[5]], eng_perf["eta_noz"],
            p_amb, eng_param["A8"], V_i, gas[st[6]]
        )

        # ── Mass-flow convergence check ─────────────────────────────────────
        if abs(mdot_noz - current_mdot) < tol:
            converged = True
        else:
            mdot_iter   += 1
            current_mdot = 0.5 * current_mdot + 0.5 * mdot_noz

    # ── Post-loop performance metrics ───────────────────────────────────────
    # Bug T1-A fix: FAR = Z/(1-Z), not Z.
    _far      = mixt_frac / (1.0 - mixt_frac) if mixt_frac < 1.0 else 0.0
    mdot_fuel = (_far / eng_perf["eta_b"]) * mdot_noz
    TSFC      = (mdot_fuel / mdot_noz) / F if (F > 0 and mdot_noz > 0) else None
    SAR       = (V_i / mdot_fuel) if mdot_fuel > 0 else None

    # ── Station summary ─────────────────────────────────────────────────────
    station_labels = {
        "a": "Ambient",
        1:   "Inlet entry",
        2:   "Compressor face",
        3:   "After compressor",
        4:   "After combustor",
        5:   "After turbine",
        8:   "Nozzle exit",
    }
    stations = {}
    for s in st:
        T0_k = float(gas[s].T)
        P0_pa = float(gas[s].P)
        m_s = float(M[s])
        gamma_s = float(gas[s].cp / gas[s].cv) if gas[s].cv > 0 else 1.4
        mw_s = float(gas[s].mean_molecular_weight)
        r_spec = ct.gas_constant / mw_s if mw_s > 0 else 287.05
        
        mach_factor = 1.0 + 0.5 * (gamma_s - 1.0) * m_s**2
        T_static = T0_k / mach_factor
        P_static = P0_pa / (mach_factor ** (gamma_s / (gamma_s - 1.0)))
        V_flow = m_s * math.sqrt(max(1.0, gamma_s * r_spec * T_static))

        stations[str(s)] = {
            "label":        station_labels[s],
            "T_K":          round(T0_k, 1),
            "T_total_K":    round(T0_k, 1),
            "T_static_K":   round(T_static, 1),
            "Ts_K":         round(T_static, 1),
            "P_Pa":         round(P0_pa, 0),
            "P_atm":        round(P0_pa / ct.one_atm, 3),
            "P_total_kPa":  round(P0_pa / 1000.0, 2),
            "P_static_kPa": round(P_static / 1000.0, 2),
            "p_kPa":        round(P0_pa / 1000.0, 2),
            "ps_kPa":       round(P_static / 1000.0, 2),
            "Mach":         round(m_s, 4),
            "V_ms":         round(V_flow, 1),
            "s_JkgK":       round(gas[s].entropy_mass, 1),
            "h_Jkg":        round(gas[s].enthalpy_mass, 1),
        }

    # ── Emissions & Combustion Metrics (Station 4) ──────────────────────────
    FAR = mixt_frac / (1.0 - mixt_frac) if mixt_frac < 1.0 else 0.0

    if phi < 0.99:
        burn_state = "Lean Burn"
    elif phi > 1.01:
        burn_state = "Rich Burn"
    else:
        burn_state = "Balanced (Stoichiometric)"

    emissions_EI = {"NOx": 0.0, "CO": 0.0, "CO2": 0.0}
    if FAR > 0:
        gas4 = gas[4]
        MW_mix = gas4.mean_molecular_weight
        sp_dict = gas4.mole_fraction_dict()
        
        def calc_ei(species_name, mw_species):
            X_spec = sp_dict.get(species_name.lower(), sp_dict.get(species_name.upper(), 0.0))
            return (X_spec * mw_species) / MW_mix * ((1.0 + FAR) / FAR) * 1000.0
            
        ei_no  = calc_ei("NO", 30.01)
        ei_no2 = calc_ei("NO2", 46.01)
        emissions_EI["NOx"] = round(ei_no + ei_no2, 2)
        emissions_EI["CO"]  = round(calc_ei("CO", 28.01), 2)
        emissions_EI["CO2"] = round(calc_ei("CO2", 44.01), 2)

    stations["4"]["combustion_metrics"] = {
        "fuel_air_ratio": round(FAR, 4),
        "equivalence_ratio": round(phi, 3),
        "burn_state": burn_state,
        "emissions_EI": emissions_EI,
    }

    thrust_kN = F * mdot_noz / 1000.0
    F_gross_kN = (F + V_i) * mdot_noz / 1000.0
    F_ram_kN = V_i * mdot_noz / 1000.0
    sp_thrust = (thrust_kN * 1000.0) / max(0.01, mdot_noz)

    V8 = stations["8"]["V_ms"]
    Q_HV = 43.1e6  # Lower heating value of aviation kerosene [J/kg]
    P_fuel = mdot_fuel * Q_HV
    P_jet_kinetic = 0.5 * mdot_noz * max(0.0, V8**2 - V_i**2)
    P_thrust_prop = (thrust_kN * 1000.0) * V_i

    eta_th = min(1.0, max(0.0, P_jet_kinetic / max(1.0, P_fuel))) if P_fuel > 0 else 0.0
    eta_p = min(1.0, max(0.0, (2.0 * V_i) / (V8 + V_i))) if (V8 + V_i) > 0 and V_i > 0 else (1.0 if V_i == 0 and thrust_kN > 0 else 0.0)
    eta_o = eta_th * eta_p

    return {
        "T":                  round(thrust_kN, 3),
        "thrust_net_kN":      round(thrust_kN, 3),
        "thrust_gross_kN":    round(F_gross_kN, 3),
        "ram_drag_kN":        round(F_ram_kN, 3),
        "thrust_lbf":         round(thrust_kN * 224.809, 1),
        "specific_thrust":    round(sp_thrust, 1),
        "mdot_fuel":          round(mdot_fuel, 5),
        "TSFC":               round(TSFC * 3600.0 * 1000.0, 2) if TSFC is not None else None,   # kg/(kN·h)
        "TSFC_lbm":           round(TSFC * 3600.0 * 1000.0 * 0.0353, 3) if TSFC is not None else None, # lbm/(lbf·h)
        "SAR":                round(SAR * ISA.ms2kt / 3600.0, 5) if SAR is not None else None, # nm/kg
        "mdot_air":           round(mdot_noz, 2),
        "eta_th":             round(eta_th, 4),
        "eta_prop":           round(eta_p, 4),
        "eta_overall":        round(eta_o, 4),
        "choked":             bool(choked),
        "T_max_limited":      T_max_limited,
        "converged":          converged,
        "alt_ft":             alt,
        "Mach":               M_i,
        "throttle_pos":       throttle_pos,
        "stations":           stations,
    }
