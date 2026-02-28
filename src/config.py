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

    # --- Week 3: Persistence, Leaderboard, Prompt Memory, Key Vault ---
    feature_persistence_cosmos = _parse_bool(
        os.environ.get("FEATURE_PERSISTENCE_COSMOS"),
        default=False,
    )
    feature_arena_leaderboard = _parse_bool(
        os.environ.get("FEATURE_ARENA_LEADERBOARD"),
        default=False,
    )
    feature_prompt_memory_enabled = _parse_bool(
        os.environ.get("FEATURE_PROMPT_MEMORY_ENABLED"),
        default=False,
    )
    feature_keyvault_enabled = _parse_bool(
        os.environ.get("FEATURE_KEYVAULT_ENABLED"),
        default=False,
    )
    persist_prompt_text = _parse_bool(
        os.environ.get("PERSIST_PROMPT_TEXT"),
        default=False,
    )

    # Cosmos DB optional config
    cosmos_endpoint = (os.environ.get("COSMOS_ENDPOINT") or "").strip()
    cosmos_account_key = (os.environ.get("COSMOS_ACCOUNT_KEY") or "").strip()
    cosmos_database_name = (
        os.environ.get("COSMOS_DATABASE_NAME") or "llm_arena"
    ).strip()
    cosmos_container_name = (
        os.environ.get("COSMOS_CONTAINER_NAME") or "arena_results"
    ).strip()

    # Key Vault optional config
    keyvault_url = (os.environ.get("KEYVAULT_URL") or "").strip()

    # Conditional validation: Cosmos
    if feature_persistence_cosmos and not cosmos_endpoint:
        raise ValueError(
            "FEATURE_PERSISTENCE_COSMOS is enabled but COSMOS_ENDPOINT is not set. "
            "Provide a valid Cosmos DB endpoint (e.g. https://<account>.documents.azure.com:443/)."
        )

    # Conditional validation: Key Vault
    if feature_keyvault_enabled and not keyvault_url:
        raise ValueError(
            "FEATURE_KEYVAULT_ENABLED is enabled but KEYVAULT_URL is not set. "
            "Provide a valid Key Vault URL (e.g. https://<vault-name>.vault.azure.net/)."
        )

    return {
        "endpoint": endpoint,
        "api_key": api_key,
        # Week 1 — Arena
        "feature_arena_elimination": feature_arena_elimination,
        "feature_arena_metrics_panel": feature_arena_metrics_panel,
        "feature_arena_cost_display": feature_arena_cost_display,
        # Week 2 — Inspector
        "feature_inspector_enabled": feature_inspector_enabled,
        "feature_inspector_validate_json": feature_inspector_validate_json,
        "feature_inspector_validate_markdown": feature_inspector_validate_markdown,
        "feature_inspector_validate_xml": feature_inspector_validate_xml,
        "feature_inspector_required_fields": feature_inspector_required_fields,
        "feature_inspector_no_extra_text": feature_inspector_no_extra_text,
        "feature_inspector_tone_check": feature_inspector_tone_check,
        "feature_inspector_persona_check": feature_inspector_persona_check,
        "feature_inspector_highlighting": feature_inspector_highlighting,
        # Week 3 — Persistence & Memory
        "feature_persistence_cosmos": feature_persistence_cosmos,
        "feature_arena_leaderboard": feature_arena_leaderboard,
        "feature_prompt_memory_enabled": feature_prompt_memory_enabled,
        "feature_keyvault_enabled": feature_keyvault_enabled,
        "persist_prompt_text": persist_prompt_text,
        "cosmos_endpoint": cosmos_endpoint,
        "cosmos_account_key": cosmos_account_key,
        "cosmos_database_name": cosmos_database_name,
        "cosmos_container_name": cosmos_container_name,
        "keyvault_url": keyvault_url,
    }
