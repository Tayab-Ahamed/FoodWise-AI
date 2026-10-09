import { CircularImpactPanel } from "../components/CircularKitchen";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import PortionTrials from "../components/PortionTrials";
import type { Impact, Report, Run } from "../types";
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
  titleCase,
} from "../components/Common";

export default function ImpactPage({
  run,
  busy,
  refresh,
  onEvidence,
}: {
  run: Run;
  busy: boolean;
  refresh: number;
  onEvidence: (ids: string[]) => void;
}) {
  const [data, setData] = useState<Impact | null>(null),
    [selected, setSelected] = useState(""),
    [report, setReport] = useState<Report | null>(null);
  useEffect(() => {
    void run(async () => {
      const d = await api<Impact>("/impact");
      setData(d);
      setSelected((s) =>
        d.plans.some((p) => p.plan.id === s) ? s : (d.plans[0]?.plan.id ?? ""),
      );
    });
  }, [refresh]);
  if (!data) return <Empty>Loading recorded outcomes…</Empty>;
  const chosen = data.plans.find((p) => p.plan.id === selected);
  const explain = async () => {
    if (!chosen) return;
    const r = await run(() =>
      api<Report>("/report", {
        forecast_id: chosen.plan.forecast_id,
        plan_id: chosen.plan.id,
      }),
    );
    if (r) setReport(r);
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">05 / LEARN FROM THE OUTCOME</p>
          <h1>
            More than numbers.
            <br />
            <em>The whole story.</em>
          </h1>
          <p className="muted">
            Keep recorded food, projected prevention, and simulated recovery
            separate.
          </p>
        </div>
        <Badge tone="blue">No causal savings claim</Badge>
      </div>
      <p className="eyebrow mb-3">
        RECORDED ACTUAL MEAL LOGS · {data.recorded_actuals.record_count} RECORDS
      </p>
      <div className="stats-grid">
        <Stat
          label="Prepared in actual logs"
          value={kg(data.recorded_actuals.totals.prepared_kg)}
          detail={
            data.recorded_actuals.sources.map(titleCase).join(" · ") ||
            "No actual logs yet"
          }
        />
        <Stat
          label="Consumed"
          value={kg(data.recorded_actuals.totals.consumed_kg)}
          detail="Recorded, not projected"
        />
        <Stat
          label="Untouched surplus"
          value={kg(data.recorded_actuals.totals.untouched_surplus_kg)}
          detail="Review status is separate"
          tone="mint"
        />
        <Stat
          label="Plate waste"
          value={kg(data.recorded_actuals.totals.plate_waste_kg)}
          detail="Permanent human-redistribution block"
          tone="sand"
        />
      </div>
      <div className="dashboard-grid">
        <Card>
          <div className="section-heading">
            <h2>Recorded food over time</h2>
            <Badge tone="gray">Actual source labels retained</Badge>
          </div>
          {data.recorded_actuals.daily.length ? (
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.recorded_actuals.daily}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip formatter={(v) => kg(Number(v))} />
                  <Legend />
                  <Bar
                    dataKey="consumed_kg"
                    stackId="mass"
                    fill="#8fa788"
                    name="Consumed"
                  />
                  <Bar
                    dataKey="untouched_surplus_kg"
                    stackId="mass"
                    fill="#e8bd49"
                    name="Untouched"
                  />
                  <Bar
                    dataKey="plate_waste_kg"
                    stackId="mass"
                    fill="#ce563e"
                    name="Plate waste"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty>Log a meal to inspect recorded outcomes.</Empty>
          )}
        </Card>
        <Card className="inventory-card">
          <p className="eyebrow">COMPLETED HANDOFF LEDGER</p>
          <h2>Recorded recipient handoffs</h2>
          {Object.entries(data.recorded_dispositions).map(([route, q]) => (
            <div className="sheet-row" key={route}>
              <span>{route.replaceAll("_", " ")}</span>
              <strong>{kg(q)}</strong>
            </div>
          ))}
          <p className="small muted mt-5">
            Measured food with staff-recorded recipient acceptance and receipt.
            Approval alone does not count as a completed handoff.
          </p>
          {Object.values(data.simulated_dispositions).some((q) => q > 0) && (
            <>
              <p className="eyebrow">SIMULATED DISPOSITION</p>
              <h3>Practice handoffs</h3>
              {Object.entries(data.simulated_dispositions).map(([route, q]) => (
                <div className="sheet-row" key={route}>
                  <span>{route.replaceAll("_", " ")}</span>
                  <strong>{kg(q)}</strong>
                </div>
              ))}
              <p className="small muted mt-5">
                Approval alone is not completed recovery. These totals count
                recorded simulated handoffs only. No real partner has been
                contacted.
              </p>
            </>
          )}
        </Card>
      </div>
      <Card className="mt-6">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PROJECTED PREPARATION EFFECT</p>
            <h2>A decision you can trace</h2>
          </div>
          <Badge tone="blue">Projected · historical samples</Badge>
        </div>
        {data.plans.length === 0 ? (
          <Empty>
            Approve a preparation plan to view its projected trade-off.
          </Empty>
        ) : (
          <>
            <Label name="Approved plan">
              <select
                value={selected}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setReport(null);
                }}
              >
                {data.plans.map((p) => (
                  <option key={p.plan.id} value={p.plan.id}>
                    {p.plan.assumptions.date} · {p.plan.approved_by} ·{" "}
                    {p.plan.id}
                  </option>
                ))}
              </select>
            </Label>
            {chosen && (
              <>
                <div className="stats-grid impact-stats">
                  <Stat
                    label="Untouched surplus difference"
                    value={kg(chosen.projected_untouched_difference_kg)}
                    detail="Baseline expected minus planned expected"
                    tone="mint"
                  />
                  <Stat
                    label={
                      chosen.projected_cost_difference_inr < 0
                        ? "Projected added cost"
                        : "Projected cost avoided"
                    }
                    value={currency(
                      Math.abs(chosen.projected_cost_difference_inr),
                    )}
                    detail="Estimated production cost; not realized savings"
                  />
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Demand kg</th>
                        <th>Approved kg</th>
                        <th>Expected surplus kg</th>
                        <th>Expected shortage kg</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {chosen.evidence.items.map((i) => (
                        <tr key={i.item}>
                          <td>{i.item}</td>
                          <td>{num(i.demand_kg)}</td>
                          <td>{num(chosen.plan.quantities[i.item])}</td>
                          <td>{num(i.simulation?.expected_surplus_kg)}</td>
                          <td>{num(i.simulation?.expected_shortage_kg)}</td>
                          <td>
                            <ActionLink
                              onClick={() => onEvidence(i.history_ids)}
                            >
                              {i.sample_count} records
                            </ActionLink>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {chosen.actual_comparison.length > 0 && (
                  <>
                    <h3 className="mt-6">
                      Approved plan versus actual service
                    </h3>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Item</th>
                            <th>Planned kg</th>
                            <th>Actually prepared kg</th>
                            <th>Actually served kg</th>
                            <th>Served forecast error kg</th>
                          </tr>
                        </thead>
                        <tbody>
                          {chosen.actual_comparison.map((a) => (
                            <tr key={a.record_id}>
                              <td>{a.item}</td>
                              <td>{num(a.planned_kg)}</td>
                              <td>{num(a.actual_prepared_kg)}</td>
                              <td>{num(a.actual_served_kg)}</td>
                              <td>{num(a.served_forecast_error_kg)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
                <p className="muted small mt-4">
                  Snapshot version {chosen.plan.dataset_version} ·{" "}
                  {chosen.plan.assumptions.expected_attendance} expected diners
                  · approved{" "}
                  {new Date(chosen.plan.approved_at).toLocaleString()}. New
                  actuals update future forecasts; saved snapshots remain fixed.
                </p>
                <button
                  className="button secondary mt-4"
                  onClick={explain}
                  disabled={busy}
                >
                  Generate offline evidence report
                </button>
              </>
            )}
          </>
        )}
        {report && (
          <div className="report">
            <Badge>Deterministic explanation · no API key</Badge>
            <p className="report-text">{report.explanation}</p>
            <details>
              <summary>Computed evidence JSON</summary>
              <pre>{JSON.stringify(report.evidence, null, 2)}</pre>
            </details>
          </div>
        )}
      </Card>
      <p className="muted small mt-5">{data.caveat}</p>
      <CircularImpactPanel run={run} refresh={refresh} />
      <PortionTrials
        run={run}
        busy={busy}
        refresh={refresh}
        onEvidence={onEvidence}
      />
    </>
  );
}
