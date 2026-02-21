from dataclasses import dataclass
from typing import Mapping
from azure.core.credentials import AzureKeyCredential


@dataclass
class FoundryApiKeyClient:
    endpoint: str
    credential: AzureKeyCredential


def create_client(config: Mapping[str, str]) -> FoundryApiKeyClient:
    endpoint = (config.get("endpoint") or "").strip()
    api_key = (config.get("api_key") or "").strip()

    if not endpoint:
        raise ValueError("Missing required config key: endpoint")

    if not api_key:
        raise ValueError("Missing required config key: api_key")

    return FoundryApiKeyClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
    )
