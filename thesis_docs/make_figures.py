"""Figures for Chapter 4 (Part A Figure 4.2 redraw + Part B figures), generated from the code.

    python3 thesis_docs/make_figures.py          (from code/; needs matplotlib)
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

from evaluation import walkthrough  # noqa: E402
from socratic_agent.learner_model import SOLO_ORDER  # noqa: E402

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10})
INK, MUTED, GRID = "#1f2937", "#6b7280", "#e5e7eb"
BLUE, GREEN, AMBER, RED, PURPLE = "#2563eb", "#15803d", "#b45309", "#b91c1c", "#7c3aed"


# ---------------------------------------------------------------- Figure: use-case diagram
def use_case_diagram():
    fig, ax = plt.subplots(figsize=(9.5, 7.8))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    ax.add_patch(FancyBboxPatch((18, 2), 64, 95, boxstyle="round,pad=0.4", fc="#f8fafc", ec=MUTED, lw=1, zorder=-2))
    ax.text(50, 95, "Socratic-Agent (Prototype V1)", ha="center", fontsize=11, weight="bold", color=INK)

    def actor(x, y, name):
        ax.add_patch(plt.Circle((x, y + 4), 1.6, fc="white", ec=INK, lw=1.2))
        ax.plot([x, x], [y + 2.4, y - 2], color=INK, lw=1.2)
        ax.plot([x - 2.5, x + 2.5], [y + 1, y + 1], color=INK, lw=1.2)
        ax.plot([x, x - 2], [y - 2, y - 5.5], color=INK, lw=1.2)
        ax.plot([x, x + 2], [y - 2, y - 5.5], color=INK, lw=1.2)
        ax.text(x, y - 8.5, name, ha="center", fontsize=10, weight="bold")

    def uc(x, y, label, color=BLUE, w=27):
        ax.add_patch(Ellipse((x, y), w, 4.7, fc="white", ec=color, lw=1.1))
        ax.text(x, y, label, ha="center", va="center", fontsize=7.6, color=INK)
        return (x, y)

    labels = [
        "UC-01/02 Register (consent) / sign in", "UC-03 Select topic, start session",
        "UC-04 State a hypothesis", "UC-05/06 Ask for the answer", "UC-07 Say \"I don't know\"",
        "UC-08 Reveal a misconception", "UC-09/10 Receive graded support", "UC-11 Answer a transfer question",
        "UC-12 Give a bare answer", "UC-13 Objective parked at cap", "UC-14 Drift off topic",
        "UC-15/17 Finish the session", "UC-16 New session / change topic",
        "UC-23 View My Progress", "UC-24/25 Earn milestones, get feedback", "UC-26 Retry a parked objective",
    ]
    student = [(lab, 89 - i * 5.25) for i, lab in enumerate(labels)]
    actor(8, 50, "Student")
    for label, y in student:
        x = 37
        uc(x, y, label, PURPLE if label.startswith(("UC-23", "UC-24", "UC-26")) else BLUE)
        ax.plot([10.5, x - 13.5], [50, y], color="#9ca3af", lw=0.7, zorder=-1)
    teacher = [("UC-18 Open dashboard (passcode)", 80), ("UC-19 Review a session", 70),
               ("UC-20 Review cohort outcomes", 60)]
    actor(92, 70, "Teacher")
    for label, y in teacher:
        uc(66, y, label, GREEN)
        ax.plot([89.5, 79.5], [70, y], color="#9ca3af", lw=0.7, zorder=-1)
    actor(92, 30, "Researcher")
    uc(66, 30, "UC-21 Export anonymised data", AMBER)
    uc(66, 20, "UC-22 Label SOLO estimates", AMBER)
    for y in (30, 20):
        ax.plot([89.5, 79.5], [30, y], color="#9ca3af", lw=0.7, zorder=-1)
    ax.text(66, 43, "Started by the orchestrator\n(no actor): stage change,\nleak retry, gate refusal,\nsupport limits, round limit",
            ha="center", va="center", fontsize=7.5, color=MUTED, style="italic")
    fig.savefig(OUT / "fig_use_cases.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 4.2 (Part A): state machine, redrawn
def state_machine():
    plt.rcParams["font.family"] = "Arial"
    fig, ax = plt.subplots(figsize=(11, 6.6))
    ax.set_xlim(0, 110); ax.set_ylim(-4, 64); ax.axis("off")
    DARK = "#334155"

    def node(x, y, w, h, title, sub="", fc="white", ec=DARK, fs=10):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8", fc=fc, ec=ec, lw=1.2))
        if sub:
            ax.text(x + w / 2, y + h - 2.3, title, ha="center", va="center", fontsize=fs, weight="bold", color=INK)
            ax.text(x + w / 2, y + (h - 4.2) / 2, sub, ha="center", va="center", fontsize=8.3, color=INK, linespacing=1.25)
        else:
            ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=fs, weight="bold", color=INK)

    def path(points, color=DARK, head=True):
        xs, ys = zip(*points)
        ax.plot(xs[:-1] + (xs[-1],), ys, color=color, lw=1.2, solid_capstyle="round")
        if head:
            ax.annotate("", points[-1], points[-2], arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2, mutation_scale=11))

    def label(x, y, text, color=DARK):
        ax.text(x, y, text, ha="center", va="center", fontsize=8, color=color, bbox=dict(fc="white", ec="none", pad=0.5))

    ax.add_patch(plt.Circle((2.5, 50), 1.5, color="#1e293b"))
    node(8, 45, 20, 10, "WONDER", "Socratic Facilitator", "#b3d4ef")
    node(42, 45, 20, 10, "ELENCHUS", "Cognitive Diagnostician", "#fde59a")
    node(83, 45, 22, 10, "ACCEPT / REJECT", "Scaffolding Curator", "#a7dfc3")
    path([(4, 50), (8, 50)])
    path([(28, 50), (42, 50)]); label(35, 52.2, "Hypothesis captured")
    path([(62, 50), (83, 50)]); label(72.5, 52.4, "Gap surfaced OR 3 rounds"); label(72.5, 47.8, "(reason recorded)")
    for x0, col, lab in ((8, "#2563a8", "Continue elicitation"), (42, "#a17a00", "Probe again (max 3 rounds)"),
                         (83, "#1f8a4c", "More support within the limits (max 3)")):
        path([(x0 + 5, 55), (x0 + 5, 59), (x0 + 15, 59), (x0 + 15, 55)], color=col)
        ax.text(x0 + 10, 61, lab, ha="center", va="center", fontsize=8, color=col)

    node(60, 22, 20, 12, "Mastered", "transfer asked earlier +\njustified transfer answer\n(relational or higher)",
         "#d1fae5", ec="#15803d", fs=9.5)
    node(88, 22, 21, 12, "Closed at round limit", "3 support rounds without\npassing the gate:\nparked, not mastered",
         "#fee2e2", ec="#b91c1c", fs=9.5)
    path([(89, 45), (89, 40), (70, 40), (70, 34)], color="#15803d"); label(79, 41.6, "Mastery gate passed", "#15803d")
    path([(99, 45), (99, 34)], color="#b91c1c"); label(104.5, 39.5, "Round limit\nreached", "#b91c1c")

    node(40, 3, 24, 10, "Objectives remaining?", fc="#eef2f6", fs=9.5)
    node(86, 3, 18, 10, "DONE", fc="#d6dbe0", fs=10.5)
    path([(99, 22), (99, 18), (70, 18)], head=False)
    path([(70, 22), (70, 18), (52, 18), (52, 13)])
    label(84, 19.6, "Record outcome; reset objective state")
    path([(64, 8), (86, 8)]); label(75, 10, "No (or practice session)")
    path([(40, 8), (18, 8), (18, 45)], color="#1f8a4c"); label(11, 27, "Yes:\nnext\nobjective", "#1f8a4c")
    ax.text(55, -2.2, "Round limits bound dialogue length. An objective closed at the round limit is recorded as not "
            "mastered. Exactly one agent is selected per student turn.", ha="center", va="center", fontsize=8.2,
            weight="bold", color=INK, bbox=dict(fc="white", ec=DARK, pad=4))
    fig.savefig(OUT / "fig_4_2_state_machine.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    plt.rcParams["font.family"] = "Times New Roman"


# ---------------------------------------------------------------- Figure: SOLO trajectory of walkthrough
def solo_trajectory():
    state, rows = walkthrough.run()
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    colors = {"LO5": BLUE, "LO6": RED, "LO7": GREEN}
    pts = [(r["step"], SOLO_ORDER.index(r["solo_estimate"]), r["lo"], r["rated_by"], r["stage_after"])
           for r in rows if r["solo_estimate"]]
    for lo in ("LO5", "LO6", "LO7"):
        xs = [p[0] for p in pts if p[2] == lo]; ys = [p[1] for p in pts if p[2] == lo]
        ax.plot(xs, ys, "-", color=colors[lo], lw=1.6, zorder=2)
        for x, y, _, agent, _ in [p for p in pts if p[2] == lo]:
            ax.scatter(x, y, s=46, marker="o" if agent == "Diagnostician" else "s",
                       color=colors[lo], zorder=3, edgecolor="white", lw=0.8)
    outcome = {r.design_id: r.status.value for r in state.objective_records}
    for lo, (x0, x1) in {"LO5": (0, 7), "LO6": (8, 14), "LO7": (15, 20)}.items():
        ax.axvspan(x0 - 0.45, x1 + 0.45, color=colors[lo], alpha=0.05)
        label = "MASTERED" if outcome[lo] == "mastered" else "CLOSED AT ROUND LIMIT\n(not mastered)"
        ax.text((x0 + x1) / 2, 4.55, f"{lo}: {label}", ha="center", va="top", fontsize=8.5,
                color=colors[lo], weight="bold")
    notes = {7: ("transfer answer justified:\ngate passes", (8.0, 3.35)),
             14: ("estimate rises, support fades;\nround limit reached: parked", (9.6, 2.45)),
             19: ("bare answer:\ngate refuses", (17.2, 0.05)),
             5: ("regresses:\nfirst hint", (3.4, 0.15)),
             11: ("Elenchus\nround cap", (10.3, 0.75))}
    for step, (text, xy) in notes.items():
        y = next(p[1] for p in pts if p[0] == step)
        ax.annotate(text, (step, y), xytext=xy, fontsize=7.4, color=INK,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7))
    ax.set_yticks(range(5)); ax.set_yticklabels([s.replace("_", " ") for s in SOLO_ORDER])
    ax.set_ylim(-0.9, 4.7); ax.set_xlim(-0.6, 20.6)
    ax.set_xticks(range(0, 21)); ax.set_xlabel("Walkthrough step (one student message per step)")
    ax.grid(axis="y", color=GRID, lw=0.7); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.scatter([], [], marker="o", color=MUTED, label="rated by Diagnostician (Elenchus)")
    ax.scatter([], [], marker="s", color=MUTED, label="rated by Scaffolding Curator")
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    fig.savefig(OUT / "fig_solo_trajectory.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- Figure: estimate -> movement -> response
def movement_flow():
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")

    def box(x, y, w, h, title, body, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5", fc="white", ec=color, lw=1.3))
        ax.text(x + w / 2, y + h - 2.2, title, ha="center", va="top", fontsize=9, weight="bold", color=color)
        ax.text(x + w / 2, y + h - 6.6, body, ha="center", va="top", fontsize=7.8, color=INK, linespacing=1.35)

    def arrow(x0, y0, x1, y1, text=""):
        ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.1))
        if text:
            ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 1.2, text, ha="center", fontsize=7.4, color=MUTED)

    box(1, 30, 20, 26, "1  Student response", "free-text answer\nto the current\nagent's question", INK)
    box(26, 30, 22, 26, "2  LLM SOLO estimate", "Diagnostician (Elenchus)\nor Curator (support)\nrates THIS response\nwith the SOLO rubric;\nrecorded as an estimate", BLUE)
    box(53, 30, 21, 26, "3  Movement (rule)", "compare with previous\nestimate, same objective:\nfirst / up one / up two+ /\nno change / down / not rated", INK)
    box(79, 36, 20, 20, "4a  Support limit", "answer improved: step\ndown one level\nelse: rise at most one\n(first move = hint)", AMBER)
    box(79, 4, 20, 26, "4b  Mastery gate", "transfer asked on an\nearlier turn AND\ntransfer answer rated\nrelational or higher\n-> mastered", GREEN)
    box(40, 2, 30, 20, "5  Round limit (rule)", "3 support rounds without\npassing the gate\n-> closed at round limit\n(covered, not mastered)", RED)
    arrow(21.5, 43, 25.5, 43); arrow(48.5, 43, 52.5, 43)
    arrow(74.5, 46, 78.5, 46, ""); arrow(74.5, 37, 78.5, 22)
    arrow(78.5, 12, 70.5, 12, "not met in 3 rounds")
    ax.text(50, 58.5, "How a SOLO estimate becomes a system decision (all steps after 2 are fixed rules)",
            ha="center", fontsize=10, weight="bold", color=INK)
    fig.savefig(OUT / "fig_movement_flow.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


use_case_diagram()
state_machine()
solo_trajectory()
movement_flow()
print("figures written to", OUT)
