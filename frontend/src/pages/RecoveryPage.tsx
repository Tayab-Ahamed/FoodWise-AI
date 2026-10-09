import { useEffect, useState } from "react";
import { ShieldCheck, Truck } from "lucide-react";
import { api } from "../api";
import type { Audit, Batch, Handoff, MealRecord, Run, Health } from "../types";
import { Badge, Card, Empty, kg, Label, titleCase } from "../components/Common";

import { DinnerReuse, BiogasPanel } from "../components/CircularKitchen";
import DispatchDesk from "../components/DispatchDesk";

const checkNames: Record<string, string> = {
  handling_log_complete: "Handling log complete",
  time_temperature_review_passed: "Time / temperature review passed",
  storage_verified: "Storage verified",
  contamination_check_passed: "Contamination check passed",
  label_allergen_info_present: "Label and allergen information present",
};
function ReviewPanel({
  batch,
  run,
  busy,
  onSaved,
  practice,
}: {
  batch: Batch;
  run: Run;
  busy: boolean;
  onSaved: () => void;
  practice: boolean;
}) {
  const [checks, setChecks] = useState(batch.checks),
    [reviewer, setReviewer] = useState(batch.reviewer ?? ""),
    [manager, setManager] = useState(""),
    [route, setRoute] = useState("human_redistribution"),
    [partner, setPartner] = useState("demo-community"),
    [quantity, setQuantity] = useState(batch.remaining_kg),
    [receipt, setReceipt] = useState<Handoff | null>(null);
  const [key, setKey] = useState(crypto.randomUUID());
  const edited =
    JSON.stringify(checks) !== JSON.stringify(batch.checks) ||
    reviewer !== (batch.reviewer ?? "");
  const saveReview = async () => {
    const result = await run(
      () =>
        api<Batch>(
          `/recovery/batches/${batch.id}/review`,
          { ...checks, reviewer },
          "PATCH",
        ),
      "Review recorded. Any prior approval has been cleared.",
    );
    if (result) onSaved();
  };
  const approve = async () => {
    const result = await run(
      () =>
        api<Batch>(`/recovery/batches/${batch.id}/approve`, {
          approved_by: manager,
        }),
      "Manager approval recorded. Recipient acceptance remains required for real dispatch.",
    );
    if (result) onSaved();
  };
  const handoff = async () => {
    const result = await run(() =>
      api<Handoff>(`/recovery/batches/${batch.id}/handoff`, {
        route,
        partner_id: partner,
        quantity_kg: quantity,
        idempotency_key: key,
      }),
    );
    if (result) {
      setReceipt(result);
      onSaved();
    }
  };
  const changeRoute = (value: string) => {
    setRoute(value);
    setPartner(
      value === "human_redistribution"
        ? "demo-community"
        : value === "compost"
          ? "demo-compost"
          : "demo-biogas",
    );
    setKey(crypto.randomUUID());
    setReceipt(null);
  };
  return (
    <div className="space-y-6">
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">DOCUMENTED POLICY REVIEW</p>
            <h2>{titleCase(batch.origin)}</h2>
          </div>
          <ShieldCheck size={24} />
        </div>
        <div className="flex gap-2 flex-wrap mb-4">
          <Badge
            tone={
              batch.state === "blocked"
                ? "red"
                : batch.approved_at
                  ? "green"
                  : "amber"
            }
          >
            {titleCase(batch.state)}
          </Badge>
          <Badge tone="gray">
            {kg(batch.quantity_kg)} · {batch.record_id}
          </Badge>
        </div>
        <p className="notice">{batch.reason}</p>
        {batch.origin === "plate_waste" && (
          <p className="permanent-block">
            Plate waste · No human redistribution, regardless of checks or
            approval.
          </p>
        )}
        <div className="review-checks">
          {Object.entries(checkNames).map(([key, label]) => (
            <Label key={key} name={label}>
              <select
                value={
                  checks[key] === null
                    ? "unknown"
                    : checks[key]
                      ? "true"
                      : "false"
                }
                onChange={(e) =>
                  setChecks({
                    ...checks,
                    [key]:
                      e.target.value === "unknown"
                        ? null
                        : e.target.value === "true",
                  })
                }
              >
                <option value="unknown">Unknown / no evidence</option>
                <option value="true">Passed — staff attestation</option>
                <option value="false">Failed</option>
              </select>
            </Label>
          ))}
        </div>
        <Label name="Reviewing staff member">
          <input
            value={reviewer}
            maxLength={100}
            onChange={(e) => setReviewer(e.target.value)}
          />
        </Label>
        <button
          className="button secondary"
          disabled={busy || !reviewer.trim()}
          onClick={saveReview}
        >
          Save documented review
        </button>
        {edited && (
          <p className="small muted mt-3">
            Unsaved review edits. Save before requesting approval. Saving review
            evidence invalidates prior approval.
          </p>
        )}
        <div className="approval-divider">
          <Label name="Approving manager">
            <input
              value={manager}
              onChange={(e) => setManager(e.target.value)}
              maxLength={100}
            />
          </Label>
          <button
            className="button"
            disabled={busy || edited || !manager.trim()}
            onClick={approve}
          >
            Request manager approval
          </button>
          <p className="small muted mt-3">
            The backend re-evaluates eligibility on every request. This workflow
            records attestations under a kitchen procedure; it does not certify
            food safety.
          </p>
          {batch.approved_by && (
            <p className="success">
              Approved by {batch.approved_by} ·{" "}
              {new Date(batch.approved_at!).toLocaleString()}
            </p>
          )}
        </div>
      </Card>
      {practice && (
        <Card>
          <div className="section-heading">
            <div>
              <p className="eyebrow">SIMULATED RECOVERY ONLY</p>
              <h2>Record a demo handoff</h2>
            </div>
            <Truck size={24} />
          </div>
          <p className="muted small">
            {kg(batch.handed_off_kg)} recorded · {kg(batch.remaining_kg)}{" "}
            remaining. Processor routes require declared demo acceptance for the
            material.
          </p>
          <div className="form-grid two">
            <Label name="Disposition route">
              <select
                value={route}
                onChange={(e) => changeRoute(e.target.value)}
              >
                <option value="human_redistribution">
                  Human redistribution · simulated
                </option>
                <option value="compost">Compost · simulated</option>
                <option value="biogas">Biogas · simulated</option>
              </select>
            </Label>
            <Label name="Demo partner">
              <select
                value={partner}
                onChange={(e) => {
                  setPartner(e.target.value);
                  setKey(crypto.randomUUID());
                  setReceipt(null);
                }}
              >
                {route === "human_redistribution" ? (
                  <option value="demo-community">Demo community handoff</option>
                ) : route === "compost" ? (
                  <>
                    <option value="demo-compost">Demo compost processor</option>
                    <option value="demo-unconfirmed">
                      Demo processor — acceptance unknown
                    </option>
                  </>
                ) : (
                  <option value="demo-biogas">Demo biogas processor</option>
                )}
              </select>
            </Label>
            <Label name="Handoff quantity (cooked kg)">
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={quantity}
                onChange={(e) => {
                  setQuantity(Number(e.target.value));
                  setKey(crypto.randomUUID());
                  setReceipt(null);
                }}
              />
            </Label>
          </div>
          <button
            className="button"
            disabled={busy || quantity <= 0}
            onClick={handoff}
          >
            {receipt
              ? "Retry same handoff (idempotent)"
              : "Record simulated handoff"}
          </button>
          {receipt && (
            <p className="success mt-3">
              {receipt.duplicate
                ? "Duplicate request returned the same receipt."
                : "Simulated receipt recorded."}{" "}
              {receipt.id} · {kg(receipt.quantity_kg)}
            </p>
          )}
          {batch.handoffs.map((h) => (
            <div className="inventory-row" key={h.id}>
              <b>
                {titleCase(h.route)} · {kg(h.quantity_kg)}
              </b>
              <p>
                {h.partner_id} · {new Date(h.recorded_at).toLocaleString()}
              </p>
              <Badge tone="blue">
                {h.simulated ? "Simulated handoff" : "Recorded handoff"}
              </Badge>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

export default function RecoveryPage({
  initialRecordId,
  run,
  busy,
  refresh,
  onSaved,
}: {
  run: Run;
  busy: boolean;
  refresh: number;
  onSaved: () => void;
  initialRecordId: string;
}) {
  const [rows, setRows] = useState<MealRecord[]>([]),
    [batches, setBatches] = useState<Batch[]>([]),
    [audit, setAudit] = useState<Audit[]>([]),
    [recordId, setRecordId] = useState(initialRecordId || "DEMO-100"),
    [origin, setOrigin] = useState("untouched_surplus"),
    [quantity, setQuantity] = useState(10),
    [selected, setSelected] = useState("");
  const [practice, setPractice] = useState(false);
  useEffect(() => {
    api<Health>("/health")
      .then((h) => setPractice(h.practice_workspace))
      .catch(() => setPractice(false));
  }, []);
  useEffect(() => {
    void run(async () => {
      const [r, b, a] = await Promise.all([
        api<MealRecord[]>("/records"),
        api<Batch[]>("/recovery/batches"),
        api<Audit[]>("/audit"),
      ]);
      setRows(r);
      setBatches(b);
      setAudit(a);
      setSelected((s) => (b.some((v) => v.id === s) ? s : (b[0]?.id ?? "")));
      setRecordId((id) =>
        r.some((v) => v.record_id === id)
          ? id
          : (r[r.length - 1]?.record_id ?? ""),
      );
    });
  }, [refresh]);
  const create = async () => {
    const result = await run(
      () =>
        api<Batch>("/recovery/batches", {
          record_id: recordId,
          origin,
          quantity_kg: quantity,
        }),
      "Recovery batch allocated. Documented review is required.",
    );
    if (result) {
      setSelected(result.id);
      onSaved();
    }
  };
  const selectedBatch = batches.find((b) => b.id === selected);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">04 / REVIEW BEFORE RECOVERY</p>
          <h1>
            A second chance.
            <br />
            <em>With care.</em>
          </h1>
          <p className="muted">
            Origin alone never establishes eligibility. Every handoff here is
            simulated.
          </p>
        </div>
        <Badge tone="amber">Policy workflow · not certification</Badge>
      </div>
      <div className="safety-path" aria-label="Recovery workflow">
        <span>
          <b>01</b> Allocate a batch
        </span>
        <span aria-hidden="true">→</span>
        <span>
          <b>02</b> Document the review
        </span>
        <span aria-hidden="true">→</span>
        <span>
          <b>03</b> Manager approval
        </span>
        <span aria-hidden="true">→</span>
        <span>
          <b>04</b> Simulate a handoff
        </span>
      </div>
      <div className="recovery-grid">
        <div className="space-y-6">
          <Card>
            <h2>Allocate a food batch</h2>
            <Label name="Linked meal record">
              <select
                value={recordId}
                onChange={(e) => setRecordId(e.target.value)}
              >
                {rows.map((r) => (
                  <option key={r.record_id} value={r.record_id}>
                    {r.record_id} · {r.item} · {r.date}
                  </option>
                ))}
              </select>
            </Label>
            {rows
              .filter((r) => r.record_id === recordId)
              .map((r) => (
                <p className="small muted" key={r.record_id}>
                  Recorded untouched: {kg(r.untouched_surplus_kg)} · plate
                  waste: {kg(r.plate_waste_kg)}. Existing allocations reduce
                  availability.
                </p>
              ))}
            <Label name="Documented origin">
              <select
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
              >
                <option value="untouched_surplus">
                  Untouched surplus — review required
                </option>
                <option value="plate_waste">
                  Plate waste — no human redistribution
                </option>
                <option value="unknown">Unknown — blocked</option>
              </select>
            </Label>
            <Label name="Allocate cooked kg">
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
              />
            </Label>
            <button
              className="button w-full"
              disabled={busy || !recordId || quantity <= 0}
              onClick={create}
            >
              Create review batch
            </button>
          </Card>
          <Card>
            <h2>Review queue</h2>
            {batches.length === 0 ? (
              <Empty>No recovery batches yet.</Empty>
            ) : (
              batches.map((b) => (
                <button
                  className={`batch-selector ${b.id === selected ? "selected" : ""}`}
                  aria-pressed={b.id === selected}
                  key={b.id}
                  onClick={() => setSelected(b.id)}
                >
                  <b>
                    {titleCase(b.origin)} · {kg(b.quantity_kg)}
                  </b>
                  <span>{b.record_id}</span>
                  <Badge
                    tone={
                      b.state === "blocked"
                        ? "red"
                        : b.approved_at
                          ? "green"
                          : "amber"
                    }
                  >
                    {titleCase(b.state)}
                  </Badge>
                </button>
              ))
            )}
          </Card>
          <Card>
            <p className="eyebrow">DECISION TRAIL</p>
            <h2>Recent activity</h2>
            <div className="activity-list">
              {audit.slice(0, 15).map((a) => (
                <details key={a.id}>
                  <summary>
                    <b>{titleCase(a.action)}</b>
                    <small>{new Date(a.timestamp).toLocaleString()}</small>
                  </summary>
                  <pre>{JSON.stringify(a.details, null, 2)}</pre>
                </details>
              ))}
              {audit.length === 0 && (
                <p className="muted small mt-3">
                  Saved decisions will appear here.
                </p>
              )}
            </div>
          </Card>
        </div>
        {selectedBatch ? (
          <div className="space-y-6">
            <ReviewPanel
              practice={practice}
              key={`${selectedBatch.id}-${selectedBatch.reviewed_at ?? ""}`}
              batch={selectedBatch}
              run={run}
              busy={busy}
              onSaved={onSaved}
            />
            <DinnerReuse
              key={selectedBatch.id}
              batch={selectedBatch}
              record={rows.find((r) => r.record_id === selectedBatch.record_id)}
              run={run}
              busy={busy}
              refresh={refresh}
              onSaved={onSaved}
            />
            <BiogasPanel
              practice={practice}
              key={`bio-${selectedBatch.id}`}
              batch={selectedBatch}
              run={run}
              busy={busy}
              onSaved={onSaved}
            />
          </div>
        ) : (
          <Card>
            <Empty>
              Choose a batch to document handling,
              <br />
              review eligibility, and record a simulated disposition.
            </Empty>
          </Card>
        )}
      </div>
      <DispatchDesk
        batches={batches}
        refresh={refresh}
        run={run}
        onSaved={onSaved}
      />
    </>
  );
}
