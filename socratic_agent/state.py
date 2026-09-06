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
    scaffold_level_last: str | None = None

    finished_objectives: list[str] = field(default_factory=list)
    started: bool = False

    # Answer-leakage guard counters (session-wide, see guardrail.py). A "leak" is
    # caught by either the agent's own reveals_answer self-check or the literal
    # safety net; leak_attempts counts every time that happened (whether the retry
    # then produced a clean message), leak_hard_blocks counts times even the retry
    # still leaked and a hardcoded fallback message had to be substituted.
    leak_attempts: int = 0
    leak_hard_blocks: int = 0

    def reset_round_counters(self) -> None:
        self.elenchus_rounds = 0
        self.scaffold_rounds = 0
        self.student_hypothesis = None
        self.transfer_check_asked = False

    def add(self, role: str, content: str, agent: str | None = None) -> None:
        self.history.append(Turn(role=role, agent=agent, content=content))
