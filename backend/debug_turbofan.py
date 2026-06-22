from physics_turbofan import calc_turbofan, DEFAULT_TF_PARAM, DEFAULT_TF_PERF
import traceback
import sys

try:
    res = calc_turbofan(DEFAULT_TF_PARAM, DEFAULT_TF_PERF, mdot_core_guess=10.0)
    print("Converged:", res['converged'])
except Exception as e:
    traceback.print_exc()
