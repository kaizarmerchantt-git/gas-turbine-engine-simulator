"""
main.py  —  Gas Turbine Engine Simulator  —  FastAPI Backend
Serves both the turbojet (Cantera-based) and turbofan (CF34 deck interpolation) models.
"""

from __future__ import annotations
import traceback
import os
import json
from typing import Literal, Optional, Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, model_validator

import numpy as np

from turbojet import calc_thrust, DEFAULT_ENG_PARAM, DEFAULT_ENG_PERF
from turbofan import interp_altMNPC, get_envelope, ENVELOPE, KEY_OUTPUTS, DF_CF34, ALTS_LIST
from physics_turbofan import calc_turbofan, DEFAULT_TF_PARAM, DEFAULT_TF_PERF
from off_design import CompressorMap, solve_off_design, run_off_design_sweep
from meanline import solve_compressor_stage, solve_multistage_compressor_meanline, solve_turbine_stage
from turboprop import calc_turboprop_performance, run_turboprop_sweep
from mission import run_mission_simulation
from surrogate import GLOBAL_SURROGATE
from hybrid import evaluate_single_hybrid_point, run_hybrid_mission_simulation, run_hybrid_trade_study, DEFAULT_POWERTRAIN

# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gas Turbine Engine Simulator",
    description=(
        "Interactive engine performance simulation combining a Cantera-based "
        "turbojet model and the GE CF34-10E turbofan deck from pyCycle."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev mode — tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


import math

def _sanitize(obj):
    """Recursively replace float nan/inf with None and convert numpy types so JSON stays RFC 8259 compliant."""
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    return obj


@app.middleware("http")
async def sanitize_nan_middleware(request: Request, call_next):
    """Intercept all responses and replace NaN/Inf with null before sending JSON."""
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            data = json.loads(body)
            clean = _sanitize(data)
            return JSONResponse(content=clean, status_code=response.status_code)
        except Exception:
            return response
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class TurbojetEngineParam(BaseModel):
    A1:             float = Field(DEFAULT_ENG_PARAM["A1"],             description="Inlet capture area [m²]")
    A2:             float = Field(DEFAULT_ENG_PARAM["A2"],             description="Compressor face area [m²]")
    comp_n_stages:  int   = Field(DEFAULT_ENG_PARAM["comp_n_stages"],  description="Number of compressor stages")
    turb_n_stages:  int   = Field(DEFAULT_ENG_PARAM["turb_n_stages"],  description="Number of turbine stages")
    A8:             float = Field(DEFAULT_ENG_PARAM["A8"],             description="Nozzle throat area [m²]")


class TurbojetEnginePerf(BaseModel):
    eta_i:      float = Field(DEFAULT_ENG_PERF["eta_i"],      gt=0.0, le=1.0, description="Inlet adiabatic efficiency (0–1]")
    CPR:        float = Field(DEFAULT_ENG_PERF["CPR"],         gt=1.0,         description="Compressor pressure ratio (>1)")
    eta_c:      float = Field(DEFAULT_ENG_PERF["eta_c"],       gt=0.0, le=1.0, description="Compressor isentropic efficiency (0–1]")
    eta_b:      float = Field(DEFAULT_ENG_PERF["eta_b"],       gt=0.0, le=1.0, description="Combustor efficiency (0–1]")
    dp_over_p:  float = Field(DEFAULT_ENG_PERF["dp_over_p"],  ge=0.0, lt=1.0, description="Combustor pressure loss fraction [0–1)")
    max_f:      float = Field(DEFAULT_ENG_PERF["max_f"],       gt=0.0, le=1.0, description="Max fuel fraction (stoich)")
    min_f:      float = Field(DEFAULT_ENG_PERF["min_f"],       ge=0.0, lt=1.0, description="Min fuel fraction (stoich)")
    V_nominal:  float = Field(DEFAULT_ENG_PERF["V_nominal"],  gt=0.0,         description="Combustor nominal flow velocity [m/s]")
    T_max:      float = Field(DEFAULT_ENG_PERF["T_max"],       gt=300.0,       description="Max combustor temperature (TIT limit) [K]")
    eta_t:      float = Field(DEFAULT_ENG_PERF["eta_t"],       gt=0.0, le=1.0, description="Turbine isentropic efficiency (0–1]")
    mech_loss:  float = Field(DEFAULT_ENG_PERF["mech_loss"],  gt=0.0, le=1.0, description="Mechanical efficiency (0–1]")
    eta_noz:    float = Field(DEFAULT_ENG_PERF["eta_noz"],     gt=0.0, le=1.0, description="Nozzle adiabatic efficiency (0–1]")


class TurbojetSingleRequest(BaseModel):
    eng_param:    TurbojetEngineParam = Field(default_factory=TurbojetEngineParam)
    eng_perf:     TurbojetEnginePerf  = Field(default_factory=TurbojetEnginePerf)
    throttle_pos: float = Field(1.0,     ge=0.5, le=1.0,    description="Throttle position (0.5–1.0)")
    alt:          float = Field(35000.0, ge=0,   le=65000,  description="Altitude [ft]")
    M_i:          float = Field(0.8,     ge=0.0, le=0.9,    description="Mach number")
    mdot_guess:   float = Field(20.0,    gt=0,              description="Initial mass-flow guess [kg/s]")


class PhysicsTurbofanParam(BaseModel):
    A1:           float = Field(DEFAULT_TF_PARAM["A1"])
    A2:           float = Field(DEFAULT_TF_PARAM["A2"])
    fan_n_stages: int   = Field(DEFAULT_TF_PARAM["fan_n_stages"])
    hpc_n_stages: int   = Field(DEFAULT_TF_PARAM["hpc_n_stages"])
    hpt_n_stages: int   = Field(DEFAULT_TF_PARAM["hpt_n_stages"])
    lpt_n_stages: int   = Field(DEFAULT_TF_PARAM["lpt_n_stages"])
    A8:           float = Field(DEFAULT_TF_PARAM["A8"])
    BPR:          float = Field(DEFAULT_TF_PARAM["BPR"])

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "fan_stages" in d and "fan_n_stages" not in d:
                d["fan_n_stages"] = d["fan_stages"]
            if "hpc_stages" in d and "hpc_n_stages" not in d:
                d["hpc_n_stages"] = d["hpc_stages"]
            if "hpt_stages" in d and "hpt_n_stages" not in d:
                d["hpt_n_stages"] = d["hpt_stages"]
            if "lpt_stages" in d and "lpt_n_stages" not in d:
                d["lpt_n_stages"] = d["lpt_stages"]
            return d
        return data

class PhysicsTurbofanPerf(BaseModel):
    eta_i:        float = Field(DEFAULT_TF_PERF["eta_i"],        gt=0.0, le=1.0)
    FPR:          float = Field(DEFAULT_TF_PERF["FPR"],          gt=1.0)
    eta_fan:      float = Field(DEFAULT_TF_PERF["eta_fan"],      gt=0.0, le=1.0)
    CPR:          float = Field(DEFAULT_TF_PERF["CPR"],          gt=1.0)
    eta_hpc:      float = Field(DEFAULT_TF_PERF["eta_hpc"],      gt=0.0, le=1.0)
    eta_b:        float = Field(DEFAULT_TF_PERF["eta_b"],        gt=0.0, le=1.0)
    dp_over_p:    float = Field(DEFAULT_TF_PERF["dp_over_p"],    ge=0.0, lt=1.0)
    max_f:        float = Field(DEFAULT_TF_PERF["max_f"],        gt=0.0, le=1.0)
    min_f:        float = Field(DEFAULT_TF_PERF["min_f"],        ge=0.0, lt=1.0)
    V_nominal:    float = Field(DEFAULT_TF_PERF["V_nominal"],    gt=0.0)
    T_max:        float = Field(DEFAULT_TF_PERF["T_max"],        gt=300.0)
    eta_hpt:      float = Field(DEFAULT_TF_PERF["eta_hpt"],      gt=0.0, le=1.0)
    eta_lpt:      float = Field(DEFAULT_TF_PERF["eta_lpt"],      gt=0.0, le=1.0)
    mech_loss_hp: float = Field(DEFAULT_TF_PERF["mech_loss_hp"], gt=0.0, le=1.0)
    mech_loss_lp: float = Field(DEFAULT_TF_PERF["mech_loss_lp"], gt=0.0, le=1.0)
    eta_noz_core: float = Field(DEFAULT_TF_PERF["eta_noz_core"], gt=0.0, le=1.0)
    eta_noz_byp:  float = Field(DEFAULT_TF_PERF["eta_noz_byp"],  gt=0.0, le=1.0)


class PhysicsTurbofanSingleRequest(BaseModel):
    eng_param:       PhysicsTurbofanParam = Field(default_factory=PhysicsTurbofanParam)
    eng_perf:        PhysicsTurbofanPerf  = Field(default_factory=PhysicsTurbofanPerf)
    throttle_pos:    float = Field(1.0,     ge=0.5, le=1.0)
    alt:             float = Field(35000.0, ge=0,   le=65000)
    M_i:             float = Field(0.8,     ge=0.0, le=0.9)
    mdot_core_guess: float = Field(20.0,    gt=0)

class PhysicsTurbofanSweepRequest(BaseModel):
    eng_param:       PhysicsTurbofanParam = Field(default_factory=PhysicsTurbofanParam)
    eng_perf:        PhysicsTurbofanPerf  = Field(default_factory=PhysicsTurbofanPerf)
    throttle_pos:    float = Field(1.0,     ge=0.5, le=1.0)
    sweep_param:     Literal["altitude", "mach", "throttle", "bpr", "cpr", "fpr"] = "altitude"
    # Altitude sweep
    alt_start:       float = Field(0.0,     ge=0, le=65000)
    alt_end:         float = Field(40000.0, ge=0, le=65000)
    # Mach sweep
    mach_start:      float = Field(0.0,  ge=0.0, le=0.9)
    mach_end:        float = Field(0.8,  ge=0.0, le=0.9)
    # Throttle sweep
    throttle_start:  float = Field(0.5, ge=0.5, le=1.0)
    throttle_end:    float = Field(1.0, ge=0.5, le=1.0)
    # BPR sweep
    bpr_start:       float = Field(3.0, ge=0.1, le=15.0)
    bpr_end:         float = Field(8.0, ge=0.1, le=15.0)
    # CPR sweep
    cpr_start:       float = Field(10.0, ge=1.0, le=40.0)
    cpr_end:         float = Field(25.0, ge=1.0, le=40.0)
    # FPR sweep
    fpr_start:       float = Field(1.2, ge=1.05, le=3.0)
    fpr_end:         float = Field(2.0, ge=1.05, le=3.0)
    # Sweep resolution
    n_steps:         int   = Field(10, ge=3, le=40, description="Number of points in sweep")
    # Fixed values when not sweeping
    fixed_alt:       float = Field(35000.0, ge=0, le=65000)
    fixed_mach:      float = Field(0.8,     ge=0.0, le=0.9)
    fixed_throttle:  float = Field(1.0,     ge=0.5, le=1.0)
    mdot_core_guess: float = Field(20.0,    gt=0)

class TurbojetSweepRequest(BaseModel):
    eng_param:    TurbojetEngineParam = Field(default_factory=TurbojetEngineParam)
    eng_perf:     TurbojetEnginePerf  = Field(default_factory=TurbojetEnginePerf)
    throttle_pos: float = Field(1.0,   ge=0.5, le=1.0)
    sweep_param:  Literal["altitude", "mach", "throttle"] = "altitude"
    # Altitude sweep
    alt_start:    float = Field(0.0,     ge=0, le=65000)
    alt_end:      float = Field(40000.0, ge=0, le=65000)
    # Mach sweep
    mach_start:   float = Field(0.0,  ge=0.0, le=0.9)
    mach_end:     float = Field(0.8,  ge=0.0, le=0.9)
    # Throttle sweep
    throttle_start: float = Field(0.5, ge=0.5, le=1.0)
    throttle_end:   float = Field(1.0, ge=0.5, le=1.0)
    # Sweep resolution
    n_steps:  int   = Field(15, ge=3, le=40, description="Number of points in sweep")
    # Fixed values when not sweeping
    fixed_alt:      float = Field(35000.0, ge=0, le=65000)
    fixed_mach:     float = Field(0.8,     ge=0.0, le=0.9)
    mdot_guess:     float = Field(20.0,    gt=0)


class TurbofanSingleRequest(BaseModel):
    alt: float = Field(35000.0, ge=0,    le=42000, description="Altitude [ft]")
    MN:  float = Field(0.8,     ge=0.0,  le=0.9,   description="Mach number")
    PC:  float = Field(1.0,     ge=0.55, le=1.0,   description="Power code (0.55–1.0)")


class TurbofanSweepRequest(BaseModel):
    sweep_param:  Literal["altitude", "mach", "throttle"] = "altitude"
    alt_start:    float = Field(0.0,     ge=0,    le=42000)
    alt_end:      float = Field(40000.0, ge=0,    le=42000)
    mach_start:   float = Field(0.0,     ge=0.0,  le=0.9)
    mach_end:     float = Field(0.8,     ge=0.0,  le=0.9)
    pc_start:     float = Field(0.55,    ge=0.55, le=1.0)
    pc_end:       float = Field(1.0,     ge=0.55, le=1.0)
    n_steps:      int   = Field(20, ge=3, le=50)
    fixed_alt:    float = Field(35000.0, ge=0,    le=42000)
    fixed_mach:   float = Field(0.8,     ge=0.0,  le=0.9)
    fixed_pc:     float = Field(1.0,     ge=0.55, le=1.0)


class OffDesignSingleRequest(BaseModel):
    N_rel:         float = Field(1.0,    ge=0.55, le=1.10, description="Relative spool speed N/N_des")
    alt:           float = Field(35000.0, ge=0,   le=65000, description="Altitude [ft]")
    mach:          float = Field(0.8,    ge=0.0,  le=0.95,  description="Flight Mach number")
    cpr_des:       float = Field(8.0,    ge=2.0,  le=35.0,  description="Design compressor pressure ratio")
    eta_c_des:     float = Field(0.85,   ge=0.60, le=0.98,  description="Design compressor efficiency")
    mdot_corr_des: float = Field(20.0,   gt=0,    le=200.0, description="Design corrected mass flow [kg/s]")
    A8:            Optional[float] = Field(None, gt=0, description="Nozzle throat area [m²]. Sized to design if omitted.")
    eta_i:         float = Field(0.98,   ge=0.70, le=1.0)
    eta_t:         float = Field(0.88,   ge=0.60, le=0.98)
    mech_loss:     float = Field(0.99,   ge=0.80, le=1.0)
    eta_b:         float = Field(0.99,   ge=0.80, le=1.0)
    dp_over_p:     float = Field(0.04,   ge=0.01, le=0.15)
    T_max:         float = Field(1500.0, ge=800.0, le=2200.0)
    eta_noz:       float = Field(0.98,   ge=0.60, le=1.0)
    throttle_pos:  float = Field(1.0,    ge=0.5,  le=1.0)


class OffDesignSweepRequest(BaseModel):
    sweep_param:   Literal["speed", "altitude", "mach"] = "speed"
    n_steps:       int   = Field(15, ge=3, le=40)
    speed_start:   float = Field(0.65, ge=0.55, le=1.10)
    speed_end:     float = Field(1.05, ge=0.55, le=1.10)
    fixed_speed:   float = Field(1.00, ge=0.55, le=1.10)
    alt_start:     float = Field(0.0, ge=0, le=65000)
    alt_end:       float = Field(40000.0, ge=0, le=65000)
    fixed_alt:     float = Field(35000.0, ge=0, le=65000)
    mach_start:    float = Field(0.0, ge=0.0, le=0.95)
    mach_end:      float = Field(0.85, ge=0.0, le=0.95)
    fixed_mach:    float = Field(0.80, ge=0.0, le=0.95)
    cpr_des:       float = Field(8.0, ge=2.0, le=35.0)
    eta_c_des:     float = Field(0.85, ge=0.60, le=0.98)
    mdot_corr_des: float = Field(20.0, gt=0, le=200.0)
    A8:            Optional[float] = Field(None, gt=0)
    eta_i:         float = Field(0.98, ge=0.70, le=1.0)
    eta_t:         float = Field(0.88, ge=0.60, le=0.98)
    mech_loss:     float = Field(0.99, ge=0.80, le=1.0)
    eta_b:         float = Field(0.99, ge=0.80, le=1.0)
    dp_over_p:     float = Field(0.04, ge=0.01, le=0.15)
    T_max:         float = Field(1500.0, ge=800.0, le=2200.0)
    eta_noz:       float = Field(0.98, ge=0.60, le=1.0)
    throttle_pos:  float = Field(1.0, ge=0.5, le=1.0)


# Mean-Line Aerodynamics Schemas
class MeanlineCompressorStageRequest(BaseModel):
    T01:         float = Field(288.15, ge=150.0, le=800.0)
    P01:         float = Field(101325.0, ge=5000.0, le=5000000.0)
    delta_T0:    float = Field(35.0, ge=5.0, le=120.0)
    N_rpm:       float = Field(12000.0, ge=1000.0, le=50000.0)
    r_mean:      float = Field(0.28, ge=0.05, le=2.0)
    C_a:         float = Field(160.0, ge=50.0, le=350.0)
    reaction:    float = Field(0.50, ge=0.1, le=0.9)
    eta_stage:   float = Field(0.88, ge=0.60, le=0.98)
    mdot:        float = Field(20.0, ge=0.5, le=200.0)
    solidity:    float = Field(1.2, ge=0.6, le=2.5)
    alpha_1_deg: Optional[float] = None
    beta_2_deg:  Optional[float] = None
    C_a1:        Optional[float] = None
    C_a2:        Optional[float] = None
    alpha_3_deg: Optional[float] = None
    U:           Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            r_mean = float(d.get("r_mean", 0.28))
            if "U" in d and "N_rpm" not in d:
                u = float(d["U"])
                d["N_rpm"] = (u * 60.0) / (2.0 * math.pi * r_mean) if r_mean > 0 else 12000.0
            if "C_a1" in d and "C_a" not in d:
                d["C_a"] = d["C_a1"]
            return d
        return data


class MeanlineMultistageRequest(BaseModel):
    CPR:        float = Field(8.0, ge=1.5, le=40.0)
    n_stages:   int   = Field(6, ge=1, le=18)
    T0_inlet:   float = Field(288.15, ge=150.0, le=600.0)
    P0_inlet:   float = Field(101325.0, ge=5000.0, le=500000.0)
    N_rpm:      float = Field(12000.0, ge=1000.0, le=50000.0)
    r_mean:     float = Field(0.28, ge=0.05, le=2.0)
    C_a:        float = Field(160.0, ge=50.0, le=350.0)
    reaction:   float = Field(0.50, ge=0.1, le=0.9)
    eta_poly:   float = Field(0.88, ge=0.60, le=0.98)
    mdot:       float = Field(20.0, ge=0.5, le=200.0)

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "num_stages" in d and "n_stages" not in d:
                d["n_stages"] = d["num_stages"]
            if "T0_in" in d and "T0_inlet" not in d:
                d["T0_inlet"] = d["T0_in"]
            if "P0_in" in d and "P0_inlet" not in d:
                d["P0_inlet"] = d["P0_in"]
            if "eta_stage" in d and "eta_poly" not in d:
                d["eta_poly"] = d["eta_stage"]
            if "U_mean" in d and "N_rpm" not in d:
                r_mean = float(d.get("r_mean", 0.28))
                u = float(d["U_mean"])
                d["N_rpm"] = (u * 60.0) / (2.0 * math.pi * r_mean) if r_mean > 0 else 12000.0
            return d
        return data


class MeanlineTurbineStageRequest(BaseModel):
    T01:         float = Field(1400.0, ge=800.0, le=2200.0)
    P01:         float = Field(800000.0, ge=50000.0, le=5000000.0)
    delta_T0:    float = Field(180.0, ge=20.0, le=400.0)
    N_rpm:       float = Field(12000.0, ge=1000.0, le=50000.0)
    r_mean:      float = Field(0.28, ge=0.05, le=2.0)
    C_a:         float = Field(220.0, ge=50.0, le=450.0)
    reaction:    float = Field(0.40, ge=0.1, le=0.9)
    eta_stage:   float = Field(0.90, ge=0.60, le=0.98)
    solidity:    float = Field(1.4, ge=0.6, le=2.5)
    alpha_2_deg: Optional[float] = None
    beta_3_deg:  Optional[float] = None
    U:           Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            r_mean = float(d.get("r_mean", 0.28))
            if "U" in d and "N_rpm" not in d:
                u = float(d["U"])
                d["N_rpm"] = (u * 60.0) / (2.0 * math.pi * r_mean) if r_mean > 0 else 12000.0
            return d
        return data


# Turboprop / Turboshaft Schemas
class TurbopropSingleRequest(BaseModel):
    alt:             float = Field(15000.0, ge=0.0, le=45000.0)
    mach:            float = Field(0.40, ge=0.0, le=0.75)
    CPR:             float = Field(12.0, ge=3.0, le=30.0)
    TIT:             float = Field(1400.0, ge=900.0, le=1900.0)
    mdot_air:        float = Field(10.0, ge=1.0, le=100.0)
    A8:              float = Field(0.08, ge=0.01, le=1.0)
    prop_diameter_m: float = Field(3.2, ge=0.5, le=6.0)
    prop_rpm:        float = Field(1200.0, ge=300.0, le=3000.0)
    eta_i:           float = Field(0.98, ge=0.8, le=1.0)
    eta_c:           float = Field(0.85, ge=0.6, le=0.98)
    eta_b:           float = Field(0.99, ge=0.8, le=1.0)
    dp_over_p:       float = Field(0.04, ge=0.01, le=0.12)
    eta_hpt:         float = Field(0.89, ge=0.6, le=0.98)
    eta_pt:          float = Field(0.90, ge=0.6, le=0.98)
    eta_mech_core:   float = Field(0.99, ge=0.8, le=1.0)
    eta_mech_pt:     float = Field(0.98, ge=0.8, le=1.0)
    eta_gearbox:     float = Field(0.985, ge=0.8, le=1.0)
    eta_noz:         float = Field(0.95, ge=0.8, le=1.0)
    prop_eff_max:    float = Field(0.84, ge=0.5, le=0.95)

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "altitude_m" in d and "alt" not in d:
                d["alt"] = float(d["altitude_m"]) * 3.28084
            if "mdot_core" in d and "mdot_air" not in d:
                d["mdot_air"] = d["mdot_core"]
            if "pi_c" in d and "CPR" not in d:
                d["CPR"] = d["pi_c"]
            if "T04" in d and "TIT" not in d:
                d["TIT"] = d["T04"]
            if "rpm" in d and "prop_rpm" not in d:
                d["prop_rpm"] = d["rpm"]
            if "burner_dP" in d and "dp_over_p" not in d:
                d["dp_over_p"] = d["burner_dP"]
            if "eta_gear" in d and "eta_gearbox" not in d:
                d["eta_gearbox"] = d["eta_gear"]
            if "eta_mech" in d:
                if "eta_mech_core" not in d:
                    d["eta_mech_core"] = d["eta_mech"]
                if "eta_mech_pt" not in d:
                    d["eta_mech_pt"] = d["eta_mech"]
            return d
        return data


class TurbopropSweepRequest(BaseModel):
    sweep_param:  Literal["power", "altitude", "mach"] = "power"
    n_steps:      int   = Field(10, ge=3, le=25)
    alt_fixed:    float = Field(15000.0, ge=0.0, le=45000.0)
    mach_fixed:   float = Field(0.40, ge=0.0, le=0.75)
    cpr_fixed:    float = Field(12.0, ge=3.0, le=30.0)
    tit_fixed:    float = Field(1400.0, ge=900.0, le=1900.0)

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "param" in d and "sweep_param" not in d:
                d["sweep_param"] = d["param"]
            if "altitude_m" in d and "alt_fixed" not in d:
                d["alt_fixed"] = float(d["altitude_m"]) * 3.28084
            if "pi_c" in d and "cpr_fixed" not in d:
                d["cpr_fixed"] = d["pi_c"]
            if "T04" in d and "tit_fixed" not in d:
                d["tit_fixed"] = d["T04"]
            return d
        return data


# Mission Simulation Schemas
class MissionSimulateRequest(BaseModel):
    cruise_alt_ft:      float = Field(35000.0, ge=10000.0, le=45000.0)
    cruise_mach:        float = Field(0.78, ge=0.40, le=0.88)
    cruise_distance_nm: float = Field(1200.0, ge=100.0, le=4000.0)
    payload_kg:         float = Field(9000.0, ge=0.0, le=15000.0)
    fuel_load_kg:       Optional[float] = Field(None, ge=1000.0, le=20000.0)
    engine_base_tsfc:   float = Field(16.5, ge=10.0, le=35.0)

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "cruise_alt_m" in d and "cruise_alt_ft" not in d:
                d["cruise_alt_ft"] = float(d["cruise_alt_m"]) * 3.28084
            if "cruise_dist_km" in d and "cruise_distance_nm" not in d:
                d["cruise_distance_nm"] = float(d["cruise_dist_km"]) / 1.852
            return d
        return data


# Fast Surrogate Schemas
class SurrogatePredictRequest(BaseModel):
    alt_ft:   float = Field(35000.0, ge=0.0, le=45000.0)
    mach:     float = Field(0.80, ge=0.0, le=0.90)
    throttle: float = Field(1.00, ge=0.50, le=1.0)
    CPR:      float = Field(14.0, ge=4.0, le=25.0)
    TIT_K:    float = Field(1450.0, ge=1100.0, le=1800.0)

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "altitude_m" in d and "alt_ft" not in d:
                d["alt_ft"] = float(d["altitude_m"]) * 3.28084
            if "cpr" in d and "CPR" not in d:
                d["CPR"] = d["cpr"]
            if "tit_K" in d and "TIT_K" not in d:
                d["TIT_K"] = d["tit_K"]
            return d
        return data


class SurrogateSurfaceRequest(BaseModel):
    x_param:        str = "CPR"
    y_param:        str = "TIT_K"
    x_min:          Optional[float] = None
    x_max:          Optional[float] = None
    n_points:       Optional[int] = Field(30, ge=5, le=100)
    fixed_params:   Optional[Dict[str, Any]] = None
    fixed_alt:      float = Field(35000.0, ge=0.0, le=45000.0)
    fixed_mach:     float = Field(0.80, ge=0.0, le=0.90)
    fixed_throttle: float = Field(1.00, ge=0.30, le=1.0)
    fixed_cpr:      float = Field(14.0, ge=4.0, le=35.0)
    fixed_tit:      float = Field(1450.0, ge=1100.0, le=1800.0)
    grid_res:       int   = Field(15, ge=5, le=30)

    @model_validator(mode="before")
    @classmethod
    def map_frontend_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            fp = d.get("fixed_params")
            if isinstance(fp, dict):
                if "altitude_m" in fp and "fixed_alt" not in d:
                    d["fixed_alt"] = float(fp["altitude_m"]) * 3.28084
                elif "alt_ft" in fp and "fixed_alt" not in d:
                    d["fixed_alt"] = float(fp["alt_ft"])
                if "mach" in fp and "fixed_mach" not in d:
                    d["fixed_mach"] = float(fp["mach"])
                if "throttle" in fp and "fixed_throttle" not in d:
                    d["fixed_throttle"] = float(fp["throttle"])
                if "cpr" in fp and "fixed_cpr" not in d:
                    d["fixed_cpr"] = float(fp["cpr"])
                elif "CPR" in fp and "fixed_cpr" not in d:
                    d["fixed_cpr"] = float(fp["CPR"])
                if "tit_K" in fp and "fixed_tit" not in d:
                    d["fixed_tit"] = float(fp["tit_K"])
                elif "TIT_K" in fp and "fixed_tit" not in d:
                    d["fixed_tit"] = float(fp["TIT_K"])
            elif "altitude_m" in d and "fixed_alt" not in d:
                d["fixed_alt"] = float(d["altitude_m"]) * 3.28084
            return d
        return data


# Hybrid Electric Schemas (Extension 5)
class HybridSingleRequest(BaseModel):
    architecture:          Literal["parallel", "series", "turboelectric"] = "parallel"
    shaft_power_req_kW:    float = Field(2000.0, ge=100.0, le=20000.0)
    hybrid_power_ratio_HP: float = Field(0.25, ge=0.0, le=1.0)
    battery_mass_kg:       float = Field(1200.0, ge=0.0, le=15000.0)
    battery_soc:           float = Field(0.85, ge=0.05, le=1.0)
    turbogen_rated_kW:     Optional[float] = Field(None, ge=100.0, le=20000.0)


class HybridMissionRequest(BaseModel):
    architecture:          Literal["parallel", "series", "turboelectric"] = "parallel"
    cruise_alt_m:          float = Field(9144.0, ge=3000.0, le=13000.0)
    cruise_mach:           float = Field(0.72, ge=0.30, le=0.88)
    cruise_dist_km:        float = Field(900.0, ge=100.0, le=3500.0)
    payload_kg:            float = Field(6500.0, ge=500.0, le=15000.0)
    battery_mass_kg:       float = Field(1800.0, ge=0.0, le=10000.0)
    specific_energy_Wh_kg: float = Field(300.0, ge=150.0, le=800.0)
    takeoff_hybrid_ratio:  float = Field(0.35, ge=0.0, le=0.70)
    climb_hybrid_ratio:    float = Field(0.20, ge=0.0, le=0.50)
    cruise_hybrid_ratio:   float = Field(0.05, ge=0.0, le=0.30)
    descent_hybrid_ratio:  float = Field(0.0, ge=0.0, le=0.20)


class HybridSweepRequest(BaseModel):
    study_type:            Literal["hybrid_ratio", "specific_energy", "distance"] = "hybrid_ratio"
    architecture:          Literal["parallel", "series", "turboelectric"] = "parallel"
    n_points:              int   = Field(10, ge=4, le=25)
    cruise_dist_km:        float = Field(900.0, ge=100.0, le=3500.0)
    specific_energy_Wh_kg: float = Field(300.0, ge=150.0, le=800.0)
    battery_mass_kg:       float = Field(1800.0, ge=0.0, le=10000.0)


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root(request: Request):
    accept = request.headers.get("accept", "")
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    # If a browser requests the root URL, serve the interactive simulator UI
    if "text/html" in accept and os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    # Default / API JSON response
    return {
        "status": "online",
        "service": "Gas Turbine Engine Simulator",
        "models": [
            "turbojet",
            "physics_turbofan",
            "turbofan_cf34",
            "off_design",
            "meanline",
            "turboprop",
            "mission",
            "surrogate",
            "hybrid_electric"
        ],
        "docs":   "/docs",
        "app":    "/app",
    }


@app.get("/app")
def serve_app():
    """Direct route to serve the interactive web simulator frontend."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    raise HTTPException(status_code=404, detail="frontend/index.html not found")


@app.get("/api/status")
@app.get("/api/health")
def api_health():
    """Health check endpoint for real-time frontend connection status badge."""
    return {
        "status": "online",
        "service": "Gas Turbine Engine Simulator",
        "version": "1.0.0",
        "models_count": 9,
        "active_models": [
            "turbojet", "physics_turbofan", "turbofan_cf34", "off_design",
            "meanline", "turboprop", "mission", "surrogate", "hybrid_electric"
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Turbojet endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/turbojet/defaults")
def turbojet_defaults():
    """Return the default engine parameters for the Orenda-style turbojet."""
    return {
        "eng_param": DEFAULT_ENG_PARAM,
        "eng_perf":  DEFAULT_ENG_PERF,
        "descriptions": {
            "eng_param": {
                "A1":            "Inlet capture area [m²]",
                "A2":            "Compressor face area [m²]",
                "comp_n_stages": "Number of compressor stages",
                "turb_n_stages": "Number of turbine stages",
                "A8":            "Nozzle throat area [m²]",
            },
            "eng_perf": {
                "eta_i":     "Inlet adiabatic efficiency (0–1)",
                "CPR":       "Compressor pressure ratio",
                "eta_c":     "Compressor isentropic stage efficiency (0–1)",
                "eta_b":     "Combustor efficiency (0–1)",
                "dp_over_p": "Combustor total-pressure loss fraction (e.g. 0.06 = 6%)",
                "max_f":     "Max fuel as fraction of stoichiometric",
                "min_f":     "Min fuel as fraction of stoichiometric",
                "V_nominal": "Nominal combustor flow velocity [m/s]",
                "T_max":     "TIT limiter — max combustor exit temperature [K]",
                "eta_t":     "Turbine isentropic stage efficiency (0–1)",
                "mech_loss": "Mechanical efficiency, turbine→compressor shaft",
                "eta_noz":   "Nozzle adiabatic efficiency (0–1)",
            },
        },
    }


@app.post("/api/turbojet/single")
def turbojet_single(req: TurbojetSingleRequest):
    """
    Run a single-point turbojet simulation and return station-level results.
    Computation time: ~5–30 seconds depending on convergence iterations.
    """
    try:
        result = calc_thrust(
            eng_param=req.eng_param.model_dump(),
            eng_perf=req.eng_perf.model_dump(),
            throttle_pos=req.throttle_pos,
            alt=req.alt,
            M_i=req.M_i,
            mdot_guess=req.mdot_guess,
        )
        return _sanitize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/turbojet/sweep")
def turbojet_sweep(req: TurbojetSweepRequest):
    """
    Run a parameter sweep for the turbojet.
    Returns a list of single-point results — one per sweep step.
    WARNING: each point takes ~5–30 s. Keep n_steps ≤ 15 for reasonable wait times.
    """
    eng_param = req.eng_param.model_dump()
    eng_perf  = req.eng_perf.model_dump()

    if req.sweep_param == "altitude":
        sweep_vals = np.linspace(req.alt_start, req.alt_end, req.n_steps).tolist()
        fixed_args = {"M_i": req.fixed_mach, "throttle_pos": req.throttle_pos}
        param_key  = "alt"
    elif req.sweep_param == "mach":
        sweep_vals = np.linspace(req.mach_start, req.mach_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "throttle_pos": req.throttle_pos}
        param_key  = "M_i"
    else:  # throttle
        sweep_vals = np.linspace(req.throttle_start, req.throttle_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "M_i": req.fixed_mach}
        param_key  = "throttle_pos"

    results = []
    mdot_guess = req.mdot_guess

    for val in sweep_vals:
        kwargs = {param_key: val, **fixed_args, "mdot_guess": mdot_guess}
        try:
            r = calc_thrust(eng_param=eng_param, eng_perf=eng_perf, **kwargs)
            # Carry over converged mdot to speed up next point
            mdot_guess = r.get("mdot_air", mdot_guess) or mdot_guess
            results.append(r)
        except Exception as e:
            results.append({
                param_key: val,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            })

    return _sanitize({"sweep_param": req.sweep_param, "points": results})


# ─────────────────────────────────────────────────────────────────────────────
# Turbofan (CF34) and Physics Turbofan endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/physics_turbofan/single")
def physics_turbofan_single(req: PhysicsTurbofanSingleRequest):
    """
    Run a single-point physics-based turbofan simulation.
    """
    try:
        result = calc_turbofan(
            eng_param=req.eng_param.model_dump(),
            eng_perf=req.eng_perf.model_dump(),
            throttle_pos=req.throttle_pos,
            alt=req.alt,
            M_i=req.M_i,
            mdot_core_guess=req.mdot_core_guess,
        )
        return _sanitize(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

@app.get("/api/physics_turbofan/defaults")
def physics_turbofan_defaults():
    """Return default parameters and performance metrics for the physics turbofan."""
    return {
        "eng_param": DEFAULT_TF_PARAM,
        "eng_perf":  DEFAULT_TF_PERF,
    }

@app.post("/api/physics_turbofan/ts_diagram")
def physics_turbofan_ts_diagram(req: PhysicsTurbofanSingleRequest):
    """
    Run the physics turbofan model and return station T and s values suitable
    for plotting a T-s diagram for both core and bypass streams.
    """
    try:
        result = calc_turbofan(
            eng_param=req.eng_param.model_dump(),
            eng_perf=req.eng_perf.model_dump(),
            throttle_pos=req.throttle_pos,
            alt=req.alt,
            M_i=req.M_i,
            mdot_core_guess=req.mdot_core_guess,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    stations = result.get("stations", {})
    ordered = ["a", "1", "2", "13", "21", "3", "4", "41", "5", "8", "18"]
    points = []
    for sid in ordered:
        if sid in stations:
            s = stations[sid]
            stream = "bypass" if sid in ("13", "18") else "core"
            points.append({
                "station": sid,
                "label":   s["label"],
                "T_K":     s["T_K"],
                "s_JkgK":  s["s_JkgK"],
                "P_atm":   s["P_atm"],
                "h_Jkg":   s.get("h_Jkg", 0.0),
                "stream":  stream,
            })

    return _sanitize({
        "points": points,
        "performance": {
            "T":         result.get("T", 0.0),
            "T_core":    result.get("T_core", 0.0),
            "T_byp":     result.get("T_byp", 0.0),
            "TSFC":      result.get("TSFC", 0.0),
            "mdot_fuel": result.get("mdot_fuel", 0.0),
            "mdot_core": result.get("mdot_core", 0.0),
            "mdot_byp":  result.get("mdot_byp", 0.0),
            "BPR":       result.get("BPR", 0.0),
            "A18_calc":  result.get("A18_calc", 0.0),
        },
        "T_max_limited": result.get("T_max_limited", False),
        "converged":     result.get("converged", False),
    })

@app.post("/api/physics_turbofan/sweep")
def physics_turbofan_sweep(req: PhysicsTurbofanSweepRequest):
    """
    Run a multi-point parameter sweep for the physics turbofan model.
    Warm-starts mdot_core_guess across consecutive steps.
    """
    if req.sweep_param == "altitude":
        sweep_vals = np.linspace(req.alt_start, req.alt_end, req.n_steps).tolist()
        fixed_args = {"M_i": req.fixed_mach, "throttle_pos": req.fixed_throttle}
        param_key  = "alt"
    elif req.sweep_param == "mach":
        sweep_vals = np.linspace(req.mach_start, req.mach_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "throttle_pos": req.fixed_throttle}
        param_key  = "M_i"
    elif req.sweep_param == "throttle":
        sweep_vals = np.linspace(req.throttle_start, req.throttle_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "M_i": req.fixed_mach}
        param_key  = "throttle_pos"
    elif req.sweep_param == "bpr":
        sweep_vals = np.linspace(req.bpr_start, req.bpr_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "M_i": req.fixed_mach, "throttle_pos": req.fixed_throttle}
        param_key  = "BPR"
    elif req.sweep_param == "cpr":
        sweep_vals = np.linspace(req.cpr_start, req.cpr_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "M_i": req.fixed_mach, "throttle_pos": req.fixed_throttle}
        param_key  = "CPR"
    elif req.sweep_param == "fpr":
        sweep_vals = np.linspace(req.fpr_start, req.fpr_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "M_i": req.fixed_mach, "throttle_pos": req.fixed_throttle}
        param_key  = "FPR"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported sweep param: {req.sweep_param}")

    results = []
    mdot_core_guess = req.mdot_core_guess
    base_eng_param = req.eng_param.model_dump()
    base_eng_perf = req.eng_perf.model_dump()

    for val in sweep_vals:
        curr_param = base_eng_param.copy()
        curr_perf  = base_eng_perf.copy()
        curr_call_kwargs = dict(fixed_args)

        if param_key in ("alt", "M_i", "throttle_pos"):
            curr_call_kwargs[param_key] = val
        elif param_key == "BPR":
            curr_param["BPR"] = val
        elif param_key == "CPR":
            curr_perf["CPR"] = val
        elif param_key == "FPR":
            curr_perf["FPR"] = val

        try:
            r = calc_turbofan(
                eng_param=curr_param,
                eng_perf=curr_perf,
                mdot_core_guess=mdot_core_guess,
                **curr_call_kwargs,
            )
            if r.get("converged") and r.get("mdot_core", 0) > 0:
                mdot_core_guess = r["mdot_core"]
            r[param_key] = val
            results.append(r)
        except Exception as e:
            results.append({
                param_key: val,
                "error": str(e)[:200],
                "alt_ft": curr_call_kwargs.get("alt", req.fixed_alt),
                "Mach": curr_call_kwargs.get("M_i", req.fixed_mach),
                "throttle_pos": curr_call_kwargs.get("throttle_pos", req.fixed_throttle),
            })

    return _sanitize({"sweep_param": req.sweep_param, "points": results})

@app.post("/api/physics_turbofan/sweep/csv")
def physics_turbofan_sweep_csv(req: PhysicsTurbofanSweepRequest):
    """Run a physics turbofan sweep and return results as a CSV string."""
    from fastapi.responses import PlainTextResponse
    import io, csv as csvmod

    res = physics_turbofan_sweep(req)
    points = res["points"]

    buf = io.StringIO()
    if points:
        fieldnames = []
        for k in points[0].keys():
            if k != "stations":
                fieldnames.append(k)
        writer = csvmod.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(points)

    return PlainTextResponse(content=buf.getvalue(), media_type="text/csv")

@app.get("/api/turbofan/envelope")
def turbofan_envelope():
    """Return the flight envelope and available parameter ranges for the CF34 deck."""
    return {
        "envelope": ENVELOPE,
        "key_outputs": KEY_OUTPUTS,
        "description": (
            "GE CF34-10E turbofan engine deck generated by pyCycle/OpenMDAO. "
            "Interpolated trilinearly over (altitude [ft], Mach, power code PC)."
        ),
    }


@app.post("/api/turbofan/single")
def turbofan_single(req: TurbofanSingleRequest):
    """
    Interpolate the CF34 deck at a given (altitude, Mach, power code).
    Very fast — typically < 50 ms.
    """
    try:
        result = interp_altMNPC(Hp=req.alt, MN=req.MN, PC=req.PC)
        # Convert Fn from lbf to kN for consistency with turbojet output
        result["Fn_kN"]  = round(result["Fn"]  * 0.00444822, 3)
        result["Fg_kN"]  = round(result["Fg"]  * 0.00444822, 3)
        result["Wf_kgs"] = round(result["Wf"]  * 0.453592, 5)   # lbm/s → kg/s
        result["alt_ft"] = req.alt
        result["Mach"]   = req.MN
        result["PC"]     = req.PC

        # Rankine to Kelvin: K = R * 5/9, atm to kPa: kPa = atm * 101.325
        T0_K = float(result.get("fc:stat:T", 390.0) * 5.0 / 9.0)
        p0_kPa = float(result.get("fc:stat:P", 0.235) * 101.325)
        V_flight = float(req.MN * math.sqrt(1.4 * 287.05 * T0_K))

        stations = {
            "0": {
                "label": "Ambient Freestream",
                "T_K": round(float(T0_K * (1.0 + 0.2 * req.MN**2)), 1),
                "Ts_K": round(float(T0_K), 1),
                "P_atm": round(float(result.get("fc:stat:P", 0.235)), 4),
                "p_kPa": round(float(p0_kPa * (1.0 + 0.2 * req.MN**2)**3.5), 1),
                "ps_kPa": round(float(p0_kPa), 1),
                "Mach": round(float(req.MN), 3),
                "V_ms": round(float(V_flight), 1),
                "s_JkgK": round(float(result.get("fc:stat:S", 1.6) * 4186.8), 0),
            },
            "1": {
                "label": "Inlet Lip Entry",
                "T_K": round(float(result.get("inlet:tot:T", 444.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("inlet:tot:T", 444.0) * 5.0 / 9.0 * 0.95), 1),
                "P_atm": round(float(result.get("inlet:tot:P", 0.35)), 4),
                "p_kPa": round(float(result.get("inlet:tot:P", 0.35) * 101.325), 1),
                "ps_kPa": round(float(result.get("inlet:tot:P", 0.35) * 101.325 * 0.85), 1),
                "Mach": round(float(req.MN * 0.85), 3),
                "V_ms": round(float(V_flight * 0.85), 1),
                "s_JkgK": round(float(result.get("inlet:tot:S", 1.6) * 4186.8), 0),
            },
            "2": {
                "label": "Fan Face / Intake Exit",
                "T_K": round(float(result.get("inlet:tot:T", 444.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("inlet:tot:T", 444.0) * 5.0 / 9.0 * 0.92), 1),
                "P_atm": round(float(result.get("inlet:tot:P", 0.35)), 4),
                "p_kPa": round(float(result.get("inlet:tot:P", 0.35) * 101.325), 1),
                "ps_kPa": round(float(result.get("inlet:tot:P", 0.35) * 101.325 * 0.78), 1),
                "Mach": 0.55,
                "V_ms": 170.0,
                "s_JkgK": round(float(result.get("inlet:tot:S", 1.6) * 4186.8), 0),
            },
            "13": {
                "label": "Bypass Duct Inlet",
                "T_K": round(float(result.get("fan:tot:T", 523.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("fan:tot:T", 523.0) * 5.0 / 9.0 * 0.94), 1),
                "P_atm": round(float(result.get("fan:tot:P", 0.55)), 4),
                "p_kPa": round(float(result.get("fan:tot:P", 0.55) * 101.325), 1),
                "ps_kPa": round(float(result.get("fan:tot:P", 0.55) * 101.325 * 0.85), 1),
                "Mach": 0.45,
                "V_ms": 160.0,
                "s_JkgK": round(float(result.get("fan:tot:S", 1.62) * 4186.8), 0),
            },
            "21": {
                "label": "Core Booster / LPC Entry",
                "T_K": round(float(result.get("lpc:tot:T", result.get("fan:tot:T", 523.0)) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("lpc:tot:T", result.get("fan:tot:T", 523.0)) * 5.0 / 9.0 * 0.95), 1),
                "P_atm": round(float(result.get("lpc:tot:P", result.get("fan:tot:P", 0.55))), 4),
                "p_kPa": round(float(result.get("lpc:tot:P", result.get("fan:tot:P", 0.55)) * 101.325), 1),
                "ps_kPa": round(float(result.get("lpc:tot:P", result.get("fan:tot:P", 0.55)) * 101.325 * 0.88), 1),
                "Mach": 0.40,
                "V_ms": 140.0,
                "s_JkgK": round(float(result.get("lpc:tot:S", 1.62) * 4186.8), 0),
            },
            "3": {
                "label": "HPC Exit / Combustor Inlet",
                "T_K": round(float(result.get("hpc:tot:T", 1000.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("hpc:tot:T", 1000.0) * 5.0 / 9.0 * 0.97), 1),
                "P_atm": round(float(result.get("hpc:tot:P", 7.0)), 4),
                "p_kPa": round(float(result.get("hpc:tot:P", 7.0) * 101.325), 1),
                "ps_kPa": round(float(result.get("hpc:tot:P", 7.0) * 101.325 * 0.92), 1),
                "Mach": 0.28,
                "V_ms": 120.0,
                "s_JkgK": round(float(result.get("hpc:tot:S", 1.68) * 4186.8), 0),
            },
            "4": {
                "label": "Combustor Exit / Turbine Inlet",
                "T_K": round(float(result.get("burner:tot:T", 2500.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("burner:tot:T", 2500.0) * 5.0 / 9.0 * 0.98), 1),
                "P_atm": round(float(result.get("burner:tot:P", result.get("hpc:tot:P", 7.0) * 0.95)), 4),
                "p_kPa": round(float(result.get("burner:tot:P", result.get("hpc:tot:P", 7.0) * 0.95) * 101.325), 1),
                "ps_kPa": round(float(result.get("burner:tot:P", result.get("hpc:tot:P", 7.0) * 0.95) * 101.325 * 0.94), 1),
                "Mach": 0.22,
                "V_ms": 115.0,
                "s_JkgK": round(float(result.get("burner:tot:S", 2.1) * 4186.8), 0),
            },
            "41": {
                "label": "HPT Rotor Entry",
                "T_K": round(float(result.get("hpt:tot:T", result.get("burner:tot:T", 2500.0) * 0.92) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("hpt:tot:T", result.get("burner:tot:T", 2500.0) * 0.92) * 5.0 / 9.0 * 0.85), 1),
                "P_atm": round(float(result.get("hpt:tot:P", result.get("burner:tot:P", 6.5) * 0.65)), 4),
                "p_kPa": round(float(result.get("hpt:tot:P", result.get("burner:tot:P", 6.5) * 0.65) * 101.325), 1),
                "ps_kPa": round(float(result.get("hpt:tot:P", result.get("burner:tot:P", 6.5) * 0.65) * 101.325 * 0.65), 1),
                "Mach": 0.75,
                "V_ms": 420.0,
                "s_JkgK": round(float(result.get("hpt:tot:S", 2.12) * 4186.8), 0),
            },
            "5": {
                "label": "LPT Exit / Core Exhaust",
                "T_K": round(float(result.get("lpt:tot:T", 1400.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("lpt:tot:T", 1400.0) * 5.0 / 9.0 * 0.92), 1),
                "P_atm": round(float(result.get("lpt:tot:P", 0.65)), 4),
                "p_kPa": round(float(result.get("lpt:tot:P", 0.65) * 101.325), 1),
                "ps_kPa": round(float(result.get("lpt:tot:P", 0.65) * 101.325 * 0.80), 1),
                "Mach": 0.52,
                "V_ms": 280.0,
                "s_JkgK": round(float(result.get("lpt:tot:S", 2.2) * 4186.8), 0),
            },
            "8": {
                "label": "Core Nozzle Throat",
                "T_K": round(float(result.get("lpt:tot:T", 1400.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("lpt:tot:T", 1400.0) * 5.0 / 9.0 * 0.833), 1),
                "P_atm": round(float(result.get("lpt:tot:P", 0.65)), 4),
                "p_kPa": round(float(result.get("lpt:tot:P", 0.65) * 101.325), 1),
                "ps_kPa": round(float(result.get("lpt:tot:P", 0.65) * 101.325 * 0.528), 1),
                "Mach": 1.0,
                "V_ms": round(float(math.sqrt(1.33 * 287.05 * (result.get("lpt:tot:T", 1400.0) * 5.0 / 9.0 * 0.833))), 1),
                "s_JkgK": round(float(result.get("lpt:tot:S", 2.2) * 4186.8), 0),
            },
            "18": {
                "label": "Bypass Nozzle Throat",
                "T_K": round(float(result.get("fan:tot:T", 523.0) * 5.0 / 9.0), 1),
                "Ts_K": round(float(result.get("fan:tot:T", 523.0) * 5.0 / 9.0 * 0.833), 1),
                "P_atm": round(float(result.get("fan:tot:P", 0.55)), 4),
                "p_kPa": round(float(result.get("fan:tot:P", 0.55) * 101.325), 1),
                "ps_kPa": round(float(result.get("fan:tot:P", 0.55) * 101.325 * 0.528), 1),
                "Mach": 1.0,
                "V_ms": round(float(math.sqrt(1.4 * 287.05 * (result.get("fan:tot:T", 523.0) * 5.0 / 9.0 * 0.833))), 1),
                "s_JkgK": round(float(result.get("fan:tot:S", 1.62) * 4186.8), 0),
            }
        }
        result["stations"] = stations
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/api/turbofan/sweep")
def turbofan_sweep(req: TurbofanSweepRequest):
    """
    Sweep altitude, Mach, or power over the CF34 deck.
    Fast operation — the deck is pre-computed.
    """
    if req.sweep_param == "altitude":
        sweep_vals = np.linspace(req.alt_start,  req.alt_end,  req.n_steps).tolist()
        fixed_args = {"MN": req.fixed_mach, "PC": req.fixed_pc}
        param_key  = "Hp"                                    # interp_altMNPC uses Hp not alt
    elif req.sweep_param == "mach":
        sweep_vals = np.linspace(req.mach_start, req.mach_end, req.n_steps).tolist()
        fixed_args = {"Hp": req.fixed_alt, "PC": req.fixed_pc}
        param_key  = "MN"
    else:  # throttle / PC
        sweep_vals = np.linspace(req.pc_start,   req.pc_end,   req.n_steps).tolist()
        fixed_args = {"Hp": req.fixed_alt, "MN": req.fixed_mach}
        param_key  = "PC"

    results = []
    for val in sweep_vals:
        kwargs = {param_key: val, **fixed_args}
        try:
            r = interp_altMNPC(**kwargs)                      # now receives Hp=, MN=, PC=
            r["Fn_kN"]  = round(r["Fn"]  * 0.00444822, 3)
            r["Fg_kN"]  = round(r["Fg"]  * 0.00444822, 3)
            r["Wf_kgs"] = round(r["Wf"]  * 0.453592, 5)
            r["alt_ft"] = kwargs.get("Hp", req.fixed_alt)    # use Hp key for consistency
            r["Mach"]   = kwargs.get("MN",  req.fixed_mach)
            r["PC"]     = kwargs.get("PC",  req.fixed_pc)
            results.append(r)
        except Exception as e:
            results.append({param_key: val, "error": str(e)[:200]})

    return {"sweep_param": req.sweep_param, "points": results}


# ─────────────────────────────────────────────────────────────────────────────
# Combined comparison endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/turbofan/altitudes")
def turbofan_altitudes():
    """Return the list of altitude values present in the CF34 deck."""
    return {"altitudes": ALTS_LIST}


# ─────────────────────────────────────────────────────────────────────────────
# T-s diagram data endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/turbojet/ts_diagram")
def turbojet_ts_diagram(req: TurbojetSingleRequest):
    """
    Run the turbojet model and return per-station T and s values suitable
    for plotting a T-s diagram.  Also returns isobar trace data for the
    pressure at each station so the frontend can draw isobars.
    """
    try:
        result = calc_thrust(
            eng_param=req.eng_param.model_dump(),
            eng_perf=req.eng_perf.model_dump(),
            throttle_pos=req.throttle_pos,
            alt=req.alt,
            M_i=req.M_i,
            mdot_guess=req.mdot_guess,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    stations = result["stations"]

    # Build ordered list of (station_id, label, T_K, s_JkgK, P_atm)
    # Station order along the gas path: a → 1 → 2 → 3 → 4 → 5 → 8
    ordered = ["a", "1", "2", "3", "4", "5", "8"]
    points = []
    for sid in ordered:
        if sid in stations:
            s = stations[sid]
            points.append({
                "station":  sid,
                "label":    s["label"],
                "T_K":      s["T_K"],
                "s_JkgK":   s["s_JkgK"],
                "P_atm":    s["P_atm"],
                "h_Jkg":    s["h_Jkg"],
            })

    return {
        "points":        points,
        "performance":   {k: result[k] for k in ["T", "TSFC", "mdot_fuel", "mdot_air", "SAR"]},
        "T_max_limited": result["T_max_limited"],
        "converged":     result["converged"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Engine compare endpoint — run two configs, return side-by-side
# ─────────────────────────────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    config_a: TurbojetSingleRequest
    config_b: TurbojetSingleRequest
    label_a:  str = "Config A"
    label_b:  str = "Config B"


@app.post("/api/turbojet/compare")
def turbojet_compare(req: CompareRequest):
    """
    Run two turbojet configurations at the same flight condition and return
    both results for side-by-side comparison.
    """
    results = {}
    for label, cfg in [(req.label_a, req.config_a), (req.label_b, req.config_b)]:
        try:
            r = calc_thrust(
                eng_param=cfg.eng_param.model_dump(),
                eng_perf=cfg.eng_perf.model_dump(),
                throttle_pos=cfg.throttle_pos,
                alt=cfg.alt,
                M_i=cfg.M_i,
                mdot_guess=cfg.mdot_guess,
            )
            results[label] = r
        except Exception as e:
            results[label] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Sweep CSV export helper — convert sweep result to CSV text
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/turbojet/sweep/csv")
def turbojet_sweep_csv(req: TurbojetSweepRequest):
    """
    Run a turbojet sweep and return results as a CSV string
    (for the frontend Download button).
    """
    from fastapi.responses import PlainTextResponse
    import io, csv as csvmod

    eng_param = req.eng_param.model_dump()
    eng_perf  = req.eng_perf.model_dump()

    if req.sweep_param == "altitude":
        sweep_vals = np.linspace(req.alt_start, req.alt_end, req.n_steps).tolist()
        fixed_args = {"M_i": req.fixed_mach, "throttle_pos": req.throttle_pos}
        param_key  = "alt"
    elif req.sweep_param == "mach":
        sweep_vals = np.linspace(req.mach_start, req.mach_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "throttle_pos": req.throttle_pos}
        param_key  = "M_i"
    else:
        sweep_vals = np.linspace(req.throttle_start, req.throttle_end, req.n_steps).tolist()
        fixed_args = {"alt": req.fixed_alt, "M_i": req.fixed_mach}
        param_key  = "throttle_pos"

    rows = []
    mdot_guess = req.mdot_guess
    for val in sweep_vals:
        kwargs = {param_key: val, **fixed_args, "mdot_guess": mdot_guess}
        try:
            r = calc_thrust(eng_param=eng_param, eng_perf=eng_perf, **kwargs)
            mdot_guess = r.get("mdot_air", mdot_guess) or mdot_guess
            rows.append({
                req.sweep_param: val,
                "Fn_kN":       r["T"],
                "FF_kgs":      r["mdot_fuel"],
                "TSFC_kgkNh":  r["TSFC"],
                "SAR_nmkg":    r["SAR"],
                "mdot_air_kgs":r["mdot_air"],
                "choked":      r["choked"],
                "T_max_limited": r["T_max_limited"],
                "alt_ft":      r["alt_ft"],
                "Mach":        r["Mach"],
                "throttle_pos":r["throttle_pos"],
            })
        except Exception as e:
            rows.append({req.sweep_param: val, "error": str(e)[:200]})

    buf = io.StringIO()
    if rows:
        writer = csvmod.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return PlainTextResponse(content=buf.getvalue(), media_type="text/csv")


@app.post("/api/turbofan/sweep/csv")
def turbofan_sweep_csv(req: TurbofanSweepRequest):
    """Run a turbofan sweep and return results as a CSV string."""
    from fastapi.responses import PlainTextResponse
    import io, csv as csvmod

    if req.sweep_param == "altitude":
        sweep_vals = np.linspace(req.alt_start, req.alt_end, req.n_steps).tolist()
        fixed_args = {"MN": req.fixed_mach, "PC": req.fixed_pc}
        param_key  = "Hp"                                    # interp_altMNPC uses Hp not alt
    elif req.sweep_param == "mach":
        sweep_vals = np.linspace(req.mach_start, req.mach_end, req.n_steps).tolist()
        fixed_args = {"Hp": req.fixed_alt, "PC": req.fixed_pc}
        param_key  = "MN"
    else:
        sweep_vals = np.linspace(req.pc_start, req.pc_end, req.n_steps).tolist()
        fixed_args = {"Hp": req.fixed_alt, "MN": req.fixed_mach}
        param_key  = "PC"

    rows = []
    for val in sweep_vals:
        kwargs = {param_key: val, **fixed_args}
        try:
            r = interp_altMNPC(**kwargs)                      # now receives Hp=, MN=, PC=
            r["Fn_kN"]  = round(r["Fn"]  * 0.00444822, 3)
            r["Wf_kgs"] = round(r["Wf"]  * 0.453592,   5)
            r["alt_ft"] = kwargs.get("Hp", req.fixed_alt)    # use Hp key
            r["Mach"]   = kwargs.get("MN",  req.fixed_mach)
            r["PC"]     = kwargs.get("PC",  req.fixed_pc)
            rows.append(r)
        except Exception as e:
            rows.append({param_key: val, "error": str(e)[:200]})

    buf = io.StringIO()
    if rows:
        writer = csvmod.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return PlainTextResponse(content=buf.getvalue(), media_type="text/csv")


# ─────────────────────────────────────────────────────────────────────────────
# Off-Design Performance Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/off_design/defaults")
def off_design_defaults():
    """Return default inputs and design parameters for off-design simulation."""
    return {
        "N_rel": 1.0,
        "alt": 35000.0,
        "mach": 0.8,
        "cpr_des": 8.0,
        "eta_c_des": 0.85,
        "mdot_corr_des": 20.0,
        "eta_i": 0.98,
        "eta_t": 0.88,
        "mech_loss": 0.99,
        "eta_b": 0.99,
        "dp_over_p": 0.04,
        "T_max": 1500.0,
        "eta_noz": 0.98,
        "throttle_pos": 1.0,
    }


@app.get("/api/off_design/map")
def off_design_map(
    cpr_des: float = 8.0,
    eta_c_des: float = 0.85,
    mdot_corr_des: float = 20.0,
):
    """
    Returns compressor map curves (speed lines, surge boundary, design point)
    scaled to the provided design parameters for front-end Chart.js visualization.
    """
    try:
        cmap = CompressorMap(cpr_des=cpr_des, eta_c_des=eta_c_des, mdot_corr_des=mdot_corr_des)
        return _sanitize(cmap.get_map_curves())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/off_design/single")
def off_design_single(req: OffDesignSingleRequest):
    """
    Run a single-point off-design operating condition solver with fixed geometry (A8).
    Computes matched operating point, station thermodynamics, and surge margin (%SM).
    """
    try:
        res = solve_off_design(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/off_design/sweep")
def off_design_sweep(req: OffDesignSweepRequest):
    """
    Run an off-design parameter sweep across relative shaft speed N, altitude, or Mach.
    Returns sweep points, map speed lines, and the engine operating line trajectory.
    """
    try:
        res = run_off_design_sweep(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/off_design/sweep/csv")
def off_design_sweep_csv(req: OffDesignSweepRequest):
    """Run an off-design sweep and stream the results as downloadable CSV."""
    from fastapi.responses import PlainTextResponse
    import io, csv as csvmod

    try:
        res = run_off_design_sweep(**req.model_dump())
        points = res.get("points", [])

        buf = io.StringIO()
        if points:
            fieldnames = [k for k in points[0].keys() if k not in ("stations", "emissions")]
            writer = csvmod.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(points)

        return PlainTextResponse(content=buf.getvalue(), media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────────
# 1D Mean-Line Aerodynamics Endpoints (Extension 6)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/meanline/defaults")
def meanline_defaults():
    """Return default parameters for single-stage and multistage meanline design."""
    return {
        "compressor_stage": {
            "T01": 288.15, "P01": 101325.0, "delta_T0": 35.0,
            "N_rpm": 12000.0, "r_mean": 0.28, "C_a": 160.0,
            "reaction": 0.50, "eta_stage": 0.88, "mdot": 20.0, "solidity": 1.2
        },
        "multistage": {
            "CPR": 8.0, "n_stages": 6, "T0_inlet": 288.15, "P0_inlet": 101325.0,
            "N_rpm": 12000.0, "r_mean": 0.28, "C_a": 160.0,
            "reaction": 0.50, "eta_poly": 0.88, "mdot": 20.0
        },
        "turbine_stage": {
            "T01": 1400.0, "P01": 800000.0, "delta_T0": 180.0,
            "N_rpm": 12000.0, "r_mean": 0.28, "C_a": 220.0,
            "reaction": 0.40, "eta_stage": 0.90, "solidity": 1.4
        }
    }


@app.post("/api/meanline/compressor_stage")
def meanline_compressor_stage_endpoint(req: MeanlineCompressorStageRequest):
    """Computes velocity triangles, stage loading, De Haller ratio, and Lieblein DF for a compressor stage."""
    try:
        res = solve_compressor_stage(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/meanline/multistage_compressor")
def meanline_multistage_compressor_endpoint(req: MeanlineMultistageRequest):
    """Solves stage-by-stage meanline aerodynamic stacking and annulus tapering for an axial compressor."""
    try:
        res = solve_multistage_compressor_meanline(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/meanline/turbine_stage")
def meanline_turbine_stage_endpoint(req: MeanlineTurbineStageRequest):
    """Computes velocity triangles, stage loading, and Zweifel coefficient for an axial turbine stage."""
    try:
        res = solve_turbine_stage(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────────
# Turboprop & Turboshaft Endpoints (Extension 4)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/turboprop/defaults")
def turboprop_defaults():
    """Return default flight and engine parameters for turboprop simulation."""
    return {
        "alt": 15000.0, "mach": 0.40, "CPR": 12.0, "TIT": 1400.0, "mdot_air": 10.0,
        "A8": 0.08, "prop_diameter_m": 3.2, "prop_rpm": 1200.0, "eta_i": 0.98,
        "eta_c": 0.85, "eta_b": 0.99, "dp_over_p": 0.04, "eta_hpt": 0.89, "eta_pt": 0.90,
        "eta_mech_core": 0.99, "eta_mech_pt": 0.98, "eta_gearbox": 0.985, "eta_noz": 0.95,
        "prop_eff_max": 0.84
    }


@app.post("/api/turboprop/single")
def turboprop_single(req: TurbopropSingleRequest):
    """Run single-point turboprop / turboshaft cycle simulation with power turbine extraction."""
    try:
        res = calc_turboprop_performance(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/turboprop/sweep")
def turboprop_sweep(req: TurbopropSweepRequest):
    """Run parametric sweep for turboprop across power (TIT), altitude, or Mach."""
    try:
        res = run_turboprop_sweep(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────────
# Mission Simulation Endpoints (Extension 8)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/mission/defaults")
def mission_defaults():
    """Return default mission profile and regional jet aircraft parameters."""
    return {
        "cruise_alt_ft": 35000.0,
        "cruise_mach": 0.78,
        "cruise_distance_nm": 1200.0,
        "payload_kg": 9000.0,
        "fuel_load_kg": None,
        "engine_base_tsfc": 16.5,
    }


@app.post("/api/mission/simulate")
def mission_simulate(req: MissionSimulateRequest):
    """Simulate a complete 6-segment flight mission and generate payload-range envelope."""
    try:
        res = run_mission_simulation(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────────
# Fast Surrogate Model Endpoints (Extension 7)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/surrogate/defaults")
def surrogate_defaults():
    """Return default query parameters for fast surrogate model evaluation."""
    return {
        "alt_ft": 35000.0,
        "mach": 0.80,
        "throttle": 1.00,
        "CPR": 14.0,
        "TIT_K": 1450.0,
    }


@app.post("/api/surrogate/predict")
def surrogate_predict(req: SurrogatePredictRequest):
    """Instantaneous (< 1 ms) multi-output cycle prediction via pure NumPy RBF surrogate."""
    try:
        res = GLOBAL_SURROGATE.predict_point(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/surrogate/surface")
def surrogate_surface(req: SurrogateSurfaceRequest):
    """Rapid (< 5 ms) 2D grid response surface or 1D response curve generation."""
    try:
        metric_names = {"thrust_kN", "thrust", "tsfc", "air_flow_kg_s", "fuel_flow_kg_s", "EI_NOx_g_kg"}
        if req.y_param in metric_names or req.x_min is not None or req.fixed_params is not None:
            res = GLOBAL_SURROGATE.generate_1d_curve(
                x_param=req.x_param,
                y_param=req.y_param,
                x_min=req.x_min,
                x_max=req.x_max,
                n_points=req.n_points or 30,
                fixed_alt=req.fixed_alt,
                fixed_mach=req.fixed_mach,
                fixed_throttle=req.fixed_throttle,
                fixed_cpr=req.fixed_cpr,
                fixed_tit=req.fixed_tit,
            )
        else:
            param_map = {"altitude_m": "alt_ft", "altitude": "alt_ft", "cpr": "CPR", "tit_K": "TIT_K", "tit": "TIT_K"}
            x_p = param_map.get(req.x_param, req.x_param)
            y_p = param_map.get(req.y_param, req.y_param)
            res = GLOBAL_SURROGATE.generate_2d_surface(
                x_param=x_p,
                y_param=y_p,
                fixed_alt=req.fixed_alt,
                fixed_mach=req.fixed_mach,
                fixed_throttle=req.fixed_throttle,
                fixed_cpr=req.fixed_cpr,
                fixed_tit=req.fixed_tit,
                grid_res=req.grid_res,
            )
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Electric Propulsion Endpoints (Extension 5)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/hybrid/defaults")
def hybrid_defaults():
    """Return default parameters for hybrid electric powertrain and aircraft simulation."""
    return {
        "architecture": "parallel",
        "shaft_power_req_kW": 2000.0,
        "hybrid_power_ratio_HP": 0.25,
        "battery_mass_kg": 1200.0,
        "battery_soc": 0.85,
        "turbogen_rated_kW": 1500.0,
        "mission": {
            "cruise_alt_m": 9144.0,
            "cruise_mach": 0.72,
            "cruise_dist_km": 900.0,
            "payload_kg": 6500.0,
            "battery_mass_kg": 1800.0,
            "specific_energy_Wh_kg": 300.0,
            "takeoff_hybrid_ratio": 0.35,
            "climb_hybrid_ratio": 0.20,
            "cruise_hybrid_ratio": 0.05,
            "descent_hybrid_ratio": 0.0,
        },
        "powertrain": DEFAULT_POWERTRAIN,
    }


@app.post("/api/hybrid/single")
def hybrid_single(req: HybridSingleRequest):
    """Evaluate instantaneous hybrid electric powertrain states (parallel, series, or turboelectric)."""
    try:
        res = evaluate_single_hybrid_point(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/hybrid/mission")
def hybrid_mission(req: HybridMissionRequest):
    """Simulate a 6-phase hybrid flight mission with battery SoC tracking and conventional comparison."""
    try:
        res = run_hybrid_mission_simulation(**req.model_dump())
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


@app.post("/api/hybrid/sweep")
def hybrid_sweep(req: HybridSweepRequest):
    """Run parametric trade studies (hybrid ratio, battery specific energy, or stage length)."""
    try:
        kwargs = {
            "cruise_dist_km": req.cruise_dist_km,
            "specific_energy_Wh_kg": req.specific_energy_Wh_kg,
            "battery_mass_kg": req.battery_mass_kg,
        }
        res = run_hybrid_trade_study(
            study_type=req.study_type,
            architecture=req.architecture,
            n_points=req.n_points,
            base_mission_kwargs=kwargs,
        )
        return _sanitize(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

