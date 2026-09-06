"""
Teacher Dashboard — read-only view over every recorded student/session.

Gated by a shared passcode (TEACHER_PASSCODE env var) rather than real
accounts: this is a pilot-scale (10-20 student) BSc thesis prototype, not a
production multi-tenant system, so a lightweight shared passcode is the
proportionate choice — see README for how to change it.

Student names are hidden by default (toggle "Show names") to keep this
dashboard consistent with the proposal's anonymization commitment (Sec 3.6):
prefer student_id for anything that leaves this screen.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st

from socratic_agent import db
from socratic_agent.topic_bank import get_topic, misconception_label


def _topic_name(topic_id: str) -> str:
    topic = get_topic(topic_id)
    return f"{topic.emoji} {topic.name}" if topic else topic_id

st.set_page_config(page_title="Socratic-Agent — Teacher Dashboard", page_icon="📈", layout="wide")
db.init_db()

SOLO_ORDER = ["prestructural", "unistructural", "multistructural", "relational", "extended_abstract"]
SOLO_RANK = {level: i + 1 for i, level in enumerate(SOLO_ORDER)}

PASSCODE = os.getenv("TEACHER_PASSCODE", "teach123")

if not st.session_state.get("teacher_authed"):
    st.title("📈 Teacher Dashboard")
    st.caption("Enter the instructor passcode to view student diagnostic records.")
    entered = st.text_input("Passcode", type="password")
    if st.button("Enter"):
        if entered == PASSCODE:
            st.session_state.teacher_authed = True
            st.rerun()
        else:
            st.error("Incorrect passcode.")
    if PASSCODE == "teach123":
        st.info("Using the default passcode `teach123` — set TEACHER_PASSCODE in .env for real use.")
    st.stop()

st.title("📈 Teacher Dashboard")
show_names = st.toggle("Show names (otherwise only student ID is shown)", value=False)

# --------------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------------
students = db.list_students()
total_sessions, completed_sessions = db.completion_stats()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Students", len(students))
c2.metric("Sessions", total_sessions)
c3.metric("Completed sessions", completed_sessions)
c4.metric(
    "Completion rate",
    f"{(completed_sessions / total_sessions * 100):.0f}%" if total_sessions else "—",
)

st.subheader("Sessions by topic")
all_sessions = db.list_sessions()
if all_sessions:
    topic_counts: dict[str, int] = {}
    for s in all_sessions:
        topic_counts[_topic_name(s["topic"])] = topic_counts.get(_topic_name(s["topic"]), 0) + 1
    topic_df = pd.DataFrame(
        [{"Topic": k, "Sessions": v} for k, v in topic_counts.items()]
    ).sort_values("Sessions", ascending=False)
    st.bar_chart(topic_df.set_index("Topic"))
else:
    st.caption("No sessions recorded yet.")

st.subheader("Misconceptions surfaced across all students")
freq = db.misconception_frequency()
if freq:
    freq_df = pd.DataFrame(
        [{"Misconception": misconception_label(mid), "Sessions": n} for mid, n in freq.items()]
    ).sort_values("Sessions", ascending=False)
    st.bar_chart(freq_df.set_index("Misconception"))
else:
    st.caption("No sessions recorded yet.")

st.subheader("🛡️ Answer-leakage guard")
st.caption(
    "How often an agent's draft was caught trying to reveal the direct answer and had "
    "to be rewritten — the evaluation metric mirroring Table 2.5.2.1's leak-robustness study."
)
leaks = db.leak_stats()
l1, l2, l3 = st.columns(3)
l1.metric("Draft leaks caught & rewritten", leaks["total_attempts"])
l2.metric("Still leaked after retry (fallback used)", leaks["total_hard_blocks"])
l3.metric(
    "Sessions with ≥1 leak attempt",
    f"{leaks['sessions_with_leak_attempt']} / {leaks['total_sessions']}" if leaks["total_sessions"] else "—",
)

st.divider()

# --------------------------------------------------------------------------------
# Student table + drill-down
# --------------------------------------------------------------------------------
st.subheader("Students")
if not students:
    st.caption("No students have logged in yet.")
    st.stop()

student_rows = [
    {
        "Student": s["name"] if show_names else "•••• (hidden)",
        "Student ID": s["student_id"],
        "Sessions": s["n_sessions"],
        "Last active": s["last_active"],
    }
    for s in students
]
st.dataframe(pd.DataFrame(student_rows), use_container_width=True, hide_index=True)

id_options = [s["student_id"] for s in students]
label_lookup = {s["student_id"]: (s["name"] if show_names else s["student_id"]) for s in students}
selected_id = st.selectbox("Inspect a student", id_options, format_func=lambda sid: label_lookup[sid])

sessions = db.list_sessions(selected_id)
if not sessions:
    st.caption("No sessions for this student.")
    st.stop()

session_options = [s["session_id"] for s in sessions]


def _session_label(sid: str) -> str:
    row = next(s for s in sessions if s["session_id"] == sid)
    return f"{row['started_at']} · {_topic_name(row['topic'])} · {row['status']}"


selected_session = st.selectbox("Session", session_options, format_func=_session_label)

snapshots = db.get_snapshots(selected_session)
transcript = db.get_transcript(selected_session)

left, right = st.columns([1, 1])

with left:
    st.markdown("**SOLO level over the session**")
    solo_rows = [
        {"turn": snap["turn_index"], "SOLO level": SOLO_RANK[snap["solo_level_estimate"]]}
        for snap in snapshots
        if snap["solo_level_estimate"] in SOLO_RANK
    ]
    if solo_rows:
        solo_df = pd.DataFrame(solo_rows).set_index("turn")
        st.line_chart(solo_df)
        st.caption("Y-axis: 1=prestructural … 5=extended abstract")
    else:
        st.caption("No SOLO estimate recorded yet for this session.")

    session_row = next(s for s in sessions if s["session_id"] == selected_session)
    st.markdown(f"**Topic:** {_topic_name(session_row['topic'])}")

    last_snapshot = snapshots[-1] if snapshots else None
    if last_snapshot:
        found = json.loads(last_snapshot["misconceptions_json"])
        finished = json.loads(last_snapshot["finished_objectives_json"])
        st.markdown("**Misconceptions found:** " + (", ".join(misconception_label(m) for m in found) or "none"))
        st.markdown("**Objectives completed:** " + (", ".join(finished) or "none yet"))
        st.markdown(f"**Final stage:** {last_snapshot['stage']}")

with right:
    st.markdown("**Transcript**")
    for turn in transcript:
        role_label = "🧑 Student" if turn["role"] == "student" else f"🤖 {turn['agent']}"
        st.markdown(f"**{role_label}:** {turn['content']}")
