import {
  useCallback,
  useEffect,
  useState,
  useRef,
  lazy,
  Suspense,
} from "react";
import {
  BarChart3,
  ChartNoAxesCombined,
  ClipboardList,
  Utensils,
  ArrowUpRight,
  CircleHelp,
  LayoutDashboard,
  RotateCcw,
  ShieldCheck,
  Upload,
  X,
  MapPinned,
  MessageCircle,
} from "lucide-react";
import { api } from "./api";
import type { Health, Run } from "./types";
import { Dialog, Evidence, ImportDialog } from "./components/Common";
import OverviewPage from "./pages/OverviewPage";
import PlanPage from "./pages/PlanPage";
import RecordPage from "./pages/RecordPage";
import RecoveryPage from "./pages/RecoveryPage";
import ImpactPage from "./pages/ImpactPage";
const StationPage = lazy(() => import("./pages/StationPage"));
const AdvisorPage = lazy(() => import("./pages/AdvisorPage"));

const navigation = [
  {
    id: "overview",
    name: "The big picture",
    hint: "Observe",
    icon: LayoutDashboard,
  },
  {
    id: "plan",
    name: "Plan next meal",
    hint: "Prepare",
    icon: ChartNoAxesCombined,
  },
  { id: "record", name: "Record meal", hint: "Account", icon: ClipboardList },
  { id: "recovery", name: "Recovery", hint: "Review", icon: ShieldCheck },
  { id: "impact", name: "Impact & evidence", hint: "Learn", icon: BarChart3 },
  { id: "station", name: "Field station", hint: "Connect", icon: MapPinned },
  { id: "advisor", name: "AI Kitchen Advisor", hint: "Ask", icon: MessageCircle },
];
const currentPage = () =>
  navigation.some((n) => n.id === location.hash.slice(1))
    ? location.hash.slice(1)
    : "overview";
export default function App() {
  const [page, setPage] = useState(currentPage),
    [refresh, setRefresh] = useState(0),
    [pending, setPending] = useState(0),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [health, setHealth] = useState<Health | null>(null),
    [importOpen, setImportOpen] = useState(false),
    [resetOpen, setResetOpen] = useState(false),
    [evidence, setEvidence] = useState<string[] | null>(null),
    [guideOpen, setGuideOpen] = useState(false),
    [activePlanId, setActivePlanId] = useState(""),
    [activeRecordId, setActiveRecordId] = useState("");
  const mainRef = useRef<HTMLElement>(null);
  const initialPage = useRef(true);
  useEffect(() => {
    const sync = () => setPage(currentPage());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  useEffect(() => {
    document.title = `${navigation.find((n) => n.id === page)?.name} · FoodWise AI`;
    if (initialPage.current) {
      initialPage.current = false;
      return;
    }
    mainRef.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [page]);
  const run: Run = useCallback(async (work, successMessage) => {
    setPending((n) => n + 1);
    setError("");
    try {
      const result = await work();
      if (successMessage) setSuccess(successMessage);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setPending((n) => n - 1);
    }
  }, []);
  useEffect(() => {
    api<Health>("/health")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, [refresh]);
  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(""), 7000);
    return () => clearTimeout(t);
  }, [success]);
  const updated = () => setRefresh((n) => n + 1);
  const navigate = (target: string) => {
    setPage(target);
    if (location.hash !== `#${target}`) location.hash = target;
    setError("");
    setSuccess("");
  };
  const reset = async () => {
    const r = await run(
      () => api("/demo/reset", { confirm: "RESET SYNTHETIC DEMO" }),
      "Practice workspace restored. Generated history and practice decisions reset.",
    );
    if (r) {
      setResetOpen(false);
      setActivePlanId("");
      setActiveRecordId("");
      navigate("overview");
      updated();
    }
  };
  return (
    <div className="app">
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          event.preventDefault();
          mainRef.current?.focus();
          mainRef.current?.scrollIntoView();
        }}
      >
        Skip to main content
      </a>
      <div className="main-shell">
        <header className="masthead">
          <a
            className="brand"
            href="#overview"
            aria-label="FoodWise AI home"
            onClick={(e) => {
              e.preventDefault();
              navigate("overview");
            }}
          >
            <span className="brand-mark">
              <Utensils size={24} strokeWidth={1.7} />
            </span>
            <span>
              foodwise<span className="brand-ai">ai</span>
              <small>THE MINDFUL KITCHEN</small>
            </span>
          </a>
          <span className="masthead-note">
            Good food deserves
            <br />
            <em>a thoughtful plan.</em>
          </span>
          <div className="topbar-actions">
            <span className={`api-indicator ${health ? "connected" : ""}`}>
              {health ? "Kitchen online" : "API unavailable"}
            </span>
            {health?.practice_workspace && (
              <button
                className="icon-button guide-button"
                aria-label="Open three-minute demo guide"
                onClick={() => setGuideOpen(true)}
              >
                <CircleHelp size={21} />
              </button>
            )}
            <button
              aria-label="Import history CSV"
              className="button secondary compact"
              disabled={pending > 0}
              onClick={() => setImportOpen(true)}
            >
              <Upload size={16} />
              <span>Import history</span>
            </button>
            {health?.practice_workspace && (
              <button
                className="icon-button"
                aria-label="Reset practice workspace"
                title="Reset practice workspace"
                disabled={pending > 0}
                onClick={() => setResetOpen(true)}
              >
                <RotateCcw size={18} />
              </button>
            )}
          </div>
        </header>
        <nav className="journey-nav" aria-label="Main navigation">
          {navigation.map((n, index) => (
            <a
              key={n.id}
              href={`#${n.id}`}
              aria-current={page === n.id ? "page" : undefined}
              className={page === n.id ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                navigate(n.id);
              }}
            >
              <span className="nav-number" aria-hidden="true">
                0{index + 1}
              </span>
              <span>
                <small>{n.hint}</small>
                <b>{n.name}</b>
              </span>
              <n.icon
                className="nav-icon"
                size={19}
                strokeWidth={1.5}
                aria-hidden="true"
              />
            </a>
          ))}
        </nav>
        <div className="demo-banner">
          <span>
            <i />
            {health?.synthetic_demo
              ? "Practice workspace · generated kitchen records"
              : health?.dataset_source === "empty"
                ? "Operations workspace · ready for measured records"
                : "Kitchen records · source tracked"}
            {health?.synthetic_demo && (
              <>
                <span className="banner-dot">/</span>Simulated handoffs
              </>
            )}
          </span>
          <span>Works offline. Decisions stay human.</span>
        </div>
        <main id="main" ref={mainRef} tabIndex={-1} data-page={page}>
          <div className="messages">
            {error && (
              <div className="error-message" role="alert">
                <span>{error}</span>
                <button
                  aria-label="Dismiss error"
                  className="icon-button"
                  onClick={() => setError("")}
                >
                  <X size={18} />
                </button>
              </div>
            )}
            {success && (
              <div className="success-message" role="status">
                {success}
              </div>
            )}
            {pending > 0 && (
              <div
                className="loading-line"
                role="status"
                aria-label="Working"
              />
            )}
          </div>
          <div className="page-content" key={page}>
            {page === "overview" && (
              <OverviewPage
                onSaved={updated}
                run={run}
                refresh={refresh}
                onPlan={() => navigate("plan")}
                onEvidence={setEvidence}
                onNavigate={navigate}
              />
            )}
            {page === "plan" && (
              <PlanPage
                run={run}
                busy={pending > 0}
                version={health?.dataset_version ?? 0}
                onRecord={(id) => {
                  setActivePlanId(id);
                  navigate("record");
                }}
                onEvidence={setEvidence}
                onSaved={updated}
              />
            )}
            {page === "record" && (
              <RecordPage
                initialPlanId={activePlanId}
                run={run}
                busy={pending > 0}
                refresh={refresh}
                onSaved={updated}
                onRecovery={(id) => {
                  setActiveRecordId(id);
                  navigate("recovery");
                }}
              />
            )}
            {page === "recovery" && (
              <RecoveryPage
                initialRecordId={activeRecordId}
                run={run}
                busy={pending > 0}
                refresh={refresh}
                onSaved={updated}
              />
            )}
            {page === "impact" && (
              <ImpactPage
                run={run}
                busy={pending > 0}
                refresh={refresh}
                onEvidence={setEvidence}
              />
            )}
            {page === "station" && (
              <Suspense
                fallback={<p role="status">Opening the field station…</p>}
              >
                <StationPage refresh={refresh} onNavigate={navigate} />
              </Suspense>
            )}
            {page === "advisor" && (
              <Suspense fallback={<p role="status">Opening the kitchen advisor…</p>}>
                <AdvisorPage onNavigate={navigate} onEvidence={setEvidence} />
              </Suspense>
            )}
          </div>
          <footer className="page-footer">
            <span>FoodWise AI / A little foresight. A lot less waste.</span>
            <span>
              Local-first · Policy review, not food-safety certification
            </span>
          </footer>
        </main>
      </div>
      {guideOpen && (
        <Dialog
          title="A kitchen story in three minutes"
          onClose={() => setGuideOpen(false)}
          returnFocus='[aria-label="Open three-minute demo guide"]'
        >
          <p className="muted">
            Follow one meal from evidence to action. Kitchen records in this
            workspace are generated; all recovery handoffs are simulated.
          </p>
          <div className="guide-steps">
            {[
              [
                "overview",
                "Read the kitchen",
                "Follow prepared food into consumed food, untouched surplus and plate waste. Open a finding to inspect its records.",
              ],
              [
                "plan",
                "Make a better preparation decision",
                "Set expected diners, calculate a forecast, and move the preparation slider. Compare both surplus and shortage before approving.",
              ],
              [
                "record",
                "Close the accounting loop",
                "Load the separate 100 kg fixture to try mass-balance validation. Save the actual meal to make it available for recovery.",
              ],
              [
                "recovery",
                "Review, then recover",
                "For DEMO-100: review 10 kg untouched surplus, save the generated hot-holding example, check dinner demand and enter a manual 20 kg total when history is sparse. Reserve 10 kg and approve the revised dinner plan as a qualified demo manager. Plate waste is blocked from human use; segregate its 8 kg, estimate potential and record a simulated biogas handoff.",
              ],
              [
                "impact",
                "Show the evidence",
                "Log dinner against the approved reuse plan: 20 kg total, 18 consumed, 1 untouched and 1 plate waste. Inspect 10 kg recorded reuse and theoretical biogas potential separately from actual energy, which is not measured. New dinner actuals feed future dinner forecasts; return to Overview for ingredient review and offline recipe ideas.",
              ],
            ].map(([target, title, description], index) => (
              <button
                key={target}
                className="guide-step"
                onClick={() => {
                  setGuideOpen(false);
                  navigate(target);
                }}
              >
                <span className="guide-number">0{index + 1}</span>
                <span>
                  <b>{title}</b>
                  <small>{description}</small>
                </span>
                <ArrowUpRight size={20} />
              </button>
            ))}
          </div>
        </Dialog>
      )}
      {importOpen && (
        <ImportDialog
          run={run}
          busy={pending > 0}
          onClose={() => setImportOpen(false)}
          onDone={updated}
        />
      )}
      {evidence && (
        <Evidence ids={evidence} onClose={() => setEvidence(null)} />
      )}
      {resetOpen && (
        <Dialog
          title="Reset the practice workspace?"
          onClose={() => setResetOpen(false)}
          returnFocus='[aria-label="Reset practice workspace"]'
        >
          <p>
            This clears approved plans, actual logs, recovery reviews, handoffs,
            and imported history in this demo database. It restores the supplied
            270 generated historical records and raw ingredient inventory.
          </p>
          <div className="flex gap-3 mt-6">
            <button
              className="button secondary"
              onClick={() => setResetOpen(false)}
            >
              Keep current demo
            </button>
            <button
              className="button danger"
              disabled={pending > 0}
              onClick={reset}
            >
              Reset practice workspace
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
