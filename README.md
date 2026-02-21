# Azure Foundry LLM Arena

Azure Foundry LLM Arena is a local Streamlit tool for comparing multiple Azure AI Foundry deployments side by side with one shared prompt.

## What it does

- Discovers text-compatible deployments from one Azure AI Foundry resource.
- Sends the same prompt to selected deployments (1–5).
- Displays raw output, token usage, estimated cost, and latency per deployment.
- Isolates failures so one deployment error does not break the whole run.
- Exports the selected best model configuration as JSON (without secrets).

## Prerequisites

- Python 3.11+
- An Azure AI Foundry resource with model deployments
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

For API-key inference endpoints that do not expose deployment listing APIs, set `AZURE_FOUNDRY_DEPLOYMENTS` (comma-separated) so the app can load your deployments.

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

## Project structure

```
src/
	app.py            # Streamlit UI and orchestration
	config.py         # Environment loading and validation
	client.py         # AIProjectClient initialization
	discovery.py      # Deployment discovery and filtering
	inference.py      # Inference execution and error isolation
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

- Single Azure AI Foundry resource per run.
- Static pricing file (manual updates required).
- No persistence of prompt history or results.
- Sequential inference execution (no parallel fan-out).
- Local-only app; no CI/CD or hosted deployment in MVP.
