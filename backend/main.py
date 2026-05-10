"""
main.py  —  Gas Turbine Engine Simulator  —  FastAPI Backend
Serves both the turbojet (Cantera-based) and turbofan (CF34 deck interpolation) models.
"""

from __future__ import annotations
import traceback
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import numpy as np

from turbojet import calc_thrust, DEFAULT_ENG_PARAM, DEFAULT_ENG_PERF
from turbofan import interp_altMNPC, get_envelope, ENVELOPE, KEY_OUTPUTS, DF_CF34

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
    eta_i:      float = Field(DEFAULT_ENG_PERF["eta_i"],      description="Inlet adiabatic efficiency")
    CPR:        float = Field(DEFAULT_ENG_PERF["CPR"],         description="Compressor pressure ratio")
    eta_c:      float = Field(DEFAULT_ENG_PERF["eta_c"],       description="Compressor isentropic efficiency")
    eta_b:      float = Field(DEFAULT_ENG_PERF["eta_b"],       description="Combustor efficiency")
    dp_over_p:  float = Field(DEFAULT_ENG_PERF["dp_over_p"],  description="Combustor pressure loss fraction")
    max_f:      float = Field(DEFAULT_ENG_PERF["max_f"],       description="Max fuel fraction (stoich)")
    min_f:      float = Field(DEFAULT_ENG_PERF["min_f"],       description="Min fuel fraction (stoich)")
    V_nominal:  float = Field(DEFAULT_ENG_PERF["V_nominal"],  description="Combustor nominal flow velocity [m/s]")
    T_max:      float = Field(DEFAULT_ENG_PERF["T_max"],       description="Max combustor temperature (TIT limit) [K]")
    eta_t:      float = Field(DEFAULT_ENG_PERF["eta_t"],       description="Turbine isentropic efficiency")
    mech_loss:  float = Field(DEFAULT_ENG_PERF["mech_loss"],  description="Mechanical efficiency")
    eta_noz:    float = Field(DEFAULT_ENG_PERF["eta_noz"],     description="Nozzle adiabatic efficiency")


class TurbojetSingleRequest(BaseModel):
    eng_param:    TurbojetEngineParam = Field(default_factory=TurbojetEngineParam)
    eng_perf:     TurbojetEnginePerf  = Field(default_factory=TurbojetEnginePerf)
    throttle_pos: float = Field(1.0,     ge=0.5, le=1.0,    description="Throttle position (0.5–1.0)")
    alt:          float = Field(35000.0, ge=0,   le=65000,  description="Altitude [ft]")
    M_i:          float = Field(0.8,     ge=0.0, le=0.9,    description="Mach number")
    mdot_guess:   float = Field(20.0,    gt=0,              description="Initial mass-flow guess [kg/s]")


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


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "online",
        "models": ["turbojet", "turbofan_cf34"],
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
        return result
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

    return {"sweep_param": req.sweep_param, "points": results}


# ─────────────────────────────────────────────────────────────────────────────
# Turbofan (CF34) endpoints
# ─────────────────────────────────────────────────────────────────────────────

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
    alts = sorted(DF_CF34["alt"].unique().tolist())
    return {"altitudes": alts}


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
