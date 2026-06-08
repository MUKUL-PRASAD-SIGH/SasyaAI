# 🚀 SETUP & DEPLOY — SasyaAI

> Everything you need to run SasyaAI locally, develop with AI-augmented tooling, and deploy to production.

---

## 1. Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend services |
| Node.js | 20+ | Frontend (React, React Native) |
| Docker Desktop | 24+ | Container orchestration |
| Git | Latest | Version control |
| AWS CLI / Azure CLI | Latest | Cloud deployment (optional) |

---

## 2. Quick Start (Local Development)

### Clone & Configure

```bash
git clone https://github.com/your-org/SasyaAI.git
cd SasyaAI
cp .env.example .env
```

Required `.env` variables:
```env
# Core
DATABASE_URL=postgresql://user:pass@localhost:5432/sasyaai
REDIS_URL=redis://localhost:6379
KAFKA_BROKERS=localhost:9092

# AI APIs
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=AIza...

# AgriStack
AGRISTACK_API_BASE=https://agristack.gov.in/api/v1
AGRISTACK_CLIENT_ID=...
AGRISTACK_CLIENT_SECRET=...

# Weather + Market
IMD_API_KEY=...
ENAM_API_KEY=...

# Auth
JWT_SECRET=...
DIGILOCKER_CLIENT_ID=...
```

### Run with Docker Compose

```bash
docker-compose up --build -d    # Build and start all services
docker-compose ps               # Check service health
docker-compose logs -f orchestrator  # View logs
```

> Load GICEN datasets (Telangana shapefiles, soil moisture, pincode GeoJSON) before running advisory pipelines.

### Services Started

| Service | Port | Description |
|---|---|---|
| orchestrator | 8000 | Main FastAPI orchestration |
| planning-agent | 8001 | Crop planning microservice |
| vision-agent | 8002 | Image inference (GPU) |
| geospatial-agent | 8003 | GIS analysis |
| monitoring-agent | 8004 | Verification + alerts |
| postgres | 5432 | Database |
| redis | 6379 | Cache |
| kafka | 9092 | Event broker |
| frontend | 3000 | React dashboard |

### Initialize Database

```bash
docker-compose exec orchestrator alembic upgrade head
docker-compose exec orchestrator python scripts/seed_demo_data.py  # dev only
```

### Run Tests

```bash
pytest tests/unit/ -v                                    # Unit tests
pytest tests/integration/ -v                             # Integration tests
pytest tests/vision/ -v --model-path models/yolov8_npss.pt  # Vision model tests
```

---

## 3. IDE Setup (VS Code)

### Required Extensions

| Extension | ID | Purpose |
|---|---|---|
| GitHub Copilot | `github.copilot` | Inline code completions |
| Copilot Chat | `github.copilot-chat` | Conversational assistance |
| Python | `ms-python.python` | Language server |
| Pylance | `ms-python.vscode-pylance` | Type checking |
| Docker | `ms-azuretools.vscode-docker` | Container management |
| Kubernetes | `ms-kubernetes-tools.vscode-kubernetes-tools` | Cluster management |
| ESLint | `dbaeumer.vscode-eslint` | JS/TS linting |
| REST Client | `humao.rest-client` | API testing |
| PostgreSQL | `cweijan.vscode-postgresql-client2` | DB explorer |
| Geo Data Viewer | `RandomFractalsInc.geo-data-viewer` | GeoJSON preview |

### VS Code Settings

```json
{
  "editor.formatOnSave": true,
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.ruffEnabled": true,
  "[python]": { "editor.defaultFormatter": "charliermarsh.ruff" },
  "editor.rulers": [88],
  "github.copilot.enable": { "*": true }
}
```

### Python Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

### Debug Configurations (`.vscode/launch.json`)

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Orchestrator (Debug)",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "env": { "ENV": "development" }
    },
    {
      "name": "Vision Agent (Debug)",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["agents.vision.main:app", "--reload", "--port", "8002"],
      "env": { "MODEL_PATH": "models/yolov8_npss.pt" }
    }
  ]
}
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: no-commit-to-branch
        args: ['--branch', 'main']
      - id: detect-private-key
      - id: check-yaml
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
```

---

## 4. Deployment Architecture

```
┌─────────────────┐     ┌────────────────┐     ┌──────────────────────┐
│  GitHub Repo    │────▶│ GitHub Actions │────▶│  AWS ECR             │
│  (main branch)  │     │  Lint + Test   │     │  (Docker images)     │
└─────────────────┘     │  Build Docker  │     └──────────┬───────────┘
                        └────────────────┘                │ ArgoCD
                                                ┌─────────▼──────────┐
                                                │  Kubernetes (EKS)  │
                                                │  NGINX + Istio     │
                                                │  Microservice Pods │
                                                └─────────┬──────────┘
                                                          │
                                    ┌─────────────────────┼─────────────────┐
                                    │                     │                 │
                             ┌──────▼──────┐    ┌────────▼──────┐  ┌──────▼──────┐
                             │ RDS Postgres│    │ ElastiCache   │  │ Amazon MSK  │
                             │ + PostGIS   │    │ (Redis)       │  │ (Kafka)     │
                             └─────────────┘    └───────────────┘  └─────────────┘
```

### Kubernetes Namespaces

```
sasyaai-prod         # Production workloads
sasyaai-staging      # Staging environment
sasyaai-monitoring   # Prometheus, Grafana, Loki
sasyaai-infra        # Kafka, Redis, ingress
```

### Helm Deployment

```bash
# Staging
helm upgrade sasyaai ./helm/sasyaai -f values-staging.yaml --namespace sasyaai-staging

# Production (via GitOps only)
git push origin main    # ArgoCD auto-syncs within 3 minutes

# Rollback
helm rollback sasyaai --namespace sasyaai-prod
```

### Multi-Region Strategy

| Region | Purpose | States Served |
|---|---|---|
| ap-south-1 (Mumbai) | Primary | Maharashtra, Gujarat, MP, Rajasthan |
| ap-south-2 (Hyderabad) | Secondary | Telangana, AP, Karnataka, Tamil Nadu |
| ap-southeast-1 (Singapore) | Disaster Recovery | Fallback for all regions |

**Data Residency**: All farmer PII stored only in India (ap-south-1/2) per DPDP Act.

---

## 5. Monitoring & Observability

### Grafana Dashboards

- **SLA**: API latency P50/P95/P99, error rates
- **Agent Health**: Inference latency, queue depth, failure rates
- **Engagement**: DAU, advisory completions, voice vs text
- **Data Freshness**: Last update for weather, market, satellite feeds

### Alerting Rules

```yaml
- alert: VisionAgentHighLatency
  expr: histogram_quantile(0.95, vision_inference_duration_seconds) > 10
  for: 5m
  annotations:
    summary: "Vision agent P95 latency > 10s"

- alert: KafkaConsumerLag
  expr: kafka_consumer_lag_sum > 10000
  for: 2m
  annotations:
    summary: "Monitoring agent falling behind on event stream"
```

### Database Backups

| Database | Frequency | Retention |
|---|---|---|
| PostgreSQL | Every 6 hours | 30 days |
| MongoDB | Daily | 14 days |
| Redis | On change (AOF) | 7 days |
| S3 Data Lake | Continuous | Indefinite |

---

## 6. For Farmers (Mobile App)

### Getting Started

1. Download **SasyaAI** from Play Store / App Store
2. Enter mobile number (Aadhaar-linked) → Complete OTP
3. Grant permissions: Camera (pest scan), Location (weather)
4. Enter AgriStack / Kisan ID → land records auto-populate
5. Select preferred language → Tap **Today's Advice**

### Key Features

| Feature | How to Use |
|---|---|
| 🌱 **Crop Planning** | Plan Next Season → Select season → View AI-ranked options → What-If simulator → Confirm |
| 🐛 **Pest Scanner** | Camera icon → Scan My Crop → Photo → 5s analysis → Treatment + dosage + cost |
| 💰 **Scheme Finder** | Government Schemes → Auto-eligibility check → Apply via DigiLocker/CSC |
| 🗺️ **Farm Map** | Farm Map → NDVI health overlay + soil zones + groundwater depth |
| 🔔 **Alerts** | Weather (48hr), pest outbreaks, market price ±15%, scheme deadlines |

### Offline Mode

Works offline for: last advisory, pest scanner (on-device model), crop calendar, cached scheme list. Syncs when connectivity is restored.

---

## 7. For Extension Workers

1. Log in at `dashboard.sasyaai.ai`
2. View assigned farmers' digital twin summaries
3. Send broadcast advisories to farmer clusters
4. Review AI recommendations flagged for human review
5. Access district-level analytics and scheme uptake reports

---

## 8. Getting Help

- **In-app**: Tap **?** on any screen
- **Voice**: Say "Help" in your language
- **Kisan helpline**: 1800-180-1551 (toll-free)
- **Email**: support@sasyaai.ai
