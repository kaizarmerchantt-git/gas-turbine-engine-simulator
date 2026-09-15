import re
with open('backend/meanline.py', 'r') as f:
    text = f.read()

# 1. Apply subagent's KPI fixes
kpi_replacement = """    overall_CPR = curr_P0 / P0_inlet
    overall_W = cp * (curr_T0 - T0_inlet) / 1000.0 # kJ/kg

    avg_psi = stages[0]["psi"] if stages else 0.0
    avg_phi = stages[0]["phi"] if stages else 0.0
    avg_reaction = stages[0]["reaction"] if stages else 0.0
    avg_pr = overall_CPR ** (1.0 / n_stages) if n_stages > 0 else 1.0

    return {
        "n_stages": n_stages,
        "num_stages": n_stages,
        "CPR_target": CPR,
        "CPR_actual": round(overall_CPR, 3),
        "total_PR": round(overall_CPR, 3),
        "total_work_kJkg": round(overall_W, 2),
        "total_delta_h0_kJkg": round(overall_W, 2),
        "T0_inlet": round(T0_inlet, 1),
        "T0_in": round(T0_inlet, 1),
        "T0_exit": round(curr_T0, 1),
        "T0_out": round(curr_T0, 1),
        "P0_inlet_kPa": round(P0_inlet / 1000.0, 2),
        "P0_exit_kPa": round(curr_P0 / 1000.0, 2),
        "P0_in": round(P0_inlet, 1),
        "P0_out": round(curr_P0, 1),
        "N_rpm": N_rpm,
        "U_mean": round(stages[0]["U"], 2),
        "psi": round(avg_psi, 4),
        "loading_coefficient_psi": round(avg_psi, 4),
        "phi": round(avg_phi, 4),
        "flow_coefficient_phi": round(avg_phi, 4),
        "reaction": round(avg_reaction, 3),
        "degree_of_reaction_R": round(avg_reaction, 3),
        "PR_stage": round(avg_pr, 4),
        "stage_PR": round(avg_pr, 4),
        "stages": stages
    }"""

# regex search to replace the return block in solve_multistage_compressor_meanline
text = re.sub(
    r'    overall_CPR = curr_P0 / P0_inlet\s+overall_W = cp \* \(curr_T0 - T0_inlet\) / 1000\.0 # kJ/kg\s+return \{\s+"n_stages": n_stages,.*?"stages": stages\s+\}',
    kpi_replacement,
    text,
    flags=re.DOTALL
)

# 2. Fix the Ca1 and Ca2 mapping in solve_compressor_stage
# rotor_inlet_dict:
text = re.sub(
    r'(rotor_inlet_dict = \{[^\}]+?)"C_a": round\(C_a, 2\),([^\}]+?)"Ca": round\(C_a, 2\),([^\}]+?\})',
    r'\1"C_a": round(Ca1, 2),\2"Ca": round(Ca1, 2),\3',
    text
)

# rotor_exit_dict:
text = re.sub(
    r'(rotor_exit_dict = \{[^\}]+?)"C_a": round\(C_a, 2\),([^\}]+?)"Ca": round\(C_a, 2\),([^\}]+?\})',
    r'\1"C_a": round(Ca2, 2),\2"Ca": round(Ca2, 2),\3',
    text
)

with open('backend/meanline.py', 'w') as f:
    f.write(text)
