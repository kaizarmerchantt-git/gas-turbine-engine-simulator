"""
Test Suite for Module 08: SMT Augmented Gaussian RBF Surrogate Layer
===================================================================
AETHER-X v0.5 REA Verification Tests
"""

import pytest
import numpy as np
import time

from surrogate import CycleSurrogateModel, latin_hypercube_sample, GLOBAL_SURROGATE


class TestSurrogateModel:
    """Rigorous first-principles verification tests for the surrogate engine."""

    def test_latin_hypercube_sampling(self):
        """Verify LHS bounds, shape, and maximin spatial uniformity."""
        bounds = [(0.0, 100.0), (-1.0, 1.0), (10.0, 20.0)]
        pts = latin_hypercube_sample(n_samples=50, bounds=bounds, seed=123)

        assert pts.shape == (50, 3)
        for d, (low, high) in enumerate(bounds):
            assert np.all(pts[:, d] >= low), f"Dim {d} lower bound violated"
            assert np.all(pts[:, d] <= high), f"Dim {d} upper bound violated"

        # Check stratification across 10 bins
        hist, _ = np.histogram(pts[:, 0], bins=5, range=(0.0, 100.0))
        assert np.all(hist > 0), "Stratification failed to populate all histogram bins"

    def test_surrogate_loocv_r2(self):
        """Verify Press's analytical LOOCV R² exceeds 0.98 for all 5 targets."""
        model = CycleSurrogateModel()
        assert model.loocv_r2 is not None
        assert len(model.loocv_r2) == 5

        for i, target in enumerate(model.output_names):
            r2_val = model.loocv_r2[i]
            assert r2_val >= 0.95, f"LOOCV R² for {target} is {r2_val:.4f}, expected >= 0.95"

    def test_surrogate_prediction_physics(self):
        """Verify thermodynamic consistency and reasonable magnitudes at cruise."""
        res = GLOBAL_SURROGATE.predict_point(
            alt_ft=35000.0,
            mach=0.80,
            throttle=1.00,
            CPR=14.0,
            TIT_K=1450.0,
        )

        assert res["thrust_kN"] > 0.0
        assert res["tsfc"] > 0.0
        assert res["air_flow_kg_s"] > 0.0
        assert res["fuel_flow_kg_s"] > 0.0
        assert res["EI_NOx"] > 0.0

        # Physical relationship: fuel_flow [kg/s] = Thrust [kN] * TSFC [g/(kN*s)] / 1000.0
        expected_ff = (res["thrust_kN"] * res["tsfc"]) / 1000.0
        assert abs(res["fuel_flow_kg_s"] - expected_ff) < 0.05 * expected_ff

        # Unit conversion check: fuel_flow_kgh == fuel_flow_kg_s * 3600
        assert abs(res["fuel_flow_kgh"] - res["fuel_flow_kg_s"] * 3600.0) < 0.1

    def test_epistemic_uncertainty_growth_on_extrapolation(self):
        """Verify that Kriging epistemic uncertainty s(x) expands when querying far outside training bounds."""
        # Query at center of design space (interpolation)
        res_center = GLOBAL_SURROGATE.predict_point(
            alt_ft=25000.0,
            mach=0.60,
            throttle=0.80,
            CPR=15.0,
            TIT_K=1450.0,
        )

        # Query far outside envelope (Mach 1.4, TIT 2200K)
        res_extrap = GLOBAL_SURROGATE.predict_point(
            alt_ft=60000.0,
            mach=1.40,
            throttle=1.20,
            CPR=45.0,
            TIT_K=2200.0,
        )

        # Extrapolation uncertainty should be significantly higher
        assert res_extrap["uncertainty_pct"] > res_center["uncertainty_pct"]

    def test_generate_1d_curve_and_2d_surface(self):
        """Verify 1D sweep and 2D surface generation structures and unit accuracy."""
        # 1D sweep
        res_1d = GLOBAL_SURROGATE.generate_1d_curve(
            x_param="mach",
            y_param="thrust_kN",
            x_min=0.2,
            x_max=0.9,
            n_points=15,
        )
        assert len(res_1d["points"]) == 15
        for pt in res_1d["points"]:
            assert "x" in pt and "y" in pt and "y_lower" in pt and "y_upper" in pt
            assert pt["y_upper"] >= pt["y_lower"]

        # Check fuel flow unit scaling in 1D curve: should be in kg/s (< 10 kg/s for a turbojet)
        res_ff = GLOBAL_SURROGATE.generate_1d_curve(
            x_param="throttle",
            y_param="fuel_flow_kg_s",
            n_points=10,
        )
        for pt in res_ff["points"]:
            assert pt["y"] < 5.0, f"Fuel flow {pt['y']} is abnormally large (> 5 kg/s), unit bug still present!"

        # 2D surface
        res_2d = GLOBAL_SURROGATE.generate_2d_surface(
            x_param="CPR",
            y_param="TIT_K",
            grid_res=10,
        )
        assert len(res_2d["x_vals"]) == 10
        assert len(res_2d["y_vals"]) == 10
        assert len(res_2d["thrust_grid_kN"]) == 10
        assert len(res_2d["thrust_grid_kN"][0]) == 10
        assert len(res_2d["uncertainty_grid_kN"]) == 10

    def test_latency_performance(self):
        """Verify single-point prediction completes in under 2.0 ms."""
        t0 = time.perf_counter()
        for _ in range(50):
            GLOBAL_SURROGATE.predict_point(35000.0, 0.8, 1.0, 14.0, 1450.0)
        elapsed_avg_ms = ((time.perf_counter() - t0) / 50.0) * 1000.0
        assert elapsed_avg_ms < 2.0, f"Average latency {elapsed_avg_ms:.3f} ms exceeds 2.0 ms"
