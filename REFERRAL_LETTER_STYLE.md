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
differential; the letter must never name it. Written the way a GP hands
a case over to a colleague at the desk — every sentence carrying
clinical information, no essay style, no filler, no repeated
demographics.

## Register

- **Plain spoken medical English.** Active voice, verbs doing the work.
  British English.
- **Short but connected.** Compress related findings: one finding's
  qualities — its character, trigger, duration, relief — fold into a
  single sentence rather than several. Vary sentence length. Never a
  long run of one-fact sentences (the staccato the v2 output fell into,
  owner judgement 2026-08-15).
- **Paragraph 4 never repeats.** Background carries only what the
  earlier paragraphs have not already said; if nothing remains, the
  paragraph is omitted. Up to four paragraphs, never more.
- **Tense carries meaning.** Past tense for what was found, present
  tense for what is true now.
- **Say the plain thing.** "Worse at night", not "nocturnally
  exacerbated"; "while", not "whilst"; state the fact instead of "it is
  of note that". That whole class of substitution applies.
- **Never comment on the record.** The letter does not write that a
  symptom, change or finding "was not documented" or "was not recorded".
  What the note lacks is omitted, or takes the placeholder.

## Selection — the silent differential

Before writing, the model lists — **in its `reasoning` field only** —
the three or four conditions the receiving consultant will weigh,
including any that would be dangerous to miss. That differential
chooses and orders every fact in the letter, and **it never appears on
the page**: not as a diagnosis, not as a "?query", not as a list of
possibilities. The reader should be able to reconstruct it from what was
selected, never read it.

**Negatives must earn their place.** A negative stays only if it does
one of three jobs: it separates conditions in the differential; it
records that a red flag was asked about and was absent; or it saves the
consultant repeating a test. Every other negative goes.

**Selection cuts negatives, never positives.** Every positive finding
the note records goes in the letter — a positive left out is work the
consultant has to repeat (the v2.1 A/B dropped "mild SOB with pain";
owner decision 2026-08-15).

## Structure (up to four body paragraphs, never more, in order)

1. **Why you are writing, and the history.** One opening sentence:
   thank you, the patient, and the problem you want an opinion on,
   stated as **symptoms, never a diagnosis** — "Thank you for seeing
   this 55-year-old man with two weeks of exertional chest tightness."
   Then the story in the note's chronological order: onset, trigger, how
   it has changed, what it stops the patient doing now. Then the
   negatives that earn their place. Past history that bears directly on
   this problem belongs here. If the note has a `Patient's
   expectations:` line, it is given in one sentence here, citing that
   line; no such line, no expectation sentence at all.
2. **What you found.** Examination findings exactly as the note records
   them, in examining order — inspection, palpation, movement, specific
   tests — giving the side. A normal finding is included only where its
   normality narrows the differential. No examination in the note, no
   paragraph.
3. **What the tests showed.** Results only as the note records them,
   with their units. **Planned, performed and resulted are three
   different claims**; the letter uses the note's wording class — "An
   ECG was arranged today", never an upgrade to performed or showed (the
   #66 QA finding). No investigations in the note, no paragraph.
4. **Background** — only what the earlier paragraphs have not already
   said: remaining past history, current medication with doses, allergy
   status, and the social or occupational detail that changes what the
   patient needs from treatment — all only as the note records them.
   Before output, every paragraph-4 sentence is checked against
   paragraphs 1–3: a fact stated anywhere earlier in the letter must not
   appear again here — the repeat is deleted, and if nothing remains the
   paragraph is omitted. A sentence that the patient knows about and agrees to
   the referral belongs here ONLY if a note line states that in those
   terms — the Plan recording a referral is not the patient's agreement.

## Hard rules

- **The differential never reaches the page** — no diagnosis, no
  "?query", no list of possibilities, the GP's or the model's. The
  note's Assessment section is masked in the model's copy of the note
  AND its lines are uncitable, so a letter can never carry the
  differential even by grounding. **One exception, bounded exactly:** a
  concern that the note's PLAN itself states — a suspected-cancer
  pathway referral, a red-flag urgency, an established diagnosis the
  consultant is inheriting — may be stated in one factual sentence
  citing that Plan line, together with what raised it.
- **Ask the consultant for nothing, and tell them nothing to do.** No
  "please arrange", no "please consider", no suggested investigations,
  no management advice.
- **Never comment on the record** (see Register): omit, or use the
  placeholder.
- **The only source is the approved note.** Letters are generated from
  the APPROVED NOTE TEXT only — never the transcript, never before
  approval (server refuses with 409 before approval and on voided). A
  letter must not cite content the doctor has not signed. Each
  paragraph's `note_lines` lists the lines it draws on; every clinical
  statement comes from those lines.
- **Salutation, Re: line and sign-off are code, not model output.**
  Demographics come from the server-side patient record; the model
  writes body paragraphs only.
- **Never invent** findings, doses, dates or history. Where something is
  missing, omit it or write exactly
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
letter. **Revised 2026-08-15 by owner decision, craft taken from the
owner's Meddbase referral-letter method** — the four-paragraph spoken
register, the silent differential, negatives that earn their place, the
never-comment-on-the-record rule and the Plan-only naming exception; the
gates did not move. The two #66 QA findings shaped the gates: a result-class
upgrade over a planned investigation, and an invented patient
expectation on the regeneration. Verification at the time: #66
regenerated under the new prompt and diffed against approved v1 for the
owner — 13/16 sentences grounded, the under-cited sentence and the
dropped invention placeholdered.
