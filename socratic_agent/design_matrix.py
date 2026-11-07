"""
Design-decision matrix (thesis Section 4.6.1, DD1-DD6) as data.

Each row links the literature basis and hypothesis to the code that implements it, says
HOW the rule is enforced, and names the tests and instruments that give evidence for it.
tests/test_v1_design.py checks that every test named here exists and passes, so the matrix
cannot silently drift from the code.

Enforcement levels (used verbatim in the thesis tables):
  code       – a deterministic rule in the orchestrator/guard; cannot be skipped by the model
  bounded    – the LLM decides, the orchestrator checks the decision against a rule and
               regenerates/overrides/counts when it is broken
  prompt     – an instruction to the LLM only; measured in the pilot, not guaranteed
  instrument – evidence comes from the study instruments (quiz, survey), not the software
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignDecision:
    id: str
    basis: str
    hypothesis: str
    requirement: str
    decision: str
    code: tuple[str, ...]
    enforcement: dict[str, str]  # rule -> enforcement level
    tests: tuple[str, ...]
    planned_evaluation: str
    claim_limit: str  # what this decision does NOT show


DESIGN_MATRIX: tuple[DesignDecision, ...] = (
    DesignDecision(
        id="DD1",
        basis="Socratic questioning (Section 2.2.5; Ng et al. [12]; Kirschner et al. [13])",
        hypothesis="H2",
        requirement="Elicit reasoning without supplying ready-made solutions",
        decision="Facilitator prompt and orchestrator response handling",
        code=("prompts/facilitator.py", "orchestrator.handle_student_message (WONDER)"),
        enforcement={
            "one question per turn, no confirmation, categories": "prompt",
            "hypothesis captured -> ELENCHUS": "code",
            "drift flagged and counted": "bounded",
            "Facilitator never receives the canonical answer": "code",
        },
        tests=("test_T07_answer_request_keeps_wonder_hypothesis_moves_to_elenchus",
               "test_T19_only_curator_sees_canonical_answer",
               "test_UC05_answer_request_declined_stays_in_wonder",
               "test_UC14_drift_is_counted_and_stage_kept"),
        planned_evaluation="Facilitator behavioural rubric (Table 4.10) and answer-leakage scenarios",
        claim_limit="Shows the dialogue is staged and the answer is withheld; not that questions are pedagogically good.",
    ),
    DesignDecision(
        id="DD2",
        basis="SOLO-informed cognitive diagnosis (Biggs & Collis [22]; Dong et al. [15]; Nichols [14])",
        hypothesis="H1",
        requirement="Estimate demonstrated understanding and possible misconceptions",
        decision="Diagnostician prompt, shared session state, learner model (SOLO trajectory)",
        code=("prompts/diagnostician.py", "learner_model.classify_movement", "state.record_solo"),
        enforcement={
            "SOLO level of each response": "prompt (LLM estimate; no trained classifier)",
            "movement between estimates": "code",
            "misconception stored only with evidence, once": "bounded",
            "estimate stored with source=llm_estimate": "code",
        },
        tests=("test_T09_solo_stored_and_repeated_misconception_stored_once",
               "test_S01_prestructural_to_unistructural_is_up",
               "test_S07_level_can_go_down",
               "test_S10_unrated_reply_keeps_previous_estimate",
               "test_DD2_every_estimate_labelled_llm_estimate",
               "test_UC22_solo_agreement_reports_disagreements"),
        planned_evaluation="Agreement with rubric-based human SOLO labels (solo_labelling.csv -> evaluation/solo_agreement.py); report disagreements",
        claim_limit="The SOLO level is the Diagnostician's estimate of one response, not a validated classification.",
    ),
    DesignDecision(
        id="DD3",
        basis="Scaffolding and ZPD (Vygotsky [17]; Wood, Bruner & Ross [18]); CLT (Sweller [19])",
        hypothesis="H3",
        requirement="Adjust hints to the learner's demonstrated needs, and fade them",
        decision="Curator prompt, support ceiling (learner_model.support_ceiling), round counter",
        code=("prompts/scaffolder.py", "learner_model.support_ceiling", "orchestrator._scaffolder_turn"),
        enforcement={
            "support level chosen": "prompt (LLM choice)",
            "first move is a hint; rise one level at most": "bounded",
            "fade one level when the response's SOLO went up": "bounded",
            "support round cap (3)": "code",
            "worked example on different values": "prompt",
        },
        tests=("test_T17_first_support_move_starts_at_hint",
               "test_T17b_persistent_level_skip_is_counted",
               "test_UC09_stuck_student_support_rises_one_level_at_a_time",
               "test_UC10_improving_student_support_fades",
               "test_UC10b_rising_support_after_improvement_counted_as_fade_violation"),
        planned_evaluation="Scenario-based support-level and fading rubric; support_violations / fade_violations counters",
        claim_limit="Rules informed by ZPD applied to LLM estimates; the system does not measure a student's ZPD.",
    ),
    DesignDecision(
        id="DD4",
        basis="Specialised roles and prompt engineering (Li et al. [26]; Liu et al. [8]; Wang et al. [7])",
        hypothesis="H4",
        requirement="Separate questioning, diagnosis and support while coordinating them",
        decision="Three role prompts, shared LLM client, central orchestrator and session state",
        code=("orchestrator.py", "state.py", "llm_client.call_json_agent"),
        enforcement={
            "exactly one agent per stage": "code",
            "stage transitions from typed JSON fields + round caps": "code",
            "per-objective state reset": "code",
        },
        tests=("test_T08_elenchus_advances_after_cap_without_gap",
               "test_T10_gap_surfaced_advances_after_one_round",
               "test_T14_counters_and_transfer_flag_reset_for_next_objective",
               "test_UC08_misconception_with_evidence_surfaces_gap",
               "test_SCENARIO_walkthrough_matches_expected_trace"),
        planned_evaluation="Agent-level tests and stage-transition tests (this suite)",
        claim_limit="Shows coordinated behaviour is implementable; not that three agents beat one.",
    ),
    DesignDecision(
        id="DD5",
        basis="Risk of direct answer disclosure (Maurya et al. [23]; Zhao et al. [24])",
        hypothesis="H2",
        requirement="Detect and reduce premature answer release",
        decision="Two-layer guard (self-report + literal), corrective retry, fallback message",
        code=("guardrail.py", "orchestrator._call_agent_guarded"),
        enforcement={
            "literal match of protected answers": "code",
            "paraphrase detection": "prompt (agent self-report)",
            "retry then fallback": "code",
        },
        tests=("test_T05_leaking_draft_regenerated_and_clean_retry_shown",
               "test_T06_two_leaking_drafts_replaced_by_fallback",
               "test_T07b_restating_wrong_answer_is_not_a_leak",
               "test_UC06_pressure_leak_is_regenerated"),
        planned_evaluation="Adversarial leakage rate and failure-case analysis",
        claim_limit="Catches listed literals and self-reported leaks; paraphrased leaks the model does not report can pass.",
    ),
    DesignDecision(
        id="DD6",
        basis="Learning assessment and user experience (Black & Wiliam [16]; Ch. 3)",
        hypothesis="H5; usability descriptive (RQ3)",
        requirement="Examine short-term score change and perceived usability",
        decision="Student interface, learning session, objective outcomes, study instruments",
        code=("app.py", "pages/1_Teacher_Dashboard.py", "evaluation/export_research_data.py", "../instruments/"),
        enforcement={
            "mastered vs closed-at-cap kept separate": "code",
            "score change and usability": "instrument",
        },
        tests=("test_T13_capped_objective_recorded_as_not_mastered",
               "test_UC13_cap_closes_objective_as_not_mastered_even_if_relational",
               "test_UC15_closing_message_is_honest_about_parked_objectives",
               "test_UC21_export_keeps_mastered_and_capped_apart"),
        planned_evaluation="One-group pre-test/post-test and questionnaire",
        claim_limit="Covering an objective is not evidence of mastery; a pilot score change is not a general effect.",
    ),
    DesignDecision(
        id="DD7",
        basis="Formative feedback (Black & Wiliam [16]); learner agency (Ouyang & Jiao [2]); "
              "SOLO growth (Biggs & Collis [22]); conceptual change (Posner et al. [9])",
        hypothesis="RQ3 (descriptive)",
        requirement="Make each student's progress visible and give motivating, process-level feedback "
                    "without revealing answers or overstating mastery",
        decision="My Progress page, milestone rules, template feedback cards, next-step and retry (no LLM)",
        code=("socratic_agent/progress.py", "pages/0_My_Progress.py", "app.py (feedback cards, summary)",
              "db.student_objective_records", "state.practice_single"),
        enforcement={
            "feedback text from fixed templates, no LLM": "code",
            "mastered and parked shown separately": "code",
            "milestones reward behaviour, not speed": "code",
            "growth described as an estimate": "code",
        },
        tests=("test_UC23_progress_covers_all_eleven_objectives_and_never_merges_parked",
               "test_UC24_milestones_reward_learning_behaviour",
               "test_UC24c_parked_objective_earns_no_mastery_milestone",
               "test_UC25_feedback_is_template_honest_and_answer_free",
               "test_UC26_next_step_prefers_retrying_a_parked_objective",
               "test_UC26b_practice_session_covers_one_objective_then_ends"),
        planned_evaluation="Post-session survey items on progress visibility and motivation; retries of parked objectives in the logs",
        claim_limit="Shows progress is tracked and feedback is consistent; does not show that it motivates students.",
    ),
)


def by_id(dd_id: str) -> DesignDecision:
    return next(d for d in DESIGN_MATRIX if d.id == dd_id)
