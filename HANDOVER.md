# HANDOVER — Consultation AI

For a capable engineer with no prior context. Read PROJECT_PLAN.md first
for intent; this document tells you what actually exists, why it's built
the way it is, what's known to be fragile, and what to do next.

> Prototype for research/education only. Not a medical device. Synthetic
> (scripted/acted) consultations only — never real patients.

## Orientation in five minutes

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
- `uv run pytest` — 57 tests; heavy ones self-skip if Ollama/Postgres/
  corpus are absent.
- Postgres 18 + pgvector, database `consultation_ai`, credentials in the
  gitignored `.env` (see `.env.example`).

## Phase status vs PROJECT_PLAN.md

| Phase | Status | Notes |
|---|---|---|
| 0 — Foundations | **Done except one recording** | Env, Postgres, app, tests all in. Seventeen mock scripts written: 10 English (5 routine, 4 red-flag variants, 1 held-out), 2 Sinhala/English code-switched (`_si`, for the Phase 5 ASR recordings eval), 5 UK private-GP (`_uk`, CDS restraint + buried-red-flag urgency) — see `mock_consultations/README.md`. **Real two-voice recordings made 2026-07-12** through the live app (consultations 66–70), copied to `mock_consultations/recordings/`: routine 01–04 English + `03_diabetes_review_si`. Still to record: `05_epigastric_pain_en` and `01_chest_pain_si`. WAVs gitignored; LFS decision still open. |
| 1 — Streaming transcription | **Done** | Voice-tested; lag inside the 2–5 s target. |
| 2 — Post-consultation note | **Done, real-audio validation begun** | Full pipeline + review UI + eval. The 2026-07-12 recordings ran through the full live→Stop→review pipeline as they were made (five consultations; three approved, two awaiting review as of that date) — diarisation and notes held up in use; the formal check against marking schemes + a real-audio section in the note-quality eval are still to do. |
| 3 — Live CDS | **Done** | Including urgency escalation, evaluated 8/9 with one documented boundary case (see docket). |
| 4 — RAG guidelines | **Done** | 9/9 eval; fidelity spot-check logged; corpus is UK/CDC/WHO starter content. |
| 5 — Sinhala | **Recordings eval run (2026-07-12); decision pending adjudication** | Benchmark (2026-07-10): 9 candidates on two OpenSLR sets, best `seniruk/whisper-small-si` CER 0.035. Pre-registered recordings eval executed on the real `03_diabetes_review_si` recording: every model degrades massively (seniruk 0.035 → 0.504; best overall xlsr-sinhala CTC 0.462) and **every Sinhala fine-tune transliterated or lost all 106 English terms** (mechanical recall 0). Off-the-shelf landscape now exhausted (post-hoc screen of remaining HF repos found only duplicates). Owner's transliteration adjudication pending (`evals/adjudication_03_si_worksheet.md`); fine-tune fallback squarely in scope. See `evals/2026-07-12_sinhala_asr_recordings_eval.md`. |
| 6 — Users/roles/front desk | **Core built and manually verified** | Auth (scrypt + signed-cookie sessions), three tabs per the agreed structure, walk-in queue, server-side RBAC (receptionist 403s on all clinical content — automated tests pass), audit log, approved-consultations read-only, full loop wired queue→live→review→approve→archive. **Verified 2026-07-10 (project owner, in-browser):** two-role click-through of the full loop, plus adversarial checks — receptionist hitting clinical URLs directly (403 confirmed), doctor attempting queue add/reorder (403 confirmed), edit attempts on an approved consultation (409 / read-only UI confirmed). **Design pass done 2026-07-24** (Heidi-inspired light theme, whole app — see the design-pass section) along with **strict own-consultations doctor scoping** and the new **referral letters** feature. Remaining build work: Docker Compose packaging, demo script. **Post-verification additions (2026-07-10, browser-testing findings):** doctor walk-in action (`queue.walk_in_started`); server-sourced patient banner on the live page (wrong-patient prevention — identity never read from URL text); queue-entry lifecycle for abandoned sessions — Resume, Close-without-consultation (`queue.cancelled`, receptionist too), and a concurrency guard so a doctor can't stack a second live consultation over an active one. |

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
app/mock_scripts.py    mock-script parser (turns)
app/static/theme.css   shared design system (2026-07-24 pass; light only)
app/static/live.html   live page; review.html  review page; nav.js app chrome
corpus/manifest.yaml   committed provenance for the gitignored corpus
scripts/               ingest_guidelines, simulate_cds, make_tts_sample,
                       evaluate_{urgency,rag,notes,sinhala_asr},
                       manage_users (break-glass CLI, see toolbox below)
```

Models: MedGemma 27B Q4_K_M GGUF via Ollama (clinical reasoning, notes,
RAG summaries), `embeddinggemma` via Ollama (768-d embeddings),
faster-whisper `distil-large-v3` (live ASR), WhisperX `large-v3` +
pyannote `speaker-diarization-3.1` (final pass). All decoding for
clinical outputs is temperature 0, seed 42 (`CDS_TEMPERATURE`/`CDS_SEED`).

## Key design decisions and why

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
5. **Finalisation needs a transcript-quality gate**: consultation #70's
   Sinhala audio went through the English-forced pipeline and produced a
   hallucinated English translation (repetition loops, avg confidence
   0.49, last 33 s dropped) — and a normal-looking draft note was
   presented and approved. Low average confidence or language mismatch
   should flag the review as unreliable, analogous to the note grounding
   gate, not present a normal draft. (#70 voided 2026-07-17 for this.
   **Void-state incident, investigated 2026-07-24:** the audit trail
   shows #70 was Unvoided 2026-07-22 07:11 by the owner's admin account,
   39 s before a batch of "Test case" voids — i.e. it was used to test
   the then-new Unvoid button during a governance-testing session and
   never re-voided, so it sat wrongly approved-and-visible for two days.
   Re-voided 2026-07-24 with the original reason; the restoration audit
   row carries user_id NULL and a `restoration` detail. Lesson for the
   demo script: don't exercise governance actions on real rows.)
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

## Phase 5 — benchmark done, recordings eval next

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
- **Next:** owner's transliteration adjudication
  (`evals/adjudication_03_si_worksheet.md`, every curated-term occurrence
  aligned across the top three models), record `01_chest_pain_si` (and
  `05_epigastric_pain_en` for Phase 0), then the step-7 decision — on
  these numbers the pre-registered fine-tune fallback (4090, plan §7) is
  the likely outcome unless adjudicated term recovery changes the picture.
  Then: translation layer (Gemma/NMT benchmark, plan §4) and
  dual-language transcript storage — the `FinalTranscript` model in the
  plan already anticipates si/en pairs.

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
  `mock_consultations/recordings/`, named per README). Still to record:
  `05_epigastric_pain_en` and `01_chest_pain_si`. Decide Git LFS.
- **Phase 2 (validate on real audio):** the recordings already ran the
  full live→Stop→review pipeline as they were made; still to do: review
  the two consultations left awaiting review, check diarisation/roles and
  confidence flags (first real test) against marking schemes, and append
  a real-audio section to the note-quality eval.
- **Phase 5:** recordings eval run on `03_diabetes_review_si` — see status
  table and `evals/2026-07-12_sinhala_asr_recordings_eval.md`. Next: the
  owner's transliteration adjudication
  (`evals/adjudication_03_si_worksheet.md`), record `01_chest_pain_si`,
  then the model decision (fine-tune fallback likely). **Fine-tune
  groundwork plan drafted 2026-07-17** —
  `evals/2026-07-17_finetune_plan.md`: data sources/licences (verified),
  code-switch synthesis strategy, two-arm base-model plan, 4090-sized
  recipe, pre-registered gates against the frozen recordings eval; eight
  owner sign-offs pending, no training started.
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

## Remote access (Tailscale, set up 2026-07-10)

The app is reachable from the project owner's other devices over their
private tailnet at **https://mlrig.tail93fa1d.ts.net** — HTTPS is
mandatory for remote microphone access (browsers only allow getUserMedia
on secure origins). Nothing is exposed to the public internet.

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
```

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
