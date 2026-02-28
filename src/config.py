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
    feature_inspector_enabled = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_ENABLED"),
        default=False,
    )
    feature_inspector_validate_json = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_VALIDATE_JSON"),
        default=False,
    )
    feature_inspector_validate_markdown = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_VALIDATE_MARKDOWN"),
        default=False,
    )
    feature_inspector_validate_xml = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_VALIDATE_XML"),
        default=False,
    )
    feature_inspector_required_fields = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_REQUIRED_FIELDS"),
        default=False,
    )
    feature_inspector_no_extra_text = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_NO_EXTRA_TEXT"),
        default=False,
    )
    feature_inspector_tone_check = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_TONE_CHECK"),
        default=False,
    )
    feature_inspector_persona_check = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_PERSONA_CHECK"),
        default=False,
    )
    feature_inspector_highlighting = _parse_bool(
        os.environ.get("FEATURE_INSPECTOR_HIGHLIGHTING"),
        default=False,
    )

    return {
        "endpoint": endpoint,
        "api_key": api_key,
        "feature_arena_elimination": feature_arena_elimination,
        "feature_arena_metrics_panel": feature_arena_metrics_panel,
        "feature_arena_cost_display": feature_arena_cost_display,
        "feature_inspector_enabled": feature_inspector_enabled,
        "feature_inspector_validate_json": feature_inspector_validate_json,
        "feature_inspector_validate_markdown": feature_inspector_validate_markdown,
        "feature_inspector_validate_xml": feature_inspector_validate_xml,
        "feature_inspector_required_fields": feature_inspector_required_fields,
        "feature_inspector_no_extra_text": feature_inspector_no_extra_text,
        "feature_inspector_tone_check": feature_inspector_tone_check,
        "feature_inspector_persona_check": feature_inspector_persona_check,
        "feature_inspector_highlighting": feature_inspector_highlighting,
    }
