import { useEffect, useState } from "react";
import { MapPin, Truck } from "lucide-react";
import { api } from "../api";
import type { Batch, Run } from "../types";
import type { Recipient } from "./RecipientNetwork";
import { Badge, kg, Label } from "./Common";

type Acceptance = {
  id: string;
  batch_id: string;
  recipient_id: string;
  route: string;
  quantity_kg: number;
  expires_at: string;
  contact_person: string;
  remaining_kg: number;
  expired: boolean;
};
export default function DispatchDesk({
  batches,
  refresh,
  run,
  onSaved,
}: {
  batches: Batch[];
  refresh: number;
  run: Run;
  onSaved: () => void;
}) {
  const [recipients, setRecipients] = useState<Recipient[]>([]),
    [acceptances, setAcceptances] = useState<Acceptance[]>([]);
  const [receipts, setReceipts] = useState<
    {
      id: string;
      quantity_kg: number;
      recorded_at: string;
      recipient_snapshot: Recipient;
      route: string;
      dispatch_intent: { receipt_reference: string; received_by: string };
    }[]
  >([]);
  const [recipient, setRecipient] = useState(""),
    [batch, setBatch] = useState(""),
    [route, setRoute] = useState("human_redistribution");
  const [quantity, setQuantity] = useState(1),
    [contact, setContact] = useState(""),
    [staff, setStaff] = useState(""),
    [evidence, setEvidence] = useState("");
  const [expiry, setExpiry] = useState(""),
    [acceptance, setAcceptance] = useState("");
  const [receivedBy, setReceivedBy] = useState(""),
    [reference, setReference] = useState(""),
    [occurred, setOccurred] = useState(false),
    [segregated, setSegregated] = useState(false);
  const [key, setKey] = useState(crypto.randomUUID()),
    [busy, setBusy] = useState(false),
    [receipt, setReceipt] = useState<{
      id: string;
      quantity_kg: number;
    } | null>(null);
  useEffect(() => {
    let alive = true;
    void run(async () => {
      const [directory, approvals, ledger] = await Promise.all([
        api<{ saved: Recipient[] }>("/recipients/directory"),
        api<Acceptance[]>("/recipients/acceptances"),
        api<typeof receipts>("/recipients/dispatch"),
      ]);
      if (alive) {
        setRecipients(directory.saved);
        setAcceptances(approvals);
        setReceipts(ledger);
      }
    });
    return () => {
      alive = false;
    };
  }, [refresh]);
  async function saveAcceptance(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const result = await run(
      () =>
        api<Acceptance>("/recipients/acceptances", {
          recipient_id: recipient,
          batch_id: batch,
          route,
          quantity_kg: quantity,
          confirmed_by: staff,
          contact_person: contact,
          evidence,
          expires_at: new Date(expiry).toISOString(),
        }),
      "Recipient acceptance recorded for this batch. Review and manager approval still apply.",
    );
    if (result) {
      setAcceptance(result.id);
      onSaved();
    }
    setBusy(false);
  }
  async function dispatch(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const result = await run(
      () =>
        api<{ id: string; quantity_kg: number }>("/recipients/dispatch", {
          acceptance_id: acceptance,
          quantity_kg: quantity,
          received_by: receivedBy,
          receipt_reference: reference,
          handoff_occurred: occurred,
          segregation_confirmed: segregated,
          idempotency_key: key,
        }),
      "Completed handoff recorded against the measured food ledger.",
    );
    if (result) {
      setReceipt(result);
      setKey(crypto.randomUUID());
      setOccurred(false);
      setSegregated(false);
      onSaved();
    }
    setBusy(false);
  }
  const changeReceipt = () => {
    setKey(crypto.randomUUID());
    setReceipt(null);
  };
  return (
    <section className="dispatch-desk">
      <div className="dispatch-heading">
        <div>
          <p className="eyebrow">FROM REVIEW TO RECEIPT</p>
          <h2>A destination you’ve agreed on.</h2>
          <p>
            Discover locally, confirm directly, and account for the food that
            actually changes hands.
          </p>
        </div>
        <Truck size={29} strokeWidth={1.3} />
      </div>
      <a className="dispatch-map-link" href="#station">
        <MapPin size={17} /> Find NGOs, food banks & processors on the recipient
        map
      </a>
      <details>
        <summary>Record recipient acceptance</summary>
        <p className="small muted">
          Contact the organization yourself. Record who accepted this specific
          material, quantity and collection arrangement. Acceptance expires
          within 24 hours and does not certify food safety.
        </p>
        {recipients.length === 0 ? (
          <p className="notice">
            Save a recipient from the Field station directory before recording
            acceptance.
          </p>
        ) : (
          <form onSubmit={saveAcceptance}>
            <div className="form-grid">
              <Label name="Saved recipient">
                <select
                  required
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                >
                  <option value="">Choose recipient</option>
                  {recipients.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </Label>
              <Label name="Food batch">
                <select
                  required
                  value={batch}
                  onChange={(e) => setBatch(e.target.value)}
                >
                  <option value="">Choose batch</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.id} · {b.origin} · {kg(b.remaining_kg)}
                    </option>
                  ))}
                </select>
              </Label>
              <Label name="Agreed route">
                <select
                  value={route}
                  onChange={(e) => setRoute(e.target.value)}
                >
                  {["human_redistribution", "compost", "biogas"].map((r) => (
                    <option key={r} value={r}>
                      {r.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </Label>
              <Label name="Accepted quantity (kg)">
                <input
                  required
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={quantity}
                  onChange={(e) => {
                    setQuantity(Number(e.target.value));
                    changeReceipt();
                  }}
                />
              </Label>
              <Label name="Recipient contact person">
                <input
                  required
                  minLength={2}
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                />
              </Label>
              <Label name="Staff member recording acceptance">
                <input
                  required
                  minLength={2}
                  value={staff}
                  onChange={(e) => setStaff(e.target.value)}
                />
              </Label>
              <Label name="Acceptance expires (local time)">
                <input
                  required
                  type="datetime-local"
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                />
              </Label>
              <Label name="Contact evidence & collection arrangement">
                <textarea
                  required
                  minLength={10}
                  value={evidence}
                  onChange={(e) => setEvidence(e.target.value)}
                />
              </Label>
            </div>
            <button className="button compact" disabled={busy}>
              Record batch acceptance
            </button>
          </form>
        )}
      </details>
      <details>
        <summary>Record a completed handoff</summary>
        <p className="notice">
          Requires a measured kitchen record, current recipient acceptance,
          remaining mass and manager-approved human recovery. Generated records
          cannot produce a real dispatch receipt.
        </p>
        <form onSubmit={dispatch}>
          <div className="form-grid">
            <Label name="Batch acceptance">
              <select
                required
                value={acceptance}
                onChange={(e) => {
                  setAcceptance(e.target.value);
                  changeReceipt();
                }}
              >
                <option value="">Choose acceptance</option>
                {acceptances.map((a) => (
                  <option
                    key={a.id}
                    value={a.id}
                    disabled={a.expired || a.remaining_kg <= 0}
                  >
                    {recipients.find((r) => r.id === a.recipient_id)?.name ??
                      a.recipient_id}{" "}
                    · {a.batch_id} · {kg(a.remaining_kg)} remaining
                    {a.expired ? " · expired" : ""}
                  </option>
                ))}
              </select>
            </Label>
            <Label name="Handoff quantity (kg)">
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={quantity}
                onChange={(e) => {
                  setQuantity(Number(e.target.value));
                  changeReceipt();
                }}
              />
            </Label>
            <Label name="Received by">
              <input
                required
                minLength={2}
                value={receivedBy}
                onChange={(e) => {
                  setReceivedBy(e.target.value);
                  changeReceipt();
                }}
              />
            </Label>
            <Label name="Receipt / collection reference">
              <input
                required
                minLength={3}
                value={reference}
                onChange={(e) => {
                  setReference(e.target.value);
                  changeReceipt();
                }}
              />
            </Label>
          </div>
          <label className="sharing-check">
            <input
              required
              type="checkbox"
              checked={occurred}
              onChange={(e) => {
                setOccurred(e.target.checked);
                changeReceipt();
              }}
            />
            I confirm the handoff occurred and the receiver is recorded.
          </label>
          <label className="sharing-check">
            <input
              required
              type="checkbox"
              checked={segregated}
              onChange={(e) => {
                setSegregated(e.target.checked);
                changeReceipt();
              }}
            />
            The food/material was segregated for the accepted route.
          </label>
          <button
            className="button compact"
            disabled={busy || !occurred || !segregated || !acceptance}
          >
            Record completed handoff
          </button>
        </form>
      </details>
      {receipt && (
        <p className="success-message" role="status">
          <Badge>Recorded handoff</Badge> {receipt.id} ·{" "}
          {kg(receipt.quantity_kg)} · staff receipt retained.
        </p>
      )}
      {receipts.length > 0 && (
        <div className="dispatch-ledger">
          <h3>Completed handoff receipts</h3>
          {receipts.map((r) => (
            <article className="inventory-row" key={r.id}>
              <b>
                {r.recipient_snapshot.name} · {kg(r.quantity_kg)}
              </b>
              <p>
                {r.route.replaceAll("_", " ")} · received by{" "}
                {r.dispatch_intent.received_by} ·{" "}
                {r.dispatch_intent.receipt_reference}
              </p>
              <small>
                {new Date(r.recorded_at).toLocaleString("en-IN")} · {r.id}
              </small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
