# Gas Turbine Engine Simulator

A fullstack web application for interactive gas turbine engine performance simulation, combining two engine models from the [Flight Test Engineering](https://www.youtube.com/@FlightTestEngineering) YouTube series.

---

## Engine models

| Model | Type | Method | Speed |
|---|---|---|---|
| **Turbojet** | Generic single-spool | Cantera thermochemistry, iterative convergence | 10–40 s / point |
| **CF34-10E Turbofan** | GE CF34-10E, high-bypass | Pre-computed pyCycle/OpenMDAO deck, trilinear interpolation | < 50 ms / point |

---

## Features

- **Single-point simulation** — compute thrust, TSFC, fuel flow, and station data at any flight condition
- **T–s diagram** — automatic Brayton cycle plot from Cantera station entropy data (turbojet)
- **Parameter sweeps** — altitude, Mach, or throttle sweeps with live charts
- **CSV export** — download any sweep result as a spreadsheet-ready CSV
- **Station data table** — T, P, Mach, and entropy at every engine station
- **Reset to defaults** — one click to restore factory parameters
- **Sweep error reporting** — failed convergence points are listed, not silently dropped

---

## Project structure

```
gas-turbine-app/
├── backend/
│   ├── main.py              FastAPI application (12 endpoints)
│   ├── turbojet.py          Turbojet model — Cantera-based, iterative
│   ├── turbofan.py          CF34 deck loader + trilinear interpolator
│   ├── engine_helper.py     Inlet / compressor / combustor / turbine / nozzle
│   ├── ISA_module.py        ICAO ISA atmosphere + airspeed conversions
│   └── requirements.txt
├── frontend/
│   └── index.html           Single-file React app (no build step needed)
├── data/
│   └── CF34_deck_v4.csv     Pre-computed CF34-10E engine deck
├── conda_env.yml            Conda environment (recommended for Windows)
├── start.sh                 macOS/Linux one-click startup
├── start.bat                Windows one-click startup
├── SETUP_GUIDE.md           Full installation and troubleshooting guide
└── README.md                This file
```

---

## Quickstart

### macOS / Linux
```bash
# 1. Create and activate environment (one time)
conda env create -f conda_env.yml
conda activate gasturbine

# 2. Start the backend
./start.sh

# 3. Open the frontend
open frontend/index.html
```

### Windows
```cmd
REM 1. Create environment (one time)
conda env create -f conda_env.yml
conda activate gasturbine

REM 2. Start the backend
start.bat

REM 3. Open frontend\index.html in your browser
```

See **SETUP_GUIDE.md** for full installation instructions, troubleshooting, and runtime expectations.

---

## API

With the backend running, interactive API docs are available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:**       http://localhost:8000/redoc

### Endpoint summary

| Method | Endpoint | Description |
|---|---|---|
| GET  | `/` | Health check |
| GET  | `/api/turbojet/defaults` | Default engine parameters |
| POST | `/api/turbojet/single` | Single-point turbojet simulation |
| POST | `/api/turbojet/sweep` | Turbojet parameter sweep |
| POST | `/api/turbojet/sweep/csv` | Sweep result as downloadable CSV |
| POST | `/api/turbojet/ts_diagram` | T–s diagram station data |
| POST | `/api/turbojet/compare` | Side-by-side two-config comparison |
| GET  | `/api/turbofan/envelope` | CF34 deck envelope and output keys |
| GET  | `/api/turbofan/altitudes` | Available altitude values in deck |
| POST | `/api/turbofan/single` | Single-point CF34 interpolation |
| POST | `/api/turbofan/sweep` | CF34 parameter sweep |
| POST | `/api/turbofan/sweep/csv` | CF34 sweep result as CSV |

---

## Source notebooks

| File | Episode | Content |
|---|---|---|
| `episd_10_limit_T.ipynb` | Ep 10 | Turbojet with TIT limiter — source of `turbojet.py` |
| `ISA_module.py` | Ep 2–3 | ISA atmosphere and airspeed conversions |
| `episod_5_results_and_lookup_table.ipynb` | Turbofan Ep 5 | CF34 deck interpolation — source of `turbofan.py` |
| `CF34_deck_v4.csv` | Turbofan Ep 4–5 | pyCycle/OpenMDAO output (bug #96 data excluded) |

---

## References

- Mattingly, J.D. — *Elements of Propulsion: Gas Turbines and Rockets*
- ICAO Doc 7488 — *Manual of the ICAO Standard Atmosphere*
- NASA pyCycle — https://github.com/OpenMDAO/pyCycle
- Cantera — https://cantera.org
- Flight Test Engineering YouTube — https://www.youtube.com/@FlightTestEngineering
