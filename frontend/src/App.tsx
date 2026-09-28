import { useCallback, useEffect, useMemo, useState } from "react";
import { api, describeApiError } from "./api";
import { PlanResult } from "./types";
import { KpiBanner } from "./components/KpiBanner";
import { ErrorBanner, Spinner } from "./components/ui";
import { OverviewView } from "./components/OverviewView";
import { ProductionView } from "./components/ProductionView";
import { CommercialView } from "./components/CommercialView";
import { AllocationView } from "./components/AllocationView";

type TabId = "today" | "production" | "commercial" | "allocation" | "assistant";

const TABS: { id: TabId; label: string; step: string }[] = [
  { id: "today", label: "Today", step: "1 · Load & compare" },
  { id: "production", label: "Production", step: "2 · Compare" },
  { id: "commercial", label: "Commercial", step: "3 · Plan" },
  { id: "allocation", label: "Allocation", step: "4 · Decide" },
  { id: "assistant", label: "Assistant", step: "5 · Explain" },
];

type Status = "loading" | "ready" | "error";

export function App() {
  const [tab, setTab] = useState<TabId>("today");
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);
  const [errorIssues, setErrorIssues] = useState<
    { location: string; message: string }[]
  >([]);
  const [plan, setPlan] = useState<PlanResult | null>(null);

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    setErrorIssues([]);
    try {
      // const [health] = await Promise.all([api.health(), api.seed()]);

      const planResult = await api.plan();
      setPlan(planResult);
      setStatus("ready");
    } catch (e) {
      const err = e as { issues?: { location: string; message: string }[] };
      setError(describeApiError(e));
      setErrorIssues(err.issues ?? []);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const topStatic = useMemo(() => {
    if (!plan) return null;
    return (
      <div className="top-static">
        <div className="data-health-line">
          <span className={`status-dot status-ok`} aria-hidden="true" />
          <span>
            <strong>Workbook loaded & validated</strong> —{" "}
            {plan.data_health.farm_count} farms ·{" "}
            {plan.data_health.client_count} clients · station{" "}
            {plan.data_health.station_capacity_t.toFixed(0)} t
          </span>
          <span className="reference-prices">
            reference prices:{" "}
            {(["A", "B", "C", "D"] as const)
              .map(
                (s) =>
                  `${s} €${plan.data_health.reference_prices[s].toLocaleString()}`,
              )
              .join(" · ")}
          </span>
        </div>
        <KpiBanner kpis={plan.kpis} />
      </div>
    );
  }, [plan]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>Atlas Fresh</h1>
          <p>Daily Apple Export Planner — Production ↔ Commercial committee</p>
        </div>
      </header>

      <nav className="tabs" aria-label="Workspace sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "tab-active" : ""}`}
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id ? "page" : undefined}
          >
            <span className="tab-step">{t.step}</span>
            <span className="tab-label">{t.label}</span>
          </button>
        ))}
      </nav>

      <main className="app-main">
        {status === "loading" && (
          <div className="page-loading">
            <Spinner label="Loading & validating the workbook, then planning today's export allocation…" />
          </div>
        )}

        {status === "error" && (
          <ErrorBanner
            message={error ?? "Unknown error"}
            issues={errorIssues}
            onRetry={() => void load()}
          />
        )}

        {status === "ready" && plan && (
          <>
            {topStatic}
            <div
              className="page"
              role="tabpanel"
              aria-label={TABS.find((t) => t.id === tab)?.label}
            >
              {tab === "today" && <OverviewView plan={plan} />}
              {tab === "production" && (
                <ProductionView farms={plan.farm_comparisons} />
              )}
              {tab === "commercial" && (
                <CommercialView clients={plan.client_statuses} />
              )}
              {tab === "allocation" && <AllocationView plan={plan} />}
              {/* {tab === "assistant" && <AssistantPanel plan={plan} />} */}
            </div>
          </>
        )}
      </main>

      <footer className="app-footer">
        <span>
          Decision-support only — Production and Commercial approve execution;
          the engine never contacts farms, clients or external systems.
        </span>
        <span>
          Source workbook:{" "}
          <code>data/Atlas_Fresh_Production_Commercial_Data.xlsx</code>{" "}
          (synthetic, unchanged).
        </span>
      </footer>
    </div>
  );
}
