# SasyaAI synthetic evaluation corpus

Version: `2026.07`

Generator: `scripts/build_seed_corpus.py`

Permitted use: development, regression testing, routing evaluation, UI review

## Contents

The deterministic generator produces:

| Collection | Records | Coverage |
| --- | ---: | --- |
| Crop planning references | 54 | 18 Indian states, 20 crops |
| Pest/IPM observation references | 36 | 18 states, two crop scenarios per state |
| Scheme verification references | 15 | All-India official-portal checks |
| Synthetic farmer profiles | 18 | One non-real profile per represented state |

Every knowledge record includes a source name, HTTPS source URL, source update
date, tags, and `review_status=synthetic_reference`. Farmer records are
explicitly marked `synthetic_data=true`.

## Source taxonomy

The crop and pest taxonomies are shaped around public references from:

- Government of India Open Government Data crop-variety and agriculture
  catalogues;
- ICAR crop-science and agricultural-technology pages; and
- official scheme portals such as PM-KISAN, PMFBY, e-NAM, and PM-KUSUM.

The generated guidance is authored for software evaluation. A provenance link
does **not** mean the generated sentence was published or agronomically reviewed
by that source.

## Intended evaluations

- typed intent routing across crop planning, pest observation, and schemes;
- state-filtered retrieval and all-India scheme retrieval;
- multilingual response routing for 11 language codes;
- water and budget guardrail checks;
- pesticide-dose blocking and low-confidence human escalation;
- UI coverage, agent telemetry, and immutable review behavior.

## Prohibited use

Do not use this corpus to make real planting, pesticide, financial, insurance,
or scheme-eligibility decisions. It contains no real farmer data, field
measurements, labels, images, market prices, or authorised pesticide protocols.
It is not a substitute for reviewed extension literature or live provider data.

## Production ingestion standard

Production Qdrant collections must be populated separately through the governed
knowledge-ingestion endpoint. Each document requires an accountable reviewer,
source URL, source update timestamp, state scope, and retained source content.
Synthetic records are never copied into the production runtime automatically.
Use `scripts/ingest_reviewed_corpus.py --dry-run` to validate a large reviewed
JSONL corpus before invoking that endpoint.

## Rebuild and validate

```powershell
python scripts/build_seed_corpus.py
python -m pytest tests/test_agent_runtime.py -q
```

The generator is deterministic; rerunning it should not create a diff unless
the corpus definition changed.
