from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


_PRICING_CACHE: Optional[Dict[str, Dict[str, float]]] = None


def _pricing_file_path() -> Path:
    return Path(__file__).with_name("model_pricing.json")


def load_pricing() -> Dict[str, Dict[str, float]]:
    global _PRICING_CACHE

    if _PRICING_CACHE is not None:
        return _PRICING_CACHE

    pricing_path = _pricing_file_path()
    with pricing_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    normalized: Dict[str, Dict[str, float]] = {}
    for model_name, pricing in data.items():
        normalized[str(model_name).lower()] = {
            "input_per_1k": float(pricing["input_per_1k"]),
            "output_per_1k": float(pricing["output_per_1k"]),
        }

    _PRICING_CACHE = normalized
    return _PRICING_CACHE


def calculate_cost(
    model_name: Optional[str],
    input_tokens: Optional[float],
    output_tokens: Optional[float],
) -> Optional[float]:
    if not model_name:
        return None

    if input_tokens is None or output_tokens is None:
        return None

    pricing = load_pricing().get(model_name.lower())
    if pricing is None:
        return None

    input_cost = (float(input_tokens) / 1000.0) * pricing["input_per_1k"]
    output_cost = (float(output_tokens) / 1000.0) * pricing["output_per_1k"]

    return input_cost + output_cost
