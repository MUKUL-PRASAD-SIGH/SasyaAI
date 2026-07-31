export type Intent = "crop_plan_request" | "diagnose" | "scheme_query";

export type VerificationStatus = "pass" | "fail" | "not_applicable";

export interface QueryRequest {
  farmer_id: string;
  query: string;
  intent?: Intent;
  language: string;
  requested_dose_ml_per_l?: number;
  image_id?: string;
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

export interface AgentRun {
  agent_id: string;
  name: string;
  role: string;
  status: "completed" | "failed" | "skipped";
  execution_mode: "llm" | "deterministic" | "tool";
  duration_ms: number;
  summary: string;
  model?: string | null;
  input_sources: string[];
  output_confidence?: number | null;
}

export interface AgentDescriptor {
  agent_id: string;
  name: string;
  role: string;
  responsibilities: string[];
  kind: "manager" | "reasoning" | "tool" | "safety";
  production_model?: string | null;
  can_write_memory: boolean;
}

export interface KnowledgeStats {
  runtime_mode: "demo" | "production";
  collections: Record<string, number>;
  total_documents: number;
  regions: number;
  crops: number;
}

export interface RuntimeHealth {
  status: string;
  service: string;
  environment: string;
  runtime_mode: "demo" | "production";
  data_source_mode: "live" | "synthetic";
  agent_execution: string;
  auth_required?: string;
  google_oauth_enabled?: string;
}

export type AppRole = "farmer" | "extension_officer" | "system_admin";

export interface SessionPrincipal {
  subject: string;
  roles: string[];
  allowed_farmer_ids?: string[] | null;
  allowed_regions?: string[] | null;
  authentication_method?: string;
}

export interface LoginPayload {
  role: AppRole;
  auth_method: "api_key" | "email_otp";
  api_key?: string;
  email?: string;
  otp_code?: string;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  subject: string;
  roles: string[];
  allowed_farmer_ids?: string[] | null;
  allowed_regions?: string[] | null;
  otp_demo_code?: string | null;
  message: string;
}

export interface OnboardingPayload {
  name: string;
  email: string;
  state: string;
  district: string;
  preferred_language: string;
  season: string;
  current_crop: string;
  soil_fertility: string;
  water_budget_mm: number;
  budget_inr: number;
  farm_size_hectares: number;
  soil_type: string;
  irrigation_type: string;
}

export interface FeedbackPayload {
  farmer_id: string;
  request_id: string;
  query: string;
  recommendation: string;
  helpful: boolean;
  note: string;
}

export interface DemoFarmerSummary {
  farmer_id: string;
  name: string;
  state: string;
  district: string;
  preferred_language: string;
  current_crop: string;
  season: string;
  water_budget_mm: number;
  farm_size_hectares: number;
}

export interface AdvisoryResponse {
  request_id: string;
  farmer_id: string;
  safety_rule_set_version: string;
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
  agent_runs: AgentRun[];
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
  safety_rule_set_version?: string | null;
  intent?: Intent | null;
  confidence?: number | null;
  original_recommendation?: string;
  original_explanation?: string;
  evidence?: Evidence[];
  verification?: VerificationCheck[];
  trace?: TraceEvent[];
  agent_runs?: AgentRun[];
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
