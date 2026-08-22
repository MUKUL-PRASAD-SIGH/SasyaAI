import type {
  AdvisoryResponse,
  AgentDescriptor,
  DemoFarmerSummary,
  DecisionRequest,
  FeedbackPayload,
  FarmerImage,
  HitlCase,
  KnowledgeStats,
  LoginPayload,
  LoginResult,
  OnboardingPayload,
  QueryRequest,
  RuntimeHealth,
  SessionPrincipal,
} from "./types";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;

export const apiBaseUrl = rawBaseUrl.replace(/\/+$/, "");
const SESSION_KEY = "sasya-session-token";
const PRINCIPAL_KEY = "sasya-session-principal";
const LEGACY_SESSION_KEYS = [
  SESSION_KEY,
  PRINCIPAL_KEY,
  "sasya-api-key",
  "sasya-operator-key",
  "sasya-auth",
];
let inMemoryApiKey = "";

export function configureApiKey(apiKey: string): void {
  inMemoryApiKey = apiKey.trim();
  if (inMemoryApiKey) {
    window.sessionStorage.setItem(SESSION_KEY, inMemoryApiKey);
  } else {
    window.sessionStorage.removeItem(SESSION_KEY);
  }
}

export function loadStoredSession(): { token: string; principal: SessionPrincipal | null } {
  const token = window.sessionStorage.getItem(SESSION_KEY) || "";
  const rawPrincipal = window.sessionStorage.getItem(PRINCIPAL_KEY);
  let principal: SessionPrincipal | null = null;
  if (rawPrincipal) {
    try {
      principal = JSON.parse(rawPrincipal) as SessionPrincipal;
    } catch {
      principal = null;
    }
  }
  // A token without a principal is not a restoreable login session.
  if (!token || !principal?.roles?.length) {
    clearSession();
    return { token: "", principal: null };
  }
  inMemoryApiKey = token;
  return { token, principal };
}

export function storeSession(token: string, principal: SessionPrincipal): void {
  configureApiKey(token);
  window.sessionStorage.setItem(PRINCIPAL_KEY, JSON.stringify(principal));
}

export function clearSession(): void {
  inMemoryApiKey = "";
  for (const key of LEGACY_SESSION_KEYS) {
    window.sessionStorage.removeItem(key);
  }
}

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return undefined;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join("; ");
    }
  }

  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const authHeaders: Record<string, string> = {};
  if (inMemoryApiKey) {
    authHeaders["X-API-Key"] = inMemoryApiKey;
    authHeaders.Authorization = `Bearer ${inMemoryApiKey}`;
  }

  try {
    response = await fetch(apiBaseUrl + path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...authHeaders,
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Could not reach the local API. Confirm it is running and that VITE_API_BASE_URL is correct.",
    );
  }

  const payload = await parseResponseBody(response);
  if (!response.ok) {
    throw new ApiError(
      errorMessage(payload, "The API request failed (" + response.status + ")."),
      response.status,
    );
  }

  return payload as T;
}

export function submitQuery(payload: QueryRequest): Promise<AdvisoryResponse> {
  return request<AdvisoryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getRuntimeHealth(): Promise<RuntimeHealth> {
  return request<RuntimeHealth>("/health");
}

export function listAgents(): Promise<AgentDescriptor[]> {
  return request<AgentDescriptor[]>("/api/v1/agents");
}

export function getKnowledgeStats(): Promise<KnowledgeStats> {
  return request<KnowledgeStats>("/api/v1/knowledge/stats");
}

export function listDemoFarmers(): Promise<DemoFarmerSummary[]> {
  return request<DemoFarmerSummary[]>("/api/v1/demo/farmers");
}

export function listSyntheticProductionFarmers(): Promise<DemoFarmerSummary[]> {
  return request<DemoFarmerSummary[]>("/api/v1/synthetic/farmers");
}

export async function listHitlCases(): Promise<HitlCase[]> {
  const payload = await request<HitlCase[] | { cases?: HitlCase[] }>("/api/v1/hitl");

  if (Array.isArray(payload)) {
    return payload;
  }

  return Array.isArray(payload.cases) ? payload.cases : [];
}

export function submitHitlDecision(
  caseId: string,
  payload: DecisionRequest,
): Promise<HitlCase> {
  return request<HitlCase>("/api/v1/hitl/" + encodeURIComponent(caseId) + "/decision", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: LoginPayload): Promise<LoginResult> {
  return request<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchAuthMe(): Promise<SessionPrincipal> {
  return request<SessionPrincipal>("/api/v1/auth/me");
}

export function logout(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/v1/auth/logout", { method: "POST" });
}

export function registerFarmer(payload: OnboardingPayload): Promise<{
  farmer: Record<string, unknown>;
  access_token: string;
  roles: string[];
  message: string;
}> {
  return request("/api/v1/farmers/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function googleLogin(payload: { email: string }): Promise<LoginResult> {
  return request<LoginResult>("/api/v1/auth/google/demo", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** @deprecated Prefer googleLogin — kept for older imports. */
export const googleDemoLogin = googleLogin;

export function uploadFarmerImage(farmerId: string, file: File): Promise<FarmerImage> {
  const body = new FormData();
  body.append("file", file);
  return request("/api/v1/farmers/" + encodeURIComponent(farmerId) + "/images", {
    method: "POST",
    body,
  });
}

export function listFarmerImages(farmerId: string): Promise<FarmerImage[]> {
  return request("/api/v1/farmers/" + encodeURIComponent(farmerId) + "/images");
}

export function submitFeedback(payload: FeedbackPayload): Promise<Record<string, unknown>> {
  return request("/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAuditEvents(limit = 50): Promise<Record<string, unknown>[]> {
  return request("/api/v1/audit?limit=" + limit);
}

export function searchMemory(farmerId: string, query: string): Promise<Record<string, unknown>[]> {
  return request("/api/v1/memory/search", {
    method: "POST",
    body: JSON.stringify({ farmer_id: farmerId, query }),
  });
}
