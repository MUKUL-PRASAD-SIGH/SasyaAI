import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  ApiError,
  apiBaseUrl,
  configureApiKey,
  getKnowledgeStats,
  getRuntimeHealth,
  listAgents,
  listDemoFarmers,
  listSyntheticProductionFarmers,
  listHitlCases,
  submitHitlDecision,
  submitQuery,
} from "./api";
import {
  intentLabels,
  languageLabels,
  queryScenarios,
  syntheticFarmers,
  type SyntheticFarmer,
} from "./data";
import type {
  AdvisoryResponse,
  AgentDescriptor,
  AgentRun,
  CaseStatus,
  Decision,
  Evidence,
  HitlCase,
  Intent,
  KnowledgeStats,
  QueryRequest,
  RuntimeHealth,
  TraceEvent,
  VerificationCheck,
} from "./types";

type QueryForm = {
  farmerId: string;
  query: string;
  intent: "auto" | Intent;
  language: string;
  requestedDose: string;
};

type ReviewForm = {
  decision: Decision;
  reviewerName: string;
  reviewerNote: string;
  editedRecommendation: string;
};

const initialScenario = queryScenarios[0];

const initialQueryForm: QueryForm = {
  farmerId: syntheticFarmers[0].id,
  query: initialScenario.query,
  intent: initialScenario.intent,
  language: syntheticFarmers[0].preferredLanguage,
  requestedDose: initialScenario.requestedDose,
};

const initialReviewForm: ReviewForm = {
  decision: "approve",
  reviewerName: "Demo extension officer",
  reviewerNote: "",
  editedRecommendation: "",
};

function statusLabel(status: "delivered" | "requires_human_review" | CaseStatus): string {
  if (status === "delivered") {
    return "Delivered after checks";
  }
  if (status === "requires_human_review") {
    return "Awaiting human review";
  }
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function intentLabel(intent?: Intent | null): string {
  return intent ? intentLabels[intent] : "Advisory";
}

function formatDate(value?: string): string {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Something went wrong while contacting the advisory runtime.";
}

function VerificationList({ checks }: { checks: VerificationCheck[] }) {
  return (
    <ul className="verification-list">
      {checks.map((check) => (
        <li key={check.name} className={`verification-item verification-${check.status}`}>
          <span className="verification-mark" aria-hidden="true">
            {check.status === "pass" ? "✓" : check.status === "fail" ? "!" : "–"}
          </span>
          <div>
            <strong>{check.name.replace(/_/g, " ")}</strong>
            <p>{check.message}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  return (
    <ul className="evidence-list">
      {evidence.map((hit) => (
        <li key={`${hit.source}-${hit.title}`}>
          <div className="evidence-title-row">
            <strong>{hit.title}</strong>
            <span>{Math.round(hit.score * 100)}% match</span>
          </div>
          <p className="source-tag">{hit.source.replace(/_/g, " ")}</p>
          {Object.keys(hit.metadata).length > 0 && (
            <dl className="metadata-list">
              {Object.entries(hit.metadata).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replace(/_/g, " ")}</dt>
                  <dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </li>
      ))}
    </ul>
  );
}

function TraceList({ trace }: { trace: TraceEvent[] }) {
  return (
    <ol className="trace-list">
      {trace.map((event) => (
        <li key={`${event.stage}-${event.detail}`}>
          <span className={`trace-dot trace-${event.status}`} aria-hidden="true" />
          <div>
            <strong>{event.stage.replace(/_/g, " ")}</strong>
            <p>{event.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function AgentRunList({ runs }: { runs: AgentRun[] }) {
  return (
    <ol className="agent-run-list">
      {runs.map((run, index) => (
        <li key={`${run.agent_id}-${index}`} className={`agent-run agent-${run.status}`}>
          <div className="agent-run-index" aria-hidden="true">
            {String(index + 1).padStart(2, "0")}
          </div>
          <div className="agent-run-copy">
            <div className="agent-run-title">
              <strong>{run.name}</strong>
              <span className={`mode-chip mode-${run.execution_mode}`}>
                {run.execution_mode === "llm" ? run.model || "LLM" : run.execution_mode}
              </span>
            </div>
            <p>{run.summary}</p>
            <small>
              {run.duration_ms} ms
              {run.input_sources.length > 0 ? ` · ${run.input_sources.join(" · ")}` : ""}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}

function App() {
  const [farmers, setFarmers] = useState<SyntheticFarmer[]>(syntheticFarmers);
  const [runtime, setRuntime] = useState<RuntimeHealth | null>(null);
  const [agents, setAgents] = useState<AgentDescriptor[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeStats | null>(null);
  const [systemError, setSystemError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [accessStatus, setAccessStatus] = useState<string | null>(null);
  const [theme, setTheme] = useState<"field" | "night">(() =>
    window.localStorage.getItem("sasya-theme") === "night" ? "night" : "field",
  );
  const [queryForm, setQueryForm] = useState<QueryForm>(initialQueryForm);
  const [scenarioId, setScenarioId] = useState(initialScenario.id);
  const [response, setResponse] = useState<AdvisoryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [cases, setCases] = useState<HitlCase[]>([]);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [isLoadingQueue, setIsLoadingQueue] = useState(true);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [reviewForm, setReviewForm] = useState<ReviewForm>(initialReviewForm);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [isDeciding, setIsDeciding] = useState(false);

  const selectedFarmer = useMemo(
    () => farmers.find((farmer) => farmer.id === queryForm.farmerId),
    [farmers, queryForm.farmerId],
  );
  const activeCase = useMemo(
    () => cases.find((caseItem) => caseItem.case_id === activeCaseId) ?? null,
    [activeCaseId, cases],
  );
  const activeCaseFarmer = useMemo(
    () =>
      activeCase
        ? farmers.find((farmer) => farmer.id === activeCase.farmer_id)
        : undefined,
    [activeCase, farmers],
  );
  const activeCaseHasHardSafetyFailure = useMemo(
    () => activeCase?.verification?.some((check) => check.status === "fail") ?? false,
    [activeCase],
  );

  async function refreshQueue() {
    setIsLoadingQueue(true);
    setQueueError(null);
    try {
      const nextCases = await listHitlCases();
      setCases(nextCases);
      setActiveCaseId((currentCaseId) => {
        if (currentCaseId && nextCases.some((caseItem) => caseItem.case_id === currentCaseId)) {
          return currentCaseId;
        }
        return nextCases[0]?.case_id ?? null;
      });
      return true;
    } catch (error) {
      setQueueError(getErrorMessage(error));
      return false;
    } finally {
      setIsLoadingQueue(false);
    }
  }

  async function refreshSystemContext() {
    const [healthResult, agentResult, knowledgeResult, farmerResult, syntheticFarmerResult] =
      await Promise.allSettled([
        getRuntimeHealth(),
        listAgents(),
        getKnowledgeStats(),
        listDemoFarmers(),
        listSyntheticProductionFarmers(),
      ]);

    if (healthResult.status === "fulfilled") {
      setRuntime(healthResult.value);
    }
    if (agentResult.status === "fulfilled") {
      setAgents(agentResult.value);
    }
    if (knowledgeResult.status === "fulfilled") {
      setKnowledge(knowledgeResult.value);
    }
    const availableFarmerResult =
      syntheticFarmerResult.status === "fulfilled" ? syntheticFarmerResult : farmerResult;
    if (availableFarmerResult.status === "fulfilled" && availableFarmerResult.value.length > 0) {
      setFarmers(
        availableFarmerResult.value.map((farmer) => ({
          id: farmer.farmer_id,
          name: farmer.name,
          state: farmer.state,
          district: farmer.district,
          preferredLanguage: farmer.preferred_language,
          crop: farmer.current_crop,
          season: farmer.season,
          waterBudget: farmer.water_budget_mm,
        })),
      );
    }

    if (
      healthResult.status === "rejected" ||
      agentResult.status === "rejected" ||
      knowledgeResult.status === "rejected"
    ) {
      setSystemError(
        "Some runtime telemetry is unavailable. Advisory safety gates remain authoritative.",
      );
    } else {
      setSystemError(null);
    }
    return agentResult.status === "fulfilled" && knowledgeResult.status === "fulfilled";
  }

  useEffect(() => {
    void refreshQueue();
  }, []);

  useEffect(() => {
    void refreshSystemContext();
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("sasya-theme", theme);
  }, [theme]);

  useEffect(() => {
    setReviewError(null);
    setReviewForm((current) => ({
      ...initialReviewForm,
      decision: activeCaseHasHardSafetyFailure ? "reject" : initialReviewForm.decision,
      reviewerName: current.reviewerName,
    }));
  }, [activeCaseId, activeCaseHasHardSafetyFailure]);

  function applyScenario(nextScenarioId: string) {
    const scenario = queryScenarios.find((item) => item.id === nextScenarioId);
    if (!scenario) {
      return;
    }
    setScenarioId(nextScenarioId);
    setQueryForm((current) => ({
      ...current,
      query: scenario.query,
      intent: scenario.intent,
      requestedDose: scenario.requestedDose,
    }));
  }

  function selectFarmer(farmerId: string) {
    const farmer = farmers.find((item) => item.id === farmerId);
    setQueryForm((current) => ({
      ...current,
      farmerId,
      language: farmer?.preferredLanguage ?? current.language,
    }));
  }

  async function handleAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    configureApiKey(apiKey);
    setAccessStatus("Checking role-scoped access…");
    const [systemReady, queueReady] = await Promise.all([
      refreshSystemContext(),
      refreshQueue(),
    ]);
    setAccessStatus(
      systemReady && queueReady
        ? "Access key is active in memory for this browser tab."
        : "The key was not accepted for all operator routes.",
    );
    setApiKey("");
  }

  async function handleQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryError(null);
    const requestedDose = queryForm.requestedDose.trim();
    const payload: QueryRequest = {
      farmer_id: queryForm.farmerId,
      query: queryForm.query.trim(),
      language: queryForm.language,
      ...(queryForm.intent === "auto" ? {} : { intent: queryForm.intent }),
    };

    if (requestedDose) {
      const numericDose = Number(requestedDose);
      if (!Number.isFinite(numericDose) || numericDose < 0) {
        setQueryError("Enter a non-negative pesticide dose or leave the field empty.");
        return;
      }
      payload.requested_dose_ml_per_l = numericDose;
    }

    setIsSubmitting(true);
    try {
      const nextResponse = await submitQuery(payload);
      setResponse(nextResponse);
      if (nextResponse.hitl_case_id) {
        setActiveCaseId(nextResponse.hitl_case_id);
        await refreshQueue();
      }
    } catch (error) {
      setResponse(null);
      setQueryError(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCase) {
      return;
    }
    setReviewError(null);
    if (activeCaseHasHardSafetyFailure && reviewForm.decision !== "reject") {
      setReviewError(
        "Cases with failed deterministic safety checks can only be rejected.",
      );
      return;
    }
    if (
      reviewForm.decision === "edit_and_approve" &&
      !reviewForm.editedRecommendation.trim()
    ) {
      setReviewError("An edited recommendation is required before you can approve an edit.");
      return;
    }

    setIsDeciding(true);
    try {
      const updatedCase = await submitHitlDecision(activeCase.case_id, {
        decision: reviewForm.decision,
        reviewer_name: reviewForm.reviewerName.trim() || "Demo extension officer",
        reviewer_note: reviewForm.reviewerNote.trim(),
        ...(reviewForm.decision === "edit_and_approve"
          ? { edited_recommendation: reviewForm.editedRecommendation.trim() }
          : {}),
      });
      setCases((currentCases) =>
        currentCases.map((caseItem) =>
          caseItem.case_id === updatedCase.case_id ? updatedCase : caseItem,
        ),
      );
      setReviewForm((current) => ({
        ...initialReviewForm,
        reviewerName: current.reviewerName,
      }));
    } catch (error) {
      setReviewError(getErrorMessage(error));
    } finally {
      setIsDeciding(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="SasyaAI extension desk home">
          <span className="brand-mark" aria-hidden="true">सा</span>
          <span>
            <strong>SasyaAI</strong>
            <small>Agent operations</small>
          </span>
        </a>
        <div className="topbar-actions">
          <div className={`runtime-badge runtime-${runtime?.runtime_mode ?? "connecting"}`}>
            <span aria-hidden="true">●</span>
            {runtime
              ? `${runtime.runtime_mode} · ${runtime.agent_execution}`
              : "Connecting to runtime"}
          </div>
          <button
            className="theme-toggle"
            type="button"
            aria-label={`Switch to ${theme === "field" ? "night" : "field"} theme`}
            onClick={() => setTheme((current) => (current === "field" ? "night" : "field"))}
          >
            <span aria-hidden="true">{theme === "field" ? "◐" : "☀"}</span>
            {theme === "field" ? "Night" : "Field"}
          </button>
        </div>
      </header>

      <section className="hero" id="workspace">
        <div>
          <p className="eyebrow">Governed agricultural intelligence</p>
          <h1>One field question. A coordinated team of accountable agents.</h1>
          <p>
            Route, retrieve, reason, reflect, and verify every advisory—with live connectors,
            source provenance, and human authority at the final safety boundary.
          </p>
        </div>
        <dl className="hero-facts" aria-label="Runtime facts">
          <div>
            <dt>Agent team</dt>
            <dd>{agents.length || 9} governed roles</dd>
          </div>
          <div>
            <dt>Knowledge</dt>
            <dd>
              {knowledge
                ? `${knowledge.total_documents} records`
                : "Loading coverage"}
            </dd>
          </div>
          <div>
            <dt>Storage</dt>
            <dd>
              {knowledge
                ? knowledge.runtime_mode === "production"
                  ? "Postgres · Qdrant"
                  : "Versioned seed files"
                : "Connecting"}
            </dd>
          </div>
        </dl>
      </section>

      {runtime?.runtime_mode === "production" && runtime.data_source_mode === "synthetic" && (
        <p className="synthetic-notice" role="status">
          Synthetic production mode: farmer, consent, market, and knowledge records are labelled
          fixtures. This environment is for internal workflow testing; enable the approved AgriStack
          gateway before serving real farmers.
        </p>
      )}

      {systemError && <p className="system-notice" role="status">{systemError}</p>}

      {runtime?.runtime_mode === "production" && (
        <form className="access-form" onSubmit={handleAccess}>
          <div>
            <strong>Operator access</strong>
            <span>
              Enter a role-scoped API key. It stays in memory only and is cleared on reload.
            </span>
          </div>
          <label>
            <span className="sr-only">Operator API key</span>
            <input
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="Role-scoped API key"
              minLength={24}
              required
            />
          </label>
          <button className="secondary-button" type="submit">Connect</button>
          {accessStatus && <small role="status">{accessStatus}</small>}
        </form>
      )}

      <section className="operations-strip" aria-labelledby="operations-heading">
        <div className="operations-copy">
          <p className="eyebrow">Runtime topology</p>
          <h2 id="operations-heading">Specialists work; the verifier controls delivery.</h2>
          <p>
            The activity contract exposes concise operational summaries, inputs, model identity,
            confidence, and latency. It never exposes private chain-of-thought.
          </p>
        </div>
        <div className="agent-roster">
          {(agents.length > 0
            ? agents
            : [
                { agent_id: "intent_router", name: "Intent Router", kind: "reasoning" },
                { agent_id: "specialist", name: "Domain Specialist", kind: "reasoning" },
                { agent_id: "reflection_agent", name: "Reflection Agent", kind: "reasoning" },
                { agent_id: "safety_verifier", name: "Safety Verifier", kind: "safety" },
              ]
          ).map((agent, index) => (
            <div className="roster-agent" key={agent.agent_id}>
              <span className="roster-number">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{agent.name}</strong>
                <small>
                  {agent.kind === "reasoning" || agent.kind === "manager"
                    ? "LLM"
                    : agent.kind === "safety"
                      ? "deterministic"
                      : "tool"}
                </small>
              </div>
            </div>
          ))}
        </div>
        <dl className="coverage-grid" aria-label="Knowledge coverage">
          <div>
            <dt>Regions</dt>
            <dd>{knowledge?.regions ?? "—"}</dd>
          </div>
          <div>
            <dt>Crops</dt>
            <dd>{knowledge?.crops ?? "—"}</dd>
          </div>
          <div>
            <dt>Profiles</dt>
            <dd>{farmers.length}</dd>
          </div>
          <div>
            <dt>Safety threshold</dt>
            <dd>70%</dd>
          </div>
        </dl>
      </section>

      <div className="workspace-grid">
        <section className="query-column" aria-labelledby="advisory-heading">
          <form className="panel query-panel" onSubmit={handleQuery}>
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Advisory simulator</p>
                <h2 id="advisory-heading">Run a safety-gated query</h2>
              </div>
              <span className="live-indicator">
                {runtime?.runtime_mode === "production" ? "Production API" : "Evaluation API"}
              </span>
            </div>

            <div className="form-grid">
              <label>
                Farmer profile
                <select
                  value={queryForm.farmerId}
                  onChange={(event) => selectFarmer(event.target.value)}
                >
                  {farmers.map((farmer) => (
                    <option key={farmer.id} value={farmer.id}>
                      {farmer.name} · {farmer.district}, {farmer.state}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Demo scenario
                <select value={scenarioId} onChange={(event) => applyScenario(event.target.value)}>
                  {queryScenarios.map((scenario) => (
                    <option key={scenario.id} value={scenario.id}>
                      {scenario.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {selectedFarmer && (
              <aside className="farmer-context" aria-label="Selected synthetic farmer context">
                <div>
                  <span>Current crop</span>
                  <strong>{selectedFarmer.crop}</strong>
                </div>
                <div>
                  <span>Water budget</span>
                  <strong>{selectedFarmer.waterBudget} mm</strong>
                </div>
                <div>
                  <span>Preferred language</span>
                  <strong>{languageLabels[selectedFarmer.preferredLanguage] ?? "English"}</strong>
                </div>
              </aside>
            )}

            <label>
              Farmer question
              <textarea
                value={queryForm.query}
                onChange={(event) => setQueryForm((current) => ({ ...current, query: event.target.value }))}
                rows={4}
                minLength={3}
                maxLength={1000}
                required
              />
            </label>

            <div className="form-grid compact-grid">
              <label>
                Route
                <select
                  value={queryForm.intent}
                  onChange={(event) =>
                    setQueryForm((current) => ({
                      ...current,
                      intent: event.target.value as QueryForm["intent"],
                    }))
                  }
                >
                  <option value="auto">Detect from question</option>
                  {Object.entries(intentLabels).map(([intent, label]) => (
                    <option key={intent} value={intent}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Language
                <select
                  value={queryForm.language}
                  onChange={(event) => setQueryForm((current) => ({ ...current, language: event.target.value }))}
                >
                  {Object.entries(languageLabels).map(([code, label]) => (
                    <option key={code} value={code}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Dose (ml/L)
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={queryForm.requestedDose}
                  onChange={(event) =>
                    setQueryForm((current) => ({ ...current, requestedDose: event.target.value }))
                  }
                  placeholder="Optional"
                />
              </label>
            </div>

            {queryError && <p className="form-message error-message" role="alert">{queryError}</p>}
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Running safety checks…" : "Run advisory workflow"}
            </button>
          </form>

          <section className="result-region" aria-label="Advisory result">
            <p className="sr-only" aria-live="polite">
              {response
                ? `Advisory ${statusLabel(response.status)} at ${Math.round(response.confidence * 100)} percent confidence.`
                : ""}
            </p>
            {!response && !queryError && (
              <div className="empty-state">
                <span aria-hidden="true">⌁</span>
                <h2>Ready for a reviewable advisory</h2>
                <p>Select a scenario to inspect the evidence, verification results, and workflow trace.</p>
              </div>
            )}

            {response && (
              <>
                <section className="result-card">
                  <div className="result-topline">
                    <span className={`status-chip status-${response.status}`}>
                      {statusLabel(response.status)}
                    </span>
                    <span className="confidence">{Math.round(response.confidence * 100)}% confidence</span>
                  </div>
                  <p className="eyebrow">{intentLabel(response.intent)}</p>
                  <h2>{response.recommendation}</h2>
                  <p className="explanation">{response.explanation}</p>
                  {response.status === "requires_human_review" && (
                    <div className="review-callout">
                      <strong>Officer action needed.</strong> This draft is pending review and must not be
                      presented as final farmer advice.
                      {response.hitl_case_id && (
                        <button
                          type="button"
                          className="text-button"
                          onClick={() => setActiveCaseId(response.hitl_case_id)}
                        >
                          Open review case
                        </button>
                      )}
                    </div>
                  )}
                </section>

                <section className="panel verification-panel" aria-labelledby="verification-heading">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">Deterministic gate</p>
                      <h3 id="verification-heading">Verification results</h3>
                    </div>
                    <span className="count-pill">{response.verification.length} checks</span>
                  </div>
                  <VerificationList checks={response.verification} />
                </section>
                <section className="panel evidence-panel" aria-labelledby="evidence-heading">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">Grounding</p>
                <h3 id="evidence-heading">Grounded evidence</h3>
                    </div>
                    <span className="count-pill">{response.evidence.length} records</span>
                  </div>
                  <EvidenceList evidence={response.evidence} />
                </section>
                {response.agent_runs.length > 0 && (
                  <section className="panel agents-panel" aria-labelledby="agent-runs-heading">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">Agent execution</p>
                        <h3 id="agent-runs-heading">Coordinated run</h3>
                      </div>
                      <span className="count-pill">{response.agent_runs.length} agents</span>
                    </div>
                    <AgentRunList runs={response.agent_runs} />
                  </section>
                )}
                <section className="panel trace-panel" aria-labelledby="trace-heading">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">Audit trail</p>
                      <h3 id="trace-heading">Workflow trace</h3>
                    </div>
                    <span className="count-pill">{response.trace.length} stages</span>
                  </div>
                  <TraceList trace={response.trace} />
                </section>
              </>
            )}
          </section>
        </section>

        <aside className="review-column" aria-labelledby="review-heading">
          <section className="panel queue-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Human-in-the-loop</p>
                <h2 id="review-heading">Review queue</h2>
              </div>
              <button className="secondary-button" type="button" onClick={() => void refreshQueue()} disabled={isLoadingQueue}>
                {isLoadingQueue ? "Loading…" : "Refresh"}
              </button>
            </div>

            {queueError && <p className="form-message error-message" role="alert">{queueError}</p>}
            {!queueError && !isLoadingQueue && cases.length === 0 && (
              <p className="queue-empty">No review cases yet. Run a diagnosis or blocked-dose scenario to create one.</p>
            )}
            {cases.length > 0 && (
              <ul className="queue-list">
                {cases.map((caseItem) => (
                  <li key={caseItem.case_id}>
                    <button
                      type="button"
                      aria-label={`Review case ${caseItem.case_id}`}
                      className={`queue-case ${activeCase?.case_id === caseItem.case_id ? "is-selected" : ""}`}
                      onClick={() => setActiveCaseId(caseItem.case_id)}
                    >
                      <span className={`queue-status status-${caseItem.status}`}>{statusLabel(caseItem.status)}</span>
                      <strong>{intentLabel(caseItem.intent)}</strong>
                      <span>{caseItem.farmer_id}</span>
                      <small>{caseItem.reason}</small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {activeCase && (
            <section className="panel case-panel" aria-labelledby="case-heading">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Case {activeCase.case_id.slice(0, 8)}</p>
                  <h3 id="case-heading">{statusLabel(activeCase.status)}</h3>
                </div>
                {activeCase.confidence !== null && activeCase.confidence !== undefined && (
                  <span className="confidence">{Math.round(activeCase.confidence * 100)}%</span>
                )}
              </div>
              <dl className="case-facts">
                <div>
                  <dt>Farmer</dt>
                  <dd>{activeCase.farmer_id}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{formatDate(activeCase.created_at)}</dd>
                </div>
              </dl>
              {activeCaseFarmer && (
                <aside className="case-farmer-context" aria-label="Selected case farmer context">
                  <div>
                    <span>Farmer</span>
                    <strong>{activeCaseFarmer.name} · {activeCaseFarmer.district}</strong>
                  </div>
                  <div>
                    <span>Current crop</span>
                    <strong>{activeCaseFarmer.crop}</strong>
                  </div>
                  <div>
                    <span>Water budget</span>
                    <strong>{activeCaseFarmer.waterBudget} mm</strong>
                  </div>
                </aside>
              )}
              <p className="case-reason">{activeCase.reason}</p>
              {activeCase.original_recommendation && (
                <div className="case-draft">
                  <span>Original draft</span>
                  <p>{activeCase.original_recommendation}</p>
                  {activeCase.original_explanation && <small>{activeCase.original_explanation}</small>}
                </div>
              )}

              {activeCase.verification && activeCase.verification.length > 0 && (
                <details className="case-details" open>
                  <summary>Review the deterministic checks</summary>
                  <VerificationList checks={activeCase.verification} />
                </details>
              )}

              {activeCase.evidence && activeCase.evidence.length > 0 && (
                <details className="case-details" open>
                  <summary>Review seeded evidence ({activeCase.evidence.length})</summary>
                  <EvidenceList evidence={activeCase.evidence} />
                </details>
              )}

              {activeCase.trace && activeCase.trace.length > 0 && (
                <details className="case-details">
                  <summary>Review workflow trace ({activeCase.trace.length})</summary>
                  <TraceList trace={activeCase.trace} />
                </details>
              )}

              {activeCase.agent_runs && activeCase.agent_runs.length > 0 && (
                <details className="case-details">
                  <summary>Review agent execution ({activeCase.agent_runs.length})</summary>
                  <AgentRunList runs={activeCase.agent_runs} />
                </details>
              )}

              {activeCase.status === "pending" ? (
                <form className="review-form" onSubmit={handleDecision}>
                  {activeCaseHasHardSafetyFailure && (
                    <div className="review-callout safety-block-callout" role="alert">
                      <strong>Hard safety check failed.</strong> Policy permits only rejection for this
                      case. Start a fresh, safely parameterised request for a revised advisory.
                    </div>
                  )}
                  <label>
                    Decision
                    <select
                      value={reviewForm.decision}
                      onChange={(event) =>
                        setReviewForm((current) => ({
                          ...current,
                          decision: event.target.value as Decision,
                        }))
                      }
                    >
                      {!activeCaseHasHardSafetyFailure && (
                        <option value="approve">Approve draft</option>
                      )}
                      {!activeCaseHasHardSafetyFailure && (
                        <option value="edit_and_approve">Edit and approve</option>
                      )}
                      <option value="reject">Reject draft</option>
                    </select>
                  </label>
                  <label>
                    Reviewer name
                    <input
                      value={reviewForm.reviewerName}
                      onChange={(event) =>
                        setReviewForm((current) => ({ ...current, reviewerName: event.target.value }))
                      }
                      maxLength={120}
                      required
                    />
                  </label>
                  <label>
                    Decision reason
                    <textarea
                      value={reviewForm.reviewerNote}
                      onChange={(event) =>
                        setReviewForm((current) => ({ ...current, reviewerNote: event.target.value }))
                      }
                      rows={3}
                      minLength={1}
                      maxLength={1000}
                      required
                    />
                  </label>
                  {reviewForm.decision === "edit_and_approve" && (
                    <label>
                      Edited farmer-facing recommendation
                      <textarea
                        value={reviewForm.editedRecommendation}
                        onChange={(event) =>
                          setReviewForm((current) => ({
                            ...current,
                            editedRecommendation: event.target.value,
                          }))
                        }
                        rows={4}
                        minLength={1}
                        maxLength={2000}
                        required
                      />
                    </label>
                  )}
                  {reviewError && <p className="form-message error-message" role="alert">{reviewError}</p>}
                  <button className="primary-button" type="submit" disabled={isDeciding}>
                    {isDeciding ? "Recording decision…" : "Record immutable decision"}
                  </button>
                </form>
              ) : (
                <div className="decision-summary">
                  <strong>Decision recorded</strong>
                  <p>{activeCase.reviewer_note ?? "No reviewer note is available."}</p>
                  {activeCase.edited_recommendation && (
                    <p><span>Approved edit:</span> {activeCase.edited_recommendation}</p>
                  )}
                </div>
              )}

              {activeCase.decision_history && activeCase.decision_history.length > 0 && (
                <details className="case-details">
                  <summary>Immutable decision history ({activeCase.decision_history.length})</summary>
                  <ol className="history-list">
                    {activeCase.decision_history.map((event) => (
                      <li key={`${event.decided_at}-${event.reviewer_name}`}>
                        <strong>{event.decision.replace(/_/g, " ")}</strong>
                        <span>{event.reviewer_name} · {formatDate(event.decided_at)}</span>
                        <p>{event.reviewer_note}</p>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}

export default App;
