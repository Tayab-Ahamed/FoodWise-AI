import { useEffect, useRef, useState } from "react";
import { BrainCircuit, ArrowRight, Leaf } from "lucide-react";
import { api } from "../api";
import { Badge, kg, Label, num, titleCase } from "./Common";
import type { Forecast } from "../types";

type CoachItem = {
  item: string;
  status: string;
  message: string;
  sources?: string[];
  prior_service_count: number;
  recommendation_allowed?: boolean;
  shortage_reported_count?: number;
  estimate_kg?: number;
  recommended_kg?: number;
  range_low_kg?: number;
  range_high_kg?: number;
  evaluation_count?: number;
  training_service_count?: number;
  trained_through?: string;
  range_label?: string;
  beats_recent_baseline?: boolean;
  metrics?: { mae_kg: number };
  baseline_metrics?: { mae_kg: number };
  scenario_outcomes?: {
    expected_surplus_kg: number;
    expected_shortage_kg: number;
    shortage_frequency: number;
  };
};
type Coach = {
  id: string;
  items: CoachItem[];
  groq_status: string;
  briefing: { id: string; title: string; text: string }[];
  decision_boundary: string;
  created_at: string;
  dataset_version: number;
};
export default function AIPrepCoach({
  forecast,
  onApply,
  disabled,
  onReport,
}: {
  forecast: Forecast;
  onReport: (id: string | null) => void;
  onApply: (item: string, kg: number) => void;
  disabled: boolean;
}) {
  const [coach, setCoach] = useState<Coach | null>(null),
    [weight, setWeight] = useState(4),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [sharing, setSharing] = useState(false),
    [briefingOpen, setBriefingOpen] = useState(false);
  const request = useRef(0);
  async function train(useGroq = false) {
    const id = ++request.current;
    setBusy(true);
    setError("");
    onReport(null);
    try {
      const result = await api<Coach>("/intelligence/prepare", {
        forecast_id: forecast.id,
        shortage_weight: weight,
        use_groq: useGroq,
        share_aggregate_evidence: sharing,
      });
      if (request.current === id) {
        setCoach(result);
        onReport(result.id);
        if (useGroq) setBriefingOpen(true);
      }
    } catch (e) {
      if (request.current === id)
        setError(e instanceof Error ? e.message : "AI coach unavailable");
    } finally {
      if (request.current === id) setBusy(false);
    }
  }
  useEffect(() => {
    setCoach(null);
    void train();
    return () => {
      request.current++;
    };
  }, [forecast.id, weight]);
  return (
    <section className="ai-prep-coach" aria-labelledby="coach-title">
      <div className="coach-heading">
        <div>
          <p className="eyebrow">LEARN / PREVENT / SERVE WELL</p>
          <h2 id="coach-title">Your kitchen’s learning curve.</h2>
          <p>
            A local AI model learns served food per diner from earlier services,
            weekdays and events.
          </p>
        </div>
        <BrainCircuit size={34} strokeWidth={1.3} />
      </div>
      <div className="coach-controls">
        <Label name="Cost of shortage relative to surplus">
          <select
            value={weight}
            onChange={(e) => setWeight(Number(e.target.value))}
          >
            <option value={1}>Equal weight · 1×</option>
            <option value={4}>Protect availability · 4×</option>
            <option value={9}>Higher shortage penalty · 9×</option>
          </select>
        </Label>
        <span className="small muted">
          A scenario preference, not a measured financial cost. Changes the AI
          suggestion, never your approved plan.
        </span>
      </div>
      {busy && (
        <p role="status" className="small">
          Training and checking strictly earlier services…
        </p>
      )}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="coach-dishes">
        {coach?.items.map((item) => (
          <article key={item.item}>
            <div className="coach-dish-title">
              <h3>{item.item}</h3>
              <Leaf size={17} />
            </div>
            {item.status === "ready" ? (
              <>
                <span className="small">AI preparation suggestion</span>
                <strong className="coach-quantity">
                  {kg(item.recommended_kg!)}
                </strong>
                <p className="small">
                  Served-demand estimate {kg(item.estimate_kg!)}
                  <br />
                  Scenario range {kg(item.range_low_kg!)} –{" "}
                  {kg(item.range_high_kg!)}
                </p>
                <div className="coach-errors">
                  <span>
                    Model error <b>{num(item.metrics!.mae_kg, 2)} kg</b>
                  </span>
                  <span>
                    Recent baseline{" "}
                    <b>{num(item.baseline_metrics!.mae_kg, 2)} kg</b>
                  </span>
                </div>
                <Badge tone={item.beats_recent_baseline ? "green" : "amber"}>
                  {item.beats_recent_baseline
                    ? "Lower temporal error"
                    : "Baseline performs better"}
                </Badge>
                <p className="small">
                  Projected surplus{" "}
                  {kg(item.scenario_outcomes!.expected_surplus_kg)} · shortage{" "}
                  {num(item.scenario_outcomes!.expected_shortage_kg, 2)} kg
                  <br />
                  {num(item.scenario_outcomes!.shortage_frequency * 100)}% of
                  residual scenarios run short.
                </p>
                <button
                  className="button secondary compact"
                  disabled={
                    disabled || busy || item.recommendation_allowed === false
                  }
                  onClick={() => onApply(item.item, item.recommended_kg!)}
                >
                  Use suggestion for {item.item} <ArrowRight size={14} />
                </button>
                {item.recommendation_allowed === false && (
                  <p className="notice">
                    Reported shortages can hide unmet demand. Set a
                    manager-selected quantity; this AI suggestion cannot be
                    applied.
                  </p>
                )}
                <details>
                  <summary>Model evidence & limits</summary>
                  <p className="small">
                    Fixed ridge regression, last {item.training_service_count}{" "}
                    training services, trained through {item.trained_through}.
                    Tested on {item.evaluation_count} later services, each with
                    a separate earlier training set. MAE measures served kg with
                    actual attendance known. Source:{" "}
                    {item.sources?.map(titleCase).join(", ")}.
                  </p>
                  <p className="small">
                    {item.range_label}. {item.message}
                  </p>
                </details>
              </>
            ) : (
              <>
                <Badge tone="amber">Collect history</Badge>
                <p>{item.message}</p>
                <p className="small">
                  {item.prior_service_count} prior services available.
                </p>
              </>
            )}
          </article>
        ))}
      </div>
      <div className="groq-briefing">
        <div>
          <p className="eyebrow">GROQ / EVIDENCE BRIEFING</p>
          <h3>What deserves attention before service?</h3>
          <p className="small">
            Groq prioritizes these model results. Quantities, uncertainty and
            safety rules remain calculated by the backend.
          </p>
        </div>
        <div>
          <label className="sharing-check">
            <input
              type="checkbox"
              checked={sharing}
              onChange={(e) => setSharing(e.target.checked)}
            />
            Share aggregate model results with Groq
          </label>
          <button
            className="button compact"
            disabled={!sharing || busy || disabled}
            onClick={() => void train(true)}
          >
            Brief me with Groq <ArrowRight size={15} />
          </button>
        </div>
      </div>
      {briefingOpen && coach && (
        <div className="coach-brief">
          <p role="status">
            {coach.groq_status === "provider_curated"
              ? "Groq prioritized these validated results."
              : coach.groq_status === "not_configured"
                ? "Groq is not connected. Add GROQ_API_KEY and GROQ_MODEL to the backend .env and restart. Showing the local evidence briefing."
                : "Groq could not return valid evidence. Showing the local briefing."}
          </p>
          {coach.briefing.map((c) => (
            <p className="small" key={c.id}>
              {c.text}
            </p>
          ))}
        </div>
      )}
      <p className="coach-boundary small">
        {coach?.decision_boundary ??
          "AI proposes. Managers decide. Food-safety review remains a separate requirement."}
      </p>
    </section>
  );
}
