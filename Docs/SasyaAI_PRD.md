# 📄 PRODUCT REQUIREMENTS DOCUMENT
# SasyaAI — An Agentic Digital Twin for the Indian Farmer

**HiDevs "Zero to AI Builder" Hackathon Submission — Open Innovation Track**
**Version:** 2.1 (Rubric-Aligned) · **Date:** July 2026 · **Team Size:** 5
**Difficulty checklist coverage: 9/9** — see §0.1

---

## 0. How to Read This PRD

This is not a CRUD feature spec. SasyaAI is a **multi-agent AI system**, and this document is organized the way judges evaluate agentic AI products: business framing first, then the full agent architecture stack — orchestration, tools, memory, reflection, verification, and failure recovery — before requirements and delivery plan.

| Section | Answers |
|---|---|
| 1–2 | Why does this need to exist, and what is it? |
| 3 | How do agents think, plan, and collaborate? (Google ADK) |
| 4 | How is the agent graph orchestrated, monitored, and approved? (Lyzr) |
| 5 | How does the system remember anything? (Memory + Qdrant) |
| 6 | What tools can agents actually call? |
| 7 | How does the system catch its own mistakes? (Reflection/Verification/HITL) |
| 8 | What happens when something fails? |
| 9 | What does the digital twin look like as data? |
| 10 | Functional & non-functional requirements |
| 11 | Data sources & derived features |
| 12 | Security, privacy, and DPDP compliance |
| 13 | Deployment, team, roadmap, risks |
| 14 | Sequence walkthrough — one query, end to end |

---

## 1. Business Problem

India has ~**100M+ operational landholdings**, over 85% of them under 2 hectares. Smallholder farmers make dozens of consequential decisions a season — what to sow, how to manage pests, when to irrigate, which scheme to claim — with fragmented, delayed, and often contradictory information: a Krishi Vigyan Kendra officer says one thing, a local input dealer says another, WhatsApp forwards say a third. Extension services in India have a ratio of roughly **1 agricultural officer to 1,000+ farmers**, so most advice never arrives in time to matter.

Meanwhile, the raw ingredients for good decisions already exist in government systems — AgriStack farmer/land/crop registries, ICAR's KrishiDSS, IMD weather, ISRO satellite feeds, eNAM market prices, DPPQ&S pest imagery — but they are siloed, technical, and never fused into a single, personalized, continuously-updating view of *one farmer's* situation.

**The problem is not lack of data. It's lack of a system that can reason over that data, on behalf of a specific farmer, the way a personal agronomist would — and that stays right the second, third, and hundredth time, not just the first.**

---

## 2. Product Vision

> **"Every Indian farmer deserves a personal agricultural scientist in their pocket — one that knows their land, their history, their constraints, and their aspirations."**

SasyaAI is a **Digital Twin** for each farmer — a continuously-updated state representation of their land, crops, finances, environment, and risk — driven by a **multi-agent AI system** that plans, retrieves, calls tools, checks its own work, and escalates to a human when it isn't sure. It is not a chatbot with an agriculture skin; it's an agentic reasoning system where the chat interface is just the front door.

**What makes it agentic, not just AI-assisted:** every recommendation passes through explicit planning, tool calling, memory retrieval, self-reflection, constraint verification, and — for low-confidence or high-stakes cases — human approval, before it ever reaches a farmer. The system can explain *why* it decided something, not just *what* it decided.

---

## 3. Agent Architecture — Google ADK Design

### 3.1 Why Google ADK

ADK gives us a typed agent hierarchy with native support for sub-agents, tool-calling, session state, and event-driven callbacks — which maps cleanly onto the reasoning lifecycle a farm-advisory system actually needs: decompose → delegate → retrieve → act → check → explain.

### 3.2 The Agent Graph

```
                         ┌─────────────────────────┐
                         │        FARMER            │
                         │  (voice / text / photo)  │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │   INTENT CLASSIFIER       │
                         │  (LLM router — 6 intents: │
                         │  plan / diagnose / scheme /│
                         │  weather-alert / market /  │
                         │  general-query)           │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │      ROOT AGENT           │
                         │   (ADK LlmAgent, orchestrates│
                         │   the whole session)      │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │     PLANNER AGENT         │
                         │  Decomposes intent into a │
                         │  directed task graph      │
                         └────────────┬─────────────┘
                                      │
              ┌───────────┬──────────┼──────────┬───────────┐
              │           │          │          │           │
        ┌─────▼────┐┌─────▼────┐┌────▼─────┐┌───▼──────┐┌───▼──────┐
        │ PLANNING ││  VISION  ││GEOSPATIAL││MONITORING││  MARKET   │
        │  AGENT   ││  AGENT   ││  AGENT   ││  AGENT   ││  AGENT    │
        │(SubAgent)││(SubAgent)││(SubAgent)││(SubAgent)││(SubAgent) │
        └─────┬────┘└─────┬────┘└────┬─────┘└───┬──────┘└───┬──────┘
              │           │          │          │           │
              └───────────┴────┬─────┴──────────┴───────────┘
                                │  (parallel execution via ADK
                                │   ParallelAgent, results joined)
                       ┌────────▼─────────┐
                       │   MEMORY AGENT     │
                       │ writes/reads twin, │
                       │ episodic + semantic│
                       └────────┬───────────┘
                       ┌────────▼─────────┐
                       │  REFLECTION AGENT  │
                       │ self-critiques draft│
                       │ answer against goal │
                       └────────┬───────────┘
                       ┌────────▼─────────┐
                       │  VERIFIER AGENT    │
                       │ hard constraint    │
                       │ checks (see §7.2)  │
                       └────────┬───────────┘
                          pass  │  fail → re-plan (loop to Planner,
                                │          max 2 retries)
                       ┌────────▼─────────┐
                       │ CONFIDENCE SCORER  │
                       └────────┬───────────┘
                     low conf.  │  high conf.
                ┌───────────────┴──────────┐
        ┌───────▼────────┐         ┌───────▼────────┐
        │ HUMAN-IN-LOOP   │         │ XAI EXPLAINER   │
        │ (Extension      │         │ builds reasoning │
        │  Officer queue) │         │ chain in NL      │
        └───────┬────────┘         └───────┬────────┘
                └─────────────┬────────────┘
                     ┌─────────▼──────────┐
                     │  NOTIFICATION AGENT │
                     │ pushes to farmer +  │
                     │ updates Digital Twin│
                     └──────────────────────┘
```

### 3.3 Agent-by-Agent Specification

Each agent below is implemented as an ADK `LlmAgent` (reasoning agents) or `Agent` wrapping deterministic code (tool-heavy agents), registered as a sub-agent of the Root Agent.

#### RootAgent
- **Objective:** Own the session, hold conversation state, decide when the task graph is complete, decide whether to loop back to the Planner.
- **Inputs:** Classified intent, session history, farmer_id.
- **Outputs:** Final response object (text/voice/structured card) + twin update event.
- **Tools:** none directly — delegates via `transfer_to_agent`.
- **Memory accessed:** session (working) memory only.
- **Failure mode:** if no sub-agent responds within timeout (8s default), returns a degraded "we're checking on this, I'll notify you" response and queues an async retry job.

#### PlannerAgent
- **Objective:** Convert an intent into a task graph — an ordered/parallel set of sub-agent calls with explicit dependencies.
- **Inputs:** Intent, farmer digital twin snapshot, prior conversation turns.
- **Outputs:** `TaskGraph` JSON (see §3.4).
- **Tools:** `get_twin_summary()`, `estimate_task_complexity()`.
- **Prompted with:** few-shot examples of intent → task graph mappings, and a rule that any task touching money, medicine/pesticide dosage, or scheme eligibility must be flagged `requires_verification: true`.
- **Failure mode:** malformed task graph → falls back to a single-agent default route per intent type (e.g., "diagnose" always routes to Vision Agent alone).

#### PlanningAgent (crop/finance sub-agent)
- **Objective:** Recommend a ranked crop plan.
- **Method:** Constraint-aware optimization — Google OR-Tools integer program for feasibility (water budget, land area, capital) layered under LLM guidance for ranking and explanation, evaluated across a **Pareto frontier** of yield, profit, and ecological sustainability.
- **Inputs:** soil health (from twin), water availability, market price forecast (from Market Agent), scheme eligibility (from twin), budget.
- **Outputs:** ranked crop options, input schedule, financial projection, risk-adjusted ROI, reasoning trace.
- **Tools:** `or_tools_solver()`, `enam_price_forecast()`, `scheme_eligibility_check()`.
- **Memory read:** Farmer Memory (financial + agronomy layers), Crop Memory collection (Qdrant).
- **Memory write:** none directly — writes go through Memory Agent.

#### VisionAgent
- **Objective:** Identify pest/disease from a farmer photo, grade severity, recommend treatment.
- **Method:** YOLOv8 (fine-tuned on NPSS) for detection, EfficientNet-B4 for severity grading, few-shot classification head for rare/emerging pests not in the base training set.
- **Inputs:** image, crop type (from twin), region (for pest-prevalence prior).
- **Outputs:** pest/disease label, confidence, severity (0–5), affected-area estimate, CIB-approved treatment protocol with dosage and cost.
- **Tools:** `yolo_infer()`, `severity_model()`, `treatment_db_lookup()`.
- **On-device variant:** quantized model runs locally for offline inference; syncs result to twin when connectivity resumes.
- **Failure mode:** confidence < 0.6 → auto-flagged for Human-in-Loop review rather than shown to farmer as certain.

#### GeospatialAgent
- **Objective:** Field-level environmental context — canopy health, water stress, microclimate risk.
- **Method:** NDVI/NDWI/EVI time-series from Sentinel-2 via ISRO Bhuvan, cross-referenced with KrishiDSS district advisories and CGWB groundwater regression.
- **Tools:** `ndvi_lookup()`, `krishidss_query()`, `groundwater_model()`.
- **Outputs:** farm health map layer, water-stress flag, microclimatic risk zone.

#### MarketAgent
- **Objective:** Price context and volatility signal for planning decisions.
- **Tools:** `enam_price_feed()`, `price_volatility_score()`.
- **Outputs:** current price, 30-day trend, Price Volatility Score, Input-Output Price Ratio.

#### MonitoringAgent
- **Objective:** Continuous, always-on constraint verification and proactive alerting — separate from the per-query Verifier Agent below, this one runs on a schedule against the whole farmer base.
- **Tools:** `scheme_deadline_scan()`, `weather_threshold_scan()`, `price_crash_scan()`.
- **Outputs:** alert events pushed to Kafka `farmer.alerts` topic, consumed by Notification Agent.

#### MemoryAgent
- **Objective:** Sole read/write path into the Digital Twin and Qdrant memory stores — keeps every other agent stateless with respect to persistence.
- **Tools:** `twin_read()`, `twin_write()`, `qdrant_upsert()`, `qdrant_search()`.
- **Enforces:** schema validation, PII field encryption before write (see §12), TTL policy per memory tier (§5).

#### ReflectionAgent
- **Objective:** Before anything reaches the farmer, re-read the draft answer against the original farmer intent and twin context, and ask: *does this actually answer what was asked, in a way this specific farmer can act on?*
- **Method:** Single LLM call with a structured self-critique prompt — checks for internal contradiction, missing units/dosage, tone mismatch (e.g., overly technical for a low-literacy persona), and whether the answer silently assumed data it doesn't have.
- **Outputs:** either "pass" or a revision instruction sent back to the originating sub-agent (max 1 revision loop before falling through to Verifier as-is).

#### VerifierAgent
- **Objective:** Hard, non-negotiable constraint gate — deterministic, not LLM-judgment-based, for anything with real-world consequence. See §7.2 for the constraint catalogue.
- **Outputs:** `PASS` / `FAIL(reason, violated_constraint)`.
- **On FAIL:** emits a re-planning event back to PlannerAgent with the failure reason attached, capped at 2 retries, after which it routes to Human-in-Loop regardless of confidence score.

#### ConfidenceScorer
- **Objective:** Produce a single 0–1 confidence score combining model confidence (Vision/Planning outputs), data freshness, and verifier pass margin.
- **Threshold:** < 0.7 → Human-in-Loop; ≥ 0.7 → auto-deliver with XAI explanation.

#### XAI Explainer
- **Objective:** Turn the internal reasoning trace into a plain-language "because X → therefore Y" chain in the farmer's language.
- **Output:** Structured Reasoning Graph (DAG) + rendered natural-language explanation + confidence badge.

#### NotificationAgent
- **Objective:** Final delivery — push notification, SMS, voice callback, or in-app card — and the trigger for the Digital Twin update.

### 3.4 Task Graph Contract

The Planner emits a typed task graph rather than free text, so downstream agents and the ADK `ParallelAgent` runner can execute deterministically:

```json
{
  "task_graph_id": "tg_88213",
  "farmer_id": "AGR_MH_001234",
  "intent": "crop_plan_request",
  "nodes": [
    {"id": "n1", "agent": "geospatial_agent", "depends_on": []},
    {"id": "n2", "agent": "market_agent", "depends_on": []},
    {"id": "n3", "agent": "planning_agent", "depends_on": ["n1", "n2"]}
  ],
  "requires_verification": true,
  "requires_reflection": true
}
```

---

## 4. Orchestration Layer — Lyzr Agent Graph

Where ADK defines *what each agent is and how it reasons*, **Lyzr** owns the *operational lifecycle* of running that agent graph in production: retries, timeouts, human approval routing, and live monitoring.

```
Lyzr Managed Lifecycle
─────────────────────────────────────────────────────────
   PLANNER  →  EXECUTOR  →  REFLECTION  →  MEMORY
      │                                       │
      └──────────────► MONITORING ◄───────────┘
                            │
                    ┌───────┴───────┐
                    │               │
              RETRY (≤2)    HUMAN APPROVAL
                    │               │
                    └───────┬───────┘
                            ▼
                        DELIVERY
```

**What Lyzr adds on top of the ADK graph:**

| Capability | Implementation |
|---|---|
| Retry policy | Exponential backoff, max 2 retries per task node, then escalate |
| Timeout budget | 8s per sub-agent call, 20s total task-graph budget before degraded response |
| Human approval routing | Confidence < 0.7 or Verifier `FAIL` after retries → routed to Extension Officer queue with full reasoning trace attached |
| Live monitoring | Per-agent latency, failure rate, and confidence-score distribution streamed to Grafana (see §13.4) |
| Cost governance | Per-session LLM token budget; Planner must stay within budget or fall back to deterministic routing |
| Session replay | Every task graph execution logged immutably for audit and debugging (ties into the audit log in §12) |

---

## 5. Memory Architecture

A farm-advisory agent is only as good as what it remembers about *this* farmer versus what it knows in general. SasyaAI separates memory into five tiers, each with a distinct owner, TTL, and retrieval policy.

| Tier | Contents | Owner | TTL | Update Policy | Retrieval |
|---|---|---|---|---|---|
| **Working Memory** | Current conversation turn, task graph state | RootAgent | Session (cleared on close) | Overwrite each turn | Direct in-context |
| **Conversation Memory** | Last N turns this session | RootAgent | Session + 24hr | Append | In-context window |
| **Digital Twin (State Memory)** | Identity, agronomy, financial, environmental, risk layers | MemoryAgent | Persistent, versioned | Event-driven (≤15 min after triggering event) | PostgreSQL keyed by farmer_id |
| **Episodic Memory** | Past recommendations + outcomes ("last season we suggested X, farmer planted Y") | MemoryAgent | 5 years (crop history), 12 months (advisory history) | Append-only, immutable | Qdrant `farmer_memory` collection, filtered by farmer_id |
| **Semantic / Knowledge Memory** | Crop knowledge, pest treatment protocols, government scheme rules | MemoryAgent (read-only for other agents) | Refreshed on source update | Batch re-embed on KB change | Qdrant `crop_kb`, `pest_kb`, `scheme_kb` collections, shared across all farmers |

### 5.1 Qdrant Collection Design

Judges specifically want to see collection-level design, not "we use a vector DB" — here it is:

```
Collections
├── farmer_memory        # one point per (farmer, advisory event)
│   payload: {farmer_id, event_type, crop, season, outcome, timestamp}
│   vector: embedding of advisory text + outcome note
│
├── crop_memory           # crop agronomy knowledge base
│   payload: {crop, region, soil_type, source: "KrishiDSS"}
│
├── pest_kb                # pest/disease knowledge + treatment protocols
│   payload: {pest_name, crop, region, cib_approved_inputs, severity_bands}
│
├── scheme_kb              # government scheme rules & eligibility text
│   payload: {scheme_name, state, eligibility_json, deadline}
│
├── weather_history        # rolling weather archive per micro-region
│   payload: {region_id, date_range, source: "IMD"}
│
└── market_history         # eNAM price history per mandi/commodity
    payload: {mandi, commodity, date_range}
```

- **Embedding model:** `sentence-transformers/multilingual-e5-large` (covers the 10+ Indian languages in scope).
- **Hybrid search:** dense vector similarity + payload filters (farmer_id, crop, region, date range) — pure semantic search alone is not acceptable for financial/scheme content where exact filters matter more than similarity.
- **Namespacing:** one logical namespace per collection above; `farmer_memory` additionally partitioned by `farmer_id` prefix for query isolation and easy per-farmer export/delete (DPDP right-to-erasure, §12).

---

## 6. Tool-Calling Architecture

All agents call tools through a single typed tool registry so the Planner can reason about *what's callable* without hardcoding integrations per agent.

| Tool | Called By | Backing Service |
|---|---|---|
| `agristack_farmer_lookup()` | RootAgent, PlanningAgent | AgriStack Farmer Data API |
| `agristack_land_lookup()` | GeospatialAgent | AgriStack Land Data API |
| `agristack_crop_lookup()` | PlanningAgent, MonitoringAgent | AgriStack Crop Data API |
| `agristack_consent_check()` | RootAgent (pre-flight, every session) | AgriStack Consent API |
| `imd_weather()` | GeospatialAgent, MonitoringAgent | IMD Open Data Portal |
| `enam_price_feed()` | MarketAgent, PlanningAgent | eNAM API |
| `bhuvan_satellite()` | GeospatialAgent | ISRO Bhuvan WCS/WMS |
| `cgwb_groundwater()` | GeospatialAgent | CGWB API |
| `yolo_infer()` | VisionAgent | Self-hosted GPU inference service |
| `or_tools_solver()` | PlanningAgent | Self-hosted optimization service |
| `scheme_eligibility_check()` | PlanningAgent, MonitoringAgent | PM-KISAN / DBT Bharat API |
| `qdrant_search()` / `qdrant_upsert()` | MemoryAgent only | Qdrant cluster |
| `twin_read()` / `twin_write()` | MemoryAgent only | PostgreSQL + PostGIS |

**Design rule:** only MemoryAgent may write to persistent state. Every other agent is stateless read-and-reason — this is what makes the Verifier and Reflection loop safe to retry without side effects.

---

## 7. Reflection, Verification & Human-in-the-Loop

### 7.1 Why two separate check layers

Reflection catches *reasoning* quality problems (unclear, incomplete, tone-mismatched). Verification catches *hard-fact* problems (violates a real-world constraint). Conflating them is a common mistake — an answer can be beautifully reasoned and still recommend an input dose that exceeds the CIB-approved limit. They run as separate, distinctly-typed agents for that reason.

### 7.2 Verifier Constraint Catalogue (illustrative, not exhaustive)

| Domain | Constraint | Action on violation |
|---|---|---|
| Water | Recommended irrigation ≤ available water budget in twin | Re-plan with tightened water constraint |
| Finance | Recommended input cost ≤ farmer's stated budget + eligible credit | Re-rank crop options, flag financing gap |
| Pesticide | Dosage ≤ CIB-approved maximum for crop+pest combination | Hard block, route to Human-in-Loop, never auto-deliver |
| Scheme | Eligibility claim matches current scheme rules in `scheme_kb` | Re-check against latest scheme_kb version; if stale, refresh and re-verify |
| Safety | No recommendation issued during active extreme-weather advisory (frost/cyclone) for that region | Suppress non-urgent recommendation, issue safety alert instead |

### 7.3 Human-in-the-Loop Routing

```
Confidence Scorer output
        │
   < 0.7 or Verifier FAIL (after 2 retries)
        │
        ▼
Extension Officer Queue (dashboard.sasyaai.ai)
        │
   Officer reviews: reasoning trace + twin snapshot + draft answer
        │
   ┌────┴────┐
 Approve   Edit & Approve   Reject (send back to Planner with note)
        │
        ▼
  Delivered to farmer, tagged "reviewed by extension officer"
```

This is not a fallback bolted on for safety theater — it is the trust mechanism the whole product leans on for agriculture, where a wrong recommendation has real financial and food-security consequences.

---

## 8. Failure Handling & Graceful Degradation

Production agent systems fail constantly at the tool layer (rate limits, API downtime, stale data) — the product design has to assume that and degrade gracefully rather than surface a raw error or, worse, a confident wrong answer.

**Worked example — weather data source failure:**

```
Primary: IMD live feed
   │ fails / times out
   ▼
Fallback 1: ISRO satellite-derived precipitation estimate
   │ unavailable
   ▼
Fallback 2: 10-year historical average for the micro-region + date
   │
   ▼
Confidence score automatically reduced by fallback-tier penalty
   │
   ▼
Farmer informed explicitly: "Based on typical weather for this time
of year (live data temporarily unavailable) —"
```

**General failure-handling rules applied across all tool calls:**

| Failure type | Response |
|---|---|
| Tool timeout | Retry once (Lyzr policy), then fallback source if defined, else degrade confidence |
| Stale data (beyond freshness SLA) | Flag in reasoning trace, reduce confidence score |
| Sub-agent exception | RootAgent catches, returns partial answer with explicit "couldn't complete X" note, never a silent partial |
| Verifier fails twice | Force Human-in-Loop regardless of confidence score |
| Total task-graph timeout (20s) | Return "checking and will notify you" + async job queued, farmer notified on completion |

---

## 9. Digital Twin Data Model

The digital twin is the persistent state every agent reads from and the Memory Agent writes to. Structurally unchanged from the original architecture, now explicitly framed as the shared state substrate for the agent graph:

```
FarmerTwin {
  identity: {
    farmerId: String        // AgriStack unique ID
    aadhaarLinked: Boolean
    location: GeoPoint       // Village centroid
    landParcels: [Parcel]    // Bhuvan/DILRMP linked
  }
  agronomyProfile: {
    soilHealthCards: [SHC]   // Historical + latest
    cropHistory: [Season]    // 5-year rolling
    irrigationSource: Enum   // Canal/borewell/rain-fed
    farmEquipment: [Item]
  }
  financialProfile: {
    schemeEligibility: [Scheme]
    creditScore: Float
    marketLinkages: [FPO, APMC]
  }
  environmentalState: {
    ndviTimeSeries: [Float]
    currentWeather: WeatherObject
    soilMoisture: Float
    pestRiskScore: Float      // 0–1, updated daily
  }
  recommendations: {
    active: [Recommendation]
    history: [Recommendation]
    verificationStatus: Enum
  }
  personaCluster: String      // e.g. "Risk-Averse Smallholder"
}
```

Update trigger: any weather/market/sensor/agent-output event → twin refresh within **15 minutes** (FR-002).

---

## 10. Requirements

### 10.1 Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| FR-001 | Digital Twin | Create and maintain a unique digital twin per farmer, keyed to AgriStack ID |
| FR-002 | Digital Twin | Refresh twin within 15 minutes of any triggering event |
| FR-003 | Digital Twin | Retain 5 years of crop history, 12 months of advisory history |
| FR-010 | Planning | Generate crop recommendations considering soil, water, market, schemes |
| FR-011 | Planning | Produce input schedules with cost estimates |
| FR-012 | Planning | Output financial projections per recommendation |
| FR-020 | Vision | Accept image uploads from mobile app |
| FR-021 | Vision | Identify pest/disease with >85% accuracy on NPSS validation set |
| FR-022 | Vision | Provide severity grading (0–5) and affected-area estimate |
| FR-023 | Vision | Generate treatment protocol with CIB-approved inputs |
| FR-030 | Geospatial | Visualize farm boundaries on interactive map |
| FR-031 | Geospatial | Display NDVI layer with field-level health interpretation |
| FR-032 | Geospatial | Flag water-stress zones, recommend irrigation adjustments |
| FR-040 | Monitoring | Run constraint validation on 100% of agent outputs |
| FR-041 | Monitoring | Send proactive alerts for frost, excess rain, price drops, scheme deadlines |
| FR-050 | Interface | Support text and voice input in 10+ Indian languages |
| FR-051 | Interface | Explain every recommendation with a reasoning chain |
| **FR-060** | **Agent Orchestration** | **Every recommendation-class response must pass through Planner → Sub-agents → Reflection → Verifier → Confidence Scorer before delivery** |
| **FR-061** | **Agent Orchestration** | **Any response scoring confidence < 0.7 must route to Human-in-Loop before delivery** |
| **FR-062** | **Memory** | **All persistent reads/writes must go through the Memory Agent; no other agent may write to the twin or Qdrant directly** |
| **FR-063** | **Failure Handling** | **Every external tool call must define a fallback source or explicit degraded-confidence response** |

### 10.2 Non-Functional Requirements

| Requirement | Target |
|---|---|
| API Response Time (P95) | < 2 seconds |
| Vision Inference Latency | < 5 seconds on mobile |
| Full task-graph latency (P95) | < 20 seconds, including reflection + verification |
| System Availability | 99.5% uptime |
| Concurrent Users | 10,000 simultaneous |
| Data Freshness | Weather: 15 min · Market: 30 min · Satellite: 48 hr |
| Offline Capability | Core advisory + Vision Agent functional without internet |
| Language Support | 10+ Indian languages + English |

---

## 11. Data Sources & Derived Features

### 11.1 Datasets

| Dataset | Source | Format | Volume |
|---|---|---|---|
| Farmer Registry | AgriStack API (sandbox → production) | JSON/REST | ~100M records |
| Soil Health Cards | Department of Agriculture | CSV + API | ~230M cards |
| Land Records (DILRMP) | MoRD / State portals | GeoJSON | Parcel-level |
| NPSS Pest Images | DPPQ&S | JPEG (labeled) | ~50K images |
| KrishiDSS Advisory | ICAR | XML/API | District-level |
| GICEN Geospatial | GICEN / INDIAAI | Shapefiles/GeoJSON/CSV | Multi-layer |
| IMD Weather | IMD Open Data Portal | NetCDF/CSV | Grid + station |
| eNAM Market Prices | eNAM API | JSON | Daily, 1000+ mandis |
| Satellite Imagery | ISRO Bhuvan / Copernicus | GeoTIFF | Bi-weekly |

### 11.2 Derived Features

| Category | Feature | Derivation |
|---|---|---|
| Soil | Composite Fertility Index (CFI) | Weighted avg of N, P, K, pH from SHC |
| Soil | Water Holding Capacity | Texture + organic carbon regression |
| Weather | Cumulative GDD | Sum of (Tmax+Tmin)/2 − base temp per crop |
| Weather | Drought Stress Index | Weighted SPI + NDVI deviation |
| Market | Price Volatility Score | Rolling 30-day CoV of eNAM prices |
| Market | Input-Output Price Ratio | (Input cost index) / (Commodity price index) |
| Risk | Financial Vulnerability Index | Landholding + credit + income diversity |
| Risk | Yield Gap Score | (Potential − actual) / potential yield |

### 11.3 AgriStack Sandbox → Production Path

All AgriStack integrations (Farmer, Land, Crop, Aggregated, Consent, Network Manager, Telemetry APIs) are developed and validated against the **AgriStack Sandbox** (synthesized, privacy-safe data) before production migration. The sandbox-testing checklist below is tracked as a pre-launch gate:

| # | Test Case | API Category |
|---|---|---|
| 1 | Authenticate and obtain access token | Network Manager / Token API |
| 2 | Fetch farmer demographic profile by Farmer ID | Farmer Data API |
| 3 | Retrieve geo-referenced land parcel map | Land Data API |
| 4 | Fetch season-specific crop data for a land record | Crop Data API |
| 5 | Get village-level aggregated crop survey data | Aggregated Data API |
| 6 | Create + grant + revoke a consent request (test Aadhaar) | Consent API |
| 7 | Monitor API telemetry and latency | Telemetry API |
| 8 | Simulate full Digital Twin creation pipeline end-to-end | — |
| 9 | Test rate-limit behavior at scale | Network Manager |

Production migration requires: public key + SSL certificates, expected daily volume, integration contact, data retention policy document, escalation contact — submitted via the AgriStack "Move to Production" workflow.

---

## 12. Security & Privacy

### 12.1 Principles

Privacy by design · Zero trust (every service authenticates every request) · Defense in depth · DPDP Act 2023 alignment.

### 12.2 Authentication Flow

```
Farmer App → Mobile OTP (Aadhaar-linked) → DigiLocker eKYC (optional)
  → JWT Access Token (15-min TTL) + Refresh Token (30-day TTL)
  → Kong API Gateway (validates every request) → Service-level RBAC
```

### 12.3 RBAC Roles

`farmer` (own twin, read/write) · `extension_officer` (assigned farmers + Human-in-Loop queue) · `fpo_admin` (anonymized cluster analytics) · `policy_analyst` (anonymized aggregates) · `system_admin` (config, no PII by default).

### 12.4 PII Minimization

Aadhaar number never stored (token reference only) · mobile number hashed (SHA-256 + salt) · GPS rounded to 100m · financial data encrypted, accessible only to Planning Agent.

### 12.5 Key Threats & Mitigations

| Threat | Mitigation |
|---|---|
| AI prompt injection via farmer input | Input sanitization + sandboxed LLM calls, Verifier gate on all agent output regardless of prompt content |
| Unauthorized farmer data access | RBAC + audit logs + column-level encryption |
| Model poisoning (adversarial images) | Input validation + confidence thresholding on Vision Agent |
| False-advisory liability | Verifier hard gates + confidence-based Human-in-Loop + disclaimer |

### 12.6 DPDP Act 2023 Compliance

Explicit granular consent at onboarding · purpose limitation to agricultural advisory · right to erasure (30 days) · data portability (JSON export) · data localization (ap-south-1/2 only) · breach notification to CERT-In within 6 hours.

*(Full permission matrix, consent-category table, and third-party data-sharing policy are maintained in `SECURITY.md` and incorporated here by reference — omitted from the main body for length.)*

---

## 13. Delivery Plan

### 13.1 Deployment Architecture

```
GitHub (main) → GitHub Actions (lint/test/build) → AWS ECR
   → ArgoCD → Kubernetes (EKS) with Istio service mesh
   → RDS PostgreSQL+PostGIS | ElastiCache Redis | Amazon MSK (Kafka) | Qdrant Cluster
```

Multi-region: ap-south-1 (Mumbai, primary) · ap-south-2 (Hyderabad, secondary) · ap-southeast-1 (Singapore, DR). All farmer PII stays in India per DPDP.

### 13.2 Team & Responsibilities (5-Member Team)

| Role | Hackathon Responsibility |
|---|---|
| Team Lead & AI Architect | Orchestrator/Planner design, ADK + Lyzr integration |
| Computer Vision Engineer | Vision Agent, NPSS dataset fine-tuning |
| Backend & Data Engineer | Kafka pipelines, Digital Twin engine, Qdrant collections |
| Full-Stack / UX Developer | Offline-first mobile app, voice UI, Human-in-Loop dashboard |
| Agricultural Domain Expert | Scheme knowledge base, verifier constraint rules, advisory validation |

### 13.3 Phased Roadmap

| Phase | Timeline | Milestones |
|---|---|---|
| Phase 0: Foundation | Month 1–2 | Sandbox integration, base digital twin, Qdrant collections live |
| Phase 1: Agent MVP | Month 3–4 | Planner + Vision + Verifier live end-to-end, NL interface (Hindi) |
| Phase 2: Full Stack | Month 5–6 | All agents live, Reflection + XAI layer, Human-in-Loop dashboard, 5-language support |
| Phase 3: Scale | Month 7–12 | 50K farmer onboarding, FPO integration, production AgriStack migration |
| Phase 4: Ecosystem | Year 2 | IoT sensor integration, B2B API for banks/insurers/input companies |

### 13.4 Monitoring Stack

Prometheus + Grafana + Loki for infra; per-agent latency, failure rate, and confidence-score distribution dashboards specifically (not just generic API metrics) — because in an agent system, *which agent* is degrading matters more than aggregate uptime.

### 13.5 Risks

| Risk | Mitigation |
|---|---|
| AI hallucination on crop/pesticide advice | Hard Verifier gates, never bypassable, even at high confidence |
| Low smartphone penetration | IVR voice interface + CSC kiosk offline mode |
| Farmer trust deficit | XAI explanation layer + Human-in-Loop transparency ("reviewed by extension officer" tag) |
| Regulatory/data privacy | DPDP compliance, consent management, India-only data residency |

---

## 14. Worked Example — One Query, End to End

*Farmer asks (voice, Marathi): "Should I switch from cotton to soybean this season?"*

1. **Intent Classifier** → `crop_plan_request`
2. **RootAgent** opens session, pulls twin snapshot for farmer `AGR_MH_001234`
3. **PlannerAgent** builds task graph: Geospatial + Market run in parallel → feed Planning Agent
4. **GeospatialAgent** returns current NDVI + water-stress flag for the parcel
5. **MarketAgent** returns cotton vs. soybean 30-day price trend + volatility score
6. **PlanningAgent** runs OR-Tools solver against water budget, soil CFI, scheme eligibility → ranks soybean above cotton on the Pareto frontier, with reasoning trace and financial projection
7. **MemoryAgent** retrieves 3 similar past decisions from `farmer_memory` (Qdrant) for context, does not yet write
8. **ReflectionAgent** checks the draft: is it in plain Marathi, does it name a specific next action, does it cite the water constraint the farmer cares about most this season → passes
9. **VerifierAgent** checks: recommended input cost within stated budget ✅, no active weather advisory suppressing recommendations ✅ → `PASS`
10. **ConfidenceScorer** → 0.84 → above threshold, skips Human-in-Loop
11. **XAI Explainer** renders: *"Because your soil's fertility index is moderate and water availability is 30% below last season, and soybean prices have been more stable than cotton over the last 30 days, we recommend soybean — you'd need less irrigation and the price is holding steadier."*
12. **NotificationAgent** delivers via voice callback in Marathi, and **MemoryAgent** writes the recommendation to the twin's `recommendations.active` list and appends the episode to `farmer_memory` in Qdrant.

Total task-graph time: ~6 seconds, well under the 20s budget, with a full audit trail retained for every step.

---

## Appendix: Source Documents

This PRD synthesizes and reframes four internal documents into an agent-first structure: `MASTER_PLAN.md` (vision, requirements, roadmap), `ARCHITECTURE.md` (tech stack, hardware, data model), `SECURITY.md` (DPDP compliance, threat model), and `SANDBOX_USAGE.md` (AgriStack sandbox integration). Full detail on any table condensed above is available in the respective source document.
