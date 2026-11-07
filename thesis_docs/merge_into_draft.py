"""
Replaces Chapter 4 in the full thesis draft with the generated, guideline-formatted chapter.

    <venv with docxcompose>/bin/python thesis_docs/merge_into_draft.py     (from code/)

Reads  ../writting/Socratic_Agent_Revised_Draft_2026-11-07.docx  and
       ../writting/Chapter 4 - System Design and Initial Results.docx
Writes the draft back in place (a backup is kept in thesis_docs/backups/draft.before-ch4-merge.docx).

docxcompose copies the chapter with its images, list numbering and landscape sections. Because
the draft's own styles win for shared style names (and its default font is Arial 11), every run
in the chapter is given explicit formatting first, so the chapter keeps the guideline layout.
Page setup and the running header are applied to the whole document, as the guidelines require:
A4, margins 25/20/20/20 mm, header with names, degree, year and page number (none on the title page).
"""
from __future__ import annotations

import copy
import shutil
from pathlib import Path

import docx
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docxcompose.composer import Composer

THESIS = Path(__file__).resolve().parents[2] / "writting"
DRAFT = THESIS / "Socratic_Agent_Revised_Draft_2026-11-07.docx"
CHAPTER = THESIS / "Chapter 4 - System Design and Initial Results.docx"
BACKUP = Path(__file__).resolve().parent / "backups" / "draft.before-ch4-merge.docx"  # kept out of writting/
HEADER_TEXT = "Sarah Abdalla Bakhit, Ryan Hasabelrasol, Afraa Abdalmonem | BSc in Information Technology | 2026 | "
A4_W, A4_H = Mm(210), Mm(297)
HEADING_SIZE = {"Heading 1": 14, "Heading 2": 14, "Heading 3": 12}


def _fonts(run, size: float | None = None, bold=None) -> None:
    run.font.name = "Times New Roman"
    run._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Times New Roman")
    run._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), "Times New Roman")
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def freeze_chapter_formatting(ch: docx.document.Document) -> None:
    """Make the chapter's look independent of the draft's styles."""
    for p in ch.paragraphs:
        style = p.style.name
        if style in HEADING_SIZE:
            for r in p.runs:
                _fonts(r, HEADING_SIZE[style], bold=True)
                r.font.color.rgb, r.italic = RGBColor(0, 0, 0), False
            pf = p.paragraph_format
            pf.space_before, pf.space_after, pf.keep_with_next, pf.line_spacing = Pt(12), Pt(6), True, 1.5
            if p.text.startswith("Chapter 4"):
                p.alignment, pf.page_break_before = WD_ALIGN_PARAGRAPH.CENTER, True
            continue
        for r in p.runs:
            _fonts(r, None if r.font.size else 12)
    for t in ch.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        _fonts(r, None if r.font.size else 10)
    for sect in ch.element.body.iter(qn("w:sectPr")):  # headers are defined once, on the merged document
        for tag in ("w:headerReference", "w:footerReference", "w:titlePg"):
            for el in sect.findall(qn(tag)):
                sect.remove(el)


def _index_of_title(body, startswith: str) -> int:
    for i, el in enumerate(body):
        if el.tag == qn("w:p"):
            text = "".join(t.text or "" for t in el.iter(qn("w:t"))).strip()
            if text.startswith(startswith):
                return i
    raise ValueError(startswith)


def _page_field(run) -> None:
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = text
        run._r.append(el)


def main() -> None:
    if not BACKUP.exists():  # keep the first backup: it is the draft before any merge
        shutil.copy2(DRAFT, BACKUP)
    ch = docx.Document(CHAPTER)
    freeze_chapter_formatting(ch)

    master = docx.Document(DRAFT)
    body = master.element.body
    start = _index_of_title(body, "Chapter 4:")
    end = _index_of_title(body, "Chapter 5")
    removed = body[start:end]
    for el in removed:
        body.remove(el)
    composer = Composer(master)
    composer.insert(start, ch)
    doc = composer.doc

    ch5 = next(p for p in doc.paragraphs if p.text.strip().startswith("Chapter 5"))
    ch5.paragraph_format.page_break_before = True

    # Chapter 4's appendices belong at the end of the thesis, after Chapter 5 (and the References).
    body = doc.element.body
    els = list(body)
    first = next((i for i, e in enumerate(els) if e.tag == qn("w:p")
                  and "".join(t.text or "" for t in e.iter(qn("w:t"))).strip().startswith("Appendix 1:")), None)
    if first is not None:
        ch5_i = els.index(ch5._p)
        block = els[first:ch5_i]
        end = body[-1]  # body-level section properties stay last
        for e in block:
            end.addprevious(e)
        print(f"moved {len(block)} appendix elements to the end of the thesis")

    for pg in doc.element.body.iter(qn("w:pgNumType")):  # sequential page numbers throughout
        pg.attrib.pop(qn("w:start"), None)
    for s in doc.sections:
        landscape = s.page_width > s.page_height
        s.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
        s.page_width, s.page_height = (A4_H, A4_W) if landscape else (A4_W, A4_H)
        s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Mm(25), Mm(20), Mm(20), Mm(20)
        s.header_distance = Mm(10)
    first = doc.sections[0]
    first.different_first_page_header_footer = True  # the title page carries no header or number
    first.header.is_linked_to_previous = False
    hp = first.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = hp.add_run(HEADER_TEXT)
    _fonts(run, 10)
    num = hp.add_run()
    _fonts(num, 10)
    _page_field(num)
    for s in doc.sections[1:]:
        s.header.is_linked_to_previous = True

    doc.save(DRAFT)
    print(f"replaced {len(removed)} body elements of the old Chapter 4; wrote {DRAFT.name}; backup {BACKUP.name}")


if __name__ == "__main__":
    main()
