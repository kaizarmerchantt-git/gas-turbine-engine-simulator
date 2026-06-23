# -*- coding: utf-8 -*-
import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add the third tab in the header
new_tabs = """
        <div className="eng-tabs">
          <button className={`eng-tab ${engine==="turbojet"?"tj":""}`} onClick={()=>setEngine("turbojet")}>
            ✈ Turbojet
          </button>
          <button className={`eng-tab ${engine==="physics_tf"?"tj":""}`} onClick={()=>setEngine("physics_tf")}>
            ✈ Physics Turbofan
          </button>
          <button className={`eng-tab ${engine==="turbofan"?"tf":""}`} onClick={()=>setEngine("turbofan")}>
            ✈ CF34 Turbofan
          </button>
        </div>"""
content = re.sub(r'<div className="eng-tabs">.*?</div>', new_tabs, content, flags=re.DOTALL)

# 2. Add the engine switch in App
app_render = """      {engine==="turbojet" ? <TurbojetPanel/> : engine==="physics_tf" ? <PhysicsTurbofanPanel/> : <TurbofanPanel/>}"""
content = content.replace('{engine==="turbojet" ? <TurbojetPanel/> : <TurbofanPanel/>}', app_render)

# 3. Create PhysicsTurbofanPanel
physics_panel = """
/* ════════════════════════════════════════════════════════════════════════════
   PHYSICS TURBOFAN PANEL
   ════════════════════════════════════════════════════════════════════════════ */
const PTF_DEF = {
  alt:35000, mach:0.8, throttle:1.0,
  A1:1.5, A2:0.32, A8:0.27, BPR:5.0, fanStages:1, hpcStages:10, hptStages:2, lptStages:3,
  etaI:0.98, FPR:1.5, etaFan:0.89, CPR:15.0, etaHpc:0.85,
  etaB:0.99, dpP:0.04, maxF:0.25, minF:0.125, Vnom:45, Tmax:1500,
  etaHpt:0.90, etaLpt:0.92, mechLossHp:0.99, mechLossLp:0.99, etaNozCore:0.98, etaNozByp:0.98,
};

function PhysicsTurbofanPanel() {
  const [mode, setMode] = useState("single");
  const [p, setP]       = useState(PTF_DEF);
  const set = (k,v) => setP(prev => ({...prev,[k]:v}));

  const [result,    setResult]    = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);

  const makeBody = () => ({
    eng_param: { A1:p.A1, A2:p.A2, fan_n_stages:p.fanStages, hpc_n_stages:p.hpcStages, hpt_n_stages:p.hptStages, lpt_n_stages:p.lptStages, A8:p.A8, BPR:p.BPR },
    eng_perf:  { eta_i:p.etaI, FPR:p.FPR, eta_fan:p.etaFan, CPR:p.CPR, eta_hpc:p.etaHpc, eta_b:p.etaB, dp_over_p:p.dpP,
                 max_f:p.maxF, min_f:p.minF, V_nominal:p.Vnom, T_max:p.Tmax,
                 eta_hpt:p.etaHpt, eta_lpt:p.etaLpt, mech_loss_hp:p.mechLossHp, mech_loss_lp:p.mechLossLp, eta_noz_core:p.etaNozCore, eta_noz_byp:p.etaNozByp },
    throttle_pos:p.throttle, alt:p.alt, M_i:p.mach, mdot_core_guess:20,
  });

  const post = async (url, payload) => {
    const r = await fetch(`${API}${url}`, {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload),
    });
    if (!r.ok) { const d = await r.json(); throw new Error(d.detail || r.statusText); }
    return r.json();
  };

  const runSingle = async () => {
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await post("/api/physics_turbofan/single", makeBody());
      setResult(r);
    } catch(e) { setError(e.message); }
    setLoading(false);
  };

  const reset = () => { setP(PTF_DEF); setResult(null); setError(null); };

  return (
    <div className="grid">
      <div className="sidebar">
        <div className="card">
          <div className="card-hd">Mode</div>
          <div className="card-bd">
            <div className="mode-tog">
              <button className={`mode-btn active`}>Single Point</button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-hd">Flight Conditions</div>
          <div className="card-bd">
            <Slider label="Altitude" unit="ft" value={p.alt} min={0} max={50000} step={500} onChange={v=>set("alt",v)} dp={0}/>
            <Slider label="Mach" unit="" value={p.mach} min={0} max={0.9} step={0.01} onChange={v=>set("mach",v)} dp={2}/>
            <Slider label="Throttle" unit="" value={p.throttle} min={0.5} max={1.0} step={0.01} onChange={v=>set("throttle",v)} dp={2}/>
          </div>
        </div>

        <div className="card">
          <div className="card-hd">Engine Geometry</div>
          <div className="card-bd">
            <Slider label="Inlet area A₁"       unit="m²" value={p.A1} min={0.1} max={5.0} step={0.01} onChange={v=>set("A1",v)}/>
            <Slider label="Core face A₂"  unit="m²" value={p.A2} min={0.05} max={2.0} step={0.01} onChange={v=>set("A2",v)}/>
            <Slider label="Bypass Ratio (BPR)"    unit="" value={p.BPR} min={0.1} max={15.0} step={0.1} onChange={v=>set("BPR",v)}/>
            <Slider label="Core Nozzle A₈"    unit="m²" value={p.A8} min={0.02} max={2.0} step={0.01} onChange={v=>set("A8",v)}/>
            <div className="row2">
              <Num label="Fan stages" unit="" value={p.fanStages} min={1} max={3} onChange={v=>set("fanStages",v)}/>
              <Num label="HPC stages" unit="" value={p.hpcStages} min={1} max={20} onChange={v=>set("hpcStages",v)}/>
            </div>
            <div className="row2">
              <Num label="HPT stages" unit="" value={p.hptStages} min={1} max={4}  onChange={v=>set("hptStages",v)}/>
              <Num label="LPT stages" unit="" value={p.lptStages} min={1} max={6}  onChange={v=>set("lptStages",v)}/>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-hd">Compression</div>
          <div className="card-bd">
            <Slider label="Fan PR (FPR)" unit=""  value={p.FPR}  min={1.1}    max={2.5}   step={0.05}   onChange={v=>set("FPR",v)}/>
            <Slider label="Fan Eff η_fan"  unit=""  value={p.etaFan} min={0.70} max={0.98} step={0.005} onChange={v=>set("etaFan",v)}/>
            <Slider label="Core PR (CPR)" unit=""  value={p.CPR}  min={2}    max={40}   step={0.1}   onChange={v=>set("CPR",v)}/>
            <Slider label="HPC Eff η_hpc"  unit=""  value={p.etaHpc} min={0.60} max={0.95} step={0.005} onChange={v=>set("etaHpc",v)}/>
          </div>
        </div>

        <div className="card">
          <div className="card-hd">Combustor</div>
          <div className="card-bd">
            <Slider label="Efficiency η_b"     unit=""   value={p.etaB} min={0.80} max={1.00} step={0.005} onChange={v=>set("etaB",v)}/>
            <Slider label="Pressure loss dp/p" unit=""   value={p.dpP}  min={0.02} max={0.15} step={0.005} onChange={v=>set("dpP",v)}/>
            <Slider label="TIT Limit T_max"    unit="K"  value={p.Tmax} min={900}  max={2000} step={10}    onChange={v=>set("Tmax",v)} dp={0}/>
          </div>
        </div>

        <div className="btn-row">
          <button className="btn btn-tj" style={{flex:3}}
            onClick={runSingle} disabled={loading}>
            {loading ? <><span className="spin"/>Computing…</> : "▶  Run Simulation"}
          </button>
          <button className="btn btn-ghost btn-sm" style={{flex:1}} onClick={reset} disabled={loading}>Reset</button>
        </div>
      </div>

      <div className="content">
        {error && <div className="alert a-err"><strong>Error:</strong>&nbsp;{error}</div>}
        
        {!result && !loading && !error && (
          <div className="alert a-info">
            Physics Turbofan Simulation combines a Cantera-based two-spool mass flow solver.<br/>
            Configure parameters on the left and click <strong>Run Simulation</strong>.
          </div>
        )}

        {result && (
          <>
            {!result.converged && (
              <div className="alert a-err">⚠ Mass-flow convergence incomplete — results are approximate.</div>
            )}
            
            <div className="kpi-strip">
              <KPI label="Total Thrust" value={fmt(result.T,2)}        unit="kN"        cls="hi-tj"/>
              <KPI label="Bypass Thrust" value={fmt(result.T_byp,2)}         unit="kN"        />
              <KPI label="Core Thrust" value={fmt(result.T_core,2)}          unit="kN"        />
              <KPI label="Fuel Flow"  value={fmt(result.mdot_fuel*3600,1)} unit="kg/h"      />
              <KPI label="TSFC"       value={fmt(result.TSFC,2)}           unit="kg/(kN&middot;h)" />
              <KPI label="Bypass Ratio" value={fmt(result.BPR,2)}            unit=""          />
              <KPI label="Req. A₁₈"     value={fmt(result.A18_calc,3)}       unit="m²"        />
            </div>
            
            <div className="card">
              <div className="card-hd">Station Data</div>
              <div className="card-bd" style={{padding:0}}>
                <StationTable stations={result.stations}/>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
"""
content = content.replace('function App() {', physics_panel + '\\nfunction App() {')

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
