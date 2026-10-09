import { useEffect, useState } from "react";
import { ArrowRight, Flame, UtensilsCrossed } from "lucide-react";
import { api } from "../api";
import type { Batch, Forecast, MealRecord, Run } from "../types";
import { Badge, Card, Empty, kg, Label, num, Stat, titleCase } from "./Common";

type Props = { run: Run; busy: boolean; refresh: number; onSaved: () => void };
interface Holding {
  procedure_reference: string;
  holding_mode: string;
  holding_started_at: string | null;
  dinner_service_at: string | null;
  temperatures: { at: string; celsius: number }[];
  continuous_monitoring_verified: boolean | null;
  procedure_allows_this_food: boolean | null;
  protected_separate_container: boolean | null;
  reviewer: string;
  notes: string;
}
export interface ReusePlan {
  id: string;
  batch_id: string;
  item: string;
  source: string;
  state: string;
  quantity_kg: number;
  dinner_total_kg: number;
  fresh_preparation_kg: number;
  demand_basis: string;
  label: string;
  plan_id?: string;
  outcome_record_id?: string;
  recorded_fresh_kg?: number;
  lunch_record_id: string;
}
interface Assumptions {
  gas_m3_per_kg_wet: number;
  methane_fraction: number;
  methane_kwh_per_m3: number;
  electricity_efficiency: number;
  heat_efficiency: number;
}
interface Potential {
  wet_food_kg: number;
  biogas_m3: number;
  electricity_kwh: number;
  useful_heat_kwh: number;
  useful_energy_kwh: number;
  label: string;
  caveat: string;
  assumptions: Assumptions;
}
interface CircularImpact {
  reuse_plans: ReusePlan[];
  staff_recorded_reuse_kg: number;
  reserved_reuse_kg: number;
  simulated_biogas_kg: number;
  potential_useful_energy_kwh: number;
  potential_covered_kg: number;
  caveat: string;
  gross_actual_service_food_kg: number;
  newly_prepared_actual_food_kg: number;
  biogas_receipts: {
    id: string;
    quantity_kg: number;
    processor: string;
    origin: string;
    outcome: string;
    segregation_confirmed: boolean | null;
    potential?: Potential;
  }[];
}
const emptyHolding: Holding = {
  procedure_reference: "",
  holding_mode: "unknown",
  holding_started_at: null,
  dinner_service_at: null,
  temperatures: [],
  continuous_monitoring_verified: null,
  procedure_allows_this_food: null,
  protected_separate_container: null,
  reviewer: "",
  notes: "",
};
const savedHolding = (batch: Batch): Holding => {
  const saved = (batch as Batch & { reuse_evidence?: Holding }).reuse_evidence;
  return saved
    ? (Object.fromEntries(
        Object.keys(emptyHolding).map((k) => [k, saved[k as keyof Holding]]),
      ) as unknown as Holding)
    : emptyHolding;
};
const boolValue = (value: string) =>
  value === "unknown" ? null : value === "true";
const holdingChecks = {
  continuous_monitoring_verified: "Continuous monitoring reviewed",
  procedure_allows_this_food: "Kitchen procedure permits this food",
  protected_separate_container: "Protected, separate container",
} as const;

export function DinnerReuse({
  batch,
  record,
  run,
  busy,
  refresh,
  onSaved,
}: Props & { batch: Batch; record?: MealRecord }) {
  const [holding, setHolding] = useState<Holding>(() => savedHolding(batch)),
    [logs, setLogs] = useState(() =>
      savedHolding(batch)
        .temperatures.map((t) => `${t.at}, ${t.celsius}`)
        .join("\n"),
    );
  const [blockers, setBlockers] = useState<string[]>([]),
    [plans, setPlans] = useState<ReusePlan[]>([]);
  const [unallocated, setUnallocated] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(batch.remaining_kg),
    [total, setTotal] = useState("");
  const [attendance, setAttendance] = useState(record?.attendance ?? 1),
    [compatible, setCompatible] = useState(false);
  const [manager, setManager] = useState(""),
    [qualified, setQualified] = useState(false),
    [procedure, setProcedure] = useState(false);
  const [forecast, setForecast] = useState<Forecast | null>(null),
    [changed, setChanged] = useState(false);
  useEffect(() => {
    let active = true;
    void run(async () => {
      const [options, p] = await Promise.all([
        api<{
          batches: (Batch & { reuse_blockers: string[] })[];
          lunch_actuals: {
            record_id: string;
            unallocated_untouched_kg: number;
          }[];
        }>("/reuse/options"),
        api<ReusePlan[]>("/reuse/plans"),
      ]);
      if (active) {
        setBlockers(
          options.batches.find((b) => b.id === batch.id)?.reuse_blockers ?? [],
        );
        setPlans(p.filter((p) => p.batch_id === batch.id));
        setUnallocated(
          options.lunch_actuals.find((r) => r.record_id === batch.record_id)
            ?.unallocated_untouched_kg ?? null,
        );
      }
    });
    return () => {
      active = false;
    };
  }, [batch.id, refresh]);
  const edit = (patch: Partial<Holding>) => {
    setHolding((h) => ({ ...h, ...patch }));
    setChanged(true);
  };
  const loadExample = async () => {
    const e = await run(() =>
      api<Holding>(`/reuse/batches/${batch.id}/synthetic-example`),
    );
    if (e) {
      setHolding(e);
      setLogs(e.temperatures.map((t) => `${t.at}, ${t.celsius}`).join("\n"));
      setChanged(true);
    }
  };
  const save = async () => {
    const result = await run(async () => {
      const temperatures = logs.trim()
        ? logs
            .trim()
            .split("\n")
            .map((line) => {
              const [at, c, ...extra] = line.split(",").map((s) => s.trim());
              if (!at || !c || extra.length || !Number.isFinite(Number(c)))
                throw new Error("Use one ISO timestamp, temperature per line.");
              return { at, celsius: Number(c) };
            })
        : [];
      return api<Batch & { reuse_blockers: string[] }>(
        `/reuse/batches/${batch.id}/evidence`,
        { ...holding, temperatures },
        "PATCH",
      );
    }, "Holding evidence saved. Any unused reuse approval was invalidated.");
    if (result) {
      setChanged(false);
      setBlockers(result.reuse_blockers);
      onSaved();
    }
  };
  const demand = async () => {
    if (!record) return;
    const f = await run(() =>
      api<Forecast>("/forecast", {
        date: record.date,
        meal: "dinner",
        items: [record.item],
        expected_attendance: attendance,
        special_event: "none",
        buffer_pct: 5,
      }),
    );
    if (f) setForecast(f);
  };
  const reserve = async () => {
    if (!forecast) return;
    const p = await run(
      () =>
        api<ReusePlan>("/reuse/proposals", {
          batch_id: batch.id,
          dinner_forecast_id: forecast.id,
          quantity_kg: quantity,
          manual_dinner_total_kg:
            forecast.items[0].status === "ready" ? null : Number(total),
          compatibility_confirmed: compatible,
        }),
      "Dinner proposal reserved. Qualified manager approval is still required.",
    );
    if (p) onSaved();
  };
  const decide = async (p: ReusePlan, decision: string) => {
    const result = await run(
      () =>
        api(`/reuse/proposals/${p.id}/decision`, {
          decision,
          approved_by: manager,
          qualified_kitchen_manager: qualified,
          procedure_review_confirmed: procedure,
        }),
      `Dinner proposal ${decision === "approve" ? "approved" : "rejected"}.`,
    );
    if (result) onSaved();
  };
  return (
    <Card className="circular-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">KEEP GOOD FOOD IN THE KITCHEN</p>
          <h2>Lunch → dinner</h2>
        </div>
        <UtensilsCrossed aria-hidden="true" />
      </div>
      <Badge tone="amber">Reviewed reuse · never automatic</Badge>
      <p className="muted small mt-3">
        Select an untouched lunch actual in the review queue. Complete its
        documented review and manager batch approval above. Only the identical
        cooked dish is supported; all quantities remain cooked kg.
      </p>
      <p>
        <b>{record?.item ?? "Selected batch"}</b> · {kg(batch.remaining_kg)}{" "}
        unreserved · {record?.source ?? "source unknown"}
      </p>
      {unallocated !== null && (
        <p className="small muted">
          Outside this batch, {kg(unallocated)} untouched lunch food remains
          unallocated for new batches. Existing batch reservations and handoffs
          cannot be reused twice.
        </p>
      )}
      {batch.origin !== "untouched_surplus" ? (
        <p className="permanent-block">
          Plate waste and unknown-origin food cannot enter dinner reuse.
        </p>
      ) : (
        <>
          <details className="research-drawer" open>
            <summary>1. Record holding evidence</summary>
            {record?.source === "synthetic" && (
              <button
                className="button secondary mt-4"
                disabled={busy}
                onClick={loadExample}
              >
                Load generated holding example
              </button>
            )}
            <p className="small muted mt-3">
              Practice policy gate: same day, hot-held at 63–100 °C, at most 6
              hours, log gaps at most 60 minutes, start/end coverage. Other
              handling modes are blocked. A qualified manager must still review
              the applicable kitchen procedure.
            </p>
            <div className="form-grid two">
              <Label name="Kitchen procedure reference">
                <input
                  value={holding.procedure_reference}
                  onChange={(e) =>
                    edit({ procedure_reference: e.target.value })
                  }
                />
              </Label>
              <Label name="Holding reviewer">
                <input
                  value={holding.reviewer}
                  onChange={(e) => edit({ reviewer: e.target.value })}
                />
              </Label>
              <Label name="Holding condition">
                <select
                  value={holding.holding_mode}
                  onChange={(e) => edit({ holding_mode: e.target.value })}
                >
                  <option value="unknown">Unknown · blocked</option>
                  <option value="hot_held">Hot held · documented log</option>
                  <option value="chilled">Chilled · unsupported</option>
                  <option value="ambient">Ambient · blocked</option>
                </select>
              </Label>
              <Label name="Holding started (ISO time with timezone)">
                <input
                  placeholder="2026-10-09T13:00:00+05:30"
                  value={holding.holding_started_at ?? ""}
                  onChange={(e) =>
                    edit({ holding_started_at: e.target.value || null })
                  }
                />
              </Label>
              <Label name="Dinner service (ISO time with timezone)">
                <input
                  placeholder="2026-10-09T19:00:00+05:30"
                  value={holding.dinner_service_at ?? ""}
                  onChange={(e) =>
                    edit({ dinner_service_at: e.target.value || null })
                  }
                />
              </Label>
            </div>
            <Label name="Temperature log: ISO timestamp, °C — one per line">
              <textarea
                rows={7}
                value={logs}
                onChange={(e) => {
                  setLogs(e.target.value);
                  setChanged(true);
                }}
              />
            </Label>
            <div className="form-grid two">
              {Object.entries(holdingChecks).map(([key, label]) => (
                <Label key={key} name={label}>
                  <select
                    value={
                      holding[key as keyof typeof holdingChecks] == null
                        ? "unknown"
                        : String(holding[key as keyof typeof holdingChecks])
                    }
                    onChange={(e) => edit({ [key]: boolValue(e.target.value) })}
                  >
                    <option value="unknown">Unknown / no evidence</option>
                    <option value="true">Passed — staff attestation</option>
                    <option value="false">Failed</option>
                  </select>
                </Label>
              ))}
            </div>
            <Label name="Holding notes">
              <textarea
                rows={2}
                value={holding.notes}
                onChange={(e) => edit({ notes: e.target.value })}
              />
            </Label>
            <button
              className="button secondary"
              disabled={busy || !changed}
              onClick={save}
            >
              Save holding evidence
            </button>
          </details>
          {blockers.length > 0 && (
            <div className="notice mt-4" role="status">
              <b>Reuse currently blocked</b>
              <ul>
                {blockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="approval-divider">
            <h3>2. Build a dinner proposal</h3>
            <Label name="Expected dinner diners">
              <input
                type="number"
                min={1}
                value={attendance}
                onChange={(e) => {
                  setAttendance(Number(e.target.value));
                  setForecast(null);
                }}
              />
            </Label>
            <button
              className="button secondary"
              disabled={busy || !record}
              onClick={demand}
            >
              Check dinner demand
            </button>
            {forecast && (
              <div className="mt-4">
                <p className="notice">
                  {forecast.items[0].status === "ready"
                    ? `Historical dinner recommendation: ${kg(forecast.items[0].recommended_kg)}`
                    : "Insufficient dinner history. Enter a manual total; no projected shortage or savings can be estimated."}
                </p>
                {forecast.items[0].status !== "ready" && (
                  <Label name="Manual total dinner food (cooked kg)">
                    <input
                      type="number"
                      min={0.01}
                      step={0.01}
                      value={total}
                      onChange={(e) => setTotal(e.target.value)}
                    />
                  </Label>
                )}
                <Label name="Reserve untouched food for dinner (kg)">
                  <input
                    type="number"
                    min={0.01}
                    step={0.01}
                    value={quantity}
                    onChange={(e) => setQuantity(Number(e.target.value))}
                  />
                </Label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={compatible}
                    onChange={(e) => setCompatible(e.target.checked)}
                  />{" "}
                  Kitchen confirms the same dish, allergens and dinner
                  compatibility.
                </label>
                <button
                  className="button mt-4"
                  disabled={busy || changed || !compatible}
                  onClick={reserve}
                >
                  Reserve dinner proposal <ArrowRight size={16} />
                </button>
              </div>
            )}
          </div>
          <div className="approval-divider">
            <h3>3. Qualified manager decision</h3>
            <Label name="Reuse approving manager">
              <input
                value={manager}
                onChange={(e) => setManager(e.target.value)}
              />
            </Label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={qualified}
                onChange={(e) => setQualified(e.target.checked)}
              />{" "}
              I attest that I am the qualified kitchen manager.
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={procedure}
                onChange={(e) => setProcedure(e.target.checked)}
              />{" "}
              I reviewed this food, handling evidence and applicable kitchen
              procedure.
            </label>
            {plans.length === 0 && (
              <Empty>No dinner reservations for this batch.</Empty>
            )}
            {plans.map((p) => (
              <article className="circular-result" key={p.id}>
                <Badge
                  tone={
                    p.state === "approved" || p.state === "completed"
                      ? "green"
                      : "amber"
                  }
                >
                  {titleCase(p.state)} · {p.source}
                </Badge>
                <h3>
                  {kg(p.fresh_preparation_kg)} fresh + {kg(p.quantity_kg)}{" "}
                  reused
                </h3>
                <p>
                  {kg(p.dinner_total_kg)} total dinner food · {p.item}
                </p>
                <p className="small muted">
                  {p.demand_basis}. {p.label}
                </p>
                {p.state === "pending" && (
                  <button
                    className="button"
                    disabled={
                      busy ||
                      changed ||
                      !manager.trim() ||
                      !qualified ||
                      !procedure
                    }
                    onClick={() => decide(p, "approve")}
                  >
                    Approve revised dinner plan
                  </button>
                )}
                {["pending", "approved"].includes(p.state) && (
                  <button
                    className="button secondary"
                    disabled={busy || !manager.trim()}
                    onClick={() => decide(p, "reject")}
                  >
                    Reject & release reservation
                  </button>
                )}
                {p.state === "approved" && (
                  <p className="success">
                    Ready to log in Record meal. Select plan {p.plan_id};
                    prepared mass means fresh + reused food.
                  </p>
                )}
                {p.outcome_record_id && (
                  <p className="success">
                    Recorded outcome: {p.outcome_record_id}
                  </p>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

const assumptionNames: Record<keyof Assumptions, string> = {
  gas_m3_per_kg_wet: "Biogas yield (m³ / kg wet food)",
  methane_fraction: "Methane fraction (0–1)",
  methane_kwh_per_m3: "Methane energy (kWh / m³)",
  electricity_efficiency: "Electricity efficiency (0–1)",
  heat_efficiency: "Useful heat efficiency (0–1)",
};
export function BiogasPanel({
  batch,
  run,
  busy,
  onSaved,
  practice = true,
}: {
  batch: Batch;
  run: Run;
  busy: boolean;
  onSaved: () => void;
  practice?: boolean;
}) {
  const [assumptions, setAssumptions] = useState<Assumptions | null>(null),
    [quantity, setQuantity] = useState(batch.remaining_kg);
  const [segregated, setSegregated] = useState(false),
    [potential, setPotential] = useState<Potential | null>(null),
    [processor, setProcessor] = useState("demo-biogas");
  const [receipt, setReceipt] = useState(false),
    [key, setKey] = useState(crypto.randomUUID());
  useEffect(() => {
    let active = true;
    void run(async () => {
      const d = await api<{ assumptions: Assumptions }>("/biogas/defaults");
      if (active) setAssumptions(d.assumptions);
    });
    return () => {
      active = false;
    };
  }, []);
  const edited = () => {
    setPotential(null);
    setReceipt(false);
    setKey(crypto.randomUUID());
  };
  const estimate = async () => {
    const p = await run(() =>
      api<Potential>("/biogas/estimate", {
        batch_id: batch.id,
        partner_id: processor,
        quantity_kg: quantity,
        segregation_confirmed: segregated,
        assumptions,
      }),
    );
    if (p) setPotential(p);
  };
  const handoff = async () => {
    const r = await run(
      () =>
        api(`/recovery/batches/${batch.id}/handoff`, {
          route: "biogas",
          partner_id: processor,
          quantity_kg: quantity,
          segregation_confirmed: segregated,
          biogas_assumptions: assumptions,
          idempotency_key: key,
        }),
      "Simulated biogas handoff saved. No gas or energy generation is recorded.",
    );
    if (r) {
      setReceipt(true);
      onSaved();
    }
  };
  return (
    <Card className="circular-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">FROM WASTE TO POSSIBILITY</p>
          <h2>Biogas potential</h2>
        </div>
        <Flame aria-hidden="true" />
      </div>
      <Badge tone="amber">Theoretical estimate · simulated processor</Badge>
      <ol className="circular-flow">
        <li>{titleCase(batch.origin)}</li>
        <li>Segregate material</li>
        <li>Accepted processor</li>
        <li>Potential biogas</li>
        <li>Potential useful energy</li>
      </ol>
      <p className="small muted">
        Human redistribution of plate waste remains permanently blocked. This
        estimator does not certify disposal, contact a facility or measure
        energy.
      </p>
      <Label name="Biogas allocation (wet food kg)">
        <input
          type="number"
          min={0.01}
          step={0.01}
          value={quantity}
          onChange={(e) => {
            setQuantity(Number(e.target.value));
            edited();
          }}
        />
      </Label>
      {practice && (
        <Label name="Biogas processor acceptance">
          <select
            value={processor}
            onChange={(e) => {
              setProcessor(e.target.value);
              edited();
            }}
          >
            <option value="demo-biogas">
              Demo biogas processor · material accepted
            </option>
            <option value="demo-unconfirmed">
              Demo processor · acceptance unknown / blocked
            </option>
          </select>
        </Label>
      )}
      <label className="check-row">
        <input
          type="checkbox"
          checked={segregated}
          onChange={(e) => {
            setSegregated(e.target.checked);
            edited();
          }}
        />{" "}
        Staff confirms segregated material for the processor.
      </label>
      {assumptions && (
        <details className="research-drawer mt-4">
          <summary>Review editable assumptions & units</summary>
          <div className="form-grid two">
            {Object.entries(assumptionNames).map(([k, label]) => (
              <Label key={k} name={label}>
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  value={assumptions[k as keyof Assumptions]}
                  onChange={(e) => {
                    setAssumptions({
                      ...assumptions,
                      [k]: Number(e.target.value),
                    });
                    edited();
                  }}
                />
              </Label>
            ))}
          </div>
          <p className="small muted">
            Illustrative wet-food yield, not a measured substrate result.
            Methane energy assumes 9.94 kWh/m³; conversion efficiencies exclude
            site-specific losses. Volume conditions are assumptions. Electricity
            + recovered heat efficiency must not exceed 1.
          </p>
        </details>
      )}
      <button
        className="button secondary mt-4"
        disabled={busy || !assumptions}
        onClick={estimate}
      >
        Estimate recovery potential
      </button>
      {potential && (
        <div className="circular-result" role="status">
          <Badge tone="amber">{potential.label}</Badge>
          <div className="circular-metrics">
            <Stat
              label="Potential biogas"
              value={`${num(potential.biogas_m3, 3)} m³`}
              detail={`${kg(potential.wet_food_kg)} wet food`}
            />
            <Stat
              label="Potential electricity"
              value={`${num(potential.electricity_kwh, 3)} kWh`}
              detail="Assumed electrical conversion"
            />
            <Stat
              label="Potential useful heat"
              value={`${num(potential.useful_heat_kwh, 3)} kWh`}
              detail="Assumed heat recovery"
            />
          </div>
          <p className="small muted">{potential.caveat}</p>
          {practice && (
            <button
              className="button"
              disabled={busy || receipt}
              onClick={handoff}
            >
              Record simulated biogas handoff
            </button>
          )}
          {!practice && (
            <p className="notice">
              Record actual processor acceptance and completed collection in the
              recipient dispatch desk below. Potential energy is not measured
              energy.
            </p>
          )}
          {receipt && (
            <p className="success">
              Simulated handoff recorded. Actual energy: not measured.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

export function CircularImpactPanel({
  run,
  refresh,
}: {
  run: Run;
  refresh: number;
}) {
  const [data, setData] = useState<CircularImpact | null>(null);
  useEffect(() => {
    let active = true;
    void run(async () => {
      const d = await api<CircularImpact>("/circular/impact");
      if (active) setData(d);
    });
    return () => {
      active = false;
    };
  }, [refresh]);
  if (!data) return null;
  return (
    <Card className="circular-card mt-6">
      <p className="eyebrow">A CIRCULAR KITCHEN, WITH EVIDENCE</p>
      <h2>Reuse & recovery outcomes</h2>
      <div className="circular-metrics">
        <Stat
          label="Reuse reserved"
          value={kg(data.reserved_reuse_kg)}
          detail="Pending / approved, awaiting actual log"
        />
        <Stat
          label="Reuse recorded"
          value={kg(data.staff_recorded_reuse_kg)}
          detail="Staff-entered outcomes; source retained"
        />
        <Stat
          label="Biogas allocation"
          value={kg(data.simulated_biogas_kg)}
          detail="Simulated processor handoffs"
        />
        <Stat
          label="Potential useful energy"
          value={`${num(data.potential_useful_energy_kwh, 3)} kWh`}
          detail={`Theoretical; covers ${kg(data.potential_covered_kg)}. Actual energy not measured.`}
        />
      </div>
      <p className="notice">{data.caveat}</p>
      <p className="small muted">
        Food available across actual meal services:{" "}
        {kg(data.gross_actual_service_food_kg)}; newly prepared food after
        removing the reuse transfer: {kg(data.newly_prepared_actual_food_kg)}.
        Source labels and staff-entered measurements apply.
      </p>
      <div className="table-scroll">
        <table>
          <caption>Dinner reuse decisions and recorded outcomes</caption>
          <thead>
            <tr>
              <th>Lunch → dinner</th>
              <th>Status / source</th>
              <th>Reused</th>
              <th>Fresh planned</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {data.reuse_plans.map((p) => (
              <tr key={p.id}>
                <td>
                  {p.item}
                  <small>{p.lunch_record_id}</small>
                </td>
                <td>
                  {titleCase(p.state)} · {p.source}
                </td>
                <td>{kg(p.quantity_kg)}</td>
                <td>{kg(p.fresh_preparation_kg)}</td>
                <td>
                  {p.outcome_record_id
                    ? `${p.outcome_record_id} · fresh ${kg(p.recorded_fresh_kg)}`
                    : p.label}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.biogas_receipts.map((h) => (
        <article className="circular-result" key={h.id}>
          <Badge tone="amber">Simulated handoff · {h.processor}</Badge>
          <h3>
            {kg(h.quantity_kg)} {titleCase(h.origin)}
          </h3>
          <p>
            Segregation:{" "}
            {h.segregation_confirmed === true
              ? "staff confirmed"
              : "not documented on legacy receipt"}{" "}
            → accepted processor →{" "}
            {h.potential
              ? `${num(h.potential.biogas_m3, 3)} m³ potential gas → ${num(h.potential.useful_energy_kwh, 3)} kWh potential useful energy`
              : "potential not estimated"}
          </p>
          <p className="small muted">{h.outcome}</p>
          {h.potential && (
            <details>
              <summary>Receipt assumptions</summary>
              <pre>{JSON.stringify(h.potential.assumptions, null, 2)}</pre>
            </details>
          )}
        </article>
      ))}
    </Card>
  );
}
