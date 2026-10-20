import re

input_path = "frontend/index_v0.5.html"

with open(input_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update CSS Variables in :root
old_root = """    :root {
      --bg-void: #090A0C;
      --bg-panel: #0E1218;
      --bg-panel-alt: #131822;
      --bg-card: #11151F;
      --bg-card-header: #161C28;
      --bg-input: #080B0F;

      --border-hairline: #1E2533;
      --border-accent: #2E384D;
      --border-highlight: #38BDF8;

      --text-titanium: #F2F4F8;
      --text-muted: #8E95A5;
      --text-dim: #525968;

      --accent-cyan: #38BDF8;
      --accent-neon: #00F0FF;
      --accent-amber: #F59E0B;
      --accent-emerald: #10B981;
      --accent-crimson: #EF4444;

      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', 'Courier New', monospace;
      --font-display: 'Share Tech Mono', monospace;
    }"""

new_root = """    :root {
      --bg-void: #090B0E;         /* Deep matte obsidian / carbon void */
      --bg-panel: #0E1217;        /* Blueprint frame panel */
      --bg-panel-alt: #131720;    /* Blueprint secondary panel */
      --bg-card: #11151D;         /* Container cards */
      --bg-card-header: #151A24;  /* Container headers */
      --bg-input: #0A0D12;        /* Dark recessed input */

      --border-hairline: #1F2633;  /* Crisp technical hairline */
      --border-accent: #2E384D;    /* Muted structural line */
      --border-highlight: #F59E0B; /* Avionics Amber accent */

      --text-titanium: #F2F4F8;   /* Stark titanium white */
      --text-muted: #8E95A5;      /* Slate silver drafting text */
      --text-dim: #555E70;        /* Subtle coordinate markings */

      --accent-amber: #F59E0B;     /* Primary Avionics Amber */
      --accent-amber-light: #FCD34D; /* Warm Gold */
      --accent-orange: #EA580C;    /* Incandescent Combustion Orange */
      --accent-emerald: #10B981;   /* Nominal / Verified Green */
      --accent-crimson: #EF4444;   /* Alert / Critical Red */

      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', 'Courier New', monospace;
      --font-display: 'Share Tech Mono', monospace;
    }"""

assert old_root in content, "old_root not found"
content = content.replace(old_root, new_root)

# 2. Update body styling to eliminate cyan radial haze
old_body = """    body {
      background-color: var(--bg-void);
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.05) 0%, transparent 60%),
        linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 100% 100%, 24px 24px, 24px 24px;"""

new_body = """    body {
      background-color: var(--bg-void);
      background-image: 
        linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 24px 24px, 24px 24px;"""

assert old_body in content, "old_body not found"
content = content.replace(old_body, new_body)

# 3. Update brand badge and active tab
old_brand_sub = """    .brand-mark .sub {
      color: var(--accent-cyan);
      font-weight: 400;
      font-size: 11px;
      letter-spacing: 1px;
      padding: 2px 6px;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.3);
      border-radius: 2px;
    }"""

new_brand_sub = """    .brand-mark .sub {
      color: var(--accent-amber);
      font-weight: 600;
      font-size: 10px;
      letter-spacing: 1px;
      padding: 2px 7px;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.35);
      border-radius: 2px;
    }"""

assert old_brand_sub in content, "old_brand_sub not found"
content = content.replace(old_brand_sub, new_brand_sub)

old_active_tab = """    .module-tab.active {
      color: var(--accent-cyan);
      background: rgba(56, 189, 248, 0.05);
    }

    .module-tab.active::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--accent-cyan);
      box-shadow: 0 0 8px var(--accent-cyan);
    }"""

new_active_tab = """    .module-tab.active {
      color: var(--text-titanium);
      background: rgba(245, 158, 11, 0.08);
    }

    .module-tab.active::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--accent-amber);
      box-shadow: 0 0 8px rgba(245, 158, 11, 0.6);
    }"""

assert old_active_tab in content, "old_active_tab not found"
content = content.replace(old_active_tab, new_active_tab)

# 4. Corner crosshairs '+' for panel cards and cutaway stage
old_panel_card = """    .panel-card {
      background: var(--bg-panel);
      border: 1px solid var(--border-hairline);
      border-radius: 4px;
      position: relative;
      margin-bottom: 20px;
    }"""

new_panel_card = """    .panel-card {
      background: var(--bg-panel);
      border: 1px solid var(--border-hairline);
      border-radius: 4px;
      position: relative;
      margin-bottom: 20px;
    }

    .panel-card::before {
      content: '+';
      position: absolute;
      top: -6px;
      left: -5px;
      color: var(--text-dim);
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1;
      pointer-events: none;
    }

    .panel-card::after {
      content: '+';
      position: absolute;
      top: -6px;
      right: -5px;
      color: var(--text-dim);
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1;
      pointer-events: none;
    }"""

assert old_panel_card in content, "old_panel_card not found"
content = content.replace(old_panel_card, new_panel_card)

# 5. Metric Color Utilities
old_colors = """.c-titanium { color: var(--text-titanium); }
    .c-cyan { color: var(--accent-cyan); }
    .c-amber { color: var(--accent-amber); }"""

new_colors = """.c-titanium { color: var(--text-titanium); }
    .c-cyan { color: var(--accent-amber); }
    .c-amber { color: var(--accent-amber); }"""

assert old_colors in content, "old_colors not found"
content = content.replace(old_colors, new_colors)

# 6. Controls: Range slider thumb
old_range_thumb = """    .range-input::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--accent-cyan);
      border: 2px solid var(--bg-void);
      cursor: pointer;
      box-shadow: 0 0 6px rgba(56, 189, 248, 0.6);
      transition: transform 0.1s ease;
    }

    .range-input::-webkit-slider-thumb:hover {
      transform: scale(1.2);
    }"""

new_range_thumb = """    .range-input::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #FFFFFF;
      border: 2px solid var(--accent-amber);
      cursor: pointer;
      box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
      transition: transform 0.1s ease;
    }

    .range-input::-webkit-slider-thumb:hover {
      transform: scale(1.25);
      background: var(--accent-amber);
      border-color: #FFFFFF;
    }"""

assert old_range_thumb in content, "old_range_thumb not found"
content = content.replace(old_range_thumb, new_range_thumb)

# 7. Action Button & Sub Button & Select Focus
old_action_btn = """    .action-btn {
      width: 100%;
      padding: 10px 16px;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid var(--accent-cyan);
      color: var(--accent-cyan);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
      border-radius: 3px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 8px;
    }

    .action-btn:hover {
      background: var(--accent-cyan);
      color: var(--bg-void);
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
    }"""

new_action_btn = """    .action-btn {
      width: 100%;
      padding: 10px 16px;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid var(--accent-amber);
      color: var(--accent-amber);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
      border-radius: 3px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 8px;
    }

    .action-btn:hover {
      background: var(--accent-amber);
      color: #090B0E;
      box-shadow: 0 0 12px rgba(245, 158, 11, 0.4);
    }"""

assert old_action_btn in content, "old_action_btn not found"
content = content.replace(old_action_btn, new_action_btn)

old_sub_btn = """    .sub-btn:hover, .sub-btn.active {
      color: var(--text-titanium);
      border-color: var(--accent-cyan);
      background: rgba(56, 189, 248, 0.08);
    }"""

new_sub_btn = """    .sub-btn:hover, .sub-btn.active {
      color: var(--text-titanium);
      border-color: var(--accent-amber);
      background: rgba(245, 158, 11, 0.1);
    }"""

assert old_sub_btn in content, "old_sub_btn not found"
content = content.replace(old_sub_btn, new_sub_btn)

old_select_focus = """    .select-input:focus {
      border-color: var(--accent-cyan);
    }"""

new_select_focus = """    .select-input:focus {
      border-color: var(--accent-amber);
    }"""

assert old_select_focus in content, "old_select_focus not found"
content = content.replace(old_select_focus, new_select_focus)

# 8. Tooltip title color in Chart.js
old_tooltip = """            tooltip: {
              backgroundColor: "rgba(14, 18, 24, 0.95)",
              titleColor: "#38BDF8","""

new_tooltip = """            tooltip: {
              backgroundColor: "rgba(14, 18, 24, 0.95)",
              titleColor: "#F59E0B","""

assert old_tooltip in content, "old_tooltip not found"
content = content.replace(old_tooltip, new_tooltip)

# 9. StationTable STN column
old_stn_col = """<td style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>STN {id}</td>"""
new_stn_col = """<td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>STN {id}</td>"""
assert old_stn_col in content, "old_stn_col not found"
content = content.replace(old_stn_col, new_stn_col)

# 10. EngineCutawaySvg: Thermal gradient & vectors
old_engine_cutaway = """            <defs>
              <linearGradient id="gasPathGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.25" />
                <stop offset="30%" stopColor="#38BDF8" stopOpacity="0.45" />
                <stop offset="48%" stopColor="#F59E0B" stopOpacity="0.55" />
                <stop offset="65%" stopColor="#EF4444" stopOpacity="0.75" />
                <stop offset="85%" stopColor="#F59E0B" stopOpacity="0.55" />
                <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.30" />
              </linearGradient>

              <pattern id="gridPattern" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />
              </pattern>
            </defs>

            {/* Drafting Grid */}
            <rect width="820" height="160" fill="url(#gridPattern)" />

            {/* Centerline */}
            <line x1="20" y1="80" x2="800" y2="80" stroke="#8E95A5" strokeDasharray="6,4" strokeWidth="1" opacity="0.4" />

            {/* Nacelle & Gas-Path Outer Mold Line */}
            <path
              d="M 120 40 L 220 32 L 380 44 L 490 40 L 610 46 L 740 52 L 780 58 L 780 102 L 740 108 L 610 114 L 490 120 L 380 116 L 220 128 L 120 120 Z"
              fill="url(#gasPathGrad)"
              stroke="#38BDF8"
              strokeWidth="1.5"
            />"""

new_engine_cutaway = """            <defs>
              <linearGradient id="gasPathGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#64748B" stopOpacity="0.30" />
                <stop offset="28%" stopColor="#94A3B8" stopOpacity="0.45" />
                <stop offset="48%" stopColor="#F59E0B" stopOpacity="0.65" />
                <stop offset="65%" stopColor="#EA580C" stopOpacity="0.85" />
                <stop offset="85%" stopColor="#F59E0B" stopOpacity="0.60" />
                <stop offset="100%" stopColor="#CBD5E1" stopOpacity="0.30" />
              </linearGradient>

              <pattern id="gridPattern" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />
              </pattern>
            </defs>

            {/* Drafting Grid */}
            <rect width="820" height="160" fill="url(#gridPattern)" />

            {/* Centerline */}
            <line x1="20" y1="80" x2="800" y2="80" stroke="#8E95A5" strokeDasharray="6,4" strokeWidth="1" opacity="0.4" />

            {/* Nacelle & Gas-Path Outer Mold Line (Titanium Blueprint Linework) */}
            <path
              d="M 120 40 L 220 32 L 380 44 L 490 40 L 610 46 L 740 52 L 780 58 L 780 102 L 740 108 L 610 114 L 490 120 L 380 116 L 220 128 L 120 120 Z"
              fill="url(#gasPathGrad)"
              stroke="#CBD5E1"
              strokeWidth="1.5"
            />"""

assert old_engine_cutaway in content, "old_engine_cutaway not found"
content = content.replace(old_engine_cutaway, new_engine_cutaway)

old_engine_pins = """                  <line x1={stn.x} y1="15" x2={stn.x} y2="145" stroke={active ? "#38BDF8" : "rgba(255,255,255,0.15)"} strokeDasharray="2,2" strokeWidth="1" />
                  <circle cx={stn.x} cy="80" r={active ? 5 : 3.5} fill={active ? "#38BDF8" : "#090A0C"} stroke="#38BDF8" strokeWidth="1.5" />
                  <rect x={stn.x - 22} y="8" width="44" height="16" fill="#0E1218" stroke={active ? "#38BDF8" : "#1E2533"} rx="2" />
                  <text x={stn.x} y="20" fill={active ? "#38BDF8" : "#8E95A5"} fontSize="9" fontFamily="var(--font-mono)" fontWeight="700" textAnchor="middle">
                    STN {stn.id}
                  </text>"""

new_engine_pins = """                  <line x1={stn.x} y1="15" x2={stn.x} y2="145" stroke={active ? "#F59E0B" : "rgba(255,255,255,0.15)"} strokeDasharray="2,2" strokeWidth="1" />
                  <circle cx={stn.x} cy="80" r={active ? 5 : 3.5} fill={active ? "#F59E0B" : "#090A0C"} stroke={active ? "#F59E0B" : "#8E95A5"} strokeWidth="1.5" />
                  <rect x={stn.x - 22} y="8" width="44" height="16" fill="#0E1218" stroke={active ? "#F59E0B" : "#1E2533"} rx="2" />
                  <text x={stn.x} y="20" fill={active ? "#F59E0B" : "#8E95A5"} fontSize="9" fontFamily="var(--font-mono)" fontWeight="700" textAnchor="middle">
                    STN {stn.id}
                  </text>"""

assert old_engine_pins in content, "old_engine_pins not found"
content = content.replace(old_engine_pins, new_engine_pins)

old_popover = """              background: "rgba(14, 18, 24, 0.96)",
              border: "1px solid var(--accent-cyan)",
              borderRadius: "4px",
              padding: "10px 14px",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
              zIndex: 10
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", marginBottom: "6px" }}>
                <strong style={{ color: "var(--accent-cyan)" }}>STATION {inspectedStation.id}: {inspectedStation.label.toUpperCase()}</strong>"""

new_popover = """              background: "rgba(14, 18, 24, 0.96)",
              border: "1px solid var(--accent-amber)",
              borderRadius: "4px",
              padding: "10px 14px",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
              zIndex: 10
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", marginBottom: "6px" }}>
                <strong style={{ color: "var(--accent-amber)" }}>STATION {inspectedStation.id}: {inspectedStation.label.toUpperCase()}</strong>"""

assert old_popover in content, "old_popover not found"
content = content.replace(old_popover, new_popover)

# 11. TsBraytonDiagram - Stark White Closed Loop (like reference image!)
old_ts_diagram = """            borderColor: "#38BDF8",
            backgroundColor: "rgba(56, 189, 248, 0.12)",
            fill: true,
            tension: 0.25,
            pointRadius: 4,
            pointBackgroundColor: "#38BDF8",
            pointBorderColor: "#FFFFFF","""

new_ts_diagram = """            borderColor: "#F2F4F8",
            backgroundColor: "rgba(245, 158, 11, 0.05)",
            fill: true,
            tension: 0.25,
            pointRadius: 4,
            pointBackgroundColor: "#F2F4F8",
            pointBorderColor: "#090B0E","""

assert old_ts_diagram in content, "old_ts_diagram not found"
content = content.replace(old_ts_diagram, new_ts_diagram)

# 12. Turbojet KPIs
old_turbojet_kpi = """            {/* KPI Ribbon */}
            <div className="kpi-grid">
              <HudKpi label="NET THRUST" value={res ? fmt(netThrust, 2) : "---"} unit="kN" color="cyan" sub="Propulsive Force" />
              <HudKpi label="SPECIFIC THRUST" value={res ? fmt(specThrust, 1) : "---"} unit="N·s/kg" color="cyan" sub="Fn / ṁ_air" />"""

new_turbojet_kpi = """            {/* KPI Ribbon */}
            <div className="kpi-grid">
              <HudKpi label="NET THRUST" value={res ? fmt(netThrust, 2) : "---"} unit="kN" color="titanium" sub="Propulsive Force" />
              <HudKpi label="SPECIFIC THRUST" value={res ? fmt(specThrust, 1) : "---"} unit="N·s/kg" color="titanium" sub="Fn / ṁ_air" />"""

assert old_turbojet_kpi in content, "old_turbojet_kpi not found"
content = content.replace(old_turbojet_kpi, new_turbojet_kpi)

# 13. Turbofan KPIs
old_turbofan_kpi = """            {/* KPI Ribbon */}
            <div className="kpi-grid">
              <HudKpi label="TOTAL THRUST" value={res ? fmt(res.T, 2) : "---"} unit="kN" color="cyan" sub="Net Output" />
              <HudKpi label="BYPASS THRUST" value={res ? fmt(res.T_byp, 2) : "---"} unit="kN" color="cyan" sub={`Fan: ${res ? fmtPct(res.T_byp / (res.T || 1)) : "---"}`} />
              <HudKpi label="CORE THRUST" value={res ? fmt(res.T_core, 2) : "---"} unit="kN" color="cyan" sub="Exhaust Core" />"""

new_turbofan_kpi = """            {/* KPI Ribbon */}
            <div className="kpi-grid">
              <HudKpi label="TOTAL THRUST" value={res ? fmt(res.T, 2) : "---"} unit="kN" color="titanium" sub="Net Output" />
              <HudKpi label="BYPASS THRUST" value={res ? fmt(res.T_byp, 2) : "---"} unit="kN" color="titanium" sub={`Fan: ${res ? fmtPct(res.T_byp / (res.T || 1)) : "---"}`} />
              <HudKpi label="CORE THRUST" value={res ? fmt(res.T_core, 2) : "---"} unit="kN" color="titanium" sub="Exhaust Core" />"""

assert old_turbofan_kpi in content, "old_turbofan_kpi not found"
content = content.replace(old_turbofan_kpi, new_turbofan_kpi)

# 14. CF34 Deck Chart & KPI
old_cf34_chart = """            label: "CALIBRATED THRUST SWEEP",
            data: chartPoints,
            borderColor: "#38BDF8",
            backgroundColor: "rgba(56, 189, 248, 0.1)",
            fill: true,"""

new_cf34_chart = """            label: "CALIBRATED THRUST SWEEP",
            data: chartPoints,
            borderColor: "#F2F4F8",
            backgroundColor: "rgba(245, 158, 11, 0.05)",
            fill: true,"""

assert old_cf34_chart in content, "old_cf34_chart not found"
content = content.replace(old_cf34_chart, new_cf34_chart)

old_cf34_kpi = """              <HudKpi label="NET THRUST" value={fmt(fn_kN, 2)} unit="kN" color="cyan" sub="CF34-10E Calibrated" />"""
new_cf34_kpi = """              <HudKpi label="NET THRUST" value={fmt(fn_kN, 2)} unit="kN" color="titanium" sub="CF34-10E Calibrated" />"""
assert old_cf34_kpi in content, "old_cf34_kpi not found"
content = content.replace(old_cf34_kpi, new_cf34_kpi)

# 15. OffDesign Compressor Map & KPIs
old_compressor_map = """            borderColor: isNom ? "#38BDF8" : "rgba(255, 255, 255, 0.25)",
            borderWidth: isNom ? 2 : 1,
            pointRadius: 0,
            showLine: true
          });
        });

        // Surge Line
        datasets.push({
          label: "SURGE BOUNDARY",
          data: (mapData.surge_line || []).map(pt => ({ x: pt.w_corr ?? pt.m_dot_corr ?? pt.x, y: pt.pr ?? pt.cpr ?? pt.y })),
          borderColor: "#EF4444",
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
          showLine: true
        });

        // Current Operating Point
        if (opPR > 0 && opFlow > 0) {
          datasets.push({
            label: "OPERATING POINT",
            data: [{ x: opFlow, y: opPR }],
            borderColor: "#FFFFFF",
            backgroundColor: "#38BDF8",
            pointRadius: 7,
            pointHoverRadius: 9,
            pointBorderWidth: 2,
            pointBackgroundColor: "#38BDF8","""

new_compressor_map = """            borderColor: isNom ? "#F2F4F8" : "rgba(255, 255, 255, 0.28)",
            borderWidth: isNom ? 2 : 1,
            pointRadius: 0,
            showLine: true
          });
        });

        // Surge Line
        datasets.push({
          label: "SURGE BOUNDARY",
          data: (mapData.surge_line || []).map(pt => ({ x: pt.w_corr ?? pt.m_dot_corr ?? pt.x, y: pt.pr ?? pt.cpr ?? pt.y })),
          borderColor: "#EF4444",
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
          showLine: true
        });

        // Current Operating Point (Avionics Amber Diamond ◇ like reference image!)
        if (opPR > 0 && opFlow > 0) {
          datasets.push({
            label: "OPERATING POINT (OP: STN 3)",
            data: [{ x: opFlow, y: opPR }],
            borderColor: "#FFFFFF",
            backgroundColor: "#F59E0B",
            pointRadius: 7,
            pointHoverRadius: 9,
            pointStyle: 'rectRot',
            pointBorderWidth: 2,
            pointBackgroundColor: "#F59E0B","""

assert old_compressor_map in content, "old_compressor_map not found"
content = content.replace(old_compressor_map, new_compressor_map)

old_offdesign_kpi = """            <div className="kpi-grid">
              <HudKpi label="NET THRUST" value={fmt(opThrust, 2)} unit="kN" color="cyan" sub="Off-Design Output" />
              <HudKpi label="OPERATING CPR" value={fmt(opCPR, 2)} color="cyan" sub={`Target: ${fmt(p.cpr_des, 1)}`} />"""

new_offdesign_kpi = """            <div className="kpi-grid">
              <HudKpi label="NET THRUST" value={fmt(opThrust, 2)} unit="kN" color="titanium" sub="Off-Design Output" />
              <HudKpi label="OPERATING CPR" value={fmt(opCPR, 2)} color="amber" sub={`Target: ${fmt(p.cpr_des, 1)}`} />"""

assert old_offdesign_kpi in content, "old_offdesign_kpi not found"
content = content.replace(old_offdesign_kpi, new_offdesign_kpi)

# Variance Table Cyan Headers
old_var_headers = """                <tr>
                  <td style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>PRESSURE RATIO (CPR)</td>
                  <td className="num">{fmt(p.cpr_des, 2)}</td>
                  <td className="num">{fmt(opCPR, 2)}</td>
                  <td className="num">{fmt(opCPR - p.cpr_des, 3)}</td>
                  <td className="num">{fmt(cprVarPct, 2)}%</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>CORRECTED FLOW [KG/S]</td>
                  <td className="num">{fmt(p.m_dot_des, 2)}</td>
                  <td className="num">{fmt(opFlow, 2)}</td>
                  <td className="num">{fmt(opFlow - p.m_dot_des, 3)}</td>
                  <td className="num">{fmt(flowVarPct, 2)}%</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>COMPRESSOR EFFICIENCY (η_c)</td>
                  <td className="num">{fmtPct(p.eta_c_des)}</td>
                  <td className="num">{fmtPct(opEta)}</td>
                  <td className="num">{fmt(opEta - p.eta_c_des, 4)}</td>
                  <td className="num">{fmt(etaVarPct, 2)}%</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>NET THRUST [KN]</td>"""

new_var_headers = """                <tr>
                  <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>PRESSURE RATIO (CPR)</td>
                  <td className="num">{fmt(p.cpr_des, 2)}</td>
                  <td className="num">{fmt(opCPR, 2)}</td>
                  <td className="num">{fmt(opCPR - p.cpr_des, 3)}</td>
                  <td className="num">{fmt(cprVarPct, 2)}%</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>CORRECTED FLOW [KG/S]</td>
                  <td className="num">{fmt(p.m_dot_des, 2)}</td>
                  <td className="num">{fmt(opFlow, 2)}</td>
                  <td className="num">{fmt(opFlow - p.m_dot_des, 3)}</td>
                  <td className="num">{fmt(flowVarPct, 2)}%</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>COMPRESSOR EFFICIENCY (η_c)</td>
                  <td className="num">{fmtPct(p.eta_c_des)}</td>
                  <td className="num">{fmtPct(opEta)}</td>
                  <td className="num">{fmt(opEta - p.eta_c_des, 4)}</td>
                  <td className="num">{fmt(etaVarPct, 2)}%</td>
                </tr>
                <tr>
                  <td style={{ color: "var(--accent-amber)", fontWeight: 700 }}>NET THRUST [KN]</td>"""

assert old_var_headers in content, "old_var_headers not found"
content = content.replace(old_var_headers, new_var_headers)

# 16. MeanLine Module: Velocity Triangles
old_meanline_tri = """                <defs>
                  <marker id="arrow-cyan" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#38BDF8" />
                  </marker>
                  <marker id="arrow-orange" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
                  </marker>
                  <marker id="arrow-white" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#F2F4F8" />
                  </marker>
                </defs>

                {/* Rotor Inlet (Station 1) Triangle */}
                <g>
                  <text x="60" y="24" fill="#38BDF8" fontSize="10" fontFamily="var(--font-mono)" fontWeight="700">ROTOR INLET TRIANGLE</text>
                  
                  {/* U1 Blade Speed (Horizontal Base) */}
                  <line x1="60" y1="130" x2="220" y2="130" stroke="#F2F4F8" strokeWidth="2.5" markerEnd="url(#arrow-white)" />
                  <text x="140" y="146" fill="#F2F4F8" fontSize="9" fontFamily="var(--font-mono)" textAnchor="middle">U₁ = {fmt(inTri.U, 0)} m/s</text>

                  {/* C1 Absolute Velocity */}
                  <line x1="60" y1="130" x2="60" y2="40" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#arrow-cyan)" />
                  <text x="45" y="85" fill="#38BDF8" fontSize="9" fontFamily="var(--font-mono)" textAnchor="end">C₁ = {fmt(inTri.C, 0)} m/s</text>

                  {/* W1 Relative Velocity (Hypotenuse: (60,40) -> (220,130)) */}
                  <line x1="60" y1="40" x2="220" y2="130" stroke="#F59E0B" strokeWidth="2" strokeDasharray="5,3" markerEnd="url(#arrow-orange)" />
                  <text x="155" y="78" fill="#F59E0B" fontSize="9" fontFamily="var(--font-mono)">W₁ = {fmt(inTri.W, 0)} m/s</text>
                </g>

                {/* Rotor Exit (Station 2) Triangle */}
                <g>
                  <text x="400" y="24" fill="#38BDF8" fontSize="10" fontFamily="var(--font-mono)" fontWeight="700">ROTOR EXIT TRIANGLE</text>

                  {/* U2 Blade Speed */}
                  <line x1="400" y1="130" x2="560" y2="130" stroke="#F2F4F8" strokeWidth="2.5" markerEnd="url(#arrow-white)" />
                  <text x="480" y="146" fill="#F2F4F8" fontSize="9" fontFamily="var(--font-mono)" textAnchor="middle">U₂ = {fmt(exTri.U, 0)} m/s</text>

                  {/* C2 Absolute Velocity */}
                  <line x1="400" y1="130" x2="470" y2="40" stroke="#38BDF8" strokeWidth="2" markerEnd="url(#arrow-cyan)" />
                  <text x="420" y="80" fill="#38BDF8" fontSize="9" fontFamily="var(--font-mono)">C₂ = {fmt(exTri.C, 0)} m/s</text>

                  {/* W2 Relative Velocity (Hypotenuse: (470,40) -> (560,130)) */}
                  <line x1="470" y1="40" x2="560" y2="130" stroke="#F59E0B" strokeWidth="2" strokeDasharray="5,3" markerEnd="url(#arrow-orange)" />
                  <text x="525" y="80" fill="#F59E0B" fontSize="9" fontFamily="var(--font-mono)">W₂ = {fmt(exTri.W, 0)} m/s</text>
                </g>"""

new_meanline_tri = """                <defs>
                  <marker id="arrow-amber" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
                  </marker>
                  <marker id="arrow-orange" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#EA580C" />
                  </marker>
                  <marker id="arrow-white" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#F2F4F8" />
                  </marker>
                </defs>

                {/* Rotor Inlet (Station 1) Triangle */}
                <g>
                  <text x="60" y="24" fill="#F59E0B" fontSize="10" fontFamily="var(--font-mono)" fontWeight="700">ROTOR INLET TRIANGLE</text>
                  
                  {/* U1 Blade Speed (Horizontal Base) */}
                  <line x1="60" y1="130" x2="220" y2="130" stroke="#F2F4F8" strokeWidth="2.5" markerEnd="url(#arrow-white)" />
                  <text x="140" y="146" fill="#F2F4F8" fontSize="9" fontFamily="var(--font-mono)" textAnchor="middle">U₁ = {fmt(inTri.U, 0)} m/s</text>

                  {/* C1 Absolute Velocity (Avionics Amber) */}
                  <line x1="60" y1="130" x2="60" y2="40" stroke="#F59E0B" strokeWidth="2" markerEnd="url(#arrow-amber)" />
                  <text x="45" y="85" fill="#F59E0B" fontSize="9" fontFamily="var(--font-mono)" textAnchor="end">C₁ = {fmt(inTri.C, 0)} m/s</text>

                  {/* W1 Relative Velocity (Combustion Orange: (60,40) -> (220,130)) */}
                  <line x1="60" y1="40" x2="220" y2="130" stroke="#EA580C" strokeWidth="2" strokeDasharray="5,3" markerEnd="url(#arrow-orange)" />
                  <text x="155" y="78" fill="#EA580C" fontSize="9" fontFamily="var(--font-mono)">W₁ = {fmt(inTri.W, 0)} m/s</text>
                </g>

                {/* Rotor Exit (Station 2) Triangle */}
                <g>
                  <text x="400" y="24" fill="#F59E0B" fontSize="10" fontFamily="var(--font-mono)" fontWeight="700">ROTOR EXIT TRIANGLE</text>

                  {/* U2 Blade Speed */}
                  <line x1="400" y1="130" x2="560" y2="130" stroke="#F2F4F8" strokeWidth="2.5" markerEnd="url(#arrow-white)" />
                  <text x="480" y="146" fill="#F2F4F8" fontSize="9" fontFamily="var(--font-mono)" textAnchor="middle">U₂ = {fmt(exTri.U, 0)} m/s</text>

                  {/* C2 Absolute Velocity (Avionics Amber) */}
                  <line x1="400" y1="130" x2="470" y2="40" stroke="#F59E0B" strokeWidth="2" markerEnd="url(#arrow-amber)" />
                  <text x="420" y="80" fill="#F59E0B" fontSize="9" fontFamily="var(--font-mono)">C₂ = {fmt(exTri.C, 0)} m/s</text>

                  {/* W2 Relative Velocity (Combustion Orange: (470,40) -> (560,130)) */}
                  <line x1="470" y1="40" x2="560" y2="130" stroke="#EA580C" strokeWidth="2" strokeDasharray="5,3" markerEnd="url(#arrow-orange)" />
                  <text x="525" y="80" fill="#EA580C" fontSize="9" fontFamily="var(--font-mono)">W₂ = {fmt(exTri.W, 0)} m/s</text>
                </g>"""

assert old_meanline_tri in content, "old_meanline_tri not found"
content = content.replace(old_meanline_tri, new_meanline_tri)

# 17. Turboprop KPIs
old_turboprop_kpis = """            {/* KPI Ribbon */}
            <div className="kpi-grid">
              <HudKpi label="TOTAL THRUST" value={res ? fmt(res.total_thrust_kN || res.F_net_kN, 2) : "---"} unit="kN" color="emerald" sub="Prop + Jet" />
              <HudKpi label="PROP THRUST" value={res ? fmt(res.thrust_prop_kN, 2) : "---"} unit="kN" color="emerald" sub="Blades" />
              <HudKpi label="SHAFT POWER" value={res ? fmt(res.P_shaft_shp || res.SHP, 0) : "---"} unit="shp" color="cyan" sub={`${res ? fmt(res.P_shaft_kW, 0) : "---"} kW`} />
              <HudKpi label="EQUIV SHAFT PWR" value={res ? fmt(res.ESHP, 0) : "---"} unit="eshp" color="cyan" sub="Shaft + Jet Residual" />
              <HudKpi label="PROP EFFICIENCY" value={res ? fmtPct(res.eta_prop) : "---"} color="amber" sub="Hamilton Standard" />
              <HudKpi label="GEARBOX TORQUE" value={res ? fmt(res.torque_Nm, 0) : "---"} unit="N·m" color="amber" sub="Reduction Ratio" />
            </div>"""

new_turboprop_kpis = """            {/* KPI Ribbon */}
            <div className="kpi-grid">
              <HudKpi label="TOTAL THRUST" value={res ? fmt(res.total_thrust_kN || res.F_net_kN, 2) : "---"} unit="kN" color="titanium" sub="Prop + Jet" />
              <HudKpi label="PROP THRUST" value={res ? fmt(res.thrust_prop_kN, 2) : "---"} unit="kN" color="titanium" sub="Blades" />
              <HudKpi label="SHAFT POWER" value={res ? fmt(res.P_shaft_shp || res.SHP, 0) : "---"} unit="shp" color="titanium" sub={`${res ? fmt(res.P_shaft_kW, 0) : "---"} kW`} />
              <HudKpi label="EQUIV SHAFT PWR" value={res ? fmt(res.ESHP, 0) : "---"} unit="eshp" color="titanium" sub="Shaft + Jet Residual" />
              <HudKpi label="PROP EFFICIENCY" value={res ? fmtPct(res.eta_prop) : "---"} color="amber" sub="Hamilton Standard" />
              <HudKpi label="GEARBOX TORQUE" value={res ? fmt(res.torque_Nm, 0) : "---"} unit="N·m" color="amber" sub="Reduction Ratio" />
            </div>"""

assert old_turboprop_kpis in content, "old_turboprop_kpis not found"
content = content.replace(old_turboprop_kpis, new_turboprop_kpis)

# Turboprop tip mach
content = content.replace('<div className="kpi-value c-cyan">{fmt(res?.tip_mach || 0.76, 2)}</div>', '<div className="kpi-value c-amber">{fmt(res?.tip_mach || 0.76, 2)}</div>')

# 18. Mission Module: Drag Polar Chart & KPIs
old_mission_chart = """          {
            label: `TOTAL DRAG [${dragUnit}]`,
            data: dragPts,
            borderColor: "#38BDF8",
            backgroundColor: "rgba(56, 189, 248, 0.1)",
            yAxisID: "y",
            fill: false,
            tension: 0.2,
            pointRadius: 3
          },"""

new_mission_chart = """          {
            label: `TOTAL DRAG [${dragUnit}]`,
            data: dragPts,
            borderColor: "#F2F4F8",
            backgroundColor: "rgba(242, 244, 248, 0.05)",
            yAxisID: "y",
            fill: false,
            tension: 0.2,
            pointRadius: 3
          },"""

assert old_mission_chart in content, "old_mission_chart not found"
content = content.replace(old_mission_chart, new_mission_chart)

old_mission_axes = """        scales: {
          x: { title: { display: true, text: "TRUE AIRSPEED [m/s]" } },
          y: { type: "linear", title: { display: true, text: "DRAG FORCE [N]", color: "#38BDF8" } },"""

new_mission_axes = """        scales: {
          x: { title: { display: true, text: "TRUE AIRSPEED [m/s]" } },
          y: { type: "linear", title: { display: true, text: "DRAG FORCE [N]", color: "#F2F4F8" } },"""

assert old_mission_axes in content, "old_mission_axes not found"
content = content.replace(old_mission_axes, new_mission_axes)

old_mission_kpi = """              <HudKpi label="BLOCK FUEL BURN" value={fuelDisp} color="cyan" sub="Gate-to-Gate" />
              <HudKpi label="FLIGHT TIME" value={fmt(summary.total_flight_time_hr, 2)} unit="hrs" color="cyan" sub={`${fmtInt(summary.total_flight_time_min)} min`} />"""

new_mission_kpi = """              <HudKpi label="BLOCK FUEL BURN" value={fuelDisp} color="amber" sub="Gate-to-Gate" />
              <HudKpi label="FLIGHT TIME" value={fmt(summary.total_flight_time_hr, 2)} unit="hrs" color="titanium" sub={`${fmtInt(summary.total_flight_time_min)} min`} />"""

assert old_mission_kpi in content, "old_mission_kpi not found"
content = content.replace(old_mission_kpi, new_mission_kpi)

# 19. Surrogate Module
old_surrogate_chart = """          {
            label: "PREDICTED THRUST [kN]",
            data: curvePts,
            borderColor: "#38BDF8",
            backgroundColor: "rgba(56, 189, 248, 0.12)",
            fill: true,
            tension: 0.3,
            pointRadius: 2
          },"""

new_surrogate_chart = """          {
            label: "PREDICTED THRUST [kN]",
            data: curvePts,
            borderColor: "#F2F4F8",
            backgroundColor: "rgba(245, 158, 11, 0.05)",
            fill: true,
            tension: 0.3,
            pointRadius: 2
          },"""

assert old_surrogate_chart in content, "old_surrogate_chart not found"
content = content.replace(old_surrogate_chart, new_surrogate_chart)

content = content.replace('<HudKpi label="PREDICTED THRUST" value={pred ? fmt(pred.thrust_kN, 2) : "---"} unit="kN" color="cyan" sub="Gaussian RBF" />',
                          '<HudKpi label="PREDICTED THRUST" value={pred ? fmt(pred.thrust_kN, 2) : "---"} unit="kN" color="titanium" sub="Gaussian RBF" />')

# 20. Hybrid-Electric Module: KPIs & SVG schematic
old_hybrid_kpis = """              <HudKpi label="GT CORE POWER" value={fmt(gtPower, 0)} unit="kW" color="cyan" sub="Thermal Engine" />
              <HudKpi label="ELECTRIC MOTOR" value={fmt(emPower, 0)} unit="kW" color="cyan" sub="Traction Motor" />"""

new_hybrid_kpis = """              <HudKpi label="GT CORE POWER" value={fmt(gtPower, 0)} unit="kW" color="titanium" sub="Thermal Engine" />
              <HudKpi label="ELECTRIC MOTOR" value={fmt(emPower, 0)} unit="kW" color="amber" sub="Traction Motor" />"""

assert old_hybrid_kpis in content, "old_hybrid_kpis not found"
content = content.replace(old_hybrid_kpis, new_hybrid_kpis)

# In hybrid SVG, replace #38BDF8 markers and rects with amber #F59E0B and titanium #CBD5E1
old_hybrid_svg = """                    <defs>
                      <marker id="flow-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#38BDF8" />
                      </marker>
                    </defs>"""

new_hybrid_svg = """                    <defs>
                      <marker id="flow-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                        <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
                      </marker>
                    </defs>"""

assert old_hybrid_svg in content, "old_hybrid_svg not found"
content = content.replace(old_hybrid_svg, new_hybrid_svg)

# Replace the remaining cyan fills/strokes in hybrid schematic:
# GT core rects can be #CBD5E1 (mechanical) and motor/props #F59E0B (electric/thrust)
content = content.replace('stroke="#38BDF8"', 'stroke="#F59E0B"')
content = content.replace('fill="#38BDF8"', 'fill="#F59E0B"')

# 21. Master Header Update to match Reference Image
old_header = """          {/* Header Bar */}
          <header className="blueprint-header">
            <div className="brand-group">
              <div className="brand-mark">
                AETHER-X <span className="sub">v0.5.0-ALPHA // BLUEPRINT</span>
              </div>
              <div className="system-status-pill">
                <span className="status-dot"></span>
                <span>KERNEL ONLINE // PORT 8000</span>
              </div>
            </div>
          </header>"""

new_header = """          {/* Technical Header Bar */}
          <header className="blueprint-header">
            <div className="brand-group">
              <div className="brand-mark">
                AETHER-X <span className="sub">v0.5.0 // OBSIDIAN BLUEPRINT</span>
              </div>
              <span style={{ color: "var(--text-muted)", fontSize: "11px", letterSpacing: "1px", fontFamily: "var(--font-mono)" }}>
                AEROSPACE PROPULSION ENGINEERING SYSTEM
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <div className="system-status-pill">
                <span className="status-dot"></span>
                <span>SYS_STAT: NOMINAL // THERMODYNAMIC KERNEL ACTIVE</span>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-dim)", letterSpacing: "1px" }}>
                PORT: 8000
              </div>
            </div>
          </header>"""

assert old_header in content, "old_header not found"
content = content.replace(old_header, new_header)

with open(input_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: frontend/index_v0.5.html has been completely updated to the dark obsidian + avionics amber blueprint aesthetic!")
