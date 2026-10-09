import { useEffect, useRef, useState, useId, type ReactNode } from "react";
import { ArrowUpRight, CheckCircle2, X } from "lucide-react";
import { api } from "../api";
import type { MealRecord, Preview, Run } from "../types";

export const num = (n: number | null | undefined, digits = 1) =>
  n == null
    ? "—"
    : n.toLocaleString("en-IN", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export const kg = (n: number | null | undefined, digits = 1) =>
  `${num(n, digits)} kg`;
export const currency = (n: number) => `₹${num(n, 0)}`;
export const titleCase = (s: string) =>
  s === "synthetic" ? "Generated practice records" : s.replaceAll("_", " ");
export function Badge({
  children,
  tone = "green",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card ${className}`}>{children}</section>;
}
export function Stat({
  label,
  value,
  detail,
  tone = "",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <div className={`stat ${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function Label({
  name,
  children,
  hint,
}: {
  name: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{name}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function ActionLink({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="link" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  );
}
export function Dialog({
  title,
  onClose,
  children,
  returnFocus,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  returnFocus?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const previousFocus = document.activeElement;
    ref.current?.showModal();
    const d = ref.current;
    return () => {
      d?.close();
      const target = returnFocus
        ? document.querySelector<HTMLElement>(returnFocus)
        : previousFocus instanceof HTMLElement &&
            previousFocus !== document.body
          ? previousFocus
          : document.querySelector<HTMLElement>("main");
      if (target?.isConnected) target.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target !== ref.current) return;
        const bounds = e.currentTarget.getBoundingClientRect();
        if (
          e.clientX < bounds.left ||
          e.clientX > bounds.right ||
          e.clientY < bounds.top ||
          e.clientY > bounds.bottom
        )
          onClose();
      }}
    >
      <header>
        <h2 id={titleId}>{title}</h2>
        <button
          autoFocus
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export function RecordTable({ records }: { records: MealRecord[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Record / date</th>
            <th>Item</th>
            <th>Diners</th>
            <th>Prepared kg</th>
            <th>Consumed kg</th>
            <th>Untouched kg</th>
            <th>Plate kg</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.record_id}>
              <td>
                <b>{r.record_id}</b>
                <small>
                  {r.date} · {r.meal}
                </small>
              </td>
              <td>{r.item}</td>
              <td>{r.attendance}</td>
              <td>{num(r.prepared_kg)}</td>
              <td>{num(r.consumed_kg)}</td>
              <td>{num(r.untouched_surplus_kg)}</td>
              <td>{num(r.plate_waste_kg)}</td>
              <td>
                <Badge tone="blue">{titleCase(r.source)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Evidence({
  ids,
  onClose,
}: {
  ids: string[];
  onClose: () => void;
}) {
  const [rows, setRows] = useState<MealRecord[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<MealRecord[]>(`/records?ids=${encodeURIComponent(ids.join(","))}`)
      .then((result) => {
        if (active) setRows(result);
      })
      .catch((e) => {
        if (active) setError(String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [ids]);
  return (
    <Dialog title="Historical record evidence" onClose={onClose}>
      <p className="muted mb-5">
        {ids.length} referenced records. Cooked food in kg; served = consumed +
        plate waste.
      </p>
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <p role="status" className="muted">
          Loading referenced records…
        </p>
      ) : (
        <RecordTable records={rows} />
      )}
      {!loading && !error && rows.length < ids.length && (
        <p className="notice">
          Some snapshot records belong to a replaced dataset and are no longer
          active. Their IDs and forecast values remain in the immutable report.
        </p>
      )}
    </Dialog>
  );
}
export function ImportDialog({
  run,
  busy,
  onClose,
  onDone,
}: {
  run: Run;
  busy: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [confirm, setConfirm] = useState(false),
    [dialogError, setDialogError] = useState("");
  const showError = (error: unknown): never => {
    setDialogError(error instanceof Error ? error.message : String(error));
    throw error;
  };
  const upload = async () => {
    if (!file) return;
    setDialogError("");
    const data = new FormData();
    data.append("file", file);
    const result = await run(() =>
      api<Preview>("/datasets/preview", data).catch(showError),
    );
    if (result) setPreview(result);
  };
  const commit = async () => {
    if (!preview?.preview_token) return;
    setDialogError("");
    const result = await run(
      () =>
        api("/datasets/commit", {
          preview_token: preview.preview_token,
          mode: "replace",
        }).catch(showError),
      "CSV imported atomically. Forecasts will use the new dataset.",
    );
    if (result) {
      onDone();
      onClose();
    }
  };
  return (
    <Dialog
      title="Import meal history"
      onClose={onClose}
      returnFocus='[aria-label="Import history CSV"]'
    >
      <p className="muted">
        Preview every row before replacing active history. Existing IDs
        conflict; imports are labeled user provided, unverified. Actual meal
        logs are retained.
      </p>
      <Label name="History CSV" hint="UTF-8 · maximum 5 MB / 10,000 rows">
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setPreview(null);
            setConfirm(false);
            setDialogError("");
          }}
        />
      </Label>
      {dialogError && (
        <p className="notice" role="alert">
          {dialogError}
        </p>
      )}
      <button className="button" disabled={!file || busy} onClick={upload}>
        Preview & validate
      </button>
      {preview && (
        <div className="mt-6">
          <Badge tone={preview.valid ? "green" : "amber"}>
            {preview.valid
              ? `${preview.row_count} valid rows`
              : "Import blocked — no data changed"}
          </Badge>
          {preview.errors.length > 0 && (
            <ul className="error-list">
              {preview.errors.map((e, i) => (
                <li key={i}>
                  Row {e.row ?? "—"} · {e.field}: {e.message}
                </li>
              ))}
            </ul>
          )}
          <RecordTable records={preview.preview} />
          {preview.valid && (
            <>
              <p className="muted small mt-4">
                File hash: {preview.sha256}. Preview expires after 30 minutes.
              </p>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={confirm}
                  onChange={(e) => setConfirm(e.target.checked)}
                />{" "}
                Replace the active history with this validated file.
              </label>
              <button
                disabled={!confirm || busy}
                className="button mt-4"
                onClick={commit}
              >
                <CheckCircle2 size={16} /> Confirm import
              </button>
            </>
          )}
        </div>
      )}
    </Dialog>
  );
}
