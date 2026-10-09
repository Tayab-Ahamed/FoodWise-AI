from datetime import date, datetime
from typing import Literal
import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Record(StrictModel):
    record_id: str = Field(min_length=1, max_length=100)
    date: date
    meal: Literal["breakfast", "lunch", "dinner"]
    item: str = Field(min_length=1, max_length=100)
    attendance: int = Field(gt=0, le=100000, strict=True)
    special_event: Literal["none", "exam", "festival"] = "none"
    prepared_kg: float = Field(ge=0, le=1000000)
    consumed_kg: float = Field(ge=0, le=1000000)
    untouched_surplus_kg: float = Field(ge=0, le=1000000)
    plate_waste_kg: float = Field(ge=0, le=1000000)
    cost_per_kg: float = Field(ge=0, le=1000000)
    source: Literal["synthetic", "measured", "user_provided_unverified"] = "user_provided_unverified"
    service_shortage_reported: bool | None = None
    display_qty: float | None = Field(default=None, ge=0)
    display_unit: Literal["pieces"] | None = None
    piece_weight_kg: float | None = Field(default=None, gt=0)

    @field_validator("date", mode="before")
    @classmethod
    def iso_date(cls, value):
        if isinstance(value, str):
            if len(value) != 10 or date.fromisoformat(value).isoformat() != value:
                raise ValueError("Use an ISO date YYYY-MM-DD")
        return value

    @field_validator("record_id", "item")
    @classmethod
    def clean_text(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def balanced(self):
        difference = self.prepared_kg - self.consumed_kg - self.untouched_surplus_kg - self.plate_waste_kg
        if abs(difference) > 0.020000001:
            raise ValueError(f"Mass balance differs by {difference:.3f} kg; tolerance is 0.02 kg")
        if any(v is not None for v in [self.display_qty, self.display_unit, self.piece_weight_kg]):
            if any(v is None for v in [self.display_qty, self.display_unit, self.piece_weight_kg]):
                raise ValueError("Pieces require display_qty, display_unit and measured piece_weight_kg")
            if abs(self.display_qty * self.piece_weight_kg - self.prepared_kg) > 0.02:
                raise ValueError("Measured piece conversion must match prepared cooked kg")
        return self


class ForecastRequest(StrictModel):
    date: date
    meal: Literal["breakfast", "lunch", "dinner"]
    expected_attendance: int = Field(gt=0, le=100000, strict=True)
    special_event: Literal["none", "exam", "festival"] = "none"
    buffer_pct: float = Field(default=5, ge=0, le=20)
    items: list[str] = Field(min_length=1, max_length=30)


class SimulationRequest(StrictModel):
    forecast_id: str
    item: str
    quantity_kg: float = Field(ge=0, le=1000000)
    baseline_prepared_kg: float = Field(ge=0, le=1000000)


class PlanRequest(StrictModel):
    forecast_id: str
    quantities: dict[str, float]
    approved_by: str = Field(min_length=1, max_length=100)
    decision_ids: dict[str, str] = Field(default_factory=dict)
    coach_id: str | None = None

    @field_validator("quantities")
    @classmethod
    def valid_quantities(cls, values):
        if not values or any(not math.isfinite(v) or v < 0 or v > 1000000 for v in values.values()):
            raise ValueError("Quantities must be finite cooked kg between 0 and 1000000")
        return values

    @field_validator("approved_by")
    @classmethod
    def manager(cls, value):
        if not value.strip():
            raise ValueError("Manager name is required")
        return value.strip()


class ActualRequest(StrictModel):
    plan_id: str | None = None
    records: list[Record] = Field(min_length=1, max_length=100)


class CommitRequest(StrictModel):
    preview_token: str
    mode: Literal["replace"]


class BatchRequest(StrictModel):
    record_id: str
    origin: Literal["untouched_surplus", "plate_waste", "unknown"]
    quantity_kg: float = Field(gt=0, le=1000000)


CHECKS = ["handling_log_complete", "time_temperature_review_passed", "storage_verified",
          "contamination_check_passed", "label_allergen_info_present"]


class ReviewRequest(StrictModel):
    handling_log_complete: bool | None = None
    time_temperature_review_passed: bool | None = None
    storage_verified: bool | None = None
    contamination_check_passed: bool | None = None
    label_allergen_info_present: bool | None = None
    reviewer: str = Field(min_length=1, max_length=100)

    @field_validator("reviewer")
    @classmethod
    def reviewer_name(cls, value):
        if not value.strip():
            raise ValueError("Reviewer name is required")
        return value.strip()


class ApproveRequest(StrictModel):
    approved_by: str = Field(min_length=1, max_length=100)

    @field_validator("approved_by")
    @classmethod
    def manager_name(cls, value):
        if not value.strip():
            raise ValueError("Manager name is required")
        return value.strip()


class BiogasAssumptions(StrictModel):
    gas_m3_per_kg_wet: float = Field(default=0.1, gt=0, le=1)
    methane_fraction: float = Field(default=0.6, gt=0, le=1)
    methane_kwh_per_m3: float = Field(default=9.94, gt=0, le=12)
    electricity_efficiency: float = Field(default=0.35, ge=0, le=1)
    heat_efficiency: float = Field(default=0.45, ge=0, le=1)

    @model_validator(mode="after")
    def energy_conservation(self):
        if self.electricity_efficiency + self.heat_efficiency > 1 + 1e-9:
            raise ValueError("Electricity and recovered heat efficiencies cannot sum above 1")
        return self


class HandoffRequest(StrictModel):
    route: Literal["human_redistribution", "compost", "biogas"]
    partner_id: str
    quantity_kg: float = Field(gt=0, le=1000000)
    idempotency_key: str = Field(min_length=1, max_length=100)
    segregation_confirmed: bool | None = None
    biogas_assumptions: BiogasAssumptions | None = None


class TemperatureReading(StrictModel):
    at: datetime
    celsius: float = Field(ge=-30, le=150)


class ReuseEvidence(StrictModel):
    procedure_reference: str = Field(min_length=1, max_length=200)
    holding_mode: Literal["hot_held", "chilled", "ambient", "unknown"] = "unknown"
    holding_started_at: datetime | None = None
    dinner_service_at: datetime | None = None
    temperatures: list[TemperatureReading] = Field(default_factory=list, max_length=50)
    continuous_monitoring_verified: bool | None = None
    procedure_allows_this_food: bool | None = None
    protected_separate_container: bool | None = None
    reviewer: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=1000)

    @field_validator("procedure_reference", "reviewer")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("A nonblank procedure reference and staff name are required")
        return value.strip()


class ReuseProposal(StrictModel):
    batch_id: str
    dinner_forecast_id: str
    quantity_kg: float = Field(gt=0, le=1000000)
    manual_dinner_total_kg: float | None = Field(default=None, gt=0, le=1000000)
    compatibility_confirmed: bool | None = None


class ReuseDecision(ApproveRequest):
    decision: Literal["approve", "reject"]
    qualified_kitchen_manager: bool | None = None
    procedure_review_confirmed: bool | None = None
    notes: str = Field(default="", max_length=1000)


class BiogasEstimateRequest(StrictModel):
    batch_id: str
    partner_id: str
    quantity_kg: float = Field(gt=0, le=1000000)
    segregation_confirmed: bool | None = None
    assumptions: BiogasAssumptions = Field(default_factory=BiogasAssumptions)


class InventoryReview(StrictModel):
    label_kind: Literal["use_by", "best_before", "unknown"] = "unknown"
    storage_verified: bool | None = None
    condition_passed: bool | None = None
    reviewed_by: str = Field(min_length=1, max_length=100)
    procedure_reference: str = Field(min_length=1, max_length=200)
    review_date: date

    @field_validator("reviewed_by", "procedure_reference")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Staff name and applicable inventory procedure are required")
        return value.strip()


class ReportRequest(StrictModel):
    forecast_id: str
    plan_id: str | None = None


class ResetRequest(StrictModel):
    confirm: Literal["RESET SYNTHETIC DEMO"]


class OptimizationRequest(StrictModel):
    forecast_id: str
    item: str
    surplus_cost_per_kg: float = Field(gt=0, le=1000000)
    shortage_cost_per_kg: float = Field(gt=0, le=1000000)
    max_shortage_frequency: float = Field(default=0.2, ge=0, le=1)
    capacity_kg: float = Field(ge=0, le=1000000)


class TrialRequest(StrictModel):
    item: str = Field(min_length=1, max_length=100)
    meal: Literal["breakfast", "lunch", "dinner"]
    baseline_start: date
    baseline_end: date
    trial_start: date
    trial_end: date
    record_scope: Literal["actual", "history"] = "actual"
    source_filter: Literal["all", "measured", "synthetic", "user_provided_unverified"] = "all"
    mode: Literal["planned_trial", "retrospective_comparison"] = "planned_trial"
    intervention: Literal["smaller_first_serving_optional_seconds", "information_only"] = "smaller_first_serving_optional_seconds"
    approved_by: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=1000)

    @field_validator("approved_by", "item")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("A nonblank value is required")
        return value.strip()

    @model_validator(mode="after")
    def valid_windows(self):
        if not self.baseline_start <= self.baseline_end < self.trial_start <= self.trial_end:
            raise ValueError("Baseline must end before the trial starts; each window needs ordered dates")
        return self
