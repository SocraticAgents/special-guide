"""
One-off: applies the agreed V1 corrections to Part A (writting/Chapter 4.docx).

Every change is listed in CHANGES below so the edit is auditable. Text is replaced inside
the existing runs, so fonts and styles are kept. Run once from code/:
    python3 thesis_docs/apply_part_a_corrections.py
It refuses to run twice (it checks for text that only exists before the corrections).
"""
from __future__ import annotations

import copy
from pathlib import Path

import docx
from PIL import Image

HERE = Path(__file__).parent
DOC = HERE.parents[1] / "writting" / "Chapter 4.docx"
FIG_4_2 = HERE / "figures" / "fig_4_2_state_machine.png"

d = docx.Document(DOC)
P = d.paragraphs
CHANGES: list[str] = []


def find(start: str):
    hits = [p for p in d.paragraphs if p.text.strip().startswith(start)]
    assert len(hits) == 1, f"expected one paragraph starting {start!r}, found {len(hits)}"
    return hits[0]


def set_text(p, text: str, lead: str | None = None) -> None:
    """Replace a paragraph's text, keeping the formatting of its runs (bold lead if 2 runs)."""
    runs = p.runs
    if lead is not None and len(runs) >= 2:
        runs[0].text, runs[1].text = lead, text
        rest = runs[2:]
    else:
        runs[0].text = text
        rest = runs[1:]
    for r in rest:
        r.text = ""


def insert_after(p, text: str, lead: str | None = None):
    new = copy.deepcopy(p._p)
    p._p.addnext(new)
    para = docx.text.paragraph.Paragraph(new, p._parent)
    set_text(para, text, lead)
    return para


def replace_in(p, old: str, new: str, why: str) -> None:
    assert old in p.text, old
    set_text(p, p.text.replace(old, new))
    CHANGES.append(why)


assert any("identify their solo level" in p.text for p in P), "Corrections already applied."

# --- headings that were typed as Normal text ---------------------------------------
for start, level in (("4.2.1 Functional Requirements", 4), ("4.2.2 Non-Functional Requirements", 4),
                     ("4.5 Agent Communication", 3), ("4.5.1 Dialogue Stage", 4), ("4.5.2", 4),
                     ("4.6.1 Design decisions Matrix", 4), ("4.7 User Interface Design", 3),
                     ("4.7.3 Interface Design", 4)):
    p = find(start)
    p.style = d.styles[f"Heading {level}"]
CHANGES.append("Headings 4.2.1, 4.2.2, 4.5, 4.5.1, 4.5.2, 4.6.1, 4.7, 4.7.3 set to heading styles")
replace_in(find("4.5.2"), "4.5.2Answer-Leakage", "4.5.2 Answer-Leakage", "Missing space in 4.5.2 heading")
replace_in(find("4.6.1 Design decisions Matrix"), "Design decisions Matrix", "Design Decisions Matrix", "Capitalised 4.6.1 heading")

# --- functional requirements (review notes 1-3, progress feature) ---------------------
set_text(find("The system shall analyze students' responses"),
         "The system shall estimate the SOLO level demonstrated in each student response (an LLM "
         "estimate produced by the agents, stored as such and compared with human labels).")
set_text(find("The system shall determine which learning objectives"),
         "The system shall record, for each learning objective, whether it was mastered (the transfer "
         "check was passed) or closed at the round limit without mastery.")
set_text(find("The system shall provide the appropriate level of support"),
         "The system shall provide support within code-enforced bounds that use the estimated SOLO level: "
         "start with a hint, increase support by at most one level at a time, and reduce it after the "
         "student's answers improve.")
CHANGES.append("FR4, FR6, FR7 reworded (SOLO estimate; mastered vs closed at the limit; bounded support)")
insert_after(find("The system shall save the data of the learning session"),
             "The system shall show each student their own progress across sessions (objectives mastered "
             "or parked, growth in their estimated SOLO level, milestones), give motivating feedback that "
             "never reveals an answer, and allow a parked objective to be retried.")
CHANGES.append("FR13 added: student progress tracking and motivating feedback")

# --- section references --------------------------------------------------------------
replace_in(find("The separation of pedagogical responsibilities"), "Sections 2.2.6 and 2.2.7", "Section 2.2.3",
           "Section 4.3 now cites Section 2.2.3 (2.2.6/2.2.7 do not exist)")

# --- 4.4.2 / 4.4.3 -----------------------------------------------------------------
set_text(find("The orchestrator stores the estimated SOLO level and detects"),
         "The orchestrator stores each estimated SOLO level as an LLM estimate, together with how it moved "
         "from the previous estimate, and records a misconception only when it is supported by the "
         "student's quoted words. When a knowledge gap has been identified, or the maximum number of "
         "diagnostic rounds is reached, the dialogue advances to the ACCEPT_REJECT stage, and the reason "
         "for leaving ELENCHUS is recorded.")
CHANGES.append("4.4.2: SOLO stored as an estimate; misconceptions recorded with evidence; exit reason")
insert_after(find("The prompt instructs the agent to use a transfer question"),
             "The Curator selects the support level, and the orchestrator bounds that choice: the first "
             "move is a hint, each further move is at most one level higher, and support drops one level "
             "on a turn whose SOLO estimate went up. A move outside the bound is regenerated once and then "
             "counted. These rules are informed by the Zone of Proximal Development and by fading; they do "
             "not measure a learner's ZPD.")
CHANGES.append("4.4.3: paragraph on code-bounded support (review note 2)")

# --- Figure 4.2 and workflow ----------------------------------------------------------
fig_par = find("Figure 4.2 illustrates")
set_text(fig_par, fig_par.text.rstrip() + " Each objective ends in one of two recorded outcomes: MASTERED, "
         "when the mastery gate is passed, or CLOSED_AT_CAP, when the scaffolding round limit is reached "
         "first. Only the first counts as mastery.")
CHANGES.append("Figure 4.2 text: two objective outcomes")
shape = d.inline_shapes[1]  # Figure 4.2 (document order: 4.1, 4.2, 4.3)
rid = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
d.part.related_parts[rid]._blob = FIG_4_2.read_bytes()
w, h = Image.open(FIG_4_2).size
shape.height = int(shape.width * h / w)
CHANGES.append("Figure 4.2 redrawn: ELENCHUS exit reasons, MASTERED / CLOSED_AT_CAP outcomes")

set_text(find("Progression may occur when sufficient understanding"),
         "Progression may occur when sufficient understanding is indicated or when the maximum number of "
         "scaffolding rounds has been reached. The first case is recorded as MASTERED and the second as "
         "CLOSED_AT_CAP, so advancing to another objective does not by itself demonstrate mastery of the "
         "previous one.")
set_text(find("When no learning objectives remain, the tutoring workflow"),
         P[[i for i, p in enumerate(P) if p.text.startswith("When no learning objectives remain")][0]].text.rstrip()
         + " Students see a session summary and can follow their progress across sessions on a My Progress "
         "page, from which a parked objective can be retried.")
CHANGES.append("4.6 workflow steps 5 and 6: outcome labels, session summary and My Progress")

# --- Table 4.2 (LO10) and the design decisions matrix ---------------------------------
lo_table, dd_table = d.tables[0], d.tables[1]
lo10 = next(r for r in lo_table.rows if r.cells[0].text.strip() == "LO10")
set_text(lo10.cells[2].paragraphs[0],
         "Predict the value of a caller's variable after it is passed to a function that modifies its "
         "parameter, and explain why the caller's value is unchanged.")
CHANGES.append("Table 4.2 LO10 text corrected (was a copy of LO9)")
for row in dd_table.rows[1:]:
    for cell in row.cells:
        for para in cell.paragraphs:
            if "Section 2.2.5" in para.text:
                set_text(para, para.text.replace("Section 2.2.5", "Section 2.2.2"))
CHANGES.append("DD1/DD2 cite Section 2.2.2 (2.2.5 does not exist)")
new_row = copy.deepcopy(dd_table.rows[-1]._tr)
dd_table.rows[-1]._tr.addnext(new_row)
row = dd_table.rows[-1]
for cell, text in zip(row.cells, [
    "DD7",
    "Formative feedback, learner agency, SOLO growth, conceptual change (Section 2.2.2; Ouyang and Jiao)",
    "H5",
    "Make progress visible and give motivating, process-level feedback without revealing answers or overstating mastery",
    "My Progress page, milestone rules, template feedback (no LLM), retry of parked objectives",
    "Post-session survey items D5-D7 and retries of parked objectives in the logs",
]):
    paras = cell.paragraphs
    set_text(paras[0], text)
    for extra in paras[1:]:
        extra._p.getparent().remove(extra._p)
CHANGES.append("Design decisions matrix: DD7 row added")

# --- 4.7.1 student interface --------------------------------------------------------
set_text(find("Learning Progress Display:"),
         " The interface shows the current learning objective, each objective's outcome in this session "
         "(mastered or parked), and a summary at the end of the session.", lead="Learning Progress Display:")
live = find("Live Diagnostic Information:")
set_text(live, " A diagnostic panel displays the current estimate of the student's understanding, labelled "
         "as an estimate, and the current support level.", lead="Live Diagnostic Information:")
insert_after(live, " A separate page shows the student's progress across all sessions, growth in their "
             "answers, milestones that reward learning behaviour rather than speed, and one suggested next "
             "step, including retrying a parked objective. All feedback here comes from fixed templates, "
             "not the language model.", lead="My Progress and Motivating Feedback:")
CHANGES.append("4.7.1: progress display, diagnostic panel wording, My Progress bullet")

d.save(DOC)
print("Applied to", DOC)
for c in CHANGES:
    print(" -", c)

# Follow-up applied once after the first run: restyled headings got black, bold run formatting
# (and Heading 4 runs inherit size) to match the document's existing headings.
