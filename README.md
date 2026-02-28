# Azure Foundry LLM Arena

Azure Foundry LLM Arena is a local Streamlit tool for comparing multiple Microsoft Foundry (formerly Azure AI Foundry) deployments side by side with one shared prompt.

## What it does

- Discovers text-compatible deployments from one Azure AI Foundry resource.
- Sends the same prompt to selected deployments (1–5).
- Displays raw output, token usage, estimated cost, and latency per deployment.
- Isolates failures so one deployment error does not break the whole run.
- Exports the selected best model configuration as JSON (without secrets).

## Prerequisites

- Python 3.11+
- A Microsoft Foundry resource with model deployments
- API key access to the resource

## Installation

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables (via shell or `.env` file):

```env
AZURE_FOUNDRY_ENDPOINT=https://<your-foundry-endpoint>
AZURE_FOUNDRY_API_KEY=<your-api-key>
AZURE_FOUNDRY_DEPLOYMENTS=DeepSeek-V3.2,gpt-5-mini,Mistral-Large-3
```

For API-key inference endpoints that do not expose deployment listing APIs, set `AZURE_FOUNDRY_DEPLOYMENTS` (comma-separated) so the app can load your deployments. You can also set `DEPLOYMENT_NAME` for a single deployment fallback.

### Feature flags

```env
FEATURE_ARENA_ELIMINATION=false
FEATURE_ARENA_METRICS_PANEL=false
FEATURE_ARENA_COST_DISPLAY=false
FEATURE_INSPECTOR_ENABLED=false
FEATURE_INSPECTOR_VALIDATE_JSON=false
FEATURE_INSPECTOR_VALIDATE_MARKDOWN=false
FEATURE_INSPECTOR_VALIDATE_XML=false
FEATURE_INSPECTOR_REQUIRED_FIELDS=false
FEATURE_INSPECTOR_NO_EXTRA_TEXT=false
FEATURE_INSPECTOR_TONE_CHECK=false
FEATURE_INSPECTOR_PERSONA_CHECK=false
FEATURE_INSPECTOR_HIGHLIGHTING=false
```

- `FEATURE_ARENA_ELIMINATION=true` enables tournament-style elimination rounds.
- `FEATURE_ARENA_METRICS_PANEL=true` shows per-model metrics (model name, latency, token usage).
- `FEATURE_ARENA_COST_DISPLAY=true` shows the static transparency note: `Cost estimation not available via SDK — see pricing page`.
- `FEATURE_INSPECTOR_ENABLED=true` enables the Output Inspector panel.
- `FEATURE_INSPECTOR_VALIDATE_JSON|MARKDOWN|XML=true` enables deterministic format checks for the selected format.
- `FEATURE_INSPECTOR_REQUIRED_FIELDS=true` enables required top-level JSON key checks.
- `FEATURE_INSPECTOR_NO_EXTRA_TEXT=true` detects prefix/suffix text outside the structured block.
- `FEATURE_INSPECTOR_TONE_CHECK=true` and/or `FEATURE_INSPECTOR_PERSONA_CHECK=true` enables semantic checks via one inspector model call per response.
- `FEATURE_INSPECTOR_HIGHLIGHTING=true` enables color-coded inspector summaries in result cards.

## Run the app

```bash
streamlit run src/app.py
```

## Usage flow

1. Launch the app.
2. Select 1–5 deployments in the sidebar.
3. Enter a prompt.
4. Click **Submit** to run inference.
5. Compare results side by side.
6. Select a best model and download `best_model_config.json`.

## Arena Elimination Mode

When `FEATURE_ARENA_ELIMINATION=true`:

1. Select 2–5 deployments and submit a prompt.
2. Round results are displayed with winner checkboxes for successful responses.
3. Click **Proceed to Next Round** to eliminate unselected models.
4. Repeat until one model remains.
5. Use **Reset Arena** at any time to restart the tournament.

Behavior notes:
- Proceed is blocked when no winner is selected.
- If all responses fail in a round, advancement is blocked and reset is required.
- If only one model remains, arena auto-completes and displays the winner banner.

## Output Inspector System

When `FEATURE_INSPECTOR_ENABLED=true`:

1. Open **Output Inspector** in the sidebar.
2. Choose validation format (`json`, `markdown`, or `xml`).
3. Optionally configure required fields and no-extra-text checks.
4. Optionally configure expected tone/persona and select an inspector deployment.
5. Submit prompt and review per-model check badges.

Inspector checks:
- Structural checks (local): JSON, Markdown, XML parsing heuristics.
- Required fields (local): top-level JSON keys only.
- No-extra-text (local): prefix/suffix detection outside JSON/XML block.
- Semantic checks (model-assisted): tone/persona adherence with structured reason text.

Behavior and failure handling:
- Inspector failures are non-blocking; arena results still render.
- Empty outputs return structured failures instead of raw exceptions.
- Invalid JSON with required fields configured returns `not_evaluated` field status.
- Local checks still run when semantic checks fail.

Security notes:
- Highlight rendering escapes model output before HTML rendering.
- Inspector prompts do not include API keys or runtime secrets.

Current limitations:
- Markdown structure and no-extra-text checks are heuristic-based.
- Semantic checks add latency proportional to number of model responses.
- Inspector results are not persisted across app restarts.

## Project structure

```
src/
	app.py            # Streamlit UI and orchestration
	config.py         # Environment loading and validation
	client.py         # AIProjectClient initialization
	discovery.py      # Deployment discovery and filtering
	inference.py      # Inference execution and error isolation
	inspector.py      # Output Inspector checks and semantic inspection helpers
	pricing.py        # Pricing load + cost calculator
	export.py         # Best-model export JSON generation
	model_pricing.json
tests/
	sanity_checks/
```

## Pricing configuration

- Pricing data is stored in `src/model_pricing.json`.
- Values are expected as USD cost per 1,000 tokens:
	- `input_per_1k`
	- `output_per_1k`
- To update pricing, edit model entries in `src/model_pricing.json`.

## Known limitations

- Single Microsoft Foundry resource per run.
- Static pricing file (manual updates required).
- No persistence of prompt history, results, or arena state across app restarts.
- Sequential inference execution (no parallel fan-out).
- Local-only app; no CI/CD or hosted deployment in MVP.
- Arena flow supports up to 5 selected deployments.
