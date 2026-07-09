from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Mapping


DEFAULT_JUDGE_PROVIDER = "codex"
DEEPSEEK_PROVIDER = "deepseek"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEEPSEEK_MODEL_ENV = "DEEPSEEK_MODEL"
DEEPSEEK_MAX_TOKENS_ENV = "DEEPSEEK_MAX_TOKENS"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_THINKING = "disabled"


class LlmProviderError(RuntimeError):
    pass


class LlmProviderResponseError(LlmProviderError):
    def __init__(self, message: str, *, diagnostics: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = dict(diagnostics)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def text_excerpt(value: str, *, limit: int = 1200) -> dict[str, Any]:
    text = str(value or "")
    return {
        "length": len(text),
        "head": text[:limit],
        "tail": text[-limit:] if len(text) > limit else text,
    }


def normalize_judge_provider(value: str | None) -> str:
    provider = (value or os.environ.get("EMPEROR_EVAL_JUDGE_PROVIDER") or DEFAULT_JUDGE_PROVIDER).strip().lower()
    if provider not in {DEFAULT_JUDGE_PROVIDER, DEEPSEEK_PROVIDER}:
        raise LlmProviderError(f"unsupported judge provider: {provider}")
    return provider


def provider_usage(raw_usage: Mapping[str, Any]) -> dict[str, Any]:
    usage = dict(raw_usage)
    if "input_tokens" not in usage and "prompt_tokens" in usage:
        usage["input_tokens"] = usage.get("prompt_tokens")
    if "output_tokens" not in usage and "completion_tokens" in usage:
        usage["output_tokens"] = usage.get("completion_tokens")
    if "total_tokens" not in usage and usage.get("input_tokens") is not None and usage.get("output_tokens") is not None:
        usage["total_tokens"] = int(usage["input_tokens"] or 0) + int(usage["output_tokens"] or 0)
    return usage


def parse_json_model_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise LlmProviderError("model response did not contain JSON object") from exc
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise LlmProviderError("model response JSON must be an object")
    return payload


def run_deepseek_chat(
    *,
    prompt: str,
    model: str | None,
    api_key_env: str,
    base_url: str | None,
    timeout_seconds: int,
    thinking: str | None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise LlmProviderError(f"missing DeepSeek API key env var: {api_key_env}")
    started = time.perf_counter()
    resolved_base_url = (base_url or os.environ.get(DEEPSEEK_BASE_URL_ENV) or DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    resolved_model = model or os.environ.get(DEEPSEEK_MODEL_ENV) or DEFAULT_DEEPSEEK_MODEL
    thinking_mode = (thinking or os.environ.get("DEEPSEEK_THINKING") or DEFAULT_DEEPSEEK_THINKING).strip().lower()
    if thinking_mode not in {"enabled", "disabled"}:
        raise LlmProviderError(f"unsupported DeepSeek thinking mode: {thinking_mode}")
    resolved_max_tokens = max_tokens
    if resolved_max_tokens is None and os.environ.get(DEEPSEEK_MAX_TOKENS_ENV):
        resolved_max_tokens = int(os.environ[DEEPSEEK_MAX_TOKENS_ENV])
    body = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": "You are a strict JSON extraction engine. Return only one valid JSON object."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": thinking_mode},
    }
    if resolved_max_tokens is not None:
        if resolved_max_tokens <= 0:
            raise LlmProviderError(f"DeepSeek max_tokens must be positive: {resolved_max_tokens}")
        body["max_tokens"] = resolved_max_tokens
    request = urllib.request.Request(
        f"{resolved_base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - live API guard
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise LlmProviderError(f"DeepSeek API request failed HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - live API guard
        raise LlmProviderError(f"DeepSeek API request failed: {exc}") from exc
    message = ((response_payload.get("choices") or [{}])[0].get("message") or {})
    content = str(message.get("content") or "")
    if not content.strip():
        raise LlmProviderError("DeepSeek API response had empty message content")
    usage = provider_usage(response_payload.get("usage") or {})
    usage["provider"] = DEEPSEEK_PROVIDER
    usage["model"] = resolved_model
    usage["thinking"] = thinking_mode
    if resolved_max_tokens is not None:
        usage["max_tokens"] = resolved_max_tokens
    try:
        payload = parse_json_model_content(content)
    except LlmProviderError as exc:
        choice = (response_payload.get("choices") or [{}])[0]
        diagnostics = {
            "provider": DEEPSEEK_PROVIDER,
            "model": resolved_model,
            "thinking": thinking_mode,
            "max_tokens": resolved_max_tokens,
            "finish_reason": choice.get("finish_reason"),
            "usage": usage,
            "content_excerpt": text_excerpt(content),
        }
        raise LlmProviderResponseError(str(exc), diagnostics=diagnostics) from exc
    return {
        "payload": payload,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "usage": usage,
    }
