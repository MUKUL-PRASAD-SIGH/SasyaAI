# 🏗️ ARCHITECTURE — SasyaAI

> Complete technical blueprint: system design, tech stack, and hardware specifications.

---

## 1. High-Level Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║                        PRESENTATION LAYER                        ║
║  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  ║
║  │ Mobile App  │  │  Web Portal  │  │  IVR / Voice (USSD)   │  ║
║  │ (React Nat) │  │  (React.js)  │  │  (Vernacular + ASR)   │  ║
║  └──────┬──────┘  └──────┬───────┘  └───────────┬───────────┘  ║
╚═════════╪════════════════╪═══════════════════════╪══════════════╝
          │                │                       │
          └────────────────▼───────────────────────┘
                           │ HTTPS / WebSocket
╔══════════════════════════▼═══════════════════════════════════════╗
║                        API GATEWAY LAYER                         ║
║  ┌──────────────────────────────────────────────────────────┐   ║
║  │  Kong API Gateway | Auth (JWT + Aadhaar OTP) | Rate Limit│   ║
║  └────────────────────────────┬─────────────────────────────┘   ║
╚═══════════════════════════════╪══════════════════════════════════╝
                                │
╔═══════════════════════════════▼══════════════════════════════════╗
║                     ORCHESTRATION LAYER                          ║
║  ┌────────────────────────────────────────────────────────┐     ║
║  │              ORCHESTRATOR AGENT (LLM Core)             │     ║
║  │   Task Decomposition | Agent Routing | Context Manager  │     ║
║  └────┬──────────────┬──────────────┬────────────────┬────┘     ║
║       │              │              │                │           ║
║  ┌────▼───┐    ┌─────▼────┐   ┌────▼────┐    ┌─────▼─────┐    ║
║  │PLANNING│    │  VISION  │   │  GEO-   │    │MONITORING │    ║
║  │ AGENT  │    │  AGENT   │   │SPATIAL  │    │  AGENT    │    ║
║  │        │    │          │   │ AGENT   │    │           │    ║
║  │FastAPI │    │ FastAPI  │   │FastAPI  │    │ Celery +  │    ║
║  │+ Celery│    │ + GPU    │   │+PostGIS │    │ Kafka     │    ║
║  └────┬───┘    └─────┬────┘   └────┬────┘    └─────┬─────┘    ║
╚═══════╪══════════════╪═════════════╪════════════════╪══════════╝
        │              │             │                │
╔═══════▼══════════════▼═════════════▼════════════════▼══════════╗
║                        DATA LAYER                                ║
║  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐║
║  │PostgreSQL│ │ MongoDB  │ │  Redis   │ │  Apache Kafka      │║
║  │+PostGIS  │ │(doc store│ │ (cache + │ │  (event streaming) │║
║  │(spatial) │ │+vectors) │ │  queue)  │ │                    │║
║  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘║
║  ┌──────────────────────────────────────────────────────────┐  ║
║  │                   DATA LAKE (S3 / Azure Blob)            │  ║
║  │  Satellite imagery | NPSS images | Weather archives      │  ║
║  └──────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════╝
        │                                        │
╔═══════▼════════════════════════════════════════▼════════════════╗
║                    EXTERNAL DATA SOURCES                         ║
║  AgriStack API | NPSS | KrishiDSS | IMD | eNAM | CGWB | ISRO   ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 2. Digital Twin Data Model

```
FarmerTwin {
  identity: {
    farmerId: String        // AgriStack unique ID
    aadhaarLinked: Boolean
    location: GeoPoint      // Village centroid
    landParcels: [Parcel]   // Bhuvan/DILRMP linked
  }
  agronomyProfile: {
    soilHealthCards: [SHC]  // Historical + latest
    cropHistory: [Season]   // 5-year rolling
    irrigationSource: Enum  // Canal/borewell/rain-fed
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
    pestRiskScore: Float     // 0-1, updated daily
  }
  recommendations: {
    active: [Recommendation]
    history: [Recommendation]
    verificationStatus: Enum
  }
}
```

---

## 3. Agent Communication Protocol

Agents communicate via **structured JSON messages** on Kafka topics:

```json
{
  "message_id": "uuid",
  "source_agent": "planning_agent",
  "target_agent": "monitoring_agent",
  "farmer_id": "AGR_MH_001234",
  "payload_type": "crop_recommendation",
  "payload": {
    "recommended_crop": "Soybean",
    "confidence": 0.87,
    "reasoning_graph_id": "rg_001234",
    "constraints_applied": ["water_budget", "scheme_pm_fasal_bima"],
    "timestamp": "2025-06-01T10:30:00Z"
  },
  "requires_verification": true
}
```

---

## 4. Verification & Monitoring Loop

```
     ┌─────────────────────────────────────┐
     │         AGENT OUTPUT                 │
     └─────────────────┬───────────────────┘
                       │
              ┌────────▼────────┐
              │  CONSTRAINT     │
              │  VALIDATOR      │
              │  • Water budget │
              │  • Scheme rules │
              │  • Risk limits  │
              └────────┬────────┘
                       │
           ┌───────────┴───────────┐
           │                       │
     ✅ PASS                  ❌ FAIL
           │                       │
    ┌──────▼──────┐        ┌───────▼───────┐
    │  DELIVERY   │        │  RE-PLANNING  │
    │  ENGINE     │        │  TRIGGER      │
    │  NL render  │        │  Adjust params│
    │  Push notify│        │  Re-run agent │
    └─────────────┘        └───────────────┘
```

---

## 5. Geospatial Pipeline

```
Raw Satellite (Sentinel-2/ResourceSat) → ISRO Bhuvan GeoServer
    → Preprocessing (atmospheric correction, cloud masking, band compositing)
    → Feature Extraction (NDVI, NDWI, LSWI, EVI)
    → KrishiDSS Layer (soil texture, drainage class, AWC)
    → Geospatial Agent (PostGIS + GDAL)
```

---

## 6. Vision Agent Pipeline

```
Farmer Photo / Drone Capture
    → Image Validation (quality + size)
    → YOLOv8 Inference (NPSS fine-tuned) + Few-shot CNN
    → Severity Grading (0-5 scale + spread prediction)
    → Treatment Engine (approved input DB, dosage calc, cost estimate)
```

---

## 7. Tech Stack

### AI / Machine Learning

| Component | Technology | Purpose |
|---|---|---|
| Orchestrator LLM | Gemini 1.5 Pro / GPT-4o | NLU, agent orchestration, XAI |
| Local/Edge LLM | Llama 3.2 (quantized, GGUF) | Offline advisory inference |
| Computer Vision | YOLOv8 (Ultralytics) | Pest/disease object detection |
| Image Classification | EfficientNet-B4 | Crop disease severity grading |
| Time Series | LSTM + Temporal Fusion Transformer | Yield prediction, weather modeling |
| Tabular ML | XGBoost + LightGBM | Scheme eligibility, soil prediction |
| NLP/ASR | OpenAI Whisper (multilingual) | Voice-to-text in 10+ languages |
| TTS | Coqui TTS / Azure Speech | Text-to-speech for IVR |
| RAG | sentence-transformers + FAISS | Crop knowledge retrieval |
| Optimization | Google OR-Tools | Constraint-aware crop planning |
| Explainability | SHAP + reasoning graph engine | Transparent decisions |

### Backend

| Component | Technology |
|---|---|
| API Framework | FastAPI (Python 3.11) |
| Task Queue | Celery + Redis |
| Event Streaming | Apache Kafka |
| Service Mesh | Istio |
| API Gateway | Kong Gateway |
| Auth | OAuth2 + JWT + Aadhaar e-KYC |
| Search | Elasticsearch |

### Databases

| Database | Use Case | Technology |
|---|---|---|
| Primary Store | Farmer digital twin, recommendations | PostgreSQL 15 + PostGIS 3.3 |
| Document Store | Unstructured advisory, logs | MongoDB Atlas |
| Cache | Session state, hot profiles | Redis 7.2 |
| Vector DB | RAG embeddings | Pgvector (PostgreSQL extension) |
| Data Lake | Satellite imagery, archives | AWS S3 / Azure Blob |
| Data Warehouse | Analytics, A/B testing | Apache Parquet + DuckDB |

### Frontend / Client

| Platform | Technology |
|---|---|
| Mobile (farmer) | React Native + Expo (iOS + Android, offline) |
| Web Dashboard (admin) | React.js + Tailwind CSS + Recharts |
| IVR | Twilio Voice + VXML |
| PWA (fallback) | Next.js |
| Mapping | MapLibre GL JS + Deck.gl |
| GIS Analysis | GDAL / Rasterio / GeoPandas |

### Infrastructure & DevOps

| Component | Technology |
|---|---|
| Containers | Docker 24 + Docker Compose |
| Orchestration | Kubernetes 1.29 (EKS / AKS) |
| CI/CD | GitHub Actions + ArgoCD |
| Auto-scaling | Kubernetes HPA + KEDA |
| Monitoring | Prometheus + Grafana + Loki |
| Tracing | OpenTelemetry + Jaeger |
| Secrets | HashiCorp Vault |
| CDN | Cloudflare + AWS CloudFront |
| IaC | Terraform + Helm charts |

### External APIs & Data Feeds

| Service | Integration |
|---|---|
| AgriStack | REST APIs via MeitY gateway |
| AgriStack Sandbox | Anonymized datasets for testing |
| GICEN | Telangana/Karnataka geospatial datasets |
| IMD Weather | Open Data Portal + MOSDAC APIs |
| eNAM | Market price feeds |
| KrishiDSS | ICAR advisory API |
| NPSS | DPPQ&S image dataset |
| CGWB | Groundwater WMS/API |
| PM-KISAN | DBT Bharat eligibility API |
| ISRO | Bhuvan GeoServer WCS/WMS |
| DigiLocker | API v2 for Aadhaar/land verification |

---

## 8. Hardware Specifications

### Development Setup

| Role | Machine | Spec |
|---|---|---|
| Team Lead | MacBook Pro M3 / WSL2 | 16GB RAM, 512GB SSD |
| AI/ML Engineer | Ubuntu 22.04 | 32GB RAM, 1TB SSD, NVIDIA RTX 4070+ |
| Backend Engineer | MacBook Pro M3 / Ubuntu | 16GB RAM, 512GB SSD |
| Frontend Engineer | MacBook Pro M3 / Windows | 16GB RAM, 512GB SSD |

### GPU Training Resources (Cloud)

| Provider | GPU | VRAM | Cost/hr | Use Case |
|---|---|---|---|---|
| Colab Pro+ | NVIDIA A100 | 40GB | ~$0.50 | YOLOv8 fine-tuning |
| RunPod | NVIDIA A100 | 40GB | $1.64 | Extended training |
| AWS g4dn.xlarge | NVIDIA T4 | 16GB | $0.53 | Inference testing |

### Model Training Requirements

| Model | Min VRAM | Training Time |
|---|---|---|
| YOLOv8-m (NPSS, ~50K images) | 8GB | 4–8 hours |
| EfficientNet-B4 (severity) | 6GB | 2–4 hours |
| LSTM yield prediction | 4GB | 1–2 hours |
| XGBoost/LightGBM (tabular) | CPU only | < 30 min |
| Whisper (multilingual ASR) | 8GB | 6–12 hours |

### Docker Compose Requirements (Local Dev)

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores | 8 cores |
| RAM | 8GB | 16GB |
| Disk | 50GB free | 100GB free |

### Production Infrastructure

| Component | Instance | Count | Spec |
|---|---|---|---|
| API Servers | c5.2xlarge | 4 | 8 vCPU, 16GB RAM |
| GPU Nodes | g4dn.xlarge | 2 | NVIDIA T4 16GB |
| PostgreSQL | r5.xlarge (Multi-AZ) | 2 | 32GB RAM, 500GB SSD |
| Redis | r6g.xlarge | 2 | 26GB RAM |
| Kafka | MSK 3-broker | 3 | kafka.m5.large |
| S3 Data Lake | Standard + IA | — | 5TB initial |

### Edge / Rural Hardware

| Component | Spec | Purpose |
|---|---|---|
| CSC Tablet | Samsung Tab A9+ (8GB) | Farmer-facing kiosk |
| Edge Computer | Raspberry Pi 5 (8GB) | Offline model inference |
| Connectivity | 4G USB dongle | Sync-on-connect |
| Power | UPS (600VA) | Uninterrupted operation |

### Production Cost Estimate

| Item | Monthly Cost |
|---|---|
| EKS Cluster | $800 |
| GPU Nodes | $600 |
| RDS PostgreSQL | $400 |
| Redis + MongoDB | $500 |
| Kafka (MSK) | $300 |
| S3 + CDN + Networking | $350 |
| Monitoring + Misc | $250 |
| **Total** | **~$3,200/month** |

*At 50K farmers: ~$0.064/farmer/month*

---

## 9. Scalability Design

| Concern | Solution |
|---|---|
| Traffic spikes (sowing season) | Kubernetes HPA + KEDA event-driven scaling |
| Offline rural areas | Edge-cached models + sync-on-connect |
| Multi-language | LLM translation layer + regional model fine-tuning |
| Data freshness | Kafka event streams with max 15-min latency SLA |
| Multi-state expansion | Stateless microservices + state-per-farmer partitioning |
