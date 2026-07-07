from app.chunking import MAX_WORDS, chunk_html

SAMPLE = """
<div class="chapter">
<h2>Recommendations</h2>
<h3>Assessment</h3>
<p>Take a focused history in everyone presenting with chest pain, covering
site, onset, character, radiation, associated symptoms, timing, exacerbating
and relieving factors, and severity, together with cardiovascular risk
factors such as smoking, hypertension, diabetes, dyslipidaemia and family
history of premature coronary artery disease in a first-degree relative.</p>
<p>Offer aspirin if:</p>
<ul><li>ACS is suspected</li><li>no allergy is documented</li></ul>
<h3>Long section</h3>
<p>""" + " ".join(
    f"Sentence number {i} contains several useful clinical words." for i in range(120)
) + """</p>
</div>
"""


def test_chunks_carry_heading_trail():
    chunks = chunk_html(SAMPLE, "Test guideline")
    assert all(c.section_path.startswith("Test guideline") for c in chunks)
    assert any("Assessment" in c.section_path for c in chunks)


def test_list_items_stay_with_their_stem():
    chunks = chunk_html(SAMPLE, "Test guideline")
    aspirin = next(c for c in chunks if "aspirin" in c.text)
    assert "ACS is suspected" in aspirin.text  # bullet and stem in one chunk


def test_long_sections_split_at_sentence_boundaries():
    chunks = chunk_html(SAMPLE, "Test guideline")
    long_chunks = [c for c in chunks if "Sentence number" in c.text]
    assert len(long_chunks) > 1  # it did split
    for c in long_chunks:
        assert c.word_count <= MAX_WORDS + 20
        assert c.text.rstrip().endswith("."), "chunk must not end mid-sentence"
