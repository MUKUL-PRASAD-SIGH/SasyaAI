import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { HitlCase } from "./types";

const apiMocks = vi.hoisted(() => ({
  getKnowledgeStats: vi.fn(),
  getRuntimeHealth: vi.fn(),
  listAgents: vi.fn(),
  listDemoFarmers: vi.fn(),
  listSyntheticProductionFarmers: vi.fn(),
  listHitlCases: vi.fn(),
  submitHitlDecision: vi.fn(),
  submitQuery: vi.fn(),
}));

vi.mock("./api", () => ({
  ApiError: class ApiError extends Error {},
  apiBaseUrl: "http://127.0.0.1:8000",
  configureApiKey: vi.fn(),
  getKnowledgeStats: apiMocks.getKnowledgeStats,
  getRuntimeHealth: apiMocks.getRuntimeHealth,
  listAgents: apiMocks.listAgents,
  listDemoFarmers: apiMocks.listDemoFarmers,
  listSyntheticProductionFarmers: apiMocks.listSyntheticProductionFarmers,
  listHitlCases: apiMocks.listHitlCases,
  submitHitlDecision: apiMocks.submitHitlDecision,
  submitQuery: apiMocks.submitQuery,
}));

const caseA: HitlCase = {
  case_id: "CASE-A",
  farmer_id: "AGR_MH_001234",
  status: "pending",
  reason: "Confidence is below the auto-delivery threshold.",
  intent: "diagnose",
  confidence: 0.62,
  original_recommendation: "Capture a cotton leaf photo.",
  evidence: [{ source: "pest_kb", title: "A evidence", score: 0.9, metadata: {} }],
  verification: [{ name: "water_budget", status: "pass", message: "A check" }],
  trace: [{ stage: "planner", status: "completed", detail: "A trace" }],
  created_at: "2026-07-30T10:00:00Z",
  decision_history: [],
};

const caseB: HitlCase = {
  ...caseA,
  case_id: "CASE-B",
  farmer_id: "AGR_KA_009012",
  original_recommendation: "Capture a maize leaf photo.",
  evidence: [{ source: "pest_kb", title: "B evidence", score: 0.85, metadata: {} }],
  verification: [{ name: "pesticide_safety", status: "pass", message: "B check" }],
  trace: [{ stage: "verifier", status: "completed", detail: "B trace" }],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function mockRuntimeContext() {
  apiMocks.getRuntimeHealth.mockResolvedValue({
    status: "ok",
    service: "SasyaAI",
    environment: "test",
    runtime_mode: "demo",
    data_source_mode: "live",
    agent_execution: "deterministic_fallback",
  });
  apiMocks.listAgents.mockResolvedValue([]);
  apiMocks.getKnowledgeStats.mockResolvedValue({
    runtime_mode: "demo",
    collections: { crop_kb: 54, pest_kb: 36, scheme_kb: 15 },
    total_documents: 105,
    regions: 18,
    crops: 20,
  });
  apiMocks.listDemoFarmers.mockResolvedValue([]);
  apiMocks.listSyntheticProductionFarmers.mockResolvedValue([]);
}

describe("extension-officer review safety", () => {
  it("binds evidence and trace to the selected case", async () => {
    mockRuntimeContext();
    apiMocks.listHitlCases.mockResolvedValue([caseA, caseB]);
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("A evidence")).toBeInTheDocument();
    expect(screen.getByText("A trace")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review case CASE-B" }));

    expect(await screen.findByText("B evidence")).toBeInTheDocument();
    expect(screen.getByText("B trace")).toBeInTheDocument();
    expect(screen.queryByText("A evidence")).not.toBeInTheDocument();
  });

  it("clears a draft decision when the officer switches cases", async () => {
    mockRuntimeContext();
    apiMocks.listHitlCases.mockResolvedValue([caseA, caseB]);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("A evidence");
    await user.selectOptions(screen.getByLabelText("Decision"), "edit_and_approve");
    await user.type(screen.getByLabelText("Decision reason"), "Draft note for case A.");
    await user.type(
      screen.getByLabelText("Edited farmer-facing recommendation"),
      "Draft edit for case A.",
    );

    await user.click(screen.getByRole("button", { name: "Review case CASE-B" }));

    expect(screen.getByLabelText<HTMLSelectElement>("Decision").value).toBe("approve");
    expect(screen.getByLabelText<HTMLTextAreaElement>("Decision reason").value).toBe("");
    expect(screen.queryByLabelText("Edited farmer-facing recommendation")).not.toBeInTheDocument();
  });

  it("does not submit an edit-and-approve decision without edited advice", async () => {
    mockRuntimeContext();
    apiMocks.listHitlCases.mockResolvedValue([caseA]);
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("A evidence");
    await user.selectOptions(screen.getByLabelText("Decision"), "edit_and_approve");
    await user.type(screen.getByLabelText("Decision reason"), "A reviewer note.");
    await user.click(screen.getByRole("button", { name: "Record immutable decision" }));

    expect(apiMocks.submitHitlDecision).not.toHaveBeenCalled();
    expect(apiMocks.submitQuery).not.toHaveBeenCalled();
  });
});
