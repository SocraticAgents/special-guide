"""
V1 progress tracking and motivating feedback (DD7, use cases UC-23 to UC-26).

Run from the code/ directory:
    python -m unittest tests.test_v1_progress -v
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SOCRATIC_AGENT_DB", os.path.join(tempfile.mkdtemp(), "test.db"))

from socratic_agent import db, orchestrator  # noqa: E402
from socratic_agent import progress as prog  # noqa: E402
from socratic_agent.state import SessionState, Stage  # noqa: E402
from socratic_agent.topic_bank import TOPICS, get_topic  # noqa: E402
from tests.test_v1_verification import Scripted, fac, scaf  # noqa: E402


def rec(design_id, status, entry="unistructural", exit_="relational", mis=(), support=("hint",)):
    return {"design_id": design_id, "status": status, "entry_solo": entry, "exit_solo": exit_, "peak_solo": exit_,
            "misconceptions": list(mis), "support_sequence": list(support)}


class TestProgress(unittest.TestCase):
    def test_UC23_progress_covers_all_eleven_objectives_and_never_merges_parked(self):
        p = prog.build_progress([rec("LO5", "mastered"), rec("LO6", "closed_at_cap")])
        self.assertEqual(p.objective_total, 11)
        self.assertEqual(p.mastered_total, 1)
        self.assertEqual(p.topic_counts(get_topic("loops")), (1, 1, 3))
        self.assertEqual(p.objectives["LO6"].status, "closed_at_cap")

    def test_UC23b_best_status_kept_across_sessions(self):
        p = prog.build_progress([rec("LO5", "mastered"), rec("LO5", "closed_at_cap")])
        self.assertEqual((p.objectives["LO5"].status, p.objectives["LO5"].attempts), ("mastered", 2))

    def test_UC24_milestones_reward_learning_behaviour(self):
        p = prog.build_progress([
            rec("LO6", "closed_at_cap", entry="prestructural", support=("hint", "simpler_sub_question", "hint")),
            rec("LO5", "mastered", entry="unistructural", mis=("LOOP_M1_OFF_BY_ONE",)),
            rec("LO6", "mastered"),
        ])
        self.assertEqual(set(p.milestones),
                         {"first_step", "stuck_with_it", "new_case", "changed_mind", "from_unsure", "comeback"})
        self.assertNotIn("topic_mastered", p.milestones)

    def test_UC24b_topic_mastered_only_when_every_objective_mastered(self):
        p = prog.build_progress([rec("LO1", "mastered"), rec("LO2", "closed_at_cap")])
        self.assertNotIn("topic_mastered", p.milestones)
        p = prog.build_progress([rec("LO1", "mastered"), rec("LO2", "mastered")])
        self.assertIn("topic_mastered", p.milestones)

    def test_UC24c_parked_objective_earns_no_mastery_milestone(self):
        p = prog.build_progress([rec("LO5", "closed_at_cap", mis=("X",))])
        self.assertEqual(p.milestones, ["first_step"])

    def test_UC25_feedback_is_template_honest_and_answer_free(self):
        mastered = prog.objective_feedback(rec("LO5", "mastered"))
        parked = prog.objective_feedback(rec("LO6", "closed_at_cap", entry="prestructural", exit_="multistructural"))
        self.assertIn("mastered", mastered)
        self.assertIn("not mastered yet", parked)
        self.assertIn("from not sure yet to several pieces of the idea (estimated)", parked)
        for obj in get_topic("loops").learning_objectives:
            for text in (mastered, parked):
                for literal in obj.protected_literals:
                    self.assertNotIn(literal.lower(), text.lower())

    def test_UC25b_no_growth_phrase_when_estimate_did_not_rise(self):
        self.assertIsNone(prog.growth_phrase("relational", "unistructural"))
        self.assertIsNone(prog.growth_phrase(None, "relational"))

    def test_UC26_next_step_prefers_retrying_a_parked_objective(self):
        p = prog.build_progress([rec("LO5", "mastered"), rec("LO6", "closed_at_cap")])
        step = prog.next_step(p)
        self.assertEqual((step["kind"], step["design_id"], step["objective_index"]), ("retry", "LO6", 1))
        p = prog.build_progress([rec("LO5", "mastered")])
        self.assertEqual(prog.next_step(p)["kind"], "continue")
        self.assertEqual(prog.next_step(prog.build_progress([]))["kind"], "start")

    def test_UC26b_practice_session_covers_one_objective_then_ends(self):
        state = SessionState(topic_id="loops", objective_index=1, practice_single=True)
        with mock.patch.object(orchestrator, "call_json_agent", Scripted(fac("What is i after the loop?"))):
            orchestrator.start_session(state)
        self.assertEqual(state.current_record.design_id, "LO6")
        state.stage = Stage.ACCEPT_REJECT
        state.transfer_check_asked = True
        state.record_solo("Diagnostician", "relational")
        with mock.patch.object(orchestrator, "call_json_agent", Scripted(scaf(solo="extended_abstract", sufficient=True))):
            orchestrator.handle_student_message(state, "i is still there and holds the last value because ...")
        self.assertEqual(state.stage, Stage.DONE)
        self.assertEqual([r.status.value for r in state.objective_records], ["mastered"])
        self.assertIsNotNone(state.objective_records[0].closed_at_turn)

    def test_UC23c_student_history_query_reads_all_sessions_oldest_first(self):
        db.init_db()
        db.create_student("prog1", "P", "secret12")
        for status in ("closed_at_cap", "mastered"):
            sid = db.create_session("prog1", "loops")
            state = SessionState(topic_id="loops")
            state.open_record("LO2", "LO6").status = prog_status(status)
            db.log_snapshot(sid, 0, state)
        rows = db.student_objective_records("prog1")
        self.assertEqual([r["status"] for r in rows], ["closed_at_cap", "mastered"])
        self.assertIn("comeback", prog.build_progress(rows).milestones)

    def test_milestones_never_reward_speed(self):
        text = " ".join(m.title + m.how_to_earn for m in prog.MILESTONES).lower()
        for word in ("fast", "quick", "streak", "minutes", "speed"):
            self.assertNotIn(word, text)
        self.assertEqual(len({m.id for m in prog.MILESTONES}), len(prog.MILESTONES))
        self.assertEqual(sum(len(t.learning_objectives) for t in TOPICS), 11)


def prog_status(value):
    from socratic_agent.learner_model import ObjectiveStatus
    return ObjectiveStatus(value)


if __name__ == "__main__":
    unittest.main()
