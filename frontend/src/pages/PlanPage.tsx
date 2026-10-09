import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../api";
import AIPrepCoach from "../components/AIPrepCoach";
import { CostPlanner, ModelComparison } from "../components/ResearchPlanning";
import type {
  Catalog,
  Forecast,
  ForecastInput,
  ForecastItem,
  Plan,
  Report,
  Run,
  Simulation,
} from "../types";
import {
  ActionLink,
  Badge,
  Card,
  currency,
  Empty,
  kg,
  Label,
  num,
  Stat,
} from "../components/Common";

function Simulator({
  forecast,
  item,
  quantity,
  onQuantity,
  run,
  onEvidence,
}: {
  forecast: Forecast;
  item: ForecastItem;
  quantity: number;
  onQuantity: (q: number) => void;
  run: Run;
  onEvidence: (ids: string[]) => void;
}) {
  const [simulation, setSimulation] = useState<Simulation | null>(null),
    [loading, setLoading] = useState(false);
  useEffect(() => {
    setSimulation(null);
    if (item.status !== "ready") return;
    let active = true;
    setLoading(true);
    const t = setTimeout(() => {
      void run(() =>
        api<Simulation>("/simulate", {
          forecast_id: forecast.id,
          item: item.item,
          quantity_kg: quantity,
          baseline_prepared_kg: item.baseline_prepared_kg,
        }),
      ).then((result) => {
        if (active) {
          if (result) setSimulation(result);
          setLoading(false);
        }
      });
    }, 180);
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, [forecast.id, item.item, quantity]);
  return (
    <Card className="simulator">
      <div className="section-heading">
        <div>
          <p className="eyebrow">LIVE PREPARATION SIMULATOR</p>
          <h2>{item.item} · find the balance</h2>
        </div>
        <SlidersHorizontal size={22} />
      </div>
      {item.status !== "ready" ? (
        <>
          <p className="notice">{item.fallback_reason}</p>
          <Label name="Manager-selected manual quantity (cooked kg)">
            <input
              type="number"
              min="0"
              max="1000000"
              step="0.1"
              value={quantity}
              onChange={(e) => onQuantity(Number(e.target.value))}
            />
          </Label>
          <p className="muted">
            No forecast or projected benefit is claimed for this item.
          </p>
        </>
      ) : (
        <>
          <div className="sim-intro">
            <div>
              <span className="muted small">Served-demand estimate</span>
              <strong>{kg(item.demand_kg)}</strong>
              <small>
                Historical range {kg(item.range_low_kg)} –{" "}
                {kg(item.range_high_kg)}
              </small>
            </div>
            <div>
              <span className="muted small">
                Historical preparation baseline
              </span>
              <strong>{kg(item.baseline_prepared_kg)}</strong>
              <small>{item.sample_count} prior observations</small>
            </div>
          </div>
          <div className="slider-row">
            <label>
              <span>Prepare cooked kg</span>
              <input
                aria-label={`${item.item} preparation slider`}
                type="range"
                min="0"
                max={item.simulator_max_kg}
                step="0.1"
                value={quantity.toFixed(1)}
                onChange={(e) => onQuantity(Number(e.target.value))}
              />
            </label>
            <Label name="Quantity (kg)">
              <input
                type="number"
                min="0"
                max="1000000"
                step="0.1"
                value={quantity.toFixed(1)}
                onChange={(e) => onQuantity(Number(e.target.value))}
              />
            </Label>
          </div>
          <div className="chart small-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={(item.demand_samples_kg ?? []).map((d, i) => ({
                  sample: i + 1,
                  demand: d,
                }))}
              >
                <CartesianGrid vertical={false} stroke="#e3ece7" />
                <XAxis
                  dataKey="sample"
                  label={{
                    value: "Prior observation",
                    position: "insideBottom",
                    offset: -3,
                  }}
                  tick={{ fontSize: 11 }}
                  height={40}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => kg(Number(v))} />
                <Bar
                  dataKey="demand"
                  name="Served-demand sample"
                  fill="#b8c88d"
                  radius={[3, 3, 0, 0]}
                />
                <ReferenceLine
                  y={quantity}
                  stroke="#315848"
                  strokeWidth={2}
                  label={{
                    value: "Preparation",
                    fill: "#315848",
                    fontSize: 11,
                  }}
                />
                <ReferenceLine
                  y={item.demand_kg}
                  stroke="#7591a2"
                  strokeDasharray="4 4"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {loading && (
            <p className="muted small" role="status">
              Calculating service trade-off…
            </p>
          )}
          {simulation && (
            <>
              <div className="stats-grid sim-stats">
                <Stat
                  label="Expected surplus"
                  value={kg(simulation.expected_surplus_kg)}
                  detail={`Baseline ${kg(simulation.baseline.expected_surplus_kg)}`}
                  tone="mint"
                />
                <Stat
                  label="Expected shortage"
                  value={kg(simulation.expected_shortage_kg)}
                  detail={`Point estimate ${kg(simulation.point_shortage_kg)}`}
                  tone="sand"
                />
                <Stat
                  label="Shortage frequency"
                  value={`${num(simulation.shortage_frequency * 100)}%`}
                  detail="Empirical · not a guarantee"
                />
                <Stat
                  label={
                    simulation.potential_cost_difference_inr < 0
                      ? "Added production cost"
                      : "Potential cost avoided"
                  }
                  value={currency(
                    Math.abs(simulation.potential_cost_difference_inr),
                  )}
                  detail={`Untouched difference ${kg(simulation.prevented_untouched_surplus_kg)}`}
                />
              </div>
              {simulation.expected_shortage_kg > 0 && (
                <p className="notice">
                  Service trade-off: historical samples include shortage at this
                  quantity. Review before approving.
                </p>
              )}
            </>
          )}
          <p className="muted small mt-4">
            {item.range_label}.{" "}
            {item.fallback_reason ?? "Matched weekday and special event."}{" "}
            Reducing cooking does not imply reduced plate waste. All outcomes
            are projected.
          </p>
          <ActionLink onClick={() => onEvidence(item.history_ids)}>
            View calculation evidence
          </ActionLink>
        </>
      )}
    </Card>
  );
}

export default function PlanPage({
  run,
  busy,
  onRecord,
  onEvidence,
  onSaved,
  version,
}: {
  run: Run;
  busy: boolean;
  onRecord: (planId: string) => void;
  onEvidence: (ids: string[]) => void;
  onSaved: () => void;
  version: number;
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [input, setInput] = useState<ForecastInput>({
      date: "2026-10-09",
      meal: "lunch",
      expected_attendance: 160,
      special_event: "none",
      buffer_pct: 5,
      items: [],
    });
  const [forecast, setForecast] = useState<Forecast | null>(null),
    [quantities, setQuantities] = useState<Record<string, number>>({}),
    [selected, setSelected] = useState(""),
    [manager, setManager] = useState(""),
    [saved, setSaved] = useState<Plan | null>(null),
    [report, setReport] = useState<Report | null>(null);
  const [coachId, setCoachId] = useState<string | null>(null);
  const [decisionIds, setDecisionIds] = useState<Record<string, string>>({});
  useEffect(() => {
    void run(async () => {
      const c = await api<Catalog>("/catalog");
      setCatalog(c);
      setInput((v) => ({ ...v, items: c.meal_items[v.meal] ?? [] }));
    });
  }, []);
  const dirty =
    forecast && JSON.stringify(input) !== JSON.stringify(forecast.assumptions);
  const calculate = async () => {
    const result = await run(
      () => api<Forecast>("/forecast", input),
      "Forecast calculated from strictly earlier historical records.",
    );
    if (result) {
      setForecast(result);
      setCoachId(null);
      setDecisionIds({});
      setQuantities(
        Object.fromEntries(
          result.items.map((i) => [i.item, i.recommended_kg ?? 0]),
        ),
      );
      setSelected(result.items[0]?.item ?? "");
      setSaved(null);
      setReport(null);
    }
  };
  const approve = async () => {
    if (!forecast) return;
    const result = await run(
      () =>
        api<Plan>("/plans", {
          forecast_id: forecast.id,
          quantities,
          approved_by: manager,
          decision_ids: decisionIds,
          coach_id: coachId,
        }),
      "Preparation plan approved and saved in SQLite.",
    );
    if (result) {
      setSaved(result);
      onSaved();
    }
  };
  const explain = async () => {
    if (!forecast) return;
    const result = await run(() =>
      api<Report>("/report", {
        forecast_id: forecast.id,
        plan_id: saved?.id ?? null,
      }),
    );
    if (result) setReport(result);
  };
  const item = forecast?.items.find((i) => i.item === selected);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">02 / PLAN WITH EVIDENCE</p>
          <h1>
            A little foresight.
            <br />
            <em>A better service.</em>
          </h1>
          <p className="muted">
            Forecast food served. Adjust preparation. Protect availability.
          </p>
        </div>
        <Badge tone="blue">Attendance-aware forecast</Badge>
      </div>
      <Card>
        <div className="plan-stage">
          <span>1</span>
          <b>Set the scene for your next service</b>
        </div>
        <div className="form-grid">
          <Label name="Meal date">
            <input
              type="date"
              value={input.date}
              onChange={(e) => setInput({ ...input, date: e.target.value })}
            />
          </Label>
          <Label name="Meal">
            <select
              value={input.meal}
              onChange={(e) =>
                setInput({
                  ...input,
                  meal: e.target.value,
                  items: catalog?.meal_items[e.target.value] ?? [],
                })
              }
            >
              {["breakfast", "lunch", "dinner"].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </Label>
          <Label name="Expected diners">
            <input
              type="number"
              min="1"
              max="100000"
              value={input.expected_attendance}
              onChange={(e) =>
                setInput({
                  ...input,
                  expected_attendance: Number(e.target.value),
                })
              }
            />
          </Label>
          <Label name="Special event">
            <select
              value={input.special_event}
              onChange={(e) =>
                setInput({ ...input, special_event: e.target.value })
              }
            >
              {["none", "exam", "festival"].map((e) => (
                <option key={e}>{e}</option>
              ))}
            </select>
          </Label>
          <Label name="Buffer (%)" hint="0–20% above served demand">
            <input
              type="number"
              min="0"
              max="20"
              step="1"
              value={input.buffer_pct}
              onChange={(e) =>
                setInput({ ...input, buffer_pct: Number(e.target.value) })
              }
            />
          </Label>
        </div>
        <div className="flex flex-wrap gap-3 items-center mt-4">
          <span className="muted small">Menu:</span>
          {catalog?.items.map((i) => (
            <label className="menu-check" key={i}>
              <input
                type="checkbox"
                checked={input.items.includes(i)}
                onChange={(e) =>
                  setInput({
                    ...input,
                    items: e.target.checked
                      ? [...input.items, i]
                      : input.items.filter((v) => v !== i),
                  })
                }
              />
              {i}
            </label>
          ))}
          <button
            className="button ml-auto"
            disabled={busy || input.items.length === 0}
            onClick={calculate}
          >
            Calculate forecast <ArrowRight size={16} />
          </button>
        </div>
      </Card>
      {dirty && (
        <p className="notice">
          Planning assumptions changed. Recalculate to approve these settings.
        </p>
      )}
      {forecast && forecast.dataset_version !== version && (
        <p className="notice">
          Dataset is now version {version}. This snapshot uses version{" "}
          {forecast.dataset_version}; recalculate before a new approval.
        </p>
      )}
      {!forecast ? (
        <Empty>
          Your preparation decision begins with expected attendance.
          <br />
          Calculate a forecast to explore surplus and shortage together.
        </Empty>
      ) : (
        <>
          <AIPrepCoach
            onReport={setCoachId}
            forecast={forecast}
            disabled={!!dirty || forecast.dataset_version !== version || busy}
            onApply={(name, q) => {
              setQuantities((values) => ({ ...values, [name]: q }));
              setSelected(name);
              setSaved(null);
              setReport(null);
              setDecisionIds((ids) =>
                Object.fromEntries(
                  Object.entries(ids).filter(([key]) => key !== name),
                ),
              );
            }}
          />
          <div className="plan-stage mt-6">
            <span>2</span>
            <b>Choose a dish. Explore the preparation trade-off.</b>
          </div>
          <div className="item-tabs" aria-label="Select a dish to simulate">
            {forecast.items.map((i) => (
              <button
                className={selected === i.item ? "selected" : ""}
                aria-pressed={selected === i.item}
                key={i.item}
                onClick={() => setSelected(i.item)}
              >
                <span>{i.item}</span>
                <strong>
                  {i.status === "ready" ? kg(i.demand_kg) : "Manual quantity"}
                </strong>
                <small>{i.sample_count} historical records</small>
              </button>
            ))}
          </div>
          {item && (
            <Simulator
              forecast={forecast}
              item={item}
              quantity={quantities[item.item] ?? 0}
              onQuantity={(q) => {
                setQuantities({ ...quantities, [item.item]: q });
                setSaved(null);
                setReport(null);
                setDecisionIds((ids) =>
                  Object.fromEntries(
                    Object.entries(ids).filter(([key]) => key !== item.item),
                  ),
                );
              }}
              run={run}
              onEvidence={onEvidence}
            />
          )}
          {item && (
            <>
              <details className="research-drawer">
                <summary>
                  <span>
                    <b>Explore a cost-aware preparation choice</b>
                    <small>
                      Optional · set your service constraint and compare surplus
                      against shortage.
                    </small>
                  </span>
                </summary>
                <CostPlanner
                  key={forecast.id + item.item}
                  forecast={forecast}
                  item={item}
                  run={run}
                  busy={busy}
                  disabled={!!dirty || forecast.dataset_version !== version}
                  onEvidence={onEvidence}
                  onApply={(decision) => {
                    if (!decision.selected) return;
                    setQuantities({
                      ...quantities,
                      [item.item]: decision.selected.quantity_kg,
                    });
                    setDecisionIds({
                      ...decisionIds,
                      [item.item]: decision.id,
                    });
                    setSaved(null);
                    setReport(null);
                  }}
                />
              </details>
              <details className="research-drawer">
                <summary>
                  <span>
                    <b>Look inside the forecasting models</b>
                    <small>
                      Compare temporal backtests, uncertainty and the historical
                      records behind this estimate.
                    </small>
                  </span>
                </summary>
                <ModelComparison item={item} onEvidence={onEvidence} />
              </details>
            </>
          )}
          <div className="dashboard-grid mt-6">
            <Card>
              <p className="eyebrow">HONEST MODEL EVALUATION</p>
              <h2>Temporal backtest</h2>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Model MAE kg</th>
                      <th>Baseline MAE kg</th>
                      <th>Evaluations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {forecast.items.map((i) => (
                      <tr key={i.item}>
                        <td>{i.item}</td>
                        <td>{num(i.backtest.mae_kg, 2)}</td>
                        <td>{num(i.backtest.baseline_mae_kg, 2)}</td>
                        <td>{i.backtest.evaluation_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="small muted mt-4">
                Each prediction uses strictly earlier dates. Actual attendance
                was known for evaluation. Baseline uses prior average served kg;
                lower MAE is better. These results do not establish performance
                in real kitchens.
              </p>
            </Card>
            <Card className="approval-card">
              <div className="plan-stage">
                <span>3</span>
                <b>Your call, chef.</b>
              </div>
              <p className="eyebrow">MANAGER DECISION</p>
              <h2>Preparation sheet</h2>
              {Object.entries(quantities).map(([name, q]) => (
                <div className="sheet-row" key={name}>
                  <span>{name}</span>
                  <strong>{kg(q)}</strong>
                  {decisionIds[name] && (
                    <Badge tone="blue">Cost-aware choice</Badge>
                  )}
                </div>
              ))}
              <Label name="Approving manager">
                <input
                  value={manager}
                  onChange={(e) => setManager(e.target.value)}
                  maxLength={100}
                />
              </Label>
              {saved ? (
                <>
                  <p className="success">
                    <CheckCircle2 size={18} /> Approved by {saved.approved_by}
                  </p>
                  <small className="muted">
                    {saved.id} · {new Date(saved.approved_at).toLocaleString()}
                  </small>
                  <button
                    className="button mt-4"
                    onClick={() => onRecord(saved.id)}
                  >
                    Record meal outcome <ArrowRight size={16} />
                  </button>
                </>
              ) : (
                <button
                  disabled={
                    busy ||
                    !manager.trim() ||
                    !!dirty ||
                    forecast.dataset_version !== version
                  }
                  className="button w-full mt-3"
                  onClick={approve}
                >
                  Approve preparation plan
                </button>
              )}
              <button
                className="button secondary w-full mt-3"
                disabled={busy}
                onClick={explain}
              >
                <FileText size={16} /> Explain{" "}
                {saved ? "approved plan" : "recommendation"}
              </button>
            </Card>
          </div>
          {report && (
            <Card className="mt-6">
              <div className="section-heading">
                <h2>Evidence-grounded explanation</h2>
                <Badge>Offline · deterministic</Badge>
              </div>
              <p className="report-text">{report.explanation}</p>
              <small className="muted">
                For custom simulator quantities, approve the plan to include
                them in this report. The recommendation report uses the forecast
                buffer.
              </small>
            </Card>
          )}
        </>
      )}
    </>
  );
}
