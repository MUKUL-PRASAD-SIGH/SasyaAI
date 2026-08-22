import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  ApiError,
  clearSession,
  fetchAuthMe,
  getKnowledgeStats,
  getRuntimeHealth,
  googleLogin,
  listAgents,
  listAuditEvents,
  listDemoFarmers,
  listFarmerImages,
  listHitlCases,
  listSyntheticProductionFarmers,
  loadStoredSession,
  login,
  logout,
  registerFarmer,
  searchMemory,
  storeSession,
  submitFeedback,
  submitHitlDecision,
  submitQuery,
  uploadFarmerImage,
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
  AppRole,
  CaseStatus,
  Decision,
  Evidence,
  FarmerImage,
  HitlCase,
  Intent,
  KnowledgeStats,
  OnboardingPayload,
  QueryRequest,
  RuntimeHealth,
  SessionPrincipal,
  TraceEvent,
  VerificationCheck,
} from "./types";

type QueryForm = {
  farmerId: string;
  query: string;
  intent: "auto" | Intent;
  language: string;
  requestedDose: string;
  imageId: string;
};

type ReviewForm = {
  decision: Decision;
  reviewerName: string;
  reviewerNote: string;
  editedRecommendation: string;
};

type WorkspaceTab =
  | "profile"
  | "advisory"
  | "images"
  | "history"
  | "workflow"
  | "farmers"
  | "review"
  | "metrics"
  | "runtime"
  | "audit"
  | "agents";

const initialScenario = queryScenarios[0];

const initialQueryForm: QueryForm = {
  farmerId: syntheticFarmers[0].id,
  query: initialScenario.query,
  intent: initialScenario.intent,
  language: syntheticFarmers[0].preferredLanguage,
  requestedDose: initialScenario.requestedDose,
  imageId: "",
};

const initialReviewForm: ReviewForm = {
  decision: "approve",
  reviewerName: "Demo extension officer",
  reviewerNote: "",
  editedRecommendation: "",
};

const initialOnboarding: OnboardingPayload = {
  name: "",
  email: "",
  state: "Maharashtra",
  district: "",
  preferred_language: "mr",
  season: "Kharif",
  current_crop: "cotton",
  soil_fertility: "moderate",
  water_budget_mm: 280,
  budget_inr: 80000,
  farm_size_hectares: 1.2,
  soil_type: "black soil",
  irrigation_type: "mixed",
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

function isAuthenticationFailure(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function primaryRole(principal: SessionPrincipal | null): AppRole | null {
  if (!principal?.roles?.length) {
    return null;
  }
  if (principal.roles.includes("system_admin")) {
    return "system_admin";
  }
  if (principal.roles.includes("extension_officer")) {
    return "extension_officer";
  }
  if (principal.roles.includes("farmer")) {
    return "farmer";
  }
  return null;
}

function scopedFarmerId(principal: SessionPrincipal | null): string | null {
  const allowed = principal?.allowed_farmer_ids;
  if (allowed?.length === 1) {
    return allowed[0];
  }
  return null;
}

function isDemoScenarioQuery(query: string): boolean {
  return queryScenarios.some((scenario) => scenario.query === query);
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
        </li>
      ))}
    </ul>
  );
}

function formatVisionLabel(label: string | null | undefined): string {
  if (!label) {
    return "No detection above threshold";
  }
  const cleaned = label.replace(/___/g, " · ").replace(/_/g, " ").trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export function CropHealthScan({ image }: { image: FarmerImage }) {
  const specialists = image.vision?.specialists ?? {};
  const rows = [
    { kind: "disease" as const, title: "Disease", evidence: specialists.disease },
    { kind: "pest" as const, title: "Pest", evidence: specialists.pest },
  ];
  const availableSpecialists = rows.filter(({ evidence }) => evidence?.available).length;

  return (
    <section className="crop-health-scan" aria-label="Crop health scan">
      <div className="scan-heading">
        <div>
          <p className="eyebrow">Crop health scan</p>
          <h3>{image.filename || "Uploaded crop image"}</h3>
        </div>
        <span className={`scan-backend scan-${image.vision?.backend || "pixel"}`}>
          {image.vision?.backend === "onnx"
            ? availableSpecialists > 1
              ? "Dual vision"
              : "ONNX vision"
            : "Pixel fallback"}
        </span>
      </div>
      <div className="scan-findings">
        {rows.map(({ kind, title, evidence }) => {
          const confidence = evidence?.confidence ?? 0;
          const modelState = evidence?.available
            ? evidence.detected
              ? "Detection"
              : "Model ran · no match"
            : evidence?.installed
              ? "Model unavailable"
              : "Model not installed";
          return (
            <article className="scan-finding" key={kind}>
              <span className="scan-kind">{title}</span>
              <strong>{formatVisionLabel(evidence?.label)}</strong>
              <div className="scan-confidence-row">
                <span>{modelState}</span>
                {evidence?.detected && <b>{Math.round(confidence * 100)}%</b>}
              </div>
              {evidence?.detected && (
                <div className="scan-meter" aria-label={`${title} confidence ${Math.round(confidence * 100)}%`}>
                  <span style={{ width: `${Math.round(confidence * 100)}%` }} />
                </div>
              )}
            </article>
          );
        })}
      </div>
      <div className="scan-evidence">
        <strong>Vision evidence</strong>
        {rows.map(({ kind, title, evidence }) => (
          <span key={kind} className={evidence?.available ? "is-available" : "is-unavailable"}>
            {evidence?.available ? "✓" : "–"} {title} model
          </span>
        ))}
      </div>
      <p className="scan-summary">{image.analysis_summary}</p>
      {image.vision?.needs_officer_review && (
        <p className="scan-review-note">Low-confidence evidence requires extension-officer review.</p>
      )}
    </section>
  );
}

function TraceList({ trace }: { trace: TraceEvent[] }) {
  return (
    <ol className="trace-list thinking-timeline">
      {trace.map((event, index) => (
        <li
          key={`${event.stage}-${event.detail}`}
          className="thinking-step"
          style={{ animationDelay: `${index * 80}ms` }}
        >
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
    <ol className="agent-run-list thinking-timeline">
      {runs.map((run, index) => (
        <li
          key={`${run.agent_id}-${index}`}
          className={`agent-run agent-${run.status}`}
          style={{ animationDelay: `${index * 90}ms` }}
        >
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

function WorkflowActivity({ runs, trace }: { runs: AgentRun[]; trace: TraceEvent[] }) {
  return (
    <div className="workflow-activity">
      <AgentRunList runs={runs} />
      {trace.length > 0 && (
        <details className="workflow-trace">
          <summary>View execution trace</summary>
          <TraceList trace={trace} />
        </details>
      )}
    </div>
  );
}

const roleOptions: { id: AppRole; title: string; blurb: string }[] = [
  {
    id: "farmer",
    title: "Farmer",
    blurb: "Ask advisory questions, upload crop images, and follow agent work.",
  },
  {
    id: "extension_officer",
    title: "Extension Officer",
    blurb: "Review assigned farms and decide human-in-the-loop cases.",
  },
  {
    id: "system_admin",
    title: "System Admin",
    blurb: "Inspect runtime health, audit trails, and platform operations.",
  },
];

function App() {
  const [sessionReady, setSessionReady] = useState(false);
  const [authBootstrapping, setAuthBootstrapping] = useState(true);
  const [principal, setPrincipal] = useState<SessionPrincipal | null>(null);
  const [loginRole, setLoginRole] = useState<AppRole>("farmer");
  const [authMethod, setAuthMethod] = useState<"api_key" | "email_otp">("email_otp");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [otpInput, setOtpInput] = useState("");
  const [otpHint, setOtpHint] = useState<string | null>(null);
  const [otpSent, setOtpSent] = useState(false);
  const [showAdvancedAuth, setShowAdvancedAuth] = useState(false);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboarding, setOnboarding] = useState<OnboardingPayload>(initialOnboarding);
  const [authRequired, setAuthRequired] = useState(true);
  const [farmers, setFarmers] = useState<SyntheticFarmer[]>(syntheticFarmers);
  const [runtime, setRuntime] = useState<RuntimeHealth | null>(null);
  const [agents, setAgents] = useState<AgentDescriptor[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeStats | null>(null);
  const [systemError, setSystemError] = useState<string | null>(null);
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
  const [isLoadingQueue, setIsLoadingQueue] = useState(false);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [reviewForm, setReviewForm] = useState<ReviewForm>(initialReviewForm);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [isDeciding, setIsDeciding] = useState(false);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("advisory");
  const [images, setImages] = useState<FarmerImage[]>([]);
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [auditEvents, setAuditEvents] = useState<Record<string, unknown>[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [advisoryImageStatus, setAdvisoryImageStatus] = useState<string | null>(null);
  const [isUploadingAdvisoryImage, setIsUploadingAdvisoryImage] = useState(false);
  const [workflowVisible, setWorkflowVisible] = useState(false);

  const role = primaryRole(principal);
  const visibleFarmers = useMemo(() => {
    if (role !== "farmer") {
      return farmers;
    }
    const allowed = new Set(principal?.allowed_farmer_ids ?? []);
    if (allowed.size === 0) {
      return farmers;
    }
    return farmers.filter((farmer) => allowed.has(farmer.id));
  }, [farmers, role, principal]);
  const selectedFarmer = useMemo(
    () => visibleFarmers.find((farmer) => farmer.id === queryForm.farmerId),
    [visibleFarmers, queryForm.farmerId],
  );
  const attachedImage = useMemo(
    () => images.find((image) => String(image.image_id || "") === queryForm.imageId),
    [images, queryForm.imageId],
  );
  const activeCase = useMemo(
    () => cases.find((caseItem) => caseItem.case_id === activeCaseId) ?? null,
    [activeCaseId, cases],
  );
  const activeCaseFarmer = useMemo(
    () =>
      activeCase ? farmers.find((farmer) => farmer.id === activeCase.farmer_id) : undefined,
    [activeCase, farmers],
  );
  const activeCaseHasHardSafetyFailure = useMemo(
    () => activeCase?.verification?.some((check) => check.status === "fail") ?? false,
    [activeCase],
  );

  const roleTabs = useMemo(() => {
    if (role === "farmer") {
      return [
        { id: "profile" as const, label: "Profile", hint: "Digital twin" },
        { id: "advisory" as const, label: "Ask advisory", hint: "Field question" },
        { id: "images" as const, label: "Images", hint: "Crop upload" },
        { id: "history" as const, label: "History", hint: "Past advice" },
        { id: "workflow" as const, label: "Agents", hint: "Thinking steps" },
      ];
    }
    if (role === "extension_officer") {
      return [
        { id: "farmers" as const, label: "Assigned farmers", hint: "Region scope" },
        { id: "review" as const, label: "HITL queue", hint: "Approvals" },
        { id: "metrics" as const, label: "Metrics", hint: "Queue health" },
        { id: "advisory" as const, label: "Advisory desk", hint: "Assist query" },
      ];
    }
    return [
      { id: "runtime" as const, label: "Runtime", hint: "Mode & sync" },
      { id: "farmers" as const, label: "All farmers", hint: "Catalog" },
      { id: "audit" as const, label: "Audit", hint: "Trail" },
      { id: "review" as const, label: "HITL", hint: "All cases" },
      { id: "agents" as const, label: "Agents", hint: "Topology" },
      { id: "advisory" as const, label: "Advisory", hint: "Ops query" },
    ];
  }, [role]);

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
      if (isAuthenticationFailure(error)) {
        setQueueError(null);
        return false;
      }
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
      const mapped = availableFarmerResult.value.map((farmer) => ({
        id: farmer.farmer_id,
        name: farmer.name,
        state: farmer.state,
        district: farmer.district,
        preferredLanguage: farmer.preferred_language,
        crop: farmer.current_crop,
        season: farmer.season,
        waterBudget: farmer.water_budget_mm,
        farmSizeHectares: farmer.farm_size_hectares,
        soilFertility: farmer.soil_fertility,
        budgetInr: farmer.budget_inr,
        soilType: farmer.soil_type,
        irrigationType: farmer.irrigation_type,
      }));
      setFarmers(mapped);
      setQueryForm((current) => {
        if (mapped.some((farmer) => farmer.id === current.farmerId)) {
          return current;
        }
        return {
          ...current,
          farmerId: mapped[0].id,
          language: mapped[0].preferredLanguage,
        };
      });
    }

    const telemetryFailures = [healthResult, agentResult, knowledgeResult].filter(
      (result) => result.status === "rejected" && !isAuthenticationFailure(result.reason),
    );
    setSystemError(
      telemetryFailures.length > 0
        ? "Some runtime telemetry is unavailable. Advisory safety gates remain authoritative."
        : null,
    );
    return agentResult.status === "fulfilled" && knowledgeResult.status === "fulfilled";
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrapSession() {
      const stored = loadStoredSession();
      let requiresAuth = true;
      try {
        const health = await getRuntimeHealth();
        if (!cancelled) {
          setRuntime(health);
          requiresAuth = health.auth_required !== "false";
          setAuthRequired(requiresAuth);
        }
      } catch {
        // Login page can still render without health telemetry.
      }

      if (!stored.token || !stored.principal) {
        clearSession();
        if (!cancelled) {
          setPrincipal(null);
          setSessionReady(false);
          setAuthBootstrapping(false);
        }
        return;
      }

      // When auth is disabled, keep the UI session locally but never auto-enter
      // without an explicit prior login/bypass stored in this tab.
      if (!requiresAuth) {
        if (!cancelled) {
          setPrincipal(stored.principal);
          setSessionReady(true);
          setAuthBootstrapping(false);
        }
        return;
      }

      try {
        const me = await fetchAuthMe();
        if (cancelled) {
          return;
        }
        setPrincipal({
          subject: me.subject,
          roles: me.roles,
          allowed_farmer_ids: me.allowed_farmer_ids,
          allowed_regions: me.allowed_regions,
          authentication_method: me.authentication_method,
        });
        setSessionReady(true);
      } catch {
        clearSession();
        if (!cancelled) {
          setPrincipal(null);
          setSessionReady(false);
        }
      } finally {
        if (!cancelled) {
          setAuthBootstrapping(false);
        }
      }
    }

    void bootstrapSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!sessionReady) {
      return;
    }
    void refreshSystemContext();
    void refreshQueue();
  }, [sessionReady]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("sasya-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!sessionReady || role !== "farmer") {
      return;
    }
    const farmerScope = scopedFarmerId(principal);
    if (!farmerScope) {
      return;
    }
    setQueryForm((current) => {
      const farmer = farmers.find((item) => item.id === farmerScope);
      const switchingScope = current.farmerId !== farmerScope;
      const shouldClearDemo = switchingScope || isDemoScenarioQuery(current.query);
      return {
        ...current,
        farmerId: farmerScope,
        language: farmer?.preferredLanguage ?? current.language,
        query: shouldClearDemo ? "" : current.query,
        intent: shouldClearDemo ? "auto" : current.intent,
        requestedDose: shouldClearDemo ? "" : current.requestedDose,
        imageId: switchingScope ? "" : current.imageId,
      };
    });
  }, [sessionReady, role, principal, farmers]);

  useEffect(() => {
    if (roleTabs.length && !roleTabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(roleTabs[0].id);
    }
  }, [roleTabs, activeTab]);

  useEffect(() => {
    setReviewError(null);
    setReviewForm((current) => ({
      ...initialReviewForm,
      decision: activeCaseHasHardSafetyFailure ? "reject" : initialReviewForm.decision,
      reviewerName: current.reviewerName,
    }));
  }, [activeCaseId, activeCaseHasHardSafetyFailure]);

  useEffect(() => {
    if (!sessionReady || !queryForm.farmerId) {
      return;
    }
    if (activeTab === "images" || activeTab === "history" || activeTab === "advisory") {
      void listFarmerImages(queryForm.farmerId)
        .then(setImages)
        .catch(() => setImages([]));
    }
    if (activeTab === "images" || activeTab === "history") {
      void searchMemory(queryForm.farmerId, "advisory")
        .then(setHistory)
        .catch(() => setHistory([]));
    }
    if (activeTab === "audit" && role === "system_admin") {
      void listAuditEvents()
        .then(setAuditEvents)
        .catch(() => setAuditEvents([]));
    }
  }, [activeTab, queryForm.farmerId, sessionReady, role]);

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

  function completeLogin(result: {
    access_token: string;
    subject: string;
    roles: string[];
    allowed_farmer_ids?: string[] | null;
    allowed_regions?: string[] | null;
  }) {
    const nextPrincipal: SessionPrincipal = {
      subject: result.subject,
      roles: result.roles,
      allowed_farmer_ids: result.allowed_farmer_ids,
      allowed_regions: result.allowed_regions,
      authentication_method: "session_token",
    };
    storeSession(result.access_token, nextPrincipal);
    setPrincipal(nextPrincipal);
    setSessionReady(true);
    if (result.roles.includes("farmer") && result.allowed_farmer_ids?.length === 1) {
      const farmerScope = result.allowed_farmer_ids[0];
      setQueryForm({
        farmerId: farmerScope,
        query: "",
        intent: "auto",
        language: initialOnboarding.preferred_language,
        requestedDose: "",
        imageId: "",
      });
    }
    setApiKeyInput("");
    setOtpInput("");
    setOtpHint(null);
    setOtpSent(false);
    setShowOnboarding(false);
    setLoginError(null);
  }

  async function handleRequestOtp() {
    setLoginError(null);
    setIsAuthenticating(true);
    try {
      const result = await login({
        role: loginRole,
        auth_method: "email_otp",
        email: emailInput,
      });
      setOtpSent(true);
      setOtpHint(result.otp_demo_code || null);
      if (!result.otp_demo_code && result.message) {
        setLoginError(null);
      }
    } catch (error) {
      setLoginError(getErrorMessage(error));
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginError(null);
    setIsAuthenticating(true);
    try {
      const prefersApiKey =
        apiKeyInput.trim().length >= 24 && (authMethod === "api_key" || !otpInput.trim());
      const method = prefersApiKey ? "api_key" : "email_otp";
      setAuthMethod(method);
      if (method === "email_otp" && !otpInput.trim()) {
        await handleRequestOtp();
        return;
      }
      const result = await login({
        role: loginRole,
        auth_method: method,
        ...(method === "api_key"
          ? { api_key: apiKeyInput }
          : { email: emailInput, otp_code: otpInput }),
      });
      if (!result.access_token && result.otp_demo_code) {
        setOtpSent(true);
        setOtpHint(result.otp_demo_code);
        return;
      }
      if (!result.access_token) {
        setLoginError(result.message || "Login did not return a session token.");
        return;
      }
      completeLogin(result);
    } catch (error) {
      setLoginError(getErrorMessage(error));
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handleGoogleLogin() {
    setLoginError(null);
    if (!emailInput.trim()) {
      setLoginError("Enter your Gmail address to continue with Google.");
      return;
    }
    setIsAuthenticating(true);
    try {
      const result = await googleLogin({ email: emailInput.trim() });
      if (!result.access_token) {
        setLoginError(result.message || "Google sign-in did not return a session token.");
        return;
      }
      completeLogin(result);
    } catch (error) {
      setLoginError(getErrorMessage(error));
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handleBypass() {
    // Persist a tab-local marker so refresh can restore only after an explicit bypass.
    storeSession("local-development-bypass", {
      subject: "local-development-bypass",
      roles: ["farmer", "extension_officer", "system_admin"],
      authentication_method: "development_bypass",
    });
    setPrincipal({
      subject: "local-development-bypass",
      roles: ["farmer", "extension_officer", "system_admin"],
      authentication_method: "development_bypass",
    });
    setSessionReady(true);
    setAuthBootstrapping(false);
  }

  async function handleOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginError(null);
    setIsAuthenticating(true);
    try {
      const result = await registerFarmer(onboarding);
      const farmerId = String((result.farmer as { farmer_id?: string }).farmer_id || "");
      completeLogin({
        access_token: result.access_token,
        subject: `farmer:${farmerId}`,
        roles: result.roles,
        allowed_farmer_ids: [farmerId],
      });
    } catch (error) {
      setLoginError(getErrorMessage(error));
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Local session is cleared even if the API revoke call fails.
    } finally {
      clearSession();
      setSessionReady(false);
      setPrincipal(null);
      setResponse(null);
      setCases([]);
      setOtpSent(false);
      setOtpHint(null);
      setApiKeyInput("");
      setOtpInput("");
      setLoginError(null);
      setShowOnboarding(false);
      setActiveTab("advisory");
    }
  }

  async function handleQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryError(null);
    setWorkflowVisible(true);
    const requestedDose = queryForm.requestedDose.trim();
    const payload: QueryRequest = {
      farmer_id: queryForm.farmerId,
      query: queryForm.query.trim(),
      language: queryForm.language,
      ...(queryForm.intent === "auto" ? {} : { intent: queryForm.intent }),
      ...(queryForm.imageId ? { image_id: queryForm.imageId } : {}),
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
      setActiveTab(role === "farmer" ? "workflow" : activeTab);
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
      setReviewError("Cases with failed deterministic safety checks can only be rejected.");
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

  async function handleAdvisoryImageUpload(file: File) {
    if (!queryForm.farmerId) {
      setAdvisoryImageStatus("Select a farmer profile before uploading an image.");
      return;
    }
    setIsUploadingAdvisoryImage(true);
    setAdvisoryImageStatus("Uploading and analysing…");
    try {
      const record = await uploadFarmerImage(queryForm.farmerId, file);
      setImages((current) => [record, ...current]);
      setQueryForm((current) => ({ ...current, imageId: String(record.image_id || "") }));
      setAdvisoryImageStatus(
        `Attached ${String(record.filename || file.name)} · ${String(record.analysis_summary || "Analysis complete.")}`,
      );
    } catch (error) {
      setAdvisoryImageStatus(getErrorMessage(error));
    } finally {
      setIsUploadingAdvisoryImage(false);
    }
  }

  async function handleImageUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("cropImage") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) {
      setUploadStatus("Choose an image first.");
      return;
    }
    setUploadStatus("Uploading and analysing…");
    try {
      const record = await uploadFarmerImage(queryForm.farmerId, file);
      setImages((current) => [record, ...current]);
      setQueryForm((current) => ({ ...current, imageId: String(record.image_id || "") }));
      setUploadStatus(`Processed ${String(record.filename || file.name)}. Ready for advisory.`);
      form.reset();
    } catch (error) {
      setUploadStatus(getErrorMessage(error));
    }
  }

  if (authBootstrapping) {
    return (
      <main className="login-page" aria-busy="true">
        <div className="login-page-inner">
          <p className="login-loading">Checking your session…</p>
        </div>
      </main>
    );
  }

  if (!sessionReady) {
    const selectedRole = roleOptions.find((option) => option.id === loginRole) ?? roleOptions[0];
    return (
      <main className="login-page">
        <div className="login-backdrop" aria-hidden="true" />
        <div className="login-page-inner">
          <header className="login-brand">
            <span className="brand-mark" aria-hidden="true">
              सा
            </span>
            <div>
              <strong>SasyaAI</strong>
              <small>Role-scoped sign in</small>
            </div>
          </header>

          <section className="login-card" aria-labelledby="login-heading">
            {!showOnboarding ? (
              <>
                <p className="eyebrow">Account login</p>
                <h1 id="login-heading">Sign in</h1>
                <p className="login-lead">
                  Farmers sign in with Email OTP or Continue with Google using a registered Gmail.
                  New farmers must register first. Reviewers can open Advanced for an API key.
                </p>

                <div className="role-card-grid" role="radiogroup" aria-label="Login role">
                  {roleOptions.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      role="radio"
                      aria-checked={loginRole === option.id}
                      className={`role-card ${loginRole === option.id ? "is-active" : ""}`}
                      onClick={() => {
                        setLoginRole(option.id);
                        setLoginError(null);
                        setOtpSent(false);
                        setOtpHint(null);
                        setOtpInput("");
                        setAuthMethod("email_otp");
                        setShowAdvancedAuth(option.id !== "farmer");
                        if (option.id !== "farmer") {
                          setShowOnboarding(false);
                        }
                      }}
                    >
                      <strong>{option.title}</strong>
                      <span>{option.blurb}</span>
                    </button>
                  ))}
                </div>

                <form className="login-form" onSubmit={handleLogin}>
                  <p className="login-role-hint">
                    Signing in as <strong>{selectedRole.title}</strong>
                  </p>

                  <label>
                    Email
                    <input
                      type="email"
                      value={emailInput}
                      onChange={(event) => {
                        setEmailInput(event.target.value);
                        setOtpSent(false);
                        setOtpHint(null);
                      }}
                      required={authMethod === "email_otp"}
                      placeholder={
                        loginRole === "farmer"
                          ? "you@gmail.com"
                          : "asha.patil@demo.sasyaai.local"
                      }
                    />
                  </label>

                  <div className="otp-row">
                    <label>
                      OTP code
                      <input
                        value={otpInput}
                        onChange={(event) => {
                          setOtpInput(event.target.value);
                          setAuthMethod("email_otp");
                        }}
                        placeholder={otpSent ? "Enter the 6-digit code" : "Request a code first"}
                        maxLength={8}
                        inputMode="numeric"
                        required={authMethod === "email_otp" && otpSent}
                      />
                    </label>
                    <button
                      className="secondary-button otp-request-button"
                      type="button"
                      disabled={isAuthenticating || !emailInput.trim()}
                      onClick={() => {
                        setAuthMethod("email_otp");
                        void handleRequestOtp();
                      }}
                    >
                      {otpSent ? "Resend OTP" : "Request OTP"}
                    </button>
                  </div>
                  {otpHint && (
                    <p className="form-message otp-demo-hint" role="status">
                      Local OTP code: <strong>{otpHint}</strong>
                    </p>
                  )}

                  {loginRole === "farmer" && (
                    <button
                      className="secondary-button google-login-button"
                      type="button"
                      disabled={isAuthenticating || !emailInput.trim()}
                      onClick={() => void handleGoogleLogin()}
                    >
                      Continue with Google
                    </button>
                  )}

                  <details
                    className="advanced-auth"
                    open={showAdvancedAuth || authMethod === "api_key"}
                    onToggle={(event) => {
                      setShowAdvancedAuth((event.currentTarget as HTMLDetailsElement).open);
                    }}
                  >
                    <summary>Advanced / reviewer API key</summary>
                    <p className="advanced-auth-hint">
                      Optional. Demo keys live in <code>REVIEWER_CREDENTIALS.example.md</code>.
                      Farmers do not need an API key after Email OTP, Google sign-in, or registration.
                    </p>
                    <label>
                      Role-scoped API key
                      <input
                        type="password"
                        autoComplete="off"
                        value={apiKeyInput}
                        onChange={(event) => {
                          setApiKeyInput(event.target.value);
                          setAuthMethod("api_key");
                        }}
                        minLength={24}
                        placeholder="Paste demo key from REVIEWER_CREDENTIALS"
                      />
                    </label>
                  </details>

                  {loginError && (
                    <p className="form-message error-message" role="alert">
                      {loginError}
                      {/not registered/i.test(loginError) && loginRole === "farmer" && (
                        <>
                          {" "}
                          <button
                            className="text-button"
                            type="button"
                            onClick={() => {
                              setShowOnboarding(true);
                              setLoginError(null);
                            }}
                          >
                            Register now
                          </button>
                        </>
                      )}
                    </p>
                  )}
                  <div className="login-actions">
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={isAuthenticating}
                      onClick={() => {
                        if (apiKeyInput.trim().length >= 24 && !otpInput.trim()) {
                          setAuthMethod("api_key");
                        } else {
                          setAuthMethod("email_otp");
                        }
                      }}
                    >
                      {isAuthenticating
                        ? "Signing in…"
                        : authMethod === "email_otp" && !otpSent && !apiKeyInput.trim()
                          ? "Request OTP & continue"
                          : "Sign in"}
                    </button>
                    {loginRole === "farmer" && (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setShowOnboarding(true);
                          setLoginError(null);
                        }}
                      >
                        Register new farmer
                      </button>
                    )}
                  </div>
                  {!authRequired && (
                    <button
                      className="text-button bypass-button"
                      type="button"
                      onClick={() => void handleBypass()}
                    >
                      Continue with local bypass (auth disabled)
                    </button>
                  )}
                  <p className="login-footnote">
                    After Email OTP, Google sign-in, or registration, your session token is attached
                    to every farmer desk request automatically — no second API-key prompt.
                  </p>
                </form>
              </>
            ) : (
              <form className="login-form" onSubmit={handleOnboarding}>
                <p className="eyebrow">Farmer onboarding</p>
                <h1 id="login-heading">Register a new farmer</h1>
                <p className="login-lead">
                  Create a digital twin profile. After signup you receive a farmer-scoped session
                  and land in the farmer desk.
                </p>
                <div className="form-grid">
                  <label>
                    Name
                    <input
                      value={onboarding.name}
                      onChange={(event) =>
                        setOnboarding((current) => ({ ...current, name: event.target.value }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Email
                    <input
                      type="email"
                      value={onboarding.email}
                      onChange={(event) =>
                        setOnboarding((current) => ({ ...current, email: event.target.value }))
                      }
                      required
                    />
                  </label>
                  <label>
                    State
                    <input
                      value={onboarding.state}
                      onChange={(event) =>
                        setOnboarding((current) => ({ ...current, state: event.target.value }))
                      }
                      required
                    />
                  </label>
                  <label>
                    District
                    <input
                      value={onboarding.district}
                      onChange={(event) =>
                        setOnboarding((current) => ({ ...current, district: event.target.value }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Current crop
                    <input
                      value={onboarding.current_crop}
                      onChange={(event) =>
                        setOnboarding((current) => ({
                          ...current,
                          current_crop: event.target.value,
                        }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Season
                    <input
                      value={onboarding.season}
                      onChange={(event) =>
                        setOnboarding((current) => ({ ...current, season: event.target.value }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Farm size (ha)
                    <input
                      type="number"
                      step="0.1"
                      value={onboarding.farm_size_hectares}
                      onChange={(event) =>
                        setOnboarding((current) => ({
                          ...current,
                          farm_size_hectares: Number(event.target.value),
                        }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Soil type
                    <input
                      value={onboarding.soil_type}
                      onChange={(event) =>
                        setOnboarding((current) => ({ ...current, soil_type: event.target.value }))
                      }
                      required
                    />
                  </label>
                </div>
                {loginError && (
                  <p className="form-message error-message" role="alert">
                    {loginError}
                  </p>
                )}
                <div className="login-actions">
                  <button className="primary-button" type="submit" disabled={isAuthenticating}>
                    {isAuthenticating ? "Creating profile…" : "Create profile & enter"}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => setShowOnboarding(false)}
                  >
                    Back to login
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="SasyaAI home">
          <span className="brand-mark" aria-hidden="true">
            सा
          </span>
          <span>
            <strong>SasyaAI</strong>
            <small>
              {role === "farmer"
                ? "Farmer desk"
                : role === "extension_officer"
                  ? "Extension desk"
                  : "Admin operations"}
            </small>
          </span>
        </a>
        <div className="topbar-actions">
          <div className={`runtime-badge runtime-${runtime?.runtime_mode ?? "connecting"}`}>
            <span aria-hidden="true">●</span>
            {principal?.subject || "Signed in"}
          </div>
          <button className="sign-out-button" type="button" onClick={() => void handleLogout()}>
            Sign out
          </button>
          <button
            className="theme-toggle"
            type="button"
            aria-label={`Switch to ${theme === "field" ? "night" : "field"} theme`}
            onClick={() => setTheme((current) => (current === "field" ? "night" : "field"))}
          >
            {theme === "field" ? "Night" : "Field"}
          </button>
        </div>
      </header>

      <section className="hero compact-hero" id="workspace">
        <div>
          <p className="eyebrow">SasyaAI workspace</p>
          <h1>
            {role === "farmer"
              ? "Your farm, clearly managed."
              : role === "extension_officer"
                ? "Review farm decisions with evidence."
                : "Operate the advisory platform with confidence."}
          </h1>
          <p className="hero-subtitle">
            {role === "farmer" ? "Ask a question, check your profile, and get guided next steps." : "A focused view of the work, decisions, and system health in your scope."}
          </p>
        </div>
        <div className="hero-status" aria-label="Workspace status">
          <span className="hero-status-dot" aria-hidden="true" />
          <div>
            <strong>{runtime?.runtime_mode === "production" ? "Production workflow" : "Demo workflow"}</strong>
            <small>{visibleFarmers.length} farmer{visibleFarmers.length === 1 ? "" : "s"} in scope · {cases.filter((item) => item.status === "pending").length} open review</small>
          </div>
        </div>
      </section>

      {systemError && (
        <p className="system-notice" role="status">
          {systemError}
        </p>
      )}

      <nav className="section-tabs" aria-label="Workspace sections" role="tablist">
        {roleTabs.map((tab, index) => (
          <button
            key={tab.id}
            className={`section-tab ${activeTab === tab.id ? "is-active" : ""}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{tab.label}</strong>
            <small>{tab.hint}</small>
          </button>
        ))}
      </nav>

      {(activeTab === "profile" || activeTab === "farmers") && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{role === "farmer" ? "Your twin" : "Farmer catalog"}</p>
              <h2>{role === "system_admin" ? "All farmers" : "Assigned farmers"}</h2>
            </div>
          </div>
          {role === "farmer" && selectedFarmer ? (
            <div className="profile-layout">
              <div className="profile-identity">
                <span className="profile-avatar" aria-hidden="true">
                  {selectedFarmer.name.slice(0, 1).toUpperCase()}
                </span>
                <div>
                  <p className="eyebrow">Registered farmer</p>
                  <h3>{selectedFarmer.name}</h3>
                  <p>{selectedFarmer.district}, {selectedFarmer.state}</p>
                  <span className="profile-id">{selectedFarmer.id}</span>
                </div>
              </div>
              <dl className="profile-details">
                <div><dt>Current crop</dt><dd>{selectedFarmer.crop}</dd></div>
                <div><dt>Season</dt><dd>{selectedFarmer.season}</dd></div>
                <div><dt>Farm size</dt><dd>{selectedFarmer.farmSizeHectares} ha</dd></div>
                <div><dt>Soil</dt><dd>{selectedFarmer.soilType}</dd></div>
                <div><dt>Soil fertility</dt><dd>{selectedFarmer.soilFertility}</dd></div>
                <div><dt>Irrigation</dt><dd>{selectedFarmer.irrigationType}</dd></div>
                <div><dt>Water budget</dt><dd>{selectedFarmer.waterBudget} mm</dd></div>
                <div><dt>Input budget</dt><dd>₹{selectedFarmer.budgetInr.toLocaleString("en-IN")}</dd></div>
                <div><dt>Language</dt><dd>{languageLabels[selectedFarmer.preferredLanguage] ?? "English"}</dd></div>
              </dl>
            </div>
          ) : (
          <div className="farmer-grid">
            {visibleFarmers.map((farmer) => (
              <button
                key={farmer.id}
                type="button"
                className={`farmer-card ${queryForm.farmerId === farmer.id ? "is-selected" : ""}`}
                onClick={() => selectFarmer(farmer.id)}
              >
                <strong>{farmer.name}</strong>
                <span>
                  {farmer.district}, {farmer.state}
                </span>
                <small>
                  {farmer.crop} · {farmer.season} · {farmer.waterBudget} mm
                </small>
              </button>
            ))}
          </div>
          )}
        </section>
      )}

      {activeTab === "images" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Vision assist</p>
              <h2>Upload crop imagery</h2>
            </div>
          </div>
          <form className="login-form" onSubmit={handleImageUpload}>
            <label>
              Crop image
              <input name="cropImage" type="file" accept="image/jpeg,image/png,image/webp" />
            </label>
            <button className="primary-button" type="submit">
              Upload & analyse
            </button>
            {uploadStatus && <p className="form-message">{uploadStatus}</p>}
          </form>
          <ul className="queue-list">
            {images.map((image) => (
              <li className="image-scan-list-item" key={image.image_id}>
                <button
                  type="button"
                  className="queue-case"
                  onClick={() =>
                    setQueryForm((current) => ({
                      ...current,
                      imageId: String(image.image_id || ""),
                    }))
                  }
                >
                  <strong>{image.filename || "image"}</strong>
                  <small>Attach this scan to the next advisory</small>
                </button>
                <CropHealthScan image={image} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {activeTab === "history" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Memory</p>
              <h2>Advisory history</h2>
            </div>
          </div>
          {!history.length && <p className="queue-empty">No stored episodes yet for this farmer.</p>}
          <ol className="history-list">
            {history.map((item) => (
              <li key={String(item.request_id || item.timestamp)}>
                <strong>{String(item.intent || "advisory")}</strong>
                <span>{formatDate(String(item.timestamp || ""))}</span>
                <p>{String(item.query || "")}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {(activeTab === "workflow" || activeTab === "agents") && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Agent thinking</p>
              <h2>What the team is doing</h2>
            </div>
          </div>
          {response ? (
            <>
              <WorkflowActivity runs={response.agent_runs} trace={response.trace} />
            </>
          ) : (
            <div className="agent-roster">
              {agents.map((agent, index) => (
                <div className="roster-agent" key={agent.agent_id}>
                  <span className="roster-number">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>{agent.name}</strong>
                    <small>{agent.role}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {activeTab === "metrics" && (
        <section className="panel">
          <dl className="coverage-grid">
            <div>
              <dt>Assigned farmers</dt>
              <dd>{farmers.length}</dd>
            </div>
            <div>
              <dt>Pending HITL</dt>
              <dd>{cases.filter((item) => item.status === "pending").length}</dd>
            </div>
            <div>
              <dt>Resolved</dt>
              <dd>{cases.filter((item) => item.status !== "pending").length}</dd>
            </div>
            <div>
              <dt>Regions</dt>
              <dd>{principal?.allowed_regions?.join(", ") || "scoped"}</dd>
            </div>
          </dl>
        </section>
      )}

      {activeTab === "runtime" && (
        <section className="panel">
          <dl className="coverage-grid">
            <div>
              <dt>Mode</dt>
              <dd>{runtime?.runtime_mode || "—"}</dd>
            </div>
            <div>
              <dt>Data</dt>
              <dd>{runtime?.data_source_mode || "—"}</dd>
            </div>
            <div>
              <dt>Agents</dt>
              <dd>{runtime?.agent_execution || "—"}</dd>
            </div>
            <div>
              <dt>Auth</dt>
              <dd>{runtime?.auth_required || "—"}</dd>
            </div>
          </dl>
        </section>
      )}

      {activeTab === "audit" && (
        <section className="panel">
          <ol className="history-list">
            {auditEvents.map((event) => (
              <li key={String(event.event_id)}>
                <strong>{String(event.action)}</strong>
                <span>
                  {String(event.actor_subject)} · {String(event.outcome)}
                </span>
                <p>{formatDate(String(event.timestamp || ""))}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {(activeTab === "advisory" || activeTab === "review") && (
        <div
          className={`workspace-grid workspace-${activeTab === "review" ? "review" : "advisory"}`}
        >
        {activeTab === "advisory" && (
        <section className="query-column" aria-labelledby="advisory-heading">
          <form className="panel query-panel" onSubmit={handleQuery}>
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Advisory</p>
                <h2 id="advisory-heading">Ask a safety-gated question</h2>
              </div>
              {workflowVisible && isSubmitting && <span className="live-indicator">Agents working…</span>}
            </div>
            <div className="form-grid">
              {role === "farmer" ? (
                selectedFarmer && (
                  <div className="farmer-scope-card">
                    <p className="eyebrow">Your farm</p>
                    <strong>
                      {selectedFarmer.name} · {selectedFarmer.district}, {selectedFarmer.state}
                    </strong>
                  </div>
                )
              ) : (
                <>
                  <label>
                    Farmer profile
                    <select
                      value={queryForm.farmerId}
                      onChange={(event) => selectFarmer(event.target.value)}
                    >
                      {visibleFarmers.map((farmer) => (
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
                </>
              )}
            </div>
            {selectedFarmer && (
              <aside className="farmer-context" aria-label="Selected farmer context">
                <div>
                  <span>Current crop</span>
                  <strong>{selectedFarmer.crop}</strong>
                </div>
                <div>
                  <span>Water budget</span>
                  <strong>{selectedFarmer.waterBudget} mm</strong>
                </div>
                <div>
                  <span>Language</span>
                  <strong>
                    {languageLabels[selectedFarmer.preferredLanguage] ?? "English"}
                  </strong>
                </div>
              </aside>
            )}
            <label>
              Farmer question
              <textarea
                value={queryForm.query}
                onChange={(event) =>
                  setQueryForm((current) => ({ ...current, query: event.target.value }))
                }
                rows={4}
                minLength={3}
                maxLength={1000}
                placeholder={
                  role === "farmer"
                    ? "Describe your crop, field condition, or advisory need in your own words."
                    : "Enter the farmer-facing question to run through the safety gates."
                }
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
                  onChange={(event) =>
                    setQueryForm((current) => ({ ...current, language: event.target.value }))
                  }
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
                    setQueryForm((current) => ({
                      ...current,
                      requestedDose: event.target.value,
                    }))
                  }
                  placeholder="Optional"
                />
              </label>
              <label>
                Crop image (optional)
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={isUploadingAdvisoryImage || !queryForm.farmerId}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      void handleAdvisoryImageUpload(file);
                    }
                    event.target.value = "";
                  }}
                />
              </label>
              {images.length > 0 && (
                <label>
                  Or use a previous upload
                  <select
                    value={queryForm.imageId}
                    onChange={(event) => {
                      const nextImageId = event.target.value;
                      setQueryForm((current) => ({ ...current, imageId: nextImageId }));
                      const selected = images.find(
                        (image) => String(image.image_id || "") === nextImageId,
                      );
                      setAdvisoryImageStatus(
                        selected
                          ? `Using ${String(selected.filename || "saved image")}.`
                          : null,
                      );
                    }}
                  >
                    <option value="">No image attached</option>
                    {images.map((image) => (
                      <option key={String(image.image_id)} value={String(image.image_id || "")}>
                        {String(image.filename || image.image_id)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            {(advisoryImageStatus || attachedImage) && (
              <div className="advisory-image-status">
                {attachedImage && <CropHealthScan image={attachedImage} />}
                {advisoryImageStatus && (
                  <p className="form-message" role="status">
                    {advisoryImageStatus}
                  </p>
                )}
                {queryForm.imageId && (
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => {
                      setQueryForm((current) => ({ ...current, imageId: "" }));
                      setAdvisoryImageStatus(null);
                    }}
                  >
                    Remove attached image
                  </button>
                )}
              </div>
            )}
            {queryError && (
              <p className="form-message error-message" role="alert">
                {queryError}
              </p>
            )}
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Running safety checks…" : "Run advisory workflow"}
            </button>
          </form>

          <section className="result-region" aria-label="Advisory result">
            {!response && !queryError && (
              <div className="empty-state">
                <span aria-hidden="true">⌁</span>
                <h2>Ready for a reviewable advisory</h2>
                <p>Run a query to inspect evidence, verification, and agent thinking.</p>
              </div>
            )}
            {response && (
              <>
                <section className="result-card">
                  <div className="result-topline">
                    <span className={`status-chip status-${response.status}`}>
                      {statusLabel(response.status)}
                    </span>
                    <span className="confidence">
                      {Math.round(response.confidence * 100)}% confidence
                    </span>
                  </div>
                  <p className="eyebrow">{intentLabel(response.intent)}</p>
                  <h2>{response.recommendation}</h2>
                  <p className="explanation">{response.explanation}</p>
                  <div className="login-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() =>
                        void submitFeedback({
                          farmer_id: response.farmer_id,
                          request_id: response.request_id,
                          query: queryForm.query,
                          recommendation: response.recommendation,
                          helpful: true,
                          note: "Marked helpful from UI",
                        })
                      }
                    >
                      Mark helpful (learn)
                    </button>
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">Thinking</p>
                      <h3>Agent workflow</h3>
                    </div>
                  </div>
                  <WorkflowActivity runs={response.agent_runs} trace={response.trace} />
                </section>
                <section className="panel verification-panel">
                  <VerificationList checks={response.verification} />
                </section>
                <section className="panel evidence-panel">
                  <EvidenceList evidence={response.evidence} />
                </section>
              </>
            )}
          </section>
        </section>
        )}

        {activeTab === "review" && (
        <aside className="review-column" aria-labelledby="review-heading">
          <section className="panel queue-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Human-in-the-loop</p>
                <h2 id="review-heading">Review queue</h2>
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={() => void refreshQueue()}
                disabled={isLoadingQueue}
              >
                {isLoadingQueue ? "Loading…" : "Refresh"}
              </button>
            </div>
            {queueError && (
              <p className="form-message error-message" role="alert">
                {queueError}
              </p>
            )}
            {!queueError && !isLoadingQueue && cases.length === 0 && (
              <p className="queue-empty">No review cases yet.</p>
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
                      <span className={`queue-status status-${caseItem.status}`}>
                        {statusLabel(caseItem.status)}
                      </span>
                      <strong>{intentLabel(caseItem.intent)}</strong>
                      <span>{caseItem.farmer_id}</span>
                      <small>{caseItem.reason}</small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {activeCase && role !== "farmer" && (
            <section className="panel case-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Case {activeCase.case_id.slice(0, 8)}</p>
                  <h3>{statusLabel(activeCase.status)}</h3>
                </div>
              </div>
              {activeCaseFarmer && (
                <aside className="case-farmer-context">
                  <div>
                    <span>Farmer</span>
                    <strong>
                      {activeCaseFarmer.name} · {activeCaseFarmer.district}
                    </strong>
                  </div>
                </aside>
              )}
              <p className="case-reason">{activeCase.reason}</p>
              {activeCase.original_recommendation && (
                <div className="case-draft">
                  <span>Original draft</span>
                  <p>{activeCase.original_recommendation}</p>
                </div>
              )}
              {activeCase.verification && activeCase.verification.length > 0 && (
                <details className="case-details" open>
                  <summary>Deterministic checks</summary>
                  <VerificationList checks={activeCase.verification} />
                </details>
              )}
              {activeCase.evidence && activeCase.evidence.length > 0 && (
                <details className="case-details" open>
                  <summary>Evidence</summary>
                  <EvidenceList evidence={activeCase.evidence} />
                </details>
              )}
              {activeCase.trace && activeCase.trace.length > 0 && (
                <details className="case-details" open>
                  <summary>Workflow trace</summary>
                  <TraceList trace={activeCase.trace} />
                </details>
              )}
              {activeCase.agent_runs && activeCase.agent_runs.length > 0 && (
                <details className="case-details">
                  <summary>Agent execution</summary>
                  <AgentRunList runs={activeCase.agent_runs} />
                </details>
              )}
              {activeCase.status === "pending" ? (
                <form className="review-form" onSubmit={handleDecision}>
                  {activeCaseHasHardSafetyFailure && (
                    <div className="review-callout safety-block-callout" role="alert">
                      <strong>Hard safety check failed.</strong> Only rejection is permitted.
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
                        setReviewForm((current) => ({
                          ...current,
                          reviewerName: event.target.value,
                        }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Decision reason
                    <textarea
                      value={reviewForm.reviewerNote}
                      onChange={(event) =>
                        setReviewForm((current) => ({
                          ...current,
                          reviewerNote: event.target.value,
                        }))
                      }
                      rows={3}
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
                        required
                      />
                    </label>
                  )}
                  {reviewError && (
                    <p className="form-message error-message" role="alert">
                      {reviewError}
                    </p>
                  )}
                  <button className="primary-button" type="submit" disabled={isDeciding}>
                    {isDeciding ? "Recording decision…" : "Record immutable decision"}
                  </button>
                </form>
              ) : (
                <div className="decision-summary">
                  <strong>Decision recorded</strong>
                  <p>{activeCase.reviewer_note ?? "No reviewer note is available."}</p>
                </div>
              )}
            </section>
          )}
        </aside>
        )}
      </div>
      )}
    </main>
  );
}

export default App;
