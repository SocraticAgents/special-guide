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
from socratic_agent.labels import nice
from socratic_agent.topic_bank import TOPICS, get_topic, misconception_label


# Internal objective IDs (VO1, LO1, LI2, ...) -> thesis Table 4.2 IDs (LO1-LO11), used for every display.
DESIGN_ID = {o.id: o.design_id for t in TOPICS for o in t.learning_objectives}


def _lo(objective_id: str | None) -> str:
    return DESIGN_ID.get(objective_id, objective_id or "—")


def _topic_name(topic_id: str) -> str:
    topic = get_topic(topic_id)
    return f"{topic.emoji} {topic.name}" if topic else topic_id

st.set_page_config(page_title="Socratic-Agent — Teacher Dashboard", page_icon="📈", layout="wide")
db.init_db()
from socratic_agent import ui  # noqa: E402
ui.style()
ui.nav(signed_in="student_id" in st.session_state)

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
    st.stop()

st.title("📈 Teacher Dashboard")

with st.expander("⬇️ Download research data (anonymised)"):
    st.caption(
        "CSV files keyed by participant code (P01, P02, …): no names or student IDs, and only "
        "students with recorded consent (Sec 3.6). Transcripts are free text, so read them once "
        "before sharing: students may name themselves. On Streamlit Cloud the database is wiped "
        "on restart or redeploy, so download after every study session."
    )
    if st.button("Prepare export"):
        from evaluation.export_research_data import export_zip_bytes

        st.session_state.export_zip = export_zip_bytes()
        st.session_state.export_name = f"socratic_agent_export_{pd.Timestamp.now():%Y-%m-%d_%H%M}.zip"
    if "export_zip" in st.session_state:
        st.download_button(
            "Download .zip",
            data=st.session_state.export_zip,
            file_name=st.session_state.export_name,
            mime="application/zip",
        )

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

st.subheader("🎯 Objectives and rule enforcement")
st.caption(
    "Objectives mastered through a passed transfer check vs. closed at the round limit (not "
    "mastered), and how often the system refused a rule the model broke."
)
obj = db.objective_stats()
o1, o2, o3, o4, o5 = st.columns(5)
o1.metric("Objectives mastered", obj["mastered"], help="Mastery gate passed: transfer question asked earlier and a justified (relational+) transfer answer.")
o2.metric("Closed at round limit", obj["not_mastered"], help="Reached the support round limit. Counted as covered, never as mastered.")
o3.metric("Mastery claims refused", obj["gate_rejections"])
o4.metric("Support-level skips", obj["support_violations"])
o5.metric("Fade violations", obj["fade_violations"], help="Support rose on a turn whose own SOLO estimate went up.")

outcomes = db.objective_outcomes()
if outcomes:
    st.markdown("**Outcome per learning objective** — SOLO levels are the tutor's estimates")
    odf = pd.DataFrame(outcomes)
    summary = (
        odf.groupby("design_id")["status"].value_counts().unstack(fill_value=0)
        .reindex(columns=["mastered", "closed_at_cap", "in_progress"], fill_value=0)
        .rename_axis("LO")
        .rename(columns=nice)
    )
    summary = summary.reindex(sorted(summary.index, key=lambda x: int(x[2:])))
    st.dataframe(summary, width="stretch")

st.subheader("⏱️ Model usage")
st.caption("Token counts for the per-session cost estimate and response time of each model call.")
usage = db.usage_stats()
if usage["calls"]:
    u1, u2, u3, u4 = st.columns(4)
    u1.metric("Model calls", usage["calls"], help=f"{usage['failed_calls']} failed")
    u2.metric("Input tokens / session", f"{usage['prompt_tokens_per_session']:,.0f}")
    u3.metric("Output tokens / session", f"{usage['completion_tokens_per_session']:,.0f}")
    u4.metric(
        "Median call latency",
        f"{usage['median_call_latency_ms'] / 1000:.1f} s" if usage["median_call_latency_ms"] else "—",
    )
else:
    st.caption("No model calls recorded yet.")

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
        "Participant": s["participant_code"],
        "Student": s["name"] if show_names else "•••• (hidden)",
        "Student ID": s["student_id"],
        "Consent": s["consent_version"] or "⚠️ none recorded",
        "Sessions": s["n_sessions"],
        "Last active": s["last_active"],
    }
    for s in students
]
st.dataframe(pd.DataFrame(student_rows), width="stretch", hide_index=True)

id_options = [s["student_id"] for s in students]
label_lookup = {
    s["student_id"]: (s["name"] if show_names else f"{s['participant_code']} ({s['student_id']})") for s in students
}
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
    st.markdown("**SOLO estimate over the session** (LLM-rated per response, not a classifier)")
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
        not_mastered = json.loads(last_snapshot["not_mastered_json"] or "[]")
        mastered = [o for o in finished if o not in not_mastered]
        st.markdown("**Misconceptions found:** " + (", ".join(misconception_label(m) for m in found) or "none"))
        st.markdown("**Objectives mastered:** " + (", ".join(map(_lo, mastered)) or "none yet"))
        st.markdown("**Closed without mastery (cap):** " + (", ".join(map(_lo, not_mastered)) or "none"))
        st.markdown(f"**Final stage:** {last_snapshot['stage']}")
        records = json.loads(last_snapshot["objective_records_json"] or "[]")
        if records:
            st.markdown("**Objective records** (entry → exit SOLO estimate, how Elenchus ended, support used)")
            st.dataframe(pd.DataFrame([
                {"LO": r["design_id"], "Status": nice(r["status"]), "Entry": nice(r["entry_solo"]), "Exit": nice(r["exit_solo"]),
                 "Elenchus ended by": nice(r["elenchus_exit"]), "Support": " → ".join(map(nice, r["support_sequence"])) or "—",
                 "Transfer asked": "yes" if r["transfer_asked"] else "no"}
                for r in records
            ]), width="stretch", hide_index=True)

    st.markdown("**Support sequence** (starts at a hint and rises one level at a time)")
    support_rows = [
        {"Turn": snap["turn_index"], "LO": _lo(snap["objective_id"]), "Support": nice(snap["scaffold_level_last"]),
         "SOLO": nice(snap["solo_level_estimate"]), "Stage": nice(snap["stage"])}
        for snap in snapshots
        if snap["stage"] == "ACCEPT_REJECT" or snap["scaffold_level_last"]
    ]
    if support_rows:
        st.dataframe(pd.DataFrame(support_rows), width="stretch", hide_index=True)
    else:
        st.caption("No support moves in this session.")

with right:
    st.markdown("**Transcript**")
    for turn in transcript:
        role_label = "🧑 Student" if turn["role"] == "student" else f"🤖 {turn['agent']}"
        st.markdown(f"**{role_label}:** {turn['content']}")
