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
- `uv run pytest` — 346 tests; heavy ones self-skip if Ollama/Postgres/
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
| 7 — Supervised auto history-taking | **OPEN as of 2026-07-25**; **7a items 0–4 and 7 built the same day — tap-to-ask and the sound check work end to end; barge-in (session 3) built 2026-07-29, `BARGE_IN_ENABLED` false pending calibration** (see "Phase 7a — session 3" below). Two gate items deliberately carried — see "Phase 7 opened". **7b session 1 built 2026-07-28**: kindalive vendored at a pinned commit, [clinical] preset, capped impulse layer, face over the existing WebSocket — default OFF, unstyled (see "Phase 7b — session 1"). **Session 2 the same day**: full expression range by owner decision (evaluation-first; brief decision 3 superseded for this phase, clinical retained as the comparison arm), the CDS affect hint, interim top-of-stack placement, and the lost specs reconstructed and committed (see "Phase 7b — session 2"). **Session 3, also the same day**: sticky top row (urgent LEFT, face RIGHT — supersedes session 2's placement), auto-on at Disclosure, the auto-chained invitation, the caged silence nudge (the only autonomous utterance until 7c), and the sound-check wording fix (see "Phase 7b — session 3"); **room-checked the same evening (452, 454)**. **Session 4**: the Face pill (manual on-path; "manual off is final" amended by the owner), questions_to_ask ordered by clinical priority (harness re-run 9/10, the known script-02 boundary case the only FAIL), and the first-assessment latency report (see "Phase 7b — session 4"). **Session 5**: first CDS call on the first committed turn (~20 s to first questions, was ~50 s), one num_ctx across all MedGemma calls (the 3.9 s reload eliminated, measured), and PHASE_7C_EVAL_PREREG.md committed FROZEN (see "Phase 7b — session 5"). | Owner's concept: in auto mode the AI conducts the history-taking by voice under doctor supervision — questions and acknowledgements only, never advice or diagnosis to the patient; urgency alarm pauses auto mode (resume/take-over is the doctor's call); doctor barge-in always wins. Full spec — hard rules, consultation behaviour policy, staged build (7a tap-to-ask → 7b kindalive face → 7c supervised auto), pre-registered eval design — in `PHASE_7_SPEC.md`. **Gate updated 2026-07-25: the Phase 5 precondition is satisfied by closure** (step 6 adjudication + Phase 5 closed with a negative result, Sinhala out of scope for v1 — not a deferral), and the recordings precondition means `05_epigastric_pain_en` only (`01_chest_pain_si` not being recorded for v1). **Remaining gate, three items: (1) `05_epigastric_pain_en`; (2) Docker Compose packaging + the two-role demo script; (3) the finalisation transcript-quality gate** — load-bearing now the project is English-only, see the pre-Phase-7 build item section. 7a+7b are the recommended first commitment, 7c committed separately. |

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
app/face.py            Phase 7b: event→impulse layer + per-muscle hard caps
vendor/kindalive/      vendored face engine, pinned commit (see NOTICE)
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
note call. ~17 s for a 4.6-min consultation. **Measured baseline: see the
VRAM section below** — the numbers there are measurements, and they replace
the estimates in this paragraph.

## VRAM baseline — MEASURED, 2026-07-28

Measured with `nvidia-smi` and `ollama ps`, not estimated, on the 24564 MiB
RTX 4090. **Nothing was changed**: models were loaded exactly as the app loads
them, and the card was confirmed back at its idle baseline afterwards with
nothing left resident. This is the starting point for any offload decision, and
no placement decision has been taken.

| Phase | Total | What is resident |
|---|---|---|
| **Idle** | **2930–2983 MiB** | the app's faster-whisper `distil-large-v3` (live ASR, loaded at startup) + its CUDA context + the Windows desktop. Ollama holds nothing. |
| **Audio phase** of a finalisation | **8318–12374 MiB** (peak 12374) | idle baseline + WhisperX `large-v3` + pyannote. MedGemma unloaded by the pipeline. |
| **Note generation** (MedGemma, `num_ctx` 16384) | **21242 MiB** | idle baseline + MedGemma |
| **Live consultation** (MedGemma `num_ctx` 8192 + embeddinggemma) | **21683–21717 MiB**, ~2.85 GB free | idle baseline + both Ollama models |
| **Worst measured** (MedGemma 16384 + embeddinggemma) | **22309 MiB**, **2255 MiB free** | the transition case |

Component costs, by difference:

| | |
|---|---|
| MedGemma 27B Q4_K_M @ `num_ctx` 8192 | **~17 633 MiB** |
| KV cache growth 8192 → 16384 | **~679 MiB** only |
| `embeddinggemma` resident | **~1067 MiB** (its `ollama ps` SIZE reads 681 MB) |
| faster-whisper + CUDA context + Windows desktop | **~2950 MiB**, not separable — see below |

**Configuration, checked rather than assumed:** `/etc/systemd/system/
ollama.service` has **no `Environment=` lines at all**, so there is **no KV
cache quantisation** (`OLLAMA_KV_CACHE_TYPE` unset → f16) and no
`OLLAMA_FLASH_ATTENTION`. Context lengths are per-call: **16384** for notes
(`app/notes.py`), **8192** for CDS (`app/cds.py`) and RAG (`app/rag.py`).
**`embeddinggemma` does stay resident alongside MedGemma** — confirmed with
both in `ollama ps` at once, which is the live-consultation shape.

**The largest reclaimable item is `embeddinggemma`, ~1067 MiB.** It is used only
to embed RAG queries, it is small, and CPU latency there is tolerable —
retrieval is not on the urgency path. Everything else is either the point
(MedGemma) or latency-critical (faster-whisper on the live path).

**Two findings that matter more than the headline totals:**

- **KV quantisation is not the win it looks like.** 8k → 16k costs only 679
  MiB, so the whole KV cache is a few hundred MB against ~17.6 GB of weights.
  Quantising it would free far less than moving `embeddinggemma` off. Nothing
  short of a smaller or differently-quantised MedGemma changes the picture
  materially.
- **MedGemma is reloaded between phases because `num_ctx` differs.** CDS and
  RAG ask for 8192, the note asks for 16384, and Ollama reloads on a `num_ctx`
  change — measured directly: a warm 16384 instance took 3.9 s to answer a
  trivial 8192 request. That reload is an unrecorded cost in the live → note
  transition and is fixable by making the two agree, but **no change has been
  made**.

**The Windows/WSL split is not resolvable from inside WSL.** Under WDDM,
`nvidia-smi --query-compute-apps` reports `[N/A]` for per-process memory —
both from WSL and from `nvidia-smi.exe` on the Windows side, which enumerates
the desktop processes holding the GPU (explorer, SearchHost, two
`NVIDIA Overlay.exe`, `msedgewebview2`, PowerToys) without sizing any of them.
The one way to get the number: **read `nvidia-smi` once with the app service
stopped** — the idle total minus that reading is the app's share, and the
reading itself is the Windows desktop's. That is worth doing during the next
restart rather than as a special exercise.

**To watch the live path** — the one phase nobody had measured, and the one with
the urgency alarm on it — run this in a second terminal during a consultation.
One command, no install, no sudo; the line rewrites in place and the peak is
always on screen, so Ctrl-C leaves it visible:

```bash
nvidia-smi --query-gpu=timestamp,memory.used,memory.total --format=csv,noheader,nounits -l 2 \
  | awk -F', ' '{if($2>m){m=$2;t=$1}; printf "\r%s  now %6d MiB | PEAK %6d MiB (free %5d) at %s   ", $1, $2, m, $3-m, t; fflush()}'
```

## Design pass + referral letters (2026-07-24)

> **Document loss and recovery (2026-07-28).** The original
> `DESIGN_SPEC.md`, `NOTE_ICE_SPEC.md` and `REFERRAL_LETTER_STYLE.md`
> were LOST — they existed only in the owner's Downloads and deleted
> chat sessions, never in the repo. All three were reconstructed
> 2026-07-28 from the code that implemented them, the mockups and this
> document, and are now committed at the repo root; each header says it
> is a reconstruction and that the code is authoritative where they
> disagree. The approved mockups (originals, not reconstructions) are
> committed at `docs/mockups/`. The lesson is already visible in this
> file's own history: a spec that lives only in Downloads is one cleanup
> away from existing only as its implementation.

Implemented from `DESIGN_SPEC.md` (Claude Cowork + owner; approved
mockups `live_mockup.html`/`review_mockup.html` are the visual source of
truth — both now committed at `docs/mockups/`, spec decisions restated
here). Five commits, "Design pass 1/5 … 5/5":

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

**Both of those were decided by the owner on 2026-07-28, and 448 is why.**
The wording is now *"you can speak to **them** at any time"* — approved,
asserted verbatim, and pinned by a second test so a revert reads as a
named regression rather than a tweak. And 448 did speak as **"Dr
Doctor"**, because the session ran on the admin account: the decision is
to **fix the display names rather than guard against them in code**, so
`scripts/manage_users.py set-display-name USERNAME "Name"` now exists
(audited `user.display_name_changed`, old and new name both in the row).
The no-invented-title convention is unchanged — the "Dr" stays in the
phrase template. The names themselves are the owner's to choose and were
deliberately not chosen here.

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

### Consultations 446 and 447 — the doctor could not stop the machine

The second and third room runs, same evening as 445. One hard-rule
breach and two reasons the owner did not see what the interface was
telling him.

**Hard rule 3 was breached: there was no way to stop an utterance.**
`PHASE_7_SPEC.md` rule 3 — the doctor always wins, one tap, immediate. In
447 the owner tapped a long question, wanted to cut it off, found nothing
to press, tapped the chip again (speaking it a second time), and in the
end **stopped the whole consultation recording to silence the machine**.
Ending a consultation is not an acceptable way to cancel an utterance.

**The control was never absent — it was invisible.** `#speakStop` had
been in the DOM since it was built; it is one of the two elements reading
"Stop" that the DOM snapshot found (the other is the main Start/Stop
button). The defect was **position**: the speaking bar sat in normal flow
at the top of `.stack`, above the urgent box, while the question chips
that trigger it are further down the page. On any page taller than the
viewport it scrolled out of sight exactly when it was needed.

It is now **fixed to the viewport** (bottom centre, z-index 60), moved
out of `.stack` so a layout change cannot re-parent it back into the
scroll, and made loud: solid accent background, white bold Stop,
`role="alert"`. **Escape is a second one-tap path.** The CSS carries a
comment saying position is the point and not cosmetic, because to the
next reader it will look like a style choice. Tests assert
`position: fixed` and non-membership of `.stack` — a test asserting only
"the control exists" would have passed throughout the incident.

Also: a question that has been asked now shows **"✓ asked"** and its icon
becomes ↻. Re-asking stays allowed and logged — the panel lags a revision
behind and repetition is sometimes right — but 447 spoke *"Have you
noticed any white patches on your tonsils"* three times (86.8 s, 123.5 s,
133.0 s) because nothing showed it had gone out. Tracked by question
**text**, not index, since the index moves when the agenda revises.

**The sound-check offer was eating taps.** In 446 the owner tapped
question chips repeatedly and nothing was spoken; the banner *"No sound
check yet this session"* was consuming the tap. Confirmed in the data:
**two system utterances all evening, both phrases, not one
`cds_question`**. Two things were wrong, and the spec asking for it was
one of them — an offer must not consume the action, and there was never a
reason for a spoken phrase to bypass a check a spoken question does not.
That asymmetry is what made it unreadable from the room, because the
machine plainly *could* speak. The offer is now passive and holds no
callback; questions and phrases take the identical path.

**`doctor_stop` is now proven on real audio.** 447's last utterance
closed with `end_reason = doctor_stop` at 133.00–134.95 s — cut to 1.95 s
where the same question ran 4.68 s when it played through — against a
134.8 s recording. Status `awaiting_review`, `quality_outcome` **pass**,
and **no exclusion anomaly and no silence hallucination** for either 446
or 447. Stopping the recording mid-utterance closes the window correctly;
that edge case is no longer only a unit test.

## THE THREE STANDING RULES (interface, non-negotiable)

**All three in one place, each with the incident that produced it, so the
next person meets them as a set rather than rediscovering the third one in
a room — which is what happened twice.** Written into `live.html`,
`review.html` and `worklist.html`, with a test per page asserting the
reason survives.

> **1. NEVER SWALLOW AN ACTION.** Either PERFORM the action, or VISIBLY
> DISABLE the control with the reason attached to the control itself. Never
> accept a tap, do nothing, and explain it somewhere else on the page.
>
> **2. A CONTROL THAT CAN ACT MUST NOT LOOK AS IF IT CANNOT.**
>
> **3. A CONTROL THE DOCTOR MUST REACH MUST BE WHERE THEY ARE LOOKING.**

| Rule | The incident that produced it |
|---|---|
| **1** | **2026-07-25, three in one evening.** The "Not connected — cannot speak" panel, the finalisation page that never left "processing", and the sound-check offer that ate question-chip taps. The owner missed all three. Then a **fourth on 2026-07-28 (450)**: the declared speaker count was accepted, discarded, and nothing on any screen said so — in the feature built to fix the third. |
| **2** | **2026-07-28, consultation 448.** An already-asked question chip turned green. Green means approved / linked / mic-live everywhere else in this app — all finished states — so the doctor read it as spent and did not re-tap, which cost the most important step of the walkthrough. Re-asking had worked the whole time. |
| **3** | **2026-07-25, consultation 447**, then **2026-07-28, consultation 449 — the same defect in a NEW control three days after the first fix.** 447: the Stop control existed the whole time, in normal flow above the chips that trigger it, so it scrolled out of sight exactly when it was needed and the doctor stopped the whole recording to silence the machine. 449: the speaker-count question rendered two divs deep inside the scrolling stack, was never seen, and was never answered. |

**Rule 1 and rule 2 are the same cost from opposite directions — a tap not
taken.** Rule 3 is why "the control exists and is correct" is not enough:
it also has to be in the doctor's field of view at the moment it is needed.
**Rule 3 governs REASONS as well as controls** — a refusal explained where
the doctor is not looking fails in exactly the way rule 1 describes, which
is why refusals now land on the control that was pressed rather than in a
banner elsewhere on the page.

**Why rule 3 took two incidents to write down** is worth keeping: after 447
the fix was recorded as a fact about *that* control ("the speaking bar is
fixed to the viewport, do not return it to normal flow") rather than as a
rule about controls in general. So when a new control was built days later,
nothing in the codebase said where to put it. A lesson recorded as a
property of one place does not generalise; a rule does.

### The first of them, in full: never swallow an action

**Adopted 2026-07-25 after the third instance in one evening.** Three
separate controls did nothing while a small banner elsewhere explained
why: the "Not connected — cannot speak" panel, the finalisation page that
never left "processing", and the sound-check offer. The owner missed all
three.

> **Either PERFORM the action, or VISIBLY DISABLE the control with the
> reason attached to the control itself. Never accept a tap, do nothing,
> and explain it somewhere else on the page.**

**This is an accessibility requirement, not a preference.** The owner is
dyslexic with ADHD; a quiet explanation placed away from the control just
pressed is, for him, no explanation at all — and in a consultation room
with a patient waiting it is no explanation for anyone. The rule is
written at the top of `live.html`'s script *with that reason attached*,
and a test asserts the reason survives: a rule stripped of its why reads
as a style opinion and gets traded away.

A banner may **accompany** a refusal that arrives asynchronously from the
server. It may never **substitute** for a control that looks live and is
not.

Auditing the page against the rule found two more violations, both fixed:

- **Speak controls stayed enabled after a WebSocket drop**, so a tap
  produced the "Not connected" panel. `onWsClose` now refreshes them and
  `openSocket` re-enables them. The in-function guard survives as a
  documented last resort against a race.
- **The mic picker silently ignored clicks during recording** — a bare
  `return`, keeping its pointer cursor and chevron. `.mic.disabled`
  already existed in the CSS and **nothing had ever applied it**. Now
  applied, chevron hidden so it stops inviting a click, reason in the
  control's own title.

### The other two pages, audited 2026-07-28

The 2026-07-25 audit covered `live.html` only. The review page and the
Consultations worklist were audited before the collaborator's access.

**Every violation on the review page was one shape**: a handler awaited a
`fetch`, ignored the response, and refreshed — so a 409 produced no message
anywhere at all. Approve, Regenerate, Swap Doctor/Patient, per-turn role
correction, the acknowledge buttons, the transcript text edit and the letter
body edit. **The two edits were the worst**: a refused correction stayed on
screen looking saved until something else reloaded and silently reverted it,
and the letter edit went further and recorded the refused text locally as
though it had been accepted. Both now restore what the server holds. One
`act()` helper per page owns refusals, and a test fails on any bare awaited
fetch left in a handler.

**The worklist's were a lesser class and are recorded as such**: they did
explain, but in `#err` above a table whose rows can be a screen away — rule
3 rather than rule 1. The reason now also goes on the control, outlined in
red. **Two paths were deliberately left alone**: cancelling your own
`prompt` is a choice, not a swallowed action.

**Not a violation, checked and confirmed**: `refreshApproveGate()` is the
only writer of Approve's disabled flag and carries all three
acknowledgement reasons — urgency, speaker labels, stale labels — in the
button's own title. The single-writer property has a test, asserted with
comments stripped so the comment explaining *why* it is single-writer
survives.

### The abandoned-walk-in lockout (entry 164, fixed 2026-07-28)

**The half that mattered was never the orphan row.** An `in_consultation`
entry holds the **single system-wide** live-consultation slot, and that
guard is global by design — so one walk-in abandoned before Start refuses
**every doctor in the practice** until the date rolls over. Then, once it
has, both recovery paths refused the entry too, because every queue query
was scoped to `queue_date = CURRENT_DATE`: Resume answered 404 and Close
answered 409. Nothing was left that could close it.

Two changes. **The close path dropped its `CURRENT_DATE` filter, and only
the close path** — an escape hatch scoped to today cannot let anybody out of
yesterday. `_ENTRY_SELECT` and the display queries keep their day scoping
and a test asserts it, so today's queue is still today's queue. And a
**startup sweep** (`frontdesk.sweep_stale_entries`, beside the retention
sweep) closes `in_consultation` entries dated before today **that have no
consultation row**. Both conditions are load-bearing: a live consultation in
progress right now looks exactly like a stale one and only the date
separates them, and an entry *with* a consultation row means the session
really started, so cancelling it would file a real consultation under "no
recording happened". The sweep audits its own closures (`queue.cancelled`,
no acting user, a `via` saying what closed it and why) and is idempotent, so
a restart loop cannot re-audit the same closure.

**The refusal itself is now legible**, which is the other half of the same
story: all four sites that fire `live.slot_rejected` say what is holding the
slot — patient name and the time the entry was opened for a queue entry,
plus that it can be closed from Today; the user holding the stream for a
WebSocket refusal. **The guard is unchanged and must stay so**: one live
consultation at a time is a safety property, not a throughput limit, because
two streams would share the transcriber and an urgency alarm arriving late
under contention is a safety regression.

### Consultation 448 — THE GUARANTEE HOLDS IN A ROOM (2026-07-28)

**The fourth run of the real-room check, and the first one the transcript
guarantee passed.** Three previous rooms each found a serious defect (445
the missing six minutes, 446 the offer eating taps, 447 no way to stop an
utterance). 448 found two interface defects and **no breach of the
guarantee**.

**448 must not be voided or purged.** It is the evidence that the
guarantee holds, and it is the first artifact of that kind the project
has. Patient "Step6 Patient", `awaiting_review`, `quality_outcome`
**pass**.

**The evidence, read from the database rather than from the screen:**

| | |
|---|---|
| System utterances | **seven**, all in `system_utterance` |
| Where they appear | the grey *Assistant · spoken aloud* channel **only** |
| Turn numbers on them | **none** — they are not `transcript_turn` rows, so there is no number to give them |
| Note claims | 6, all cited: **grounding 6/6** |
| What those claims cite | `transcript_turn` rows only — **no citation resolves to a system utterance**, and none can, because the two live in different tables |

That last row is the whole architectural point paying off: exclusion is
structural, so "the note cited a machine utterance" is not a bug that was
avoided, it is a sentence with nowhere to happen.

**Two things the note did right and both are worth keeping:**

- **Objective, Assessment and Plan are all empty**, not fabricated. The
  consultation stopped early and never reached them. Same behaviour as the
  2026-07-07 two-hats loop test (docket item 7); it has now held on real
  room audio with a real early stop.
- **Roughly 80 seconds of near-silence at the start produced no phantom
  turns in the final transcript** — the first human turn begins at 94.4 s.
  That is direct support for the 445 finding that the hallucinated-filler
  problem is a **live-path** phenomenon (`distil-large-v3` re-transcribing
  a short rolling buffer) and not a final-path one (WhisperX + silero VAD
  over the whole file). It does not close docket item 8; it narrows it.

**The two interface defects, both fixed the same day:**

1. **Speak controls rendered enabled before the first connection.** The
   doctor tapped a phrase button before pressing Start, got the red "Not
   connected — cannot speak" panel, and only *then* did the controls grey
   out. The standing rule broken from the one direction the 2026-07-25
   audit could not see: before Start there has never *been* a socket, so
   neither `onWsClose` nor `openSocket` had fired and the markup's default
   enabled state was what rendered. `refreshSpeechControls()` is now called
   at page load. **The old test passed throughout** — it asserts the
   refresh inside `onWsClose`, and a test of the post-drop path cannot see
   a pre-connection one; the new test asserts a **top-level** call.
2. **An asked chip looked spent.** The doctor read the green chip as used
   up and did not re-tap, which **cost the most important step of the
   walkthrough** (hard rule 3's scroll-away Stop test). The briefed
   suspicion was that the ↻ icon was not rendering. **It was rendering.**
   What failed was legibility: three things said *done* (text greyed to
   `--ink-faint`, a green ✓ ASKED label, and the button restyled to
   `var(--green)` — this app's colour for approved / linked / mic-live,
   every one a finished state) against one 12 px glyph saying *again*, and
   the button's tooltip still read "Ask the patient this". The row now
   keeps the receipt and the **button** says "↻ Again" in words at the
   accent colour, tooltip "Already asked once — tap to ask it again".

That second one produced a **companion to the standing rule**, recorded in
`live.html` beside it: **a control that CAN act must not look as if it
cannot.** Same cost — a tap not taken — from the opposite direction. Green
is the specific trap in this app because the design system already spends
it on finished states.

One further defect found while establishing those facts and fixed with
them: **`renderCDS` re-creates every question chip and did not call
`refreshSpeechControls` afterwards**, so a CDS revision arriving before the
disclosure rendered live-looking chips the server would have refused — the
original rule, reached through a re-render.

**Two open questions 448 raised. Both were investigated and reported before
anything was changed, because the fix was the owner's decision to take — and
on 2026-07-28 they took it: the diarisation one is addressed, the
speaker-aware gate is deliberately held. See the sections below.**

**448 is also part of the three-consultation evidence set for the speaker
misattribution defect** (with 446 and 447), on top of being the evidence that
the transcript guarantee holds. Neither role permits voiding, purging,
re-finalising, or editing its stored transcript.

### Speaker misattribution — ALL THREE 7a consultations (2026-07-28)

**Superseding the "open question 1" section below, which is kept because its
investigation is what led here.** The defect is not 448's alone. Checked
directly on the review pages by the owner:

| | Turns labelled **Doctor** that are the **patient** |
|---|---|
| **446** | turn 0 — *"Oh hi, I have tummy ache"* |
| **447** | turns 0, 2 and 4 |
| **448** | turns 0 and 2 |

**The mechanism is the exact speaker count, and nothing to do with 7a's
exclusion machinery.** `app/finalize.py` called pyannote with
`num_speakers=2`, which does not mean "expect about two" — it *requires*
two. One human in the room therefore had that voice split into two clusters,
and `attribute_roles` labelled the first cluster Doctor.

**What hid it for three consultations is the lesson worth keeping: the notes
were correct.** 4/4, 12/12 and 6/6 claims cited. The model inferred the
speakers from the *content* and wrote accurate notes over wrong labels — so
every downstream check passed, the review page read well, and nothing
objected. **A downstream component doing its job well concealed an upstream
defect.** That is the same shape as consultation #70 (a note faithful to a
transcript that was not faithful to the audio) reached from the opposite
end: here the note was *better* than its input, which is not a mercy, it is
camouflage. It is also why the speaker-aware grounding gate is worth
building eventually — it is the one check that would have failed.

**Owner decisions, 2026-07-28:**

1. **Unpin the speaker count AND add per-turn role correction** — because
   one fixes new consultations and only the other can repair existing ones.
   Both are built (see the two subsections below).
2. **The speaker-aware grounding gate is deliberately HELD** until the
   labels are trustworthy. The sequencing argument was accepted: built
   first, it would fire on every single-human consultation and mostly report
   the diarisation defect. **Do not build it yet.**
3. **446, 447 and 448 are retained UNREPAIRED as the evidence set** for this
   defect, the way 445 is for the missing six minutes. Do not re-finalise
   them and do not modify their stored transcripts.

**Consultation 447 is sitting in `awaiting_review`. If it were approved as
it stands, it would be signed with a transcript saying the DOCTOR complained
of a sore throat.** That is what an unrepaired evidence-set row costs if
someone treats it as ordinary work, and it is the reason the review page now
refuses to let a single-voice consultation through unacknowledged.

#### What the change actually fixed, measured (item 2, 2026-07-28)

Re-diarised offline against the stored WAVs with the real pipeline
functions, writing nothing to the database. **This is not a clean win and
the numbers say so:**

| | clusters before | clusters after | outcome |
|---|---|---|---|
| **448** | 2 (split) | **1** | fixed — all turns Patient, flagged |
| **446** | 2 (split) | **1** | fixed — all turns Patient, flagged |
| **447** | 2 (split) | **2** | **NOT fixed** — pyannote still splits one voice |
| **67, 68, 69, 70** | 2 | 2 | unchanged, roles still alternate correctly |
| **66** | 2 | **1** | **REGRESSED** — a genuine two-person consultation now reads as one voice |

Two conclusions follow, and both are load-bearing:

- **pyannote's speaker count is unreliable in both directions on this data.**
  It over-splits one voice (447) and under-splits two (66). Unpinning is a
  net improvement, not a fix, and it does not meet the owner's own bar on
  its own — which is exactly why per-turn correction was decided alongside
  it rather than after it.
- **66's regression was made catastrophic by the speaker merge, so that is
  where the rule went.** With one cluster the merge has nothing to join *on*
  and joined the whole 300-second consultation into a SINGLE turn: 22 turns
  down to 1, citations pointing at one blob, and one label to correct where
  the doctor needs twenty-two. Same shape as consultation 445 — the merge is
  what turns a small upstream error into a large downstream one. Segment
  boundaries are now kept when there is one cluster. **The cost, stated:
  single-cluster transcripts come out at ASR-segment granularity** (66 → 99
  turns, 448 → 10, 446 → 9), so reading is choppier and there are more
  labels to check. Grouping by pause length would need a threshold nobody
  has calibrated on this room, so it is deliberately not done.

**The first-speaker-is-Doctor premise is falsified and its replacement is an
open design question.** The docstring justified itself with "the doctor opens
the consultation", true when a human opened it; in tap-to-ask the **machine**
opens with the disclosure and invitation, both excluded from the transcript,
so the first *human* voice is frequently the patient. The heuristic is
knowingly left in place for the two-cluster case and the docstring now says
the premise is false instead of asserting it. Replacing it was deliberately
not attempted in the same commit.

**The single-cluster default is Patient, and it is a default.** In
tap-to-ask the machine asks the questions, so a lone human voice is
answering them, and in all three observed cases that voice was the patient.
The owner may change it; the code comment says so, and every single-voice
consultation raises the review notice regardless.

#### What was built alongside it

- **The single-voice notice** (review page, above the transcript, existing
  acknowledge-gated banner pattern): the roles were not determined from the
  audio and must be checked before approving. Refused server-side with a 409
  as well — a disabled button can be re-enabled from the console.
- **Per-turn role correction**: `PATCH /api/consultations/{cid}/turns/{idx}`
  now takes `text`, `role`, or both, same RBAC and same voided/approved
  refusals, audited as `turn.role_changed` with the **old and new** role. In
  the page the speaker label **is** the control. Swap Doctor/Patient stays —
  a genuine whole-consultation inversion is a real case — it just stops
  being the only tool.
- **The stale-note gate**: swap and per-turn correction both stamp
  `labels_changed_at`, and a note created before that stamp cannot be
  approved until it is regenerated or acknowledged. **Never silently
  regenerated** — the note is the doctor's document. Staleness is two
  timestamps compared in SQL, so a regenerate clears it for free and a
  *second* role change re-arms the gate instead of inheriting the first
  acknowledgement.

### The count is DECLARED, not detected (owner decision, 2026-07-28)

**The permitted range was tried, measured and replaced — not extended.** This
is the second correction to the same line in one day, and the sequence is the
point:

| Setting | Result |
|---|---|
| `num_speakers=2` (original) | splits a lone voice in two — 446, 447, 448 all mislabelled |
| `min_speakers=1, max_speakers=2` | fixed 448 and 446; **did not fix 447** (pyannote still chose two clusters when allowed one); **REGRESSED recording 66**, two real people, to one cluster |
| `num_speakers` = declared (now) | **all eight recordings correct** |

**A change that fixed two of three artificial cases and broke one real one.**
That is the sentence worth carrying: the range looked like the principled fix —
stop over-constraining the model, let it answer — and letting it answer is
precisely what it cannot do reliably on this data. It is wrong in *both*
directions, over-splitting one voice and under-splitting two, so no automatic
setting can be right.

Every row resolves once the count is **stated** rather than inferred: 447 is
correct forced to one, 66 is correct forced to two. So the doctor declares it.
**This is the sound check's established pattern — the human in the room is
authoritative and the measurement corroborates** — and it is the second place
in the project where that pattern has been the answer.

- **Asked at Stop**, three one-tap answers (just me / two of us / skip). It
  appears from the `done` handler, *after* the server confirms the
  consultation is complete, so no answer can hold the consultation open. Skip
  sends nothing at all, because NULL already means defaulted. **No
  auto-dismiss timer** — a timer would make the behaviour depend on how fast
  the doctor reads.
- **`DEFAULT_SPEAKERS = 2`** when nobody answers: today's behaviour, correct on
  four of the five real two-person recordings, so a defaulted consultation
  behaves exactly as it did before this work.
- **Two columns, and the distinction is load-bearing.** `declared_speakers` is
  what the doctor SAID (NULL = not asked or skipped); `speakers_used` is what
  the pipeline actually handed pyannote. The count is read as late as possible,
  immediately before the audio phase, so a one-tap answer has the whole
  MedGemma-unload window to arrive — and if it arrives later, the endpoint
  returns `applied: false` and stores the answer **without** rewriting
  `speakers_used`. A best-effort write that never blocks the doctor must also
  never claim more than happened, and the UI says which of the two it got.
- **Per-turn role correction stays the backstop.** A declaration can be
  mis-tapped, and it is still the only thing that can repair a consultation
  after the fact.

**The single-voice notice was reworded to describe what the system did.** It
said *"only one voice was detected in this recording"* — and recording 66 is
two real people arriving on that exact path, so the sentence can be flatly
false. A safety notice that can state something untrue about the consultation
teaches the doctor to discount it. It now says identification returned a single
voice, that every line was labelled Patient **by default**, and that the labels
must be checked; and it distinguishes a declared count from a defaulted one,
because two-because-you-said-so and two-because-nobody-answered are the same
number and different statements.

#### Item 5 verification — measurements, not a success claim

Re-diarised offline against the stored WAVs, real pipeline functions, **nothing
written to the database**. 446, 447, 448 and 66–70 were **not re-finalised**;
they remain the evidence set.

| cid | declared | clusters | turns before → after | roles after |
|---|---|---|---|---|
| **448** | 1 | 1 | 3 → 10 | all Patient ✓ |
| **446** | 1 | 1 | 2 → 9 | all Patient ✓ |
| **447** | 1 | 1 | 6 → 18 | all Patient ✓ — **the row no automatic setting fixed** |
| **66** | 2 | 2 | 22 → 22 | alternating D/P, spot-checked against the text ✓ — **regression repaired** |
| **67** | 2 | 2 | 19 → 21 | alternating ✓ |
| **68** | 2 | 2 | 27 → 27 | alternating ✓ |
| **69** | 2 | 2 | 25 → 30 | alternating ✓ |
| **70** | 2 | 2 | 29 → 27 | alternating ✓ |

**Eight of eight correct.** Two things not to read generously, both stated
because the table would otherwise flatter itself:

- **Turn counts move on 67, 69 and 70** (±2 to +5). That is WhisperX
  re-transcription variance between runs, not a role change — the alternation
  and the alignment are preserved. It does mean turn *indices* are not stable
  across re-finalisation, which matters to anything holding stored citations.
- **Within-turn speaker bleed is unchanged and pre-existing**: some 67 and 70
  turns contain a few words of the other speaker at a boundary. It is
  independent of the speaker count, was there before all of this, and is not
  addressed by any of it.

#### The merge has now been the amplifier twice

Worth its own note, because the pattern is more useful than either instance:

1. **Consultation 445** — the silence invariant dropped any segment
   overlapping an excluded span, and *after* the merge a hallucinated fragment
   sat inside a 204-second merged turn, so removing 12.7 s of muted audio
   discarded six minutes of consultation.
2. **Recording 66** — a single cluster gave the merge nothing to join *on*, so
   it joined the entire 300-second consultation into one turn: 22 turns down to
   1, citations pointing at a blob, one label to correct where the doctor needs
   twenty-two.

Different upstream causes, same amplifier. **A small upstream error becomes a
large downstream one at the merge, so that is where proportionality rules
belong** — the majority-fraction rule for 445, keeping segment boundaries for a
single cluster.

**It had no test of its own until this week.** The merge loop lived inline
inside `transcribe_and_diarise`, which needs WhisperX and pyannote loaded, so
nothing exercised it directly — which is how both amplifications were possible.
It is now `finalize.merge_into_turns()` with unit tests on both branches.

### 448's open question 1 — one human, two labels (diarisation)

**The original investigation, kept as written. Superseded by the section
above: the defect is in all three 7a consultations, and items 1-5 of the
2026-07-28 work are the response.**

**Reported, not fixed.** Only one human was in the room. Turns 0 and 2 are
labelled **Doctor** while being unmistakably the patient; turn 1 is
labelled **Patient** and is correct. So a single speaker was **split across
two labels** — the labels are not inverted.

The cause is two lines, and neither is a bug in the ordinary sense:

- `app/finalize.py` calls pyannote with **`num_speakers=2`** — a **fixed,
  exact** count, not `min_speakers`/`max_speakers`. pyannote is therefore
  *required* to return two clusters. With one voice in the room it has no
  way to answer "one", so it splits that voice.
- `attribute_roles` then takes **the first turn's cluster as Doctor** and
  labels **every other cluster Patient**. Both halves of one human get a
  label, and one of them is wrong by construction.

**A single-human consultation cannot be labelled correctly by this code.**
Both outcomes are wrong: if both clusters carry words, one human appears as
both Doctor and Patient (448's shape); if all words land in one cluster,
every turn is labelled **Doctor**, so a patient-only recording is
attributed wholesale to the doctor.

**And 7a has already broken the heuristic's stated premise.** "First
speaker is the Doctor (they open the consultation)" was true when a human
opened. In tap-to-ask the **machine** opens — disclosure, then invitation —
and those are excluded, so the first *human* voice is now very often the
patient. This is not a 7c problem waiting to arrive: it is live in 7a
today. In 7c, where the machine asks and the doctor may barely speak, one
human voice becomes the normal case rather than a testing artefact.
(Recorded as context only — no action taken.)

**The review page's Swap Doctor/Patient cannot fix 448**, and the reason
is exactly as suspected: `consultations.swap_roles` is a whole-transcript
`CASE role WHEN 'Doctor' THEN 'Patient' ELSE 'Doctor' END`, which assumes a
uniform inversion. On 448 it would correct turns 0 and 2 and **break turn
1**. Counted against the note: 5 of the 6 claims cite turns 0 or 2, so the
swap takes the note from 1 claim agreeing with its cited turn's role to 5 —
better, and still wrong, with the transcript itself now wrong on turn 1.
**There is no per-turn role edit**: `PATCH /api/consultations/{cid}/turns/
{idx}` takes `text` only.

Options, for the owner to choose between — none of them started:

1. **Stop forcing two speakers.** `min_speakers=1, max_speakers=2` lets
   pyannote answer "one". Then a single-cluster consultation needs a role
   rule that does not assume two voices, and 66–70 must be re-checked so a
   fix for the one-human case does not degrade the two-human one.
2. **Per-turn role correction** in the review UI, which is the honest
   answer to a split cluster whatever the diarisation does, and is the only
   option that can repair 448 itself.
3. **Leave the heuristic and change what opens the consultation** — e.g.
   have the doctor speak first deliberately. Cheapest, and it puts a
   workflow constraint on the room to protect a code assumption.

**Outcome: the owner chose 1 AND 2, and both shipped 2026-07-28.** Option 3
was not taken. Worth recording that the re-check option 1 demanded is the
thing that earned its keep — it found the 66 regression, and without it
unpinning would have shipped looking like a clean fix.

### 448's open question 2 — the grounding gate is speaker-blind

**STILL OPEN, and deliberately HELD by owner decision 2026-07-28 until the
speaker labels are trustworthy. Do not build it yet.** The sequencing
argument below was accepted: built before diarisation is fixed, it would
fire on every single-human consultation and mostly report the other defect.
Note the irony worth keeping — this is the one check that *would* have caught
the three-consultation misattribution, because the notes were correct and
only the label/claim disagreement was visible.

**Reported, not fixed.** In 448 the claim *"Patient requests prostate
cancer screening…"* cites turn 0, which the transcript labels **Doctor**,
and the gate passed the note at **6/6**.

`notes.validate_and_gate` checks exactly three things: that each cited
index **exists** in the turn set, the cited **fraction** against
`NOTE_MIN_CITED_FRACTION`, and the ⚠ flag (load-bearing regex AND cited
turn confidence < 0.6). **It never reads `turn["role"]`.** Role appears in
`app/notes.py` in one place only — `format_turns`, which builds the
prompt text. So, plainly: **a claim beginning "Patient reports…" can cite a
Doctor turn and pass the gate today.** 448 is the proof, five claims over.

What closing it would cost, so the decision is informed:

- **It inherits open question 1.** A speaker check keyed on `role` is only
  as good as diarisation, and diarisation is currently *systematically*
  wrong for one human — 7c's normal case. Built first, it would fire on
  every single-human consultation and mostly report the other defect.
  **Sequence matters: diarisation before the gate.**
- **False positives are structural, not tunable.** Legitimate claims cite
  doctor turns all the time — the doctor summarising the history back, or
  one claim citing a question and its answer together. A rule reading
  "'Patient' prefix ⇒ must cite a Patient turn" would reject good notes.
- **The refusal tier is the wrong lever.** `validate_and_gate` has one
  action, refuse the whole note. Speaker mismatch is per-claim, so it wants
  a marker — but ⚠ currently means *low-confidence audio*, and overloading
  it blurs two unrelated faults. It likely needs its own marker class.
- **It goes stale on swap.** `swap-roles` runs *after* the note is drafted
  and does not re-validate, so any stored verdict must be recomputed when
  roles change or it silently describes the old labels.

### Run 5 — consultation 450: PHASE 7a'S HARD RULES ARE VERIFIED IN A ROOM

**The fifth run of the real-room check, and the one that clears it.** Runs 1–4
each found a serious defect no test would have caught (445 the missing six
minutes, 446 the offer eating taps, 447 no way to stop an utterance, 448 the
speaker misattribution and the invisible speaking bar). 450 is the run where
every hard rule held.

**450 is the evidence. What passed, in the room:**

| | |
|---|---|
| **Hard rule 3 — the doctor always wins** | the speaking bar rendered **solid and pinned**, and **Stop cut playback mid-sentence five times** |
| **Hard rule 1 — reference-only speech** | seven system utterances, all resolved server-side |
| **The transcript guarantee** | all seven in the grey channel, **none numbered**, note grounded **12/12** citing human turns only |
| **Hard rule 4 — the disclosure lock** | disclosure spoken as *"Dr Herath … you can speak to them"* — the 2026-07-28 wording, in the room |
| **The standing rule** | speak controls carried their reason **on the control** before Start; the labels gate disabled Approve with its reason in its own title |
| **The companion rule** | the asked chip read **"Again"** in words, not a lone glyph |
| **Single-voice labelling** | the one voice was labelled **Patient**, correctly |

**And the correction loop ran end to end on real data for the first time.**
Wrong labels → per-turn correction (turns 0 and 2, `turn.role_changed`
Doctor→Patient) → the stale-note gate arming → acknowledgement → approval.
**450 is the first consultation in this project approved after a hand-corrected
speaker label.** The audit trail carries the whole sequence, which is what
makes it evidence rather than a recollection: two `turn.role_changed`, two
`labels.acknowledged` (the second because the first correction's acknowledgement
was re-armed by the second correction — the gate behaving exactly as designed),
then `note.approved`.

**Third confirmation that the phantom filler is a live-path phenomenon:** three
"Thank you." turns appeared in 450's LIVE transcript and **none** in its final
transcript. That now holds for 445 (fifteen live, none final), 448 (~80 s of
near-silence, none final) and 450. Docket item 8 stays open, and its scope is
now firmly "the live transcript the doctor reads", not the note.

#### The defect run 5 found: an answer accepted and discarded in silence

The doctor tapped the speaker-count answer and **the pipeline ignored it**. 450
came out with the two-cluster split (turns 0 and 2 Doctor) and **no notice
anywhere**. The audit row settles the cause without guesswork:

    speakers.declared  {"count": 1, "applied": false, "already_used": 2}

The answer arrived **11 s after the consultation row was created** and found
`speakers_used` already set to 2. My own documented race, and the assumption
underneath it was simply wrong: the count was read immediately before the audio
phase on the theory that unloading MedGemma bought 10–30 s of slack, and on a
three-minute consultation it bought less than eleven seconds.

Both halves are fixed, and **the second half is the one that matters**:

1. **The pipeline now waits for the answer** rather than hoping to be slower
   than it — an event registered at Stop before the job is queued, released by
   any of the three taps, abandoned after a bounded 25 s. What must never wait
   is the RECORDING, and it does not: Stop still ends the consultation
   immediately and the patient can leave, because finalisation is already an
   asynchronous queued job. Pausing that job is not holding the consultation
   open. **Skip now posts** rather than staying silent, purely so it releases
   the wait at once — an offer that costs time is not an offer. A grace-period
   finalisation registers no waiter, because nobody is at the screen.
2. **A declaration that does not apply is now visible in three places**: the
   state says `declaration_ignored` explicitly rather than leaving two numbers
   to be compared, the review page carries the count used and the count declared
   and that the answer arrived too late, and approval is refused until it is
   acknowledged. One helper — `consultations.speaker_labels_unverified()` — is
   read by both the page and the approve guard so they cannot drift apart.

**The lesson is the pattern, not the instance.** This is the **fourth time in a
week** that a control accepted an action and explained itself somewhere the
doctor never looked — the sound-check offer, the finalisation spinner, the speak
controls, and now the feature built to fix the third one. Writing the standing
rule down did not prevent the fourth instance; what has actually caught each one
is a room. So the response is a test per instance rather than another reminder:
the new test fails if an answer can be accepted and then discarded without a
trace in the state, the guard, or the banner.

**Three smaller faults from the same run, all fixed:**

- **"Just me" contradicted the pipeline.** One declared voice labels every turn
  **Patient**, so a doctor who genuinely was the only speaker would tap "just
  me" and have their own words attributed to the patient — the exact failure this
  line of work exists to prevent, arriving through the wording. Options now
  describe who spoke: **only the patient / both of us / skip**. **A doctor-only
  recording is unsupported by design** (owner's call). Revisit it if a
  doctor-only recording ever becomes a real case: it would need a third option
  and a role rule that can label a lone voice Doctor.
- **The live transcript was ordered by arrival, not by time** — the Assistant
  line at 2:25 rendered above the patient line at 2:24. Not a lost race but the
  guaranteed outcome of the commit margin: a transcript line is committed only
  once it ends >2 s before the newest audio, while a spoken utterance is logged
  the instant it plays, so the machine is always ahead. One `insertByTime()` for
  both channels, and the tests **execute** it under Node rather than recognising
  it in the source.
- **The sound check claimed the room heard it on headphones**, in the same
  breath as saying no sound reached the microphone. Both cannot be true. It now
  reports what the doctor confirmed and says the room was not tested — and
  **every reading records its output device**, because the three readings so far
  (27 dB, 15 dB, 4 dB) cannot be compared when the audio path differed each time
  and nothing recorded it. The cause was the resolver, not the schema:
  `device_label` was filled from `audioCtx.sinkId`, a device id that is empty for
  the default device, so it recorded nothing.

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
6. **Hard rule 3 — do this one properly, it is what 447 failed.** Tap a
   long question, then *scroll down to the transcript* while it speaks.
   The speaking bar must still be on screen (it is fixed to the viewport);
   press **Stop** and playback must cut immediately. Repeat using **Esc**.
   Then confirm the chip you used now reads **✓ asked** with a ↻ icon, and
   that tapping it again still works.
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

## Phase 7b — session 1 (2026-07-28): the machinery, unstyled

Built to `PHASE_7B_KINDALIVE.md` as written. Four commits ("Phase 7b
1/4 … 4/4"), no new dependency anywhere — `pyproject.toml` and `uv.lock`
are byte-identical; vendoring is file copying, the same arms-length
pattern as Piper.

- **Vendored kindalive at pinned commit
  `a29bcf73e2c44cbf2fa6549ae28d1a9d1f6f37b6`** (MIT, upstream LICENSE kept
  beside the code, attribution in NOTICE): `engine/`, `emotions/`,
  `expression/face.py` **and `face_3d.py`** — kept because the
  `setTargets` payload construction (`face_payload`) lives there, not in
  `face.py` — plus `base.py` and the four config TOMLs, all under
  `vendor/kindalive/`, imports rewritten to `vendor.kindalive`.
  `face3d.js` copied **unchanged** into `app/static/`. The upstream LLM
  interpreter was deliberately NOT vendored (owner decision 2: impulses
  are injected deterministically). One structural note a future reader
  needs: **at this commit the upstream TOMLs are documentation mirrors**
  — upstream's presets actually live in a Python module that was not
  vendored — so this project reads the vendored `personalities.toml` with
  stdlib `tomllib` as its real config source (`app/face.py::load_preset`).
- **`[clinical]` preset** in the vendored `personalities.toml`, from
  stoic: GABA 0.7 / serotonin 0.55 baselines, adrenaline 0.02 with a 72 s
  effective half-life, affinity 0.4, interaction coupling 0.5. Every
  number is a commented first guess; the calibration pass sets them from
  real use. Measured: the same 0.5 adrenaline spike peaks lower and
  settles ~70 s vs ~85 s against [default]. One subtlety recorded in the
  TOML: lowering `interaction_scale` also weakens the GABA→adrenaline
  brake, so the shortened half-life is deliberately the main damping
  mechanism.
- **`app/face.py`** — everything between consultation events and the
  engine, deterministic (no model calls, no randomness, injectable
  clock, GPU-free). Events map to small commented impulses:
  consultation started, patient audio arriving (rate-limited to one
  injection per 2 s; frames inside a speaking window are skipped — that
  audio is our own playback), system speech started/ended (fed from the
  same server-held speak windows that drive transcript exclusion), stop.
  **The urgency alarm is deliberately NOT wired to the face** — a
  listening presence must not signal clinical state to the patient; the
  reason is in the module docstring and a test fails if an urgency event
  ever appears in the mapping.
- **Hard caps as a per-muscle policy in our layer** (the preset expresses
  intent, the caps enforce it): nine muscles **PINNED** at the preset's
  resting neutral — anger, frustration, disgust, fear and distress are
  unexpressible, not damped — including the inner-brow raise (empathic
  concern sits next to sadness; allowing a little of it is the owner's
  clinical call, so it starts pinned), `jaw_open` (laughter; the TTS
  mouth flap is unaffected — face3d.js layers `setSpeaking`'s flap on top
  client-side) and `lip_pucker` (ambiguous). Three **BANDED** —
  `eyelid_upper_raise` (attention), `cheek_raise` and `lip_corner_pull`
  (warmth) — clamped to neutral‥neutral+`FACE_BAND` (env, default 0.15).
  The **FREE** class (blink, breathing, saccades, speech flap) is
  client-side self-animation the server never sends. Full commented
  table in `app/face.py`; loosening any row is the calibration pass.
  Adversarial test: chemistry driven to anger/disgust maxima (brow_lower
  reaches 0.85 uncapped) and every emitted payload holds pinned at
  exactly neutral.
- **Wired over the existing WebSocket, no new transport.** Client sends
  `{"type":"face","on":bool}`; server confirms with `face_toggled`
  BEFORE the first tick, then streams `face_state` payloads at
  `FACE_TICK_HZ` (env, default 5). **Default OFF, and OFF is a
  first-class state** — no driver, no `face_state` traffic at all, and
  the renderer node is absent from the DOM, not blanked: it is the
  control arm of the planned CARE study. The unstyled panel sits last in
  the live page's stack; the toggle is disabled with its reason on the
  control until a live session exists. `setSpeaking` follows the same
  client transitions as the speaking pill. One client-side constraint
  worth knowing: the vendored `face3d.js` starts one rAF loop per init
  and has no teardown, so the page initialises it at most once and
  detaches/re-attaches a single stage node on toggle.
- **Audit (hard rule 5):** `face.toggled` per toggle (carries the
  session id and audio offset — no consultation row exists until Stop),
  plus one consultation-linked **`face.arms`** row written by
  `_complete_session` with the whole toggle history, so reconstructing a
  study arm is one query.
- **Deliberately deferred:** styling (DESIGN_SPEC.md and the mockups are
  in the owner's Downloads, not the repo — ask before styling anything);
  the CDS affect hint (owner decision 2 allows it later; nothing model-
  driven ships in this pass); the calibration pass (preset numbers, band
  width, impulse sizes, mood accent recolour). Face chemistry does not
  survive a reconnect (the driver is per-session but its tick task is
  per-connection and the driver is reset with a fresh toggle) — accepted
  for session 1, revisit only if it matters in a room.

### Are pre-merge WhisperX segments persisted? (REPORT ONLY, 2026-07-28)

Investigated for `RAW_TRANSCRIPT_VIEW_SPEC.md` (approved, not yet in the
repo). **The decision on building it is the owner's; nothing was
changed.**

> **Owner decision, 2026-07-29 — the persistence point is BEFORE the
> silence invariant.** The stored set is `result["segments"]` (the
> report's "one line earlier" option), with the segments the invariant
> drops **flagged in the stored set** rather than absent from it. The
> reason is the deciding argument, so it is recorded with the decision:
> the silence invariant is itself a layer that has eaten transcript —
> 445 lost six minutes to it — and the raw-transcript view exists
> precisely to make such layers visible. A view that only showed what
> survived the invariant would be blind to the one failure mode it was
> commissioned after. **Not built yet; the decision is banked** so the
> build, whenever it happens, starts from this point rather than
> re-litigating it.

- **What finalisation persists today:** `transcript_turn` rows only —
  post-merge, post-role (idx, role, start_s, end_s, text, confidence) —
  plus `quality_signals`, the single-voice flag, `system_utterance`
  rows and the note. **The raw ASR segments survive nowhere**: no table,
  no JSON on disk, no log line. One partial exception: when the silence
  invariant fires, up to 10 of the segments it DROPPED (start/end/first
  200 chars) go into the `transcript.silence_hallucination` audit row —
  dropped ones only, and only on that anomaly.
- **Where they last exist:** `app/finalize.py::transcribe_and_diarise`,
  local `raw_segments` — created by `drop_segments_in_excluded_spans(...)`
  and last consumed by `merge_into_turns(raw_segments)` a few lines
  later. They are not in the function's returned dict, so they die when
  it returns. The function runs in `asyncio.to_thread` with no DB
  access, so the minimal persistence point is: add them to the returned
  dict (pure data change inside the thread), then write them in
  `finalize_consultation` beside `save_turns` — which also covers
  refused (`unreliable_transcript`) consultations, since `save_turns`
  runs before the quality gate.
- **Minimal shape:** one row per segment mirroring `transcript_turn` —
  `(consultation_id, idx, cluster text, start_s, end_s, text,
  confidence, dropped bool)` where `cluster` is pyannote's SPEAKER_xx
  majority label and `dropped` marks silence-invariant removals if the
  view should show them. Size is trivial: segments are roughly
  sentence-sized (recording 66 → 99 segments over 300 s), so a 10-minute
  consultation is ~200 rows / tens of KB — against a ~19 MB WAV. Keeping
  full per-word JSON would multiply that by ~10 and is not needed for
  the spec's view.
- **Are `merge_into_turns()`'s inputs the segments the spec means?**
  Yes — post-ASR (WhisperX transcribe → align → `assign_word_speakers`),
  pre-merge, pre-role — with two nuances stated so the spec can decide:
  (1) they already carry **cluster labels** (per-word SPEAKER_xx), just
  not roles; (2) they are **post-silence-invariant** — segments mostly
  inside excluded spans are already gone. If the view must show those
  too, persist one line earlier (`result["segments"]`) or store both
  with the `dropped` flag above.
- The spec's read-from-storage-never-rebuild rule is confirmed
  load-bearing: re-running the pipeline is not reproducible (WhisperX
  turn counts moved ±2‥+5 on identical audio in the 2026-07-28 item-5
  verification), so a rebuilt view would describe a different run.

## Phase 7b — session 2 (2026-07-28): full range, the affect hint, placement

Two owner decisions made after using the face in the room, both the same
day. Four commits ("Phase 7b s2 1/4 … 4/4"); no dependency changes.

**1. Evaluation-first on expression range — PHASE_7B_KINDALIVE.md
decision 3 is SUPERSEDED for this phase, by the owner who wrote it.**
The face now displays kindalive's FULL emotional range, un-damped, and
the owner will gather feedback from human mock patients playing
difficult patients before deciding any caps. `FACE_EXPRESSION_MODE`
(env): **"full" (default)** runs the upstream default personality with
the per-muscle policy bypassed entirely — original kindalive behaviour;
**"clinical"** is exactly the session-1 behaviour ([clinical] preset +
per-muscle caps). The clinical arm is deliberately retained, built and
tested — it is one arm of the later comparison, not dead code, and the
session-1 section above describes it. The mode is read at driver
creation and recorded in `face.toggled` (every on-toggle) and
`face.arms` (`modes` list), so feedback sessions can always be
correlated with what the face was running; an unknown env value falls
back to full WITH a warning while the audit records what actually ran.

**2. The affect hint is in** (the piggyback option in brief decision 2).
Found in the room: with the upstream LLM interpreter skipped, nothing
drove the emotions — the engine only ever received the neutral attention
impulses, so the face could not respond to the patient at all. One
OPTIONAL field now rides the existing CDS assessment call (zero extra
model calls): `patient_affect`, enum positive/neutral/low/anxious/
distressed, judged from how the patient seems rather than their
diagnosis, "neutral" when unsure, absent means neutral. On a CHANGED
value `FaceDriver.on_affect` injects impulses shaped as **an attentive
listener's response, not a mirror** — warmth (oxytocin) always rises
more than any stress chemical, asserted by test; a distressed patient
gets warm concern, never a distressed face reflected back. Neutral
halves each affect chemical's excess over baseline (species half-lives
run 20 min–4 h — decay alone would never visibly settle a face within a
consultation). Magnitudes are commented first guesses for the
mock-patient sessions; the mapping table is in `app/face.py`.
Deterministic throughout; the real CDS model already emits the field
(seen in the live-Ollama test the day it was added).

**The urgency alarm stays NOT wired to the face — unchanged.** The
full-range decision changed expression RANGE, not inputs. The guard test
now covers the affect map as well as the event map.

**Fixed en route, worth knowing:** every multi-chemical injection shared
one `source_id`, and the engine's per-source saturation dampening is
keyed by source_id — so the second and third chemicals of a single event
were silently dampened because the first had just used the key. Source
ids are now per (event, chemical); repeats of the same event still
saturate, which is what saturation is for.

**3. Panel placement, interim:** the face pane moved from last in the
stack to directly below the session header, above the urgent-actions
position — visible without scrolling with a patient in front of the
screen. The transient alert banners keep priority above it (rule 3).
Commented as interim: final placement is an owner decision with the
styling pass (DESIGN_SPEC.md 7b addendum). Off still means absent from
the DOM entirely.

**Housekeeping the same session:** the lost specs were reconstructed and
committed (see the note at the design-pass section) — `DESIGN_SPEC.md`,
`NOTE_ICE_SPEC.md`, `REFERRAL_LETTER_STYLE.md` (all marked as
reconstructions; code authoritative where they disagree), the approved
`RAW_TRANSCRIPT_VIEW_SPEC.md`, and the original mockups at
`docs/mockups/`.

## Phase 7b — session 3 (2026-07-28): sticky dock, auto-on, the chain, the nudge

Five owner decisions, five commits ("Phase 7b s3 1/5 … 5/5"). Session 2
ran an earlier draft of its prompt, so its first two items here (the
placement and the auto-on) are 2026-07-28 decisions that missed session 2
— which is why **session 2's top-of-stack placement lasted one session**:
not a reversal, a prompt-version miss. All patient-facing wordings in
this session are the owner's, verbatim.

- **Sticky top row — urgent LEFT, face RIGHT (revised variant A,
  supersedes session 2's placement).** The approved mockup is
  `docs/mockups/face_placement_mockup.html` (body class vA; variants B
  and C are rejected alternatives kept for the record). A sticky
  two-column row under the app header with the page scrolling beneath:
  the red-flag alert MOVED out of the scrolling stack into the row's
  left half, so an unresolved alarm is on screen at every scroll
  position; the left half is the alarm's reserved home and **empty is
  the good state**; positions never swap. Clicks pass through empty
  halves (pointer-events), z-index below the app header and nowhere near
  the speaking bar. **Membership, not visibility, is the state model** —
  `updateStickyRow()` is the only writer, the row leaves the DOM when
  both halves are empty, and the tests execute the presence logic under
  Node for all four combinations, asserting position and container
  membership rather than existence (the 447 lesson). **The face-off
  toggle lives on the card, and with the card absent (face off) there is
  deliberately no manual-on control** — the on-path is the disclosure
  auto-on below; a manual off is final for the session.
- **Auto-on at Disclosure** (`FACE_AUTO_ON_DISCLOSURE`, default true):
  tapping the SPOKEN Disclosure button with the face off switches it on;
  the "in my own words" tick does not (the owner named the button).
  `face.toggled` carries `via` ("manual" | "disclosure_auto").
  **STUDY-ARM WARNING: face-off arm sessions must run with this flag
  DISABLED, or the arm silently breaks** — the disclosure will switch
  the face on mid-session. A manual face-off is never overridden again
  in the same session; the doctor always wins. *(Amended session 4: the
  Face pill can now turn it back on manually — what stays suppressed
  after a manual off is the AUTO-on. See the session 4 section.)*
- **The invitation auto-chains after a completed disclosure**
  (`AUTO_INVITATION_AFTER_DISCLOSURE`, default true): a disclosure that
  plays THROUGH (end_reason complete) is followed by the existing
  invitation phrase, wording unchanged, through the NORMAL speak path —
  its own utterance and audit rows (via `auto_invitation`), cut by
  Stop/Esc like any utterance. The structural safety is the existing
  disclosure lock: a cut-off disclosure leaves the session with no
  disclosure, so the lock refuses the invitation even if the chain
  condition ever regressed. Tested from both ends.
- **The silence nudge — THE FIRST AUTONOMOUS UTTERANCE, deliberately
  caged.** After the invitation has played through, if neither person
  speaks for `SILENCE_NUDGE_S` (default 5 s) the system speaks the new
  `silence_nudge` phrase ("When you're ready, tell me what's brought you
  in today." — owner's wording verbatim, pinned by test). The cage, all
  load-bearing: **at most once per consultation, enforced server-side**
  (marked used at request, so a cut-off nudge was still the one nudge);
  only after a COMPLETED invitation; disclosure-gated like every
  clinical phrase; `SILENCE_NUDGE_ENABLED` kills it at both ends (the
  client is told via `speech_config` and never asks; the server refuses
  if it asks anyway). The client detects the quiet window from what it
  already holds — the mic analyser (same 1e-4 floor as the dead-mic
  pill, so the surfaces agree about silence; ambient noise suppressing
  the nudge is the accepted bias) and the transcript stream — and
  requests through the normal speak path with `via` and the measured
  quiet duration, both audited (calibration data for the threshold).
  **The boundary this introduces, written in client and server and
  guarded by a test: this is the ONLY autonomous utterance in 7a/7b and
  must stay that way until 7c's behaviour-policy machinery exists — do
  not generalise it into an encourager loop.**
- **Sound-check wording**: the result no longer claims "expected on
  headphones" regardless of the audio path — in the room it said that
  while the recorded output was the monitor's NVIDIA HD Audio. It now
  reports what is known (the doctor's confirmation, the level, the
  output device by name) and the flat headphones explanation survives
  only when the device label itself indicates headphones; otherwise it
  is conditional. Same lesson as the single-voice notice: a notice that
  can assert something untrue teaches the doctor to discount it.

## Phase 7b — session 4 (2026-07-28): the pill, agenda priority, latency report

Session 3 passed its room check the same evening (consultations 452 and
454: sticky row, auto-on, invitation chain, sound-check wording all
verified in the room). Two follow-on items and one investigation.

**1. The Face pill — and one session-3 rule amended, by the owner.**
Room finding: after a manual face-off nothing could turn the face back
on, and before the disclosure there was no on-path at all. A Face pill
now sits beside Sound check: a full toggle showing its current state,
same toggle path, `face.toggled` audit with via "manual", disabled with
its reason until a live session exists. **"A manual off is final" is
amended: the pill can turn the face back on.** That rule existed only
because no control could reverse an off; the owner has now added one.
What stays: the disclosure AUTO-on remains suppressed after a manual
off — only the pill overrides one. The session-3 tests were amended
rather than deleted, each with a comment naming this decision.

**2. `questions_to_ask` is ordered by clinical priority** (CDS-side
prompt change only; schema untouched; the page renders in the order
received and has no client-side sort). The order is explicitly living —
re-rank freely — while the differential's pinned-name revision rules
stay as documented. **Harness re-run: 9/10 pass**, the one FAIL being
script-02 dengue, the docket's documented boundary case, which also
failed at baseline. Fire/silence and first-fire turns identical to the
stored baseline on all nine common scripts; script 10 (testicular
torsion) is in EXPECTATIONS but predated the stored JSON and passes.
Differential stability moved slightly both ways (aggregate
unchanged-update count 67/72 → 62/72; 09 improved) — a changed prompt
shifts temperature-0 outputs, and this is reported rather than glossed.
Spot check (01_chest_pain): radiation tops the agenda while
undetermined, answered questions drop off, differential untouched 4/4.
**REPORT, as asked: an explicit priority field is NOT materially more
robust** — every consumer (the tap-to-ask panel, 7c's "top agenda
question") needs only rank order, which the array already carries; a
field would add schema churn and a second thing the model can get
wrong. Revisit only if the UI ever needs to DISPLAY per-question
urgency.

**3. First-assessment latency (REPORT ONLY — nothing changed).** Room
finding: some patients stop talking before the questions box first
populates. Measured from code and the journals of 452 and 454:

- **The trigger:** audio commits through the rolling live path
  (re-transcribe every `PROCESS_INTERVAL_S` = 1.5 s; a segment commits
  only when it ends > `COMMIT_MARGIN_S` = 2.0 s before the newest
  audio); the first CDS call fires when committed transcript reaches
  `CDS_MIN_NEW_CHARS` = **150 characters** (main.py) — roughly 15–40 s
  of patient speech depending on pace and pauses. `engine.update` then
  runs TWO sequential model calls (assessment, then the urgency
  officer); the result is sent on the next ≤2 s loop pass; render is
  immediate.
- **452 (MedGemma warm):** first human speech ≈19:18:00 → assessment
  call started 19:18:43 (43 s accumulating 150 chars) → assessment
  8.7 s + urgency 3.2 s → questions on screen ≈19:18:55. **≈55 s
  speech-to-questions.**
- **454 (MedGemma cold):** first human speech ≈20:13:44 → first call
  ≈20:14:14, which had to RELOAD MedGemma (453's finalisation had
  unloaded it): 14.4 s including the llama-server start, + urgency
  4.5 s → questions ≈20:14:33. **≈49 s speech-to-questions,** ~10 s of
  it the reload — the num_ctx-mismatch reload cost already measured in
  the VRAM section, now observed on the live path.
- **Where the time goes:** the 150-char gate dominates (30–45 s); the
  two sequential model calls add 12–19 s; commit margin and loop tick
  add a ~3.5–5 s floor; render is negligible.
- **Options, all the owner's to choose (none taken):** (a) a lower
  FIRST-call threshold (e.g. ~50 chars, 150 thereafter) — pulls the
  first population earlier by ~20–30 s at the cost of one extra
  MedGemma round (~12 s GPU) and a thinner first differential; the
  prompt already says "early, prefer a short list", and the revision
  rules cope — the pinned-name rule just starts from a smaller list.
  The urgency officer would also run earlier, which is a safety gain,
  and it is stateless so an extra early round cannot anchor it. (b) A
  first-call-specific trigger (first committed turn, or N seconds after
  the invitation) — same effect, more code paths. (c) Send the
  assessment to the client before the urgency call returns — saves
  3–4.5 s every round but splits one message into two and reorders the
  alarm relative to the panel; the alarm must never arrive later than
  it does today. (d) Keep MedGemma resident across finalisation by
  matching num_ctx (the reload was ~10 s of 454's 49) — already flagged
  in the VRAM section as fixable and unfixed. (e) A lighter first
  prompt — saves a few seconds of generation; another prompt variant to
  keep coherent with the revision rules.

## Phase 7b — session 5 (2026-07-28): first-call trigger, num_ctx, 7c prereg

The owner chose among session 4's latency options: the first-call
trigger and the num_ctx alignment — and explicitly NOT the
assessment-before-urgency reordering (the alarm path is not to be
touched for a 3–4 s gain). Three commits ("Phase 7b s5 1/3 … 3/3").

- **First CDS call fires on the first committed turn**
  (`CDS_FIRST_CALL_ON_FIRST_TURN`, env, default true — the old
  behaviour is restorable without a deploy). Every later call keeps the
  150-character cadence unchanged. **The new latency expectation is
  ~20 s from first patient speech to first questions** — the ~3.5–5 s
  commit floor plus the two sequential model calls (9–12 s warm) —
  model-call bound now instead of gate-bound; the old figures were 55 s
  (452) and 49 s (454). The urgency officer rides the same update it
  always has (asserted by test: assessment call, then urgency call, one
  update, the alarm in its result), so the alarm can only arrive
  EARLIER than before. A live-model test pins the session-4 claim that
  the revision rules tolerate the thin first list.
- **One `num_ctx` for every MedGemma call** (`CDS_NUM_CTX`, env,
  default 16384, defined in `app/cds.py` and imported by `rag.py` and
  `notes.py` so the paths cannot drift apart again). This removes the
  reload the VRAM section flagged and session 4 saw cost ~10 s on 454's
  first live assessment. **Measured after the change: warm same-context
  round trip 0.23 s; each num_ctx switch cost 3.90 s.** Fit confirmed
  live: 21672 MiB with MedGemma resident 100% GPU at 16384 (the
  baseline's worst case for this exact configuration was 22309 MiB with
  2255 MiB free). Temperature, seed, keep_alive untouched. The VRAM
  section's "reloaded between phases" finding is now resolved.
- **`PHASE_7C_EVAL_PREREG.md` is committed and FROZEN** — approved by
  the owner at the end of the 2026-07-28 working session; changes from
  now on are logged amendments. One TODO it creates is deliberately not
  done and is **pending, assigned to the owner + Claude Cowork**: the
  one-page open/closed question-classification rule (metric 5), to be
  written before the first 7c run.

## Phase 7a — session 3 (2026-07-29): the barge-in detector, built and OFF

The deliberately-held last 7a item, unblocked by owner decision
2026-07-29 (the mock-patient round moved to next week; barge-in is a hard
precondition for 7c). Five commits ("Phase 7a s3 1/5 … 5/5"). No new
dependencies; `pyproject.toml` and `uv.lock` byte-identical.

**What was built (spec build item 5 / Part 9 D5, gate-and-cut's detection
half):**

- **The detector** (`live.html`): a SECOND, echo-cancelled capture stream
  (`echoCancellation: true`, `autoGainControl: false` — AGC would break
  the envelope proportionality) feeding one analyser and nothing else.
  Detection runs ONLY while a system utterance is playing. On a sustained
  crossing it cuts through `stopSpeaking('barge_in', latency)` — the SAME
  server-audited path as the Stop button, `end_reason` distinguishing the
  two, measured `cut_latency_ms` riding `speak_ended` into the existing
  column. Nothing is ever queued behind an utterance (queue depth zero),
  so cutting the current one cancels everything; a barged disclosure does
  not chain the invitation (reason ≠ complete — the session-3 chain
  condition already guarantees it).
- **The envelope-proportional threshold**: `speech.playback_envelope()`
  computes each utterance's normalised RMS envelope server-side from the
  same bytes the client plays (no second implementation in JS to drift);
  it rides `speak_ready` only when the flag is up, so the shipped
  protocol is byte-identical to session 2's. The expected residual echo
  is **the measured loopback level — read from the newest
  `speech.sound_check` audit row for the session's doctor
  (`audit.latest_detail`), never re-measured — scaled by that envelope**;
  mic energy must exceed it by `BARGE_IN_MARGIN` (2.0, an uncalibrated
  guess, stated as such), sustained `BARGE_IN_MIN_MS` (150), with an
  absolute floor `BARGE_IN_RMS_THRESHOLD` (default 0.02 — a guess placed
  between this project's own measurements: room noise 0.008–0.011, real
  speech 0.056–0.153, the 445 numbers). Config reaches the client in
  `speech_config`; a doctor with no sound-check rows gets a null loopback
  and absolute-floor-only detection, stated rather than invented.
- **The two standing constraints, enforced as tests**
  (`tests/test_barge_in_constraints.py`): the detector stream is NEVER
  wired to the mic meter (structural asserts — one `connect` on the
  detector source, no barge token in the meter's loop or the sound
  check's measurement function, no reassignment of the shared analyser),
  and the approved disclosure gains no interruption line (the original
  absence test in `test_speech.py` is **pinned verbatim** — amending it
  there fails loudly here; the phrase table is asserted not to branch on
  any BARGE_IN flag). One pre-existing test was AMENDED, not weakened:
  "exactly one getUserMedia in the page" became "exactly two, and the
  second only inside the detector" — the spec (§1.4) requires the second
  stream, while the sound check still reads the shared capture.
- **`scripts/calibrate_barge_in.py`** — REPORT ONLY (reads in a READ ONLY
  transaction; sets nothing). Groups the `speech.sound_check` rows by
  output device (readings on different devices are not comparable),
  reports both sides of the D5 target with the measured numbers and a
  plain per-device verdict — predicted MET / predicted NOT MET /
  INSUFFICIENT DATA — plus recommended sound-check good/faint ratios
  when ≥5 consistent confirmed-heard readings exist, and a what-next
  footer. **First live run, 2026-07-29: 14 readings across three device
  groups; seven predate the device-label fix and can support nothing;
  the NVIDIA monitor output has 4 usable of the 5 needed; the Realtek
  speakers have 1 (a `not_heard`, same day). Verdict everywhere:
  INSUFFICIENT DATA.** So the current state is exactly what the report
  says: more sound checks at normal room volume on the device the room
  actually uses, then re-run.

**`BARGE_IN_ENABLED` is FALSE and stays false pending calibration.** Hard
mute is this design with the detector off; both failure modes degrade
safely (a false stop costs a re-tap, a miss IS hard mute). It flips only
when both sides of the D5 target are met — false stops ≤ 1% of
utterances AND ≥ 90% of true interruptions caught within 300 ms — **and
flipping it is the owner's act, recorded here, not a code change.** This
is a comfort parameter, not a safety parameter: exclusion is structural,
so no threshold setting can corrupt a transcript.

**What the owner runs next:** sound checks at normal room volume on the
room's real output device until a device group reaches 5 usable readings
(each check is stored automatically), then
`uv run python scripts/calibrate_barge_in.py` again. If both sides read
predicted met, the next step is the D5 scripted room run — utterances
under silence, under room noise, and with scripted interruptions,
tallied against the script — before any flip of the flag. Re-run on any
change of speakers, microphone or room, and record results here.

### The within-minute loopback collapse, and what is processing the mic (2026-07-29)

The owner took four sound checks in 32 seconds on the NVIDIA monitor
output at a volume he confirms he did not change (22:42:49–22:43:21,
in the audit rows): **peaks 0.148, 0.182, 0.014, 0.025 — a ×13 collapse
inside one minute**, with the noise floor stable (0.004–0.008) and the
doctor answering *yes* every time. The room stayed audible; only the
measurement collapsed. Separately, two low-ratio readings that morning
carry visibly inflated noise floors (0.089, 0.077) from street noise
through an open door — procedural, explained, and not this finding.

**The capture-stream constraints report (item 1, REPORT ONLY — no
behaviour change; which streams get which constraints is the owner's
decision because it touches the faithfulness guarantee):**

- **What each stream actually requests** (`live.html`). Stream (a) — the
  one capture feeding the meter, the transcriber and the recording —
  explicitly sets `echoCancellation: true` and `noiseSuppression: true`;
  `autoGainControl` is **unspecified, and Chrome defaults it ON**. So all
  three processors are active on the audio the server stores, and AGC
  was never chosen by anyone. Stream (b) — the barge-in detector — sets
  all three explicitly (EC on, NS on, AGC off).
- **The hypothesis holds.** Chrome's echo canceller uses the browser's
  own playback as its reference, and it is *adaptive*: repeated exposure
  to the same signal converges the filter. The sound check plays the
  same phrase through the same path — readings 1–2 are pre-convergence
  residual, readings 3–4 post-convergence. A stable floor, a constant
  volume, a human hearing it fine, and a ×13 measured collapse in nine
  seconds is the textbook AEC-convergence signature (NS adaptation and
  AGC can contribute; AEC is the dominant term). The constraint
  configuration doesn't merely permit this — it guarantees it: **the
  sound check measures our own playback through a canceller whose
  entire job is to remove that exact signal.**
- **Implication 1 — the recording.** The stored WAV is **already
  processed audio**: our own utterances arrive partially cancelled,
  quiet speech is shaped by NS, and absolute levels ride on AGC. The
  transcript-exclusion guarantee is untouched (server-held byte windows,
  signal-independent), but "the original WAV is the faithful record of
  the room" is true of the bytes, not of the room: they were never raw.
  Every RMS number this project has derived from recordings — the 445
  forensics, the S4 trailing-content thresholds, the hallucinated-filler
  analysis, the barge-in absolute-floor default — is a calibration of
  the *processed* chain. Internally consistent while the constraints
  stay put; re-derive them if the constraints ever change.
- **Implication 2 — ASR.** EC/NS/AGC is the standard comms chain and can
  help or hurt Whisper (NS strips hiss but eats soft consonants; AGC
  pumps room noise in silences — possibly feeding the live-path filler
  turns). Unmeasured on this system either way; recordings 66–70 were
  all made through the current chain, so any constraint change needs at
  least the note-quality eval re-run before being trusted.
- **Implication 3 — measurement stability, the barge-in input.** The
  measured "loopback level" is an AEC *residual*, which depends on
  convergence state, not just room and volume — so the spread check can
  never pass on this chain, however many readings are taken: the
  instrument adapts, the room doesn't. Worse, the failure direction is
  the bad one: at the first utterance after a quiet gap the canceller is
  unconverged (residual at its highest) while a stored converged-low
  reading would set the threshold low — a predicted false stop, D5's
  side 1.
- **Options (costs stated, NONE taken):** (A) raw capture on stream (a)
  — all three explicitly off: the WAV becomes the actual room, levels
  stabilise, sound checks become calibratable; costs an ASR re-check and
  re-deriving every RMS threshold, and old sound-check rows stop being
  comparable (the `--since` cut below exists for exactly that). (B) EC
  off on stream (a) only — the transcript path never needed AEC
  (exclusion is server-held), and this alone removes both the ×13
  instability and the erasure of our voice from the WAV; NS/AGC
  decisions stay separable. (C) measure loopback on the detector's own
  stream (b) — measures what the detector actually hears, but it is a
  different AEC instance, still convergence-dependent, and does nothing
  for the recording. (D) status quo — barge-in calibration stays
  impossible on this chain and the D5 ship rule resolves to hard mute,
  which the spec explicitly blesses. Whatever is chosen, future
  sound-check rows should record the constraint set in force (a small
  follow-up), so readings are comparable within a configuration epoch.

### Threshold design under the split chains (2026-07-30, REPORT ONLY)

With EC off on the main stream (the 2026-07-30 decision, next section),
the sound check now measures the TRUE acoustic loopback — stable, at
last calibratable — while the detector still listens through its own
echo-cancelled stream, where our playback arrives as a much smaller,
convergence-dependent *residual*. The question item 3 asked: can a
raw-stream measurement drive an EC-stream detector threshold?

- **Yes, as an upper bound — and the bias direction is the safe one.**
  Threshold = margin × raw loopback × envelope is always ≥ margin × the
  residual the detector actually hears, so echo-driven false stops
  become nearly impossible (D5 side 1 strengthened). The cost lands on
  side 2: during loud playback the threshold (raw peaks measured at
  0.15–0.18 → threshold 0.3+) sits above quiet interrupting speech
  (0.056), so soft interruptions are missed in loud moments. A miss IS
  hard mute, per utterance — the failure mode the spec explicitly
  blesses — and no setting here touches a transcript. Two honest
  caveats: (1) AGC still rides the main stream, so the measured absolute
  peak drifts slowly with gain state — if the five fresh readings still
  spread wide, AGC is the next suspect, and comparing the stored ratio
  (floor and peak ride together) against the absolute peak will say so;
  (2) under option 1 the margin's meaning changes — it is now a margin
  over the TRUE loopback, not over the residual, and the room run may
  justify lowering it (1.2–1.5) if misses dominate.
- **The dual measurement (recommended if side 2 fails in the room):**
  the sound check samples BOTH streams during the same playback — the
  main stream giving the true loopback, the detector stream giving the
  residual the detector will actually compare against. The pair yields
  the detector's true expected residual (an envelope scale neither over-
  nor under-estimated), and their ratio is the canceller's attenuation —
  the ×13 story becomes a measured convergence curve across repeated
  checks instead of a mystery. Costs: the check must open (or briefly
  open) the detector stream before a consultation, which brushes spec
  10.3's "do not open a second stream for this" — that sentence was
  written to protect the mic-cluster invariant for the check's own
  measurement, but extending the check to a second stream is a spec
  amendment and therefore the owner's; the audit row would carry two
  measurement sets with per-stream chains; and a pre-consultation
  convergence state is representative of, not identical to,
  mid-consultation state.
- **Rejected: a fixed attenuation factor** scaling raw loopback down to
  a guessed residual — the attenuation is exactly the unstable quantity,
  and only the dual measurement can measure it.

**Recommendation (nothing built beyond items 1–2, per the brief):** run
the calibration campaign on the raw-stream measurement first — stable,
calibratable, fails toward hard mute. If the D5 scripted room run then
fails side 2 for soft speech, build the dual measurement with the
owner's spec-10.3 amendment; it is the principled fix and makes the
canceller's convergence visible into the bargain.

### Regression insurance for the chain change (2026-07-30)

The note-quality harness was re-run against its stored expectations
after the capture-chain change: **mean coverage 94%, 0 discrepancies
across all 10 notes, citations 100% bar the one pre-existing 23/24**.
Nine of ten notes are byte-identical to the stored baseline
(`evals/note_results.json`, refreshed); script 01's note is reworded at
identical marks — the known temperature-0 wobble of this stack (same
class as the session-4 CDS re-run's differential drift), reported rather
than glossed.

**What this does and does not cover, plainly:** the stored recordings
and mock scripts all predate the chain change, so this run proves the
NOTE PIPELINE is undisturbed by this session's code — it says nothing
about audio captured through the new chain. **The live-chain check is
the owner's two-minute job after the restart**: one short scripted
recording through live→Stop→review on the new EC-free capture, read the
transcript and note. Until that is done, the new chain has never
produced a consultation.

**`calibrate_barge_in.py --since YYYY-MM-DD`** (built the same session):
limits every per-device analysis to readings from that date onward, so
the current room configuration is evaluated without the device's history
polluting the spread — the intended cut after any change of volume,
position, or capture constraints. Excluded readings are counted and
dated in the output; a narrowed window is never silent. Default remains
all readings. Live run with `--since 2026-07-29`: the NVIDIA device
still reads spread ×16.5 — the collapse is *inside* the window, which is
the finding above confirmed by the tool built to see it.

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
6. **Phase 7a session 3: BUILT 2026-07-29** — the barge-in detector
   (second echo-cancelled stream, envelope-proportional threshold fed
   from the `speech.sound_check` audit rows, never re-measured) and
   `scripts/calibrate_barge_in.py` reporting both sides of the D5 target
   per output device. The two standing constraints are enforced as tests
   (`tests/test_barge_in_constraints.py`). `BARGE_IN_ENABLED` remains
   **false pending calibration** — the first live report read
   INSUFFICIENT DATA on every device — and flipping it is the owner's
   act. Full account in "Phase 7a — session 3" below.
7. **The Phase 7a real-room check has now been run FOUR times, and the
   fourth passed the guarantee** — 445, 446, 447 on 2026-07-25 (the missing
   six minutes, the offer eating taps, no way to stop an utterance) and
   **448 on 2026-07-28, where the transcript guarantee held**: seven system
   utterances, all in the grey channel, none numbered, note grounding 6/6
   citing human turns only. Full account in "Consultation 448" above; **448
   must not be voided or purged.** The pattern held even so — 448 found two
   interface defects (speak controls enabled before the first connection;
   an asked chip that looked spent), both fixed and pinned, and it raised
   **two open questions that are still open**: the diarisation
   misattribution and the speaker-blind grounding gate. 448 **stopped
   early**, so the parts of the walkthrough after the chip defect —
   including hard rule 3's scroll-away Stop — were not done in that run.

   **RUN 5 — consultation 450, 2026-07-28 — CLEARED IT.** Every hard rule
   verified in a room: the speaking bar solid and pinned with Stop cutting
   playback mid-sentence five times, seven system utterances all in the grey
   channel and none numbered, note grounded 12/12 on human turns only, the
   amended disclosure spoken, the standing rule and its companion both holding
   on screen. The full correction loop also ran end to end on real data for the
   first time, and **450 is the first consultation approved after a
   hand-corrected speaker label.** Full account in "Run 5 — consultation 450"
   above. **The pattern held a fifth time**: 450 found the declared count being
   accepted and silently discarded, plus three smaller faults, all fixed. It is
   the fourth instance in a week of a control accepting an action and explaining
   itself where nobody looked — see the lesson in that section.
8. **Hallucinated filler on ordinary silence: assessed, not built.** About
   fifteen phantom "Thank you." turns in 445's LIVE transcript. Confidence
   cannot catch it (there is none on the live path, and on the final path
   it does not separate); acoustic energy separates it by more than an
   order of magnitude. Findings and a sketch are in its own section; the
   shape of any defence is the owner's call. **Narrowed by 448 and confirmed
   again by 450**: 448's ~80 s of near-silence produced **no** phantom turns in
   the final transcript, and 450 produced **three** in its live transcript and
   **none** in its final one. Three consultations, same split — this is a
   live-path phenomenon, and its scope is the transcript the doctor reads in the
   room rather than the note.
9a. **Speaker misattribution — (a) ADDRESSED 2026-07-28, (b) HELD.** The
   defect was in ALL THREE 7a consultations (446 turn 0; 447 turns 0, 2, 4;
   448 turns 0, 2), caused by the fixed `num_speakers=2`, and hidden for
   three consultations because the notes were correct — the model inferred
   speakers from content and wrote accurate notes over wrong labels.
   **(a)** RESOLVED by a **declared** count, after the unpinned range was
   tried, measured and replaced — it fixed 448 and 446, failed on 447 and
   **regressed recording 66**. The doctor now declares the count at Stop
   (default 2), a single cluster is labelled Patient and flagged, the review
   page raises an acknowledge-gated notice worded to describe what the system
   did rather than what was in the room, per-turn role correction is the
   backstop, and a role change marks the note as drafted against older
   labels. **Verified 8/8 on the real recordings** — table in the section
   above, with the turn-count variance and the pre-existing within-turn
   speaker bleed both stated rather than glossed. **(b)** The
   speaker-aware grounding gate is **deliberately not built** until the
   labels are trustworthy — owner decision, the sequencing argument was
   accepted. **446, 447 and 448 are retained unrepaired as the evidence
   set**; 447 in particular would, if approved as it stands, be signed with
   a transcript saying the doctor complained of a sore throat.
9d. **The suite's green depended on alphabetical collection order** (found
   and fixed 2026-07-28). `tests/test_speech_exclusion.py` installed a
   `StubSpeech` on the process-global `app.state` and never removed it, so
   four tests in `tests/test_speech.py` failed whenever they ran *after* it —
   which they never did, because `test_speech.py` sorts first. **A suite that
   can hide a failure by ordering is the same class of problem as a test that
   encodes the bug as the requirement:** in both cases the tests agree with
   something that is wrong. Fixed by restoring every installed attribute in a
   `finally` and asserting the stub is gone. Running the suite in **reverse
   collection order** then found a second dependency pointing the other way:
   three sound-check tests never installed a speech service and only worked
   because an earlier test in the same file had left one behind. **Depending
   on another test having set up your state is the same fault as leaking
   state into another test.** Both fixed; 375 pass in forward order and 375
   in reverse. Worth repeating the reverse run after any new app.state
   fixture — a throwaway `pytest_collection_modifyitems` plugin does it with
   no new dependency, so the lockfile stays untouched.
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

9c. **Interface lesson, 2026-07-25 (446/447): a control that cannot act
   must not look as if it can.** Three controls in one evening accepted a
   tap, did nothing, and explained themselves in a banner elsewhere; the
   owner missed all three. The standing rule and its accessibility
   reasoning are recorded in its own section above and in `live.html`.
   The generalisable part for the failure-mode library: **the bug was
   never in the explaining, it was in the accepting.** Each of the three
   had a perfectly good message that nobody read, because the place a
   person looks after pressing a control is the control. Worth applying
   to the other pages (Today, Consultations, review) — this audit covered
   the live page only.

9. **Safety note carried forward from the adjudication:** any future
   Sinhala transcription path must be evaluated **specifically on
   drug-name and numeric-marker recovery**, not on CER or WER alone.
   The four terms lost by every model were two drug names (`losartan`,
   `atorvastatin`), the three-month control marker (`HbA1c`), and the
   diagnosis (`neuropathy`) — while the aggregate metrics rated the
   models as merely mediocre. Aggregate error rates do not see this
   class of loss; the step 6 method (curated terms, adjudicated) does.

10. **A stale `in_consultation` queue entry, and what day-scoping does to
   it** — **FIXED 2026-07-28** ahead of the collaborator's access, because the
   lockout half of it would have met her with nothing but "busy". The close
   path can now reach past today and a startup sweep closes entries abandoned
   before Start on an earlier day; see "The abandoned-walk-in lockout" above
   for the shape and the two conditions that keep the sweep safe. The
   observation as originally recorded follows, unchanged, because the analysis
   is what led to the fix. (Observed 2026-07-27, deliberately not fixed at the
   time — recorded for the owner's decision.) **Queue entry 164 exists and is
   stale**: patient 253
   ("Shivesh"), `queue_date` **2026-07-26**, position 1, created 14:53:24
   by user 182 (`herath`) via `queue.walk_in_started`. Verified against
   the database: it is still `in_consultation`, there is **no consultation
   row for that patient at all**, and its only audit event is the walk-in
   start — no `queue.cancelled`, no completion. A walk-in was opened for
   the 2026-07-26 demo and abandoned before Start.

   **Every queue query is scoped to `queue_date = CURRENT_DATE`** —
   `frontdesk._ENTRY_SELECT` (so `get_entry`/`current_entry`),
   `close_entry`'s own `SELECT`, and the concurrency guard inside
   `start_walk_in`. The consequence, checked in the code rather than
   inferred: once the date rolls over, **both** front-desk recovery paths
   for an abandoned session stop being able to see it. `GET
   /api/queue/{id}/resume` answers **404 "no such queue entry today"**
   (`get_entry` returns None) and `POST /api/queue/{id}/close` answers
   **409 "entry is not open"** (`close_entry` returns None). Nothing that
   can close such an entry is left; it is now permanent.

   **While it is still the current day, the same entry holds the
   one-active-consultation slot with nothing to resume into.** The guard
   is stronger than "that doctor's" slot — it is the single system-wide
   slot from the capacity statement, so an abandoned walk-in blocks
   **every** doctor, not just the one who opened it (`start_walk_in`
   inserts only `WHERE NOT EXISTS (… queue_date = CURRENT_DATE AND status
   = 'in_consultation')`; `queue_start` refuses via `current_entry` the
   same way, auditing `live.slot_rejected`). Resume would have sent the
   doctor to the live page (`mode: live`, since no consultation exists),
   which is survivable — but the slot stays held until someone closes the
   entry or the day ends. Nobody was actually blocked here: there are no
   `live.slot_rejected` events on 2026-07-26 or after.

   So day-scoping is both the reason it becomes unreachable and the reason
   its blast radius is bounded — the block expires overnight, and what
   survives is an uncloseable row. **The decision is the owner's** and
   there is a real one in it: whether an `in_consultation` entry with no
   consultation row should be resumable at all, whether the recovery paths
   should be able to look past today, and whether an abandoned walk-in
   should release the slot by itself. Not something to settle by quietly
   updating one row.

11. **Fidelity specimen 5 — attribution drift (consultation 448,
   2026-07-28).** For the claim-by-claim audit (item 2), and the same class
   as the *wheelbarrow*/three-wheeler substitution in item 3 — the words
   are close to the audio and the **attribution** is not.

   | | |
   |---|---|
   | Transcript, turn 0 | "My friend was watching the farm, Clarkson's farm. And as you know, Jeremy Clarkson was diagnosed with …" |
   | Note claim | "Patient requests prostate cancer screening due to worry **after seeing** Jeremy Clarkson's diagnosis **on TV** [0]." |

   The transcript has the patient's *friend* watching, and the patient
   hearing about it. The note has the patient seeing it on television. Both
   sentences are about the same programme and only one of them is what was
   said. It is cited, it is not flagged, and the citation chip resolves — so
   **this is the specimen class that survives every gate the project
   currently has**: grounding checks that a claim cites a real turn, never
   that the claim is what the turn says. Nothing here proposes a defence;
   it is recorded as evidence for the human-led audit.

   **Recorded with it, from the same note: the ICE extraction returned
   identical text for two different fields** — *"Patient's ideas: Worried
   about prostate cancer [2]"* and *"Patient's concerns: Worried about
   prostate cancer [2]"*, word for word. Ideas (what they think is going
   on) and concerns (what they are worried about) are meant to be
   different things, and duplicating one into both loses the distinction
   the 2026-07-24 ICE prompt change exists to capture. The expectations
   entry was distinct and correct ("Wants a PSA test as it is simple").
   Prompt-level observation for the owner, not a code defect.

12. **Guideline retrieval drifted to the wrong anaemia (consultation 450,
   2026-07-28). MEASURED, NOT CHANGED** — retrieval evaluates 9/9 and a change
   made without a harness run risks that, so the fix (if any) belongs with one.

   450 was a 47-year-old with fatigue, brain fog, lighter periods and flushes;
   the differential led with perimenopause and the panel gave three of six
   citations to **NG203, chronic kidney disease** — erythropoiesis-stimulating
   agents, IV iron in stage 5 haemodialysis. Accurate, cited, and irrelevant to
   this patient.

   Reproduced against the live corpus (read-only). **The condition that drove it
   is the bare word "Anaemia".** Perimenopause and Hypothyroidism retrieve
   cleanly from their own guidelines (NG23 top hit 0.631, NG145 0.570, nothing
   else near). The anaemia query does not: of its top 12, **six are NG203 and
   five are CKS iron-deficiency**, and NG203's best (0.570) outranks four of the
   five CKS passages. CKD-anaemia text genuinely *is* about anaemia, and NG203
   brings **75 chunks to CKS's 32**.

   **What each control did, measured:**

   - **The similarity floor (0.45) did nothing at all.** Every candidate is well
     above it, and structurally it can never trim a mixed set: it gates only
     `passages[0]`, the single top hit. It is a relevance floor, not a
     composition control.
   - **The per-source cap (2) is the only thing that held**, and it worked: the
     merged pool held **seven** NG203 passages and the cap admitted two.
   - **But the cap is symmetric, and that is the finding.** With a six-slot
     budget it limits the RIGHT source exactly as hard as the wrong one. Asked
     the more specific *"Iron deficiency anaemia"*, CKS contributed **ten**
     passages to the pool and **eight were discarded by the cap** while NG203
     still took two slots (0.613, 0.594). The correct guideline can never exceed
     2 of 6 however well it matches.
   - **The cap governs PASSAGES, not CITATIONS.** Two NG203 passages can carry
     three of six citations, which is the likely arithmetic behind what the owner
     saw. Nothing limits how often the summariser cites the same passage.

   **It is only partly the NG28-versus-CG173 shape.** That was one guideline's
   *title vocabulary* dominating a concatenated query, and the per-condition
   search already fixed it. This is different: two guidelines legitimately
   competing for the same one-word query, with the larger corpus winning more
   slots. Options for a harness run, none started — a per-condition slot budget
   instead of a global six; citation-level diversity rather than passage-level;
   or having the CDS name conditions more specifically, since *"iron deficiency
   anaemia"* retrieves visibly better than *"anaemia"* and that is a CDS-side
   change, not a retrieval one.

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
  check (spec Part 10). **Tap-to-ask works end to end.** **Session 3 (the
  barge-in detector + its calibration script) was built 2026-07-29 after
  the real room had used tap-to-ask; `BARGE_IN_ENABLED` stays false
  pending calibration — see "Phase 7a — session 3".** The real-room check
  has since been run five times and **run 5 (consultation 450) cleared
  every hard rule** — see "Phase 7 opened" item 7. **OPENED 2026-07-25 by
  owner decision**,
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
- **`JoydeepSinha1988` (id 570) audits as `user.registered`, not
  `user.registered_pending`, because it predates approve-to-activate** — it
  was created 2026-07-24 19:29, before that landing, so it went active
  without an approval step and its audit row carries no `ip`. It is a known
  invited demo user who **has not yet logged in** and is **deliberately
  being kept active**. Recorded so a future audit does not re-flag it as a
  gate failure: it is not one, it is a pre-gate account.

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
