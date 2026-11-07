"""
Socratic-Agent — Streamlit chat interface (Section 3.5 of the proposal).

Flow: sign in / sign up  ->  pick a topic  ->  chat, with a live diagnostic
panel in the sidebar. "Change topic" returns to the topic picker without
signing out; "Log out" clears everything.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import os

import streamlit as st

from socratic_agent import db
from socratic_agent.llm_client import LLMError, drain_usage
from socratic_agent.orchestrator import handle_student_message, start_session
from socratic_agent.state import SessionState, Stage
from socratic_agent import progress as prog
from socratic_agent.labels import nice
from socratic_agent import ui
from socratic_agent.topic_bank import TOPICS, get_topic, misconception_label

st.set_page_config(page_title="Socratic-Agent", page_icon="🤔", layout="centered")

db.init_db()

# Demo mode (SOCRATIC_AGENT_DEMO=1): agent replies come from the scripted walkthrough
# (evaluation/walkthrough.py) and run through the real orchestrator, with no LLM calls — for
# demonstrations and thesis screenshots. Off by default; the sidebar says when it is on.
DEMO = os.getenv("SOCRATIC_AGENT_DEMO") == "1"
if DEMO:
    from unittest import mock

    from evaluation import walkthrough as _wt
    from socratic_agent import orchestrator as _orch

    if "demo_llm" not in st.session_state:
        st.session_state.demo_llm = _wt.ScriptedLLM()
    mock.patch.object(_orch, "call_json_agent", st.session_state.demo_llm).start()

AGENT_LABELS = {"Facilitator": "Socratic Facilitator", "Diagnostician": "Cognitive Diagnostician",
                "Scaffolder": "Scaffolding Curator", "Orchestrator": "Tutor"}
AGENT_AVATARS = {"Facilitator": "🧭", "Diagnostician": "🔍", "Scaffolder": "🪜", "Orchestrator": "⚙️", None: "🎓"}
OUTCOME_LABELS = {
    "mastered": "✅ applied to a new case (mastery gate passed)",
    "closed_at_cap": "⏸️ parked at the round limit — not mastered",
    "in_progress": "… in progress",
}
MOVEMENT_LABELS = {
    "first_rating": "first rating", "stable": "→ same level", "up": "↑ up one level",
    "jump_up": "⇈ up two or more", "down": "↓ down", "unrated": "not rated",
}
STAGE_LABELS = {
    Stage.WONDER: "🧭 Wondering — forming a hypothesis",
    Stage.ELENCHUS: "🔍 Diagnosing — probing for gaps",
    Stage.ACCEPT_REJECT: "🪜 Scaffolding — building understanding",
    Stage.DONE: "✅ Session complete",
}
DIFFICULTY_BADGE = {"Beginner": "🟢 Beginner", "Intermediate": "🟡 Intermediate"}

ui.style()
ui.nav(signed_in="student_id" in st.session_state)


# --------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------
def _persist_new_turns() -> None:
    """Writes any state.history turns not yet in SQLite, plus one snapshot, to the DB."""
    state: SessionState = st.session_state.tutor_state
    session_id = st.session_state.db_session_id
    persisted = st.session_state.persisted_upto
    for idx in range(persisted, len(state.history)):
        turn = state.history[idx]
        db.log_turn(session_id, idx, turn.role, turn.agent, turn.content)
    if len(state.history) > persisted:
        db.log_snapshot(session_id, len(state.history) - 1, state)
    db.log_llm_calls(session_id, max(len(state.history) - 1, 0), drain_usage())
    st.session_state.persisted_upto = len(state.history)
    if state.stage == Stage.DONE:
        db.end_session(session_id, "completed")


def _student_progress() -> prog.StudentProgress:
    return prog.build_progress(db.student_objective_records(st.session_state.student_id))


def _new_session(topic_id: str, start_index: int = 0, practice: bool = False) -> None:
    """Starts a fresh tutoring session for the already-logged-in student on `topic_id`.

    practice=True starts at `start_index` and covers only that objective (a retry from the
    My Progress page).
    """
    state = SessionState(topic_id=topic_id, objective_index=start_index, practice_single=practice)
    st.session_state.tutor_state = state
    if DEMO:  # the scripted replies only fit the Loops walkthrough from its first objective
        st.session_state.demo_llm.queue = [r for _, _, replies in _wt.SCENARIO for r in replies]
    st.session_state.feedback_log = []  # (after_history_len, kind, text) shown inline in the chat
    st.session_state.session_milestones = []
    st.session_state.db_session_id = db.create_session(st.session_state.student_id, topic_id)
    st.session_state.persisted_upto = 0
    st.session_state.pending_error = None
    try:
        start_session(state)
    except LLMError as exc:
        st.session_state.pending_error = str(exc)
    _persist_new_turns()


def _process_student_text(student_text: str) -> None:
    """One student turn: orchestrator, persistence, then template feedback (no LLM).

    One feedback card per objective that closed this turn, one per newly earned milestone,
    both placed right after the closing objective's wrap-up in the chat.
    """
    state: SessionState = st.session_state.tutor_state
    before = _student_progress()
    closed_before = {id(r) for r in state.objective_records if r.status.value != "in_progress"}
    try:
        handle_student_message(state, student_text)
        st.session_state.pending_error = None
    except LLMError as exc:
        st.session_state.pending_error = str(exc)
    _persist_new_turns()
    after = _student_progress()
    log = st.session_state.setdefault("feedback_log", [])
    position = len(state.history)
    for rec in state.objective_records:
        if rec.status.value != "in_progress" and id(rec) not in closed_before:
            position = rec.closed_at_turn or position
            log.append((position, rec.status.value, prog.objective_feedback(rec.as_dict())))
    earned = prog.new_milestones(before, after)
    if earned:
        names = ", ".join(f"{m.icon} {m.title}" for m in earned)
        log.append((position, "milestone",
                    f"{'New milestone' if len(earned) == 1 else f'{len(earned)} new milestones'}: {names}"))
    for m in earned:
        st.toast(f"{m.icon} Milestone: {m.title}")
    st.session_state.setdefault("session_milestones", []).extend(earned)
    if earned:
        st.session_state.celebrate = True


def _select_topic(topic_id: str) -> None:
    st.session_state.selected_topic_id = topic_id
    _new_session(topic_id)


def _change_topic() -> None:
    for key in ("selected_topic_id", "tutor_state", "db_session_id", "persisted_upto"):
        st.session_state.pop(key, None)


def _logout() -> None:
    for key in (
        "student_id", "student_name", "selected_topic_id",
        "tutor_state", "db_session_id", "persisted_upto",
    ):
        st.session_state.pop(key, None)


# --------------------------------------------------------------------------------
# Auth gate: sign in / sign up
# --------------------------------------------------------------------------------
if "student_id" not in st.session_state:
    st.markdown(
        """<div class="sa-hero"><h1>🤔 Socratic-Agent</h1>
        <p>A tutor for introductory Python that asks instead of tells: you work the answer out,
        it helps you get there.</p>
        <div class="sa-steps">
          <div class="sa-step"><b>1 · Your idea</b><span>Say what you think the code does, and why.</span></div>
          <div class="sa-step"><b>2 · Test it</b><span>The tutor questions your reasoning, one step at a time.</span></div>
          <div class="sa-step"><b>3 · Apply it</b><span>Explain the idea on a new case to master it.</span></div>
        </div></div>""",
        unsafe_allow_html=True,
    )

    tab_signin, tab_signup = st.tabs(["Sign in", "Sign up"])

    with tab_signin:
        with st.form("signin_form"):
            si_id = st.text_input("Student ID")
            si_pwd = st.text_input("Password", type="password")
            si_submitted = st.form_submit_button("Sign in", width="stretch")
        if si_submitted:
            if not si_id.strip() or not si_pwd:
                st.error("Please enter your student ID and password.")
            else:
                try:
                    name = db.verify_student(si_id.strip(), si_pwd)
                    st.session_state.student_id = si_id.strip()
                    st.session_state.student_name = name
                    st.rerun()
                except db.AuthError as exc:
                    st.error(str(exc))

    with tab_signup:
        with st.form("signup_form"):
            su_name = st.text_input("Full name")
            su_id = st.text_input("Student ID")
            su_pwd = st.text_input("Password", type="password")
            su_pwd2 = st.text_input("Confirm password", type="password")
            su_consent = st.checkbox(
                "I agree to take part in this pilot study; my responses will be used, in "
                "anonymized form, for research analysis."
                f" (Consent text {db.CONSENT_VERSION})"
            )
            su_submitted = st.form_submit_button("Create account", width="stretch")
        if su_submitted:
            if not su_name.strip() or not su_id.strip() or not su_pwd:
                st.error("Please fill in your name, student ID, and a password.")
            elif len(su_pwd) < 6:
                st.error("Password must be at least 6 characters.")
            elif su_pwd != su_pwd2:
                st.error("Passwords do not match.")
            elif not su_consent:
                st.error("Consent is required to create an account.")
            else:
                try:
                    db.create_student(su_id.strip(), su_name.strip(), su_pwd)
                    st.session_state.student_id = su_id.strip()
                    st.session_state.student_name = su_name.strip()
                    st.rerun()
                except db.AuthError as exc:
                    st.error(str(exc))

    st.stop()


# A retry chosen on the My Progress page arrives here.
if st.session_state.get("practice_request"):
    req = st.session_state.pop("practice_request")
    st.session_state.selected_topic_id = req["topic_id"]
    _new_session(req["topic_id"], req["objective_index"], practice=req["kind"] == "retry")

# --------------------------------------------------------------------------------
# Topic picker (shown after auth, before any chat)
# --------------------------------------------------------------------------------
if "selected_topic_id" not in st.session_state:
    overall = _student_progress()
    step = prog.next_step(overall)
    st.markdown(
        f"""<div class="sa-hero"><h1>Welcome, {st.session_state.student_name.split()[0]}</h1>
        <p>{overall.mastered_total} of {overall.objective_total} objectives mastered ·
        {len(overall.milestones)} of {len(prog.MILESTONES)} milestones. Suggested next: {step['text']}</p></div>""",
        unsafe_allow_html=True,
    )
    st.markdown("#### Choose a topic")
    cols = st.columns(2)
    for i, topic in enumerate(TOPICS):
        mastered, parked, total = overall.topic_counts(topic)
        with cols[i % 2]:
            with st.container(border=True):
                tags = f'<span class="sa-tag">{topic.difficulty}</span>'
                if step.get("topic_id") == topic.id:
                    tags += '<span class="sa-tag rec">Recommended next</span>'
                st.markdown(f"**{topic.emoji} {topic.name}**<br>{tags}", unsafe_allow_html=True)
                st.caption(topic.description)
                st.progress(mastered / total, text=f"{mastered}/{total} mastered" + (f" · {parked} parked" if parked else ""))
                label = "Continue" if mastered or parked else "Start"
                if st.button(label, key=f"start_{topic.id}", width="stretch",
                             type="primary" if step.get("topic_id") == topic.id else "secondary"):
                    _select_topic(topic.id)
                    st.rerun()
    with st.sidebar:
        if st.button("Log out", width="stretch"):
            _logout()
            st.rerun()
    st.stop()


# --------------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------------
if "tutor_state" not in st.session_state:
    _new_session(st.session_state.selected_topic_id)

state: SessionState = st.session_state.tutor_state
topic = get_topic(state.topic_id)
assert topic is not None

overall = _student_progress()

with st.sidebar:
    st.markdown(f"**👤 {st.session_state.student_name}**")
    st.caption(f"Student ID {st.session_state.student_id}")
    col_a, col_b = st.columns(2)
    if col_a.button("New session", width="stretch", help="Restart this topic from the first objective"):
        _new_session(state.topic_id)
        st.rerun()
    if col_b.button("Change topic", width="stretch"):
        _change_topic()
        st.rerun()
    if st.button("Log out", width="stretch"):
        _logout()
        st.rerun()
    if state.practice_single:
        st.caption("🔁 Practice session: one objective only.")
    if DEMO:
        st.caption("🎬 Demo mode: scripted agent replies, no LLM calls (Loops topic only).")
        if topic.id == "loops" and len(state.history) == 1 and st.button("Play scripted walkthrough", width="stretch"):
            for text, _, _ in _wt.SCENARIO[1:]:
                _process_student_text(text)
            st.rerun()

    st.divider()
    st.markdown("#### 📊 What the tutor sees")
    st.caption("Estimates from your latest answer, not marks.")
    objective = topic.learning_objectives[state.objective_index] if state.stage != Stage.DONE else None
    move = MOVEMENT_LABELS.get(state.solo_movement_last or "", "")
    st.markdown(
        f"**SOLO estimate:** {nice(state.solo_level_estimate)}" + (f"  \n<small>{move}</small>" if move else ""),
        unsafe_allow_html=True,
        help="Estimated by the tutor from your latest answer using the SOLO rubric. It describes that "
             "one answer, not you, and it is not a test score.",
    )
    st.markdown(
        f"**Support level:** {nice(state.scaffold_level_last)}",
        help="Starts with a hint, rises one step at a time when you are stuck, and steps back down "
             "when your answer improves.",
    )
    st.caption(f"Stage: {STAGE_LABELS[state.stage]}")

    st.markdown("**Misconceptions surfaced:**")
    if state.misconceptions_found:
        chips = "".join(
            f'<span class="chip">⚠️ {misconception_label(m)}</span>' for m in state.misconceptions_found
        )
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.caption("None yet.")

    with st.expander("Round limits (why the stage moves on)"):
        st.write(f"Testing rounds this objective: {state.elenchus_rounds} / 3")
        st.write(f"Support rounds this objective: {state.scaffold_rounds} / 3")
        st.write(f"Transfer/generalization check asked: {'✅ yes' if state.transfer_check_asked else '⏳ not yet'}")
        if state.support_ceiling_last:
            st.write(f"Highest support allowed last turn: {nice(state.support_ceiling_last)}")
        if state.gate_rejections:
            st.write(f"Mastery claims refused by the gate: {state.gate_rejections}")
        st.caption(
            "Each agent decides when to move on; these limits make sure the session "
            "keeps moving if it does not. Mastery is only accepted after a transfer "
            "question has been answered with an explanation; an objective that reaches "
            "the limit is recorded as not mastered."
        )

    st.markdown("**🛡️ Answer-leakage guard:**")
    if state.leak_attempts == 0:
        st.caption("No leak attempts caught yet this session.")
    else:
        st.caption(
            f"Caught {state.leak_attempts} draft(s) that would have leaked the answer "
            f"and rewrote them" + (f"; {state.leak_hard_blocks} needed a fallback message." if state.leak_hard_blocks else ".")
        )

ui.progress_header(topic, state, overall, len(prog.MILESTONES))
if st.button("🌟 My progress", help="Your progress across all topics. Your session stays open."):
    st.switch_page("pages/0_My_Progress.py")

feedback_after = {}
for after_len, kind, text in st.session_state.get("feedback_log", []):
    feedback_after.setdefault(after_len, []).append((kind, text))

for idx, turn in enumerate(state.history):
    if turn.role == "student":
        with st.chat_message("user"):
            st.markdown(turn.content)
    else:
        with st.chat_message("assistant", avatar=AGENT_AVATARS.get(turn.agent)):
            st.markdown(turn.content)
            st.caption(AGENT_LABELS.get(turn.agent, turn.agent or ""))
    for kind, text in feedback_after.get(idx + 1, []):
        (st.success if kind == "mastered" else st.info)(text, icon="🎯" if kind == "mastered" else "🌱" if kind == "parked" else "🏅")

if st.session_state.get("pending_error"):
    st.error(f"LLM call failed: {st.session_state.pending_error}")

if state.stage == Stage.DONE:
    with st.container(border=True):
        st.markdown("#### 🌟 Session summary")
        closed = [r for r in state.objective_records if r.status.value != "in_progress"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Mastered", sum(r.status.value == "mastered" for r in closed))
        c2.metric("Parked (not yet)", sum(r.status.value == "closed_at_cap" for r in closed))
        c3.metric("New milestones", len(st.session_state.get("session_milestones", [])))
        for r in closed:
            growth = prog.growth_phrase(r.entry_solo, r.exit_solo)
            line = f"{prog.STATUS_ICON[r.status.value]} **{r.design_id}** — {prog.STATUS_TEXT[r.status.value]}"
            st.markdown(line + (f" · your answers moved {growth} (estimated)" if growth else ""))
        for m in st.session_state.get("session_milestones", []):
            st.markdown(f"{m.icon} **{m.title}** — {m.how_to_earn}")
        step = prog.next_step(_student_progress())
        st.markdown(f"**Next step:** {step['text']}")
        if step["kind"] != "done" and st.button("Do the next step", type="primary"):
            st.session_state.practice_request = step
            st.rerun()
    if state.not_mastered_objectives:
        st.info("Session complete. Some objectives were parked without mastery — try them again in a new session.")
    else:
        st.success("Session complete — great work! Start a new session or change topic from the sidebar.")

student_text = st.chat_input("Type your answer and explain why…", disabled=(state.stage == Stage.DONE))
if student_text:
    _process_student_text(student_text)
    st.rerun()

if st.session_state.pop("celebrate", False):
    st.balloons()
