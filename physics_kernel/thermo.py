"""
physics_kernel.thermo: NASA 9-Coefficient Polynomial Thermodynamics Kernel.
Evaluates high-fidelity thermodynamic properties for atmospheric air and
combustion products from first principles.

Reference:
- McBride, Zehe, Sanford, "NASA Glenn Coefficients for Calculating Thermodynamic
  Properties of Individual Species", NASA TP-2002-211556 (2002) & NASA RP-1311 (1996).
- Standard dry air composition: N2 (78.084%), O2 (20.947%), Ar (0.934%), CO2 (0.035%).
- Standard Jet-A aviation kerosene: CH_1.9167, LHV = 43.1 MJ/kg, M_fuel = 170.0 kg/kmol.
"""

import math
from typing import Dict, Tuple, Optional
import numpy as np

# Universal Gas Constant R_u [J / (mol * K)] = [kJ / (kmol * K)]
R_UNIVERSAL = 8.31446261815324  # J / (mol * K)

# NASA 9-coefficient species definitions from NASA TP-2002-211556
# Format per interval: [a0, a1, a2, a3, a4, a5, a6, b1, b2]
SPECIES_DATA = {
    "N2": {
        "molecular_weight": 28.0134,  # g/mol
        "intervals": [
            (200.0, 1000.0, [
                2.210371497e04, -3.818461820e02, 6.082738360e00, -8.530914410e-03,
                1.384646189e-05, -9.625793620e-09, 2.519734237e-12, 7.108460860e02, -1.076003758e01
            ]),
            (1000.0, 6000.0, [
                5.877124262e05, -2.239249073e03, 6.066949220e00, -6.139685500e-04,
                1.491806679e-07, -1.923105485e-11, 1.061954386e-15, 1.283210415e04, -1.586640027e01
            ])
        ]
    },
    "O2": {
        "molecular_weight": 31.9988,  # g/mol
        "intervals": [
            (200.0, 1000.0, [
                -3.425563420e04, 4.847000970e02, 1.119010961e00, 4.293889240e-03,
                -6.836300520e-07, -2.023835041e-09, 1.039040018e-12, -3.391454870e03, 1.849699470e01
            ]),
            (1000.0, 6000.0, [
                -1.037939022e06, 2.344830282e03, 1.819732036e00, 1.267847582e-03,
                -2.188067988e-07, 2.053719572e-11, -8.193467050e-16, -1.689010929e04, 1.738716506e01
            ])
        ]
    },
    "Ar": {
        "molecular_weight": 39.948,  # g/mol
        "intervals": [
            (200.0, 1000.0, [
                0.0, 0.0, 2.500000000e00, 0.0, 0.0, 0.0, 0.0, -7.453750000e02, 4.379674910e00
            ]),
            (1000.0, 6000.0, [
                2.010538475e01, -5.992661070e-02, 2.500069401e00, -3.992141160e-08,
                1.205272140e-11, -1.819015576e-15, 1.078576636e-19, -7.449939610e02, 4.379180110e00
            ])
        ]
    },
    "CO2": {
        "molecular_weight": 44.0095,  # g/mol
        "intervals": [
            (200.0, 1000.0, [
                4.943650540e04, -6.264116010e02, 5.301725240e00, 2.503813816e-03,
                -2.127308728e-07, -7.689988780e-10, 2.849677801e-13, -4.528198460e04, -7.048279440e00
            ]),
            (1000.0, 6000.0, [
                1.176962419e05, -1.788791477e03, 8.291523190e00, -9.228285310e-05,
                4.863676880e-09, -1.891053312e-12, 6.330036590e-16, -3.908350590e04, -2.652669045e01
            ])
        ]
    },
    "H2O": {
        "molecular_weight": 18.01528,  # g/mol
        "intervals": [
            (200.0, 1000.0, [
                -3.947960830e04, 5.755731020e02, 9.317826530e-01, 7.222712860e-03,
                -7.342557370e-06, 4.955043490e-09, -1.336933246e-12, -3.303974310e04, 1.724205775e01
            ]),
            (1000.0, 6000.0, [
                1.034972096e06, -2.412698562e03, 4.646110780e00, 2.291998307e-03,
                -6.836861600e-07, 9.426468930e-11, -4.822380530e-15, -1.384286509e04, -7.978148510e00
            ])
        ]
    }
}

# Ambient atmospheric dry air molar fractions
AIR_MOLAR_FRACTIONS = {
    "N2": 0.78084,
    "O2": 0.20947,
    "Ar": 0.00934,
    "CO2": 0.00035
}

# Default aviation kerosene fuel parameters (DECISIONS.md)
DEFAULT_FUEL_LHV = 43.1e6       # J / kg (43.1 MJ/kg)
DEFAULT_FUEL_H_C_RATIO = 1.9167 # C_n H_{1.9167 n} nominal Jet-A
DEFAULT_FUEL_MW = 170.0         # g / mol


def _eval_nasa9_species(species_name: str, T: float) -> Tuple[float, float, float]:
    """
    Evaluate dimensionless (Cp/R, H/RT, S0/R) for a single species at temperature T [K].
    """
    sp = SPECIES_DATA[species_name]
    intervals = sp["intervals"]
    
    # Select appropriate interval with clamping
    coeffs = None
    for (t_min, t_max, c) in intervals:
        if t_min <= T <= t_max:
            coeffs = c
            break
            
    if coeffs is None:
        if T < intervals[0][0]:
            coeffs = intervals[0][2]
            T = intervals[0][0]
        else:
            coeffs = intervals[-1][2]
            T = intervals[-1][1]

    a0, a1, a2, a3, a4, a5, a6, b1, b2 = coeffs

    # Dimensionless expressions from NASA TP-2002-211556:
    # Cp / R = a0*T^-2 + a1*T^-1 + a2 + a3*T + a4*T^2 + a5*T^3 + a6*T^4
    cp_over_r = (
        a0 * (T**-2) +
        a1 * (T**-1) +
        a2 +
        a3 * T +
        a4 * (T**2) +
        a5 * (T**3) +
        a6 * (T**4)
    )

    # H / RT = -a0*T^-2 + a1*ln(T)/T + a2 + (a3/2)*T + (a4/3)*T^2 + (a5/4)*T^3 + (a6/5)*T^4 + b1/T
    h_over_rt = (
        -a0 * (T**-2) +
        a1 * (math.log(T) / T) +
        a2 +
        (a3 / 2.0) * T +
        (a4 / 3.0) * (T**2) +
        (a5 / 4.0) * (T**3) +
        (a6 / 5.0) * (T**4) +
        b1 / T
    )

    # S0 / R = -(a0/2)*T^-2 - a1*T^-1 + a2*ln(T) + a3*T + (a4/2)*T^2 + (a5/3)*T^3 + (a6/4)*T^4 + b2
    s0_over_r = (
        -(a0 / 2.0) * (T**-2) -
        a1 * (T**-1) +
        a2 * math.log(T) +
        a3 * T +
        (a4 / 2.0) * (T**2) +
        (a5 / 3.0) * (T**3) +
        (a6 / 4.0) * (T**4) +
        b2
    )

    return cp_over_r, h_over_rt, s0_over_r


def get_mixture_composition(far: float, h_c_ratio: float = DEFAULT_FUEL_H_C_RATIO) -> Dict[str, float]:
    """
    Computes product species mole fractions for lean Jet-A / air combustion at Fuel-Air Ratio FAR.
    Returns dict mapping species name -> mole fraction.
    """
    if far <= 1e-7:
        return dict(AIR_MOLAR_FRACTIONS)

    # Reaction stoichiometry per mole of air (0.78084 N2 + 0.20947 O2 + 0.00934 Ar + 0.00035 CO2)
    # Mean molecular weight of dry air [g/mol]:
    mw_air = sum(AIR_MOLAR_FRACTIONS[sp] * SPECIES_DATA[sp]["molecular_weight"] for sp in AIR_MOLAR_FRACTIONS)
    
    # Fuel formula: CH_y where y = h_c_ratio
    # MW of CH_y: 12.011 + y * 1.008
    mw_unit_fuel = 12.011 + h_c_ratio * 1.008
    
    # Moles of fuel unit per mole of air:
    # m_fuel / m_air = far = (n_fuel * mw_unit_fuel) / mw_air
    n_fuel = (far * mw_air) / mw_unit_fuel

    # Stoichiometric O2 needed per mole of CH_y: 1 (for C) + y/4 (for H)
    o2_needed_per_fuel = 1.0 + (h_c_ratio / 4.0)
    o2_consumed = n_fuel * o2_needed_per_fuel
    
    # Lean check: ensure remaining O2 is non-negative
    initial_o2 = AIR_MOLAR_FRACTIONS["O2"]
    remaining_o2 = max(0.0, initial_o2 - o2_consumed)
    
    # Generated products per mole of air:
    gen_co2 = AIR_MOLAR_FRACTIONS["CO2"] + n_fuel
    gen_h2o = n_fuel * (h_c_ratio / 2.0)
    n2 = AIR_MOLAR_FRACTIONS["N2"]
    ar = AIR_MOLAR_FRACTIONS["Ar"]

    total_moles = n2 + ar + remaining_o2 + gen_co2 + gen_h2o
    return {
        "N2": n2 / total_moles,
        "O2": remaining_o2 / total_moles,
        "Ar": ar / total_moles,
        "CO2": gen_co2 / total_moles,
        "H2O": gen_h2o / total_moles
    }


def mixture_properties(T: float, far: float = 0.0) -> Tuple[float, float, float, float, float]:
    """
    Computes mixture specific heat Cp [J/(kg*K)], Enthalpy h [J/kg], standard entropy s0 [J/(kg*K)],
    gas constant R [J/(kg*K)], and specific heat ratio gamma [-].
    """
    comp = get_mixture_composition(far)
    
    # Compute mixture molecular weight M [g/mol]
    mw_mix = sum(comp[sp] * SPECIES_DATA[sp]["molecular_weight"] for sp in comp)  # g / mol
    r_mix = (R_UNIVERSAL / (mw_mix * 1e-3))  # J / (kg * K)

    cp_molar = 0.0
    h_molar = 0.0
    s0_molar = 0.0

    for sp, x_i in comp.items():
        cp_r, h_rt, s0_r = _eval_nasa9_species(sp, T)
        cp_molar += x_i * (cp_r * R_UNIVERSAL)
        h_molar += x_i * (h_rt * R_UNIVERSAL * T)
        s0_molar += x_i * (s0_r * R_UNIVERSAL)

    # Convert molar quantities [J/mol] to mass specific [J/kg]
    mass_factor = 1.0 / (mw_mix * 1e-3)
    cp_mass = cp_molar * mass_factor
    
    # Sensible enthalpy relative to T_ref = 298.15 K
    h_ref_molar = 0.0
    for sp, x_i in comp.items():
        _, h_rt_ref, _ = _eval_nasa9_species(sp, 298.15)
        h_ref_molar += x_i * (h_rt_ref * R_UNIVERSAL * 298.15)

    h_mass = (h_molar - h_ref_molar) * mass_factor
    s0_mass = s0_molar * mass_factor

    gamma = cp_mass / (cp_mass - r_mix)
    return cp_mass, h_mass, s0_mass, r_mix, gamma


# ==============================================================================
# State Functions & Inverses
# ==============================================================================

def cp(T: float, far: float = 0.0) -> float:
    """Specific heat at constant pressure [J/(kg·K)]."""
    return mixture_properties(T, far)[0]


def h(T: float, far: float = 0.0) -> float:
    """Specific enthalpy [J/kg]."""
    return mixture_properties(T, far)[1]


def s(T: float, P_Pa: float, far: float = 0.0, P_ref_Pa: float = 100000.0) -> float:
    """Specific entropy [J/(kg·K)] at temperature T [K] and pressure P [Pa]."""
    _, _, s0_mass, r_mix, _ = mixture_properties(T, far)
    return s0_mass - r_mix * math.log(max(1.0, P_Pa) / P_ref_Pa)


def gamma(T: float, far: float = 0.0) -> float:
    """Specific heat ratio gamma = Cp / Cv [-]."""
    return mixture_properties(T, far)[4]


def gas_constant(far: float = 0.0) -> float:
    """Specific gas constant R [J/(kg·K)]."""
    return mixture_properties(300.0, far)[3]


def T_from_h(h_target: float, far: float = 0.0, tol: float = 1e-4, max_iter: int = 50) -> float:
    """
    Inverse state function: finds temperature T [K] from specific enthalpy h [J/kg]
    using Newton-Raphson with bisection fallback.
    """
    # Initial guess using standard air cp = 1005 J/(kg*K)
    T = max(200.0, min(3500.0, 300.0 + (h_target - h(300.0, far)) / 1050.0))
    t_lo, t_hi = 150.0, 5000.0

    for _ in range(max_iter):
        cp_val, h_val, _, _, _ = mixture_properties(T, far)
        res = h_val - h_target
        if abs(res) < tol:
            return T
        # Update bounds
        if res < 0.0:
            t_lo = max(t_lo, T)
        else:
            t_hi = min(t_hi, T)

        # Newton step
        step = res / cp_val
        t_next = T - step
        if t_lo <= t_next <= t_hi:
            T = t_next
        else:
            # Bisection fallback
            T = 0.5 * (t_lo + t_hi)

    return T


def T_from_s(s_target: float, P_Pa: float, far: float = 0.0, tol: float = 1e-4, max_iter: int = 50) -> float:
    """
    Inverse state function: finds temperature T [K] from entropy s [J/(kg·K)] and pressure P [Pa]
    using Newton-Raphson with bisection fallback.
    """
    T = 300.0
    t_lo, t_hi = 150.0, 5000.0

    for _ in range(max_iter):
        cp_val, _, _, _, _ = mixture_properties(T, far)
        s_val = s(T, P_Pa, far)
        res = s_val - s_target
        if abs(res) < tol:
            return T
        if res < 0.0:
            t_lo = max(t_lo, T)
        else:
            t_hi = min(t_hi, T)

        # Derivative ds/dT = Cp / T
        ds_dt = cp_val / T
        step = res / ds_dt
        t_next = T - step
        if t_lo <= t_next <= t_hi:
            T = t_next
        else:
            T = 0.5 * (t_lo + t_hi)

    return T


# ==============================================================================
# Compression & Expansion Turbomachinery Processes
# ==============================================================================

def isentropic_compression(T1: float, P1_Pa: float, P2_Pa: float, far: float = 0.0) -> float:
    """Computes isentropic exit temperature T2s [K] for pressure ratio P2/P1."""
    s1 = s(T1, P1_Pa, far)
    return T_from_s(s1, P2_Pa, far)


def real_compression(
    T1: float,
    P1_Pa: float,
    P2_Pa: float,
    eta_comp: float,
    far: float = 0.0
) -> Tuple[float, float]:
    """
    Computes real compression exit temperature T2 [K] and specific work delta_h [J/kg]
    given isentropic efficiency eta_comp.
    """
    s1 = s(T1, P1_Pa, far)
    T2s = T_from_s(s1, P2_Pa, far)
    h1 = h(T1, far)
    h2s = h(T2s, far)
    delta_h = (h2s - h1) / eta_comp
    h2 = h1 + delta_h
    T2 = T_from_h(h2, far)
    return T2, delta_h


def real_expansion(
    T1: float,
    P1_Pa: float,
    P2_Pa: float,
    eta_turb: float,
    far: float = 0.0
) -> Tuple[float, float]:
    """
    Computes real expansion exit temperature T2 [K] and specific work delta_h [J/kg]
    given isentropic efficiency eta_turb.
    """
    s1 = s(T1, P1_Pa, far)
    T2s = T_from_s(s1, P2_Pa, far)
    h1 = h(T1, far)
    h2s = h(T2s, far)
    delta_h = eta_turb * (h1 - h2s)
    h2 = h1 - delta_h
    T2 = T_from_h(h2, far)
    return T2, delta_h


# ==============================================================================
# Combustor Energy Balance & ISA Atmosphere
# ==============================================================================

def combustor_far_from_tit(
    T3: float,
    tit_target: float,
    eta_comb: float = 0.99,
    lhv: float = DEFAULT_FUEL_LHV,
    t_fuel: float = 288.15
) -> float:
    """
    Computes Fuel-Air Ratio (FAR) required to achieve target TIT from combustor inlet T3
    via real-gas enthalpy energy conservation:
    h(T3, 0) + FAR * (eta_comb * LHV + h_fuel) = (1 + FAR) * h(tit, FAR)
    """
    h3 = h(T3, 0.0)
    far = 0.02  # initial guess
    for _ in range(25):
        h4 = h(tit_target, far)
        # Residual: FAR * (eta_comb * LHV - h4) + (h3 - h4) = 0
        denom = eta_comb * lhv - h4
        if denom <= 0:
            break
        far_next = (h4 - h3) / denom
        if abs(far_next - far) < 1e-7:
            return max(0.0, far_next)
        far = far_next
    return max(0.0, far)


def isa_atmosphere(altitude_m: float) -> Tuple[float, float, float, float]:
    """
    ISA standard atmosphere model up to 20,000 m.
    Returns: (T_K, P_Pa, rho_kg_m3, speed_of_sound_m_s)
    """
    T0 = 288.15
    P0 = 101325.0
    R_air = 287.05287
    g0 = 9.80665
    L = -0.0065  # K / m

    h_geom = max(-500.0, min(20000.0, altitude_m))

    if h_geom <= 11000.0:
        T = T0 + L * h_geom
        P = P0 * ((T / T0) ** (-g0 / (L * R_air)))
    else:
        T11 = T0 + L * 11000.0
        P11 = P0 * ((T11 / T0) ** (-g0 / (L * R_air)))
        dh = h_geom - 11000.0
        T = T11
        P = P11 * math.exp(-g0 * dh / (R_air * T11))

    rho = P / (R_air * T)
    a = math.sqrt(1.4 * R_air * T)
    return T, P, rho, a
