# Gas Turbine Engine Simulator — Local Setup Guide

## What this app is
A fullstack web application combining:
- **Turbojet** — a physics-first, Cantera-powered single-spool turbojet simulation (ported from the `flight-test-engineering/Gas-Turbine-Propulsion` YouTube series)
- **CF34 Turbofan** — a pre-computed GE CF34-10E engine deck interpolated in real-time over altitude / Mach / power

---

## Project structure

```
gas-turbine-app/
├── backend/
│   ├── main.py              FastAPI application — all API endpoints
│   ├── turbojet.py          Turbojet engine model (Cantera-based)
│   ├── turbofan.py          CF34 deck loader + trilinear interpolator
│   ├── engine_helper.py     Inlet, compressor, combustor, turbine, nozzle functions
│   ├── ISA_module.py        ICAO ISA atmosphere + airspeed conversions
│   └── requirements.txt     Python dependencies
├── frontend/
│   └── index.html           Single-file React app (no build step required)
├── data/
│   └── CF34_deck_v4.csv     Pre-computed turbofan engine deck (from pyCycle)
├── start.sh                 Unix/macOS startup script
├── start.bat                Windows startup script
└── SETUP_GUIDE.md           This file
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or higher | 3.11 recommended |
| pip | latest | `pip install --upgrade pip` |
| conda (optional) | latest | Easiest way to install Cantera on Windows |
| A modern browser | Chrome, Firefox, Edge | For the frontend |

---

## Step-by-step setup

### 1. Clone / download the repository

```bash
git clone https://github.com/flight-test-engineering/Gas-Turbine-Propulsion.git
# or just unzip the project folder
```

### 2. Create a Python virtual environment

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install Cantera

Cantera is the thermochemistry library used by the turbojet model. It is available on pip for most platforms, but **conda is the easiest method**, especially on Windows.

#### Option A — pip (recommended for macOS / Linux)
```bash
pip install cantera==3.0.0
```

#### Option B — conda (recommended for Windows, or if pip fails)
```bash
conda install -c conda-forge cantera=3.0.0
```

> **Troubleshooting Cantera on Windows:**
> If `pip install cantera` fails, try:
> 1. Install Miniconda: https://docs.anaconda.com/miniconda/
> 2. `conda create -n gasturbine python=3.11`
> 3. `conda activate gasturbine`
> 4. `conda install -c conda-forge cantera`
> 5. Continue from step 4 below using this conda environment

### 4. Install remaining Python dependencies

```bash
cd gas-turbine-app/backend
pip install -r requirements.txt
```

> **Note:** If you installed Cantera via conda, skip `cantera` from requirements and run:
> ```bash
> pip install fastapi==0.111.0 uvicorn[standard]==0.30.1 pydantic==2.7.1 numpy==1.26.4 pandas==2.2.2 python-multipart==0.0.9
> ```

### 5. Verify the Cantera installation

```bash
python -c "import cantera as ct; print('Cantera OK, version:', ct.__version__)"
```

Expected output: `Cantera OK, version: 3.0.0`

### 6. Confirm the CF34 deck is in place

```bash
ls ../data/CF34_deck_v4.csv   # should print the file path
```

If the file is missing, copy it from the repository:
```bash
cp /path/to/Gas-Turbine-Propulsion/turbofan/CF34_deck_v4.csv ../data/
```

### 7. Start the backend API

```bash
# From the backend/ directory:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 8. Open the frontend

Open `gas-turbine-app/frontend/index.html` directly in your browser:

- **macOS:** `open frontend/index.html`
- **Windows:** double-click `frontend/index.html` in Explorer
- **Linux:** `xdg-open frontend/index.html`

The green **● API online** indicator in the top-left will confirm the backend is reachable.

---

## Quick start scripts

If you have the environment set up, use the provided scripts:

**macOS / Linux:**
```bash
chmod +x start.sh    # only needed once — makes the script executable
./start.sh
```

**Windows:**
```cmd
start.bat
```

---

## Fastest setup path (conda — all platforms)

If you have Miniconda or Anaconda installed, this is the single-command setup:

```bash
# From the project root:
conda env create -f conda_env.yml
conda activate gasturbine
./start.sh          # macOS/Linux
# or: start.bat    # Windows
```

The `conda_env.yml` file pins exact versions of all dependencies including Cantera.

---

## API Documentation (interactive)

With the backend running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:**      http://localhost:8000/redoc

All endpoints, request schemas, and response formats are documented there.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'cantera'`
You are running Python from a different environment than where Cantera was installed.  
Check: `which python` / `where python` — make sure the virtual environment is activated.

### `FileNotFoundError: CF34_deck_v4.csv`
The turbofan module looks for the CSV at:
- `gas-turbine-app/data/CF34_deck_v4.csv` (primary)
- `gas-turbine-app/backend/CF34_deck_v4.csv` (fallback)

Copy the file to either location.

### `CORS error` in browser console
This happens when the backend is not running. Start uvicorn (step 7) before opening the frontend.

### Turbojet simulation is very slow (>60 s per point)
The multi-stage compressor convergence loop (up to 5,000 iterations) is CPU-bound.  
For sweeps, keep `n_steps ≤ 10` during exploration. The turbofan deck is always near-instant.

### `nDodecane_Reitz.yaml not found`
This file ships with Cantera 3.0+. If you see this error, your Cantera version is too old.  
Run: `pip install --upgrade cantera`

### Browser shows `● API offline` but uvicorn is running
Check that uvicorn is bound to `0.0.0.0` (not `127.0.0.1`) and port 8000.  
The frontend hardcodes `http://localhost:8000` — make sure nothing else is on that port.

---

## Typical runtime expectations

| Operation | Expected time |
|---|---|
| Turbojet — single point (SL, M=0) | ~5–15 s |
| Turbojet — single point (35,000 ft, M=0.8) | ~15–40 s |
| Turbojet — altitude sweep, 10 points | ~2–5 min |
| Turbofan CF34 — single point | < 50 ms |
| Turbofan CF34 — altitude sweep, 20 points | < 1 s |

---

## Engine model origins

| Model | Source |
|---|---|
| Turbojet | `episd_10_limit_T.ipynb` — Flight Test Engineering YouTube series |
| ISA module | `ISA_module.py` — same repository |
| CF34 turbofan deck | `CF34_deck_v4.csv` — generated by pyCycle / OpenMDAO (NASA) |
| CF34 interpolation | `episod_5_results_and_lookup_table.ipynb` |
