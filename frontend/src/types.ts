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
  agent_execution: string;
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
