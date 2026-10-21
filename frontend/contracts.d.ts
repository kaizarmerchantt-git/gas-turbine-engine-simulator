/**
 * AETHER-X v0.5 Pure Physics & API Type Definitions
 * Auto-generated from FastAPI OpenAPI schema. DO NOT HAND EDIT.
 */

export interface CompareRequest {
  config_a: TurbojetSingleRequest;
  config_b: TurbojetSingleRequest;
  label_a?: string;
  label_b?: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface HybridMissionRequest {
  architecture?: string;
  cruise_alt_m?: number;
  cruise_mach?: number;
  cruise_dist_km?: number;
  payload_kg?: number;
  battery_mass_kg?: number;
  specific_energy_Wh_kg?: number;
  takeoff_hybrid_ratio?: number;
  climb_hybrid_ratio?: number;
  cruise_hybrid_ratio?: number;
  descent_hybrid_ratio?: number;
}

export interface HybridSingleRequest {
  architecture?: string;
  shaft_power_req_kW?: number;
  hybrid_power_ratio_HP?: number;
  battery_mass_kg?: number;
  battery_soc?: number;
  turbogen_rated_kW?: any;
}

export interface HybridSweepRequest {
  study_type?: string;
  architecture?: string;
  n_points?: number;
  cruise_alt_m?: number;
  cruise_mach?: number;
  cruise_dist_km?: number;
  payload_kg?: number;
  specific_energy_Wh_kg?: number;
  battery_mass_kg?: number;
  takeoff_hybrid_ratio?: number;
  climb_hybrid_ratio?: number;
  cruise_hybrid_ratio?: number;
  descent_hybrid_ratio?: number;
}

export interface MeanlineCompressorStageRequest {
  T01?: number;
  P01?: number;
  delta_T0?: number;
  N_rpm?: number;
  r_mean?: number;
  C_a?: number;
  reaction?: number;
  eta_stage?: number;
  mdot?: number;
  solidity?: number;
  alpha_1_deg?: any;
  beta_2_deg?: any;
  C_a1?: any;
  C_a2?: any;
  alpha_3_deg?: any;
  U?: any;
}

export interface MeanlineMultistageRequest {
  CPR?: number;
  n_stages?: number;
  T0_inlet?: number;
  P0_inlet?: number;
  N_rpm?: number;
  r_mean?: number;
  C_a?: number;
  reaction?: number;
  eta_poly?: number;
  mdot?: number;
}

export interface MeanlineTurbineStageRequest {
  T01?: number;
  P01?: number;
  delta_T0?: number;
  N_rpm?: number;
  r_mean?: number;
  C_a?: number;
  reaction?: number;
  eta_stage?: number;
  solidity?: number;
  alpha_2_deg?: any;
  beta_3_deg?: any;
  U?: any;
}

export interface MissionAirspeedTrendsRequest {
  gross_mass_kg?: number;
  wing_area_m2?: number;
  aspect_ratio?: number;
  CD0?: number;
  oswald_e?: number;
  CL_max?: number;
  alt_ft?: number;
  n_points?: number;
  engine_base_tsfc?: number;
}

export interface MissionSimulateRequest {
  aircraft_type?: string;
  cruise_alt_ft?: number;
  cruise_mach?: number;
  cruise_distance_nm?: number;
  payload_kg?: number;
  fuel_load_kg?: any;
  engine_base_tsfc?: number;
}

export interface MissionSizingRequest {
  gross_mass_kg?: number;
  wing_loading_kg_m2?: any;
  aspect_ratio?: number;
  taper_ratio?: number;
  V_H?: number;
  V_V?: number;
  material?: string;
}

export interface OffDesignSingleRequest {
  /** Relative spool speed N/N_des */
  N_rel?: number;
  /** Altitude [ft] */
  alt?: number;
  /** Flight Mach number */
  mach?: number;
  /** Design compressor pressure ratio */
  cpr_des?: number;
  /** Design compressor efficiency */
  eta_c_des?: number;
  /** Design corrected mass flow [kg/s] */
  mdot_corr_des?: number;
  /** Nozzle throat area [m²]. Sized to design if omitted. */
  A8?: any;
  /** Reference design point altitude [ft] */
  des_alt?: number;
  /** Reference design point Mach number */
  des_mach?: number;
  eta_i?: number;
  eta_t?: number;
  mech_loss?: number;
  eta_b?: number;
  dp_over_p?: number;
  T_max?: number;
  eta_noz?: number;
  throttle_pos?: number;
}

export interface OffDesignSweepRequest {
  sweep_param?: string;
  n_steps?: number;
  speed_start?: number;
  speed_end?: number;
  fixed_speed?: number;
  alt_start?: number;
  alt_end?: number;
  fixed_alt?: number;
  mach_start?: number;
  mach_end?: number;
  fixed_mach?: number;
  cpr_des?: number;
  eta_c_des?: number;
  mdot_corr_des?: number;
  A8?: any;
  des_alt?: number;
  des_mach?: number;
  eta_i?: number;
  eta_t?: number;
  mech_loss?: number;
  eta_b?: number;
  dp_over_p?: number;
  T_max?: number;
  eta_noz?: number;
  throttle_pos?: number;
}

export interface PhysicsTurbofanParam {
  A1?: number;
  A2?: number;
  fan_n_stages?: number;
  hpc_n_stages?: number;
  hpt_n_stages?: number;
  lpt_n_stages?: number;
  A8?: number;
  BPR?: number;
}

export interface PhysicsTurbofanPerf {
  eta_i?: number;
  FPR?: number;
  eta_fan?: number;
  CPR?: number;
  eta_hpc?: number;
  eta_b?: number;
  dp_over_p?: number;
  max_f?: number;
  min_f?: number;
  V_nominal?: number;
  T_max?: number;
  eta_hpt?: number;
  eta_lpt?: number;
  mech_loss_hp?: number;
  mech_loss_lp?: number;
  cooling_bleed_frac?: number;
  gear_ratio?: number;
  eta_gearbox?: number;
  eta_noz_core?: number;
  eta_noz_byp?: number;
}

export interface PhysicsTurbofanSingleRequest {
  eng_param?: PhysicsTurbofanParam;
  eng_perf?: PhysicsTurbofanPerf;
  throttle_pos?: number;
  alt?: number;
  M_i?: number;
  mdot_core_guess?: number;
}

export interface PhysicsTurbofanSweepRequest {
  eng_param?: PhysicsTurbofanParam;
  eng_perf?: PhysicsTurbofanPerf;
  throttle_pos?: number;
  sweep_param?: string;
  alt_start?: number;
  alt_end?: number;
  mach_start?: number;
  mach_end?: number;
  throttle_start?: number;
  throttle_end?: number;
  bpr_start?: number;
  bpr_end?: number;
  cpr_start?: number;
  cpr_end?: number;
  fpr_start?: number;
  fpr_end?: number;
  /** Number of points in sweep */
  n_steps?: number;
  fixed_alt?: number;
  fixed_mach?: number;
  fixed_throttle?: number;
  mdot_core_guess?: number;
}

export interface SurrogatePredictRequest {
  alt_ft?: number;
  mach?: number;
  throttle?: number;
  CPR?: number;
  TIT_K?: number;
}

export interface SurrogateSurfaceRequest {
  x_param?: string;
  y_param?: string;
  x_min?: any;
  x_max?: any;
  n_points?: any;
  fixed_params?: any;
  fixed_alt?: number;
  fixed_mach?: number;
  fixed_throttle?: number;
  fixed_cpr?: number;
  fixed_tit?: number;
  grid_res?: number;
}

export interface TurbofanSingleRequest {
  /** Altitude [ft] */
  alt?: number;
  /** Mach number */
  MN?: number;
  /** Power code (0.55–1.0) */
  PC?: number;
}

export interface TurbofanSweepRequest {
  sweep_param?: string;
  alt_start?: number;
  alt_end?: number;
  mach_start?: number;
  mach_end?: number;
  pc_start?: number;
  pc_end?: number;
  n_steps?: number;
  fixed_alt?: number;
  fixed_mach?: number;
  fixed_pc?: number;
}

export interface TurbojetEngineParam {
  /** Inlet capture area [m²] */
  A1?: number;
  /** Compressor face area [m²] */
  A2?: number;
  /** Number of compressor stages */
  comp_n_stages?: number;
  /** Number of turbine stages */
  turb_n_stages?: number;
  /** Nozzle throat area [m²] */
  A8?: number;
}

export interface TurbojetEnginePerf {
  /** Inlet adiabatic efficiency (0–1] */
  eta_i?: number;
  /** Compressor pressure ratio (>1) */
  CPR?: number;
  /** Compressor isentropic efficiency (0–1] */
  eta_c?: number;
  /** Combustor efficiency (0–1] */
  eta_b?: number;
  /** Combustor pressure loss fraction [0–1) */
  dp_over_p?: number;
  /** Max fuel fraction (stoich) */
  max_f?: number;
  /** Min fuel fraction (stoich) */
  min_f?: number;
  /** Combustor nominal flow velocity [m/s] */
  V_nominal?: number;
  /** Max combustor temperature (TIT limit) [K] */
  T_max?: number;
  /** Turbine isentropic efficiency (0–1] */
  eta_t?: number;
  /** Mechanical efficiency (0–1] */
  mech_loss?: number;
  /** Nozzle adiabatic efficiency (0–1] */
  eta_noz?: number;
}

export interface TurbojetLTORequest {
  eng_param?: TurbojetEngineParam;
  eng_perf?: TurbojetEnginePerf;
  /** Field elevation [ft] */
  alt?: number;
  /** Runway/taxi Mach */
  M_i?: number;
}

export interface TurbojetSingleRequest {
  eng_param?: TurbojetEngineParam;
  eng_perf?: TurbojetEnginePerf;
  /** Throttle position (0.1–1.0) */
  throttle_pos?: number;
  /** Altitude [ft] */
  alt?: number;
  /** Mach number */
  M_i?: number;
  /** Initial mass-flow guess [kg/s] */
  mdot_guess?: number;
}

export interface TurbojetSweepRequest {
  eng_param?: TurbojetEngineParam;
  eng_perf?: TurbojetEnginePerf;
  throttle_pos?: number;
  sweep_param?: string;
  alt_start?: number;
  alt_end?: number;
  mach_start?: number;
  mach_end?: number;
  throttle_start?: number;
  throttle_end?: number;
  /** Number of points in sweep */
  n_steps?: number;
  fixed_alt?: number;
  fixed_mach?: number;
  mdot_guess?: number;
}

export interface TurbopropSingleRequest {
  alt?: number;
  mach?: number;
  CPR?: number;
  TIT?: number;
  mdot_air?: number;
  A8?: number;
  prop_diameter_m?: number;
  prop_rpm?: number;
  eta_i?: number;
  eta_c?: number;
  eta_b?: number;
  dp_over_p?: number;
  eta_hpt?: number;
  eta_pt?: number;
  eta_mech_core?: number;
  eta_mech_pt?: number;
  eta_gearbox?: number;
  eta_noz?: number;
  prop_eff_max?: number;
}

export interface TurbopropSweepRequest {
  sweep_param?: string;
  n_steps?: number;
  alt_fixed?: number;
  mach_fixed?: number;
  cpr_fixed?: number;
  tit_fixed?: number;
}

export interface ValidationError {
  loc: any[];
  msg: string;
  type: string;
}
