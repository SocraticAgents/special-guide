"""
One-off: makes H1-H5 explicit and testable in the thesis draft.

Reads  ~/Downloads/Socratic_Agent_Revised_Draft_2026-11-05.docx (left unchanged)
Writes ../writting/Socratic_Agent_Revised_Draft_2026-11-07.docx with:
  - 1.5.1 Research Hypotheses (after the RQs): each hypothesis linked to RQ2/RQ3
  - 2.5.5: the five statements sharpened to match 1.5.1, plus forward references
  - 3.3.4 Testing the Research Hypotheses + Table 3.3 (evidence, measure, criterion, Chapter 5 section)
  - design matrix: DD6 maps usability to RQ3 (descriptive), not to H5
Also updates the DD6/DD7 hypothesis cells in ../writting/Chapter 4.docx.

Criteria reuse the targets already set for V1 (weighted kappa >= 0.6, misconception support >= 80%,
no answer disclosure, >= 90% sessions completed); the rubric threshold (1.5 of 2) is new.
"""
from __future__ import annotations

import copy
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph

SRC = Path.home() / "Downloads" / "Socratic_Agent_Revised_Draft_2026-11-05.docx"
THESIS = Path(__file__).resolve().parents[2]
OUT = THESIS / "writting" / "Socratic_Agent_Revised_Draft_2026-11-07.docx"
PART_A = THESIS / "writting" / "Chapter 4.docx"

HYPOTHESES = [
    ("H1", "Cognitive Diagnosis", "RQ2, RQ3",
     "The Cognitive Diagnostician's estimates of the SOLO level of students' responses will agree with "
     "rubric-based human labels at an acceptable level, and the misconceptions it records will be "
     "supported by the students' own words."),
    ("H2", "Socratic Questioning", "RQ2, RQ3",
     "The Socratic Facilitator, supported by the answer-leakage guard, will guide students through "
     "structured questioning without disclosing the target answer."),
    ("H3", "Adaptive Scaffolding", "RQ2, RQ3",
     "The Scaffolding Curator will provide support that matches students' demonstrated understanding, "
     "increasing it when they are stuck and reducing it when their reasoning improves."),
    ("H4", "Multi-Agent Coordination", "RQ2",
     "The orchestrator will coordinate cognitive diagnosis, Socratic questioning and adaptive "
     "scaffolding as designed within a learning session."),
    ("H5", "Learning Improvement", "RQ3",
     "Students' scores on a reasoning-based post-test will be higher than their pre-test scores after "
     "one learning session with the system."),
]

TABLE_3_3 = [
    ["Hypothesis", "RQ", "Evidence", "Measure", "Supported if", "Tested in"],
    ["H1 Cognitive diagnosis", "RQ2, RQ3",
     "Student responses rated by the Diagnostician (scenario set and pilot transcripts) and labelled by a "
     "human rater with the SOLO descriptors; recorded misconceptions and their quoted evidence",
     "Accuracy, confusion matrix, quadratic-weighted kappa; share of recorded misconceptions supported by "
     "the student's own words",
     "Weighted kappa >= 0.60 and >= 80% of recorded misconceptions supported", "5.3.2"],
    ["H2 Socratic questioning", "RQ2, RQ3",
     "Scripted Facilitator scenarios; adversarial leakage scenarios; pilot sessions",
     "Facilitator rubric (four dimensions, 0-2); leakage rate (leaking cases / evaluated cases)",
     "Mean >= 1.5 of 2 on each dimension, and no case or session in which the answer reaches the student",
     "5.3.1, 5.4.2"],
    ["H3 Adaptive scaffolding", "RQ2, RQ3",
     "Scaffolding scenarios needing minimal, moderate and explicit help; support sequence in the logs",
     "Scaffolding rubric (four dimensions, 0-2); support-level and fading violations",
     "Mean >= 1.5 of 2 on each dimension; violations reported", "5.3.3"],
    ["H4 Multi-agent coordination", "RQ2",
     "Orchestration test cases; pilot session logs",
     "Test-case pass rate; sessions completed without a blocking error",
     "100% of test cases pass and >= 90% of sessions complete", "5.4.1"],
    ["H5 Learning improvement", "RQ3",
     "Pre-test and post-test scores on parallel reasoning items (0-2 rubric)",
     "Score change, normalised gain, one-sided Wilcoxon signed-rank test",
     "Median score change > 0 with p < 0.05", "5.5"],
]


def set_text(p: Paragraph, text: str, bold_lead: str | None = None) -> None:
    runs = p.runs
    if bold_lead is not None:
        runs[0].text, runs[0].bold = bold_lead, True
        if len(runs) < 2:
            new = copy.deepcopy(runs[0]._r)
            runs[0]._r.addnext(new)
            runs = p.runs
        runs[1].text, runs[1].bold = text, False
        rest = runs[2:]
    else:
        runs[0].text = text
        rest = runs[1:]
    for r in rest:
        r.text = ""


def clone_after(anchor, template: Paragraph, text: str, bold_lead: str | None = None) -> Paragraph:
    """Insert a copy of `template` (formatting, numbering) after `anchor` (a paragraph or table)."""
    el = copy.deepcopy(template._p)
    (anchor._p if isinstance(anchor, Paragraph) else anchor._tbl).addnext(el)
    p = Paragraph(el, template._parent)
    set_text(p, text, bold_lead)
    return p


def exact(d, text: str) -> Paragraph:
    hits = [p for p in d.paragraphs if p.text.strip() == text]
    assert len(hits) == 1, (text, len(hits))
    return hits[0]


def find(d, start: str) -> Paragraph:
    hits = [p for p in d.paragraphs if p.text.strip().startswith(start)]
    assert len(hits) == 1, (start, len(hits))
    return hits[0]


def main() -> None:
    d = docx.Document(SRC)
    assert not any(p.text.startswith("1.5.1 Research Hypotheses") for p in d.paragraphs), "already applied"
    dd_matrix = next(t for t in d.tables if t.rows[0].cells[0].text.strip() == "ID" and len(t.columns) == 6
                     and any(r.cells[0].text.strip() == "DD1" for r in t.rows))

    # The new Table 3.3 goes before the timeline table: shift Table 3.4 -> 3.5, then 3.3 -> 3.4.
    renumbered = 0
    for old, new in (("Table 3.4", "Table 3.5"), ("Table 3.3", "Table 3.4")):
        for p in d.paragraphs:
            if old in p.text:
                runs = [r for r in p.runs if old in r.text]
                assert runs, f"'{old}' split across runs in: {p.text[:60]}"
                for r in runs:
                    r.text = r.text.replace(old, new)
                    renumbered += 1
    assert renumbered == 4, renumbered

    # ---- Chapter 1: 1.5.1 after the research questions ---------------------------------
    rq3 = find(d, "What preliminary evidence does the Socratic-Agent prototype")
    rq_heading = find(d, "1.5 Research Questions")
    intro_style = find(d, "To achieve the above research objectives")
    h = clone_after(rq3, rq_heading, "1.5.1 Research Hypotheses")
    h.style = d.styles["Heading 2"]
    last = clone_after(h, intro_style,
                       "RQ1 is answered through the literature synthesis in Chapter 2 and has no hypothesis. "
                       "RQ2 and RQ3 are examined through five hypotheses. They follow from the research gaps "
                       "identified in Section 2.5, are tested in Chapter 5, and Section 3.3.4 defines the "
                       "evidence and criterion for each.")
    for hid, name, rqs, statement in HYPOTHESES:
        last = clone_after(last, rq3, f" ({rqs}) {statement}", bold_lead=f"{hid} – {name}")
        pPr = last._p.pPr
        num = pPr.find(qn("w:numPr")) if pPr is not None else None
        if num is not None:  # copied from the numbered RQ list: drop numbering, keep the indent
            pPr.remove(num)
        last.paragraph_format.left_indent = Inches(0.5)
        last.paragraph_format.first_line_indent = Inches(0)
    clone_after(last, intro_style,
                "Because the user study uses a single group without a control condition, support for H5 would "
                "show a change within the participants, not that the system alone caused it. Usability and "
                "perceived interaction quality are reported descriptively under RQ3 rather than tested as "
                "hypotheses.")

    # ---- Chapter 2: sharpen 2.5.5 --------------------------------------------------------
    for hid, name, _, statement in HYPOTHESES:
        heading = exact(d, f"{hid} – {name}")
        body = Paragraph(heading._p.getnext(), heading._parent)
        set_text(body, statement)
    h5 = exact(d, "H5 – Learning Improvement")
    clone_after(Paragraph(h5._p.getnext(), h5._parent), h5,
                "Section 1.5.1 links each hypothesis to the research questions, and Section 3.3.4 defines how "
                "each one is tested.")
    p_last = [p for p in d.paragraphs if p.text.startswith("Section 1.5.1 links each hypothesis")][0]
    for r in p_last.runs:
        r.bold = False

    # ---- Chapter 3: 3.3.4 + Table 3.3, before 3.4 ----------------------------------------
    h333 = find(d, "3.3.3 Data Analysis Procedures")
    h34 = find(d, "3.4 Research Timeline")
    prev = Paragraph(h34._p.getprevious(), h34._parent)
    body_tpl = Paragraph(h333._p.getnext(), h333._parent)
    caption_tpl = exact(d, "Table 3.2 Data Analysis Techniques")
    h334 = clone_after(prev, h333, "3.3.4 Testing the Research Hypotheses")
    intro = clone_after(h334, body_tpl,
                        "Table 3.3 sets out, for each hypothesis in Section 1.5.1, the evidence used, how it is "
                        "measured, the criterion for treating it as supported, and the section of Chapter 5 that "
                        "reports it. The criteria were fixed before data collection so that results are judged "
                        "against them rather than interpreted afterwards.")
    tbl = copy.deepcopy(dd_matrix._tbl)  # design-matrix table: same borders and fonts, 6 columns
    intro._p.addnext(tbl)
    table = docx.table.Table(tbl, intro._parent)
    while len(table.rows) > len(TABLE_3_3):
        tbl.remove(table.rows[-1]._tr)
    for row, values in zip(table.rows, TABLE_3_3):
        for cell, value in zip(row.cells, values):
            paras = cell.paragraphs
            set_text(paras[0], value.replace(">=", "≥"))
            for extra in paras[1:]:
                extra._p.getparent().remove(extra._p)
    widths = [1.05, 0.65, 1.55, 1.45, 1.35, 0.6]
    tblPr = table._tbl.tblPr
    layout = tblPr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tblPr.append(layout)
    layout.set(qn("w:type"), "fixed")
    for gc, w in zip(table._tbl.tblGrid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w * 1440)))
    for row in table.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = Inches(w)
    for cell in table.rows[0].cells:
        for r in cell.paragraphs[0].runs:
            r.bold = True
    cap = clone_after(table, caption_tpl, "Table 3.3 Operationalisation of the research hypotheses")
    clone_after(cap, body_tpl,
                "Each hypothesis is reported as supported, partly supported (some criteria met) or not supported. "
                "H1 to H3 rely on LLM outputs, so failures are analysed case by case as well as counted. With "
                "10–20 participants the Wilcoxon test has little power, so H5 is read as the direction of change "
                "within this group (Section 3.3.3). Usability, interaction quality and the progress features are "
                "summarised descriptively under RQ3.")

    # ---- design matrix in the draft: DD6 ------------------------------------------------
    for row in dd_matrix.rows:
        if row.cells[0].text.strip() == "DD6":
            set_text(row.cells[2].paragraphs[0], "H5; usability descriptive (RQ3)")
    d.save(OUT)
    print("wrote", OUT)

    # ---- Part A (writting/Chapter 4.docx): DD6 and DD7 -------------------------------------
    a = docx.Document(PART_A)
    for row in a.tables[1].rows:
        dd = row.cells[0].text.strip()
        if dd == "DD6":
            set_text(row.cells[2].paragraphs[0], "H5; usability descriptive (RQ3)")
        if dd == "DD7":
            set_text(row.cells[2].paragraphs[0], "RQ3 (descriptive)")
    a.save(PART_A)
    print("updated", PART_A)


if __name__ == "__main__":
    main()
