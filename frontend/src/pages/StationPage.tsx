import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowUpRight,
  Check,
  CloudSun,
  ExternalLink,
  MapPin,
  Radio,
  Search,
  Sprout,
  WifiOff,
} from "lucide-react";
import { api } from "../api";
import RecipientNetwork from "../components/RecipientNetwork";
import { Badge, Label, num, titleCase } from "../components/Common";

type Place = {
  latitude: number;
  longitude: number;
  map_embed_url: string;
  map_url: string;
  campus_name?: string;
  campus_address?: string;
  campus_source?: string;
  location_note?: string;
  name?: string;
  region?: string;
  country?: string;
};
type Weather = {
  status: string;
  temperature_c: number | null;
  precipitation_mm?: number;
  wind_kmh?: number;
  observed_at?: string;
  fetched_at?: string;
  description?: string;
  cache_age_seconds?: number;
  message?: string;
  context?: string;
};
type Systems = {
  providers: {
    id: string;
    configured: boolean;
    model: string;
    key_present: boolean;
  }[];
  forecast: {
    name: string;
    runtime: string;
    target: string;
    validation: string;
    challengers: string[];
  };
  safety: string;
  ai_role: string;
  agents: string;
  external_context: string;
  persistence: string;
};
type Brief = {
  mode: string;
  status: string;
  requested_provider: string;
  dataset_version: number;
  generated_at: string;
  label: string;
  cards: {
    id: string;
    title: string;
    text: string;
    path: string;
    basis: string;
    sources: string[];
  }[];
};
const storageKey = "foodwise.field-station.location.v1";
const providerName = (id: string) =>
  ({
    offline: "Offline",
    groq: "Groq",
    gemini: "Gemini",
    openrouter: "OpenRouter",
  })[id] ?? id;
const timeLabel = (value: string) =>
  new Date(value).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }) + " IST";

export default function StationPage({
  refresh,
  onNavigate,
}: {
  refresh: number;
  onNavigate: (page: string) => void;
}) {
  const [place, setPlace] = useState<Place | null>(null),
    [systems, setSystems] = useState<Systems | null>(null);
  const [city, setCity] = useState(""),
    [places, setPlaces] = useState<Place[]>([]),
    [searchStatus, setSearchStatus] = useState("");
  const [latitude, setLatitude] = useState(""),
    [longitude, setLongitude] = useState("");
  const [weather, setWeather] = useState<Weather | null>(null),
    [weatherBusy, setWeatherBusy] = useState(false);
  const [provider, setProvider] = useState("groq"),
    [topic, setTopic] = useState("overview"),
    [sharing, setSharing] = useState(false);
  const [brief, setBrief] = useState<Brief | null>(null),
    [briefBusy, setBriefBusy] = useState(false),
    [error, setError] = useState("");
  const weatherRequest = useRef(0),
    searchRequest = useRef(0);
  const changePlace = (next: Place, persist = true) => {
    weatherRequest.current++;
    searchRequest.current++;
    setPlace(next);
    setLatitude(String(next.latitude));
    setLongitude(String(next.longitude));
    setWeather(null);
    setWeatherBusy(false);
    setPlaces([]);
    setSearchStatus("");
    setError("");
    if (persist) {
      try {
        localStorage.setItem(
          storageKey,
          JSON.stringify({
            latitude: next.latitude,
            longitude: next.longitude,
            name: next.name ?? next.campus_name,
          }),
        );
      } catch {
        /* Storage can be disabled; the current session still works. */
      }
    }
  };
  useEffect(() => {
    let alive = true;
    let saved: { latitude: number; longitude: number; name?: string } | null =
      null;
    try {
      const candidate = JSON.parse(localStorage.getItem(storageKey) ?? "null");
      if (
        candidate &&
        Number.isFinite(candidate.latitude) &&
        Number.isFinite(candidate.longitude) &&
        Math.abs(candidate.latitude) <= 85 &&
        Math.abs(candidate.longitude) <= 180
      )
        saved = candidate;
    } catch {
      /* Invalid local preferences fall back to campus. */
    }
    const suffix = saved
      ? `?latitude=${saved.latitude}&longitude=${saved.longitude}`
      : "";
    Promise.all([
      api<Place>(`/station/location${suffix}`),
      api<Systems>("/station/systems"),
    ])
      .then(([location, status]) => {
        if (!alive) return;
        changePlace(
          saved
            ? {
                ...location,
                name: saved.name ?? "Selected location",
                campus_source: undefined,
                location_note:
                  "Location selected on this browser; no recovery partners are inferred from this point.",
              }
            : location,
          false,
        );
        setSystems(status);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
      weatherRequest.current++;
      searchRequest.current++;
    };
  }, []);
  useEffect(() => {
    let alive = true;
    api<Brief>("/station/brief", { provider: "offline", topic: "overview" })
      .then((result) => {
        if (alive) setBrief(result);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [refresh]);
  async function search(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSearchStatus("Searching places…");
    const request = ++searchRequest.current;
    try {
      const result = await api<{
        status: string;
        places: Place[];
        message?: string;
      }>(`/station/places?name=${encodeURIComponent(city.trim())}`);
      if (request !== searchRequest.current) return;
      setPlaces(result.places);
      setSearchStatus(
        result.status === "unavailable"
          ? (result.message ?? "Search unavailable")
          : result.places.length
            ? "Choose a place below."
            : "No matching places. Try the city name or enter coordinates.",
      );
    } catch (e) {
      if (request === searchRequest.current)
        setSearchStatus(e instanceof Error ? e.message : "Search unavailable");
    }
  }
  async function applyCoordinates(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const next = await api<Place>(
        `/station/location?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`,
      );
      changePlace({
        ...next,
        name: "Selected coordinates",
        campus_source: undefined,
        location_note:
          "User-selected point. This does not establish a kitchen or recovery facility.",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not set location");
    }
  }
  async function loadWeather() {
    if (!place) return;
    const request = ++weatherRequest.current;
    setWeatherBusy(true);
    setError("");
    try {
      const result = await api<Weather>(
        `/station/weather?latitude=${place.latitude}&longitude=${place.longitude}`,
      );
      if (request === weatherRequest.current) setWeather(result);
    } catch (e) {
      if (request === weatherRequest.current)
        setError(e instanceof Error ? e.message : "Weather unavailable");
    } finally {
      if (request === weatherRequest.current) setWeatherBusy(false);
    }
  }
  async function createBrief() {
    setBriefBusy(true);
    setError("");
    try {
      setBrief(
        await api<Brief>("/station/brief", {
          provider,
          topic,
          share_aggregate_evidence: sharing,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Briefing unavailable");
    } finally {
      setBriefBusy(false);
    }
  }
  const locationName =
    place?.name ?? place?.campus_name ?? "Finding the campus…";
  return (
    <>
      <header className="station-heading">
        <div>
          <p className="eyebrow">FOODWISE / FIELD STATION</p>
          <h1>
            A kitchen belongs
            <br />
            to a <em>larger world.</em>
          </h1>
          <p>
            Know your place. Read the conditions. Understand the decisions.
            <br className="desktop-break" /> Connect your kitchen to its
            community, with every decision backed by evidence.
          </p>
        </div>
        <div className="station-seal">
          <Sprout size={36} strokeWidth={1.2} />
          <span>
            Rooted locally.
            <br />
            <b>Accounted carefully.</b>
          </span>
        </div>
      </header>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="field-grid">
        <section className="atlas-panel" aria-labelledby="atlas-title">
          <div className="atlas-title">
            <div>
              <p className="eyebrow">YOUR PLACE ON THE MAP</p>
              <h2 id="atlas-title">{locationName}</h2>
              <p>
                {place?.name
                  ? [place.region, place.country].filter(Boolean).join(", ") ||
                    "Selected on this browser"
                  : place?.campus_address}
              </p>
            </div>
            <MapPin size={25} strokeWidth={1.5} />
          </div>
          {place && (
            <RecipientNetwork
              key={`${place.latitude},${place.longitude}`}
              latitude={place.latitude}
              longitude={place.longitude}
              locationName={locationName}
            />
          )}
          <p className="small muted">
            {place?.location_note}{" "}
            {place?.campus_source && (
              <a href={place.campus_source} target="_blank" rel="noreferrer">
                Campus location source
              </a>
            )}
          </p>
          <details className="location-settings">
            <summary>Change location</summary>
            <form onSubmit={search} className="place-search">
              <Label name="City search">
                <input
                  value={city}
                  minLength={2}
                  maxLength={100}
                  required
                  placeholder="Search Bengaluru, Mysuru…"
                  onChange={(e) => setCity(e.target.value)}
                />
              </Label>
              <button className="button secondary compact" type="submit">
                <Search size={16} /> Search
              </button>
            </form>
            <small className="muted">
              Search sends the entered place name to Open-Meteo / GeoNames.
            </small>
            <p className="small" role="status">
              {searchStatus}
            </p>
            {places.length > 0 && (
              <ul className="place-results">
                {places.map((p) => (
                  <li key={`${p.latitude},${p.longitude}`}>
                    <button
                      onClick={() =>
                        changePlace({
                          ...p,
                          location_note:
                            "City search result, not a surveyed campus or kitchen location.",
                        })
                      }
                    >
                      {p.name}
                      <small>
                        {p.region}, {p.country}
                      </small>
                      <ArrowUpRight size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={applyCoordinates} className="coordinate-form">
              <Label name="Latitude">
                <input
                  type="number"
                  min={-85}
                  max={85}
                  step="any"
                  required
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                />
              </Label>
              <Label name="Longitude">
                <input
                  type="number"
                  min={-180}
                  max={180}
                  step="any"
                  required
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                />
              </Label>
              <button className="button secondary compact" type="submit">
                Use point
              </button>
            </form>
            <button
              className="link"
              onClick={async () => {
                try {
                  changePlace(await api<Place>("/station/location"), false);
                  localStorage.removeItem(storageKey);
                } catch {
                  setError("Could not restore the campus point.");
                }
              }}
            >
              Restore KNSIT campus <ArrowUpRight size={14} />
            </button>
          </details>
        </section>
        <section className="weather-panel" aria-labelledby="weather-title">
          <div className="weather-top">
            <p className="eyebrow">OUTSIDE THE KITCHEN</p>
            <CloudSun size={34} strokeWidth={1.2} />
          </div>
          <h2 id="weather-title">
            The local
            <br />
            conditions.
          </h2>
          <p className="muted">
            A moment to review your attendance assumptions, before the next
            meal.
          </p>
          <div
            className="weather-reading"
            aria-live="polite"
            aria-atomic="true"
          >
            {weatherBusy ? (
              <div className="weather-skeleton" role="status">
                Checking local conditions…
              </div>
            ) : weather?.temperature_c != null ? (
              <>
                <Badge tone={weather.status === "stale" ? "amber" : "green"}>
                  {weather.status === "live"
                    ? "Live model estimate"
                    : weather.status === "cached"
                      ? "Cached estimate"
                      : "Stale cached estimate"}
                </Badge>
                <strong>
                  {num(weather.temperature_c)}
                  <small>°C</small>
                </strong>
                <p>{weather.description}</p>
                <dl>
                  <div>
                    <dt>Precipitation</dt>
                    <dd>{num(weather.precipitation_mm)} mm</dd>
                  </div>
                  <div>
                    <dt>Wind</dt>
                    <dd>{num(weather.wind_kmh)} km/h</dd>
                  </div>
                </dl>
                <small>
                  Provider time:{" "}
                  {weather.observed_at && timeLabel(weather.observed_at)}
                  <br />
                  Retrieved:{" "}
                  {weather.fetched_at && timeLabel(weather.fetched_at)}
                </small>
              </>
            ) : (
              <>
                <WifiOff size={22} />
                <b>
                  {weather ? "Conditions unavailable" : "Ready when you are."}
                </b>
                <p>
                  {weather?.message ??
                    "Fetch current outdoor conditions for the selected location. The complete kitchen workflow works without this connection."}
                </p>
              </>
            )}
          </div>
          <button
            className="button secondary"
            disabled={!place || weatherBusy}
            onClick={loadWeather}
          >
            <Radio size={16} />
            {weather ? "Refresh conditions" : "Fetch local weather"}
          </button>
          <div className="weather-boundary">
            <b>Context, never a safety signal.</b>
            <p>
              Outdoor weather does not establish food holding temperatures and
              never changes your forecast automatically.
            </p>
            <small>
              Coordinates sent only when you fetch.{" "}
              <a
                href="https://open-meteo.com/"
                target="_blank"
                rel="noreferrer"
              >
                Weather data by Open-Meteo
              </a>{" "}
              ·{" "}
              <a
                href="https://creativecommons.org/licenses/by/4.0/"
                target="_blank"
                rel="noreferrer"
              >
                CC BY 4.0
              </a>
            </small>
          </div>
        </section>
      </div>
      <section className="evidence-studio" aria-labelledby="brief-title">
        <header className="studio-heading">
          <div>
            <p className="eyebrow">THE EVIDENCE DESK</p>
            <h2 id="brief-title">Intelligence you can inspect.</h2>
            <p>
              Local AI learns demand. Groq helps prioritize what deserves your
              attention.
            </p>
          </div>
          <span className="desk-stamp">
            HUMAN DECISIONS
            <br />
            <b>SERVER-OWNED FACTS</b>
          </span>
        </header>
        <div className="brief-controls">
          <Label name="Briefing topic">
            <select value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="overview">The food journey</option>
              <option value="preparation">Preparing the next meal</option>
              <option value="recovery">Surplus and recovery</option>
            </select>
          </Label>
          <Label name="Explanation provider">
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setSharing(false);
              }}
            >
              <option value="offline">Offline · always available</option>
              <option value="groq">Groq · default</option>
              <option value="gemini">Gemini</option>
              <option value="openrouter">OpenRouter</option>
            </select>
          </Label>
          <button
            className="button"
            disabled={briefBusy || (provider !== "offline" && !sharing)}
            onClick={createBrief}
          >
            {briefBusy ? "Preparing the briefing…" : "Create evidence briefing"}
            <ArrowUpRight size={17} />
          </button>
        </div>
        {provider !== "offline" && (
          <div className="provider-sharing">
            <label>
              <input
                type="checkbox"
                checked={sharing}
                onChange={(e) => setSharing(e.target.checked)}
              />{" "}
              I agree to send aggregate food quantities and predefined evidence
              text to {providerName(provider)} for this request.
            </label>
            <small>
              No staff names, record IDs, CSV files, location, tools or safety
              actions are sent. If the provider is unconfigured or unavailable,
              the offline briefing is returned.
            </small>
          </div>
        )}
        {brief && (
          <>
            <div className="brief-provenance" role="status">
              <Badge
                tone={brief.mode === "provider_curated" ? "green" : "gray"}
              >
                {brief.mode === "provider_curated"
                  ? `${providerName(brief.requested_provider)} curated`
                  : "Offline evidence briefing"}
              </Badge>
              <span>
                Dataset v{brief.dataset_version} ·{" "}
                {timeLabel(brief.generated_at)}
              </span>
              {brief.status === "not_configured" && (
                <b>
                  Provider needs a server key and model ID; offline fallback
                  used.
                </b>
              )}
              {brief.status === "provider_unavailable_or_invalid" && (
                <b>Provider unavailable or invalid; offline fallback used.</b>
              )}
            </div>
            <div className="brief-cards">
              {brief.cards.map((card, index) => (
                <article key={card.id}>
                  <span className="brief-number">0{index + 1}</span>
                  <div>
                    <h3>{card.title}</h3>
                    <p>{card.text}</p>
                    <small>
                      {card.basis} · {card.sources.map(titleCase).join(", ")}
                    </small>
                    <button
                      className="link"
                      onClick={() => onNavigate(card.path)}
                    >
                      Inspect in the kitchen <ArrowUpRight size={14} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
            <p className="small muted">
              {brief.label}. Briefing actions open the relevant workflow; every
              approval stays with a manager.
            </p>
          </>
        )}
      </section>
      <section className="system-garden" aria-labelledby="systems-title">
        <div className="system-intro">
          <p className="eyebrow">UNDER THE SURFACE</p>
          <h2 id="systems-title">
            What’s actually
            <br />
            doing the thinking?
          </h2>
          <p>
            There is no mysterious agent running your kitchen. You initiate the
            work; the software calculates and explains.
          </p>
        </div>
        <div className="system-ledger">
          {systems ? (
            <>
              <article>
                <span>01</span>
                <div>
                  <h3>Local forecasting models</h3>
                  <p>
                    {systems.forecast.name}. {systems.forecast.runtime}. Target:{" "}
                    {systems.forecast.target}.
                  </p>
                  <small>
                    {systems.forecast.validation}. Challengers:{" "}
                    {systems.forecast.challengers.join(", ")}.
                  </small>
                  <button className="link" onClick={() => onNavigate("plan")}>
                    See the model comparison <ArrowUpRight size={14} />
                  </button>
                </div>
                <Badge tone="green">Offline</Badge>
              </article>
              <article>
                <span>02</span>
                <div>
                  <h3>Deterministic safety rules</h3>
                  <p>{systems.safety}. No model can override them.</p>
                </div>
                <Badge tone="green">Server</Badge>
              </article>
              <article>
                <span>03</span>
                <div>
                  <h3>Learning & Groq briefing</h3>
                  <p>{systems.ai_role}</p>
                  <ul className="provider-ledger">
                    {systems.providers.map((p) => (
                      <li key={p.id}>
                        <b>{providerName(p.id)}</b>
                        <span>
                          {p.configured ? (
                            <>
                              <Check size={13} /> Configured · {p.model}
                            </>
                          ) : p.key_present ? (
                            "Key present · model ID required"
                          ) : (
                            "Not configured"
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <details>
                    <summary>Connect your own provider</summary>
                    <p className="small">
                      Copy <code>.env.example</code> to <code>.env</code> in the
                      project root. Set the relevant <code>GROQ_API_KEY</code>,{" "}
                      <code>GEMINI_API_KEY</code> or{" "}
                      <code>OPENROUTER_API_KEY</code> and matching{" "}
                      <code>GROQ_MODEL</code>, <code>GEMINI_MODEL</code> or{" "}
                      <code>OPENROUTER_MODEL</code>. Use a JSON-capable model ID
                      available in your account, then restart the backend and
                      reload this page. Keep keys in the server file; never use
                      a VITE_ variable.
                    </p>
                    <p className="small">
                      Provider support:{" "}
                      <a
                        href="https://console.groq.com/docs/structured-outputs"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Groq
                      </a>{" "}
                      ·{" "}
                      <a
                        href="https://ai.google.dev/gemini-api/docs/structured-output"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Gemini
                      </a>{" "}
                      ·{" "}
                      <a
                        href="https://openrouter.ai/docs/guides/features/structured-outputs"
                        target="_blank"
                        rel="noreferrer"
                      >
                        OpenRouter
                      </a>
                      . Unsupported output falls back safely.
                    </p>
                  </details>
                </div>
                <Badge tone="gray">AI</Badge>
              </article>
              <article>
                <span>04</span>
                <div>
                  <h3>People hold the decision</h3>
                  <p>{systems.agents}</p>
                  <small>{systems.persistence}.</small>
                </div>
                <Badge tone="green">Human</Badge>
              </article>
            </>
          ) : (
            <p className="muted">Waiting for the local systems API…</p>
          )}
        </div>
      </section>
    </>
  );
}
