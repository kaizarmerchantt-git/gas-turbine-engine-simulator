"""
physics_kernel.contracts: Typed Pydantic data contracts for AETHER-X.
Pure physics definitions with physical units, valid bounds, status metadata,
and zero web framework dependencies.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator
import math


class ExecutionStatus(str, Enum):
    OK = "ok"
    INFEASIBLE = "infeasible"
    ERROR = "error"


class SolverMetadata(BaseModel):
    """
    Standard solver execution telemetry required by Stage 4.1.
    Tracks mathematical convergence, residual error, iteration count,
    input clamps (AN-2), and model fidelity.
    """
    status: ExecutionStatus = Field(
        default=ExecutionStatus.OK,
        description="Execution status: ok, infeasible, or error"
    )
    converged: bool = Field(
        default=True,
        description="Whether the numerical solver successfully converged within tolerance"
    )
    residual_norm: float = Field(
        default=0.0,
        ge=0.0,
        description="L2 norm of the governing cycle balance equations at termination"
    )
    iterations: int = Field(
        default=1,
        ge=0,
        description="Number of iterations executed by the nonlinear solver"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Physically meaningful warning messages generated during solution"
    )
    clamped_inputs: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Inputs that were bounded/clamped to valid physical envelopes (AN-2)"
    )
    fidelity_level: str = Field(
        default="cycle_0d_meanline_1d",
        description="Computational fidelity level of the active solver"
    )
    model_version: str = Field(
        default="0.5.0",
        description="Version string of the physics kernel model"
    )


def clamp_input(
    name: str,
    val: float,
    min_v: float,
    max_v: float,
    clamped_dict: Dict[str, Dict[str, float]],
    warnings_list: List[str]
) -> float:
    """
    AN-2 Compliant input clamper.
    Logs any clamped variable to both clamped_dict and warnings_list.
    """
    if val < min_v:
        clamped_dict[name] = {"requested": float(val), "clamped_to": float(min_v)}
        warnings_list.append(f"Input '{name}' ({val}) below physical lower bound ({min_v}); clamped to {min_v}.")
        return float(min_v)
    elif val > max_v:
        clamped_dict[name] = {"requested": float(val), "clamped_to": float(max_v)}
        warnings_list.append(f"Input '{name}' ({val}) above physical upper bound ({max_v}); clamped to {max_v}.")
        return float(max_v)
    return float(val)


# ==============================================================================
# Base Thermodynamic & Station Contracts
# ==============================================================================

class StationPropertyContract(BaseModel):
    """Properties at a gas-path thermodynamic station (SAE AS681 station numbering)."""
    station_number: str = Field(..., description="Station label, e.g. STA 0, STA 1, STA 2, STA 3, STA 4, STA 5, STA 8, STA 9")
    T_total_K: float = Field(..., ge=0.0, description="Total temperature [K]")
    P_total_kPa: float = Field(..., ge=0.0, description="Total pressure [kPa]")
    T_static_K: Optional[float] = Field(None, ge=0.0, description="Static temperature [K]")
    P_static_kPa: Optional[float] = Field(None, ge=0.0, description="Static pressure [kPa]")
    Mach: Optional[float] = Field(None, ge=0.0, description="Local Mach number [-]")
    velocity_m_s: Optional[float] = Field(None, ge=0.0, description="Flow velocity [m/s]")
    mass_flow_kg_s: Optional[float] = Field(None, ge=0.0, description="Mass flow rate [kg/s]")
    enthalpy_kJ_kg: Optional[float] = Field(None, description="Specific enthalpy [kJ/kg]")
    entropy_kJ_kg_K: Optional[float] = Field(None, description="Specific entropy [kJ/(kg·K)]")


# ==============================================================================
# Module 01: Turbojet Contracts
# ==============================================================================

class TurbojetEngineParamContract(BaseModel):
    """Turbojet design cycle parameters."""
    CPR: float = Field(..., ge=1.0, le=45.0, description="Compressor Pressure Ratio [-]")
    TIT: float = Field(..., ge=600.0, le=2200.0, description="Turbine Inlet Temperature [K]")
    mass_flow: float = Field(..., gt=0.0, le=500.0, description="Air mass flow rate at design [kg/s]")
    eta_comp: float = Field(..., gt=0.5, le=1.0, description="Compressor isentropic efficiency [0..1]")
    eta_turb: float = Field(..., gt=0.5, le=1.0, description="Turbine isentropic efficiency [0..1]")
    eta_comb: float = Field(..., gt=0.5, le=1.0, description="Combustor efficiency [0..1]")
    eta_mech: float = Field(..., gt=0.5, le=1.0, description="Mechanical transmission efficiency [0..1]")
    eta_noz: float = Field(..., gt=0.5, le=1.0, description="Nozzle discharge efficiency [0..1]")


class TurbojetEnginePerfContract(BaseModel):
    """Turbojet performance metrics."""
    net_thrust: float = Field(..., description="Net thrust [N]")
    fuel_flow: float = Field(..., ge=0.0, description="Fuel mass flow [kg/s]")
    tsfc: float = Field(..., ge=0.0, description="Thrust Specific Fuel Consumption [kg/(N·s)]")
    thermal_efficiency: float = Field(..., ge=0.0, le=1.0, description="Thermal efficiency [0..1]")


class TurbojetSingleRequestContract(BaseModel):
    """Request contract for single-point turbojet calculation."""
    eng_param: TurbojetEngineParamContract
    eng_perf: TurbojetEnginePerfContract
    throttle_pos: float = Field(1.0, ge=0.0, le=1.5, description="Throttle position (0..1.5 for afterburner)")
    alt: float = Field(0.0, ge=-1000.0, le=85000.0, description="Flight altitude [ft]")
    M_i: float = Field(0.0, ge=0.0, le=3.5, description="Flight Mach number [-]")
    mdot_guess: float = Field(25.0, gt=0.0, description="Initial guess for air mass flow [kg/s]")


class TurbojetSingleResponseContract(BaseModel):
    """Response contract for single-point turbojet calculation."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    net_thrust_kN: float = Field(..., description="Net thrust [kN]")
    fuel_flow_kg_s: float = Field(..., description="Fuel mass flow rate [kg/s]")
    tsfc_g_kN_s: float = Field(..., description="TSFC [g/(kN·s)]")
    thermal_efficiency_pct: float = Field(..., description="Thermal efficiency [%]")
    exhaust_velocity_m_s: float = Field(..., description="Nozzle exit velocity [m/s]")
    stations: List[Dict[str, Any]] = Field(default_factory=list, description="Gas-path station properties")
    brayton_cycle: Optional[List[Dict[str, float]]] = Field(None, description="T-s thermodynamic cycle loop coordinates")


# ==============================================================================
# Module 02: Turbofan Contracts
# ==============================================================================

class PhysicsTurbofanParamContract(BaseModel):
    """Two-spool turbofan cycle parameters."""
    cpr: float = Field(..., ge=1.0, le=60.0, description="Core Compressor Pressure Ratio [-]")
    fan_pr: float = Field(..., ge=1.05, le=4.0, description="Fan Pressure Ratio [-]")
    bpr: float = Field(..., ge=0.0, le=25.0, description="Bypass Ratio [-]")
    tit: float = Field(..., ge=600.0, le=2400.0, description="Turbine Inlet Temperature [K]")
    mass_flow: float = Field(..., gt=0.0, le=2000.0, description="Total mass flow rate [kg/s]")
    eta_fan: float = Field(0.89, gt=0.5, le=1.0, description="Fan isentropic efficiency")
    eta_comp: float = Field(0.87, gt=0.5, le=1.0, description="High-pressure compressor isentropic efficiency")
    eta_turb: float = Field(0.89, gt=0.5, le=1.0, description="Turbine isentropic efficiency")
    eta_comb: float = Field(0.99, gt=0.5, le=1.0, description="Combustor efficiency")
    eta_mech: float = Field(0.99, gt=0.5, le=1.0, description="Mechanical spool efficiency")
    eta_noz: float = Field(0.98, gt=0.5, le=1.0, description="Nozzle discharge efficiency")
    p_amb: float = Field(101325.0, gt=0.0, description="Ambient pressure [Pa]")
    t_amb: float = Field(288.15, gt=0.0, description="Ambient temperature [K]")


class TurbofanSingleRequestContract(BaseModel):
    """Request contract for single-point turbofan calculation."""
    eng_param: PhysicsTurbofanParamContract
    throttle_pos: float = Field(1.0, ge=0.0, le=1.5, description="Throttle position")
    alt: float = Field(0.0, ge=-1000.0, le=85000.0, description="Flight altitude [ft]")
    M_i: float = Field(0.0, ge=0.0, le=2.5, description="Flight Mach number")


class TurbofanSingleResponseContract(BaseModel):
    """Response contract for single-point turbofan calculation."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    net_thrust_kN: float = Field(..., description="Net total thrust [kN]")
    bypass_thrust_kN: float = Field(..., description="Bypass nozzle thrust [kN]")
    core_thrust_kN: float = Field(..., description="Core nozzle thrust [kN]")
    fuel_flow_kg_s: float = Field(..., description="Fuel mass flow [kg/s]")
    tsfc_g_kN_s: float = Field(..., description="Thrust specific fuel consumption [g/(kN·s)]")
    thermal_eff_pct: float = Field(..., description="Thermal efficiency [%]")
    propulsive_eff_pct: float = Field(..., description="Propulsive efficiency [%]")
    overall_eff_pct: float = Field(..., description="Overall efficiency [%]")
    stations: List[Dict[str, Any]] = Field(default_factory=list, description="Station table results")


# ==============================================================================
# Module 03: CF34 Deck Contracts
# ==============================================================================

class CF34SingleRequestContract(BaseModel):
    """Request contract for CF34 engine deck lookups."""
    altitude_ft: float = Field(..., ge=-1000.0, le=50000.0, description="Flight altitude [ft]")
    mach: float = Field(..., ge=0.0, le=0.95, description="Flight Mach number [-]")
    throttle: float = Field(..., ge=0.0, le=1.2, description="Throttle fraction [0..1.2]")


class CF34SingleResponseContract(BaseModel):
    """Response contract for CF34 engine deck lookup."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    thrust_lbf: float = Field(..., description="Net thrust [lbf]")
    thrust_kN: float = Field(..., description="Net thrust [kN]")
    fuel_flow_pph: float = Field(..., description="Fuel flow rate [lbm/hr]")
    fuel_flow_kg_s: float = Field(..., description="Fuel flow rate [kg/s]")
    tsfc_imperial: float = Field(..., description="TSFC [lbm/(lbf·hr)]")
    tsfc_si: float = Field(..., description="TSFC [g/(kN·s)]")
    n1_rpm: Optional[float] = Field(None, description="Fan speed [RPM]")
    n2_rpm: Optional[float] = Field(None, description="Core speed [RPM]")
    itt_C: Optional[float] = Field(None, description="Inter-turbine temperature [°C]")


# ==============================================================================
# Module 04: Off-Design Contracts
# ==============================================================================

class OffDesignSingleRequestContract(BaseModel):
    """Request contract for off-design compressor equilibrium."""
    cpr_design: float = Field(13.5, ge=1.0, le=45.0, description="Design CPR [-]")
    tit_design: float = Field(1400.0, ge=800.0, le=2200.0, description="Design TIT [K]")
    mass_flow_design: float = Field(25.0, gt=0.0, le=500.0, description="Design mass flow [kg/s]")
    speed_fraction: float = Field(1.0, ge=0.5, le=1.15, description="Corrected shaft speed fraction N/N_des")
    throttle: float = Field(1.0, ge=0.1, le=1.2, description="Relative fuel throttle setting")
    alt_ft: float = Field(0.0, ge=-1000.0, le=60000.0, description="Altitude [ft]")
    mach: float = Field(0.0, ge=0.0, le=2.0, description="Mach number [-]")


class OffDesignSingleResponseContract(BaseModel):
    """Response contract for off-design operating point."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    operating_pr: float = Field(..., description="Operating compressor pressure ratio")
    operating_mass_flow_corr: float = Field(..., description="Corrected mass flow [kg/s]")
    operating_eff: float = Field(..., description="Operating compressor adiabatic efficiency")
    surge_margin_pct: float = Field(..., description="Surge margin percentage [%]")
    net_thrust_kN: float = Field(..., description="Net thrust at operating point [kN]")
    tsfc_g_kN_s: float = Field(..., description="TSFC at operating point [g/(kN·s)]")
    is_choked: bool = Field(False, description="Whether turbine or nozzle is choked")
    is_surged: bool = Field(False, description="Whether operating point is in surge")


# ==============================================================================
# Module 05: Mean-Line Turbomachinery Contracts
# ==============================================================================

class MeanlineCompressorStageRequestContract(BaseModel):
    """Request contract for single-stage axial compressor mean-line analysis."""
    U_mid: float = Field(300.0, ge=100.0, le=600.0, description="Mid-span blade speed [m/s]")
    Ca: float = Field(150.0, ge=50.0, le=350.0, description="Axial flow velocity [m/s]")
    r_mean: float = Field(0.35, gt=0.05, le=2.0, description="Mean radius [m]")
    alpha1_deg: float = Field(15.0, ge=-45.0, le=60.0, description="Inlet guide vane swirl angle [deg]")
    beta2_deg: float = Field(20.0, ge=-45.0, le=65.0, description="Rotor exit relative flow angle [deg]")
    eta_stage: float = Field(0.88, ge=0.5, le=0.99, description="Stage isentropic total-to-total efficiency")
    T01: float = Field(288.15, ge=180.0, le=800.0, description="Stage inlet total temperature [K]")
    P01: float = Field(101325.0, ge=1000.0, le=3000000.0, description="Stage inlet total pressure [Pa]")
    aspect_ratio: float = Field(2.0, ge=0.5, le=6.0, description="Blade aspect ratio h/c")
    solidity: float = Field(1.2, ge=0.5, le=3.0, description="Chord-to-spacing solidity ratio c/s")


class MeanlineCompressorStageResponseContract(BaseModel):
    """Response contract for single-stage axial compressor kinematics & performance."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    stage_pressure_ratio: float = Field(..., description="Stage total pressure ratio P03/P01")
    delta_T0_K: float = Field(..., description="Stage total temperature rise [K]")
    euler_work_kJ_kg: float = Field(..., description="Euler specific work [kJ/kg]")
    de_haller_ratio: float = Field(..., description="De Haller diffusion ratio W2/W1")
    lieblein_diffusion_factor: float = Field(..., description="Lieblein diffusion factor DF")
    inlet_rel_mach: float = Field(..., description="Rotor inlet relative Mach number M1_rel")
    triangles: Dict[str, Any] = Field(default_factory=dict, description="Kinematic velocity triangle vectors")


# ==============================================================================
# Module 06: Turboprop Contracts
# ==============================================================================

class TurbopropSingleRequestContract(BaseModel):
    """Request contract for free-turbine turboprop calculation."""
    alt_ft: float = Field(0.0, ge=-1000.0, le=45000.0, description="Altitude [ft]")
    mach: float = Field(0.0, ge=0.0, le=0.85, description="Mach number [-]")
    cpr: float = Field(10.0, ge=2.0, le=35.0, description="Compressor Pressure Ratio [-]")
    tit_k: float = Field(1350.0, ge=800.0, le=2000.0, description="Turbine Inlet Temperature [K]")
    air_flow_kg_s: float = Field(5.0, gt=0.1, le=100.0, description="Engine core mass flow [kg/s]")
    prop_rpm: float = Field(1500.0, ge=500.0, le=3000.0, description="Propeller rotational speed [RPM]")
    prop_dia_m: float = Field(2.8, ge=1.0, le=6.0, description="Propeller diameter [m]")
    throttle: float = Field(1.0, ge=0.1, le=1.2, description="Throttle position")


class TurbopropSingleResponseContract(BaseModel):
    """Response contract for turboprop power & thrust balance."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    shaft_power_kW: float = Field(..., description="Delivered propeller shaft power [kW]")
    residual_thrust_kN: float = Field(..., description="Residual jet nozzle thrust [kN]")
    equivalent_power_kW: float = Field(..., description="Equivalent shaft power ESHP [kW]")
    bsfc_g_kWh: float = Field(..., description="Brake specific fuel consumption [g/(kW·h)]")
    propeller_thrust_kN: float = Field(..., description="Propeller aerodynamic thrust [kN]")
    fuel_flow_kg_s: float = Field(..., description="Fuel mass flow rate [kg/s]")


# ==============================================================================
# Module 07: Mission Contracts
# ==============================================================================

class MissionSimulateRequestContract(BaseModel):
    """Request contract for multi-phase flight mission simulation."""
    mtow_kg: float = Field(45000.0, ge=1000.0, le=500000.0, description="Maximum Takeoff Weight [kg]")
    empty_weight_kg: float = Field(25000.0, ge=500.0, le=300000.0, description="Operating Empty Weight [kg]")
    fuel_capacity_kg: float = Field(12000.0, ge=200.0, le=200000.0, description="Maximum usable fuel weight [kg]")
    cruise_alt_ft: float = Field(35000.0, ge=5000.0, le=55000.0, description="Design cruise altitude [ft]")
    cruise_mach: float = Field(0.78, ge=0.2, le=0.95, description="Design cruise Mach number [-]")
    sfc_cruise: float = Field(16.5, ge=5.0, le=45.0, description="Cruise TSFC [g/(kN·s)]")
    engine_type: str = Field("turbofan", description="Engine propulsion architecture")


class MissionSimulateResponseContract(BaseModel):
    """Response contract for mission profile trajectory."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    total_range_km: float = Field(..., description="Total mission ground range [km]")
    total_range_nm: float = Field(..., description="Total mission ground range [NM]")
    total_fuel_burned_kg: float = Field(..., description="Total mission fuel consumed [kg]")
    flight_time_min: float = Field(..., description="Total block mission time [min]")
    reserve_fuel_kg: float = Field(..., description="Unspent reserve fuel at landing [kg]")
    profile: List[Dict[str, Any]] = Field(default_factory=list, description="Time-step flight profile points")


# ==============================================================================
# Module 08: Surrogate Modeling Contracts
# ==============================================================================

class SurrogatePredictRequestContract(BaseModel):
    """Request contract for Kriging surrogate model evaluation."""
    model_name: str = Field("krg_thrust", description="Identifier of surrogate model")
    cpr: float = Field(..., ge=1.0, le=45.0, description="Compressor Pressure Ratio [-]")
    tit: float = Field(..., ge=600.0, le=2400.0, description="Turbine Inlet Temperature [K]")
    mass_flow: float = Field(..., gt=0.0, le=500.0, description="Air mass flow rate [kg/s]")


class SurrogatePredictResponseContract(BaseModel):
    """Response contract for Kriging evaluation with 95% Confidence Interval."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    predicted_value: float = Field(..., description="Kriging mean prediction")
    uncertainty_variance: float = Field(..., ge=0.0, description="Predicted estimation variance")
    uncertainty_std: float = Field(..., ge=0.0, description="Standard error (+/- 1 sigma)")
    ci_95_lower: float = Field(..., description="95% confidence lower bound")
    ci_95_upper: float = Field(..., description="95% confidence upper bound")


class SurrogateSurfaceRequestContract(BaseModel):
    """Request contract for 2D surrogate response surface generation."""
    x_param: str = Field("cpr", description="X-axis parameter name")
    y_param: str = Field("tit", description="Y-axis parameter name")
    fixed_mass_flow: float = Field(25.0, gt=0.0, description="Fixed third parameter value")
    resolution: int = Field(15, ge=5, le=50, description="Grid resolution per axis")


class SurrogateSurfaceResponseContract(BaseModel):
    """Response contract for 2D surrogate response surface."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    x_values: List[float] = Field(..., description="X-axis grid coordinates")
    y_values: List[float] = Field(..., description="Y-axis grid coordinates")
    z_mean: List[List[float]] = Field(..., description="2D array of predicted mean values")
    z_std: List[List[float]] = Field(..., description="2D array of predictive uncertainties")


# ==============================================================================
# Module 09: Hybrid Electric Contracts
# ==============================================================================

class HybridSingleRequestContract(BaseModel):
    """Request contract for hybrid-electric gas turbine & battery dispatch."""
    throttle: float = Field(1.0, ge=0.0, le=1.2, description="Total demand thrust throttle fraction")
    alt_ft: float = Field(0.0, ge=-1000.0, le=45000.0, description="Flight altitude [ft]")
    mach: float = Field(0.0, ge=0.0, le=0.9, description="Flight Mach number [-]")
    hybrid_split: float = Field(0.2, ge=0.0, le=1.0, description="Electrical power split ratio P_elec / P_total")
    battery_charge_kwh: float = Field(500.0, ge=10.0, le=10000.0, description="Usable battery pack capacity [kWh]")
    battery_mass_kg: float = Field(2500.0, ge=100.0, le=20000.0, description="Battery pack structural mass [kg]")
    motor_eff: float = Field(0.96, ge=0.7, le=0.99, description="Electric motor & inverter efficiency")
    cpr: float = Field(12.0, ge=2.0, le=35.0, description="Gas turbine CPR [-]")
    tit_k: float = Field(1350.0, ge=800.0, le=2000.0, description="Gas turbine TIT [K]")


class HybridSingleResponseContract(BaseModel):
    """Response contract for single-point hybrid electric power split."""
    meta: SolverMetadata = Field(default_factory=SolverMetadata)
    total_power_demand_kW: float = Field(..., description="Total shaft/propulsion power requested [kW]")
    gas_turbine_power_kW: float = Field(..., description="Delivered gas turbine thermal power [kW]")
    battery_power_kW: float = Field(..., description="Delivered electric battery power [kW]")
    gt_fuel_flow_kg_s: float = Field(..., description="Gas turbine fuel flow rate [kg/s]")
    battery_soc_pct: float = Field(..., description="Current battery State of Charge [%]")
    battery_current_A: float = Field(..., description="Instantaneous battery discharge current [A]")
    co2_reduction_pct: float = Field(..., description="CO2 emission reduction relative to pure fossil [%]")
    phases: List[Dict[str, Any]] = Field(default_factory=list, description="Telemetry records")
