# PRD: Azure Foundry LLM Arena

## 1. Product overview

### 1.1 Document title and version

- PRD: Azure Foundry LLM Arena
- Version: 0.1

### 1.2 Product summary

Azure Foundry LLM Arena is a local developer tool that enables side-by-side comparison of multiple large language model deployments hosted on a single Azure AI Foundry resource. Users enter a single text prompt, and the tool sends it to up to five selected model deployments simultaneously, presenting the outputs, token usage, estimated cost, and latency in a comparative column layout.

The project solves a practical problem: choosing the best-value model for a given task. Developers use it to evaluate output quality across deployments, while managers and decision-makers use it to compare pricing, budget impact, and demonstrate Azure AI capabilities. The tool runs entirely locally, authenticates via environment-variable API keys, and requires no infrastructure beyond a Python environment with Streamlit.

This PRD covers the MVP scope only. The MVP auto-discovers deployments at startup, supports single-prompt comparison, isolates per-model failures, and allows exporting the chosen best model's configuration as a reusable JSON file.

## 2. Goals

### 2.1 Business goals

- Reduce time spent manually testing individual model deployments by consolidating comparison into a single workflow.
- Provide transparent cost and performance data to support informed procurement and budgeting decisions.
- Serve as a lightweight demo tool showcasing Azure AI Foundry capabilities to internal stakeholders.

### 2.2 User goals

- Quickly compare output quality, latency, and cost across multiple Azure AI Foundry model deployments.
- Select the best model for a specific task and export its configuration for downstream use.
- Get started with zero configuration beyond two environment variables.

### 2.3 Non-goals

- Multi-resource or multi-subscription support (only one Azure AI Foundry resource in MVP).
- User authentication or multi-tenancy — the app runs locally for a single user.
- Markdown rendering or rich output formatting in the UI.
- Persistent storage of prompts, results, or history.
- Automated or scheduled benchmarking runs.
- Deployment or hosting of the tool as a shared web service.

## 3. User personas

### 3.1 Key user types

- Developers evaluating which model deployment best suits a specific AI task.
- Technical managers and decision-makers comparing cost, budget impact, and model capabilities.

### 3.2 Basic persona details

- **Dev — the AI developer**: A software engineer integrating Azure AI into an application. They need to test multiple models with representative prompts and pick the one that balances quality and cost. They are comfortable with environment variables, Python, and CLI tools.
- **Mia — the technical manager**: A team lead or engineering manager responsible for budget. She wants to see side-by-side cost and latency data to justify model selection decisions to leadership and demonstrate Azure AI capabilities in business reviews.

### 3.3 Role-based access

- **Local user**: Full access to all features. The app does not implement roles — it is a single-user, locally-run tool. Access is implicitly controlled by possession of the API key in the environment.

## 4. Functional requirements

- **Authentication and initialization** (Priority: High)
  - The app must read `AZURE_FOUNDRY_ENDPOINT` and `AZURE_FOUNDRY_API_KEY` from environment variables at startup.
  - If either variable is missing, the app must fail immediately with a clear, descriptive error message.
  - The app must initialize SDK clients using the loaded credentials: Azure AI Foundry/Projects SDK for discovery and Azure AI Inference SDK for model calling.

- **Deployment discovery** (Priority: High)
  - On startup, the app must connect to the configured Foundry resource and retrieve all available deployments.
  - For each deployment, the app must store: deployment name, model name (if available), model type (chat, completion, etc.), and any relevant metadata.
  - The app must filter deployments to include only text-based inference models, excluding non-compatible types.

- **Model selection** (Priority: High)
  - The UI must present a multi-select dropdown populated with discovered deployments.
  - The user must be able to select between 1 and 5 deployments.
  - Upon selection, the UI must dynamically create one output column per selected deployment.

- **Prompt input and execution** (Priority: High)
  - The UI must provide a text input area for a single prompt.
  - On submission, the app must send the identical prompt to every selected deployment in sequence.
  - For each deployment call, the app must capture start and end timestamps to calculate latency.

- **Results display** (Priority: High)
  - Each model column must display: deployment name, raw text output, input token count, output token count, total token count, estimated cost, latency in milliseconds, and an error message if the call failed.
  - No Markdown parsing or rich rendering is required — raw text output is shown as-is.

- **Cost calculation** (Priority: High)
  - Cost must be calculated locally using token counts returned by the SDK and a static pricing configuration (JSON file or internal dictionary).
  - Pricing structure must map model names to input and output cost per 1,000 tokens.
  - Formula: `cost = (input_tokens / 1000 × input_price) + (output_tokens / 1000 × output_price)`.

- **Latency measurement** (Priority: High)
  - For each deployment call, the app must record the request start timestamp and response timestamp.
  - Latency in milliseconds must be computed and displayed in the corresponding column.

- **Failure isolation** (Priority: High)
  - If a deployment call fails, the error message must be displayed in that deployment's column.
  - Failures in one deployment must not affect other deployments — the remaining calls must continue and display results normally.
  - The app must never crash globally due to a single deployment failure.

- **Export best model configuration** (Priority: Medium)
  - After viewing results, the user must be able to select one model as "Best."
  - The user must be able to click an "Export Configuration" button to download a JSON file.
  - The exported JSON must include: `endpoint`, `deployment_name`, `api_type` (set to `azure_foundry`), `inference_type` (e.g., `chat`), `model_name`, `pricing_reference`, and `export_timestamp`.
  - The API key must never be included in the exported file.

## 5. User experience

### 5.1 Entry points and first-time user flow

- The user sets two environment variables (`AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_API_KEY`) and launches the Streamlit app from the terminal.
- On first load, the app validates credentials and auto-discovers deployments. If environment variables are missing, a clear error message is shown and the app does not proceed.
- Once deployments are loaded, the main interface is immediately ready for use — no onboarding wizard or additional setup.

### 5.2 Core experience

- **Step 1 — Select models**: The user picks 1–5 deployments from the multi-select dropdown. The UI dynamically adjusts to show the corresponding number of output columns.
- **Step 2 — Enter prompt**: The user types or pastes a prompt into the text input area and clicks "Submit."
- **Step 3 — Review results**: All selected models process the prompt. Results appear side-by-side, showing output text, token counts, cost, and latency for instant comparison.
- **Step 4 — Export (optional)**: The user selects the preferred model and exports its configuration as a JSON file for downstream use.

### 5.3 Advanced features and edge cases

- If zero deployments are discovered (e.g., empty resource), the app must display a clear message explaining no compatible deployments were found.
- If the user selects more than 5 deployments, the UI must prevent submission or enforce the limit.
- If all selected deployments fail, each column shows its respective error; the app remains usable.
- Network timeouts or SDK errors must be caught and surfaced per-column, not as global exceptions.

### 5.4 UI/UX highlights

- Clean Streamlit layout with a sidebar or top section for model selection and prompt input.
- Dynamic column rendering — columns appear and disappear based on the number of selected models.
- Each column is self-contained: deployment name as header, output text, metrics, and error state.
- Minimal chrome — the focus is on the comparison data, not decorative UI elements.

## 6. Narrative

Dev has been asked to integrate an AI assistant into the company's customer-support tool. The team has access to an Azure AI Foundry resource with half a dozen model deployments — GPT-4o, GPT-4o-mini, Phi, and several others. Rather than writing bespoke test scripts for each, Dev launches Azure Foundry LLM Arena, selects three candidate models, and pastes in a representative support-ticket prompt. Within seconds, the tool shows that GPT-4o delivers the highest quality answer but at 3× the cost of GPT-4o mini, which produces an acceptable response at a fraction of the price. Dev selects GPT-4o mini as the best model, exports the configuration JSON, and hands it to the integration team. Mia reviews the cost data in a budget meeting, confirms the selection fits within quarterly spend targets, and greenlights the rollout — all based on a five-minute session with the Arena.

## 7. Success metrics

### 7.1 User-centric metrics

- Time from app launch to first comparison result is under 30 seconds (excluding model inference time).
- Users can complete a full compare-and-export workflow in under 2 minutes.
- Error messages are actionable — the user can identify and resolve the issue without consulting documentation.

### 7.2 Business metrics

- The tool replaces ad-hoc manual testing, reducing model evaluation effort from hours to minutes.
- Exported configurations are directly usable in downstream integration, eliminating manual config authoring.

### 7.3 Technical metrics

- Deployment discovery completes within 5 seconds of app startup on a typical connection.
- Latency measurement accuracy is within ±50 ms of the actual network round-trip.
- The app handles up to 5 concurrent model calls without UI freezing or crashes.
- Zero data leakage — API key never appears in UI, logs, or exported files.

## 8. Technical considerations

### 8.1 Integration points

- **Azure AI Foundry/Projects SDK (Python)**: Used for authentication and deployment discovery.
- **Azure AI Inference SDK (Python)**: Used for model calling (chat/completions) and token usage capture.
- **Environment variables**: `AZURE_FOUNDRY_ENDPOINT` and `AZURE_FOUNDRY_API_KEY` are the sole external configuration inputs.
- **Streamlit**: Serves as the UI framework, handling user input, dynamic layout, and data presentation.

### 8.2 Data storage and privacy

- No persistent data storage — all prompt data, results, and metrics exist in memory only for the duration of the session.
- The API key is never stored, displayed, logged, or exported.
- The endpoint URL may be exported as it is considered non-sensitive.
- The static pricing configuration is stored locally as a JSON file or in-code dictionary.

### 8.3 Scalability and performance

- MVP is designed for single-user, local execution only — no server-side scaling concerns.
- Inference calls are made sequentially per deployment; parallel execution is not required for MVP.
- Performance is bounded by the Azure AI Foundry API response times.

### 8.4 Potential challenges

- **Deployment filtering accuracy**: The SDK may return deployment types that are not straightforward to categorize; robust filtering logic will be needed.
- **Pricing data staleness**: The static pricing config must be manually updated when Azure pricing changes or new models are added.
- **SDK rate limiting**: Sending multiple inference requests in rapid succession may trigger rate limits on the Foundry resource.
- **Token count availability**: Some deployment types may not return token usage metadata; the app must handle missing data gracefully.
- **Streamlit state management**: Dynamic column creation and multi-model state tracking in Streamlit require careful session-state handling.

## 9. Milestones and sequencing

### 9.1 Project estimate

- Small: approximately 5–7 working days for a solo developer using agentic development tooling.

### 9.2 Team size and composition

- 1 developer (full-stack Python / Streamlit) handling all implementation, testing, and documentation.

### 9.3 Suggested phases

- **Phase 1 — Foundation** (Days 1–2)
  - Project scaffolding, dependency setup, environment config loading.
  - Azure AI Foundry/Projects SDK authentication and deployment discovery.
  - Key deliverables: working SDK client, deployment list printed to console.

- **Phase 2 — Core UI and execution** (Days 3–4)
  - Streamlit app with model selection dropdown and prompt input.
  - Azure AI Inference SDK model-calling execution loop with latency measurement.
  - Side-by-side results display with token counts and raw output.
  - Key deliverables: end-to-end prompt-to-results workflow in the UI.

- **Phase 3 — Cost, errors, and export** (Days 5–6)
  - Cost calculation engine with static pricing configuration.
  - Per-deployment failure isolation and error display.
  - "Best model" selection and JSON configuration export.
  - Key deliverables: complete MVP feature set.

- **Phase 4 — Polish and documentation** (Day 7)
  - Edge case hardening (missing deployments, network errors, empty responses).
  - README update with setup instructions and usage guide.
  - Key deliverables: release-ready MVP.

## 10. User stories

### 10.1 Load credentials from environment

- **ID**: GH-001
- **Description**: As a developer, I want the app to load the Azure AI Foundry endpoint and API key from environment variables so that I can start the tool without hardcoding secrets.
- **Acceptance criteria**:
  - The app reads `AZURE_FOUNDRY_ENDPOINT` and `AZURE_FOUNDRY_API_KEY` from environment variables on startup.
  - If either variable is missing, the app exits immediately with a clear error message naming the missing variable.
  - The API key is never displayed in the UI, logged, or written to any file.

### 10.2 Auto-discover deployments

- **ID**: GH-002
- **Description**: As a developer, I want the app to automatically discover all available model deployments from my Azure AI Foundry resource so that I do not have to manually configure model names.
- **Acceptance criteria**:
  - On startup, the app connects to the Foundry resource and retrieves all deployments.
  - Each deployment's name, model name, and model type are stored.
  - Only text-based inference models are included; incompatible types are filtered out.
  - If no compatible deployments are found, a clear message is displayed.

### 10.3 Select models for comparison

- **ID**: GH-003
- **Description**: As a developer, I want to select between 1 and 5 model deployments from a dropdown so that I can choose which models to compare.
- **Acceptance criteria**:
  - A multi-select dropdown lists all discovered deployments.
  - The user can select a minimum of 1 and a maximum of 5 deployments.
  - The UI dynamically creates one output column per selected deployment.
  - If the user attempts to select more than 5, the selection is prevented or the user is warned.

### 10.4 Submit prompt to selected models

- **ID**: GH-004
- **Description**: As a developer, I want to enter a text prompt and send it to all selected deployments at once so that I can compare their outputs on the same input.
- **Acceptance criteria**:
  - The UI provides a text input area for the prompt.
  - Clicking "Submit" sends the identical prompt to each selected deployment.
  - Results are displayed once all deployments have responded (or timed out).

### 10.5 Display side-by-side results

- **ID**: GH-005
- **Description**: As a developer, I want to see each model's output, token usage, cost, and latency in a side-by-side column layout so that I can quickly compare them.
- **Acceptance criteria**:
  - Each column displays: deployment name, raw text output, input tokens, output tokens, total tokens, estimated cost, and latency in milliseconds.
  - Output is displayed as raw text without Markdown rendering.
  - Columns are visually aligned for easy comparison.

### 10.6 Calculate estimated cost

- **ID**: GH-006
- **Description**: As a technical manager, I want to see the estimated cost of each model's response so that I can evaluate budget impact.
- **Acceptance criteria**:
  - Cost is calculated using the formula: `(input_tokens / 1000 × input_price) + (output_tokens / 1000 × output_price)`.
  - Pricing data is loaded from a static local configuration (JSON file or dictionary).
  - If pricing data is unavailable for a model, the cost field displays "N/A" or a clear indication.

### 10.7 Measure and display latency

- **ID**: GH-007
- **Description**: As a developer, I want to see the latency of each model's response in milliseconds so that I can factor response time into my decision.
- **Acceptance criteria**:
  - The app records a timestamp before and after each inference call.
  - Latency is displayed in milliseconds in the corresponding model column.
  - Latency reflects the full round-trip time including network overhead.

### 10.8 Isolate deployment failures

- **ID**: GH-008
- **Description**: As a developer, I want a failed deployment to show an error in its own column without affecting other deployments so that I still get results from the working models.
- **Acceptance criteria**:
  - If a deployment call fails (timeout, error, etc.), the error message is shown in that deployment's column.
  - Other deployment calls continue to execute and display results normally.
  - The app does not crash or show a global error page due to a single deployment failure.

### 10.9 Export best model configuration

- **ID**: GH-009
- **Description**: As a developer, I want to select the best model and export its configuration as a JSON file so that I can reuse it in production integration.
- **Acceptance criteria**:
  - After results are displayed, the user can select one model as "Best."
  - Clicking "Export Configuration" generates and downloads a JSON file.
  - The JSON includes: `endpoint`, `deployment_name`, `api_type`, `inference_type`, `model_name`, `pricing_reference`, and `export_timestamp`.
  - The API key is never included in the exported JSON.

### 10.10 Handle missing deployments gracefully

- **ID**: GH-010
- **Description**: As a developer, I want the app to display a helpful message when no compatible deployments are found so that I understand why I cannot proceed.
- **Acceptance criteria**:
  - If the Foundry resource has no deployments or none pass the text-inference filter, a message is shown explaining the situation.
  - The app remains in a stable state — it does not crash or display an empty dropdown without explanation.

### 10.11 Fail fast on missing environment variables

- **ID**: GH-011
- **Description**: As a developer, I want the app to immediately tell me which environment variable is missing so that I can fix my setup quickly.
- **Acceptance criteria**:
  - If `AZURE_FOUNDRY_ENDPOINT` is missing, the error message explicitly names it.
  - If `AZURE_FOUNDRY_API_KEY` is missing, the error message explicitly names it.
  - No partial initialization occurs — the app stops before attempting SDK calls.
