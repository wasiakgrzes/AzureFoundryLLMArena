import os
from typing import Any, Dict

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if not normalized:
        return default

    if normalized in {"true", "1", "yes", "y", "on"}:
        return True

    if normalized in {"false", "0", "no", "n", "off"}:
        return False

    return default


def load_config() -> Dict[str, Any]:
    load_dotenv()

    endpoint = (os.environ.get("AZURE_FOUNDRY_ENDPOINT") or "").strip()
    api_key = (os.environ.get("AZURE_FOUNDRY_API_KEY") or "").strip()

    if not endpoint:
        raise ValueError(
            "Missing required environment variable: AZURE_FOUNDRY_ENDPOINT"
        )

    if not api_key:
        raise ValueError(
            "Missing required environment variable: AZURE_FOUNDRY_API_KEY"
        )

    feature_arena_elimination = _parse_bool(
        os.environ.get("FEATURE_ARENA_ELIMINATION"),
        default=False,
    )
    feature_arena_metrics_panel = _parse_bool(
        os.environ.get("FEATURE_ARENA_METRICS_PANEL"),
        default=False,
    )
    feature_arena_cost_display = _parse_bool(
        os.environ.get("FEATURE_ARENA_COST_DISPLAY"),
        default=False,
    )

    return {
        "endpoint": endpoint,
        "api_key": api_key,
        "feature_arena_elimination": feature_arena_elimination,
        "feature_arena_metrics_panel": feature_arena_metrics_panel,
        "feature_arena_cost_display": feature_arena_cost_display,
    }
