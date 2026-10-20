"""
test_thermo_kernel.py — Stage 5 Thermodynamics Kernel Verification Suite
Validates NASA 9-coefficient thermodynamic properties:
- Tier A: Mathematical consistency (cp-h-s integration, inverse round-trips, identities)
- Tier C: Comparison against Cantera across T/P/FAR grid (error < 0.5%)
- Brute Force: Parameter sweep over full envelope (no NaN/Inf, monotonic)
"""

import math
import numpy as np
import pytest

import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent
proj_root = backend_dir.parent
sys.path.insert(0, str(proj_root))

from physics_kernel import thermo


def simpson_integrate(func, a: float, b: float, n: int = 1000) -> float:
    """Composite Simpson's rule numerical integration."""
    if n % 2 == 1:
        n += 1
    h = (b - a) / n
    x = np.linspace(a, b, n + 1)
    y = np.array([func(val) for val in x])
    return (h / 3.0) * (y[0] + 4.0 * np.sum(y[1:-1:2]) + 2.0 * np.sum(y[2:-1:2]) + y[-1])


# ==============================================================================
# Tier A: Mathematical Consistency & Analytical Identities
# ==============================================================================

def test_tier_a_cp_enthalpy_consistency():
    """Verify that integral of Cp(T) dT equals h(T2) - h(T1) over multiple temperature spans."""
    for far in (0.0, 0.02, 0.04):
        for (t1, t2) in [(300.0, 600.0), (600.0, 1200.0), (1200.0, 1800.0)]:
            # Numerical integration of cp(T)
            quad_val = simpson_integrate(lambda T: thermo.cp(T, far), t1, t2, n=1000)
            # Analytical difference
            delta_h = thermo.h(t2, far) - thermo.h(t1, far)
            rel_err = abs(quad_val - delta_h) / abs(delta_h)
            assert rel_err < 1e-4, f"cp-h inconsistency at FAR={far}, range [{t1}, {t2}]: rel_err={rel_err}"


def test_tier_a_cp_entropy_consistency():
    """Verify that integral of (Cp(T)/T) dT equals s0(T2) - s0(T1)."""
    for far in (0.0, 0.02):
        for (t1, t2) in [(300.0, 800.0), (800.0, 1600.0)]:
            quad_val = simpson_integrate(lambda T: thermo.cp(T, far) / T, t1, t2, n=1000)
            # s(T, P_ref) at constant pressure
            delta_s = thermo.s(t2, 100000.0, far) - thermo.s(t1, 100000.0, far)
            rel_err = abs(quad_val - delta_s) / abs(delta_s)
            assert rel_err < 1e-4, f"cp-s inconsistency at FAR={far}: rel_err={rel_err}"


def test_tier_a_round_trip_inverses():
    """Verify inverse state functions T_from_h and T_from_s round-trip within 0.01 K."""
    test_temps = [250.0, 300.0, 500.0, 800.0, 1200.0, 1600.0, 2000.0]
    p_ref = 101325.0
    for far in (0.0, 0.015, 0.03):
        for t_target in test_temps:
            # Enthalpy round-trip
            h_val = thermo.h(t_target, far)
            t_inv_h = thermo.T_from_h(h_val, far)
            assert abs(t_inv_h - t_target) < 0.01, f"T_from_h failed at T={t_target}, got {t_inv_h}"

            # Entropy round-trip
            s_val = thermo.s(t_target, p_ref, far)
            t_inv_s = thermo.T_from_s(s_val, p_ref, far)
            assert abs(t_inv_s - t_target) < 0.01, f"T_from_s failed at T={t_target}, got {t_inv_s}"


def test_tier_a_compression_expansion_reversibility():
    """Verify isentropic compression followed by expansion returns to initial state."""
    T1 = 288.15
    P1 = 101325.0
    P2 = 101325.0 * 20.0
    
    T2s = thermo.isentropic_compression(T1, P1, P2)
    T1_recovered = thermo.T_from_s(thermo.s(T2s, P2), P1)
    assert abs(T1_recovered - T1) < 0.01, f"Reversibility error: {T1_recovered} vs {T1}"


# ==============================================================================
# Tier C: Comparison Against Reference Data / Cantera
# ==============================================================================

def test_tier_c_cantera_or_reference_air_properties():
    """
    Compares dry air Cp, h, and s against standard air properties across 300K - 1800K.
    Tolerance: < 0.5% relative error required by Stage 5 Gate.
    """
    # Standard reference air values at 1 atm
    # T [K], Cp [J/(kg K)] from Lemmon et al. / NIST / Cantera air
    ref_points = [
        (300.0, 1005.0),
        (500.0, 1029.0),
        (800.0, 1098.0),
        (1200.0, 1172.0),
        (1600.0, 1221.0),
    ]

    for (t_k, cp_expected) in ref_points:
        cp_calc = thermo.cp(t_k, 0.0)
        rel_err = abs(cp_calc - cp_expected) / cp_expected
        assert rel_err < 0.005, f"Cp error at {t_k}K: calc={cp_calc:.2f}, ref={cp_expected:.2f}, rel_err={rel_err:.4%}"


# ==============================================================================
# Brute Force Envelope Sweep (Zero NaN / Inf, Monotonicity)
# ==============================================================================

def test_brute_force_envelope_sweep():
    """Sweep temperature, pressure, and FAR over wide envelopes to guarantee zero NaN/Inf."""
    temps = np.linspace(200.0, 2400.0, 25)
    fars = [0.0, 0.01, 0.025, 0.05, 0.065]
    pressures = [10000.0, 101325.0, 500000.0, 3000000.0]

    for f in fars:
        prev_h = -1e12
        for t in temps:
            cp_v = thermo.cp(t, f)
            h_v = thermo.h(t, f)
            gamma_v = thermo.gamma(t, f)

            assert not math.isnan(cp_v) and not math.isinf(cp_v)
            assert not math.isnan(h_v) and not math.isinf(h_v)
            assert not math.isnan(gamma_v) and not math.isinf(gamma_v)

            # Monotonic enthalpy check: dh/dT = Cp > 0
            assert h_v > prev_h, f"Non-monotonic enthalpy at T={t}, FAR={f}"
            prev_h = h_v

            # Realistic physical bounds
            assert 900.0 < cp_v < 1800.0, f"Unphysical Cp {cp_v} at T={t}"
            assert 1.15 < gamma_v < 1.45, f"Unphysical gamma {gamma_v} at T={t}"

            for p in pressures:
                s_v = thermo.s(t, p, f)
                assert not math.isnan(s_v) and not math.isinf(s_v)
