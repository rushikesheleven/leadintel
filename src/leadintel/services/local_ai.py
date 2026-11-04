"""
Local AI Service via Ollama.

Communicates with locally running Ollama instances (default http://localhost:11434).
Strictly local-first:
- Enforces local loopback interface (localhost / 127.0.0.1 / ::1). Rejects external/cloud hosts.
- Bypasses ambient environment proxies (trust_env=False) to prevent data exfiltration.
- Rejects HTTP redirects (follow_redirects=False).
- Never sends business data to external/cloud services.
- Never falls back to cloud AI.
- Handles Ollama offline, uninstalled, or missing model gracefully.
- Does not download models automatically.
- Enforces request timeouts and JSON structured responses.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from ..config import settings
from .url_validator import SecurityValidationError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0

LOCAL_LOOPBACK_HOSTS = {"localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0"}


class OllamaError(Exception):
    """Base exception for Ollama interactions."""


class OllamaUnavailableError(OllamaError):
    """Raised when the Ollama service is unreachable or not running."""


class OllamaModelNotFoundError(OllamaError):
    """Raised when the specified model is not loaded in Ollama."""


class LocalAIClient:
    """HTTP client interacting strictly with locally running Ollama API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        raw_url = (base_url or settings.ollama_base_url).rstrip("/")
        parsed = urlparse(raw_url)
        host = (parsed.hostname or "").lower().strip("[]")

        # Guarantee local-first privacy: reject external cloud or remote endpoints
        if host and host not in LOCAL_LOOPBACK_HOSTS:
            raise SecurityValidationError(
                f"Ollama endpoint '{raw_url}' is not a local loopback address. "
                "LeadIntel strictly enforces that Ollama must run on the local machine "
                "(localhost / 127.0.0.1 / ::1) to ensure local-first privacy and prevent data exfiltration."
            )

        self.base_url = raw_url
        self.model = model or settings.ollama_model
        self.timeout = timeout

    async def is_available(self, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Check if local Ollama server is running and reachable."""
        endpoint = f"{self.base_url}/api/tags"
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=3.0, trust_env=False, follow_redirects=False)
            should_close = True
        try:
            resp = await client.get(endpoint)
            return resp.status_code == 200
        except Exception:
            return False
        finally:
            if should_close:
                await client.aclose()

    async def list_models(self, client: Optional[httpx.AsyncClient] = None) -> list[str]:
        """List locally available models in Ollama."""
        endpoint = f"{self.base_url}/api/tags"
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=5.0, trust_env=False, follow_redirects=False)
            should_close = True
        try:
            resp = await client.get(endpoint)
            if resp.status_code != 200:
                raise OllamaUnavailableError(f"Ollama returned HTTP {resp.status_code}")
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return [m for m in models if m]
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaUnavailableError(
                f"Local Ollama server is not running at {self.base_url}. Start it with 'ollama serve'."
            ) from e
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Failed to query Ollama models: {e}") from e
        finally:
            if should_close:
                await client.aclose()

    async def check_model_installed(self, model_name: Optional[str] = None, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Check if a specific model or the default model is installed locally."""
        target = model_name or self.model
        available = await self.list_models(client=client)
        # Match exact name or without tag (e.g. 'llama3:latest' matches 'llama3')
        return any(m == target or m.split(":")[0] == target for m in available)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        format_json: bool = False,
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """
        Generate completion from local Ollama model.

        Args:
            prompt: User prompt.
            system_prompt: Optional system instructions.
            model: Specific model override.
            format_json: If True, request JSON formatting from Ollama.
            client: Optional HTTPX async client.
        """
        target_model = model or self.model
        endpoint = f"{self.base_url}/api/generate"

        payload: dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        should_close = False
        if client is None:
            # Enforce trust_env=False to prevent proxy interception, and follow_redirects=False
            client = httpx.AsyncClient(timeout=self.timeout, trust_env=False, follow_redirects=False)
            should_close = True

        try:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 404:
                raise OllamaModelNotFoundError(
                    f"Model '{target_model}' not found in local Ollama. Install with 'ollama pull {target_model}'."
                )
            if resp.status_code != 200:
                raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            response_text = data.get("response", "")
            return response_text.strip()

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaUnavailableError(
                f"Local Ollama server is not running at {self.base_url}. Start it with 'ollama serve'."
            ) from e
        except httpx.ReadTimeout as e:
            raise OllamaError(f"Ollama request timed out after {self.timeout}s.") from e
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Ollama inference error: {e}") from e
        finally:
            if should_close:
                await client.aclose()


# Default singleton instance
local_ai_client = LocalAIClient()
