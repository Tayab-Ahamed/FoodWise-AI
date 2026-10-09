export interface MealRecord {
  record_id: string;
  date: string;
  meal: string;
  item: string;
  attendance: number;
  special_event: string;
  prepared_kg: number;
  consumed_kg: number;
  untouched_surplus_kg: number;
  plate_waste_kg: number;
  cost_per_kg: number;
  source: string;
  service_shortage_reported?: boolean | null;
  served_kg?: number;
  weekday?: string;
  display_qty?: number | null;
  display_unit?: string | null;
  piece_weight_kg?: number | null;
}
export interface Totals {
  prepared_kg: number;
  consumed_kg: number;
  served_kg: number;
  untouched_surplus_kg: number;
  plate_waste_kg: number;
  waste_kg: number;
  estimated_waste_cost_inr: number;
  balance_difference_kg: number;
  untouched_pct: number;
}
export interface Aggregate extends Totals {
  date?: string;
  item?: string;
  weekday?: string;
}
export interface Overview {
  totals: Totals;
  daily: Aggregate[];
  weekday: Aggregate[];
  items: Aggregate[];
  record_count: number;
  meal_services: number;
  diners: number;
  sources: string[];
  date_from: string | null;
  date_to: string | null;
  dataset_version: number;
  dataset_source: string;
  recorded_actual_count: number;
}
export interface Finding {
  id: string;
  title: string;
  observed_metrics: Record<string, number>;
  evidence_record_ids: string[];
  sample_count: number;
  caveats: string;
  suggested_action: string;
}
export interface Inventory {
  as_of: string;
  near_days: number;
  units: string;
  items: {
    id: string;
    ingredient: string;
    quantity_kg: number;
    expiry_date: string;
    storage_verified: boolean | null;
    storage_status: string;
    status: string;
    warning: string;
    allergens: string[];
  }[];
}
export interface ForecastInput {
  date: string;
  meal: string;
  expected_attendance: number;
  special_event: string;
  buffer_pct: number;
  items: string[];
}
export interface Backtest {
  mae_kg: number | null;
  baseline_mae_kg: number | null;
  evaluation_count: number;
  attendance_known: boolean;
  method: string;
  range_diagnostics?: {
    coverage_pct: number | null;
    mean_width_kg: number | null;
    label: string;
  };
  benchmark?: Benchmark;
  evaluations: {
    record_id: string;
    date: string;
    actual_served_kg: number;
    prediction_kg: number;
    baseline_kg: number;
    training_ids: string[];
  }[];
}
export interface ForecastItem {
  item: string;
  status: string;
  sample_count: number;
  history_ids: string[];
  method: string;
  fallback_reason: string | null;
  backtest: Backtest;
  demand_kg?: number;
  recommended_kg?: number;
  range_low_kg?: number;
  range_high_kg?: number;
  range_label?: string;
  demand_samples_kg?: number[];
  baseline_prepared_kg?: number;
  simulator_max_kg?: number;
  cost_per_kg?: number;
  data_quality?: DataQuality;
}
export interface Forecast {
  id: string;
  dataset_version: number;
  assumptions: ForecastInput;
  created_at: string;
  items: ForecastItem[];
}
export interface Simulation {
  quantity_kg: number;
  expected_surplus_kg: number;
  expected_shortage_kg: number;
  shortage_frequency: number;
  point_surplus_kg: number;
  point_shortage_kg: number;
  baseline_prepared_kg: number;
  baseline: {
    expected_surplus_kg: number;
    expected_shortage_kg: number;
    shortage_frequency: number;
  };
  prevented_untouched_surplus_kg: number;
  potential_cost_difference_inr: number;
  sample_count: number;
  label: string;
}
export interface Plan {
  reuse_id?: string;
  reuse_state?: string;
  source?: string;
  fresh_quantities?: Record<string, number>;
  reuse_quantities?: Record<string, number>;
  id: string;
  forecast_id: string;
  quantities: Record<string, number>;
  approved_by: string;
  approved_at: string;
  dataset_version: number;
  assumptions: ForecastInput;
  manual_items: string[];
  decision_ids?: Record<string, string>;
  decisions?: Record<string, Optimization>;
}
export interface Validation {
  valid: boolean;
  rows: {
    record_id: string;
    served_kg: number;
    balance_difference_kg: number;
  }[];
}
export interface Preview {
  valid: boolean;
  errors: { row?: number; field?: string; message: string }[];
  preview_token?: string;
  sha256?: string;
  row_count: number;
  preview: MealRecord[];
  source: string;
}
export interface Batch {
  id: string;
  record_id: string;
  origin: string;
  quantity_kg: number;
  checks: Record<string, boolean | null>;
  reviewer: string | null;
  reviewed_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  state: string;
  reason: string;
  remaining_kg: number;
  handed_off_kg: number;
  handoffs: Handoff[];
}
export interface Handoff {
  id: string;
  batch_id: string;
  quantity_kg: number;
  route: string;
  partner_id: string;
  simulated: boolean;
  recorded_at: string;
  idempotency_key: string;
  duplicate?: boolean;
}
export interface Audit {
  id: string;
  action: string;
  entity_id: string;
  timestamp: string;
  details: Record<string, unknown>;
}
export interface EvidenceItem {
  item: string;
  history_ids: string[];
  sample_count: number;
  fallback_reason: string | null;
  demand_kg?: number;
  quantity_kg?: number;
  range_low_kg?: number;
  range_high_kg?: number;
  simulation?: Simulation;
  backtest: Backtest;
}
export interface Report {
  explanation: string;
  explanation_mode: string;
  generated_at: string;
  evidence: {
    forecast_id: string;
    dataset_version: number;
    assumptions: ForecastInput;
    plan_id: string | null;
    approved_by: string | null;
    items: EvidenceItem[];
  };
}
export interface Impact {
  recorded_actuals: Overview;
  simulated_dispositions: Record<string, number>;
  recorded_dispositions: Record<string, number>;
  caveat: string;
  plans: {
    plan: Plan;
    projected_untouched_difference_kg: number;
    projected_cost_difference_inr: number;
    evidence: Report["evidence"];
    actual_comparison: {
      record_id: string;
      item: string;
      planned_kg: number;
      actual_prepared_kg: number;
      actual_served_kg: number;
      served_forecast_error_kg: number | null;
    }[];
  }[];
}
export interface Health {
  synthetic_demo: boolean;
  practice_workspace: boolean;
  dataset_source: string;
  status: string;
  explanation_mode: string;
  dataset_version: number;
  demo_date: string;
}
export interface Catalog {
  items: string[];
  meal_items: Record<string, string[]>;
}
export type Run = <T>(
  work: () => Promise<T>,
  success?: string,
) => Promise<T | undefined>;

export interface DataQuality {
  sources: string[];
  confirmed_shortage_ids: string[];
  shortage_unknown_count: number;
  zero_surplus_ids: string[];
  caveat: string;
}
export interface Benchmark {
  models: {
    key: string;
    label: string;
    status: string;
    mae_kg: number | null;
    rmse_kg: number | null;
    bias_kg: number | null;
    wape_pct: number | null;
    evaluation_count: number;
  }[];
  evaluations: {
    record_id: string;
    date: string;
    actual_served_kg: number;
    predictions: Record<string, number>;
    training_ids: Record<string, string[]>;
  }[];
  default_model: string;
  method: string;
  caveat: string;
}
export interface PolicyPoint {
  quantity_kg: number;
  expected_surplus_kg: number;
  expected_shortage_kg: number;
  shortage_frequency: number;
  scenario_loss_inr: number;
  service_constraint_met: boolean;
}
export interface Optimization {
  id: string;
  status: string;
  critical_ratio: number;
  unconstrained_quantity_kg: number;
  selected: PolicyPoint | null;
  capacity_best_effort: PolicyPoint;
  frontier: PolicyPoint[];
  frequency_resolution: number;
  history_ids: string[];
  data_quality: DataQuality;
  caveat: string;
  assumptions: {
    forecast_id: string;
    item: string;
    surplus_cost_per_kg: number;
    shortage_cost_per_kg: number;
    capacity_kg: number;
    max_shortage_frequency: number;
  };
}
export interface TrialInput {
  item: string;
  meal: string;
  baseline_start: string;
  baseline_end: string;
  trial_start: string;
  trial_end: string;
  record_scope: string;
  source_filter: string;
  mode: string;
  intervention: string;
  approved_by: string;
  notes: string;
}
export interface TrialPhase {
  services: number;
  diners: number;
  totals: Record<string, number>;
  per_diner_g: Record<string, number | null>;
  evidence_ids: string[];
  sources: string[];
  event_counts: Record<string, number>;
  shortage_reported_count: number;
  shortage_unknown_count: number;
}
export interface TrialEvaluation {
  trial: TrialInput & { id: string; approved_at: string };
  baseline: TrialPhase;
  comparison: TrialPhase;
  status: string;
  minimum_services_per_phase: number;
  change_per_diner_g: Record<string, number> | null;
  excluded_duplicate_ids: string[];
  dataset_version: number;
  label: string;
  caveat: string;
}
