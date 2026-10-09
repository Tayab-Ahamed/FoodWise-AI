import { useEffect, useRef, useState, useMemo } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  ArrowUpRight,
  MapPin,
  Search,
  BookmarkPlus,
  ExternalLink,
} from "lucide-react";
import { api } from "../api";
import { Label, Badge, num } from "./Common";

export type Recipient = {
  id: string;
  name: string;
  category: string;
  address: string;
  contact?: string;
  phone?: string;
  email?: string;
  website?: string;
  source_url?: string;
  source: string;
  latitude: number | null;
  longitude: number | null;
  distance_km?: number | null;
  note?: string;
};
type Directory = {
  status: string;
  places: Recipient[];
  contacts: Recipient[];
  saved: Recipient[];
  fetched_at: string | null;
  coverage: string;
  radius_km: number;
};
const categoryName = (value: string) => value.replaceAll("_", " ");

function NetworkMap({
  latitude,
  longitude,
  places,
  selected,
  onSelect,
}: {
  latitude: number;
  longitude: number;
  places: Recipient[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    mapRef = useRef<L.Map | null>(null);
  const markers = useRef(new Map<string, L.CircleMarker>());
  useEffect(() => {
    if (!container.current) return;
    const map = L.map(container.current, { scrollWheelZoom: false }).setView(
      [latitude, longitude],
      13,
    );
    mapRef.current = map;
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    const label = document.createElement("strong");
    label.textContent = "Kitchen location";
    L.circleMarker([latitude, longitude], {
      radius: 11,
      color: "#214d3b",
      weight: 3,
      fillColor: "#fff",
      fillOpacity: 1,
    })
      .addTo(map)
      .bindPopup(label);
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, [latitude, longitude]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markers.current.forEach((marker) => marker.remove());
    markers.current.clear();
    const points: L.LatLngExpression[] = [[latitude, longitude]];
    for (const p of places) {
      if (p.latitude === null || p.longitude === null) continue;
      const content = document.createElement("div"),
        title = document.createElement("strong"),
        note = document.createElement("p");
      title.textContent = p.name;
      note.textContent = `${categoryName(p.category)} · contact required`;
      content.append(title, note);
      const marker = L.circleMarker([p.latitude, p.longitude], {
        radius: 8,
        color: "#fff",
        weight: 2,
        fillColor: p.category === "organic_processor" ? "#a06839" : "#527c55",
        fillOpacity: 1,
      })
        .addTo(map)
        .bindPopup(content)
        .on("click", () => onSelect(p.id));
      markers.current.set(p.id, marker);
      points.push([p.latitude, p.longitude]);
    }
    if (points.length > 1)
      map.fitBounds(L.latLngBounds(points), { padding: [35, 35], maxZoom: 14 });
  }, [places, latitude, longitude]);
  useEffect(() => {
    const marker = markers.current.get(selected);
    if (marker) {
      marker.openPopup();
      mapRef.current?.panTo(marker.getLatLng());
    }
  }, [selected]);
  return (
    <div
      ref={container}
      className="recipient-map"
      aria-label="Map of nearby recipient candidates"
    />
  );
}

export default function RecipientNetwork({
  latitude,
  longitude,
  locationName,
}: {
  latitude: number;
  longitude: number;
  locationName: string;
}) {
  const [directory, setDirectory] = useState<Directory | null>(null),
    [radius, setRadius] = useState(15);
  const [mapOpen, setMapOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [filter, setFilter] = useState("all"),
    [selected, setSelected] = useState("");
  const [formOpen, setFormOpen] = useState(false),
    [savedMessage, setSavedMessage] = useState("");
  const [form, setForm] = useState({
    name: "",
    address: "",
    contact: "",
    category: "ngo",
    source_url: "",
    latitude: "",
    longitude: "",
  });
  const requestVersion = useRef(0);
  async function load(discover = false) {
    const request = ++requestVersion.current;
    setBusy(true);
    setError("");
    try {
      const result = await api<Directory>(
        `/recipients/directory?latitude=${latitude}&longitude=${longitude}&radius_km=${radius}&discover=${discover}`,
      );
      if (request === requestVersion.current) setDirectory(result);
    } catch (e) {
      if (request === requestVersion.current)
        setError(e instanceof Error ? e.message : "Directory unavailable");
    } finally {
      if (request === requestVersion.current) setBusy(false);
    }
  }
  useEffect(() => {
    setDirectory(null);
    setSelected("");
    void load();
    return () => {
      requestVersion.current++;
    };
  }, [latitude, longitude, radius]);
  const all = useMemo(
    () => [...(directory?.places ?? []), ...(directory?.saved ?? [])],
    [directory],
  );
  const plotted = useMemo(
    () => all.filter((p) => p.latitude !== null && p.longitude !== null),
    [all],
  );
  const visible = all.filter(
    (p) =>
      filter === "all" ||
      (filter === "saved"
        ? directory?.saved.some((s) => s.id === p.id)
        : filter === "processor"
          ? p.category === "organic_processor"
          : p.category !== "organic_processor"),
  );
  const focused = all.find((p) => p.id === selected);
  function prefill(p?: Recipient) {
    setForm({
      name: p?.name ?? "",
      address: p?.address ?? "",
      contact: p?.contact ?? [p?.phone, p?.email].filter(Boolean).join(" / "),
      category: [
        "food_bank",
        "food_rescue_network",
        "ngo",
        "social_facility",
        "soup_kitchen",
        "organic_processor",
      ].includes(p?.category ?? "")
        ? p!.category
        : "social_facility",
      source_url: p?.source_url ?? "",
      latitude: p?.latitude?.toString() ?? "",
      longitude: p?.longitude?.toString() ?? "",
    });
    setFormOpen(true);
    setSavedMessage("");
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/recipients", {
        ...form,
        latitude: form.latitude === "" ? null : Number(form.latitude),
        longitude: form.longitude === "" ? null : Number(form.longitude),
      });
      setFormOpen(false);
      setSavedMessage(
        "Recipient saved. Confirm acceptance separately for each food batch.",
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save recipient");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="recipient-network">
      <div className="network-toolbar">
        <Label name="Search radius">
          <select
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          >
            {[5, 10, 15, 30].map((n) => (
              <option key={n} value={n}>
                {n} km
              </option>
            ))}
          </select>
        </Label>
        <button
          className="button compact"
          disabled={busy}
          onClick={() => {
            setMapOpen(true);
            void load(true);
          }}
        >
          <Search size={16} />
          {busy ? "Finding organizations…" : "Find nearby organizations"}
        </button>
      </div>
      {mapOpen ? (
        <div className="network-map-wrap">
          <NetworkMap
            latitude={latitude}
            longitude={longitude}
            places={plotted}
            selected={selected}
            onSelect={setSelected}
          />
          <button
            className="button secondary compact map-close"
            onClick={() => setMapOpen(false)}
          >
            Close map
          </button>
        </div>
      ) : (
        <div className="map-resting network-resting">
          <div className="map-contours" aria-hidden="true" />
          <MapPin size={36} />
          <b>{locationName}</b>
          <span>
            Your kitchen. Its community. A shorter journey for good food.
          </span>
          <button className="button" onClick={() => setMapOpen(true)}>
            Open recipient map <ArrowUpRight size={16} />
          </button>
          <small>
            Opening the map loads OpenStreetMap tiles. Discovery queries the
            public Overpass directory.
          </small>
        </div>
      )}
      <div className="network-legend">
        <span>
          <i className="kitchen-dot" /> Kitchen
        </span>
        <span>
          <i /> NGO / community candidate
        </span>
        <span>
          <i className="processor-dot" /> Organic processor
        </span>
      </div>
      <p className="small muted" role="status">
        {directory?.coverage}{" "}
        {directory?.fetched_at &&
          `Fetched ${new Date(directory.fetched_at).toLocaleString("en-IN")}.`}
      </p>
      {(directory?.status === "unavailable" ||
        directory?.status === "stale") && (
        <p className="notice" role="status">
          {directory.status === "stale"
            ? "Live refresh unavailable. Showing the previous directory snapshot."
            : "Live directory unavailable. Official contacts and saved recipients remain available; retry discovery later."}
        </p>
      )}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="network-list-heading">
        <h3>Nearby candidates & saved recipients</h3>
        <button className="text-button" onClick={() => prefill()}>
          <BookmarkPlus size={15} /> Add recipient
        </button>
      </div>
      <div className="network-filters" aria-label="Filter recipient directory">
        {[
          ["all", "All"],
          ["community", "Community"],
          ["processor", "Processors"],
          ["saved", "Saved"],
        ].map(([id, label]) => (
          <button
            key={id}
            aria-pressed={filter === id}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="network-results">
        {visible.map((p) => (
          <article
            key={p.id}
            className={`recipient-row ${selected === p.id ? "selected" : ""}`}
          >
            <button
              className="recipient-select"
              onClick={() => {
                setSelected(p.id);
                if (p.latitude !== null) setMapOpen(true);
              }}
            >
              <span className="recipient-category">
                {categoryName(p.category)}
              </span>
              <b>{p.name}</b>
              <span>
                {p.address || "Address not mapped; confirm before collection"}
              </span>
              <small>
                {p.distance_km != null
                  ? `${num(p.distance_km)} km straight-line`
                  : p.latitude === null
                    ? "Location needs confirmation"
                    : "Staff-entered location"}{" "}
                · contact required
              </small>
            </button>
            <div className="recipient-links">
              {p.source_url && (
                <a href={p.source_url} target="_blank" rel="noreferrer">
                  Source <ExternalLink size={12} />
                </a>
              )}
              <button className="text-button" onClick={() => prefill(p)}>
                Save contact
              </button>
            </div>
          </article>
        ))}
      </div>
      {visible.length === 0 && (
        <p className="network-empty">
          {directory?.status === "not_requested"
            ? "Discover mapped organizations around the campus, or add a recipient you already know."
            : "No candidates in this view. Expand the radius or add a verified contact."}
        </p>
      )}
      {focused && (
        <div className="recipient-detail">
          <Badge>Contact required</Badge>
          <h3>{focused.name}</h3>
          <p>
            {focused.note ??
              "Verify the recipient and agree acceptance for each batch before dispatch."}
          </p>
          <p>
            {focused.contact ||
              [focused.phone, focused.email].filter(Boolean).join(" · ") ||
              "No contact provided by this source"}
          </p>
          {focused.website && (
            <a href={focused.website} target="_blank" rel="noreferrer">
              Organization website <ExternalLink size={13} />
            </a>
          )}
        </div>
      )}
      {(directory?.contacts.length ?? 0) > 0 && (
        <div className="official-contacts">
          <p className="eyebrow">
            OFFICIAL CONTACTS / CONFIRM A LOCAL COLLECTION POINT
          </p>
          {directory!.contacts.map((p) => (
            <article key={p.id}>
              <b>{p.name}</b>
              <p>{p.address}</p>
              <p>{[p.phone, p.email].filter(Boolean).join(" · ")}</p>
              <small>{p.note}</small>
              <div className="recipient-links">
                <a href={p.source_url} target="_blank" rel="noreferrer">
                  Official source <ExternalLink size={12} />
                </a>
                <button className="text-button" onClick={() => prefill(p)}>
                  Save contact
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {savedMessage && (
        <p className="success-message" role="status">
          {savedMessage}
        </p>
      )}
      {formOpen && (
        <form className="recipient-form" onSubmit={save}>
          <h3>Save a recipient contact</h3>
          <p className="small muted">
            A saved contact can be selected in Recovery. Acceptance is recorded
            separately; saving does not authorize a handoff.
          </p>
          <div className="form-grid">
            {[
              ["name", "Organization name"],
              ["address", "Collection address"],
              ["contact", "Contact phone or email"],
              ["source_url", "Source URL (optional)"],
              ["latitude", "Confirmed latitude (optional)"],
              ["longitude", "Confirmed longitude (optional)"],
            ].map(([key, label]) => (
              <Label key={key} name={label}>
                <input
                  required={["name", "address", "contact"].includes(key)}
                  type={
                    key === "source_url"
                      ? "url"
                      : ["latitude", "longitude"].includes(key)
                        ? "number"
                        : "text"
                  }
                  step="any"
                  value={form[key as keyof typeof form]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              </Label>
            ))}
            <Label name="Recipient category">
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {[
                  "ngo",
                  "food_bank",
                  "soup_kitchen",
                  "social_facility",
                  "food_rescue_network",
                  "organic_processor",
                ].map((c) => (
                  <option key={c} value={c}>
                    {categoryName(c)}
                  </option>
                ))}
              </select>
            </Label>
          </div>
          <div className="recipient-links">
            <button className="button compact" disabled={busy}>
              Save recipient
            </button>
            <button
              className="button secondary compact"
              type="button"
              onClick={() => setFormOpen(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
