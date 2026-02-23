# PRD: Azure Foundry LLM Arena — Week 1 Arena engine and elimination

## 1. Product overview

### 1.1 Document title and version

- PRD: Azure Foundry LLM Arena — Week 1 Arena engine and elimination
- Version: 1.0

### 1.2 Product summary

This week introduces formal arena mechanics on top of the existing side-by-side comparison app. Users can run a round, pick winners, eliminate weaker models, and continue until one winner remains.

The scope also adds objective response metadata (latency and token usage) as decision support. Cost estimation remains intentionally non-dynamic; when enabled, the UI displays a transparent static notice rather than inaccurate calculations.

## 2. Goals

### 2.1 Business goals

- Increase confidence in model selection by adding repeatable tournament-style narrowing.
- Improve comparability with explicit, per-model operational metadata.
- Preserve trust with transparent handling of unavailable cost estimation.

### 2.2 User goals

- Progress through multiple rounds without re-selecting models each time.
- Quickly identify surviving models and the final winner.
- Use latency and token metrics as objective tie-breakers.

### 2.3 Non-goals

- Inspector validation and semantic quality checks.
- Historical persistence or leaderboard.
- Prompt memory and Key Vault credential path.

## 3. User personas

### 3.1 Key user types

- AI developer evaluating candidate deployments.
- Technical lead making cost/performance trade-offs.

### 3.2 Basic persona details

- **Dev evaluator**: Runs repeated prompts and needs a deterministic elimination flow.
- **Tech lead reviewer**: Needs transparent metadata to support decision rationale.

### 3.3 Role-based access

- **Local app user**: Full access to arena rounds, elimination actions, and reset.

## 4. Functional requirements

- **Arena elimination flow** (Priority: High)
  - Add winner-selection controls for each model after a completed round.
  - Require selecting at least one winner before proceeding.
  - Eliminate unselected models and carry survivors to the next round.
  - Persist round state in `st.session_state` using `arena_round`, `arena_active_models`, and `arena_eliminated_models`.
  - Display a final winner banner when one model remains.
  - Provide a reset action that clears arena state and returns to initial selection.

- **Arena metrics panel** (Priority: High)
  - Display per-model latency, input tokens, output tokens, model name, and deployment name.
  - Keep metrics visible with each response card for round decisions.

- **Cost display placeholder** (Priority: Medium)
  - Add feature flag `feature_arena_cost_display`.
  - When enabled, show: “Cost estimation not available via SDK — see pricing page.”
  - Do not compute dynamic cost in this week’s scope.

- **Execution path consistency** (Priority: High)
  - Ensure all model calls route through `ModelRunner.run(deployment_name, prompt)` abstraction.

- **Feature flags** (Priority: High)
  - Implement `feature_arena_elimination`, `feature_arena_metrics_panel`, and `feature_arena_cost_display` configurable via `.env`.

## 5. User experience

### 5.1 Entry points and first-time user flow

- User launches app, selects deployments, enters prompt, and runs first round.
- Arena controls appear only when elimination feature flag is enabled.
- Round 1 is labeled clearly and active model count is visible.

### 5.2 Core experience

- **Run round**: User submits one prompt for all active models.
  - Ensures fair comparison on identical input.
- **Select winners**: User checks one or more models as winners.
  - Prevents accidental elimination of all models by enforcing at least one selection.
- **Advance round**: App eliminates unselected models and increments round number.
  - Preserves flow continuity and reduces manual reconfiguration.
- **Complete arena**: One survivor triggers winner banner and completion state.
  - Provides clear task closure.

### 5.3 Advanced features and edge cases

- If all responses fail in a round, user can reset arena.
- If user tries to proceed with zero winners selected, show blocking validation message.
- If only one model is active after inference, auto-mark arena complete.

### 5.4 UI/UX highlights

- Round badge near results header.
- Winner-selection controls aligned with each model response.
- Eliminated models listed in a compact “Eliminated” panel.
- Reset button always visible during active arena.

## 6. Narrative

A developer starts with five candidate deployments and runs a prompt. After reviewing outputs and metrics, they select two winners, advance to round 2, and then pick a final winner in round 3. The process is explicit, repeatable, and easy to explain to stakeholders.

## 7. Success metrics

### 7.1 User-centric metrics

- At least 90% of arena runs complete without manual re-selection of models.
- Median time between rounds is under 20 seconds.
- Validation errors for zero winner selection are resolved by users within one retry.

### 7.2 Business metrics

- Reduced model-selection decision time compared with one-shot comparisons.
- Higher stakeholder confidence due to explicit elimination rationale.

### 7.3 Technical metrics

- Arena state survives Streamlit reruns within a session.
- Round transition executes without app crash for 2–5 models.
- Per-model metrics remain visible for every successful response.

## 8. Technical considerations

### 8.1 Integration points

- `src/app.py` for arena state machine and round transitions.
- `src/inference.py` for per-model latency/token fields.
- `src/config.py` for feature-flag loading.

### 8.2 Data storage and privacy

- Session-only state in `st.session_state`; no persistent storage.
- No prompt/result archival in week 1.

### 8.3 Scalability and performance

- Sequential calls remain acceptable for max 5 models.
- Arena progression should not trigger duplicate inference for unchanged rounds.

### 8.4 Potential challenges

- Streamlit rerun behavior causing unintended state resets.
- Checkbox state drift between rounds.
- Clear winner-selection UX when responses include errors.

## 9. Milestones and sequencing

### 9.1 Project estimate

- Medium: 1 week implementation + 1–2 days stabilization.

### 9.2 Team size and composition

- 1 Python/Streamlit developer.
- 1 product reviewer for acceptance validation (part-time).

### 9.3 Suggested phases

- **Phase 1 — Week 1 delivery** (5 days)
  - Arena elimination state, round controls, metrics panel, cost placeholder.
  - Key deliverables: complete multi-round workflow to final winner.
- **Phase 2 — Week 2 roadmap** (next 5 days)
  - Inspector system (structural + semantic checks).
  - Key deliverables: inspection toggle, format validation, tone/persona checks.
- **Phase 3 — Week 3 roadmap** (next 5 days)
  - Persistence, leaderboard, prompt memory, Key Vault toggle.
  - Key deliverables: historical analysis and enterprise-ready configuration path.

## 10. User stories

### 10.1 Advance arena by elimination

- **ID**: GH-W1-001
- **Description**: As a user, I want to select winners each round so that unselected models are eliminated and I can converge on the best deployment.
- **Acceptance criteria**:
  - Each model result shows a “Select as Winner” control after responses are rendered.
  - Proceed action is blocked if zero winners are selected.
  - Unselected models move to eliminated list and are excluded from next round calls.
  - Round number increments by 1 when proceeding.
  - Final winner banner appears when one active model remains.

### 10.2 Reset arena session

- **ID**: GH-W1-002
- **Description**: As a user, I want to reset the arena so that I can restart comparison from the full selected set.
- **Acceptance criteria**:
  - Reset control is available during active arena flow.
  - Reset clears `arena_round`, `arena_active_models`, and `arena_eliminated_models`.
  - UI returns to initial pre-round state without app restart.

### 10.3 View objective metrics panel

- **ID**: GH-W1-003
- **Description**: As a user, I want metadata shown beside each response so that my elimination decision includes latency and token evidence.
- **Acceptance criteria**:
  - Each successful model result shows latency, input tokens, output tokens, model name, and deployment name.
  - Missing token values render as `N/A` without breaking layout.

### 10.4 Handle cost transparency notice

- **ID**: GH-W1-004
- **Description**: As a user, I want an explicit message about cost unavailability so that I do not assume inaccurate dynamic pricing.
- **Acceptance criteria**:
  - With `feature_arena_cost_display=true`, the static placeholder message is visible near metrics.
  - No dynamic cost calculation is executed in week 1.

### 10.5 Protect feature access via configuration

- **ID**: GH-W1-005
- **Description**: As a product owner, I want feature flags in configuration so that arena capabilities can be enabled gradually.
- **Acceptance criteria**:
  - Feature flags load from `.env` on startup.
  - Disabled features do not render their related UI.
  - Flag defaults are documented and deterministic.

### 10.6 Maintain local security baseline

- **ID**: GH-W1-006
- **Description**: As a user, I want secrets handled safely so that enabling week 1 features does not expose credentials.
- **Acceptance criteria**:
  - API key is never displayed in UI components or exported artifacts.
  - Error messages avoid printing full credential values.
