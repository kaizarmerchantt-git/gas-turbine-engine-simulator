# Next-Session Context Loader (READ-ONLY — make NO changes while loading)

Paste everything below into the new session.

---

Resume work on AETHER-X Gas Turbine Engine Simulator (v0.6.0 Obsidian Blueprint). **During this context-loading phase, only read files. Do not edit, create, delete, run generators, run `graphify update`, commit, or push anything.** When done, give me a short summary and wait for instructions.

Project root: `C:\Users\kaiza\Downloads\Gas Turbine Simulator`
App directory: `C:\Users\kaiza\Downloads\Gas Turbine Simulator\gas-turbine-engine-simulator`

## Read in this order
1. `gas-turbine-engine-simulator/SESSION_LOG.md` — what we did, known issues, caveats (most important; note that the earlier "all passed" report overstated results).
2. `.agents/rules/graphify.md` and `graphify-out/GRAPH_REPORT.md` — project rules and architecture overview (use `graphify query` for questions; do not update the graph yet).
3. `gas-turbine-engine-simulator/README.md`, `Scope`, `SETUP_GUIDE.md`.
4. Backend: `backend/main.py` (endpoints + Pydantic models), `physics_turbofan.py`, `turbojet.py`, `engine_helper.py`, `turboprop.py`, `off_design.py`, `meanline.py`, `mission.py`, `surrogate.py`, `hybrid.py`.
5. Frontend generators (source of truth; `frontend/index.html` and `index_v0.5.html` are generated — never hand-edit): `scratch/assemble.py`, `gen_css.py`, `gen_common_components.py`, `gen_domains_1_to_4.py`, `gen_domains_5_to_9.py`, `gen_app.py`. Reference only: `frontend/index_v0.4_legacy.html`.
6. Tests: `verify_e2e_render.py`, `backend/test_*.py`.
7. Artifacts in `C:\Users\kaiza\.gemini\antigravity\brain\5b64f18d-03a6-4591-b642-0659bfedb842`: `v0.6_forensic_verification_and_restoration_report.md`, `v0.5_forensic_bug_report_and_upgrade_plan.md`, and screenshots `v06_e2e_*.png`.
8. Also `Audit01 - Multispool extension.md` in the project root.

## Key facts to confirm you understood
- Nothing is committed or pushed to git; many files are modified/untracked. Do not commit or push unless I explicitly ask.
- Frontend rebuild: `python scratch/assemble.py`; e2e test: `python verify_e2e_render.py` (backend on port 8899).
- Known weaknesses: fragile turbofan solver convergence, masking hardcoded KPI fallbacks, weak e2e assertions, Domains 07-09 only screenshot-checked.
- After modifying code files in a later session, run `graphify update .` (per project rule).

Then report: (a) project state in ~10 lines, (b) the open issues list, (c) a proposed plan for today. Wait for my go-ahead.
