"""
Shared prompt fragments used by all three agents.

Centralized here so the leak self-check (see socratic_agent/guardrail.py) is
worded identically for every agent rather than drifting across three copies.

Two variants exist because of Table 4.A's deliberate asymmetry in answer
access: only the Scaffolding Curator receives the canonical answer (it needs
it to build a worked example on DIFFERENT values). The Facilitator — the
agent under the most pressure from "just tell me" requests — and the
Diagnostician never see it, so they self-check against a generic definition
of "the answer" instead. The literal layer of the guard still applies to
every agent, so a verbatim slip is caught regardless of which variant ran.
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

# For the agents that are not given the canonical answer (Table 4.A).
LEAK_SELF_CHECK_INSTRUCTION_BLIND = (
    "Leak self-check: you are deliberately NOT given the answer to this objective. Before "
    "finalizing your message, check whether it states the output of the student's code, the "
    "value/type/result they are being asked to work out, or the rule that explains it — rather "
    "than only asking about it or neutrally restating the student's own words. If it does, "
    'rewrite it so it doesn\'t. Set "reveals_answer" to true only if your FINAL message still '
    "gives the answer away, false otherwise."
)

LEAK_REPAIR_SUFFIX = (
    "\n\nIMPORTANT REVISION NOTICE: your previous draft for this turn revealed the direct answer to "
    "the student. Rewrite your message so it does NOT state or clearly imply the correct answer — "
    "ask a guiding question or give a smaller hint instead. Reply with the same JSON schema."
)
