# Implementation Plan — Week 1: Arena Engine & Elimination

## Architecture Summary

The arena engine extends the existing MVP comparison app with tournament-style elimination mechanics. It adds a round-based state machine, winner-selection UI, per-model metrics, and a cost transparency placeholder.

| Layer              | Modules                          | Responsibility                                                 |
|--------------------|----------------------------------|----------------------------------------------------------------|
| **Infrastructure** | `config.py` (extended)           | Arena feature flags (`feature_arena_elimination`, `feature_arena_metrics_panel`, `feature_arena_cost_display`) |
| **Domain**         | `arena.py` (new)                 | Arena state machine: rounds, active/eliminated models, advancement, reset |
| **UI**             | `app.py` (extended)              | Winner selection controls, round indicator, eliminated panel, winner banner, reset button |
| **Metrics**        | `app.py` (extended)              | Per-model metrics panel, static cost notice |

## Updated Source Structure

```
src/
├── __init__.py
├── app.py              # Extended with arena UI controls and metrics panel
├── arena.py            # NEW — Arena state machine and round logic
├── config.py           # Extended with arena feature flags
├── client.py
├── discovery.py
├── pricing.py
├── inference.py
├── export.py
└── model_pricing.json
```

## Implementation Order & Dependencies

```
Part 01: Arena Feature Flags & Config ──────────────────────┐
                                                             │
Part 02: Arena State Machine & Round Logic ─────────────┐    │ depends on Part 01
                                                         │    │
Part 03: Arena Elimination UI & Winner Selection ───────┤    │ depends on Parts 01, 02
                                                         │    │
Part 04: Arena Metrics Panel & Cost Placeholder ────────┤    │ depends on Part 01
                                                         │    │
Part 05: Arena Edge Cases, Security & Docs ─────────────┘    │ depends on Parts 01-04
                                                              │
```

## Part Summary

| Part | Title                                    | Type            | Key Deliverables                                       |
|------|------------------------------------------|-----------------|--------------------------------------------------------|
| 01   | Arena Feature Flags & Config             | Infrastructure  | Feature flags in config, .env.example update           |
| 02   | Arena State Machine & Round Logic        | Domain          | src/arena.py with init, advance, reset, completion     |
| 03   | Arena Elimination UI & Winner Selection  | UI              | Checkboxes, proceed button, eliminated panel, winner   |
| 04   | Arena Metrics Panel & Cost Placeholder   | UI              | Per-model metrics, static cost notice                  |
| 05   | Arena Edge Cases, Security & Docs        | Validation      | Edge case hardening, security audit, README update     |

## PRD Reference

- Source: `prd/prd_1_arena_engine_elimination.md`
- User Stories: GH-W1-001 through GH-W1-006
