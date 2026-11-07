"""
Student progress tracking and motivating feedback (V1, design decision DD7).

Everything here is deterministic and template-based — no LLM call — so progress feedback
can never reveal an answer and always says the same thing for the same record.

Design rules (and the Chapter 2 theory each one comes from):
- Feedback describes the learner's own process and growth, and says what to do next,
  rather than giving a grade (formative assessment and feedback, Black & Wiliam [16]).
- Growth is described in SOLO terms the student can read ("one piece of the idea" ->
  "how the pieces connect"), always labelled as an estimate (SOLO [22]; review note 1).
- Changing one's mind after a misconception surfaced is rewarded explicitly
  (conceptual change, Posner et al. [9]).
- The learner chooses what to practise next, including retrying a parked objective
  (learner agency in AI-supported learning, Ouyang & Jiao [2]).
- Mastered and parked are never merged: a parked objective is "not yet", never "done"
  (review note 3). No milestone rewards speed, streaks or session length.

The input is a list of objective-record dicts (learner_model.ObjectiveRecord.as_dict()
plus "session_id", "topic" and "started_at"), oldest session first.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from socratic_agent.learner_model import SOLO_ORDER, solo_rank
from socratic_agent.topic_bank import TOPICS, Topic

# Student-facing wording for SOLO levels. Shown with "estimated" in the UI.
SOLO_PLAIN = {
    "prestructural": "not sure yet",
    "unistructural": "one piece of the idea",
    "multistructural": "several pieces of the idea",
    "relational": "how the pieces connect",
    "extended_abstract": "using the idea on a new case",
}

STATUS_RANK = {"not_started": 0, "in_progress": 1, "closed_at_cap": 2, "mastered": 3}
STATUS_ICON = {"mastered": "✅", "closed_at_cap": "⏸️", "in_progress": "🔄", "not_started": "○"}
STATUS_TEXT = {
    "mastered": "Mastered — applied to a new case",
    "closed_at_cap": "Parked — not yet, worth another go",
    "in_progress": "In progress",
    "not_started": "Not started",
}


@dataclass(frozen=True)
class Milestone:
    id: str
    icon: str
    title: str
    how_to_earn: str


MILESTONES: tuple[Milestone, ...] = (
    Milestone("first_step", "👣", "First step", "Finish working on any objective, mastered or parked."),
    Milestone("new_case", "🎯", "Applied it to a new case", "Master an objective by explaining a transfer question."),
    Milestone("changed_mind", "🔄", "Changed your mind", "Master an objective after a misconception came up in it."),
    Milestone("from_unsure", "🌱", "From unsure to sure", "Master an objective you started with 'not sure yet' or 'one piece of the idea'."),
    Milestone("stuck_with_it", "🧗", "Stuck with it", "Keep going through three rounds of support on one objective."),
    Milestone("comeback", "💪", "Comeback", "Master an objective that was parked in an earlier session."),
    Milestone("topic_mastered", "🏆", "Topic mastered", "Master every objective in one topic."),
)
MILESTONE_BY_ID = {m.id: m for m in MILESTONES}


@dataclass
class ObjectiveProgress:
    design_id: str
    objective_id: str
    topic_id: str
    status: str = "not_started"          # best status reached across all sessions
    attempts: int = 0                    # objective records that closed (mastered or parked)
    first_entry_solo: str | None = None  # first estimate ever, for growth
    best_solo: str | None = None         # highest estimate ever
    parked_before_mastered: bool = False


@dataclass
class StudentProgress:
    objectives: dict[str, ObjectiveProgress] = field(default_factory=dict)  # by design_id
    milestones: list[str] = field(default_factory=list)                   # earned ids, in order earned

    def topic_counts(self, topic: Topic) -> tuple[int, int, int]:
        """(mastered, parked, total) for one topic."""
        rows = [self.objectives[o.design_id] for o in topic.learning_objectives]
        return (sum(r.status == "mastered" for r in rows), sum(r.status == "closed_at_cap" for r in rows), len(rows))

    @property
    def mastered_total(self) -> int:
        return sum(r.status == "mastered" for r in self.objectives.values())

    @property
    def objective_total(self) -> int:
        return len(self.objectives)


def _empty_progress() -> StudentProgress:
    progress = StudentProgress()
    for topic in TOPICS:
        for obj in topic.learning_objectives:
            progress.objectives[obj.design_id] = ObjectiveProgress(obj.design_id, obj.id, topic.id)
    return progress


def _earn(progress: StudentProgress, milestone_id: str) -> None:
    if milestone_id not in progress.milestones:
        progress.milestones.append(milestone_id)


def build_progress(records: list[dict]) -> StudentProgress:
    """Folds every objective record (oldest first) into one progress view."""
    progress = _empty_progress()
    for rec in records:
        row = progress.objectives.get(rec.get("design_id"))
        if row is None:
            continue
        status = rec.get("status", "in_progress")
        if row.first_entry_solo is None and rec.get("entry_solo") in SOLO_ORDER:
            row.first_entry_solo = rec["entry_solo"]
        for level in (rec.get("peak_solo"), rec.get("exit_solo")):
            if solo_rank(level) is not None and (row.best_solo is None or solo_rank(level) > solo_rank(row.best_solo)):
                row.best_solo = level
        if status in ("mastered", "closed_at_cap"):
            row.attempts += 1
            _earn(progress, "first_step")
        if len(rec.get("support_sequence") or []) >= 3:
            _earn(progress, "stuck_with_it")
        if status == "closed_at_cap" and row.status != "mastered":
            row.parked_before_mastered = True
        if status == "mastered":
            _earn(progress, "new_case")
            if rec.get("misconceptions"):
                _earn(progress, "changed_mind")
            if solo_rank(rec.get("entry_solo")) is not None and solo_rank(rec["entry_solo"]) <= 1:
                _earn(progress, "from_unsure")
            if row.parked_before_mastered and row.status != "mastered":
                _earn(progress, "comeback")
        if STATUS_RANK[status] > STATUS_RANK[row.status]:
            row.status = status
        if status == "mastered":
            topic = next(t for t in TOPICS if t.id == row.topic_id)
            mastered, _, total = progress.topic_counts(topic)
            if mastered == total:
                _earn(progress, "topic_mastered")
    return progress


def new_milestones(before: StudentProgress, after: StudentProgress) -> list[Milestone]:
    return [MILESTONE_BY_ID[m] for m in after.milestones if m not in before.milestones]


def growth_phrase(entry: str | None, exit_: str | None) -> str | None:
    """'from one piece of the idea to how the pieces connect' — None if there is no growth to show."""
    if solo_rank(entry) is None or solo_rank(exit_) is None or solo_rank(exit_) <= solo_rank(entry):
        return None
    return f"from {SOLO_PLAIN[entry]} to {SOLO_PLAIN[exit_]}"


def objective_feedback(record: dict) -> str:
    """Process-level feedback shown when an objective closes. Never states an answer."""
    lo = record["design_id"]
    growth = growth_phrase(record.get("entry_solo"), record.get("exit_solo"))
    if record["status"] == "mastered":
        msg = f"{lo} mastered — you explained it on a new case."
        if record.get("misconceptions"):
            msg += " You also changed your mind about an earlier idea, which is how understanding grows."
        elif growth:
            msg += f" Your answers moved {growth} (estimated)."
        return msg
    growth_text = f" Your answers still moved {growth} (estimated)." if growth else ""
    return (f"{lo} is parked for now — not mastered yet, and that's fine.{growth_text} "
            f"It will be waiting for you in My Progress.")


def next_step(progress: StudentProgress) -> dict:
    """The single suggested next action: retry a parked objective, continue a topic, or start one."""
    for topic in TOPICS:
        for idx, obj in enumerate(topic.learning_objectives):
            if progress.objectives[obj.design_id].status == "closed_at_cap":
                return {"kind": "retry", "topic_id": topic.id, "objective_index": idx, "design_id": obj.design_id,
                        "text": f"Have another go at {obj.design_id} ({topic.name}) — you've already made a start."}
    for topic in TOPICS:
        mastered, _, total = progress.topic_counts(topic)
        if 0 < mastered < total:
            return {"kind": "continue", "topic_id": topic.id, "objective_index": 0, "design_id": None,
                    "text": f"Keep going with {topic.name}: {mastered} of {total} objectives mastered."}
    for topic in TOPICS:
        if progress.topic_counts(topic)[0] == 0:
            return {"kind": "start", "topic_id": topic.id, "objective_index": 0, "design_id": None,
                    "text": f"Try a new topic: {topic.emoji} {topic.name} ({topic.difficulty})."}
    return {"kind": "done", "topic_id": None, "objective_index": 0, "design_id": None,
            "text": "You've mastered every objective. Try explaining one of them to a friend."}
