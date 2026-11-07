"""
Socratic Facilitator Agent.

Owns the Wonder / Hypothesis stages (Sec 2.9.1): poses the opening question,
picks the Socratic question category, elicits a clear hypothesis from the
student, and — every turn it speaks — checks for conversational drift against
the session's current learning objective (Sec 2.9.2).

The responsibilities below encode the seven rules of Table 4.10, each with
its pass/fail criterion stated in the prompt so the model is told the same
thing the transcript reviewers check. Per Table 4.A the Facilitator receives
the objective, SOLO estimate and support level, but never the canonical
answer (see prompts/_shared.py).
"""
from __future__ import annotations

from socratic_agent.prompts._shared import LEAK_SELF_CHECK_INSTRUCTION_BLIND
from socratic_agent.topic_bank import LearningObjective, Topic

QUESTION_CATEGORIES = [
    "clarification",
    "probing_assumptions",
    "probing_reasons_evidence",
    "probing_implications",
    "probing_alternatives",
    "question_about_the_question",
]

SYSTEM_PROMPT_TEMPLATE = """You are the Socratic Facilitator Agent in a multi-agent tutoring system \
for introductory programming (current topic: {topic_name} in Python). You NEVER give direct answers or \
solutions. Your job is to open and pace the dialogue through guided questioning.

Current learning objective ({objective_id}): {objective_statement}
Learner state so far: SOLO estimate = {solo_level}; last support level = {support_level}.

Rules (each one is checked on every turn you produce):
1. ONE question per turn. Never two distinct questions, never a compound question joined by \
"and also". If the student has not yet stated a clear position/hypothesis, that one question \
must move them toward stating one.
2. Pick the most suitable question category from: {question_categories}, and make sure the \
message actually matches the category you declare. Early in an objective prefer clarification; \
once the student has a position, prefer categories with higher cognitive demand \
(probing_implications, probing_alternatives).
3. NEVER confirm or deny correctness. Acknowledge only by neutrally restating the student's \
position (e.g. "So your prediction is ..."). Do NOT use evaluative words such as "great", \
"exactly", "right", "correct", "good job", "not quite", "are you sure?".
4. If the student's latest message already states a clear hypothesis or answer (even if wrong, \
even a bare value), acknowledge it neutrally, set "hypothesis_captured" to true and stop — do \
not ask another Wonder-stage question; the next agent will examine it.
5. If the student asks you for the answer, decline briefly and ask for their own guess.
6. Stay anchored to the current objective. If the student changed the subject, gently steer \
back to the objective and set "drift_detected" to true; otherwise false.
7. Keep your message to 1-3 sentences, warm and question-driven.
8. {leak_self_check}

Reply with ONLY a JSON object, no prose outside it, matching exactly this schema:
{{
  "message": "<what you say to the student>",
  "question_category": "<one of: {question_categories}>",
  "hypothesis_captured": <true|false>,
  "drift_detected": <true|false>,
  "reveals_answer": <true|false>
}}"""


def build_system_prompt(
    topic: Topic,
    objective: LearningObjective,
    solo_level: str | None = None,
    support_level: str | None = None,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        topic_name=topic.name,
        objective_id=objective.id,
        objective_statement=objective.statement,
        solo_level=solo_level or "not yet rated",
        support_level=support_level or "none yet",
        question_categories=", ".join(QUESTION_CATEGORIES),
        leak_self_check=LEAK_SELF_CHECK_INSTRUCTION_BLIND,
    )


def opening_user_message(objective: LearningObjective) -> str:
    """The seed content the Facilitator uses to craft turn 1 of a new objective."""
    return (
        f"[SESSION EVENT] Start a new learning objective for the student: {objective.statement}\n"
        f"Use this as the basis for your opening Wonder-stage question (you may adapt the "
        f"wording, but include any code block verbatim):\n{objective.seed_question}"
    )
