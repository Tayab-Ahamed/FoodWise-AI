import { useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import type { Forecast, ForecastItem, Optimization, Run } from "../types";
import {
  ActionLink,
  Badge,
  Card,
  currency,
  kg,
  Label,
  num,
  Stat,
} from "./Common";

export function CostPlanner({
  forecast,
  item,
  run,
  busy,
  disabled,
  onApply,
  onEvidence,
}: {
  forecast: Forecast;
  item: ForecastItem;
  run: Run;
  busy: boolean;
  disabled: boolean;
  onApply: (decision: Optimization) => void;
  onEvidence: (ids: string[]) => void;
}) {
  const [surplusCost, setSurplusCost] = useState(item.cost_per_kg ?? 0);
  const [shortageCost, setShortageCost] = useState(180);
  const [frequency, setFrequency] = useState(0.2);
  const [capacity, setCapacity] = useState(item.simulator_max_kg ?? 0);
  const [decision, setDecision] = useState<Optimization | null>(null);
  const revision = useRef(0);
  useEffect(() => {
    setSurplusCost(item.cost_per_kg ?? 0);
    setCapacity(item.simulator_max_kg ?? 0);
    setDecision(null);
  }, [forecast.id, item.item]);
  if (item.status !== "ready") return null;
  const edit = (setter: (v: number) => void, value: number) => {
    revision.current += 1;
    setter(value);
    setDecision(null);
  };
  const calculate = async () => {
    const submittedRevision = revision.current;
    const result = await run(() =>
      api<Optimization>("/optimize", {
        forecast_id: forecast.id,
        item: item.item,
        surplus_cost_per_kg: surplusCost,
        shortage_cost_per_kg: shortageCost,
        max_shortage_frequency: frequency,
        capacity_kg: capacity,
      }),
    );
    if (result && submittedRevision === revision.current) setDecision(result);
  };
  return (
    <Card className="mt-6">
      <div className="section-heading">
        <div>
          <p className="eyebrow">RESEARCH INTO A MANAGER DECISION</p>
          <h2>Cost-aware preparation</h2>
        </div>
        <Badge tone="blue">Empirical newsvendor</Badge>
      </div>
      <p className="muted">
        Choose the cost of leftovers and unmet service, then set a capacity and
        shortage limit. This proposes a quantity for your approval.
      </p>
      <div className="form-grid mt-4">
        <Label
          name="Surplus penalty (₹ / kg)"
          hint="Scenario assumption; starts at recorded cost"
        >
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={surplusCost}
            onChange={(e) => edit(setSurplusCost, Number(e.target.value))}
          />
        </Label>
        <Label
          name="Shortage penalty (₹ / kg)"
          hint="Illustrative 180; edit for your kitchen"
        >
          <input
            type="number"
            min="0.01"
            step="1"
            value={shortageCost}
            onChange={(e) => edit(setShortageCost, Number(e.target.value))}
          />
        </Label>
        <Label name="Maximum shortage frequency">
          <select
            value={frequency}
            onChange={(e) => edit(setFrequency, Number(e.target.value))}
          >
            <option value={0}>0% of historical samples</option>
            <option value={0.1}>10% of historical samples</option>
            <option value={0.2}>20% of historical samples</option>
            <option value={0.5}>50% of historical samples</option>
            <option value={1}>No frequency constraint</option>
          </select>
        </Label>
        <Label name="Kitchen capacity (cooked kg)">
          <input
            type="number"
            min="0"
            step="0.1"
            value={Number(capacity.toFixed(2))}
            onChange={(e) => edit(setCapacity, Number(e.target.value))}
          />
        </Label>
      </div>
      <button
        className="button secondary mt-4"
        disabled={busy || disabled || surplusCost <= 0 || shortageCost <= 0}
        onClick={calculate}
      >
        Find cost-aware quantity
      </button>
      {item.data_quality && (
        <p className="small muted mt-4">
          Sources: {item.data_quality.sources.join(" · ")}. Shortage status
          unknown in {item.data_quality.shortage_unknown_count} observations.{" "}
          {item.data_quality.caveat}
        </p>
      )}
      {!!item.data_quality?.confirmed_shortage_ids.length && (
        <p className="notice">
          Confirmed service shortage in the sample: automatic optimization is
          blocked by the backend. Manager review is required.
        </p>
      )}
      {decision && (
        <>
          <div className="stats-grid mt-5">
            <Stat
              label="Critical cost ratio"
              value={`${num(decision.critical_ratio * 100)}%`}
              detail={`Unconstrained quantity ${kg(decision.unconstrained_quantity_kg)}`}
            />
            <Stat
              label="Frequency resolution"
              value={`${num(decision.frequency_resolution * 100)} percentage points`}
              detail="Small samples limit precision"
            />
          </div>
          {decision.selected ? (
            <>
              <div className="stats-grid">
                <Stat
                  label="Proposed preparation"
                  value={kg(decision.selected.quantity_kg)}
                  tone="mint"
                  detail="Capacity and frequency limit satisfied"
                />
                <Stat
                  label="Projected scenario loss"
                  value={currency(decision.selected.scenario_loss_inr)}
                  detail="Manager penalties; not savings"
                />
                <Stat
                  label="Expected surplus"
                  value={kg(decision.selected.expected_surplus_kg, 2)}
                  detail="Projected historical average"
                />
                <Stat
                  label="Expected shortage"
                  value={kg(decision.selected.expected_shortage_kg, 2)}
                  tone="sand"
                  detail={`${num(decision.selected.shortage_frequency * 100)}% historical frequency`}
                />
              </div>
              <button
                className="button mt-4"
                disabled={busy || disabled}
                onClick={() => onApply(decision)}
              >
                Use this quantity in preparation sheet
              </button>
            </>
          ) : (
            <p className="notice">
              Capacity cannot meet the requested shortage frequency. No quantity
              is recommended. Best cost scenario within capacity:{" "}
              {kg(decision.capacity_best_effort.quantity_kg)}, with{" "}
              {num(decision.capacity_best_effort.shortage_frequency * 100)}%
              historical shortage frequency. Increase capacity or explicitly
              revise your service constraint.
            </p>
          )}
          <div className="chart small-chart mt-5">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={decision.frontier}>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="quantity_kg"
                  type="number"
                  domain={[0, "dataMax"]}
                  tickFormatter={(v: number) => num(v)}
                  label={{
                    value: "Cooked preparation kg",
                    position: "insideBottom",
                    offset: -4,
                  }}
                  height={45}
                />
                <YAxis tickFormatter={(v: number) => num(v)} />
                <Tooltip
                  formatter={(v) => currency(Number(v))}
                  labelFormatter={(v) => `Prepare ${kg(Number(v))}`}
                />
                <Line
                  dataKey="scenario_loss_inr"
                  name="Scenario loss ₹"
                  stroke="#12634f"
                  strokeWidth={2}
                  dot={false}
                />
                {decision.selected && (
                  <ReferenceLine
                    x={decision.selected.quantity_kg}
                    stroke="#a16b2b"
                    strokeDasharray="4 4"
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="small muted">{decision.caveat}</p>
          <ActionLink onClick={() => onEvidence(decision.history_ids)}>
            Trace the demand sample
          </ActionLink>
        </>
      )}
    </Card>
  );
}

export function ModelComparison({
  item,
  onEvidence,
}: {
  item: ForecastItem;
  onEvidence: (ids: string[]) => void;
}) {
  const benchmark = item.backtest.benchmark,
    diagnostics = item.backtest.range_diagnostics;
  if (!benchmark) return null;
  return (
    <Card className="mt-6">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            MODEL CHALLENGERS · {item.item.toUpperCase()}
          </p>
          <h2>Does complexity help?</h2>
        </div>
        <Badge tone="gray">P0 model stays the default</Badge>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>MAE kg ↓</th>
              <th>RMSE kg ↓</th>
              <th>Bias kg</th>
              <th>WAPE % ↓</th>
              <th>Services</th>
            </tr>
          </thead>
          <tbody>
            {benchmark.models.map((m) => (
              <tr key={m.key}>
                <td>
                  {m.label}
                  {m.status !== "compared" && (
                    <small className="block muted">
                      Insufficient shared history
                    </small>
                  )}
                </td>
                <td>{num(m.mae_kg, 2)}</td>
                <td>{num(m.rmse_kg, 2)}</td>
                <td>{num(m.bias_kg, 2)}</td>
                <td>{num(m.wape_pct, 2)}</td>
                <td>{m.evaluation_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted mt-4">
        {benchmark.method} {benchmark.caveat}
      </p>
      {diagnostics && (
        <p className="notice">
          Observed range coverage: {num(diagnostics.coverage_pct)}%. Mean range
          width: {kg(diagnostics.mean_width_kg)}. {diagnostics.label}
        </p>
      )}
      <details className="mt-4">
        <summary>Inspect rolling predictions and training evidence</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Served kg</th>
                {benchmark.models
                  .filter((m) => m.status === "compared")
                  .map((m) => (
                    <th key={m.key}>{m.label}</th>
                  ))}
              </tr>
            </thead>
            <tbody>
              {benchmark.evaluations.map((r) => (
                <tr key={r.record_id}>
                  <td>
                    <ActionLink onClick={() => onEvidence([r.record_id])}>
                      {r.date}
                    </ActionLink>
                  </td>
                  <td>{num(r.actual_served_kg, 2)}</td>
                  {benchmark.models
                    .filter((m) => m.status === "compared")
                    .map((m) => (
                      <td key={m.key}>
                        <ActionLink
                          onClick={() => onEvidence(r.training_ids[m.key])}
                        >
                          {num(r.predictions[m.key], 2)}
                        </ActionLink>
                      </td>
                    ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  );
}
