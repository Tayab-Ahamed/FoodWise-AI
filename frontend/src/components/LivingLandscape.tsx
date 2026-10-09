import { useState } from "react";
import { ArrowUpRight, Pause, Play } from "lucide-react";
import type { Totals } from "../types";
import { kg } from "./Common";

export default function LivingLandscape({
  totals,
  onNavigate,
}: {
  totals: Totals;
  onNavigate: (page: string) => void;
}) {
  const [selected, setSelected] = useState(0),
    [paused, setPaused] = useState(false);
  const stops = [
    {
      name: "Prepare",
      value: totals.prepared_kg,
      title: "Start with a thoughtful quantity.",
      description:
        "Recorded preparation covers each meal service and can include reused food. Forecast served demand using attendance, then compare surplus and shortage before approving a plan.",
      path: "plan",
      action: "Explore preparation",
      className: "prepare",
    },
    {
      name: "Serve",
      value: totals.served_kg,
      title: "A meal is more than what gets eaten.",
      description:
        "Served food includes consumed food and plate waste. Staff record the whole meal so the next forecast protects availability.",
      path: "record",
      action: "Record a meal",
      className: "serve",
    },
    {
      name: "Review surplus",
      value: totals.untouched_surplus_kg,
      title: "Untouched still needs a review.",
      description:
        "Food never served needs documented handling and storage evidence. Reuse and human recovery require manager approval under the applicable procedure.",
      path: "recovery",
      action: "Review recovery",
      className: "review",
    },
    {
      name: "Separate plate waste",
      value: totals.plate_waste_kg,
      title: "Give each stream the right path.",
      description:
        "Plate waste is always blocked from human redistribution. Non-human recovery needs segregation and processor acceptance; every handoff here is simulated.",
      path: "recovery",
      action: "Inspect the safeguards",
      className: "separate",
    },
  ];
  const active = stops[selected];
  return (
    <section
      className={`living-landscape ${paused ? "motion-paused" : ""}`}
      aria-label="Explore the food journey"
    >
      <div className="landscape-art">
        <img
          src="/foodwise-living-landscape.png"
          width="1774"
          height="887"
          alt="Conceptual miniature landscape connecting a campus kitchen, dining table, greenhouse, compost beds and biogas vessel. It does not depict actual campus facilities."
          fetchPriority="high"
        />
        <div className="landscape-trail" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
        {stops.map((stop, index) => (
          <button
            key={stop.name}
            className={`landscape-stop ${stop.className} ${index === selected ? "selected" : ""}`}
            aria-pressed={index === selected}
            onClick={() => setSelected(index)}
            aria-label={`${stop.name}: ${kg(stop.value)}. Explore this food stream.`}
          >
            <span className="stop-dot" />
            <span>
              {stop.name}
              <b>{kg(stop.value)}</b>
            </span>
          </button>
        ))}
        <button
          className="landscape-motion"
          onClick={() => setPaused(!paused)}
          aria-label={
            paused ? "Play landscape motion" : "Pause landscape motion"
          }
        >
          {paused ? <Play size={14} /> : <Pause size={14} />}
        </button>
      </div>
      <div className="landscape-caption">
        <span>Concept landscape · select a food stream</span>
        <span>Recorded cooked mass · current date filters</span>
      </div>
      <div className="landscape-story" aria-live="polite" aria-atomic="true">
        <span className="story-index" aria-hidden="true">
          0{selected + 1}
        </span>
        <div>
          <h2>{active.title}</h2>
          <p>{active.description}</p>
          <button className="link" onClick={() => onNavigate(active.path)}>
            {active.action}
            <ArrowUpRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
