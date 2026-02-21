from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping


def generate_export_config(endpoint: str, deployment: Mapping[str, Any]) -> str:
    model_name = str(deployment.get("model_name") or "unknown")
    export_payload = {
        "endpoint": str(endpoint),
        "deployment_name": str(deployment.get("deployment_name") or "unknown"),
        "api_type": "azure_foundry",
        "inference_type": str(deployment.get("model_type") or "unknown"),
        "model_name": model_name,
        "pricing_reference": model_name,
        "export_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    for forbidden_key in ("api_key", "key", "credential", "token"):
        if forbidden_key in export_payload:
            raise ValueError("Export payload contains a forbidden secret field")

    return json.dumps(export_payload, indent=2)
