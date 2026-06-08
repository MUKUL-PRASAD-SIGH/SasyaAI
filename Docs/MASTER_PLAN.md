# 🧠 MASTER PLAN — SasyaAI

---

## 1. Vision

**"Every Indian farmer deserves a personal agricultural scientist in their pocket — one that knows their land, their history, their constraints, and their aspirations."**

SasyaAI is not merely an advisory chatbot. It is a living, breathing digital representation of a farmer's entire agricultural reality — a twin that thinks, learns, and acts on their behalf.

---

## 2. Core Innovation Pillars

### 2.1 Dynamic Digital Twin Architecture
Each farmer gets a continuously updated profile comprising:
- **Identity Layer**: Aadhaar-linked AgriStack ID, land parcel data, family size
- **Agronomy Layer**: Historical crop choices, yields, input usage, soil test results
- **Financial Layer**: Credit history, scheme eligibility, market access
- **Environmental Layer**: Real-time weather, satellite NDVI, water table depth
- **Risk Layer**: Pest probability scores, climate stress index, price volatility

The twin is updated via event streams (weather APIs, market feeds, field sensor data) and agent outputs.

### 2.2 Multi-Agent Reasoning Pipeline

```
┌─────────────────────────────────────────────────────┐
│                  ORCHESTRATOR AGENT                  │
│  (Task decomposition, agent routing, context mgmt)  │
└──────────┬──────────────┬──────────────┬────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────────┐
    │  PLANNING   │ │   VISION   │ │  GEOSPATIAL   │
    │    AGENT    │ │   AGENT    │ │     AGENT     │
    │             │ │            │ │               │
    │ • Crop opt  │ │ • NPSS img │ │ • Soil map    │
    │ • Finance   │ │ • YOLOv8   │ │ • Water risk  │
    │ • Schemes   │ │ • Disease  │ │ • KrishiDSS   │
    │ • Timeline  │ │   grading  │ │ • Micro-clim  │
    └──────┬──────┘ └─────┬──────┘ └────┬──────────┘
           └──────────────┼─────────────┘
                          │
              ┌───────────▼───────────┐
              │   MONITORING AGENT    │
              │  (Verification Loop)  │
              │                       │
              │ • Constraint checks   │
              │ • Eligibility gates   │
              │ • Drift detection     │
              │ • Alert generation    │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │    XAI EXPLAINER      │
              │                       │
              │ • Reasoning graphs    │
              │ • Confidence scores   │
              │ • Plain language NL   │
              └───────────────────────┘
```

#### Planning Agent
- Uses **Constraint-Aware Optimization** (Integer Programming + LLM guidance)
- Inputs: soil health, budget, water availability, market prices, scheme eligibility
- Outputs: ranked crop plan, input schedule, financial projections, risk-adjusted ROI
- Novel approach: **Pareto-optimal frontier** across yield, profit, and ecological sustainability

#### Vision Agent
- Fine-tuned **YOLOv8** on NPSS pest/disease image dataset
- **Few-shot learning** for rare or emerging pest species
- Mobile-first: runs inference on-device (quantized model) for offline operation
- Output: pest identification, severity grading (0–5), treatment protocol, spray schedule

#### Geospatial Agent
- Integrates **KrishiDSS** district-level crop advisory with satellite-derived indices
- **NDVI time series** analysis for canopy health monitoring
- Groundwater depth modeling using CGWB data + ML regression
- Generates **microclimatic risk zones** at sub-district level

#### Monitoring & Verification Agent
- Runs continuous checks: scheme eligibility, subsidy caps, weather-based replanning
- **Constraint satisfaction engine**: flags AI outputs violating farm-level feasibility
- Generates alerts: frost risk, excess rainfall, price crash, scheme deadline
- Maintains **audit log** of all recommendations and validations

### 2.3 Explainable AI Layer
- Builds **Structured Reasoning Graphs** (directed acyclic graphs of decision logic)
- Each recommendation links back to supporting data evidence
- Visualized as a simple "because X → therefore Y" chain for farmers
- Policy dashboard shows aggregate reasoning patterns for policymakers

### 2.4 Natural Language Interface
- Supports 10+ Indian languages (Hindi, Tamil, Telugu, Marathi, Bengali, etc.)
- Voice-first for low-literacy users (Whisper ASR + TTS)
- Contextual conversation memory: remembers prior queries within a session
- Escalation path: routes complex queries to human agri-expert KAMs

---

## 3. Creative Differentiators

| Feature | Description |
|---|---|
| 🎯 **Farmer Persona Clustering** | Unsupervised ML clusters farmers into personas (e.g., "Risk-Averse Smallholder"). Advisory tone and risk appetite calibrated per persona. |
| 🌍 **Peer Benchmarking** | Anonymous comparison vs. similar farms in same agro-climatic zone. |
| 📊 **What-If Simulator** | Interactive: "What if I switch from rice to millets?" Shows projected yield, income, water savings, carbon footprint. |
| 🌱 **Carbon Credit Advisory** | Calculates potential carbon credits from sustainable practices; connects to carbon markets. |
| 🤝 **FPO Collective Intelligence** | Aggregates anonymized insights across FPOs for coordinated advisory and bulk pricing. |
| 📡 **IoT Integration Readiness** | Architecture supports plug-in sensors; live telemetry replaces modeled estimates. |
| 🏆 **Gamified Adoption** | Achievement system: "Soil Champion", "Water Saver" — builds engagement. |

---

## 4. Requirements

### 4.1 Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| FR-001 | Digital Twin | Create and maintain unique digital twin per farmer, keyed to AgriStack ID |
| FR-002 | Digital Twin | Update twin within 15 minutes of any triggering event |
| FR-003 | Digital Twin | Retain 5 years of crop history and 12-month advisory history |
| FR-010 | Planning | Generate crop recommendations considering soil, water, market, schemes |
| FR-011 | Planning | Produce input schedules with cost estimates |
| FR-012 | Planning | Output financial projections per recommendation |
| FR-020 | Vision | Accept image uploads from mobile app |
| FR-021 | Vision | Identify pest/disease with >85% accuracy on NPSS validation set |
| FR-022 | Vision | Provide severity grading (0–5) and affected area estimate |
| FR-023 | Vision | Generate treatment protocol with CIB-approved inputs |
| FR-030 | Geospatial | Visualize farm boundaries on interactive map |
| FR-031 | Geospatial | Display NDVI layer with field-level health interpretation |
| FR-032 | Geospatial | Flag water stress zones and recommend irrigation adjustments |
| FR-040 | Monitoring | Run constraint validation on 100% of agent outputs |
| FR-041 | Monitoring | Send proactive alerts for frost, rain, price drops, scheme deadlines |
| FR-050 | Interface | Support text and voice input in 10+ Indian languages |
| FR-051 | Interface | Explain each recommendation with reasoning chain |

### 4.2 Non-Functional Requirements

| Requirement | Target |
|---|---|
| API Response Time (P95) | < 2 seconds |
| Vision Inference Latency | < 5 seconds on mobile |
| System Availability | 99.5% uptime |
| Concurrent Users | 10,000 simultaneous |
| Data Freshness | Weather: 15 min · Market: 30 min · Satellite: 48 hr |
| Offline Capability | Core advisory functional without internet |
| Language Support | 10+ Indian languages + English |

### 4.3 Datasets

| Dataset | Source | Format | Volume |
|---|---|---|---|
| Farmer Registry | AgriStack API | JSON/REST | ~100M records |
| Soil Health Cards | Department of Agriculture | CSV + API | ~230M cards |
| Land Records (DILRMP) | MoRD / State portals | GeoJSON | Parcel-level |
| NPSS Pest Images | DPPQ&S | JPEG (labeled) | ~50K images |
| KrishiDSS Advisory | ICAR | XML/API | District-level |
| GICEN Geospatial | GICEN / INDIAAI | Shapefiles/GeoJSON/CSV | Multi-layer |
| IMD Weather | IMD Open Data Portal | NetCDF/CSV | Grid + station |
| eNAM Market Prices | eNAM API | JSON | Daily, 1000+ mandis |
| Satellite Imagery | ISRO Bhuvan / Copernicus | GeoTIFF | Bi-weekly |

### 4.4 Derived Features

| Category | Feature | Derivation |
|---|---|---|
| Soil | Composite Fertility Index (CFI) | Weighted avg of N, P, K, pH from SHC |
| Soil | Water Holding Capacity | Texture + organic carbon regression |
| Weather | Cumulative GDD | Sum of (Tmax+Tmin)/2 - base temp per crop |
| Weather | Drought Stress Index | Weighted SPI + NDVI deviation |
| Market | Price Volatility Score | Rolling 30-day CoV of eNAM prices |
| Market | Input-Output Price Ratio | (Input cost index) / (Commodity price index) |
| Risk | Financial Vulnerability Index | Landholding + credit + income diversity |
| Risk | Yield Gap Score | (Potential - actual) / potential yield |

---

## 5. Team Roles & Execution Readiness (5-Member Team)

```text
                    ┌─────────────────────────────────┐
                    │      TEAM LEAD & AI ARCHITECT    │
                    │   Orchestrator + Multi-Agent     │
                    └────────────────┬─────────────────┘
                                     │
         ┌───────────────────┬───────┴───────┬───────────────────┐
         │                   │               │                   │
┌────────▼────────┐ ┌────────▼───────┐ ┌─────▼────────┐ ┌────────▼────────┐
│ COMPUTER VISION │ │ BACKEND & DATA │ │  FULL-STACK  │ │   AGRICULTURAL  │
│    ENGINEER     │ │    ENGINEER    │ │ UX DEVELOPER │ │  DOMAIN EXPERT  │
└─────────────────┘ └────────────────┘ └──────────────┘ └─────────────────┘
```

### Team Capability Map

| Role | Expertise | Hackathon Responsibility |
|---|---|---|
| **Team Lead & AI Architect** | ML/LLM systems, 5 yrs agri-tech | Orchestrator design, multi-agent integration. |
| **Computer Vision Engineer** | YOLOv8, PyTorch, image datasets | Vision agent, NPSS dataset processing. |
| **Backend & Data Engineer** | FastAPI, Kafka, PostGIS, GIS | Kafka pipelines, Digital Twin engine. |
| **Full-Stack / UX Developer** | React Native, UI/UX | Offline-first architecture, Voice UI. |
| **Agricultural Domain Expert** | Agricultural science, KVK | Scheme knowledge, advisory validation. |

### Compliance & Readiness Note

> 📋 **MoAFW Terms Compliance**:
> - **Institution/Company NOCs**: All required No Objection Certificates have been secured.
> - **Commitment**: The team is fully committed to the 6-month Proof of Concept (PoC) deployment and maintenance phase following the hackathon.

### Git Branching Strategy

```text
main ← master ← feat/orchestrator (Lead)
                ← feat/vision-agent (CV Eng)
                ← feat/digital-twin (Data Eng)
                ← feat/mobile-app (UX Dev)
                ← docs/domain-rules (Domain Expert)
```

All changes via PR with 1 reviewer. Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`.

---

## 6. Phased Execution Roadmap

| Phase | Timeline | Milestones |
|---|---|---|
| Phase 0: Foundation | Div 1-2 | Data pipelines, AgriStack integration, base digital twin |
| Phase 1: Agent MVP | Div 3-4 | Planning + Vision agent live, NL interface (Hindi) |
| Phase 2: Full Stack | Div 5-6 | All 4 agents, XAI layer, 5 language support |
| Phase 3: Scale | Div 7-12 | 50K farmer onboarding, FPO integration, carbon module |
| Phase 4: Ecosystem | Div 12+ | IoT network, B2B API for banks/insurers/input cos |

---

## 7. Success Metrics

| Metric | Target (Year 1) |
|---|---|
| Farmers onboarded | 50,000 |
| Average yield improvement | 15–20% |
| Input cost reduction | 10–15% |
| Scheme adoption uplift | 30% increase |
| Pest damage reduction | 25% |
| NPS (farmer satisfaction) | > 60 |

---

## 8. Risk & Mitigation

| Risk | Mitigation |
|---|---|
| Low smartphone penetration | IVR voice interface + CSC kiosk mode |
| Data quality from AgriStack | Validation pipelines + crowdsourced correction |
| AI hallucination on crop advice | Hard constraint gates in Monitoring Agent |
| Farmer trust deficit | Explainability layer + peer testimonials |
| Regulatory/data privacy | DPDP Act compliance, consent management |
