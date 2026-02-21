# Implementation Plan — Azure Foundry LLM Arena

## Architecture Summary

The application is decomposed into **4 layers** with clean boundaries:

| Layer              | Modules                          | Responsibility                                      |
|--------------------|----------------------------------|-----------------------------------------------------|
| **Infrastructure** | `config.py`, `client.py`         | Env var loading, validation, discovery client init (`azure-ai-projects`) |
| **Domain**         | `discovery.py`, `pricing.py`, `inference.py` | Deployment listing, cost calc, model calling via `azure-ai-inference` |
| **UI**             | `app.py`                         | Streamlit layout, model selection, results display   |
| **Export**          | `export.py`                      | Best model JSON configuration export                 |

## Proposed Source Folder Structure

```
AzureFoundryLLMArena/
├── implementation_plan/
│   ├── README.md                          # This file
│   ├── part_01_project_scaffolding.json
│   ├── part_02_config_and_client.json
│   ├── part_03_deployment_discovery.json
│   ├── part_04_pricing_configuration.json
│   ├── part_05_inference_engine.json
│   ├── part_06_ui_layout_and_selection.json
│   ├── part_07_results_display.json
│   ├── part_08_export_configuration.json
│   └── part_09_edge_cases_and_docs.json
├── src/
│   ├── __init__.py
│   ├── app.py                  # Streamlit entry point & UI orchestration
│   ├── config.py               # Environment variable loading & validation
│   ├── client.py               # Azure AI Foundry/Projects SDK client initialization (discovery)
│   ├── discovery.py            # Deployment discovery & filtering
│   ├── pricing.py              # Cost calculation logic
│   ├── inference.py            # Inference engine using Azure AI Inference SDK (prompt → response)
│   ├── export.py               # Best model configuration export
│   └── model_pricing.json      # Static pricing data (input/output per 1K tokens)
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_discovery.py
│   ├── test_pricing.py
│   ├── test_inference.py
│   └── test_export.py
├── specification/
│   └── user_stories.md
├── .env.example
├── .gitignore
├── requirements.txt
├── prd.md
└── README.md
```

## Implementation Order & Dependencies

```
Part 01: Project Scaffolding ──────────────────────────┐
                                                        │
Part 02: Config & Client ────────────────┐              │
                                          │              │
Part 03: Deployment Discovery ───────────┤  depends on  │
                                          │  Part 02     │
Part 04: Pricing Configuration ──────────│              │
                                          │              │
Part 05: Inference Engine ───────────────┤  depends on  │
                                          │  Parts 02,03 │
                                          │              │
Part 06: UI Layout & Selection ──────────┤  depends on  │
                                          │  Parts 02,03 │
                                          │              │
Part 07: Results Display ───────────────┤  depends on  │
                                          │  Parts 04-06 │
                                          │              │
Part 08: Export Configuration ───────────┤  depends on  │
                                          │  Parts 02,03,│
                                          │  07           │
                                          │              │
Part 09: Edge Cases & Docs ─────────────┘  depends on  │
                                            Parts 01-08  │
```

## User Story Coverage

| User Story | Part(s) |
|-----------|---------|
| GH-001 (Load credentials)        | Part 02 |
| GH-002 (Auto-discover)           | Part 03 |
| GH-003 (Select models)           | Part 06 |
| GH-004 (Submit prompt)           | Parts 05, 06 |
| GH-005 (Side-by-side results)    | Part 07 |
| GH-006 (Calculate cost)          | Part 04 |
| GH-007 (Measure latency)         | Part 05 |
| GH-008 (Failure isolation)       | Part 05 |
| GH-009 (Export config)           | Part 08 |
| GH-010 (Handle missing deploys)  | Parts 03, 06 |
| GH-011 (Fail fast env vars)      | Part 02 |

## Execution Notes

- **Parts 03, 04, 05 can be developed in parallel** after Part 02 is complete
- Each part produces independently testable modules
- No part writes to persistent storage — all state is in-memory
- The API key is never exposed in any output across all parts
