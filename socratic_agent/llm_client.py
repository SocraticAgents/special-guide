"""
Thin, provider-agnostic LLM wrapper.

Per Section 3.5 of the proposal, all three agents are realized as distinct
role-specific system prompts called through a single external LLM API rather
than as separately trained models. This module is the one place that knows
which provider that is, so swapping providers never touches agent code.

Set LLM_PROVIDER=anthropic|openai|openrouter in the environment (see .env.example).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class LLMError(RuntimeError):
    """Raised when the provider call fails or returns unparsable output."""


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
    return "".join(block.text for block in response.content if block.type == "text")


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
    return response.choices[0].message.content or ""


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
        temperature=temperature,
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in messages],
        extra_headers={
            # Optional but recommended by OpenRouter for attribution/rankings.
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://localhost"),
            "X-Title": os.getenv("OPENROUTER_SITE_NAME", "Socratic-Agent"),
        },
    )
    return response.choices[0].message.content or ""


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
    }.get(provider)
    if caller is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}' (expected anthropic|openai|openrouter).")

    working_messages = list(messages)
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        raw = caller(system_prompt, working_messages, temperature)
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
