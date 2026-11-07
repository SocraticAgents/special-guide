"""
System walkthrough: one complete scripted scenario run through the REAL orchestrator.

The language model is replaced by scripted agent replies (what each agent "says" and the
JSON control fields it returns). Everything else — stage transitions, the leakage guard,
the mastery gate, the support ceiling, SOLO movement, objective outcomes — is the
production code. The trace therefore proves the orchestration logic described in the
thesis tables; it says nothing about how well a real model writes questions (that is
measured in the pilot).

Scenario: one student, topic Loops, objectives LO5 -> LO6 -> LO7 (Table 4.2).
  LO5  asks for the answer (leaky draft regenerated), states an off-by-one hypothesis,
       is probed, regresses, gets a hint, jumps to relational, passes a transfer check -> MASTERED
  LO6  holds the "loop variable vanishes" misconception, stalls through Elenchus (round cap),
       support rises hint -> sub-question, then fades after progress; support cap -> CLOSED_AT_CAP
  LO7  gives a bare transfer answer (gate refuses mastery), then justifies it -> MASTERED
  End  honest closing message: 2 of 3 applied to a new case, LO6 parked.

    python -m evaluation.walkthrough            -> prints the table, writes evaluation/results/walkthrough.{md,csv,json}
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

os.environ.setdefault("SOCRATIC_AGENT_DB", os.path.join(tempfile.mkdtemp(), "walkthrough.db"))

from socratic_agent import orchestrator  # noqa: E402
from socratic_agent.state import SessionState  # noqa: E402
from socratic_agent.topic_bank import get_topic  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def F(message, hypothesis=False, category="clarification", drift=False, leak=False):
    return dict(message=message, question_category=category, hypothesis_captured=hypothesis,
                drift_detected=drift, reveals_answer=leak)


def D(message, solo, mis=None, evidence=None, gap=False):
    return dict(message=message, solo_level_estimate=solo, misconception_detected=mis,
                evidence=evidence, gap_surfaced=gap, reveals_answer=False)


def S(message, support, solo, transfer=False, sufficient=False):
    return dict(message=message, support_level=support, solo_level_estimate=solo,
                transfer_check_asked=transfer, understanding_sufficient=sufficient, reveals_answer=False)


OPEN_LO5 = F("Here's a small loop. Before running it in your head line by line, what do you think it prints, and why?")
OPEN_LO6 = F("Suppose that same loop has just finished. What do you think `i` holds right after it ends, and can you still use it?")
OPEN_LO7 = F("Say you want the numbers 1 through 5 from `range(...)`. What would you put inside the brackets, and why?")

# Each step: (student text or None for the session start, use-case tags, scripted replies in call order)
SCENARIO: list[tuple[str | None, str, list[dict]]] = [
    (None, "UC-03, UC-04", [OPEN_LO5]),
    ("Can you just tell me what it prints? I have a quiz tomorrow.", "UC-05, UC-06",
     [F("It prints 0, 1, 2 — but try to see why.", leak=True),  # leaky draft -> guard retries
      F("I'd rather you work it out — that's what sticks before a quiz. What's your best guess for the first thing printed?", category="clarification")]),
    ("I think it prints 0 1 2 3, because it keeps going until 3.", "UC-04",
     [F("So your prediction is that the loop prints up to and including 3.", hypothesis=True, category="probing_reasons_evidence")]),
    ("i starts at 0 and it prints until it gets to 3", "UC-07, UC-08",
     [D("When i has just become 3, what is the very next thing Python does before it could print?", "unistructural",
        mis="LOOP_M3_CHECK_ORDER", evidence="it prints until it gets to 3")]),
    ("it checks i < 3 first... and then prints? so maybe 3 is printed and then it stops", "UC-08",
     [D("Try it with i equal to 3: is `3 < 3` true or false, and what does that mean for the print line?", "multistructural",
        mis="LOOP_M1_OFF_BY_ONE", evidence="maybe 3 is printed and then it stops", gap=True)]),
    ("I don't know, I'm confused about what happens after the print", "UC-09, S7",
     [S("Look only at the last line inside the loop. What does it do to i each time?", "hint", "unistructural")]),
    ("oh, i goes up by one after each print, so when i is 3 the check 3 < 3 is false and it stops before printing 3",
     "S5, UC-11",
     [S("What if the condition were `i < 5` instead — what would print, and why?", "hint", "relational", transfer=True)]),
    ("it would print 0 to 4, because the check happens before every print and fails once i reaches 5", "S4, UC-11",
     [S("You traced the check-before-print order and carried it to a new bound yourself.", "hint", "extended_abstract",
        sufficient=True),
      OPEN_LO6]),
    ("i disappears once the loop is over", "UC-04",
     [F("So your position is that i no longer exists after the loop.", hypothesis=True, category="probing_assumptions")]),
    ("because the loop is finished so its variables get deleted", "UC-08",
     [D("If you wrote `print(i)` on the line after the loop, what would you expect Python to do?", "unistructural",
        mis="LOOP_M2_VAR_VANISHES", evidence="the loop is finished so its variables get deleted")]),
    ("I think so", "S7",
     [D("Which line in the code is the last one that changes i?", "prestructural")]),
    ("not sure", "S6",
     [D("Let's take one step: right before the loop's final check, what value does i have?", "prestructural")]),
    ("no idea", "UC-09, S6",
     [S("Think about the very last time `i += 1` runs. What number does i become?", "hint", "prestructural")]),
    ("still no idea", "UC-09, S6",
     [S("Smaller step: if i is 2 and the line `i += 1` runs, what is i now?", "simpler_sub_question", "prestructural")]),
    ("i would be 3 then, since the last change made it 3", "UC-10, UC-13",
     [S("Good step. So when the loop stops, has anything happened that would remove i?", "hint", "multistructural"),
      OPEN_LO7]),
    ("range(1, 6)", "UC-04",
     [F("So your choice is range with a start of 1 and a stop of 6.", hypothesis=True, category="probing_reasons_evidence")]),
    ("because it stops before 6", "S8",
     [D("Why does the stop value need to be one more than the last number you want?", "unistructural")]),
    ("the stop value is never included, so to reach 5 the stop has to be 6, and the start 1 is included", "S3",
     [D("Is there a case where that rule would surprise someone who expects range to include its stop?", "relational", gap=True)]),
    ("someone wanting 1 to 5 might write range(1, 5) and miss the 5", "UC-11",
     [S("Now try a new case: which range call gives 0, 2, 4, 6, 8?", "hint", "relational", transfer=True)]),
    ("range(0, 10, 2)", "UC-12, S8",
     [S("Nice, that's it!", "hint", "unistructural", sufficient=True),  # bare answer -> gate refuses
      S("Before we move on — why does 10 work as the stop there?", "hint", "unistructural")]),
    ("10 is excluded so the last value is 8, and the step 2 skips the odd numbers — same stop rule as before",
     "S4, UC-11, UC-15",
     [S("You applied the excluded-stop rule to a stepped range and explained it.", "hint", "extended_abstract",
        sufficient=True)]),
]


class ScriptedLLM:
    def __init__(self):
        self.queue: list[dict] = []
        self.prompts: list[str] = []

    def __call__(self, system_prompt, messages, **_):
        self.prompts.append(system_prompt)
        if not self.queue:
            raise AssertionError("scripted LLM ran out of replies")
        return self.queue.pop(0)


def run() -> tuple[SessionState, list[dict]]:
    state = SessionState(topic_id="loops")
    llm = ScriptedLLM()
    design = {o.id: o.design_id for o in get_topic("loops").learning_objectives}
    rows: list[dict] = []
    with mock.patch.object(orchestrator, "call_json_agent", llm):
        for step, (student, tags, replies) in enumerate(SCENARIO):
            llm.queue = list(replies)
            leaks_before, gates_before = state.leak_attempts, state.gate_rejections
            n_obs = len(state.solo_trajectory)
            record = state.current_record
            lo_before = record.design_id if record else design[get_topic("loops").learning_objectives[0].id]
            n_support = len(record.support_sequence) if record else 0
            turns = orchestrator.start_session(state) if student is None else orchestrator.handle_student_message(state, student)
            assert not llm.queue, f"step {step}: {len(llm.queue)} scripted replies unused"
            rec_for_lo = next((r for r in state.objective_records if r.design_id == lo_before), None)
            new_obs = state.solo_trajectory[n_obs:]
            new_support = rec_for_lo.support_sequence[n_support:] if rec_for_lo else []
            new_ceiling = rec_for_lo.ceiling_sequence[n_support:] if rec_for_lo else []
            rows.append({
                "step": step,
                "lo": lo_before,
                "student": student or "(session start)",
                "agents": " + ".join(a for _, a in turns),
                "tutor": " ¶ ".join(m.replace("\n", " ") for m, _ in turns),
                "stage_after": state.stage.value,
                "solo_estimate": new_obs[-1].level if new_obs else "",
                "movement": new_obs[-1].movement if new_obs else "",
                "rated_by": new_obs[-1].agent if new_obs else "",
                "misconceptions": ", ".join(rec_for_lo.misconceptions) if rec_for_lo else "",
                "support": new_support[-1] if new_support else "",
                "ceiling": new_ceiling[-1] if new_ceiling else "",
                "rounds": f"E{state.elenchus_rounds}/S{state.scaffold_rounds}",
                "lo_status": rec_for_lo.status.value if rec_for_lo else "",
                "guard": ("leak regenerated" if state.leak_attempts > leaks_before else "")
                         + ("gate refused mastery" if state.gate_rejections > gates_before else ""),
                "cases": tags,
            })
    return state, rows


EXPECTED_OUTCOMES = {"LO5": "mastered", "LO6": "closed_at_cap", "LO7": "mastered"}


def main() -> None:
    state, rows = run()
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "walkthrough.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "objective_records": [r.as_dict() for r in state.objective_records],
        "solo_trajectory": [o.__dict__ for o in state.solo_trajectory],
        "counters": {k: getattr(state, k) for k in (
            "leak_attempts", "leak_hard_blocks", "gate_rejections", "support_violations", "fade_violations",
            "drift_events")},
        "final_stage": state.stage.value,
        "closing_message": state.history[-1].content,
    }
    (RESULTS / "walkthrough.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    cols = ["step", "lo", "student", "agents", "stage_after", "solo_estimate", "movement", "rated_by", "support", "ceiling",
            "rounds", "lo_status", "guard", "cases"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |")
    (RESULTS / "walkthrough.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(json.dumps(summary["counters"]), file=sys.stderr)
    for rec in state.objective_records:
        print(f"{rec.design_id}: {rec.status.value}  entry={rec.entry_solo} exit={rec.exit_solo} "
              f"elenchus_exit={rec.elenchus_exit.value if rec.elenchus_exit else None} support={rec.support_sequence}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
