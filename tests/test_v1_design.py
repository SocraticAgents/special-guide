"""
V1 design verification: use cases (UC-xx), SOLO movement cases (S1-S10), the design
matrix (DD1-DD6) and the walkthrough scenario.

As in the V1 suite, the language model is replaced by scripted replies, so these tests
prove the program's own rules (stage control, guard, gate, support bounds, outcome
records). They do not measure model quality; that is the pilot's job.

Run from the code/ directory:
    python -m unittest tests.test_v1_design -v
"""
from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SOCRATIC_AGENT_DB", os.path.join(tempfile.mkdtemp(), "test.db"))

from socratic_agent import db, orchestrator  # noqa: E402
from socratic_agent.design_matrix import DESIGN_MATRIX  # noqa: E402
from socratic_agent.learner_model import Movement, classify_movement, support_ceiling  # noqa: E402
from socratic_agent.state import MAX_ELENCHUS_ROUNDS, SessionState, Stage  # noqa: E402
from socratic_agent.topic_bank import TOPICS, get_topic  # noqa: E402
from tests import test_v1_verification as v1  # noqa: E402  (module import: don't re-run V1 tests here)
from tests.test_v1_verification import Scripted, diag, fac, scaf  # noqa: E402


def state_at(stage: Stage, topic_id="loops", previous_solo=None, previous_support=None) -> SessionState:
    """A state already inside objective 0 of `topic_id`, at `stage`."""
    state = SessionState(topic_id=topic_id, started=True)
    obj = get_topic(topic_id).learning_objectives[0]
    state.open_record(obj.id, obj.design_id)
    state.stage = stage
    if previous_solo:
        state.record_solo("Diagnostician", previous_solo)
    state.scaffold_level_last = previous_support
    if previous_support:
        state.current_record.support_sequence.append(previous_support)
    return state


def run(state, *replies, text="student reply"):
    stub = Scripted(*replies)
    with mock.patch.object(orchestrator, "call_json_agent", stub):
        turns = orchestrator.handle_student_message(state, text)
    assert not stub.replies, "unused scripted replies"
    return turns, stub


class TestDesignTables(unittest.TestCase):
    def test_LO_ids_match_table_4_2(self):
        ids = [o.design_id for t in TOPICS for o in t.learning_objectives]
        self.assertEqual(ids, [f"LO{i}" for i in range(1, 12)])

    def test_DESIGN_MATRIX_every_named_test_exists(self):
        from tests import test_v1_progress as v1p
        known = set(dir(v1.TestV1Verification)) | set(dir(v1p.TestProgress)) | {
            n for c in (TestDesignTables, TestUseCases, TestSoloMovement) for n in dir(c)}
        for dd in DESIGN_MATRIX:
            self.assertTrue(dd.tests, dd.id)
            for name in dd.tests:
                self.assertIn(name, known, f"{dd.id} names missing test {name}")
        self.assertEqual([d.id for d in DESIGN_MATRIX], [f"DD{i}" for i in range(1, 8)])

    def test_SCENARIO_walkthrough_matches_expected_trace(self):
        from evaluation import walkthrough
        state, rows = walkthrough.run()
        outcomes = {r.design_id: r.status.value for r in state.objective_records}
        self.assertEqual(outcomes, walkthrough.EXPECTED_OUTCOMES)
        self.assertEqual(state.stage, Stage.DONE)
        self.assertEqual((state.leak_attempts, state.gate_rejections), (1, 1))
        lo6 = state.objective_records[1]
        self.assertEqual(lo6.elenchus_exit.value, "round_cap")
        self.assertEqual(lo6.support_sequence, ["hint", "simpler_sub_question", "hint"])  # rise, then fade
        self.assertIn("LO6", state.history[-1].content)  # closing names the parked objective


class TestUseCases(unittest.TestCase):
    # --- accounts and sessions -----------------------------------------------------
    def test_UC01_UC02_register_with_consent_then_sign_in(self):
        db.init_db()
        db.create_student("uc01", "Test Student", "secret12")
        self.assertEqual(db.verify_student("uc01", "secret12"), "Test Student")
        with self.assertRaises(db.AuthError):
            db.verify_student("uc01", "wrong")

    def test_UC03_starting_a_topic_opens_its_first_objective_record(self):
        state = SessionState(topic_id="variables")
        with mock.patch.object(orchestrator, "call_json_agent", Scripted(fac("What type is x now?"))):
            orchestrator.start_session(state)
        self.assertEqual(state.current_record.design_id, "LO1")
        self.assertEqual(state.stage, Stage.WONDER)

    # --- Wonder ------------------------------------------------------------------
    def test_UC04_hypothesis_moves_to_elenchus(self):
        state = state_at(Stage.WONDER)
        run(state, fac("So your prediction is 0 to 3.", hypothesis=True), text="0 1 2 3")
        self.assertEqual(state.stage, Stage.ELENCHUS)
        self.assertEqual(state.student_hypothesis, "0 1 2 3")

    def test_UC05_answer_request_declined_stays_in_wonder(self):
        state = state_at(Stage.WONDER)
        turns, _ = run(state, fac("What's your own guess first?"), text="just tell me the answer")
        self.assertEqual(state.stage, Stage.WONDER)
        self.assertEqual(turns[0][1], "Facilitator")

    def test_UC06_pressure_leak_is_regenerated(self):
        state = state_at(Stage.WONDER)
        turns, _ = run(state, fac("It prints 0, 1, 2."), fac("What would you guess?"), text="please, quiz tomorrow")
        self.assertEqual(state.leak_attempts, 1)
        self.assertNotIn("0, 1, 2", turns[0][0])

    def test_UC14_drift_is_counted_and_stage_kept(self):
        state = state_at(Stage.WONDER)
        run(state, dict(fac("Let's come back to the loop: what prints first?"), drift_detected=True),
            text="what's your favourite football team?")
        self.assertEqual((state.drift_events, state.stage), (1, Stage.WONDER))

    # --- Elenchus ----------------------------------------------------------------
    def test_UC07_dont_know_is_rated_prestructural_and_probed(self):
        state = state_at(Stage.ELENCHUS)
        run(state, diag("Look only at the first line: what is i?", solo="prestructural"), text="I don't know")
        self.assertEqual(state.solo_level_estimate, "prestructural")
        self.assertEqual(state.stage, Stage.ELENCHUS)

    def test_UC08_misconception_with_evidence_surfaces_gap(self):
        state = state_at(Stage.ELENCHUS)
        run(state, diag("Is 3 < 3 true?", solo="multistructural", mis="LOOP_M1_OFF_BY_ONE", gap=True),
            text="it prints 3 too")
        self.assertEqual(state.stage, Stage.ACCEPT_REJECT)
        self.assertEqual(state.current_record.elenchus_exit.value, "gap_surfaced")
        self.assertEqual(state.current_record.misconceptions, ["LOOP_M1_OFF_BY_ONE"])

    def test_UC08b_elenchus_round_cap_recorded(self):
        state = state_at(Stage.ELENCHUS)
        for _ in range(MAX_ELENCHUS_ROUNDS):
            run(state, diag())
        self.assertEqual(state.current_record.elenchus_exit.value, "round_cap")

    # --- Scaffolding ---------------------------------------------------------------
    def test_UC09_stuck_student_support_rises_one_level_at_a_time(self):
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="unistructural")
        run(state, scaf(support="hint", solo="unistructural"))
        run(state, scaf(support="simpler_sub_question", solo="unistructural"))
        self.assertEqual(state.current_record.support_sequence, ["hint", "simpler_sub_question"])
        self.assertEqual(state.support_violations, 0)

    def test_UC10_improving_student_support_fades(self):
        self.assertEqual(support_ceiling("simpler_sub_question", Movement.UP), "hint")
        self.assertEqual(support_ceiling("worked_example", Movement.JUMP_UP), "simpler_sub_question")
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="unistructural", previous_support="simpler_sub_question")
        _, stub = run(state, scaf(support="hint", solo="multistructural"))
        self.assertEqual(state.support_ceiling_last, "hint")
        self.assertEqual(state.fade_violations, 0)
        self.assertIn('fade instead: use at most "hint"', stub.prompts[0])

    def test_UC10b_rising_support_after_improvement_counted_as_fade_violation(self):
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="unistructural", previous_support="hint")
        _, stub = run(state, scaf(support="simpler_sub_question", solo="multistructural"),
                      scaf(support="simpler_sub_question", solo="multistructural"))
        self.assertIn("REVISION NOTICE", stub.prompts[1])
        self.assertEqual((state.fade_violations, state.support_violations), (1, 0))

    def test_UC11_justified_transfer_answer_masters_and_opens_next(self):
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="relational")
        run(state, scaf("What if it were i < 5?", solo="relational", transfer=True))
        run(state, scaf("You carried the rule to a new bound.", solo="extended_abstract", sufficient=True),
            fac("Next: what is i after the loop?"))
        self.assertEqual(state.objective_records[0].status.value, "mastered")
        self.assertEqual(state.current_record.design_id, "LO6")

    def test_UC12_bare_transfer_answer_refused_by_gate(self):
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="relational")
        run(state, scaf("What if it were i < 5?", solo="relational", transfer=True))
        run(state, scaf("Correct!", solo="unistructural", sufficient=True), scaf("Why?", solo="unistructural"),
            text="0 to 4")
        self.assertEqual(state.gate_rejections, 1)
        self.assertEqual(state.current_record.status.value, "in_progress")

    def test_UC13_cap_closes_objective_as_not_mastered_even_if_relational(self):
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="multistructural")
        run(state, scaf(support="hint", solo="multistructural"))
        run(state, scaf(support="simpler_sub_question", solo="multistructural"))
        turns, _ = run(state, scaf(support="hint", solo="relational"), fac("Next objective question"))
        rec = state.objective_records[0]
        self.assertEqual(rec.status.value, "closed_at_cap")
        self.assertEqual(rec.exit_solo, "relational")  # a good estimate is still not mastery
        self.assertNotIn(rec.objective_id, state.mastered_objectives)
        self.assertEqual(turns[1], (orchestrator.PARKED_MESSAGE, "Orchestrator"))

    def test_UC15_closing_message_is_honest_about_parked_objectives(self):
        state = state_at(Stage.ACCEPT_REJECT, topic_id="functions", previous_solo="unistructural")
        state.objective_index = 1  # last objective of the topic
        state.objective_records[0].objective_id, state.objective_records[0].design_id = "FN2", "LO11"
        for support in ("hint", "simpler_sub_question", "worked_example"):
            run(state, scaf(support=support, solo="unistructural"))
        self.assertEqual(state.stage, Stage.DONE)
        self.assertIn("LO11", state.history[-1].content)
        self.assertNotIn("nice work", state.history[-1].content)

    def test_UC17_message_after_done_calls_no_agent(self):
        state = state_at(Stage.DONE)
        turns, stub = run(state)
        self.assertEqual(stub.prompts, [])
        self.assertEqual(len(turns), 1)

    # --- teacher / researcher -----------------------------------------------------
    def test_UC19_UC20_dashboard_reads_objective_outcomes(self):
        db.init_db()
        db.create_student("uc19", "T", "secret12")
        sid = db.create_session("uc19", "loops")
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="relational")
        run(state, scaf(transfer=True, solo="relational"))
        run(state, scaf(solo="extended_abstract", sufficient=True), fac("next"))
        db.log_snapshot(sid, len(state.history) - 1, state)
        rows = [r for r in db.objective_outcomes() if r["session_id"] == sid]
        self.assertEqual([(r["design_id"], r["status"]) for r in rows], [("LO5", "mastered"), ("LO6", "in_progress")])

    def test_UC21_export_keeps_mastered_and_capped_apart(self):
        from evaluation.export_research_data import export
        db.init_db()
        db.create_student("uc21", "T", "secret12")
        sid = db.create_session("uc21", "loops")
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="unistructural")
        for support in ("hint", "simpler_sub_question"):
            run(state, scaf(support=support))
        run(state, scaf(support="worked_example"), fac("next"))
        for i, t in enumerate(state.history):
            db.log_turn(sid, i, t.role, t.agent, t.content)
        db.log_snapshot(sid, len(state.history) - 1, state)
        out = Path(tempfile.mkdtemp())
        export(out)
        with (out / "objective_outcomes.csv").open() as f:
            rows = [r for r in csv.DictReader(f) if r["session_id"] == sid]
        self.assertEqual(rows[0]["status"], "closed_at_cap")
        with (out / "solo_labelling.csv").open() as f:
            labels = [r for r in csv.DictReader(f) if r["session_id"] == sid]
        self.assertTrue(labels and all(r["source"] == "llm_estimate" and r["human_solo"] == "" for r in labels))
        self.assertNotIn("uc21", (out / "objective_outcomes.csv").read_text())  # no student IDs leave


    def test_UC22_solo_agreement_reports_disagreements(self):
        from evaluation.solo_agreement import agreement
        rows = [dict(session_id="s", turn_index=i, student_response="r", llm_solo_estimate=m, human_solo=h)
                for i, (m, h) in enumerate([("relational", "relational"), ("relational", "multistructural"),
                                            ("unistructural", "unistructural"), ("multistructural", "")])]
        result = agreement(rows)
        self.assertEqual((result["n"], result["llm_higher"], len(result["disagreements"])), (3, 1, 1))


class TestSoloMovement(unittest.TestCase):
    """Table 'How a student moves between SOLO levels' (S1-S10)."""

    def test_S01_prestructural_to_unistructural_is_up(self):
        self.assertEqual(classify_movement("prestructural", "unistructural"), Movement.UP)

    def test_S02_unistructural_to_multistructural_is_up(self):
        self.assertEqual(classify_movement("unistructural", "multistructural"), Movement.UP)

    def test_S03_multistructural_to_relational_is_up(self):
        self.assertEqual(classify_movement("multistructural", "relational"), Movement.UP)

    def test_S04_relational_transfer_to_extended_abstract_passes_gate(self):
        state = state_at(Stage.ACCEPT_REJECT, previous_solo="relational")
        state.transfer_check_asked = True
        run(state, scaf(solo="extended_abstract", sufficient=True), fac("next"))
        self.assertEqual(state.objective_records[0].status.value, "mastered")

    def test_S05_jump_of_two_levels_is_recorded_and_fades_support(self):
        self.assertEqual(classify_movement("unistructural", "relational"), Movement.JUMP_UP)
        self.assertEqual(support_ceiling("simpler_sub_question", Movement.JUMP_UP), "hint")

    def test_S06_stable_level_allows_one_step_more_support(self):
        self.assertEqual(classify_movement("unistructural", "unistructural"), Movement.STABLE)
        self.assertEqual(support_ceiling("hint", Movement.STABLE), "simpler_sub_question")

    def test_S07_level_can_go_down(self):
        state = state_at(Stage.ELENCHUS, previous_solo="relational")
        run(state, diag(solo="unistructural"))
        self.assertEqual(state.solo_trajectory[-1].movement, "down")
        self.assertEqual(state.solo_level_estimate, "unistructural")

    def test_S08_bare_correct_answer_is_unistructural_and_not_mastery(self):
        TestUseCases.test_UC12_bare_transfer_answer_refused_by_gate(self)

    def test_S09_cap_reached_with_good_estimate_is_still_not_mastery(self):
        TestUseCases.test_UC13_cap_closes_objective_as_not_mastered_even_if_relational(self)

    def test_S10_unrated_reply_keeps_previous_estimate(self):
        state = state_at(Stage.ELENCHUS, previous_solo="multistructural")
        run(state, diag(solo="not-a-level"))
        self.assertEqual(state.solo_trajectory[-1].movement, "unrated")
        self.assertEqual(state.solo_level_estimate, "multistructural")

    def test_DD2_every_estimate_labelled_llm_estimate(self):
        from evaluation import walkthrough
        state, _ = walkthrough.run()
        self.assertTrue(state.solo_trajectory)
        self.assertEqual({o.source for o in state.solo_trajectory}, {"llm_estimate"})
        self.assertEqual({o.agent for o in state.solo_trajectory}, {"Diagnostician", "Scaffolder"})


if __name__ == "__main__":
    unittest.main()
