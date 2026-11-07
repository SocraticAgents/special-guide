"""
Answer-leakage guard.

The proposal's own literature review flags answer leakage — student pressure
or adversarial queries causing a tutor to prematurely reveal the solution —
as an unresolved robustness gap in existing Socratic AI tutors (Sec 2.7.2,
2.8.2; cf. Table 2.5.2.1's "Evaluating Answer Leakage Robustness" study).
Before this module existed, the only defense in this codebase was the
system-prompt instruction "never state the answer" — i.e. nothing actually
checked the agent's output. This module is that check.

Two layers, both applied to every agent message before it reaches the
student (see orchestrator.py's `_call_agent_guarded`):

Layer 1 (semantic, primary): each agent's own JSON schema includes a
"reveals_answer" self-check field (see prompts/*.py), judged against the
objective's `canonical_answer`. Cheap — it's part of the same API call — and
it catches a paraphrased leak a literal string match would miss.

Layer 2 (literal, safety net): a deterministic check against the
objective's `protected_literals`, independent of what the model
self-reports, so a model that is simply wrong about its own output is still
caught. Literals are matched as whole tokens, not plain substrings: "0,1,2"
must not fire inside a restatement of the wrong answer "0,1,2,3", and
"prints 5" must not fire inside "prints 50" (verification test T07b).

Either layer tripping counts as a leak; the caller then retries once with a
repair instruction and, failing that, substitutes a hardcoded safe message
rather than ever displaying the leak.
"""
from __future__ import annotations

import re

from socratic_agent.topic_bank import LearningObjective


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _literal_pattern(literal: str) -> re.Pattern[str]:
    """Whole-token pattern for one normalized literal.

    Word-character edges must not touch another word character, and a literal that
    starts/ends with a digit must not be part of a longer number sequence such as
    "0, 1, 2, 3" or "5.5" — that would be a different (often wrong) answer.
    """
    norm = _normalize(literal)
    pre = r"(?<!\w)" if re.match(r"\w", norm[0]) else ""
    post = r"(?!\w)" if re.match(r"\w", norm[-1]) else ""
    if norm[0].isdigit():
        pre = r"(?<!\d,\s)(?<!\d\.)(?<!\d,)(?<!\d\s)" + pre
    if norm[-1].isdigit():
        post += r"(?!\s?[,.]?\s?\d)"
    return re.compile(pre + re.escape(norm) + post)


def literal_leak_match(message: str, objective: LearningObjective) -> str | None:
    """Returns the matched protected literal if `message` contains one, else None."""
    normalized = _normalize(message)
    for literal in objective.protected_literals:
        if _literal_pattern(literal).search(normalized):
            return literal
    return None


def is_leak(
    message: str,
    objective: LearningObjective,
    self_reported: bool,
    *,
    check_literal: bool = True,
) -> tuple[bool, str | None]:
    """Combines both layers. Returns (leaked, matched_literal_or_None).

    `check_literal=False` skips the deterministic layer — used for the
    Scaffolder's legitimate wrap-up message once understanding_sufficient is
    true, which necessarily restates what the student already concluded
    themselves and would otherwise false-positive against the same literals.
    """
    literal_hit = literal_leak_match(message, objective) if check_literal else None
    return (bool(self_reported) or literal_hit is not None), literal_hit
