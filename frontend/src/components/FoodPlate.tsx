import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import type { Totals } from "../types";
import { kg, num } from "./Common";

/** The plate is a chart of server-calculated mass, not a safety or impact score. */
export default function FoodPlate({ totals }: { totals: Totals }) {
  const [selected, setSelected] = useState<number | null>(null);
  const portions = [
    {
      name: "Consumed",
      value: totals.consumed_kg,
      color: "#315848",
      detail: "Food eaten by diners.",
    },
    {
      name: "Untouched",
      value: totals.untouched_surplus_kg,
      color: "#e8bd49",
      detail: "Never served. Review and manager approval required.",
    },
    {
      name: "Plate waste",
      value: totals.plate_waste_kg,
      color: "#ce563e",
      detail: "Already served. Never eligible for human redistribution.",
    },
  ];
  const active = selected == null ? null : portions[selected];
  return (
    <figure
      className="food-plate-figure"
      aria-label="Prepared food mass accounting"
    >
      <div className="plate-caption">
        <span>THE WHOLE PICTURE</span>
        <span>COOKED KG</span>
      </div>
      <div className="plate-stage">
        <div className="plate-rim">
          <div className="plate-chart" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart accessibilityLayer={false}>
                <Pie
                  data={portions}
                  dataKey="value"
                  innerRadius="72%"
                  outerRadius="96%"
                  startAngle={90}
                  endAngle={-270}
                  stroke="#fbfaf4"
                  strokeWidth={4}
                  isAnimationActive={false}
                >
                  {portions.map((p, index) => (
                    <Cell
                      key={p.name}
                      fill={p.color}
                      opacity={
                        selected == null || selected === index ? 1 : 0.25
                      }
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="plate-center" aria-live="polite" aria-atomic="true">
            <span>{active?.name ?? "Food prepared"}</span>
            <strong>{num(active?.value ?? totals.prepared_kg)}</strong>
            <small>kilograms</small>
            <div className="plate-rule" />
            <p>
              {active?.detail ??
                `${num(totals.untouched_pct)}% remained untouched`}
            </p>
          </div>
        </div>
        <span className="plate-annotation">
          Every kilogram
          <br />
          <em>has a story.</em>
        </span>
      </div>
      <figcaption className="plate-legend" aria-label="Explore food accounting">
        {portions.map((p, index) => (
          <button
            key={p.name}
            aria-pressed={selected === index}
            onClick={() => setSelected(selected === index ? null : index)}
          >
            <span>
              <i style={{ background: p.color }} />
              {p.name}
            </span>
            <b>{kg(p.value)}</b>
          </button>
        ))}
      </figcaption>
    </figure>
  );
}
