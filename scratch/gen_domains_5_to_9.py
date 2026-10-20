DOMAINS_5_TO_9 = """
    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 05: 1D MEAN-LINE STAGE AERODYNAMICS & ANNULUS SIZING
    // ═════════════════════════════════════════════════════════════════════════
    function VelocityTrianglesSvg({ inlet, exit, type = "compressor" }) {
      if (!inlet || !exit) return (
        <div style={{ padding: "20px", textAlign: "center", color: "#485063" }}>
          [VELOCITY TRIANGLES STANDBY]
        </div>
      );

      const U = Number(inlet.U || exit.U || 350.0);
      const Ca1 = Number(inlet.C_a ?? inlet.Ca ?? 180.0);
      const Ctheta1 = Number(inlet.C_theta ?? inlet.Ctheta ?? 0.0);
      const C1 = Number(inlet.C ?? Math.hypot(Ca1, Ctheta1));
      const W1 = Number(inlet.W ?? Math.hypot(Ca1, Ctheta1 - U));
      const alpha1 = Number(inlet.alpha_deg ?? 0.0);
      const beta1 = Number(inlet.beta_deg ?? (Math.atan2(Ctheta1 - U, Ca1) * 180 / Math.PI));

      const Ca2 = Number(exit.C_a ?? exit.Ca ?? 175.0);
      const Ctheta2 = Number(exit.C_theta ?? exit.Ctheta ?? 120.0);
      const C2 = Number(exit.C ?? Math.hypot(Ca2, Ctheta2));
      const W2 = Number(exit.W ?? Math.hypot(Ca2, Ctheta2 - U));
      const alpha2 = Number(exit.alpha_deg ?? (Math.atan2(Ctheta2, Ca2) * 180 / Math.PI));
      const beta2 = Number(exit.beta_deg ?? 45.0);

      const maxVel = Math.max(U, Ca1, Ca2, Math.abs(Ctheta1), Math.abs(Ctheta2), C1, W1, C2, W2, 140);
      const scale = 135 / maxVel;

      const isTurbine = type === "turbine";
      const title1 = isTurbine ? "STATOR EXIT (NGV) TRIANGLE" : "ROTOR INLET TRIANGLE (STA 1)";
      const title2 = isTurbine ? "ROTOR EXIT TRIANGLE" : "ROTOR EXIT TRIANGLE (STA 2)";

      // Top apex coordinates (flow moving downward from apex)
      const y0 = 30;
      const x1 = 165;
      const x2 = 485;

      // Triangle 1 geometry satisfying C = U + W
      const ca1_h = Ca1 * scale;
      const c1_x = x1 + Ctheta1 * scale;
      const w1_x = x1 + (Ctheta1 - U) * scale;
      const base1_y = y0 + ca1_h;

      // Triangle 2 geometry satisfying C = U + W
      const ca2_h = Ca2 * scale;
      const c2_x = x2 + Ctheta2 * scale;
      const w2_x = x2 + (Ctheta2 - U) * scale;
      const base2_y = y0 + ca2_h;

      return (
        <div style={{ background: "#0B0D11", border: "1px solid var(--border-hairline)", padding: "10px 14px" }}>
          <svg viewBox="0 0 660 215" style={{ width: "100%", maxHeight: "215px" }}>
            <defs>
              <marker id="arr-blue" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#38BDF8" />
              </marker>
              <marker id="arr-amber" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
              </marker>
              <marker id="arr-white" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#F2F4F8" />
              </marker>
            </defs>

            {/* Station 1 Triangle Header */}
            <text x={x1} y="18" fill="#38BDF8" fontSize="10" fontWeight="700" textAnchor="middle">{title1}</text>

            {/* Station 1: Vector C1 (Absolute) from apex down to (c1_x, base1_y) */}
            <line x1={x1} y1={y0} x2={c1_x} y2={base1_y} stroke="#38BDF8" strokeWidth="2.5" markerEnd="url(#arr-blue)" />
            <text x={(x1 + c1_x) / 2 + 12} y={(y0 + base1_y) / 2} fill="#38BDF8" fontSize="10" fontWeight="700">C₁={fmt(C1, 0)}</text>

            {/* Station 1: Vector W1 (Relative) from apex down to (w1_x, base1_y) */}
            <line x1={x1} y1={y0} x2={w1_x} y2={base1_y} stroke="#F59E0B" strokeWidth="2.5" markerEnd="url(#arr-amber)" />
            <text x={(x1 + w1_x) / 2 - 32} y={(y0 + base1_y) / 2} fill="#F59E0B" fontSize="10" fontWeight="700">W₁={fmt(W1, 0)}</text>

            {/* Station 1: Vector U (Blade Speed) horizontally from w1_x to c1_x */}
            <line x1={w1_x} y1={base1_y} x2={c1_x} y2={base1_y} stroke="#F2F4F8" strokeWidth="2.5" markerEnd="url(#arr-white)" />
            <text x={(w1_x + c1_x) / 2} y={base1_y + 15} fill="#F2F4F8" fontSize="9.5" textAnchor="middle">U={fmt(U, 0)} m/s</text>

            {/* Station 1 Angles Info */}
            <text x={x1} y={base1_y + 32} fill="#8E95A5" fontSize="9" textAnchor="middle">
              α₁={fmt(alpha1, 1)}° | β₁={fmt(beta1, 1)}° | Ca₁={fmt(Ca1, 0)} m/s
            </text>

            {/* Stage Divider */}
            <line x1="330" y1="12" x2="330" y2="205" stroke="#242832" strokeDasharray="3,3" />

            {/* Station 2 Triangle Header */}
            <text x={x2} y="18" fill="#38BDF8" fontSize="10" fontWeight="700" textAnchor="middle">{title2}</text>

            {/* Station 2: Vector C2 (Absolute) from apex down to (c2_x, base2_y) */}
            <line x1={x2} y1={y0} x2={c2_x} y2={base2_y} stroke="#38BDF8" strokeWidth="2.5" markerEnd="url(#arr-blue)" />
            <text x={(x2 + c2_x) / 2 + 12} y={(y0 + base2_y) / 2} fill="#38BDF8" fontSize="10" fontWeight="700">C₂={fmt(C2, 0)}</text>

            {/* Station 2: Vector W2 (Relative) from apex down to (w2_x, base2_y) */}
            <line x1={x2} y1={y0} x2={w2_x} y2={base2_y} stroke="#F59E0B" strokeWidth="2.5" markerEnd="url(#arr-amber)" />
            <text x={(x2 + w2_x) / 2 - 32} y={(y0 + base2_y) / 2} fill="#F59E0B" fontSize="10" fontWeight="700">W₂={fmt(W2, 0)}</text>

            {/* Station 2: Vector U (Blade Speed) horizontally from w2_x to c2_x */}
            <line x1={w2_x} y1={base2_y} x2={c2_x} y2={base2_y} stroke="#F2F4F8" strokeWidth="2.5" markerEnd="url(#arr-white)" />
            <text x={(w2_x + c2_x) / 2} y={base2_y + 15} fill="#F2F4F8" fontSize="9.5" textAnchor="middle">U={fmt(U, 0)} m/s</text>

            {/* Station 2 Angles Info */}
            <text x={x2} y={base2_y + 32} fill="#8E95A5" fontSize="9" textAnchor="middle">
              α₂={fmt(alpha2, 1)}° | β₂={fmt(beta2, 1)}° | Ca₂={fmt(Ca2, 0)} m/s
            </text>
          </svg>
        </div>
      );
    }

    function AnnulusSvg({ stages }) {
      if (!stages || !stages.length) return null;
      const n = stages.length;
      const w = 620;
      const h = 100;
      const dx = w / (n + 1);

      // Extract tip and hub radii
      const r_tip_pts = [];
      const r_hub_pts = [];
      stages.forEach((stg, i) => {
        const x = dx * (i + 1);
        const r_hub = stg.r_hub_m || 0.22;
        const r_tip = stg.r_tip_m || 0.42;
        r_tip_pts.push({ x, y: 50 - (r_tip * 90) });
        r_hub_pts.push({ x, y: 50 + (r_hub * 90) });
      });

      return (
        <div style={{ background: "#0B0D11", border: "1px solid var(--border-hairline)", padding: "10px", marginTop: "10px" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-amber)", marginBottom: "4px" }}>
            MERIDIONAL ANNULUS CONVERGENCE PROFILE (CASING & HUB)
          </div>
          <svg viewBox="0 0 640 100" style={{ width: "100%", maxHeight: "100px" }}>
            {/* Centerline */}
            <line x1="20" y1="50" x2="620" y2="50" stroke="#485063" strokeDasharray="4,4" />
            <text x="30" y="46" fill="#8E95A5" fontSize="8">ROTATIONAL AXIS</text>

            {/* Blade Stages vertical spans */}
            {stages.map((stg, i) => {
              const x = dx * (i + 1);
              const r_hub = stg.r_hub_m || 0.22;
              const r_tip = stg.r_tip_m || 0.42;
              const y1 = 50 - (r_tip * 90);
              const y2 = 50 + (r_hub * 90);
              return (
                <g key={i}>
                  <line x1={x} y1={y1} x2={x} y2={y2} stroke="#38BDF8" strokeWidth="2.5" />
                  <text x={x} y={y1 - 6} fill="#F2F4F8" fontSize="8" textAnchor="middle">S{i + 1}</text>
                </g>
              );
            })}

            {/* Casing Top Line */}
            {r_tip_pts.length > 1 && (
              <polyline
                points={r_tip_pts.map(p => `${p.x},${p.y}`).join(" ")}
                fill="none"
                stroke="#F2F4F8"
                strokeWidth="1.5"
              />
            )}

            {/* Hub Bottom Line */}
            {r_hub_pts.length > 1 && (
              <polyline
                points={r_hub_pts.map(p => `${p.x},${p.y}`).join(" ")}
                fill="none"
                stroke="#F59E0B"
                strokeWidth="1.5"
              />
            )}
          </svg>
        </div>
      );
    }

    function MeanLinePanel() {
      const [mode, setMode] = useState("compressor"); // "compressor", "multistage", "turbine"
      const [selectedStage, setSelectedStage] = useState(0);
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [result, setResult] = useState(null);
      const reqSeqRef = useRef(0);

      const [compParams, setCompParams] = useState({
        U: 350.0,
        C_a1: 180.0,
        C_a2: 175.0,
        alpha_1_deg: 0.0,
        beta_2_deg: 45.0,
        alpha_3_deg: 0.0,
        r_mean: 0.35,
        T01: 288.15,
        P01: 101325.0,
        mdot: 35.0,
        eta_stage: 0.89
      });

      const [multiParams, setMultiParams] = useState({
        n_stages: 6,
        CPR: 8.0,
        T0_inlet: 288.15,
        P0_inlet: 101325.0,
        N_rpm: 12000.0,
        r_mean: 0.28,
        C_a: 160.0,
        reaction: 0.50,
        eta_poly: 0.88,
        mdot: 20.0
      });

      const [turbParams, setTurbParams] = useState({
        U: 380.0,
        C_a: 200.0,
        alpha_1_deg: 0.0,
        alpha_2_deg: 65.0,
        beta_3_deg: -60.0,
        r_mean: 0.30,
        T01: 1450.0,
        P01: 1200000.0,
        mdot: 25.0,
        eta_stage: 0.91
      });

      const setComp = (k, v) => setCompParams(prev => ({ ...prev, [k]: v }));
      const setMulti = (k, v) => setMultiParams(prev => ({ ...prev, [k]: v }));
      const setTurb = (k, v) => setTurbParams(prev => ({ ...prev, [k]: v }));

      const solveStage = useCallback(async () => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          let endpoint = "/api/meanline/compressor_stage";
          let body = compParams;

          if (mode === "multistage") {
            endpoint = "/api/meanline/multistage_compressor";
            body = multiParams;
          } else if (mode === "turbine") {
            endpoint = "/api/meanline/turbine_stage";
            body = turbParams;
          }

          const resp = await fetch(`${API}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Aero stage solver failed");
          }
          const data = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setResult(data);
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, [mode, compParams, multiParams, turbParams]);

      const debouncedSolve = useDebouncedCallback(solveStage, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          solveStage();
          return;
        }
        debouncedSolve();
      }, [mode, compParams, multiParams, turbParams, debouncedSolve, solveStage]);

      // Extract active velocity triangles safely
      let inletTri = null;
      let exitTri = null;
      let stageCount = 1;

      if (mode === "compressor" && result) {
        inletTri = result.rotor_inlet_triangle;
        exitTri = result.rotor_exit_triangle;
      } else if (mode === "multistage" && result?.stages?.length) {
        stageCount = result.stages.length;
        const stg = result.stages[Math.min(selectedStage, stageCount - 1)] || result.stages[0];
        inletTri = stg?.rotor_inlet_triangle || stg?.inlet_triangle || stg?.velocity_triangles?.rotor_inlet;
        exitTri = stg?.rotor_exit_triangle || stg?.exit_triangle || stg?.velocity_triangles?.rotor_exit;
      } else if (mode === "turbine" && result) {
        inletTri = result.stator_exit_triangle;
        exitTri = result.rotor_exit_triangle;
      }

      const activeStg = (mode === "multistage" && result?.stages?.length) ? (result.stages[Math.min(selectedStage, result.stages.length - 1)] || result.stages[0]) : result;

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar with 3 Restored Sub-Tabs */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[MODE] MEAN-LINE TURBOMACHINERY</span>
                <span className="tech-tag optimal">{mode.toUpperCase()}</span>
              </div>
              <div className="panel-card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px", marginBottom: "10px" }}>
                  <button className={`blueprint-btn ${mode === "compressor" ? "active" : ""}`} onClick={() => setMode("compressor")}>
                    COMP STG
                  </button>
                  <button className={`blueprint-btn ${mode === "multistage" ? "active" : ""}`} onClick={() => setMode("multistage")}>
                    ANNULUS
                  </button>
                  <button className={`blueprint-btn ${mode === "turbine" ? "active" : ""}`} onClick={() => setMode("turbine")}>
                    TURB STG
                  </button>
                </div>

                {mode === "compressor" && (
                  <div>
                    <HudSlider label="BLADE SPEED (U)" value={compParams.U} min={200} max={500} step={10} unit="M/S" onChange={v => setComp("U", v)} />
                    <HudSlider label="AXIAL INLET VEL (Ca1)" value={compParams.C_a1} min={100} max={250} step={5} unit="M/S" onChange={v => setComp("C_a1", v)} />
                    <HudSlider label="AXIAL EXIT VEL (Ca2)" value={compParams.C_a2} min={100} max={250} step={5} unit="M/S" onChange={v => setComp("C_a2", v)} />
                    <HudSlider label="INLET FLOW ANGLE (α1)" value={compParams.alpha_1_deg} min={-20} max={40} step={2} unit="DEG" onChange={v => setComp("alpha_1_deg", v)} />
                    <HudSlider label="ROTOR EXIT REL ANGLE (β2)" value={compParams.beta_2_deg} min={20} max={65} step={1} unit="DEG" onChange={v => setComp("beta_2_deg", v)} />
                    <HudSlider label="MEAN RADIUS (r_mean)" value={compParams.r_mean} min={0.15} max={0.80} step={0.02} unit="M" onChange={v => setComp("r_mean", v)} />
                  </div>
                )}

                {mode === "multistage" && (
                  <div>
                    <HudSlider label="NUMBER OF STAGES" value={multiParams.n_stages} min={1} max={16} step={1} onChange={v => setMulti("n_stages", v)} />
                    <HudSlider label="TOTAL PRESSURE RATIO" value={multiParams.CPR} min={3.0} max={30.0} step={0.5} onChange={v => setMulti("CPR", v)} />
                    <HudSlider label="ROTOR SHAFT SPEED" value={multiParams.N_rpm} min={5000} max={25000} step={500} unit="RPM" onChange={v => setMulti("N_rpm", v)} />
                    <HudSlider label="CONSTANT AXIAL VEL (Ca)" value={multiParams.C_a} min={120} max={220} step={5} unit="M/S" onChange={v => setMulti("C_a", v)} />
                    <HudSlider label="STAGE DEGREE OF REACTION" value={multiParams.reaction} min={0.30} max={0.70} step={0.05} onChange={v => setMulti("reaction", v)} />
                  </div>
                )}

                {mode === "turbine" && (
                  <div>
                    <HudSlider label="BLADE SPEED (U)" value={turbParams.U} min={250} max={550} step={10} unit="M/S" onChange={v => setTurb("U", v)} />
                    <HudSlider label="AXIAL VELOCITY (Ca)" value={turbParams.C_a} min={120} max={280} step={5} unit="M/S" onChange={v => setTurb("C_a", v)} />
                    <HudSlider label="STATOR EXIT SWIRL (α2)" value={turbParams.alpha_2_deg} min={45} max={75} step={1} unit="DEG" onChange={v => setTurb("alpha_2_deg", v)} />
                    <HudSlider label="ROTOR EXIT REL ANGLE (β3)" value={turbParams.beta_3_deg} min={-75} max={-40} step={1} unit="DEG" onChange={v => setTurb("beta_3_deg", v)} />
                  </div>
                )}
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] AERO SOLVER ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top 6 KPI Cards (Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="STAGE LOADING (ψ)" value={activeStg?.loading_coefficient_psi != null || activeStg?.psi != null ? fmt(activeStg.loading_coefficient_psi ?? activeStg.psi, 3) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Δh₀ / U²" />
              <HudKpi label="FLOW COEFFICIENT (ϕ)" value={activeStg?.flow_coefficient_phi != null || activeStg?.phi != null ? fmt(activeStg.flow_coefficient_phi ?? activeStg.phi, 3) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Ca / U" />
              <HudKpi label="DEGREE OF REACTION (R)" value={activeStg?.degree_of_reaction_R != null || activeStg?.reaction != null ? fmt(activeStg.degree_of_reaction_R ?? activeStg.reaction, 3) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Rotor Enthalpy Rise" />
              {mode === "turbine" ? (
                <HudKpi label="ZWEIFEL COEFF (ψ_z)" value={result?.zweifel_coefficient != null || result?.zweifel_coefficient_stator != null ? fmt(result.zweifel_coefficient ?? result.zweifel_coefficient_stator, 2) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Aerodynamic Loading" />
              ) : (
                <HudKpi label="DE HALLER RATIO" value={activeStg?.de_haller_ratio != null || (inletTri && exitTri && inletTri.W) ? fmt(activeStg?.de_haller_ratio || (inletTri && exitTri ? exitTri.W / inletTri.W : 0.76), 3) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="W₂ / W₁ ≥ 0.72" />
              )}
              <HudKpi label="STAGE PR" value={activeStg?.stage_PR != null || activeStg?.PR_stage != null ? fmt(activeStg.stage_PR ?? activeStg.PR_stage, 3) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Isentropic Work" />
              <HudKpi label="STAGE WORK (Δh₀)" value={activeStg?.delta_h0_kJkg != null || activeStg?.delta_h0 != null ? fmt(activeStg.delta_h0_kJkg ?? (activeStg.delta_h0 / 1000), 1) : (loading ? "COMPUTING..." : "NOT COMPUTED")} unit="kJ/kg" sub="Euler Equation" />
            </div>

            {/* Velocity Triangles SVG */}
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[AERO-KINEMATICS] DYNAMIC VELOCITY TRIANGLES ({typeUpper(mode)})</span>
                <span className="tech-tag optimal">
                  {mode === "multistage" ? `STAGE ${selectedStage + 1} OF ${stageCount}` : "SINGLE STAGE"}
                </span>
              </div>
              <div className="panel-card-body">
                <VelocityTrianglesSvg
                  inlet={inletTri}
                  exit={exitTri}
                  type={mode === "turbine" ? "turbine" : "compressor"}
                />
              </div>
            </div>

            {/* Annulus Profile & Restored Stage Selection Buttons (when in Annulus mode) */}
            {mode === "multistage" && result?.stages && (
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[ANNULUS-SINK] MULTI-STAGE MERIDIONAL PROFILE & STAGE PROBING</span>
                  <span className="tech-tag optimal">{result.stages.length} ACTIVE STAGES</span>
                </div>
                <div className="panel-card-body">
                  <AnnulusSvg stages={result.stages} />
                  
                  {/* Restored Dynamic Stage Buttons */}
                  <div style={{ marginTop: "10px" }}>
                    <div style={{ fontSize: "9.5px", color: "var(--text-silver)", marginBottom: "4px" }}>
                      CLICK STAGE TO INSPECT VELOCITY TRIANGLES & LOADING:
                    </div>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {result.stages.map((stg, i) => (
                        <button
                          key={i}
                          className={`blueprint-btn ${selectedStage === i ? "active" : ""}`}
                          onClick={() => setSelectedStage(i)}
                          style={{ padding: "4px 8px", fontSize: "9.5px" }}
                        >
                          STAGE {i + 1} (PR: {fmt(stg.stage_PR || stg.PR_stage, 2)})
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      );
    }

    function typeUpper(m) {
      if (m === "compressor") return "COMPRESSOR ROTOR";
      if (m === "turbine") return "AXIAL TURBINE";
      return "MULTI-STAGE COMPRESSOR";
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 06: TURBOPROP INTEGRATED POWERTRAIN & PROPELLER DYNAMICS
    // ═════════════════════════════════════════════════════════════════════════
    function TurbopropSweepCharts({ sweepData }) {
      const r1 = useRef(null);
      const r2 = useRef(null);
      const r3 = useRef(null);
      const r4 = useRef(null);

      const pts = sweepData?.points || [];
      const labels = pts.map(p => fmt(p.sweep_val ?? p.CPR ?? p.mach ?? p.alt ?? 0, 1));

      const d1 = pts.length > 0 ? {
        labels,
        datasets: [{
          label: "SHAFT POWER [SHP]",
          data: pts.map(p => p.SHP ?? p.P_shaft_shp ?? 0),
          borderColor: "#38BDF8",
          backgroundColor: "rgba(56, 189, 248, 0.08)",
          fill: true, tension: 0.2, pointRadius: 3
        }]
      } : null;

      const d2 = pts.length > 0 ? {
        labels,
        datasets: [{
          label: "EQUIVALENT SHP [ESHP]",
          data: pts.map(p => p.ESHP ?? 0),
          borderColor: "#F59E0B",
          backgroundColor: "rgba(245, 158, 11, 0.08)",
          fill: true, tension: 0.2, pointRadius: 3
        }]
      } : null;

      const d3 = pts.length > 0 ? {
        labels,
        datasets: [{
          label: "PSFC [kg/(kW·h)]",
          data: pts.map(p => p.PSFC_kg_kWh ?? 0),
          borderColor: "#EF4444",
          backgroundColor: "rgba(239, 68, 68, 0.08)",
          fill: true, tension: 0.2, pointRadius: 3
        }]
      } : null;

      const d4 = pts.length > 0 ? {
        labels,
        datasets: [{
          label: "PROPULSIVE EFFICIENCY (η_prop)",
          data: pts.map(p => (p.eta_prop ?? p.propeller_efficiency ?? 0) * 100),
          borderColor: "#10B981",
          backgroundColor: "rgba(16, 185, 129, 0.08)",
          fill: true, tension: 0.2, pointRadius: 3
        }]
      } : null;

      useNeonChart(r1, "line", d1);
      useNeonChart(r2, "line", d2);
      useNeonChart(r3, "line", d3);
      useNeonChart(r4, "line", d4);

      return (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
          <div className="panel-card">
            <div className="panel-card-header"><span>[SWEEP] SHAFT HORSEPOWER</span><span className="tech-tag optimal">SHP</span></div>
            <div className="panel-card-body"><div className="chart-box" style={{ height: "200px" }}><canvas ref={r1} /></div></div>
          </div>
          <div className="panel-card">
            <div className="panel-card-header"><span>[SWEEP] EQUIVALENT SHAFT POWER</span><span className="tech-tag optimal">ESHP</span></div>
            <div className="panel-card-body"><div className="chart-box" style={{ height: "200px" }}><canvas ref={r2} /></div></div>
          </div>
          <div className="panel-card">
            <div className="panel-card-header"><span>[SWEEP] POWER SPECIFIC FUEL CONS</span><span className="tech-tag optimal">PSFC</span></div>
            <div className="panel-card-body"><div className="chart-box" style={{ height: "200px" }}><canvas ref={r3} /></div></div>
          </div>
          <div className="panel-card">
            <div className="panel-card-header"><span>[SWEEP] PROPULSIVE EFFICIENCY (%)</span><span className="tech-tag optimal">η_prop</span></div>
            <div className="panel-card-body"><div className="chart-box" style={{ height: "200px" }}><canvas ref={r4} /></div></div>
          </div>
        </div>
      );
    }

    function TurbopropPanel({ onUpdateStations, selectedStation, onSelectStation }) {
      const [mode, setMode] = useState("single"); // "single" or "sweep"
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        alt: 15000.0,
        mach: 0.40,
        CPR: 12.0,
        TIT: 1400.0,
        mdot_air: 10.0,
        A8: 0.08,
        prop_diameter_m: 3.2,
        prop_rpm: 1200.0,
        eta_i: 0.98,
        eta_c: 0.85,
        eta_b: 0.99,
        dp_over_p: 0.04,
        eta_hpt: 0.89,
        eta_pt: 0.90,
        eta_gearbox: 0.985,
        eta_mech_core: 0.99,
        eta_mech_pt: 0.98,
        eta_noz: 0.95,
        prop_eff_max: 0.84
      });

      const [sw, setSw] = useState({
        sweep_param: "mach",
        n_steps: 10,
        alt_fixed: 15000.0,
        mach_fixed: 0.40,
        cpr_fixed: 12.0,
        tit_fixed: 1400.0
      });

      const [res, setRes] = useState(null);
      const [sweepRes, setSweepRes] = useState(null);

      const setParam = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const runSingle = useCallback(async (currentP) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const resp = await fetch(`${API}/api/turboprop/single`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentP)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Turboprop calculation failed");
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

      const runSweep = useCallback(async (currentSw) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const resp = await fetch(`${API}/api/turboprop/sweep`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentSw)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Turboprop sweep failed");
          }
          const data = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setSweepRes(data);
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, []);

      const debouncedSingle = useDebouncedCallback(runSingle, 80);
      const debouncedSweep = useDebouncedCallback(runSweep, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          if (mode === "single") runSingle(p);
          else runSweep(sw);
          return;
        }
        if (mode === "single") debouncedSingle(p);
        else debouncedSweep(sw);
      }, [mode, p, sw, debouncedSingle, debouncedSweep, runSingle, runSweep]);

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar with Restored Mode Switcher */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[INPUT] TURBOPROP POWERTRAIN</span>
                <span className="tech-tag optimal">{mode === "single" ? "DESIGN POINT" : "PARAMETRIC"}</span>
              </div>
              <div className="panel-card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", marginBottom: "10px" }}>
                  <button className={`blueprint-btn ${mode === "single" ? "active" : ""}`} onClick={() => setMode("single")}>
                    DESIGN POINT
                  </button>
                  <button className={`blueprint-btn ${mode === "sweep" ? "active" : ""}`} onClick={() => setMode("sweep")}>
                    PARAMETRIC
                  </button>
                </div>

                {mode === "single" ? (
                  <div>
                    <HudSlider label="ALTITUDE" value={p.alt} min={0} max={30000} step={1000} unit="FT" onChange={v => setParam("alt", v)} />
                    <HudSlider label="FLIGHT MACH" value={p.mach} min={0.10} max={0.65} step={0.05} unit="M" onChange={v => setParam("mach", v)} />
                    <HudSlider label="PRESSURE RATIO (CPR)" value={p.CPR} min={4.0} max={24.0} step={1.0} onChange={v => setParam("CPR", v)} />
                    <HudSlider label="TURBINE INLET TEMP (TIT)" value={p.TIT} min={1000} max={1700} step={25} unit="K" onChange={v => setParam("TIT", v)} />
                    <HudSlider label="CORE AIR FLOW" value={p.mdot_air} min={2.0} max={30.0} step={1.0} unit="KG/S" onChange={v => setParam("mdot_air", v)} />
                    <HudSlider label="PROPELLER DIAMETER" value={p.prop_diameter_m} min={1.5} max={5.0} step={0.1} unit="M" onChange={v => setParam("prop_diameter_m", v)} />
                    <HudSlider label="PROPELLER RPM" value={p.prop_rpm} min={800} max={2400} step={50} unit="RPM" onChange={v => setParam("prop_rpm", v)} />
                  </div>
                ) : (
                  <div>
                    <div style={{ marginBottom: "6px", fontSize: "10px", color: "var(--text-silver)" }}>SWEEP VARIABLE:</div>
                    <select
                      className="blueprint-select"
                      value={sw.sweep_param}
                      onChange={e => setSw(prev => ({ ...prev, sweep_param: e.target.value }))}
                    >
                      <option value="mach">FLIGHT MACH NUMBER</option>
                      <option value="altitude">ALTITUDE</option>
                      <option value="cpr">PRESSURE RATIO (CPR)</option>
                      <option value="power">TIT / POWER LEVEL</option>
                    </select>
                    <HudSlider label="SWEEP STEPS" value={sw.n_steps} min={5} max={15} step={1} onChange={v => setSw(prev => ({ ...prev, n_steps: v }))} />
                  </div>
                )}
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] TURBOPROP ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top 6 KPI Cards (Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="SHAFT POWER" value={res?.P_shaft_kW != null ? res.P_shaft_kW : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="power" sub={`${res?.P_shaft_shp != null ? fmt(res.P_shaft_shp, 0) : "---"} shp`} />
              <HudKpi label="EQUIV SHAFT PWR" value={res?.ESHP != null ? fmt(res.ESHP, 0) : (loading ? "COMPUTING..." : "NOT COMPUTED")} unit="eshp" sub="Shaft + Jet Residual" />
              <HudKpi label="TOTAL THRUST" value={res?.F_total_kN != null ? res.F_total_kN : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="thrust" sub={`Prop: ${res ? fmt(res.F_prop_kN, 1) : "---"} kN`} />
              <HudKpi label="PROP EFFICIENCY" value={res?.eta_prop != null || res?.propeller_efficiency != null ? fmtPct(res.eta_prop || res.propeller_efficiency) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Hamilton Standard" />
              <HudKpi label="PSFC" value={res?.PSFC_kg_kWh != null ? fmt(res.PSFC_kg_kWh, 3) : (loading ? "COMPUTING..." : "NOT COMPUTED")} unit="kg/kW·h" sub={`${res?.PSFC_lbm_shph != null ? fmt(res.PSFC_lbm_shph, 3) : "---"} lbm/shp·h`} />
              <HudKpi label="GEARBOX TORQUE" value={res?.torque_Nm != null ? res.torque_Nm : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="torque" sub="Planetary Reduction" />
            </div>

            {/* Restored Propeller Dynamics Sub-Ribbon */}
            {mode === "single" && res && (
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[PROP-AERO] PROPELLER KINEMATICS & COMPRESSIBILITY TELEMETRY</span>
                  <span className="tech-tag optimal">M_tip &lt; 0.95</span>
                </div>
                <div className="panel-card-body">
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px" }}>
                    <div>
                      <div className="slider-label">ADVANCE RATIO (J)</div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(res.advance_ratio_J, 3)}</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>V_inf / (n · D)</div>
                    </div>
                    <div>
                      <div className="slider-label">HELICAL TIP MACH (M_tip)</div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: res.tip_mach_helical >= 0.85 ? "var(--accent-amber)" : "#F2F4F8" }}>
                        {fmt(res.tip_mach_helical, 3)}
                      </div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Tip Speed: {fmt(res.tip_speed_ms, 0)} m/s</div>
                    </div>
                    <div>
                      <div className="slider-label">COMPRESSIBILITY FACTOR</div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: "#F2F4F8" }}>
                        {fmt(res.compressibility_loss, 4)}
                      </div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Δη Loss Offset</div>
                    </div>
                    <div>
                      <div className="slider-label">PROPELLER THRUST</div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: "#F2F4F8" }}>
                        {fmt(res.F_prop_kN, 2)} <span style={{ fontSize: "10px", color: "#8E95A5" }}>kN</span>
                      </div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Jet: {fmt(res.F_jet_kN, 2)} kN</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Mode-Dependent View: Station Table vs 2x2 Grid of 4 Sweep Charts */}
            {mode === "single" ? (
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[GAS-PATH] TURBOPROP THERMODYNAMIC STATIONS (FREE POWER TURBINE)</span>
                  <span className="tech-tag info">7-ROW CANTERA SPECS</span>
                </div>
                <div className="panel-card-body">
                  <StationTable stations={res?.stations} />
                </div>
              </div>
            ) : (
              <TurbopropSweepCharts sweepData={sweepRes} />
            )}
          </main>
        </div>
      );
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 07: 7-PHASE FLIGHT MISSION & BREGUET INTEGRATION
    // ═════════════════════════════════════════════════════════════════════════
    function MissionProfileChart({ phases }) {
      const ref = useRef(null);
      const pts = phases || [];
      const labels = pts.map(p => p.name || p.phase || "Phase");

      const chartData = pts.length > 0 ? {
        labels,
        datasets: [{
          label: "ALTITUDE PROFILE [FT]",
          data: pts.map(p => p.altitude_ft ?? p.alt_ft ?? 0),
          borderColor: "#38BDF8",
          backgroundColor: "rgba(56, 189, 248, 0.08)",
          fill: true,
          tension: 0.15,
          pointRadius: 4,
          pointBackgroundColor: "#38BDF8"
        }]
      } : null;

      useNeonChart(ref, "line", chartData, {
        scales: {
          y: { title: { display: true, text: "ALTITUDE [FT]", color: "#8E95A5" } }
        }
      });

      return <div className="chart-box" style={{ height: "200px" }}><canvas ref={ref} /></div>;
    }

    function PayloadRangeChart({ envelope, currentPoint }) {
      const ref = useRef(null);
      const pts = envelope || [];

      const chartData = pts.length > 0 ? {
        datasets: [
          {
            label: "PAYLOAD-RANGE ENVELOPE",
            data: pts.map(p => ({ x: p.range_nm || p.range_km, y: p.payload_kg })),
            borderColor: "#F59E0B",
            backgroundColor: "rgba(245, 158, 11, 0.08)",
            fill: true,
            tension: 0.1,
            pointRadius: 3,
            showLine: true
          },
          ...(currentPoint ? [{
            label: "CURRENT MISSION",
            data: [{ x: currentPoint.range_nm || currentPoint.range_km, y: currentPoint.payload_kg }],
            pointRadius: 8,
            pointStyle: "rectRot",
            pointBackgroundColor: "#F2F4F8",
            borderColor: "#090A0C",
            borderWidth: 2,
            showLine: false
          }] : [])
        ]
      } : null;

      useNeonChart(ref, "line", chartData, {
        scales: {
          x: { type: "linear", title: { display: true, text: "RANGE [NM]", color: "#8E95A5" } },
          y: { type: "linear", title: { display: true, text: "PAYLOAD [KG]", color: "#8E95A5" } }
        }
      });

      return <div className="chart-box" style={{ height: "200px" }}><canvas ref={ref} /></div>;
    }

    function AirspeedTrendsChart({ trendsData }) {
      const ref = useRef(null);
      const pts = trendsData?.airspeeds_kts || [];

      const chartData = pts.length > 0 ? {
        labels: pts.map(v => fmt(v, 0)),
        datasets: [
          {
            label: "TOTAL DRAG [N]",
            data: trendsData.total_drag_N || [],
            borderColor: "#EF4444",
            tension: 0.2,
            pointRadius: 0,
            yAxisID: "y"
          },
          {
            label: "L/D EFFICIENCY",
            data: trendsData.L_over_D || [],
            borderColor: "#10B981",
            tension: 0.2,
            pointRadius: 0,
            yAxisID: "y1"
          }
        ]
      } : null;

      useNeonChart(ref, "line", chartData, {
        scales: {
          x: { title: { display: true, text: "TRUE AIRSPEED [KTS]", color: "#8E95A5" } },
          y: { title: { display: true, text: "DRAG [N]", color: "#EF4444" } },
          y1: {
            position: "right",
            grid: { drawOnChartArea: false },
            title: { display: true, text: "L/D RATIO", color: "#10B981" }
          }
        }
      });

      return <div className="chart-box" style={{ height: "200px" }}><canvas ref={ref} /></div>;
    }

    function MissionPanel() {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [res, setRes] = useState(null);
      const [trends, setTrends] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        aircraft_type: "generic_twin",
        cruise_alt_ft: 35000.0,
        cruise_mach: 0.78,
        cruise_distance_nm: 1200.0,
        payload_kg: 9000.0,
        fuel_load_kg: 18000.0
      });

      const isUav = p.aircraft_type === "tactical_uav";
      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const runMission = useCallback(async (currentP) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const resp = await fetch(`${API}/api/mission/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentP)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Flight mission simulation failed");
          }
          const data = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setRes(data);

          // Fetch continuous polar airspeed trends
          try {
            const sizing = data.airframe_sizing || {};
            const tResp = await fetch(`${API}/api/mission/airspeed_trends`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                gross_mass_kg: data.mission_summary?.takeoff_weight_kg || (currentP.aircraft_type === "tactical_uav" ? 25.0 : 75000.0),
                wing_area_m2: sizing.wing_area_m2 || (currentP.aircraft_type === "tactical_uav" ? 1.6 : 122.6),
                aspect_ratio: sizing.aspect_ratio || (currentP.aircraft_type === "tactical_uav" ? 10.0 : 9.5),
                CD0: currentP.aircraft_type === "tactical_uav" ? 0.024 : 0.0185,
                alt_ft: currentP.cruise_alt_ft,
                n_points: 35
              })
            });
            if (reqId !== reqSeqRef.current) return;
            if (tResp.ok) setTrends(await tResp.json());
          } catch (_) {}
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, []);

      const debouncedSolve = useDebouncedCallback(runMission, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          runMission(p);
          return;
        }
        debouncedSolve(p);
      }, [p, debouncedSolve, runMission]);

      const summary = res?.mission_summary || res?.summary || {};
      const phases = res?.flight_profile || res?.phases || [];
      const envelope = res?.payload_range_envelope || [];
      const curPt = res?.current_mission_point;
      const sizing = res?.airframe_sizing;
      const charSpeeds = res?.characteristic_speeds;

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar with Restored Payload Slider */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[INPUT] MISSION SPECIFICATION</span>
                <span className="tech-tag optimal">BREGUET NUMERICAL</span>
              </div>
              <div className="panel-card-body">
                <div style={{ marginBottom: "6px", fontSize: "10px", color: "var(--text-silver)" }}>AIRCRAFT PLATFORM:</div>
                <select
                  className="blueprint-select"
                  value={p.aircraft_type}
                  onChange={e => {
                    const t = e.target.value;
                    if (t === "tactical_uav") {
                      setP({
                        aircraft_type: t,
                        cruise_alt_ft: 8000.0,
                        cruise_mach: 0.08,
                        cruise_distance_nm: 80.0,
                        payload_kg: 4.0,
                        fuel_load_kg: 8.5
                      });
                    } else if (t === "regional_twin") {
                      setP({
                        aircraft_type: t,
                        cruise_alt_ft: 35000.0,
                        cruise_mach: 0.78,
                        cruise_distance_nm: 1000.0,
                        payload_kg: 8500.0,
                        fuel_load_kg: 12000.0
                      });
                    } else if (t === "long_range_twin") {
                      setP({
                        aircraft_type: t,
                        cruise_alt_ft: 38000.0,
                        cruise_mach: 0.82,
                        cruise_distance_nm: 3500.0,
                        payload_kg: 32000.0,
                        fuel_load_kg: 65000.0
                      });
                    } else {
                      setP({
                        aircraft_type: "generic_twin",
                        cruise_alt_ft: 35000.0,
                        cruise_mach: 0.78,
                        cruise_distance_nm: 1200.0,
                        payload_kg: 9000.0,
                        fuel_load_kg: 18000.0
                      });
                    }
                  }}
                >
                  <option value="tactical_uav">TACTICAL RECON UAV (25kg MTOW)</option>
                  <option value="regional_twin">TWIN-JET REGIONAL (45t MTOW)</option>
                  <option value="generic_twin">NARROWBODY TWIN (75t MTOW)</option>
                  <option value="long_range_twin">WIDEBODY TWIN (228t MTOW)</option>
                </select>

                <HudSlider
                  label="CRUISE ALTITUDE"
                  value={p.cruise_alt_ft}
                  min={isUav ? 1000 : 15000}
                  max={isUav ? 15000 : 43000}
                  step={isUav ? 500 : 1000}
                  unit="FT"
                  onChange={v => setVal("cruise_alt_ft", v)}
                />
                <HudSlider
                  label="CRUISE MACH"
                  value={p.cruise_mach}
                  min={isUav ? 0.05 : 0.50}
                  max={isUav ? 0.25 : 0.88}
                  step={0.01}
                  unit="M"
                  onChange={v => setVal("cruise_mach", v)}
                />
                <HudSlider
                  label="STAGE DISTANCE"
                  value={p.cruise_distance_nm}
                  min={isUav ? 10 : 100}
                  max={isUav ? 250 : (p.aircraft_type === "long_range_twin" ? 7500 : 3000)}
                  step={isUav ? 5 : 50}
                  unit="NM"
                  onChange={v => setVal("cruise_distance_nm", v)}
                />
                {/* Restored Payload Mass Slider */}
                <HudSlider
                  label="PAYLOAD MASS"
                  value={p.payload_kg}
                  min={isUav ? 0.5 : 1000}
                  max={isUav ? 5.0 : (p.aircraft_type === "long_range_twin" ? 45000 : 18000)}
                  step={isUav ? 0.5 : 500}
                  unit="KG"
                  onChange={v => setVal("payload_kg", v)}
                />
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] MISSION ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top 6 KPI Cards (Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="BLOCK FUEL BURN" value={summary.block_fuel_kg != null ? summary.block_fuel_kg : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="mass" decimals={isUav ? 1 : 0} sub="Gate-to-Gate" />
              <HudKpi label="FLIGHT TIME" value={summary.total_flight_time_hr != null ? fmt(summary.total_flight_time_hr, 2) : (loading ? "COMPUTING..." : "NOT COMPUTED")} unit="hrs" sub={`${summary.total_flight_time_min != null ? fmtInt(summary.total_flight_time_min) : "---"} min`} />
              <HudKpi label="CRUISE L/D" value={summary.cruise_L_over_D != null ? fmt(summary.cruise_L_over_D, 2) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Aero Efficiency" />
              <HudKpi label="BREGUET RANGE" value={summary.breguet_cruise_range_km != null ? summary.breguet_cruise_range_km : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="distance_km" decimals={0} sub={`${summary.breguet_cruise_range_nm != null ? fmtInt(summary.breguet_cruise_range_nm) : "---"} NM`} />
              <HudKpi label="AVERAGE TSFC" value={summary.average_cruise_TSFC != null ? summary.average_cruise_TSFC : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="tsfc" decimals={2} sub="Cruise Phase" />
              <HudKpi label="TAKEOFF WEIGHT" value={summary.takeoff_weight_kg != null ? summary.takeoff_weight_kg : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="mass" decimals={isUav ? 1 : 0} sub={`Landing: ${summary.landing_weight_kg != null ? fmt(summary.landing_weight_kg, isUav ? 1 : 0) : "---"} kg`} />
            </div>

            {/* Restored Panel 1: Conceptual Sizing */}
            {sizing && (
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[AIRFRAME-GEOM] CONCEPTUAL SIZING & MASS FRACTIONS</span>
                  <span className="tech-tag optimal">{sizing.material ? sizing.material.toUpperCase() : "COMPOSITE"}</span>
                </div>
                <div className="panel-card-body">
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "8px" }}>
                    <div>
                      <div className="slider-label">WING AREA (S)</div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(sizing.wing_area_m2, 2)} m²</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>W/S: {fmt(sizing.wing_loading_kg_m2, 1)} kg/m²</div>
                    </div>
                    <div>
                      <div className="slider-label">WING SPAN (b)</div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(sizing.span_b_m, 2)} m</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>AR: {fmt(sizing.aspect_ratio, 1)}</div>
                    </div>
                    <div>
                      <div className="slider-label">MEAN CHORD (MAC)</div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(sizing.mac_m, 2)} m</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Root: {fmt(sizing.root_chord_m, 2)}m</div>
                    </div>
                    <div>
                      <div className="slider-label">HORIZ TAIL (S_H)</div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(sizing.horizontal_tail_area_m2, 2)} m²</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Arm: {fmt(sizing.moment_arm_H_m, 2)}m</div>
                    </div>
                    <div>
                      <div className="slider-label">VERT TAIL (S_V)</div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(sizing.vertical_tail_area_m2, 2)} m²</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Arm: {fmt(sizing.moment_arm_V_m, 2)}m</div>
                    </div>
                    <div>
                      <div className="slider-label">STRUCTURAL MASS</div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(sizing.structural_mass_kg, 1)} kg</div>
                      <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Fraction: {fmt(sizing.structural_mass_fraction * 100, 1)}%</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Restored Panel 2: Operational Flight Envelope Speeds */}
            {charSpeeds && (
              <div className="panel-card">
                <div className="panel-card-header">
                  <span>[AERO-SPEEDS] OPERATIONAL FLIGHT ENVELOPE (ISA @ {fmtInt(p.cruise_alt_ft)} FT)</span>
                  <span className="tech-tag optimal">CLOSED-FORM</span>
                </div>
                <div className="panel-card-body">
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px" }}>
                    <div>
                      <span style={{ fontSize: "9.5px", color: "var(--accent-crimson)", fontWeight: 700 }}>STALL SPEED (V_stall): </span>
                      <strong style={{ color: "#ffffff" }}>{fmt(charSpeeds.V_stall_kts, 1)} kts</strong>
                      <span style={{ fontSize: "8.5px", color: "#8E95A5" }}> ({fmt(charSpeeds.V_stall_ms, 1)} m/s)</span>
                    </div>
                    <div>
                      <span style={{ fontSize: "9.5px", color: "var(--accent-amber)", fontWeight: 700 }}>MIN POWER / LOITER: </span>
                      <strong style={{ color: "#ffffff" }}>{fmt(charSpeeds.V_minP_kts, 1)} kts</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "9.5px", color: "var(--accent-emerald)", fontWeight: 700 }}>MIN DRAG / BEST RANGE: </span>
                      <strong style={{ color: "#ffffff" }}>{fmt(charSpeeds.V_minD_kts, 1)} kts</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: "9.5px", color: "var(--accent-cyan)", fontWeight: 700 }}>MAX L/D RATIO: </span>
                      <strong style={{ color: "#ffffff" }}>{fmt(charSpeeds.LD_max, 2)}</strong>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Restored 3 Charts in a 3-Column Row */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
              <div className="panel-card">
                <div className="panel-card-header"><span>[TRAJECTORY] ALTITUDE PROFILE</span><span className="tech-tag optimal">7 PHASES</span></div>
                <div className="panel-card-body"><MissionProfileChart phases={phases} /></div>
              </div>

              <div className="panel-card">
                <div className="panel-card-header"><span>[ENVELOPE] BREGUET ENVELOPE</span><span className="tech-tag optimal">MTOW / MZFW</span></div>
                <div className="panel-card-body"><PayloadRangeChart envelope={envelope} currentPoint={curPt} /></div>
              </div>

              <div className="panel-card">
                <div className="panel-card-header"><span>[DRAG-POLAR] AIRSPEED TRENDS</span><span className="tech-tag optimal">D0 / Di / L/D</span></div>
                <div className="panel-card-body"><AirspeedTrendsChart trendsData={trends} /></div>
              </div>
            </div>

            {/* Restored Flight Log Table with Auto-Scaled Units for UAV */}
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[FLIGHT-LOG] MISSION INTEGRATION TABLE</span>
                <span className="tech-tag optimal">NUMERICAL INTEGRATION</span>
              </div>
              <div className="table-container">
                <table className="blueprint-table">
                  <thead>
                    <tr>
                      <th>FLIGHT PHASE</th>
                      <th className="num">DURATION [MIN]</th>
                      <th className="num">DISTANCE [KM]</th>
                      <th className="num">FUEL BURN [{isUav ? "G" : "KG"}]</th>
                      <th className="num">THRUST [{isUav ? "N" : "KN"}]</th>
                      <th className="num">TSFC [G/KN·S]</th>
                    </tr>
                  </thead>
                  <tbody>
                    {phases.map((ph, idx) => {
                      const dur = ph.duration_min != null ? ph.duration_min : (ph.time_min != null ? ph.time_min : 0);
                      const dist = ph.distance_km != null ? ph.distance_km : ((ph.distance_nm || 0) * 1.852);
                      const fuelKg = ph.fuel_burned_kg != null ? ph.fuel_burned_kg : (ph.fuel_burn_step_kg != null ? ph.fuel_burn_step_kg : (ph.fuel_burn_kg || 0));
                      const thrustKn = ph.thrust_per_eng_kN != null ? ph.thrust_per_eng_kN : (ph.thrust_kN != null ? ph.thrust_kN : ((ph.thrust_N || 0) / 1000));
                      const tsfc = ph.avg_tsfc != null ? ph.avg_tsfc : (ph.tsfc != null ? ph.tsfc : (ph.TSFC_g_kNs || 18.0));

                      const displayFuel = isUav ? (fuelKg * 1000.0) : fuelKg;
                      const displayThrust = isUav ? (thrustKn * 1000.0) : thrustKn;

                      return (
                        <tr key={idx}>
                          <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>{ph.phase || ph.name || `Phase ${idx + 1}`}</td>
                          <td className="num">{fmt(dur, 1)}</td>
                          <td className="num">{fmt(dist, 1)}</td>
                          <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(displayFuel, 1)}</td>
                          <td className="num">{fmt(displayThrust, 2)}</td>
                          <td className="num">{fmt(tsfc, 2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </main>
        </div>
      );
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 08: AI / NEURAL FAST SURROGATE MODEL
    // ═════════════════════════════════════════════════════════════════════════
    function SurrogateCurveChart({ points, xParam, yParam }) {
      const ref = useRef(null);
      const pts = points || [];

      const chartData = useMemo(() => {
        if (!pts.length) return null;

        const meanPts = pts.map(p => ({ x: p.x, y: p.y }));
        const upperPts = pts.map(p => ({ x: p.x, y: p.y_upper != null ? p.y_upper : p.y * 1.05 }));
        const lowerPts = pts.map(p => ({ x: p.x, y: p.y_lower != null ? p.y_lower : p.y * 0.95 }));

        return {
          datasets: [
            // Mean Prediction Curve in Stark Titanium White
            {
              label: "SURROGATE MEAN PREDICTION",
              data: meanPts,
              borderColor: "#F2F4F8",
              borderWidth: 2,
              tension: 0.25,
              pointRadius: 0,
              showLine: true,
              fill: false
            },
            // Confidence Upper Bound (+1.96σ)
            {
              label: "+1.96σ UPPER BOUND (95% CI)",
              data: upperPts,
              borderColor: "#38BDF8",
              borderDash: [4, 4],
              borderWidth: 1.2,
              tension: 0.25,
              pointRadius: 0,
              showLine: true,
              fill: false
            },
            // Confidence Lower Bound (-1.96σ) with semi-transparent cyan ribbon
            {
              label: "-1.96σ LOWER BOUND (95% CI)",
              data: lowerPts,
              borderColor: "#38BDF8",
              borderDash: [4, 4],
              borderWidth: 1.2,
              tension: 0.25,
              pointRadius: 0,
              showLine: true,
              fill: "-1",
              backgroundColor: "rgba(56, 189, 248, 0.18)"
            }
          ]
        };
      }, [pts]);

      useNeonChart(ref, "line", chartData, {
        scales: {
          x: { type: "linear", title: { display: true, text: `PARAM: ${xParam.toUpperCase()}`, color: "#8E95A5" } },
          y: { type: "linear", title: { display: true, text: `RESPONSE: ${yParam.toUpperCase()}`, color: "#8E95A5" } }
        }
      });

      return <div className="chart-box" style={{ height: "300px" }}><canvas ref={ref} /></div>;
    }

    function SurrogatePanel() {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [pred, setPred] = useState(null);
      const [surface, setSurface] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        alt_ft: 35000.0,
        mach: 0.80,
        throttle: 1.00,
        CPR: 14.0,
        TIT_K: 1450.0
      });

      const [surfParams, setSurfParams] = useState({
        x_param: "mach",
        y_param: "thrust_kN"
      });

      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));

      const runPredict = useCallback(async (currentP, currentSurf) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          const resp = await fetch(`${API}/api/surrogate/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentP)
          });
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || "Surrogate prediction failed");
          }
          const predData = await resp.json();
          if (reqId !== reqSeqRef.current) return;
          setPred(predData);

          // Fetch 2D slice response surface
          const sResp = await fetch(`${API}/api/surrogate/surface`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              x_param: currentSurf.x_param,
              y_param: currentSurf.y_param,
              fixed_alt: currentP.alt_ft,
              fixed_mach: currentP.mach,
              fixed_throttle: currentP.throttle,
              fixed_cpr: currentP.CPR,
              fixed_tit: currentP.TIT_K
            })
          });
          if (reqId !== reqSeqRef.current) return;
          if (sResp.ok) setSurface(await sResp.json());
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, []);

      const debouncedPredict = useDebouncedCallback(runPredict, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          runPredict(p, surfParams);
          return;
        }
        debouncedPredict(p, surfParams);
      }, [p, surfParams, debouncedPredict, runPredict]);

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[INPUT] SURROGATE EVALUATION</span>
                <span className="tech-tag optimal">&lt; 0.25 MS LATENCY</span>
              </div>
              <div className="panel-card-body">
                <HudSlider label="ALTITUDE" value={p.alt_ft} min={0} max={45000} step={1000} unit="FT" onChange={v => setVal("alt_ft", v)} />
                <HudSlider label="FLIGHT MACH" value={p.mach} min={0.10} max={0.95} step={0.05} unit="M" onChange={v => setVal("mach", v)} />
                <HudSlider label="THROTTLE" value={p.throttle} min={0.20} max={1.00} step={0.05} onChange={v => setVal("throttle", v)} />
                <HudSlider label="PRESSURE RATIO (CPR)" value={p.CPR} min={5.0} max={30.0} step={1.0} onChange={v => setVal("CPR", v)} />
                <HudSlider label="TURBINE INLET TEMP" value={p.TIT_K} min={1100} max={1850} step={25} unit="K" onChange={v => setVal("TIT_K", v)} />
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] SURROGATE ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {/* Top 5 KPI Cards (Stark Titanium White) */}
            <div className="kpi-grid">
              <HudKpi label="PREDICTED THRUST" value={pred?.thrust_kN != null ? pred.thrust_kN : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="thrust" sub="Augmented Gaussian RBF" />
              <HudKpi label="PREDICTED TSFC" value={pred?.tsfc != null ? pred.tsfc : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="tsfc" decimals={2} sub={pred && pred.uncertainty_pct != null ? `± ${fmt(pred.uncertainty_pct, 1)}% (95% CI)` : "Specific Fuel Cons."} />
              <HudKpi label="AIR MASS FLOW" value={pred?.air_flow_kg_s != null ? pred.air_flow_kg_s : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="massflow" decimals={1} sub="Engine Inlet Flow" />
              <HudKpi label="FUEL MASS FLOW" value={pred?.fuel_flow_kg_s != null ? pred.fuel_flow_kg_s : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="fuelflow" decimals={4} sub="Combustor Fuel" />
              <HudKpi label="SOLVE LATENCY" value={pred && pred.latency_ms != null ? fmt(pred.latency_ms, 3) : (loading ? "COMPUTING..." : "< 0.25")} unit="ms" sub={pred && pred.loocv_r2 ? `LOOCV R²: ${fmt(pred.loocv_r2, 4)}` : "High Fidelity RBF"} />
            </div>

            {/* 2D Slice Response Surface Chart with Working Selectors */}
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[SURFACE] 2D RESPONSE SLICE SENSITIVITY CURVE & 95% CONFIDENCE RIBBON</span>
                <div style={{ display: "flex", gap: "8px" }}>
                  <select
                    className="blueprint-select"
                    style={{ width: "130px", marginBottom: 0, padding: "2px 6px", fontSize: "9.5px" }}
                    value={surfParams.x_param}
                    onChange={e => setSurfParams(prev => ({ ...prev, x_param: e.target.value }))}
                  >
                    <option value="mach">X: FLIGHT MACH</option>
                    <option value="alt_ft">X: ALTITUDE</option>
                    <option value="throttle">X: THROTTLE</option>
                    <option value="cpr">X: CPR</option>
                    <option value="tit">X: TIT</option>
                  </select>
                  <select
                    className="blueprint-select"
                    style={{ width: "130px", marginBottom: 0, padding: "2px 6px", fontSize: "9.5px" }}
                    value={surfParams.y_param}
                    onChange={e => setSurfParams(prev => ({ ...prev, y_param: e.target.value }))}
                  >
                    <option value="thrust_kN">Y: THRUST [kN]</option>
                    <option value="tsfc">Y: TSFC [g/kN·s]</option>
                    <option value="fuel_flow_kg_s">Y: FUEL FLOW [kg/s]</option>
                  </select>
                </div>
              </div>
              <div className="panel-card-body">
                <SurrogateCurveChart
                  points={surface?.points}
                  xParam={surfParams.x_param}
                  yParam={surfParams.y_param}
                />
              </div>
            </div>
          </main>
        </div>
      );
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DOMAIN 09: HYBRID-ELECTRIC POWERTRAIN ARCHITECTURE
    // ═════════════════════════════════════════════════════════════════════════
    function HybridSchematicSvg({ arch = "parallel", p_gt = 1800, p_motor = 600, p_batt = 650, p_req = 2400 }) {
      const a = (arch || "parallel").toLowerCase();

      return (
        <div style={{ background: "#0B0D11", border: "1px solid var(--border-hairline)", padding: "10px", marginTop: "10px" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--accent-amber)", marginBottom: "4px" }}>
            POWERTRAIN TOPOLOGY & POWER FLOW BUS // {a.toUpperCase()}
          </div>
          <svg viewBox="0 0 620 120" style={{ width: "100%", maxHeight: "120px" }}>
            <defs>
              <marker id="hw-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#38BDF8" />
              </marker>
            </defs>

            {a === "series" ? (
              // Series Hybrid: GT -> Gen -> Electric Bus -> Motor -> Propulsor
              <g>
                <rect x="20" y="20" width="100" height="38" fill="#101216" stroke="#38BDF8" strokeWidth="1.5" />
                <text x="70" y="36" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">GAS TURBINE</text>
                <text x="70" y="48" fill="#38BDF8" fontSize="8" textAnchor="middle">{fmt(p_gt, 0)} kW</text>

                <line x1="120" y1="39" x2="160" y2="39" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="160" y="20" width="90" height="38" fill="#101216" stroke="#F59E0B" strokeWidth="1.5" />
                <text x="205" y="36" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">GENERATOR</text>
                <text x="205" y="48" fill="#F59E0B" fontSize="8" textAnchor="middle">Gen Bus</text>

                <line x1="250" y1="39" x2="300" y2="39" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="300" y="20" width="110" height="38" fill="#101216" stroke="#10B981" strokeWidth="1.5" />
                <text x="355" y="36" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">ELECTRIC MOTOR</text>
                <text x="355" y="48" fill="#10B981" fontSize="8" textAnchor="middle">{fmt(p_motor, 0)} kW</text>

                <line x1="410" y1="39" x2="480" y2="39" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="480" y="20" width="120" height="38" fill="#101216" stroke="#F2F4F8" strokeWidth="1.5" />
                <text x="540" y="36" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">PROPULSOR / FAN</text>
                <text x="540" y="48" fill="#F2F4F8" fontSize="8" textAnchor="middle">{fmt(p_req, 0)} kW</text>

                {/* Battery connected to bus */}
                <rect x="160" y="70" width="110" height="36" fill="#101216" stroke="#F59E0B" strokeWidth="1.5" />
                <text x="215" y="86" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">BATTERY PACK</text>
                <text x="215" y="98" fill="#F59E0B" fontSize="8" textAnchor="middle">{fmt(p_batt, 0)} kW</text>

                <line x1="270" y1="88" x2="340" y2="58" stroke="#F59E0B" strokeWidth="2" markerEnd="url(#hw-arrow)" />
              </g>
            ) : a === "turboelectric" ? (
              // Turboelectric: GT -> Main Gen -> Distributed Bus -> Multiple Propulsors
              <g>
                <rect x="20" y="35" width="110" height="42" fill="#101216" stroke="#38BDF8" strokeWidth="1.5" />
                <text x="75" y="52" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">TURBOGENERATOR</text>
                <text x="75" y="66" fill="#38BDF8" fontSize="8" textAnchor="middle">{fmt(p_gt, 0)} kW</text>

                <line x1="130" y1="56" x2="210" y2="56" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="210" y="30" width="130" height="52" fill="#101216" stroke="#F59E0B" strokeWidth="1.5" />
                <text x="275" y="50" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">POWER ELECTRONICS</text>
                <text x="275" y="62" fill="#F59E0B" fontSize="8" textAnchor="middle">SUPERCONDUCTING BUS</text>

                <line x1="340" y1="44" x2="420" y2="28" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />
                <line x1="340" y1="68" x2="420" y2="84" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="420" y="10" width="180" height="36" fill="#101216" stroke="#10B981" strokeWidth="1.5" />
                <text x="510" y="26" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">DEP / BLI FAN ARRAY [WING]</text>
                <text x="510" y="38" fill="#10B981" fontSize="8" textAnchor="middle">{fmt(p_req * 0.5, 0)} kW</text>

                <rect x="420" y="68" width="180" height="36" fill="#101216" stroke="#10B981" strokeWidth="1.5" />
                <text x="510" y="84" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">AFT FUSELAGE BLI PROPULSOR</text>
                <text x="510" y="96" fill="#10B981" fontSize="8" textAnchor="middle">{fmt(p_req * 0.5, 0)} kW</text>
              </g>
            ) : (
              // Parallel Hybrid: GT + EM both mechanical coupled to propulsor
              <g>
                <rect x="30" y="15" width="120" height="38" fill="#101216" stroke="#38BDF8" strokeWidth="1.5" />
                <text x="90" y="31" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">GAS TURBINE CORE</text>
                <text x="90" y="44" fill="#38BDF8" fontSize="8" textAnchor="middle">{fmt(p_gt, 0)} kW</text>

                <rect x="30" y="65" width="120" height="38" fill="#101216" stroke="#F59E0B" strokeWidth="1.5" />
                <text x="90" y="81" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">BATTERY PACK</text>
                <text x="90" y="94" fill="#F59E0B" fontSize="8" textAnchor="middle">{fmt(p_batt, 0)} kW</text>

                <line x1="150" y1="84" x2="230" y2="84" stroke="#F59E0B" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="230" y="65" width="120" height="38" fill="#101216" stroke="#10B981" strokeWidth="1.5" />
                <text x="290" y="81" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">ELECTRIC MOTOR</text>
                <text x="290" y="94" fill="#10B981" fontSize="8" textAnchor="middle">{fmt(p_motor, 0)} kW</text>

                {/* Mechanical Combiner Gearbox */}
                <line x1="150" y1="34" x2="390" y2="48" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#hw-arrow)" />
                <line x1="350" y1="84" x2="390" y2="62" stroke="#10B981" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="390" y="38" width="70" height="38" fill="#101216" stroke="#F59E0B" strokeWidth="1.5" />
                <text x="425" y="54" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">GEARBOX</text>
                <text x="425" y="66" fill="#F59E0B" fontSize="8" textAnchor="middle">Combiner</text>

                <line x1="460" y1="57" x2="490" y2="57" stroke="#F2F4F8" strokeWidth="2" markerEnd="url(#hw-arrow)" />

                <rect x="490" y="38" width="110" height="38" fill="#101216" stroke="#F2F4F8" strokeWidth="1.5" />
                <text x="545" y="54" fill="#F2F4F8" fontSize="8.5" fontWeight="700" textAnchor="middle">MAIN PROPULSOR</text>
                <text x="545" y="66" fill="#F2F4F8" fontSize="8" textAnchor="middle">{fmt(p_req, 0)} kW</text>
              </g>
            )}
          </svg>
        </div>
      );
    }

    function BatteryGauge({ soc = 0.85, capacity_kWh = 450, p_batt_kW = 250 }) {
      const socPct = soc > 1.0 ? soc : soc * 100;
      const isCritical = socPct <= 20.0;
      const statusColor = isCritical ? "var(--accent-crimson)" : (socPct <= 35.0 ? "var(--accent-amber)" : "var(--accent-emerald)");

      return (
        <div style={{ marginTop: "10px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px", fontSize: "10px" }}>
            <span style={{ color: "var(--text-silver)" }}>BATTERY STATE OF CHARGE (SOC):</span>
            <span style={{ fontWeight: 700, color: statusColor }}>{fmt(socPct, 1)}%</span>
          </div>
          <div style={{ width: "100%", height: "8px", background: "#0B0D11", border: "1px solid var(--border-hairline)" }}>
            <div
              style={{
                width: `${Math.min(100, Math.max(0, socPct))}%`,
                height: "100%",
                background: statusColor,
                transition: "width 0.2s ease"
              }}
            />
          </div>
        </div>
      );
    }

    function HybridTradeStudyChart({ tradeData }) {
      const ref = useRef(null);
      const pts = Array.isArray(tradeData) ? tradeData : (tradeData?.points || []);

      const chartData = pts.length > 0 ? {
        datasets: [{
          label: "FUEL FLOW REDUCTION (%) VS HYBRID RATIO",
          data: pts.map(p => ({
            x: p.x != null ? p.x : (p.hp_ratio || p.HP || 0),
            y: p.fuel_saved_percent != null ? p.fuel_saved_percent : (p.fuel_savings_pct || p.savings || 0)
          })),
          borderColor: "#10B981",
          backgroundColor: "rgba(16, 185, 129, 0.12)",
          fill: true,
          tension: 0.25,
          pointRadius: 3,
          showLine: true
        }]
      } : null;

      useNeonChart(ref, "line", chartData, {
        scales: {
          x: { type: "linear", title: { display: true, text: "HYBRID POWER RATIO (H_P)", color: "#8E95A5" } },
          y: { type: "linear", title: { display: true, text: "FUEL REDUCTION [%]", color: "#8E95A5" } }
        }
      });

      return <div className="chart-box" style={{ height: "220px" }}><canvas ref={ref} /></div>;
    }

    function HybridMissionProfileChart({ phases }) {
      const ref = useRef(null);
      const pts = phases || [];
      const labels = pts.map(p => p.name || p.phase || "Phase");

      const chartData = pts.length > 0 ? {
        labels,
        datasets: [
          {
            label: "HYBRID FUEL BURN [KG]",
            data: pts.map(p => p.fuel_burned_kg ?? p.fuel_burn_kg ?? 0),
            backgroundColor: "rgba(56, 189, 248, 0.5)",
            borderColor: "#38BDF8",
            borderWidth: 1
          },
          {
            label: "BATTERY ENERGY USED [KWH]",
            data: pts.map(p => p.elec_energy_kWh ?? 0),
            backgroundColor: "rgba(245, 158, 11, 0.4)",
            borderColor: "#F59E0B",
            borderWidth: 1,
            yAxisID: "y1"
          }
        ]
      } : null;

      useNeonChart(ref, "bar", chartData, {
        scales: {
          y: { title: { display: true, text: "FUEL BURN [KG]", color: "#8E95A5" } },
          y1: {
            position: "right",
            grid: { drawOnChartArea: false },
            title: { display: true, text: "BATTERY ENERGY [KWH]", color: "#F59E0B" }
          }
        }
      });

      return <div className="chart-box" style={{ height: "220px" }}><canvas ref={ref} /></div>;
    }

    function HybridPanel() {
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState(null);
      const [mode, setMode] = useState("single"); // 'single' or 'mission'
      const [res, setRes] = useState(null);
      const [missionRes, setMissionRes] = useState(null);
      const [tradeRes, setTradeRes] = useState(null);
      const reqSeqRef = useRef(0);

      const [p, setP] = useState({
        architecture: "parallel",
        shaft_power_req_kW: 2000.0,
        hybrid_power_ratio_HP: 0.25,
        battery_mass_kg: 1200.0,
        battery_soc: 0.85
      });

      const [mParam, setMParam] = useState({
        architecture: "parallel",
        cruise_dist_km: 800.0,
        payload_kg: 6000.0,
        battery_mass_kg: 1500.0,
        specific_energy_Wh_kg: 320.0,
        takeoff_hybrid_ratio: 0.35,
        climb_hybrid_ratio: 0.20,
        cruise_hybrid_ratio: 0.05
      });

      const setVal = (k, v) => setP(prev => ({ ...prev, [k]: v }));
      const setMVal = (k, v) => setMParam(prev => ({ ...prev, [k]: v }));

      const runHybrid = useCallback(async (currentP, currentM, currentMode) => {
        const reqId = ++reqSeqRef.current;
        setLoading(true);
        setError(null);
        try {
          if (currentMode === "single") {
            const resp = await fetch(`${API}/api/hybrid/single`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(currentP)
            });
            if (!resp.ok) {
              const err = await resp.json().catch(() => ({ detail: resp.statusText }));
              throw new Error(err.detail || "Hybrid calculation failed");
            }
            const data = await resp.json();
            if (reqId !== reqSeqRef.current) return;
            setRes(data);

            // Fetch trade study sweep
            const tResp = await fetch(`${API}/api/hybrid/sweep`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                study_type: "hybrid_ratio",
                architecture: currentP.architecture,
                n_points: 10,
                cruise_dist_km: 900.0,
                battery_mass_kg: currentP.battery_mass_kg
              })
            });
            if (reqId !== reqSeqRef.current) return;
            if (tResp.ok) {
              const tData = await tResp.json();
              setTradeRes(tData.points || []);
            }
          } else {
            const resp = await fetch(`${API}/api/hybrid/mission`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                ...currentM,
                architecture: currentP.architecture
              })
            });
            if (!resp.ok) {
              const err = await resp.json().catch(() => ({ detail: resp.statusText }));
              throw new Error(err.detail || "Hybrid mission simulation failed");
            }
            const data = await resp.json();
            if (reqId !== reqSeqRef.current) return;
            setMissionRes(data);
          }
        } catch (e) {
          if (reqId !== reqSeqRef.current) return;
          setError(e.message || String(e));
        } finally {
          if (reqId === reqSeqRef.current) {
            setLoading(false);
          }
        }
      }, []);

      const debouncedSolve = useDebouncedCallback(runHybrid, 80);

      const isFirstMount = useRef(true);
      useEffect(() => {
        if (isFirstMount.current) {
          isFirstMount.current = false;
          runHybrid(p, mParam, mode);
          return;
        }
        debouncedSolve(p, mParam, mode);
      }, [p, mParam, mode, debouncedSolve, runHybrid]);

      const gtPower = res ? (res.gas_turbine_power_kW ?? res.P_gt_kW ?? (p.shaft_power_req_kW * (1 - p.hybrid_power_ratio_HP))) : null;
      const emPower = res ? (res.electric_motor_power_kW ?? res.P_em_kW ?? (p.shaft_power_req_kW * p.hybrid_power_ratio_HP)) : null;
      const fuelSavings = res ? (res.fuel_savings_pct ?? (res.delta_fuel_pct ? -res.delta_fuel_pct : null)) : null;
      const battPower = res ? (res.battery_power_kW ?? res.P_batt_kW ?? null) : null;
      const masses = res?.powertrain_masses || {};
      const mSummary = missionRes?.summary || {};
      const totalPowertrainMass = masses.total_powertrain_kg ?? (p.battery_mass_kg + (masses.gas_turbine_kg || 420) + (masses.electric_motor_kg || 180) + (masses.generator_kg || 150) + (masses.inverter_tms_kg || 95));

      return (
        <div className="app-workspace">
          {/* Left Controls Sidebar with Restored Mode Switcher */}
          <aside className="app-sidebar">
            <div className="panel-card">
              <div className="panel-card-header">
                <span>[INPUT] HYBRID POWERTRAIN</span>
                <span className="tech-tag optimal">{p.architecture.toUpperCase()}</span>
              </div>
              <div className="panel-card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", marginBottom: "10px" }}>
                  <button className={`blueprint-btn ${mode === "single" ? "active" : ""}`} onClick={() => setMode("single")}>
                    STEADY STATE
                  </button>
                  <button className={`blueprint-btn ${mode === "mission" ? "active" : ""}`} onClick={() => setMode("mission")}>
                    FLIGHT MISSION
                  </button>
                </div>

                <div style={{ marginBottom: "6px", fontSize: "10px", color: "var(--text-silver)" }}>ARCHITECTURE:</div>
                <select
                  className="blueprint-select"
                  value={p.architecture}
                  onChange={e => {
                    setVal("architecture", e.target.value);
                    setMVal("architecture", e.target.value);
                  }}
                >
                  <option value="parallel">PARALLEL HYBRID (GT CORE DOWNSIZING)</option>
                  <option value="series">SERIES HYBRID (TURBOGENERATOR BUS)</option>
                  <option value="turboelectric">TURBOELECTRIC (DEP & BLI AERO GAIN)</option>
                </select>

                {mode === "single" ? (
                  <div>
                    <HudSlider label="SHAFT POWER REQUIRED" value={p.shaft_power_req_kW} min={500} max={6000} step={100} unit="KW" onChange={v => setVal("shaft_power_req_kW", v)} />
                    <HudSlider label="HYBRID POWER RATIO (HP)" value={p.hybrid_power_ratio_HP} min={0.0} max={0.60} step={0.05} onChange={v => setVal("hybrid_power_ratio_HP", v)} />
                    <HudSlider label="BATTERY PACK MASS" value={p.battery_mass_kg} min={200} max={5000} step={100} unit="KG" onChange={v => setVal("battery_mass_kg", v)} />
                    <HudSlider label="STATE OF CHARGE (SOC)" value={p.battery_soc} min={0.10} max={1.00} step={0.05} onChange={v => setVal("battery_soc", v)} />
                  </div>
                ) : (
                  <div>
                    <HudSlider label="STAGE DISTANCE" value={mParam.cruise_dist_km} min={300} max={2500} step={50} unit="KM" onChange={v => setMVal("cruise_dist_km", v)} />
                    <HudSlider label="TAKEOFF HYBRID RATIO" value={mParam.takeoff_hybrid_ratio} min={0.10} max={0.50} step={0.05} onChange={v => setMVal("takeoff_hybrid_ratio", v)} />
                    <HudSlider label="CLIMB HYBRID RATIO" value={mParam.climb_hybrid_ratio} min={0.05} max={0.35} step={0.05} onChange={v => setMVal("climb_hybrid_ratio", v)} />
                    <HudSlider label="BATTERY SPECIFIC ENERGY" value={mParam.specific_energy_Wh_kg} min={200} max={550} step={25} unit="WH/KG" onChange={v => setMVal("specific_energy_Wh_kg", v)} />
                    <HudSlider label="BATTERY PACK MASS" value={mParam.battery_mass_kg} min={500} max={3500} step={100} unit="KG" onChange={v => setMVal("battery_mass_kg", v)} />
                  </div>
                )}
              </div>
            </div>
          </aside>

          {/* Right Mainstage */}
          <main className="app-mainstage">
            {error && (
              <div className="panel-card" style={{ borderColor: "var(--accent-crimson)" }}>
                <div className="panel-card-header" style={{ color: "var(--accent-crimson)" }}>[FAULT] HYBRID SOLVER ERROR</div>
                <div className="panel-card-body" style={{ color: "var(--accent-crimson)" }}>{formatErrorText(error)}</div>
              </div>
            )}

            {mode === "single" ? (
              <div>
                {/* Top 6 KPI Cards (Stark Titanium White) */}
                <div className="kpi-grid">
                  <HudKpi label="GT SHAFT POWER" value={gtPower != null ? gtPower : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="power" decimals={0} sub="Gas Turbine Core" />
                  <HudKpi label="ELECTRIC MOTOR" value={emPower != null ? emPower : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="power" decimals={0} sub="EM Traction" />
                  <HudKpi label="FUEL SAVINGS" value={fuelSavings != null ? fmtPct(fuelSavings) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Vs Conventional" />
                  <HudKpi label="BATTERY DISCHARGE" value={battPower != null ? battPower : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="power" decimals={0} sub={`C-Rate: ${res ? fmt(res.c_rate || 1.8, 1) : "---"}C`} />
                  <HudKpi label="TMS WASTE HEAT" value={res?.waste_heat_kW != null ? res.waste_heat_kW : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="power" decimals={1} sub="Heat Rejection" />
                  <HudKpi label="TOTAL EFFICIENCY" value={res?.system_efficiency != null ? fmtPct(res.system_efficiency) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Coupled Powertrain" />
                </div>

                {/* Restored 3 Distinct SVG Powertrain Schematics & Battery Gauge */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  <div className="panel-card">
                    <div className="panel-card-header">
                      <span>[PWR-SCHEM] ENERGY BUS SCHEMATIC</span>
                      <span className="tech-tag optimal">{p.architecture.toUpperCase()}</span>
                    </div>
                    <div className="panel-card-body">
                      <HybridSchematicSvg
                        arch={p.architecture}
                        p_gt={gtPower || 0}
                        p_motor={emPower || 0}
                        p_batt={battPower || 0}
                        p_req={p.shaft_power_req_kW}
                      />
                      <BatteryGauge soc={p.battery_soc} />
                    </div>
                  </div>

                  <div className="panel-card">
                    <div className="panel-card-header">
                      <span>[TRADE] FUEL FLOW REDUCTION (%) VS HYBRID RATIO (H_P)</span>
                      <span className="tech-tag optimal">PARAMETRIC STUDY</span>
                    </div>
                    <div className="panel-card-body">
                      <HybridTradeStudyChart tradeData={tradeRes} />
                    </div>
                  </div>
                </div>

                {/* Restored 6 Electrical Component Mass Breakdown Cards */}
                <div className="panel-card" style={{ marginTop: "10px" }}>
                  <div className="panel-card-header">
                    <span>[MASS-BREAKDOWN] POWERTRAIN COMPONENT DRY MASS FRACTIONS</span>
                    <span className="tech-tag optimal">POWER DENSITY ESTIMATES</span>
                  </div>
                  <div className="panel-card-body">
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "8px" }}>
                      <div>
                        <div className="slider-label">GAS TURBINE</div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(masses.gas_turbine_kg || 420, 0)} kg</div>
                        <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Core Mass</div>
                      </div>
                      <div>
                        <div className="slider-label">ELECTRIC MOTOR</div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(masses.electric_motor_kg || 180, 0)} kg</div>
                        <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>10 kW/kg</div>
                      </div>
                      <div>
                        <div className="slider-label">GENERATOR</div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(masses.generator_kg || 150, 0)} kg</div>
                        <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>P_gen Split</div>
                      </div>
                      <div>
                        <div className="slider-label">BATTERY PACK</div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(masses.battery_kg || p.battery_mass_kg, 0)} kg</div>
                        <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Cells + Packaging</div>
                      </div>
                      <div>
                        <div className="slider-label">INVERTER / TMS</div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(masses.inverter_tms_kg || 95, 0)} kg</div>
                        <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Power Electronics</div>
                      </div>
                      <div>
                        <div className="slider-label">TOTAL DRY MASS</div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#F2F4F8" }}>{fmt(totalPowertrainMass, 0)} kg</div>
                        <div style={{ fontSize: "8.5px", color: "#8E95A5" }}>Powertrain System</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                {/* Mission Mode KPI Ribbon */}
                <div className="kpi-grid">
                  <HudKpi label="MISSION FUEL BURN" value={mSummary.hybrid_fuel_burn_kg != null ? mSummary.hybrid_fuel_burn_kg : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="mass" decimals={1} sub="Total Jet Fuel" />
                  <HudKpi label="CONVENTIONAL FUEL" value={mSummary.conventional_fuel_burn_kg != null ? mSummary.conventional_fuel_burn_kg : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="mass" decimals={1} sub="Baseline GT" />
                  <HudKpi 
                    label="NET FUEL SAVED" 
                    value={mSummary.fuel_saved_percent != null ? fmtPct(mSummary.fuel_saved_percent) : (loading ? "COMPUTING..." : "NOT COMPUTED")} 
                    subTag={{
                      type: (mSummary.fuel_saved_percent || 0) >= 0 ? "optimal" : "critical",
                      label: (mSummary.fuel_saved_percent || 0) >= 0 ? "SAVINGS POSITIVE" : "WEIGHT PENALTY"
                    }}
                  />
                  <HudKpi label="BATTERY ENERGY USED" value={mSummary.battery_energy_used_kWh != null ? fmt(mSummary.battery_energy_used_kWh, 1) : (loading ? "COMPUTING..." : "NOT COMPUTED")} unit="kWh" sub="Total Pack Discharge" />
                  <HudKpi label="END-OF-MISSION SOC" value={mSummary.end_soc != null ? fmtPct(mSummary.end_soc) : (loading ? "COMPUTING..." : "NOT COMPUTED")} sub="Reserve Status" />
                  <HudKpi label="EQUIV CO2 SAVINGS" value={mSummary.co2_saved_kg != null ? mSummary.co2_saved_kg : (loading ? "COMPUTING..." : "NOT COMPUTED")} unitType="mass" decimals={1} sub="Emissions Abatement" />
                </div>

                {/* Restored 6-Phase Fuel & Energy Bar Chart */}
                <div className="panel-card">
                  <div className="panel-card-header">
                    <span>[MISSION-ENERGY] 6-PHASE FUEL BURN & BATTERY ENERGY CONSUMPTION</span>
                    <span className="tech-tag optimal">PHASE ENERGY ALLOCATION</span>
                  </div>
                  <div className="panel-card-body">
                    <HybridMissionProfileChart phases={missionRes?.phases} />
                  </div>
                </div>

                {/* Restored 6-Phase Flight Orbit Table with Depleting End SOC */}
                <div className="panel-card">
                  <div className="panel-card-header">
                    <span>[FLIGHT-ORBIT] 6-PHASE HYBRID POWER & BATTERY DEPLETION TABLE</span>
                    <span className="tech-tag optimal">NUMERICAL INTEGRATION</span>
                  </div>
                  <div className="table-container">
                    <table className="blueprint-table">
                      <thead>
                        <tr>
                          <th>FLIGHT PHASE</th>
                          <th className="num">DURATION [MIN]</th>
                          <th className="num">GT POWER [KW]</th>
                          <th className="num">BATTERY DISCHARGE [KW]</th>
                          <th className="num">FUEL BURN [KG]</th>
                          <th className="num">BATTERY ENERGY [KWH]</th>
                          <th className="num">END SOC [%]</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(missionRes?.phases || []).map((ph, idx) => {
                          const endSoc = ph.end_soc != null ? (ph.end_soc * 100) : 80;
                          return (
                            <tr key={idx}>
                              <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>{ph.name || ph.phase || `Phase ${idx + 1}`}</td>
                              <td className="num">{fmt(ph.duration_min, 1)}</td>
                              <td className="num">{fmt(ph.gt_power_kW ?? ph.gas_turbine_power_kW ?? ph.P_gt_kW, 0)}</td>
                              <td className="num">{fmt(ph.battery_power_kW ?? ph.battery_discharge_kW ?? ph.P_batt_kW, 0)}</td>
                              <td className="num" style={{ color: "#F2F4F8", fontWeight: 700 }}>{fmt(ph.fuel_burned_kg || ph.fuel_burn_kg, 1)}</td>
                              <td className="num">{fmt(ph.elec_energy_kWh, 1)}</td>
                              <td className="num" style={{ color: endSoc >= 30 ? "var(--accent-emerald)" : (endSoc >= 20 ? "var(--accent-amber)" : "var(--accent-crimson)") }}>
                                {fmt(endSoc, 1)}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      );
    }
"""
