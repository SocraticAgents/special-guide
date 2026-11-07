"""
Builds the complete Chapter 4 ("System Design and Initial Results") as one Word document.

Sections 4.1-4.7 come from writting/Chapter 4.docx (the design, edited by hand); Sections 4.8
onward are generated here from the live code, the walkthrough run and the test suites. The whole
chapter is then formatted to the Research Office writing guidelines (A4, margins 25/20 mm,
Times New Roman 12, 1.5 spacing, justified blocked paragraphs, bold 14 pt major headings, bold
centred legends, tables at 10 pt, header with names, degree, year and page number top right).

    python3 thesis_docs/make_figures.py && python3 thesis_docs/build_chapter4.py     (from code/)
Writes ../writting/Chapter 4 - System Design and Initial Results.docx (refuses if any test fails).
"""
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
FIG = Path(__file__).parent / "figures"
PART_A = CODE.parent / "writting" / "Chapter 4.docx"
OUT = CODE.parent / "writting" / "Chapter 4 - System Design and Initial Results.docx"
HEADER_TEXT = "Sarah Abdalla Bakhit, Ryan Hasabelrasol, Afraa Abdalmonem | BSc in Information Technology | 2026 | "

from evaluation import walkthrough  # noqa: E402
from socratic_agent.design_matrix import DESIGN_MATRIX  # noqa: E402

state, ROWS = walkthrough.run()

doc = Document(PART_A)
BODY = doc.element.body
# The hand-written base document lacks the "Table Grid" style used for generated tables.
_default_styles = Document().styles
for _name in ("Table Grid",):
    if _name not in [st_.name for st_ in doc.styles]:
        doc.styles.element.append(copy.deepcopy(_default_styles[_name].element))


def _para(start: str) -> Paragraph:
    hits = [p for p in doc.paragraphs if p.text.strip().startswith(start)]
    assert len(hits) == 1, (start, len(hits))
    return hits[0]


def _set(p: Paragraph, text: str) -> None:
    p.runs[0].text = text
    for r in p.runs[1:]:
        r.text = ""


def prepare_sections_4_1_to_4_7() -> None:
    """Edits the hand-written design part so it reads as the first half of one chapter."""
    _set(doc.paragraphs[0], "Chapter 4: System Design and Initial Results")
    _set(_para("In this chapter, we will present"),
         "This chapter presents the design of the Socratic-Agent prototype and the initial results of "
         "implementing it. Sections 4.1 to 4.7 set out the design: the functional and non-functional "
         "requirements, the four-layer architecture, the three agents and how they communicate, the "
         "student's interaction workflow, the design decisions and the user interface. Sections 4.8 to 4.16 "
         "report the initial results for Prototype V1: how the design was implemented and enforced, the use "
         "cases, how a student moves between levels of the Structure of the Observed Learning Outcome "
         "(SOLO) taxonomy, a complete walkthrough for a student and a teacher, progress tracking, the links "
         "to the underlying theories, the verification of the design, and screens of the running system. "
         "The prototype uses a large language model (LLM) reached through an application programming "
         "interface (API).")
    fr = _para("4.2.1 Functional Requirements")
    note = copy.deepcopy(_para("This arrangement was selected because")._p)
    fr._p.addnext(note)
    _set(Paragraph(note, fr._parent), "The functional requirements are referred to as FR1 to FR13 in the order "
         "listed below.")
    nfr = _para("4.2.2 Non-Functional Requirements")
    note2 = copy.deepcopy(note)
    nfr._p.addnext(note2)
    _set(Paragraph(note2, nfr._parent), "The non-functional requirements (NFR) are listed below.")
    sep = _para("The separation of pedagogical responsibilities")
    _set(sep, sep.text.replace("reviewed in Section 2.2.3.", "reviewed in Sections 2.2.6 and 2.2.7."))
    arch = _para("The proposed system will follow a four-layer architecture")
    _set(arch, arch.text.replace("data management.This design", "data management. This design")
         + " Figure 4.1 shows the four layers and their components.")
    js = _para("All three agents use a shared external")
    _set(js, js.text.replace("service.They", "service. They")
         .replace("structured JSON objects", "structured JavaScript Object Notation (JSON) objects"))
    # Figure captions: "Figure 4.2: Title" / "Figure 4.1   Title" -> "Figure 4.2 Title"
    for p in doc.paragraphs:
        m = re.match(r"^(Figure 4\.\d+)[:\s]+(.*)$", p.text.strip())
        if m and len(p.text) < 120:
            _set(p, f"{m.group(1)} {m.group(2).strip()}")
    # Learning-objective table becomes Table 4.1 with its caption above it.
    lo_cap = _para("Table 4.2  Learning objectives proposed")
    _set(lo_cap, "Table 4.1 Learning objectives of the prototype (LO1–LO11)")
    lo_tbl = doc.tables[0]
    lo_tbl._tbl.addprevious(lo_cap._p)
    lo_txt = _para("The learning objectives were formulated using measurable action verbs")
    _set(lo_txt, "Table 4.1 lists the eleven learning objectives (LO1–LO11) used in the prototype. They were "
         "formulated using measurable action verbs aligned with the revised Bloom's Taxonomy (Anderson and "
         "Krathwohl, 2001). The "
         "objectives primarily target understanding and application, with selected tasks requiring analysis.")
    lo_cap._p.addprevious(lo_txt._p)  # reference text, then caption, then table
    # Design decisions matrix becomes Table 4.2, referenced in the text, caption above it.
    _set(_para("The following statements connect the literature-informed rationale"),
         "Table 4.2 connects each literature-informed basis to the hypothesis or research question it serves, "
         "a design requirement, its design decision (DD1–DD7) and a planned evaluation.")
    dd_tbl = doc.tables[1]
    for row in dd_tbl.rows:  # IEEE numbering, as in Chapter 2
        for cell in row.cells:
            for para in cell.paragraphs:
                for r in para.runs:
                    r.text = (r.text.replace("Socratic questioning (Section 2.2.2)", "Socratic questioning (Section 2.2.5)")
                              .replace("(Section 2.2.2 and Dong et al.)", "(Section 2.2.5; Dong et al., 2025)")
                              .replace("Section 2.2.2; Ouyang and Jiao)", "Section 2.2.1; Ouyang and Jiao, 2021)"))
    dd_cap = copy.deepcopy(lo_cap._p)
    dd_tbl._tbl.addprevious(dd_cap)
    _set(Paragraph(dd_cap, lo_cap._parent), "Table 4.2 Design decisions matrix")
    # Drop Part A's own summary (a combined summary closes the chapter) and empty paragraphs.
    start = _para("4.8 Chapter Summary")._p
    el = start
    while el is not None and el.tag != qn("w:sectPr"):
        nxt = el.getnext()
        BODY.remove(el)
        el = nxt
    for p in list(doc.paragraphs):
        if not p.text.strip() and not p._p.findall(".//" + qn("w:drawing")) and p._p.find(".//" + qn("w:sectPr")) is None:
            BODY.remove(p._p) if p._p.getparent() is BODY else None


prepare_sections_4_1_to_4_7()


# ---------------------------------------------------------------- text adaptation for 4.8 onward
def _renum(n: int) -> int:
    return n  # section numbers below are written as they appear in the chapter


# Harvard keys for the IEEE numbers of the reference list in writting/Chapter 2.docx [1]-[27].
HARVARD = {
    1: ("Zawacki-Richter et al.", 2019), 2: ("Ouyang and Jiao", 2021), 3: ("VanLehn", 2011), 4: ("Woolf", 2010),
    5: ("Rus et al.", 2015), 6: ("Liu et al.", 2025), 7: ("Wang et al.", 2025), 8: ("Liu et al.", 2024),
    9: ("Posner et al.", 1982), 10: ("Chi and Roscoe", 2002), 11: ("Kaczmarczyk et al.", 2010), 12: ("Ng et al.", 2024),
    13: ("Kirschner et al.", 2006), 14: ("Nichols", 1994), 15: ("Dong et al.", 2025), 16: ("Black and Wiliam", 2009),
    17: ("Vygotsky", 1978), 18: ("Wood et al.", 1976), 19: ("Sweller", 1988), 20: ("Bloom", 1956),
    21: ("Anderson and Krathwohl", 2001), 22: ("Biggs and Collis", 1982), 23: ("Maurya et al.", 2025),
    24: ("Zhao et al.", 2026), 25: ("Gabrovšek and Rihtaršič", 2025), 26: ("Li et al.", 2024), 27: ("Blasco and Charisi", 2024),
}
_GROUP = re.compile(r"\[(\d+)\](?:\s*(?:,|–)\s*\[(\d+)\])*")


def to_harvard(text: str) -> str:
    """Rewrite IEEE citations as Harvard: narrative after the author's name, parenthetical otherwise."""
    out, pos = [], 0
    for m in _GROUP.finditer(text):
        nums, raw = [], m.group(0)
        for part in re.finditer(r"\[(\d+)\]|(–)", raw):
            if part.group(2):
                nums.append("range")
            else:
                n = int(part.group(1))
                if nums and nums[-1] == "range":
                    nums.pop()
                    nums.extend(range(nums[-1] + 1, n + 1))
                else:
                    nums.append(n)
        before = text[pos:m.start()]
        first_surname = HARVARD[nums[0]][0].split()[0].rstrip(",")
        tail = before[-45:]
        if len(nums) == 1 and first_surname in tail:          # "Biggs and Collis [22]" -> "Biggs and Collis (1982)"
            out.append(before.rstrip() + f" ({HARVARD[nums[0]][1]})")
        else:
            cites = "; ".join(f"{HARVARD[n][0]}, {HARVARD[n][1]}" for n in nums)
            opened = (text[:m.start()].count("(") > text[:m.start()].count(")"))
            out.append(before + (cites if opened else f"({cites})"))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


PLAIN = [  # code values -> ordinary words (the thesis describes behaviour, not identifiers)
    ("CLOSED_AT_CAP", "closed at the round limit"), ("closed_at_cap", "closed at the round limit"),
    ("MASTERED", "mastered"), ("extended_abstract", "extended abstract"),
    ("simpler_sub_question", "simpler sub-question"), ("worked_example", "worked example"),
    ("jump_up", "up two or more levels"), ("first_rating", "first rating"), ("gap_surfaced", "gap surfaced"),
    ("round_cap", "round limit"), ("in_progress", "in progress"),
]


def T(text: str) -> str:
    """Adapts generated text to the merged chapter: section numbers shift by one (4.9 -> 4.8 ...),
    the learning-objective table is Table 4.1, and 'Part A' becomes the design sections."""
    if not isinstance(text, str):
        return text
    text = re.sub(r"(Sections?\s+)(4\.\d+(?:\.\d+)?(?:\s*(?:–|and|,)\s*4\.\d+(?:\.\d+)?)*)",
                  lambda m: m.group(1) + re.sub(r"4\.(\d+)", lambda k: f"4.{_renum(int(k.group(1)))}", m.group(2)),
                  text)
    text = to_harvard(text)
    for a, b in PLAIN:
        text = text.replace(a, b)
    for a, b in (("Part A artefact", "Design artefact"), ("of the Part A design", "of the design"),
                 ("artefact of Part A", "artefact of the design (Sections 4.2–4.7)"),
                 ("Match Part A", "Match the design")):
        text = text.replace(a, b)
    return text


TABLE_NO = [2]  # Sections 4.1-4.7 hold Tables 4.1-4.2
APPX = [None, 0]  # appendix label ("A1") and its own table counter once the appendices start
FIG_NO = [3]    # and Figures 4.1-4.3


def H(text, level=2):
    text = re.sub(r"^4\.(\d+)", lambda m: f"4.{_renum(int(m.group(1)))}", text)
    doc.add_heading(T(text), level=level)


def P(text, italic=False, size=None, align=None, space_after=6):
    p = doc.add_paragraph()
    run = p.add_run(T(text))
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def RICH(parts):
    """parts: list of (text, bold) tuples in one paragraph."""
    p = doc.add_paragraph()
    for text, bold in parts:
        r = p.add_run(text)
        r.bold = bold
    p.paragraph_format.space_after = Pt(6)


def BUL(text, bold_lead=None):
    p = doc.add_paragraph()  # the base document has no List Bullet style: bullet + hanging indent
    p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Inches(0.3), Inches(-0.2)
    p.add_run("•\u00a0\u00a0")
    if bold_lead:
        p.add_run(T(bold_lead)).bold = True
    p.add_run(T(text))
    p.paragraph_format.space_after = Pt(3)


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def TABLE(headers, rows, widths, caption, size=9):
    if APPX[0]:
        APPX[1] += 1
        label = f"Table {APPX[0]}.{APPX[1]}"
    else:
        TABLE_NO[0] += 1
        label = f"Table 4.{TABLE_NO[0]}"
    cap = P(f"{label} {caption}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    cap.runs[0].bold = True
    cap.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(T(h))
        r.bold = True
        r.font.size = Pt(size)
        shade(c, "D9E2F3")
    repeat_header(t.rows[0])
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            para = cells[i].paragraphs[0]
            text = "" if val is None else T(str(val))
            if text.startswith("**") and text.endswith("**"):
                rr = para.add_run(text[2:-2]); rr.bold = True
            else:
                rr = para.add_run(text)
            rr.font.size = Pt(size)
    t.autofit = False
    tblPr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed"); tblPr.append(layout)
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW"); tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa"); tblW.set(qn("w:w"), str(int(sum(widths) * 1440)))
    grid = t._tbl.tblGrid
    for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(int(widths[i] * 1440)))
    for i, w in enumerate(widths):
        t.columns[i].width = Inches(w)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return label


def FIGURE(path, caption, width=6.4):
    FIG_NO[0] += 1
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = P(f"Figure 4.{FIG_NO[0]} {caption}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    cap.runs[0].bold = True
    return f"Figure 4.{FIG_NO[0]}"


PAGE_W, PAGE_H = Mm(210), Mm(297)  # A4 (guidelines)


def _margins(s):
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Mm(25), Mm(20), Mm(20), Mm(20)


def landscape():
    s = doc.add_section()
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = PAGE_H, PAGE_W
    _margins(s)


def portrait():
    s = doc.add_section()
    s.orientation = WD_ORIENT.PORTRAIT
    s.page_width, s.page_height = PAGE_W, PAGE_H
    _margins(s)


# =====================================================================================
# Research Office writing guidelines (final report, Appendix A)
CAPTION = re.compile(r"^(Table|Figure) (?:4|A\d)\.\d+ \S")
HEADING = [(re.compile(r"^Chapter 4\b"), 1, 14), (re.compile(r"^Appendix \d+:"), 1, 14), (re.compile(r"^4\.\d+\.\d+\s"), 3, 12), (re.compile(r"^4\.\d+\s"), 2, 14)]


def _page_number_field(run):
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = text
        run._r.append(el)


def format_to_guidelines(d):
    black = RGBColor(0, 0, 0)
    normal = d.styles["Normal"]
    normal.font.name, normal.font.size = "Times New Roman", Pt(12)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Times New Roman")
    for lvl, size in ((1, 14), (2, 14), (3, 12)):
        h = d.styles[f"Heading {lvl}"]
        h.font.name, h.font.size, h.font.bold, h.font.italic, h.font.color.rgb = "Times New Roman", Pt(size), True, False, black
        h.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Times New Roman")
        h.paragraph_format.space_before, h.paragraph_format.space_after = Pt(12), Pt(6)
        h.paragraph_format.keep_with_next = True
    # Pages: A4, left 25 mm, others 20 mm; header with names, degree, year and page number (top right).
    for sec_ in d.sections:
        landscape_ = sec_.page_width > sec_.page_height
        sec_.page_width, sec_.page_height = (PAGE_H, PAGE_W) if landscape_ else (PAGE_W, PAGE_H)
        _margins(sec_)
        sec_.header_distance = Mm(10)
    hdr = d.sections[0].header
    hdr.is_linked_to_previous = False
    hp = hdr.paragraphs[0]
    for r in hp.runs:
        r.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = hp.add_run(HEADER_TEXT); run.font.size = Pt(10); run.font.name = "Times New Roman"
    num = hp.add_run(); num.font.size = Pt(10); _page_number_field(num)
    for sec_ in d.sections[1:]:
        sec_.header.is_linked_to_previous = True

    # Page numbers run on through the whole report: no section restarts them.
    for pg in d.element.body.iter(qn("w:pgNumType")):
        pg.attrib.pop(qn("w:start"), None)
    for el in d.element.body.iter(qn("w:contextualSpacing")):  # uneven list spacing in the base document
        el.getparent().remove(el)
    for p in d.paragraphs:
        text = p.text.strip()
        pf = p.paragraph_format
        level = next(((lvl, size) for rx, lvl, size in HEADING if rx.match(text)), None)
        if level and (p.style.name.startswith(("Heading", "Title")) or all(r.bold for r in p.runs if r.text.strip())):
            p.style = d.styles[f"Heading {level[0]}"]
            for r in p.runs:
                r.font.size = r.font.color.rgb = r.font.name = r.bold = r.italic = None
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level[0] == 1 else WD_ALIGN_PARAGRAPH.LEFT
            if text.startswith("Appendix"):
                pf.page_break_before = True
            pf.line_spacing = 1.5
            continue
        if CAPTION.match(text) and len(text) < 160 and not re.match(r"^(Table|Figure) \S+ (shows|lists|sets|summarises|presents|connects|details|will|takes|gives|extends|covers)\b", text):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.bold, r.italic, r.font.size, r.font.color.rgb = True, False, Pt(12), black
            pf.space_before, pf.space_after, pf.line_spacing = Pt(6), Pt(12), 1.0
            nxt = p._p.getnext()
            follows_evidence = (nxt is not None and nxt.tag == qn("w:p")
                                and Paragraph(nxt, p._parent).text.startswith("Evidence for"))
            pf.keep_with_next = text.startswith("Table") or follows_evidence
            if follows_evidence:
                pf.space_after = Pt(0)
            continue
        if p._p.findall(".//" + qn("w:drawing")):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf.keep_with_next, pf.space_after, pf.line_spacing = True, Pt(6), 1.0
            continue
        if not text:  # d.paragraphs holds body-level paragraphs only; tables are handled below
            continue
        listed = (p.style.name.startswith("List") or text.startswith("•")
                  or (p._p.pPr is not None and p._p.pPr.find(qn("w:numPr")) is not None))
        if p.alignment != WD_ALIGN_PARAGRAPH.CENTER:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.line_spacing, pf.widow_control = 1.5, True
        if not listed:
            pf.first_line_indent = Pt(0)
        pf.space_before, pf.space_after = Pt(0), Pt(6 if listed else 12)
        for r in p.runs:
            if r.font.size and r.font.size < Pt(12) and not r.italic:
                r.font.size = Pt(12)
    # Tables: 10 pt (the smallest size the guidelines allow), single spacing, centred.
    for t in d.tables:
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        repeat_header(t.rows[0]) if t.rows[0]._tr.trPr is None or t.rows[0]._tr.trPr.find(qn("w:tblHeader")) is None else None
        for row in t.rows:  # rows never split across pages; the header row stays with the first data row
            trPr = row._tr.get_or_add_trPr()
            if trPr.find(qn("w:cantSplit")) is None:
                trPr.append(OxmlElement("w:cantSplit"))
        for c in t.rows[0].cells:
            for p in c.paragraphs:
                p.paragraph_format.keep_with_next = True
                for r in p.runs:
                    r.bold = True
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.line_spacing, p.paragraph_format.space_after = 1.0, Pt(0)
                    p.paragraph_format.space_before = Pt(0)
                    for r in p.runs:
                        r.font.size, r.font.name = Pt(10), "Times New Roman"
    # Pictures: never wider than the text block.
    max_w = PAGE_W - Mm(45)
    for shape in d.inline_shapes:
        if shape.width > max_w:
            ratio = max_w / shape.width
            shape.width, shape.height = int(shape.width * ratio), int(shape.height * ratio)


# =====================================================================================
H("4.8 Implementation Overview")
P("This part of the chapter reports the initial results: how the design of Sections 4.2 to 4.7 was "
  "implemented in Prototype V1, how a student moves through it, and what evidence shows that it behaves "
  "as designed. Prototype V2 will be developed after the evaluation, using its results (Chapter 5). "
  "Table " + f"4.{TABLE_NO[0] + 1}" + " lists the technologies used.")
TABLE(["Component", "Technology", "Role"], [
    ["Interface", "Streamlit web application (Python)", "Student chat, My Progress page, Teacher Dashboard"],
    ["Language model", "Gemini 2.5 Flash through OpenRouter", "The three agents, each with its own instructions"],
    ["Orchestrator and learner model", "Python", "Stages, round limits, support limits, answer-leakage guard, objective outcomes"],
    ["Database", "SQLite", "Accounts, sessions, dialogue turns and learner-state snapshots"],
    ["Testing", "Automated tests with scripted agent replies", "Checks the system's own rules without calling the language model"],
], [1.6, 2.2, 2.7], "Technologies used in Prototype V1", size=9)
P("Each rule in the design is enforced in one of four ways: by code, which the model cannot bypass; "
  "bounded, where the model decides and the orchestrator checks the decision; by prompt, an instruction the "
  "model may not follow; or by the study instruments. Appendix 3 gives the enforcement of every design "
  "decision.")

H("4.8.1 What the Implementation Claims, and What It Does Not", 3)
P("A review of the first V1 build found three places where the natural description of the design says more "
  "than the system actually does. V1 was corrected, in its behaviour and in its wording, so that the two "
  "match. " + f"Table 4.{TABLE_NO[0] + 1}" + " states each claim as precisely as the implementation supports it.")
TABLE(
    ["Topic", "Tempting description (avoid)", "What the system actually does", "V1 correction", "Enforcement"],
    [
        ["SOLO classification",
         "\"The system classifies the student's SOLO level.\"",
         "The Cognitive Diagnostician (and, during support, the Scaffolding Curator) judges the SOLO level of "
         "the latest response using the SOLO rubric in its instructions. No separately trained classifier "
         "exists.",
         "Every rating is recorded as the language model's estimate, together with the agent that made it. "
         "Only the change between two estimates is calculated by the system. The estimates can be exported "
         "for human rating and compared with them (DD2).",
         "Prompt (level); Code (recording, movement)"],
        ["Scaffolding",
         "\"A ZPD algorithm measures the student's level and sets the right support.\"",
         "Support is chosen by the Curator, not calculated from a measurement of the student (Section 4.4.3).",
         "The limits of Section 4.4.3 are enforced by the orchestrator and every breach is counted. They are "
         "described as rules informed by ZPD and fading [17], [18], not as a measurement of the ZPD.",
         "Prompt (choice); Bounded (limits)"],
        ["Mastery",
         "\"When the student reaches the next objective, the previous one is mastered.\"",
         "An objective also closes when the round limit for support is reached, even if the Curator has not "
         "judged the understanding sufficient.",
         "Each objective ends in one of the two outcomes of Figure 4.2. The student is told when an objective "
         "is parked, and the interface, dashboard and data export never merge the two outcomes.",
         "Code"],
    ],
    [1.0, 1.25, 1.6, 1.9, 0.75], "Implementation claims made precise in V1", size=8.5)
P("The rest of this chapter uses the precise wording. \"SOLO estimate\" means the agent's rating of one "
  "response. \"Support limit\" means the upper limit the orchestrator places on support. \"Mastered\" "
  "means the mastery gate was passed; "
  "\"covered\" includes objectives closed at the cap.")


# -------------------------------------------------------------------------------------
H("4.9 Use Cases")
P("Three actors use the system: the Student, the Teacher and the Researcher. Figure " + f"4.{FIG_NO[0] + 1}"
  + " shows the 26 use cases and Table " + f"4.{TABLE_NO[0] + 1}" + " summarises the main ones. The "
  "complete catalogue, and the full description of the central use case UC-11, are in Appendix 1.")
FIGURE(FIG / "fig_use_cases.png", "Use-case diagram of Prototype V1", width=6.0)
TABLE(["Use cases", "Actor", "Situation", "System response"], [
    ["UC-03, UC-04", "Student", "Starts a topic and states a hypothesis", "The Facilitator captures the hypothesis and the dialogue moves to testing"],
    ["UC-05, UC-06", "Student", "Asks for the answer", "The request is declined; a draft that gives the answer away is regenerated"],
    ["UC-07, UC-08", "Student", "Is unsure, or shows a misconception", "The Diagnostician narrows the task or probes it; a misconception is recorded with the student's words"],
    ["UC-09, UC-10", "Student", "Is stuck, or improves", "Support rises one step at a time, and steps back down after an improvement"],
    ["UC-11, UC-12", "Student", "Answers a transfer question", "A justified answer masters the objective; a bare answer is asked why"],
    ["UC-13", "Student", "Makes no progress in three support rounds", "The objective is parked and recorded as not mastered"],
    ["UC-23 to UC-26", "Student", "Checks progress or retries", "My Progress shows outcomes and milestones and offers a retry"],
    ["UC-18 to UC-20", "Teacher", "Reviews sessions", "The dashboard shows outcomes, SOLO estimates, misconceptions and transcripts"],
    ["UC-21, UC-22", "Researcher", "Exports and rates data", "Anonymised export; SOLO estimates ready for human rating"],
], [1.05, 0.8, 1.9, 2.75], "Main use cases", size=9)

# -------------------------------------------------------------------------------------
H("4.10 How a Student Moves Between SOLO Levels")
P("Biggs and Collis [22] describe five levels of structural complexity in a response. The system uses "
  "these levels in three ways. Each response is rated with the SOLO rubric written into the agent prompts: the five levels plus two coding rules (a bare correct answer is unistructural; a well-connected account with a wrong value stays relational). This rating is an LLM estimate. The "
  "change between two estimates decides how much support is allowed. The level of the transfer answer "
  "decides whether an objective is mastered. A level describes one response, not the student, so it can "
  "fall as well as rise [22]. " + f"Figure 4.{FIG_NO[0] + 1}" + " shows the path from a student response to a system decision.")
FIGURE(FIG / "fig_movement_flow.png", "From a student response to a system decision (only step 2 is an LLM judgement)")
H("4.10.1 SOLO Movement Cases", 3)
P("The movement cases in Table " + f"4.{TABLE_NO[0] + 1}" + " cover every kind of change the prototype handles, using objective LO5 (loop tracing, "
  "while i < 3: print(i); i += 1) as the example. Each case is checked by a test with a scripted model, "
  "so the table describes the system's actual response.")
TABLE(["Case", "Movement", "Example response (LO5)", "Recorded as", "System response"], [
    ["S1", "prestructural → unistructural", "\"I don't know\" → \"i starts at 0\"", "up one level",
     "Elenchus: keep probing one aspect. Support: the limit drops one level."],
    ["S2", "unistructural → multistructural", "\"it checks i < 3, prints, adds one\" (listed, not connected)", "up one level",
     "Diagnostician tests a likely misconception with a counterexample."],
    ["S3", "multistructural → relational", "order and cause stated: \"when i is 3, 3 < 3 is false, so 3 is never printed\"", "up one level",
     "Curator stops supporting and asks a transfer question; mastery not yet allowed."],
    ["S4", "relational → extended abstract", "\"with i < 5 it prints 0 to 4, because the check comes before every print\"", "up one level",
     "Transfer asked earlier + justified answer → gate passes → mastered."],
    ["S5", "jump of two or more levels", "unistructural → relational in one answer", "up two or more levels",
     "Recorded separately for review; support fades."],
    ["S6", "no change", "unistructural twice", "no change", "Support may rise by one level."],
    ["S7", "down", "relational → unistructural after a counterexample", "down",
     "Recorded; the level describes the response, not the student; support may rise by one level."],
    ["S8", "bare correct answer", "\"0 1 2\" with no explanation", "unistructural (rule a)",
     "Gate refuses mastery and asks why."],
    ["S9", "good estimate, but cap reached", "relational in the third support round, no transfer yet", "any",
     "Closed at the round limit: covered, not mastered."],
    ["S10", "invalid rating", "model returns an unknown label", "not rated",
     "Previous estimate kept; treated as no movement."],
], [0.4, 1.2, 1.9, 1.0, 2.0], "SOLO movement cases and the system's response", size=8.5)
P("Two limits apply to this table. First, every level in it is an LLM estimate. DD2 evaluates it "
  "against rubric-based human labels (Section 5.3.2): every estimate can be exported for human rating, and "
  "the agreement analysis reports "
  "the disagreements as well as the agreement statistics. Second, a rise in the estimate within one "
  "session is an observation about responses. It is not, by itself, evidence of learning; that question "
  "is addressed by the pre/post quiz (DD6).")


# -------------------------------------------------------------------------------------
H("4.11 System Walkthrough: One Complete Scenario")
P("The walkthrough follows one student through the Loops topic (LO5, LO6, LO7). The agents' replies are "
  "scripted and given to the real orchestrator in place of the language model, so the trace shows the "
  "system's own behaviour, not the quality of a real model's questions. It covers both endings of an "
  "objective: LO5 and LO7 are mastered, and LO6 is parked at the round limit. Table " + f"4.{TABLE_NO[0] + 1}"
  + " gives the key moments and Figure " + f"4.{FIG_NO[0] + 1}" + " plots the SOLO estimates; the full "
  "turn-by-turn trace is in Appendix 2.")
MOVE = {"first_rating": "first rating", "up": "up one level", "jump_up": "up two or more", "stable": "no change",
        "down": "down", "unrated": "not rated", "": ""}
OUTCOME = {"mastered": "Mastered", "closed_at_cap": "Closed at round limit", "in_progress": "In progress"}
wt_rows = []
for r in ROWS:
    tutor = r["tutor"].replace(" ¶ ", " | ").replace("```python", "[code:").replace("```", "]")
    if len(tutor) > 210:
        tutor = tutor[:207] + "…"
    solo = f"{r['solo_estimate']} ({MOVE[r['movement']]})" if r["solo_estimate"] else "—"
    support = f"{r['support']} (limit: {r['ceiling']})" if r["support"] else "—"
    event = OUTCOME[r["lo_status"]] if r["lo_status"] in ("mastered", "closed_at_cap") else ""
    if r["guard"]:
        event = (event + "; " if event else "") + r["guard"]
    wt_rows.append([r["step"], r["lo"], r["student"], f"{r['agents']}: {tutor}", r["stage_after"], solo,
                    support, event or "—", r["cases"]])
TABLE(["Step", "LO", "What happens", "System response"], [
    ["1", "LO5", "The student asks for the answer", "The Facilitator's draft gave it away; the guard regenerated it and the student saw only a question"],
    ["2", "LO5", "States a hypothesis: 0, 1, 2, 3", "Hypothesis captured; testing begins"],
    ["4", "LO5", "Says 3 may be printed", "Misconception recorded; gap surfaced; support begins"],
    ["6", "LO5", "Explains why the loop stops before 3", "Estimate jumps to relational; a transfer question is asked"],
    ["7", "LO5", "Explains the new case i < 5", "Mastered; the next objective opens"],
    ["11", "LO6", "Still unsure after three testing rounds", "Testing ends at the round limit; support begins"],
    ["12–13", "LO6", "Stays stuck", "Support rises from a hint to a simpler sub-question"],
    ["14", "LO6", "Works out the value of i", "Support steps back to a hint; the round limit is reached and LO6 is parked"],
    ["19", "LO7", "Gives a bare answer to the transfer question", "Mastery refused; the student is asked why"],
    ["20", "LO7", "Explains the answer", "Mastered; the session ends and names LO6 as parked"],
], [0.55, 0.5, 2.3, 3.15], "Key moments of the walkthrough", size=9)
FIGURE(FIG / "fig_solo_trajectory.png", "SOLO estimates across the walkthrough (circles: Diagnostician; squares: Curator)")

H("4.11.1 The Teacher's View of the Same Session", 3)
from socratic_agent import db as _db  # noqa: E402
from evaluation.export_research_data import export as _export  # noqa: E402

_db.init_db()
_db.create_student("walkthrough-student", "Walkthrough Student", "walkthrough-pass")
_sid = _db.create_session("walkthrough-student", "loops")
for _i, _t in enumerate(state.history):
    _db.log_turn(_sid, _i, _t.role, _t.agent, _t.content)
_db.log_snapshot(_sid, len(state.history) - 1, state)
_db.end_session(_sid, "completed")
_rows = [r for r in _db.objective_outcomes() if r["session_id"] == _sid]
_stats, _leaks = _db.objective_stats(), _db.leak_stats()
_mis = [m for m, _ in sorted(_db.misconception_frequency().items())]
_exp_dir = Path(tempfile.mkdtemp())
_export(_exp_dir)
_n_out = sum(1 for line in (_exp_dir / "objective_outcomes.csv").read_text().splitlines()[1:] if _sid in line)
_n_solo = sum(1 for line in (_exp_dir / "solo_labelling.csv").read_text().splitlines()[1:] if _sid in line)
from socratic_agent.topic_bank import misconception_label as _ml  # noqa: E402
SHOT = FIG.parent / "screenshots"
_lo6 = next(r for r in _rows if r["design_id"] == "LO6")
P("After the session, the teacher reviews it on the Teacher Dashboard. The four screens below follow "
  "the teacher through that review; they show the walkthrough session itself, stored in the database "
  "exactly as the student produced it.")
P(f"Step 1, sign in (UC-18). The teacher opens the dashboard and enters the shared passcode "
  f"(Figure 4.{FIG_NO[0] + 1}). Students cannot reach any recorded data without it.")
FIGURE(SHOT / "ui_10_dashboard_passcode.png", "Teacher Dashboard: passcode screen", width=5.6)
P(f"Step 2, overview (UC-20). The first screen summarises all sessions (Figure 4.{FIG_NO[0] + 1}). For "
  f"the walkthrough student it shows {_stats['mastered']} objectives mastered and {_stats['not_mastered']} "
  f"closed at the round limit, kept apart so that coverage is not mistaken for mastery, together with "
  f"{_stats['gate_rejections']} mastery claim refused by the orchestrator and the outcome of each learning "
  f"objective: LO5 and LO7 mastered, LO6 not yet. Students appear only as participant codes unless names "
  f"are switched on.")
FIGURE(SHOT / "ui_07_dashboard_outcomes.png",
       "Teacher Dashboard overview: rule enforcement and the outcome of each learning objective", width=6.3)
P(f"Step 3, the student's session (UC-19). Selecting the student and the session opens the session view "
  f"(Figure 4.{FIG_NO[0] + 1}). The chart plots the SOLO estimate of every rated answer; beside it are the "
  f"misconceptions found ({', '.join(_ml(m) for m in _mis)}), the objectives mastered and parked, and the "
  f"full transcript, so each estimate can be checked against the student's own words.")
FIGURE(SHOT / "ui_09_dashboard_solo_trajectory.png",
       "Teacher Dashboard: SOLO estimates, outcomes, misconceptions and transcript of the walkthrough session",
       width=6.3)
P(f"Step 4, how much help was needed (UC-19). Further down, the objective records and the support "
  f"sequence show where the student started and ended on each objective and which support was given "
  f"(Figure 4.{FIG_NO[0] + 1}). For LO6 the student moved from {_lo6['entry_solo']} to "
  f"{_lo6['exit_solo'].replace('_', ' ')} while the support rose from a hint to a simpler sub-question and "
  f"stepped back to a hint, before the objective was parked at the round limit.")
FIGURE(SHOT / "ui_08_dashboard_objective_records.png",
       "Teacher Dashboard: objective records and support sequence of the walkthrough session", width=6.3)
P("From these screens the teacher can see that the student needs another attempt at LO6, with the "
  "misconception that a loop variable disappears after the loop, while LO5 and LO7 were explained on new "
  "cases. The researcher can then export the session (UC-21): the export for this session contained "
  f"{_n_out} objective outcomes and {_n_solo} SOLO estimates ready for human rating (UC-22), keyed "
  "by participant code and without the student's name or ID.")


# -------------------------------------------------------------------------------------
H("4.12 Progress Tracking and Motivating Feedback")
P("Design decision DD7 adds a student-facing view of progress, to keep students engaged with a process "
  "that can feel slower than being given the answer (Section 2.2.5). Table " + f"4.{TABLE_NO[0] + 1}"
  + " lists the features. All feedback comes from fixed text, not the language model, so it cannot give an "
  "answer away, and mastered and parked objectives are never shown together. Seven milestones reward "
  "learning behaviour, such as explaining a new case, changing one's mind after a misconception, or coming "
  "back to a parked objective; none rewards speed. Whether these features motivate students is measured "
  "in the pilot (survey items D5–D7).")
TABLE(["Feature", "What the student sees", "Rule", "Theory"], [
    ["Progress header", "Pinned at the top of the chat: the current objective, a progress bar, one pill per objective and the three dialogue stages", "Shows mastered and parked objectives in different colours; stays visible while the conversation scrolls", "Formative feedback [16]"],
    ["Feedback card when an objective closes", "\"LO5 mastered — you explained it on a new case\" or \"LO6 is parked for now — not mastered yet\", with growth in plain words",
     "Fixed templates, no LLM; growth shown only if the estimate rose; labelled \"estimated\"", "Formative feedback [16]; SOLO [22]"],
    ["Milestones", "Seven badges, each with how to earn it", "Earned from objective records only; none rewards speed, streaks or time", "Conceptual change [9]; feedback on process [16]"],
    ["Session summary", "Mastered, parked and new milestones; growth per objective; next step", "Mastered and parked counted separately", "Formative feedback [16]"],
    ["My Progress page", "All topics and objectives across sessions; best answer so far; milestones", "Best status per objective across sessions; parked never shown as done", "Learner agency [2]"],
    ["Next step and retry", "One suggested action; a Retry button for parked objectives", "Retry first, then continue a topic, then a new topic; a retry is a one-objective practice session", "Learner agency [2]; ZPD [17]"],
], [1.25, 1.85, 1.85, 1.55], "Progress and motivation features (DD7)", size=8.5)


# -------------------------------------------------------------------------------------
H("4.13 Linking the Theories to the Implementation")
P("Each theory used in the design is connected to the mechanism that implements it, and to the limit of the "
  "claim, in Table " + f"4.{TABLE_NO[0] + 1}" + ".")
THEORY_ROWS = [
    ["Constructivism, conceptual change [9], [10]", "Start from the learner's own model; make it explicit before challenging it",
     "WONDER stage captures a hypothesis before any probing (code); \"Changed your mind\" milestone (code)", "Stored hypothesis; milestones",
     "The model may accept a vague position as a hypothesis"],
    ["Socratic method [12]", "Question rather than tell; one question; no confirmation",
     "Facilitator rules, six question categories (prompt); answer withheld (code + prompt)",
     "Question category and drift count of each turn; transcript", "Question quality is judged in the pilot rubric"],
    ["Cognitive diagnosis [11], [14], [15]", "Infer difficulties from evidence, not from correctness alone",
     "Misconception bank; misconception stored only with a quote (bounded)", "Misconception chips; evidence field",
     "An LLM inference, not a validated diagnosis [15]"],
    ["Formative assessment and feedback [16]", "Use evidence to change the next step; tell learners where they are",
     "SOLO movement sets the support ceiling; outcome and growth feedback cards (code)",
     "Support limit applied to each move; feedback cards; session summary", "Uses LLM estimates as its evidence"],
    ["SOLO taxonomy [22]", "Rate the structure of the response; bare answer = unistructural",
     "SOLO rubric in two prompts (prompt); gate requires relational or higher (code)",
     "SOLO estimate of every answer; export for human rating", "Agreement with human raters still to be measured"],
    ["Bloom's revised taxonomy [21]", "Objectives written with measurable verbs",
     "Table 4.1 objectives with design IDs LO1–LO11 (code)", "Objective panel; dashboard",
     "Classifies tasks, not the understanding shown"],
    ["ZPD and scaffolding [17], [18]", "Least support that lets the learner progress; fade it",
     "Curator chooses the level (prompt) inside the orchestrator's limits (bounded)",
     "Support sequence; counts of limit breaches", "Not a measurement of the ZPD"],
    ["Cognitive Load Theory [13], [19]", "Limit simultaneous demands; guide novices",
     "One idea per turn (prompt); round caps of 3 (code); task narrowing (prompt)", "Round counters",
     "The caps are design choices, not calibrated values"],
    ["AI paradigms, learner agency [2]", "Learners direct part of their own learning",
     "My Progress page, next step and retry of parked objectives (code)", "Retries in the logs; survey D6",
     "Agency is offered, not measured"],
    ["Prompt engineering, multi-agent systems [7], [8], [25], [26]", "Separate roles; central coordination",
     "Three role prompts; orchestrator picks one agent per stage (code)", "Stage-transition tests",
     "Does not show three agents outperform one"],
    ["AI tutor evaluation, leakage [23], [24]", "Test behaviour under pressure, not only accuracy",
     "Two-layer guard, retry, fallback (code + prompt); progress feedback never uses the LLM", "Leak counters; adversarial scenarios",
     "Unreported paraphrased leaks can pass"],
]
TABLE(["Theory", "Mechanism (enforcement)", "Limit"], [[r[0], r[2], r[4]] for r in THEORY_ROWS],
      [1.8, 2.8, 1.9], "Theories, mechanisms and their limits", size=9)

# -------------------------------------------------------------------------------------
import io  # noqa: E402
import unittest  # noqa: E402

SUITES = {"tests.test_v1_verification": "first-build verification", "tests.test_v1_design": "design verification",
          "tests.test_v1_progress": "progress and feedback"}
RESULTS = {}
for name in SUITES:
    suite = unittest.TestLoader().loadTestsFromName(name)
    res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    assert res.wasSuccessful(), f"{name} failed — not building a document that claims it passes"
    RESULTS[name] = res.testsRun
TOTAL = sum(RESULTS.values())

H("4.14 Verification")
parts = ", ".join(f"{RESULTS[n]} {label} tests" for n, label in SUITES.items())
P("The automated tests replace the language model with scripted replies, so each test checks the system's "
  f"own rules rather than the model. All {TOTAL} tests passed when this document was generated ({parts}), "
  "and every requirement and design decision is covered by at least one test or check (Appendix 3). The "
  "tests do not show that the model asks good questions, rates SOLO levels accurately or keeps to the "
  "prompt-level rules, nor that students learn or feel more motivated; these are the questions for the "
  "pilot evaluation in Chapter 5.")

# -------------------------------------------------------------------------------------
H("4.15 Prototype V1 Screens")
P(f"Figures 4.{FIG_NO[0] + 1}–4.{FIG_NO[0] + 6} show the student side of the prototype (the teacher screens are "
  "in Section 4.11.1). They were captured from the running application in its demonstration mode, which "
  "replays the walkthrough without calling the language model.")
SHOTS = FIG.parent / "screenshots"
for fname, caption in [
    ("ui_00a_sign_in", "Sign-in screen, with the three steps of the tutoring process"),
    ("ui_00b_sign_up", "Sign-up screen with the research consent"),
    ("ui_00c_topics", "Topic selection with each topic's progress and the recommended next topic"),
    ("ui_01_chat_opening", "Opening question for LO5, with the progress header at the top of the chat"),
    ("ui_04_session_summary", "Session summary: mastered and parked objectives, growth, milestones and the next step"),
    ("ui_05_my_progress_top", "My Progress: objectives mastered, suggested next step and topics"),
]:
    FIGURE(SHOTS / f"{fname}.png", caption, width=6.0)

H("4.16 Chapter Summary")
P("This chapter presented the design of the Socratic AI tutoring system for introductory Python "
  "programming and the initial results of implementing it as Prototype V1. The design set out the "
  "requirements, a four-layer architecture and three specialised agents coordinated by a central "
  "orchestrator through a staged dialogue with an answer-leakage guard.")
P("The implementation realises every design decision and states how strongly each rule is enforced. The "
  "use cases cover the student, the teacher and the researcher; the SOLO-movement cases show how the "
  "estimated level of an answer moves and how the system responds; and the walkthrough shows one student "
  "mastering two objectives and being honestly parked on a third, followed by the teacher's review. Three "
  "claims are kept precise: SOLO levels are estimates by the language model; support is chosen by the "
  "model within limits set by the orchestrator; and completing an objective is recorded separately from "
  "mastering it. Whether these hold with a real model and whether students learn are the questions for "
  "Chapter 5.")

# ===================================================================================== appendices
APPX[0] = "A1"
H("Appendix 1: Use-Case Catalogue", 1)
P("This appendix lists every use case of Prototype V1 (Table A1.1) and describes the central use case, UC-11, in full (Table A1.2).")
UC = [
    ["UC-01", "Student", "Register with consent", "Sign-up form, consent ticked",
     "Account stored with a securely hashed password, an anonymous participant code (P01, P02, …) and the consent version.",
     "—", "Research ethics (Section 3.6)", "DD6"],
    ["UC-02", "Student", "Sign in", "Student ID and password",
     "Password checked; a wrong password is rejected.", "—", "—", "DD6"],
    ["UC-03", "Student", "Select topic, start session", "Topic card clicked",
     "A session is created and the first learning objective (Table 4.1) is opened; the "
     "Facilitator opens with the seed question and its code.", "WONDER / Facilitator",
     "Constructivism: start from prior knowledge [9]", "DD1, DD4"],
    ["UC-04", "Student", "State a hypothesis", "Student gives a position, even a wrong or bare one",
     "The Facilitator reports that a hypothesis was captured; it is stored and the stage moves to ELENCHUS.", "WONDER → ELENCHUS",
     "Socratic method: commit to a claim before it is examined [12]; conceptual change [9]", "DD1, DD4"],
    ["UC-05", "Student", "Ask for the answer", "\"Just tell me\"",
     "Facilitator declines briefly and asks for the student's own guess; stage unchanged.", "WONDER / Facilitator",
     "Guided rather than minimal or direct instruction [13]; answer disclosure [23]", "DD1"],
    ["UC-06", "Student", "Pressure produces a leaky draft", "An agent's draft states the answer",
     "Guard trips (self-report or protected literal); draft regenerated once with a repair instruction; "
     "fixed fallback if it still leaks; leak counters updated.", "Any stage",
     "Leakage robustness [24]", "DD5"],
    ["UC-07", "Student", "Say \"I don't know\"", "Response with no relevant content",
     "Rated prestructural (estimate); task narrowed to one smaller step; no explanation given.",
     "ELENCHUS / Diagnostician", "CLT [19]; diagnosis needs evidence [14]", "DD2"],
    ["UC-08", "Student", "Reveal a misconception", "Student's words match a misconception-bank entry",
     "Stored once, only with the student's quoted words as evidence; when a gap is surfaced, or after "
     "three rounds, the stage moves to ACCEPT_REJECT and the reason (gap surfaced or round limit) is recorded.",
     "ELENCHUS / Diagnostician", "Cognitive diagnosis [14], [11]; Elenchus", "DD2, DD4"],
    ["UC-09", "Student", "Stay stuck and receive graded support", "No progress in the content of the answer",
     "First move is a hint; each further move at most one level higher (hint → sub-question → worked "
     "example); a skip is regenerated, then counted.", "ACCEPT_REJECT / Curator",
     "Scaffolding [18]; ZPD [17]", "DD3"],
    ["UC-10", "Student", "Improve, and support fades", "The Curator's estimate of the latest response rose",
     "Ceiling drops one level below the previous move; a breach is regenerated, then counted as a fade violation.",
     "ACCEPT_REJECT / Curator", "Fading [18]; CLT [19]", "DD3"],
    ["UC-11", "Student", "Answer a transfer question with justification",
     "Reasoning on the original case is sound",
     "Transfer question asked first; a justified (relational or higher) answer on a later turn → MASTERED; "
     "the next objective opens.", "ACCEPT_REJECT → WONDER",
     "SOLO extended abstract [22]; formative assessment [16]", "DD3, DD6"],
    ["UC-12", "Student", "Give a bare answer", "Correct value without an explanation",
     "Gate refuses the mastery claim and asks why; refusal counted.", "ACCEPT_REJECT / Curator",
     "SOLO coding rule (a): bare answer = unistructural [22]", "DD2, DD6"],
    ["UC-13", "Student", "Objective parked at the cap", "Three support rounds without passing the gate",
     "Objective recorded as closed at the round limit; the student is told it is parked; never counted as mastered.",
     "Orchestrator", "CLT: bounded dialogue [19]", "DD6"],
    ["UC-14", "Student", "Drift off topic", "Unrelated message",
     "Facilitator steers back to the objective; drift counted; stage kept.", "WONDER / Facilitator",
     "Context anchoring (Section 2.2.5)", "DD1"],
    ["UC-15", "Student", "Finish the session", "Last objective closes",
     "Stage DONE; the closing message names any parked objectives and is only congratulatory if all were mastered.",
     "Orchestrator", "Formative feedback [16]", "DD6"],
    ["UC-16", "Student", "New session / change topic", "Sidebar button",
     "New session state and row; earlier sessions kept.", "—", "—", "DD6"],
    ["UC-17", "Student", "Write after the session ended", "Message in DONE",
     "Fixed reply; no LLM call.", "DONE", "—", "DD4"],
    ["UC-18", "Teacher", "Open the dashboard", "Passcode",
     "Gated by a shared passcode; warning when the default is in use.", "—", "—", "DD6"],
    ["UC-19", "Teacher", "Review one session", "Select student and session",
     "SOLO-estimate trajectory, objective records (entry/exit estimate, Elenchus exit, support sequence, "
     "transfer), misconceptions, transcript.", "—", "Formative assessment [16]", "DD2, DD6"],
    ["UC-20", "Teacher", "Review cohort outcomes", "Dashboard overview",
     "Per-objective counts of mastered vs closed-at-cap; misconception frequency; leakage, gate, skip and fade counters.",
     "—", "Cognitive diagnosis at class level [14]", "DD5, DD6"],
    ["UC-21", "Researcher", "Export anonymised data", "Run the export script",
     "Data files keyed by participant code only, including the outcome of every objective and every SOLO estimate.",
     "—", "Research ethics (Section 3.6)", "DD6"],
    ["UC-22", "Researcher", "Label SOLO estimates", "Reviewers rate each exported answer",
     "Exact and adjacent agreement, quadratic-weighted kappa, and every disagreement listed.",
     "—", "LLM diagnosis must be validated [15]", "DD2"],
    ["UC-23", "Student", "View my progress", "Sidebar chips or My Progress page",
     "Best status of every objective across sessions (mastered / parked / not started), best answer so far "
     "in plain SOLO words, growth; mastered and parked never merged.", "—", "Formative feedback [16]; SOLO [22]",
     "DD7"],
    ["UC-24", "Student", "Earn a milestone", "An objective closes",
     "Milestones computed from objective records; toast and card in the chat; none rewards speed.",
     "Orchestrator → UI", "Conceptual change [9]; feedback [16]", "DD7"],
    ["UC-25", "Student", "Receive feedback on an objective", "An objective closes",
     "Template feedback card (no LLM): mastered, or parked \"not mastered yet\", with growth labelled as an estimate.",
     "Orchestrator → UI", "Formative feedback [16]", "DD7"],
    ["UC-26", "Student", "Retry a parked objective", "Retry or next-step button",
     "Practice session covering only that objective, then DONE.", "WONDER … DONE", "Learner agency [2]; ZPD [17]",
     "DD7"],
]
landscape()
TABLE(["ID", "Actor", "Use case", "Trigger", "System response", "Stage / agent", "Theory", "DD"],
      UC, [0.45, 0.6, 1.1, 1.15, 3.05, 1.0, 1.55, 0.5], "Use-case catalogue of Prototype V1", size=7.5)
P("Every use case except the passcode screen (UC-18) is replayed by an automated test with scripted "
  "agent replies; UC-18 was checked on the running dashboard.")
portrait()
TABLE(["Element", "Description"], [
    ["Actor", "Student (primary); Facilitator, Cognitive Diagnostician and Scaffolding Curator, coordinated by the orchestrator"],
    ["Precondition", "Student signed in with consent; topic selected; the learning objective is open."],
    ["Main flow",
     "The student interaction workflow of Section 4.6 (Figure 4.3), steps 2 to 5: the student states a "
     "hypothesis, the Diagnostician tests it, the Curator supports and asks a transfer question, and a "
     "justified transfer answer passes the mastery gate, after which the next objective opens."],
    ["Alternative flows",
     "A1 (at the hypothesis) Student asks for the answer → UC-05; a leaking draft → UC-06.\n"
     "A2 (during testing) \"I don't know\" → UC-07; misconception → UC-08.\n"
     "A3 (during support) No progress → support rises one level (UC-09); progress → support fades (UC-10).\n"
     "A4 (at the transfer answer) Bare answer → gate refuses, asks why (UC-12).\n"
     "A5 (during support or transfer) Three support rounds without passing the gate → closed at the round limit, parked (UC-13).\n"
     "A6 (at any point) Off-topic message → UC-14."],
    ["Postcondition",
     "The learner model holds the objective's outcome, the first, last and highest SOLO estimate, why "
     "the Elenchus stage ended, the support given and the limit applied to each move, whether a transfer "
     "question was asked, and the misconceptions with the student's words. The session is saved after "
     "every turn."],
    ["Evidence", "Walkthrough (Section 4.11), steps 0–7 (main flow), 8–14 (A2, A3, A5) and 15–20 (A4)."],
], [1.3, 5.2], "Fully described main use case (UC-11)", size=9)


APPX[0], APPX[1] = "A2", 0
H("Appendix 2: Walkthrough Trace", 1)
P("This appendix gives every turn of the walkthrough in Section 4.11, as produced by running the prototype with "
  "scripted agent replies (Table A2.1), and the resulting objective records (Table A2.2).")
landscape()
TABLE(["#", "LO", "Student says", "Tutor (agent: message)", "Stage after", "SOLO estimate (movement)",
       "Support / ceiling", "Outcome / control event", "Cases"],
      wt_rows, [0.3, 0.4, 1.5, 2.75, 0.85, 1.1, 1.0, 0.85, 0.6],
      "Turn-by-turn walkthrough (produced by running the prototype with scripted agent replies)", size=7)
portrait()
recs = []
for r in state.objective_records:
    recs.append([r.design_id, OUTCOME[r.status.value], r.entry_solo, r.exit_solo,
                 {"gap_surfaced": "gap surfaced", "round_cap": "round limit"}.get(r.elenchus_exit.value, "—") if r.elenchus_exit else "—",
                 " → ".join(r.support_sequence) or "—", " → ".join(r.ceiling_sequence) or "—",
                 "yes" if r.transfer_asked else "no", ", ".join(r.misconceptions) or "—"])
TABLE(["LO", "Status", "Entry estimate", "Exit estimate", "Elenchus exit", "Support used", "Ceiling applied",
       "Transfer", "Misconceptions"], recs, [0.35, 0.85, 0.75, 0.8, 0.7, 0.95, 0.95, 0.45, 0.7],
      "Objective records at the end of the walkthrough", size=8)
c = state
P(f"Session counters at the end: leak drafts regenerated = {c.leak_attempts}, fallbacks = {c.leak_hard_blocks}, "
  f"mastery claims refused = {c.gate_rejections}, support skips = {c.support_violations}, "
  f"fade violations = {c.fade_violations}. Closing message: \"{c.history[-1].content}\"", size=10)

APPX[0], APPX[1] = "A3", 0
H("Appendix 3: Enforcement and Traceability", 1)
P("This appendix shows how strongly each rule of every design decision in Table 4.2 is enforced (Table A3.1), "
  "and traces each part of the design to what realises it and to the evidence for it (Table A3.2).")
REALISED = {
    "DD1": "Facilitator instructions; orchestrator moves on once a hypothesis is captured",
    "DD2": "Diagnostician instructions with the SOLO rubric and misconception bank; learner model records each estimate",
    "DD3": "Curator instructions; orchestrator limits on the support level; round limit",
    "DD4": "Three role-specific agents on one shared LLM; orchestrator selects one agent per stage",
    "DD5": "Answer-leakage guard: agent self-check and protected-answer check, one regeneration, fixed fallback",
    "DD6": "Student interface, objective outcomes, data export; pre-test, post-test and questionnaire",
    "DD7": "Feedback cards, milestones, session summary and My Progress page, all from fixed text",
}
ENFORCED = {
    "DD1": "One question per turn and question categories: prompt. Moving on after a hypothesis, and never "
           "giving the Facilitator the answer: code. Drift flagged and counted: bounded.",
    "DD2": "SOLO level of each response: prompt (an LLM estimate). Recording and movement: code. A "
           "misconception recorded only with the student's own words: bounded.",
    "DD3": "Support level: prompt. First move a hint, rise one level at most, step down after improvement: "
           "bounded. Round limit of three: code. Worked example on different values: prompt.",
    "DD4": "One agent per stage, stage changes and per-objective reset: code.",
    "DD5": "Protected-answer check, regeneration and fallback: code. Detecting paraphrased answers: prompt.",
    "DD6": "Mastered and closed-at-limit kept apart: code. Score change and usability: instrument.",
    "DD7": "Fixed feedback text, no LLM; mastered and parked shown apart; no reward for speed: code.",
}
rows = [[d.id, ENFORCED[d.id], d.claim_limit] for d in DESIGN_MATRIX]
TABLE(["ID", "Enforcement of each rule", "What it does not show"],
      rows, [0.5, 4.0, 2.0], "Enforcement of the design decisions in Table 4.2", size=8.5)
TR = [
    ["FR1 Accounts and secure login", "Sign-up with consent; hashed passwords", "Code", "Automated test"],
    ["FR2 Start a session within a topic; switch", "Topic picker; new-session and change-topic controls", "Code", "Automated test; screens"],
    ["FR3 Socratic questions, not direct answers", "Agent instructions; answer-leakage guard", "Prompt + Code", "Automated tests; pilot rubric"],
    ["FR4 Estimate the SOLO level of each response", "Diagnostician and Curator instructions; learner model", "Prompt (level), Code (recording, movement)", "Automated tests; human rating in the pilot"],
    ["FR5 Identify misconceptions against the bank", "Diagnostician instructions with the misconception bank", "Bounded", "Automated tests; pilot transcripts"],
    ["FR6 Record mastered vs closed at the limit", "Objective outcome in the learner model", "Code", "Automated tests; walkthrough"],
    ["FR7 Bounded support; reduce it after improvement", "Orchestrator limits on the Curator's support level", "Bounded", "Automated tests; walkthrough"],
    ["FR8 Coordinate agents from responses and state", "Orchestrator", "Code", "Automated tests; walkthrough"],
    ["FR9 Maintain context; prevent drift", "Dialogue history given to every agent; drift check", "Bounded", "Automated test; pilot transcripts"],
    ["FR10 Prevent direct answers", "Answer-leakage guard with regeneration and fallback", "Code + Prompt", "Automated tests; adversarial scenarios"],
    ["FR11 Track learning progress", "Learner model; progress display", "Code", "Automated tests; screens"],
    ["FR12 Save session data for the teacher dashboard", "Database; Teacher Dashboard", "Code", "Automated tests; screens"],
    ["FR13 Student progress, motivating feedback, retry", "Feedback cards; milestones; My Progress page", "Code", "Automated tests; screens"],
    ["NFR Privacy", "Hashed passwords; participant codes; export without names or IDs", "Code", "Automated tests"],
    ["NFR Reliability", "Repair of malformed replies, retries, round limits, fallbacks", "Code", "Automated tests"],
    ["NFR Performance", "Response time and token use recorded for every model call", "Code (measurement)", "Pilot"],
    ["NFR Usability", "Chat, diagnostic panel, progress page", "Instrument", "Questionnaire C1–C5, D5–D7"],
    ["NFR Accuracy", "Guard; answer given only to the Curator", "Code + Prompt", "Automated test; pilot leakage rate"],
    ["NFR Adaptability", "Support limits follow the SOLO movement", "Bounded", "Automated tests"],
    ["Table 4.1 Learning objectives LO1–LO11", "Topic catalogue", "Code", "Automated test"],
    ["Figure 4.2 Orchestration state machine", "Orchestrator stages, transitions and objective outcomes", "Code", "Automated tests; walkthrough"],
    ["Figure 4.3 Student interaction workflow", "Interface and orchestrator", "Code", "Walkthrough; screens"],
    ["Section 4.5.2 Leak detection and regeneration", "Answer-leakage guard", "Code", "Automated tests"],
    ["DD1–DD7 Design decisions matrix", "See Table A3.1", "See Table A3.1", "Automated check that every row is tested"],
]
TABLE(["Design artefact", "Realised by", "Enforcement", "Evidence"], TR, [2.0, 2.15, 1.15, 1.2],
      "Traceability of the design to the implementation and the evidence", size=8.5)

format_to_guidelines(doc)
doc.save(OUT)
print("saved", OUT, "tables:", TABLE_NO[0], "figures:", FIG_NO[0], "tests:", RESULTS)
