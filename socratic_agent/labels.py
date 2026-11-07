"""Readable labels for values shown to students and teachers (the stored values stay unchanged)."""
from __future__ import annotations

LABELS = {
    # SOLO levels
    "prestructural": "Prestructural", "unistructural": "Unistructural", "multistructural": "Multistructural",
    "relational": "Relational", "extended_abstract": "Extended abstract",
    # support levels
    "hint": "Hint", "simpler_sub_question": "Simpler sub-question", "worked_example": "Worked example",
    # objective outcomes
    "mastered": "Mastered", "closed_at_cap": "Closed at round limit", "in_progress": "In progress",
    # why the Elenchus stage ended
    "gap_surfaced": "Gap surfaced", "round_cap": "Round limit",
    # stages
    "WONDER": "Wonder", "ELENCHUS": "Elenchus", "ACCEPT_REJECT": "Accept / reject", "DONE": "Done",
}


def nice(value) -> str:
    if value is None or value == "":
        return "—"
    return LABELS.get(str(value), str(value))
