# AETHER-X: Gas Turbine Engine Simulator (v0.5.0)

Interactive 0D thermodynamic gas turbine engine cycle simulator and flight mission analysis application.

This release updates the project from the initial v0.1 prototype to v0.5.0. In this update, we integrated NASA-standard real-gas thermodynamic polynomials, added multi-spool cycle calculations, and cleaned up the single-page HUD interface for smoother parameter sweeps.

The simulation and matching routines are currently undergoing active validation and testing against standard reference data. Planning for a v1.0 release is underway.

---

## Origin & Credits

This project was built upon the open-source [Gas-Turbine-Propulsion](https://github.com/flight-test-engineering/Gas-Turbine-Propulsion) repository created by the [Flight Test Engineering](https://www.youtube.com/@FlightTestEngineering) team, with thermodynamic formulations referencing [NASA pyCycle](https://github.com/OpenMDAO/pyCycle) and [Cantera](https://cantera.org).

---

## Propulsion Domains & Current Capabilities

The suite provides 9 integrated cycle calculation modules available via the REST API and the web interface:

1. **Turbojet (`/api/turbojet/single`)**: Single-spool turbojet thermodynamic station calculations, net thrust, specific fuel consumption, and ICAO LTO emissions estimation.
2. **Turbofan Physics (`/api/turbofan/physics`)**: Dual-spool turbofan cycle matching using real-gas enthalpy balances across high-pressure and low-pressure spools.
3. **CF34 Engine Deck (`/api/turbofan/point`)**: 4D multidimensional flight envelope interpolation based on empirical CF34 performance tables.
4. **Compressor Off-Design (`/api/off-design/match`)**: Scaled axial compressor map operating lines, mass-flow matching, and surge margin tracking.
5. **Mean-Line Aerodynamics (`/api/meanline/compressor`)**: Stage-by-stage velocity triangle kinematics, flow angles, and stage loading for axial compressors and turbines.
6. **Turboprop / Turboshaft (`/api/turboprop/single`)**: Gas generator core coupled to a free power turbine with variable-pitch propeller thrust calculations.
7. **Mission Analysis (`/api/mission/simulate`)**: 6-phase flight profile mission integrator (Taxi, Takeoff, Climb, Cruise, Descent, Landing) with coupled aircraft drag polar sizing.
8. **Cycle Surrogate Model (`/api/surrogate/predict`)**: Fast polynomial response surface predictor for rapid design space exploration.
9. **Hybrid-Electric Propulsion (`/api/hybrid/simulate`)**: Parallel and series hybrid-electric cycle calculations with battery state-of-charge tracking.

---

## Interface & HUD Features

- **Obsidian Telemetry HUD**: Single-page browser interface displaying real-time gas path station telemetry (Stations 0 to 8: Temperature, Pressure, Mach, Specific Enthalpy, Entropy).
- **Brayton Cycle Display**: Real-time Temperature-Entropy (T-s) diagram with closed isobaric loops.
- **Vernier Sliders**: Real-time throttle and atmospheric sliders (Mach 0.0 to 1.8, Altitude 0 to 60,000 ft).
- **Unit Toggle**: One-click switching between SI Metric and Imperial units without page reloads.
- **Telemetry Export**: Direct CSV and JSON data exports for mission phases and thermodynamic stations.

---

## Quick Start

### 1. Requirements
- Python 3.10 or higher
- Standard modern browser (Chrome, Edge, Firefox)

### 2. Setup
Clone the repository and install dependencies:

```bash
git clone https://github.com/kaizarmerchantt-git/gas-turbine-engine-simulator.git
cd gas-turbine-engine-simulator
pip install -r backend/requirements.txt
```

### 3. Launching
On Windows:
```cmd
start.bat
```

On Linux or macOS:
```bash
chmod +x start.sh
./start.sh
```

The script initializes the FastAPI backend and opens the interface at `http://localhost:8000/`.

To stop the server:
```cmd
stop.bat
```

---

## API Documentation

When the backend is running, the interactive OpenAPI Swagger documentation is available at:
`http://localhost:8000/docs`
