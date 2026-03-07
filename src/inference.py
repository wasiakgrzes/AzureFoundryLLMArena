from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional

from azure.ai.inference import ChatCompletionsClient


SUPPORTED_MODEL_TYPES = {
    "chat",
    "completion",
    "text",
    "text-generation",
    "text_generation",
    "chat-completion",
}


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_endpoint(client: Any) -> Optional[str]:
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


def _normalize_model_type(model_type: str) -> str:
    return (model_type or "").strip().lower()


def _resolve_inference_client(client: Any) -> ChatCompletionsClient:
    endpoint = _extract_endpoint(client)
    credential = _extract_credential(client)

    if not endpoint:
        raise ValueError("Could not resolve endpoint from initialized SDK client")

    if credential is None:
        raise ValueError("Could not resolve credential from initialized SDK client")

    return ChatCompletionsClient(endpoint=_inference_endpoint(endpoint), credential=credential)


def _friendly_inference_error(ex: Exception, timeout_seconds: int) -> str:
    message = str(ex).lower()

    if isinstance(ex, TimeoutError) or "timeout" in message or "timed out" in message:
        return f"Request timed out after {timeout_seconds} seconds"

    if "429" in message or "rate limit" in message or "too many requests" in message:
        return "Rate limit exceeded. Please wait and try again."

    if (
        "connection" in message
        or "network" in message
        or "dns" in message
        or "name resolution" in message
        or "unreachable" in message
    ):
        return "Network error while contacting Azure Foundry. Please check connectivity and try again."

    return "Inference request failed. Please verify deployment configuration and try again."


def _extract_output_text(response: Any) -> Optional[str]:
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
        collected_parts: List[str] = []
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


def _extract_usage(response: Any) -> Dict[str, Optional[int]]:
    usage = _safe_get(response, "usage")
    if usage is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    input_tokens = _safe_get(usage, "prompt_tokens")
    if input_tokens is None:
        input_tokens = _safe_get(usage, "input_tokens")

    output_tokens = _safe_get(usage, "completion_tokens")
    if output_tokens is None:
        output_tokens = _safe_get(usage, "output_tokens")

    total_tokens = _safe_get(usage, "total_tokens")

    return {
        "input_tokens": int(input_tokens) if input_tokens is not None else None,
        "output_tokens": int(output_tokens) if output_tokens is not None else None,
        "total_tokens": int(total_tokens) if total_tokens is not None else None,
    }


def run_inference(
    client: Any,
    deployment_name: str,
    model_type: str,
    prompt: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    start_time = time.perf_counter()

    try:
        normalized_type = _normalize_model_type(model_type)
        if normalized_type not in SUPPORTED_MODEL_TYPES:
            raise ValueError(
                f"Unsupported model type for inference: {model_type}"
            )

        inference_client = _resolve_inference_client(client)

        messages: List[Dict[str, str]] = []
        if conversation_history:
            for message in conversation_history:
                role = str(message.get("role", "")).strip()
                content = str(message.get("content", "")).strip()
                if role and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        response = inference_client.complete(
            messages=messages,
            model=deployment_name,
            timeout=timeout_seconds,
        )

        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000)

        usage = _extract_usage(response)
        output_text = _extract_output_text(response)
        response_model_name = _safe_get(response, "model") or deployment_name

        return {
            "deployment_name": deployment_name,
            "model_name": str(response_model_name),
            "output_text": output_text,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "latency_ms": latency_ms,
            "error": None,
        }
    except Exception as ex:
        return {
            "deployment_name": deployment_name,
            "model_name": None,
            "output_text": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "latency_ms": None,
            "error": _friendly_inference_error(ex, timeout_seconds),
        }


def run_batch_inference(
    client: Any,
    deployments: Iterable[Dict[str, Any]],
    prompt: str,
    conversation_history_by_deployment: Optional[Dict[str, List[Dict[str, str]]]] = None,
    timeout_seconds: int = 60,
) -> List[Dict[str, Any]]:
    deployment_list = list(deployments)
    if not deployment_list:
        return []

    def _infer(deployment: Dict[str, Any]) -> Dict[str, Any]:
        deployment_name = str(deployment.get("deployment_name", "unknown"))
        model_type = str(deployment.get("model_type", "unknown"))
        expected_model_name = deployment.get("model_name")

        result = run_inference(
            client=client,
            deployment_name=deployment_name,
            model_type=model_type,
            prompt=prompt,
            conversation_history=(conversation_history_by_deployment or {}).get(deployment_name),
            timeout_seconds=timeout_seconds,
        )

        if result.get("error") is None and expected_model_name:
            result["model_name"] = str(expected_model_name)

        return result

    with ThreadPoolExecutor(max_workers=len(deployment_list)) as executor:
        futures = [executor.submit(_infer, dep) for dep in deployment_list]
        results = [f.result() for f in futures]

    return results
