"""
main.py  —  Gas Turbine Engine Simulator  —  FastAPI Backend
Serves both the turbojet (Cantera-based) and turbofan (CF34 deck interpolation) models.
"""

from __future__ import annotations
import traceback
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import json

import numpy as np

from turbojet import calc_thrust, DEFAULT_ENG_PARAM, DEFAULT_ENG_PERF
from turbofan import interp_altMNPC, get_envelope, ENVELOPE, KEY_OUTPUTS, DF_CF34, ALTS_LIST
from physics_turbofan import calc_turbofan, DEFAULT_TF_PARAM, DEFAULT_TF_PERF
from off_design import CompressorMap, solve_off_design, run_off_design_sweep

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
    """Recursively replace float nan/inf with None so JSON stays RFC 8259 compliant."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
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


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "online",
        "models": ["turbojet", "physics_turbofan", "turbofan_cf34", "off_design"],
        "docs":   "/docs",
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
