"""Extracted UI rendering panels for Azure Foundry LLM Arena.

Contains results display, export, leaderboard, connection status,
prompt memory, and persistence orchestration — extracted from app.py
to reduce monolith size (code smell C-01).
"""

from typing import Any
import uuid
import logging

import streamlit as st

from src.arena import get_arena_winner, get_eliminated_models
from src.export import generate_export_config
from src.inspector import highlighted_output_html
from src.persistence import (
	build_arena_record,
	build_arena_session_record,
	query_leaderboard_data,
	query_prompt_history,
	write_arena_result,
)

logger = logging.getLogger(__name__)


def format_token_value(value: Any) -> str:
	if value is None:
		return "N/A"
	return str(value)


def format_latency_value(value: Any) -> str:
	if value is None:
		return "N/A"
	return f"{value} ms"


def successful_result_candidates(
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


# ---------------------------------------------------------------------------
# Results rendering
# ---------------------------------------------------------------------------


def render_results(
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
				st.metric("Input Tokens", format_token_value(result.get("input_tokens")))
				st.metric("Output Tokens", format_token_value(result.get("output_tokens")))
				st.metric("Total Tokens", format_token_value(result.get("total_tokens")))
				st.metric("Latency", format_latency_value(result.get("latency_ms")))


def render_arena_results_history(metrics_enabled: bool) -> None:
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
			render_results(round_results, metrics_enabled=metrics_enabled)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def render_export_section(config: dict, results: list[dict], selected_deployments: list[dict]) -> None:
	if not results:
		return

	candidates = successful_result_candidates(results, selected_deployments)
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


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------


def render_connection_status(config: dict) -> None:
	"""Render a collapsed expander showing service connection statuses."""
	if not bool(config.get("feature_connection_status_panel")):
		return
	with st.expander("Service Connections", expanded=False):
		rows: list[dict[str, str]] = []

		# 1. Azure Foundry
		endpoint = config.get("endpoint", "")
		api_key = config.get("api_key", "")
		foundry_ok = bool(endpoint and api_key and st.session_state.get("client"))
		rows.append({
			"Service": "Azure AI Foundry",
			"Connection": endpoint if endpoint else "(not configured)",
			"Status": "\u2705 Connected" if foundry_ok else "\u274c Disconnected",
		})

		# 2. Model Discovery
		deployments = st.session_state.get("deployments") or []
		rows.append({
			"Service": "Model Discovery",
			"Connection": f"{len(deployments)} deployment(s) found",
			"Status": "\u2705 OK" if deployments else "\u26a0\ufe0f No deployments",
		})

		# 3. Cosmos DB
		cosmos_enabled = bool(config.get("feature_persistence_cosmos"))
		cosmos_endpoint = config.get("cosmos_endpoint", "")
		cosmos_connected = st.session_state.get("cosmos_container") is not None
		degraded = st.session_state.get("persistence_degraded", False)
		if not cosmos_enabled:
			cosmos_status = "\u23f8\ufe0f Disabled"
		elif degraded:
			cosmos_status = "\u274c Failed"
		elif cosmos_connected:
			db_name = config.get("cosmos_database_name", "")
			ctr_name = config.get("cosmos_container_name", "")
			cosmos_status = f"\u2705 Connected (db={db_name}, container={ctr_name})"
		else:
			cosmos_status = "\u23f3 Pending"
		rows.append({
			"Service": "Cosmos DB",
			"Connection": cosmos_endpoint if cosmos_endpoint else "(not configured)",
			"Status": cosmos_status,
		})

		# 4. Key Vault
		kv_enabled = bool(config.get("feature_keyvault_enabled"))
		kv_url = config.get("keyvault_url", "")
		if not kv_enabled:
			kv_status = "\u23f8\ufe0f Disabled"
		elif kv_url:
			kv_status = "\u2705 Configured"
		else:
			kv_status = "\u274c Missing URL"
		rows.append({
			"Service": "Azure Key Vault",
			"Connection": kv_url if kv_url else "(not configured)",
			"Status": kv_status,
		})

		# 5. Feature flags from .env
		flags = [
			("Arena Elimination", "feature_arena_elimination"),
			("Metrics Panel", "feature_arena_metrics_panel"),
			("Inspector", "feature_inspector_enabled"),
			("Persistence (Cosmos)", "feature_persistence_cosmos"),
			("Leaderboard", "feature_arena_leaderboard"),
			("Prompt Memory", "feature_prompt_memory_enabled"),
			("Key Vault", "feature_keyvault_enabled"),
		]

		st.table(rows)

		st.caption("Feature Flags")
		flag_rows = [
			{"Feature": label, "Enabled": "\u2705" if bool(config.get(key)) else "\u274c"}
			for label, key in flags
		]
		st.table(flag_rows)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def render_leaderboard(config: dict) -> None:
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


# ---------------------------------------------------------------------------
# Prompt memory
# ---------------------------------------------------------------------------


def render_prompt_memory_selector(config: dict) -> str | None:
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


# ---------------------------------------------------------------------------
# Persistence orchestration
# ---------------------------------------------------------------------------


def persist_arena_results(
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


def persist_arena_final_results(config: dict) -> None:
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
