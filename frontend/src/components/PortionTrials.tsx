import { useEffect, useState } from "react";
import { api } from "../api";
import type { Catalog, Run, TrialEvaluation, TrialInput } from "../types";
import { ActionLink, Badge, Card, Empty, Label, num } from "./Common";

const today = () => new Date().toLocaleDateString("en-CA");
const initial = (): TrialInput => ({
  item: "Rice",
  meal: "lunch",
  baseline_start: "2026-09-25",
  baseline_end: "2026-10-08",
  trial_start: today(),
  trial_end: today(),
  record_scope: "actual",
  source_filter: "all",
  mode: "planned_trial",
  intervention: "smaller_first_serving_optional_seconds",
  approved_by: "Demo manager",
  notes: "",
});

export default function PortionTrials({
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
  const [input, setInput] = useState<TrialInput>(initial);
  const [trials, setTrials] = useState<TrialEvaluation[]>([]),
    [catalog, setCatalog] = useState<Catalog | null>(null),
    [selected, setSelected] = useState("");
  useEffect(() => {
    void run(async () => {
      const [all, c] = await Promise.all([
        api<TrialEvaluation[]>("/trials"),
        api<Catalog>("/catalog"),
      ]);
      setTrials(all);
      setCatalog(c);
      setSelected((id) =>
        all.some((t) => t.trial.id === id) ? id : (all[0]?.trial.id ?? ""),
      );
    });
  }, [refresh]);
  const save = async () => {
    const result = await run(
      () => api<TrialEvaluation>("/trials", input),
      "Portion measurement protocol saved with manager approval.",
    );
    if (result) {
      setTrials([result, ...trials]);
      setSelected(result.trial.id);
    }
  };
  const change = (fields: Partial<TrialInput>) =>
    setInput({ ...input, ...fields });
  const chosen = trials.find((t) => t.trial.id === selected);
  return (
    <Card className="mt-6">
      <div className="section-heading">
        <div>
          <p className="eyebrow">MEASURE PLATE WASTE SEPARATELY</p>
          <h2>Portion trials &amp; comparisons</h2>
        </div>
        <Badge tone="blue">Evidence before impact claims</Badge>
      </div>
      <p className="muted">
        Register a smaller-first-serving trial with optional seconds, or inspect
        a labeled historical comparison. We compare recorded mass per diner,
        including consumption and service exposure.
      </p>
      <details className="research-drawer">
        <summary>
          <span>
            <b>Set up a measurement protocol</b>
            <small>
              Define the dish, comparison windows and how you will measure a
              portion trial.
            </small>
          </span>
        </summary>
        <button
          className="link mt-3"
          onClick={() =>
            setInput({
              ...initial(),
              mode: "retrospective_comparison",
              record_scope: "history",
              source_filter: "synthetic",
              baseline_start: "2026-07-11",
              baseline_end: "2026-08-20",
              trial_start: "2026-08-21",
              trial_end: "2026-10-08",
              notes:
                "Synthetic illustration only. No portion intervention was performed.",
            })
          }
        >
          Load synthetic comparison settings
        </button>
        <div className="form-grid mt-4">
          <Label name="Measurement mode">
            <select
              value={input.mode}
              onChange={(e) =>
                change(
                  e.target.value === "planned_trial"
                    ? {
                        mode: e.target.value,
                        record_scope: "actual",
                        trial_start: today(),
                        trial_end: today(),
                      }
                    : { mode: e.target.value },
                )
              }
            >
              <option value="planned_trial">
                Future trial · actual meal logs
              </option>
              <option value="retrospective_comparison">
                Retrospective · no intervention claim
              </option>
            </select>
          </Label>
          <Label name="Trial dish">
            <input
              value={input.item}
              list="trial-dishes"
              onChange={(e) => change({ item: e.target.value })}
            />
            <datalist id="trial-dishes">
              {catalog?.items.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </Label>
          <Label name="Trial meal">
            <select
              value={input.meal}
              onChange={(e) => change({ meal: e.target.value })}
            >
              {["breakfast", "lunch", "dinner"].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </Label>
          <Label name="Intervention to investigate">
            <select
              value={input.intervention}
              onChange={(e) => change({ intervention: e.target.value })}
            >
              <option value="smaller_first_serving_optional_seconds">
                Smaller first serving · optional seconds
              </option>
              <option value="information_only">Information / signs only</option>
            </select>
          </Label>
          <Label name="Baseline starts">
            <input
              type="date"
              value={input.baseline_start}
              onChange={(e) => change({ baseline_start: e.target.value })}
            />
          </Label>
          <Label name="Baseline ends">
            <input
              type="date"
              value={input.baseline_end}
              onChange={(e) => change({ baseline_end: e.target.value })}
            />
          </Label>
          <Label name="Comparison / trial starts">
            <input
              type="date"
              value={input.trial_start}
              onChange={(e) => change({ trial_start: e.target.value })}
            />
          </Label>
          <Label name="Comparison / trial ends">
            <input
              type="date"
              value={input.trial_end}
              onChange={(e) => change({ trial_end: e.target.value })}
            />
          </Label>
          <Label name="Meal record scope">
            <select
              value={input.record_scope}
              disabled={input.mode === "planned_trial"}
              onChange={(e) => change({ record_scope: e.target.value })}
            >
              <option value="actual">Recorded actual meals</option>
              <option value="history">Historical dataset</option>
            </select>
          </Label>
          <Label name="Source filter">
            <select
              value={input.source_filter}
              onChange={(e) => change({ source_filter: e.target.value })}
            >
              {["all", "measured", "synthetic", "user_provided_unverified"].map(
                (s) => (
                  <option key={s}>{s}</option>
                ),
              )}
            </select>
          </Label>
          <Label name="Trial approving manager">
            <input
              maxLength={100}
              value={input.approved_by}
              onChange={(e) => change({ approved_by: e.target.value })}
            />
          </Label>
        </div>
        <Label
          name="Protocol notes"
          hint="Record how optional seconds and consistent weighing will be maintained."
        >
          <textarea
            rows={2}
            maxLength={1000}
            value={input.notes}
            onChange={(e) => change({ notes: e.target.value })}
          />
        </Label>
        <button
          className="button secondary mt-4"
          disabled={busy || !input.approved_by.trim() || !input.item.trim()}
          onClick={save}
        >
          Save approved measurement protocol
        </button>
      </details>
      {trials.length === 0 ? (
        <Empty>
          No measurement protocols yet. Actual logs will populate approved trial
          windows.
        </Empty>
      ) : (
        <div className="mt-6">
          <Label name="Saved measurement protocol">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {trials.map((r) => (
                <option key={r.trial.id} value={r.trial.id}>
                  {r.trial.item} · {r.trial.mode.replaceAll("_", " ")} ·{" "}
                  {r.trial.id}
                </option>
              ))}
            </select>
          </Label>
          {chosen && (
            <>
              <div className="section-heading">
                <h3>
                  {chosen.trial.item} · {chosen.trial.meal}
                </h3>
                <Badge
                  tone={
                    chosen.status === "comparison_available" ? "green" : "gray"
                  }
                >
                  {chosen.status.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="small muted">
                Approved by {chosen.trial.approved_by} · dataset version{" "}
                {chosen.dataset_version}. {chosen.label} {chosen.trial.notes}
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Phase</th>
                      <th>Services / diners</th>
                      <th>Source labels</th>
                      <th>Plate waste g/diner</th>
                      <th>Consumed g/diner</th>
                      <th>Served g/diner</th>
                      <th>Untouched g/diner</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["Baseline", chosen.baseline],
                      ["Comparison", chosen.comparison],
                    ].map(([label, phase]) => {
                      const p = phase as TrialEvaluation["baseline"];
                      return (
                        <tr key={label as string}>
                          <td>
                            <ActionLink
                              onClick={() => onEvidence(p.evidence_ids)}
                            >
                              {label as string}
                            </ActionLink>
                          </td>
                          <td>
                            {p.services} / {p.diners}
                          </td>
                          <td>{p.sources.join(" · ") || "No observations"}</td>
                          {[
                            "plate_waste_kg",
                            "consumed_kg",
                            "served_kg",
                            "untouched_surplus_kg",
                          ].map((key) => (
                            <td key={key}>{num(p.per_diner_g[key], 2)}</td>
                          ))}
                        </tr>
                      );
                    })}
                    {chosen.change_per_diner_g && (
                      <tr>
                        <td>Observed change</td>
                        <td>Comparison − baseline</td>
                        <td>No causal attribution</td>
                        {[
                          "plate_waste_kg",
                          "consumed_kg",
                          "served_kg",
                          "untouched_surplus_kg",
                        ].map((key) => (
                          <td key={key}>
                            {num(chosen.change_per_diner_g?.[key], 2)}
                          </td>
                        ))}
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {chosen.status !== "comparison_available" && (
                <p className="notice">
                  Collect at least {chosen.minimum_services_per_phase} distinct
                  services in each phase before a difference is displayed. This
                  minimum is a demo rule, not a power analysis.
                </p>
              )}
              <p className="small muted mt-4">
                Baseline events:{" "}
                {Object.entries(chosen.baseline.event_counts)
                  .map(([e, n]) => `${e}: ${n}`)
                  .join(" · ")}
                . Comparison events:{" "}
                {Object.entries(chosen.comparison.event_counts)
                  .map(([e, n]) => `${e}: ${n}`)
                  .join(" · ")}
                . Confirmed shortages: {chosen.baseline.shortage_reported_count}{" "}
                / {chosen.comparison.shortage_reported_count}; unknown flags:{" "}
                {chosen.baseline.shortage_unknown_count} /{" "}
                {chosen.comparison.shortage_unknown_count} (baseline /
                comparison).
              </p>
              {!!chosen.excluded_duplicate_ids.length && (
                <p className="notice">
                  Ambiguous duplicate services were excluded:{" "}
                  {chosen.excluded_duplicate_ids.join(", ")}. Resolve the
                  records before drawing a comparison.
                </p>
              )}
              <p className="small muted mt-4">{chosen.caveat}</p>
            </>
          )}
        </div>
      )}
    </Card>
  );
}
