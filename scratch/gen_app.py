APP_MAIN = """
    // ═════════════════════════════════════════════════════════════════════════
    // ROOT APP COMPONENT (44px HEADER | calc(100vh - 70px) WORKSPACE | 26px FOOTER)
    // ═════════════════════════════════════════════════════════════════════════
    const MODULES = [
      { id: "turbojet", num: "01", label: "[01 TURBOJET]" },
      { id: "physics_turbofan", num: "02", label: "[02 TURBOFAN]" },
      { id: "cf34", num: "03", label: "[03 CF34 DECK]" },
      { id: "off_design", num: "04", label: "[04 OFF-DESIGN]" },
      { id: "meanline", num: "05", label: "[05 MEAN-LINE]" },
      { id: "turboprop", num: "06", label: "[06 TURBOPROP]" },
      { id: "mission", num: "07", label: "[07 MISSION]" },
      { id: "surrogate", num: "08", label: "[08 SURROGATE]" },
      { id: "hybrid", num: "09", label: "[09 HYBRID]" }
    ];

    // Isolated Status Badge component: health polling does not re-render App
    function HeaderSolverStatus() {
      const [solverOnline, setSolverOnline] = useState(true);
      const [solverLatency, setSolverLatency] = useState(12);

      useEffect(() => {
        let isMounted = true;
        const checkHealth = async () => {
          const t0 = performance.now();
          try {
            const r = await fetch(`${API}/api/health`);
            if (!isMounted) return;
            if (r.ok) {
              setSolverOnline(true);
              setSolverLatency(Math.max(1, Math.round(performance.now() - t0)));
            } else {
              setSolverOnline(false);
            }
          } catch (_) {
            if (isMounted) setSolverOnline(false);
          }
        };
        checkHealth();
        const id = setInterval(checkHealth, 15000);
        return () => {
          isMounted = false;
          clearInterval(id);
        };
      }, []);

      return (
        <div className={`solver-status-badge ${solverOnline ? "" : "error"}`}>
          <span className={`status-dot ${solverOnline ? "" : "error"}`}></span>
          <span>{solverOnline ? `SOLVER ONLINE: ${solverLatency}ms` : "SOLVER OFFLINE"}</span>
        </div>
      );
    }

    // Isolated UTC Clock: 1 Hz tick strictly confined to this leaf node
    function HeaderUtcClock() {
      const [utcTime, setUtcTime] = useState("");

      useEffect(() => {
        const updateClock = () => {
          const now = new Date();
          const h = String(now.getUTCHours()).padStart(2, "0");
          const m = String(now.getUTCMinutes()).padStart(2, "0");
          const s = String(now.getUTCSeconds()).padStart(2, "0");
          setUtcTime(`${h}:${m}:${s} UTC`);
        };
        updateClock();
        const id = setInterval(updateClock, 1000);
        return () => clearInterval(id);
      }, []);

      return (
        <div className="utc-clock">
          {utcTime}
        </div>
      );
    }

    function App() {
      const [activeModule, setActiveModule] = useState("turbojet");
      const [unitSystem, setUnitSystem] = useState("SI");
      const [liveStations, setLiveStations] = useState(null);
      const [selectedStation, setSelectedStation] = useState(null);

      return (
        <UnitContext.Provider value={{ unitSystem, setUnitSystem }}>
          <div id="root">
            {/* 44px Top Header with Brand, 9 Compact Numbered Pills, Units, Status, UTC Clock */}
            <header className="app-header">
              <div className="header-branding">
                <span className="crosshair-mark">✛</span>
                <span>AETHER-X</span>
              </div>

              {/* High-Contrast Compact Numbered Pills [01 TURBOJET] .. [09 HYBRID] + Dropdown Fallback */}
              <nav className="domain-nav-container">
                <div className="domain-pills-strip">
                  {MODULES.map(m => (
                    <button
                      key={m.id}
                      className={`domain-pill ${activeModule === m.id ? "active" : ""}`}
                      onClick={() => {
                        setActiveModule(m.id);
                        setSelectedStation(null);
                      }}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
                <select
                  className="domain-select-dropdown"
                  value={activeModule}
                  onChange={e => {
                    setActiveModule(e.target.value);
                    setSelectedStation(null);
                  }}
                  aria-label="Select Domain"
                >
                  {MODULES.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </nav>

              {/* Right Telemetry Cluster: Units, Isolated Solver Status Badge, Isolated UTC Clock */}
              <div className="header-telemetry-cluster">
                <div className="unit-toggle-pill">
                  <button
                    className={`unit-toggle-btn ${unitSystem === "SI" ? "active" : ""}`}
                    onClick={() => setUnitSystem("SI")}
                  >
                    SI METRIC
                  </button>
                  <button
                    className={`unit-toggle-btn ${unitSystem === "IMPERIAL" ? "active" : ""}`}
                    onClick={() => setUnitSystem("IMPERIAL")}
                  >
                    IMPERIAL
                  </button>
                </div>

                <HeaderSolverStatus />
                <HeaderUtcClock />
              </div>
            </header>

            {/* Main Domain Workspace (calc(100vh - 70px), Zero Top Cutaway SVG) */}
            <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
              {activeModule === "turbojet" && (
                <TurbojetPanel
                  onUpdateStations={setLiveStations}
                  selectedStation={selectedStation}
                  onSelectStation={setSelectedStation}
                />
              )}
              {activeModule === "physics_turbofan" && (
                <PhysicsTurbofanPanel
                  onUpdateStations={setLiveStations}
                  selectedStation={selectedStation}
                  onSelectStation={setSelectedStation}
                />
              )}
              {activeModule === "cf34" && (
                <TurbofanPanel
                  onUpdateStations={setLiveStations}
                  selectedStation={selectedStation}
                  onSelectStation={setSelectedStation}
                />
              )}
              {activeModule === "off_design" && <OffDesignPanel />}
              {activeModule === "meanline" && <MeanLinePanel />}
              {activeModule === "turboprop" && (
                <TurbopropPanel
                  onUpdateStations={setLiveStations}
                  selectedStation={selectedStation}
                  onSelectStation={setSelectedStation}
                />
              )}
              {activeModule === "mission" && <MissionPanel />}
              {activeModule === "surrogate" && <SurrogatePanel />}
              {activeModule === "hybrid" && <HybridPanel />}
            </div>

            {/* 26px Bottom Telemetry Footer */}
            <footer className="app-footer">
              <div>ENGINE KERNEL: CANTERA 3.0 + NUMPY VECTORIZED</div>
              <div>BREGUET RANGE INTEGRATOR: STABLE</div>
              <div>AETHER-X BUILD v0.6 OBSIDIAN</div>
            </footer>
          </div>
        </UnitContext.Provider>
      );
    }

    ReactDOM.createRoot(document.getElementById("root")).render(<App />);
"""
