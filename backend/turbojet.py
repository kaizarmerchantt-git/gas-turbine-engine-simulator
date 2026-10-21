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
    "A1": 0.40,           # m²  inlet capture area at station 1
    "A2": 0.38,           # m²  inlet exit area (compressor face, station 2)
    "comp_n_stages": 10,  #     number of compressor stages
    "turb_n_stages": 2,   #     number of turbine stages
    "A8": 0.28,           # m²  nozzle throat area
}

DEFAULT_ENG_PERF: dict = {
    "eta_i":     0.98,    # inlet adiabatic efficiency
    "CPR":       12.0,    # overall compressor pressure ratio
    "eta_c":     0.80,    # compressor isentropic stage efficiency
    "eta_b":     0.90,    # combustor efficiency
    "dp_over_p": 0.06,    # combustor total-pressure loss fraction (6%)
    "max_f":     0.30,    # max fuel — fraction of stoichiometric (swirl limit)
    "min_f":     0.05,    # min fuel — fraction of stoichiometric (stability)
    "V_nominal": 45.0,    # m/s  nominal combustor flow velocity
    "T_max":     1450.0,  # K    maximum turbine inlet temperature (TIT limit)
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
    throttle_pos  : throttle lever from 0.15 (idle) to 1.0 (max)
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

    # Guard: ensure throttle position does not collapse combustion below ground/flight idle (0.15)
    eff_throttle = max(0.15, min(1.0, float(throttle_pos)))

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
    max_mdot_iter = 35
    conv_error  = False
    # Aerodynamic inlet throat choking limit for compressor face area A2
    _gamma_a = 1.4
    _R_a = 287.05
    _Tt_inlet = T_amb * (1.0 + 0.5 * (_gamma_a - 1.0) * M_i**2)
    _Pt_inlet = p_amb * ((1.0 + 0.5 * (_gamma_a - 1.0) * M_i**2) ** (_gamma_a / (_gamma_a - 1.0))) * eng_perf.get("eta_i", 0.98)
    _q_sonic = math.sqrt(_gamma_a / _R_a) * (2.0 / (_gamma_a + 1.0)) ** ((_gamma_a + 1.0) / (2.0 * (_gamma_a - 1.0)))
    _mdot_inlet_cap = (_Pt_inlet * eng_param.get("A2", 0.38) / math.sqrt(max(10.0, _Tt_inlet))) * _q_sonic * 0.96
    current_mdot = min(mdot_guess, _mdot_inlet_cap)

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
            * eff_throttle
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
                    * eff_throttle
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
                * eff_throttle
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
        if abs(mdot_noz - current_mdot) < tol or (current_mdot >= _mdot_inlet_cap - tol and mdot_noz >= _mdot_inlet_cap):
            converged = True
        else:
            mdot_iter   += 1
            current_mdot = min(_mdot_inlet_cap, 0.5 * current_mdot + 0.5 * mdot_noz)

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

    emissions_EI = {"NOx": 0.0, "CO": 0.0, "CO2": 0.0, "NOx_lefebvre": 0.0}
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

        # Lefebvre semi-empirical kinetic NOx correlation:
        P3_pa = float(gas[3].P)
        T3_k = float(gas[3].T)
        T4_k = float(gas[4].T)
        v_pz = 0.008  # Compact combustor primary zone volume [m^3]
        tau_corr = v_pz / (max(0.5, mdot_noz) * (T4_k / 1000.0))
        ei_nox_lef = 1.0e-6 * (P3_pa ** 0.5) * math.exp(min(25.0, T3_k / 194.0)) * tau_corr
        emissions_EI["NOx_lefebvre"] = round(min(80.0, max(0.5, ei_nox_lef)), 2)
        if emissions_EI["NOx"] == 0.0:
            emissions_EI["NOx"] = emissions_EI["NOx_lefebvre"]

    stations["4"]["combustion_metrics"] = {
        "fuel_air_ratio": round(FAR, 4),
        "equivalence_ratio": round(phi, 3),
        "burn_state": burn_state,
        "emissions_EI": emissions_EI,
        "EI_NOx_kinetic_lefebvre": emissions_EI.get("NOx_lefebvre", 0.0),
        "EI_NOx_equilibrium": emissions_EI.get("NOx", 0.0),
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

    # Standardized TSFC metrics (SYS-01)
    tsfc_g_kns = (mdot_fuel * 1000.0 / thrust_kN) if (thrust_kN > 0 and mdot_fuel > 0) else None
    tsfc_kg_knh = (mdot_fuel * 3600.0 / thrust_kN) if (thrust_kN > 0 and mdot_fuel > 0) else None
    tsfc_lbm_lbfh = (tsfc_g_kns * 0.03530394) if tsfc_g_kns is not None else None

    return {
        "T":                  round(thrust_kN, 3),
        "thrust_net_kN":      round(thrust_kN, 3),
        "thrust_gross_kN":    round(F_gross_kN, 3),
        "ram_drag_kN":        round(F_ram_kN, 3),
        "thrust_lbf":         round(thrust_kN * 224.809, 1),
        "specific_thrust":    round(sp_thrust, 1),
        "mdot_fuel":          round(mdot_fuel, 5),
        "TSFC":               round(tsfc_g_kns, 2) if tsfc_g_kns is not None else None,     # g/(kN·s)
        "TSFC_g_kNs":         round(tsfc_g_kns, 2) if tsfc_g_kns is not None else None,     # g/(kN·s)
        "TSFC_kg_kNh":        round(tsfc_kg_knh, 2) if tsfc_kg_knh is not None else None,    # kg/(kN·h)
        "TSFC_lbm_lbfh":      round(tsfc_lbm_lbfh, 3) if tsfc_lbm_lbfh is not None else None,# lbm/(lbf·h)
        "TSFC_lbm":           round(tsfc_lbm_lbfh, 3) if tsfc_lbm_lbfh is not None else None,
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


def calc_icao_lto_cycle(
    eng_param: dict,
    eng_perf: dict,
    alt: float = 0.0,
    M_i: float = 0.0,
) -> dict:
    """
    Computes ICAO Annex 16 Volume II certified Landing and Take-Off (LTO) emissions cycle:
    Modes:
    1. Take-off:  100% thrust (throttle 1.00), 0.7 min (42 s)
    2. Climb-out:  85% thrust (throttle 0.85), 2.2 min (132 s)
    3. Approach:   30% thrust (throttle 0.35), 4.0 min (240 s)
    4. Taxi/Idle:   7% thrust (throttle 0.15), 26.0 min (1560 s)

    Returns mode-by-mode fuel burned, emissions mass (NOx, CO, CO2),
    and ICAO characteristic emissions metrics (Dp/Foo [g/kN]).
    """
    modes = [
        {"mode": "Takeoff",  "throttle": 1.00, "time_min": 0.7,  "time_s": 42.0},
        {"mode": "Climbout", "throttle": 0.85, "time_min": 2.2,  "time_s": 132.0},
        {"mode": "Approach", "throttle": 0.35, "time_min": 4.0,  "time_s": 240.0},
        {"mode": "Taxi/Idle","throttle": 0.25, "time_min": 26.0, "time_s": 1560.0},
    ]

    mode_results = []
    total_fuel_kg = 0.0
    total_nox_kg = 0.0
    total_nox_lef_kg = 0.0
    total_co_kg = 0.0
    total_co2_kg = 0.0
    f00_takeoff_thrust_kN = 0.0

    for m in modes:
        res = calc_thrust(
            eng_param=eng_param,
            eng_perf=eng_perf,
            throttle_pos=m["throttle"],
            alt=alt,
            M_i=M_i,
        )
        t_s = m["time_s"]
        wf_kgs = res.get("mdot_fuel", 0.0)
        fuel_mode_kg = wf_kgs * t_s
        total_fuel_kg += fuel_mode_kg

        thrust_kn = res.get("thrust_net_kN", 0.0)
        if m["mode"] == "Takeoff":
            f00_takeoff_thrust_kN = thrust_kn

        st4_metrics = res.get("stations", {}).get("4", {}).get("combustion_metrics", {})
        ei_dict = st4_metrics.get("emissions_EI", {})
        ei_nox = ei_dict.get("NOx", 0.0)
        ei_nox_lef = ei_dict.get("NOx_lefebvre", ei_nox)
        ei_co = ei_dict.get("CO", 0.0)
        ei_co2 = ei_dict.get("CO2", 0.0)

        nox_kg = (ei_nox * fuel_mode_kg) / 1000.0
        nox_lef_kg = (ei_nox_lef * fuel_mode_kg) / 1000.0
        co_kg = (ei_co * fuel_mode_kg) / 1000.0
        co2_kg = (ei_co2 * fuel_mode_kg) / 1000.0

        total_nox_kg += nox_kg
        total_nox_lef_kg += nox_lef_kg
        total_co_kg += co_kg
        total_co2_kg += co2_kg

        mode_results.append({
            "mode": m["mode"],
            "throttle": m["throttle"],
            "time_min": m["time_min"],
            "thrust_kN": round(thrust_kn, 2),
            "fuel_flow_kgs": round(wf_kgs, 4),
            "fuel_burned_kg": round(fuel_mode_kg, 2),
            "EI_NOx": round(ei_nox, 2),
            "EI_NOx_lefebvre": round(ei_nox_lef, 2),
            "EI_CO": round(ei_co, 2),
            "EI_CO2": round(ei_co2, 1),
            "mass_NOx_kg": round(nox_kg, 3),
            "mass_NOx_lefebvre_kg": round(nox_lef_kg, 3),
            "mass_CO_kg": round(co_kg, 3),
            "mass_CO2_kg": round(co2_kg, 2),
        })

    # ICAO Characteristic parameter: Dp / Foo [g / kN]
    f00_safe = max(0.1, f00_takeoff_thrust_kN)
    dp_foo_nox = (total_nox_kg * 1000.0) / f00_safe
    dp_foo_nox_lef = (total_nox_lef_kg * 1000.0) / f00_safe
    dp_foo_co = (total_co_kg * 1000.0) / f00_safe

    return {
        "modes": mode_results,
        "summary": {
            "total_lto_time_min": 32.9,
            "total_fuel_burned_kg": round(total_fuel_kg, 2),
            "takeoff_thrust_F00_kN": round(f00_takeoff_thrust_kN, 2),
            "total_NOx_kg": round(total_nox_kg, 3),
            "total_NOx_lefebvre_kg": round(total_nox_lef_kg, 3),
            "total_CO_kg": round(total_co_kg, 3),
            "total_CO2_kg": round(total_co2_kg, 2),
            "Dp_Foo_NOx_g_kN": round(dp_foo_nox, 2),
            "Dp_Foo_NOx_lefebvre_g_kN": round(dp_foo_nox_lef, 2),
            "Dp_Foo_CO_g_kN": round(dp_foo_co, 2),
            "icao_annex_16_compliant": bool(dp_foo_nox_lef < 80.0),
        }
    }
