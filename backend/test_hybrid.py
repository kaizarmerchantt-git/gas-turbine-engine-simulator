"""
Automated Pytest Suite for Extension 5 — Hybrid Electric Propulsion Integration
================================================================================
Validates mathematical and physical consistency of:
- Parallel hybrid mechanical shaft power split and electrical loss chains
- Series hybrid DC bus power balance, turbogenerator sizing, and battery charging
- Turboelectric direct transmission loss chain (zero battery)
- Battery State-of-Charge (SoC) integration, C-rate, and 20% health reserve cutoff
- 6-phase hybrid flight mission fuel savings & CO2 reduction vs conventional baseline
- Parametric trade study sweeps across hybrid ratio, battery specific energy, and distance
- All FastAPI hybrid electric REST API endpoints
"""

import os
import sys
import math
import pytest
from fastapi.testclient import TestClient

# Ensure backend modules can be imported
sys.path.insert(0, os.path.dirname(__file__))

import main
import hybrid


@pytest.fixture
def client():
    return TestClient(main.app)


def test_parallel_hybrid_power_split_and_efficiency_losses():
    """Validates parallel hybrid mechanical coupling and electrical conversion losses."""
    req_power = 2400.0  # kW
    hp_ratio = 0.30     # 30% electric assist
    batt_mass = 1500.0  # kg
    soc = 0.90

    res = hybrid.evaluate_single_hybrid_point(
        architecture="parallel",
        shaft_power_req_kW=req_power,
        hybrid_power_ratio_HP=hp_ratio,
        battery_mass_kg=batt_mass,
        battery_soc=soc,
    )

    # Mechanical power split check
    expected_motor_mech = req_power * hp_ratio
    expected_gt_mech = req_power * (1.0 - hp_ratio)
    assert math.isclose(res["electric_motor_power_kW"], expected_motor_mech, rel_tol=1e-3)
    assert math.isclose(res["gas_turbine_power_kW"], expected_gt_mech, rel_tol=1e-3)

    # Battery power draw must be higher than mechanical power due to electrical losses
    # P_batt = P_motor / (eta_motor * eta_inv * eta_dist * eta_batt_disch)
    assert res["battery_power_kW"] > expected_motor_mech
    eta_chain = hybrid.DEFAULT_POWERTRAIN["eta_motor"] * hybrid.DEFAULT_POWERTRAIN["eta_inverter"] * hybrid.DEFAULT_POWERTRAIN["eta_dist"] * hybrid.DEFAULT_POWERTRAIN["eta_batt_disch"]
    assert math.isclose(res["battery_power_kW"], expected_motor_mech / eta_chain, rel_tol=1e-3)

    # Battery C-rate check
    capacity_kWh = (batt_mass * hybrid.DEFAULT_POWERTRAIN["specific_energy_Wh_kg"]) / 1000.0
    expected_c_rate = res["battery_power_kW"] / capacity_kWh
    assert math.isclose(res["c_rate"], expected_c_rate, rel_tol=1e-3)

    # Fuel savings should be positive relative to 100% conventional
    assert res["fuel_savings_pct"] > 0.0


def test_series_hybrid_dc_bus_balance_and_charging():
    """Validates series hybrid DC bus power balance and battery charging when turbogenerator exceeds demand."""
    batt_mass = 1200.0
    soc = 0.80

    # Case 1: High demand - battery assists turbogenerator
    res_high = hybrid.evaluate_single_hybrid_point(
        architecture="series",
        shaft_power_req_kW=3000.0,
        turbogen_rated_kW=2000.0,
        battery_mass_kg=batt_mass,
        battery_soc=soc,
    )
    # Propulsor is 100% electric
    assert math.isclose(res_high["electric_motor_power_kW"], 3000.0, rel_tol=1e-3)
    assert res_high["gas_turbine_power_kW"] == 2000.0
    # Battery discharges to cover remainder
    assert res_high["battery_power_kW"] > 0.0

    # Case 2: Low demand - excess turbogenerator power recharges battery
    res_low = hybrid.evaluate_single_hybrid_point(
        architecture="series",
        shaft_power_req_kW=800.0,
        turbogen_rated_kW=1600.0,
        battery_mass_kg=batt_mass,
        battery_soc=soc,
    )
    # Battery power must be negative (charging)
    assert res_low["battery_power_kW"] < 0.0
    assert res_low["dSoC_dt_percent_per_min"] > 0.0  # SoC is increasing


def test_turboelectric_transmission_loss_chain():
    """Validates turboelectric direct generator-to-motor transmission with zero battery."""
    req_power = 2500.0  # kW

    res = hybrid.evaluate_single_hybrid_point(
        architecture="turboelectric",
        shaft_power_req_kW=req_power,
    )

    # Battery mass and power must be zero
    assert res["battery_mass_kg"] == 0.0
    assert res["battery_power_kW"] == 0.0
    assert res["battery_capacity_kWh"] == 0.0

    # Gas turbine power must be higher than shaft power to cover generator, inverter, and motor losses
    assert res["gas_turbine_power_kW"] > req_power
    pt = hybrid.DEFAULT_POWERTRAIN
    expected_chain = pt["eta_motor"] * pt["eta_inverter"] * pt["eta_dist"] * pt["eta_generator"] * pt["eta_inverter"]
    assert math.isclose(res["gas_turbine_power_kW"], req_power / expected_chain, rel_tol=1e-3)


def test_battery_soc_cutoff_protection():
    """Validates that low battery (SoC <= 0.20) disables electric boost to protect battery life."""
    req_power = 2000.0
    hp_requested = 0.30

    # Test with depleted battery (SoC = 0.18)
    res_depleted = hybrid.evaluate_single_hybrid_point(
        architecture="parallel",
        shaft_power_req_kW=req_power,
        hybrid_power_ratio_HP=hp_requested,
        battery_soc=0.18,
    )

    # Effective hybrid ratio must be forced to 0.0
    assert res_depleted["hybrid_power_ratio_HP"] == 0.0
    assert res_depleted["electric_motor_power_kW"] == 0.0
    assert res_depleted["battery_power_kW"] == 0.0
    assert math.isclose(res_depleted["gas_turbine_power_kW"], req_power, rel_tol=1e-3)


def test_hybrid_mission_simulation_and_fuel_savings():
    """Validates 6-phase hybrid flight mission simulation and fuel savings comparison vs baseline."""
    res = hybrid.run_hybrid_mission_simulation(
        architecture="parallel",
        cruise_alt_m=9144.0,
        cruise_mach=0.72,
        cruise_dist_km=800.0,
        payload_kg=6000.0,
        battery_mass_kg=1500.0,
        specific_energy_Wh_kg=320.0,
        takeoff_hybrid_ratio=0.35,
        climb_hybrid_ratio=0.20,
        cruise_hybrid_ratio=0.05,
    )

    # Check structure
    assert "summary" in res
    assert "phases" in res
    assert len(res["phases"]) == 6

    # Verify standard phase names
    expected_phases = ["Taxi-out", "Takeoff", "Climb", "Cruise", "Descent", "Loiter (Reserves)"]
    actual_phases = [p["phase"] for p in res["phases"]]
    assert actual_phases == expected_phases

    # Fuel saved should be positive for this regional mission
    summ = res["summary"]
    assert summ["fuel_saved_kg"] > 0.0
    assert summ["fuel_saved_percent"] > 0.0
    assert summ["co2_reduction_kg"] > 0.0
    assert math.isclose(summ["co2_reduction_kg"], summ["fuel_saved_kg"] * 3.16, rel_tol=1e-2)

    # Final battery SoC should remain above safety limit
    assert summ["final_battery_soc"] >= 0.20

    # Verify mass conservation: weight decreases across each phase
    prev_wt = res["phases"][0]["aircraft_weight_kg"]
    for ph in res["phases"][1:]:
        assert ph["aircraft_weight_kg"] < prev_wt
        prev_wt = ph["aircraft_weight_kg"]


def test_hybrid_trade_study_sweeps():
    """Validates parametric trade study sweeps across hybrid ratio and battery technology."""
    # 1. Hybrid ratio sweep
    sw_hp = hybrid.run_hybrid_trade_study(
        study_type="hybrid_ratio",
        architecture="parallel",
        n_points=6,
    )
    assert len(sw_hp["points"]) == 6
    assert sw_hp["points"][0]["x"] == 0.0

    # 2. Specific energy sweep
    sw_sp = hybrid.run_hybrid_trade_study(
        study_type="specific_energy",
        architecture="parallel",
        n_points=5,
    )
    assert len(sw_sp["points"]) == 5
    assert sw_sp["points"][0]["x"] == 180.0
    assert sw_sp["points"][-1]["x"] == 550.0

    # 3. Distance sweep
    sw_d = hybrid.run_hybrid_trade_study(
        study_type="distance",
        architecture="parallel",
        n_points=5,
    )
    assert len(sw_d["points"]) == 5
    assert sw_d["points"][0]["x"] == 300.0


def test_all_fastapi_hybrid_endpoints(client):
    """Validates all 4 FastAPI REST endpoints for hybrid electric simulation."""
    # 1. Defaults endpoint
    r_def = client.get("/api/hybrid/defaults")
    assert r_def.status_code == 200
    d = r_def.json()
    assert d["architecture"] == "parallel"
    assert "powertrain" in d

    # 2. Single-point evaluation endpoint
    r_sng = client.post("/api/hybrid/single", json={
        "architecture": "parallel",
        "shaft_power_req_kW": 2500.0,
        "hybrid_power_ratio_HP": 0.25,
        "battery_mass_kg": 1200.0,
        "battery_soc": 0.85,
    })
    assert r_sng.status_code == 200
    s = r_sng.json()
    assert s["architecture"] == "parallel"
    assert s["gas_turbine_power_kW"] == 1875.0
    assert s["electric_motor_power_kW"] == 625.0
    assert s["battery_power_kW"] > 625.0

    # 3. Mission simulation endpoint
    r_ms = client.post("/api/hybrid/mission", json={
        "architecture": "parallel",
        "cruise_dist_km": 750.0,
        "payload_kg": 6000.0,
        "battery_mass_kg": 1600.0,
        "specific_energy_Wh_kg": 320.0,
        "takeoff_hybrid_ratio": 0.30,
    })
    assert r_ms.status_code == 200
    m = r_ms.json()
    assert "summary" in m
    assert m["summary"]["fuel_saved_percent"] > 0.0

    # 4. Sweep trade study endpoint
    r_sw = client.post("/api/hybrid/sweep", json={
        "study_type": "hybrid_ratio",
        "architecture": "parallel",
        "n_points": 5,
        "cruise_dist_km": 750.0,
    })
    assert r_sw.status_code == 200
    sw = r_sw.json()
    assert len(sw["points"]) == 5
