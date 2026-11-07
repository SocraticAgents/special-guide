"""
Deterministic implementation-verification tests for Prototype V1 (thesis Table 4.28).

The language model is replaced by a scripted stub that returns predetermined
JSON replies, so every test checks the program's own logic independently of
the model's behaviour. Test IDs match Table 4.28; the five tests that failed
in the first V1 build (T07b, T11, T13, T16, T17) are the acceptance tests for
the corrections in Table 4.29.

Run from the code/ directory:
    python -m unittest tests.test_v1_verification -v
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

os.environ["SOCRATIC_AGENT_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from socratic_agent import db, orchestrator  # noqa: E402
from socratic_agent.guardrail import is_leak, literal_leak_match  # noqa: E402
from socratic_agent.state import MAX_ELENCHUS_ROUNDS, MAX_SCAFFOLD_ROUNDS, SessionState, Stage  # noqa: E402
from socratic_agent.topic_bank import TOPICS, get_topic  # noqa: E402

LO1 = get_topic("loops").learning_objectives[0]


def fac(message="What do you think it prints?", hypothesis=False, **kw):
    return dict(message=message, question_category="clarification", hypothesis_captured=hypothesis,
                drift_detected=False, reveals_answer=False, **kw)


def diag(message="What happens after the first pass?", solo="unistructural", mis=None, gap=False, **kw):
    return dict(message=message, solo_level_estimate=solo, misconception_detected=mis,
                evidence="their words" if mis else None, gap_surfaced=gap, reveals_answer=False, **kw)


def scaf(message="What is i the first time the condition is checked?", support="hint", solo="unistructural",
         transfer=False, sufficient=False, **kw):
    return dict(message=message, support_level=support, solo_level_estimate=solo,
                transfer_check_asked=transfer, understanding_sufficient=sufficient, reveals_answer=False, **kw)


class Scripted:
    """Stands in for call_json_agent: returns the queued replies in order."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, system_prompt, messages, **_):
        self.prompts.append(system_prompt)
        if not self.replies:
            raise AssertionError("Stub ran out of scripted replies")
        return self.replies.pop(0)


def new_state(topic_id="loops", stage=Stage.WONDER) -> SessionState:
    state = SessionState(topic_id=topic_id, started=True)
    state.stage = stage
    return state


def run(state, stub, text="student says something"):
    with mock.patch.object(orchestrator, "call_json_agent", stub):
        return orchestrator.handle_student_message(state, text)


class TestV1Verification(unittest.TestCase):
    def test_T01_catalogue_counts(self):
        self.assertEqual(len(TOPICS), 5)
        self.assertEqual(sum(len(t.learning_objectives) for t in TOPICS), 11)
        self.assertEqual(sum(len(t.misconceptions) for t in TOPICS), 22)

    def test_T02_literal_layer_catches_verbatim_leak_ignoring_case_and_spacing(self):
        self.assertIsNotNone(literal_leak_match("It   PRINTS 0,  1, 2 in total", LO1))

    def test_T03_literal_layer_ignores_guiding_question(self):
        self.assertIsNone(literal_leak_match("What is i before the loop starts?", LO1))

    def test_T04_self_report_alone_trips_guard(self):
        leaked, literal = is_leak("A harmless-looking sentence.", LO1, self_reported=True)
        self.assertTrue(leaked)
        self.assertIsNone(literal)

    def test_T05_leaking_draft_regenerated_and_clean_retry_shown(self):
        state = new_state()
        stub = Scripted(fac(message="It prints 0, 1, 2."), fac(message="What is i at the start?"))
        turns = run(state, stub)
        self.assertEqual(turns[0][0], "What is i at the start?")
        self.assertEqual((state.leak_attempts, state.leak_hard_blocks), (1, 0))

    def test_T06_two_leaking_drafts_replaced_by_fallback(self):
        state = new_state()
        stub = Scripted(fac(message="It prints 0, 1, 2."), fac(message="Fine: 0 1 2."))
        turns = run(state, stub)
        self.assertEqual(turns[0][0], orchestrator.FALLBACK_MESSAGES["Facilitator"])
        self.assertEqual(state.leak_hard_blocks, 1)

    def test_T07_answer_request_keeps_wonder_hypothesis_moves_to_elenchus(self):
        state = new_state()
        run(state, Scripted(fac(hypothesis=False)), "just give me the answer")
        self.assertEqual(state.stage, Stage.WONDER)
        run(state, Scripted(fac(message="So your prediction is 0 1 2 3?", hypothesis=True)), "0 1 2 3")
        self.assertEqual(state.stage, Stage.ELENCHUS)
        self.assertEqual(state.student_hypothesis, "0 1 2 3")

    def test_T07b_restating_wrong_answer_is_not_a_leak(self):
        self.assertIsNone(literal_leak_match("So you think it prints 0,1,2,3?", LO1))
        self.assertIsNone(literal_leak_match("So your prediction is 0 1 2 3?", LO1))

    def test_T08_elenchus_advances_after_cap_without_gap(self):
        state = new_state(stage=Stage.ELENCHUS)
        for _ in range(MAX_ELENCHUS_ROUNDS):
            run(state, Scripted(diag(gap=False)))
        self.assertEqual(state.stage, Stage.ACCEPT_REJECT)

    def test_T09_solo_stored_and_repeated_misconception_stored_once(self):
        state = new_state(stage=Stage.ELENCHUS)
        run(state, Scripted(diag(solo="multistructural", mis="LOOP_M3_CHECK_ORDER")))
        run(state, Scripted(diag(solo="multistructural", mis="LOOP_M3_CHECK_ORDER")))
        self.assertEqual(state.solo_level_estimate, "multistructural")
        self.assertEqual(state.misconceptions_found, ["LOOP_M3_CHECK_ORDER"])

    def test_T10_gap_surfaced_advances_after_one_round(self):
        state = new_state(stage=Stage.ELENCHUS)
        run(state, Scripted(diag(gap=True)))
        self.assertEqual(state.stage, Stage.ACCEPT_REJECT)
        self.assertEqual(state.elenchus_rounds, 1)

    def test_T11_mastery_refused_when_no_transfer_question_asked(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        stub = Scripted(
            scaf(message="Well done!", solo="relational", sufficient=True),
            scaf(message="What if the bound were 5 instead?", solo="relational", transfer=True),
        )
        run(state, stub)
        self.assertEqual(state.finished_objectives, [])
        self.assertTrue(state.transfer_check_asked)
        self.assertEqual(state.gate_rejections, 1)

    def test_T11b_bare_transfer_answer_does_not_grant_mastery(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        state.transfer_check_asked = True
        stub = Scripted(
            scaf(message="Perfect!", solo="unistructural", sufficient=True),
            scaf(message="Why would that be?", solo="unistructural"),
        )
        run(state, stub, "3")
        self.assertEqual(state.finished_objectives, [])
        self.assertEqual(state.gate_rejections, 1)

    def test_T12_support_cap_advances_dialogue(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        replies = [scaf(support="hint"), scaf(support="simpler_sub_question"), scaf(support="worked_example")]
        for reply in replies[:-1]:
            run(state, Scripted(reply))
        run(state, Scripted(replies[-1], fac(message="Next: what is i after the loop?")))
        self.assertEqual(state.objective_index, 1)
        self.assertEqual(state.stage, Stage.WONDER)
        self.assertEqual(state.scaffold_rounds, 0)
        self.assertEqual(MAX_SCAFFOLD_ROUNDS, 3)

    def test_T13_capped_objective_recorded_as_not_mastered(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        run(state, Scripted(scaf(support="hint")))
        run(state, Scripted(scaf(support="simpler_sub_question")))
        run(state, Scripted(scaf(support="worked_example"), fac()))
        self.assertEqual(state.finished_objectives, ["LO1"])
        self.assertEqual(state.not_mastered_objectives, ["LO1"])
        self.assertEqual(state.mastered_objectives, [])

    def test_T14_counters_and_transfer_flag_reset_for_next_objective(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        state.transfer_check_asked = True
        state.elenchus_rounds = 2
        run(state, Scripted(scaf(message="You traced it yourself.", solo="relational", sufficient=True), fac()))
        self.assertEqual(state.finished_objectives, ["LO1"])
        self.assertEqual(state.not_mastered_objectives, [])
        self.assertEqual((state.elenchus_rounds, state.scaffold_rounds), (0, 0))
        self.assertFalse(state.transfer_check_asked)
        self.assertIsNone(state.scaffold_level_last)

    def test_T15_wrapup_after_mastery_not_blocked_by_literal_layer(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        state.transfer_check_asked = True
        wrap = "You worked out it prints 0, 1, 2 because the check runs before each pass."
        turns = run(state, Scripted(scaf(message=wrap, solo="relational", sufficient=True), fac()))
        self.assertEqual(turns[0][0], wrap)
        self.assertEqual(state.leak_attempts, 0)

    def test_T16_solo_can_change_during_support_and_transfer(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        state.solo_level_estimate = "unistructural"
        run(state, Scripted(scaf(solo="relational", transfer=True, message="What if it were i <= 3?")))
        self.assertEqual(state.solo_level_estimate, "relational")

    def test_T17_first_support_move_starts_at_hint(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        stub = Scripted(scaf(support="worked_example"), scaf(support="hint"))
        run(state, stub)
        self.assertEqual(state.scaffold_level_last, "hint")
        self.assertIn("HIGHEST support level allowed this turn: hint", stub.prompts[0])

    def test_T17b_persistent_level_skip_is_counted(self):
        state = new_state(stage=Stage.ACCEPT_REJECT)
        run(state, Scripted(scaf(support="worked_example"), scaf(support="worked_example")))
        self.assertEqual(state.support_violations, 1)

    def test_T18_done_returns_closing_without_calling_agent(self):
        state = new_state(stage=Stage.DONE)
        turns = run(state, Scripted())
        self.assertEqual(len(turns), 1)

    def test_T19_only_curator_sees_canonical_answer(self):
        """Table 4.A: the Facilitator and Diagnostician never receive the answer."""
        from socratic_agent.prompts import diagnostician, facilitator, scaffolder

        topic = get_topic("loops")
        self.assertNotIn(LO1.canonical_answer, facilitator.build_system_prompt(topic, LO1))
        self.assertNotIn(LO1.canonical_answer, diagnostician.build_system_prompt(topic, LO1, "0 1 2"))
        self.assertIn(LO1.canonical_answer, scaffolder.build_system_prompt(topic, LO1, [], 0, False))

    def test_T20_participant_code_and_consent_stored(self):
        db.init_db()
        db.create_student("test-1", "Test Student", "secret1")
        row = next(s for s in db.list_students() if s["student_id"] == "test-1")
        self.assertRegex(row["participant_code"], r"^P\d{2}$")
        self.assertEqual(row["consent_version"], db.CONSENT_VERSION)


if __name__ == "__main__":
    unittest.main()
