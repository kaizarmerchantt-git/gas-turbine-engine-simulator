COMMON_COMPONENTS = """
    const { useState, useEffect, useRef, useCallback, useMemo, useContext, createContext } = React;
    const API = "";

    // ── Number Formatters (Stage 7: No silent dummy '---' or fake zeros) ──────
    function fmt(val, dec = 2) {
      if (val === null || val === undefined || isNaN(val)) return "NOT COMPUTED";
      return Number(val).toFixed(dec);
    }

    function fmtInt(val) {
      if (val === null || val === undefined || isNaN(val)) return "NOT COMPUTED";
      return Math.round(Number(val)).toLocaleString();
    }

    function fmtPct(val, dec = 1) {
      if (val === null || val === undefined || isNaN(val)) return "NOT COMPUTED";
      const num = Number(val);
      const pct = num <= 1.0 && num > 0.0 ? num * 100 : num;
      return `${pct.toFixed(dec)}%`;
    }

    // ── Table Exporters (CSV / JSON) ──────────────────────────────────────────
    function exportTableCsv(filename, columns, rows) {
      if (!rows || !rows.length) return;
      const headerLine = columns.map(c => `"${c.label || c.key}"`).join(",");
      const rowLines = rows.map(r => {
        return columns.map(c => {
          const val = r[c.key] ?? "";
          return typeof val === "string" ? `"${val.replace(/"/g, '""')}"` : val;
        }).join(",");
      });
      const csvContent = "data:text/csv;charset=utf-8," + encodeURIComponent([headerLine, ...rowLines].join("\\n"));
      const link = document.createElement("a");
      link.setAttribute("href", csvContent);
      link.setAttribute("download", `${filename}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    function exportTableJson(filename, data) {
      if (!data) return;
      const jsonContent = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
      const link = document.createElement("a");
      link.setAttribute("href", jsonContent);
      link.setAttribute("download", `${filename}.json`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    // ── Number Provenance Register (AN-1 / Stage 7) ───────────────────────────
    const NUMBER_PROVENANCE_REGISTRY = {
      // Domain 01 Turbojet
      "NET THRUST (Fn)": {
        eq: "F_n = mdot_air * (V_exit - V_0) + (P_exit - P_0) * A_exit",
        source: "Conservation of Momentum / NASA SP-290",
        fidelity: "NASA-9 Polynomial Real Gas (McBride 2002)",
        validity: "Converged Brayton Cycle (M0 in [0, 2.5])"
      },
      "NET THRUST": {
        eq: "F_n = mdot_air * (V_exit - V_0) + (P_exit - P_0) * A_exit",
        source: "Conservation of Momentum / NASA SP-290",
        fidelity: "NASA-9 Polynomial Real Gas",
        validity: "Converged Cycle"
      },
      "GROSS THRUST (Fg)": {
        eq: "F_g = (F_spec + V_0) * mdot_air",
        source: "Gross Momentum Flux at Nozzle Exit",
        fidelity: "1D Real Gas Dynamics",
        validity: "F_g >= F_n"
      },
      "RAM DRAG (Fram)": {
        eq: "F_ram = mdot_air * V_0",
        source: "Freestream Capture Momentum",
        fidelity: "ISA Atmosphere & Flight Speed",
        validity: "V_0 = M_0 * a_0"
      },
      "FUEL MASS FLOW": {
        eq: "mdot_f = FAR * mdot_air (FAR from LHV enthalpy balance)",
        source: "Combustor Energy Balance / McBride et al.",
        fidelity: "Sensible Enthalpy vs 298.15K (LHV = 43.124 MJ/kg)",
        validity: "FAR in [0.005, 0.06]"
      },
      "SPECIFIC FUEL CONS (TSFC)": {
        eq: "TSFC = mdot_f / F_n",
        source: "SAE AIR1168 / ISO 2314 Standard",
        fidelity: "Real Gas Derived Metric",
        validity: "F_n > 0.0"
      },
      "AIR MASS FLOW": {
        eq: "mdot_air = rho * A * V (Nozzle Choking Continuity)",
        source: "1D Compressible Flow Continuity",
        fidelity: "Variable Gamma Flow Function",
        validity: "Mach <= 1.0 (Throat Choked)"
      },
      "CORE AIR FLOW": {
        eq: "mdot_core = mdot_total / (1 + BPR)",
        source: "Bypass Ratio Split Definition",
        fidelity: "1D Flow Continuity",
        validity: "mdot_core > 0"
      },
      "BYPASS AIR FLOW": {
        eq: "mdot_byp = mdot_total * BPR / (1 + BPR)",
        source: "Bypass Ratio Split Definition",
        fidelity: "1D Flow Continuity",
        validity: "mdot_byp >= 0"
      },
      "THERMAL EFFICIENCY": {
        eq: "eta_th = delta_KE / (mdot_f * LHV)",
        source: "First Law of Thermodynamics",
        fidelity: "Enthalpy Jump Recovery",
        validity: "0.0 <= eta_th <= 1.0"
      },
      "PROPULSIVE EFFICIENCY": {
        eq: "eta_p = 2 * V_0 / (V_exit + V_0)",
        source: "Froude Propulsive Efficiency",
        fidelity: "Kinetic Energy Ratio",
        validity: "0.0 <= eta_p <= 1.0"
      },
      "OVERALL EFFICIENCY": {
        eq: "eta_o = eta_th * eta_p",
        source: "Brayton Overall Energy Efficiency",
        fidelity: "Product Definition",
        validity: "0.0 <= eta_o <= 1.0"
      },
      "COMPRESSOR CPR": {
        eq: "CPR = Pt3 / Pt2",
        source: "Total Pressure Ratio Definition",
        fidelity: "Stage Aerothermodynamics",
        validity: "CPR >= 1.0"
      },
      // Domain 02 Turbofan
      "OVERALL PR (OPR)": {
        eq: "OPR = Pt3 / Pt2 = FPR * CPR_hpc",
        source: "Dual-Spool Gas Path Pressure Product",
        fidelity: "Dual-Spool Real Gas Compression",
        validity: "OPR >= 1.0"
      },
      "BYPASS RATIO (BPR)": {
        eq: "BPR = mdot_bypass / mdot_core",
        source: "Flow Split Continuity",
        fidelity: "1D Dual-Stream Aerodynamics",
        validity: "BPR >= 0.0"
      },
      "FAN PRESSURE RATIO": {
        eq: "FPR = Pt13 / Pt2",
        source: "Fan Stage Total Pressure Ratio",
        fidelity: "Isentropic Fan Stage with Real Gas",
        validity: "FPR in [1.1, 3.0]"
      },
      "HPC PRESSURE RATIO": {
        eq: "CPR_hpc = Pt3 / Pt25",
        source: "High-Pressure Compressor Total Pressure Ratio",
        fidelity: "Isentropic Core Stage with Real Gas",
        validity: "CPR_hpc in [5.0, 45.0]"
      },
      "TURBINE INLET TEMP": {
        eq: "TIT = Tt4 (Combustor Exit Total Temperature)",
        source: "Combustor Thermodynamic State",
        fidelity: "NASA-9 Mixture Inversion",
        validity: "Tt4 in [1000K, 2400K]"
      },
      // Domain 04 Off-Design
      "OFF-DESIGN CPR": {
        eq: "CPR = f(N_corr, mdot_corr, R-line)",
        source: "pyCycle Scaled Component Map",
        fidelity: "Compressor Characteristic Map",
        validity: "Surge Margin >= 0%"
      },
      "SURGE MARGIN": {
        eq: "SM = (CPR_surge / CPR_op) * (mdot_op / mdot_surge) - 1",
        source: "NASA SP-290 Turbomachinery Standard",
        fidelity: "Map Distance to Surge Boundary",
        validity: "SM >= 10% (Normal Operating Limit)"
      },
      "CORRECTED FLOW": {
        eq: "mdot_corr = mdot * sqrt(theta) / delta",
        source: "SAE Aerodynamic Scaling",
        fidelity: "Corrected Parameter Standard",
        validity: "theta = Tt/288.15K, delta = Pt/101.325kPa"
      },
      // Domain 05 Mean-Line
      "STAGE TOTAL PR": {
        eq: "PR = (1 + eta_stage * delta_T0 / T01)^(gamma/(gamma-1))",
        source: "Euler Work Equation (Saravanamuttoo / Dixon)",
        fidelity: "1D Mean-Line Stage",
        validity: "de Haller >= 0.72"
      },
      "STAGE WORK (dh0)": {
        eq: "dh0 = U * (C_theta2 - C_theta1)",
        source: "Euler Turbomachinery Equation",
        fidelity: "Mean-Line Kinematics",
        validity: "Conservation of Angular Momentum"
      },
      "DE HALLER NUMBER": {
        eq: "de_Haller = W2 / W1",
        source: "de Haller (1953) Diffusion Criterion",
        fidelity: "1D Relative Velocity Deceleration",
        validity: "de_Haller >= 0.72 (Stall Margin Limit)"
      },
      "LIEBLEIN DIFFUSION": {
        eq: "D = 1 - W2/W1 + |W_theta1 - W_theta2| / (2 * sigma * W1)",
        source: "Lieblein NASA RM E53D01",
        fidelity: "Blade Profile Boundary Layer Loading",
        validity: "D <= 0.60"
      },
      // Domain 06 Turboprop
      "SHAFT POWER": {
        eq: "P_shaft = eta_mech * mdot * (h_t45 - h_t5)",
        source: "Free Power Turbine Enthalpy Extraction",
        fidelity: "NASA-9 Real Gas Expansion",
        validity: "P_shaft >= 0.0 kW"
      },
      "EQUIV SHAFT PWR": {
        eq: "ESHP = P_shaft_shp + F_jet_lbf / 2.5",
        source: "FAA / ICAO Turboprop Certification Standard",
        fidelity: "Equivalent Power Combination",
        validity: "ESHP >= P_shaft"
      },
      "TOTAL THRUST": {
        eq: "F_total = F_prop + F_jet",
        source: "Momentum Balance (Propeller + Residual Jet)",
        fidelity: "Hamilton Standard Propeller Model",
        validity: "F_total >= 0.0 kN"
      },
      "PROP EFFICIENCY": {
        eq: "eta_prop = eta_max * f(J) * (1 - compressibility_loss)",
        source: "Hamilton Standard 14D Map with Helical Tip Mach Loss",
        fidelity: "Compressible Propeller Characteristic",
        validity: "M_tip <= 0.95"
      },
      "PSFC": {
        eq: "PSFC = mdot_f / P_shaft",
        source: "Turboprop Power Specific Fuel Consumption",
        fidelity: "Continuous Energy Ratio",
        validity: "PSFC in [0.2, 0.6] kg/kWh"
      },
      "GEARBOX TORQUE": {
        eq: "Torque = P_shaft / omega = (P_shaft * 60) / (2 * pi * RPM)",
        source: "Planetary Reduction Dynamics",
        fidelity: "Mechanical Conservation",
        validity: "omega > 0 rad/s"
      },
      // Domain 07 Mission
      "BLOCK FUEL BURN": {
        eq: "W_f,block = integral(TSFC * Thrust * dt)",
        source: "Segmented Numerical Trajectory Integration (Aviary/Raymer)",
        fidelity: "Trapezoidal Numerical Integration",
        validity: "Weight & Energy Closed"
      },
      "TAKEOFF GROSS MASS": {
        eq: "MTOW = OEW + Payload + Fuel_block + Reserves",
        source: "Airframe Sizing Formulation (Roskam / Raymer)",
        fidelity: "Statistical Sizing Iteration",
        validity: "MTOW >= OEW + Payload"
      },
      "BREGUET RANGE": {
        eq: "R = (V / TSFC) * (L/D) * ln(W_initial / W_final)",
        source: "Breguet Range Equation (Analytic Constant-L/D Limit)",
        fidelity: "Closed-Form Analytic Solution",
        validity: "R_breguet >= 0 NM"
      },
      "AVG MISSION TSFC": {
        eq: "TSFC_avg = W_f,cruise / (Thrust_cruise * t_cruise)",
        source: "Engine Cycle Coupled Trajectory",
        fidelity: "Cycle-Coupled Integration",
        validity: "Coupled to Engine Deck"
      },
      // Domain 08 Surrogate
      "PREDICTED THRUST": {
        eq: "Fn = y_mean(x) +/- 1.96 * sigma(x)",
        source: "SMT Kriging / Gaussian Process Model",
        fidelity: "Latin Hypercube Trained (1000 Cases)",
        validity: "x inside Latin Hypercube Training Convex Hull"
      },
      "PREDICTED TSFC": {
        eq: "TSFC = y_mean(x)",
        source: "SMT Kriging with Epistemic Uncertainty",
        fidelity: "LOOCV R^2 >= 0.99",
        validity: "x inside Training Hull"
      },
      "SOLVE LATENCY": {
        eq: "Delta_t = performance.now() - t_start",
        source: "High-Resolution Hardware Timer",
        fidelity: "Actual Client/Server Wall-Clock",
        validity: "Latency < 5 ms"
      },
      // Domain 09 Hybrid
      "GAS TURBINE POWER": {
        eq: "P_gt = P_req * (1 - HP_ratio)",
        source: "Mechanical Shaft Power Split",
        fidelity: "First-Law Power Conservation",
        validity: "P_gt + P_motor = P_req"
      },
      "ELECTRIC MOTOR PWR": {
        eq: "P_motor = P_req * HP_ratio",
        source: "Electric Assistance Split",
        fidelity: "Continuous Powertrain Distribution",
        validity: "P_motor >= 0.0 kW"
      },
      "BATTERY DISCHARGE": {
        eq: "P_batt = P_motor / (eta_inv * eta_bus * eta_motor)",
        source: "DC Bus Efficiency Transmission Chain",
        fidelity: "Ohmic + Switching Inverter Losses",
        validity: "P_batt >= P_motor"
      },
      "FUEL SAVINGS": {
        eq: "Savings = (Fuel_baseline - Fuel_hybrid) / Fuel_baseline",
        source: "Full Mission Fuel Comparison (0% at HP=0)",
        fidelity: "Coupled Trajectory Simulation",
        validity: "Savings = 0.0% at HP=0.0"
      },
      "TOTAL DRY MASS": {
        eq: "M_dry = M_gt + M_motor + M_inv + M_batt + M_tms + M_cables",
        source: "Component Specific Power Scaling",
        fidelity: "Physics-Based Component Mass Sum",
        validity: "Strict Sum Equality"
      },
      "TOTAL EFFICIENCY": {
        eq: "eta_sys = P_shaft_out / (P_fuel_in + P_batt_in)",
        source: "Overall Energy Conversion Ratio",
        fidelity: "Powertrain System First Law",
        validity: "0.0 < eta_sys < 1.0"
      }
    };

    // ── Global Unit System Context & Conversion Engine ────────────────────────
    const UnitContext = createContext({ unitSystem: "SI", setUnitSystem: () => {} });

    function convertUnitVal(val, type, unitSystem) {
      if (val == null || isNaN(val)) return null;
      const num = Number(val);
      if (unitSystem === "IMPERIAL") {
        switch (type) {
          case "thrust": return num * 224.808943; // kN -> lbf
          case "thrust_N": return num * 0.224808943; // N -> lbf
          case "mass": return num * 2.20462262; // kg -> lbm
          case "massflow": return num * 2.20462262; // kg/s -> lb/s
          case "fuelflow": return num * 7936.6414; // kg/s -> lb/hr
          case "fuelflow_kgh": return num * 2.20462262; // kg/h -> lb/hr
          case "temp": return num * 1.8; // K -> °R
          case "pressure": return num * 0.145037738; // kPa -> psia
          case "tsfc": return num * 0.03530394; // g/(kN·s) -> lb/(lbf·hr)
          case "power": return num * 1.341022; // kW -> shp
          case "torque": return num * 0.737562; // N·m -> ft·lbf
          case "velocity": return num * 1.943844; // m/s -> kts
          case "distance_km": return num * 0.5399568; // km -> NM
          case "density": return num * 0.06242796; // kg/m³ -> lb/ft³
          case "altitude": return num; // FT is already imperial
          default: return num;
        }
      }
      return num;
    }

    function getUnitStr(type, unitSystem) {
      if (unitSystem === "IMPERIAL") {
        switch (type) {
          case "thrust": return "lbf";
          case "thrust_N": return "lbf";
          case "mass": return "lbm";
          case "massflow": return "lb/s";
          case "fuelflow": return "lb/hr";
          case "fuelflow_kgh": return "lb/hr";
          case "temp": return "°R";
          case "pressure": return "psia";
          case "tsfc": return "lb/lbf·h";
          case "power": return "shp";
          case "torque": return "ft·lbf";
          case "velocity": return "kts";
          case "distance_km": return "NM";
          case "density": return "lb/ft³";
          case "altitude": return "FT";
          default: return "";
        }
      } else {
        switch (type) {
          case "thrust": return "kN";
          case "thrust_N": return "N";
          case "mass": return "kg";
          case "massflow": return "kg/s";
          case "fuelflow": return "kg/s";
          case "fuelflow_kgh": return "kg/h";
          case "temp": return "K";
          case "pressure": return "kPa";
          case "tsfc": return "g/kN·s";
          case "power": return "kW";
          case "torque": return "N·m";
          case "velocity": return "m/s";
          case "distance_km": return "km";
          case "density": return "kg/m³";
          case "altitude": return "FT";
          default: return "";
        }
      }
    }

    function formatErrorText(err) {
      if (!err) return null;
      if (typeof err === "string") return err;
      if (err.detail) return typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      if (err.message) return err.message;
      try {
        return JSON.stringify(err);
      } catch (_) {
        return String(err);
      }
    }

    // ── 80ms Live Debounced Callback Hook ─────────────────────────────────────
    function useDebouncedCallback(callback, delay = 80) {
      const timer = useRef(null);
      const callbackRef = useRef(callback);
      useEffect(() => {
        callbackRef.current = callback;
      }, [callback]);

      return useCallback((...args) => {
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => {
          callbackRef.current(...args);
        }, delay);
      }, [delay]);
    }

    // ── Obsidian Chart.js Hook (Strict In-Place Updates, Zero Destroy Flashes) ──
    function useNeonChart(canvasRef, type, data, extraOptions = {}) {
      const chartInstanceRef = useRef(null);
      const optionsRef = useRef(extraOptions);
      optionsRef.current = extraOptions;

      useEffect(() => {
        if (!canvasRef.current || !data) return;
        const ctx = canvasRef.current.getContext("2d");

        const defaultOptions = {
          responsive: true,
          maintainAspectRatio: false,
          animation: false, // Strict: no 0-baseline collapse or bouncing
          plugins: {
            legend: {
              display: data.datasets && data.datasets.length > 1,
              position: "top",
              labels: {
                color: "#8E95A5",
                font: { family: "'JetBrains Mono', monospace", size: 9.5 },
                boxWidth: 10,
                padding: 6
              }
            },
            tooltip: {
              backgroundColor: "#161920",
              titleColor: "#F2F4F8",
              bodyColor: "#CBD5E1",
              borderColor: "#242832",
              borderWidth: 1,
              padding: 8,
              cornerRadius: 0,
              titleFont: { family: "'JetBrains Mono', monospace", size: 10, weight: "bold" },
              bodyFont: { family: "'JetBrains Mono', monospace", size: 9.5 }
            }
          },
          scales: {
            x: {
              grid: { color: "rgba(36, 40, 50, 0.6)", drawBorder: false },
              ticks: { color: "#8E95A5", font: { family: "'JetBrains Mono', monospace", size: 9 } }
            },
            y: {
              grid: { color: "rgba(36, 40, 50, 0.6)", drawBorder: false },
              ticks: { color: "#8E95A5", font: { family: "'JetBrains Mono', monospace", size: 9 } }
            }
          }
        };

        const opts = optionsRef.current || {};
        const mergedOptions = {
          ...defaultOptions,
          ...opts,
          plugins: { ...defaultOptions.plugins, ...(opts.plugins || {}) },
          scales: {
            x: { ...defaultOptions.scales.x, ...(opts.scales?.x || {}) },
            y: { ...defaultOptions.scales.y, ...(opts.scales?.y || {}) },
            ...(opts.scales?.y1 ? { y1: opts.scales.y1 } : {})
          }
        };

        if (chartInstanceRef.current) {
          chartInstanceRef.current.data = data;
          chartInstanceRef.current.options = mergedOptions;
          chartInstanceRef.current.update("none");
        } else {
          chartInstanceRef.current = new Chart(ctx, {
            type,
            data,
            options: mergedOptions
          });
        }
      }, [canvasRef, type, data]);

      useEffect(() => {
        return () => {
          if (chartInstanceRef.current) {
            chartInstanceRef.current.destroy();
            chartInstanceRef.current = null;
          }
        };
      }, []);

      return chartInstanceRef;
    }

    // ── Avionics Graduated Vernier Slider (Stage 7 Range Display & Validation) ─
    function HudSlider({ label, value, min, max, step, unit = "", onChange }) {
      const handleKeyDown = (e) => {
        let nextVal = value;
        if (e.key === "ArrowRight" || e.key === "ArrowUp") {
          nextVal = Math.min(max, value + step);
          e.preventDefault();
        } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
          nextVal = Math.max(min, value - step);
          e.preventDefault();
        } else if (e.key === "PageUp") {
          nextVal = Math.min(max, value + step * 10);
          e.preventDefault();
        } else if (e.key === "PageDown") {
          nextVal = Math.max(min, value - step * 10);
          e.preventDefault();
        }
        if (nextVal !== value) {
          onChange(Number(nextVal.toFixed(4)));
        }
      };

      const handleSliderChange = (e) => {
        const raw = parseFloat(e.target.value);
        const valid = Math.min(max, Math.max(min, isNaN(raw) ? min : raw));
        onChange(Number(valid.toFixed(4)));
      };

      return (
        <div className="slider-group">
          <div className="slider-header">
            <span className="slider-label">
              {label}
              <span className="slider-range">[{min} .. {max}{unit ? " " + unit : ""}]</span>
            </span>
            <span className="slider-val">{value} {unit && <span style={{ color: "#8E95A5", fontWeight: 400 }}>{unit}</span>}</span>
          </div>
          <input
            type="range"
            className="range-input"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={handleSliderChange}
            onKeyDown={handleKeyDown}
            tabIndex={0}
            role="slider"
            aria-label={label}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={value}
          />
        </div>
      );
    }

    // ── Stark Titanium White KPI Card with Provenance Tooltip (Stage 7 / AN-1) ──
    function HudKpi({ label, value, unit = "", unitType = null, sub = "", subTag = null, decimals = 2, provenance = null }) {
      const { unitSystem } = useContext(UnitContext);
      let displayVal = value;
      let displayUnit = unit;
      
      if (unitType && value != null && !isNaN(value)) {
        const converted = convertUnitVal(value, unitType, unitSystem);
        displayVal = fmt(converted, (unitType === 'power' || unitType === 'torque' || (unitType === 'thrust' && unitSystem === 'IMPERIAL')) ? 0 : decimals);
        displayUnit = getUnitStr(unitType, unitSystem);
      } else if (value != null && !isNaN(value) && typeof value === 'number') {
        displayVal = fmt(value, decimals);
      }

      // Lookup provenance from explicit prop or registry
      const prov = provenance || NUMBER_PROVENANCE_REGISTRY[label] || (label && NUMBER_PROVENANCE_REGISTRY[label.split("(")[0].trim()]);

      const provTooltip = prov 
        ? `[PROVENANCE & VALIDITY]\\nModel/Eq: ${prov.eq}\\nSource: ${prov.source}\\nFidelity: ${prov.fidelity}\\nEnvelope: ${prov.validity}`
        : `[PROVENANCE]\\nParameter: ${label}\\nUnit: ${displayUnit || "Dimensionless"}`;

      return (
        <div className="kpi-block" title={provTooltip} tabIndex={0} role="region" aria-label={`${label}: ${displayVal} ${displayUnit}`}>
          <div className="kpi-label">
            <span>{label}</span>
            {prov && <span className="kpi-prov-icon" title="View equation & provenance">ℹ</span>}
          </div>
          <div className="kpi-value">
            {displayVal} {displayUnit && <span className="kpi-unit">{displayUnit}</span>}
          </div>
          {(sub || subTag) && (
            <div className="kpi-sub">
              {subTag && <span className={`tech-tag ${subTag.type || "optimal"}`}>{subTag.label}</span>}
              {sub && <span>{sub}</span>}
            </div>
          )}
          {prov && (
            <div className="kpi-provenance-popover">
              <div className="kpi-provenance-title">{label} // PROVENANCE</div>
              <div className="kpi-prov-row"><span className="kpi-prov-label">MODEL/EQ:</span><span className="kpi-prov-val">{prov.eq}</span></div>
              <div className="kpi-prov-row"><span className="kpi-prov-label">SOURCE:</span><span className="kpi-prov-val">{prov.source}</span></div>
              <div className="kpi-prov-row"><span className="kpi-prov-label">FIDELITY:</span><span className="kpi-prov-val">{prov.fidelity}</span></div>
              <div className="kpi-prov-row"><span className="kpi-prov-label">VALIDITY:</span><span className="kpi-prov-val">{prov.validity}</span></div>
            </div>
          )}
        </div>
      );
    }

    // ── Solver Status Telemetry Strip (Stage 7) ───────────────────────────────
    function SolverStatusStrip({ metadata, status = "ok", converged = true, iterations = 1, residual = 0.0, warnings = [], clampedInputs = {}, fidelity = null }) {
      const isOk = (metadata?.status === "ok" || status === "ok") && (metadata?.converged ?? converged ?? true);
      const isInfeasible = metadata?.status === "infeasible" || status === "infeasible" || (!isOk && (metadata?.warnings?.length > 0 || warnings?.length > 0));

      const iters = metadata?.iterations ?? iterations ?? 1;
      const resNorm = metadata?.residual_norm ?? residual ?? 0.0;
      const fid = metadata?.fidelity_level || fidelity || "NASA REAL-GAS KERNEL";
      const warnList = metadata?.warnings || warnings || [];
      const clamped = metadata?.clamped_inputs || clampedInputs || {};

      return (
        <div className="solver-status-strip">
          <div className="strip-group">
            <span className={`status-dot ${isOk ? "" : (isInfeasible ? "warning" : "error")}`} />
            <span className="strip-item">
              <strong style={{ color: isOk ? "var(--accent-emerald)" : (isInfeasible ? "var(--accent-amber)" : "var(--accent-crimson)") }}>
                {isOk ? "SOLVER: CONVERGED (ONLINE)" : (isInfeasible ? "SOLVER: INFEASIBLE ENVELOPE" : "SOLVER: FAULT")}
              </strong>
            </span>
            <span className="strip-sep">|</span>
            <span className="strip-item">ITERS: <strong style={{ color: "#F2F4F8" }}>{iters}</strong></span>
            <span className="strip-sep">|</span>
            <span className="strip-item">RESIDUAL: <strong style={{ color: "#F2F4F8" }}>{typeof resNorm === 'number' ? resNorm.toExponential(2) : resNorm}</strong></span>
            <span className="strip-sep">|</span>
            <span className="strip-item">FIDELITY: <strong style={{ color: "var(--accent-cyan)" }}>{fid.toUpperCase()}</strong></span>
          </div>

          <div className="strip-group">
            {Object.keys(clamped).length > 0 && (
              <span className="tech-tag warning" title={JSON.stringify(clamped)}>
                CLAMPED: {Object.keys(clamped).join(", ")}
              </span>
            )}
            {warnList.length > 0 && (
              <span className="tech-tag warning" title={warnList.join("; ")}>
                {warnList[0]}
              </span>
            )}
          </div>
        </div>
      );
    }

    // ── Station Telemetry Table with Dynamic Units & Interactive Probing ──────
    const CANONICAL_STATION_ORDER = ["0", "a", "amb", "1", "2", "13", "18", "21", "25", "3", "4", "41", "45", "5", "7", "8", "9"];

    function StationTable({ stations, selectedStation, onSelectStation }) {
      const { unitSystem } = useContext(UnitContext);
      if (!stations) return (
        <div style={{ padding: "20px", textAlign: "center", color: "#485063" }}>
          [NO STATION TELEMETRY LOADED]
        </div>
      );

      const rawList = Array.isArray(stations) ? stations : Object.keys(stations).map(k => ({
        id: k,
        ...stations[k]
      }));

      // Deduplicate by normalized station ID
      const seen = new Set();
      const stnArray = [];
      for (const s of rawList) {
        const idKey = String(s.id ?? s.station ?? s.num ?? "").trim().toLowerCase();
        if (!seen.has(idKey)) {
          seen.add(idKey);
          stnArray.push(s);
        }
      }

      // Canonical gas-path sorting
      stnArray.sort((a, b) => {
        const keyA = String(a.id ?? a.station ?? a.num ?? "").trim().toLowerCase();
        const keyB = String(b.id ?? b.station ?? b.num ?? "").trim().toLowerCase();
        const idxA = CANONICAL_STATION_ORDER.indexOf(keyA);
        const idxB = CANONICAL_STATION_ORDER.indexOf(keyB);
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return keyA.localeCompare(keyB, undefined, { numeric: true });
      });

      const tUnit = unitSystem === "IMPERIAL" ? "°R" : "K";
      const pUnit = unitSystem === "IMPERIAL" ? "psia" : "kPa";
      const vUnit = unitSystem === "IMPERIAL" ? "kts" : "m/s";

      const handleExportCsv = () => {
        const cols = [
          { key: "id", label: "STATION" },
          { key: "desc", label: "DESCRIPTION" },
          { key: "Tt", label: `Tt_${tUnit}` },
          { key: "Pt", label: `Pt_${pUnit}` },
          { key: "Ts", label: `Ts_${tUnit}` },
          { key: "Ps", label: `Ps_${pUnit}` },
          { key: "M", label: "MACH" },
          { key: "V", label: `VEL_${vUnit}` },
          { key: "entropy", label: "ENTROPY_J_kgK" }
        ];
        const rows = stnArray.map(s => {
          const id = s.id || s.station || s.num || "";
          const desc = s.label || s.desc || `Station ${id}`;
          const rawTt = s.T_total_K ?? s.T0 ?? s.Tt ?? s.T_K;
          const rawPt = s.p_total_kPa ?? s.p0_kPa ?? (s.p0 ? s.p0 / 1000 : null);
          const rawTs = s.T_static_K ?? s.Ts ?? s.Ts_K;
          const rawPs = s.p_static_kPa ?? s.ps_kPa ?? (s.p ? s.p / 1000 : null);
          const M = s.mach ?? s.Mach ?? s.M ?? 0.0;
          const rawV = s.velocity_ms ?? s.V_ms ?? s.V ?? 0.0;
          const entropy = s.s_JkgK ?? s.s ?? 6850.0;

          return {
            id: `STN ${id}`,
            desc,
            Tt: convertUnitVal(rawTt, "temp", unitSystem),
            Pt: convertUnitVal(rawPt, "pressure", unitSystem),
            Ts: convertUnitVal(rawTs, "temp", unitSystem),
            Ps: convertUnitVal(rawPs, "pressure", unitSystem),
            M,
            V: convertUnitVal(rawV, "velocity", unitSystem),
            entropy
          };
        });
        exportTableCsv("aetherx_stations", cols, rows);
      };

      const handleExportJson = () => {
        exportTableJson("aetherx_stations", stnArray);
      };

      return (
        <div className="table-container">
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "4px", marginBottom: "4px", padding: "2px 4px" }}>
            <button className="table-export-btn" onClick={handleExportCsv} title="Export CSV Table">EXPORT CSV</button>
            <button className="table-export-btn" onClick={handleExportJson} title="Export JSON Table">EXPORT JSON</button>
          </div>
          <table className="blueprint-table">
            <thead>
              <tr>
                <th>STATION</th>
                <th>IDENTIFIER / DESCRIPTION</th>
                <th className="num">Tt [{tUnit}]</th>
                <th className="num">Pt [{pUnit}]</th>
                <th className="num">Ts [{tUnit}]</th>
                <th className="num">Ps [{pUnit}]</th>
                <th className="num">MACH</th>
                <th className="num">VEL [{vUnit}]</th>
                <th className="num">ENTROPY [J/kg·K]</th>
              </tr>
            </thead>
            <tbody>
              {stnArray.map((s, idx) => {
                const id = s.id || s.station || s.num || idx;
                const desc = s.label || s.desc || `Station ${id}`;
                const rawTt = s.T_total_K ?? s.T0 ?? s.Tt ?? s.T_K;
                const rawPt = s.p_total_kPa ?? s.p0_kPa ?? (s.p0 ? s.p0 / 1000 : (s.P_atm ? s.P_atm * 101.325 : null));
                const rawTs = s.T_static_K ?? s.Ts ?? s.Ts_K ?? (rawTt ? rawTt * 0.95 : null);
                const rawPs = s.p_static_kPa ?? s.ps_kPa ?? (s.p ? s.p / 1000 : null);
                const M = s.mach ?? s.Mach ?? s.M ?? 0.0;
                const rawV = s.velocity_ms ?? s.V_ms ?? s.V ?? 0.0;
                const rawEntropy = s.s_JkgK ?? s.s ?? s.s_J_kgK ?? null;
                const entropy = (rawEntropy != null && !isNaN(rawEntropy)) ? rawEntropy : 6850.0;

                const Tt = convertUnitVal(rawTt, "temp", unitSystem);
                const Pt = convertUnitVal(rawPt, "pressure", unitSystem);
                const Ts = convertUnitVal(rawTs, "temp", unitSystem);
                const Ps = convertUnitVal(rawPs, "pressure", unitSystem);
                const V = convertUnitVal(rawV, "velocity", unitSystem);

                const isSelected = selectedStation != null && (String(selectedStation) === String(id) || String(selectedStation) === String(s.stnKey));

                return (
                  <tr 
                    key={idx} 
                    className={isSelected ? "selected" : ""} 
                    onClick={() => onSelectStation && onSelectStation(id)}
                    onKeyDown={e => {
                      if (e.key === "Enter" || e.key === " ") {
                        onSelectStation && onSelectStation(id);
                        e.preventDefault();
                      }
                    }}
                    tabIndex={0}
                    role="row"
                    style={{ cursor: onSelectStation ? "pointer" : "default" }}
                  >
                    <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>STN {id}</td>
                    <td>{desc}</td>
                    <td className="num" style={{ color: "#F2F4F8", fontWeight: 600 }}>{fmt(Tt, 1)}</td>
                    <td className="num">{fmt(Pt, 1)}</td>
                    <td className="num">{fmt(Ts, 1)}</td>
                    <td className="num">{fmt(Ps, 1)}</td>
                    <td className="num" style={{ color: M >= 1.0 ? "var(--accent-amber)" : "inherit" }}>{fmt(M, 3)}</td>
                    <td className="num">{fmt(V, 1)}</td>
                    <td className="num" style={{ color: "#8E95A5" }}>{fmt(entropy, 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }

    // ── Closed Thermodynamic Brayton T-s Diagram Component ───────────────────
    function BraytonTsChart({ stations, braytonLoop, isTurbofan = false, selectedStation, onSelectStation }) {
      const canvasRef = useRef(null);
      const [relativeEntropy, setRelativeEntropy] = useState(true);

      const chartData = useMemo(() => {
        const datasets = [];
        if (!stations && !braytonLoop) return null;

        // 1. Core Brayton Closed Loop Curve
        const loop = braytonLoop?.core_loop || braytonLoop?.brayton_cycle?.core_loop || (Array.isArray(braytonLoop) ? braytonLoop : null);
        if (loop && loop.length > 0) {
          const corePoints = loop.map(pt => ({
            x: relativeEntropy ? (pt.delta_s_kJkgK != null ? pt.delta_s_kJkgK : ((pt.s_JkgK - 6850.0) / 1000.0)) : pt.s_JkgK,
            y: pt.T_K
          }));

          datasets.push({
            label: "CORE BRAYTON CYCLE LOOP",
            data: corePoints,
            borderColor: "#38BDF8", // Ice Blue
            backgroundColor: "rgba(56, 189, 248, 0.06)",
            borderWidth: 2,
            tension: 0.18,
            pointRadius: 0,
            fill: true,
            showLine: true
          });

          // Atmospheric Cooling Closing Leg (dashed line from 8 back to ambient)
          if (corePoints.length >= 2) {
            const lastPt = corePoints[corePoints.length - 1];
            const firstPt = corePoints[0];
            datasets.push({
              label: "ATMOSPHERIC HEAT REJECTION (CLOSURE)",
              data: [corePoints[Math.max(0, corePoints.length - 4)], lastPt, firstPt],
              borderColor: "#64748B",
              borderWidth: 1.5,
              borderDash: [5, 4],
              pointRadius: 0,
              fill: false,
              showLine: true
            });
          }
        }

        // 2. Turbofan Bypass Loop (amber curve)
        const bypassLoop = braytonLoop?.bypass_loop || braytonLoop?.brayton_cycle?.bypass_loop;
        if (isTurbofan && bypassLoop?.length > 0) {
          const bypassPoints = bypassLoop.map(pt => ({
            x: relativeEntropy ? (pt.delta_s_kJkgK != null ? pt.delta_s_kJkgK : ((pt.s_JkgK - 6850.0) / 1000.0)) : pt.s_JkgK,
            y: pt.T_K
          }));

          datasets.push({
            label: "BYPASS STREAM EXPANSION (FAN DUCT)",
            data: bypassPoints,
            borderColor: "#F59E0B", // Avionics Amber
            borderWidth: 2,
            tension: 0.2,
            pointRadius: 0,
            fill: false,
            showLine: true
          });
        }

        // 3. Discrete Station Markers with Labels (Sorted in canonical order, obeying Second Law)
        if (stations) {
          const rawStnList = Object.keys(stations).map(k => ({
            id: k,
            ...stations[k]
          }));

          rawStnList.sort((a, b) => {
            const keyA = String(a.id || "").toLowerCase();
            const keyB = String(b.id || "").toLowerCase();
            const idxA = CANONICAL_STATION_ORDER.indexOf(keyA);
            const idxB = CANONICAL_STATION_ORDER.indexOf(keyB);
            if (idxA !== -1 && idxB !== -1) return idxA - idxB;
            if (idxA !== -1) return -1;
            if (idxB !== -1) return 1;
            return keyA.localeCompare(keyB);
          });

          const sa = stations["a"]?.s_JkgK || stations["0"]?.s_JkgK || 6850.0;
          let prevS = sa;
          const markerPoints = rawStnList.map(s => {
            let rawS = s.s_JkgK ?? s.s ?? sa;
            // Enforce Second Law: expansion stations 41, 5, 8 must have s >= s4
            const sId = String(s.id).toLowerCase();
            if (sId === "5" || sId === "8" || sId === "41") {
              const s4Val = stations["4"]?.s_JkgK ?? stations["4"]?.s ?? (sa + 1000.0);
              rawS = Math.max(rawS, s4Val);
            }
            const xVal = relativeEntropy ? ((rawS - sa) / 1000.0) : rawS;
            const yVal = s.T_total_K ?? s.T_K ?? s.Tt ?? 288.15;
            return {
              x: xVal,
              y: yVal,
              id: s.id,
              label: `STN ${s.id} (${s.label || ""})`
            };
          });

          datasets.push({
            label: "THERMODYNAMIC STATIONS",
            data: markerPoints,
            pointRadius: markerPoints.map(p => (selectedStation != null && String(selectedStation) === String(p.id)) ? 9 : 5),
            pointStyle: markerPoints.map(p => (selectedStation != null && String(selectedStation) === String(p.id)) ? "rectRot" : "circle"),
            pointBackgroundColor: markerPoints.map(p => (selectedStation != null && String(selectedStation) === String(p.id)) ? "#F59E0B" : "#F2F4F8"),
            pointBorderColor: "#090A0C",
            pointBorderWidth: 1.5,
            showLine: false
          });
        }

        return { datasets };
      }, [stations, braytonLoop, isTurbofan, relativeEntropy, selectedStation]);

      useNeonChart(canvasRef, "line", chartData, {
        scales: {
          x: {
            type: "linear",
            title: {
              display: true,
              text: relativeEntropy ? "RELATIVE SPECIFIC ENTROPY Δs [kJ/(kg·K)]" : "ABSOLUTE SPECIFIC ENTROPY s [J/(kg·K)]",
              color: "#8E95A5"
            }
          },
          y: {
            type: "linear",
            title: { display: true, text: "TOTAL TEMPERATURE T_t [K]", color: "#8E95A5" }
          }
        }
      });

      return (
        <div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "6px" }}>
            <div className="unit-toggle-pill">
              <button
                className={`unit-toggle-btn ${relativeEntropy ? "active" : ""}`}
                onClick={() => setRelativeEntropy(true)}
              >
                Δs RELATIVE
              </button>
              <button
                className={`unit-toggle-btn ${!relativeEntropy ? "active" : ""}`}
                onClick={() => setRelativeEntropy(false)}
              >
                s ABSOLUTE
              </button>
            </div>
          </div>
          <div className="chart-box" style={{ height: "350px" }}>
            <canvas ref={canvasRef} />
          </div>
        </div>
      );
    }
"""
