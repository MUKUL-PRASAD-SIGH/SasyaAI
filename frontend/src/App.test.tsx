import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { ApiError } from "./api";
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
  loadStoredSession: vi.fn(),
  configureApiKey: vi.fn(),
  storeSession: vi.fn(),
  clearSession: vi.fn(),
  login: vi.fn(),
  googleLogin: vi.fn(),
  googleDemoLogin: vi.fn(),
  fetchAuthMe: vi.fn(),
  logout: vi.fn(),
  registerFarmer: vi.fn(),
  uploadFarmerImage: vi.fn(),
  listFarmerImages: vi.fn(),
  submitFeedback: vi.fn(),
  listAuditEvents: vi.fn(),
  searchMemory: vi.fn(),
}));

vi.mock("./api", () => ({
  ApiError: class ApiError extends Error {
    status?: number;
    constructor(message: string, status?: number) {
      super(message);
      this.status = status;
    }
  },
  apiBaseUrl: "http://127.0.0.1:8000",
  configureApiKey: apiMocks.configureApiKey,
  loadStoredSession: apiMocks.loadStoredSession,
  storeSession: apiMocks.storeSession,
  clearSession: apiMocks.clearSession,
  login: apiMocks.login,
  googleLogin: apiMocks.googleLogin,
  googleDemoLogin: apiMocks.googleDemoLogin,
  fetchAuthMe: apiMocks.fetchAuthMe,
  logout: apiMocks.logout,
  registerFarmer: apiMocks.registerFarmer,
  uploadFarmerImage: apiMocks.uploadFarmerImage,
  listFarmerImages: apiMocks.listFarmerImages,
  submitFeedback: apiMocks.submitFeedback,
  listAuditEvents: apiMocks.listAuditEvents,
  searchMemory: apiMocks.searchMemory,
  getKnowledgeStats: apiMocks.getKnowledgeStats,
  getRuntimeHealth: apiMocks.getRuntimeHealth,
  listAgents: apiMocks.listAgents,
  listDemoFarmers: apiMocks.listDemoFarmers,
  listSyntheticProductionFarmers: apiMocks.listSyntheticProductionFarmers,
  listHitlCases: apiMocks.listHitlCases,
  submitHitlDecision: apiMocks.submitHitlDecision,
  submitQuery: apiMocks.submitQuery,
}));

const officerPrincipal = {
  subject: "officer-west",
  roles: ["extension_officer"],
  allowed_regions: ["Maharashtra", "Karnataka"],
  authentication_method: "session_token",
};

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

function mockRuntimeContext() {
  apiMocks.getRuntimeHealth.mockResolvedValue({
    status: "ok",
    service: "SasyaAI",
    environment: "test",
    runtime_mode: "demo",
    data_source_mode: "live",
    agent_execution: "deterministic_fallback",
    auth_required: "true",
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

async function renderAuthenticatedOfficer() {
  apiMocks.loadStoredSession.mockReturnValue({
    token: "officer-session-token-0123456789",
    principal: officerPrincipal,
  });
  apiMocks.fetchAuthMe.mockResolvedValue(officerPrincipal);
  mockRuntimeContext();
  apiMocks.listHitlCases.mockResolvedValue([caseA, caseB]);
  render(<App />);
  expect(await screen.findByRole("button", { name: "Sign out" })).toBeInTheDocument();
}

beforeEach(() => {
  apiMocks.loadStoredSession.mockReturnValue({ token: "", principal: null });
  apiMocks.listFarmerImages.mockResolvedValue([]);
  apiMocks.searchMemory.mockResolvedValue([]);
  apiMocks.listAuditEvents.mockResolvedValue([]);
  apiMocks.logout.mockResolvedValue({ status: "logged_out" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("login gate", () => {
  it("shows the login page before any dashboard content", async () => {
    mockRuntimeContext();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Farmer/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Extension Officer/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /System Admin/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continue with Google/i })).toBeInTheDocument();
    expect(screen.getByText(/Advanced \/ reviewer API key/i)).toBeInTheDocument();
    expect(screen.queryByText("Operator access")).not.toBeInTheDocument();
    expect(screen.queryByText("Governed agricultural intelligence")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /HITL queue/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Ask a safety-gated question")).not.toBeInTheDocument();
  });

  it("signs in with an API key and reveals the role desk", async () => {
    mockRuntimeContext();
    apiMocks.listHitlCases.mockResolvedValue([]);
    apiMocks.login.mockResolvedValue({
      access_token: "farmer-session-token-0123456789",
      token_type: "bearer",
      subject: "farmer-asha",
      roles: ["farmer"],
      allowed_farmer_ids: ["AGR_MH_001234"],
      message: "Authenticated.",
    });
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Sign in" });
    await user.click(screen.getByText(/Advanced \/ reviewer API key/i));
    await user.type(
      screen.getByLabelText("Role-scoped API key"),
      "farmer-demo-key-0123456789abcdef",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(apiMocks.storeSession).toHaveBeenCalled();
    });
    expect(await screen.findByText("Farmer desk")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Demo scenario")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Farmer profile")).not.toBeInTheDocument();
  });

  it("requests an OTP then completes email login", async () => {
    mockRuntimeContext();
    apiMocks.listHitlCases.mockResolvedValue([]);
    apiMocks.login
      .mockResolvedValueOnce({
        access_token: "",
        token_type: "bearer",
        subject: "",
        roles: ["extension_officer"],
        otp_demo_code: "123456",
        message: "OTP sent.",
      })
      .mockResolvedValueOnce({
        access_token: "officer-session-token-0123456789",
        token_type: "bearer",
        subject: "officer-west",
        roles: ["extension_officer"],
        allowed_regions: ["Maharashtra"],
        message: "Authenticated.",
      });
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Sign in" });
    await user.click(screen.getByRole("radio", { name: /Extension Officer/i }));
    await user.type(screen.getByLabelText("Email"), "officer.west@demo.sasyaai.local");
    await user.click(screen.getByRole("button", { name: "Request OTP" }));

    expect(await screen.findByText(/Local OTP code/i)).toBeInTheDocument();
    expect(screen.getByText("123456")).toBeInTheDocument();

    await user.type(screen.getByLabelText("OTP code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Extension desk")).toBeInTheDocument();
  });

  it("shows register guidance when Google email is not registered", async () => {
    mockRuntimeContext();
    apiMocks.googleLogin.mockRejectedValue(
      new ApiError("Farmer not registered. Please register first.", 404),
    );
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Sign in" });
    await user.type(screen.getByLabelText("Email"), "new.farmer@gmail.com");
    await user.click(screen.getByRole("button", { name: /Continue with Google/i }));

    expect(
      await screen.findByText(/Farmer not registered\. Please register first\./i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register now" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("returns to the login page after sign out", async () => {
    await renderAuthenticatedOfficer();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(apiMocks.clearSession).toHaveBeenCalled();
    expect(apiMocks.logout).toHaveBeenCalled();
  });
});

describe("extension-officer review safety", () => {
  it("binds evidence and trace to the selected case", async () => {
    await renderAuthenticatedOfficer();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("tab", { name: /HITL queue/i }));
    expect(await screen.findByText("A evidence")).toBeInTheDocument();
    expect(screen.getByText("A trace")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review case CASE-B" }));

    expect(await screen.findByText("B evidence")).toBeInTheDocument();
    expect(screen.getByText("B trace")).toBeInTheDocument();
    expect(screen.queryByText("A evidence")).not.toBeInTheDocument();
  });

  it("clears a draft decision when the officer switches cases", async () => {
    await renderAuthenticatedOfficer();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("tab", { name: /HITL queue/i }));
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
    apiMocks.loadStoredSession.mockReturnValue({
      token: "officer-session-token-0123456789",
      principal: officerPrincipal,
    });
    apiMocks.fetchAuthMe.mockResolvedValue(officerPrincipal);
    mockRuntimeContext();
    apiMocks.listHitlCases.mockResolvedValue([caseA]);
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("button", { name: "Sign out" })).toBeInTheDocument();
    await user.click(await screen.findByRole("tab", { name: /HITL queue/i }));
    await screen.findByText("A evidence");
    await user.selectOptions(screen.getByLabelText("Decision"), "edit_and_approve");
    await user.type(screen.getByLabelText("Decision reason"), "A reviewer note.");
    await user.click(screen.getByRole("button", { name: "Record immutable decision" }));

    expect(apiMocks.submitHitlDecision).not.toHaveBeenCalled();
    expect(apiMocks.submitQuery).not.toHaveBeenCalled();
  });
});
