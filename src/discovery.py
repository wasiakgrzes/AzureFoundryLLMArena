from __future__ import annotations

import json
import os
from urllib import error as urllib_error
from urllib import request as urllib_request
from typing import Any, Dict, Iterable, List


COMPATIBLE_MODEL_TYPES = {
    "chat",
    "completion",
    "text",
    "text-generation",
    "text_generation",
    "chat-completion",
}

NON_TEXT_TYPE_HINTS = {
    "embedding",
    "image",
    "vision",
    "audio",
    "speech",
    "whisper",
    "tts",
}

TEXT_TYPE_HINTS = {
    "chat",
    "completion",
    "text",
    "gpt",
    "phi",
    "llama",
    "mistral",
}


class DeploymentDiscoveryError(RuntimeError):
    pass


def _friendly_discovery_error(ex: Exception, timeout_seconds: int) -> str:
    message = str(ex).lower()

    if isinstance(ex, TimeoutError) or "timeout" in message or "timed out" in message:
        return (
            "Deployment discovery timed out. "
            f"Please retry or check network connectivity (timeout: {timeout_seconds}s)."
        )

    if "401" in message or "403" in message or "authentication" in message or "unauthorized" in message:
        return "Deployment discovery failed due to authentication. Check endpoint and API key configuration."

    if "connection" in message or "network" in message or "dns" in message:
        return "Deployment discovery failed due to network connectivity. Please verify network access and retry."

    if "404" in message or "not found" in message:
        return (
            "Deployment discovery failed because the endpoint does not expose deployment listing. "
            "For API-key inference endpoints, set AZURE_FOUNDRY_DEPLOYMENTS (comma-separated) or DEPLOYMENT_NAME."
        )

    return "Deployment discovery failed. Please verify Azure Foundry configuration and try again."


def _extract_endpoint(client: Any) -> str:
    endpoint = _read_value(client, "endpoint", "_endpoint", default="")
    return str(endpoint).strip()


def _extract_api_key(client: Any) -> str:
    credential = _read_value(client, "credential", "_credential")
    key = _read_value(credential, "key", default="")
    return str(key).strip()


def _normalize_endpoint_for_rest(endpoint: str) -> str:
    normalized = endpoint.strip().rstrip("/")
    if normalized.endswith("/models"):
        normalized = normalized[: -len("/models")]
    return normalized


def _payload_list_candidates(payload: Any) -> tuple[bool, List[Any]]:
    if not isinstance(payload, dict):
        return False, []

    for key in ("data", "value", "deployments", "items", "models"):
        value = payload.get(key)
        if isinstance(value, list):
            return True, value

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("data", "value", "deployments", "items", "models"):
            value = result.get(key)
            if isinstance(value, list):
                return True, value

    return False, []


def _http_get_json(url: str, api_key: str, timeout_seconds: int) -> Any:
    request = urllib_request.Request(
        url,
        headers={
            "api-key": api_key,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def _list_deployments_via_rest(client: Any, timeout_seconds: int) -> List[Any]:
    endpoint = _extract_endpoint(client)
    api_key = _extract_api_key(client)

    if not endpoint:
        raise DeploymentDiscoveryError("Deployment discovery fallback failed: missing endpoint on SDK client")

    if not api_key:
        raise DeploymentDiscoveryError("Deployment discovery fallback failed: missing API key on SDK client")

    base = _normalize_endpoint_for_rest(endpoint)
    candidate_urls = [
        f"{base}/openai/deployments?api-version=2024-10-21",
        f"{base}/openai/deployments?api-version=2024-06-01",
        f"{base}/models?api-version=2024-05-01-preview",
    ]

    errors: List[Exception] = []
    for url in candidate_urls:
        try:
            payload = _http_get_json(url, api_key=api_key, timeout_seconds=timeout_seconds)
            is_list_payload, deployments = _payload_list_candidates(payload)
            if is_list_payload:
                return deployments
        except urllib_error.URLError as ex:
            errors.append(ex)
        except json.JSONDecodeError as ex:
            errors.append(ex)

    if errors:
        raise DeploymentDiscoveryError(_friendly_discovery_error(errors[-1], timeout_seconds))

    raise DeploymentDiscoveryError(
        "Deployment discovery fallback failed: endpoint returned an unsupported payload shape"
    )


def _deployment_names_from_env() -> List[str]:
    raw_multi = (os.environ.get("AZURE_FOUNDRY_DEPLOYMENTS") or "").strip()
    if raw_multi:
        return [item.strip() for item in raw_multi.split(",") if item.strip()]

    raw_single = (os.environ.get("DEPLOYMENT_NAME") or "").strip()
    if raw_single:
        return [raw_single]

    return []


def _deployments_from_env() -> List[Dict[str, Any]]:
    names = _deployment_names_from_env()
    return [
        {
            "deployment_name": name,
            "model_name": name,
            "model_type": "chat",
            "raw_metadata": {"source": "env-fallback"},
        }
        for name in names
    ]


def _read_value(item: Any, *candidate_keys: str, default: Any = None) -> Any:
    for key in candidate_keys:
        if isinstance(item, dict) and key in item:
            value = item.get(key)
            if value is not None:
                return value
        elif hasattr(item, key):
            value = getattr(item, key)
            if value is not None:
                return value
    return default


def _normalize_text(value: Any, fallback: str = "unknown") -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else fallback


def _extract_model_name(raw_deployment: Any) -> str:
    model_name = _read_value(raw_deployment, "model_name", "model", "model_id")

    if isinstance(model_name, dict):
        model_name = _read_value(model_name, "name", "id", "model")
    elif model_name is not None and not isinstance(model_name, str):
        model_name = _read_value(model_name, "name", "id")

    return _normalize_text(model_name, fallback="unknown")


def _extract_model_type(raw_deployment: Any, model_name: str) -> str:
    explicit_type = _read_value(
        raw_deployment,
        "model_type",
        "type",
        "kind",
        "inference_type",
        "task",
    )
    normalized_explicit = _normalize_text(explicit_type, fallback="unknown").lower()

    if normalized_explicit != "unknown":
        return normalized_explicit

    lowered_model_name = model_name.lower()
    if any(hint in lowered_model_name for hint in NON_TEXT_TYPE_HINTS):
        return "non-text"
    if any(hint in lowered_model_name for hint in TEXT_TYPE_HINTS):
        return "text-generation"

    return "unknown"


def _is_text_compatible(model_type: str) -> bool:
    normalized = model_type.strip().lower()
    return normalized in COMPATIBLE_MODEL_TYPES


def _deployment_to_dict(raw_deployment: Any) -> Dict[str, Any]:
    deployment_name = _normalize_text(
        _read_value(raw_deployment, "deployment_name", "name", "id"),
        fallback="unknown",
    )
    model_name = _extract_model_name(raw_deployment)
    model_type = _extract_model_type(raw_deployment, model_name)

    return {
        "deployment_name": deployment_name,
        "model_name": model_name,
        "model_type": model_type,
        "raw_metadata": raw_deployment,
    }


def _list_deployments(client: Any, timeout_seconds: int) -> Iterable[Any]:
    sdk_errors: List[Exception] = []

    deployments_attr = getattr(client, "deployments", None)
    if deployments_attr is not None:
        list_method = getattr(deployments_attr, "list", None)
        if callable(list_method):
            try:
                return list_method(timeout=timeout_seconds)
            except TypeError:
                try:
                    return list_method()
                except Exception as ex:
                    sdk_errors.append(ex)
            except Exception as ex:
                sdk_errors.append(ex)

    list_method = getattr(client, "list_deployments", None)
    if callable(list_method):
        try:
            return list_method(timeout=timeout_seconds)
        except TypeError:
            try:
                return list_method()
            except Exception as ex:
                sdk_errors.append(ex)
        except Exception as ex:
            sdk_errors.append(ex)

    try:
        return _list_deployments_via_rest(client, timeout_seconds=timeout_seconds)
    except DeploymentDiscoveryError:
        if sdk_errors:
            raise DeploymentDiscoveryError(_friendly_discovery_error(sdk_errors[-1], timeout_seconds))
        raise


def discover_deployments(client: Any, timeout_seconds: int = 30) -> List[Dict[str, Any]]:
    try:
        raw_deployments = _list_deployments(client, timeout_seconds=timeout_seconds)
        normalized_deployments = [_deployment_to_dict(item) for item in raw_deployments]
    except DeploymentDiscoveryError:
        env_deployments = _deployments_from_env()
        if env_deployments:
            return env_deployments
        raise
    except Exception as ex:
        env_deployments = _deployments_from_env()
        if env_deployments:
            return env_deployments
        raise DeploymentDiscoveryError(_friendly_discovery_error(ex, timeout_seconds)) from ex

    compatible = [
        deployment
        for deployment in normalized_deployments
        if _is_text_compatible(deployment["model_type"])
    ]

    return compatible
