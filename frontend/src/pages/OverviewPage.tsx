import IngredientRecipes from "../components/IngredientRecipes";
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowUpRight, CalendarDays, Search, Sprout } from "lucide-react";
import { api } from "../api";
import LivingLandscape from "../components/LivingLandscape";
import type { Finding, Inventory, Overview, Run } from "../types";
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

export default function OverviewPage({
  refresh,
  run,
  onPlan,
  onEvidence,
  onSaved,
  onNavigate,
}: {
  refresh: number;
  onSaved: () => void;
  run: Run;
  onPlan: () => void;
  onEvidence: (ids: string[]) => void;
  onNavigate: (page: string) => void;
}) {
  const [data, setData] = useState<Overview | null>(null),
    [findings, setFindings] = useState<Finding[]>([]),
    [inventory, setInventory] = useState<Inventory | null>(null);
  const [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [asOf, setAsOf] = useState("2026-10-09");
  useEffect(() => {
    void run(async () => {
      const [d, f, i] = await Promise.all([
        api<Overview>(
          `/overview?${from ? `from=${from}&` : ""}${to ? `to=${to}` : ""}`,
        ),
        api<Finding[]>("/investigations"),
        api<Inventory>(`/inventory?as_of=${asOf}`),
      ]);
      setData(d);
      setFindings(f);
      setInventory(i);
    });
  }, [refresh, from, to, asOf]);
  if (!data) return <Empty>Loading kitchen accounting…</Empty>;
  return (
    <>
      <section className="kitchen-hero sustainability-hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="edition-mark" /> FOODWISE / THE LIVING KITCHEN
          </p>
          <h1>
            Less waste.
            <br />
            <em>More life.</em>
          </h1>
          <p className="hero-description">
            Better meals begin with a little foresight. Follow the food, protect
            every plate, and give surplus a considered next step.
          </p>
          <button className="button hero-button" onClick={onPlan}>
            Let’s plan the next meal <ArrowUpRight size={20} />
          </button>
          <div className="hero-footnote">
            <span className="tiny-rule" />
            {data.record_count} records. {data.meal_services} meal services.
            <br />A food journey you can account for.
          </div>
        </div>
        <LivingLandscape totals={data.totals} onNavigate={onNavigate} />
      </section>
      <div className="campus-ribbon">
        <span>
          <Sprout size={17} /> Rooted in a real place. Grounded in kitchen
          evidence.
        </span>
        <button className="link" onClick={() => onNavigate("station")}>
          Visit the KNSIT Field station <ArrowUpRight size={15} />
        </button>
      </div>
      <div className="overview-toolbar">
        <div className="flex flex-wrap gap-2 items-center">
          <Badge tone="blue">{titleCase(data.dataset_source)}</Badge>
          <span className="muted small">
            Version {data.dataset_version} · {data.record_count} records ·{" "}
            {data.meal_services} meal services
          </span>
        </div>
        <div className="flex gap-3 flex-wrap">
          <Label name="From date">
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </Label>
          <Label name="To date">
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </Label>
        </div>
      </div>
      <div className="stats-grid overview-ledger">
        <Stat
          label="Food prepared"
          value={kg(data.totals.prepared_kg)}
          detail={`${data.date_from ?? "No history"} → ${data.date_to ?? "—"}`}
        />
        <Stat
          label="Food served"
          value={kg(data.totals.served_kg)}
          detail="Consumed + plate waste"
        />
        <Stat
          label="Untouched surplus"
          value={kg(data.totals.untouched_surplus_kg)}
          detail={`${num(data.totals.untouched_pct)}% of prepared · review required`}
          tone="mint"
        />
        <Stat
          label="Plate waste"
          value={kg(data.totals.plate_waste_kg)}
          detail="No human redistribution"
          tone="sand"
        />
      </div>
      <div className="dashboard-grid">
        <Card>
          <div className="section-heading">
            <div>
              <p className="eyebrow">FOOD ACCOUNTING</p>
              <h2>Where the food goes</h2>
            </div>
            <Badge tone="gray">Cooked kg</Badge>
          </div>
          <p className="muted small mb-5">
            Served food includes plate waste. Untouched surplus is the food
            never served.
          </p>
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.daily}>
                <CartesianGrid vertical={false} stroke="#e7eeeb" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => String(d).slice(5)}
                  minTickGap={38}
                  tick={{ fontSize: 11 }}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => kg(Number(value))} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="consumed_kg"
                  stackId="mass"
                  name="Consumed"
                  fill="#b6c9b5"
                  stroke="#315848"
                />
                <Area
                  type="monotone"
                  dataKey="plate_waste_kg"
                  stackId="mass"
                  name="Plate waste"
                  fill="#e8a18a"
                  stroke="#ce563e"
                />
                <Area
                  type="monotone"
                  dataKey="untouched_surplus_kg"
                  stackId="mass"
                  name="Untouched"
                  fill="#f0d78e"
                  stroke="#b18a20"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="card-footer">
            <span>Estimated production cost of recorded waste</span>
            <b>{currency(data.totals.estimated_waste_cost_inr)}</b>
          </div>
          <small className="muted">
            Cost estimate, not a realized financial loss or savings claim.
            Aggregate balance residual: {kg(data.totals.balance_difference_kg)}.
          </small>
        </Card>
        <Card className="inventory-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">USE YOUR STOCK WISELY</p>
              <h2>Expiry watch</h2>
            </div>
            <Sprout size={23} />
          </div>
          <Label name="Review label dates as of">
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
            />
          </Label>
          {inventory?.items.map((i) => (
            <div className="inventory-row" key={i.id}>
              <div className="flex justify-between gap-2">
                <b>{i.ingredient}</b>
                <Badge
                  tone={
                    i.status === "expired"
                      ? "red"
                      : i.status === "later"
                        ? "gray"
                        : "amber"
                  }
                >
                  {titleCase(i.status)}
                </Badge>
              </div>
              <p>
                {kg(i.quantity_kg)} raw · Label: {i.expiry_date}
              </p>
              <small>
                {i.storage_status}
                {i.allergens.length
                  ? ` · Allergen: ${i.allergens.join(", ")}`
                  : ""}
              </small>
            </div>
          ))}
          <p className="small muted mt-4">
            Recorded label dates are warnings. They do not establish safe
            storage or certify food.
          </p>
        </Card>
      </div>
      <Card className="mt-6">
        <div className="section-heading">
          <div>
            <p className="eyebrow">OBSERVE → INVESTIGATE → ACT</p>
            <h2>Patterns worth a closer look</h2>
          </div>
          <Search size={22} />
        </div>
        <p className="muted small">
          Computed from all active records; comparisons normalize by diners.
          Associations in generated records do not establish real-kitchen
          causes.
        </p>
        <div className="findings-grid">
          {findings.length === 0 ? (
            <Empty>No patterns available. Import history to begin.</Empty>
          ) : (
            findings.map((f) => (
              <article className="finding" key={f.id}>
                <span className="finding-label">
                  <CalendarDays size={15} /> KITCHEN OBSERVATION
                </span>
                <h3>{f.title}</h3>
                <div className="metric-list">
                  {Object.entries(f.observed_metrics).map(([key, v]) => (
                    <div key={key}>
                      <span>{titleCase(key)}</span>
                      <b>{num(v, key.includes("per_diner") ? 3 : 1)}</b>
                    </div>
                  ))}
                </div>
                <p>{f.suggested_action}</p>
                <details className="finding-caveat">
                  <summary>How to interpret this</summary>
                  <small className="muted">{f.caveats}</small>
                </details>
                <ActionLink onClick={() => onEvidence(f.evidence_record_ids)}>
                  Inspect {f.sample_count} records
                </ActionLink>
              </article>
            ))
          )}
        </div>
      </Card>
      <IngredientRecipes
        run={run}
        refresh={refresh}
        asOf={asOf}
        onSaved={onSaved}
      />
    </>
  );
}
