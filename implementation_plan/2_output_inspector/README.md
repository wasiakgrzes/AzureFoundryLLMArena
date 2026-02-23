# Implementation Plan — Week 2: Output Inspector System

## Architecture Summary

The Output Inspector adds a quality evaluation layer that runs structural and semantic checks on model responses. Structural checks (JSON/Markdown/XML, required fields, no-extra-text) run locally with zero network dependency. Semantic checks (tone/persona adherence) use a single inspector LLM call per model response to balance insight depth with cost.

| Layer              | Modules                          | Responsibility                                                 |
|--------------------|----------------------------------|----------------------------------------------------------------|
| **Infrastructure** | `config.py` (extended)           | Inspector feature flags (9 new flags including master toggle)  |
| **Domain**         | `inspector.py` (new)             | Structural validators, required fields, extra-text detection, semantic tone/persona checks |
| **UI**             | `app.py` (extended)              | Collapsible inspector panel, pass/fail badges, color-coded highlights, inspector config controls |

## Updated Source Structure

```
src/
├── __init__.py
├── app.py              # Extended with inspector panel UI and highlighting
├── arena.py            # From Week 1
├── config.py           # Extended with inspector feature flags
├── client.py
├── discovery.py
├── inspector.py        # NEW — Structural and semantic output inspection
├── pricing.py
├── inference.py
├── export.py
└── model_pricing.json
```

## Implementation Order & Dependencies

```
Part 01: Inspector Feature Flags & Scaffold ────────────────┐
                                                              │
Part 02: Structural Format Validators ──────────────────┐    │ depends on Part 01
                                                         │    │
Part 03: Required Fields & No-Extra-Text Checks ───────┤    │ depends on Parts 01, 02
                                                         │    │
Part 04: Semantic Tone & Persona Checks ───────────────┤    │ depends on Part 01
                                                         │    │
Part 05: Inspector UI Panel & Highlighting ────────────┤    │ depends on Parts 01-04
                                                         │    │
Part 06: Inspector Error Handling & Docs ──────────────┘    │ depends on Parts 01-05
                                                              │
```

## Part Summary

| Part | Title                                    | Type            | Key Deliverables                                       |
|------|------------------------------------------|-----------------|--------------------------------------------------------|
| 01   | Inspector Feature Flags & Scaffold       | Infrastructure  | 9 feature flags, inspector.py module scaffold          |
| 02   | Structural Format Validators             | Domain          | JSON, Markdown, XML validation functions               |
| 03   | Required Fields & No-Extra-Text Checks   | Domain          | Field presence check, prefix/suffix text detection     |
| 04   | Semantic Tone & Persona Checks           | Domain          | LLM-based tone/persona evaluation, single call per response |
| 05   | Inspector UI Panel & Highlighting        | UI              | Collapsible panel, badges, color-coded highlights      |
| 06   | Inspector Error Handling & Docs          | Validation      | Graceful failures, security audit, README update       |

## PRD Reference

- Source: `prd/prd_2_output_inspector_system.md`
- User Stories: GH-W2-001 through GH-W2-008
