# 🏗️ SasyaAI — Architecture (Derived from `.gitignore`)

> Every section in the [.gitignore](./.gitignore) maps to a logical layer in the architecture below.

---

## 1. High-Level System Topology

```mermaid
graph TB
    subgraph PRESENTATION["🌐 Presentation Layer"]
        WEB["React.js Web Dashboard<br/>(Admin / Policy)"]
        MOBILE["React Native + Expo<br/>(Farmer Mobile App)"]
        IVR["Twilio IVR / USSD<br/>(Voice + Feature Phone)"]
        PWA["Next.js PWA<br/>(Low-bandwidth Fallback)"]
    end

    subgraph GATEWAY["🔐 API Gateway Layer"]
        KONG["Kong Gateway<br/>JWT + Aadhaar OTP + Rate Limit"]
    end

    subgraph ORCHESTRATION["🧠 Orchestration Layer"]
        ORCH["Orchestrator Agent<br/>(Gemini 1.5 Pro / GPT-4o)<br/>Task Decomposition + Routing"]
        PLAN["Planning Agent<br/>FastAPI + Celery<br/>Crop Optimization + Finance"]
        VISION["Vision Agent<br/>FastAPI + GPU<br/>YOLOv8 + EfficientNet"]
        GEO["Geospatial Agent<br/>FastAPI + PostGIS<br/>NDVI + Soil + KrishiDSS"]
        MON["Monitoring Agent<br/>Celery + Kafka<br/>Constraint Validation"]
    end

    subgraph DATA["🗄️ Data Layer"]
        PG["PostgreSQL 15<br/>+ PostGIS + pgvector"]
        MONGO["MongoDB Atlas<br/>(Document Store)"]
        REDIS["Redis 7.2<br/>(Cache + Queue)"]
        KAFKA["Apache Kafka<br/>(Event Streaming)"]
        S3["S3 / Azure Blob<br/>(Data Lake)"]
        ES["Elasticsearch<br/>(Search)"]
    end

    subgraph EXTERNAL["🌍 External Data Sources"]
        AGRI["AgriStack API"]
        IMD["IMD Weather"]
        ENAM["eNAM Prices"]
        ISRO["ISRO Bhuvan"]
        KRISHI["KrishiDSS"]
        NPSS["NPSS Dataset"]
        GICEN["GICEN Catalog"]
    end

    WEB & MOBILE & IVR & PWA --> KONG
    KONG --> ORCH
    ORCH --> PLAN & VISION & GEO & MON
    PLAN & VISION & GEO & MON --> PG & MONGO & REDIS & KAFKA & S3 & ES
    PG & KAFKA & S3 --> AGRI & IMD & ENAM & ISRO & KRISHI & NPSS & GICEN

    style PRESENTATION fill:#1a1a2e,stroke:#e94560,color:#fff
    style GATEWAY fill:#16213e,stroke:#0f3460,color:#fff
    style ORCHESTRATION fill:#0f3460,stroke:#533483,color:#fff
    style DATA fill:#533483,stroke:#e94560,color:#fff
    style EXTERNAL fill:#2d4059,stroke:#ea5455,color:#fff
```

---

## 2. Project Directory Tree (from `.gitignore`)

The `.gitignore` implicitly defines the full project structure:

```
SasyaAI/
│
├── 📄 .gitignore                  ← Architecture map
├── 📄 README.md                   ← Project overview
├── 📄 AgriTwin_AI_Proposal.docx   ← Hackathon proposal
│
├── 📁 Docs/                       ← Design documentation (git-ignored)
│   ├── ARCHITECTURE.md
│   ├── TECH_STACK.md
│   ├── MASTER_PLAN.md
│   ├── REQUIREMENTS.md
│   ├── DEPLOYMENT.md
│   ├── SECURITY.md
│   ├── PERMISSIONS.md
│   ├── HOW_TO_USE.md
│   └── AI_IDE_SETUP.md
│
├── 📁 services/                   ← Backend microservices (Python/FastAPI)
│   ├── orchestrator/              ← LLM core — task decomposition + routing
│   ├── planning_agent/            ← Crop/finance constraint optimization
│   ├── vision_agent/              ← YOLOv8 pest/disease detection (GPU)
│   ├── geospatial_agent/          ← PostGIS + GDAL spatial analysis
│   ├── monitoring_agent/          ← Kafka consumer + constraint validator
│   └── shared/                    ← Common schemas, utils, configs
│
├── 📁 models/                     ← ML model artifacts (git-ignored)
│   ├── yolov8_npss/               ← Fine-tuned YOLOv8 weights
│   ├── efficientnet_b4/           ← Disease severity grading
│   ├── lstm_yield/                ← Time-series yield forecasting
│   ├── tft_weather/               ← Temporal Fusion Transformer
│   ├── xgboost_scheme/            ← Scheme eligibility scoring
│   ├── whisper_indic/             ← Multilingual ASR (10+ languages)
│   ├── coqui_tts/                 ← Text-to-speech for IVR
│   ├── embeddings/                ← sentence-transformers + FAISS
│   └── llm_gguf/                  ← Quantized Llama 3.2 for edge
│
├── 📁 data/                       ← All datasets (git-ignored)
│   ├── raw/
│   │   ├── agristack/             ← Farmer registry + land records
│   │   ├── soil_health/           ← 230M+ Soil Health Cards
│   │   ├── npss_images/           ← ~50K labeled pest images
│   │   ├── weather_imd/           ← IMD NetCDF/CSV archives
│   │   ├── enam_prices/           ← Market price snapshots
│   │   ├── satellite/             ← Sentinel-2 / ResourceSat GeoTIFFs
│   │   └── gicen/                 ← Telangana shapefiles, soil moisture
│   ├── processed/                 ← Feature-engineered datasets
│   ├── embeddings/                ← FAISS vector indices
│   └── cache/                     ← Redis dumps, temp processing
│
├── 📁 frontend/                   ← Client applications
│   ├── web/                       ← React.js + Tailwind (admin dashboard)
│   ├── mobile/                    ← React Native + Expo (farmer app)
│   └── ivr/                       ← Twilio VXML voice configs
│
├── 📁 infra/                      ← Infrastructure as Code
│   ├── docker/                    ← Dockerfiles per service
│   ├── helm/sasyaai/              ← Helm charts (prod + staging values)
│   ├── terraform/                 ← AWS/Azure IaC (EKS, RDS, MSK)
│   ├── k8s/                       ← Raw K8s manifests
│   └── monitoring/                ← Prometheus rules, Grafana dashboards
│
├── 📁 tests/                      ← Testing pyramid
│   ├── unit/                      ← Per-service unit tests
│   ├── integration/               ← Cross-service API tests
│   ├── e2e/                       ← Cypress / Playwright
│   └── fixtures/                  ← Mock data (farmer profiles, images)
│
├── 📁 notebooks/                  ← Jupyter experiments
│   ├── eda/                       ← Exploratory data analysis
│   ├── model_training/            ← Training experiments
│   └── prototyping/               ← Agent behavior prototyping
│
└── 📁 secrets/                    ← Credentials (git-ignored, Vault-managed)
```

---

## 3. Multi-Agent Data Flow

```mermaid
sequenceDiagram
    participant F as 👨‍🌾 Farmer
    participant GW as Kong Gateway
    participant O as Orchestrator
    participant P as Planning Agent
    participant V as Vision Agent
    participant G as Geospatial Agent
    participant M as Monitoring Agent
    participant DB as PostgreSQL + PostGIS
    participant K as Kafka
    participant EXT as External APIs

    F->>GW: Query (text/voice/image)
    GW->>GW: JWT + Aadhaar OTP Auth
    GW->>O: Authenticated request

    O->>O: Task decomposition
    O->>DB: Load Farmer Digital Twin

    par Agent Dispatch
        O->>P: Crop/finance task
        P->>DB: Soil + Crop history
        P->>EXT: eNAM prices, PM-KISAN
        P-->>O: Ranked crop plan + projections

        O->>V: Image analysis task
        V->>V: YOLOv8 inference (GPU)
        V-->>O: Pest ID + severity + treatment

        O->>G: Spatial analysis task
        G->>DB: PostGIS spatial queries
        G->>EXT: ISRO Bhuvan + KrishiDSS
        G-->>O: NDVI map + water stress zones
    end

    O->>M: Validate all outputs
    M->>M: Constraint checks (water, scheme, risk)

    alt ✅ Validation Passed
        M->>K: Publish recommendation event
        M-->>O: Approved output
        O->>F: Explainable recommendation (NL)
    else ❌ Validation Failed
        M-->>O: Re-planning trigger
        O->>P: Adjust constraints & retry
    end

    K->>DB: Update Digital Twin
```

---

## 4. Deployment Pipeline

```mermaid
flowchart LR
    subgraph DEV["💻 Developer"]
        CODE["Code Push"]
    end

    subgraph CI["⚙️ CI/CD"]
        GHA["GitHub Actions"]
        LINT["Lint + Test"]
        BUILD["Docker Build"]
        ECR["Push to ECR"]
    end

    subgraph CD["🚀 GitOps"]
        ARGO["ArgoCD"]
        HELM["Helm Upgrade"]
    end

    subgraph K8S["☸️ Kubernetes (EKS/AKS)"]
        direction TB
        ING["NGINX Ingress"]
        ISTIO["Istio Service Mesh"]
        PODS["Microservice Pods"]
        GPU["GPU Nodes (Vision)"]
    end

    subgraph MANAGED["☁️ Managed Services"]
        RDS["RDS PostgreSQL"]
        ELAST["ElastiCache Redis"]
        MSK["Amazon MSK Kafka"]
        BLOB["S3 Data Lake"]
    end

    subgraph OBS["📊 Observability"]
        PROM["Prometheus"]
        GRAF["Grafana"]
        JAEG["Jaeger Tracing"]
        OTEL["OpenTelemetry"]
    end

    CODE --> GHA --> LINT --> BUILD --> ECR
    ECR --> ARGO --> HELM
    HELM --> K8S
    K8S --> MANAGED
    K8S --> OBS

    style DEV fill:#1a1a2e,stroke:#e94560,color:#fff
    style CI fill:#16213e,stroke:#0f3460,color:#fff
    style CD fill:#0f3460,stroke:#533483,color:#fff
    style K8S fill:#533483,stroke:#e94560,color:#fff
    style MANAGED fill:#2d4059,stroke:#ea5455,color:#fff
    style OBS fill:#1b1b2f,stroke:#e94560,color:#fff
```

---

## 5. Digital Twin Data Model

```mermaid
classDiagram
    class FarmerTwin {
        +String farmerId
        +Boolean aadhaarLinked
        +GeoPoint location
        +Parcel[] landParcels
    }

    class AgronomyProfile {
        +SHC[] soilHealthCards
        +Season[] cropHistory
        +Enum irrigationSource
        +Item[] farmEquipment
    }

    class FinancialProfile {
        +Scheme[] schemeEligibility
        +Float creditScore
        +String[] marketLinkages
    }

    class EnvironmentalState {
        +Float[] ndviTimeSeries
        +WeatherObject currentWeather
        +Float soilMoisture
        +Float pestRiskScore
    }

    class Recommendation {
        +String type
        +Float confidence
        +String reasoningGraphId
        +String[] constraintsApplied
        +Enum verificationStatus
    }

    FarmerTwin --> AgronomyProfile
    FarmerTwin --> FinancialProfile
    FarmerTwin --> EnvironmentalState
    FarmerTwin --> "0..*" Recommendation
```

---

## 6. `.gitignore` ↔ Architecture Layer Mapping

| `.gitignore` Section | Architecture Layer | Key Technologies |
|---|---|---|
| `Docs/` | Documentation | ARCHITECTURE, TECH_STACK, MASTER_PLAN, REQUIREMENTS |
| `__pycache__/`, `*.py[cod]`, `venv/` | Backend Services | Python 3.11, FastAPI, Celery |
| `*.pt`, `*.onnx`, `models/` | AI/ML Models | YOLOv8, EfficientNet, LSTM, XGBoost, Whisper, FAISS |
| `data/`, `*.csv`, `*.geojson`, `*.tif` | Data Lake + Spatial | AgriStack, SHC, NPSS, IMD, GICEN, Satellite |
| `node_modules/`, `.next/`, `.expo/` | Frontend / Clients | React.js, React Native, Next.js, Twilio IVR |
| `*.tfstate`, `.terraform/` | Infrastructure | Terraform, Docker, Helm, Kubernetes |
| `*.pem`, `*.key`, `secrets/` | Security / Secrets | HashiCorp Vault, JWT, Aadhaar e-KYC |
| `.pytest_cache/`, `coverage/` | Testing | pytest, Cypress, Playwright |
| `.ipynb_checkpoints/` | Experimentation | Jupyter notebooks, EDA, model training |
| `.vscode/`, `.idea/` | Developer Tooling | IDE configs |
| `.DS_Store`, `Thumbs.db` | OS Artifacts | macOS / Windows system files |
