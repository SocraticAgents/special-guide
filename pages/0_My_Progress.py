"""
My Progress — the student's own view of their learning across all sessions (DD7).

Shows, per topic and objective, whether it is mastered (gate passed), parked (closed at the
round limit — "not yet"), or not started; how the student's answers grew (in plain SOLO
wording, labelled as an estimate); milestones that reward learning behaviour rather than
speed; and one suggested next step, including a retry of a parked objective.

Everything is computed by socratic_agent/progress.py from stored records — no LLM call.
"""
from __future__ import annotations

import streamlit as st

from socratic_agent import db
from socratic_agent import progress as prog
from socratic_agent import ui
from socratic_agent.topic_bank import TOPICS

st.set_page_config(page_title="My Progress — Socratic-Agent", page_icon="🌟", layout="centered")
db.init_db()
ui.style()
ui.nav(signed_in="student_id" in st.session_state)

st.markdown(
    """
    <style>
    .ms { border: 1px solid rgba(128,128,128,0.3); border-radius: 12px; padding: 0.6rem 0.7rem;
          margin-bottom: 0.5rem; min-height: 92px; }
    .ms.locked { opacity: 0.45; }
    .ms .t { font-weight: 600; }
    .ms .h { font-size: 0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "student_id" not in st.session_state:
    st.title("🌟 My Progress")
    st.info("Sign in on the main page first to see your progress.")
    st.page_link("app.py", label="Go to sign in", icon="➡️")
    st.stop()

records = db.student_objective_records(st.session_state.student_id)
progress = prog.build_progress(records)

# A session that is still running: offer the way back first, and never replace it without saying so.
active = st.session_state.get("tutor_state")
active_running = active is not None and active.stage.value != "DONE"
if active_running:
    topic_now = next(t for t in TOPICS if t.id == active.topic_id)
    lo_now = topic_now.learning_objectives[active.objective_index].design_id
    if st.button(f"← Back to my session ({topic_now.name} · {lo_now})", type="primary"):
        st.switch_page("app.py")
else:
    if st.button("← Back to the tutor"):
        st.switch_page("app.py")

st.title("🌟 My Progress")
st.caption(f"{st.session_state.student_name} · everything you have worked on, across all sessions")

m1, m2, m3 = st.columns(3)
m1.metric("Objectives mastered", f"{progress.mastered_total} / {progress.objective_total}")
m2.metric("Topics mastered", sum(progress.topic_counts(t)[0] == progress.topic_counts(t)[2] for t in TOPICS))
m3.metric("Milestones", f"{len(progress.milestones)} / {len(prog.MILESTONES)}")
st.progress(progress.mastered_total / progress.objective_total)

# --- next step -----------------------------------------------------------------------
step = prog.next_step(progress)
with st.container(border=True):
    st.markdown("#### 👉 Your next step")
    st.write(step["text"])
    if active_running and step["kind"] != "done":
        st.caption("This starts a new session. Your current session is saved and stays in your history.")
    if step["kind"] != "done":
        label = {"retry": f"Retry {step['design_id']}", "continue": "Continue topic", "start": "Start topic"}[step["kind"]]
        if st.button(label, type="secondary" if active_running else "primary"):
            st.session_state.practice_request = step
            st.switch_page("app.py")

# --- per topic -------------------------------------------------------------------------
st.markdown("### 📚 Topics")
st.caption(
    "✅ mastered = you explained the idea on a new case · ⏸️ parked = not yet, worth another go · "
    "○ not started. \"Your answers\" are the tutor's estimate of how complete your explanations were."
)
for topic in TOPICS:
    mastered, parked, total = progress.topic_counts(topic)
    with st.expander(f"{topic.emoji} {topic.name} — {mastered}/{total} mastered" + (f", {parked} parked" if parked else ""),
                     expanded=bool(mastered or parked)):
        st.progress(mastered / total)
        for idx, obj in enumerate(topic.learning_objectives):
            row = progress.objectives[obj.design_id]
            left, right = st.columns([5, 2])
            with left:
                st.markdown(f"{prog.STATUS_ICON[row.status]} **{obj.design_id}** — {obj.statement}")
                details = [prog.STATUS_TEXT[row.status]]
                if row.best_solo:
                    details.append(f"best answer so far: {prog.SOLO_PLAIN[row.best_solo]}")
                growth = prog.growth_phrase(row.first_entry_solo, row.best_solo)
                if growth:
                    details.append(f"grew {growth}")
                if row.attempts > 1:
                    details.append(f"{row.attempts} attempts")
                st.caption(" · ".join(details))
            with right:
                if row.status == "closed_at_cap":
                    if st.button("Retry", key=f"retry_{obj.design_id}", width="stretch"):
                        st.session_state.practice_request = {"kind": "retry", "topic_id": topic.id,
                                                             "objective_index": idx, "design_id": obj.design_id}
                        st.switch_page("app.py")

# --- milestones ------------------------------------------------------------------------
st.markdown("### 🏅 Milestones")
st.caption("Milestones reward how you learn — explaining, changing your mind, coming back — never speed.")
cols = st.columns(3)
for i, m in enumerate(prog.MILESTONES):
    earned = m.id in progress.milestones
    with cols[i % 3]:
        st.markdown(
            f'<div class="ms{"" if earned else " locked"}"><div class="t">{m.icon} {m.title}</div>'
            f'<div class="h">{"Earned" if earned else "How to earn: " + m.how_to_earn}</div></div>',
            unsafe_allow_html=True,
        )

st.divider()
if st.button("← Back to my session" if active_running else "← Back to the tutor", key="back_bottom"):
    st.switch_page("app.py")
