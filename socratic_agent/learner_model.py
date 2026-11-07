"""
Learner model (V1): the deterministic record-keeping layer around the agents' outputs.

This module exists to keep three claims about the prototype honest (code review notes,
Nov 2026). Each one is enforced here rather than left to the write-up:

1. SOLO level = an LLM estimate, not a classifier.
   There is no separately trained SOLO classifier anywhere in this code. The level comes
   from the Cognitive Diagnostician (and, during scaffolding, the Scaffolding Curator)
   rating the student's latest response with the Table 4.9 indicators inside its prompt.
   Every observation is therefore stored with ``source="llm_estimate"`` and the agent that
   produced it, so the data can be compared with human rubric labels (DD2) rather than
   treated as ground truth. The only deterministic part is *movement* between two estimates
   (``classify_movement``), which is arithmetic on the ordinal scale, not a judgement.

2. Scaffolding = prompt-chosen support inside code-enforced bounds, not a ZPD measurement.
   The Curator chooses the support level; the orchestrator only bounds it
   (``support_ceiling``): start at hint, rise at most one level when the student has not
   moved, and do not rise (fade one level) on a turn whose own SOLO rating went up. These
   are rules *informed by* ZPD and fading (Wood, Bruner & Ross), applied to LLM estimates;
   they do not measure a student's ZPD.

3. Completing an objective is not the same as mastering it.
   An objective closes either because the mastery gate passed (transfer question asked on
   an earlier turn + a justified, relational-or-higher transfer answer) or because the
   support round cap was reached. Only the first is recorded as ``MASTERED``; the second is
   ``CLOSED_AT_CAP`` and is never counted as mastery anywhere (UI, dashboard, export).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

SOLO_ORDER = (
    "prestructural",
    "unistructural",
    "multistructural",
    "relational",
    "extended_abstract",
)

SUPPORT_ORDER = ("hint", "simpler_sub_question", "worked_example")

SOLO_SOURCE = "llm_estimate"


def solo_rank(level: str | None) -> int | None:
    return SOLO_ORDER.index(level) if level in SOLO_ORDER else None


class Movement(str, Enum):
    """How one SOLO estimate relates to the previous estimate for the same objective."""

    FIRST = "first_rating"      # no earlier estimate for this objective
    STABLE = "stable"           # same level
    UP = "up"                   # one level higher
    JUMP_UP = "jump_up"         # two or more levels higher in one response
    DOWN = "down"               # lower (the level describes the response, not the student)
    UNRATED = "unrated"         # agent returned no valid level


def classify_movement(previous: str | None, new: str | None) -> Movement:
    new_rank, prev_rank = solo_rank(new), solo_rank(previous)
    if new_rank is None:
        return Movement.UNRATED
    if prev_rank is None:
        return Movement.FIRST
    delta = new_rank - prev_rank
    if delta == 0:
        return Movement.STABLE
    if delta == 1:
        return Movement.UP
    if delta > 1:
        return Movement.JUMP_UP
    return Movement.DOWN


def support_ceiling(previous_support: str | None, movement: Movement | None) -> str:
    """Highest support level the Curator may use this turn (rule-bounded, not ZPD-measured).

    - first support move for an objective -> "hint"
    - the student's response moved UP/JUMP_UP -> fade: one level below the previous move
    - otherwise (stable, down, first, unrated) -> at most one level above the previous move
    """
    if previous_support not in SUPPORT_ORDER:
        return SUPPORT_ORDER[0]
    idx = SUPPORT_ORDER.index(previous_support)
    if movement in (Movement.UP, Movement.JUMP_UP):
        return SUPPORT_ORDER[max(idx - 1, 0)]
    return SUPPORT_ORDER[min(idx + 1, len(SUPPORT_ORDER) - 1)]


class ObjectiveStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"            # mastery gate passed
    CLOSED_AT_CAP = "closed_at_cap"  # support round cap reached; NOT evidence of mastery


class ElenchusExit(str, Enum):
    GAP_SURFACED = "gap_surfaced"
    ROUND_CAP = "round_cap"


@dataclass
class SoloObservation:
    turn_index: int
    objective_id: str
    agent: str
    level: str | None
    movement: str
    evidence: str | None = None
    source: str = SOLO_SOURCE


@dataclass
class ObjectiveRecord:
    objective_id: str
    design_id: str
    status: ObjectiveStatus = ObjectiveStatus.IN_PROGRESS
    entry_solo: str | None = None           # first estimate for this objective
    exit_solo: str | None = None            # last estimate before it closed
    peak_solo: str | None = None
    elenchus_exit: ElenchusExit | None = None
    support_sequence: list[str] = field(default_factory=list)
    ceiling_sequence: list[str] = field(default_factory=list)  # bound applied to each support move
    transfer_asked: bool = False
    misconceptions: list[str] = field(default_factory=list)
    student_turns: int = 0
    closed_at_turn: int | None = None  # history length when the objective closed

    def observe(self, level: str | None) -> None:
        if solo_rank(level) is None:
            return
        if self.entry_solo is None:
            self.entry_solo = level
        self.exit_solo = level
        if self.peak_solo is None or solo_rank(level) > solo_rank(self.peak_solo):
            self.peak_solo = level

    @property
    def solo_gain(self) -> int | None:
        """Exit minus entry rank. An observation of change in LLM estimates, not a learning gain."""
        if self.entry_solo is None or self.exit_solo is None:
            return None
        return solo_rank(self.exit_solo) - solo_rank(self.entry_solo)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["elenchus_exit"] = self.elenchus_exit.value if self.elenchus_exit else None
        d["solo_gain"] = self.solo_gain
        return d
