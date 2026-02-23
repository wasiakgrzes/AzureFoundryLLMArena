from typing import Any

import streamlit as st

try:
	from src.arena import (
		advance_round,
		get_active_models,
		get_arena_winner,
		get_current_round,
		get_eliminated_models,
		init_arena,
		is_arena_completed,
		is_arena_initialized,
		reset_arena,
	)
	from src.client import create_client
	from src.config import load_config
	from src.discovery import discover_deployments
	from src.export import generate_export_config
	from src.inference import run_batch_inference
	from src.pricing import calculate_cost
except ModuleNotFoundError:
	from arena import (
		advance_round,
		get_active_models,
		get_arena_winner,
		get_current_round,
		get_eliminated_models,
		init_arena,
		is_arena_completed,
		is_arena_initialized,
		reset_arena,
	)
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


def _selected_deployments_for_active_models(
	deployments: list[dict], active_names: list[str]
) -> list[dict]:
	active_set = set(active_names)
	return [
		deployment
		for deployment in deployments
		if str(deployment.get("deployment_name", "unknown")) in active_set
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
		"arena_prompts": {},
		"arena_continue_by_round": {},
		"arena_conversation_history": {},
		"arena_results_history": {},
		"submitted_prompt": "",
		"submitted_deployments": [],
		"results": [],
		"best_model_name": None,
		"arena_initial_selection": [],
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


def _render_results(results: list[dict], metrics_enabled: bool) -> None:
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

			if metrics_enabled:
				st.caption(f"Model: {str(result.get('model_name') or 'unknown')}")
				st.metric("Input Tokens", _format_token_value(result.get("input_tokens")))
				st.metric("Output Tokens", _format_token_value(result.get("output_tokens")))
				st.metric("Total Tokens", _format_token_value(result.get("total_tokens")))
				if PRICING_ENABLED:
					st.metric("Estimated Cost", _format_cost_value(result.get("estimated_cost")))
				st.metric("Latency", _format_latency_value(result.get("latency_ms")))


def _render_arena_results_history(metrics_enabled: bool) -> None:
	history = st.session_state.get("arena_results_history", {})
	if not history:
		return

	st.subheader("Previous Round Results")
	for round_number in sorted(history.keys(), reverse=True):
		round_payload = history.get(round_number, {})
		round_prompt = str(round_payload.get("prompt", ""))
		round_results = list(round_payload.get("results", []))
		if not round_results:
			continue

		with st.expander(f"Round {round_number}", expanded=False):
			if round_prompt.strip():
				st.caption(f"Prompt: {round_prompt}")
			_render_results(round_results, metrics_enabled=metrics_enabled)


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


def _run_inference_and_store_results(
	client: Any,
	selected_deployments: list[dict],
	prompt: str,
	conversation_history_by_deployment: dict[str, list[dict[str, str]]] | None = None,
) -> None:
	with st.spinner("Running inference..."):
		inference_results = run_batch_inference(
			client,
			selected_deployments,
			prompt,
			conversation_history_by_deployment=conversation_history_by_deployment,
			timeout_seconds=60,
		)

		if PRICING_ENABLED:
			st.session_state["results"] = _enrich_results_with_cost(inference_results)
		else:
			st.session_state["results"] = inference_results


def _render_arena_controls(
	config: dict,
	selected_deployments: list[dict],
	prompt: str,
	results: list[dict],
) -> None:
	if not bool(config.get("feature_arena_elimination", False)):
		return

	if not is_arena_initialized():
		return

	active_models = get_active_models()
	eliminated_models = get_eliminated_models()
	current_round = get_current_round()
	completed = is_arena_completed()
	winner = get_arena_winner()

	st.subheader("Arena")
	st.caption(f"Round {current_round} • Active models: {len(active_models)}")

	if eliminated_models:
		with st.expander("Eliminated"):
			for model_name in eliminated_models:
				st.write(f"- {model_name}")

	if completed and winner:
		st.success(f"Arena winner: {winner}")

	if st.button("Reset Arena", key="arena_reset_button"):
		reset_arena()
		st.session_state["arena_initial_selection"] = []
		st.session_state["arena_prompts"] = {}
		st.session_state["arena_continue_by_round"] = {}
		st.session_state["arena_conversation_history"] = {}
		st.session_state["arena_results_history"] = {}
		st.session_state["prompt_input"] = ""
		st.session_state["results"] = []
		st.session_state["submitted_deployments"] = []
		st.rerun()

	if completed:
		return

	successful_results = [
		result
		for result in results
		if result.get("error") is None
		and str(result.get("deployment_name", "unknown")) in set(active_models)
	]

	if results and not successful_results:
		st.error("All responses failed. Reset arena to try again.")
		return

	if not successful_results:
		return

	with st.form(key=f"arena_round_form_{current_round}"):
		st.write("Select winner(s) to proceed to the next round:")
		checkbox_keys: list[tuple[str, str]] = []
		for result in successful_results:
			deployment_name = str(result.get("deployment_name", "unknown"))
			checkbox_key = f"arena_winner_{current_round}_{deployment_name}"
			st.checkbox(f"Select as Winner — {deployment_name}", key=checkbox_key)
			checkbox_keys.append((deployment_name, checkbox_key))

		proceed_clicked = st.form_submit_button("Proceed to Next Round", type="primary")

	if not proceed_clicked:
		return

	winner_names = [
		deployment_name
		for deployment_name, checkbox_key in checkbox_keys
		if bool(st.session_state.get(checkbox_key, False))
	]

	if not winner_names:
		st.error("Select at least one winner before proceeding")
		return

	try:
		advance_round(winner_names)
	except ValueError as ex:
		st.error(str(ex))
		return

	st.session_state["selected_deployment_names"] = get_active_models()
	st.session_state["results"] = []
	st.session_state["submitted_deployments"] = []
	st.session_state["best_model_name"] = None
	st.session_state["prompt_input"] = ""

	if is_arena_completed():
		st.rerun()

	st.success("Round advanced. Edit prompt if needed, then click Submit to run the next round.")
	st.rerun()


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
	config = st.session_state.get("config", {})
	arena_enabled = bool(config.get("feature_arena_elimination", False))
	metrics_enabled = bool(config.get("feature_arena_metrics_panel", False))
	cost_notice_enabled = bool(config.get("feature_arena_cost_display", False))

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

		prompt = ""
		if arena_enabled:
			arena_prompts = st.session_state.get("arena_prompts", {})
			arena_continue_by_round = st.session_state.get("arena_continue_by_round", {})
			current_round = get_current_round() if is_arena_initialized() else 1

			for round_number in range(1, current_round):
				previous_prompt = str(arena_prompts.get(round_number, ""))
				st.text_area(
					f"Round {round_number} Prompt",
					value=previous_prompt,
					height=120,
					disabled=True,
					key=f"arena_round_prompt_display_{round_number}",
				)
				st.checkbox(
					"Continue previous message thread",
					value=bool(arena_continue_by_round.get(round_number, False)),
					disabled=True,
					key=f"arena_round_continue_display_{round_number}",
				)

			active_prompt = str(arena_prompts.get(current_round, ""))
			prompt = st.text_area(
				f"Round {current_round} Prompt",
				value=active_prompt,
				height=180,
				placeholder=f"Enter prompt for round {current_round}...",
				key=f"arena_round_prompt_input_{current_round}",
			)
			continue_default = bool(arena_continue_by_round.get(current_round, False))
			continue_disabled = current_round == 1
			continue_value = st.checkbox(
				"Continue previous message thread",
				value=continue_default,
				disabled=continue_disabled,
				key=f"arena_round_continue_input_{current_round}",
			)
			arena_continue_by_round[current_round] = continue_value if not continue_disabled else False
			arena_prompts[current_round] = prompt
			st.session_state["arena_prompts"] = arena_prompts
			st.session_state["arena_continue_by_round"] = arena_continue_by_round
		else:
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
		selected_deployment_names = _deployment_names(selected_deployments)

		if arena_enabled and is_arena_initialized():
			initial_selection = set(st.session_state.get("arena_initial_selection", []))
			current_selection = set(selected_deployment_names)
			if initial_selection != current_selection:
				st.warning(
					"Deployment selection changed during arena flow. Arena was reset to keep state consistent."
				)
				reset_arena()
				st.session_state["results"] = []
				st.session_state["arena_prompts"] = {}
				st.session_state["arena_continue_by_round"] = {}
				st.session_state["arena_conversation_history"] = {}
				st.session_state["arena_results_history"] = {}

		if arena_enabled and not is_arena_initialized():
			init_arena(selected_deployments)
			st.session_state["arena_initial_selection"] = selected_deployment_names

		if arena_enabled:
			current_round = get_current_round()
			arena_prompts = st.session_state.get("arena_prompts", {})
			arena_prompts[current_round] = prompt
			st.session_state["arena_prompts"] = arena_prompts

		deployments_for_inference = selected_deployments
		conversation_history_by_deployment: dict[str, list[dict[str, str]]] | None = None
		if arena_enabled:
			active_models = get_active_models()
			deployments_for_inference = _selected_deployments_for_active_models(
				selected_deployments,
				active_models,
			)

			current_round = get_current_round()
			continue_by_round = st.session_state.get("arena_continue_by_round", {})
			continue_thread = bool(continue_by_round.get(current_round, False))
			conversation_history = st.session_state.get("arena_conversation_history", {})

			if continue_thread:
				conversation_history_by_deployment = {
					str(deployment.get("deployment_name", "unknown")): list(
						conversation_history.get(str(deployment.get("deployment_name", "unknown")), [])
					)
					for deployment in deployments_for_inference
				}
			else:
				for deployment in deployments_for_inference:
					deployment_name = str(deployment.get("deployment_name", "unknown"))
					conversation_history[deployment_name] = []
				st.session_state["arena_conversation_history"] = conversation_history
		st.session_state["submitted_prompt"] = prompt
		st.session_state["submitted_deployments"] = selected_deployments

		if not deployments_for_inference:
			st.error("No active deployments available for this round. Reset arena and try again.")
			return

		_run_inference_and_store_results(
			client=st.session_state["client"],
			selected_deployments=deployments_for_inference,
			prompt=prompt,
			conversation_history_by_deployment=conversation_history_by_deployment,
		)

		if arena_enabled:
			current_round = get_current_round()
			history = st.session_state.get("arena_results_history", {})
			history[current_round] = {
				"prompt": prompt,
				"results": [dict(item) for item in st.session_state.get("results", [])],
			}
			st.session_state["arena_results_history"] = history

		if arena_enabled:
			conversation_history = st.session_state.get("arena_conversation_history", {})
			for result in st.session_state.get("results", []):
				if result.get("error") is not None:
					continue

				deployment_name = str(result.get("deployment_name", "unknown"))
				assistant_text = str(result.get("output_text") or "")
				history = list(conversation_history.get(deployment_name, []))
				history.append({"role": "user", "content": prompt})
				history.append({"role": "assistant", "content": assistant_text})
				conversation_history[deployment_name] = history

			st.session_state["arena_conversation_history"] = conversation_history

	if cost_notice_enabled and st.session_state.get("results", []):
		st.info("Cost estimation not available via SDK — see pricing page")

	_render_results(st.session_state.get("results", []), metrics_enabled=metrics_enabled)

	if arena_enabled:
		_render_arena_results_history(metrics_enabled=metrics_enabled)

	_render_arena_controls(
		config=config,
		selected_deployments=st.session_state.get("submitted_deployments", []),
		prompt=st.session_state.get("submitted_prompt", ""),
		results=st.session_state.get("results", []),
	)

	_render_export_section(
		config=st.session_state.get("config", {}),
		results=st.session_state.get("results", []),
		selected_deployments=st.session_state.get("submitted_deployments", []),
	)


if __name__ == "__main__":
	main()
