from typing import Any

import streamlit as st

try:
	from src.client import create_client
	from src.config import load_config
	from src.discovery import discover_deployments
	from src.export import generate_export_config
	from src.inference import run_batch_inference
	from src.pricing import calculate_cost
except ModuleNotFoundError:
	from client import create_client
	from config import load_config
	from discovery import discover_deployments
	from export import generate_export_config
	from inference import run_batch_inference
	from pricing import calculate_cost


MAX_SELECTION = 5
PRICING_ENABLED = False


def _deployment_names(deployments: list[dict]) -> list[str]:
	return [str(item.get("deployment_name", "unknown")) for item in deployments]


def _selected_deployments(
	deployments: list[dict], selected_names: list[str]
) -> list[dict]:
	selected_set = set(selected_names)
	return [
		deployment
		for deployment in deployments
		if str(deployment.get("deployment_name", "unknown")) in selected_set
	]


def _is_submit_disabled(selected_names: list[str], prompt: str) -> bool:
	return len(selected_names) == 0 or len(selected_names) > MAX_SELECTION


def _format_token_value(value: Any) -> str:
	if value is None:
		return "N/A"
	return str(value)


def _format_cost_value(value: Any) -> str:
	if value is None:
		return "N/A"
	return f"${float(value):.4f}"


def _format_latency_value(value: Any) -> str:
	if value is None:
		return "N/A"
	return f"{value} ms"


def _enrich_results_with_cost(results: list[dict]) -> list[dict]:
	enriched: list[dict] = []
	for result in results:
		estimated_cost = calculate_cost(
			result.get("model_name"),
			result.get("input_tokens"),
			result.get("output_tokens"),
		)
		updated_result = dict(result)
		updated_result["estimated_cost"] = estimated_cost
		enriched.append(updated_result)

	return enriched


def _initialize_state() -> None:
	defaults = {
		"config": None,
		"client": None,
		"deployments": None,
		"selected_deployment_names": [],
		"prompt_input": "",
		"submitted_prompt": "",
		"submitted_deployments": [],
		"results": [],
		"best_model_name": None,
	}

	for key, value in defaults.items():
		if key not in st.session_state:
			st.session_state[key] = value


def _load_startup_dependencies() -> None:
	if st.session_state["config"] is None:
		st.session_state["config"] = load_config()

	if st.session_state["client"] is None:
		st.session_state["client"] = create_client(st.session_state["config"])

	if st.session_state["deployments"] is None:
		st.session_state["deployments"] = discover_deployments(
			st.session_state["client"], timeout_seconds=30
		)


def _render_results(results: list[dict]) -> None:
	if not results:
		return

	st.subheader("Results")
	columns = st.columns(len(results))

	for result, column in zip(results, columns):
		with column:
			st.subheader(str(result.get("deployment_name", "unknown")))

			error = result.get("error")
			if error is not None:
				st.error(str(error))
				continue

			output_text = result.get("output_text")
			if output_text is None:
				st.text("")
			elif isinstance(output_text, str) and not output_text.strip():
				st.text("Model returned an empty response")
			else:
				st.text(output_text)

			st.metric("Input Tokens", _format_token_value(result.get("input_tokens")))
			st.metric("Output Tokens", _format_token_value(result.get("output_tokens")))
			st.metric("Total Tokens", _format_token_value(result.get("total_tokens")))
			if PRICING_ENABLED:
				st.metric("Estimated Cost", _format_cost_value(result.get("estimated_cost")))
			st.metric("Latency", _format_latency_value(result.get("latency_ms")))


def _successful_result_candidates(
	results: list[dict], selected_deployments: list[dict]
) -> list[dict]:
	selected_by_name = {
		str(item.get("deployment_name", "unknown")): item for item in selected_deployments
	}

	candidates: list[dict] = []
	for result in results:
		if result.get("error") is not None:
			continue

		deployment_name = str(result.get("deployment_name", "unknown"))
		selected_meta = selected_by_name.get(deployment_name, {})
		model_name = result.get("model_name") or selected_meta.get("model_name") or "unknown"
		model_type = selected_meta.get("model_type") or "unknown"

		candidates.append(
			{
				"deployment_name": deployment_name,
				"model_name": str(model_name),
				"model_type": str(model_type),
			}
		)

	return candidates


def _render_export_section(config: dict, results: list[dict], selected_deployments: list[dict]) -> None:
	if not results:
		return

	candidates = _successful_result_candidates(results, selected_deployments)
	if not candidates:
		return

	st.subheader("Select Best Model")
	option_names = [item["deployment_name"] for item in candidates]

	default_name = st.session_state.get("best_model_name")
	default_index = 0
	if default_name in option_names:
		default_index = option_names.index(default_name)

	selected_name = st.selectbox(
		"Best model deployment",
		options=option_names,
		index=default_index,
	)
	st.session_state["best_model_name"] = selected_name

	selected_candidate = next(
		(item for item in candidates if item["deployment_name"] == selected_name),
		candidates[0],
	)

	json_payload = generate_export_config(
		endpoint=str(config.get("endpoint", "")),
		deployment=selected_candidate,
	)

	st.download_button(
		label="Export Configuration",
		data=json_payload,
		file_name="best_model_config.json",
		mime="application/json",
	)


def main() -> None:
	st.set_page_config(page_title="Azure Foundry LLM Arena", layout="wide", page_icon="🤖")
	st.title("Azure Foundry LLM Arena")

	_initialize_state()

	try:
		_load_startup_dependencies()
	except ValueError as ex:
		st.error(str(ex))
		st.stop()
	except Exception as ex:
		st.error(f"Deployment discovery failed: {str(ex)}")
		st.stop()

	st.caption("Startup status: credentials validated and deployment discovery completed.")

	deployments: list[dict] = st.session_state["deployments"] or []
	deployment_names = _deployment_names(deployments)

	if len(deployments) == 0:
		st.warning("No compatible text-based deployments were found in the configured Foundry resource.")

	with st.sidebar:
		st.subheader("Model Selection")
		selected_names = st.multiselect(
			"Select deployments (1–5)",
			options=deployment_names,
			default=[name for name in st.session_state["selected_deployment_names"] if name in deployment_names],
		)

		st.session_state["selected_deployment_names"] = selected_names

		if len(selected_names) > MAX_SELECTION:
			st.warning("You can select at most 5 deployments.")

		prompt = st.text_area(
			"Prompt",
			value=st.session_state["prompt_input"],
			height=180,
			placeholder="Enter one prompt to compare across selected deployments...",
		)
		st.session_state["prompt_input"] = prompt

		submit_clicked = st.button(
			"Submit",
			disabled=_is_submit_disabled(selected_names, prompt),
			type="primary",
		)

	if submit_clicked:
		if not prompt.strip():
			st.warning("Prompt cannot be empty. Please enter a prompt before submitting.")
			return

		selected_deployments = _selected_deployments(deployments, selected_names)
		st.session_state["submitted_prompt"] = prompt
		st.session_state["submitted_deployments"] = selected_deployments

		with st.spinner("Running inference..."):
			inference_results = run_batch_inference(
				st.session_state["client"], selected_deployments, prompt, timeout_seconds=60
			)
			if PRICING_ENABLED:
				st.session_state["results"] = _enrich_results_with_cost(inference_results)
			else:
				st.session_state["results"] = inference_results

	_render_results(st.session_state.get("results", []))
	_render_export_section(
		config=st.session_state.get("config", {}),
		results=st.session_state.get("results", []),
		selected_deployments=st.session_state.get("submitted_deployments", []),
	)


if __name__ == "__main__":
	main()
