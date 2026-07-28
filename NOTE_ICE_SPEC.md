# NOTE_ICE_SPEC.md — ICE extraction in the SOAP note

> **RECONSTRUCTION, 2026-07-28.** The original (2026-07-24) was lost —
> it existed only in Downloads and a deleted chat. Rebuilt from the
> implemented prompt in `app/notes.py` (`NOTE_PROMPT`), `tests/
> test_ice.py`, and HANDOVER's note-citation section. Where this
> document and the code disagree, the code wins.

## What this is

A prompt-level change to the note generator (2026-07-24): the Subjective
section ends with the patient's **Ideas, Concerns and Expectations**,
extracted as up to three labelled entries — but only when the transcript
actually contains them.

## The rules

1. **Up to three labelled entries, fixed order, ending Subjective:**
   - `Patient's ideas: …` — what they think is going on.
   - `Patient's concerns: …` — what they are worried about.
   - `Patient's expectations: …` — what they hoped for from the visit:
     a test, a referral, reassurance, a certificate.
2. **Patient-volunteered or patient-answered only.** ICE is what the
   patient said — never what the doctor proposed or offered. A doctor
   suggesting "shall we do a blood test?" does not create an
   expectation.
3. **Omitted entirely when absent.** No "not elicited" filler, no empty
   labels. This is the project-wide leave-empty-rather-than-fabricate
   principle applied to ICE.
4. **Cited like every claim.** Each ICE entry carries transcript turn
   citations and passes through `validate_and_gate` like any other
   claim — uncited ICE counts against the grounding fraction the same
   way.

## Downstream contract — the referral letter

The letter's patient-expectation sentence draws **only** from the
`Patient's expectations:` entry. This is enforced in code
(`app/letters.py`): an expectation-class sentence in a letter whose
paragraph does not cite a `Patient's expectations:` note line is
**dropped outright** — no bullet, no sentence. The model invented an
expectation on the #66 regeneration; the gate makes that impossible.
Changing the ICE labels therefore breaks the letter gate's line
matching (`_EXPECTATION_LINE` regex) — the two must change together.

## Provenance and verification

- Introduced 2026-07-24; any note-output diff after that date traces to
  this prompt change. The note-quality eval record carries the
  changelog entry and the harness was re-run the same day.
- Tests: `tests/test_ice.py`.

## Known observation (consultation 448, docket item 11)

The extraction returned identical text for ideas and concerns —
"Worried about prostate cancer" in both fields, word for word. Ideas
(what they think is going on) and concerns (what they are worried
about) are meant to be different things; duplicating one into both
loses the distinction this change exists to capture. The expectations
entry was distinct and correct. Recorded as a prompt-level observation
for the owner; no code defect.
