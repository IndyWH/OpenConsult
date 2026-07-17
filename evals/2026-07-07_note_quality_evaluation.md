# Note-quality evaluation — Phase 2 SOAP note drafting

**Date:** 2026-07-07
**Component:** note generator (`app/notes.py`), MedGemma 27B Q4_K_M via
Ollama, temperature 0, seed 42, structured JSON with per-claim transcript
citations. Inputs are the ten mock scripts used as stand-in diarised
transcripts (confidence 1.0 — the ASR-confidence flagging path is
exercised separately in the audio pipeline test).
**Harness:** `scripts/evaluate_notes.py`. Raw data: `evals/note_results.json`.

## Question under test

Do generated SOAP notes (a) capture the clinical content that each
script's marking scheme ("Expected clinical content") says a good note
must contain, (b) cite valid transcript turns for every claim, and (c)
avoid asserting things the transcript doesn't support?

## Method

- Mechanical checks in code: citation validity (every claim's turns must
  exist in the transcript; invalid ones stripped and the claim marked
  uncited).
- Clinical coverage and discrepancies: an LLM judge compares each note
  against its script's marking scheme, scoring each expected point
  covered/missed and listing discrepancies (things the note asserts that
  are wrong — an omission is a miss, not a discrepancy).
- **Judge = the same MedGemma model that wrote the notes.** A stated
  limitation: self-judging underestimates errors that stem from the
  model's own blind spots. The project owner (a doctor) reviews the
  judge's output; known seed examples below were found by human reading.

## Seed findings (human-spotted before the run)

Two fidelity slips found by eye in the first script-03 note, of the class
the discrepancy check must catch:

- **Invented dose:** the script says "atorvastatin, one at night" (no dose
  stated); the note wrote "Atorvastatin 1mg nocte" — reading "one" as a
  milligram dose. (Also clinically implausible: atorvastatin starts at
  10–20 mg.)
- **Inverted laterality-class finding:** the script has monofilament
  sensation reduced in the toes but intact at the ankle; the note wrote
  "reduced sensation to monofilament in toes and ankle".

## Results

**Mechanical grounding: 263/263 claims across all ten notes cite valid
transcript turns** (code-enforced, reliable). Clinical coverage per the
LLM judge, transcript-grounded run:

| Script | Claims | Cited | Coverage | Discrepancies (judge) |
|---|---|---|---|---|
| 01_chest_pain_en.md | 26 | 26/26 | 18/18 (100%) | 0 |
| 02_febrile_child_en.md | 32 | 32/32 | 24/26 (92%) | 0 |
| 03_diabetes_review_en.md | 29 | 29/29 | 31/33 (94%) | 0 |
| 04_asthma_en.md | 26 | 26/26 | 20/22 (91%) | 0 |
| 05_epigastric_pain_en.md | 29 | 29/29 | 23/26 (88%) | 0 |
| 06_tia_funny_turn_en.md | 22 | 22/22 | 4/4 (100%) | 0 |
| 07_gi_bleed_en.md | 24 | 24/24 | 16/19 (84%) | 0 |
| 08_pulmonary_embolism_en.md | 26 | 26/26 | 21/22 (95%) | 0 |
| 09_septic_child_en.md | 28 | 28/28 | 22/22 (100%) | 0 |
| 10_testicular_torsion_en.md | 21 | 21/21 | 12/14 (86%) | 0 |

Mean coverage ~93% (first judge run: ~85% — see below on why the numbers
carry uncertainty). Missed items cluster in safety-netting details and
secondary negatives; no note missed its primary diagnosis or urgent plan.

### The judge-reliability finding (read before trusting the table)

The discrepancy column is NOT evidence of zero errors. Two judge
calibrations were run, and both failed in opposite directions against
known ground truth:

- **Judge v1** (marking scheme only): 17 discrepancies reported, of which
  15 were false positives — it treated correct note detail drawn from the
  transcript as "invented" because the judge had never seen the
  transcript. It did catch both seeded real errors.
- **Judge v2** (transcript provided, told extra transcript-supported
  detail is fine): 0 discrepancies — including MISSING both seeded real
  errors it was pointed at in v1 (the invented "atorvastatin 1mg" dose
  and the inverted monofilament finding, both still present in the
  deterministic notes). Its expected-item enumeration also proved
  unstable (script 06: 14 items in v1, 4 in v2 — which is why coverage
  percentages between runs differ).

Conclusion: same-model LLM judging is adequate for coarse coverage
scoring but demonstrably unreliable for fine-grained fidelity in either
direction. The two confirmed distortions in ten notes remain the
human-found seed findings. This strengthens the case for the deferred
end-of-project fidelity review being a human review, possibly assisted by
a *different* model.

## Audio-path smoke test (disposable TTS sample)

A 4.6-minute two-voice TTS rendering of script 04 (en-GB male doctor /
female patient; `scripts/make_tts_sample.py`; explicitly NOT part of the
permanent test set) run through the full pipeline:

- **Wall clock:** 17.1 s for 275.9 s of audio (~16× real time), inside the
  plan's "a minute or two" budget with a large margin.
- **VRAM sequencing verified:** MedGemma unloaded (17 GB freed), WhisperX
  large-v3 + pyannote 3.1 loaded, used, and released; MedGemma reloads on
  the next note-generation call.
- **Diarisation + roles:** 27 ASR turns against the script's 30 (adjacent
  same-speaker merges only); role attribution correct on 27/27 aligned
  turns with the first-speaker-is-Doctor heuristic.
- **Confidence:** all turns ~0.8 (clean synthetic voices); no turn below
  the 0.6 flag threshold — the flagging path therefore awaits real
  recordings for a meaningful test.

Dependency notes for reproducibility (all encoded in pyproject.toml):
ctranslate2 ≥4.6 override (4.4 fails on WSL2's glibc), pyannote pinned to
3.4 with whisperx's Silero VAD (whisperx 3.8/pyannote 4 route requires the
separately-gated `speaker-diarization-community-1` model — switchable
later via `DIARIZATION_MODEL` after accepting its licence), torch 2.8
`weights_only` workaround for pyannote 3.4 checkpoints.

## Limitations

- Stand-in transcripts are clean scripts, not ASR output; real-recording
  evaluation follows the weekend's recordings.
- Same-model judging is unreliable for fidelity (demonstrated above);
  coverage percentages carry enumeration noise between judge runs
  (85–93% band). Treat coverage as approximate and discrepancy counts as
  untrustworthy; the ground truth for fidelity is human review.
- The confidence-flagging path (⚠ on load-bearing claims citing
  low-confidence turns) is only exercised by the TTS audio test here;
  real accented audio is the true test.
- n=1 per script, deterministic settings.

## Addendum 2026-07-17 — fidelity specimen 4: wholesale fabrication on an
## empty transcript, and the grounding gate it forced

The fourth and most severe fidelity specimen, found in live use
(consultation #78, 2026-07-15). The transcript was a mic check — one turn,
"Check one, two, three. Check one, two, three." — yet the generator
produced a complete, internally coherent **fabricated angina
consultation**: exertional chest pain radiating to the left arm, 2-month
timeline, 20-pack-year ex-smoker, father's MI at 55, Ramipril 5mg,
Atorvastatin 20mg, BP 150/95, "possible angina", ECG-then-cardiology plan.

Mechanism, established by investigation:

- **Not prompt regurgitation**: `NOTE_PROMPT` contains no few-shot example.
- **Not context leakage**: `draft_note` sends a single stateless call
  containing only this consultation's turns.
- **Not a Regenerate-path quirk**: fresh generation and Regenerate share
  the same `draft_note` call; note v1 (fresh) and v2 (Regenerate) were
  byte-identical (temperature 0, seed 42). This is pure confabulation:
  given no clinical content, MedGemma writes the archetypal GP
  consultation, and chest pain is the archetype.
- **Citation validation worked** — all 12 claims came back `uncited` —
  but nothing consumed that signal; the note reached the review page with
  only per-claim "(uncited — verify manually)" tags, and Approve was
  available.

Fix (2026-07-17): the note pipeline now applies the same demotion rule as
the RAG layer. `validate_and_gate` (`app/notes.py`) counts validly-cited
claims after citation validation; when fewer than
`NOTE_MIN_CITED_FRACTION` (default 0.5) of claims cite a real turn — or
the draft has no claims — the note is replaced by a refusal
(`refusal: true` + reason + claim counts) and the fabricated draft is
discarded. The review page renders the refusal ("insufficient clinical
content to draft a note") instead of a draft and hides Approve/Copy;
the approve API independently returns 409 for a refusal note, so approval
is impossible client- and server-side. Regenerate remains available for
the correct-transcript-then-retry loop.

Verification: regenerating #78 post-fix produced note v3 = refusal (the
model fabricated 18 claims that run; 0 cited; all suppressed). Tests in
`tests/test_note_gating.py`: the #78 shape → refusal; sparse-but-real
transcripts stay notes; the 50% threshold boundary; refusal plain-text
serialisation; approve → 409; and an Ollama-gated end-to-end regression
(real model, mic-check transcript → refusal).

Classification note: specimens 1–3 were distortions of real content; this
one is fabrication of the entire encounter — caught by citation
validation, previously unblocked by the UI. The gate turns the existing
detection into an enforcement.

## Reproduce

```bash
uv run python scripts/evaluate_notes.py
uv run python scripts/make_tts_sample.py   # disposable audio sample
```
