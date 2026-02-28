"""Cosmos DB persistence adapter for arena results, leaderboard, and prompt history.

Provides functions to initialize a CosmosClient, create the database/container
if missing, write flat-schema arena result records, and query historical data.

All functions are designed to be called from the Streamlit app layer with the
config dict produced by ``load_config()``.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos import exceptions as cosmos_exceptions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema reference (flat, query-friendly)
# ---------------------------------------------------------------------------

ARENA_RESULT_SCHEMA: Dict[str, str] = {
    "id": "Cosmos document id (= arena_id UUID string)",
    "arena_id": "UUID v4 identifying the arena run",
    "timestamp": "UTC ISO-8601 timestamp of the record creation",
    "prompt_hash": "SHA-256 hex digest of the prompt text",
    "prompt_text": "Original prompt text (None when persist_prompt_text is false)",
    "models_compared": "List of deployment names that participated",
    "winner": "Winning deployment name (or None if undecided)",
    "elimination_reasons": "Dict mapping eliminated deployments to reason strings",
    "inspector_flags_used": "Dict of inspector flag names to booleans",
    "model_version": "Model version string returned by the API (if available)",
    "deployment_name": "Deployment that this record row describes (partition key)",
    "latency_ms": "Inference latency in milliseconds",
    "token_usage": "Dict with input_tokens, output_tokens, total_tokens",
}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def generate_prompt_hash(prompt_text: str) -> str:
    """Return a deterministic SHA-256 hex digest for *prompt_text*."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Client / database / container initialisation
# ---------------------------------------------------------------------------


def init_cosmos_client(
    cosmos_endpoint: str,
    cosmos_key: Optional[str] = None,
) -> CosmosClient:
    """Create a ``CosmosClient``.

    If *cosmos_key* is provided it is used directly as the credential.
    Otherwise ``DefaultAzureCredential`` from ``azure-identity`` is used,
    which supports managed-identity, Azure CLI, and environment-variable
    authentication chains.
    """
    if cosmos_key:
        return CosmosClient(url=cosmos_endpoint, credential=cosmos_key)

    from azure.identity import DefaultAzureCredential

    return CosmosClient(url=cosmos_endpoint, credential=DefaultAzureCredential())


def get_or_create_database(client: CosmosClient, database_name: str):
    """Return a ``DatabaseProxy``, creating the database when it doesn't exist."""
    return client.create_database_if_not_exists(id=database_name)


def get_or_create_container(database, container_name: str):
    """Return a ``ContainerProxy`` with partition key ``/deployment_name``.

    No throughput is specified — compatible with both serverless and
    provisioned Cosmos accounts.
    """
    return database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path="/deployment_name"),
    )


def init_persistence(config: Dict[str, Any]):
    """High-level helper: initialise client → database → container.

    Returns the ``ContainerProxy`` ready for reads/writes, or raises on
    configuration / connectivity failures.

    Authentication priority:
        1. ``cosmos_account_key`` from config (COSMOS_ACCOUNT_KEY env var)
           — used when set; fastest for local dev.
        2. ``DefaultAzureCredential`` — used when no account key is
           provided; supports managed identity, Azure CLI, etc.
    """
    cosmos_endpoint = config["cosmos_endpoint"]
    cosmos_account_key = (config.get("cosmos_account_key") or "").strip() or None

    client = init_cosmos_client(cosmos_endpoint, cosmos_key=cosmos_account_key)
    database = get_or_create_database(client, config["cosmos_database_name"])
    container = get_or_create_container(database, config["cosmos_container_name"])
    return container


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------


def build_arena_record(
    arena_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct a flat Cosmos document from inference/arena results.

    *arena_data* is expected to carry keys produced by the arena + inference
    pipeline (e.g. ``deployment_name``, ``model_name``, ``latency_ms``,
    token-usage fields, winner info, etc.).

    Fields:
        - ``id`` / ``arena_id`` — new UUID
        - ``timestamp`` — current UTC time
        - ``prompt_hash`` — SHA-256 of prompt text
        - ``prompt_text`` — included only when ``persist_prompt_text`` is true
        - ``models_compared`` / ``winner`` / ``elimination_reasons`` — from arena
        - ``inspector_flags_used`` — from config flags
        - ``deployment_name`` — partition key value
        - ``latency_ms`` / ``token_usage`` — from inference result
    """
    arena_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    prompt_text_raw = str(arena_data.get("prompt_text", "") or "")
    prompt_hash = generate_prompt_hash(prompt_text_raw)

    persist_text = bool(config.get("persist_prompt_text", False))

    record: Dict[str, Any] = {
        "id": arena_id,
        "arena_id": arena_id,
        "timestamp": timestamp,
        "prompt_hash": prompt_hash,
        "prompt_text": prompt_text_raw if persist_text else None,
        "models_compared": arena_data.get("models_compared", []),
        "winner": arena_data.get("winner"),
        "elimination_reasons": arena_data.get("elimination_reasons", {}),
        "inspector_flags_used": {
            "inspector_enabled": bool(config.get("feature_inspector_enabled")),
            "validate_json": bool(config.get("feature_inspector_validate_json")),
            "validate_markdown": bool(config.get("feature_inspector_validate_markdown")),
            "validate_xml": bool(config.get("feature_inspector_validate_xml")),
            "required_fields": bool(config.get("feature_inspector_required_fields")),
            "no_extra_text": bool(config.get("feature_inspector_no_extra_text")),
            "tone_check": bool(config.get("feature_inspector_tone_check")),
            "persona_check": bool(config.get("feature_inspector_persona_check")),
        },
        "model_version": arena_data.get("model_version") or arena_data.get("model_name"),
        "deployment_name": str(arena_data.get("deployment_name", "unknown")),
        "latency_ms": arena_data.get("latency_ms"),
        "token_usage": {
            "input_tokens": arena_data.get("input_tokens"),
            "output_tokens": arena_data.get("output_tokens"),
            "total_tokens": arena_data.get("total_tokens"),
        },
    }

    return record


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def build_arena_session_record(
    deployment_name: str,
    arena_session_id: str,
    winner: str | None,
    total_rounds: int,
    models_compared: List[str],
    eliminated_models: List[str],
    round_details: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a comprehensive record for one deployment in a completed arena.

    Called once per deployment when the arena finishes (winner selected).
    Aggregates per-round stats and marks winner / elimination round.
    """
    record_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    is_winner = (deployment_name == winner) if winner else False

    # Determine which round the model was eliminated in
    eliminated_in_round: int | None = None
    if not is_winner and round_details:
        eliminated_in_round = round_details[-1].get("round")

    # Aggregate stats across rounds
    total_latency = sum(r.get("latency_ms", 0) or 0 for r in round_details)
    total_input = sum(r.get("input_tokens", 0) or 0 for r in round_details)
    total_output = sum(r.get("output_tokens", 0) or 0 for r in round_details)
    total_tok = sum(r.get("total_tokens", 0) or 0 for r in round_details)
    rounds_count = len(round_details)

    # Use first prompt for top-level prompt_hash
    first_prompt = ""
    for rd in round_details:
        if rd.get("prompt_text"):
            first_prompt = rd["prompt_text"]
            break
    prompt_hash = generate_prompt_hash(first_prompt)
    persist_text = bool(config.get("persist_prompt_text", False))

    record: Dict[str, Any] = {
        "id": record_id,
        "arena_session_id": arena_session_id,
        "timestamp": timestamp,
        "deployment_name": deployment_name,
        "model_name": round_details[0].get("model_name") if round_details else None,
        "is_winner": is_winner,
        "winner": winner,
        "eliminated_in_round": eliminated_in_round,
        "total_rounds": total_rounds,
        "models_compared": models_compared,
        "eliminated_models": eliminated_models,
        "prompt_hash": prompt_hash,
        "prompt_text": first_prompt if persist_text else None,
        "round_details": [
            {
                "round": rd.get("round"),
                "prompt_hash": generate_prompt_hash(rd.get("prompt_text", "")),
                "prompt_text": rd.get("prompt_text") if persist_text else None,
                "latency_ms": rd.get("latency_ms"),
                "input_tokens": rd.get("input_tokens"),
                "output_tokens": rd.get("output_tokens"),
                "total_tokens": rd.get("total_tokens"),
            }
            for rd in round_details
        ],
        "aggregate_stats": {
            "avg_latency_ms": round(total_latency / rounds_count) if rounds_count > 0 else None,
            "total_latency_ms": total_latency,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tok,
            "rounds_participated": rounds_count,
        },
        "inspector_flags_used": {
            "inspector_enabled": bool(config.get("feature_inspector_enabled")),
            "validate_json": bool(config.get("feature_inspector_validate_json")),
            "validate_markdown": bool(config.get("feature_inspector_validate_markdown")),
            "validate_xml": bool(config.get("feature_inspector_validate_xml")),
            "required_fields": bool(config.get("feature_inspector_required_fields")),
            "no_extra_text": bool(config.get("feature_inspector_no_extra_text")),
            "tone_check": bool(config.get("feature_inspector_tone_check")),
            "persona_check": bool(config.get("feature_inspector_persona_check")),
        },
        # Backward-compatible flat fields for leaderboard queries
        "latency_ms": round(total_latency / rounds_count) if rounds_count > 0 else None,
        "token_usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tok,
        },
    }

    return record


def write_arena_result(container, record: Dict[str, Any]) -> None:
    """Persist a single arena result document via upsert.

    Raises ``cosmos_exceptions.CosmosHttpResponseError`` on transient or
    permanent write failures — callers should handle gracefully.
    """
    container.upsert_item(body=record)


def write_arena_results_batch(
    container,
    records: Sequence[Dict[str, Any]],
) -> List[str]:
    """Write multiple records, returning IDs of successfully written items.

    Failures for individual records are logged but do not abort the batch.
    """
    written_ids: List[str] = []
    for record in records:
        try:
            container.upsert_item(body=record)
            written_ids.append(record.get("id", ""))
        except cosmos_exceptions.CosmosHttpResponseError as exc:
            logger.warning(
                "Failed to persist record %s: %s",
                record.get("id", "?"),
                exc,
            )
    return written_ids


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def query_results(
    container,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query arena result records with optional filters.

    Supported filter keys (all optional):
        - ``deployment_name`` — exact match
        - ``winner`` — exact match
        - ``prompt_hash`` — exact match

    Returns a list of matching documents ordered by timestamp descending.
    """
    conditions: List[str] = []
    parameters: List[Dict[str, Any]] = []

    if filters:
        if filters.get("deployment_name"):
            conditions.append("c.deployment_name = @deployment_name")
            parameters.append({"name": "@deployment_name", "value": filters["deployment_name"]})
        if filters.get("winner"):
            conditions.append("c.winner = @winner")
            parameters.append({"name": "@winner", "value": filters["winner"]})
        if filters.get("prompt_hash"):
            conditions.append("c.prompt_hash = @prompt_hash")
            parameters.append({"name": "@prompt_hash", "value": filters["prompt_hash"]})

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"SELECT * FROM c{where_clause} ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit"
    parameters.append({"name": "@limit", "value": limit})

    items = list(
        container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
    )

    return items


def query_leaderboard_data(container) -> List[Dict[str, Any]]:
    """Retrieve fields needed for Python-side leaderboard aggregation.

    Returns records with ``deployment_name``, ``winner``, ``latency_ms``,
    and ``timestamp`` — enough to compute wins, win-rate, average latency,
    and task count in the application layer.
    """
    query = (
        "SELECT c.deployment_name, c.winner, c.is_winner, c.latency_ms, "
        "c.timestamp, c.models_compared, c.total_rounds, "
        "c.aggregate_stats FROM c"
    )

    items = list(
        container.query_items(
            query=query,
            enable_cross_partition_query=True,
        )
    )

    return items


def query_prompt_history(
    container,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve recent distinct prompts ordered by timestamp descending.

    Returns documents with ``prompt_hash``, ``prompt_text`` (if persisted),
    and ``timestamp``.  Results are de-duplicated by *prompt_hash* in Python
    since Cosmos SQL doesn't support ``DISTINCT`` on complex projections
    efficiently.
    """
    query = (
        "SELECT c.prompt_hash, c.prompt_text, c.timestamp "
        "FROM c ORDER BY c.timestamp DESC"
    )

    raw_items = list(
        container.query_items(
            query=query,
            enable_cross_partition_query=True,
        )
    )

    # De-duplicate by prompt_hash, keeping the newest occurrence (first seen
    # because the query is ordered by timestamp DESC).
    seen_hashes: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for item in raw_items:
        ph = item.get("prompt_hash", "")
        if ph and ph not in seen_hashes:
            seen_hashes.add(ph)
            unique.append(item)
            if len(unique) >= limit:
                break

    return unique
