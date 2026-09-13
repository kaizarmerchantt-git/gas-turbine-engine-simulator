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
| **Physics-based Turbofan** | Dual-spool, physics-based | Dual mass-flow convergence loop + Cantera chemistry | 10–60 s / point |
| **Off-Design Component Matching** | Scalable axial map, 1D matching | Pure Python Brent root matching + fixed throat A₈ + Surge Margin | < 0.5 s / point |
| **GE CF34-10E Turbofan** | High-bypass, data-driven | Pre-computed pyCycle/OpenMDAO deck, trilinear interpolation | < 50 ms / point |
| **1D Mean-Line Aerodynamics** | Velocity triangles & stage sizing | Euler turbomachinery, De Haller diffusion limit, Zweifel loading | < 20 ms / stage |
| **Turboprop & Turboshaft Cycle** | Shaft power & propeller thrust | Gas generator core + free power turbine + variable prop efficiency | 5–25 s / point |
| **Mission Analysis & Fuel Burn** | 6-phase flight mission profile | Coupled aircraft drag polar + numerical fuel burn + payload-range | < 50 ms / mission |
| **Response Surface Surrogate** | Multi-output fast predictor | 2nd-order regularized polynomial with interaction cross-terms | < 0.2 ms / point |
| **Hybrid Electric Propulsion** | Series / Parallel / Turboelectric | Coupled GT cycle + electrical loss chain + battery SoC tracking | < 30 ms / mission |

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
EI        = (X_species × MW_species) / (FAR × MW_mixture) × 1000  [g/kg fuel]
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

### `off_design.py` — Off-Design Component Matching & Compressor Map (Extension 1)

Solves true off-design throttled engine performance using scalable component maps and 1D aerodynamic matching:

1. **Compressor Map Parameterization ($\beta$-lines)**:
   - Axial compressor performance curves digitized across relative speeds $N_{\text{rel}} \in [0.60, 0.70, 0.80, 0.90, 1.00, 1.05]$.
   - Unambiguous $\beta$-coordinate transformation ($\beta \in [0, 1]$, where $\beta=0$ is choke and $\beta=1$ is surge boundary).
   - Pressure ratio curves modeled with cubic S-curves; isentropic efficiency parameterized via parabolic peak profiles.
   - Dynamic scaling factors to user design targets: $(CPR_{\text{des}}, \eta_{c,\text{des}}, \dot{m}_{\text{corr,des}})$.

2. **Zero-Dependency Brent Root Finder**:
   - Pure Python and NumPy Brent root finder (`brent_root()`) with sign-change bracket discovery and bisection fallback.
   - Requires no SciPy dependency, enabling lightweight deployment across any Python environment.

3. **1D Component Matching Equations**:
   - **Shaft Power Balance**: Turbine work output matches compressor work demand: $W_c = W_t \cdot \eta_m$.
   - **Mass Continuity**: Mass flow is conserved through the core gas path: $\dot{m}_8 = \dot{m}_2 + \dot{m}_f$.
   - **Fixed Physical Throat Area**: Fixed exhaust nozzle area $A_8$ enforces that the cycle throat area calculated from gas thermodynamics must match physical hardware: $A_{8,\text{calc}}(\beta) = A_8$ (residual $< 0.1\%$).

4. **Dynamic Surge Margin**:
   - Calculates Surge Margin ($\%SM$) relative to the instantaneous operating line:
     $$\%SM = \left( \frac{PR_{\text{surge}} / \dot{m}_{\text{corr,surge}}}{PR_{\text{op}} / \dot{m}_{\text{corr,op}}} - 1 \right) \times 100\%$$
   - Color-coded safety status: Stable ($> 15\%$), Marginal ($10\% - 15\%$), or Critical Surge ($< 10\%$).

### `meanline.py` — 1D Mean-Line Aerodynamic Stage Design (Extension 6)

Bridging 0D thermodynamic station models and physical 3D blading hardware:
1. **Euler Turbomachinery Equation**:
   $$\Delta h_0 = U \cdot (C_{\theta 2} - C_{\theta 1}) = U \cdot \Delta C_\theta$$
2. **Kinematic Velocity Triangles**:
   - Resolves absolute velocities ($\vec{C} = C_a \hat{x} + C_\theta \hat{\theta}$) and relative velocities ($\vec{W} = \vec{C} - \vec{U}$).
   - Flow angles: $\alpha = \arctan(C_\theta / C_a)$, $\beta = \arctan(W_\theta / C_a)$.
   - Local Mach numbers: absolute Mach $M = C / \sqrt{\gamma R T}$ and relative Mach $M_{\text{rel}} = W / \sqrt{\gamma R T}$.
3. **Aerodynamic Loading & Diffusion Limits**:
   - Work coefficient $\psi = \Delta h_0 / U^2$, flow coefficient $\phi = C_a / U$, and degree of reaction $R = \Delta h_{\text{rotor}} / \Delta h_0$.
   - **De Haller Criterion**: Enforces $W_2 / W_1 \ge 0.72$ to prevent boundary layer separation and stall across compressor rotor blades.
   - **Lieblein Diffusion Factor ($DF$)**: Evaluates blade surface deceleration and boundary layer thickening ($DF \le 0.45$ for modern conservative design).
4. **Multi-Stage Casing Annulus Sizing**:
   - Computes density increase $\rho_0(s)$ across stages and sizes annulus area $A(s) = \dot{m} / (\rho(s) C_a)$.
   - Predicts blade height tapering ($h_s$) and hub-to-tip radius ratio ($r_h / r_t$) progression.
5. **Axial Turbine Stage Aerodynamics**:
   - Evaluates expansion ratio, total work extraction, reaction, and **Zweifel loading coefficient** ($\psi_z \approx 0.8 - 1.0$ for optimal solidity without separation).

### `turboprop.py` — Turboprop & Turboshaft Cycle Variant (Extension 4)

Simulates shaft-power producing gas turbines for propeller-driven and rotorcraft applications:
1. **Core Work Matching & Free Power Turbine**:
   - Gas generator core: Compressor work demand $W_c$ is balanced by High Pressure Turbine (HPT) work extraction: $W_{\text{hpt}} = W_c / \eta_m$.
   - Free Power Turbine (PT): Extracts remaining enthalpy to generate mechanical shaft power:
     $$P_{\text{shaft}} = \dot{m}_{\text{core}} \cdot \Delta h_{0,\text{pt}} \cdot \eta_{\text{gear}} \cdot \eta_m$$
2. **Propeller Kinematics & Residual Jet Thrust**:
   - Propeller efficiency dynamically parameterized by flight Mach: $\eta_{\text{prop}}(M) = \eta_{\text{max}} \cdot \left[1 - 0.15 \cdot \left(\frac{M - M_{\text{opt}}}{0.5}\right)^2\right]$.
   - Propeller thrust: $F_{\text{prop}} = \frac{P_{\text{shaft}} \cdot \eta_{\text{prop}}}{V_{\text{flight}}}$.
   - Residual jet thrust from exhaust nozzle: $F_{\text{jet}} = \dot{m} (V_8 - V_0) + A_8 (p_8 - p_0)$.
   - Equivalent Shaft Horsepower: $\text{ESHP} = \text{SHP} + \frac{F_{\text{jet}} [\text{lbf}]}{2.5}$.
3. **Cantera Equilibrium Combustion**:
   - Real-gas fuel/air equilibrium with `nDodecane_Reitz.yaml` calculating PSFC [$\text{kg}/(\text{kW}\cdot\text{h})$] and emission indices ($EI_{\text{NOx}}, EI_{\text{CO}}, EI_{\text{CO}_2}$).

### `mission.py` — Flight Mission Profile & Fuel Burn Integration (Extension 8)

Connects 0D cycle models to real aircraft flight operations:
1. **6-Phase Standard Mission Profile**:
   - Standard sequence: Taxi-Out (15 min) $\to$ Takeoff $\to$ Climb $\to$ Cruise $\to$ Descent $\to$ 45-min Loiter (FAA/EASA reserves).
2. **Coupled Aircraft Drag Polar**:
   - Lift coefficient: $C_L = \frac{2 W}{\rho V^2 S_{\text{wing}}}$.
   - Parabolic drag polar with wave drag rise: $C_D = C_{D0} + K \cdot C_L^2 + C_{D,\text{wave}}(M)$.
   - Required engine thrust: $T_{\text{req}} = \frac{D + W \sin\gamma}{N_{\text{engines}}}$.
3. **Numerical Fuel Burn Integration**:
   - Solves $\Delta W = \int \dot{m}_f \, dt$ with mass conservation update $W_{k+1} = W_k - \Delta W_k$.
4. **Payload-Range Diagram Envelope**:
   - Solves the classic 3-point Breguet range envelope:
     - Point A: Maximum structural payload capacity.
     - Point B: MTOW limit with maximum fuel tank capacity.
     - Point C: Zero-payload ferry range.

### `surrogate.py` — Fast Response Surface Surrogate Model (Extension 7)

Provides sub-millisecond cycle queries for real-time optimization and flight simulation:
1. **Formulation**:
   - 2nd-order polynomial response surface with full pairwise interaction cross-terms:
     $$\mathbf{p}(\mathbf{x}) = \left[1, x_1, \dots, x_5, x_1^2, \dots, x_5^2, x_1 x_2, \dots, x_4 x_5\right]^T \in \mathbb{R}^{21}$$
   - Ridge regularized least-squares regression: $\mathbf{W} = (\mathbf{P}^T \mathbf{P} + \lambda \mathbf{I})^{-1} \mathbf{P}^T \mathbf{Y}$.
2. **Multi-Output Mapping**:
   - Maps 5D operating vector $(\text{Alt}, M, \text{Throttle}, CPR, TIT)$ simultaneously to: Net Thrust [kN], TSFC [g/(kN·s)], Mass Airflow [kg/s], Fuel Flow [kg/s], and $EI_{\text{NOx}}$ [g/kg].
3. **Speed & Stability**:
   - Single-point prediction latency $< 0.2\text{ ms}$ (pure NumPy vectorized linear algebra).
   - Strict physical monotonicity preserved across flight throttle and TIT ranges.

### `hybrid.py` — Hybrid Electric Propulsion Integration (Extension 5)

Couples gas turbine thermodynamic cycles with electrical powertrains to evaluate fuel burn and carbon emission reduction:
1. **Three Core System Architectures**:
   - **Parallel Hybrid**: Mechanical shaft coupling of Gas Turbine and Electric Motor ($P_{\text{req}} = P_{\text{GT}} + P_{\text{motor}}$). Hybrid power ratio $H_P = P_{\text{motor}} / P_{\text{req}}$. Enables core downsizing and improved cruise thermal efficiency.
   - **Series Hybrid**: Gas turbine operates exclusively as a constant-efficiency Turbogenerator decoupled from propulsors, feeding a DC bus. Electric motors drive distributed propulsors. Battery supplies peak demand or absorbs excess generator power.
   - **Turboelectric**: Direct electrical distribution from turbogenerator to electric propulsors without battery weight ($M_{\text{batt}} = 0$). Eliminates mechanical shafting and enables Boundary Layer Ingestion (BLI).
2. **Electrical Powertrain Loss Chain**:
   - Component efficiencies: $\eta_{\text{motor}} = 95\%$, $\eta_{\text{inv}} = 98\%$, $\eta_{\text{gen}} = 96\%$, $\eta_{\text{dist}} = 99\%$, $\eta_{\text{batt}} = 98\%$.
   - Component power densities: Motor ($5\text{ kW/kg}$), Inverter ($15\text{ kW/kg}$), Generator ($6\text{ kW/kg}$).
3. **Battery State of Charge (SoC) Dynamics**:
   - Stored capacity $E_{\text{batt}} = M_{\text{batt}} \cdot e_{\text{batt}} / 1000$ [kWh].
   - Dynamic integration: $\Delta SoC = -P_{\text{batt}} \cdot \Delta t / E_{\text{batt}}$.
   - C-rate tracking and automatic 20% health reserve protection cutoff.
4. **Multi-Phase Mission Energy Audit**:
   - Simulates 6 phases: 100% electric ground taxi $\to$ Takeoff boost ($H_P = 0.35$) $\to$ Climb assist ($H_P = 0.20$) $\to$ Cruise ($H_P = 0.05$) $\to$ Descent $\to$ 45-min Loiter reserves.
   - Outputs block fuel savings [%], net $\text{CO}_2$ emissions reduction [kg], and primary energy [MJ] comparison vs non-hybrid baseline.
5. **Parametric Trade Studies**:
   - Sweeps $H_P$, battery specific energy ($180 - 550\text{ Wh/kg}$), and stage length to identify the breakeven mission range.

### `main.py` — FastAPI backend

Defines Pydantic request/response schemas with range validation for all inputs. The 26 endpoints cover single-point simulation, parameter sweeps, T–s diagram data, side-by-side comparison, off-design map and operating lines, and CSV export for all engine models. CORS is open (`*`) for local development.

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

- **Single-point simulation** — thrust, TSFC, SAR, fuel flow, and full station data across single-spool turbojet, dual-spool turbofan, and CF34 models
- **Dual-Spool Physics Turbofan** — first-principles 2-spool solver with Fan, HPC, HPT, LPT, and independent core and bypass choked/unchoked nozzles
- **Off-Design Performance & Component Matching (Extension 1)** — 1D matching solver with shaft power balance ($W_c = W_t \cdot \eta_m$), mass conservation, fixed throat geometry ($A_8$), and pure Python/NumPy Brent root finding
- **Interactive Compressor Performance Maps** — scalable multi-speed axial compressor maps with $\beta$-coordinate parameterization, dynamic Surge Margin ($\%SM$) computation, and engine operating line tracing
- **1D Mean-Line Aerodynamic Stage Design (Extension 6)** — velocity triangles ($U, C_a, C_\theta, W_a, W_\theta$), Euler work equation, De Haller ratio ($W_2/W_1 \ge 0.72$), Lieblein diffusion factor, and multi-stage annulus tapering
- **Turboprop & Turboshaft Cycle Variant (Extension 4)** — gas generator core, free power turbine work extraction, propeller kinematics ($\eta_{\text{prop}}(M)$), shaft power (SHP/ESHP), and residual jet thrust
- **Mission Flight Profile & Aircraft Fuel Burn (Extension 8)** — 6-phase mission simulation (Taxi $\to$ Takeoff $\to$ Climb $\to$ Cruise $\to$ Descent $\to$ 45-min Loiter), coupled aircraft polar drag matching, and Breguet payload-range envelope curves
- **High-Speed Response Surface Surrogate (Extension 7)** — sub-millisecond (< 0.2 ms) multi-output prediction layer utilizing regularized 2nd-order polynomial models with interaction cross-terms
- **T–s diagrams** — single-spool Brayton cycle and dual-stream (core + bypass) cycle diagrams with Cantera entropy data
- **Parameter sweeps** — shaft speed ($N/N_{\text{des}}$), altitude, Mach, throttle, BPR, CPR, and FPR sweeps with live Chart.js visualizations
- **Binary bisection TIT limiter** — $O(\log N)$ logarithmic bisection limiter enforcing combustor temperature limits without performance cliffs
- **Side-by-side comparison** — two engine configurations at the same flight condition
- **Emissions tracking** — calculates Emission Index for NOx, CO, and CO2 and classifies combustion state
- **CSV export** — any sweep as a downloadable spreadsheet
- **Automated test suite** — 26 pytest tests covering ISA, compressible flow, turbojet, turbofan, off-design matching, compressor maps, and all 26 API endpoints
- **REST API** — 26 documented endpoints, interactive Swagger UI at `/docs`

---

## Project structure

```
gas-turbine-app/
├── backend/
│   ├── main.py                   FastAPI — 41 API endpoints + Pydantic schemas
│   ├── meanline.py               1D mean-line aerodynamic stage design & annulus sizing
│   ├── turboprop.py              Turboprop & turboshaft Brayton cycle solver with free PT
│   ├── mission.py                Aircraft mission fuel burn simulation & payload-range curves
│   ├── surrogate.py              Fast 2nd-order response surface surrogate model (< 0.2 ms)
│   ├── off_design.py             Off-design matching solver, compressor maps & surge margin
│   ├── turbojet.py               Turbojet model — mass-flow convergence + bisection TIT limiter
│   ├── physics_turbofan.py       Dual-spool turbofan model — two-spool work balance + dual nozzle solver
│   ├── turbofan.py               CF34 deck loader + trilinear interpolation
│   ├── engine_helper.py          Inlet / compressor / combustor / turbine / nozzle functions
│   ├── ISA_module.py             ICAO ISA atmosphere + airspeed conversions
│   ├── test_advanced_modules.py  Automated test suite for advanced extensions (8 tests)
│   ├── test_off_design.py        Automated test suite for off-design matching & maps (10 tests)
│   ├── test_physics.py           Automated test suite for baseline models & endpoints (16 tests)
│   └── requirements.txt
├── frontend/
│   └── index.html                Single-file React app with 9 panels, Chart.js, SVGs & maps
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

### Running Tests

Run the full automated test suite:

```bash
pytest -v backend/test_physics.py backend/test_off_design.py backend/test_advanced_modules.py backend/test_hybrid.py
```

Full instructions in **[SETUP_GUIDE.md](SETUP_GUIDE.md)**.

---

## API endpoints

With the backend running, interactive docs at http://localhost:8000/docs

| Method | Endpoint | Description |
|---|---|---|
| GET  | `/` | Health check |
| GET  | `/api/turbojet/defaults` | Default turbojet parameters |
| POST | `/api/turbojet/single` | Single-point turbojet simulation |
| POST | `/api/turbojet/sweep` | Turbojet parameter sweep (alt, Mach, throttle) |
| POST | `/api/turbojet/sweep/csv` | Turbojet sweep result as CSV |
| POST | `/api/turbojet/ts_diagram` | Turbojet T–s diagram station data |
| POST | `/api/turbojet/compare` | Side-by-side two-config comparison |
| GET  | `/api/physics_turbofan/defaults` | Default physics turbofan parameters |
| POST | `/api/physics_turbofan/single` | Single-point physics turbofan simulation |
| POST | `/api/physics_turbofan/sweep` | Physics turbofan sweep (alt, Mach, throttle, BPR, CPR, FPR) |
| POST | `/api/physics_turbofan/sweep/csv` | Physics turbofan sweep result as CSV |
| POST | `/api/physics_turbofan/ts_diagram` | Physics turbofan dual-stream T–s diagram data |
| GET  | `/api/turbofan/envelope` | CF34 deck envelope info |
| GET  | `/api/turbofan/altitudes` | Available altitudes in deck |
| POST | `/api/turbofan/single` | Single-point CF34 interpolation |
| POST | `/api/turbofan/sweep` | CF34 parameter sweep |
| POST | `/api/turbofan/sweep/csv` | CF34 sweep result as CSV |
| GET  | `/api/off_design/defaults` | Default off-design simulation inputs |
| GET  | `/api/off_design/map` | Scaled compressor map curves (speed lines & surge boundary) |
| POST | `/api/off_design/single` | 1D matched off-design cycle solver with Surge Margin |
| POST | `/api/off_design/sweep` | Off-design parameter sweep & operating line construction |
| POST | `/api/off_design/sweep/csv` | Off-design operating sweep result as CSV |
| GET  | `/api/meanline/defaults` | Default meanline compressor stage inputs |
| POST | `/api/meanline/compressor_stage` | 1D compressor stage kinematics, triangles & De Haller |
| POST | `/api/meanline/multistage_compressor` | Multi-stage compressor stacking & annulus tapering |
| POST | `/api/meanline/turbine_stage` | 1D turbine stage aerodynamics & Zweifel loading |
| GET  | `/api/turboprop/defaults` | Default turboprop cycle inputs |
| POST | `/api/turboprop/single` | Single-point turboprop cycle (SHP, ESHP, prop thrust, PSFC) |
| POST | `/api/turboprop/sweep` | Turboprop parameter sweep (Mach, altitude, PR, TIT) |
| GET  | `/api/mission/defaults` | Default mission simulation inputs |
| POST | `/api/mission/simulate` | 6-phase flight mission fuel burn & payload-range envelope |
| GET  | `/api/surrogate/defaults` | Default surrogate model query vector |
| POST | `/api/surrogate/predict` | Real-time surrogate evaluation (< 0.2 ms latency) |
| POST | `/api/surrogate/surface` | 2D response surface generator across any input slice |
| GET  | `/api/hybrid/defaults` | Default hybrid electric powertrain parameters |
| POST | `/api/hybrid/single` | Single operating point hybrid state (power split, SoC, fuel) |
| POST | `/api/hybrid/mission` | 6-phase hybrid flight mission simulation & baseline comparison |
| POST | `/api/hybrid/sweep` | Parametric trade study sweep (H_P, battery Wh/kg, distance) |

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
- Steady-state off-design component matching and compressor surge margin estimation (Extension 1)
- Teaching and learning cycle thermodynamics

Not appropriate for:
- Detailed 3D aerodynamic blade design (requires CFD / mean-line solvers)
- Transient dynamic control simulation (requires shaft inertia and spool acceleration models)
- Production engine certification or regulatory compliance
