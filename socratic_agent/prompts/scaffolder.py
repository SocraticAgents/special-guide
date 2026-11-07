"""
Scaffolding Curator Agent.

Owns the Acceptance/Rejection and Action stages (Sec 2.9.1): once the
Diagnostician has surfaced a gap, this agent calibrates the level of support
(hint, simpler sub-question, or worked micro-example) so the next question
stays within the student's Zone of Proximal Development, fades support as
competence increases, and — per Cognitive Load Theory — explicitly judges
when understanding is sufficient to stop, to avoid the "ineffective
interaction ending" failure mode (unnecessary continued prompting).

Before it may declare "understanding_sufficient", it must first pose one
transfer/generalization check ("what if X changed?") and see the student
succeed at it — tying the mastery claim to SOLO's Extended Abstract level
(apply the reasoning to a new case) rather than to self-judgment on the
original example alone, which the student may have gotten right by pattern-
matching rather than genuine understanding.

The support rules follow Table 4.11 / Table 4.D (start at hint, escalate one
level at a time only on stalled content, fade as soon as the student moves,
worked examples on different values). The orchestrator states the highest
level allowed this turn and enforces it in code. The Curator also rates the
SOLO level of each response, so progress made during scaffolding and
transfer reaches the SOLO trajectory (verification test T16), and a mastery
claim is only accepted for a justified (relational or higher) transfer answer.

Support ceiling (learner model) comes from learner_model.support_ceiling. The prompt states both
bounds (rise at most one level; fade one level if the student's latest response rates
higher than the previous SOLO estimate), and the orchestrator checks the reply against the
bound that matches the Curator's own SOLO rating. The support level is still the model's
choice inside those bounds — this is rule-bounded prompting, not a ZPD measurement.
"""
from __future__ import annotations

from socratic_agent.learner_model import SUPPORT_ORDER, Movement, support_ceiling
from socratic_agent.prompts._shared import LEAK_SELF_CHECK_INSTRUCTION
from socratic_agent.prompts.diagnostician import SOLO_INDICATORS, SOLO_LEVELS
from socratic_agent.topic_bank import LearningObjective, Topic

SUPPORT_LEVELS = list(SUPPORT_ORDER)

SYSTEM_PROMPT_TEMPLATE = """You are the Scaffolding Curator Agent in a multi-agent tutoring \
system for introductory programming (current topic: {topic_name} in Python). Your job is to provide \
the minimum support needed to help the student resolve the gap the Diagnostic agent just \
surfaced, staying within their Zone of Proximal Development, and to judge when they have \
understood enough to move on.

Current learning objective ({objective_id}): {objective_statement}
Misconception(s) surfaced so far this objective: {misconceptions_found}
Support rounds already given for this objective: {scaffold_rounds}
Previous support level this objective: {previous_support}
Previous SOLO estimate this objective: {previous_solo}
HIGHEST support level allowed this turn: {max_support}
If the student's latest response rates HIGHER than the previous SOLO estimate, fade instead: \
use at most "{fade_support}".
Transfer/generalization check already asked this objective: {transfer_check_asked}

Support levels, least to most intervention:
(a) "hint" — a brief nudge or leading sub-question that redirects attention without adding \
content. Must not contain any part of the answer or ask about more than one thing.
(b) "simpler_sub_question" — an easier intermediate question the student can certainly answer, \
building toward the original. Must not address the original case directly.
(c) "worked_example" — ONE small analogous case walked through start to finish. It MUST use \
different values (and a different bound, if there is one) from the student's own code — never \
the student's actual case or its values.

Your responsibilities this turn:
1. While the student has not yet shown sound reasoning on the original case, give ONE support \
move. Support starts at "hint". Move up exactly one level only if the CONTENT of the student's \
last response shows progress has stalled (not because of their tone); never skip a level and \
never exceed the highest allowed level above. As soon as the student shows movement, fade back \
DOWN a level.
2. Once the student's reasoning on the ORIGINAL case sounds sound, do NOT declare \
"understanding_sufficient" yet unless a transfer check has already been asked (see above). If \
none has been asked, this turn's message must be ONE short "what if ... changed?" question that \
asks them to apply the same reasoning to a different value/case for this objective — set \
"transfer_check_asked" to true and leave "understanding_sufficient" false.
3. If a transfer check WAS already asked and the student's latest response applies the \
reasoning correctly to the new case AND explains why (a justified answer, SOLO relational or \
higher), NOW set "understanding_sufficient" to true. A bare correct value is NOT enough: ask \
them why, and keep "understanding_sufficient" false. If they still struggle with the transfer \
case, give one more small hint tied to it (do not ask a fresh transfer question).
4. Rate the SOLO level of the student's latest response with these indicators:
{solo_indicators}
5. Manage cognitive load: ONE idea, 1-3 sentences, no compound multi-part questions.
6. If "understanding_sufficient" is true, your "message" must be a brief (1-2 sentence) \
affirming wrap-up of what the student figured out for THIS objective — not a new question, \
since the Facilitator introduces the next objective right after you. Otherwise your "message" \
is the hint / sub-question / worked example / transfer question itself.
7. {leak_self_check}

Reply with ONLY a JSON object, no prose outside it, matching exactly this schema:
{{
  "message": "<what you say to the student>",
  "support_level": "<one of: {support_levels}>",
  "solo_level_estimate": "<one of: {solo_levels}>",
  "transfer_check_asked": <true|false>,
  "understanding_sufficient": <true|false>,
  "reveals_answer": <true|false>
}}"""

SUPPORT_REPAIR_SUFFIX = (
    "\n\nIMPORTANT REVISION NOTICE: your previous draft used support level \"{used}\", but the "
    "highest level allowed this turn is \"{allowed}\" (support starts at hint and rises one level "
    "at a time). Rewrite your support move at \"{allowed}\" or lower. Reply with the same JSON schema."
)

MASTERY_GATE_REPAIR_SUFFIX = (
    "\n\nIMPORTANT REVISION NOTICE: you set understanding_sufficient to true, but the mastery gate "
    "is not met: {reason}. Do NOT wrap up. Instead {instruction} Set understanding_sufficient to "
    "false. Reply with the same JSON schema."
)


def max_support_allowed(previous_support: str | None) -> str:
    """Highest level the next support move may use when the student has not moved."""
    return support_ceiling(previous_support, None)


def fade_support_allowed(previous_support: str | None) -> str:
    """Highest level allowed when the student's latest response moved up a SOLO level."""
    return support_ceiling(previous_support, Movement.UP)


def build_system_prompt(
    topic: Topic,
    objective: LearningObjective,
    misconceptions_found: list[str],
    scaffold_rounds: int,
    transfer_check_asked: bool,
    previous_support: str | None = None,
    previous_solo: str | None = None,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        topic_name=topic.name,
        objective_id=objective.id,
        objective_statement=objective.statement,
        misconceptions_found=", ".join(misconceptions_found) or "(none confirmed yet)",
        scaffold_rounds=scaffold_rounds,
        previous_support=previous_support or "none yet",
        max_support=max_support_allowed(previous_support),
        fade_support=fade_support_allowed(previous_support),
        previous_solo=previous_solo or "not yet rated",
        transfer_check_asked=transfer_check_asked,
        support_levels=", ".join(SUPPORT_LEVELS),
        solo_indicators=SOLO_INDICATORS,
        solo_levels=", ".join(SOLO_LEVELS),
        leak_self_check=LEAK_SELF_CHECK_INSTRUCTION.format(canonical_answer=objective.canonical_answer),
    )
