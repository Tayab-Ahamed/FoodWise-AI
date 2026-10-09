import { useEffect, useState, useRef } from "react";
import { ArrowRight, CheckCircle2, ClipboardList } from "lucide-react";
import { api } from "../api";
import type { MealRecord, Plan, Run, Validation, Health } from "../types";
import { Badge, Card, kg, Label, titleCase } from "../components/Common";

const newRecord = (): MealRecord => ({
  record_id: `ACT-${crypto.randomUUID().slice(0, 8)}`,
  date: "2026-10-09",
  meal: "lunch",
  item: "Rice",
  attendance: 160,
  special_event: "none",
  prepared_kg: 0,
  consumed_kg: 0,
  untouched_surplus_kg: 0,
  plate_waste_kg: 0,
  cost_per_kg: 45,
  source: "user_provided_unverified",
});
export default function RecordPage({
  initialPlanId,
  run,
  busy,
  refresh,
  onSaved,
  onRecovery,
}: {
  run: Run;
  busy: boolean;
  refresh: number;
  onSaved: () => void;
  initialPlanId: string;
  onRecovery: (recordId: string) => void;
}) {
  const [plans, setPlans] = useState<Plan[]>([]),
    [planId, setPlanId] = useState(""),
    [record, setRecord] = useState<MealRecord>(newRecord),
    [validation, setValidation] = useState<Validation | null>(null),
    [validationError, setValidationError] = useState(""),
    [saved, setSaved] = useState(false);
  const [practice, setPractice] = useState(false);
  useEffect(() => {
    api<Health>("/health")
      .then((h) => setPractice(h.practice_workspace))
      .catch(() => setPractice(false));
  }, []);
  useEffect(() => {
    void run(async () =>
      setPlans(
        (await api<Plan[]>("/plans")).filter(
          (p) => !p.reuse_id || p.reuse_state === "approved",
        ),
      ),
    );
  }, [refresh]);
  useEffect(() => {
    setValidation(null);
    setValidationError("");
    let active = true;
    const t = setTimeout(
      () =>
        api<Validation>("/actuals/validate", { records: [record] })
          .then((result) => {
            if (active) setValidation(result);
          })
          .catch((e) => {
            if (active) setValidationError((e as Error).message);
          }),
      250,
    );
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, [record]);
  const change = (fields: Partial<MealRecord>) => {
    setRecord({ ...record, ...fields });
    setSaved(false);
  };
  const selectPlan = (id: string) => {
    setPlanId(id);
    const p = plans.find((p) => p.id === id);
    if (p) {
      const item = Object.keys(p.quantities)[0];
      setRecord({
        ...newRecord(),
        date: p.assumptions.date,
        meal: p.assumptions.meal,
        special_event: p.assumptions.special_event,
        attendance: p.assumptions.expected_attendance,
        item,
        prepared_kg: p.quantities[item],
        source: p.source ?? "user_provided_unverified",
      });
      setSaved(false);
    }
  };
  const linkedInitialPlan = useRef(false);
  useEffect(() => {
    if (
      !linkedInitialPlan.current &&
      initialPlanId &&
      plans.some((p) => p.id === initialPlanId)
    ) {
      linkedInitialPlan.current = true;
      selectPlan(initialPlanId);
    }
  }, [initialPlanId, plans]);
  const fixture = async () => {
    const r = await run(() => api<MealRecord>("/demo/accounting"));
    if (r) {
      setRecord(r);
      setPlanId("");
      setSaved(false);
    }
  };
  const save = async () => {
    const result = await run(
      () => api("/actuals", { plan_id: planId || null, records: [record] }),
      "Actual meal saved. Dataset version advanced; future forecasts will incorporate it.",
    );
    if (result) {
      setSaved(true);
      onSaved();
    }
  };
  const plan = plans.find((p) => p.id === planId);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">03 / RECORD WHAT HAPPENED</p>
          <h1>
            Every kilogram.
            <br />
            <em>Accounted for.</em>
          </h1>
          <p className="muted">
            Separate consumed food, untouched surplus, and plate waste.
          </p>
        </div>
        {practice && (
          <button
            className="button secondary"
            disabled={busy}
            onClick={fixture}
          >
            <ClipboardList size={17} /> Load 100 kg accounting fixture
          </button>
        )}
      </div>
      <div className="dashboard-grid">
        <Card>
          <div className="plan-stage">
            <span>1</span>
            <b>Tell the story of this service</b>
          </div>
          <div className="section-heading">
            <h2>Actual meal log</h2>
            <Badge tone="gray">Cooked-food mass</Badge>
          </div>
          <Label name="Link an approved preparation plan">
            <select value={planId} onChange={(e) => selectPlan(e.target.value)}>
              <option value="">Unplanned / separate accounting fixture</option>
              {plans.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.assumptions.date} · {p.approved_by} · {p.id}
                </option>
              ))}
            </select>
          </Label>
          <div className="form-grid two">
            <Label name="Record ID">
              <input
                value={record.record_id}
                onChange={(e) => change({ record_id: e.target.value })}
              />
            </Label>
            <Label name="Meal date">
              <input
                type="date"
                value={record.date}
                disabled={!!plan}
                onChange={(e) => change({ date: e.target.value })}
              />
            </Label>
            <Label name="Meal">
              <select
                value={record.meal}
                disabled={!!plan}
                onChange={(e) => change({ meal: e.target.value })}
              >
                {["breakfast", "lunch", "dinner"].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </Label>
            <Label name="Dish / cooked item">
              {plan ? (
                <select
                  value={record.item}
                  onChange={(e) =>
                    change({
                      item: e.target.value,
                      prepared_kg: plan.quantities[e.target.value],
                    })
                  }
                >
                  {Object.keys(plan.quantities).map((i) => (
                    <option key={i}>{i}</option>
                  ))}
                </select>
              ) : (
                <input
                  value={record.item}
                  onChange={(e) => change({ item: e.target.value })}
                />
              )}
            </Label>
            <Label name="Actual diners">
              <input
                type="number"
                min="1"
                value={record.attendance}
                onChange={(e) => change({ attendance: Number(e.target.value) })}
              />
            </Label>
            <Label name="Event">
              <select
                value={record.special_event}
                disabled={!!plan}
                onChange={(e) => change({ special_event: e.target.value })}
              >
                {["none", "exam", "festival"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </Label>
          </div>
          {plan?.reuse_id && (
            <p className="notice">
              Approved reuse plan: {kg(plan.fresh_quantities?.[record.item])}{" "}
              fresh + {kg(plan.reuse_quantities?.[record.item])} reused.
              Prepared kg below means total food available for dinner. Keep its{" "}
              {plan.source} source label. Actual fresh kg is calculated by the
              backend on save.
            </p>
          )}
          <div className="plan-stage mt-6">
            <span>2</span>
            <b>Weigh each food stream</b>
          </div>
          <div className="mass-inputs">
            {(
              [
                "prepared_kg",
                "consumed_kg",
                "untouched_surplus_kg",
                "plate_waste_kg",
              ] as const
            ).map((field) => (
              <Label key={field} name={titleCase(field)}>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={record[field]}
                  onChange={(e) => change({ [field]: Number(e.target.value) })}
                />
              </Label>
            ))}
          </div>
          <div className="form-grid two">
            <Label name="Estimated cost / cooked kg (₹)">
              <input
                type="number"
                min="0"
                step="0.1"
                value={record.cost_per_kg}
                onChange={(e) =>
                  change({ cost_per_kg: Number(e.target.value) })
                }
              />
            </Label>
            <Label name="Record source">
              <select
                value={record.source}
                onChange={(e) => change({ source: e.target.value })}
              >
                {["user_provided_unverified", "synthetic", "measured"].map(
                  (s) => (
                    <option value={s} key={s}>
                      {titleCase(s)}
                    </option>
                  ),
                )}
              </select>
            </Label>
          </div>
          <p className="small muted">
            Use measured cooked kg. Count-based dishes need measured piece
            weight; raw ingredient kg is separate. “Measured” is a staff-entered
            source label, not independent verification.
          </p>
          <Label
            name="Was a dish shortage reported?"
            hint="Running out can hide unmet demand in served-food records."
          >
            <select
              value={
                record.service_shortage_reported == null
                  ? "unknown"
                  : String(record.service_shortage_reported)
              }
              onChange={(e) =>
                change({
                  service_shortage_reported:
                    e.target.value === "unknown"
                      ? null
                      : e.target.value === "true",
                })
              }
            >
              <option value="unknown">Unknown / not logged</option>
              <option value="false">Staff reported no shortage</option>
              <option value="true">Yes · confirmed service shortage</option>
            </select>
          </Label>
          <button
            className="button mt-5"
            disabled={busy || !validation || saved}
            onClick={save}
          >
            Save actual meal <ArrowRight size={16} />
          </button>
          {saved && (
            <p className="success">
              <CheckCircle2 size={18} /> Saved · {record.record_id}
            </p>
          )}
          {saved && (
            <button
              className="link"
              onClick={() => onRecovery(record.record_id)}
            >
              Review food recovery <ArrowRight size={16} />
            </button>
          )}
        </Card>
        <div className="space-y-6">
          <Card className="accounting-card">
            <p className="eyebrow">SERVER-VALIDATED ACCOUNTING</p>
            <h2>Balance before saving</h2>
            <p className="accounting-equation">
              Prepared = consumed
              <br />+ untouched + plate waste
            </p>
            {validation ? (
              <>
                <Badge>Within 0.02 kg tolerance</Badge>
                <div className="balance-value">
                  <span>Food served</span>
                  <strong>{kg(validation.rows[0].served_kg)}</strong>
                  <small>Consumed + plate waste</small>
                </div>
                <p className="muted">
                  Balance residual:{" "}
                  {kg(validation.rows[0].balance_difference_kg)}
                </p>
              </>
            ) : (
              <p className="notice" role="status">
                {validationError || "Checking mass balance on the backend…"}
              </p>
            )}
          </Card>
          <Card>
            <h2>Two different waste streams</h2>
            <div className="inventory-row">
              <b>Untouched surplus</b>
              <p>
                Never served. Documented handling and safety review required,
                followed by manager approval.
              </p>
            </div>
            <div className="inventory-row">
              <Badge tone="red">Plate waste: no human redistribution</Badge>
              <p>
                Already served. The backend blocks human redistribution
                regardless of completed checks.
              </p>
            </div>
            {practice && (
              <p className="muted small mt-4">
                The 100 / 82 / 10 / 8 fixture gives 90 kg served. It is an
                accounting example; it is kept separate from forecast history
                until explicitly logged as an actual.
              </p>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
