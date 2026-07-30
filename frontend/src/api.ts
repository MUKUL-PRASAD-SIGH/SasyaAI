import type {
  AdvisoryResponse,
  DecisionRequest,
  HitlCase,
  QueryRequest,
} from "./types";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const apiBaseUrl = rawBaseUrl.replace(/\/+$/, "");

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

  try {
    response = await fetch(apiBaseUrl + path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
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
