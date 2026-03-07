from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from azure.ai.inference import ChatCompletionsClient


def _result(check_name: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "check_name": check_name,
        "status": status,
        "detail": detail,
    }
    payload.update(extra)
    return payload


def _normalize_text(text: Any) -> str | None:
    if text is None:
        return None
    if isinstance(text, str):
        return text
    return str(text)


def _json_structure_hints(text: str) -> list[str]:
    hints: list[str] = []
    stripped = text.lstrip()
    if stripped.startswith("```"):
        hints.append("output starts with a Markdown code fence")

    first_non_space = stripped[:1]
    if first_non_space and first_non_space not in {"{", "["}:
        hints.append(f"first non-whitespace character is '{first_non_space}' (expected '{{' or '[')")

    if "{" in text or "[" in text:
        hints.append("JSON-like block markers were detected in the output")

    return hints


def _parse_model_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if not candidate:
        return None

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate, flags=re.IGNORECASE)
    if fence_match:
        fenced_json = fence_match.group(1)
        try:
            parsed = json.loads(fenced_json)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    object_match = re.search(r"\{[\s\S]*\}", candidate)
    if not object_match:
        return None

    try:
        parsed = json.loads(object_match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _friendly_semantic_error(ex: Exception, timeout_seconds: int) -> str:
    message = str(ex)
    lowered = message.lower()

    if isinstance(ex, TimeoutError) or "timeout" in lowered or "timed out" in lowered:
        return f"Inspector model timed out after {timeout_seconds} seconds"

    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return "Inspector request was rate-limited (429). Retry in a moment."

    if "401" in lowered or "403" in lowered or "unauthorized" in lowered or "authentication" in lowered:
        return "Inspector authentication failed. Verify endpoint/key configuration."

    if "404" in lowered or "not found" in lowered or "deployment" in lowered and "not" in lowered:
        return "Inspector deployment was not found or is unavailable for this endpoint."

    if (
        "context" in lowered
        or "token" in lowered and "maximum" in lowered
        or "request too large" in lowered
        or "payload too large" in lowered
        or "input too long" in lowered
    ):
        return (
            "Inspector request exceeded model context limits. "
            "Use shorter outputs/prompts or a larger-context inspector deployment."
        )

    if "connection" in lowered or "network" in lowered or "dns" in lowered:
        return "Network error while calling inspector model. Please retry."

    safe_message = " ".join(message.split())
    if not safe_message:
        return "Semantic inspection failed"
    return f"Semantic inspection failed: {safe_message[:220]}"


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


def validate_json(text: Any) -> dict[str, Any]:
    normalized = _normalize_text(text)
    if normalized is None:
        return _result("validate_json", "fail", "No output to validate")
    if not normalized.strip():
        return _result("validate_json", "fail", "Empty output")

    try:
        json.loads(normalized)
        return _result("validate_json", "pass", "Valid JSON structure")
    except json.JSONDecodeError as ex:
        extracted = _parse_model_json(normalized)
        hints = _json_structure_hints(normalized)

        if extracted is not None:
            detail = (
                "Strict JSON validation failed, but a JSON object was detected inside surrounding text. "
                "This usually means extra prefix/suffix text or code fences are present. "
                f"Parser detail: {str(ex)}"
            )
            return _result("validate_json", "fail", detail, hints=hints)

        detail = f"Invalid JSON: {str(ex)}"
        if hints:
            detail = f"{detail}. Hints: {'; '.join(hints)}"
        return _result("validate_json", "fail", detail, hints=hints)


def validate_markdown(text: Any) -> dict[str, Any]:
    normalized = _normalize_text(text)
    if normalized is None:
        return _result("validate_markdown", "fail", "No output to validate")
    if not normalized.strip():
        return _result("validate_markdown", "fail", "Empty output")

    has_heading = bool(re.search(r"(?m)^\s{0,3}#{1,6}\s+\S", normalized))
    has_list = bool(re.search(r"(?m)^\s*[-*+]\s+\S", normalized))

    heading_count = len(re.findall(r"(?m)^\s{0,3}#{1,6}\s+\S", normalized))
    list_count = len(re.findall(r"(?m)^\s*[-*+]\s+\S", normalized))

    if has_heading or has_list:
        found: list[str] = []
        if has_heading:
            found.append(f"headings={heading_count}")
        if has_list:
            found.append(f"list_items={list_count}")
        return _result("validate_markdown", "pass", f"Found Markdown structure: {', '.join(found)}")

    lines = [line for line in normalized.splitlines() if line.strip()]
    sample = lines[0][:120] if lines else ""
    return _result(
        "validate_markdown",
        "fail",
        (
            "No Markdown structure detected (missing heading and list markers). "
            f"Non-empty lines={len(lines)}. First line sample: {sample}"
        ),
    )


def validate_xml(text: Any) -> dict[str, Any]:
    normalized = _normalize_text(text)
    if normalized is None:
        return _result("validate_xml", "fail", "No output to validate")
    if not normalized.strip():
        return _result("validate_xml", "fail", "Empty output")

    try:
        ET.fromstring(normalized)
        return _result("validate_xml", "pass", "Valid XML structure")
    except ET.ParseError as ex:
        return _result("validate_xml", "fail", f"Invalid XML: {str(ex)}")


def check_required_fields(text: Any, required_fields: list[str]) -> dict[str, Any]:
    normalized = _normalize_text(text)
    if normalized is None:
        return _result("required_fields", "fail", "No output to validate", fields=[])
    if not normalized.strip():
        return _result("required_fields", "fail", "Empty output", fields=[])

    cleaned_fields = [field.strip() for field in required_fields if field and field.strip()]
    if not cleaned_fields:
        return _result("required_fields", "not_evaluated", "No required fields configured", fields=[])

    parsed: Any = None
    parse_mode = "strict"
    strict_error = ""

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as ex:
        strict_error = str(ex)
        parsed = _parse_model_json(normalized)
        parse_mode = "extracted"

    if parsed is None:
        field_statuses = [
            {
                "field_name": field,
                "found": False,
                "status": "not_evaluated",
                "detail": "Cannot evaluate fields: invalid JSON",
            }
            for field in cleaned_fields
        ]
        return _result(
            "required_fields",
            "not_evaluated",
            f"Cannot evaluate fields: invalid JSON ({strict_error})",
            fields=field_statuses,
        )

    if not isinstance(parsed, dict):
        field_statuses = [
            {
                "field_name": field,
                "found": False,
                "status": "not_evaluated",
                "detail": "Cannot evaluate fields: top-level JSON is not an object",
            }
            for field in cleaned_fields
        ]
        return _result(
            "required_fields",
            "not_evaluated",
            "Cannot evaluate fields: top-level JSON is not an object",
            fields=field_statuses,
        )

    field_statuses = []
    missing_fields: list[str] = []
    for field in cleaned_fields:
        found = field in parsed
        if not found:
            missing_fields.append(field)
        field_statuses.append(
            {
                "field_name": field,
                "found": found,
                "status": "found" if found else "missing",
            }
        )

    detail_prefix = ""
    if parse_mode == "extracted":
        detail_prefix = "Required fields evaluated from extracted JSON block. "

    if missing_fields:
        return _result(
            "required_fields",
            "fail",
            f"{detail_prefix}Missing required fields: {', '.join(missing_fields)}",
            fields=field_statuses,
        )

    return _result(
        "required_fields",
        "pass",
        f"{detail_prefix}All required fields are present",
        fields=field_statuses,
    )


def check_no_extra_text(text: Any, format_type: str) -> dict[str, Any]:
    normalized = _normalize_text(text)
    if normalized is None:
        return _result("no_extra_text", "fail", "No output to validate")
    if not normalized.strip():
        return _result("no_extra_text", "fail", "Empty output")

    format_key = (format_type or "").strip().lower()

    if format_key == "markdown":
        return _result(
            "no_extra_text",
            "not_evaluated",
            "No-extra-text check is skipped for Markdown due to ambiguous boundaries",
        )

    if format_key in {"", "n/a", "na", "none"}:
        return _result(
            "no_extra_text",
            "not_evaluated",
            "No-extra-text check skipped because validation format is N/A",
        )

    start_index = -1
    end_index = -1

    if format_key == "json":
        left_candidates = [idx for idx in (normalized.find("{"), normalized.find("[")) if idx >= 0]
        if left_candidates:
            start_index = min(left_candidates)

        right_candidates = [idx for idx in (normalized.rfind("}"), normalized.rfind("]")) if idx >= 0]
        if right_candidates:
            end_index = max(right_candidates)
    elif format_key == "xml":
        start_index = normalized.find("<")
        end_index = normalized.rfind(">")
    else:
        return _result("no_extra_text", "not_evaluated", f"Unsupported format for no-extra-text check: {format_type}")

    if start_index < 0 or end_index < 0 or end_index < start_index:
        return _result("no_extra_text", "fail", f"Could not find a structured {format_key.upper()} block")

    prefix = normalized[:start_index].strip()
    suffix = normalized[end_index + 1 :].strip()

    if not prefix and not suffix:
        return _result("no_extra_text", "pass", "No extra text found outside structured content")

    details: list[str] = []
    if prefix:
        details.append(f"Prefix extra text: {prefix[:200]}")
    if suffix:
        details.append(f"Suffix extra text: {suffix[:200]}")

    return _result("no_extra_text", "fail", " | ".join(details))


def run_semantic_inspection(
    text: Any,
    expected_tone: str,
    expected_persona: str,
    inspector_client: Any,
    inspector_deployment: str,
    custom_instructions: str = "",
    include_task_fulfillment_report: bool = False,
    validation_format: str = "n/a",
    original_prompt: str = "",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    normalized = _normalize_text(text)
    if normalized is None or not normalized.strip():
        return {
            "status": "error",
            "detail": "Cannot run semantic inspection: empty output",
            "tone_match": None,
            "persona_match": None,
            "reason": "",
        }

    if not inspector_client:
        return {
            "status": "error",
            "detail": "Cannot run semantic inspection: inspector client is not initialized",
            "tone_match": None,
            "persona_match": None,
            "reason": "",
        }

    if not str(inspector_deployment or "").strip():
        return {
            "status": "error",
            "detail": "Cannot run semantic inspection: inspector deployment is not selected",
            "tone_match": None,
            "persona_match": None,
            "reason": "",
        }

    tone_input = (expected_tone or "").strip() or "Not specified"
    persona_input = (expected_persona or "").strip() or "Not specified"

    system_prompt = (
        "You are an output inspector. Evaluate whether the candidate output matches requested tone "
        "and persona. Respond with strict JSON only."
    )

    expected_keys = "tone_match (boolean), persona_match (boolean), reason (string)"
    if include_task_fulfillment_report:
        expected_keys += ", task_fulfillment_match (boolean), task_fulfillment_reason (string)"

    normalized_format = (validation_format or "").strip().lower()
    if normalized_format not in {"json", "markdown", "xml"}:
        normalized_format = "n/a"

    if normalized_format == "n/a":
        task_mode_instruction = (
            "Task fulfillment mode: content-only. Do NOT fail based on output format/structure style "
            "(JSON/XML/Markdown/table/wrapping). Evaluate only whether the response fulfills substantive "
            "task intent and constraints."
        )
    else:
        task_mode_instruction = (
            f"Task fulfillment mode: include both content and selected format expectations ({normalized_format})."
        )

    max_candidate_chars = 6000
    candidate_output = normalized
    was_truncated = False
    if len(candidate_output) > max_candidate_chars:
        candidate_output = candidate_output[:max_candidate_chars]
        was_truncated = True

    user_prompt = (
        f"Return ONLY a JSON object with keys: {expected_keys}.\n"
        f"Selected validation format: {normalized_format}\n"
        f"{task_mode_instruction}\n"
        f"Expected tone: {tone_input}\n"
        f"Expected persona: {persona_input}\n"
        f"Original user prompt: {(original_prompt or '').strip() or 'Not provided'}\n"
        f"Custom inspector instructions: {(custom_instructions or '').strip() or 'None'}\n"
        f"Candidate output truncated: {'yes' if was_truncated else 'no'}\n"
        "Candidate output:\n"
        f"{candidate_output}"
    )

    try:
        inference_client = _resolve_inference_client(inspector_client)
        response = inference_client.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=str(inspector_deployment).strip(),
            timeout=timeout_seconds,
        )

        output_text = _extract_output_text(response)
        if output_text is None:
            return {
                "status": "error",
                "detail": "Inspector model returned an empty response",
                "tone_match": None,
                "persona_match": None,
                "reason": "",
            }

        parsed = _parse_model_json(output_text)
        if parsed is None:
            return {
                "status": "error",
                "detail": "Inspector model returned non-JSON output",
                "tone_match": None,
                "persona_match": None,
                "reason": "",
            }

        tone_match = parsed.get("tone_match")
        persona_match = parsed.get("persona_match")
        reason = str(parsed.get("reason") or "").strip()
        task_fulfillment_match = parsed.get("task_fulfillment_match")
        task_fulfillment_reason = str(parsed.get("task_fulfillment_reason") or "").strip()

        return {
            "status": "ok",
            "detail": "Semantic inspection completed",
            "tone_match": bool(tone_match) if isinstance(tone_match, bool) else None,
            "persona_match": bool(persona_match) if isinstance(persona_match, bool) else None,
            "reason": reason,
            "task_fulfillment_match": (
                bool(task_fulfillment_match)
                if isinstance(task_fulfillment_match, bool)
                else None
            ),
            "task_fulfillment_reason": task_fulfillment_reason,
        }
    except Exception as ex:
        return {
            "status": "error",
            "detail": _friendly_semantic_error(ex, timeout_seconds),
            "tone_match": None,
            "persona_match": None,
            "reason": "",
            "task_fulfillment_match": None,
            "task_fulfillment_reason": "",
        }


def check_tone(
    text: Any,
    expected_tone: str,
    inspector_client: Any,
    inspector_deployment: str,
    semantic_payload: dict[str, Any] | None = None,
    expected_persona: str = "",
    custom_instructions: str = "",
    include_task_fulfillment_report: bool = False,
    validation_format: str = "n/a",
    original_prompt: str = "",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if not (expected_tone or "").strip():
        return _result("tone_check", "not_evaluated", "Expected tone is not configured")

    payload = semantic_payload or run_semantic_inspection(
        text=text,
        expected_tone=expected_tone,
        expected_persona=expected_persona,
        inspector_client=inspector_client,
        inspector_deployment=inspector_deployment,
        custom_instructions=custom_instructions,
        include_task_fulfillment_report=include_task_fulfillment_report,
        validation_format=validation_format,
        original_prompt=original_prompt,
        timeout_seconds=timeout_seconds,
    )

    if payload.get("status") != "ok":
        return _result("tone_check", "error", str(payload.get("detail") or "Tone check failed"))

    tone_match = payload.get("tone_match")
    if tone_match is None:
        return _result("tone_check", "error", "Inspector result is missing tone_match")

    reason = str(payload.get("reason") or "")
    if tone_match:
        detail = "Tone matches expected style"
        if reason:
            detail = f"{detail}. Reason: {reason}"
        return _result("tone_check", "pass", detail)

    detail = "Tone does not match expected style"
    if reason:
        detail = f"{detail}. Reason: {reason}"
    return _result("tone_check", "fail", detail)


def check_persona(
    text: Any,
    expected_persona: str,
    inspector_client: Any,
    inspector_deployment: str,
    semantic_payload: dict[str, Any] | None = None,
    expected_tone: str = "",
    custom_instructions: str = "",
    include_task_fulfillment_report: bool = False,
    validation_format: str = "n/a",
    original_prompt: str = "",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if not (expected_persona or "").strip():
        return _result("persona_check", "not_evaluated", "Expected persona is not configured")

    payload = semantic_payload or run_semantic_inspection(
        text=text,
        expected_tone=expected_tone,
        expected_persona=expected_persona,
        inspector_client=inspector_client,
        inspector_deployment=inspector_deployment,
        custom_instructions=custom_instructions,
        include_task_fulfillment_report=include_task_fulfillment_report,
        validation_format=validation_format,
        original_prompt=original_prompt,
        timeout_seconds=timeout_seconds,
    )

    if payload.get("status") != "ok":
        return _result("persona_check", "error", str(payload.get("detail") or "Persona check failed"))

    persona_match = payload.get("persona_match")
    if persona_match is None:
        return _result("persona_check", "error", "Inspector result is missing persona_match")

    reason = str(payload.get("reason") or "")
    if persona_match:
        detail = "Persona matches expected profile"
        if reason:
            detail = f"{detail}. Reason: {reason}"
        return _result("persona_check", "pass", detail)

    detail = "Persona does not match expected profile"
    if reason:
        detail = f"{detail}. Reason: {reason}"
    return _result("persona_check", "fail", detail)


def check_task_fulfillment(
    semantic_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if semantic_payload is None:
        return _result("task_fulfillment", "not_evaluated", "Task fulfillment report is not available")

    if semantic_payload.get("status") != "ok":
        return _result(
            "task_fulfillment",
            "error",
            str(semantic_payload.get("detail") or "Task fulfillment analysis failed"),
        )

    task_match = semantic_payload.get("task_fulfillment_match")
    task_reason = str(semantic_payload.get("task_fulfillment_reason") or "").strip()

    if task_match is None:
        return _result(
            "task_fulfillment",
            "not_evaluated",
            "Inspector response did not include task fulfillment fields",
        )

    if task_match:
        return _result(
            "task_fulfillment",
            "pass",
            task_reason or "Output appears to fulfill the requested task constraints",
        )

    return _result(
        "task_fulfillment",
        "fail",
        task_reason or "Output does not fully satisfy the requested task constraints",
    )


def run_all_checks(
    text: Any,
    format_type: str,
    required_fields: list[str],
    enabled_checks: dict[str, bool],
    inspector_client: Any = None,
    inspector_deployment: str = "",
    expected_tone: str = "",
    expected_persona: str = "",
    custom_instructions: str = "",
    include_task_fulfillment_report: bool = False,
    original_prompt: str = "",
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    normalized = _normalize_text(text)
    if normalized is None or not normalized.strip():
        return [
            _result("summary", "fail", "Empty output response"),
        ]

    format_key = (format_type or "").strip().lower()

    if format_key == "json" and enabled_checks.get("validate_json", False):
        checks.append(validate_json(normalized))
    if format_key == "markdown" and enabled_checks.get("validate_markdown", False):
        checks.append(validate_markdown(normalized))
    if format_key == "xml" and enabled_checks.get("validate_xml", False):
        checks.append(validate_xml(normalized))

    if enabled_checks.get("required_fields", False):
        checks.append(check_required_fields(normalized, required_fields))

    if enabled_checks.get("no_extra_text", False):
        checks.append(check_no_extra_text(normalized, format_key))

    need_tone = enabled_checks.get("tone_check", False)
    need_persona = enabled_checks.get("persona_check", False)
    need_task_fulfillment = include_task_fulfillment_report

    semantic_payload: dict[str, Any] | None = None
    if need_tone or need_persona or need_task_fulfillment:
        semantic_payload = run_semantic_inspection(
            text=normalized,
            expected_tone=expected_tone,
            expected_persona=expected_persona,
            inspector_client=inspector_client,
            inspector_deployment=inspector_deployment,
            custom_instructions=custom_instructions,
            include_task_fulfillment_report=include_task_fulfillment_report,
            validation_format=format_key,
            original_prompt=original_prompt,
            timeout_seconds=timeout_seconds,
        )

    if need_tone:
        checks.append(
            check_tone(
                text=normalized,
                expected_tone=expected_tone,
                inspector_client=inspector_client,
                inspector_deployment=inspector_deployment,
                semantic_payload=semantic_payload,
                expected_persona=expected_persona,
                custom_instructions=custom_instructions,
                include_task_fulfillment_report=include_task_fulfillment_report,
                validation_format=format_key,
                original_prompt=original_prompt,
                timeout_seconds=timeout_seconds,
            )
        )

    if need_persona:
        checks.append(
            check_persona(
                text=normalized,
                expected_persona=expected_persona,
                inspector_client=inspector_client,
                inspector_deployment=inspector_deployment,
                semantic_payload=semantic_payload,
                expected_tone=expected_tone,
                custom_instructions=custom_instructions,
                include_task_fulfillment_report=include_task_fulfillment_report,
                validation_format=format_key,
                original_prompt=original_prompt,
                timeout_seconds=timeout_seconds,
            )
        )

    if need_task_fulfillment:
        checks.append(check_task_fulfillment(semantic_payload))

    return checks


def highlighted_output_html(output_text: Any, checks: list[dict[str, Any]]) -> str:
    text = _normalize_text(output_text) or ""
    escaped_text = html.escape(text)

    violations = [item for item in checks if item.get("status") == "fail"]
    validations = [item for item in checks if item.get("status") == "pass"]
    informational = [item for item in checks if item.get("status") in {"error", "not_evaluated"}]

    sections: list[str] = [
        f"<div><span style='color:green'>Validated checks: {len(validations)}</span></div>",
        f"<div><span style='color:red'>Violations: {len(violations)}</span></div>",
        f"<div><span style='color:blue'>Informational: {len(informational)}</span></div>",
        "<hr/>",
        f"<pre style='white-space: pre-wrap; margin: 0;'>{escaped_text}</pre>",
    ]

    return "\n".join(sections)
