export type Intent = "crop_plan_request" | "diagnose" | "scheme_query";

export type VerificationStatus = "pass" | "fail" | "not_applicable";

export interface QueryRequest {
  farmer_id: string;
  query: string;
  intent?: Intent;
  language: string;
  requested_dose_ml_per_l?: number;
}

export interface Evidence {
  source: string;
  title: string;
  score: number;
  metadata: Record<string, string | number | boolean | string[]>;
}

export interface VerificationCheck {
  name: string;
  status: VerificationStatus;
  message: string;
}

export interface TraceEvent {
  stage: string;
  status: "completed" | "skipped" | "queued";
  detail: string;
}

export interface AdvisoryResponse {
  request_id: string;
  farmer_id: string;
  intent: Intent;
  status: "delivered" | "requires_human_review";
  confidence: number;
  recommendation: string;
  explanation: string;
  evidence: Evidence[];
  reflection: {
    status: "pass" | "revise";
    notes: string[];
  };
  verification: VerificationCheck[];
  trace: TraceEvent[];
  hitl_case_id: string | null;
}

export type Decision = "approve" | "edit_and_approve" | "reject";
export type CaseStatus = "pending" | "approved" | "rejected";

export interface DecisionHistoryItem {
  decision: Decision;
  reviewer_name: string;
  reviewer_note: string;
  edited_recommendation: string | null;
  decided_at: string;
}

export interface HitlCase {
  case_id: string;
  farmer_id: string;
  status: CaseStatus;
  reason: string;
  request_id?: string;
  intent?: Intent | null;
  confidence?: number | null;
  original_recommendation?: string;
  original_explanation?: string;
  evidence?: Evidence[];
  verification?: VerificationCheck[];
  trace?: TraceEvent[];
  created_at?: string;
  reviewer_note?: string | null;
  edited_recommendation?: string | null;
  decision_history?: DecisionHistoryItem[];
}

export interface DecisionRequest {
  decision: Decision;
  reviewer_name: string;
  reviewer_note: string;
  edited_recommendation?: string;
}
