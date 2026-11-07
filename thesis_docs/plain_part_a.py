"""One-off: plain wording for the outcome names in Part A (writting/Chapter 4.docx) and the redrawn Figure 4.2."""
from pathlib import Path

import docx
from PIL import Image

HERE = Path(__file__).parent
DOC = HERE.parents[1] / "writting" / "Chapter 4.docx"
d = docx.Document(DOC)
REPL = [
    ("Each objective ends in one of two recorded outcomes: MASTERED, when the mastery gate is passed, or "
     "CLOSED_AT_CAP, when the scaffolding round limit is reached first. Only the first counts as mastery.",
     "Each objective ends in one of two recorded outcomes: mastered, when the mastery gate is passed, or closed "
     "at the round limit, when the scaffolding round limit is reached first. Only the first counts as mastery."),
    ("The first case is recorded as MASTERED and the second as CLOSED_AT_CAP,",
     "The first case is recorded as mastered and the second as closed at the round limit (not mastered),"),
]
done = 0
for p in d.paragraphs:
    for a, b in REPL:
        if a in p.text:
            p.runs[0].text = p.text.replace(a, b)
            for r in p.runs[1:]:
                r.text = ""
            done += 1
assert done == 2, done
shape = d.inline_shapes[1]  # Figure 4.2
fig = HERE / "figures" / "fig_4_2_state_machine.png"
d.part.related_parts[shape._inline.graphic.graphicData.pic.blipFill.blip.embed]._blob = fig.read_bytes()
w, h = Image.open(fig).size
shape.height = int(shape.width * h / w)
d.save(DOC)
print("Part A: outcome names in plain words; Figure 4.2 replaced")
