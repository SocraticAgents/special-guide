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

`state.topic_id` selects which Topic (topic_bank.TOPICS) the session is
about; every function here looks it up fresh from state rather than caching
it, since the caller sets state.topic_id once at session start and it never
changes mid-session.
"""
from __future__ import annotations

from typing import Callable

from socratic_agent.guardrail import is_leak
from socratic_agent.llm_client import Message, call_json_agent
from socratic_agent.prompts import diagnostician, facilitator, scaffolder
from socratic_agent.prompts._shared import LEAK_REPAIR_SUFFIX
from socratic_agent.state import MAX_ELENCHUS_ROUNDS, MAX_SCAFFOLD_ROUNDS, SessionState, Stage
from socratic_agent.topic_bank import LearningObjective, Topic, get_topic, objective_by_index

AgentTurn = tuple[str, str]  # (message, agent_name)

FALLBACK_MESSAGES = {
    "Facilitator": "Let's slow down for a second — rather than me telling you, what do you think happens here, step by step?",
    "Diagnostician": "Good attempt — before we go further, can you walk me through your reasoning for that, one step at a time?",
    "Scaffolder": "Let's take a smaller step: what's the very first thing about this you're already confident about?",
}


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
    system_prompt = facilitator.build_system_prompt(topic, objective)
    seed = facilitator.opening_user_message(objective)
    result = _call_agent_guarded(
        state, system_prompt, [Message(role="user", content=seed)], objective, "Facilitator"
    )
    message = result["message"]
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
    if objective_by_index(_topic(state), state.objective_index) is None:
        state.stage = Stage.DONE
        return None
    state.stage = Stage.WONDER
    return _facilitator_opens_objective(state)


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
    turns: list[AgentTurn] = []

    if state.stage == Stage.WONDER:
        system_prompt = facilitator.build_system_prompt(topic, objective)
        result = _call_agent_guarded(
            state, system_prompt, _history_as_messages(state), objective, "Facilitator"
        )
        message = result["message"]
        state.add("assistant", message, agent="Facilitator")
        turns.append((message, "Facilitator"))
        if result.get("hypothesis_captured"):
            state.student_hypothesis = student_text
            state.stage = Stage.ELENCHUS
        return turns

    if state.stage == Stage.ELENCHUS:
        system_prompt = diagnostician.build_system_prompt(topic, objective, state.student_hypothesis)
        result = _call_agent_guarded(
            state, system_prompt, _history_as_messages(state), objective, "Diagnostician"
        )
        message = result["message"]
        state.add("assistant", message, agent="Diagnostician")
        turns.append((message, "Diagnostician"))

        state.elenchus_rounds += 1
        state.solo_level_estimate = result.get("solo_level_estimate") or state.solo_level_estimate
        misconception = result.get("misconception_detected")
        if misconception and misconception not in state.misconceptions_found:
            state.misconceptions_found.append(misconception)

        if result.get("gap_surfaced") or state.elenchus_rounds >= MAX_ELENCHUS_ROUNDS:
            state.stage = Stage.ACCEPT_REJECT
        return turns

    if state.stage == Stage.ACCEPT_REJECT:
        system_prompt = scaffolder.build_system_prompt(
            topic, objective, state.misconceptions_found, state.scaffold_rounds, state.transfer_check_asked
        )
        result = _call_agent_guarded(
            state,
            system_prompt,
            _history_as_messages(state),
            objective,
            "Scaffolder",
            literal_check_exempt=lambda r: bool(r.get("understanding_sufficient")),
        )
        message = result["message"]
        state.add("assistant", message, agent="Scaffolder")
        turns.append((message, "Scaffolder"))

        state.scaffold_rounds += 1
        state.scaffold_level_last = result.get("support_level") or state.scaffold_level_last
        if result.get("transfer_check_asked"):
            state.transfer_check_asked = True

        if result.get("understanding_sufficient") or state.scaffold_rounds >= MAX_SCAFFOLD_ROUNDS:
            state.finished_objectives.append(objective.id)
            next_turn = _advance_to_next_objective(state)
            if next_turn is None:
                closing = (
                    "That covers everything for this session, nice work reasoning it through "
                    "yourself rather than being handed the answer."
                )
                state.add("assistant", closing, agent="Facilitator")
                turns.append((closing, "Facilitator"))
            else:
                turns.append(next_turn)
        return turns

    raise RuntimeError(f"Unhandled stage: {state.stage}")
