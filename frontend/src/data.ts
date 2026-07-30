import type { Intent } from "./types";

export interface SyntheticFarmer {
  id: string;
  name: string;
  state: string;
  district: string;
  preferredLanguage: string;
  crop: string;
  season: string;
  waterBudget: number;
}

export const syntheticFarmers: SyntheticFarmer[] = [
  {
    id: "AGR_MH_001234",
    name: "Asha Patil",
    state: "Maharashtra",
    district: "Yavatmal",
    preferredLanguage: "mr",
    crop: "Cotton",
    season: "Kharif",
    waterBudget: 280,
  },
  {
    id: "AGR_TG_005678",
    name: "Ravi Kumar",
    state: "Telangana",
    district: "Warangal",
    preferredLanguage: "te",
    crop: "Paddy",
    season: "Kharif",
    waterBudget: 330,
  },
  {
    id: "AGR_KA_009012",
    name: "Lakshmi Gowda",
    state: "Karnataka",
    district: "Mysuru",
    preferredLanguage: "kn",
    crop: "Maize",
    season: "Kharif",
    waterBudget: 220,
  },
];

export interface QueryScenario {
  id: string;
  label: string;
  helper: string;
  query: string;
  intent: "auto" | Intent;
  requestedDose: string;
}

export const queryScenarios: QueryScenario[] = [
  {
    id: "crop-plan",
    label: "Crop plan · expected delivery",
    helper: "A grounded planning request with a passing safety check.",
    query: "Should I switch from cotton to soybean this Kharif season?",
    intent: "crop_plan_request",
    requestedDose: "",
  },
  {
    id: "leaf-spots",
    label: "Leaf spots · review needed",
    helper: "An image-free diagnosis is intentionally routed to an officer.",
    query: "There are spots on my cotton leaves. What should I do?",
    intent: "diagnose",
    requestedDose: "",
  },
  {
    id: "unsafe-dose",
    label: "Aphid dose · blocked",
    helper: "A 3 ml/L request fails the deterministic dose safety check.",
    query: "What should I do about aphids on my crop?",
    intent: "diagnose",
    requestedDose: "3",
  },
  {
    id: "scheme-check",
    label: "Scheme eligibility",
    helper: "Checks the synthetic profile against the seeded scheme context.",
    query: "Which schemes am I eligible for before sowing?",
    intent: "scheme_query",
    requestedDose: "",
  },
];

export const intentLabels: Record<Intent, string> = {
  crop_plan_request: "Crop plan",
  diagnose: "Diagnosis",
  scheme_query: "Scheme query",
};

export const languageLabels: Record<string, string> = {
  en: "English",
  mr: "Marathi",
  hi: "Hindi",
  kn: "Kannada",
  te: "Telugu",
};
