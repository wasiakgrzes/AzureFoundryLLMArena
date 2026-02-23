# Naming Convention for Feature Flags

All new features follow the naming convention:

```
feature_<domain>_<capability>
```

## Examples:

- `feature_arena_elimination`
- `feature_inspector_json_validation`
- `feature_persistence_cosmos`
- `feature_prompt_memory_enabled`

Flags must be configurable via:

- **.env**
- **Azure Key Vault** (when enabled)
- **Optional UI toggle** (if appropriate)

---

# WEEK 1 — Arena Engine + Elimination Logic

## You already have:

- Select 2–5 Foundry deployments
- Submit single prompt
- Display side-by-side responses

Now we formalize Arena behavior.

### 🔹 Feature 1: Arena Elimination Flow

**Flag:** `feature_arena_elimination`

#### User Story

As a user,  
I want to eliminate models after each round  
so that I can progressively narrow down to a winner.

#### Acceptance Criteria

After responses are shown:

- Each model has a “Select as Winner” checkbox.
- User must select at least 1.
- Unselected models are eliminated.
- Survivors proceed to next round.
- “Reset Arena” button available.
- Current round number displayed.
- Final winner banner displayed when 1 model remains.

#### Technical Design

Maintain state in `st.session_state`:

- `arena_round`
- `arena_active_models`
- `arena_eliminated_models`

No database persistence yet.

#### SDK Usage

Continue using official Azure AI Inference SDK:

```python
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
```

All calls must route through:

```
ModelRunner.run(deployment_name, prompt)
```

### 🔹 Feature 2: Arena Metrics Panel (Without Cost Estimation)

**Flag:** `feature_arena_metrics_panel`

#### User Story

As a user,  
I want to see objective metadata for each response  
so that I can consider latency and token usage in my decision.

#### Acceptance Criteria

Display per model:

- Latency (measured client-side)
- Input tokens
- Output tokens
- Model name
- Deployment name

**Cost Estimation**

Do NOT estimate cost dynamically. Instead:

Add:

**Flag:** `feature_arena_cost_display`

If enabled:

Show static placeholder:

> “Cost estimation not available via SDK — see pricing page.”

This is transparent and technically correct.

---

# Week 1 Deliverable

- Arena elimination system fully functional with metadata panel.
- No inspectors yet.

---

# WEEK 2 — Output Inspector System

This is your differentiator.

## Design Decision: Inspector Architecture

You asked:

**One inspector model or multiple?**

### Recommendation:

Single inspector model call per response.

#### Reason:

Deterministic checks handled locally.  
Only semantic checks use LLM.  
Avoid multiple Foundry calls per response.

### 🔹 Feature 3: Inspector Activation

**Flag:** `feature_inspector_enabled`

If disabled: No inspection performed.

If enabled: Inspector panel becomes visible.

### 🔹 Feature 4: Output Format Validation

**Flags:**

- `feature_inspector_validate_json`
- `feature_inspector_validate_markdown`
- `feature_inspector_validate_xml`

#### User Story

As a user,  
I want to validate output structure  
so that I can verify format compliance.

#### Acceptance Criteria

If JSON selected:

- Attempt `json.loads`
- Highlight:
  - Valid JSON → green badge
  - Invalid JSON → red badge

If "no additional comments" selected:

- Detect text before/after JSON block

**Markdown:**

- Basic heading/list structure validation

**XML:**

- Parse with `xml.etree.ElementTree`

No LLM required for structural validation.

### 🔹 Feature 5: Required Field Enforcement

**Flag:** `feature_inspector_required_fields`

#### User Story

As a user,  
I want to require specific fields in the output  
so that structured outputs are production-ready.

#### Acceptance Criteria

User inputs field name(s).

If JSON:

- Verify key existence.
- Highlight:
  - Found → green
  - Missing → red

### 🔹 Feature 6: No Additional Comments

**Flag:** `feature_inspector_no_extra_text`

If enabled:

- Ensure output contains only structured block.
- Any prefix/suffix text → red highlight.

### 🔹 Feature 7: Tone & Persona Adherence

**Flags:**

- `feature_inspector_tone_check`
- `feature_inspector_persona_check`

#### User Story

As a user,  
I want to verify tone and persona adherence  
so that the output aligns with project style requirements.

#### Implementation

This requires LLM evaluation.

Inspector model selection:

- Dropdown: choose one Foundry deployment.  
- Stored in session.

Single inspector call per model response.

**Inspector prompt:**

> Analyze the following response:  
> - Does it match requested tone?  
> - Does it follow requested persona?  
> Return structured JSON:
```json
{
  "tone_match": true/false,
  "persona_match": true/false,
  "reason": ""
}
```

No scoring.  
Binary evaluation.

### 🔹 Feature 8: Output Highlight Layer

**Flag:** `feature_inspector_highlighting`

#### User Story

As a user,  
I want visual highlights  
so that violations are instantly visible.

#### Implementation

- Red for violations
- Green for validated sections
- Blue for informational notes

Use simple HTML injection in Streamlit:

```python
st.markdown(rendered_html, unsafe_allow_html=True)
```

---

# Week 2 Deliverable

- Inspector toggle system
- Structural validation
- Required field check
- Tone/persona LLM check
- Visual highlighting
- Single inspector model selection

Arena now becomes intelligent without paperwork.

---

# WEEK 3 — Persistence + Prompt Memory + Azure Maturity

### 🔹 Feature 9: Cosmos DB Persistence

**Flag:** `feature_persistence_cosmos`

#### User Story

As a user,  
I want arena results stored historically  
so that I can analyze model drift and performance over time.

#### SDK

Use official:

```python
from azure.cosmos import CosmosClient
```

#### Stored Fields

- `arena_id`
- `timestamp`
- `prompt_hash`
- `prompt_text` (optional)
- `models_compared`
- `winner`
- `elimination_reasons`
- `inspector_flags_used`
- `model_version`
- `deployment_name`
- `latency`
- `token_usage`

Keep schema flat and simple.

### 🔹 Feature 10: Arena Leaderboard

**Flag:** `feature_arena_leaderboard`

#### User Story

As a user,  
I want to see historical winners  
so that I can identify consistently strong models.

#### Display:

- Wins
- Win rate
- Avg latency
- Task count

Aggregation done in Python.

### 🔹 Feature 11: Prompt Memory

**Flag:** `feature_prompt_memory_enabled`

#### User Story

As a user,  
I want previous prompts saved  
so that I can reuse and re-run evaluations.

#### Storage Options

If Cosmos enabled:

- Store in Cosmos

Else:

- Local JSON file

#### Features:

- Prompt history dropdown
- Re-run previous arena

### 🔹 Feature 12: Key Vault Toggle

**Flag:** `feature_keyvault_enabled`

#### Behavior

If true:

- Use `azure.identity.DefaultAzureCredential`
- Load secrets from Key Vault

If false:

- Load from .env

Clean separation.

---

# Final Architecture

```
UI
  ↓
Arena Controller
  ↓
Model Runner (Azure AI Inference SDK)
  ↓
Inspector Engine (Local + LLM)
  ↓
Cosmos Persistence (Optional)
  ↓
Leaderboard + Prompt Memory
```