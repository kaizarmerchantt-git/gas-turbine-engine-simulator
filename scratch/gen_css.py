CSS_CONTENT = """
    :root {
      --bg-void: #090A0C;
      --bg-panel: #101216;
      --bg-panel-header: #161920;
      --bg-card: #101216;
      --bg-card-header: #161920;
      --bg-input: #0B0D11;
      
      --border-hairline: #242832;
      --border-focus: #363C4A;
      --border-crosshair: #485063;

      --text-white: #F2F4F8;
      --text-silver: #8E95A5;
      --text-dim: #4B5563;

      --accent-emerald: #10B981;
      --accent-amber: #F59E0B;
      --accent-crimson: #EF4444;
      --accent-cyan: #38BDF8;

      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-display: 'Share Tech Mono', 'JetBrains Mono', monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: var(--font-mono);
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    html, body {
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background-color: var(--bg-void);
      color: var(--text-white);
      font-size: 11px;
      line-height: 1.4;
    }

    #root {
      width: 100vw;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* Subtle Avionics Drafting Grid */
    body::before {
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background:
        linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
      background-size: 24px 24px;
      pointer-events: none;
      z-index: 0;
    }

    /* Custom Precision Scrollbars */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: var(--bg-void); }
    ::-webkit-scrollbar-thumb { background: #242832; border-radius: 0; }
    ::-webkit-scrollbar-thumb:hover { background: #363C4A; }

    /* ════════════════════════════════════════════════════════════════════════
       3-ROW MASTER VIEWPORT LAYOUT (LOCKED 100vh - NO SCROLL)
       ════════════════════════════════════════════════════════════════════════ */
    .app-header {
      height: 44px;
      min-height: 44px;
      background: var(--bg-panel);
      border-bottom: 1px solid var(--border-hairline);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      gap: 12px;
      z-index: 100;
      position: relative;
    }

    .app-workspace {
      height: calc(100vh - 70px);
      display: grid;
      grid-template-columns: 300px 1fr;
      overflow: hidden;
      position: relative;
      z-index: 1;
    }

    .app-sidebar {
      width: 300px;
      height: 100%;
      overflow-y: auto;
      background: var(--bg-panel);
      border-right: 1px solid var(--border-hairline);
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .app-mainstage {
      height: 100%;
      overflow-y: auto;
      background: var(--bg-void);
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .app-footer {
      height: 26px;
      min-height: 26px;
      background: var(--bg-panel);
      border-top: 1px solid var(--border-hairline);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      font-size: 10px;
      color: var(--text-silver);
      letter-spacing: 0.5px;
      z-index: 100;
      position: relative;
    }

    /* ════════════════════════════════════════════════════════════════════════
       TOP HEADER NAV: TITLE, 9 DOMAIN PILLS, UNITS, STATUS, CLOCK
       ════════════════════════════════════════════════════════════════════════ */
    .header-branding {
      display: flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 1px;
      color: var(--text-white);
      flex-shrink: 0;
    }
    .header-branding .crosshair-mark {
      color: var(--accent-amber);
      font-size: 14px;
      line-height: 1;
    }

    .domain-nav-container {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex-shrink: 0;
    }

    .domain-pills-strip {
      display: flex;
      align-items: center;
      gap: 3px;
      flex-wrap: nowrap;
      overflow-x: auto;
      white-space: nowrap;
      scrollbar-width: none;
      flex-shrink: 0;
    }
    .domain-pills-strip::-webkit-scrollbar { display: none; }

    .domain-pill {
      background: transparent;
      border: 1px solid var(--border-hairline);
      color: var(--text-silver);
      font-size: 9.5px;
      font-weight: 600;
      letter-spacing: 0.3px;
      padding: 3px 6px;
      cursor: pointer;
      transition: all 0.15s ease;
      border-radius: 0;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .domain-pill:hover {
      color: var(--text-white);
      border-color: var(--border-focus);
      background: rgba(255, 255, 255, 0.03);
    }
    .domain-pill.active {
      color: var(--accent-amber);
      border-color: var(--accent-amber);
      background: rgba(245, 158, 11, 0.08);
      font-weight: 700;
    }

    .domain-select-dropdown {
      background: var(--bg-card);
      border: 1px solid var(--border-hairline);
      color: var(--accent-amber);
      font-size: 9.5px;
      font-weight: 700;
      padding: 2px 6px;
      height: 23px;
      cursor: pointer;
      border-radius: 0;
      flex-shrink: 0;
    }
    .domain-select-dropdown:focus {
      outline: none;
      border-color: var(--accent-amber);
    }

    .header-telemetry-cluster {
      display: flex;
      align-items: center;
      gap: 12px;
      white-space: nowrap;
    }

    .unit-toggle-pill {
      display: flex;
      background: var(--bg-input);
      border: 1px solid var(--border-hairline);
      padding: 1px;
    }
    .unit-toggle-btn {
      background: transparent;
      border: none;
      color: var(--text-silver);
      font-size: 9.5px;
      font-weight: 600;
      padding: 3px 8px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .unit-toggle-btn.active {
      background: #1C2028;
      color: var(--text-white);
      font-weight: 700;
    }

    .solver-status-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 10px;
      color: var(--text-silver);
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 3px 8px;
    }
    .solver-status-badge.error {
      background: rgba(239, 68, 68, 0.08);
      border-color: rgba(239, 68, 68, 0.3);
      color: var(--accent-crimson);
    }
    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 6px var(--accent-emerald);
    }
    .status-dot.error {
      background: var(--accent-crimson);
      box-shadow: 0 0 6px var(--accent-crimson);
    }

    .utc-clock {
      font-size: 10px;
      color: var(--text-dim);
      letter-spacing: 0.5px;
    }

    /* ════════════════════════════════════════════════════════════════════════
       PANEL CARDS WITH CORNER CROSSHAIR REGISTRATION MARKS (+)
       ════════════════════════════════════════════════════════════════════════ */
    .panel-card {
      background: var(--bg-panel);
      border: 1px solid var(--border-hairline);
      position: relative;
      border-radius: 0;
    }
    .panel-card::before {
      content: '+';
      position: absolute;
      top: -6px;
      left: -5px;
      color: var(--border-crosshair);
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1;
      pointer-events: none;
    }
    .panel-card::after {
      content: '+';
      position: absolute;
      bottom: -6px;
      right: -5px;
      color: var(--border-crosshair);
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1;
      pointer-events: none;
    }

    .panel-card-header {
      background: var(--bg-panel-header);
      border-bottom: 1px solid var(--border-hairline);
      padding: 6px 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: 1px;
      color: var(--text-silver);
      text-transform: uppercase;
    }

    .panel-card-body {
      padding: 10px;
    }

    /* ════════════════════════════════════════════════════════════════════════
       KPI METRIC CARDS (ALL NUMBERS STARK TITANIUM WHITE)
       ════════════════════════════════════════════════════════════════════════ */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
    }

    .kpi-block {
      background: var(--bg-panel);
      border: 1px solid var(--border-hairline);
      padding: 7px 10px;
      position: relative;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .kpi-label {
      font-size: 9px;
      color: var(--text-silver);
      letter-spacing: 0.5px;
      text-transform: uppercase;
      margin-bottom: 3px;
    }

    .kpi-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--text-white); /* MANDATORY TITANIUM WHITE */
      display: flex;
      align-items: baseline;
      gap: 4px;
      line-height: 1.2;
    }

    .kpi-unit {
      font-size: 10px;
      font-weight: 400;
      color: var(--text-silver); /* MUTED SILVER */
    }

    .kpi-sub {
      font-size: 9px;
      color: var(--text-dim);
      margin-top: 3px;
      display: flex;
      align-items: center;
      gap: 4px;
    }

    /* ════════════════════════════════════════════════════════════════════════
       HARDWARE-STYLE GRADUATED RULER SLIDERS (VERNIER SCALE)
       ════════════════════════════════════════════════════════════════════════ */
    .slider-group {
      margin-bottom: 9px;
    }
    .slider-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 10px;
      margin-bottom: 2px;
    }
    .slider-label {
      color: var(--text-silver);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .slider-val {
      color: var(--text-white);
      font-weight: 700;
    }

    .range-input {
      width: 100%;
      height: 6px;
      -webkit-appearance: none;
      background: repeating-linear-gradient(90deg, #363C4A 0px, #363C4A 1px, transparent 1px, transparent 8px), #161920;
      border: 1px solid var(--border-hairline);
      border-radius: 0;
      outline: none;
      cursor: pointer;
      margin: 3px 0 6px;
    }
    .range-input::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 8px;
      height: 16px;
      background: var(--text-white);
      border: 1px solid var(--bg-void);
      border-radius: 0;
      cursor: ew-resize;
      box-shadow: 0 0 4px rgba(0,0,0,0.8);
      transition: background 0.1s ease;
    }
    .range-input::-webkit-slider-thumb:hover {
      background: var(--accent-amber);
    }
    .range-input::-moz-range-thumb {
      width: 8px;
      height: 16px;
      background: var(--text-white);
      border: 1px solid var(--bg-void);
      border-radius: 0;
      cursor: ew-resize;
      box-shadow: 0 0 4px rgba(0,0,0,0.8);
    }
    .range-input::-moz-range-thumb:hover {
      background: var(--accent-amber);
    }

    /* ════════════════════════════════════════════════════════════════════════
       BUTTONS, DROPDOWNS, SUB-TABS & SELECTORS
       ════════════════════════════════════════════════════════════════════════ */
    .blueprint-btn {
      background: #14171E;
      border: 1px solid var(--border-hairline);
      color: var(--text-silver);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.5px;
      padding: 5px 10px;
      cursor: pointer;
      border-radius: 0;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    .blueprint-btn:hover {
      color: var(--text-white);
      border-color: var(--border-focus);
      background: #1A1F29;
    }
    .blueprint-btn.primary {
      background: rgba(245, 158, 11, 0.12);
      border-color: var(--accent-amber);
      color: var(--accent-amber);
      font-weight: 700;
    }
    .blueprint-btn.primary:hover {
      background: rgba(245, 158, 11, 0.22);
    }
    .blueprint-btn.active {
      background: #1E2430;
      border-color: var(--accent-amber);
      color: var(--text-white);
      font-weight: 700;
    }

    .blueprint-select {
      width: 100%;
      background: var(--bg-input);
      border: 1px solid var(--border-hairline);
      color: var(--text-white);
      font-size: 10.5px;
      font-weight: 600;
      padding: 5px 8px;
      border-radius: 0;
      outline: none;
      cursor: pointer;
      margin-bottom: 8px;
    }
    .blueprint-select:focus {
      border-color: var(--accent-amber);
    }

    /* ════════════════════════════════════════════════════════════════════════
       BLUEPRINT DATA TABLES
       ════════════════════════════════════════════════════════════════════════ */
    .table-container {
      overflow-x: auto;
      overflow-y: auto;
      max-height: 420px;
    }
    .blueprint-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10px;
    }
    .blueprint-table th {
      background: var(--bg-panel-header);
      color: var(--text-silver);
      text-align: left;
      padding: 5px 8px;
      border-bottom: 1px solid var(--border-hairline);
      font-weight: 600;
      position: sticky;
      top: 0;
      z-index: 2;
      white-space: nowrap;
    }
    .blueprint-table th.num, .blueprint-table td.num {
      text-align: right;
    }
    .blueprint-table td {
      padding: 4px 8px;
      border-bottom: 1px solid #1A1E26;
      color: #CBD5E1;
      white-space: nowrap;
    }
    .blueprint-table tr:nth-child(even) td {
      background: rgba(255, 255, 255, 0.015);
    }
    .blueprint-table tr:hover td {
      background: rgba(245, 158, 11, 0.06);
    }
    .blueprint-table tr.selected td {
      background: rgba(56, 189, 248, 0.12);
      color: var(--text-white);
      font-weight: 700;
    }

    /* ════════════════════════════════════════════════════════════════════════
       TECHNICAL TAGS & STATUS BADGES
       ════════════════════════════════════════════════════════════════════════ */
    .tech-tag {
      font-size: 9px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 0;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      display: inline-block;
    }
    .tech-tag.optimal {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid var(--accent-emerald);
      color: var(--accent-emerald);
    }
    .tech-tag.warning {
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid var(--accent-amber);
      color: var(--accent-amber);
    }
    .tech-tag.critical {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid var(--accent-crimson);
      color: var(--accent-crimson);
    }
    .tech-tag.info {
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid var(--accent-cyan);
      color: var(--accent-cyan);
    }

    .chart-box {
      width: 100%;
      height: 250px;
      position: relative;
    }
"""
