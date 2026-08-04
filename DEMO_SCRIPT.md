# DEMO SCRIPT — the ten-minute run of play

The performed version of `DOCKER_DEMO_SPEC.md` §2.2, amended by the
owner's sign-off decisions (2026-08-04). The rule that outranks the
clock: **no governance action touches a real row** — every beat below
runs on data created by `scripts/seed_demo.py`, and
`scripts/reset_demo.py` returns the system to its pre-demo state
afterwards, touching only what seeding created.

## Owner-supplied prerequisites (before demo day)

Two assets this repository cannot provide:

1. **The throwaway non-English clip** for the gate-refusal moment
   (decision 3). A short utterance in any non-English language, recorded
   by the owner specifically for the demo. Never #70's audio — that is a
   voided real consultation and a research fixture.
2. **The choice of pre-recorded urgency consultation** (decision 2): a
   past mock consultation on which the urgency alarm fired and was
   acknowledged — the urgency beat is *shown from its review page*, not
   performed live.

## Setup (any time before; ~10 minutes + one restart-fresh check)

- Seed the demo data: `uv run python scripts/seed_demo.py` — three
  marked patients on today's queue, one pending applicant account for
  the approve-to-activate beat. Note the printed applicant username.
- Accounts for the performers come from the break-glass CLI, never the
  web form: `uv run python scripts/manage_users.py create …` for a demo
  doctor and a demo receptionist if the machine does not already have
  accounts to use.
- Open the pre-recorded urgency consultation's review page in a spare
  tab, logged in as the doctor.
- Have the non-English clip ready to play at the microphone.
- Sound check: the speak button's own check confirms the room can hear.

## The run of play

1. **Reception** *(1 min)* — as the receptionist: register a walk-in
   (one of the seeded DEMO patients), reorder the queue. Role
   separation shown by doing, not by probing 403s.
2. **Doctor picks the patient** *(30 s)* — as the doctor: Start
   consultation on that queue entry. Point at the server-sourced
   patient banner: identity comes from the server, never from URL text —
   the wrong-patient defence.
3. **Mic check** *(30 s)* — the level meter runs off the same
   getUserMedia stream the transcriber consumes. One capture, so the
   meter cannot disagree with what the server hears. Small moment,
   strong point.
4. **Live consultation** *(3 min)* — perform the routine English script
   (suggested spine: `03_diabetes_review_en` — calm, well-covered by
   the corpus). Streaming transcript; CDS differentials revising as
   evidence arrives; questions disappearing once answered; the
   guideline panel citing the corpus.
5. **The cricket refusal** *(30 s)* — ask the guideline layer an
   out-of-corpus question. Cricket lands the point that this thing
   knows what it does not know, and gets a laugh.
6. **Urgency, pre-recorded** *(1 min)* — switch to the spare tab: the
   consultation where the alarm fired. Show when it fired, what it
   said, and the acknowledge-gate — approval blocked until the banner
   is acknowledged. Said plainly: the live face never shows urgency;
   the alarm speaks to the doctor, not the patient.
7. **Stop and finalise** *(1–2 min, the pipeline runs)* — Stop; while
   finalisation runs, say what is happening: re-transcription,
   diarisation, role attribution, the drafted note. **While it runs:
   the gate refusal** — play the non-English clip into a second short
   consultation and Stop: the finalisation gate refuses to draft from a
   transcript it cannot trust. The system declines rather than
   fabricates.
8. **Verification** *(1 min — give it time)* — on the review page,
   click a citation chip and land on the transcript turn. This is the
   whole thesis of the project in one gesture. Click a ⚠-marked claim
   too: numbers resting on low-confidence audio announce themselves.
9. **Approve, then a referral letter** *(1 min)* — approve the note;
   generate a referral letter from the approved note only, with the
   grounding gate.
10. **Approve-to-activate** *(1 min)* — as the admin, in the Users
    view: the seeded applicant is pending; approve it; it can now log
    in. Registration is public, activation is governed — the security
    story in one click. Seeded data only.

## Afterwards

`uv run python scripts/reset_demo.py` — deletes the demo patients,
their queue entries, any consultations recorded against them (audio
included), and deactivates the applicant account. It refuses to touch
anything it did not create.

## Deliberately left out (spec §2.3)

RBAC probes and 403s — true but dull. Void, unvoid and purge — the
exact actions the no-real-rows rule exists for; nothing in this demo
performs governance on a real row. And nothing involving the real
accounts.
