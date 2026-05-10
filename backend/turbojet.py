"""
turbojet.py
Full port of the calc_thrust() function from episd_10_limit_T.ipynb
(flight-test-engineering/Gas-Turbine-Propulsion).

All engine parameters are passed in as dictionaries — exactly matching
the notebook's eng_param / eng_perf interface — so the defaults shown
in the notebook are preserved.
"""

from __future__ import annotations
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
    T_max_limited = False

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

        # ── Station 1 → 2 (inlet with losses) ──────────────────────────────
        M_calc, conv = iterate_inlet(
            current_mdot, eng_param["A2"],
            gas[st[1]], eng_perf["eta_i"], M[st[1]], gas[st[2]]
        )
        if conv:
            for i in range(st.index(2), len(st)):
                M[st[i]] = M_calc
        else:
            conv_error = True

        # ── Station 2 → 3 (multi-stage compressor) ─────────────────────────
        _, conv, compressor_work = multi_stage_compressor(
            gas[st[2]], eng_param["comp_n_stages"],
            eng_perf["CPR"], eng_perf["eta_c"],
            M[st[2]], gas[st[3]]
        )
        if not conv:
            conv_error = True

        # ── Station 3 → 4 (combustor with TIT limiter) ─────────────────────
        T_loop       = True
        T_throttle   = 1.0
        T_throttle_limit = 0.5

        while T_loop:
            phi = (
                (eng_perf["max_f"] - eng_perf["min_f"])
                * throttle_pos
                * T_throttle
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
                T_throttle -= 0.001
                T_max_limited = True
            elif T_throttle < T_throttle_limit:
                T_loop = False
            else:
                T_loop = False

        # Propagate burned-gas composition to downstream stations
        for i in st[5:]:
            gas[i].TPX = gas[st[4]].T, gas[st[4]].P, gas[st[4]].X

        # ── Station 4 → 5 (multi-stage turbine) ────────────────────────────
        _, _ = multi_stage_turbine(
            gas[st[4]], compressor_work,
            eng_param["turb_n_stages"], eng_perf["eta_t"],
            eng_perf["mech_loss"], M[st[4]], M[st[5]], gas[st[5]]
        )

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
            current_mdot = mdot_noz

    # ── Post-loop performance metrics ───────────────────────────────────────
    mdot_fuel = (mixt_frac / eng_perf["eta_b"]) * mdot_noz
    TSFC      = (mdot_fuel / mdot_noz) / F if F > 0 else float("nan")
    SAR       = V_i / mdot_fuel if mdot_fuel > 0 else float("nan")

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
    stations = {
        str(s): {
            "label":   station_labels[s],
            "T_K":     round(gas[s].T, 1),
            "P_Pa":    round(gas[s].P, 0),
            "P_atm":   round(gas[s].P / ct.one_atm, 3),
            "Mach":    round(M[s], 4),
            "s_JkgK":  round(gas[s].entropy_mass, 1),     # specific entropy [J/(kg·K)] for T-s diagram
            "h_Jkg":   round(gas[s].enthalpy_mass, 1),    # specific enthalpy [J/kg]
        }
        for s in st
    }

    thrust_kN = F * mdot_noz / 1000.0

    return {
        "T":              round(thrust_kN, 3),
        "mdot_fuel":      round(mdot_fuel, 5),
        "TSFC":           round(TSFC * 3600.0 * 1000.0, 2),   # kg/(kN·h)
        "SAR":            round(SAR * ISA.ms2kt / 3600.0, 5), # nm/kg
        "mdot_air":       round(mdot_noz, 2),
        "choked":         bool(choked),
        "T_max_limited":  T_max_limited,
        "converged":      converged,
        "alt_ft":         alt,
        "Mach":           M_i,
        "throttle_pos":   throttle_pos,   # BUG-1 fix: was "throttle", sweep xKey expects "throttle_pos"
        "stations":       stations,
    }
