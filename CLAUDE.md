# CLAUDE.md

Orientation for an AI assistant working in this repository. Read
`HANDOVER.md` § *Orientation in five minutes* next; it is the engineering
record and it is long, so read the sections you need rather than all of
it.

## What this project is

Consultation AI transcribes a doctor–patient consultation live, offers
clinical decision support while it runs, and afterwards produces a
diarised transcript and a cited draft note the doctor edits and approves.
Everything runs locally on one machine — no cloud inference.

**It is a research and education prototype. It is not a medical device,
it has had no regulatory assessment, and it must never be used with real
patients or real patient data. Every consultation used in development is
synthetic — scripted or acted.** That framing is in `README.md` and
`PROJECT_PLAN.md`, and it belongs in anything you write here.

v1 is English-only. Sinhala was the question the project asked first and
answered first, with a pre-registered negative result in `evals/`; it is
out of scope, not postponed. Do not reopen it as an implementation task.

## The team, and whose decision it is

Three members: **the owner**, a GP, who makes every product and clinical
decision; an orchestration assistant that writes specs and reviews; and
you.

If a choice is a product or clinical judgement — what the system should
say to a patient, what a threshold should be, what a face should express,
whether a rule can be relaxed — **stop and say so rather than deciding
it.** Reporting a well-analysed choice back is the finished job. Decisions
already made are recorded in `HANDOVER.md` and marked as owner decisions;
implement those rather than re-litigating them.

## Running it

One machine: WSL2 Ubuntu, an RTX 4090 (24 GB), Postgres 18 + pgvector,
Ollama in user space. Credentials live in `.env`, which is gitignored;
`.env.example` is the template and every new setting belongs there with a
one-line comment.

```bash
uv sync                                    # env (uv manages Python 3.12)
uv run uvicorn app.main:app --port 8000    # manual run on a fresh box
uv run pytest                              # the suite
uv run python scripts/migrate.py --check   # DB drift report, read-only
```

On this machine Ollama and the app are systemd services and are already
running. **Do not restart the service. The owner does that himself.** The
app runs without `--reload`, so code changes are not live until he
restarts it — say when a change needs a restart, and leave it to him.

## Tests

`uv run pytest` — heavy tests self-skip when Ollama, Postgres or the
corpus are absent, and the suite runs against a disposable
`consultation_ai_test` database, never the live one.

**Tests are evaluation-first: a test pins a property, not a snapshot.**
The suite is evidence about the code, so:

- Never weaken an assertion or delete a test to make a suite green.
- When a deliberate change makes a test fail, update it one by one, keep
  its spirit, and say in the commit what changed and why. If you cannot
  keep its spirit, that is a finding to report, not an edit to make.
- Adversarial tests must not pass vacuously — assert that the attack
  reached the thing being tested.
- A failing acceptance criterion is a result. Report which one and by how
  much; do not adjust the criterion to fit the code.

Model-dependent behaviour is evaluated in `evals/`, with reusable
harnesses in `scripts/evaluate_*.py`, not asserted in unit tests.
Clinical decoding is temperature 0, seed 42.

## Commits

**One logical change per commit, with the suite green.** Do not bundle
unrelated changes; a spec lands before the code that depends on it, and
tests land with the behaviour they pin. Write the *why* in the message —
the git history is a coordination channel, and this project's messages
carry the reasoning, not just the diff.

## Where the writing goes

- **`HANDOVER.md` is the record.** Anything a future reader would need
  and could not derive from the code goes there: what was decided, what
  was measured, what is fragile. Add a dated section; cross-reference a
  spec rather than copying its numbers.
- **Specs live at the repository root** (`PROJECT_PLAN.md`,
  `PHASE_7_SPEC.md`, `PHASE_7A_SPEC.md`, `PHASE_7B_KINDALIVE.md`,
  `PHASE_7B_FACE_DRIVE_SPEC.md`, `TRANSCRIPT_QUALITY_GATE_SPEC.md`,
  and others). Two are **FROZEN** — `PHASE_7C_EVAL_PREREG.md` and
  `OPEN_CLOSED_RULE.md` — and change only by logged amendment.
- **`help/` explains; `HANDOVER.md` records.** The help series is
  reader-facing prose. A behaviour change updates the help series in the
  same change — but the articles are owner-approved verbatim text, so
  propose the correction and let the owner approve it rather than
  rewriting a page on your own initiative.

## Things that are load-bearing

- **`vendor/` is pinned and must not be edited.** The vendored face
  engine sits at a pinned upstream commit with its licence beside it and
  attribution in `NOTICE`; editing it invalidates both. If the vendored
  behaviour is wrong for this project, change our layer.
- **The urgency alarm is not wired to the face**, and the face has no
  urgency input. An alarmed face would tell the patient something the
  doctor has not decided yet. A test guards it.
- **The three standing interface rules** (`HANDOVER.md`, *THE THREE
  STANDING RULES*), each written after an incident in a real room: never
  swallow an action; a control that can act must not look as if it
  cannot; a control the doctor must reach must be where they are looking.
- **Every AI output is a draft.** Nothing enters the record until the
  doctor reviews and approves it, and consequential actions are audited.
- **Refusal is a feature.** The guideline layer refuses when the corpus
  does not cover a topic and the finalisation gate refuses to draft from
  an untrustworthy transcript. Do not soften a refusal to make a demo
  smoother.
