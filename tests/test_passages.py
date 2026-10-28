"""A document into passages (spec 15.12, ruling 5 and the detail The
passages and the search; 6.5): HTML by headings with the trail, PDF and
plain text by blank lines, 350 and 40 words, never a cut inside a
sentence. Made-up pages; no document of any publisher."""

import pytest

from openconsult.guidelines import passages
from openconsult.guidelines.passages import MAX_WORDS, MIN_WORDS, Unreadable, cut, read_document, sniff_kind, title_from_line
from openconsult.guidelines.texts import TRAIL_JOINT, passage_text, search_text, source_line


def sentence(n: int, words: int = 10) -> str:
    return " ".join(f"Word{n}x{i}" for i in range(words - 1)) + f" end{n}."


def paragraph(words: int, start: int = 0) -> str:
    """About `words` words in sentences of ten, each ending with a full stop."""
    return " ".join(sentence(start + i) for i in range(words // 10))


PAGE = f"""<!DOCTYPE html>
<html><head><title>Overview | Made-up guideline: a made-up condition | Guidance | Made-up body</title></head>
<body>
<nav><p>Skip to content. {paragraph(50)}</p></nav>
<div class="chapter">
<h2>On this page</h2>
<p>Intro paragraph before any real heading. {paragraph(50, 100)}</p>
<h2>Recommendations</h2>
<p>{paragraph(60, 200)}</p>
<h3>Assessment</h3>
<p>Offer the following if:</p>
<ul><li>first bullet with words</li><li>second bullet <em>with</em> words<ul><li>nested words</li></ul></li></ul>
<p>{paragraph(50, 300)}</p>
<h4>Tests</h4>
<p>{paragraph(50, 400)}</p>
<h3>Treatment</h3>
<p>Twenty words only here, a small section that should join the next one under the same parent heading. Done.</p>
<h3>Review</h3>
<p>{paragraph(60, 500)}</p>
<aside><p>{paragraph(50, 600)} an aside that must be dropped</p></aside>
<h2>Context</h2>
<p>{paragraph(400, 700)}</p>
<p>{paragraph(300, 800)}</p>
<p>{paragraph(300, 900)}</p>
<h3>Last</h3>
<p>A last small section of a dozen words that joins the one before it.</p>
</div>
<footer><p>{paragraph(50, 999)} footer words</p></footer>
</body></html>"""


def test_ruling_5_6_5_html_is_split_by_headings_into_passages_with_their_trails():
    document = read_document("made.html", PAGE.encode())
    assert document.kind == "html"
    assert title_from_line(document.title_line, "html") == "Made-up guideline: a made-up condition"
    assert title_from_line("No separators here", "html") == "No separators here"
    trails = [s.trail for s in document.sections]
    assert trails[0] == [] and ["Recommendations"] in trails and ["Recommendations", "Assessment"] in trails
    assert ["Recommendations", "Assessment", "Tests"] in trails and ["Context", "Last"] in trails
    assert "On this page" not in str(trails)
    assessment = next(s for s in document.sections if s.trail == ["Recommendations", "Assessment"])
    # The stem and its bullets are one unit; the nested item's words stay with its item.
    assert assessment.blocks[0] == "Offer the following if:\n- first bullet with words\n- second bullet with words nested words"
    whole = "\n".join(b for s in document.sections for b in s.blocks)
    assert "Skip to content" not in whole and "footer words" not in whole and "an aside" not in whole and "Word0x0" not in whole
    found = cut(document)
    assert all(MIN_WORDS <= c.words <= MAX_WORDS for c in found), [c.words for c in found]
    assert any(c.trail == TRAIL_JOINT.join(["Recommendations", "Assessment"]) for c in found)
    assert found[0].trail == "" and found[0].text.startswith("Intro paragraph")


def test_ruling_5_350_and_40_words_a_small_section_joins_the_next_and_a_long_one_splits_at_a_sentence_end():
    found = cut(read_document("made.html", PAGE.encode()))
    by_trail = {}
    for c in found:
        by_trail.setdefault(c.trail, []).append(c)
    # The 20-word Treatment joins Review under the same parent; the trail is the later section's.
    assert TRAIL_JOINT.join(["Recommendations", "Treatment"]) not in by_trail
    review = by_trail[TRAIL_JOINT.join(["Recommendations", "Review"])]
    assert len(review) == 1 and "Twenty words only here" in review[0].text and "Word500x0" in review[0].text
    # The 1,000-word Context section splits at paragraph ends; the 400-word paragraph at a sentence end into 350 and 50.
    context = by_trail["Context"]
    assert len(context) == 4 and all(c.words <= MAX_WORDS for c in context)
    assert context[0].words == MAX_WORDS and context[0].text.endswith("end734.") and context[1].text.startswith("Word735x0")
    assert context[1].words == 50 and context[2].text == paragraph(300, 800) and context[3].text.startswith(paragraph(300, 900)[:20])
    # The last dozen-word subsection joins its parent section before it, and does not stand alone.
    assert "Context" + TRAIL_JOINT + "Last" not in by_trail and "A last small section" in context[3].text and context[3].words == 314
    # A small section whose next is under another parent does not join it, and stays as it is.
    page = "<html><body><h2>A</h2><h3>Sub</h3><p>short words here</p><h2>B</h2><p>" + paragraph(60) + "</p></body></html>"
    two = cut(read_document("x.html", page.encode()))
    assert [(c.trail, c.words) for c in two] == [("A" + TRAIL_JOINT + "Sub", 3), ("B", 60)]
    # Two small sections under one parent join, and the later heading names the passage.
    page = "<html><body><h2>A</h2><p>short words here</p><h2>B</h2><p>" + paragraph(60) + "</p></body></html>"
    one = cut(read_document("x.html", page.encode()))
    assert [(c.trail, c.words) for c in one] == [("B", 63)] and one[0].text.startswith("short words here")
    assert passages.SENTENCE_END.split("First one. second stays. Third One.") == ["First one. second stays.", "Third One."]


def made_pdf(pages: list[str]) -> bytes:
    """A small PDF by hand: one text line per page, Helvetica."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None]
    kids = []
    for text in pages:
        page_n, content_n = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_n} 0 R")
        stream = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET"
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_n} 0 R "
                       f"/Resources << /Font << /F1 {len(pages) * 2 + 3} 0 R >> >> >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_ruling_5_a_pdf_and_a_plain_text_file_split_at_blank_lines_in_reading_order():
    first, second = paragraph(50), paragraph(50, 100)
    pdf = read_document("made.pdf", made_pdf([first, second]))
    assert pdf.kind == "pdf" and pdf.title_line == first and [s.trail for s in pdf.sections] == [[]]
    found = cut(pdf)
    assert len(found) == 1 and found[0].trail == "" and found[0].text.index("Word0x0") < found[0].text.index("Word100x0")
    text = f"A made title line\n\n{first}\n\n\n{second}\n".encode()
    plain = read_document("made.txt", text)
    assert plain.kind == "text" and plain.title_line == "A made title line" and plain.sections[0].blocks[0] == "A made title line"
    assert len(plain.sections[0].blocks) == 3 and title_from_line(plain.title_line, "text") == "A made title line"
    # The kind is sniffed from the bytes: a .txt that begins %PDF- is a PDF; an unknown kind is refused.
    assert sniff_kind("odd.txt", b"%PDF-1.4 ...") == "pdf" and sniff_kind("odd.txt", b"<!DOCTYPE html>") == "html"
    assert sniff_kind("notes.md", b"plain") == "text" and sniff_kind("x.HTM", b"x") == "html"
    with pytest.raises(Unreadable):
        sniff_kind("letter.docx", b"PK...")
    with pytest.raises(Unreadable):
        read_document("broken.pdf", b"%PDF-1.4 but nothing else")
    assert cut(read_document("empty.txt", b"\n\n")) == []
    # The two forms (v1's, byte for byte) and the source line.
    assert search_text("Made-up A") == "task: search result | query: Made-up A"
    assert source_line("T", "") == "T" and source_line("T", "H1" + TRAIL_JOINT + "H2") == "T: H1" + TRAIL_JOINT + "H2"
    assert passage_text("T", "H", "words") == "title: T: H | text: words"
