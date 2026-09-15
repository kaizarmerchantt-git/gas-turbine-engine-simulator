"""
off_design.py
Component Performance Maps and Off-Design Matching Solver for Gas Turbine Engines.

Implements:
- Scalable axial compressor performance map parameterized by relative corrected speed N_rel
  and auxiliary coordinate beta in [0, 1].
- Surge boundary definition and dynamic Surge Margin (%SM) calculation.
- Turbine swallowing capacity and power matching.
- Pure-Python robust 1D root finder (Brent / Illinois hybrid) without scipy dependency.
- Off-design operating line solver across shaft speeds, altitudes, and Mach numbers.
"""

from __future__ import annotations

import numpy as np
import cantera as ct
from typing import Dict, Any, Tuple, List, Optional

import ISA_module as ISA
from engine_helper import (
    REACTION_MECHANISM, PHASE_NAME, COMP_AIR, COMP_FUEL,
    get_gamma, get_R, get_T, get_p, get_Ts, get_ps,
    iterate_inlet, iterate_combustor,
)


def brent_root(f, a: float, b: float, tol: float = 1e-5, max_iter: int = 50) -> float:
    """
    Pure-Python Brent root finder on interval [a, b].
    Does not require external scipy dependency.
    """
    fa = f(a)
    fb = f(b)
    if fa * fb > 0:
        # Scan for sign change
        grid = np.linspace(a, b, 30)
        fg = [f(x) for x in grid]
        sc = np.where(np.diff(np.sign(fg)))[0]
        if len(sc) > 0:
            a, b = float(grid[sc[0]]), float(grid[sc[0] + 1])
            fa, fb = float(fg[sc[0]]), float(fg[sc[0] + 1])
        else:
            return float(grid[np.argmin(np.abs(fg))])

    if abs(fa) < abs(fb):
        a, b = b, a
        fa, fb = fb, fa

    c, fc, mflag, d = a, fa, True, 0.0

    for _ in range(max_iter):
        if abs(fb) < tol or abs(b - a) < tol:
            return float(b)

        if fa != fc and fb != fc:
            s = (a * fb * fc) / ((fa - fb) * (fa - fc)) + \
                (b * fa * fc) / ((fb - fa) * (fb - fc)) + \
                (c * fa * fb) / ((fc - fa) * (fc - fb))
        else:
            s = b - fb * (b - a) / (fb - fa)

        cond1 = not ((3 * a + b) / 4 <= s <= b or b <= s <= (3 * a + b) / 4)
        cond2 = mflag and abs(s - b) >= abs(b - c) / 2
        cond3 = not mflag and abs(s - b) >= abs(c - d) / 2
        cond4 = mflag and abs(b - c) < tol
        cond5 = not mflag and abs(c - d) < tol

        if cond1 or cond2 or cond3 or cond4 or cond5:
            s = (a + b) / 2
            mflag = True
        else:
            mflag = False

        fs = f(s)
        d, c, fc = c, b, fb

        if fa * fs < 0:
            b, fb = s, fs
        else:
            a, fa = s, fs

        if abs(fa) < abs(fb):
            a, b = b, a
            fa, fb = fb, fa

    return float(b)


class CompressorMap:
    """
    Standardized, scalable axial compressor performance map.
    Parameterized by relative corrected speed N_rel in [0.60, 1.05]
    and auxiliary coordinate beta in [0, 1].

    - beta = 1.0: Surge boundary (minimum mass flow, maximum pressure ratio)
    - beta = 0.5: Nominal design operating line
    - beta = 0.0: Choke boundary (maximum mass flow, minimum pressure ratio)
    """

    SPEEDS = np.array([0.60, 0.70, 0.80, 0.90, 1.00, 1.05], dtype=float)

    # Reference characteristic map parameters per speed line:
    # (m_choke_rel, m_surge_rel, pi_choke_rel, pi_surge_rel, eta_peak_rel, beta_peak)
    MAP_DATA = {
        0.60: (0.48, 0.39, 0.25, 0.35, 0.84, 0.50),
        0.70: (0.63, 0.53, 0.35, 0.50, 0.91, 0.50),
        0.80: (0.78, 0.67, 0.48, 0.68, 0.96, 0.50),
        0.90: (0.91, 0.80, 0.63, 0.88, 0.99, 0.50),
        1.00: (1.06, 0.94, 0.82, 1.18, 1.00, 0.50),
        1.05: (1.07, 0.96, 0.93, 1.25, 0.98, 0.50),
    }

    def __init__(self, cpr_des: float = 8.0, eta_c_des: float = 0.85, mdot_corr_des: float = 20.0):
        self.cpr_des = float(cpr_des)
        self.eta_c_des = float(eta_c_des)
        self.mdot_corr_des = float(mdot_corr_des)

    def _interp_speed(self, N_rel: float) -> np.ndarray:
        N_clamped = float(np.clip(N_rel, self.SPEEDS[0], self.SPEEDS[-1]))
        idx = int(np.searchsorted(self.SPEEDS, N_clamped))
        if idx == 0:
            s0 = s1 = self.SPEEDS[0]
            w1 = 0.0
        elif idx >= len(self.SPEEDS):
            s0 = s1 = self.SPEEDS[-1]
            w1 = 0.0
        else:
            s0 = self.SPEEDS[idx - 1]
            s1 = self.SPEEDS[idx]
            w1 = (N_clamped - s0) / (s1 - s0)

        d0 = np.array(self.MAP_DATA[s0])
        d1 = np.array(self.MAP_DATA[s1])
        return (1.0 - w1) * d0 + w1 * d1

    def evaluate(self, N_rel: float, beta: float) -> Tuple[float, float, float]:
        """
        Evaluate the compressor map at (N_rel, beta).
        Returns:
            mdot_corr [kg/s]: Corrected mass flow
            cpr       [-]:    Compressor pressure ratio
            eta_c     [-]:    Compressor isentropic efficiency
        """
        beta_c = float(np.clip(beta, 0.0, 1.0))
        m_choke, m_surge, pi_choke, pi_surge, eta_peak, beta_peak = self._interp_speed(N_rel)

        # Monotonic mass flow variation from choke to surge
        m_rel = m_choke + beta_c * (m_surge - m_choke)
        mdot_corr = m_rel * self.mdot_corr_des

        # S-curve smooth pressure ratio variation
        shape = 0.5 * (1.0 - np.cos(np.pi * beta_c))
        pi_rel = pi_choke + shape * (pi_surge - pi_choke)
        cpr = 1.0 + pi_rel * (self.cpr_des - 1.0)

        # Efficiency parabolic degradation away from peak efficiency
        eta_rel = eta_peak * (1.0 - 0.25 * ((beta_c - beta_peak) / 0.5) ** 2)
        eta_c = float(np.clip(eta_rel * self.eta_c_des, 0.50, 0.98))

        return float(mdot_corr), float(cpr), float(eta_c)

    def surge_point(self, N_rel: float) -> Tuple[float, float]:
        """Returns (mdot_corr_surge [kg/s], cpr_surge [-]) at relative speed N_rel."""
        mdot_s, cpr_s, _ = self.evaluate(N_rel, beta=1.0)
        return mdot_s, cpr_s

    def choke_point(self, N_rel: float) -> Tuple[float, float]:
        """Returns (mdot_corr_choke [kg/s], cpr_choke [-]) at relative speed N_rel."""
        mdot_c, cpr_c, _ = self.evaluate(N_rel, beta=0.0)
        return mdot_c, cpr_c

    def surge_margin(self, N_rel: float, mdot_corr_op: float, cpr_op: float) -> Tuple[float, str]:
        """
        Computes constant-speed Surge Margin (%SM):
        %SM = [(cpr_surge / mdot_surge) / (cpr_op / mdot_op) - 1] * 100%

        Returns:
            (sm_pct, status)
            where status is 'HEALTHY' (>15%), 'MARGIN_LOW' (0-15%), or 'SURGE_VIOLATION' (<=0%).
        """
        m_surge, cpr_surge = self.surge_point(N_rel)
        if cpr_op <= 1.0 or mdot_corr_op <= 0.0 or m_surge <= 0.0:
            return 0.0, "SURGE_VIOLATION"

        sm = float(((cpr_surge / m_surge) / (cpr_op / mdot_corr_op) - 1.0) * 100.0)
        if sm >= 15.0:
            status = "HEALTHY"
        elif sm > 0.0:
            status = "MARGIN_LOW"
        else:
            status = "SURGE_VIOLATION"
        return round(sm, 2), status

    def get_map_curves(self, n_pts: int = 25) -> Dict[str, Any]:
        """
        Generate coordinates for speed lines and the surge line
        for front-end Chart.js visualization.
        """
        speed_lines = []
        betas = np.linspace(0.0, 1.0, n_pts)

        for s in self.SPEEDS:
            line_pts = []
            for b in betas:
                m_c, cpr, eta = self.evaluate(s, b)
                line_pts.append({"x": round(m_c, 3), "y": round(cpr, 3), "eta": round(eta, 4)})
            speed_lines.append({
                "speed_pct": int(round(s * 100)),
                "points": line_pts,
            })

        # Surge boundary
        surge_pts = []
        for s in np.linspace(self.SPEEDS[0], self.SPEEDS[-1], 20):
            ms, cprs = self.surge_point(s)
            surge_pts.append({"x": round(ms, 3), "y": round(cprs, 3)})

        return {
            "speed_lines": speed_lines,
            "surge_line": surge_pts,
            "design_point": {
                "x": round(self.mdot_corr_des, 3),
                "y": round(self.cpr_des, 3),
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# Cycle evaluation and matching solver
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_cycle_state(
    N_rel: float,
    beta: float,
    alt: float,
    mach: float,
    cmap: CompressorMap,
    A8_target: float,
    eta_i: float = 0.98,
    eta_t: float = 0.88,
    mech_loss: float = 0.99,
    eta_b: float = 0.99,
    dp_over_p: float = 0.04,
    T_max: float = 1500.0,
    eta_noz: float = 0.98,
    throttle_pos: float = 1.0,
    gas: Optional[ct.Solution] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Evaluates one candidate thermodynamic cycle state at (N_rel, beta).
    Returns (area_residual, state_dictionary).
    """
    if gas is None:
        gas = ct.Solution(REACTION_MECHANISM, PHASE_NAME)

    p_amb = float(ISA.p(alt))
    T_amb = float(ISA.T(alt))
    V_inf = float(ISA.M2Vt(mach, alt) * ISA.kt2ms)
    gamma_amb = 1.4
    R_air = 287.05
    rho_amb = p_amb / (R_air * T_amb)

    # Inlet state (Station a -> 2)
    T02 = eh_get_T(T_amb, gamma_amb, mach)
    p02 = p_amb * (1.0 + eta_i * ((gamma_amb - 1.0) / 2.0) * mach**2) ** (gamma_amb / (gamma_amb - 1.0))
    theta2 = T02 / 288.15
    delta2 = p02 / 101325.0

    # Compressor state (Station 2 -> 3)
    mdot_corr, cpr, eta_c = cmap.evaluate(N_rel, beta)
    mdot_air = mdot_corr * delta2 / np.sqrt(theta2)

    p03 = p02 * cpr
    T03 = T02 * (1.0 + (1.0 / eta_c) * (cpr ** ((gamma_amb - 1.0) / gamma_amb) - 1.0))

    gas.TPX = T02, p02, COMP_AIR
    s02 = gas.s
    h02 = gas.h

    gas.TPX = T03, p03, COMP_AIR
    s03 = gas.s
    h03 = gas.h
    cp_c = gas.cp
    w_c = cp_c * (T03 - T02)
    W_c_total = mdot_air * w_c

    # Combustor state (Station 3 -> 4)
    p04 = p03 * (1.0 - dp_over_p)

    # Schedule fuel-air ratio with shaft speed & throttle
    phi_base = 0.15 + (N_rel - 0.60) * (0.35 - 0.15) / (1.05 - 0.60)
    phi_cmd = phi_base * throttle_pos

    gas.TPX = T03, p04, COMP_AIR
    gas.set_equivalence_ratio(phi=phi_cmd, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole")
    gas.equilibrate("HP")

    # Binary bisection TIT limiter if T04 > T_max
    tit_limited = False
    if gas.T > T_max:
        tit_limited = True
        lo, hi = 0.05, phi_cmd
        for _ in range(20):
            mid = 0.5 * (lo + hi)
            gas.TPX = T03, p04, COMP_AIR
            gas.set_equivalence_ratio(phi=mid, fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mole")
            gas.equilibrate("HP")
            if gas.T > T_max:
                hi = mid
            else:
                lo = mid
            if abs(gas.T - T_max) < 0.5:
                break

    T04 = gas.T
    s04 = gas.s
    h04 = gas.h
    Z = gas.mixture_fraction(fuel=COMP_FUEL, oxidizer=COMP_AIR, basis="mass")
    far = Z / (1.0 - Z) if Z < 1.0 else 0.0
    mdot_fuel = (far / eta_b) * mdot_air
    mdot_turb = mdot_air + mdot_fuel

    # Emissions indices (g/kg fuel)
    try:
        mw_mix = gas.mean_molecular_weight
        X_NO  = gas["NO"].X[0]  if "NO"  in gas.species_names else 0.0
        X_NO2 = gas["NO2"].X[0] if "NO2" in gas.species_names else 0.0
        X_CO  = gas["CO"].X[0]  if "CO"  in gas.species_names else 0.0
        X_CO2 = gas["CO2"].X[0] if "CO2" in gas.species_names else 0.0

        mw_NO  = gas.molecular_weights[gas.species_index("NO")]  if "NO"  in gas.species_names else 30.01
        mw_NO2 = gas.molecular_weights[gas.species_index("NO2")] if "NO2" in gas.species_names else 46.01
        mw_CO  = gas.molecular_weights[gas.species_index("CO")]  if "CO"  in gas.species_names else 28.01
        mw_CO2 = gas.molecular_weights[gas.species_index("CO2")] if "CO2" in gas.species_names else 44.01

        ei_nox = ((X_NO * mw_NO + X_NO2 * mw_NO2) / (far * mw_mix)) * 1000.0 if far > 0 else 0.0
        ei_co  = ((X_CO * mw_CO) / (far * mw_mix)) * 1000.0 if far > 0 else 0.0
        ei_co2 = ((X_CO2 * mw_CO2) / (far * mw_mix)) * 1000.0 if far > 0 else 0.0
    except Exception:
        ei_nox, ei_co, ei_co2 = 0.0, 0.0, 0.0

    # Turbine work balance (Station 4 -> 5)
    W_t_req = W_c_total / mech_loss
    w_t_spec = W_t_req / mdot_turb
    cp_t = gas.cp
    gamma_t = get_gamma(gas)
    R_t = get_R(gas)

    h_avail = cp_t * T04 * eta_t
    if w_t_spec >= h_avail or T04 <= 10.0:
        return 999.0, {"valid": False}

    T05 = T04 - w_t_spec / cp_t
    if T05 <= 1.0:
        return 999.0, {"valid": False}

    p05 = p04 * (1.0 - w_t_spec / (eta_t * cp_t * T04)) ** (gamma_t / (gamma_t - 1.0))

    gas.TPX = T05, p05, gas.X
    s05 = gas.s
    h05 = gas.h

    # Exhaust Nozzle (Station 5 -> 8)
    if p05 <= 100.0:
        return 999.0, {"valid": False}
    pc_ratio = 1.0 / (1.0 - (1.0 / eta_noz) * ((gamma_t - 1.0) / (gamma_t + 1.0))) ** (gamma_t / (gamma_t - 1.0))
    if p05 / p_amb >= pc_ratio:
        choked = True
        T8 = T05 * (2.0 / (gamma_t + 1.0))
        p8 = p05 / pc_ratio
        V8 = np.sqrt(gamma_t * R_t * T8)
        rho8 = p8 / (R_t * T8)
        A8_calc = mdot_turb / (rho8 * V8)
        M8 = 1.0
    else:
        choked = False
        p8 = p_amb
        exp_term = (gamma_t - 1.0) / gamma_t
        T8 = T05 * (1.0 - eta_noz * (1.0 - (p_amb / p05) ** exp_term))
        T8 = max(T8, 10.0)
        V8 = np.sqrt(max(2.0 * cp_t * (T05 - T8), 0.0))
        rho8 = p_amb / (R_t * T8) if (R_t * T8) > 0 else 1.0
        A8_calc = mdot_turb / (rho8 * V8) if (rho8 * V8) > 0 else 999.0
        a8 = np.sqrt(gamma_t * R_t * T8)
        M8 = V8 / a8 if a8 > 0 else 0.0

    gas.TPX = T8, p8, gas.X
    s08 = gas.s
    h08 = gas.h

    res = A8_calc - A8_target

    details = {
        "valid": True,
        "beta": beta,
        "mdot_corr": mdot_corr,
        "mdot_air": mdot_air,
        "mdot_fuel": mdot_fuel,
        "mdot_turb": mdot_turb,
        "cpr": cpr,
        "eta_c": eta_c,
        "W_c_total": W_c_total,
        "W_t_req": W_t_req,
        "w_t_spec": w_t_spec,
        "T02": T02, "p02": p02, "s02": s02, "h02": h02,
        "T03": T03, "p03": p03, "s03": s03, "h03": h03,
        "T04": T04, "p04": p04, "s04": s04, "h04": h04,
        "T05": T05, "p05": p05, "s05": s05, "h05": h05,
        "T8": T8, "p8": p8, "V8": V8, "M8": M8, "s08": s08, "h08": h08,
        "choked": choked,
        "A8_calc": A8_calc,
        "V_inf": V_inf,
        "p_amb": p_amb,
        "T_amb": T_amb,
        "tit_limited": tit_limited,
        "emissions": {
            "EI_NOx": round(ei_nox, 2),
            "EI_CO":  round(ei_co, 2),
            "EI_CO2": round(ei_co2, 1),
        }
    }
    return res, details


def eh_get_T(Ts: float, gamma: float, M: float) -> float:
    return Ts * (1.0 + ((gamma - 1.0) / 2.0) * M**2)


def solve_off_design(
    N_rel: float = 1.0,
    alt: float = 35000.0,
    mach: float = 0.8,
    cpr_des: float = 8.0,
    eta_c_des: float = 0.85,
    mdot_corr_des: float = 20.0,
    A8: Optional[float] = None,
    eta_i: float = 0.98,
    eta_t: float = 0.88,
    mech_loss: float = 0.99,
    eta_b: float = 0.99,
    dp_over_p: float = 0.04,
    T_max: float = 1500.0,
    eta_noz: float = 0.98,
    throttle_pos: float = 1.0,
    gas: Optional[ct.Solution] = None,
) -> Dict[str, Any]:
    """
    Solves for the matched off-design operating condition of the gas turbine.
    If A8 is None or <= 0, A8 is calibrated to the design point (N_rel=1.0, beta=0.50).
    """
    if gas is None:
        gas = ct.Solution(REACTION_MECHANISM, PHASE_NAME)

    cmap = CompressorMap(cpr_des=cpr_des, eta_c_des=eta_c_des, mdot_corr_des=mdot_corr_des)

    # Determine fixed nozzle area A8 if not provided
    if A8 is None or A8 <= 0.0:
        _, det_des = evaluate_cycle_state(
            1.0, 0.50, alt, mach, cmap, 0.0,
            eta_i, eta_t, mech_loss, eta_b, dp_over_p, T_max, eta_noz, 1.0, gas
        )
        A8_target = det_des["A8_calc"]
    else:
        A8_target = float(A8)

    def f_res(b: float) -> float:
        res, det = evaluate_cycle_state(
            N_rel, b, alt, mach, cmap, A8_target,
            eta_i, eta_t, mech_loss, eta_b, dp_over_p, T_max, eta_noz, throttle_pos, gas
        )
        if not det.get("valid", False):
            return 999.0
        return res

    beta_match = brent_root(f_res, 0.02, 0.98, tol=1e-4)
    _, det = evaluate_cycle_state(
        N_rel, beta_match, alt, mach, cmap, A8_target,
        eta_i, eta_t, mech_loss, eta_b, dp_over_p, T_max, eta_noz, throttle_pos, gas
    )

    if not det.get("valid", False):
        return {
            "N_rel":            round(N_rel, 3),
            "N_pct":            round(N_rel * 100.0, 1),
            "beta":             round(beta_match, 4),
            "CPR":              0.0,
            "eta_c":            0.0,
            "mdot_air":         0.0,
            "mdot_corr":        0.0,
            "mdot_fuel":        0.0,
            "mdot_fuel_kgh":    0.0,
            "Thrust_kN":        0.0,
            "TSFC":             None,
            "SAR":              None,
            "Surge_Margin_pct": 0.0,
            "Surge_Status":     "SURGE_VIOLATION",
            "T04":              0.0,
            "T05":              0.0,
            "A8_target":        round(A8_target, 4),
            "A8_calc":          0.0,
            "A8_match_err_pct": 999.0,
            "choked":           False,
            "tit_limited":      False,
            "emissions":        {"EI_NOx": 0.0, "EI_CO": 0.0, "EI_CO2": 0.0},
            "stations":         {},
            "converged":        False,
            "error":            "Thermodynamic cycle limits exceeded (enthalpy exhaustion or stall)",
        }

    # Thrust and Performance
    F_net = det["mdot_turb"] * det["V8"] - det["mdot_air"] * det["V_inf"] + A8_target * (det["p8"] - det["p_amb"])
    F_net_kN = F_net / 1000.0
    tsfc = (det["mdot_fuel"] / F_net_kN * 3600.0) if F_net_kN > 0 else None
    sar = (det["V_inf"] / det["mdot_fuel"] * ISA.ms2kt / 3600.0) if det["mdot_fuel"] > 0 else None

    # Surge margin
    sm_pct, sm_status = cmap.surge_margin(N_rel, det["mdot_corr"], det["cpr"])
    a8_err_pct = abs(det["A8_calc"] - A8_target) / A8_target * 100.0

    stations = {
        "a": {"label": "Ambient",          "T_K": round(det["T_amb"], 1), "P_atm": round(det["p_amb"] / 101325.0, 3), "s_JkgK": round(det["s02"], 1), "M": round(mach, 2)},
        "2": {"label": "Compressor Inlet", "T_K": round(det["T02"], 1),   "P_atm": round(det["p02"] / 101325.0, 3), "s_JkgK": round(det["s02"], 1), "M": 0.5},
        "3": {"label": "Compressor Exit",  "T_K": round(det["T03"], 1),   "P_atm": round(det["p03"] / 101325.0, 3), "s_JkgK": round(det["s03"], 1), "M": 0.3},
        "4": {"label": "Combustor Exit",   "T_K": round(det["T04"], 1),   "P_atm": round(det["p04"] / 101325.0, 3), "s_JkgK": round(det["s04"], 1), "M": 0.3},
        "5": {"label": "Turbine Exit",     "T_K": round(det["T05"], 1),   "P_atm": round(det["p05"] / 101325.0, 3), "s_JkgK": round(det["s05"], 1), "M": 0.4},
        "8": {"label": "Nozzle Exit",      "T_K": round(det["T8"], 1),    "P_atm": round(det["p8"] / 101325.0, 3),  "s_JkgK": round(det["s08"], 1), "M": round(det["M8"], 2)},
    }

    return {
        "N_rel":            round(N_rel, 3),
        "N_pct":            round(N_rel * 100.0, 1),
        "beta":             round(beta_match, 4),
        "CPR":              round(det["cpr"], 3),
        "eta_c":            round(det["eta_c"], 3),
        "mdot_air":         round(det["mdot_air"], 2),
        "mdot_corr":        round(det["mdot_corr"], 2),
        "mdot_fuel":        round(det["mdot_fuel"], 5),
        "mdot_fuel_kgh":    round(det["mdot_fuel"] * 3600.0, 1),
        "Thrust_kN":        round(F_net_kN, 3),
        "TSFC":             round(tsfc, 2) if tsfc is not None else None,
        "SAR":              round(sar, 4) if sar is not None else None,
        "Surge_Margin_pct": sm_pct,
        "Surge_Status":     sm_status,
        "T04":              round(det["T04"], 1),
        "T05":              round(det["T05"], 1),
        "A8_target":        round(A8_target, 4),
        "A8_calc":          round(det["A8_calc"], 4),
        "A8_match_err_pct": round(a8_err_pct, 3),
        "choked":           bool(det["choked"]),
        "tit_limited":      bool(det["tit_limited"]),
        "emissions":        det["emissions"],
        "stations":         stations,
        "converged":        bool(a8_err_pct < 1.0),
    }


def run_off_design_sweep(
    sweep_param: str = "speed",
    n_steps: int = 15,
    speed_start: float = 0.65,
    speed_end: float = 1.05,
    fixed_speed: float = 1.00,
    alt_start: float = 0.0,
    alt_end: float = 40000.0,
    fixed_alt: float = 35000.0,
    mach_start: float = 0.0,
    mach_end: float = 0.85,
    fixed_mach: float = 0.80,
    cpr_des: float = 8.0,
    eta_c_des: float = 0.85,
    mdot_corr_des: float = 20.0,
    A8: Optional[float] = None,
    eta_i: float = 0.98,
    eta_t: float = 0.88,
    mech_loss: float = 0.99,
    eta_b: float = 0.99,
    dp_over_p: float = 0.04,
    T_max: float = 1500.0,
    eta_noz: float = 0.98,
    throttle_pos: float = 1.0,
) -> Dict[str, Any]:
    """
    Executes an off-design parameter sweep and constructs the operating line trajectory.
    """
    gas = ct.Solution(REACTION_MECHANISM, PHASE_NAME)
    cmap = CompressorMap(cpr_des=cpr_des, eta_c_des=eta_c_des, mdot_corr_des=mdot_corr_des)

    if A8 is None or A8 <= 0.0:
        _, det_des = evaluate_cycle_state(
            1.0, 0.50, fixed_alt, fixed_mach, cmap, 0.0,
            eta_i, eta_t, mech_loss, eta_b, dp_over_p, T_max, eta_noz, 1.0, gas
        )
        A8_target = det_des["A8_calc"]
    else:
        A8_target = float(A8)

    if sweep_param == "speed":
        sweep_vals = np.linspace(speed_start, speed_end, n_steps).tolist()
    elif sweep_param == "altitude":
        sweep_vals = np.linspace(alt_start, alt_end, n_steps).tolist()
    elif sweep_param == "mach":
        sweep_vals = np.linspace(mach_start, mach_end, n_steps).tolist()
    else:
        raise ValueError(f"Unsupported sweep_param: {sweep_param}")

    points = []
    operating_line = []

    for val in sweep_vals:
        n_curr = val if sweep_param == "speed" else fixed_speed
        alt_curr = val if sweep_param == "altitude" else fixed_alt
        mach_curr = val if sweep_param == "mach" else fixed_mach

        try:
            pt = solve_off_design(
                N_rel=n_curr, alt=alt_curr, mach=mach_curr,
                cpr_des=cpr_des, eta_c_des=eta_c_des, mdot_corr_des=mdot_corr_des,
                A8=A8_target, eta_i=eta_i, eta_t=eta_t, mech_loss=mech_loss,
                eta_b=eta_b, dp_over_p=dp_over_p, T_max=T_max, eta_noz=eta_noz,
                throttle_pos=throttle_pos, gas=gas,
            )
            pt["sweep_val"] = round(val, 3)
            points.append(pt)
            operating_line.append({
                "x": pt["mdot_corr"],
                "y": pt["CPR"],
                "N_pct": pt["N_pct"],
                "SM_pct": pt["Surge_Margin_pct"],
            })
        except Exception as e:
            points.append({
                "sweep_val": round(val, 3),
                "error": str(e)[:200],
            })

    map_curves = cmap.get_map_curves()

    return {
        "sweep_param": sweep_param,
        "points": points,
        "operating_line": operating_line,
        "map_curves": map_curves,
        "A8_target": round(A8_target, 4),
    }
