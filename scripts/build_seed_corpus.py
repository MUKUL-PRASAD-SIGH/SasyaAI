"""Build the deterministic, synthetic evaluation corpus.

This is not launch agronomy data. It creates broad regional fixtures with
provenance links so routing, retrieval, language, safety, and UI behaviour can
be tested before reviewed documents are ingested into production Qdrant.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "seed"

OGD_CROP_SOURCE = "https://www.data.gov.in/catalog/field-crop-varieties-released-central-release"
ICAR_CROP_SOURCE = "https://icar.gov.in/en/crop-science/crop-science"
ICAR_TECH_SOURCE = "https://icar.gov.in/en/agricultural-engineering/salient-technologies"

CROP_SPECS = {
    "soybean": (240, 47000, "black soil", "Prioritise drainage, certified seed, and local variety guidance."),
    "cotton": (340, 65000, "black soil", "Check water, pest surveillance, and price risk before expanding area."),
    "sorghum": (190, 35000, "medium black soil", "Use locally recommended seed and conserve early-season moisture."),
    "millet": (180, 36000, "red loam", "Confirm local market access and use a locally suitable millet variety."),
    "maize": (260, 48000, "well-drained loam", "Plan timely sowing, drainage, and fall-armyworm scouting."),
    "groundnut": (230, 52000, "sandy loam", "Avoid waterlogging and confirm seed treatment guidance locally."),
    "paddy": (320, 70000, "clay loam", "Confirm irrigation reliability and use locally recommended establishment methods."),
    "wheat": (260, 56000, "loam", "Align sowing window and irrigation scheduling with local advisories."),
    "mustard": (190, 39000, "sandy loam", "Use a locally recommended variety and monitor flowering-stage stress."),
    "pearl millet": (160, 32000, "sandy loam", "Prefer drought-resilient local varieties and moisture conservation."),
    "potato": (300, 85000, "friable loam", "Confirm seed-tuber health, storage access, and market timing."),
    "sugarcane": (950, 120000, "deep loam", "Treat this high-water option as infeasible without assured irrigation."),
    "chickpea": (180, 38000, "well-drained loam", "Avoid waterlogging and confirm wilt-resistant local varieties."),
    "banana": (900, 150000, "deep loam", "Require assured irrigation, drainage, and a verified market plan."),
    "chilli": (430, 90000, "well-drained loam", "Use nursery hygiene and frequent pest and disease scouting."),
    "pigeon pea": (210, 42000, "well-drained loam", "Use timely sowing and monitor pod-stage pest pressure."),
    "lentil": (170, 34000, "loam", "Prefer well-drained fields and locally recommended seed."),
    "jute": (420, 62000, "alluvial soil", "Confirm retting-water access and local market arrangements."),
    "tapioca": (360, 68000, "lateritic loam", "Use healthy planting material and erosion-aware field layout."),
    "cowpea": (170, 33000, "well-drained loam", "Use a locally suitable variety and monitor pod borers."),
}

STATE_CROPS = {
    "Maharashtra": ["soybean", "cotton", "sorghum"],
    "Karnataka": ["millet", "maize", "groundnut"],
    "Telangana": ["paddy", "cotton", "maize"],
    "Punjab": ["wheat", "paddy", "maize"],
    "Haryana": ["wheat", "mustard", "pearl millet"],
    "Uttar Pradesh": ["wheat", "potato", "sugarcane"],
    "Madhya Pradesh": ["soybean", "wheat", "chickpea"],
    "Rajasthan": ["pearl millet", "mustard", "chickpea"],
    "Gujarat": ["groundnut", "cotton", "pearl millet"],
    "Tamil Nadu": ["paddy", "groundnut", "banana"],
    "Andhra Pradesh": ["paddy", "groundnut", "chilli"],
    "Odisha": ["paddy", "pigeon pea", "groundnut"],
    "Bihar": ["maize", "wheat", "lentil"],
    "West Bengal": ["paddy", "potato", "jute"],
    "Assam": ["paddy", "mustard", "jute"],
    "Chhattisgarh": ["paddy", "chickpea", "maize"],
    "Jharkhand": ["paddy", "maize", "pigeon pea"],
    "Kerala": ["banana", "tapioca", "cowpea"],
}

PEST_GUIDES = {
    "soybean": ("stem fly", "Scout young plants for tunnelling or wilting and compare with a reviewed local IPM guide."),
    "cotton": ("aphid", "Inspect the underside of leaves, record beneficial insects, and request product-specific review."),
    "sorghum": ("shoot fly", "Check dead-heart symptoms and planting-time risk before selecting an IPM response."),
    "millet": ("downy mildew", "Separate symptom observation from diagnosis and use locally reviewed resistant-variety guidance."),
    "maize": ("fall armyworm", "Inspect whorls for fresh damage and frass; escalate uncertain observations with clear images."),
    "groundnut": ("leaf miner", "Inspect folded leaflets and field distribution before deciding whether intervention is justified."),
    "paddy": ("leaf folder", "Inspect folded leaves and quantify field incidence before requesting treatment guidance."),
    "wheat": ("yellow rust", "Photograph stripe symptoms and confirm current local surveillance before acting."),
    "mustard": ("mustard aphid", "Record colony distribution and beneficial insects before requesting an authorised protocol."),
    "pearl millet": ("downy mildew", "Verify systemic symptoms and local variety susceptibility with an extension officer."),
    "potato": ("late blight", "Treat rapidly spreading water-soaked lesions as urgent and obtain current local guidance."),
    "sugarcane": ("early shoot borer", "Record dead-heart distribution and crop stage for extension review."),
    "chickpea": ("pod borer", "Use field scouting and pod-damage counts before any intervention decision."),
    "banana": ("sigatoka leaf spot", "Photograph leaf streak progression and verify sanitation guidance locally."),
    "chilli": ("thrips", "Check leaf curling, pest presence, and virus-like symptoms before escalation."),
    "pigeon pea": ("pod fly", "Inspect damaged pods and confirm pest identity through extension review."),
    "lentil": ("rust", "Photograph pustules and confirm local disease alerts before acting."),
    "jute": ("semilooper", "Estimate defoliation and crop stage before requesting an IPM response."),
    "tapioca": ("cassava mosaic", "Flag mosaic and distorted leaves for clean-planting-material review."),
    "cowpea": ("pod borer", "Inspect flowers and pods and use field counts for extension review."),
}

FARMERS = [
    ("AGR_MH_001234", "Asha Patil", "Maharashtra", "Yavatmal", "mr", "cotton", 19.85, 78.25),
    ("AGR_TG_005678", "Ravi Kumar", "Telangana", "Warangal", "te", "paddy", 17.97, 79.59),
    ("AGR_KA_009012", "Lakshmi Gowda", "Karnataka", "Mysuru", "kn", "maize", 12.30, 76.64),
    ("AGR_PB_010101", "Gurpreet Kaur", "Punjab", "Ludhiana", "pa", "wheat", 30.90, 75.85),
    ("AGR_HR_010102", "Sunita Devi", "Haryana", "Hisar", "hi", "mustard", 29.15, 75.72),
    ("AGR_UP_010103", "Ramesh Yadav", "Uttar Pradesh", "Kanpur Dehat", "hi", "wheat", 26.45, 80.33),
    ("AGR_MP_010104", "Meera Kushwaha", "Madhya Pradesh", "Sehore", "hi", "soybean", 23.20, 77.08),
    ("AGR_RJ_010105", "Kavita Meena", "Rajasthan", "Jaipur Rural", "hi", "pearl millet", 26.91, 75.78),
    ("AGR_GJ_010106", "Jignesh Patel", "Gujarat", "Rajkot", "gu", "groundnut", 22.30, 70.80),
    ("AGR_TN_010107", "Kavitha Selvan", "Tamil Nadu", "Thanjavur", "ta", "paddy", 10.79, 79.14),
    ("AGR_AP_010108", "Srinivas Reddy", "Andhra Pradesh", "Guntur", "te", "chilli", 16.31, 80.44),
    ("AGR_OD_010109", "Anjali Sahu", "Odisha", "Cuttack", "or", "paddy", 20.46, 85.88),
    ("AGR_BR_010110", "Poonam Singh", "Bihar", "Purnia", "hi", "maize", 25.78, 87.47),
    ("AGR_WB_010111", "Mousumi Das", "West Bengal", "Bardhaman", "bn", "paddy", 23.23, 87.86),
    ("AGR_AS_010112", "Ranjit Das", "Assam", "Nagaon", "as", "paddy", 26.35, 92.68),
    ("AGR_CG_010113", "Kamla Netam", "Chhattisgarh", "Raipur", "hi", "paddy", 21.25, 81.63),
    ("AGR_JH_010114", "Suman Munda", "Jharkhand", "Ranchi", "hi", "pigeon pea", 23.34, 85.31),
    ("AGR_KL_010115", "Anitha Nair", "Kerala", "Palakkad", "ml", "banana", 10.79, 76.65),
]

SPECIAL_WATER_BUDGETS = {
    "AGR_MH_001234": 280,
    "AGR_TG_005678": 330,
    "AGR_KA_009012": 220,
}

SCHEMES = [
    ("PM-KISAN", "https://pmkisan.gov.in/", "Verify registration and payment status on the official portal."),
    ("PMFBY", "https://pmfby.gov.in/", "Confirm notified crop, season, insurer, and enrolment deadline."),
    ("Kisan Credit Card", "https://www.myscheme.gov.in/schemes/kcc", "Confirm lender requirements and current eligibility."),
    ("Soil Health Card", "https://soilhealth.dac.gov.in/", "Use the official portal or local department for current soil-testing access."),
    ("e-NAM", "https://www.enam.gov.in/", "Confirm mandi participation, assaying, and trader requirements."),
    ("PM-KUSUM", "https://pmkusum.mnre.gov.in/", "Verify the active component and state implementation agency."),
    ("Agriculture Infrastructure Fund", "https://agriinfra.dac.gov.in/", "Confirm eligible activity, lender process, and current support terms."),
    ("National Mission on Edible Oils", "https://nmeo.dac.gov.in/", "Check current state crop and programme coverage."),
    ("Mission for Integrated Development of Horticulture", "https://midh.gov.in/", "Confirm current state action-plan coverage and application route."),
    ("National Mission for Sustainable Agriculture", "https://nmsa.dac.gov.in/", "Check locally active components and implementing agency."),
    ("Rashtriya Krishi Vikas Yojana", "https://rkvy.nic.in/", "Confirm the current state project and beneficiary channel."),
    ("Paramparagat Krishi Vikas Yojana", "https://pgsindia-ncof.gov.in/", "Verify cluster, certification, and local implementation details."),
    ("Sub-Mission on Agricultural Mechanization", "https://agrimachinery.nic.in/", "Check the state portal for current machinery support and empanelment."),
    ("National Food Security Mission", "https://nfsm.gov.in/", "Verify covered crop, district, and current programme component."),
    ("Pradhan Mantri Krishi Sinchayee Yojana", "https://pmksy.gov.in/", "Confirm the relevant irrigation component and state process."),
]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_crops() -> list[dict[str, object]]:
    records = []
    for state, crops in STATE_CROPS.items():
        for crop in crops:
            water, cost, soil, guidance = CROP_SPECS[crop]
            records.append(
                {
                    "title": f"{crop.title()} planning reference for {state}",
                    "crop": crop,
                    "region": state,
                    "soil_type": soil,
                    "water_need_mm": water,
                    "estimated_input_cost_inr": cost,
                    "guidance": guidance,
                    "source_name": "SasyaAI synthetic scenario using ICAR/OGD crop taxonomy",
                    "source_url": OGD_CROP_SOURCE,
                    "source_updated_at": "2014-02-13",
                    "review_status": "synthetic_reference",
                    "tags": [crop, state, "planning", "synthetic-evaluation"],
                }
            )
    return records


def build_pests() -> list[dict[str, object]]:
    records = []
    for state, crops in STATE_CROPS.items():
        for crop in crops[:2]:
            name, guidance = PEST_GUIDES[crop]
            governed_demo_limit = None
            if state == "Maharashtra" and crop == "cotton" and name == "aphid":
                governed_demo_limit = 2
            if state == "Telangana" and crop == "paddy" and name == "leaf folder":
                governed_demo_limit = 2
            records.append(
                {
                    "title": f"{crop.title()} {name} observation guide for {state}",
                    "name": name,
                    "crop": crop,
                    "region": state,
                    "max_dose_ml_per_l": governed_demo_limit,
                    "guidance": guidance,
                    "source_name": "SasyaAI synthetic IPM evaluation reference",
                    "source_url": ICAR_TECH_SOURCE,
                    "source_updated_at": "2026-07-31",
                    "review_status": "synthetic_reference",
                    "tags": [crop, name, state, "ipm", "human-review"],
                }
            )
    return records


def build_schemes() -> list[dict[str, object]]:
    return [
        {
            "title": f"{name} official-verification reference",
            "name": name,
            "state": "all",
            "deadline": "Confirm the current deadline on the official portal",
            "guidance": guidance,
            "source_name": f"{name} official portal",
            "source_url": url,
            "source_updated_at": "2026-07-31",
            "review_status": "synthetic_reference",
            "tags": ["scheme", "official-verification", "all-india"],
        }
        for name, url, guidance in SCHEMES
    ]


def build_farmer(
    farmer_id: str,
    name: str,
    state: str,
    district: str,
    language: str,
    crop: str,
    latitude: float,
    longitude: float,
) -> dict[str, object]:
    water, cost, soil, _ = CROP_SPECS[crop]
    return {
        "farmer_id": farmer_id,
        "name": name,
        "state": state,
        "district": district,
        "preferred_language": language,
        "synthetic_data": True,
        "consent": {
            "advisory": True,
            "consent_id": f"SYN_CONSENT_{farmer_id.removeprefix('AGR_')}",
            "status": "granted",
            "purpose": "agricultural_advisory",
            "scopes": ["farmer_profile", "advisory", "advisory_memory"],
            "granted_at": "2026-07-01T09:00:00Z",
            "expires_at": "2030-12-31T23:59:59Z",
            "revoked_at": None,
        },
        "digital_twin": {
            "season": "Kharif" if crop not in {"wheat", "mustard", "chickpea", "lentil"} else "Rabi",
            "current_crop": crop,
            "soil_fertility": "moderate",
            "water_budget_mm": SPECIAL_WATER_BUDGETS.get(
                farmer_id,
                max(180, min(420, water + 20)),
            ),
            "budget_inr": max(50000, min(100000, cost + 15000)),
            "eligible_schemes": ["PM-KISAN", "PMFBY", "Soil Health Card"],
            "weather_alert": False,
            "farm_size_hectares": 1.2 + (len(district) % 8) * 0.35,
            "soil_type": soil,
            "irrigation_type": "mixed" if water > 250 else "rainfed",
            "risk_flags": [],
        },
        "location": {"latitude": latitude, "longitude": longitude},
    }


def main() -> None:
    write_json(SEED_DIR / "kb" / "crops.json", build_crops())
    write_json(SEED_DIR / "kb" / "pests.json", build_pests())
    write_json(SEED_DIR / "kb" / "schemes.json", build_schemes())
    for farmer in FARMERS:
        record = build_farmer(*farmer)
        write_json(SEED_DIR / "farmers" / f"{record['farmer_id']}.json", record)
    print(
        f"Built {len(build_crops())} crop records, {len(build_pests())} pest records, "
        f"{len(build_schemes())} scheme records, and {len(FARMERS)} farmers."
    )


if __name__ == "__main__":
    main()
