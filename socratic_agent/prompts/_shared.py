"""
Shared prompt fragments used by all three agents.

Centralized here so the leak self-check (see socratic_agent/guardrail.py) is
worded identically for every agent rather than drifting across three copies.
"""
from __future__ import annotations

LEAK_SELF_CHECK_INSTRUCTION = (
    'Leak self-check: the correct answer to the current objective is, for your eyes only — '
    'NEVER state this to the student: "{canonical_answer}". Before finalizing your message, check '
    "whether it directly states or clearly gives away this answer, rather than only asking about "
    "it or neutrally acknowledging the student's own guess. If it does, rewrite your message so it "
    'doesn\'t, before replying. Set "reveals_answer" to true only if your FINAL message still '
    "reveals the answer, false otherwise."
)

LEAK_REPAIR_SUFFIX = (
    "\n\nIMPORTANT REVISION NOTICE: your previous draft for this turn revealed the direct answer to "
    "the student. Rewrite your message so it does NOT state or clearly imply the correct answer — "
    "ask a guiding question or give a smaller hint instead. Reply with the same JSON schema."
)
