"""
Socratic-Agent — Streamlit chat interface (Section 3.5 of the proposal).

Flow: sign in / sign up  ->  pick a topic  ->  chat, with a live diagnostic
panel in the sidebar. "Change topic" returns to the topic picker without
signing out; "Log out" clears everything.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from socratic_agent import db
from socratic_agent.llm_client import LLMError
from socratic_agent.orchestrator import handle_student_message, start_session
from socratic_agent.state import SessionState, Stage
from socratic_agent.topic_bank import TOPICS, get_topic, misconception_label

st.set_page_config(page_title="Socratic-Agent", page_icon="🤔", layout="centered")

db.init_db()

AGENT_AVATARS = {"Facilitator": "🧭", "Diagnostician": "🔍", "Scaffolder": "🪜", None: "🎓"}
STAGE_LABELS = {
    Stage.WONDER: "🧭 Wondering — forming a hypothesis",
    Stage.ELENCHUS: "🔍 Diagnosing — probing for gaps",
    Stage.ACCEPT_REJECT: "🪜 Scaffolding — building understanding",
    Stage.DONE: "✅ Session complete",
}
DIFFICULTY_BADGE = {"Beginner": "🟢 Beginner", "Intermediate": "🟡 Intermediate"}

st.markdown(
    """
    <style>
    .chip {
        display: inline-block; padding: 2px 10px; margin: 2px 4px 2px 0;
        border-radius: 999px; font-size: 0.78rem; border: 1px solid rgba(128,128,128,0.35);
    }
    .header-banner {
        padding: 1rem 1.2rem; border-radius: 12px; margin-bottom: 0.8rem;
        background: linear-gradient(90deg, rgba(99,102,241,0.14), rgba(236,72,153,0.11));
        border: 1px solid rgba(128,128,128,0.2);
    }
    .header-banner h2 { margin: 0 0 0.2rem 0; }
    div[data-testid="stChatMessage"] {
        border-radius: 12px; padding: 0.4rem 0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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
    st.session_state.persisted_upto = len(state.history)
    if state.stage == Stage.DONE:
        db.end_session(session_id, "completed")


def _new_session(topic_id: str) -> None:
    """Starts a fresh tutoring session for the already-logged-in student on `topic_id`."""
    state = SessionState(topic_id=topic_id)
    st.session_state.tutor_state = state
    st.session_state.db_session_id = db.create_session(st.session_state.student_id, topic_id)
    st.session_state.persisted_upto = 0
    st.session_state.pending_error = None
    try:
        start_session(state)
    except LLMError as exc:
        st.session_state.pending_error = str(exc)
    _persist_new_turns()


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
        '<div class="header-banner"><h2>🤔 Socratic-Agent</h2>'
        "A guided-questioning tutor across introductory Python concepts — it won't just "
        "give you the answer.</div>",
        unsafe_allow_html=True,
    )

    tab_signin, tab_signup = st.tabs(["Sign in", "Sign up"])

    with tab_signin:
        with st.form("signin_form"):
            si_id = st.text_input("Student ID")
            si_pwd = st.text_input("Password", type="password")
            si_submitted = st.form_submit_button("Sign in", use_container_width=True)
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
            )
            su_submitted = st.form_submit_button("Create account", use_container_width=True)
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


# --------------------------------------------------------------------------------
# Topic picker (shown after auth, before any chat)
# --------------------------------------------------------------------------------
if "selected_topic_id" not in st.session_state:
    st.markdown(
        f'<div class="header-banner"><h2>🤔 Socratic-Agent</h2>'
        f"Welcome, {st.session_state.student_name}! Pick a Python topic to practice through "
        f"guided questioning.</div>",
        unsafe_allow_html=True,
    )
    with st.expander("ℹ️ How this tutor works"):
        st.write(
            "You won't get direct answers. A **Facilitator** asks guiding questions, a "
            "**Diagnostician** probes your reasoning for gaps, and a **Scaffolder** gives just "
            "enough support to help you figure it out yourself — then checks you can apply the "
            "idea to a new case before moving on. Pick any topic below to start."
        )

    cols = st.columns(2)
    for i, topic in enumerate(TOPICS):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"#### {topic.emoji} {topic.name}")
                st.caption(DIFFICULTY_BADGE.get(topic.difficulty, topic.difficulty))
                st.write(topic.description)
                st.caption(f"{len(topic.learning_objectives)} learning objectives")
                if st.button("Start this topic", key=f"start_{topic.id}", use_container_width=True):
                    _select_topic(topic.id)
                    st.rerun()

    st.divider()
    if st.button("Log out"):
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

with st.sidebar:
    st.header("Socratic-Agent")
    st.subheader(f"{topic.emoji} {topic.name}")
    st.caption(DIFFICULTY_BADGE.get(topic.difficulty, topic.difficulty))
    st.write(topic.description)

    st.divider()
    st.subheader(f"👤 {st.session_state.student_name}")
    st.caption(f"ID: {st.session_state.student_id}")

    col_a, col_b = st.columns(2)
    if col_a.button("New session", use_container_width=True):
        _new_session(state.topic_id)
        st.rerun()
    if col_b.button("Change topic", use_container_width=True):
        _change_topic()
        st.rerun()
    if st.button("Log out", use_container_width=True):
        _logout()
        st.rerun()

    st.divider()
    st.subheader("📊 Diagnostic panel")
    n_objectives = len(topic.learning_objectives)
    progress = len(state.finished_objectives) / n_objectives if n_objectives else 0
    st.progress(progress, text=f"{len(state.finished_objectives)}/{n_objectives} objectives complete")

    objective = topic.learning_objectives[state.objective_index] if state.stage != Stage.DONE else None
    st.markdown(f"**Current stage:** {STAGE_LABELS[state.stage]}")
    st.markdown(f"**Objective:** {objective.id + ' — ' + objective.statement if objective else '— none —'}")

    m1, m2 = st.columns(2)
    m1.metric("SOLO level", state.solo_level_estimate or "—")
    m2.metric("Support level", state.scaffold_level_last or "—")

    st.markdown("**Misconceptions surfaced:**")
    if state.misconceptions_found:
        chips = "".join(
            f'<span class="chip">⚠️ {misconception_label(m)}</span>' for m in state.misconceptions_found
        )
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.caption("None yet.")

    with st.expander("Round counters (why the stage advances)"):
        st.write(f"Elenchus rounds this objective: {state.elenchus_rounds} / 3 max")
        st.write(f"Scaffold rounds this objective: {state.scaffold_rounds} / 3 max")
        st.write(f"Transfer/generalization check asked: {'✅ yes' if state.transfer_check_asked else '⏳ not yet'}")
        st.caption(
            "Each agent decides when to move on via its own judgment "
            "(gap_surfaced / understanding_sufficient); these caps force "
            "progression if it never does. Mastery also requires passing a "
            "transfer check, not just self-judgment on the original example."
        )

    st.markdown("**🛡️ Answer-leakage guard:**")
    if state.leak_attempts == 0:
        st.caption("No leak attempts caught yet this session.")
    else:
        st.caption(
            f"Caught {state.leak_attempts} draft(s) that would have leaked the answer "
            f"and rewrote them" + (f"; {state.leak_hard_blocks} needed a fallback message." if state.leak_hard_blocks else ".")
        )

st.markdown(
    f'<div class="header-banner"><h2>{topic.emoji} {topic.name}</h2>'
    f"<span>A guided-questioning tutor — it won't just give you the answer.</span></div>",
    unsafe_allow_html=True,
)

for turn in state.history:
    if turn.role == "student":
        with st.chat_message("user"):
            st.markdown(turn.content)
    else:
        with st.chat_message("assistant", avatar=AGENT_AVATARS.get(turn.agent)):
            st.markdown(turn.content)
            st.caption(turn.agent or "")

if st.session_state.get("pending_error"):
    st.error(f"LLM call failed: {st.session_state.pending_error}")

if state.stage == Stage.DONE:
    st.success("Session complete — great work! Start a new session or change topic from the sidebar.")

student_text = st.chat_input("Your response...", disabled=(state.stage == Stage.DONE))
if student_text:
    try:
        handle_student_message(state, student_text)
        st.session_state.pending_error = None
    except LLMError as exc:
        st.session_state.pending_error = str(exc)
    _persist_new_turns()
    st.rerun()
