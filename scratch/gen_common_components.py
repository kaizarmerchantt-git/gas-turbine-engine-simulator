COMMON_COMPONENTS = """
    const { useState, useEffect, useRef, useCallback, useMemo, useContext, createContext } = React;
    const API = "";

    // ── Number Formatters ─────────────────────────────────────────────────────
    function fmt(val, dec = 2) {
      if (val === null || val === undefined || isNaN(val)) return "---";
      return Number(val).toFixed(dec);
    }

    function fmtInt(val) {
      if (val === null || val === undefined || isNaN(val)) return "---";
      return Math.round(Number(val)).toLocaleString();
    }

    function fmtPct(val, dec = 1) {
      if (val === null || val === undefined || isNaN(val)) return "---";
      const num = Number(val);
      const pct = num <= 1.0 && num > 0.0 ? num * 100 : num;
      return `${pct.toFixed(dec)}%`;
    }

    // ── Global Unit System Context & Conversion Engine ────────────────────────
    const UnitContext = createContext({ unitSystem: "SI", setUnitSystem: () => {} });

    function convertUnitVal(val, type, unitSystem) {
      if (val == null || isNaN(val)) return null;
      const num = Number(val);
      if (unitSystem === "IMPERIAL") {
        switch (type) {
          case "thrust": return num * 224.80894; // kN -> lbf
          case "thrust_N": return num * 0.224809; // N -> lbf
          case "massflow": return num * 2.20462; // kg/s -> lb/s
          case "fuelflow": return num * 7936.64; // kg/s -> lb/hr
          case "fuelflow_kgh": return num * 2.20462; // kg/h -> lb/hr
          case "temp": return num * 1.8; // K -> °R
          case "pressure": return num * 0.1450377; // kPa -> psia
          case "tsfc": return num * 0.03530394; // g/(kN·s) -> lb/(lbf·hr)
          case "power": return num * 1.34102; // kW -> shp
          case "torque": return num * 0.737562; // N·m -> ft·lbf
          case "velocity": return num * 1.94384; // m/s -> kts
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
          case "massflow": return "lb/s";
          case "fuelflow": return "lb/hr";
          case "fuelflow_kgh": return "lb/hr";
          case "temp": return "°R";
          case "pressure": return "psia";
          case "tsfc": return "lb/lbf·h";
          case "power": return "shp";
          case "torque": return "ft·lbf";
          case "velocity": return "kts";
          case "altitude": return "FT";
          default: return "";
        }
      } else {
        switch (type) {
          case "thrust": return "kN";
          case "thrust_N": return "N";
          case "massflow": return "kg/s";
          case "fuelflow": return "kg/s";
          case "fuelflow_kgh": return "kg/h";
          case "temp": return "K";
          case "pressure": return "kPa";
          case "tsfc": return "g/kN·s";
          case "power": return "kW";
          case "torque": return "N·m";
          case "velocity": return "m/s";
          case "altitude": return "FT";
          default: return "";
        }
      }
    }

    // ── 60ms Live Debounced Callback Hook ─────────────────────────────────────
    function useDebouncedCallback(callback, delay = 60) {
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

    // ── Obsidian Chart.js Hook ────────────────────────────────────────────────
    function useNeonChart(canvasRef, type, data, extraOptions = {}) {
      const chartInstanceRef = useRef(null);

      useEffect(() => {
        if (!canvasRef.current || !data) return;
        const ctx = canvasRef.current.getContext("2d");

        if (chartInstanceRef.current) {
          chartInstanceRef.current.destroy();
        }

        const defaultOptions = {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 150 },
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

        const mergedOptions = {
          ...defaultOptions,
          ...extraOptions,
          plugins: { ...defaultOptions.plugins, ...(extraOptions.plugins || {}) },
          scales: {
            x: { ...defaultOptions.scales.x, ...(extraOptions.scales?.x || {}) },
            y: { ...defaultOptions.scales.y, ...(extraOptions.scales?.y || {}) },
            ...(extraOptions.scales?.y1 ? { y1: extraOptions.scales.y1 } : {})
          }
        };

        chartInstanceRef.current = new Chart(ctx, {
          type,
          data,
          options: mergedOptions
        });

        return () => {
          if (chartInstanceRef.current) {
            chartInstanceRef.current.destroy();
            chartInstanceRef.current = null;
          }
        };
      }, [data, extraOptions]);

      return chartInstanceRef;
    }

    // ── Avionics Graduated Vernier Slider ─────────────────────────────────────
    function HudSlider({ label, value, min, max, step, unit = "", onChange }) {
      return (
        <div className="slider-group">
          <div className="slider-header">
            <span className="slider-label">{label}</span>
            <span className="slider-val">{value} {unit && <span style={{ color: "#8E95A5", fontWeight: 400 }}>{unit}</span>}</span>
          </div>
          <input
            type="range"
            className="range-input"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={e => onChange(parseFloat(e.target.value))}
          />
        </div>
      );
    }

    // ── Stark Titanium White KPI Card ─────────────────────────────────────────
    function HudKpi({ label, value, unit = "", unitType = null, sub = "", subTag = null, decimals = 2 }) {
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

      return (
        <div className="kpi-block">
          <div className="kpi-label">{label}</div>
          <div className="kpi-value">
            {displayVal} {displayUnit && <span className="kpi-unit">{displayUnit}</span>}
          </div>
          {(sub || subTag) && (
            <div className="kpi-sub">
              {subTag && <span className={`tech-tag ${subTag.type || "optimal"}`}>{subTag.label}</span>}
              {sub && <span>{sub}</span>}
            </div>
          )}
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

      return (
        <div className="table-container">
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
