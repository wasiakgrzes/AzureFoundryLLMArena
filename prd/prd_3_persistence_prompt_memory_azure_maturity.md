# PRD: Azure Foundry LLM Arena — Week 3 Persistence prompt memory and Azure maturity

## 1. Product overview

### 1.1 Document title and version

- PRD: Azure Foundry LLM Arena — Week 3 Persistence prompt memory and Azure maturity
- Version: 1.0

### 1.2 Product summary

This week evolves the project from session-only comparison into a traceable evaluation system. Arena outcomes are stored for historical analysis, a leaderboard surfaces long-term winners, and prompt memory enables fast reruns.

It also adds an enterprise-oriented credential path with optional Azure Key Vault usage while preserving `.env` fallback. The combined scope supports reproducibility, governance, and operational readiness.

## 2. Goals

### 2.1 Business goals

- Enable longitudinal model-performance tracking over time.
- Improve model-selection consistency with leaderboard insights.
- Increase enterprise readiness through secure secret management options.

### 2.2 User goals

- Save and review previous arena outcomes.
- Reuse successful prompts without manual copy/paste.
- Operate with Key Vault-backed secrets in secure environments.

### 2.3 Non-goals

- Multi-tenant RBAC authorization model.
- Fully managed cloud-hosted app deployment.
- Real-time streaming analytics pipeline.

## 3. User personas

### 3.1 Key user types

- Platform engineer tracking model drift.
- Applied AI developer iterating on prompts.
- Security-conscious team lead enforcing secret-management practices.

### 3.2 Basic persona details

- **Platform engineer**: Needs historical winner/latency trends for governance.
- **Applied AI developer**: Needs quick reruns from prior prompts.
- **Security lead**: Needs configurable transition from local secrets to Key Vault.

### 3.3 Role-based access

- **Local app user**: Full access to persistence, leaderboard, and prompt memory in single-user mode.

## 4. Functional requirements

- **Cosmos DB persistence** (Priority: High)
  - Add `feature_persistence_cosmos` flag.
  - Store arena result records with flat schema fields:
    - `arena_id`, `timestamp`, `prompt_hash`, `prompt_text` (optional), `models_compared`, `winner`, `elimination_reasons`, `inspector_flags_used`, `model_version`, `deployment_name`, `latency`, `token_usage`.
  - Use official `azure.cosmos.CosmosClient` SDK.

- **Arena leaderboard** (Priority: High)
  - Add `feature_arena_leaderboard` flag.
  - Aggregate historical records in Python and display wins, win rate, average latency, and task count.

- **Prompt memory** (Priority: High)
  - Add `feature_prompt_memory_enabled` flag.
  - If Cosmos persistence enabled, store and fetch prompt history from Cosmos.
  - Otherwise store prompt history in local JSON file.
  - Support prompt-history dropdown and rerun action.

- **Key Vault toggle** (Priority: High)
  - Add `feature_keyvault_enabled` flag.
  - If true, load secrets via `DefaultAzureCredential` + Key Vault.
  - If false, load from `.env` as current behavior.

- **Data quality and compatibility** (Priority: Medium)
  - Keep storage schema flat and query-friendly.
  - Maintain backward compatibility when optional fields are missing.

## 5. User experience

### 5.1 Entry points and first-time user flow

- User enables persistence and/or prompt memory flags.
- If Key Vault is enabled, app validates secret resolution at startup.
- Leaderboard tab appears only when persistence data is available.

### 5.2 Core experience

- **Run and persist arena**: User completes arena; app writes result record automatically.
  - Builds historical traceability with minimal user effort.
- **Review leaderboard**: User opens leaderboard to compare historical winners.
  - Supports data-backed model decisions.
- **Reuse prompt memory**: User selects prior prompt from history and reruns.
  - Shortens iteration loop and improves reproducibility.
- **Switch secret source**: User toggles Key Vault mode for secure environments.
  - Enables progressive security maturity without app rewrite.

### 5.3 Advanced features and edge cases

- If Cosmos is unavailable, app shows non-blocking persistence warning and continues session flow.
- If local JSON prompt store is missing/corrupt, app recreates it and logs user-facing warning.
- Duplicate prompts can be deduplicated by prompt hash while preserving latest timestamp.

### 5.4 UI/UX highlights

- Lightweight leaderboard table with sortable key metrics.
- Prompt history dropdown with last-used timestamp label.
- Clear status badge showing active secret source (`.env` or Key Vault).

## 6. Narrative

A platform engineer tracks weekly model performance and sees one deployment steadily losing win rate. An AI developer reuses high-signal prompts from memory to verify the trend. Meanwhile, the security lead enables Key Vault-backed secrets in a controlled environment, keeping the same user workflow while improving secret hygiene.

## 7. Success metrics

### 7.1 User-centric metrics

- At least 70% of users rerun saved prompts instead of manually re-entering text.
- Leaderboard is consulted in at least 50% of arena sessions after first week of release.
- Users can recover from persistence outages without losing current-session functionality.

### 7.2 Business metrics

- Improved consistency of selected winner models across repeated task categories.
- Reduced time spent compiling manual performance reports.

### 7.3 Technical metrics

- Persistence write success rate above 99% when Cosmos is reachable.
- Leaderboard query/render time under 2 seconds for 10,000 records.
- Prompt-memory load time under 500 ms for 1,000 saved prompts.

## 8. Technical considerations

### 8.1 Integration points

- `src/config.py` for feature toggles and secret-source branching.
- New `src/persistence.py` for Cosmos and local storage adapters.
- `src/app.py` for leaderboard UI and prompt-history controls.
- Existing inference and inspector outputs as source data for persisted records.

### 8.2 Data storage and privacy

- Prompt text persistence is optional; prompt hash is default-safe identifier.
- Persisted records should avoid secrets and sensitive environment values.
- Local JSON fallback path should be documented and permission-aware.

### 8.3 Scalability and performance

- Cosmos partitioning should support efficient winner and timestamp queries.
- Aggregation can start in Python; move to pre-aggregated views only if needed.
- Use bounded history fetch for UI responsiveness.

### 8.4 Potential challenges

- Cosmos schema drift during iterative rollout.
- Key Vault latency or managed identity misconfiguration.
- Consistency between local fallback and Cosmos-backed records.

## 9. Milestones and sequencing

### 9.1 Project estimate

- Medium to Large: 1 week implementation + 1 week hardening and operational testing.

### 9.2 Team size and composition

- 1 Python developer.
- 1 cloud engineer (part-time) for Cosmos/Key Vault setup.
- 1 QA reviewer for data integrity scenarios.

### 9.3 Suggested phases

- **Phase 1 — Week 3 delivery** (5 days)
  - Cosmos persistence, leaderboard aggregation, prompt memory fallback, Key Vault toggle.
  - Key deliverables: historical records, leaderboard UI, reusable prompt history.
- **Phase 2 — Post-week stabilization** (next 5 days)
  - Retry logic, schema validation, diagnostics, and failure recovery hardening.
  - Key deliverables: robust persistence under intermittent cloud failures.
- **Phase 3 — Extended roadmap** (following 1–2 weeks)
  - Governance reporting, retention controls, and broader test coverage.
  - Key deliverables: enterprise-ready operations baseline.

## 10. User stories

### 10.1 Persist arena outcomes to Cosmos

- **ID**: GH-W3-001
- **Description**: As a user, I want each completed arena stored so that I can analyze historical model behavior.
- **Acceptance criteria**:
  - With `feature_persistence_cosmos=true`, completion of an arena writes one or more records to Cosmos.
  - Persisted schema includes all required flat fields from the spec.
  - Persistence failures are surfaced as non-blocking warnings.

### 10.2 View leaderboard metrics

- **ID**: GH-W3-002
- **Description**: As a user, I want a leaderboard of historical winners so that I can identify consistently strong deployments.
- **Acceptance criteria**:
  - With `feature_arena_leaderboard=true`, leaderboard shows wins, win rate, average latency, and task count.
  - Metrics are computed from persisted data and refresh on demand.

### 10.3 Reuse prompt memory with fallback

- **ID**: GH-W3-003
- **Description**: As a user, I want prompt history and rerun capability so that repeated evaluations are faster.
- **Acceptance criteria**:
  - With `feature_prompt_memory_enabled=true`, prompt history dropdown is visible.
  - If Cosmos persistence is active, prompt history comes from Cosmos; otherwise from local JSON.
  - Selecting a history item pre-fills prompt and allows rerun.

### 10.4 Toggle secret source to Key Vault

- **ID**: GH-W3-004
- **Description**: As a security-conscious user, I want to load secrets from Key Vault when enabled so that credentials are managed centrally.
- **Acceptance criteria**:
  - With `feature_keyvault_enabled=true`, app resolves required secrets via `DefaultAzureCredential` and Key Vault.
  - With flag disabled, app uses existing `.env` path.
  - Startup errors clearly indicate missing Key Vault configuration without exposing secret values.

### 10.5 Preserve functionality during cloud outages

- **ID**: GH-W3-005
- **Description**: As a user, I want the app to remain usable when Cosmos or Key Vault is temporarily unavailable so that evaluation work can continue.
- **Acceptance criteria**:
  - Arena execution and result display continue when persistence write fails.
  - Prompt memory falls back to local JSON when configured and possible.
  - User-visible warnings explain degraded mode.

### 10.6 Enforce baseline privacy and data minimization

- **ID**: GH-W3-006
- **Description**: As a product owner, I want persisted data to avoid secret leakage and support privacy controls.
- **Acceptance criteria**:
  - No API keys or secret values are written to Cosmos or local JSON.
  - Prompt text storage is configurable (optional) with safe default behavior.
  - Record schema remains flat for auditable querying.
