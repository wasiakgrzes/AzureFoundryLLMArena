from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Iterable


ARENA_STATE_KEYS = (
    "arena_round",
    "arena_active_models",
    "arena_eliminated_models",
    "arena_completed",
    "arena_winner",
)


def _default_session_state() -> MutableMapping[str, Any]:
    import streamlit as st

    return st.session_state


def _session_state(session_state: MutableMapping[str, Any] | None) -> MutableMapping[str, Any]:
    if session_state is not None:
        return session_state
    return _default_session_state()


def _normalize_selected_models(selected_deployments: Iterable[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for deployment in selected_deployments:
        deployment_name = str(deployment.get("deployment_name", "")).strip()
        if deployment_name:
            names.append(deployment_name)
    return names


def is_arena_initialized(session_state: MutableMapping[str, Any] | None = None) -> bool:
    state = _session_state(session_state)
    return all(key in state for key in ARENA_STATE_KEYS)


def init_arena(
    selected_deployments: Iterable[dict[str, Any]],
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    state = _session_state(session_state)
    active_models = _normalize_selected_models(selected_deployments)

    state["arena_round"] = 1
    state["arena_active_models"] = active_models
    state["arena_eliminated_models"] = []
    state["arena_completed"] = len(active_models) <= 1
    state["arena_winner"] = active_models[0] if len(active_models) == 1 else None


def get_active_models(session_state: MutableMapping[str, Any] | None = None) -> list[str]:
    state = _session_state(session_state)
    return list(state.get("arena_active_models", []))


def get_eliminated_models(session_state: MutableMapping[str, Any] | None = None) -> list[str]:
    state = _session_state(session_state)
    return list(state.get("arena_eliminated_models", []))


def get_current_round(session_state: MutableMapping[str, Any] | None = None) -> int:
    state = _session_state(session_state)
    return int(state.get("arena_round", 1))


def is_arena_completed(session_state: MutableMapping[str, Any] | None = None) -> bool:
    state = _session_state(session_state)
    return bool(state.get("arena_completed", False))


def get_arena_winner(session_state: MutableMapping[str, Any] | None = None) -> str | None:
    state = _session_state(session_state)
    winner = state.get("arena_winner")
    if winner is None:
        return None
    return str(winner)


def advance_round(
    winner_names: Iterable[str],
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    state = _session_state(session_state)

    active_models = list(state.get("arena_active_models", []))
    winners = [name for name in winner_names if name in active_models]

    if not winners:
        raise ValueError("Select at least one winner before proceeding")

    winner_set = set(winners)
    updated_active = [name for name in active_models if name in winner_set]
    newly_eliminated = [name for name in active_models if name not in winner_set]

    eliminated_models = list(state.get("arena_eliminated_models", []))
    for name in newly_eliminated:
        if name not in eliminated_models:
            eliminated_models.append(name)

    state["arena_active_models"] = updated_active
    state["arena_eliminated_models"] = eliminated_models
    state["arena_round"] = int(state.get("arena_round", 1)) + 1

    if len(updated_active) <= 1:
        state["arena_completed"] = True
        state["arena_winner"] = updated_active[0] if updated_active else None
    else:
        state["arena_completed"] = False
        state["arena_winner"] = None


def reset_arena(session_state: MutableMapping[str, Any] | None = None) -> None:
    state = _session_state(session_state)
    for key in ARENA_STATE_KEYS:
        if key in state:
            del state[key]
