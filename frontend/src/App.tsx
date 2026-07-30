import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  ApiError,
  apiBaseUrl,
  listHitlCases,
  submitHitlDecision,
  submitQuery,
} from "./api";
import {
  intentLabels,
  languageLabels,
  queryScenarios,
  syntheticFarmers,
} from "./data";
import type {
  AdvisoryResponse,
  CaseStatus,
  Decision,
  HitlCase,
  Intent,
  QueryRequest,
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
  return "Something went wrong while contacting the demonstrator.";
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

function EvidenceList({ response }: { response: AdvisoryResponse }) {
  return (
    <section className="panel evidence-panel" aria-labelledby="evidence-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Grounding</p>
          <h3 id="evidence-heading">Seeded evidence</h3>
        </div>
        <span className="count-pill">{response.evidence.length} records</span>
      </div>
      <ul className="evidence-list">
        {response.evidence.map((hit) => (
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
    </section>
  );
}

function TraceList({ response }: { response: AdvisoryResponse }) {
  return (
    <section className="panel trace-panel" aria-labelledby="trace-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Audit trail</p>
          <h3 id="trace-heading">Workflow trace</h3>
        </div>
        <span className="count-pill">{response.trace.length} stages</span>
      </div>
      <ol className="trace-list">
        {response.trace.map((event) => (
          <li key={`${event.stage}-${event.detail}`}>
            <span className={`trace-dot trace-${event.status}`} aria-hidden="true" />
            <div>
              <strong>{event.stage.replace(/_/g, " ")}</strong>
              <p>{event.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function App() {
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
    () => syntheticFarmers.find((farmer) => farmer.id === queryForm.farmerId),
    [queryForm.farmerId],
  );
  const activeCase = useMemo(
    () => cases.find((caseItem) => caseItem.case_id === activeCaseId) ?? null,
    [activeCaseId, cases],
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
    } catch (error) {
      setQueueError(getErrorMessage(error));
    } finally {
      setIsLoadingQueue(false);
    }
  }

  useEffect(() => {
    void refreshQueue();
  }, []);

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
    const farmer = syntheticFarmers.find((item) => item.id === farmerId);
    setQueryForm((current) => ({
      ...current,
      farmerId,
      language: farmer?.preferredLanguage ?? current.language,
    }));
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
        ...current,
        reviewerNote: "",
        editedRecommendation: "",
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
          <span className="brand-mark" aria-hidden="true">S</span>
          <span>
            <strong>SasyaAI</strong>
            <small>Extension desk</small>
          </span>
        </a>
        <div className="demo-badge">
          <span aria-hidden="true">●</span>
          Synthetic-data demonstrator
        </div>
      </header>

      <section className="hero" id="workspace">
        <div>
          <p className="eyebrow">Safety-gated advisory review</p>
          <h1>See the evidence. Check the guardrails. Decide with context.</h1>
          <p>
            A local demonstrator for extension officers. Pending recommendations are never shown as
            final farmer advice.
          </p>
        </div>
        <dl className="hero-facts" aria-label="Demonstrator facts">
          <div>
            <dt>Farmers</dt>
            <dd>3 synthetic profiles</dd>
          </div>
          <div>
            <dt>Threshold</dt>
            <dd>70% confidence</dd>
          </div>
          <div>
            <dt>API</dt>
            <dd>{apiBaseUrl}</dd>
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
              <span className="live-indicator">Local API</span>
            </div>

            <div className="form-grid">
              <label>
                Farmer profile
                <select
                  value={queryForm.farmerId}
                  onChange={(event) => selectFarmer(event.target.value)}
                >
                  {syntheticFarmers.map((farmer) => (
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

          <section className="result-region" aria-live="polite" aria-label="Advisory result">
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
                <EvidenceList response={response} />
                <TraceList response={response} />
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

              {activeCase.status === "pending" ? (
                <form className="review-form" onSubmit={handleDecision}>
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
                      <option value="approve">Approve draft</option>
                      <option value="edit_and_approve">Edit and approve</option>
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
