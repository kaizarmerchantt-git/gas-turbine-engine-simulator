# Gas Turbine Engine Simulator

An interactive, web-based **0D thermodynamic cycle simulator** for gas turbine engines. Built as a learning project on top of the [Flight Test Engineering](https://www.youtube.com/@FlightTestEngineering) YouTube series and their open-source [Gas-Turbine-Propulsion](https://github.com/flight-test-engineering/Gas-Turbine-Propulsion) repository.

> **What is 0D modelling?**
> A zero-dimensional cycle model computes averaged thermodynamic states — temperature, pressure, Mach number, specific entropy, specific enthalpy — at discrete stations along the engine gas path, with no spatial resolution. No flow field, no blade geometry, no radial or axial distributions. This is the standard tool for preliminary design: you use it to verify that a proposed cycle (CPR, TIT, efficiency targets) is thermodynamically consistent and to estimate thrust and fuel burn across the flight envelope before any component geometry is defined.

---

## What it simulates

### Engine models

| Model | Type | Method | Speed |
|---|---|---|---|
| **Generic Turbojet** | Single-spool, physics-based | Cantera real-gas thermochemistry + iterative station convergence | 5–40 s / point |
| **GE CF34-10E Turbofan** | High-bypass, data-driven | Pre-computed pyCycle/OpenMDAO deck, trilinear interpolation | < 50 ms / point |

### Gas path stations

```
Ambient (a) ──▶ Inlet entry (1) ──▶ Compressor face (2) ──▶ Compressor exit (3)
             ──▶ Combustor exit (4) ──▶ Turbine exit (5) ──▶ Nozzle exit (8)
```

At every station the code tracks: T [K], P [Pa], P [atm], Mach number, specific entropy s [J/(kg·K)], specific enthalpy h [J/kg].

---

## How the code works — in detail

### `ISA_module.py` — ICAO Standard Atmosphere

Implements the ICAO ISA for the **troposphere** (0–36 089 ft, lapse rate −6.5 K/km) and **stratosphere** (36 089–65 617 ft, isothermal at 216.65 K). Computes pressure ratio δ, temperature ratio θ, and density ratio σ using the standard hydrostatic equations. Vectorised with `np.vectorize` so it works on both scalars and arrays.

The airspeed conversion suite covers every combination: CAS ↔ Mach, TAS ↔ EAS, TAS ↔ Mach, CAS ↔ TAS — all referenced to the ISA sea-level speed of sound and pressure.

### `engine_helper.py` — Component-level thermodynamics

All component functions take [Cantera](https://cantera.org) `Solution` objects for gas state. The fuel model is **n-dodecane (C₁₂H₂₆)** via the `nDodecane_Reitz.yaml` reaction mechanism — a well-validated surrogate for Jet-A/kerosene.

#### Isentropic helpers
`get_p`, `get_T`, `get_Ts`, `get_ps` convert between static and stagnation quantities using the standard compressible flow relations. `get_gamma`, `get_R`, `get_a` pull instantaneous properties from the Cantera gas object — important because γ varies with temperature and composition.

#### `iterate_inlet` — Inlet convergence
Models a duct section with an adiabatic efficiency η_i (1.0 = isentropic, < 1.0 = losses).

The physics: total enthalpy is conserved, so `h + V²/2 = const`. At efficiency < 1, stagnation pressure recovery is penalised:
```
p0_out = p_in × (1 + η_i × V_in²/(2 × cp × T_in))^(γ/(γ−1))
```
The iteration: guess V_out → compute T_out from energy balance → update gas state → recompute density → recompute V_out = mdot/(ρ×A) → repeat until |V_guess − V_computed| < 0.01 m/s. This is a fixed-point iteration on exit velocity.

#### `multi_stage_compressor` — Axial multi-stage compression
The challenge: simply applying `CPR^(1/N)` per stage gives equal pressure ratio per stage, but **not** equal temperature rise — because cp and γ change with temperature as the gas heats up. Real axial compressors are designed for approximately equal stage loading (ΔT per stage).

The solution is an iterative "shifter" array: earlier stages are loaded slightly more, later stages slightly less. The code runs up to 5,000 outer iterations, adjusting the per-stage pressure multiplier each iteration, until the maximum ΔT between adjacent stages stops decreasing. For each stage:
```
p0_out = p0_in × CR_stage × multiplier[stage]
T0_out = T0_in/η_c × ((p0_out/p0_in)^((γ−1)/γ) − 1) + T0_in   [isentropic + efficiency]
```
Static T and P are recovered from the stagnation values using the local Mach number. Total compressor work W_c = Σ cp × ΔT across all stages.

#### `iterate_combustor` — Pre-combustion state
Sets the static T and P at the combustor exit *before* combustion, based on:
- Stagnation temperature carried over from compressor exit
- A fractional total-pressure loss dp/p (typically 6%)
- A prescribed nominal flow velocity inside the combustor (sets the kinetic energy term)

After this function returns, the caller sets the fuel-air mixture composition (`set_equivalence_ratio`) then calls `gas.equilibrate("HP")` — Cantera solves the **full chemical equilibrium at constant enthalpy and pressure**, giving the post-combustion T and species concentrations (CO₂, H₂O, N₂, O₂, and trace species). This is the most physically rigorous part of the model.

#### TIT limiter (in `turbojet.py`)
After equilibration, if `gas[4].T > T_max`, the equivalence ratio is decremented by 0.001 and the combustion is re-run. This mimics a closed-loop temperature limiting controller. The flag `T_max_limited = True` is returned in the results.

#### `multi_stage_turbine` — Power extraction
The turbine must extract exactly `W_c / η_mechanical` of specific work from the hot gas, distributed equally across N stages. For each stage:
```
T0_out_prime = T0_in − W_per_stage / (cp × η_t)           [uncorrected exit total temp]
p0_out       = p0_in × (T0_out_prime / T0_in)^(γ/(γ−1))   [isentropic pressure drop]
T0_out       = T0_in − η_t × (T0_in − T0_out_prime)        [actual exit total temp with efficiency]
```
Static conditions are again recovered from stagnation at the exit Mach number.

#### `calc_nozzle` — Choking and thrust
Determines whether the nozzle is choked (sonic throat) by comparing ambient pressure to the critical pressure ratio:
```
p_crit_ratio = 1 / (1 − (1/η_noz) × (γ−1)/(γ+1))^(γ/(γ−1))
```
**Choked case** (p_amb ≤ p0/p_crit): throat is sonic, exit pressure > ambient, thrust includes a pressure term:
```
F = (V_exit − V_flight) + (A_throat/mdot) × (p_exit − p_amb)
```
**Unchoked case**: gas expands fully to ambient pressure:
```
V_exit = sqrt(2 × cp × (T0 − T_amb))
F = V_exit − V_flight
```

### `turbojet.py` — Full engine integration and convergence

`calc_thrust()` integrates all component functions in a **mass-flow convergence loop**:

1. Initialise all stations at ambient T and P.
2. March the gas through: inlet (×2) → compressor → combustor → turbine → nozzle.
3. The nozzle independently computes what mass flow it passes (`mdot_noz = ρ × V × A_throat`).
4. Compare `mdot_noz` against `current_mdot`. If `|diff| > 0.1 kg/s`, update the guess and restart from step 2.
5. Repeat up to 10 outer iterations (typically converges in 3–5).

Why does mass flow need to converge? Because the nozzle area is fixed. The throat condition sets mdot as a function of upstream T and P — which themselves depend on what mass flow was assumed at the inlet. The loop finds the self-consistent solution.

Post-convergence metrics:
```
mdot_fuel = (mixture_fraction / η_combustor) × mdot_air
TSFC      = (mdot_fuel / mdot_air) / F_specific          [kg/(kN·h)]
SAR       = V_true / mdot_fuel                           [nm/kg, specific air range]
```

### `turbofan.py` — CF34-10E deck interpolation

The `CF34_deck_v4.csv` was generated by NASA's **pyCycle/OpenMDAO** thermodynamic cycle tool — it covers a grid of (altitude ft, Mach, PC) points, where PC (power code) ranges from 0.55 (idle) to 1.0 (TOGA). At each grid point the deck contains: Fn [lbf], Fg, F_ram, TSFC, BPR, fuel flow, OPR, FAR, N1, N2, turbine inlet temperature (TIT), HPC exit temperature, LPT exit temperature, fan total pressure, HPC total pressure.

The 19 000 ft rows are removed at load time — they contain a known numerical anomaly from pyCycle issue #96.

For any query point (Hp, MN, PC):
1. Find the nearest lower/upper altitude values in the table (boundary clamping for out-of-range queries).
2. For each altitude bracket, find the Mach bracket.
3. **Interpolate in PC** (power) at all four (alt_low/high × Mach_low/high) corners.
4. **Interpolate in Mach** for each altitude bracket.
5. **Interpolate in altitude** between the two Mach-interpolated rows.

This is a standard trilinear interpolation — three sequential 1D linear interpolations — giving a complete set of engine parameters in under 50 ms.

### `main.py` — FastAPI backend

Defines Pydantic request/response schemas with range validation for all inputs. The 12 endpoints cover single-point simulation, parameter sweeps, T–s diagram data, side-by-side comparison, and CSV export for both engine models. CORS is open (`*`) for local development.

Sweep endpoints chain single-point calls sequentially, carrying the last converged mass flow forward as the initial guess for the next point — this warm-starting cuts convergence iterations on sweeps significantly.

### `index.html` — Frontend

Self-contained React app (loaded from CDN, no build step). Parameter forms feed POST requests to the backend. Results are charted with Chart.js. The `● API online` indicator polls `/` every few seconds.

---

## T–s diagram — reading it

The T–s diagram plots temperature vs. specific entropy at each station. It gives a direct visual of the Brayton cycle efficiency:

- **a → 2** (inlet): nearly isentropic if η_i ≈ 1; slight rightward drift means pressure loss
- **2 → 3** (compression): temperature rises steeply; the rightward drift from the ideal vertical line represents isentropic efficiency losses (η_c < 1)
- **3 → 4** (combustion): large entropy increase — heat addition at ~constant pressure; this is the irreversible combustion process
- **4 → 5** (turbine expansion): temperature drops; again, deviation from vertical = turbine losses (η_t < 1)
- **5 → 8** (nozzle): further expansion; kinetic energy converts to thrust

The area enclosed by the cycle is proportional to net specific work. The gap between the real cycle curves and the ideal vertical compression/expansion lines is a direct visual measure of component irreversibility.

---

## Features

- **Single-point simulation** — thrust, TSFC, SAR, fuel flow, and full station data
- **T–s diagram** — Brayton cycle from Cantera entropy data
- **Parameter sweeps** — altitude, Mach, or throttle with live charts
- **Side-by-side comparison** — two engine configurations at the same flight condition
- **TIT limiter** — automatic fuel cutback if turbine inlet temperature exceeds limit
- **CSV export** — any sweep as a downloadable spreadsheet
- **REST API** — 12 documented endpoints, interactive Swagger UI at `/docs`

---

## Project structure

```
gas-turbine-app/
├── backend/
│   ├── main.py              FastAPI — all 12 API endpoints + Pydantic schemas
│   ├── turbojet.py          Turbojet model — mass-flow convergence loop
│   ├── turbofan.py          CF34 deck loader + trilinear interpolation
│   ├── engine_helper.py     Inlet / compressor / combustor / turbine / nozzle functions
│   ├── ISA_module.py        ICAO ISA atmosphere + airspeed conversions
│   └── requirements.txt
├── frontend/
│   └── index.html           Single-file React app (no build step)
├── data/
│   └── CF34_deck_v4.csv     Pre-computed CF34-10E engine deck (pyCycle)
├── notebooks/               Source Jupyter notebooks from the YT series
├── conda_env.yml            Conda environment (recommended for Windows)
├── start.sh / start.bat     One-click startup scripts
├── SETUP_GUIDE.md           Full install + troubleshooting guide
└── README.md
```

---

## Quickstart

```bash
# macOS / Linux
conda env create -f conda_env.yml
conda activate gasturbine
./start.sh
open frontend/index.html

# Windows
conda env create -f conda_env.yml
conda activate gasturbine
start.bat
# open frontend\index.html in browser
```

Full instructions in **[SETUP_GUIDE.md](SETUP_GUIDE.md)**.

---

## API endpoints

With the backend running, interactive docs at http://localhost:8000/docs

| Method | Endpoint | Description |
|---|---|---|
| GET  | `/` | Health check |
| GET  | `/api/turbojet/defaults` | Default engine parameters |
| POST | `/api/turbojet/single` | Single-point turbojet simulation |
| POST | `/api/turbojet/sweep` | Turbojet parameter sweep |
| POST | `/api/turbojet/sweep/csv` | Sweep result as CSV |
| POST | `/api/turbojet/ts_diagram` | T–s diagram station data |
| POST | `/api/turbojet/compare` | Side-by-side two-config comparison |
| GET  | `/api/turbofan/envelope` | CF34 deck envelope info |
| GET  | `/api/turbofan/altitudes` | Available altitudes in deck |
| POST | `/api/turbofan/single` | Single-point CF34 interpolation |
| POST | `/api/turbofan/sweep` | CF34 parameter sweep |
| POST | `/api/turbofan/sweep/csv` | CF34 sweep result as CSV |

---

## Credits

This project is built directly on top of:

### 🎬 Flight Test Engineering — YouTube series
The turbojet thermodynamic model, ISA module, and CF34 deck interpolation are all ported from their Jupyter notebooks. If you are learning propulsion from scratch, this channel is one of the best free resources available.

- **YouTube:** https://www.youtube.com/@FlightTestEngineering
- **Source repo:** https://github.com/flight-test-engineering/Gas-Turbine-Propulsion

| File | Source notebook | Episode |
|---|---|---|
| `turbojet.py`, `engine_helper.py` | `episd_10_limit_T.ipynb` | Ep 10 — turbojet with TIT limiter |
| `ISA_module.py` | `ISA_module.py` in source repo | Ep 2–3 |
| `turbofan.py` | `episod_5_results_and_lookup_table.ipynb` | Turbofan Ep 5 |
| `CF34_deck_v4.csv` | Generated by pyCycle/OpenMDAO | Turbofan Ep 4–5 |

### Dependencies
- **[Cantera](https://cantera.org)** — thermochemistry and chemical equilibrium
- **[NASA pyCycle / OpenMDAO](https://github.com/OpenMDAO/pyCycle)** — source of `CF34_deck_v4.csv`
- **[FastAPI](https://fastapi.tiangolo.com)** — backend API framework
- Mattingly, J.D. — *Elements of Propulsion: Gas Turbines and Rockets*
- ICAO Doc 7488 — *Manual of the ICAO Standard Atmosphere*

---

## Scope and limitations

Appropriate for:
- Preliminary cycle trade studies (CPR, TIT, efficiency budgets)
- Understanding Brayton cycle physics before geometry is defined
- Estimating thrust and fuel burn across the flight envelope
- Teaching and learning cycle thermodynamics

Not appropriate for:
- Detailed component design (requires 1D mean-line or higher fidelity)
- Off-design or transient simulation
- Production engine certification or regulatory compliance
