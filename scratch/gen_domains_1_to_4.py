DOMAINS_1_TO_4 = """
    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 01: TURBOJET SINGLE-SPOOL THERMODYNAMICS
    // ═════════════════════════════════════════════════════════════════════════
    function TurbojetPanel({ onUpdateStations, selectedStation, onSelectStation }) {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [res, setRes] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        A1: 0.40,
        A2: 0.38,
        A8: 0.28,
        CPR: 12.0,
        T_max: 1450.0,
        throttle_pos: 1.0,
        alt: 10000.0,
        M_i: 0.85,
        eta_i: 0.98,
        eta_c: 0.80,
        eta_b: 0.90,
        dp_over_p: 0.06,
        eta_t: 0.80,
        mech_loss: 0.99,
        eta_noz: 0.80,
        mdot_guess: 24.0
      });

      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const solveCycle = useCallback(async (currentP) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const reqBody = {
            eng_param: {
              A1: currentP.A1,
              A2: currentP.A2,
              comp_n_stages: 8,
              turb_n_stages: 2,
              A8: currentP.A8
            },
            eng_perf: {
              eta_i: currentP.eta_i,
              CPR: currentP.CPR,
              eta_c: currentP.eta_c,
              eta_b: currentP.eta_b,
              dp_over_p: currentP.dp_over_p,
              max_f: 0.30,
              min_f: 0.05,
              V_nominal: 25.0,
              T_max: currentP.T_max,
              eta_t: currentP.eta_t,
              mech_loss: currentP.mech_loss,
              eta_noz: currentP.eta_noz
            },
            throttle_pos: Math.max(0.15, currentP.throttle_pos),
            alt: currentP.alt,
            M_i: currentP.M_i,
            mdot_guess: currentP.mdot_guess
          };

          const resp = await fetch(`${API}/api/turbojet/single`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(reqBody)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Turbojet solver failed");
          }
          const data = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setRes(data);
          if (onUpdateStations && data.stations) onUpdateStations(data.stations);
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, [onUpdateStations]);

      const debouncedSolve = useDebouncedCallback(solveCycle, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          solveCycle(p);
          return;
        }
        debouncedSolve(p);
      }, [p, debouncedSolve, solveCycle]);

      const fn_kN = res?.thrust_net_kN ?? res?.T ?? res?.Fn_kN ?? (res?.thrust_N ? res.thrust_N / 1000.0 : null);
      const wf_kgs = res?.mdot_fuel ?? res?.Wf_kgs ?? res?.fuel_flow_kg_s ?? null;
      const tsfc = res?.TSFC_g_kNs ?? res?.TSFC_g_kns ?? res?.tsfc_g_kns ?? res?.TSFC ?? null;
      const mdot = res?.mdot_air ?? res?.W_inlet ?? res?.mdot ?? null;
      const eta_th = res?.eta_th ?? null;

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[CONTROLS] TURBOJET AEROTHERMODYNAMICS</span>
                <span className="tech-tag info">
                  VALIDATION: TIER A/B/C [NASA-9 REAL GAS]
                </span>
              </div>
              <div className="panel-card-body">
                <HudSlider label="COMPRESSOR PR (CPR)" value={p.CPR} min={3.0} max={25.0} step={0.5} onChange={v => setVal("CPR", v)} />
                <HudSlider label="TIT LIMIT (T_max)" value={p.T_max} min={1100} max={1850} step={25} unit="K" onChange={v => setVal("T_max", v)} />
                <HudSlider label="THROTTLE POSITION" value={p.throttle_pos} min={0.2} max={1.0} step={0.05} onChange={v => setVal("throttle_pos", v)} />
                <HudSlider label="ALTITUDE" value={p.alt} min={0} max={60000} step={1000} unit="FT" onChange={v => setVal("alt", v)} />
                <HudSlider label="FLIGHT MACH" value={p.M_i} min={0.0} max={1.8} step={0.05} unit="M" onChange={v => setVal("M_i", v)} />
                <div style={{ height: "1px", background: "var(--border-hairline)", margin: "8px 0" }} />
                <HudSlider label="CAPTURE AREA (A1)" value={p.A1} min={0.05} max={0.60} step={0.01} unit="M²" onChange={v => setVal("A1", v)} />
                <HudSlider label="NOZZLE AREA (A8)" value={p.A8} min={0.02} max={0.40} step={0.01} unit="M²" onChange={v => setVal("A8", v)} />
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            <SolverStatusStrip metadata={res?.metadata} fidelity="NASA-9 Real Gas" />

            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] SOLVER ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top KPI Ribbon (All Numbers Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="NET THRUST (Fn)" value={fn_kN != null ? fn_kN : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="thrust" sub="NASA-9 Expansion" />
              <HudKpi label="FUEL MASS FLOW" value={wf_kgs != null ? wf_kgs : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="fuelflow" decimals={4} sub="LHV Energy Balance" />
              <HudKpi label="SPECIFIC FUEL CONS (TSFC)" value={tsfc != null ? tsfc : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="tsfc" decimals={2} sub="Metric Cycle Spec" />
              <HudKpi label="AIR MASS FLOW" value={mdot != null ? mdot : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="massflow" decimals={1} sub="Inlet Capture Face" />
              <HudKpi label="THERMAL EFFICIENCY" value={eta_th != null ? fmtPct(eta_th) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="First Law Energy Jump" />
              <HudKpi label="COMPRESSOR CPR" value={fmt(p.CPR, 1)} sub="Total-to-Total" />
            </div>

            {/* Middle Side-by-Side: 55% T-s Diagram | 45% Aerodynamics Table */}
            <div style={{ display: "grid", gridTemplateColumns: "55% calc(45% - 10px)", gap: "10px", alignItems: "start" }}>
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[THERMO-CYCLE] BRAYTON T-s DIAGRAM // CLOSED ISOBARIC LOOP</span>
                  <span className="tech-tag optimal">CANTERA INTEGRATION</span>
                </div>
                <div className="panel-card-body">
                  <BraytonTsChart
                    stations={res?.stations}
                    braytonLoop={res?.brayton_cycle || res?.brayton_loop}
                    isTurbofan={false}
                    selectedStation={selectedStation}
                    onSelectStation={onSelectStation}
                  />
                </div>
              </div>

              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[AEROTHERMODYNAMICS] STATION FLOW PROPERTIES TABLE</span>
                  <span className="tech-tag info">SELECT ROW TO PROBE</span>
                </div>
                <div className="panel-card-body">
                  <StationTable
                    stations={res?.stations}
                    selectedStation={selectedStation}
                    onSelectStation={onSelectStation}
                  />
                </div>
              </div>
            </div>
          </main>
        </div>
      );
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 02: DUAL-SPOOL TURBOFAN AEROTHERMODYNAMICS
    // ═════════════════════════════════════════════════════════════════════════
    function PhysicsTurbofanPanel({ onUpdateStations, selectedStation, onSelectStation }) {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [res, setRes] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        BPR: 5.0,
        FPR: 1.6,
        CPR_hpc: 18.0,
        TIT: 1600.0,
        throttle_pos: 1.0,
        alt: 10000.0,
        mach: 0.80,
        A1: 1.5,
        A2: 1.5,
        A8_core: 0.15,
        A18_bypass: 0.45,
        eta_fan: 0.89,
        eta_hpc: 0.85,
        eta_b: 0.99,
        dp_over_p: 0.04,
        eta_hpt: 0.89,
        eta_lpt: 0.91,
        eta_noz_core: 0.98,
        eta_noz_fan: 0.98
      });

      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const solveTurbofan = useCallback(async (currentP) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const reqBody = {
            eng_param: {
              A1: currentP.A1,
              A2: currentP.A2,
              fan_n_stages: 1,
              hpc_n_stages: 9,
              hpt_n_stages: 1,
              lpt_n_stages: 3,
              A8: currentP.A8_core,
              BPR: currentP.BPR
            },
            eng_perf: {
              eta_i: 0.98,
              FPR: currentP.FPR,
              eta_fan: currentP.eta_fan,
              CPR: currentP.CPR_hpc,
              eta_hpc: currentP.eta_hpc,
              eta_b: currentP.eta_b,
              dp_over_p: currentP.dp_over_p,
              max_f: 0.30,
              min_f: 0.05,
              V_nominal: 30.0,
              T_max: currentP.TIT,
              eta_hpt: currentP.eta_hpt,
              eta_lpt: currentP.eta_lpt,
              mech_loss_hp: 0.99,
              mech_loss_lp: 0.99,
              eta_noz_core: currentP.eta_noz_core,
              eta_noz_byp: currentP.eta_noz_fan
            },
            throttle_pos: Math.max(0.15, currentP.throttle_pos),
            alt: currentP.alt,
            M_i: currentP.mach,
            mdot_core_guess: 20.0
          };

          const resp = await fetch(`${API}/api/physics_turbofan/single`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(reqBody)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Physics turbofan solver failed");
          }
          const data = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setRes(data);
          if (onUpdateStations && data.stations) onUpdateStations(data.stations);
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, [onUpdateStations]);

      const debouncedSolve = useDebouncedCallback(solveTurbofan, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          solveTurbofan(p);
          return;
        }
        debouncedSolve(p);
      }, [p, debouncedSolve, solveTurbofan]);

      const fn_kN = res?.thrust_net_kN ?? res?.T ?? null;
      const bpr = res?.BPR ?? p.BPR;
      const tsfc = res?.TSFC_g_kNs ?? res?.TSFC ?? null;
      const mdot_total = res?.mdot_air ?? (res?.mdot_core && res?.mdot_byp ? res.mdot_core + res.mdot_byp : null);
      const mdot_core = res?.mdot_core ?? null;
      const opr = (p.FPR * p.CPR_hpc).toFixed(1);

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[CONTROLS] DUAL-SPOOL TURBOFAN</span>
                <span className="tech-tag info">
                  VALIDATION: TIER B/C [DUAL-SPOOL REAL GAS]
                </span>
              </div>
              <div className="panel-card-body">
                <HudSlider label="BYPASS RATIO (BPR)" value={p.BPR} min={1.0} max={12.0} step={0.2} onChange={v => setVal("BPR", v)} />
                <HudSlider label="FAN PRESSURE RATIO (FPR)" value={p.FPR} min={1.2} max={2.4} step={0.05} onChange={v => setVal("FPR", v)} />
                <HudSlider label="HPC PRESSURE RATIO" value={p.CPR_hpc} min={8.0} max={30.0} step={0.5} onChange={v => setVal("CPR_hpc", v)} />
                <HudSlider label="TURBINE INLET TEMP (TIT)" value={p.TIT} min={1200} max={1900} step={25} unit="K" onChange={v => setVal("TIT", v)} />
                <HudSlider label="THROTTLE POSITION" value={p.throttle_pos} min={0.2} max={1.0} step={0.05} onChange={v => setVal("throttle_pos", v)} />
                <HudSlider label="ALTITUDE" value={p.alt} min={0} max={50000} step={1000} unit="FT" onChange={v => setVal("alt", v)} />
                <HudSlider label="FLIGHT MACH" value={p.mach} min={0.0} max={0.92} step={0.02} unit="M" onChange={v => setVal("mach", v)} />
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            <SolverStatusStrip metadata={res?.metadata} fidelity="Dual-Spool Real Gas" />

            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] SOLVER ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top KPI Ribbon (All Numbers Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="NET THRUST (Fn)" value={fn_kN != null ? fn_kN : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="thrust" sub="Core + Fan Thrust" />
              <HudKpi label="BYPASS RATIO (BPR)" value={fmt(bpr, 2)} sub="Secondary Mass Split" />
              <HudKpi label="TSFC (METRIC)" value={tsfc != null ? tsfc : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="tsfc" decimals={2} sub="Specific Fuel Cons." />
              <HudKpi label="TOTAL AIRFLOW" value={mdot_total != null ? mdot_total : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="massflow" decimals={1} sub="Fan Face Capture" />
              <HudKpi label="CORE AIRFLOW" value={mdot_core != null ? mdot_core : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="massflow" decimals={1} sub="HPC Inflow Mass" />
              <HudKpi label="OVERALL PR (OPR)" value={opr} sub="FPR × HPC PR" />
            </div>

            {/* Middle Side-by-Side: 55% T-s Diagram | 45% Aerodynamics Table */}
            <div style={{ display: "grid", gridTemplateColumns: "55% calc(45% - 10px)", gap: "10px", alignItems: "start" }}>
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[THERMO-CYCLE] DUAL-SPOOL T-s DIAGRAM // CORE & BYPASS EXPANSIONS</span>
                  <span className="tech-tag optimal">NASA-9 REAL GAS INTEGRATION</span>
                </div>
                <div className="panel-card-body">
                  <BraytonTsChart
                    stations={res?.stations}
                    braytonLoop={res?.brayton_cycle || res?.brayton_loop}
                    isTurbofan={true}
                    selectedStation={selectedStation}
                    onSelectStation={onSelectStation}
                  />
                </div>
              </div>

              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[AEROTHERMODYNAMICS] DUAL-SPOOL STATION PROPERTIES</span>
                  <span className="tech-tag info">SELECT ROW TO PROBE</span>
                </div>
                <div className="panel-card-body">
                  <StationTable
                    stations={res?.stations}
                    selectedStation={selectedStation}
                    onSelectStation={onSelectStation}
                  />
                </div>
              </div>
            </div>
          </main>
        </div>
      );
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 03: CF34 EMPIRICAL FLIGHT DECK (TRILINEAR INTERPOLATION)
    // ═════════════════════════════════════════════════════════════════════════
    function TurbofanPanel({ onUpdateStations, selectedStation, onSelectStation }) {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [res, setRes] = useState(null);
      const [altPts, setAltPts] = useState([]);
      const [machPts, setMachPts] = useState([]);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        alt: 35000.0,
        MN: 0.80,
        PC: 1.00
      });

      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const solveDeck = useCallback(async (currentP) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          // Direct call to /api/turbofan/single (or alias /api/cf34/single)
          const resp = await fetch(`${API}/api/turbofan/single`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentP)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "CF34 deck interpolation failed");
          }
          const data = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setRes(data);
          if (onUpdateStations && data.stations) onUpdateStations(data.stations);

          // Fetch altitude and Mach sweeps
          const [aRes, mRes] = await Promise.all([
            fetch(`${API}/api/cf34/sweep_altitude?MN=${currentP.MN}&PC=${currentP.PC}&n_points=25`),
            fetch(`${API}/api/cf34/sweep_mach?alt=${currentP.alt}&PC=${currentP.PC}&n_points=25`)
          ]);
          if (reqId !== reqSeqRef.current) return;
          if (aRes.ok) setAltPts((await aRes.json()).points || []);
          if (mRes.ok) setMachPts((await mRes.json()).points || []);
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, [onUpdateStations]);

      const debouncedSolve = useDebouncedCallback(solveDeck, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          solveDeck(p);
          return;
        }
        debouncedSolve(p);
      }, [p, debouncedSolve, solveDeck]);

      const fn_kN = res?.Fn_kN ?? null;
      const wf_kgh = res ? (res.Wf_kgh ?? (res.Wf_kgs ? res.Wf_kgs * 3600 : null)) : null;
      const tsfc = (fn_kN && wf_kgh) ? ((wf_kgh / 3.6) / fn_kN) : (res?.TSFC ?? null);
      const wc_kgs = res?.Wc_kgs ?? null;

      const altRef = useRef(null);
      const machRef = useRef(null);

      const altDatasets = useMemo(() => {
        const ds = [{
          label: "THRUST LAPSE VS ALTITUDE",
          data: altPts.map(pt => ({ x: pt.alt, y: pt.Fn_kN })),
          borderColor: "#38BDF8",
          backgroundColor: "rgba(56, 189, 248, 0.08)",
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          showLine: true
        }];
        if (res && res.Fn_kN != null) {
          ds.push({
            label: `OPERATING POINT (${fmtInt(p.alt)} FT, ${fmt(res.Fn_kN, 2)} kN)`,
            data: [{ x: p.alt, y: res.Fn_kN }],
            pointRadius: 8,
            pointStyle: "rectRot",
            pointBackgroundColor: "#F59E0B",
            borderColor: "#FFFFFF",
            borderWidth: 2,
            showLine: false
          });
        }
        return { datasets: ds };
      }, [altPts, res, p.alt]);

      const machDatasets = useMemo(() => {
        const ds = [{
          label: "THRUST VS FLIGHT MACH",
          data: machPts.map(pt => ({ x: pt.MN, y: pt.Fn_kN })),
          borderColor: "#F59E0B",
          backgroundColor: "rgba(245, 158, 11, 0.08)",
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          showLine: true
        }];
        if (res && res.Fn_kN != null) {
          ds.push({
            label: `OPERATING POINT (M ${fmt(p.MN, 2)}, ${fmt(res.Fn_kN, 2)} kN)`,
            data: [{ x: p.MN, y: res.Fn_kN }],
            pointRadius: 8,
            pointStyle: "rectRot",
            pointBackgroundColor: "#F59E0B",
            borderColor: "#FFFFFF",
            borderWidth: 2,
            showLine: false
          });
        }
        return { datasets: ds };
      }, [machPts, res, p.MN]);

      useNeonChart(altRef, "line", altDatasets, {
        scales: {
          x: { type: "linear", title: { display: true, text: "ALTITUDE [FT]", color: "#8E95A5" } },
          y: { type: "linear", title: { display: true, text: "NET THRUST [kN]", color: "#8E95A5" } }
        }
      });

      useNeonChart(machRef, "line", machDatasets, {
        scales: {
          x: { type: "linear", title: { display: true, text: "FLIGHT MACH", color: "#8E95A5" } },
          y: { type: "linear", title: { display: true, text: "NET THRUST [kN]", color: "#8E95A5" } }
        }
      });

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[INPUT] CF34 EMPIRICAL FLIGHT DECK</span>
                <span className="tech-tag warning">
                  VALIDATION: UNVALIDATED EMPIRICAL FIT
                </span>
              </div>
              <div className="panel-card-body">
                <HudSlider label="ALTITUDE" value={p.alt} min={0} max={45000} step={1000} unit="FT" onChange={v => setVal("alt", v)} />
                <HudSlider label="FLIGHT MACH NUMBER" value={p.MN} min={0.0} max={0.88} step={0.02} unit="M" onChange={v => setVal("MN", v)} />
                <HudSlider label="POWER CODE (PC)" value={p.PC} min={0.2} max={1.0} step={0.05} onChange={v => setVal("PC", v)} />
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            <SolverStatusStrip status={error ? "error" : "ok"} fidelity="Empirical Flight Deck Fit" />

            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] DECK INTERPOLATION ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top 4 KPI Cards (Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="NET THRUST (Fn)" value={fn_kN != null ? fn_kN : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="thrust" sub="CF34-10E (UNVALIDATED EMPIRICAL FIT)" />
              <HudKpi label="FUEL FLOW (Wf)" value={wf_kgh != null ? wf_kgh : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="fuelflow_kgh" decimals={1} sub="Empirical Rate" />
              <HudKpi label="TSFC (SPECIFIC FUEL CONS)" value={tsfc != null ? tsfc : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="tsfc" decimals={2} sub="g/(kN·s)" />
              <HudKpi label="CORRECTED AIRFLOW (Wc)" value={wc_kgs != null ? wc_kgs : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="massflow" decimals={1} sub="Fan Face" />
            </div>

            {/* Middle: 2 Sweep Charts */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[SWEEP] NET THRUST [kN] VS ALTITUDE [FT]</span>
                  <span className="tech-tag optimal">LAPSE CURVE</span>
                </div>
                <div className="panel-card-body">
                  <div className="chart-box" style={{ height: "260px" }}><canvas ref={altRef} /></div>
                </div>
              </div>

              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[SWEEP] NET THRUST [kN] VS FLIGHT MACH</span>
                  <span className="tech-tag optimal">RAM RECOVERY</span>
                </div>
                <div className="panel-card-body">
                  <div className="chart-box" style={{ height: "260px" }}><canvas ref={machRef} /></div>
                </div>
              </div>
            </div>

            {/* Restored Bottom Panel: Operational Status & Certification Limits */}
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[ENVELOPE] CF34 OPERATIONAL STATUS & CERTIFICATION LIMITS</span>
                <span className="tech-tag" style={{borderColor: '#F59E0B', color: '#F59E0B'}}>CF34-10E // UNVALIDATED EMPIRICAL FIT</span>
              </div>
              <div className="panel-card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", color: "var(--text-silver)" }}>
                  <div>
                    <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-amber)", marginBottom: "4px" }}>OPERATING CONDITIONS</div>
                    <div>GEOPOTENTIAL ALTITUDE: <strong style={{ color: "#ffffff" }}>{fmtInt(p.alt)} FT</strong></div>
                    <div>FLIGHT MACH NUMBER: <strong style={{ color: "#ffffff" }}>{fmt(p.MN, 2)}</strong></div>
                    <div>THROTTLE RATING (PC): <strong style={{ color: "#ffffff" }}>{fmt(p.PC, 2)} ({Math.round(p.PC * 100)}%)</strong></div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-emerald)", marginBottom: "4px" }}>SAFETY MARGINS & BOUNDARIES</div>
                    <div>MAX OPERATING ALT: <strong style={{ color: "#ffffff" }}>41,000 FT</strong></div>
                    <div>MAX OPERATING MACH (M_MO): <strong style={{ color: "#ffffff" }}>0.85 M</strong></div>
                    <div>TRILINEAR BOUNDARY: <span className="tech-tag optimal">INTERIOR GRID MATCH</span></div>
                  </div>
                </div>
              </div>
            </div>
          </main>
        </div>
      );
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 04: OFF-DESIGN COMPONENT MATCHING & MAPS
    // ═════════════════════════════════════════════════════════════════════════
    function OffDesignPanel() {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [result, setResult] = useState(null);
      const [mapData, setMapData] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        N_rel: 1.0,
        alt: 35000.0,
        mach: 0.80,
        throttle_pos: 1.0,
        cpr_des: 8.0,
        eta_c_des: 0.85,
        mdot_corr_des: 20.0,
        eta_i: 0.98,
        eta_t: 0.88,
        mech_loss: 0.99,
        eta_b: 0.99,
        dp_over_p: 0.04,
        T_max: 1550.0,
        eta_noz: 0.98
      });

      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const solveOffDesign = useCallback(async (currentP) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const [mapRes, singleRes] = await Promise.all([
            fetch(`${API}/api/off_design/map?cpr_des=${currentP.cpr_des}&eta_c_des=${currentP.eta_c_des}&mdot_corr_des=${currentP.mdot_corr_des}`),
            fetch(`${API}/api/off_design/single`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(currentP)
            })
          ]);

          if (reqId !== reqSeqRef.current) return;
          if (mapRes.ok) setMapData(await mapRes.json());
          if (!singleRes.ok) {
            const err = await singleRes.json().catch(() => ({ detail: singleRes.statusText }));
            throw new Error(err.detail || "Off-design component matching failed");
          }
          setResult(await singleRes.json());
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, []);

      const debouncedSolve = useDebouncedCallback(solveOffDesign, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          solveOffDesign(p);
          return;
        }
        debouncedSolve(p);
      }, [p, debouncedSolve, solveOffDesign]);

      const sm = result?.Surge_Margin_pct ?? result?.surge_margin_pct ?? null;
      const opCPR = result?.CPR ?? result?.cpr ?? null;
      const opMdot = result?.mdot_corr ?? null;
      const opEta = result?.eta_c ?? null;
      const opTIT = result?.TIT ?? result?.T04 ?? result?.TIT_K ?? null;
      const opThrust = result?.Thrust_kN ?? (result?.thrust_N ? result.thrust_N / 1000 : result?.Fn_kN ?? null);
      const opA8 = result?.A8_target ?? result?.A8 ?? null;

      const mapCanvasRef = useRef(null);

      // High-contrast progressive titanium palette for speed lines
      const speedColors = ["#475569", "#64748B", "#94A3B8", "#CBD5E1", "#E2E8F0", "#F8FAFC", "#F59E0B", "#FCD34D"];

      const mapDatasets = useMemo(() => {
        const ds = [];
        if (mapData?.speed_lines) {
          mapData.speed_lines.forEach((sl, idx) => {
            const isNom = Math.abs((sl.N_pct || sl.N_rel * 100) - 100) < 1;
            const lineColor = isNom ? "#F59E0B" : (speedColors[idx % speedColors.length] || "#94A3B8");
            ds.push({
              label: `N = ${sl.N_pct || Math.round(sl.N_rel * 100)}%`,
              data: [...sl.points].sort((a, b) => a.mdot_corr - b.mdot_corr).map(pt => ({
                x: pt.mdot_corr,
                y: pt.cpr != null ? pt.cpr : (pt.PR != null ? pt.PR : pt.y)
              })),
              borderColor: lineColor,
              borderWidth: isNom ? 2.5 : 1.2,
              tension: 0.25,
              pointRadius: 0,
              showLine: true
            });
          });
        }

        if (mapData?.surge_line) {
          ds.push({
            label: "SURGE BOUNDARY (STABILITY LIMIT)",
            data: mapData.surge_line.map(pt => ({
              x: pt.mdot_corr,
              y: pt.cpr != null ? pt.cpr : (pt.PR != null ? pt.PR : pt.y)
            })),
            borderColor: "#EF4444",
            borderDash: [6, 4],
            borderWidth: 2,
            pointRadius: 2,
            pointBackgroundColor: "#EF4444",
            showLine: true
          });
        }

        // Design Point Marker
        ds.push({
          label: `DESIGN POINT (CPR: ${fmt(p.cpr_des, 1)}, ṁ: ${fmt(p.mdot_corr_des, 1)} kg/s)`,
          data: [{ x: p.mdot_corr_des, y: p.cpr_des }],
          pointRadius: 8,
          pointStyle: "rectRot",
          pointBackgroundColor: "#F2F4F8",
          borderColor: "#090B0E",
          borderWidth: 2,
          showLine: false
        });

        // Current Operating Point Marker
        if (result) {
          ds.push({
            label: `OPERATING POINT (CPR: ${fmt(opCPR, 2)}, ṁ: ${fmt(opMdot, 1)} kg/s)`,
            data: [{ x: opMdot, y: opCPR }],
            pointRadius: 9,
            pointStyle: "rectRot",
            pointBackgroundColor: "#F59E0B",
            borderColor: "#FFFFFF",
            borderWidth: 2.5,
            showLine: false
          });
        }
        return ds;
      }, [mapData, result, p.cpr_des, p.mdot_corr_des, opCPR, opMdot]);

      useNeonChart(mapCanvasRef, "line", { datasets: mapDatasets }, {
        scales: {
          x: { type: "linear", title: { display: true, text: "CORRECTED MASS FLOW ṁ_corr [kg/s]", color: "#8E95A5" } },
          y: { type: "linear", title: { display: true, text: "COMPRESSOR PRESSURE RATIO (CPR)", color: "#8E95A5" } }
        }
      });

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[CONTROLS] OFF-DESIGN MATCHING</span>
                <span className="tech-tag info">
                  VALIDATION: TIER C [SCALED COMPONENT MAPS]
                </span>
              </div>
              <div className="panel-card-body">
                <HudSlider label="RELATIVE SPEED (N/N_des)" value={p.N_rel} min={0.50} max={1.10} step={0.01} onChange={v => setVal("N_rel", v)} />
                <HudSlider label="ALTITUDE" value={p.alt} min={0} max={50000} step={1000} unit="FT" onChange={v => setVal("alt", v)} />
                <HudSlider label="FLIGHT MACH" value={p.mach} min={0.0} max={0.95} step={0.05} unit="M" onChange={v => setVal("mach", v)} />
                <HudSlider label="THROTTLE POSITION" value={p.throttle_pos} min={0.2} max={1.0} step={0.05} onChange={v => setVal("throttle_pos", v)} />
                <div style={{ height: "1px", background: "var(--border-hairline)", margin: "8px 0" }} />
                <HudSlider label="DESIGN CPR" value={p.cpr_des} min={4.0} max={25.0} step={0.5} onChange={v => setVal("cpr_des", v)} />
                <HudSlider label="DESIGN MASS FLOW" value={p.mdot_corr_des} min={5.0} max={60.0} step={1.0} unit="KG/S" onChange={v => setVal("mdot_corr_des", v)} />
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            <SolverStatusStrip metadata={result?.metadata} fidelity="Scaled Component Map" />

            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] SOLVER ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top 5 KPI Cards (Restored 5th: Nozzle Area A8) */}
            <div className="kpi-grid">
              <HudKpi label="NET THRUST" value={opThrust != null ? opThrust : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="thrust" sub="Off-Design Output" />
              <HudKpi label="OPERATING CPR" value={opCPR != null ? fmt(opCPR, 2) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub={`Target: ${fmt(p.cpr_des, 1)}`} />
              <HudKpi label="CORRECTED FLOW" value={opMdot != null ? opMdot : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="massflow" decimals={1} sub={`Design: ${fmt(p.mdot_corr_des, 1)}`} />
              <HudKpi 
                label="SURGE MARGIN" 
                value={sm != null ? fmt(sm, 1) : (loading ? "COMPUTING..." : "NOT COMPUTED")} 
                unit={sm != null ? "%" : ""} 
                subTag={sm != null ? {
                  type: sm >= 15 ? "optimal" : (sm >= 8 ? "warning" : "critical"),
                  label: sm >= 15 ? "HEALTHY" : (sm >= 8 ? "LOW MARGIN" : "SURGE RISK")
                } : null}
              />
              <HudKpi label="NOZZLE AREA (A8)" value={opA8 != null ? fmt(opA8, 4) : (loading ? "COMPUTING..." : "NOT COMPUTED")} unit={opA8 != null ? "m²" : ""} sub={result?.A4_star_m2 ? `A4* NGV: ${fmt(result.A4_star_m2, 4)} m²` : "Locked Hardware"} />
            </div>

            {/* Middle: Compressor Map */}
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[COMPRESSOR-MAP] SPEED LINES (50%-110%), SURGE BOUNDARY & OPERATING POINT</span>
                <span className="tech-tag optimal">BETA-LINE PARAMETERIZATION</span>
              </div>
              <div className="panel-card-body">
                <div className="chart-box" style={{ height: "300px" }}><canvas ref={mapCanvasRef} /></div>
              </div>
            </div>

            {/* Restored 5-Row Variance Matrix Table */}
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[VARIANCE MATRIX] DESIGN BENCHMARK VS LIVE OFF-DESIGN STATE</span>
                <span className="tech-tag optimal">ALL 5 PARAMETERS COMPUTED</span>
              </div>
              <div className="table-container">
                <table className="blueprint-table">
                  <thead>
                    <tr>
                      <th>PARAMETER</th>
                      <th className="num">DESIGN BENCHMARK</th>
                      <th className="num">OFF-DESIGN ACTUAL</th>
                      <th className="num">ABSOLUTE VARIANCE (Δ)</th>
                      <th className="num">PERCENT OFFSET (%)</th>
                      <th>AERODYNAMIC STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Row 1: CPR */}
                    <tr>
                      <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>COMPRESSOR PRESSURE RATIO (CPR)</td>
                      <td className="num">{fmt(p.cpr_des, 2)}</td>
                      <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(opCPR, 2)}</td>
                      <td className="num" style={{ color: opCPR >= p.cpr_des ? "var(--accent-emerald)" : "var(--accent-amber)" }}>
                        {opCPR >= p.cpr_des ? `+${fmt(opCPR - p.cpr_des, 2)}` : fmt(opCPR - p.cpr_des, 2)}
                      </td>
                      <td className="num">{fmt(((opCPR - p.cpr_des) / p.cpr_des) * 100, 1)}%</td>
                      <td><span className="tech-tag optimal">{opCPR >= p.cpr_des ? "SUPERCHARGED" : "THROTTLED"}</span></td>
                    </tr>

                    {/* Row 2: TIT */}
                    <tr>
                      <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>TURBINE INLET TEMP (TIT) [K]</td>
                      <td className="num">{fmt(p.T_max, 1)} K</td>
                      <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(opTIT, 1)} K</td>
                      <td className="num" style={{ color: opTIT <= p.T_max ? "var(--accent-emerald)" : "var(--accent-crimson)" }}>
                        {opTIT >= p.T_max ? `+${fmt(opTIT - p.T_max, 1)}` : fmt(opTIT - p.T_max, 1)} K
                      </td>
                      <td className="num">{fmt(((opTIT - p.T_max) / p.T_max) * 100, 1)}%</td>
                      <td>
                        <span className={`tech-tag ${opTIT <= p.T_max ? "optimal" : "critical"}`}>
                          {opTIT <= p.T_max ? "THERMAL MARGIN NOMINAL" : "TIT LIMIT EXCEEDED"}
                        </span>
                      </td>
                    </tr>

                    {/* Row 3: Isentropic Efficiency */}
                    <tr>
                      <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>COMPRESSOR ISENTROPIC EFFICIENCY (η_c)</td>
                      <td className="num">{fmt(p.eta_c_des, 3)}</td>
                      <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(opEta, 3)}</td>
                      <td className="num">{fmt(opEta - p.eta_c_des, 3)}</td>
                      <td className="num">{fmt(((opEta - p.eta_c_des) / p.eta_c_des) * 100, 1)}%</td>
                      <td>
                        <span className={`tech-tag ${opEta >= p.eta_c_des - 0.03 ? "optimal" : "warning"}`}>
                          {opEta >= p.eta_c_des - 0.03 ? "NOMINAL η" : "DEGRADED η"}
                        </span>
                      </td>
                    </tr>

                    {/* Row 4: Corrected Mass Flow */}
                    <tr>
                      <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>CORRECTED MASS FLOW (kg/s)</td>
                      <td className="num">{fmt(p.mdot_corr_des, 2)}</td>
                      <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(opMdot, 2)}</td>
                      <td className="num" style={{ color: opMdot >= p.mdot_corr_des ? "var(--accent-emerald)" : "var(--accent-amber)" }}>
                        {opMdot >= p.mdot_corr_des ? `+${fmt(opMdot - p.mdot_corr_des, 2)}` : fmt(opMdot - p.mdot_corr_des, 2)}
                      </td>
                      <td className="num">{fmt(((opMdot - p.mdot_corr_des) / p.mdot_corr_des) * 100, 1)}%</td>
                      <td><span className="tech-tag optimal">{opMdot >= p.mdot_corr_des ? "HIGH MASS FLOW" : "PART-LOAD FLOW"}</span></td>
                    </tr>

                    {/* Row 5: Surge Margin */}
                    <tr>
                      <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>SURGE MARGIN (%SM)</td>
                      <td className="num">20.0% (STANDARD)</td>
                      <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(sm, 1)}%</td>
                      <td className="num">{fmt(sm - 20.0, 1)}%</td>
                      <td className="num">---</td>
                      <td>
                        <span className={`tech-tag ${sm >= 15 ? "optimal" : (sm >= 8 ? "warning" : "critical")}`}>
                          {sm >= 15 ? "HEALTHY STABILITY" : (sm >= 8 ? "ADVISORY MARGIN" : "SURGE IMMINENT")}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </main>
        </div>
      );
    }
"""
