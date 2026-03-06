from typing import Any
import uuid

import streamlit as st

import logging

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
	from src.inspector import highlighted_output_html, run_all_checks
	from src.persistence import (
		build_arena_record,
		build_arena_session_record,
		init_persistence,
		query_leaderboard_data,
		query_prompt_history,
		write_arena_result,
	)
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
	from inspector import highlighted_output_html, run_all_checks
	from persistence import (
		build_arena_record,
		build_arena_session_record,
		init_persistence,
		query_leaderboard_data,
		query_prompt_history,
		write_arena_result,
	)
	from pricing import calculate_cost

logger = logging.getLogger(__name__)


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
	return len(selected_names) == 0 or len(selected_names) > MAX_SELECTION or not prompt.strip()


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
		"inspector_format": "n/a",
		"inspector_required_fields_input": "",
		"inspector_expected_tone_preset": "",
		"inspector_expected_tone_custom": "",
		"inspector_expected_tone": "",
		"inspector_expected_persona": "",
		"inspector_custom_instructions": "",
		"inspector_task_fulfillment_report": False,
		"inspector_deployment_name": "",
		"inspector_timeout_seconds": 30,
		"inspector_results": {},
		"cosmos_container": None,
		"persistence_degraded": False,
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

	# Cosmos persistence — non-blocking init
	config = st.session_state["config"] or {}
	if (
		bool(config.get("feature_persistence_cosmos"))
		and st.session_state["cosmos_container"] is None
		and not st.session_state.get("persistence_degraded", False)
	):
		try:
			st.session_state["cosmos_container"] = init_persistence(config)
		except Exception as exc:
			logger.warning("Cosmos persistence init failed: %s", exc)
			st.session_state["persistence_degraded"] = True


def _render_results(
	results: list[dict],
	metrics_enabled: bool,
	inspector_results_by_deployment: dict[str, list[dict]] | None = None,
	highlighting_enabled: bool = False,
) -> None:
	if not results:
		return

	st.subheader("Results")
	columns = st.columns(len(results))

	for result, column in zip(results, columns):
		with column:
			deployment_name = str(result.get("deployment_name", "unknown"))
			st.subheader(deployment_name)
			checks = (inspector_results_by_deployment or {}).get(deployment_name, [])

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
				if highlighting_enabled and checks:
					st.markdown(highlighted_output_html(output_text, checks), unsafe_allow_html=True)
				else:
					st.text(output_text)

			for check in checks:
				check_name = str(check.get("check_name", "check"))
				status = str(check.get("status", "not_evaluated"))
				detail = str(check.get("detail", ""))
				label = f"{check_name}: {status}"

				if status == "pass":
					st.success(label)
				elif status == "fail":
					st.error(label)
				elif status == "error":
					st.warning(label)
				else:
					st.info(label)

				if detail:
					st.caption(detail)

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


def _parse_required_fields(raw_value: str) -> list[str]:
	return [item.strip() for item in raw_value.split(",") if item.strip()]


def _enabled_inspector_checks(config: dict, format_type: str) -> dict[str, bool]:
	format_key = (format_type or "").strip().lower()
	format_selected = format_key in {"json", "markdown", "xml"}
	return {
		"validate_json": bool(config.get("feature_inspector_validate_json", False)) and format_selected and format_key == "json",
		"validate_markdown": bool(config.get("feature_inspector_validate_markdown", False)) and format_selected and format_key == "markdown",
		"validate_xml": bool(config.get("feature_inspector_validate_xml", False)) and format_selected and format_key == "xml",
		"required_fields": bool(config.get("feature_inspector_required_fields", False)),
		"no_extra_text": bool(config.get("feature_inspector_no_extra_text", False)) and format_selected,
		"tone_check": bool(config.get("feature_inspector_tone_check", False)),
		"persona_check": bool(config.get("feature_inspector_persona_check", False)),
	}


def _resolve_expected_tone() -> str:
	preset = str(st.session_state.get("inspector_expected_tone_preset", "")).strip().lower()
	if preset == "custom":
		return str(st.session_state.get("inspector_expected_tone_custom", "")).strip()
	return preset


def _run_inspector_for_results(
	config: dict,
	results: list[dict],
	client: Any,
	inspector_format: str,
	original_prompt: str,
	required_fields: list[str],
	expected_tone: str,
	expected_persona: str,
	custom_instructions: str,
	include_task_fulfillment_report: bool,
	inspector_deployment: str,
	timeout_seconds: int,
) -> dict[str, list[dict]]:
	enabled_checks = _enabled_inspector_checks(config, inspector_format)
	if not any(enabled_checks.values()):
		return {}

	inspections: dict[str, list[dict]] = {}
	for result in results:
		deployment_name = str(result.get("deployment_name", "unknown"))
		if result.get("error") is not None:
			inspections[deployment_name] = [
				{
					"check_name": "summary",
					"status": "not_evaluated",
					"detail": "Inspector skipped because inference failed",
				}
			]
			continue

		inspections[deployment_name] = run_all_checks(
			text=result.get("output_text"),
			format_type=inspector_format,
			required_fields=required_fields,
			enabled_checks=enabled_checks,
			inspector_client=client,
			inspector_deployment=inspector_deployment,
			expected_tone=expected_tone,
			expected_persona=expected_persona,
			custom_instructions=custom_instructions,
			include_task_fulfillment_report=include_task_fulfillment_report,
			original_prompt=original_prompt,
			timeout_seconds=timeout_seconds,
		)

	return inspections


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

	st.session_state["_pending_deployment_names"] = get_active_models()
	st.session_state["results"] = []
	st.session_state["submitted_deployments"] = []
	st.session_state["best_model_name"] = None
	st.session_state["prompt_input"] = ""

	if is_arena_completed():
		# Persist full arena stats now that winner is known
		persistence_enabled = bool(config.get("feature_persistence_cosmos", False))
		if persistence_enabled and st.session_state.get("cosmos_container") is not None:
			_persist_arena_final_results(config)
		st.rerun()

	st.success("Round advanced. Edit prompt if needed, then click Submit to run the next round.")
	st.rerun()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _persist_arena_results(
	config: dict,
	results: list[dict],
	prompt: str,
	winner: str | None,
	eliminated_models: list[str],
	models_compared: list[str],
) -> None:
	"""Write arena result records to Cosmos (non-blocking).

	One record per deployment in *results* is persisted.  Failures are
	logged and surfaced as a warning but do **not** interrupt the session.
	"""
	container = st.session_state.get("cosmos_container")
	if container is None:
		return

	elimination_reasons = {name: "eliminated" for name in (eliminated_models or [])}

	for result in results:
		if result.get("error") is not None:
			continue

		arena_data = {
			"prompt_text": prompt,
			"models_compared": models_compared,
			"winner": winner,
			"elimination_reasons": elimination_reasons,
			"deployment_name": result.get("deployment_name", "unknown"),
			"model_name": result.get("model_name"),
			"model_version": result.get("model_name"),
			"latency_ms": result.get("latency_ms"),
			"input_tokens": result.get("input_tokens"),
			"output_tokens": result.get("output_tokens"),
			"total_tokens": result.get("total_tokens"),
		}

		try:
			record = build_arena_record(arena_data, config)
			write_arena_result(container, record)
		except Exception as exc:
			logger.warning("Failed to persist result for %s: %s", result.get("deployment_name"), exc)
			st.warning(f"Persistence warning: could not save result for {result.get('deployment_name')}. Session continues.")


def _persist_arena_final_results(config: dict) -> None:
	"""Persist comprehensive stats for every deployment when the arena finishes.

	Reads the full ``arena_results_history`` from session state, aggregates
	per-deployment round data, and writes one document per deployment with
	winner, elimination round, and aggregate statistics.
	"""
	container = st.session_state.get("cosmos_container")
	if container is None:
		return

	winner = get_arena_winner()
	eliminated = get_eliminated_models()
	results_history: dict = st.session_state.get("arena_results_history", {})

	if not results_history:
		return

	# Collect all models that participated across rounds
	all_models: set[str] = set()
	for round_data in results_history.values():
		for result in round_data.get("results", []):
			all_models.add(str(result.get("deployment_name", "unknown")))

	models_compared = sorted(all_models)
	actual_rounds = len(results_history)
	arena_session_id = str(uuid.uuid4())

	# Group per-deployment round details
	deployment_rounds: dict[str, list[dict]] = {}
	for round_num, round_data in sorted(
		results_history.items(), key=lambda x: int(x[0])
	):
		prompt_text = round_data.get("prompt", "")
		for result in round_data.get("results", []):
			if result.get("error") is not None:
				continue
			dep = str(result.get("deployment_name", "unknown"))
			if dep not in deployment_rounds:
				deployment_rounds[dep] = []
			deployment_rounds[dep].append(
				{
					"round": int(round_num),
					"prompt_text": prompt_text,
					"model_name": result.get("model_name"),
					"latency_ms": result.get("latency_ms"),
					"input_tokens": result.get("input_tokens"),
					"output_tokens": result.get("output_tokens"),
					"total_tokens": result.get("total_tokens"),
				}
			)

	# Write one comprehensive record per deployment
	for dep_name, rounds in deployment_rounds.items():
		try:
			record = build_arena_session_record(
				deployment_name=dep_name,
				arena_session_id=arena_session_id,
				winner=winner,
				total_rounds=actual_rounds,
				models_compared=models_compared,
				eliminated_models=eliminated,
				round_details=rounds,
				config=config,
			)
			write_arena_result(container, record)
		except Exception as exc:
			logger.warning("Failed to persist final arena result for %s: %s", dep_name, exc)
			st.warning(f"Persistence warning: could not save final result for {dep_name}.")


def _render_leaderboard(config: dict) -> None:
	"""Render a leaderboard table aggregated from Cosmos history."""
	if not bool(config.get("feature_arena_leaderboard")):
		return

	container = st.session_state.get("cosmos_container")
	if container is None:
		return

	with st.expander("Leaderboard", expanded=False):
		try:
			raw = query_leaderboard_data(container)
		except Exception as exc:
			st.warning(f"Could not load leaderboard data: {exc}")
			return

		if not raw:
			st.info("No historical arena data yet.")
			return

		# Aggregate in Python
		stats: dict[str, dict[str, Any]] = {}
		for item in raw:
			dep = item.get("deployment_name", "unknown")
			if dep not in stats:
				stats[dep] = {"wins": 0, "tasks": 0, "total_latency": 0, "latency_count": 0}
			stats[dep]["tasks"] += 1
			if item.get("is_winner", item.get("winner") == dep):
				stats[dep]["wins"] += 1
			lat = item.get("latency_ms")
			if lat is not None:
				stats[dep]["total_latency"] += lat
				stats[dep]["latency_count"] += 1

		rows: list[dict[str, Any]] = []
		for dep, s in sorted(stats.items(), key=lambda kv: kv[1]["wins"], reverse=True):
			avg_lat = (
				round(s["total_latency"] / s["latency_count"])
				if s["latency_count"] > 0
				else None
			)
			win_rate = round(s["wins"] / s["tasks"] * 100, 1) if s["tasks"] > 0 else 0
			rows.append(
				{
					"Deployment": dep,
					"Wins": s["wins"],
					"Win Rate (%, per model)": win_rate,
					"Avg Latency (ms)": avg_lat if avg_lat is not None else "N/A",
					"Tasks": s["tasks"],
				}
			)

		st.table(rows)


def _render_prompt_memory_selector(config: dict) -> str | None:
	"""Render prompt-history dropdown in sidebar. Returns selected prompt text or None."""
	if not bool(config.get("feature_prompt_memory_enabled")):
		return None

	container = st.session_state.get("cosmos_container")
	if container is None:
		return None

	try:
		history = query_prompt_history(container, limit=30)
	except Exception as exc:
		logger.warning("Prompt history query failed: %s", exc)
		return None

	if not history:
		return None

	options = [""] + [
		(item.get("prompt_text") or item.get("prompt_hash", "?"))[:120]
		for item in history
	]
	labels = ["Select a previous prompt..."] + [
		f"{(item.get('prompt_text') or item.get('prompt_hash', '?'))[:80]} ({item.get('timestamp', '')[:10]})"
		for item in history
	]

	selected_idx = st.selectbox(
		"Prompt History",
		options=range(len(options)),
		format_func=lambda i: labels[i],
		key="prompt_memory_selector",
	)

	if selected_idx and selected_idx > 0:
		chosen = history[selected_idx - 1]
		return chosen.get("prompt_text") or None

	return None


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
	inspector_enabled = bool(config.get("feature_inspector_enabled", False))
	highlighting_enabled = bool(config.get("feature_inspector_highlighting", False))
	persistence_enabled = bool(config.get("feature_persistence_cosmos", False))
	leaderboard_enabled = bool(config.get("feature_arena_leaderboard", False))
	prompt_memory_enabled = bool(config.get("feature_prompt_memory_enabled", False))

	if persistence_enabled and st.session_state.get("persistence_degraded"):
		st.warning("Cosmos DB persistence is unavailable. Arena results will not be saved this session.")

	if len(deployments) == 0:
		st.warning("No compatible text-based deployments were found in the configured Foundry resource.")

	with st.sidebar:
		st.subheader("Model Selection")
		selected_names = st.multiselect(
			"Select deployments (1–5)",
			options=deployment_names,
			default=None,
			key="selected_deployment_names",
		)

		if len(selected_names) > MAX_SELECTION:
			st.warning("You can select at most 5 deployments.")

		prompt = ""

		# Prompt memory: previous-prompt selector
		remembered_prompt = None
		if prompt_memory_enabled and persistence_enabled:
			remembered_prompt = _render_prompt_memory_selector(config)
			# Only apply when the user just picked a *new* prompt from the dropdown
			if remembered_prompt and remembered_prompt != st.session_state.get("_last_applied_prompt"):
				st.session_state["_last_applied_prompt"] = remembered_prompt
				st.session_state["prompt_input"] = remembered_prompt
				if arena_enabled:
					current_rnd = get_current_round() if is_arena_initialized() else 1
					widget_key = f"arena_round_prompt_input_{current_rnd}"
					st.session_state[widget_key] = remembered_prompt
					arena_prompts_mem = st.session_state.get("arena_prompts", {})
					arena_prompts_mem[current_rnd] = remembered_prompt
					st.session_state["arena_prompts"] = arena_prompts_mem

		if arena_enabled:
			arena_prompts = st.session_state.get("arena_prompts", {})
			arena_continue_by_round = st.session_state.get("arena_continue_by_round", {})
			current_round = get_current_round() if is_arena_initialized() else 1
			arena_completed = is_arena_completed() if is_arena_initialized() else False

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

			# Only show the editable prompt box if the arena is still running
			if not arena_completed:
				# Seed the widget key with stored prompt only on first encounter
				widget_key = f"arena_round_prompt_input_{current_round}"
				if widget_key not in st.session_state:
					st.session_state[widget_key] = str(arena_prompts.get(current_round, ""))
				prompt = st.text_area(
					f"Round {current_round} Prompt",
					height=180,
					placeholder=f"Enter prompt for round {current_round}...",
					key=widget_key,
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
				height=180,
				placeholder="Enter one prompt to compare across selected deployments...",
				key="prompt_input",
			)

		submit_clicked = st.button(
			"Submit",
			disabled=_is_submit_disabled(selected_names, prompt),
			type="primary",
		)

		if inspector_enabled:
			with st.expander("Output Inspector", expanded=False):
				st.selectbox(
					"Validation format",
					options=["n/a", "json", "markdown", "xml"],
					format_func=lambda item: "N/A" if item == "n/a" else item,
					key="inspector_format",
				)

				if bool(config.get("feature_inspector_required_fields", False)):
					st.text_input(
						"Required fields (comma-separated)",
						key="inspector_required_fields_input",
					)

				if bool(config.get("feature_inspector_tone_check", False)):
					st.selectbox(
						"Expected tone",
						options=["", "formal", "relaxed", "casual", "serious", "funny", "respectful", "custom"],
						format_func=lambda item: item if item else "Select tone (optional)",
						key="inspector_expected_tone_preset",
					)
					if str(st.session_state.get("inspector_expected_tone_preset", "")) == "custom":
						st.text_input(
							"Custom tone",
							key="inspector_expected_tone_custom",
						)

				if bool(config.get("feature_inspector_persona_check", False)):
					st.text_input(
						"Expected persona",
						key="inspector_expected_persona",
					)

				st.text_area(
					"Custom inspector instructions",
					key="inspector_custom_instructions",
					height=110,
					placeholder="Optional additional instructions for semantic inspector...",
				)

				st.checkbox(
					"Additional task fulfillment report",
					key="inspector_task_fulfillment_report",
				)

				st.session_state["inspector_expected_tone"] = _resolve_expected_tone()

				need_semantic_deployment = (
					bool(config.get("feature_inspector_tone_check", False))
					or bool(config.get("feature_inspector_persona_check", False))
					or bool(st.session_state.get("inspector_task_fulfillment_report", False))
				)
				if need_semantic_deployment:
					inspector_options = [""] + deployment_names
					default_name = str(st.session_state.get("inspector_deployment_name", ""))
					default_index = 0
					if default_name in inspector_options:
						default_index = inspector_options.index(default_name)
					selected_inspector_deployment = st.selectbox(
						"Inspector deployment",
						options=inspector_options,
						index=default_index,
						format_func=lambda item: item if item else "Select deployment",
					)
					st.session_state["inspector_deployment_name"] = selected_inspector_deployment

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

		if inspector_enabled:
			with st.spinner("Running output inspector..."):
				st.session_state["inspector_results"] = _run_inspector_for_results(
					config=config,
					results=st.session_state.get("results", []),
					client=st.session_state["client"],
					inspector_format=str(st.session_state.get("inspector_format", "json")),
					original_prompt=prompt,
					required_fields=_parse_required_fields(
						str(st.session_state.get("inspector_required_fields_input", ""))
					),
					expected_tone=str(st.session_state.get("inspector_expected_tone", "")),
					expected_persona=str(st.session_state.get("inspector_expected_persona", "")),
					custom_instructions=str(st.session_state.get("inspector_custom_instructions", "")),
					include_task_fulfillment_report=bool(
						st.session_state.get("inspector_task_fulfillment_report", False)
					),
					inspector_deployment=str(st.session_state.get("inspector_deployment_name", "")),
					timeout_seconds=int(st.session_state.get("inspector_timeout_seconds", 30)),
				)
		else:
			st.session_state["inspector_results"] = {}

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

		# Persist results to Cosmos DB (non-blocking) — non-arena only.
		# Arena results are persisted when the winner is selected
		# (see _render_arena_controls → _persist_arena_final_results).
		if persistence_enabled and not arena_enabled and st.session_state.get("cosmos_container") is not None:
			models_list = [str(d.get("deployment_name", "unknown")) for d in deployments_for_inference]
			_persist_arena_results(
				config=config,
				results=st.session_state.get("results", []),
				prompt=prompt,
				winner=None,
				eliminated_models=[],
				models_compared=models_list,
			)

	if cost_notice_enabled and st.session_state.get("results", []):
		st.info("Cost estimation not available via SDK — see pricing page")

	_render_results(
		st.session_state.get("results", []),
		metrics_enabled=metrics_enabled,
		inspector_results_by_deployment=st.session_state.get("inspector_results", {}),
		highlighting_enabled=inspector_enabled and highlighting_enabled,
	)

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

	# Leaderboard (Week 3)
	if leaderboard_enabled and persistence_enabled:
		_render_leaderboard(config)


if __name__ == "__main__":
	main()
