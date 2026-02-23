# PRD: Azure Foundry LLM Arena — Week 2 Output inspector system

## 1. Product overview

### 1.1 Document title and version

- PRD: Azure Foundry LLM Arena — Week 2 Output inspector system
- Version: 1.0

### 1.2 Product summary

This week adds the Output Inspector layer that evaluates response compliance and style. Structural checks (JSON/Markdown/XML, required fields, no extra text) run locally, while semantic checks (tone/persona adherence) use a single inspector-model call per response.

The design prioritizes cost and latency control by avoiding multiple LLM validation calls. The inspector becomes an optional but high-value decision aid that turns raw comparison into quality-governed evaluation.

## 2. Goals

### 2.1 Business goals

- Differentiate the project with objective and semantic quality checks.
- Reduce manual review effort for structured-output tasks.
- Keep operational cost bounded via one inspector model call per response.

### 2.2 User goals

- Toggle inspection on demand.
- Validate output format and required fields quickly.
- Confirm tone/persona adherence with explainable binary verdicts.

### 2.3 Non-goals

- Numeric quality scoring or rubric weighting.
- Multi-inspector ensemble voting.
- Persistence of inspection history (handled in week 3).

## 3. User personas

### 3.1 Key user types

- Prompt engineer validating response contract compliance.
- QA analyst checking output quality gates before release.

### 3.2 Basic persona details

- **Prompt engineer**: Needs fast pass/fail checks for structured outputs.
- **QA analyst**: Needs clear reasons when tone/persona requirements fail.

### 3.3 Role-based access

- **Local app user**: Can configure and run all inspector checks.

## 4. Functional requirements

- **Inspector activation** (Priority: High)
  - Add `feature_inspector_enabled` flag.
  - If disabled, hide all inspector UI and skip inspection runtime.

- **Output format validation** (Priority: High)
  - Add flags: `feature_inspector_validate_json`, `feature_inspector_validate_markdown`, `feature_inspector_validate_xml`.
  - JSON: validate with `json.loads` and report valid/invalid state.
  - Markdown: validate basic heading/list structure.
  - XML: validate parseability with `xml.etree.ElementTree`.

- **Required field enforcement** (Priority: High)
  - Add `feature_inspector_required_fields` flag.
  - Accept user-entered required fields and verify existence for JSON outputs.

- **No additional comments enforcement** (Priority: High)
  - Add `feature_inspector_no_extra_text` flag.
  - Detect and flag prefix/suffix content outside structured block.

- **Tone and persona adherence** (Priority: High)
  - Add flags: `feature_inspector_tone_check`, `feature_inspector_persona_check`.
  - Support inspector-model selection from deployment dropdown.
  - Make one inspector LLM call per model response with structured JSON return:
    - `tone_match`
    - `persona_match`
    - `reason`

- **Output highlighting layer** (Priority: Medium)
  - Add `feature_inspector_highlighting` flag.
  - Render highlights in Streamlit with simple HTML:
    - Red = violation
    - Green = validated
    - Blue = informational

## 5. User experience

### 5.1 Entry points and first-time user flow

- User enables inspector feature flag and opens inspector panel.
- User configures validation mode (JSON/Markdown/XML), required fields, and optional tone/persona expectations.
- User picks inspector deployment once per session.

### 5.2 Core experience

- **Run arena prompt**: User executes standard model comparison.
  - Keeps baseline arena workflow unchanged.
- **Auto-run local checks**: App validates structure and required fields.
  - Provides immediate deterministic feedback.
- **Run semantic checks**: App sends one inspector call per model output if configured.
  - Balances insight depth with controlled cost.
- **Review highlights**: Violations and passes appear inline with color coding.
  - Speeds decision-making and troubleshooting.

### 5.3 Advanced features and edge cases

- If inspector model call fails, local checks still render and semantic status shows graceful failure.
- Invalid JSON with required fields configured returns “cannot evaluate fields” state.
- Empty output returns structured failure summary rather than raw exception.

### 5.4 UI/UX highlights

- Collapsible inspector panel to avoid clutter.
- Clear pass/fail badges for each check.
- Structured reason text for semantic failures.
- Consistent color semantics across all checks.

## 6. Narrative

A prompt engineer compares three models for JSON-only output with strict keys and a formal tone. The inspector immediately flags one model for invalid JSON, another for missing a required field, and confirms that the third meets structure and tone/persona requirements. The team selects the compliant model with less manual reading.

## 7. Success metrics

### 7.1 User-centric metrics

- At least 80% of inspection issues are identified without manual code-level parsing.
- Median inspection feedback render time under 2 seconds after inference completion (excluding semantic LLM latency).
- Users can explain model rejection reasons using inspector output in under 1 minute.

### 7.2 Business metrics

- Reduced rework caused by malformed structured outputs.
- Higher reliability of selected model behavior in downstream integration tasks.

### 7.3 Technical metrics

- Exactly one semantic inspector call per model response when enabled.
- Local validations execute without network dependency.
- Inspector failures do not block arena results rendering.

## 8. Technical considerations

### 8.1 Integration points

- `src/app.py` for inspector panel controls and rendering.
- New `src/inspector.py` module for deterministic and semantic checks orchestration.
- `src/inference.py` reused for inspector model invocation path.
- `src/config.py` for inspector feature-flag loading.

### 8.2 Data storage and privacy

- Week 2 remains session-only; no persistence by default.
- Inspector prompts and model outputs remain in-memory for current run.
- Secrets continue to load from existing local configuration.

### 8.3 Scalability and performance

- Semantic checks add N inspector calls for N candidate outputs.
- Deterministic checks remain O(N) and low-latency.
- Highlight rendering should avoid expensive HTML transformations.

### 8.4 Potential challenges

- Reliable extraction of “structured block only” for no-extra-text checks.
- Consistent JSON schema handling in inspector model responses.
- Avoiding false positives in markdown structure validation.

## 9. Milestones and sequencing

### 9.1 Project estimate

- Medium: 1 week implementation + 2 days tuning and prompt hardening.

### 9.2 Team size and composition

- 1 Python/Streamlit developer.
- 1 QA reviewer for rule validation.

### 9.3 Suggested phases

- **Phase 1 — Week 2 delivery** (5 days)
  - Inspector toggle, local validators, required fields, no-extra-text, semantic checks, highlighting.
  - Key deliverables: complete inspector panel with binary semantic verdicts.
- **Phase 2 — Week 3 roadmap** (next 5 days)
  - Persistence, leaderboard, prompt memory, Key Vault toggle.
  - Key deliverables: historical and operational maturity.
- **Phase 3 — Post-week roadmap** (following 1–2 weeks)
  - Hardening, test expansion, and documentation for enterprise adoption.
  - Key deliverables: stable release candidate and operational playbook.

## 10. User stories

### 10.1 Toggle inspector system

- **ID**: GH-W2-001
- **Description**: As a user, I want to enable or disable the inspector so that I can control validation overhead per session.
- **Acceptance criteria**:
  - Inspector panel is visible only when `feature_inspector_enabled=true`.
  - When disabled, no inspection logic executes.

### 10.2 Validate output structure by format

- **ID**: GH-W2-002
- **Description**: As a user, I want structural validation for JSON/Markdown/XML so that I can detect format violations quickly.
- **Acceptance criteria**:
  - JSON validation uses parse attempt and shows pass/fail badge.
  - XML validation uses parse attempt and shows pass/fail badge.
  - Markdown validation checks basic heading/list presence and reports pass/fail.

### 10.3 Enforce required fields

- **ID**: GH-W2-003
- **Description**: As a user, I want required fields checked for JSON output so that responses are integration-ready.
- **Acceptance criteria**:
  - User can input one or more required fields.
  - Inspector marks each field Found or Missing.
  - If JSON is invalid, field validation reports Not Evaluated with reason.

### 10.4 Enforce no extra text

- **ID**: GH-W2-004
- **Description**: As a user, I want to reject responses with additional comments outside structured output so that parsing remains deterministic.
- **Acceptance criteria**:
  - Prefix/suffix text outside the structured block is flagged as violation.
  - Compliant outputs are marked pass.

### 10.5 Evaluate tone and persona adherence

- **ID**: GH-W2-005
- **Description**: As a user, I want semantic checks for tone and persona so that output style aligns with requirements.
- **Acceptance criteria**:
  - User can choose one inspector deployment.
  - App performs one inspector call per model response when enabled.
  - Result includes `tone_match`, `persona_match`, and `reason` fields.

### 10.6 Render visual highlight layer

- **ID**: GH-W2-006
- **Description**: As a user, I want color-coded highlights so that I can identify violations at a glance.
- **Acceptance criteria**:
  - Violations render in red, validations in green, informational notes in blue.
  - Highlight rendering does not alter original response text semantics.

### 10.7 Protect inspection flow from failures

- **ID**: GH-W2-007
- **Description**: As a user, I want graceful handling when inspector calls fail so that deterministic checks still provide value.
- **Acceptance criteria**:
  - Semantic call failures show non-blocking error status in inspection panel.
  - Local structural checks still execute and render.

### 10.8 Preserve secure runtime behavior

- **ID**: GH-W2-008
- **Description**: As a product owner, I want inspector additions to preserve secure handling of credentials and prompts.
- **Acceptance criteria**:
  - API keys are not displayed in inspector UI or failure messages.
  - Inspector prompts avoid embedding secrets from runtime configuration.
