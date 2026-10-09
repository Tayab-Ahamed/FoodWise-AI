import { useEffect, useState } from "react";
import { Leaf } from "lucide-react";
import { api } from "../api";
import type { Run } from "../types";
import { Badge, Card, Empty, kg, Label, titleCase } from "./Common";

interface Stock {
  id: string;
  ingredient: string;
  quantity_kg: number;
  expiry_date: string;
  source: string;
  label_kind: string;
  date_meaning: string;
  storage_verified: boolean | null;
  condition_passed?: boolean | null;
  recipe_eligible: boolean;
  recipe_blockers: string[];
  reviewed_by?: string;
  procedure_reference?: string;
}
interface Recommendation {
  id: string;
  dish: string;
  portions: number;
  status: string;
  near_use_by_usage_raw_kg: number;
  label: string;
  method: string;
  allergens: string[];
  allocation_note: string;
  ingredients: {
    ingredient: string;
    required_raw_kg: number;
    eligible_available_raw_kg: number;
    planned_usage_raw_kg: number;
    shortage_raw_kg: number;
    batch_allocations: {
      batch_id: string;
      use_raw_kg: number;
      label_kind: string;
      source: string;
    }[];
  }[];
}
interface Suggestions {
  inventory: Stock[];
  recipes: Recommendation[];
  units: string;
  caveat: string;
  excluded_recipes: { dish: string; reason: string; ingredients: string[] }[];
}
const value = (v: string) => (v === "unknown" ? null : v === "true");

export default function IngredientRecipes({
  run,
  refresh,
  asOf,
  onSaved,
}: {
  run: Run;
  refresh: number;
  asOf: string;
  onSaved: () => void;
}) {
  const [data, setData] = useState<Suggestions | null>(null),
    [portions, setPortions] = useState(100);
  const [selected, setSelected] = useState("INV-1"),
    [label, setLabel] = useState("unknown"),
    [storage, setStorage] = useState<boolean | null>(null),
    [condition, setCondition] = useState<boolean | null>(null);
  const [staff, setStaff] = useState(""),
    [procedure, setProcedure] = useState(""),
    [working, setWorking] = useState(false);
  useEffect(() => {
    let active = true;
    void run(async () => {
      const d = await api<Suggestions>(
        `/recipes/recommendations?as_of=${asOf}&portions=${portions}`,
      );
      if (active) setData(d);
    });
    return () => {
      active = false;
    };
  }, [asOf, portions, refresh]);
  const choose = (id: string) => {
    setSelected(id);
    const i = data?.inventory.find((i) => i.id === id);
    setLabel(i?.label_kind ?? "unknown");
    setStorage(i?.storage_verified ?? null);
    setCondition(i?.condition_passed ?? null);
    setStaff(i?.reviewed_by ?? "");
    setProcedure(i?.procedure_reference ?? "");
  };
  const save = async () => {
    setWorking(true);
    const r = await run(
      () =>
        api(
          `/inventory/${selected}/review`,
          {
            label_kind: label,
            storage_verified: storage,
            condition_passed: condition,
            reviewed_by: staff,
            procedure_reference: procedure,
            review_date: asOf,
          },
          "PATCH",
        ),
      "Inventory review saved. Recipe eligibility is calculated on the backend.",
    );
    setWorking(false);
    if (r) onSaved();
  };
  return (
    <Card className="circular-card mt-6">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            USE INGREDIENTS WHILE THEY BELONG ON THE MENU
          </p>
          <h2>Near-expiry recipe ideas</h2>
        </div>
        <Leaf aria-hidden="true" />
      </div>
      <Badge tone="amber">
        Offline planning suggestions · kitchen review required
      </Badge>
      <p className="small muted mt-3">
        Planning date: {asOf}. Use-by is a safety date; best-before is a quality
        date. Unknown labels, failed storage checks and past dates are excluded
        from this planner. Recipe quantities are raw ingredients, never
        cooked-food forecasts.
      </p>
      <details className="research-drawer mt-4">
        <summary>Review ingredient eligibility</summary>
        <Label name="Ingredient batch for review">
          <select value={selected} onChange={(e) => choose(e.target.value)}>
            {data?.inventory.map((i) => (
              <option key={i.id} value={i.id}>
                {i.ingredient} · {kg(i.quantity_kg)} raw · {i.expiry_date} ·{" "}
                {i.source}
              </option>
            ))}
          </select>
        </Label>
        <div className="form-grid two">
          <Label name="Date label on packaging">
            <select value={label} onChange={(e) => setLabel(e.target.value)}>
              <option value="unknown">Unknown · cannot recommend</option>
              <option value="use_by">Use-by · safety date</option>
              <option value="best_before">Best-before · quality date</option>
            </select>
          </Label>
          {[
            {
              label: "Ingredient storage verified",
              state: storage,
              change: setStorage,
            },
            {
              label: "Ingredient condition check",
              state: condition,
              change: setCondition,
            },
          ].map((c) => (
            <Label key={c.label} name={c.label}>
              <select
                value={c.state == null ? "unknown" : String(c.state)}
                onChange={(e) => c.change(value(e.target.value))}
              >
                <option value="unknown">Unknown / no evidence</option>
                <option value="true">Passed — staff attestation</option>
                <option value="false">Failed / unsafe</option>
              </select>
            </Label>
          ))}
          <Label name="Inventory reviewing staff">
            <input value={staff} onChange={(e) => setStaff(e.target.value)} />
          </Label>
          <Label name="Inventory procedure reference">
            <input
              value={procedure}
              onChange={(e) => setProcedure(e.target.value)}
            />
          </Label>
        </div>
        <button
          className="button secondary"
          disabled={working || !staff.trim() || !procedure.trim()}
          onClick={save}
        >
          Save ingredient review for {asOf}
        </button>
      </details>
      <Label name="Recipe portions to plan">
        <input
          type="number"
          min={1}
          max={100000}
          step={1}
          value={portions}
          onChange={(e) => setPortions(Number(e.target.value))}
        />
      </Label>
      {!data ? (
        <Empty>Checking ingredient evidence…</Empty>
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <caption>Inventory eligibility for this planning date</caption>
              <thead>
                <tr>
                  <th>Ingredient / raw stock</th>
                  <th>Date label</th>
                  <th>Eligibility</th>
                </tr>
              </thead>
              <tbody>
                {data.inventory.map((i) => (
                  <tr key={i.id}>
                    <td>
                      {i.ingredient} · {kg(i.quantity_kg)}
                      <small>
                        {i.id} · {i.source}
                      </small>
                    </td>
                    <td>
                      {titleCase(i.label_kind)} · {i.expiry_date}
                      <small>{i.date_meaning}</small>
                    </td>
                    <td>
                      <Badge tone={i.recipe_eligible ? "green" : "amber"}>
                        {i.recipe_eligible
                          ? "Eligible for planning"
                          : "Excluded"}
                      </Badge>
                      {i.recipe_blockers.map((b) => (
                        <small key={b}>{b}</small>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.recipes.length === 0 && (
            <Empty>
              No eligible near-date ingredients yet. Review label type, storage
              and condition above. Expired or unsafe stock cannot be
              recommended.
            </Empty>
          )}
          {data.recipes.map((r) => (
            <article className="circular-result" key={r.id}>
              <Badge tone="amber">{titleCase(r.status)}</Badge>
              <h3>
                {r.dish} · {r.portions} portions
              </h3>
              <p>{r.label}</p>
              <p className="small muted">{r.method}</p>
              <p className="small">
                Near use-by inventory planned: {kg(r.near_use_by_usage_raw_kg)}{" "}
                raw. Declared recipe allergens:{" "}
                {r.allergens.join(", ") ||
                  "none in template; check every purchased ingredient"}
                .
              </p>
              <div className="table-scroll">
                <table>
                  <caption>{r.dish}: raw ingredient requirements</caption>
                  <thead>
                    <tr>
                      <th>Ingredient</th>
                      <th>Required raw kg</th>
                      <th>Eligible stock kg</th>
                      <th>Use raw kg</th>
                      <th>Shortage kg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.ingredients.map((i) => (
                      <tr key={i.ingredient}>
                        <td>
                          {i.ingredient}
                          <small>
                            {i.batch_allocations
                              .map(
                                (a) =>
                                  `${a.batch_id}: ${kg(a.use_raw_kg)} ${a.source}`,
                              )
                              .join(" · ") || "Verified procurement required"}
                          </small>
                        </td>
                        <td>{kg(i.required_raw_kg, 2)}</td>
                        <td>{kg(i.eligible_available_raw_kg, 2)}</td>
                        <td>{kg(i.planned_usage_raw_kg, 2)}</td>
                        <td>{kg(i.shortage_raw_kg, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="small muted">
                {r.allocation_note} Cooked yield is unknown.
              </p>
            </article>
          ))}
          {data.excluded_recipes.length > 0 && (
            <details className="mt-4">
              <summary>Recipes excluded by ingredient evidence</summary>
              {data.excluded_recipes.map((r) => (
                <p className="small muted" key={r.dish}>
                  {r.dish}: {r.ingredients.join(", ")}. {r.reason}
                </p>
              ))}
            </details>
          )}
          <p className="notice mt-4">
            {data.units} {data.caveat}
          </p>
        </>
      )}
    </Card>
  );
}
