"""
Stage-driven orchestrator: on each student turn, exactly one agent is
"active" according to `state.stage` (see socratic_agent/state.py), mirroring
the stage-to-agent mapping in Section 2.9.1 of the proposal. Stage
transitions are decided by the structured fields each agent returns
(hypothesis_captured / gap_surfaced / understanding_sufficient), capped by
MAX_ELENCHUS_ROUNDS / MAX_SCAFFOLD_ROUNDS as a lightweight, prompt-level
guard against endless probing (Sec 2.8.2, 2.9.2). Before the Scaffolder may
set understanding_sufficient, it must first pose one transfer/generalization
check and see the student succeed at it (tracked via state.transfer_check_asked)
— ties the mastery claim to SOLO's Extended Abstract level rather than to
self-judgment on the original example alone.

Every agent call is routed through `_call_agent_guarded`, which applies the
answer-leakage guard (socratic_agent/guardrail.py) before a message is ever
returned to the caller — see that module's docstring for why this exists.

Every function returns a list of (message, agent_name) turns rather than a
single turn, because a stage transition can produce more than one agent
message in response to a single student message (e.g. the Scaffolder's
wrap-up for one objective immediately followed by the Facilitator's opener
for the next).

Rules that Table 4.E lists as hard-blocked are enforced here in code rather
than trusted to the model: a mastery claim is refused unless a transfer
question was asked on an EARLIER turn and the transfer answer is rated
relational or higher (gate_rejections), a support move may rise at most one
level above the previous one starting at hint (support_violations), and an
objective closed by the support cap is recorded as not mastered.

Learner model (V1, socratic_agent/learner_model.py): every SOLO rating is stored as an
LLM estimate with its movement; the Curator's support choice is bounded by
`support_ceiling` (rise one level at most when the student has not moved, fade one level
on a turn whose own rating went up — fade_violations); and every objective ends with an
explicit status, MASTERED (gate passed) or CLOSED_AT_CAP (round cap; not mastery). A
capped objective is announced to the student as "parked", never praised as understood.

`state.topic_id` selects which Topic (topic_bank.TOPICS) the session is
about; every function here looks it up fresh from state rather than caching
it, since the caller sets state.topic_id once at session start and it never
changes mid-session.
"""
from __future__ import annotations

import re
from typing import Callable

from socratic_agent.guardrail import is_leak
from socratic_agent.learner_model import (
    SUPPORT_ORDER,
    ElenchusExit,
    Movement,
    ObjectiveStatus,
    classify_movement,
    support_ceiling,
)
from socratic_agent.llm_client import Message, call_json_agent
from socratic_agent.prompts import diagnostician, facilitator, scaffolder
from socratic_agent.prompts._shared import LEAK_REPAIR_SUFFIX
from socratic_agent.prompts.scaffolder import (
    MASTERY_GATE_REPAIR_SUFFIX,
    SUPPORT_REPAIR_SUFFIX,
)
from socratic_agent.state import MAX_ELENCHUS_ROUNDS, MAX_SCAFFOLD_ROUNDS, SessionState, Stage
from socratic_agent.topic_bank import LearningObjective, Topic, get_topic, objective_by_index

AgentTurn = tuple[str, str]  # (message, agent_name)

FALLBACK_MESSAGES = {
    "Facilitator": "Let's slow down for a second — rather than me telling you, what do you think happens here, step by step?",
    "Diagnostician": "Good attempt — before we go further, can you walk me through your reasoning for that, one step at a time?",
    "Scaffolder": "Let's take a smaller step: what's the very first thing about this you're already confident about?",
}

# Used when the Curator keeps claiming mastery after a gate rejection and its retry.
GATE_FALLBACK_TRANSFER = (
    "Before we move on, try the same idea on a slightly different case: if the values in the "
    "code were changed, what would happen, and why?"
)
GATE_FALLBACK_JUSTIFY = "Before we move on — why does that happen? Walk me through your reasoning."

# Shown when an objective closes at the support cap (review note 3): honest to the
# student that the objective is parked, not mastered.
PARKED_MESSAGE = (
    "Let's park this one for now — it's worth coming back to, and your teacher can see "
    "where we got to. On to the next idea."
)
CLOSING_ALL_MASTERED = (
    "That covers everything for this session, nice work reasoning it through yourself "
    "rather than being handed the answer."
)
CLOSING_SOME_PARKED = (
    "That's the end of this session's objectives. You showed you could apply {mastered} of "
    "{total} to a new case; the parked one(s) ({parked}) are worth another go in a new session."
)

# A transfer answer must be justified (Sec 4.7.1 coding rule: a bare correct answer is unistructural).
_JUSTIFIED_SOLO = {"relational", "extended_abstract"}


def _topic(state: SessionState) -> Topic:
    topic = get_topic(state.topic_id)
    assert topic is not None, f"Unknown topic_id: {state.topic_id!r}"
    return topic


def _history_as_messages(state: SessionState) -> list[Message]:
    return [
        Message(role="user" if t.role == "student" else "assistant", content=t.content)
        for t in state.history
    ]


def _call_agent_guarded(
    state: SessionState,
    system_prompt: str,
    messages: list[Message],
    objective: LearningObjective,
    agent_name: str,
    *,
    literal_check_exempt: Callable[[dict], bool] | None = None,
) -> dict:
    """Calls an agent and enforces the answer-leakage guard before returning.

    On a leak (self-reported or literal-match), retries once with a repair
    instruction; if the retry still leaks, substitutes a hardcoded safe
    message rather than ever surfacing the leak. `literal_check_exempt` lets
    the Scaffolder's legitimate wrap-up message (which necessarily restates
    what the student already concluded) skip the literal safety net — see
    guardrail.is_leak's docstring.
    """

    def _leaked(result: dict) -> bool:
        exempt = literal_check_exempt(result) if literal_check_exempt else False
        leaked, _ = is_leak(
            result.get("message", ""),
            objective,
            result.get("reveals_answer", False),
            check_literal=not exempt,
        )
        return leaked

    result = call_json_agent(system_prompt, messages)
    if not _leaked(result):
        return result

    state.leak_attempts += 1
    retry = call_json_agent(system_prompt + LEAK_REPAIR_SUFFIX, messages)
    if not _leaked(retry):
        return retry

    state.leak_hard_blocks += 1
    retry["message"] = FALLBACK_MESSAGES[agent_name]
    return retry


def _facilitator_opens_objective(state: SessionState) -> AgentTurn:
    topic = _topic(state)
    objective = objective_by_index(topic, state.objective_index)
    assert objective is not None
    state.open_record(objective.id, objective.design_id)
    system_prompt = facilitator.build_system_prompt(topic, objective, state.solo_level_estimate)
    seed = facilitator.opening_user_message(objective)
    result = _call_agent_guarded(
        state, system_prompt, [Message(role="user", content=seed)], objective, "Facilitator"
    )
    message = result["message"]
    # The model often paraphrases the seed and drops its code block, leaving the
    # student asked about code they can't see — so always show the snippet.
    snippet = re.search(r"```.*?```", objective.seed_question, re.DOTALL)
    if snippet and snippet.group(0) not in message:
        message = f"{message}\n\n{snippet.group(0)}"
    state.add("assistant", message, agent="Facilitator")
    return message, "Facilitator"


def start_session(state: SessionState) -> list[AgentTurn]:
    """Produce the very first Facilitator message for objective_index 0.

    `state.topic_id` must already be set (see app.py's topic picker).
    """
    turn = _facilitator_opens_objective(state)
    state.started = True
    return [turn]


def _advance_to_next_objective(state: SessionState) -> AgentTurn | None:
    """Moves to the next objective and returns its opening turn, or None if done."""
    state.objective_index += 1
    state.reset_round_counters()
    if state.practice_single or objective_by_index(_topic(state), state.objective_index) is None:
        state.stage = Stage.DONE
        return None
    state.stage = Stage.WONDER
    return _facilitator_opens_objective(state)


def _mastery_gate_problem(result: dict, transfer_asked_before: bool) -> tuple[str, str] | None:
    """Returns (reason, instruction) if a mastery claim must be refused, else None."""
    if not result.get("understanding_sufficient"):
        return None
    if not transfer_asked_before:
        return (
            "no transfer question has been asked yet for this objective",
            "ask ONE short \"what if ... changed?\" transfer question on a different value/case "
            "and set transfer_check_asked to true.",
        )
    if result.get("solo_level_estimate") not in _JUSTIFIED_SOLO:
        return (
            "the transfer answer is not justified (a bare answer is unistructural)",
            "ask the student to explain WHY their transfer answer holds.",
        )
    return None


def _support_rank(level: str | None) -> int | None:
    return SUPPORT_ORDER.index(level) if level in SUPPORT_ORDER else None


def _scaffolder_turn(state: SessionState, topic: Topic, objective: LearningObjective) -> dict:
    """One Scaffolding Curator call with the support-bound and mastery-gate rules enforced.

    The Curator chooses the support level (prompt). The orchestrator bounds it: the ceiling
    depends on the previous support move and on how the Curator's own SOLO rating of the
    latest response moved (learner_model.support_ceiling). This is a rule check on LLM
    outputs, not a measurement of the student's ZPD.
    """
    transfer_asked_before = state.transfer_check_asked
    previous_support = state.scaffold_level_last
    previous_solo = state.previous_solo_this_objective()
    system_prompt = scaffolder.build_system_prompt(
        topic, objective, state.misconceptions_found, state.scaffold_rounds,
        transfer_asked_before, previous_support, previous_solo,
    )
    messages = _history_as_messages(state)

    def _call(prompt: str) -> dict:
        # The wrap-up may restate the student's conclusion, so it skips the literal
        # layer — but only when the gate would actually accept it.
        return _call_agent_guarded(
            state, prompt, messages, objective, "Scaffolder",
            literal_check_exempt=lambda r: _mastery_gate_problem(r, transfer_asked_before) is None
            and bool(r.get("understanding_sufficient")),
        )

    def _bound(r: dict) -> tuple[str, Movement]:
        movement = classify_movement(previous_solo, r.get("solo_level_estimate"))
        return support_ceiling(previous_support, movement), movement

    def _exceeds(r: dict) -> bool:
        is_support_move = not r.get("understanding_sufficient") and not r.get("transfer_check_asked")
        used = _support_rank(r.get("support_level"))
        return is_support_move and used is not None and used > _support_rank(_bound(r)[0])

    result = _call(system_prompt)

    problem = _mastery_gate_problem(result, transfer_asked_before)
    if problem:
        state.gate_rejections += 1
        reason, instruction = problem
        result = _call(system_prompt + MASTERY_GATE_REPAIR_SUFFIX.format(reason=reason, instruction=instruction))
        if _mastery_gate_problem(result, transfer_asked_before):
            state.gate_rejections += 1
            result = dict(result, understanding_sufficient=False)
            if not transfer_asked_before:
                result.update(message=GATE_FALLBACK_TRANSFER, transfer_check_asked=True)
            else:
                result.update(message=GATE_FALLBACK_JUSTIFY)

    if _exceeds(result):
        allowed, _ = _bound(result)
        retry = _call(system_prompt + SUPPORT_REPAIR_SUFFIX.format(used=result["support_level"], allowed=allowed))
        if _mastery_gate_problem(retry, transfer_asked_before) is None:
            result = retry
        if _exceeds(result):
            _, movement = _bound(result)
            if movement in (Movement.UP, Movement.JUMP_UP):
                state.fade_violations += 1
            else:
                state.support_violations += 1
    state.support_ceiling_last = _bound(result)[0]
    return result


def _close_objective(state: SessionState, objective: LearningObjective, mastered: bool) -> list[AgentTurn]:
    """Records the objective's outcome and opens the next one (or ends the session)."""
    record = state.current_record
    if record is not None:
        record.status = ObjectiveStatus.MASTERED if mastered else ObjectiveStatus.CLOSED_AT_CAP
        record.transfer_asked = state.transfer_check_asked
    state.finished_objectives.append(objective.id)
    turns: list[AgentTurn] = []
    if not mastered:
        state.not_mastered_objectives.append(objective.id)
        state.add("assistant", PARKED_MESSAGE, agent="Orchestrator")
        turns.append((PARKED_MESSAGE, "Orchestrator"))
    if record is not None:
        record.closed_at_turn = len(state.history)
    next_turn = _advance_to_next_objective(state)
    if next_turn is not None:
        turns.append(next_turn)
        return turns
    if state.not_mastered_objectives:
        topic = _topic(state)
        design = {o.id: o.design_id for o in topic.learning_objectives}
        closing = CLOSING_SOME_PARKED.format(
            mastered=len(state.mastered_objectives), total=len(state.finished_objectives),
            parked=", ".join(design.get(o, o) for o in state.not_mastered_objectives),
        )
    else:
        closing = CLOSING_ALL_MASTERED
    state.add("assistant", closing, agent="Orchestrator")
    turns.append((closing, "Orchestrator"))
    return turns


def handle_student_message(state: SessionState, student_text: str) -> list[AgentTurn]:
    """Process one student turn and return the resulting agent turn(s), in order."""
    if state.stage == Stage.DONE:
        return [(
            "We've covered all the objectives for this session, nicely done. "
            "Start a new session from the sidebar to go again.",
            "Facilitator",
        )]

    state.add("student", student_text)
    topic = _topic(state)
    objective = objective_by_index(topic, state.objective_index)
    assert objective is not None
    if state.current_record is None:  # e.g. a state built directly at a later stage
        state.open_record(objective.id, objective.design_id)
    record = state.current_record
    record.student_turns += 1
    turns: list[AgentTurn] = []

    if state.stage == Stage.WONDER:
        system_prompt = facilitator.build_system_prompt(
            topic, objective, state.solo_level_estimate, state.scaffold_level_last
        )
        result = _call_agent_guarded(
            state, system_prompt, _history_as_messages(state), objective, "Facilitator"
        )
        message = result["message"]
        state.add("assistant", message, agent="Facilitator")
        turns.append((message, "Facilitator"))
        state.question_category_last = result.get("question_category") or state.question_category_last
        state.drift_detected_last = bool(result.get("drift_detected"))
        if state.drift_detected_last:
            state.drift_events += 1
        if result.get("hypothesis_captured"):
            state.student_hypothesis = student_text
            state.stage = Stage.ELENCHUS
        return turns

    if state.stage == Stage.ELENCHUS:
        system_prompt = diagnostician.build_system_prompt(
            topic, objective, state.student_hypothesis, state.solo_level_estimate
        )
        result = _call_agent_guarded(
            state, system_prompt, _history_as_messages(state), objective, "Diagnostician"
        )
        message = result["message"]
        state.add("assistant", message, agent="Diagnostician")
        turns.append((message, "Diagnostician"))

        state.elenchus_rounds += 1
        state.record_solo("Diagnostician", result.get("solo_level_estimate"), result.get("evidence"))
        misconception = result.get("misconception_detected")
        if misconception:
            state.diagnostic_evidence = result.get("evidence") or state.diagnostic_evidence
            if misconception not in state.misconceptions_found:
                state.misconceptions_found.append(misconception)
            if misconception not in record.misconceptions:
                record.misconceptions.append(misconception)

        if result.get("gap_surfaced"):
            record.elenchus_exit = ElenchusExit.GAP_SURFACED
            state.stage = Stage.ACCEPT_REJECT
        elif state.elenchus_rounds >= MAX_ELENCHUS_ROUNDS:
            record.elenchus_exit = ElenchusExit.ROUND_CAP
            state.stage = Stage.ACCEPT_REJECT
        return turns

    if state.stage == Stage.ACCEPT_REJECT:
        result = _scaffolder_turn(state, topic, objective)
        message = result["message"]
        state.add("assistant", message, agent="Scaffolder")
        turns.append((message, "Scaffolder"))

        state.scaffold_rounds += 1
        state.record_solo("Scaffolder", result.get("solo_level_estimate"))
        mastered = bool(result.get("understanding_sufficient"))
        if not mastered and not result.get("transfer_check_asked"):
            # Only genuine support moves enter the support sequence (Table 4.11);
            # transfer questions and wrap-ups are not support.
            level = result.get("support_level")
            if level in SUPPORT_ORDER:
                state.scaffold_level_last = level
                record.support_sequence.append(level)
                record.ceiling_sequence.append(state.support_ceiling_last)
        if result.get("transfer_check_asked"):
            state.transfer_check_asked = True
            record.transfer_asked = True

        if mastered or state.scaffold_rounds >= MAX_SCAFFOLD_ROUNDS:
            turns.extend(_close_objective(state, objective, mastered))
        return turns

    raise RuntimeError(f"Unhandled stage: {state.stage}")
