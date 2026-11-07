"""
Session state for one Socratic-Agent tutoring session.

The stage field implements the state machine described in the proposal's
Section 2.9.1 (Wonder/Hypothesis -> Elenchus -> Acceptance-Rejection/Action),
collapsed to three stages since Wonder and Hypothesis are both owned by the
Facilitator agent and are really "open" vs. "hypothesis captured" within the
same stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from socratic_agent.learner_model import (
    Movement,
    ObjectiveRecord,
    SoloObservation,
    classify_movement,
)

MAX_ELENCHUS_ROUNDS = 3   # CLT-motivated cap: don't probe forever (Sec 2.9.2 / 2.8.2)
MAX_SCAFFOLD_ROUNDS = 3   # cap on hint/example rounds before forcing progression


class Stage(str, Enum):
    WONDER = "WONDER"              # Facilitator: pose question / capture hypothesis
    ELENCHUS = "ELENCHUS"          # Diagnostician: probe for gaps/misconceptions
    ACCEPT_REJECT = "ACCEPT_REJECT"  # Scaffolder: calibrate support, judge sufficiency
    DONE = "DONE"                  # all objectives covered


@dataclass
class Turn:
    role: str        # "student" | "assistant"
    agent: str | None  # "Facilitator" | "Diagnostician" | "Scaffolder" | None (student turns)
    content: str


@dataclass
class SessionState:
    topic_id: str = ""  # which Topic (topic_bank.TOPICS) this session is about
    objective_index: int = 0
    stage: Stage = Stage.WONDER
    history: list[Turn] = field(default_factory=list)

    student_hypothesis: str | None = None
    elenchus_rounds: int = 0
    scaffold_rounds: int = 0
    transfer_check_asked: bool = False  # has a generalization/"what if X changed" check happened yet?

    solo_level_estimate: str | None = None
    misconceptions_found: list[str] = field(default_factory=list)
    scaffold_level_last: str | None = None  # last support move for the CURRENT objective (Table 4.11)
    diagnostic_evidence: str | None = None  # student's own words behind the last misconception (Table 4.B)

    # Facilitator control fields (Table 4.22) — stored so Table 4.10's category and
    # drift rules can be audited from the snapshots, not only by reading transcripts.
    question_category_last: str | None = None
    drift_detected_last: bool = False
    drift_events: int = 0

    # Every objective that has closed, mastered or not (drives the progress bar), plus
    # the subset that closed at the support cap without mastery (Sec 4.7.3: "recorded as
    # not mastered"). Mastered = finished_objectives minus not_mastered_objectives.
    finished_objectives: list[str] = field(default_factory=list)
    not_mastered_objectives: list[str] = field(default_factory=list)
    started: bool = False
    # Practice mode (progress page "retry"): the session covers only the objective it starts
    # at (objective_index), then ends.
    practice_single: bool = False

    # Answer-leakage guard counters (session-wide, see guardrail.py). A "leak" is
    # caught by either the agent's own reveals_answer self-check or the literal
    # safety net; leak_attempts counts every time that happened (whether the retry
    # then produced a clean message), leak_hard_blocks counts times even the retry
    # still leaked and a hardcoded fallback message had to be substituted.
    leak_attempts: int = 0
    leak_hard_blocks: int = 0

    # V1 learner model (socratic_agent/learner_model.py). solo_trajectory keeps every SOLO
    # estimate with its source ("llm_estimate"), agent and movement; objective_records keeps
    # one record per objective with an explicit MASTERED / CLOSED_AT_CAP status.
    solo_trajectory: list[SoloObservation] = field(default_factory=list)
    objective_records: list[ObjectiveRecord] = field(default_factory=list)
    solo_movement_last: str | None = None
    support_ceiling_last: str | None = None  # the bound the orchestrator applied last turn

    # Hard-blocked rule counters (Table 4.E). gate_rejections: the Curator claimed
    # mastery without an earlier transfer question or without a justified (relational+)
    # transfer answer, and the orchestrator refused it. support_violations: a support
    # move skipped a level and was still skipping after one regeneration.
    gate_rejections: int = 0
    support_violations: int = 0
    fade_violations: int = 0  # support rose on a turn whose own SOLO rating went up

    @property
    def mastered_objectives(self) -> list[str]:
        return [o for o in self.finished_objectives if o not in self.not_mastered_objectives]

    @property
    def current_record(self) -> ObjectiveRecord | None:
        if self.objective_records and self.objective_records[-1].status.value == "in_progress":
            return self.objective_records[-1]
        return None

    def open_record(self, objective_id: str, design_id: str) -> ObjectiveRecord:
        record = ObjectiveRecord(objective_id=objective_id, design_id=design_id)
        self.objective_records.append(record)
        return record

    def previous_solo_this_objective(self) -> str | None:
        record = self.current_record
        return record.exit_solo if record else None

    def record_solo(self, agent: str, level: str | None, evidence: str | None = None) -> Movement:
        """Stores one LLM SOLO estimate and returns how it moved for this objective."""
        record = self.current_record
        objective_id = record.objective_id if record else ""
        movement = classify_movement(self.previous_solo_this_objective(), level)
        self.solo_trajectory.append(SoloObservation(
            turn_index=len(self.history) - 1, objective_id=objective_id, agent=agent,
            level=level, movement=movement.value, evidence=evidence,
        ))
        if record:
            record.observe(level)
        if movement != Movement.UNRATED:
            self.solo_level_estimate = level
        self.solo_movement_last = movement.value
        return movement

    def reset_round_counters(self) -> None:
        """Starts a fresh objective-specific state (Sec 4.8: evidence for one objective
        is never carried over as evidence for the next)."""
        self.elenchus_rounds = 0
        self.scaffold_rounds = 0
        self.student_hypothesis = None
        self.transfer_check_asked = False
        self.scaffold_level_last = None
        self.solo_movement_last = None
        self.support_ceiling_last = None

    def add(self, role: str, content: str, agent: str | None = None) -> None:
        self.history.append(Turn(role=role, agent=agent, content=content))
