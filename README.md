# PS 5: AI-Powered Personalized Agriculture Services Using AgriStack

> AI Hackathon: Leveraging Emerging Technologies for Smarter Farming Systems
>
> Organized by  Department of Agriculture & Farmers Welfare | MoAFW | Government of India
>
> ✅ Selected for the next round

# 🌾 SasyaAI — Intelligent Agriculture Advisory Platform

**SasyaAI delivers hyperlocal, explainable agricultural recommendations by combining AgriStack data, soil health metrics, crop history, weather intelligence, and scheme eligibility into a unified decision support system.**

---

## Overview

SasyaAI is a project developed for the AI Hackathon: Leveraging Emerging Technologies for Smarter Farming Systems.
It uses the AgriStack ecosystem to create personalized agriculture services for farmers, including credit and insurance profiling, nutrient and irrigation guidance, production forecasting, and scheme benefit recommendations.

The platform transforms sparse and fragmented agricultural data into actionable insights for smallholder farmers, cooperatives, and extension workers.

---

## Problem Statement

Indian agriculture still struggles with disconnected farmer records, generic advisory outputs, and weak linkage between scheme eligibility and field reality.
SasyaAI addresses these issues by:
- Using verified farmer and land data from AgriStack
- Creating personalized recommendations for crop inputs, irrigation, and risk mitigation
- Predicting production at local farm level using historical and near-real-time data
- Matching farmers to government schemes and benefits through registry-linked analytics

This project is built specifically for:
- PS 5: AI-Powered Personalized Agriculture Services Using AgriStack
- AI Hackathon: Leveraging Emerging Technologies for Smarter Farming Systems

---

## Key Capabilities

- Personalized credit, insurance, and risk profiling based on verified farmer, land, and crop data
- AI-driven fertilizer, water, and input recommendations tailored to plot-level soil and weather conditions
- Production forecasting and harvest planning using historical crop records and live agricultural signals
- Automated scheme matching and benefit recommendation for eligible farmers
- Explainable output designed for farmers, extension agents, and policymakers

---

## System Architecture

SasyaAI is built as a modular decision support system with the following logical components:

1. Data Integration
   - Farmer Registry and land records from AgriStack
   - Crop surveys and digital crop registration
   - Soil Health Card data and nutrient analysis
   - Weather, precipitation, and dry spell information
2. Reasoning Engine
   - Multi-agent inference for planning, geospatial assessment, and monitoring
   - Validation layer for eligibility and risk checks
3. Recommendation Layer
   - Crop/input advisory
   - Harvest planning and yield forecasting
   - Scheme and subsidy recommendations
4. User Interaction
   - Natural language interface for farmer queries
   - Dashboard views for extension workers and administrators

---

## Technology Stack

- Backend: Python, FastAPI, Celery, Redis
- Data Storage: PostgreSQL, PostGIS, MongoDB
- Messaging: Apache Kafka
- AI/ML: LLM reasoning, tree-based models, image vision models, time-series forecasting
- Frontend: React, optional mobile interface
- Infrastructure: Docker, Kubernetes-compatible deployment

---

## Data Platform and Sandbox

SasyaAI is designed to consume data from the AgriStack Sandbox — a secure, controlled environment for experimenting with AgriStack APIs using anonymized datasets and realistic simulations.
The sandbox enables seamless integration, controlled experimentation, and rapid prototyping for agricultural services.

## Data Sources and Inputs

SasyaAI leverages the following agricultural datasets and signals:
- AgriStack Farmer Registry and land record metadata
- Agri Stack Sandbox datasets such as Telangana district/mandal geospatial shapefiles, soil moisture time series, and pincode boundary geojson
- Digital crop surveys and crop registry history
- Soil Health Card profiles and soil nutrient data
- Precipitation, weather, and dry spell information
- Scheme eligibility data for PM-KISAN, input subsidies, and insurance programs
- Market price signals and local supply chain indicators
- Kisan Call Centre transcripts and farmer query logs for question-answer modeling

---

## Project Use Cases

- Intelligent credit and insurance profiling for farmers
- Precision farm input recommendations using soil + weather data
- Localized production forecasting and harvest planning
- Scheme and benefit recommendation using registry-linked analytics

---

## How to Use

1. Clone the repository.
2. Install required dependencies.
3. Load AgriStack-aligned farmer, soil, crop, and weather datasets.
4. Start the backend services.
5. Submit farmer queries or field data and evaluate the generated recommendations.

Example commands:

```bash
git clone https://github.com/your-org/SasyaAI.git
cd SasyaAI
pip install -r requirements.txt
python -m sasyaai.main
```

---

## Deployment Notes

SasyaAI is designed for cloud-ready deployment with containerized services.
Key deployment considerations include:
- Secure storage of farmer PII and land records
- Scalable data ingestion for weather and remote sensing feeds
- Role-based access for extension agents and policymakers

---

## Security and Data Privacy

- Farmer identity and personal information are treated as sensitive data
- Access controls are enforced for system users
- Outputs are designed to be explainable and auditable for responsible decision-making

---

## Team

This project is targeted at an AI Hackathon audience and is intended as a prototype for personalized agriculture services using AgriStack.

---

## License

MIT License

---

*Project: PS 5 – AI-Powered Personalized Agriculture Services Using AgriStack*
*Hackathon: AI Hackathon: Leveraging Emerging Technologies for Smarter Farming Systems*
