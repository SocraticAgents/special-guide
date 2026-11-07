"""
Formats the whole thesis draft to the Research Office writing guidelines and completes its structure.

    python3 thesis_docs/format_draft.py        (from code/; run after merge_into_draft.py; needs LibreOffice)

What it does (Chapter 4 is already formatted by build_chapter4.py and is left alone except captions):
  - citations: normalises malformed Harvard citations (references.CITATION_FIXES);
  - structure: chapter titles, x.y and x.y.z headings as Heading 1/2/3 (14/14/12 pt bold); 4th-level
    headings in 2.2.5 become divisions A-D (guidelines: never beyond three levels); stray numbering fixed;
  - captions: missing captions added (Tables 2.1, 2.2, 5.1-5.5; Figure 2.1) with a reference in the text;
    table captions above tables, figure captions below; bold, centred, 12 pt; styles "Table Caption" and
    "Figure Caption" so Word can rebuild the lists;
  - body: Times New Roman 12, justified, 1.5 spacing, blocked paragraphs separated by a blank line;
    tables 10 pt; empty spacer paragraphs removed; every chapter and front-matter list on a new page;
  - front matter: Table of Contents, List of Tables and List of Figures filled as Word fields whose
    current results carry page numbers measured from a LibreOffice render (Word can update them);
  - References: a Harvard list of every cited source found in references.ENTRIES; unmatched citations
    are reported, not invented.
The file is rewritten in place; a backup of the input is kept in thesis_docs/backups/draft.before-format.docx.
"""
from __future__ import annotations

import copy
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import docx
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph

sys.path.insert(0, str(Path(__file__).parent))
from references import CITATION_FIXES, ENTRIES, KEY  # noqa: E402

THESIS = Path(__file__).resolve().parents[2] / "writting"
DRAFT = THESIS / "Socratic_Agent_Revised_Draft_2026-11-07.docx"
BACKUP = Path(__file__).resolve().parent / "backups" / "draft.before-format.docx"  # kept out of writting/
TEXT_W = Mm(165)  # A4 width minus 25 + 20 mm margins
BLACK = RGBColor(0, 0, 0)
W = qn


# ------------------------------------------------------------------ small helpers
def body_paras(doc):
    return [Paragraph(el, doc._body) for el in doc.element.body if el.tag == W("w:p")]


def text_of(el) -> str:
    return "".join(t.text or "" for t in el.iter(W("w:t")))


def set_text(p: Paragraph, text: str) -> None:
    if not p.runs:
        p.add_run(text)
        return
    p.runs[0].text = text
    for r in p.runs[1:]:
        r.text = ""


def replace_in(p: Paragraph, old: str, new: str) -> bool:
    if old not in p.text:
        return False
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new)
            return True
    set_text(p, p.text.replace(old, new))  # spans runs: keep the first run's formatting
    return True


def fmt_run(r, size=12, bold=None, italic=None):
    r.font.name = "Times New Roman"
    rf = r._r.get_or_add_rPr().get_or_add_rFonts()
    for k in ("w:eastAsia", "w:cs", "w:hAnsi", "w:ascii"):
        rf.set(qn(k), "Times New Roman")
    r.font.size = Pt(size)
    r.font.color.rgb = BLACK
    if bold is not None:
        r.bold = bold
    if italic is not None:
        r.italic = italic


PARENT = []  # the document body, set in main(): paragraphs need it to resolve styles


def new_para(anchor_el, text="", before=True, bold=False, italic=False):
    el = OxmlElement("w:p")
    (anchor_el.addprevious if before else anchor_el.addnext)(el)
    p = Paragraph(el, PARENT[0] if PARENT else None)
    r = p.add_run(text)
    fmt_run(r, 12, bold=bold, italic=italic)
    return p


def has(el, tag) -> bool:
    return el.find(".//" + W(tag)) is not None


def is_page_break_only(el) -> bool:
    return any(br.get(W("w:type")) == "page" for br in el.iter(W("w:br"))) and not text_of(el).strip()


def ensure_style(doc, name):
    if name not in [s.name for s in doc.styles]:
        st = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = doc.styles["Normal"]
        st.font.name, st.font.size, st.font.bold = "Times New Roman", Pt(12), True
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return doc.styles[name]


def heading_style(doc, level):
    st = doc.styles[f"Heading {level}"]
    st.font.name, st.font.bold, st.font.color.rgb = "Times New Roman", True, BLACK
    st.font.size = Pt(14 if level < 3 else 12)
    return st


# ------------------------------------------------------------------ the pass
def appendix_els(els):
    """Chapter 4's appendices, moved to the end of the thesis: already formatted, left as they are."""
    first = next((i for i, e in enumerate(els) if e.tag == W("w:p") and re.match(r"^Appendix \d+:", text_of(e).strip())), None)
    return set(els[first:]) if first is not None else set()


def locate(doc):
    els = list(doc.element.body)
    idx = {k: next(i for i, e in enumerate(els)
                   if e.tag == W("w:p") and text_of(e).strip().lower().startswith(k.lower()))
           for k in ("Abstract", "Table of contents", "List of tables", "List of figures", "Chapter 1",
                     "Chapter 4:", "Chapter 5")}
    return els, idx


def format_draft(doc, stats):
    els, idx = locate(doc)
    ch4_els = set(els[idx["Chapter 4:"]:idx["Chapter 5"]]) | appendix_els(els)
    title_page = set(els[:idx["Abstract"]])

    # 1. citations ------------------------------------------------------------
    for p in body_paras(doc):
        for old, new in CITATION_FIXES:
            if replace_in(p, old, new):
                stats.setdefault("citations", []).append(f"{old} -> {new}")

    # 1b. citation spacing and position, run by run (keeps bold/italic terms intact)
    cite = r"[A-Z][\w\-]+(?:, [A-Z]\.)?(?: et al\.?| and [A-Z][\w\-]+)?,\s*\d{4}[a-z]?"
    rules = [
        (re.compile(r"(\d{4}[a-z]?)\s+\)"), r"\1)"),                       # "2013 )" -> "2013)"
        (re.compile(r";\s*\)"), ")"),                                       # "2015;)" -> "2015)"
        (re.compile(r"([a-z,])\((?=" + cite + ")"), r"\1 ("),               # "learners(Wang" -> "learners (Wang"
        (re.compile(r"([a-z0-9])\.\s?\((" + cite + r"(?:;\s*" + cite + r")*)\)"), r"\1 (\2)."),  # ".(X, 2013)" -> " (X, 2013)."
    ]
    for p in body_paras(doc):
        if p._p in ch4_els:
            continue
        for r in p.runs:
            new = r.text
            for rx, rep in rules:
                new = rx.sub(rep, new)
            if new != r.text:
                stats.setdefault("cite_spacing", 0)
                stats["cite_spacing"] += 1
                r.text = new

    # 1c. title page must fit on one page: drop spacer lines between the date and "Supervised by"
    els_now = list(doc.element.body)
    date_i = next(i for i, e in enumerate(els_now) if e.tag == W("w:p") and text_of(e).strip() == "July 2026")
    sup_i = next(i for i, e in enumerate(els_now) if e.tag == W("w:p") and text_of(e).strip().startswith("Supervised by"))
    spacers = [e for e in els_now[date_i + 1:sup_i] if e.tag == W("w:p") and not text_of(e).strip()
               and not has(e, "w:drawing") and not has(e, "w:sectPr")]
    for e in spacers[:max(0, len(spacers) - 2)]:
        e.getparent().remove(e)
    abs_i = next(i for i, e in enumerate(els_now) if e.tag == W("w:p") and text_of(e).strip() == "Abstract")
    trailing = [e for e in els_now[sup_i:abs_i] if e.tag == W("w:p") and not text_of(e).strip()
                and not has(e, "w:drawing") and not has(e, "w:sectPr")]
    for e in trailing:  # blank lines after the names only push an empty second page
        e.getparent().remove(e)
    stats["title_spacers_removed"] = max(0, len(spacers) - 2) + len(trailing)

    # 2. structural text fixes ---------------------------------------------------
    for p in body_paras(doc):
        t = p.text.strip()
        if t.startswith(".5.6 Results"):
            replace_in(p, ".5.6", "5.6")
        if t.startswith("Chapter 5 :"):
            replace_in(p, "Chapter 5 :", "Chapter 5:")
        if re.match(r"^\d\.\d(\.\d)?\s.*:$", t):
            set_text(p, t.rstrip(":"))
        m = re.match(r"^2\.2\.5\.(\d)\s+(.*)$", t)
        if m:
            set_text(p, f"{'ABCD'[int(m.group(1)) - 1]}. {m.group(2).strip()}")
            stats.setdefault("divisions", []).append(p.text)
        for a, b in (("Table of contents", "Table of Contents"), ("List of tables", "List of Tables"),
                     ("List of figures", "List of Figures")):
            if t == a:
                set_text(p, b)
        if "summarised in Table 2.2" in p.text or ("Table 2.2" in p.text and "Educational Theories" in p.text):
            replace_in(p, "Table 2.2", "Table 2.3")
    for t in doc.tables:
        if t.rows[0].cells[0].text.strip() == "Peaper":
            set_text(t.rows[0].cells[0].paragraphs[0], "Paper")

    # 3. captions ------------------------------------------------------------------
    tcap, fcap = ensure_style(doc, "Table Caption"), ensure_style(doc, "Figure Caption")
    els = list(doc.element.body)

    def table_after(start_text):
        i = next(i for i, e in enumerate(els) if e.tag == W("w:p") and text_of(e).strip().startswith(start_text))
        return next(e for e in els[i:] if e.tag == W("w:tbl"))

    def add_table_caption(tbl, caption, ref_sentence):
        new_para(tbl, ref_sentence)
        new_para(tbl, caption)
        stats.setdefault("captions_added", []).append(caption)

    add_table_caption(table_after("2.3 Overview of Previous Studies"), "Table 2.1 Summary of previous studies",
                      "Table 2.1 summarises the previous studies reviewed in this section: their aim, approach, key "
                      "finding and limitation.")
    t22 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Paper")._tbl
    add_table_caption(t22, "Table 2.2 How each reviewed study was evaluated",
                      "Table 2.2 lists how each of the reviewed studies was evaluated.")
    for p in body_paras(doc):
        if p.text.strip().startswith("Table 2.2: How Educational Theories"):
            set_text(p, "Table 2.3 How Educational Theories Inform the Proposed System Design")
    lr = next(e for e in els if e.tag == W("w:p") and text_of(e).strip().startswith("2.4 Literature Review Map"))
    img = lr.getnext()
    while img is not None and not has(img, "w:drawing"):
        img = img.getnext()
    new_para(img, "Figure 2.1 presents the literature review map, which groups the reviewed work and shows how "
                  "it leads to the research gap.")
    new_para(img, "Figure 2.1 Literature Review Map", before=False)
    stats.setdefault("captions_added", []).append("Figure 2.1 Literature Review Map")
    ch5 = [
        ("5.5.2 Procedure", "Table 5.1 Procedure of a study session", "Table 5.1 sets out the procedure of each session."),
        ("In the end", "Table 5.2 Usability questionnaire statements", "The statements are listed in Table 5.2."),
        ("5.6.1 Agent and System Results", "Table 5.3 Agent and system evaluation results",
         "Table 5.3 will report the results of the agent-level and system-level evaluation."),
        ("5.6.2 Student Results", "Table 5.4 Pre-test and post-test scores", "Table 5.4 will report each participant's scores."),
        ("5.6.3 Questionnaire and Interpretation", "Table 5.5 Questionnaire results",
         "Table 5.5 will summarise the questionnaire responses."),
    ]
    for start, caption, ref in ch5:
        add_table_caption(table_after(start), caption, ref)

    # Table captions above their tables (Chapter 3 had them below).
    els = list(doc.element.body)
    for i, e in enumerate(els):
        if e.tag == W("w:tbl"):
            nxt = els[i + 1] if i + 1 < len(els) else None
            prev = els[i - 1]
            if (nxt is not None and nxt.tag == W("w:p") and re.match(r"^Table \d\.\d+ ", text_of(nxt).strip())
                    and not re.match(r"^Table \d\.\d+ ", text_of(prev).strip())):
                e.addprevious(nxt)

    # 4. headings, captions and body formatting --------------------------------------
    els, idx = locate(doc)
    ch4_els = set(els[idx["Chapter 4:"]:idx["Chapter 5"]]) | appendix_els(els)
    title_page = set(els[:idx["Abstract"]])
    h = {lvl: heading_style(doc, lvl) for lvl in (1, 2, 3)}
    for el in list(doc.element.body):
        if el.tag != W("w:p") or el in title_page:
            continue
        p = Paragraph(el, doc._body)
        t = p.text.strip()
        pf = p.paragraph_format
        cap = re.match(r"^(Table|Figure) (\d|A\d)\.(\d+)[.:]?\s+(.*)$", t)
        if cap and len(t) < 170 and not re.match(r"^(Table|Figure) \S+ (shows|lists|sets|summarises|presents|connects|details|will|takes|gives|extends|covers)\b", t):
            if cap.group(0) != f"{cap.group(1)} {cap.group(2)}.{cap.group(3)} {cap.group(4)}":
                set_text(p, f"{cap.group(1)} {cap.group(2)}.{cap.group(3)} {cap.group(4)}")
            p.style = tcap if cap.group(1) == "Table" else fcap
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                fmt_run(r, 12, bold=True, italic=False)
            pf.space_before, pf.space_after, pf.line_spacing = Pt(6), Pt(12), 1.0
            pf.keep_with_next = cap.group(1) == "Table"
            continue
        if el in ch4_els:
            continue
        if not t:  # spacer lines and manual page breaks: headings now start their own pages
            if not (has(el, "w:drawing") or has(el, "w:sectPr")):
                el.getparent().remove(el)
            continue
        level = None
        if t.startswith("Chapter ") and (p.style.name == "Title" or len(t) < 70):
            level = 1
        elif t in ("Abstract", "Table of Contents", "List of Tables", "List of Figures", "References") or re.match(r"^Appendix \d+:", t):
            level = 1
        elif re.match(r"^\d\.\d+\.\d+\s", t) and len(t) < 110:
            level = 3
        elif re.match(r"^\d\.\d+\s", t) and len(t) < 110:
            level = 2
        if level:
            p.style = h[level]
            for r in p.runs:
                fmt_run(r, 14 if level < 3 else 12, bold=True, italic=False)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
            pf.space_before, pf.space_after, pf.line_spacing, pf.keep_with_next = Pt(12), Pt(6), 1.5, True
            pf.page_break_before = level == 1
            pf.first_line_indent = Pt(0)
            continue
        if has(el, "w:drawing"):
            p.alignment, pf.keep_with_next = WD_ALIGN_PARAGRAPH.CENTER, True
            continue
        listed = (p._p.pPr is not None and p._p.pPr.find(W("w:numPr")) is not None) or t[:1] in "•-–"
        if p.alignment != WD_ALIGN_PARAGRAPH.CENTER:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.line_spacing, pf.widow_control, pf.space_before = 1.5, True, Pt(0)
        pf.space_after = Pt(6 if listed else 12)
        if not listed:
            pf.first_line_indent, pf.left_indent = Pt(0), None
        division = re.match(r"^[A-D]\. ", t) and t in stats.get("divisions", [])
        if division:
            pf.keep_with_next, p.alignment = True, WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            fmt_run(r, 12, bold=True if division else None)
    for el in doc.element.body.iter(W("w:contextualSpacing")):
        el.getparent().remove(el)

    for t in doc.tables:
        if t._tbl in ch4_els:
            continue
        for ri, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            if trPr.find(W("w:cantSplit")) is None:
                trPr.append(OxmlElement("w:cantSplit"))
            for c in row.cells:
                for p in c.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.line_spacing, p.paragraph_format.space_after = 1.0, Pt(0)
                    for r in p.runs:
                        fmt_run(r, 10, bold=True if ri == 0 else None)
        grid = t._tbl.tblGrid.findall(W("w:gridCol"))
        total = sum(int(g.get(W("w:w")) or 0) for g in grid)
        limit = int(TEXT_W.twips) if hasattr(TEXT_W, "twips") else int(165 / 25.4 * 1440)
        if total > limit:
            for g in grid:
                g.set(W("w:w"), str(int(int(g.get(W("w:w"))) * limit / total)))
            for row in t.rows:
                for c, g in zip(row.cells, grid):
                    c.width = int(int(g.get(W("w:w"))) * 635)
    for shape in doc.inline_shapes:
        if shape.width > TEXT_W:
            ratio = TEXT_W / shape.width
            shape.width, shape.height = int(shape.width * ratio), int(shape.height * ratio)


# ------------------------------------------------------------------ front matter, references
def citations_in(doc):
    texts = [p.text for p in doc.paragraphs] + [c.text for t in doc.tables for r in t.rows for c in r.cells]
    found = set()
    for t in texts:
        for m in re.finditer(r"\(([^()]*?\d{4}[^()]*)\)", t):
            for part in m.group(1).split(";"):
                mm = re.match(r"^\s*([A-Z][\w\-]+(?:, [A-Z]\.)?(?: and [A-Z][\w\-]+)?)(?: et al\.)?(?: and [A-Z][\w\-]+)?,\s*(\d{4})", part)
                if mm:
                    found.add((mm.group(1), mm.group(2)))
        for m in re.finditer(r"([A-Z][\w\-]+(?:, [A-Z]\.)?)(?: et al\.| and [A-Z][\w\-]+)? \((\d{4})\)", t):
            found.add((m.group(1), m.group(2)))
    keys, unmatched = set(), set()
    for name, year in found:
        k = KEY.get((name, year)) or KEY.get((name.split(" and ")[0].split(",")[0], year))
        if name.startswith("Li and Chang"):
            k = KEY[("Li and Chang", year)]
        (keys.add(k) if k else unmatched.add(f"{name}, {year}"))
    return keys, unmatched


def add_references(doc, stats):
    keys, unmatched = citations_in(doc)
    stats["references"], stats["unmatched"] = len(keys), sorted(unmatched)
    appendix = next((e for e in doc.element.body if e.tag == W("w:p") and re.match(r"^Appendix \d+:", text_of(e).strip())), None)
    last = appendix if appendix is not None else doc.element.body[-1]  # before the appendices, else at the end
    head = new_para(last, "References")
    head.style = heading_style(doc, 1)
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    head.paragraph_format.page_break_before = True
    for r in head.runs:
        fmt_run(r, 14, bold=True)
    for entry in sorted((ENTRIES[k] for k in keys), key=lambda e: e.lower()):
        p = new_para(last, entry)
        pf = p.paragraph_format
        pf.left_indent, pf.first_line_indent = Inches(0.5), Inches(-0.5)
        pf.line_spacing, pf.space_after = 1.5, Pt(6)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT


def field_list(doc, heading_text, instr, entries_by_level, stats_key, stats):
    """Replace everything between `heading_text` and the next level-1 heading with a TOC field."""
    els = list(doc.element.body)
    i = next(i for i, e in enumerate(els) if e.tag == W("w:p") and text_of(e).strip() == heading_text)
    j = i + 1
    while j < len(els) and not (els[j].tag == W("w:p") and Paragraph(els[j], doc._body).style.name == "Heading 1"):
        j += 1
    for e in els[i + 1:j]:
        if not has(e, "w:sectPr"):
            e.getparent().remove(e)
    anchor = els[j] if j < len(els) else doc.element.body[-1]
    paras = []
    for level, text in entries_by_level or [(1, "(no entries)")]:
        p = new_para(anchor, "")
        p.runs[0].text = text
        pf = p.paragraph_format
        pf.left_indent = Inches(0.3 * (level - 1))
        pf.line_spacing, pf.space_after = 1.5, Pt(0)
        pf.tab_stops.add_tab_stop(TEXT_W, WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = p.add_run("\t0")
        fmt_run(r, 12)
        if level == 1 and stats_key == "toc":
            p.runs[0].bold = True
        paras.append(p)
    # Wrap the entries in one field: begin + instruction + separate in the first, end in the last.
    first, lastp = paras[0], paras[-1]
    begin_r = OxmlElement("w:r"); fc = OxmlElement("w:fldChar"); fc.set(W("w:fldCharType"), "begin"); begin_r.append(fc)
    instr_r = OxmlElement("w:r"); it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr; instr_r.append(it)
    sep_r = OxmlElement("w:r"); fs = OxmlElement("w:fldChar"); fs.set(W("w:fldCharType"), "separate"); sep_r.append(fs)
    first_run = first._p.find(W("w:r"))
    for x in (begin_r, instr_r, sep_r):
        first_run.addprevious(x)
    end_r = OxmlElement("w:r"); fe = OxmlElement("w:fldChar"); fe.set(W("w:fldCharType"), "end"); end_r.append(fe)
    lastp._p.append(end_r)
    stats[stats_key] = len(paras)
    return paras


def build_front_lists(doc, stats):
    els, idx = locate(doc)
    headings, tables, figures = [], [], []
    started = False
    for el in doc.element.body:
        if el.tag != W("w:p"):
            continue
        p = Paragraph(el, doc._body)
        t = p.text.strip()
        if t == "Abstract":
            started = True
        if not started or not t:
            continue
        sn = p.style.name
        if sn in ("Heading 1", "Heading 2", "Heading 3") and t not in ("Table of Contents",):
            headings.append((int(sn[-1]), t))
        elif sn == "Table Caption":
            tables.append((1, t))
        elif sn == "Figure Caption":
            figures.append((1, t))
    toc = field_list(doc, "Table of Contents", ' TOC \\o "1-3" \\h \\z \\u ', headings, "toc", stats)
    lot = field_list(doc, "List of Tables", ' TOC \\h \\z \\t "Table Caption,1" ', tables, "tables", stats)
    lof = field_list(doc, "List of Figures", ' TOC \\h \\z \\t "Figure Caption,1" ', figures, "figures", stats)
    return toc + lot + lof, headings + tables + figures


def page_numbers(path: Path, targets):
    """Physical page (1-based) of each target text, searched in order after the front lists."""
    out = Path(tempfile.mkdtemp())
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out), str(path)],
                   check=True, capture_output=True)
    pdf = next(out.glob("*.pdf"))
    pages = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout.split("\f")
    norm = [re.sub(r"\s+", " ", pg) for pg in pages]
    # Pages with dot leaders are the contents/list pages: they mention every heading, so a heading is only
    # looked for there if it is one of the list headings themselves (each starts its own page).
    leader = [("....." in pg) for pg in norm]
    found, cursor, kind = [], 0, None
    for _, text in targets:
        key = re.sub(r"\s+", " ", text)[:60]
        this_kind = "table" if re.match(r"^Table \d", text) else "figure" if re.match(r"^Figure \d", text) else "heading"
        if this_kind != kind:  # each list (contents, tables, figures) is searched from the start
            cursor, kind = 0, this_kind
        hit = None
        for i in range(cursor, len(norm)):
            if leader[i] and not norm[i].split("| ")[-1].lstrip("0123456789 ").startswith(key):
                continue
            if key in norm[i]:
                hit = i
                break
        found.append(hit + 1 if hit is not None else 0)
        if hit is not None:
            cursor = hit
    return found


def main():
    if not BACKUP.exists():
        shutil.copy2(DRAFT, BACKUP)
    doc = docx.Document(DRAFT)
    PARENT.append(doc._body)
    stats = {}
    format_draft(doc, stats)
    add_references(doc, stats)
    entry_paras, targets = build_front_lists(doc, stats)
    doc.save(DRAFT)
    numbers = page_numbers(DRAFT, targets)
    for p, n in zip(entry_paras, numbers):
        tab_run = [r for r in p.runs if r.text.startswith("\t")][-1]
        tab_run.text = f"\t{n}" if n else "\t"
    doc.save(DRAFT)
    missing = [t for (_, t), n in zip(targets, numbers) if not n]
    print("captions added:", stats.get("captions_added"))
    print("divisions:", stats.get("divisions"))
    print("citations fixed:", len(stats.get("citations", [])), "| spacing/position fixes:", stats.get("cite_spacing"),
          "| title spacers removed:", stats.get("title_spacers_removed"))
    print("TOC entries:", stats.get("toc"), "| tables:", stats.get("tables"), "| figures:", stats.get("figures"))
    print("references:", stats.get("references"), "| unmatched citations:", stats.get("unmatched"))
    print("entries without a page number:", missing)


if __name__ == "__main__":
    main()
