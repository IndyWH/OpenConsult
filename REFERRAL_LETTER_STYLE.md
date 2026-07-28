# REFERRAL_LETTER_STYLE.md — the owner's clinical framework for referral letters

> **RECONSTRUCTION, 2026-07-28.** The original addendum (2026-07-24,
> written by the owner after reviewing the #66 letter) was lost — it
> existed only in Downloads and a deleted chat. Rebuilt from the
> implemented prompt and gates in `app/letters.py`, `tests/
> test_letters.py`, and HANDOVER's referral-letter sections. The
> framework is the owner's; this document restates it from what was
> built. Where this document and the code disagree, the code wins.

## The principle

**A real GP referral letter presents the evidence and lets the
specialist draw the conclusion.** The selection of facts carries the
differential; the letter must never name it. Concise, evidence-first,
well under a page, every sentence carrying clinical information — no
essay style, no sympathy padding, no repeated demographics.

## Structure (body paragraphs, in order)

1. **Opening** — who is being referred and the presenting problem
   stated as **symptoms, never a diagnosis**: "I would be grateful if
   you would see this 55-year-old man with a two-week history of
   exertional chest tightness." Add "urgently" only when the note's
   plan says so.
2. **History** — the positive and relevant negative points from the
   note: symptoms with duration and pattern, PMH, family history, drug
   history and allergies, relevant social history. Compressed,
   bullet-like prose.
3. **Examination findings** — as recorded in the note, nothing more.
   Omitted if none are recorded.
4. **Investigations** — results only if the note records them. A test
   arranged with no result reads exactly as arranged: "An ECG was
   arranged today." **Planned, performed and resulted are three
   different claims**; the letter uses the note's wording class (the
   #66 QA finding).
5. **Patient expectation** — one sentence, only if the note contains a
   `Patient's expectations:` entry, citing that line. No entry, no
   sentence.
6. **Close** — at most one neutral sentence ("Thank you for seeing
   him."). Nothing else.

## Hard rules

- **No diagnosis or differential, stated or implied** — not the GP's,
  not the model's. The note's Assessment section is masked in the
  model's copy of the note AND its lines are uncitable, so a letter can
  never carry the differential even by grounding.
- **No advice to the consultant.** Nothing that reads as directing
  specialist management.
- **The only source is the approved note.** Letters are generated from
  the APPROVED NOTE TEXT only — never the transcript, never before
  approval (server refuses with 409 before approval and on voided). A
  letter must not cite content the doctor has not signed.
- **Salutation, Re: line and sign-off are code, not model output.**
  Demographics come from the server-side patient record; the model
  writes body paragraphs only.
- **Never invent** examination findings, doses, or dates. Where
  something is missing, omit it or write exactly
  "[to be completed by the referring doctor]".

## The gates (code, per sentence — `letters.validate_letter`)

The owner's bar is per sentence: **every clinical sentence traceable to
the note.** A bad sentence costs itself, not its paragraph.

- Citations must point at real, **citable** note lines: Subjective,
  Objective and Plan content only. A citation into Assessment is
  discarded.
- A sentence with load-bearing content (numbers, dose units,
  laterality) and no valid citations is replaced by the placeholder.
- **Every number must literally appear in the cited lines** (or in the
  code-supplied allowed set, e.g. the patient's age). An unmatched
  number is an invented number.
- **Tense fidelity**: a result-class verb (performed / showed /
  revealed…) over cited lines carrying only planned-class wording
  (arranged / requested…) is an upgrade the note never made — replaced.
- An expectation-class sentence without a cited
  `Patient's expectations:` line is **dropped**, not placeholdered —
  an invented expectation should vanish, not invite filling in.
- A sentence with no load-bearing content may pass uncited only when it
  reads as courtesy boilerplate.

## Workflow and audit

Suggestions come from the approved note only (`SUGGEST_PROMPT` — an
empty list is a common correct answer), cached per note version.
Letters are draft-until-approved with their own edit and approve steps,
then read-only; void freezes letter operations; decoding is
deterministic (temperature 0, seed 42) like every clinical output.
Audit events: `letter.suggested / created / edited / approved`.

## Provenance

Framework written by the owner 2026-07-24 after reviewing the #66
letter. The two #66 QA findings shaped the gates: a result-class
upgrade over a planned investigation, and an invented patient
expectation on the regeneration. Verification at the time: #66
regenerated under the new prompt and diffed against approved v1 for the
owner — 13/16 sentences grounded, the under-cited sentence and the
dropped invention placeholdered.
