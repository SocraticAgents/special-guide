"""
Thin, provider-agnostic LLM wrapper.

Per Section 3.5 of the proposal, all three agents are realized as distinct
role-specific system prompts called through a single external LLM API rather
than as separately trained models. This module is the one place that knows
which provider that is, so swapping providers never touches agent code.

Set LLM_PROVIDER=anthropic|openai|openrouter|gemini in the environment (see .env.example).

Every call's token usage and latency is recorded (see `drain_usage`) so the
per-session cost estimate promised in Section 3.5 and the responsiveness
criterion of Table 4.30 can be measured from the pilot itself. Rate-limit
responses (common on free OpenRouter models) are retried with a short
backoff instead of surfacing as an error on the first 429.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class LLMError(RuntimeError):
    """Raised when the provider call fails or returns unparsable output."""


# Streamlit runs each browser session in its own thread, so usage is buffered per thread.
_usage_local = threading.local()


def _record_usage(provider: str, model: str, prompt_tokens: int | None, completion_tokens: int | None,
                  latency_ms: int, ok: bool) -> None:
    if not hasattr(_usage_local, "calls"):
        _usage_local.calls = []
    _usage_local.calls.append(dict(
        provider=provider, model=model, prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens, latency_ms=latency_ms, ok=ok,
    ))


def drain_usage() -> list[dict]:
    """Returns and clears the calls recorded on this thread since the last drain."""
    calls = getattr(_usage_local, "calls", [])
    _usage_local.calls = []
    return calls


def _is_rate_limit(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 429 or "429" in str(exc) or "rate limit" in str(exc).lower()


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


def _get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "anthropic").strip().lower()


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from model output.

    Models are instructed to return raw JSON, but sometimes wrap it in
    ```json fences or add stray prose, so we strip fences first and then
    fall back to grabbing the outermost {...} block.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise LLMError(f"Could not parse JSON from model output:\n{text!r}")


def _openai_style(response, model: str) -> tuple[str, str, int | None, int | None]:
    usage = getattr(response, "usage", None)
    prompt_t = getattr(usage, "prompt_tokens", None)
    completion_t = getattr(usage, "completion_tokens", None)
    total_t = getattr(usage, "total_tokens", None)
    if prompt_t is not None and total_t is not None:
        # Hidden "thinking" tokens are billed as output: output = total - prompt.
        completion_t = max(total_t - prompt_t, completion_t or 0)
    return (
        response.choices[0].message.content or "",
        getattr(response, "model", None) or model,
        prompt_t,
        completion_t,
    )


def _call_anthropic(system_prompt: str, messages: list[Message], temperature: float) -> str:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY is not set (see .env.example).")

    client = anthropic.Anthropic(api_key=api_key)
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": m.role, "content": m.content} for m in messages],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return text, model, response.usage.input_tokens, response.usage.output_tokens


def _call_openai(system_prompt: str, messages: list[Message], temperature: float) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OPENAI_API_KEY is not set (see .env.example).")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in messages],
    )
    return _openai_style(response, model)


def _call_openrouter(system_prompt: str, messages: list[Message], temperature: float) -> str:
    # OpenRouter exposes an OpenAI-compatible Chat Completions API, so the
    # OpenAI SDK works unmodified with a different base_url + key.
    from openai import OpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY is not set (see .env.example).")

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

    response = client.chat.completions.create(
        model=model,
        # Without a cap OpenRouter reserves credit for the model's full output limit.
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        temperature=temperature,
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in messages],
        extra_headers={
            # Optional but recommended by OpenRouter for attribution/rankings.
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://localhost"),
            "X-Title": os.getenv("OPENROUTER_SITE_NAME", "Socratic-Agent"),
        },
        # Route only to providers that do not store/train on prompts (student dialogue, Sec 3.6).
        # Free ":free" model variants are often served only by providers that do log prompts, so
        # set OPENROUTER_DATA_COLLECTION=allow to use them — and say so in the thesis.
        extra_body={"provider": {"data_collection": os.getenv("OPENROUTER_DATA_COLLECTION", "deny")}},
    )
    return _openai_style(response, model)


def _call_gemini(system_prompt: str, messages: list[Message], temperature: float) -> str:
    # Google's Gemini API also exposes an OpenAI-compatible Chat Completions endpoint.
    from openai import OpenAI

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not set (see .env.example).")

    client = OpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in messages],
    )
    return _openai_style(response, model)


def call_json_agent(
    system_prompt: str,
    messages: list[Message],
    *,
    retries: int = 1,
) -> dict[str, Any]:
    """Call the configured LLM provider and parse a JSON object from its reply.

    `system_prompt` must instruct the model to reply with ONLY a JSON object
    matching the agent's response schema (see socratic_agent/prompts/*.py).
    On a parse failure, one repair turn is appended asking the model to
    re-emit valid JSON before giving up.
    """
    provider = _get_provider()
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
    caller = {
        "anthropic": _call_anthropic,
        "openai": _call_openai,
        "openrouter": _call_openrouter,
        "gemini": _call_gemini,
    }.get(provider)
    if caller is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}' (expected anthropic|openai|openrouter|gemini).")

    working_messages = list(messages)
    last_error: Exception | None = None

    rate_limit_retries = int(os.getenv("LLM_RATE_LIMIT_RETRIES", "2"))

    for attempt in range(retries + 1):
        for backoff in range(rate_limit_retries + 1):
            started = time.monotonic()
            try:
                reply = caller(system_prompt, working_messages, temperature)
                # evaluation/compare_models.py swaps in a caller that returns plain text.
                raw, model, prompt_tokens, completion_tokens = (
                    (reply, "", None, None) if isinstance(reply, str) else reply
                )
                _record_usage(provider, model, prompt_tokens, completion_tokens,
                              int((time.monotonic() - started) * 1000), ok=True)
                break
            except LLMError:
                raise
            except Exception as exc:
                _record_usage(provider, "", None, None, int((time.monotonic() - started) * 1000), ok=False)
                if _is_rate_limit(exc) and backoff < rate_limit_retries:
                    time.sleep(2 * (backoff + 1))
                    continue
                # Provider SDK errors (auth, no credits, rate limit, network) become LLMError
                # so the UI shows them as an error banner instead of crashing the session.
                raise LLMError(f"{provider} API call failed: {exc}") from exc
        try:
            return _extract_json(raw)
        except LLMError as exc:
            last_error = exc
            working_messages = working_messages + [
                Message(role="assistant", content=raw),
                Message(
                    role="user",
                    content=(
                        "That was not valid JSON. Reply again with ONLY the JSON "
                        "object described in your instructions — no prose, no "
                        "markdown fences."
                    ),
                ),
            ]

    raise last_error or LLMError("Unknown LLM call failure.")
