import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { ArrowUpRight, BookOpen, Leaf, Plus, Send, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { titleCase } from "../components/Common";
import "./advisor.css";

type Provider = { id: string; configured: boolean; model: string };
type Evidence = {
  id: string; title: string; text: string; path: string; basis: string;
  reference_ids: string[]; record_reference_ids: string[]; reference_count: number; sources: string[];
  source_url: string | null; dataset_version: number;
};
type Reply = {
  mode: "ai_assisted" | "offline"; status: string; label: string; answer: string;
  evidence: Evidence[]; dataset_version: number; generated_at: string;
  context: { planning_date: string; timezone: string; inventory_as_of: string | null };
  limitations: string[];
};
type Turn = { question: string; reply?: Reply; error?: string };
type Capabilities = { suggestions: string[]; providers: Provider[]; privacy: string; today: string };
// Memory only: survives page navigation, clears on a full reload or New Chat.
let conversation: { turns: Turn[]; busy: boolean } = { turns: [], busy: false };
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
const snapshot = () => conversation;
const store = (turns: Turn[], busy = conversation.busy) => {
  conversation = { turns: turns.slice(-24), busy };
  listeners.forEach((listener) => listener());
};
const examples = [
  "How much food should we prepare tomorrow?", "Which ingredients are nearing expiry?",
  "Why is our food waste increasing?", "What can we do with untouched surplus?",
  "Which nearby NGOs are shown on our map?", "How can we reduce plate waste?",
];
const names: Record<string, string> = { groq: "Groq", gemini: "Gemini", openrouter: "OpenRouter", offline: "Offline" };
const fallbackStatus: Record<string, string> = {
  not_configured: "The selected provider is not configured. This answer uses local evidence.",
  provider_unavailable_or_invalid: "AI was unavailable or returned an invalid response. Local evidence is shown instead.",
};

function EvidenceNotes({ evidence, onNavigate, onEvidence }: {
  evidence: Evidence[]; onNavigate: (page: string) => void; onEvidence: (ids: string[]) => void;
}) {
  return <details className="advisor-evidence"><summary><BookOpen size={15} /> Evidence & data references</summary>
    <div>{evidence.map((e) => <article key={e.id}>
      <strong>{e.title}</strong><p>{e.basis}</p>
      <small>Dataset v{e.dataset_version}{e.sources.length ? ` · ${e.sources.map(titleCase).join(", ")}` : " · Application rules"}</small>
      <div className="advisor-reference-actions">
        <button className="link" onClick={() => onNavigate(e.path)}>Open {({ overview: "overview", plan: "planning", recovery: "recovery", station: "NGO map", impact: "impact & evidence" } as Record<string, string>)[e.path]} <ArrowUpRight size={13} /></button>
        {e.source_url && /^https?:\/\//.test(e.source_url) && <a className="link" href={e.source_url} target="_blank" rel="noreferrer">Published source <ArrowUpRight size={13} /></a>}
        {!!e.record_reference_ids.length && <button className="link" onClick={() => onEvidence(e.record_reference_ids)}>Inspect meal records</button>}
      </div>
      {!!e.reference_ids.length && <details className="advisor-ids"><summary>Reference IDs ({e.reference_count}{e.reference_count > e.reference_ids.length ? `; first ${e.reference_ids.length} shown` : ""})</summary><p>{e.reference_ids.join(", ")}</p></details>}
    </article>)}</div>
  </details>;
}

export default function AdvisorPage({ onNavigate, onEvidence }: {
  onNavigate: (page: string) => void; onEvidence: (ids: string[]) => void;
}) {
  const { turns, busy } = useSyncExternalStore(subscribe, snapshot);
  const [question, setQuestion] = useState("");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [provider, setProvider] = useState("groq"), [sharing, setSharing] = useState(false);
  const [planningDate, setPlanningDate] = useState(""), [meal, setMeal] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const input = useRef<HTMLTextAreaElement>(null), latest = useRef<HTMLDivElement>(null), mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    api<Capabilities>("/advisor/capabilities").then((data) => { if (mounted.current) setCapabilities(data); })
      .catch(() => { if (mounted.current) setConnectionError("Cannot reach the kitchen API. Check that the backend is running and retry your question."); });
    return () => { mounted.current = false; };
  }, []);
  const send = async (text: string) => {
    text = text.trim();
    if (!text || conversation.busy) return;
    const next = [...conversation.turns, { question: text }];
    const history = conversation.turns.filter((turn) => turn.reply).slice(-8).map((turn) => turn.question);
    store(next, true); setQuestion(""); setConnectionError("");
    let location: { latitude?: number; longitude?: number } = {};
    try {
      const candidate = JSON.parse(localStorage.getItem("foodwise.field-station.location.v1") ?? "null");
      if (candidate && Number.isFinite(candidate.latitude) && Math.abs(candidate.latitude) <= 85 && Number.isFinite(candidate.longitude) && Math.abs(candidate.longitude) <= 180)
        location = { latitude: candidate.latitude, longitude: candidate.longitude };
    } catch { /* Disabled browser storage leaves the existing campus default. */ }
    try {
      const reply = await api<Reply>("/advisor/chat", { question: text, history,
        provider: sharing ? provider : "offline", share_aggregate_evidence: sharing && provider !== "offline",
        planning_date: planningDate || null, meal: meal || null, ...location });
      store([...next.slice(0, -1), { question: text, reply }]);
    } catch (error) {
      store([...next.slice(0, -1), { question: text, error: error instanceof Error ? error.message : "Unable to get an answer. Please retry." }]);
    } finally { store(conversation.turns, false); if (mounted.current) { input.current?.focus({ preventScroll: true }); latest.current?.scrollIntoView({ behavior: "instant", block: "nearest" }); } }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void send(question); };
  const selected = capabilities?.providers.find((p) => p.id === provider);
  return <section className="advisor-page" aria-labelledby="advisor-title">
    <header className="advisor-heading"><div><span className="eyebrow">A thoughtful second opinion</span><h1 id="advisor-title">AI Kitchen Advisor<span>.</span></h1><p>Ask your kitchen records. Understand the next decision.</p></div>
      <button className="button secondary" disabled={busy || !turns.length} onClick={() => { store([]); setQuestion(""); input.current?.focus(); }}><Plus size={16} /> New Chat</button></header>
    <div className="advisor-workspace">
      <div className="advisor-controls">
        <span className="advisor-readonly"><ShieldCheck size={17} /> Read-only advisor</span>
        <label>Model <select aria-label="Advisor provider" value={provider} disabled={busy} onChange={(event) => { setProvider(event.target.value); if (event.target.value === "offline") setSharing(false); }}>
          <option value="groq">Groq</option><option value="gemini">Gemini</option><option value="openrouter">OpenRouter</option><option value="offline">Offline</option>
        </select></label>
        <span className="advisor-model-status">{provider === "offline" ? "Works without internet" : selected?.configured ? selected.model : "Not configured · local fallback available"}</span>
      </div>
      <div className="advisor-sharing"><label><input type="checkbox" checked={sharing} disabled={busy || provider === "offline"} onChange={(event) => setSharing(event.target.checked)} /> {provider === "offline" ? "AI sharing disabled in offline mode" : `Use ${names[provider]} AI to prioritize aggregate evidence`}</label><p>{capabilities?.privacy ?? "Your question stays local. Enable AI to share only recognized topics and validated aggregate evidence."}</p></div>
      {connectionError && <p className="advisor-error" role="alert">{connectionError}</p>}
      <div className="advisor-conversation" role="log" aria-label="Kitchen advisor conversation" aria-live="polite" aria-busy={busy}>
        {!turns.length && <div className="advisor-welcome"><span className="advisor-leaf"><Leaf size={31} strokeWidth={1.4} /></span><span className="eyebrow">Evidence before advice</span><h2>What’s on your mind<br />in the kitchen?</h2><p>From tomorrow’s preparation to today’s surplus.<br />Every answer starts with the records you have.</p></div>}
        {turns.map((turn, index) => <div className="advisor-turn" key={index}>
          <div className="advisor-user"><small>You asked</small><p>{turn.question}</p></div>
          {turn.reply && <article className="advisor-reply"><div className="advisor-reply-label"><Leaf size={17} /><strong>{turn.reply.label}</strong><small>Dataset v{turn.reply.dataset_version}</small></div>
            {fallbackStatus[turn.reply.status] && <p className="advisor-fallback">{fallbackStatus[turn.reply.status]}</p>}
            {turn.reply.evidence.map((e) => <div className="advisor-fact" key={e.id}><h3>{e.title}</h3><p>{e.text}</p></div>)}
            <EvidenceNotes evidence={turn.reply.evidence} onNavigate={onNavigate} onEvidence={onEvidence} />
            <small className="advisor-answer-note">{turn.reply.mode === "ai_assisted" ? "AI prioritized the evidence. All facts and safety rules come from the backend." : "Deterministic response from local records and application rules."} No actions performed.</small>
          </article>}
          {turn.error && <div className="advisor-error" role="alert"><p>{turn.error}</p><button className="link" disabled={busy} onClick={() => void send(turn.question)}>Retry question</button></div>}
        </div>)}
        {busy && <div className="advisor-thinking" role="status"><Leaf size={17} /><span>Reading the kitchen evidence…</span><i /><i /><i /></div>}
        <div ref={latest} />
      </div>
      <div className="advisor-bottom">
        {!turns.length && <div className="advisor-suggestions" aria-label="Suggested questions">{(capabilities?.suggestions ?? examples).map((example) => <button key={example} disabled={busy} onClick={() => void send(example)}>{example}<ArrowUpRight size={15} /></button>)}</div>}
        {!!turns.length && <details className="advisor-more"><summary>Try another kitchen question</summary><div className="advisor-suggestions">{examples.map((example) => <button key={example} disabled={busy} onClick={() => void send(example)}>{example}<ArrowUpRight size={15} /></button>)}</div></details>}
        <form onSubmit={submit} className="advisor-form">
          <label className="sr-only" htmlFor="advisor-question">Your kitchen question</label>
          <div className="advisor-composer"><textarea id="advisor-question" ref={input} value={question} maxLength={1000} rows={2} disabled={busy} placeholder="Ask about forecasts, expiry, waste or recovery…" onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(question); } }} /><button className="button primary" type="submit" aria-label="Send question" disabled={busy || !question.trim()}><Send size={17} /><span>Send</span></button></div>
          <div className="advisor-compose-note"><span>Enter to send · Shift + Enter for a new line</span><span>{question.length}/1000</span></div>
          <details className="advisor-context"><summary>Planning context (optional)</summary><p>Leave blank to use the date and meal in your question. “Tomorrow” uses Asia/Kolkata time. Saved forecasts must match the current dataset.</p><div><label>Planning date <input aria-label="Advisor planning date" type="date" value={planningDate} disabled={busy} onChange={(event) => setPlanningDate(event.target.value)} /></label><label>Meal <select aria-label="Advisor meal" value={meal} disabled={busy} onChange={(event) => setMeal(event.target.value)}><option value="">From my question / all meals</option><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="dinner">Dinner</option></select></label><button type="button" className="link" onClick={() => { setPlanningDate(""); setMeal(""); }}>Clear context</button></div></details>
        </form>
      </div>
    </div>
    <p className="advisor-footer">Suggestions support a manager’s judgment. Food-safety review and approval stay in Recovery. Conversation is held in memory for this session.</p>
  </section>;
}
