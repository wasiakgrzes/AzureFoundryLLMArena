from __future__ import annotations

from typing import Any

from azure.ai.inference import ChatCompletionsClient


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_endpoint(client: Any) -> str | None:
    endpoint = _safe_get(client, "endpoint") or _safe_get(client, "_endpoint")
    if endpoint is None:
        return None

    endpoint_text = str(endpoint).strip()
    return endpoint_text or None


def _inference_endpoint(endpoint: str) -> str:
    normalized = endpoint.strip().rstrip("/")
    if normalized.endswith("/models"):
        return normalized
    return f"{normalized}/models"


def _extract_credential(client: Any) -> Any:
    return _safe_get(client, "credential") or _safe_get(client, "_credential")


def _resolve_inference_client(client: Any) -> ChatCompletionsClient:
    endpoint = _extract_endpoint(client)
    credential = _extract_credential(client)

    if not endpoint:
        raise ValueError("Could not resolve endpoint from initialized SDK client")

    if credential is None:
        raise ValueError("Could not resolve credential from initialized SDK client")

    return ChatCompletionsClient(endpoint=_inference_endpoint(endpoint), credential=credential)


def _extract_output_text(response: Any) -> str | None:
    choices = _safe_get(response, "choices")
    if not choices:
        return None

    first_choice = choices[0]
    message = _safe_get(first_choice, "message")
    if message is None:
        return None

    content = _safe_get(message, "content")
    if content is None:
        return None

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        collected_parts: list[str] = []
        for item in content:
            text = _safe_get(item, "text")
            if isinstance(text, str) and text:
                collected_parts.append(text)
            elif isinstance(item, str) and item:
                collected_parts.append(item)

        if collected_parts:
            return "".join(collected_parts)

    text_field = _safe_get(message, "text")
    if isinstance(text_field, str):
        return text_field

    return None
