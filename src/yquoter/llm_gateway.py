# yquoter/llm_gateway.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""LLM Gateway -- Unified multi-provider AI analysis interface.

Automatically detects configured AI providers from system environment
variables, supports priority-based automatic fallback, and normalizes
common provider name aliases (e.g., "ChatGPT" -> "openai").
"""

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from yquoter.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Provider name normalization
# ---------------------------------------------------------------------------

#: Maps common brand/vendor names to canonical provider identifiers.
#: The key space is normalized (lowercase, no hyphens/spaces/underscores).
_PROVIDER_ALIASES: Dict[str, str] = {
    "deepseek": "deepseek",
    "openai": "openai",
    "chatgpt": "openai",
    "gpt": "openai",
    "gpt4": "openai",
    "gpt4o": "openai",
    "qwen": "qwen",
    "tongyi": "qwen",
    "kimi": "kimi",
    "moonshot": "kimi",
    "claude": "claude",
    "anthropic": "claude",
    "gemini": "gemini",
    "google": "gemini",
    "googlegemini": "gemini",
    "googlegemini": "gemini",
}


def normalize_provider_name(name: Optional[str]) -> Optional[str]:
    """Normalize a user-supplied provider name to its canonical identifier.

    Handles common variations in spelling and casing:

    * ``"ChatGPT"``, ``"Chat-GPT"``, ``"chat gpt"`` -> ``"openai"``
    * ``"Claude"``, ``"claude"``, ``"Anthropic"`` -> ``"claude"``
    * ``"DeepSeek"``, ``"deepseek"`` -> ``"deepseek"``

    Args:
        name: Raw provider name from user input, or ``None``.

    Returns:
        Optional[str]: Canonical provider name (e.g., ``"openai"``),
            or ``None`` if the input cannot be resolved.
    """
    if not name:
        return None
    cleaned = re.sub(r"[\s\-_]", "", name.strip().lower())
    return _PROVIDER_ALIASES.get(cleaned)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


@dataclass
class LLMProvider:
    """Configuration for a single LLM provider.

    Attributes:
        name: Canonical provider name (e.g., ``"deepseek"``).
        api_key_env: Environment variable name for the API key.
        api_base_env: Environment variable name for the API base URL.
        chat_endpoint: API path for chat completions
            (e.g., ``"/v1/chat/completions"``).
        default_model: Fallback model name when not overridden via env.
        priority: Numeric priority (lower = higher priority).
        model_env: Optional env var to override the model name.
        api_type: API protocol type -- ``"openai_compat"`` (default),
            ``"anthropic"``, or ``"gemini"``.
    """
    name: str
    api_key_env: str
    api_base_env: str
    default_model: str
    priority: int
    model_env: Optional[str] = None
    api_type: str = "openai_compat"
    chat_endpoint: str = "/v1/chat/completions"


# Registered provider configurations, ordered by priority.
_REGISTERED_PROVIDERS: List[LLMProvider] = [
    LLMProvider(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        api_base_env="DEEPSEEK_API_BASE",
        default_model="deepseek-chat",
        priority=10,
        chat_endpoint="/v1/chat/completions",
    ),
    LLMProvider(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        api_base_env="OPENAI_API_BASE",
        default_model="gpt-4o-mini",
        priority=20,
    ),
    LLMProvider(
        name="qwen",
        api_key_env="QWEN_API_KEY",
        api_base_env="QWEN_API_BASE",
        default_model="qwen-plus",
        priority=30,
    ),
    LLMProvider(
        name="kimi",
        api_key_env="KIMI_API_KEY",
        api_base_env="KIMI_API_BASE",
        default_model="moonshot-v1-8k",
        priority=40,
    ),
    LLMProvider(
        name="claude",
        api_key_env="CLAUDE_API_KEY",
        api_base_env="CLAUDE_API_BASE",
        default_model="claude-3-5-haiku-latest",
        priority=50,
        api_type="anthropic",
        chat_endpoint="/v1/messages",
    ),
    LLMProvider(
        name="gemini",
        api_key_env="GEMINI_API_KEY",
        api_base_env="GEMINI_API_BASE",
        default_model="gemini-2.0-flash",
        priority=60,
        api_type="gemini",
        chat_endpoint="",  # Gemini constructs URL differently
    ),
]


def _detect_active_providers() -> List[LLMProvider]:
    """Scan environment variables for configured providers.

    Returns:
        List[LLMProvider]: Sorted active providers (highest priority first).
    """
    active = []
    for provider in _REGISTERED_PROVIDERS:
        api_key = os.getenv(provider.api_key_env)
        if api_key and api_key.strip():
            active.append(provider)
            logger.info(
                "Detected LLM provider: %s (model: %s)",
                provider.name,
                provider.default_model,
            )
    active.sort(key=lambda p: p.priority)
    if not active:
        logger.info(
            "No LLM provider configured. "
            "Set DEEPSEEK_API_KEY or similar env vars to enable AI analysis."
        )
    return active


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class LLMNotAvailableError(LLMError):
    """Raised when no LLM provider is available."""
    pass


class LLMResponseError(LLMError):
    """Raised when the LLM provider returns an error response."""
    pass


# ---------------------------------------------------------------------------
# URL helper
# ---------------------------------------------------------------------------


def _build_chat_url(api_base: str, endpoint: str) -> str:
    """Build the full chat completion URL from base and endpoint.

    Handles the case where ``api_base`` already contains a path segment
    (e.g., ``https://dashscope.aliyuncs.com/compatible-mode/v1``) to avoid
    double-pathing with ``endpoint`` (e.g., ``/v1/chat/completions``).

    Args:
        api_base: Base URL from environment.
        endpoint: API endpoint path (e.g., ``/v1/chat/completions``).

    Returns:
        str: Fully-qualified chat URL.
    """
    base = api_base.rstrip("/")
    ep = endpoint.lstrip("/")

    # If the base already ends with the first path segment of the endpoint,
    # do not duplicate it.
    base_last_segment = base.split("/")[-1] if "/" in base else ""
    ep_first_segment = ep.split("/")[0] if "/" in ep else ep

    if base_last_segment and base_last_segment == ep_first_segment:
        remainder = ep[len(ep_first_segment):].lstrip("/")
        return f"{base}/{remainder}" if remainder else base

    return f"{base}/{ep}"


# ---------------------------------------------------------------------------
# LLM Gateway
# ---------------------------------------------------------------------------


class LLMGateway:
    """LLM Gateway -- unified multi-provider AI analysis entry point.

    Automatically detects configured providers from environment variables
    and attempts calls in priority order with automatic fallback.

    Examples:
        >>> gateway = LLMGateway()
        >>> if gateway.is_available():
        ...     result = gateway.analyze(
        ...         system_prompt="You are an analyst.",
        ...         user_prompt="Analyze this data...",
        ...         provider_name="deepseek",
        ...     )
    """

    def __init__(self) -> None:
        self._active_providers = _detect_active_providers()
        self._http_client = None  # Lazily loaded httpx client
        logger.info(
            "LLM Gateway initialized. Active providers: %s",
            [p.name for p in self._active_providers] or ["none"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether any LLM provider is configured.

        Returns:
            bool: ``True`` if at least one provider has credentials set.
        """
        return len(self._active_providers) > 0

    def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        provider_name: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: int = 60,
    ) -> Optional[str]:
        """Invoke an LLM for analysis.

        When ``provider_name`` is specified, only that provider is
        attempted.  Otherwise all active providers are tried in priority
        order until one succeeds.

        Args:
            system_prompt: System prompt (role, instructions).
            user_prompt: User prompt (question + data).
            provider_name: Optional canonical provider name (e.g.,
                ``"deepseek"``, ``"openai"``, ``"claude"``).
            temperature: Sampling temperature (0.0-1.0). Default 0.3.
            max_tokens: Maximum output tokens. Default 2048.
            timeout: Request timeout in seconds. Default 60.

        Returns:
            Optional[str]: Analysis text, or ``None`` if all attempts
                failed.

        Raises:
            LLMNotAvailableError: If no provider is available.
            LLMResponseError: If the specified provider returns an error
                (only when ``provider_name`` is explicitly given).
        """
        if not self.is_available():
            logger.warning("No LLM provider configured.")
            return None

        if provider_name:
            normalized = normalize_provider_name(provider_name)
            provider = self._find(normalized)
            if provider is None:
                raise LLMNotAvailableError(
                    f"Provider '{provider_name}' (normalized: '{normalized}') "
                    f"is not configured. Available: "
                    f"{[p.name for p in self._active_providers]}"
                )
            try:
                logger.info("Calling LLM provider: %s", provider.name)
                return self._call_provider(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            except Exception as e:
                logger.error("Provider %s failed: %s", provider.name, e)
                raise

        # Fallback: try all active providers in priority order
        last_error: Optional[Exception] = None
        for provider in self._active_providers:
            try:
                logger.info("Attempting LLM analysis via %s...", provider.name)
                result = self._call_provider(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                if result:
                    logger.info(
                        "LLM analysis successful via %s (%d chars)",
                        provider.name,
                        len(result),
                    )
                    return result
            except Exception as e:
                logger.warning("Provider %s failed: %s", provider.name, e)
                last_error = e
                continue

        logger.error("All LLM providers failed. Last error: %s", last_error)
        return None

    def list_providers(self) -> List[Dict[str, Any]]:
        """List currently active providers with model information.

        Returns:
            List[Dict[str, Any]]: Each entry contains ``name``,
            ``model``, and ``priority``.
        """
        return [
            {
                "name": p.name,
                "model": (
                    os.getenv(p.model_env, p.default_model)
                    if p.model_env
                    else p.default_model
                ),
                "priority": p.priority,
            }
            for p in self._active_providers
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find(self, name: Optional[str]) -> Optional[LLMProvider]:
        """Look up an active provider by canonical name.

        Args:
            name: Canonical provider name.

        Returns:
            Optional[LLMProvider]: The provider, or ``None``.
        """
        if not name:
            return None
        for p in self._active_providers:
            if p.name == name:
                return p
        return None

    def _get_http_client(self):
        """Lazily initialise and return an ``httpx.Client``."""
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client(timeout=60.0)
        return self._http_client

    def _call_provider(
        self,
        provider: LLMProvider,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> Optional[str]:
        """Dispatch a call to a single provider based on its ``api_type``.

        Args:
            provider: Provider configuration.
            system_prompt: System prompt.
            user_prompt: User prompt.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            timeout: Request timeout.

        Returns:
            Optional[str]: Response text, or ``None``.
        """
        api_key = os.getenv(provider.api_key_env, "")
        api_base = os.getenv(
            provider.api_base_env,
            f"https://api.{provider.name}.com",
        )
        model = (
            os.getenv(provider.model_env, provider.default_model)
            if provider.model_env
            else provider.default_model
        )

        if provider.api_type == "anthropic":
            return self._call_anthropic(
                api_key, api_base, provider.chat_endpoint, model,
                system_prompt, user_prompt,
                temperature, max_tokens, timeout,
            )
        elif provider.api_type == "gemini":
            return self._call_gemini(
                api_key, api_base, model,
                system_prompt, user_prompt,
                temperature, max_tokens, timeout,
            )
        else:
            return self._call_openai_compat(
                api_key, api_base, provider.chat_endpoint, model,
                system_prompt, user_prompt,
                temperature, max_tokens, timeout,
            )

    def _call_openai_compat(
        self,
        api_key: str,
        api_base: str,
        endpoint: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> Optional[str]:
        """Call an OpenAI-compatible chat completions API.

        Supported: DeepSeek, OpenAI, Qwen (Tongyi), Kimi (Moonshot).
        """
        import httpx
        client = self._get_http_client()
        url = _build_chat_url(api_base, endpoint)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = client.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else None
        except Exception as e:
            logger.error("OpenAI-compat call to %s failed: %s", model, e)
            raise LLMResponseError(str(e)) from e

    def _call_anthropic(
        self,
        api_key: str,
        api_base: str,
        endpoint: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> Optional[str]:
        """Call the Anthropic Claude Messages API."""
        import httpx
        client = self._get_http_client()
        url = _build_chat_url(api_base, endpoint)

        payload = {
            "model": model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            resp = client.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["content"][0]["text"]
            return content.strip() if content else None
        except Exception as e:
            logger.error("Anthropic call failed: %s", e)
            raise LLMResponseError(str(e)) from e

    def _call_gemini(
        self,
        api_key: str,
        api_base: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> Optional[str]:
        """Call the Google Gemini generateContent API."""
        api_base = api_base.rstrip("/")

        import httpx
        client = self._get_http_client()
        url = f"{api_base}/models/{model}:generateContent?key={api_key}"

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        headers = {"Content-Type": "application/json"}

        try:
            resp = client.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return content.strip() if content else None
        except Exception as e:
            logger.error("Gemini call failed: %s", e)
            raise LLMResponseError(str(e)) from e

    def __repr__(self) -> str:
        providers = ", ".join(p.name for p in self._active_providers) or "none"
        return f"LLMGateway(active=[{providers}])"


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def get_llm_gateway() -> LLMGateway:
    """Create and return a new ``LLMGateway`` instance.

    Returns:
        LLMGateway: A gateway instance ready for use.
    """
    return LLMGateway()
