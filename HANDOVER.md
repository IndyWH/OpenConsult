# HANDOVER — Consultation AI

For a capable engineer with no prior context. Read PROJECT_PLAN.md first
for intent; this document tells you what actually exists, why it's built
the way it is, what's known to be fragile, and what to do next.

> Prototype for research/education only. Not a medical device. Synthetic
> (scripted/acted) consultations only — never real patients.

## Orientation in five minutes

**Read first:** PROJECT_PLAN.md § *What v1 is, and is not* — what v1
does, what it does not (no Sinhala or other non-English transcription),
and the one consequence that is specified but **not yet built** (the
finalisation transcript-quality gate). Read it before the phase table
below, or the Sinhala rows will read as work in progress rather than as
a closed question.

One machine (RTX 4090, 24 GB VRAM, WSL2 Ubuntu 26.04), everything local.

```bash
uv sync    # Python env (uv manages Python 3.12)
# Ollama (MedGemma + embeddinggemma) and the app are systemd services —
# already running on this machine. Manual equivalent on a fresh box:
#   ollama serve &
#   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- http://localhost:8000/live — live consultation: streaming transcript,
  CDS panel (differentials / questions / signs / urgency alarm),
  corpus-grounded guideline panel.
- Press **Stop** → finalisation pipeline runs → browser lands on
  `/review/{id}`: diarised transcript + cited draft SOAP note + urgency
  banner if the alarm was never resolved.
- `uv run pytest` — 333 tests; heavy ones self-skip if Ollama/Postgres/
  corpus are absent. Since 2026-07-24 the suite runs against a disposable
  `consultation_ai_test` database (created/dropped per session by
  `tests/conftest.py`) and never writes to the live database; needs a
  one-time superuser grant, see Troubleshooting.
- Postgres 18 + pgvector, database `consultation_ai`, credentials in the
  gitignored `.env` (see `.env.example`).

## Phase status vs PROJECT_PLAN.md

| Phase | Status | Notes |
|---|---|---|
| 0 — Foundations | **Done except one recording** | Env, Postgres, app, tests all in. Seventeen mock scripts written: 10 English (5 routine, 4 red-flag variants, 1 held-out), 2 Sinhala/English code-switched (`_si`, for the Phase 5 ASR recordings eval), 5 UK private-GP (`_uk`, CDS restraint + buried-red-flag urgency) — see `mock_consultations/README.md`. **Real two-voice recordings made 2026-07-12** through the live app (consultations 66–70), copied to `mock_consultations/recordings/`: routine 01–04 English + `03_diabetes_review_si`. **Still to record: `05_epigastric_pain_en`** — required for Phase 2 real-audio validation and the note-quality eval, and the one item Phase 0 now closes out on. `01_chest_pain_si` is **not being recorded for v1** (2026-07-25): it needs a Sinhala-speaking second reader and only feeds an out-of-scope arm. The script stays in the tree and is available if Sinhala ever restarts. WAVs gitignored; LFS decision still open. |
| 1 — Streaming transcription | **Done** | Voice-tested; lag inside the 2–5 s target. |
| 2 — Post-consultation note | **Done, real-audio validation begun** | Full pipeline + review UI + eval. The 2026-07-12 recordings ran through the full live→Stop→review pipeline as they were made (five consultations; three approved, two awaiting review as of that date) — diarisation and notes held up in use; the formal check against marking schemes + a real-audio section in the note-quality eval are still to do. |
| 3 — Live CDS | **Done** | Including urgency escalation, evaluated 8/9 with one documented boundary case (see docket). |
| 4 — RAG guidelines | **Done; corpus expanded 2026-07-24** | 9/9 eval (re-run after expansion, still 9/9); fidelity spot-check logged. Corpus grew 7 → 38 sources (1301 chunks) to cover common primary-care presentations for the public demo — see the corpus section below. |
| 5 — Sinhala | **CLOSED 2026-07-25 with a negative result; Sinhala out of scope for v1** | Benchmark (2026-07-10): 9 candidates on two OpenSLR sets, best `seniruk/whisper-small-si` CER 0.035. Pre-registered recordings eval executed on the real `03_diabetes_review_si` recording: every model degrades massively (seniruk 0.035 → 0.504; best overall xlsr-sinhala CTC 0.462) and **every Sinhala fine-tune transliterated or lost all 106 English terms** (mechanical recall 0). Off-the-shelf landscape now exhausted (post-hoc screen of remaining HF repos found only duplicates). **Step 6 adjudication completed 2026-07-25** (owner, binary measure unchanged): seniruk-small recovers clinically usable content for 7 of 12 curated terms vs 0 (rrashmini-large-v2) and 1 (xlsr-sinhala) — **the ranking reverses, seniruk-small over xlsr despite xlsr's better CER**, because clinical survival is what matters here. Four terms — `HbA1c`, `losartan`, `atorvastatin`, `neuropathy` — survive in **no** model. Verdict unchanged: no off-the-shelf model is usable for code-switched clinical Sinhala. **Fine-tune NOT PROCEEDING by owner decision 2026-07-25** (eight sign-offs deliberately not sought); Consultation AI is **English-only for v1** and Sinhala is out of scope, not postponed — see the decision header in `evals/2026-07-17_finetune_plan.md` and PROJECT_PLAN.md §§4, 7. All Sinhala research artifacts are retained deliberately (scripts, recording, reference, harness, eval records) — they are the pre-registered negative result. See `evals/2026-07-12_sinhala_asr_recordings_eval.md` § Step 6. |
| 6 — Users/roles/front desk | **Core built and manually verified** | Auth (scrypt + signed-cookie sessions), three tabs per the agreed structure, walk-in queue, server-side RBAC (receptionist 403s on all clinical content — automated tests pass), audit log, approved-consultations read-only, full loop wired queue→live→review→approve→archive. **Verified 2026-07-10 (project owner, in-browser):** two-role click-through of the full loop, plus adversarial checks — receptionist hitting clinical URLs directly (403 confirmed), doctor attempting queue add/reorder (403 confirmed), edit attempts on an approved consultation (409 / read-only UI confirmed). **Design pass done 2026-07-24** (Heidi-inspired light theme, whole app — see the design-pass section) along with **strict own-consultations doctor scoping** and the new **referral letters** feature. Remaining build work: Docker Compose packaging, demo script. **Post-verification additions (2026-07-10, browser-testing findings):** doctor walk-in action (`queue.walk_in_started`); server-sourced patient banner on the live page (wrong-patient prevention — identity never read from URL text); queue-entry lifecycle for abandoned sessions — Resume, Close-without-consultation (`queue.cancelled`, receptionist too), and a concurrency guard so a doctor can't stack a second live consultation over an active one. |
| 7 — Supervised auto history-taking | **OPEN as of 2026-07-25**; **7a items 0–4 and 7 built the same day — tap-to-ask and the sound check work end to end, barge-in is session 3** (see "Phase 7a — the transcript guarantee" below, and run its real-room check before calling 7a done). Two gate items deliberately carried — see "Phase 7 opened". | Owner's concept: in auto mode the AI conducts the history-taking by voice under doctor supervision — questions and acknowledgements only, never advice or diagnosis to the patient; urgency alarm pauses auto mode (resume/take-over is the doctor's call); doctor barge-in always wins. Full spec — hard rules, consultation behaviour policy, staged build (7a tap-to-ask → 7b kindalive face → 7c supervised auto), pre-registered eval design — in `PHASE_7_SPEC.md`. **Gate updated 2026-07-25: the Phase 5 precondition is satisfied by closure** (step 6 adjudication + Phase 5 closed with a negative result, Sinhala out of scope for v1 — not a deferral), and the recordings precondition means `05_epigastric_pain_en` only (`01_chest_pain_si` not being recorded for v1). **Remaining gate, three items: (1) `05_epigastric_pain_en`; (2) Docker Compose packaging + the two-role demo script; (3) the finalisation transcript-quality gate** — load-bearing now the project is English-only, see the pre-Phase-7 build item section. 7a+7b are the recommended first commitment, 7c committed separately. |

Every completed phase has an evaluation record in `evals/` with a
reusable harness in `scripts/evaluate_*.py`. Raw per-case JSON sits next
to each record.

## Component map

```
app/main.py            FastAPI app, WebSocket /ws/transcribe, review API
app/transcription.py   faster-whisper wrapper (live path, distil-large-v3)
app/live.py            per-connection audio buffer + commit logic + session recording
app/cds.py             CDS engine: assessment call + stateless urgency call
app/rag.py             guideline retrieval + grounded summarisation + refusal
app/chunking.py        structure-aware guideline chunker
app/finalize.py        Stop-triggered pipeline: WhisperX + pyannote + roles + note
app/notes.py           cited SOAP note generation + plain-text serialiser
app/consultations.py   Postgres persistence (consultation/turns/notes/urgency)
app/letters.py         referral letters: suggest/draft calls + grounding gate
app/schema.py          one entry point + ordering for the whole DB schema
app/speech.py          Phase 7a: TTS subprocess adapter, phrases, ref resolution
app/system_utterances.py  what the system said, and its exclusion spans
app/monitor.py         public monitoring pulse: aggregate counts, 10 s cache
app/ratelimit.py       per-IP auth rate limits + proxy-aware client_ip
app/mock_scripts.py    mock-script parser (turns)
app/static/theme.css   shared design system (2026-07-24 pass; light only)
app/static/live.html   live page; review.html  review page; nav.js app chrome
corpus/manifest.yaml   committed provenance for the gitignored corpus
scripts/               ingest_guidelines, simulate_cds, make_tts_sample,
                       evaluate_{urgency,rag,notes,sinhala_asr},
                       manage_users (break-glass CLI, see toolbox below),
                       migrate.py [--check] (schema apply / drift report)
```

Models: MedGemma 27B Q4_K_M GGUF via Ollama (clinical reasoning, notes,
RAG summaries), `embeddinggemma` via Ollama (768-d embeddings),
faster-whisper `distil-large-v3` (live ASR), WhisperX `large-v3` +
pyannote `speaker-diarization-3.1` (final pass). All decoding for
clinical outputs is temperature 0, seed 42 (`CDS_TEMPERATURE`/`CDS_SEED`).

## Key design decisions and why

**English-only for v1 (owner decision, 2026-07-25).** Sinhala
transcription, the translation layer, and dual-language transcript
generation are **out of scope for v1** — not postponed. The reason is
measured, not resourcing: the pre-registered benchmark and recordings
eval established that no off-the-shelf model handles code-switched
clinical Sinhala, and the 2026-07-25 adjudication established that four
of twelve curated clinical terms — including two drug names — survive in
no model at all. Phase 5 is closed with a negative result; that result
is the finding. Full statement in PROJECT_PLAN.md §4 (Scope decision).
Two deliberate retentions, so nobody "tidies" them away later: (1) **all
Sinhala research artifacts stay** — both `_si` scripts, the
`03_diabetes_review_si` recording and its frozen reference,
`scripts/evaluate_sinhala_asr.py`, the benchmark, the recordings eval,
the adjudication worksheet and the fine-tune plan — because they are a
standalone research contribution (a pre-registered negative result on
code-switched clinical ASR) intended for external collaboration; and (2)
**the si/en seam in the `FinalTranscript` design is retained on
purpose**, even though nothing populates the Sinhala side in v1, because
removing and later restoring it would be a schema migration against a
database holding approved clinical notes.

**Live ASR: distil-large-v3, beam 5, clinical initial prompt.** The
original small.en garbled drug names on accented speech ("gliclazide" →
"nucleoside"). distil-large-v3 is more accurate AND faster (67× real
time). The `WHISPER_INITIAL_PROMPT` env seeds clinical vocabulary.

**Streaming commit logic (app/live.py):** re-transcribe the whole rolling
buffer every ~1.5 s; segments ending >2 s before the newest audio are
*committed* (sent as final, audio dropped); the rest streams as a grey
revisable partial. Rough-but-live by design — the accurate pass is
Phase 2's job (plan: "live path is rough, final path is accurate").

**CDS revision rules (app/cds.py, ASSESSMENT_PROMPT):** the model always
receives its previous assessment and *revises* it. Pinned: condition
names and list order. Living: rationales (must absorb new evidence) and
likelihood grades. Questions/signs must be removed once the transcript
answers them. This was tuned empirically: "keep items verbatim" froze the
assessment; free revision churned it. Stability is measured by the
simulate/evaluate harnesses (differential-churn metric).

**Urgency: a stateless "safety officer" split from the assessment call.**
The single most important architectural lesson in the repo. In one
combined call, urgency failed every way we tried: strict JSON schema
suppressed the model's reasoning phase (it recommends an ECG in free
text, returns an empty alarm under a schema); prose checkpoints didn't
bind ("Immediate step demanded: ECG" alongside an empty actions array);
previous-state feedback anchored the alarm (empty stays empty). Fixes
that shipped: urgency is its own model call seeing ONLY the current
transcript, fresh every update; the checkpoint fields are typed booleans;
all bookkeeping is code, not prompt — the engine clears the alarm when
`already_done_or_arranged` is true and latches "arranged" for the session.
Full five-attempt history: `evals/2026-07-07_urgency_evaluation.md`.

**RAG grounding and refusal (app/rag.py):** summaries may use ONLY
retrieved passages; every claim carries a [n] citation validated in code;
a "covered" answer with zero valid citations is demoted to refusal.
Refusal is two-layer: a similarity floor (0.45) in code, then the model's
own covered=false verdict for near-misses (e.g. TIA retrieving the
*cardiac* guideline). Retrieval is per-CDS-condition with a per-source
cap — concatenated queries let one guideline's title vocabulary crowd out
cross-referenced content (the NG28-vs-CG173 finding). The corpus is
gitignored; `corpus/manifest.yaml` + `scripts/ingest_guidelines.py`
rebuild it. Chunking is section-based with heading trails, list items
kept with their stems, never mid-sentence (`app/chunking.py`).

**Corpus scope + ingestion validation (2026-07-24 expansion):** the
corpus grew from the five mock-script topics to 38 sources / 1301 chunks
covering the presentations external demo users are likely to record
(cardiovascular, respiratory/ENT, urinary, MSK/neuro, mental health,
endocrine/renal/haematology, skin, women's health, paediatrics, sepsis,
dengue) — the app is publicly demoable and common topics should retrieve
rather than refuse. Content is third-party (NICE/CKS/CDC/WHO), local
research use only, never committed or redistributed; the committed
manifest is the provenance record. **Validation convention** (the NG28
lesson, now enforced in code): every manifest source carries
`expect_title` — checked against each fetched page's `<title>`, with any
redirect to a different page treated as a fetch failure — and 2–3
`expected_queries`, each of which must retrieve a chunk from its own
source within the global top 8 at similarity ≥ the refusal floor after
ingestion, or `ingest_guidelines.py` exits non-zero listing every failed
source. The expansion itself caught three instances of guideline drift:
NG51 (sepsis) replaced by NG253/NG254, NG138 (CAP) replaced by NG250,
and both replacements' /Recommendations URLs silently redirecting to
research-only chapters. Where no NICE guideline exists, CKS topics fill
in (iron-deficiency anaemia, adult eczema, giant cell arteritis — the
CKS GCA topic is written from the BSR guideline, whose full text on
academic.oup.com blocks automated fetch). Eval expectation changes that
came with coverage (documented in the eval record addendum): TIA is now
an in-corpus case, and the chest-pain case accepts CG126 or CG95 as
top-cited.

**Note citation architecture (app/notes.py):** same pattern as RAG —
every SOAP claim cites transcript turn numbers, validated in code,
click-to-verify in the UI. **Prompt change 2026-07-24 (ICE):** the note
prompt now extracts the patient's Ideas/Concerns/Expectations as up to
three labelled entries ending Subjective — only when the transcript
contains them (patient-volunteered, never doctor-proposed; omitted
entirely when absent, per the leave-empty-rather-than-fabricate
principle), cited like every claim. Any note-output diff after this date
traces to that prompt change (`NOTE_ICE_SPEC.md` addendum; eval record
changelog updated, harness re-run same day). The referral letter's
patient-expectation sentence draws ONLY from the "Patient's
expectations:" bullet. Flagging is deterministic code, not model
judgement: a claim is ⚠-marked iff it contains load-bearing content
(number / dose unit / laterality, by regex) AND cites a turn whose ASR
confidence is below 0.6. Doctor-corrected turns get confidence 1.0.

**Review-page urgency banner:** unresolved urgent actions (alarm fired,
transcript never showed arrangement) persist at Stop with first-fired
audio timestamps, and render as an acknowledge-gated alert above the
note. Approve is blocked client- AND server-side (409) until
acknowledged; the ack timestamp is recorded. Urgent actions are never
merged into the note text or the plain-text export — **the note is the
doctor's document**; the banner is the system speaking, and the two must
not blur. The plan's draft-until-approved principle depends on the note
containing only what the doctor signs.

**VRAM sequencing (app/finalize.py):** MedGemma (~17 GB) and
WhisperX+pyannote (~6–8 GB) cannot coexist in 24 GB. The pipeline
explicitly unloads MedGemma (keep_alive=0, polls /api/ps), runs the audio
models, frees them (del + empty_cache), and lets MedGemma reload on the
note call. ~17 s for a 4.6-min consultation.

## Design pass + referral letters (2026-07-24)

Implemented from `DESIGN_SPEC.md` (Claude Cowork + owner; approved
mockups `live_mockup.html`/`review_mockup.html` are the visual source of
truth — both in the owner's Downloads, spec decisions restated here).
Five commits, "Design pass 1/5 … 5/5":

- **Design system** (`app/static/theme.css`, linked everywhere): warm
  cream canvas, one plum accent reserved for the primary action + active
  tab, semantic colours scarce (red = urgency ONLY, amber =
  low-confidence/awaiting, green = mic/linked/approved), serif display
  type for titles/patient names/SOAP headings. **Deliberately light-only**
  (owner call): dark mode dropped, including the old `select, option
  { background: Canvas }` workaround — don't reintroduce
  `color-scheme: light dark` piecemeal. `nav.js` renders the shared
  chrome (brand, pill tabs, identity block, footer disclaimer).
- **Live page reorder** (owner's priority): urgent-actions banner first,
  questions|signs duo, differential with the guidelines summary inside an
  open `<details>`, transcript last. **Mic status cluster is a safety
  feature** (answers docket #78 mic-check fabrication and #70 degraded
  audio, in-room): level meter runs from page load off the SAME
  getUserMedia stream the transcriber consumes — one capture, so the
  meter cannot disagree with what the server hears; sustained RMS < 1e-4
  for 3 s turns the pill red (hysteresis at 5e-4); device picker
  re-acquires with `deviceId: {exact}`, disabled while recording
  (mid-recording switch is v2).
- **Review page reorder**: header (chips + Regenerate/Copy/Approve) →
  urgency banner → draft SOAP note (grounding footer "N/M claims cited")
  → letter panes → diarised transcript last.
- **Strict own-consultations scoping** (owner decision, over
  continuity-of-care sharing — revisit only as an owner decision): a
  doctor's worklist and every `/api/consultations/{cid}` op are filtered
  server-side to their own consultations; foreign probes 403 (matching
  the receptionist pattern; voided stays 410). Unowned rows
  (`doctor_id IS NULL`, legacy/test data) stay open to clinical roles.
  Tests: `tests/test_scoping.py`.
- **Referral letters** (`app/letters.py`; tests `tests/test_letters.py`):
  on an approved consultation the Approve button becomes a plum "+" →
  menu of model-suggested referrals + manual specialty picker (patient
  info letter = stub). Hard rules, extending the two-hats principles:
  generated from the APPROVED NOTE TEXT only (server 409s before
  approval/on voided — a letter must not cite content the doctor hasn't
  signed); grounding gate in code (`validate_letter`); salutation/Re:
  line (server demographics)/sign-off are code, not model; letters are
  draft-until-approved with their own edit+approve, then read-only;
  suggestions cached per note version; deterministic decoding. Audit:
  `letter.suggested/created/edited/approved`. RBAC doctor+admin;
  receptionist and foreign-doctor probes 403-tested. Tables `letter` /
  `letter_suggestion` cascade on purge; void freezes letter ops.

  **Owner's clinical framework (2026-07-24 addendum,
  `REFERRAL_LETTER_STYLE.md`, after reviewing the #66 letter):** the
  letter presents the evidence and lets the specialist draw the
  conclusion. Prompt rewritten (symptoms-first opening, compressed
  history, findings/investigations as recorded, one expectation sentence
  only from the note's ICE bullet, neutral close, no diagnosis, no
  advice to the consultant). The gates are the guarantee, per sentence
  ("every clinical sentence traceable"): Assessment lines are masked in
  the model's copy of the note AND uncitable (a letter can never carry
  the differential); numbers must appear in cited lines; result-class
  verbs over planned-class citations are rejected (planned ≠ performed ≠
  resulted, the #66 QA finding); expectation-class sentences without a
  cited "Patient's expectations:" bullet are dropped outright (the model
  invented one on the #66 regen — the gate now makes that impossible).
  Verification: #66 regenerated under the new prompt and diffed against
  approved v1 for the owner (13/16 sentences grounded; the one
  under-cited sentence and the dropped invention placeholdered).

## Phase 7a — the transcript guarantee (2026-07-25, session 1 of 2)

`PHASE_7A_SPEC.md` (in the repo since this session) is the *how*;
`PHASE_7_SPEC.md` § Stage 7a stays the statement of what 7a is *for*.
Build order items 0–4 and 7 are done: schema module, `app/speech.py`,
live-path exclusion, finalisation exclusion, real speech through Piper,
the doctor-facing UI, and the sound check. **Not built, and deliberately
session 3: the barge-in detector (build item 5) and
`scripts/calibrate_barge_in.py`** — held back on purpose until the owner
has used tap-to-ask in the real room. `BARGE_IN_ENABLED` ships false;
hard mute is this design with the detector off.

### The guarantee, and why it is structural

7a introduces audio output into a system whose entire safety guarantee is
that *the transcript is faithful to the room*. If the system's own voice
can enter the transcript, the system can put words in the patient's
mouth — and every downstream defence inherits the corruption, because the
note grounding gate would faithfully cite a fabricated turn. That is
consultation #70's failure shape exactly (a note faithful to a transcript
that was not faithful to the audio), reached by a new route.

So the mechanism is **server-held knowledge of when we were speaking**,
never signal quality and never text comparison. Echo cancellation that
works 98% of the time is *detection*, and a rare fabrication is worse
than a frequent one because nobody builds the habit of checking for it.

> String comparison against the spoken text is legitimate **as a test
> assertion** and forbidden **as a runtime mechanism**. Both test files
> say so in their docstrings, because it is exactly the thing a future
> contributor will promote into the pipeline as a helpful safeguard.

### Exclusion happens twice, from one persisted source

1. **Live path** (`app/live.py::append_pcm16`): the recording gets the
   real audio, the transcriber's buffer gets **silence** for any part of
   it we were speaking over. Silence rather than nothing, deliberately —
   dropping the samples would shift every later timestamp relative to the
   recording, and the urgency alarm's first-fired times read that clock.
2. **Final path** (`app/finalize.py::mute_spans`): finalisation
   re-transcribes the *whole* recording, so gating the live path alone
   would leave our voice in the final transcript. The models are handed a
   **derived copy** with the spans zero-filled.

**The original WAV is never modified.** It stays byte-intact as the
faithful record of the room and is what the retention sweep and
FLAC-on-approval operate on; a test sha256s it before and after.

A window is a **byte range on the recording**, not a sequence range.
Verified against the client: frames are a fixed 4000 samples (0.25 s),
but the server appends whatever arrives and only *warns* on a seq gap, so
`seq × frame_size` is not a safe offset — the server's own byte count is.
That choice also removes the need for a timer: a window carries a ceiling
of `start + synthesised duration + tail` from the moment it opens, so a
`speak_ended` that never arrives closes it exactly right, and a late one
is clamped.

**Ordering, checked rather than assumed:** the client sends
`speak_started` at playback start carrying the seq of the next frame, and
WebSocket messages are ordered — so the server knows the window is open
before the first in-window byte arrives. It is a message-ordering
guarantee, not a timing one, and it does **not** depend on the ~2 s commit
margin. The client's declared seq is logged as a cross-check and never
used as the offset; trusting it would put the guarantee in the client's
hands.

### Reference-only speech (`app/speech.py`)

Hard rule 1 — questions and acknowledgements only, never advice — is
enforced in code, not prompt. The client sends a **reference**
(`{"kind":"phrase","id":…}` or
`{"kind":"cds_question","assessment_version":N,"index":i}`) and the
server resolves it against its own phrase table or its own versioned copy
of the CDS agenda, authoring the words itself. A `speak` carrying `text`
is **rejected outright and audited**, not sanitised: sanitising would make
it a filter, and a filter is detection. An unresolvable agenda version is
refused rather than guessed — substituting another version's wording
would be the server authoring a question nobody tapped. A question since
revised off the agenda is allowed and logged (the panel lags a turn;
re-asking is redundant, not unsafe).

`cds_rationale` records the assessment's `reasoning` field, because the
CDS schema gives questions as bare strings with no rationale of their own.
That is the honest reading of hard rule 5's "the rationale, not just the
question".

### `system_utterance` — a separate table, on purpose

**Not** a `system` role in `transcript_turn`. The note generator receives
turns, and system utterances are not turns: there is no enum value to
forget to filter and no query that includes us by omitting a WHERE clause.
It is also what carries the spans across a restart, which is why a
`connection_lost` finalisation still excludes correctly. Byte offsets are
authoritative; the `*_offset_ms` columns are derived and rounded.

### Transcript-quality gate interaction — what S4 actually measures

The spec recorded this as unverified and inferred it might be a silence
measure. **It is not.** `s4_truncation_gap` is
`audio_duration − max(turn.end)`: the **trailing** gap only. So muted
spans in the *middle* of a recording cannot move it and cannot manufacture
a spurious `unreliable_transcript` refusal. There is exactly one exception
— the system speaks **last** (the examination handover) and the recording
ends, so the last transcribed segment now ends before our utterance and
the gap grows by its length. S4 is therefore now told about the excluded
spans and discounts them from the trailing region. A test builds that
scenario, asserts it genuinely trips the gate undiscounted, and asserts
the discount clears it; another asserts a real 33 s truncation with no
windows still refuses, so the discount cannot become a way to silence the
gate. **S2 needed no adjustment** and is asserted unchanged: a muted span
produces no segments, so it contributes no confidence and no duration
weight.

`scripts/calibrate_transcript_quality.py` now **delegates S2 and S4** to
`app/transcript_quality.py` instead of keeping its own copies — changing
S4's arithmetic in one of two implementations would have made the
calibration stop describing what the pipeline does. **S1 is still two code
paths**; that one needs the multi-window redesign and was not touched.

### Piper runs as a subprocess, at arm's length — do not "simplify" it

Owner's decision 2026-07-25, settled. **There is no `import piper`
anywhere in `app/`, and there must not be one.** Synthesis goes through a
configurable command (`TTS_COMMAND`) run as a separate process which
writes a WAV and exits. Two reasons, both recorded in `app/speech.py` and
`NOTICE` so the indirection is not removed as pointless:

- `piper-tts` is **GPL-3.0-or-later** and links espeak-ng. Invoking a
  separate program at arm's length is a different relationship from
  linking it into our process, and this project is intended for external
  collaboration.
- Adding it to `pyproject.toml` would **re-resolve the app's lockfile** —
  the churn that corrupted this machine's CUDA wheels before.

Installed with `uv tool install piper-tts` into its own environment
(`~/.local/share/uv/tools/piper-tts`). Verified after installing:
`uv.lock` and `pyproject.toml` unchanged, and the app's venv still cannot
`import piper`.

Voice `en_GB-alba-medium` lives **outside the repo** at
`~/.local/share/piper-voices/` (63 MB, never committed), path via
`TTS_MODEL_PATH`. **Its licence position is recorded in `NOTICE` as the
model card states it, not as assumed:** the card gives the *training
dataset's* licence (CC BY 4.0, the Edinburgh CSTR corpus) and states **no
licence for the weights**. That gap is deliberately left visible.

**CPU only, structurally.** `--cuda` is not passed, but the stronger
guarantee is that the tool environment's onnxruntime is a CPU-only build
whose available providers are `['AzureExecutionProvider',
'CPUExecutionProvider']` — there is no CUDA provider to select even if
someone added the flag. Nothing was resident on the card during
synthesis.

**Absolute paths in `.env`, deliberately:** `consultation-ai.service`
inherits systemd's default `PATH`, which does **not** include
`~/.local/bin`. A bare `piper` resolves in an interactive shell and fails
under the service — the kind of difference that only shows up in the
room. `TTS_COMMAND` is also quoted, so `set -a && . ./.env` still works
(unquoted, bash ran `--model` as a command).

**Measured latency**, en_GB-alba-medium, this machine, five typical CDS
questions plus the fixed phrases:

| | |
|---|---|
| Cold (cache miss: process start + model load + synthesis) | median **749 ms**, range 735–843 ms |
| Warm (cache hit, no subprocess at all) | median **0.04 ms** |

Cold cost is dominated by process start and is near-independent of text
length (a 650 ms utterance and a 3.4 s one both cost ~0.75 s to make).
Every invocation is a fresh process, so there is no "warm process" — the
warm path is the on-disk cache. That is fine for 7a, where the doctor
taps and waits once per distinct question; it is the number 7c's
pre-synthesis plan has to hide.

Failure never degrades to silence. A missing command or model is
`SpeechUnavailable` (a configuration state); a non-zero exit, a timeout,
or an empty output file is `SpeechFailed` (a fault). Both reach the
doctor as a visible red panel — **a dead speaker must look like a fault,
not like a system that chose not to speak.**

### The disclosure, and the doctor's name

The disclosure wording was **approved by the owner 2026-07-25** and is in
`PHRASES` verbatim, asserted word for word in the tests because it is the
sentence a patient hears:

> Hello. I'm a computer, not a person. I'll ask you some questions about
> what's brought you in. Dr {doctor} is here with you and you can speak
> to him at any time.

It deliberately says **nothing about interrupting** the system, so it
stays true whether or not barge-in is enabled and stays constant across
the face study's arms. A test asserts the absence; **do not add an
interruption line when the detector lands.**

`{doctor}` is interpolated **server-side from the session's doctor
account** — code, never a model, the same convention as `letters.py`.
Fallback is display name, then username. **No title is ever invented**:
the "Dr" lives in the phrase template, not in a transform on the name.

Three things about the live data are the owner's to decide, not to fix
here: no account carries a title; the display names are inconsistent in
form (`herath` → "Herath", `vicky` → "Victoria", `JoydeepSinha1988` →
"Joydeep Sinha"); and the admin account `doctor` has display name
"Doctor", so it would speak as **"Dr Doctor"**. Also flagged rather than
changed: the approved wording's *"you can speak to him"* assumes the
doctor is male, which is a wording change and therefore the owner's.

**The disclosure lock is server-side** (hard rule 4). Every CDS question
and the two clinical phrases are refused until the session has recorded a
disclosure — the phrase played *through* (a cut-off one does not count),
or the doctor ticking "disclosure given in my own words". Both audit
`speech.disclosure_given` with user and timestamp. The disclosure cannot
gate itself; the encouragers are exempt, because "mm-hm" is not a
clinical interaction and gating it would make the lock feel like a
nuisance rather than a rule. A disabled button can be re-enabled from the
console in ten seconds; a server refusal cannot.

### The silence invariant — not detection, and it must not become that

Zero-filled digital silence is a classic Whisper hallucination trigger.
Silero VAD should emit no speech regions on pure zeros, so this should
never fire — which is exactly the sort of claim that deserves a check.
`finalize.drop_segments_in_excluded_spans` drops any segment overlapping
an excluded span, audits `transcript.silence_hallucination`, and feeds
`silence_hallucinations_today` on the monitoring pulse, so "should never
happen" is visible to the sentry rather than buried in a log line.

It **never looks at what a segment says**, and a test asserts that: a
segment whose text is exactly what the system spoke, but *outside* any
span, is kept. It asserts a property of a region that is provably digital
silence, because the pipeline zero-filled it a few lines earlier. If it
ever fires, the fix under consideration is low-level noise instead of
pure zeros — the fill is deliberately **not** changed pre-emptively,
because a real firing is the evidence that would justify it.

### The sound check — a dead speaker eats transcript, silently

Spec Part 10 / D6, owner's addition 2026-07-25. **Built, then POSTPONED
by the owner 2026-07-25** in favour of the consultation-445 investigation
below. The code is in the tree and tested; its specification is safe in
`PHASE_7A_SPEC.md` Part 10. Nothing about it is retracted — it simply has
not been through a room yet.

**This is a safety feature, not a convenience**, and the reasoning is the
whole point:

A dead speaker fails **silently**. If the volume is down or the output
device is wrong, playback still succeeds — nothing errors, because
nothing failed — and the patient simply hears nothing. The doctor reads
that silence as a patient who is not answering. **Worse, the exclusion
window opens anyway**, so for the length of that inaudible utterance the
microphone feeds nothing to the transcript, and whatever the patient says
during it is dropped **by construction**. A dead speaker therefore
converts quietly into missing transcript, with nothing on screen to say
so — the same shape as every other failure this project has designed
against: not visibly broken, just wrong.

The mic cluster answers *"is the room being heard"*. This answers the
other half: *"is the room hearing us"*.

- A **labelled** control beside Start — speaker icon plus the words
  *Sound check*. **Not a cogwheel**: settings iconography reads as
  configuration rather than as test, and icon-only controls cost a beat
  on every use.
- Plays the fixed phrase `sound_check` ("Sound check. If you can hear
  this clearly, press yes.") through the same audio **output** path a
  spoken question uses. Deliberately **not** over the `/ws/transcribe`
  speak protocol — that protocol belongs to a live consultation, and this
  runs before one starts. Two small endpoints instead:
  `POST /api/speech/sound-check` and `.../result`.
- Measures from the **existing** analyser on the capture stream. The
  mic-cluster invariant stands — no second stream for this.
- Reports a **level, not a boolean**, then asks a one-tap question. **The
  human answer is authoritative**; the measurement corroborates it and is
  the part that produces a number.
- Four classes: heard well / heard faint / not heard / unverified. *Faint
  reads differently from silent on purpose* — it predicts both a patient
  who strains and an unreliable barge-in detector later. Declining is
  recorded as **unverified, never as a pass**.
- **Headphones are a known confound and not a warning**: they defeat the
  acoustic path, so energy absent plus a "yes" is expected. The answer is
  accepted and the discrepancy recorded. The same courtesy runs the other
  way — energy present plus a "no" is still `not_heard`.
- **Disabled while recording**, in the UI and again server-side (409). A
  test phrase inside a live consultation would be a system utterance
  needing the whole exclusion machinery for no clinical benefit. A
  disabled button is a courtesy; a refusal is a rule.
- **Offered, never blocking.** The first question tap of a session with
  no check offers one — one tap to run, one to skip — and skipping
  proceeds immediately. Asked once per session, not once per tap.

**On the thresholds, plainly: two of the three are guesses.**

| | value | provenance |
|---|---|---|
| Silence floor | `1e-4` RMS | **Not new.** The same value the mic cluster's dead-mic pill already uses, reused so the two surfaces cannot disagree about what silence is. |
| "Good" boundary | `4.0×` floor (≈ +12 dB) | **Uncalibrated guess.** |
| "Faint" boundary | `1.8×` floor (≈ +5 dB) | **Uncalibrated guess.** |

Nobody has measured this room, this speaker or this microphone. Both
ratios are env-tunable (`SOUND_CHECK_GOOD_RATIO`,
`SOUND_CHECK_FAINT_RATIO`) precisely so the owner can set them from his
own room, and **every raw measurement is stored** in the
`speech.sound_check` audit row — noise floor, peak, mean, ratio, ratio in
dB, plus the thresholds that were in force — so they can be set from real
data rather than re-guessed.

The noise floor is sampled over 400 ms of the quiet room immediately
before playback, and the "peak" is the loudest 50 ms window during it.
Using the floor's own peak (not its mean) as the denominator is
deliberately conservative: it makes the ratio harder to pass, so a noisy
room under-reports rather than over-reports.

**For session 3:** the measured loopback level is exactly the input the
barge-in detector's envelope-proportional threshold needs.
`scripts/calibrate_barge_in.py` should **read these audit rows rather
than re-measure from scratch** — that is why the numbers are stored flat
and raw.

### Consultation 445 — "the missing six minutes" (2026-07-25)

**The first real-room test of 7a, and it lost about six minutes of a
consultation.** 445 is the regression fixture and a failure-mode-library
entry. **It must not be voided, purged or modified** — it is the
evidence.

What the doctor saw: an 11-minute consultation (669 s), 16 tapped
utterances, finalisation completing with **four turns ending at 4:36**,
the transcript-quality gate refusing on a 360.7 s trailing gap, status
`unreliable_transcript`, and no note. Speech the live transcript had
captured — including *"I have type 2 diabetes and I take metformin"* —
was absent from the final transcript entirely.

**The briefed hypothesis was that an exclusion window never closed and
zero-filled the derived copy from 4:40 to the end. That is disproved.**
Established by measurement before anything was changed:

| Suspect | Verdict |
|---|---|
| Capture | **Innocent.** The original WAV holds the speech at full level — RMS 0.056 at 4:44, 0.089 at 7:11, 0.068 at 8:04. |
| Exclusion windows | **Innocent.** All 16 spans well-formed, every `end_reason` `complete`, longest 8.9 s, none running to EOF, union 67.36 s = **10.1%** of the recording. |
| The derived copy | **Innocent.** Measured directly, not reasoned about: bit-identical to the original outside those 16 spans, and *not* zero after 4:40. |
| The quality gate | **Innocent, and the reason we found out.** Its arithmetic was exact including the excluded-span discount (360.66 computed, 360.662 stored). Refusing was correct: the transcript really had lost six minutes. |

**The culprit was the silence invariant added the session before.**
WhisperX's speaker merge joins consecutive same-speaker segments into one
turn, and produced a single turn spanning **284.874–488.829 s**. That
204-second turn *contained* four of our own short utterances totalling
**12.69 s**. The invariant dropped a segment on **any** overlap — so it
discarded all 204 seconds to remove 12.69. **Sixteen times more
transcript than was ever muted.**

The reasoning behind "any overlap" was sound for a segment *straddling* a
boundary and catastrophic for one that *contains* spans. Two changes:

1. **Majority rule.** A segment is discarded only when at least
   `SEGMENT_MUTED_FRACTION` (0.5) of it lies inside muted audio. A
   hallucination on silence sits wholly inside a span (fraction ~1.0); a
   turn that merely contains one got its words from the real audio around
   it (6.2% here).
2. **Ordering.** The check now runs on **raw segments, before the speaker
   merge**. After the merge, a hallucinated fragment can sit inside a turn
   spanning minutes and take it down with it.

The regression test uses 445's real numbers, read from `system_utterance`
and the audit row rather than rounded. One pre-existing test asserted the
old any-overlap behaviour *as if it were the requirement* — which is
exactly how this shipped — so it was rewritten with a comment saying so.

**Two backstops, because the deeper problem is that one utterance
silenced six minutes and nothing objected:** no span may exceed
`SPEECH_MAX_UTTERANCE_S` + tail (clamped, anomaly recorded), and the union
may not exceed `MAX_EXCLUDED_FRACTION` of the recording (default 25%).
Both audit `transcript.exclusion_anomaly` and feed
`exclusion_anomalies_today` on the pulse. They are recorded, not refused —
the quality gate already decides draftability, and a second refusal path
would be a second thing to get wrong.

**Stated plainly so it is not mistaken for a fix: 445 sat at 10.1% and
would NOT have tripped the fraction limit.** It is a ceiling on absurdity,
not a tight bound. What catches that class now is the majority rule.

Also fixed from the same session: the live page had **no landing for the
refusal** — it enumerated the good outcomes and spun on "processing…"
forever while the doctor waited for a note that was never coming. The
list is now inverted (only `live`/`queued`/`processing` continue), so an
unforeseen status lands rather than hangs. Plus three UI faults: the live
transcript logged **button labels** instead of spoken text; the
disclosure never showed itself as **given** and invited a repeat tap; and
the Say-to-patient buttons were tappable while disconnected.

### Hallucinated filler on ordinary silence — ASSESSED, NOT BUILT

445's **live** transcript carried about fifteen turns reading only
"Thank you." (1:43, 3:27, 3:44, 3:47, 5:53, 7:32, 7:35, 7:42, 8:48, and a
run of seven between 10:12 and 10:28). Nobody said them. This is Whisper
filling ordinary room silence, **outside** any excluded span, so the
invariant above does not and should not cover it. Owner's call on the
shape of a defence; findings only:

**1. It is overwhelmingly a live-path phenomenon.** Across all ten stored
consultations there is exactly **one** filler-only turn in a *final*
transcript (#162 turn 0, "Thank you.", 1.9–10.6 s). 445's final
transcript has none. The two paths differ — live is faster-whisper
`distil-large-v3` re-transcribing a short rolling buffer every ~1.5 s;
final is WhisperX `large-v3` with silero VAD over the whole file — and
repeatedly re-transcribing a near-silent rolling buffer is prime
hallucination territory. **The note is grounded in the final transcript,
so this is currently a display problem, not a note-fidelity one.** That
is the reason it can wait; it is not a reason to ignore it, because the
live transcript is what the doctor reads in the room.

**2. Confidence cannot catch it — twice over.**

- On the **live path there is no confidence at all**: `Segment` is
  `(start, end, text)`. A confidence filter there is not merely
  ineffective, it is structurally impossible without changing the
  transcriber's output.
- On the **final path it does not separate**: #162's "Thank you." scores
  **0.646**, sitting inside the modal band (0.6–0.7 holds 74 of 263
  stored turns; 0.7–0.8 holds 79). Genuine clinical turns run 0.58–0.82.
  A threshold catching 0.646 would take out a large share of real
  transcript. This is the same lesson as docket item 4, where two
  load-bearing numbers were corrupted on *confident* turns.

**3. Acoustic energy separates it cleanly, by more than an order of
magnitude.** Measured on 445's own audio:

| Region | RMS |
|---|---|
| Under the live filler timestamps | 0.0077 – 0.0105 |
| Real speech at 7:11 | **0.153** |
| #162's filler turn (1.9–10.6 s) | 0.0077 (file mean 0.0255) |

**4. What a general defence would therefore look like** (sketch, not a
decision): measure the RMS of the **original** audio under each segment's
time range and reject segments whose audio is at the noise floor —
generalising the existing invariant from *silence we created* to *silence
we measured*, with the excluded-span case becoming the special case where
we happen to know it is silent because we made it so. Two cautions worth
carrying into that design: the threshold is a calibration number and
needs real data from this room (same lesson as the sound check); and a
quietly-spoken patient must not read as silence, so it should key on the
noise floor rather than merely "low". A second, cheaper signal is
available free — **words per second**: #162's turn is 8.7 seconds
carrying two words, which is anomalous regardless of energy. One caveat
from the measurements: the 7:32 filler reads 0.054 because a 3-second
window there straddles real speech, so window sizing matters.

### The real-room check — this, not the suite, is what proves it

The suite is evidence about the code. Nothing in it drives a browser, and
no test plays audio into a microphone. **This walkthrough is what tells
us the guarantee holds in the room**, and it should be run before Phase
7a is called done.

The app must be restarted first to pick up this code
(`sudo systemctl restart consultation-ai`) — it runs without `--reload`.
**That restart is also what creates the `system_utterance` table**: the
drift check on 2026-07-25 confirmed the live database does not have it
yet (see "Shared schema module"). Re-run
`uv run python scripts/migrate.py --check` afterwards; it should print
"no drift". Until the restart happens, none of what follows exists in the
running app — the pulse fetched at 12:30 on 2026-07-25 still had no
`silence_hallucinations_today` field, which is the tell.

1. Log in as a doctor. **Before starting**, tap **Sound check** beside
   Start. Confirm you hear "Sound check. If you can hear this clearly,
   press yes.", answer Yes, and note the level it reports. Then start a
   consultation from Today (or a walk-in). (Confirm the Sound check
   button greys out once recording begins.)
2. **Before disclosure:** confirm the question chips and the Invitation /
   Hand-over buttons are greyed. Tap one anyway — nothing should be
   spoken. (The server refuses regardless of the button state; to see
   that, re-enable a chip in the browser console and tap it — a red
   panel should say the patient has not been told.)
3. Tap **Disclosure**. Confirm you hear it through the room speaker, that
   the name spoken is *your* account's, and that the speaking pill
   appears with a Stop button while it plays.
4. Confirm the chips and phrase buttons become live once it finishes, and
   that the disclosure line appears in the live transcript in grey,
   marked *Assistant*.
5. Let the patient-actor talk for a minute. Tap a **question chip**.
   Confirm: it speaks, the pill shows it, all other chips grey out while
   it does, and **the spoken question does not appear as patient or
   doctor text in the live transcript** — only in the grey channel.
6. Tap a chip and press **Stop** mid-sentence. Playback must cut
   immediately.
7. Speak normally straight after an utterance ends and confirm your
   speech still reaches the transcript (the 200 ms tail should cost you
   nothing at conversational pace).
8. Press **Stop** to finish, wait for finalisation, open the review page.
9. **The check that matters:** read the diarised transcript end to end.
   Every question the machine asked must appear **only** in the grey
   *Assistant · spoken aloud* channel — never as a Doctor or Patient
   turn, never with a turn number, and never citable from the note. Click
   through the note's citation chips and confirm none lands on a grey
   line.
10. Confirm the draft note contains nothing the machine said.

**If any machine utterance appears as a patient or doctor turn, stop and
report it — that is the guarantee failing, and it is the one failure this
phase exists to prevent.**

Worth also checking, since they are cheap: pull the speaker cable and tap
a chip (a red error panel, not silence); and confirm
`/api/monitor/pulse` reports `silence_hallucinations_today: 0` after the
consultation finalises.

## Shared schema module (2026-07-25)

`app/schema.py`; tests `tests/test_schema.py`. Built as commit 0 of Phase
7a, because 7a adds a table and the live-versus-code drift found on
2026-07-25 had just cost a debugging session.

**What changed:** nothing about *how* the schema is expressed. The
per-module `SCHEMA_SQL` strings stay next to the code that queries them —
that locality is worth keeping. What there now is exactly one of is the
**ordering** and the **entry point**:

```python
from app import schema
schema.ensure_all()      # auth → frontdesk → consultations → letters → audit
```

Called by the app lifespan, by `tests/conftest.py`, and by every
DB-touching script (`manage_users`, `manage_consultations`,
`ingest_guidelines`, `calibrate_transcript_quality`). Before this, only
the lifespan and conftest made all five calls, so a script that imported
one module got that module's tables and nothing else — a database could
sit in a state no single code path had ever produced.

**`scripts/migrate.py`** applies it; **`--check`** reports drift and exits
non-zero *without writing*: it runs the DDL inside a transaction, compares
an `information_schema` snapshot either side, and always rolls back (the
same rolled-back-transaction technique `tests/test_admin.py` uses for the
last-admin guard). Rows are not compared — the backfill UPDATEs in
`SCHEMA_SQL` touch data, and data is not drift.

**First live run, 2026-07-25 — it found real drift on its first outing.**
Run against the live database (owner-authorised, after confirming
`live_consultation_active` was false on a cache-busted pulse fetch):

```
consultation_ai: schema drift — 1 item(s) the code expects and the
database does not have:
  missing table: system_utterance (17 columns)
```

Confirmed directly against `information_schema`. **This is the expected
self-healing case, not an incident:** `system_utterance` was added in
Phase 7a and the schema is applied by the app's lifespan, but
`consultation-ai.service` has not been restarted since. The restart that
picks up the Phase 7a code creates the table. Nothing was applied by hand
— the design is deliberately that the app applies the schema, and
`--check` reports.

The useful part is that the tool answered the question it was built for
in one command, and the answer was specific: one table, named, with a
column count. Worth re-running after any restart-free deployment.

Two things it deliberately is **not**, both decided before the build:

- **Not a startup refuse-to-start gate.** The app is what applies the
  schema; a gate would convert a self-healing restart into an outage.
- **Not a test against the live database.** That would break the
  deliberate test isolation. `tests/test_schema.py` runs against the
  disposable test database like everything else, and its "no drift"
  assertion is evidence that `check_drift()` and `ensure_all()` agree with
  each other — checking the *live* database is an operator action, which
  is why `--check` is in the after-reboot checklist.

## Troubleshooting (read before touching dependencies)

The dependency battle scars are documented in
`evals/2026-07-07_note_quality_evaluation.md` (audio-path section) and
encoded in `pyproject.toml`. Summary:

- **ctranslate2 ≥4.6 override**: whisperx pins <4.5; 4.4's bundled lib
  fails on WSL2/newer glibc ("cannot enable executable stack").
- **pyannote pinned to 3.4.0** (uv override) + whisperx uses
  `vad_method="silero"` + we call pyannote directly in `app/finalize.py`:
  the whisperx-3.8/pyannote-4 route requires the separately-gated HF model
  `speaker-diarization-community-1`. To upgrade: accept that model's
  licence on HF, drop the override, set `DIARIZATION_MODEL`.
- **torch 2.8 weights_only**: pyannote 3.4 checkpoints need
  `weights_only=False`; scoped monkeypatch in finalize.py.
- **`import torch` fails with missing libcudnn/libcusparseLt**: the venv's
  NVIDIA wheels got corrupted once during resolution churn —
  `uv sync --reinstall` fixes; `app.transcription._preload_cuda_libraries()`
  must run before torch/ctranslate2 imports in fresh processes.
- **NICE URLs are not stable contracts**: NG28's /Recommendations chapter
  silently became research-only content. Validate ingestion with expected
  queries, not chunk counts (see RAG eval, finding 1).
- **torchcodec is excluded via uv override** (2026-07-12): whisperx
  declares it but never imports it; torchcodec 0.7 can't load against
  Ubuntu 26.04's FFmpeg 8, and its mere installed presence makes
  transformers' chunked ASR pipeline throw — which silently produced
  empty transcripts (uniform WER/CER 1.000) the first time the Sinhala
  recordings eval ran. If a future dependency really needs torchcodec,
  it needs FFmpeg ≤7 or a torchcodec release supporting FFmpeg 8.
- **Models published without config files**: the evaluate_sinhala_asr
  long-form path patches over repos missing tokenizer files AND missing
  `generation_config.json` (borrow stock base config — and install it on
  both the model and the pipeline object; the pipeline snapshots its own
  copy at construction and that copy wins).
- Ollama is a user-space install (`~/.local/opt/ollama`), run by the
  `ollama.service` systemd unit since 2026-07-10 (as is the app, via
  `consultation-ai.service` — see the startup sequence below). Models
  keep_alive 30 m.
- sudo needs a real terminal (the assistant's shell can't prompt); batch
  root steps into one command for the user.
- **Test-database bootstrap fails** ("CREATEDB not granted" / "pgvector
  missing from template1"): the suite creates/drops `consultation_ai_test`
  each session instead of touching the live DB (pytest used to leave
  hundreds of active junk accounts in it). One-time setup, safe to re-run:
  `sudo -u postgres psql -c "ALTER ROLE consultation_app CREATEDB;"` and
  `sudo -u postgres psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS
  vector;"` (pgvector is untrusted, so it must live in template1 for the
  test DB to inherit it). Done on this machine 2026-07-24. The suite
  refuses to fall back to the live database by design.

## Toolbox: break-glass user CLI (2026-07-17)

`scripts/manage_users.py` — server shell only, never exposed over HTTP.
For a forgotten admin password, a lost admin, or console role changes:

```bash
uv run python scripts/manage_users.py list                      # all accounts
uv run python scripts/manage_users.py reset-password USERNAME   # prompts; never argv
uv run python scripts/manage_users.py set-role USERNAME ROLE    # promote/demote
```

Passwords are prompted via getpass so they stay out of shell history.
`set-role` refuses to demote the last active admin (same invariant the
admin UI enforces for deactivation). In the UI, every logged-in user has
"Change password" in the nav bar (current password required, audited as
`user.password_changed`).

## Admin governance (2026-07-17)

Built after the Phase 6 verification, admin-only, all 403-tested:

- **Approve-to-activate registration (2026-07-24, public exposure):**
  public registration still works (doctor/receptionist only) but creates
  the account INACTIVE with `pending_approval` set — no session cookie,
  and login answers "awaiting administrator approval" (correct password
  only; a wrong password, or a governance-deactivated account, stays
  "invalid credentials"). The admin approves via the Users view, where
  pending accounts pin to the top with an amber chip and an Approve
  button (the existing reactivate endpoint; first approval audits
  `user.activated`, later governance reactivation stays
  `user.reactivated`; registration audits `user.registered_pending`).
  Tests: `tests/test_registration_approval.py`.
- **Users view** (`/users`): deactivate/reactivate accounts. Deactivation
  blocks login AND kills existing sessions (the cookie stays signed but
  `get_user` only resolves active accounts); rows are never deleted —
  audit events and consultations keep their names. Guards: no
  self-deactivation, never the last active admin (enforced inside the
  UPDATE, concurrency-safe). Audit: `user.deactivated`/`user.reactivated`.
- **Void** (Consultations tab, admin): mark any consultation —
  including approved ones; that's the error-correction point — voided
  with a mandatory reason. Voided consultations vanish from
  doctor/receptionist worklists (410 on direct URL), show struck-through
  with the reason in the admin view, are frozen against edits, and any
  open queue entry for that patient today is cancelled (frees the
  one-active-consultation guard). Content stays in the database. Audit:
  `consultation.voided` {reason}. Mistaken voids are reversible: **Unvoid**
  on the struck-through row restores the consultation to working views in
  its prior state (audit: `consultation.unvoided` with the reverted
  reason).
- **Purge** (separate, second step): "Purge voided test data" hard-deletes
  already-voided consultations (turns/notes cascade), their WAVs, and
  synthetic patients left with no other consultations. Double-confirm in
  the UI. Audit: `data.purged` with counts. Void first, purge second —
  two deliberate steps by design. Tests: `tests/test_admin.py`
  (RBAC, last-admin guard via rolled-back transaction, void-then-purge).

## Connection resilience (2026-07-24)

Built after the owner lost a full remote consultation to a drop near the
end. Principle: **received audio is never abandoned, buffered audio is
never silently discarded.** Tests: `tests/test_resilience.py`.

- **Protocol** (`/ws/transcribe`, live.html is the only client — they
  version together): first message is JSON config with a client
  `session_id`; binary frames carry a 4-byte big-endian sequence number
  before the PCM; the server acks progress (`{"type":"ack","seq":N}`).
- **Client:** unacked frames stay in a ring buffer (capped at 10 min,
  far beyond any grace window); on a drop mid-recording capture
  continues into the buffer, the mic pill shows an amber reconnecting
  state, and the socket auto-reconnects with backoff, sending
  `{resume: true, session_id}`; on `resume` the server names its
  `last_seq` and the client resends only what's missing (duplicates
  are skipped server-side by seq). Stop while disconnected is queued
  and delivered on reconnect.
- **Server:** live sessions live in a registry keyed by session id and
  survive their WebSocket. On abrupt disconnect with audio received,
  the session detaches and waits `LIVE_RECONNECT_GRACE_S` (env, default
  120 s); a reconnect cancels the timer and resumes CDS state intact.
  If the grace expires — or the owner starts a brand-new session (e.g.
  page reload = new session id) — the received audio is finalised
  through the normal queue with **connection_lost** set, which renders
  an amber warning banner on the review page ("the end may be missing —
  review with care"). Resuming an already-finalised session gets
  `resume_failed` pointing at the Consultations tab.

## Concurrent capacity (2026-07-24, investigated + enforced)

**Capacity statement: any number of concurrent logins/browsing sessions
is fine (I/O-bound reads); exactly ONE live consultation and ONE
finalisation pipeline run at a time, both enforced server-side.**

Investigation findings (why the limits exist):

- Two Stops within seconds — reachable today with a single doctor,
  because the queue's one-active-entry guard releases at Stop while
  finalisation keeps running — used to launch two concurrent
  `finalize_consultation` tasks: both load WhisperX+pyannote (6–8 GB
  each) while MedGemma (~17 GB) reloads for whichever reaches the note
  step first (24 GB card ⇒ OOM territory), and
  `transcribe_and_diarise` briefly monkeypatches the process-global
  `torch.load`, which two threads corrupt for each other.
- Two live WebSocket streams — unreachable through the UI (Start gates
  on the single global in-consultation queue entry) but the WS endpoint
  had no server-side guard; two streams would share the one
  faster-whisper model and blow the 2–5 s commit-latency target.

Enforcement (tests `tests/test_capacity.py`):

- **Finalisation queue:** single-consumer asyncio queue in main.py
  (`finalize_worker`); Stop sets status `queued` (worklist/review show
  "processing (queued)") and enqueues; the worker runs pipelines FIFO,
  one at a time, and survives failing jobs. Startup re-enqueues any
  consultation left `queued` with audio on disk, so a crash never
  strands a recording.
- **Live-session wall:** `/ws/transcribe` refuses a second concurrent
  stream with a `busy` message naming the active user (client stands
  down cleanly and shows the reason); slot freed on any disconnect.

## Audio retention (2026-07-24, plan §8)

`app/retention.py`; tests `tests/test_retention.py`. Audio ONLY — the
sweep never touches transcripts or notes.

- **On approval** the consultation's WAV is compressed to lossless FLAC
  (16-bit PCM, sample rate untouched, bit-exact round-trip tested);
  best-effort, approval never fails on compression.
- **Retention sweep** runs at startup and daily (lifespan task): deletes
  audio older than `AUDIO_RETENTION_DAYS` (env, default 90) unless the
  consultation is flagged **keep_for_research** (admin checkbox in the
  Consultations view; audit `consultation.keep_for_research`). Deleted
  rows get `audio_deleted_at` stamped and show "purged (retention)".
  Audit per sweep: `data.audio_purged` {consultation_ids, bytes_freed}.
- Admin Consultations view shows per-recording size and a total-disk
  line. `keep_for_research`/`audio_deleted_at`/sizes are admin-only
  (stripped from the shared worklist payload).
- **Test-safety convention:** `sweep_expired_audio(only_ids=…)` — tests
  MUST scope the sweep (same rule as `purge_voided`); an unscoped sweep
  in a test would delete real recordings the day they age past the
  window.

## Public monitoring pulse (2026-07-24)

`GET /api/monitor/pulse` — **deliberately unauthenticated** (the one
exception to the logged-in wall), for watching an external demo without
logging in. `app/monitor.py`; tests in `tests/test_monitor.py` plus the
RBAC assertions in `tests/test_rbac.py`.

- **Aggregate counts ONLY**: `server_time`, `registrations_today`,
  `logins_today`, `consultations_started_today`,
  `finalisations_failed_today`, `live_consultation_active`,
  `live_slot_rejections_today`, `errors_last_hour`,
  `audio_disk_used_mb`, and (2026-07-24)
  `registrations_pending_activation_today`/`_last_hour` — live counts of
  accounts still awaiting the admin's approval, windowed by registration
  time, so the hourly sentry can say someone is waiting (approve-to-
  activate; `user.registered_pending` also feeds `registrations_today`).
  Never a username, patient name, or clinical
  content — enforced structurally (every value is a number/boolean plus
  one ISO timestamp) and tested against the actual names in the
  database. Keep it that way: any new field must be a count or boolean.
- **"Today" is Europe/London** (`monitor.london_day_start`, DST-correct).
- **Cheap by construction**: the per-day counters are one grouped query
  over the audit log's new `(action, at)` index; DB + disk aggregates
  are cached ~10 s (`PULSE_CACHE_TTL_S`) so external polling cannot
  load the database. `server_time`, the live boolean, and the error
  counter are in-memory and always fresh.
- **New audit events feeding it**: `live.slot_rejected` (the
  one-active-consultation guard firing — logged at all four refusal
  sites: walk-in 409, queue-start 409, WS global wall, WS duplicate
  tab; detail carries `via`. Expected under concurrent demo users, so
  counted separately from errors) and `finalisation.failed` (system
  event, user_id NULL). Being audit rows, the counts survive restarts.
- **Fetch it with a cache-busting query parameter.** On 2026-07-25 the
  hourly demo sentry was found to have been blind for roughly a day: its
  bare `WebFetch` of the pulse URL was being served a **cached payload
  from 2026-07-24 15:44**, predating the `_last_hour` counters. So it
  reported "no activity" every hour, and could not have reported a dead
  Funnel either — **a cached 200 never fails**. That is the failure mode
  worth remembering: a monitor that cannot fail is not a monitor.
  **The endpoint was never at fault.** The stale payload's missing
  fields produced a confident, entirely wrong bug report against
  `/api/monitor/pulse` that nearly became a commit; the fix was in the
  scheduled task's own prompt (cache-busting parameter, a `server_time`
  freshness check, and an explicit rule not to diagnose the app's code
  from a stale payload), and was verified by a manual fire. Anything
  reading this endpoint programmatically should do the same:
  `?cb=<UTC date+hour>`, then check `server_time` before believing a word
  of it.
- **`audio_disk_used_mb` is decimal MB (10⁶), since 2026-07-25.** It
  previously divided by 1024² and called the result "mb" — MiB under an
  SI label. The admin worklist had the identical mislabelling and both
  now use decimal. Decimal was chosen over renaming the field to `_mib`
  because this field is public and the sentry consumes it *by name*.
  **The pulse total and the admin Consultations total still differ, and
  legitimately so:** the pulse walks the recordings *directory*, the
  admin page sums only recordings *linked to a consultation row*. On
  2026-07-25 that was 37 files (213.7 MB) against 9 files (203.9 MB) —
  **28 orphan WAVs on disk with no consultation row**, which the
  retention sweep will never collect because it works from consultations.
  Flagged, not deleted. If the two numbers are ever reported as
  disagreeing again, this is why, and it is not a units bug.
- **`errors_last_hour`** counts unhandled exceptions and 5xx responses
  via the `count_errors` middleware into an in-process ring buffer
  (maxlen 1000, pruned on read). 4xx refusals — RBAC probes, guards —
  are deliberately NOT errors. In-process by design: restarts zero it.

## Phase 6 — agreed UI structure (do not re-litigate)

Three tabs, mirroring a Sri Lankan GP surgery:

1. **Today** — the queue, role-split: receptionist registers patients and
   manages the walk-in queue (`waiting → in consultation → done`); doctor
   sees the same queue read-only and picks the next patient.
2. **Consultation** — the live view (current /live page, reached by
   starting a consultation from the queue).
3. **Consultations** — worklist of past/processing consultations with
   status badges (`processing / awaiting review / approved / failed`),
   opening into the review page.

Explicitly v2 (out of scope): a demographics tab, calendar/appointment
scheduling. Roles per plan: doctor / receptionist / admin; receptionist
must not open transcripts or notes.

## Phase 7 opened (2026-07-25) — with two gate items carried

**Owner decision: Phase 7 is open.** Two of the three entry-gate items
were **deliberately carried rather than met**. This is a decision to
proceed knowingly; the items did not stop mattering.

| Gate item | State | Why |
|---|---|---|
| `05_epigastric_pain_en` | **carried** | Cannot be recorded for roughly 8 days (reader availability). |
| Docker Compose packaging + two-role demo script | **carried** | Spec exists but awaits the owner's decisions. |
| Finalisation transcript-quality gate | **MET, for its refuse path** | Built and live (commit `1277a31`): S2 < 0.60 and S4 > 20 s refuse independently, no note drafted, status `unreliable_transcript`. |

First commitment inside Phase 7 remains **7a (tap-to-ask) + 7b (face)**,
with 7c committed separately after review. 7b's build brief is
`PHASE_7B_KINDALIVE.md`; note the **new hard requirement on 7a** in
`PHASE_7_SPEC.md` — system-spoken utterances excluded from the patient
transcript by construction, never by prompt or post-hoc filtering.

**Outstanding work carried alongside — recorded here so none of it is
lost while Phase 7 takes attention:**

1. **The transcript-quality gate's flag tier is specified but unbuilt.**
   Thresholds are recorded (S2 < 0.70, S4 > 10 s) and the config keys
   sit unused in `.env.example`, so the follow-up sets behaviour rather
   than inventing numbers. It needs the acknowledge-gated amber banner
   and the 409 approval block — `TRANSCRIPT_QUALITY_GATE_SPEC.md` §11,
   "v1 build scope".
2. **S1 and S3 redesigns are pending.** S1 must go multi-window
   (single-window detection returns English at p=0.90 for #70); S3 must
   measure *within* segments (cross-segment run length is 1 everywhere).
   Neither may act until re-calibrated against 66–70. **Shared-measurement
   requirement — partly discharged 2026-07-25:** S2 and S4 are now single
   implementations in `app/transcript_quality.py`, with
   `scripts/calibrate_transcript_quality.py` delegating to them (Phase 7a
   had to change S4's arithmetic, and two copies would have diverged).
   **S1 is still two code paths**: measured inside
   `app/finalize.py::transcribe_and_diarise` (reusing the already-loaded
   WhisperX model) while the calibration harness measures it
   independently. The redesign must collapse those into one shared
   function, or the calibration will stop describing what the pipeline
   actually does.
3. **Schema-drift protection: BUILT 2026-07-25** as commit 0 of Phase 7a
   (`PHASE_7A_SPEC.md` §3.4 — 7a adds a table, which made this the
   cheapest moment to pay for it). See "Shared schema module" below.
4. **Phase 2 real-audio validation still needs `05_epigastric_pain_en`**
   — the same recording as gate item 1, so the two unblock together.
5. **Consultations #78 and #162 await the owner's review** (both
   `awaiting_review` in the live database, verified 2026-07-25).
6. **Phase 7a session 3**: the barge-in detector (second echo-cancelled
   stream, envelope-proportional threshold) and
   `scripts/calibrate_barge_in.py` reporting both sides of the D5 target.
   Deliberately held until the owner has used tap-to-ask in the real
   room. `BARGE_IN_ENABLED` ships false — hard mute is this design with
   the detector off — and flips only if calibration meets both sides of
   the target. Two standing constraints for whoever builds it: the
   detector stream must never be wired to the mic meter, and the approved
   disclosure must not gain an interruption line. **Read the sound-check
   levels from the `speech.sound_check` audit rows rather than
   re-measuring** — that loopback level is exactly what the
   envelope-proportional threshold needs, and it is already being
   recorded. The good/faint ratios there are uncalibrated guesses and
   should be set from the same run.
7. **The Phase 7a real-room check has been run ONCE, on 2026-07-25, and
   it found a serious defect** — consultation 445, "the missing six
   minutes" (see its section). The defect is fixed and pinned by a
   regression test built from 445's real data. **The check has not been
   re-run since the fix**, so the guarantee is again proven in code and
   not in the room. Re-run it before calling 7a done.
8. **Hallucinated filler on ordinary silence: assessed, not built.** About
   fifteen phantom "Thank you." turns in 445's LIVE transcript. Confidence
   cannot catch it (there is none on the live path, and on the final path
   it does not separate); acoustic energy separates it by more than an
   order of magnitude. Findings and a sketch are in its own section; the
   shape of any defence is the owner's call.
9. **The sound check is built but postponed** — untested in a room, and
   its good/faint thresholds are uncalibrated guesses.

## Pre-Phase-7 build item: finalisation transcript-quality gate

**Promoted out of the deferred review docket on 2026-07-25** (was docket
item 5) and now the third item of the Phase 7 gate.

**Spec: `TRANSCRIPT_QUALITY_GATE_SPEC.md`** (repo root), revised
2026-07-25 after the calibration run — **read its §11 first**, which
supersedes the signal selection in §3, the outcomes in §5, the config in
§6 and the tests in §8. §§1–10 are left standing so the superseded
reasoning stays visible beside its correction. Calibration harness:
`scripts/calibrate_transcript_quality.py`; measured table in
`evals/transcript_quality_calibration.json`.

**Why it was promoted.** Declaring the project English-only (2026-07-25)
makes this gate load-bearing rather than a nice-to-have. The app is
publicly reachable via Tailscale Funnel, and an approved public account
has real clinical-role access. A non-English speaker who records a
consultation would otherwise be handed a **fluent, fabricated note** —
which is not hypothetical: it is exactly what consultation #70 produced
(Sinhala audio through the English-forced pipeline → hallucinated
English translation, repetition loops, avg confidence 0.49, last 33 s
dropped → a normal-looking draft that was presented and approved).
English-only removes the Sinhala path but not the failure: it converts a
known-language limitation into a silent one.

**What it must do.** On **language mismatch** or **low average
confidence**, flag the review as unreliable instead of presenting a
normal draft — the same shape as the note grounding gate
(`validate_and_gate`, `NOTE_MIN_CITED_FRACTION`), which already refuses
rather than drafting when a note cannot be grounded. The failure mode
being defended against is a plausible artifact, not a visibly broken
one; the defence therefore has to sit in code and refuse, not in a
warning the doctor can read past.

Full #70 history, including the void/unvoid/re-void sequence, stays in
docket item 5.

## Deferred end-of-project review docket (project owner = doctor)

1. **Script-02 dengue boundary case** (urgency eval): transient alarm on
   borderline WHO warning signs (vomiting ×2 + anorexia, day 3); content
   matches the script doctor's own plan; recorded as FAIL per the
   unamended marking scheme. Decide: relax expectation, or encode a
   ≥3-episodes vomiting threshold with clinical sign-off.
1b. **Script-11 TATT over-commitment boundary case** (restraint eval,
   2026-07-17): the CDS kept the differential correctly broad (all 5
   finals in the marking scheme) but graded iron-deficiency anaemia AND
   depression/anxiety "high" on the undifferentiated tired-all-the-time
   case, failing the scheme's strict "none high-confidence". Both are
   clinically defensible top candidates (heavy periods → iron loss; flat
   mood), so this is early over-commitment, not a wrong list. Decide:
   is strict "none high" the right bar for an undifferentiated
   presentation, or should one defensible high-confidence leader be
   allowed? Same class of call as the dengue case.
2. **Claim-by-claim fidelity audit** of RAG summaries and SOAP notes —
   human-led. Context: the LLM-judge experiment failed in both directions
   (over-flagged without the transcript: 15 false positives; missed both
   known-real errors with it) — see the note-quality eval. Consider a
   different model as assistant, never the authoring model.
3. **Specimens for that audit**: invented "atorvastatin **1mg**" dose
   (transcript says "one at night") and inverted monofilament finding
   ("toes and ankle" vs toes-only) — both in the deterministic script-03
   note; a "**wheelbarrow**" noun substitution where the transcript said
   *three-wheeler* (2026-07-07 live loop test — caught by clicking the
   claim's citation chip during review, which is exactly the verification
   loop working); plus the RAG aspirin-qualifier paraphrase ("unless
   contraindicated" vs CG95's "unless clear evidence of allergy"); and
   specimen 4 (2026-07-15, consultation #78): a mic-check transcript
   yielded a wholly fabricated angina consultation, every claim uncited —
   now blocked by the note grounding gate (`validate_and_gate`,
   `NOTE_MIN_CITED_FRACTION`, refusal instead of draft; see the
   2026-07-17 addendum in the note-quality eval).
4. **Confidence-flag heuristic failed its first real test** (2026-07-17
   recordings deviation report): two load-bearing numbers were corrupted
   on CONFIDENT turns (HbA1c 8.4 → "84", respiratory rate 18 → "80") —
   the ⚠ flag never fired because it keys solely on ASR confidence.
   Needs a plausibility-range defence for clinical numbers (an RR of 80
   or an HbA1c of 84 is physiologically absurd), not just confidence.
   Clinical sign-off on the ranges is the owner's.
5. **Finalisation needs a transcript-quality gate** — **PROMOTED
   2026-07-25 out of this docket to a pre-Phase-7 build item** (see the
   section immediately above; it is now the third item of the Phase 7
   gate). The requirement is no longer deferred; the #70 history below
   stays here as the record of how it was found. Consultation #70's
   Sinhala audio went through the English-forced pipeline and produced a
   hallucinated English translation (repetition loops, avg confidence
   0.49, last 33 s dropped) — and a normal-looking draft note was
   presented and approved. Low average confidence or language mismatch
   should flag the review as unreliable, analogous to the note grounding
   gate, not present a normal draft.

   **Full void history of #70, from the audit trail (verified
   2026-07-25).** Four events, not two:

   | When | Action | By |
   |---|---|---|
   | 2026-07-17 17:02:46 | `consultation.voided` (the original, for the invalid transcription) | user 10 |
   | 2026-07-22 07:11:20 | `consultation.unvoided` | user 10 |
   | 2026-07-24 10:43:32 | `consultation.voided` — the documented restoration, `restoration` detail | user_id NULL |
   | **2026-07-24 10:49:20** | **`consultation.unvoided` again — six minutes after the restoration** | user 10 |

   The first unvoid (07-22) was the governance-testing incident
   investigated on 2026-07-24: the Unvoid button was exercised on a real
   row 39 s before a batch of "Test case" voids and never reverted, so
   #70 sat wrongly approved-and-visible for two days. The restoration
   re-voided it. **Six minutes later it was unvoided again**, and that
   second recurrence went unrecorded until the 2026-07-25 calibration
   run read the row directly.

   **The lesson, honestly.** Item 5's existing lesson was *don't
   exercise governance actions on real rows*. The identical failure
   recurred **within six minutes of the fix that documented it**. A
   written lesson did not prevent recurrence — which is why the
   correction is the code guard below (void reason classes +
   unvoid friction, `consultation.unvoid_refused`) and not a third note
   telling people to be careful.

   **#70 was re-voided 2026-07-25 10:59:07 — this is now CLOSED.**
   Verified against the audit trail and the row itself: `voided_at` is
   set, `keep_for_research` is true, and the void carries reason class
   **`clinical_safety`**, which the guard below makes irreversible over
   HTTP (reversal is break-glass only). It was done `via break-glass CLI`
   with a reason naming it as the transcript-quality gate's regression
   fixture and saying never purge. `status` still reads `approved`, which
   is correct and not a leftover: voiding stamps `voided_at` rather than
   rewriting status.

   The earlier ⚠ in this item said the state was still wrong and the
   re-void outstanding. That was true when written at 10:29 and was
   superseded half an hour later.

   **#70 must never be purged.** It now carries `keep_for_research`
   (set 2026-07-25 03:06), protecting its audio from the retention
   sweep. It is the regression fixture for the transcript-quality gate
   (`TRANSCRIPT_QUALITY_GATE_SPEC.md` §11) and the object of study in
   `evals/2026-07-25_sinhala_confound_prereg.md`. **Its correct end
   state is voided and preserved** — out of clinical worklists, retained
   in full on disk.
6. **Workflow observation — end-of-recording contamination**: recordings
   66 and 68 captured off-script reader speech after the scripted close
   (worst: 68's "I don't read the script but I do naturally"). Owner's
   ruling 2026-07-17: ASR-scoring references are truncated at the
   scripted close; the recordings themselves stay untouched on disk.
   Future recording sessions: pause capture before debriefing.
7. **Two-hats loop-test notes** (2026-07-07, project owner playing both
   roles in one voice, consultation deliberately interrupted): diarisation
   held up despite a single speaker — one boundary merge only; and the
   note generator left Assessment and Plan **empty rather than
   fabricating** when the consultation never reached them. Both behaviours
   worth preserving; re-check them during real-audio validation.
8. **ASR specimen — code-switched near-homophone collapse** (from the
   2026-07-25 adjudication, `03_diabetes_review_si`):
   rrashmini-large-v2 renders *ulcer* as පල්සර් and the immediately
   following reference word *pulses* as පල්සර්ස්. Two clinically
   opposite findings collapse onto near-identical output **in adjacent
   words**, in a sentence whose meaning is *no ulcer, pulses present*.
   (Not a single-model quirk: seniruk-small does the same thing one
   glyph over — අල්සර් නෑ අල්සර්ස්.) This is the code-switched analogue
   of the existing noun-substitution specimens (the *wheelbarrow* /
   three-wheeler substitution, specimen 3) — same failure class,
   reached by transliteration collision rather than acoustic confusion.
   For the claim-by-claim fidelity audit (item 2).
9b. **Consultation 445 — an invariant that ate six minutes** (2026-07-25,
   full account in its own section above). A safety check added to catch
   one failure caused a worse one: the silence invariant dropped a
   204-second turn to remove 12.7 s of muted audio. For the failure-mode
   library, the generalisable lesson is not about spans — it is that
   **a defence whose failure mode is deletion needs a proportionality
   rule**. "Any overlap" seemed conservative and was the opposite: it
   maximised what was thrown away. Two supporting observations worth
   keeping: the test suite *encoded the bug as the requirement* (a test
   asserted any-overlap dropping, so the fix had to rewrite an assertion
   rather than add one), and the transcript-quality gate is what surfaced
   it — the layer that refused was doing its job, and without it a
   four-turn transcript would have been drafted from.

9. **Safety note carried forward from the adjudication:** any future
   Sinhala transcription path must be evaluated **specifically on
   drug-name and numeric-marker recovery**, not on CER or WER alone.
   The four terms lost by every model were two drug names (`losartan`,
   `atorvastatin`), the three-month control marker (`HbA1c`), and the
   diagnosis (`neuropathy`) — while the aggregate metrics rated the
   models as merely mediocre. Aggregate error rates do not see this
   class of loss; the step 6 method (curated terms, adjudicated) does.

## Phase 5 — CLOSED with a negative result (2026-07-25)

Benchmark stage (plan §7 "benchmark FIRST, train later") completed
2026-07-10 — `evals/2026-07-10_sinhala_asr_benchmark.md`, harness
`scripts/evaluate_sinhala_asr.py`. What a newcomer needs to know:

- **No public Sinhala test set exists** (Common Voice never collected
  Sinhala; FLEURS, MMS, SeamlessM4T all skip it). Benchmarked on two
  OpenSLR corpora (SLR52 sample n=500 / SLR30 sample n=250, seed 42)
  with per-model contamination documented — the dual-set design caught
  one candidate that had memorised SLR30.
- **Stock Whisper (any size, incl. large-v3) emits degenerate
  repetition loops on Sinhala** — so Phase 5 must swap both
  transcription paths, not just the live one.
- **Front-runner:** `seniruk/whisper-small-si` (CER 0.035 on both
  sets); challenger `janiduchamika/whisper-small-sinhala-general-185k`.
- **Code-switched scripts now exist:** `01_chest_pain_si.md` and
  `03_diabetes_review_si.md` — patient mostly Sinhala with embedded English
  medical/loan terms ("pressure eka", drug names, test names), doctor mixes
  both. Each carries the Sinhala-script as-spoken reference transcript
  (parseable turns), a turn-by-turn romanised reading guide for the readers,
  the clinical-content marking scheme (identical to the English twin), and
  the curated English-term list the code-switching metric needs. Draft
  references generated via `app/mock_scripts.py` sit in
  `mock_consultations/recordings/refs/*.txt` — correct to as-spoken and
  freeze before viewing model output, per the pre-registration.
- **Recordings eval executed 2026-07-12** on `03_diabetes_review_si`
  (`evals/2026-07-12_sinhala_asr_recordings_eval.md`): reference frozen by
  the owner's verbatim attestation, 12-term curated list frozen before any
  output viewed. Headlines: all models collapse on real conversational
  code-switched audio (best CER 0.46–0.50 vs 0.035 on read speech);
  English-term mechanical recall 0/106 for every fine-tune — some
  transliterations clean (metformin → මෙත්ෆෝමෙන්), some dangerous
  (gliclazide → වික්පසායිල්). Ranking reshuffled: xlsr-sinhala (CTC) best
  CER but fragmentary output; seniruk-small best Whisper and best WER.
- **Off-the-shelf landscape is exhausted:** no seniruk-large exists; the
  four other RRashmini repos hold only two distinct models (one is the
  benchmarked large-v2 under another name, byte-identical transcript; the
  other is worse, 0.710; the medium repo is empty). Post-hoc screen kept
  separate: `evals/sinhala_asr_results_recordings_posthoc.json`.
- **Adjudication done 2026-07-25 (step 6), and it changed the ranking.**
  The owner adjudicated the frozen worksheet
  (`evals/adjudication_03_si_worksheet.md`) with the pre-registered
  binary intact — transliteration hit / genuine loss, plus whether the
  clinical content survives. Clinical survival: **seniruk-small 7/12,
  xlsr-sinhala 1/12, rrashmini-large-v2 0/12.** So seniruk-small now
  leads *despite* xlsr's better CER (0.462 vs 0.504) — the mechanical
  0/106 recall figure had concealed the only difference with clinical
  meaning. Four terms — `HbA1c`, `losartan`, `atorvastatin`,
  `neuropathy` — survive in no model at all; for a diabetes review that
  is two drug names, the three-month control marker, and the diagnosis.
  What did NOT change: no off-the-shelf model is usable for
  code-switched clinical Sinhala. Full table and limitations (unblinded,
  single adjudicator) in the eval record's § Step 6.
- **Decision (step 7), 2026-07-25: Phase 5 is CLOSED with a negative
  result, and the fine-tune is NOT PROCEEDING** — owner's call, with the
  eight sign-offs in the groundwork plan deliberately not sought.
  **Consultation AI is English-only for v1: Sinhala is out of scope, not
  postponed.** The pre-registered investigation ran to completion and
  its conclusion stands; the negative result *is* the Phase 5 finding.
  The plan is preserved unchanged as the restart point — see its
  decision header (`evals/2026-07-17_finetune_plan.md`), which also
  carries the one substantive amendment: lead with
  `seniruk/whisper-small-si`, not xlsr. **Restart trigger (narrow):**
  only a materially better Sinhala or multilingual model, or a
  code-switched clinical dataset, appearing — a demo or study commitment
  is not a trigger. Whoever restarts reads § Step 6 first.
- **One piece of Sinhala work remains designed and available** (the
  phase stays closed — this is not queued work): a pre-registered
  decomposition of the 0.035 → 0.504 CER confound,
  `evals/2026-07-25_sinhala_confound_prereg.md`, **designed 2026-07-25,
  NOT RUN, no data collected.** Trigger: Prof Henry Potts replying with
  interest, or the owner deciding to write up the benchmark. It cannot
  change the English-only decision and is not intended to — it refines
  the explanation of the collapse for the paper. Two solo read
  recordings, no second reader needed, which is why it stays feasible
  while the rest of Sinhala is closed.
- **Out of scope for v1 with it:** the translation layer (Gemma/NMT
  benchmark, plan §4) and dual-language transcript generation. The
  project-wide English-only decision and its two deliberate retentions
  (research artifacts; the si/en seam in `FinalTranscript`) are recorded
  in PROJECT_PLAN.md §§4, 7 and under "English-only for v1" in Key
  design decisions above.

## CDS restraint dimension — built and evaluated (2026-07-17)

**Status update:** the differential-breadth restraint metric is now built
(`scripts/evaluate_cds_restraint.py`) and run — see
`evals/2026-07-17_cds_restraint_evaluation.md`. Both arms on script text
(the correction below): **urgency 5/5, restraint 4/5**. 14/15 catch the
buried emergencies and clear; 11/12 don't false-alarm; 13 narrows
confidently to migraine; **11 is the one restraint FAIL** — it keeps the
list broad but over-grades two conditions "high" on the undifferentiated
TATT case (a subtle, clinically-arguable over-commitment, now on the
docket for adjudication). Correction absorbed: the HANDOVER previously
said `_uk` wires in "once recorded", but the urgency/CDS harnesses run on
script text (as the 2026-07-07 eval did); recordings later add only the
noisy-ASR arm. The urgency harness keeps `UK_EXPECTATIONS` separate from
the canonical `EXPECTATIONS`, so `urgency_results.json` is unchanged.

A new evaluation dimension the existing eval records don't cover: does the
CDS keep the differential appropriately **broad** on undifferentiated
presentations, or does it over-commit? Introduced by the UK private-GP
series (`_uk`), designed as controlled comparisons:

- **11 (TATT), 12 (dizziness)** — undifferentiated; the differential must
  stay broad and the urgency alarm must stay silent (negative controls).
- **13 (migraine)** — the differentiable *positive* control: the picture is
  textbook, so narrowing confidently IS correct. Proves restraint is
  calibration, not blanket caution.
- **14 (giant cell arteritis), 15 (cauda equina)** — subtle emergencies with
  red flags buried in casual, minimised asides; the alarm must fire. 13 and
  14 are a controlled headache pair (same complaint, opposite correct
  behaviour).

Each header carries its Expected clinical content + Expected urgent_actions
marking schemes, written before any recording. **Deliberately not wired into
the harnesses yet:** `scripts/evaluate_urgency.py` runs an explicit
filename→expected dict and `scripts/evaluate_notes.py` globs `[01]*_en.md`,
so neither picks up `_uk`/`_si` automatically and existing eval runs are
unaffected. To evaluate once recorded, add the `_uk` names to the urgency
dict (11/12/13 → False, 14/15 → True); the restraint metric itself
(differential breadth / over-commitment) still needs a harness.

## Precise next steps

- **Phase 0 (close out):** recorded 2026-07-12: routine 01–04 English +
  `03_diabetes_review_si` (via the live app; WAVs in
  `mock_consultations/recordings/`, named per README). **Still to
  record: `05_epigastric_pain_en`** — required for Phase 2 real-audio
  validation and the note-quality eval. **Phase 0 closes out on that one
  recording**: `01_chest_pain_si` is **not being recorded for v1**
  (2026-07-25) — it needs a Sinhala-speaking second reader and only
  feeds an out-of-scope arm. The script stays in the tree, available if
  Sinhala ever restarts. Decide Git LFS.
- **Phase 2 (validate on real audio):** the recordings already ran the
  full live→Stop→review pipeline as they were made; still to do: review
  the two consultations left awaiting review, check diarisation/roles and
  confidence flags (first real test) against marking schemes, and append
  a real-audio section to the note-quality eval.
- **Phase 5: CLOSED with a negative result — nothing outstanding, and
  nothing queued.** Recordings eval run on `03_diabetes_review_si`,
  adjudicated 2026-07-25, and the fine-tune **NOT PROCEEDING** by owner
  decision the same day (the eight sign-offs in the groundwork plan were
  deliberately not sought, not left pending). **Sinhala is out of scope
  for v1, not postponed** — see "English-only for v1" in Key design
  decisions. See the status table, the eval record's § Step 6, and the
  decision header in `evals/2026-07-17_finetune_plan.md` — which stays
  the restart point, with its data sources/licences, code-switch
  synthesis strategy, base-model arms, 4090-sized recipe and
  pre-registered gates preserved unchanged. No training started.
- **CDS restraint dimension:** UK `_uk` scripts (11–15) written with marking
  schemes; wire them into the urgency dict once recorded, and build the
  differential-breadth metric (see the CDS restraint section above).
- **Phase 6:** core is built and manually verified (auth + roles, queue,
  three tabs, RBAC, audit log; click-through and adversarial checks done
  2026-07-10 — see status table). Design pass, strict scoping, and
  referral letters shipped 2026-07-24 (see the design-pass section);
  in-browser verification of the six-stage UI work completed by Claude
  Cowork 2026-07-24. Next: Docker Compose packaging and the two-role
  demo script.
- **Whole-project:** the end-of-project review docket above.
- **Phase 7 (OPEN; 7a items 0–4 built 2026-07-25):** supervised auto
  history-taking is spec'd in `PHASE_7_SPEC.md`, and 7a's *how* is in the
  repo as `PHASE_7A_SPEC.md`. Built: the shared schema module,
  `app/speech.py` (Piper as an isolated subprocess), the live-path
  exclusion with the `system_utterance` table, the finalisation
  exclusion, the doctor-facing UI with the disclosure lock, and the sound
  check (spec Part 10). **Tap-to-ask works end to end.** Session 3 is the barge-in detector and
  its calibration script, deliberately held until the owner has used this
  in the real room — and **the real-room check in "Phase 7a — the
  transcript guarantee" has not been run yet**, so the guarantee is
  proven in code and not in the room. **OPENED 2026-07-25 by owner
  decision**,
  with `05_epigastric_pain_en` and the Docker/demo work **deliberately
  carried** rather than met; the transcript-quality gate item is **met
  for its refuse path**, which is live. Full amendment, plus the five
  pieces of outstanding work carried alongside, in the "Phase 7 opened"
  section above. First commitment is 7a (tap-to-ask) + 7b (face — build
  brief in `PHASE_7B_KINDALIVE.md`), with 7c decided separately after
  review. Note 7a's new hard requirement: system-spoken utterances stay
  out of the patient transcript **by construction**.

## Remote access (Tailscale, set up 2026-07-10)

The app is reachable from the project owner's other devices over their
private tailnet at **https://mlrig.tail93fa1d.ts.net** — HTTPS is
mandatory for remote microphone access (browsers only allow getUserMedia
on secure origins). Since 2026-07-24 the app is ALSO reachable from the
public internet via Tailscale Funnel (owner's decision, external demo) —
see the public-exposure posture section below.

How the pieces fit (each is required):

1. **Tailscale on Windows** (host `mlrig`, 100.94.144.52) — the tailnet
   endpoint. Signed in as wajirah@; other devices must run Tailscale on
   the same account.
2. **WSL2 mirrored networking** (`C:\Users\wajir\.wslconfig`,
   `networkingMode=mirrored`) — WSL shares the Windows network
   interfaces, so a WSL service on 0.0.0.0 is reachable at the Windows
   machine's addresses. Changing .wslconfig requires `wsl --shutdown`
   from Windows — that kills every WSL process (shells, uvicorn, Ollama,
   any running Claude session); see the startup sequence below for what
   comes back by itself and what doesn't.
3. **uvicorn must bind 0.0.0.0** (not the default 127.0.0.1) — see
   startup sequence below.
4. **Tailscale Serve** (`tailscale.exe serve --bg 8000` on Windows,
   runnable from WSL via the interop path below) — terminates HTTPS with
   a tailnet certificate at mlrig.tail93fa1d.ts.net and proxies to
   port 8000. The config persists across reboots; it needed a one-time
   "enable Serve" approval in the admin console. WebSockets are proxied
   fine; live.html already picks wss:// under https.

## Public-exposure posture (Tailscale Funnel, 2026-07-24)

The owner exposed the app to the public internet via Tailscale Funnel
for the external demo. Everything below exists because of that; the
defence layers, outermost first:

- **The logged-in wall** stands everywhere except `GET /api/monitor/pulse`
  (deliberate, aggregate-only — see the monitoring-pulse section).
- **Approve-to-activate registration**: a public registrant gets an
  inactive account until the admin approves it in the Users view (see
  the admin-governance section). Approval is the gate: an approved
  public account has real clinical-role access, including the single
  live-consultation slot — approve only people you know.
- **Per-IP rate limits** on login and registration (`app/ratelimit.py`,
  env-tunable, clear 429 + Retry-After). `client_ip` trusts
  X-Forwarded-For only when the direct peer is loopback, which is where
  Tailscale Serve/Funnel terminates — direct peers cannot spoof it.
- **Source-IP forensics**: `user.login` / `user.login_failed` (new; has
  the typed username + reason) / `user.registered_pending` audit events
  all carry `ip` in their detail.
- **Test isolation**: pytest runs in a disposable `consultation_ai_test`
  database and can no longer create accounts (or anything else) in the
  live one.
- **Repo visibility**: verified PRIVATE on GitHub 2026-07-24
  (`gh repo view --json visibility`) — an earlier assumption that the
  fixed test password was world-readable was wrong; it is still a
  shared fixed string, hence the sweep below.

**Legacy junk-account sweep: DONE 2026-07-24** (owner-approved). All 489
pre-isolation test accounts (`role_8hex` names, shared password
`test-password-123`, incl. ~131 admins) were bulk-deactivated in one
audited action — audit row `user.deactivated` `{bulk: true, count: 489}`,
user_id NULL. With test isolation in place they cannot reaccumulate.
The active set was five at that point (owner-confirmed): `doctor`
(admin), `receptionist`, `herath`, `vicky`, and invited demo user
`JoydeepSinha1988`. Accounts are deactivated, never deleted — the rows
keep their names for the audit trail.

**The active set is now six** (verified against `app_user` and the audit
log 2026-07-25). The list above was correct when written; approve-to-
activate then did its job and added one:

| | |
|---|---|
| `claudia` (id 572, receptionist) | registered 2026-07-25 11:37:27 from **100.94.144.52 — mlrig's own tailnet address**, approved 37 s later by user 10 (the `doctor` admin account), first login 11:38:17 from the same address |

That shape — self-registration from the host machine, approved by the
owner within the minute — reads as the owner exercising the
approve-to-activate flow rather than an outside registrant. Worth
re-checking the count after any demo: a growing set is the *expected*
behaviour of a public registration page, not a defect, and the number
here should be treated as a snapshot rather than an invariant.

## After-reboot startup sequence

Since 2026-07-10 everything is systemd-managed (`/etc/systemd/system/
ollama.service` and `consultation-ai.service`, both enabled,
Restart=on-failure): Postgres, Ollama, and the app all start when WSL
boots. WSL itself does not boot until something starts it — after a
Windows reboot, open a WSL terminal once (it can be closed again;
running services keep the VM alive). Then verify:

```bash
systemctl is-active postgresql@18-main ollama consultation-ai
# and that Serve still routes (config persists, this just checks):
"/mnt/c/Program Files/Tailscale/tailscale.exe" serve status
# and that the live database still matches the code (read-only; the DDL
# runs in a transaction that is always rolled back). Exits 1 on drift:
uv run python scripts/migrate.py --check
```

`migrate.py --check` is the drift report added 2026-07-25 with
`app/schema.py` — see "Shared schema module" below. It is a report, not a
gate: the app applies the schema at startup, so a restart is the fix.

Manual fallback (if ever needed): `ollama serve &` and
`uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` — 0.0.0.0
matters for remote access. Logs: `journalctl -u consultation-ai`.

If Postgres is down after a reboot (`pg_isready` says no response), check
`systemctl status postgresql@18-main`. Mirrored networking means Windows
and WSL share one port space; a leftover Windows PostgreSQL 18 service
(`postgresql-x64-18`, empty default databases only) used to auto-start,
grab 5432 first, and the WSL cluster then failed with "address already in
use" — worse, the app would reach the *Windows* Postgres and die with a
password-authentication error. Fixed 2026-07-10 by disabling the Windows
service (admin PowerShell: `Stop-Service postgresql-x64-18;
Set-Service postgresql-x64-18 -StartupType Disabled`) and
`sudo systemctl restart postgresql@18-main`. If it recurs, check nothing
on Windows is listening on 5432 (`netstat.exe -ano | findstr 5432`).

Note: testing the HTTPS URL with curl *from inside WSL* fails (hairpin
limitation of mirrored networking) — test from Windows
(`curl.exe https://mlrig.tail93fa1d.ts.net`) or another tailnet device.

**If the web interface goes unreachable while everything looks healthy**
(post-mortem of the 2026-07-11 overnight "crash" that wasn't): journals
showed app/Ollama/Postgres ran perfectly all night, Windows never slept,
Tailscale never restarted — but no request reached uvicorn after 22:38.
The one link that fails silently and leaves no logs is the Windows↔WSL
mirrored-networking bridge, which both access routes (localhost AND
Tailscale Serve → 127.0.0.1:8000) cross. Before rebooting, run
`curl.exe http://localhost:8000/login` in Windows PowerShell: if it fails
while `systemctl status consultation-ai` says active, the bridge is the
culprit — `wsl --shutdown` + reopening a WSL terminal usually rebuilds it
without a full Windows reboot.

Then from any tailnet device: https://mlrig.tail93fa1d.ts.net
(log in as a doctor; mic permission prompt should appear on the live page).

## Session/environment facts

WSL2 Ubuntu 26.04, RTX 4090 (24 GB), Postgres 18 + pgvector on localhost,
DB `consultation_ai` / role `consultation_app` (`.env`), HF token via
`hf` CLI cache (needed for pyannote), Ollama user-space at
`~/.local/opt/ollama`. GitHub: IndyWH/consultation-ai. The project owner
is a doctor building this to learn — explain technical decisions in
plain terms, and treat clinical-judgement questions as theirs to decide.
