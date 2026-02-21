import os
from typing import Dict

from dotenv import load_dotenv


def load_config() -> Dict[str, str]:
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

    return {
        "endpoint": endpoint,
        "api_key": api_key,
    }
