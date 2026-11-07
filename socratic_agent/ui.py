"""
Shared interface pieces for the Streamlit pages: styling, navigation and the progress header.

Navigation is drawn by hand (Streamlit's automatic page list is switched off in
.streamlit/config.toml) so the pages have readable names — Tutor, My progress, Teacher
dashboard — and every page offers a visible way back to the student's current session.
"""
from __future__ import annotations

import html

import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

CSS = """
<style>
.block-container { padding-top: 2.2rem; }
.sa-hero { padding: 1.4rem 1.5rem; border-radius: 16px; margin-bottom: 1rem;
  background: linear-gradient(120deg, #eef2ff 0%, #fdf2f8 100%); border: 1px solid #e0e7ff; }
.sa-hero h1 { font-size: 1.9rem; margin: 0 0 .3rem 0; }
.sa-hero p { margin: 0; color: #374151; }
.sa-steps { display: flex; gap: .6rem; margin-top: 1rem; flex-wrap: wrap; }
.sa-step { flex: 1 1 150px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: .6rem .8rem; }
.sa-step b { display: block; margin-bottom: .15rem; }
.sa-step span { font-size: .85rem; color: #4b5563; }

/* the progress header stays pinned at the top of the chat while the conversation scrolls */
div[data-testid="stElementContainer"]:has(.sa-header) { position: sticky; top: 3.2rem; z-index: 50; }
.sa-header { border-radius: 16px; padding: 1rem 1.1rem .9rem; margin-bottom: .9rem;
  box-shadow: 0 6px 18px rgba(79,70,229,.12);
  background: linear-gradient(120deg, #eef2ff 0%, #f5f3ff 100%); border: 1px solid #c7d2fe; }
.sa-row { display: flex; justify-content: space-between; align-items: baseline; gap: .8rem; flex-wrap: wrap; }
.sa-title { font-size: 1.25rem; font-weight: 700; color: #1e1b4b; }
.sa-badges span { display: inline-block; margin-left: .35rem; padding: .15rem .55rem; border-radius: 999px;
  background: #fff; border: 1px solid #c7d2fe; font-size: .8rem; color: #3730a3; }
.sa-objective { margin: .35rem 0 .7rem; color: #374151; font-size: .92rem; }
.sa-bar { height: 12px; border-radius: 999px; background: #e0e7ff; overflow: hidden; display: flex; }
.sa-bar div { height: 100%; }
.sa-pills { display: flex; gap: .4rem; margin-top: .55rem; flex-wrap: wrap; }
.sa-pill { padding: .2rem .6rem; border-radius: 999px; font-size: .8rem; border: 1px solid #d1d5db; background: #fff; color: #6b7280; }
.sa-pill.done { background: #dcfce7; border-color: #86efac; color: #166534; }
.sa-pill.parked { background: #fef3c7; border-color: #fcd34d; color: #92400e; }
.sa-pill.now { background: #4f46e5; border-color: #4f46e5; color: #fff; font-weight: 600; }
.sa-stepper { display: flex; gap: .35rem; margin-top: .75rem; }
.sa-stage { flex: 1; text-align: center; padding: .35rem .3rem; border-radius: 10px; font-size: .8rem;
  background: #fff; border: 1px solid #e5e7eb; color: #9ca3af; }
.sa-stage.past { color: #4338ca; border-color: #c7d2fe; }
.sa-stage.now { background: #4f46e5; color: #fff; border-color: #4f46e5; font-weight: 600; }
.sa-hint { margin-top: .55rem; font-size: .85rem; color: #4338ca; }

.sa-card { border: 1px solid #e5e7eb; border-radius: 14px; padding: .9rem 1rem; background: #fff; }
.sa-tag { display: inline-block; padding: .1rem .5rem; border-radius: 999px; font-size: .75rem; margin-right: .3rem;
  border: 1px solid #e5e7eb; color: #4b5563; }
.sa-tag.rec { background: #4f46e5; color: #fff; border-color: #4f46e5; }
.chip { display: inline-block; padding: 2px 10px; margin: 2px 4px 2px 0; border-radius: 999px;
  font-size: 0.78rem; border: 1px solid rgba(128,128,128,0.35); }
div[data-testid="stChatMessage"] { border-radius: 12px; }
</style>
"""

STAGES = [("WONDER", "1 · Your idea"), ("ELENCHUS", "2 · Test it"), ("ACCEPT_REJECT", "3 · Build and apply")]
STAGE_HINT = {
    "WONDER": "Say what you think and why. Being wrong is fine; it gives the tutor something to work with.",
    "ELENCHUS": "The tutor is checking your reasoning with one question or a counterexample at a time.",
    "ACCEPT_REJECT": "Small hints help you connect the pieces; then you will try the idea on a new case.",
    "DONE": "Session complete. See your summary below.",
}


def style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def nav(signed_in: bool) -> None:
    """Sidebar navigation with readable page names."""
    with st.sidebar:
        st.markdown("### 🤔 Socratic-Agent")
        links = [("app.py", "Tutor", "💬")]
        if signed_in:
            links.append(("pages/0_My_Progress.py", "My progress", "🌟"))
        links.append(("pages/1_Teacher_Dashboard.py", "Teacher dashboard", "📈"))
        for page, label, icon in links:
            try:
                st.page_link(page, label=label, icon=icon)
            except StreamlitPageNotFoundError:  # a page opened on its own (tests): no link to draw
                pass
        st.divider()


def progress_header(topic, state, overall, milestones_total: int) -> None:
    """The prominent card at the top of the chat: where the student is and how far they have come."""
    stage = state.stage.value
    records = {r.objective_id: r.status.value for r in state.objective_records}
    objectives = topic.learning_objectives
    total = len(objectives)
    current = objectives[state.objective_index] if stage != "DONE" and state.objective_index < total else None
    pills, segments = [], []
    for i, obj in enumerate(objectives):
        status = records.get(obj.id)
        if status == "mastered":
            cls, label, color = "done", f"✓ {obj.design_id}", "#22c55e"
        elif status == "closed_at_cap":
            cls, label, color = "parked", f"⏸ {obj.design_id}", "#f59e0b"
        elif current is not None and obj.id == current.id:
            cls, label, color = "now", f"▶ {obj.design_id}", "#818cf8"
        else:
            cls, label, color = "", obj.design_id, "#e0e7ff"
        pills.append(f'<span class="sa-pill {cls}">{label}</span>')
        segments.append(f'<div style="width:{100 / total:.2f}%;background:{color};'
                        f'border-right:2px solid #fff"></div>')
    done = sum(1 for o in objectives if records.get(o.id) in ("mastered", "closed_at_cap"))
    where = (f"Objective {state.objective_index + 1} of {total} · <b>{current.design_id}</b> — "
             f"{html.escape(current.statement)}" if current else f"All {total} objectives covered")
    order = [s for s, _ in STAGES]
    stepper = []
    for key, label in STAGES:
        if stage == "DONE" or (stage in order and order.index(key) < order.index(stage)):
            cls = "past"
        elif key == stage:
            cls = "now"
        else:
            cls = ""
        stepper.append(f'<div class="sa-stage {cls}">{label}</div>')
    st.markdown(
        f'''<div class="sa-header">
          <div class="sa-row"><div class="sa-title">{topic.emoji} {html.escape(topic.name)}</div>
            <div class="sa-badges"><span>{done}/{total} done this session</span>
            <span>🏅 {len(overall.milestones)}/{milestones_total} milestones</span></div></div>
          <div class="sa-objective">{where}</div>
          <div class="sa-bar">{"".join(segments)}</div>
          <div class="sa-pills">{"".join(pills)}</div>
          <div class="sa-stepper">{"".join(stepper)}</div>
          <div class="sa-hint">{STAGE_HINT[stage]}</div>
        </div>''',
        unsafe_allow_html=True,
    )
