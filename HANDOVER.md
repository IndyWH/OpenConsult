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

One machine (RTX 4090, 24 GB VRAM, native Ubuntu 26.04 — `indy@mlrig`,
project at `/home/indy/Projects/consultation-ai`), everything local.

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
- `uv run pytest` — 683 tests; heavy ones self-skip if Ollama/Postgres/
  corpus are absent (none do on this machine — see the post-migration
  operations section). Since 2026-07-24 the suite runs against a disposable
  `consultation_ai_test` database (created/dropped per session by
  `tests/conftest.py`) and never writes to the live database; needs a
  one-time superuser grant, see Troubleshooting.
- Postgres 18.4 + pgvector, running natively, database `consultation_ai`,
  credentials in the gitignored `.env` (see `.env.example`).

## Phase status vs PROJECT_PLAN.md

| Phase | Status | Notes |
|---|---|---|
| 0 — Foundations | **Done except one recording** | Env, Postgres, app, tests all in. Seventeen mock scripts written: 10 English (5 routine, 4 red-flag variants, 1 held-out), 2 Sinhala/English code-switched (`_si`, for the Phase 5 ASR recordings eval), 5 UK private-GP (`_uk`, CDS restraint + buried-red-flag urgency) — see `mock_consultations/README.md`. **Real two-voice recordings made 2026-07-12** through the live app (consultations 66–70), copied to `mock_consultations/recordings/`: routine 01–04 English + `03_diabetes_review_si`. **Still to record: `05_epigastric_pain_en`** — required for Phase 2 real-audio validation and the note-quality eval, and the one item Phase 0 now closes out on. `01_chest_pain_si` is **not being recorded for v1** (2026-07-25): it needs a Sinhala-speaking second reader and only feeds an out-of-scope arm. The script stays in the tree and is available if Sinhala ever restarts. WAVs gitignored; LFS decision still open. |
| 1 — Streaming transcription | **Done** | Voice-tested; lag inside the 2–5 s target. |
| 2 — Post-consultation note | **Done, real-audio validation begun** | Full pipeline + review UI + eval. The 2026-07-12 recordings ran through the full live→Stop→review pipeline as they were made (five consultations; three approved, two awaiting review as of that date) — diarisation and notes held up in use; the formal check against marking schemes + a real-audio section in the note-quality eval are still to do. |
| 3 — Live CDS | **Done** | Including urgency escalation, evaluated 8/9 with one documented boundary case (see docket). |
| 4 — RAG guidelines | **Done; corpus expanded 2026-07-24** | 9/9 eval (re-run after expansion, still 9/9); fidelity spot-check logged. Corpus grew 7 → 38 sources (1301 chunks) to cover common primary-care presentations for the public demo — see the corpus section below. |
| 5 — Sinhala | **CLOSED 2026-07-25 with a negative result; Sinhala out of scope for v1** | Benchmark (2026-07-10): 9 candidates on two OpenSLR sets, best `seniruk/whisper-small-si` CER 0.035. Pre-registered recordings eval executed on the real `03_diabetes_review_si` recording: every model degrades massively (seniruk 0.035 → 0.504; best overall xlsr-sinhala CTC 0.462) and **every Sinhala fine-tune transliterated or lost all 106 English terms** (mechanical recall 0). Off-the-shelf landscape now exhausted (post-hoc screen of remaining HF repos found only duplicates). **Step 6 adjudication completed 2026-07-25** (owner, binary measure unchanged): seniruk-small recovers clinically usable content for 7 of 12 curated terms vs 0 (rrashmini-large-v2) and 1 (xlsr-sinhala) — **the ranking reverses, seniruk-small over xlsr despite xlsr's better CER**, because clinical survival is what matters here. Four terms — `HbA1c`, `losartan`, `atorvastatin`, `neuropathy` — survive in **no** model. Verdict unchanged: no off-the-shelf model is usable for code-switched clinical Sinhala. **Fine-tune NOT PROCEEDING by owner decision 2026-07-25** (eight sign-offs deliberately not sought); Consultation AI is **English-only for v1** and Sinhala is out of scope, not postponed — see the decision header in `evals/2026-07-17_finetune_plan.md` and PROJECT_PLAN.md §§4, 7. All Sinhala research artifacts are retained deliberately (scripts, recording, reference, harness, eval records) — they are the pre-registered negative result. See `evals/2026-07-12_sinhala_asr_recordings_eval.md` § Step 6. |
| 6 — Users/roles/front desk | **Core built and manually verified** | Auth (scrypt + signed-cookie sessions), three tabs per the agreed structure, walk-in queue, server-side RBAC (receptionist 403s on all clinical content — automated tests pass), audit log, approved-consultations read-only, full loop wired queue→live→review→approve→archive. **Verified 2026-07-10 (project owner, in-browser):** two-role click-through of the full loop, plus adversarial checks — receptionist hitting clinical URLs directly (403 confirmed), doctor attempting queue add/reorder (403 confirmed), edit attempts on an approved consultation (409 / read-only UI confirmed). **Design pass done 2026-07-24** (Heidi-inspired light theme, whole app — see the design-pass section) along with **strict own-consultations doctor scoping** and the new **referral letters** feature. Remaining build work: **NONE — done.** Docker packaging and demo script authored 2026-08-04 (slice 5, per DOCKER_DEMO_SPEC.md) and the in-container validation discharged the same day (slice 6: image builds, in-container suite green forward and reverse, CUDA audio path proven inside the container, §1.7 restart re-enqueue verified — see the slice-6 entry in the Phase 2 security section). **Post-verification additions (2026-07-10, browser-testing findings):** doctor walk-in action (`queue.walk_in_started`); server-sourced patient banner on the live page (wrong-patient prevention — identity never read from URL text); queue-entry lifecycle for abandoned sessions — Resume, Close-without-consultation (`queue.cancelled`, receptionist too), and a concurrency guard so a doctor can't stack a second live consultation over an active one. |
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
app/face.py            Phase 7b: affect/attention drive + per-muscle policy
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
form (the owner's doctor account carries a bare surname, the second
doctor account a first name, the invited outside clinician's demo
account a full name); and the admin account has display name
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
  now on are logged amendments. One TODO it created was assigned to the
  owner + Claude Cowork: the one-page open/closed question-classification
  rule (metric 5). **DISCHARGED 2026-07-30** — the rule was drafted by
  Cowork + owner, approved by the owner 2026-07-30, and is committed
  FROZEN at the repo root as `OPEN_CLOSED_RULE.md`, an annex to the
  pre-registration; changes from now on are logged amendments.

## Phase 7b — the drive rewrite (2026-08-01)

**Consultation 463: the owner watched a curious face at the start turn
into a smiling face, and it stayed smiling while the patient described
chest pain and a family history of heart disease.** The drive between
consultation events and the vendored engine has been replaced. The
diagnosis, the decisions and every number are in
`PHASE_7B_FACE_DRIVE_SPEC.md`, committed before the code; this section
records what a future reader needs to know without re-reading it.

- **The dominant input was a metronome.** `on_patient_audio()` fired from
  the live frame loop on every PCM frame that arrived while the system
  was not speaking. There was no voice-activity test and no speaker test
  on that path, so the call did not mean *the patient is talking* — it
  meant *the microphone is on*, which is true for the whole
  consultation. Rate-limited to one injection per 2 s, it was a steady
  tick for as long as the session ran. **Measured offline against the
  real driver and the real engine** (spec § 1): dopamine 0.40 → 0.91 over
  15 simulated minutes, the smile muscle 0.31 → 0.61 — and **0.31 → 0.56
  with the affect hint disabled entirely**. Roughly five sixths of what
  the owner watched was the metronome, not the patient. The affect hint
  could not compete and pointed the wrong way: `distressed` moved the
  smile by about **+0.008**, upward.
- **Attention moved from dopamine to adrenaline.** In the vendored
  `FACE_WEIGHTS` dopamine is the largest term in the smile (0.40 in
  `lip_corner_pull`, 0.45 in `cheek_raise`); alertness lives in
  adrenaline (`eyelid_upper_raise` 0.55, `brow_outer_raise` 0.50). Using
  dopamine for *someone is talking* was the category error, and the
  consequence was that the longer the consultation ran, the harder the
  face smiled. The *curious* opening face is the same mechanism in
  reverse — `brow_inner_raise` reads the dopamine deficit below baseline,
  which exists only before any has accumulated.
- **Nothing integrates any more.** Affect is a STATE that sets a target
  chemistry the driver ramps toward and then holds; attention is a
  bounded level in [0, 1] with an attack and a release. There is no
  accumulator, so **no repeating stimulus can push any chemical upward
  without limit and the face cannot drift with time**. This is
  structural, not a tuning choice, and it is pinned by acceptance
  criterion C1 in `tests/test_face_drive.py`: the face at 15 minutes
  equals the face at 2 minutes to within 0.01 on every muscle, affect
  held and the room active throughout. The practical consequence is worth
  knowing: if `FACE_ACTIVITY_RMS` is set wrongly and the room reads as
  permanently active, the failure is cosmetic — the eyes sit slightly
  open — not a return of the 463 defect.
- **Speech activity counts BOTH speakers, and our own voice
  (owner decision, 2026-08-01).** `on_speech_activity()` replaces
  `on_patient_audio()` and fires when a frame's RMS clears the activity
  floor — the same floor `live.html` already uses for the silence
  nudge's detector, so the two surfaces cannot disagree about when the
  room is quiet. The face is a listening presence for the patient, and it
  is at least as relevant while the doctor — or Alba — is talking, which
  is also what Stage 7c will need. The two `on_system_speech_*` call
  sites are kept as aliases for speech activity: the face stays attentive
  during playback even if the microphone is quiet.
  `on_consultation_started()` is now a no-op and its call site is kept
  deliberately.
- **The engine's decay, cross-interactions and saturation are
  deliberately unused, and that changes what kindalive is in this
  project.** Their time constants (20 min to 4 h) are an order of
  magnitude too slow for a 15-minute consultation — the root of the
  defect, and not tunable away without editing vendored files. What is
  still used is the `FACE_WEIGHTS` projection, the renderer and the
  config; the engine is a state holder our layer overwrites each tick.
  **After this change kindalive supplies the projection, the renderer and
  the config, and the clinical behaviour lives in our targets, in this
  repository, where it can be reviewed.** That is a loss of emergent
  plausibility and a gain in reviewability, and on a clinical surface the
  trade is the right way round. `vendor/` is untouched at its pinned
  commit `a29bcf7`; `NOTICE` needs no change.
- **The jaw is capped at rest in BOTH modes** (`JAW_REST_CAP` 0.08).
  `face3d.js` draws an open mouth above `jaw_open` 0.10 and layers the
  syllable-rate speaking flap on top, and kindalive opens the jaw for
  excitement — so at any real dopamine level a resting face looked about
  to speak. Not an expression cap: `jaw_open` carries no emotional
  information the smile and brow do not already carry. Note the clinical
  arm's own resting jaw is 0.12, above the render threshold, so the cap
  is what closes the resting mouth there.
- **`brow_inner_raise` and `lip_corner_depress` move from PINNED to
  BANDED in the clinical arm, and the band becomes two-sided
  (`neutral ± band`).** With the drive corrected, the old pin list left
  that arm able to show warmth but not concern — the original defect in
  miniature. **OWNER DECISION, and it is one line to revert**: the two
  muscle names in `BANDED_MUSCLES` in `app/face.py`. It affects the
  comparison arm only; `full` remains the default and is what runs live.
- **Every on-toggle now audits `drive` (`FACE_DRIVE_VERSION`) beside
  `mode`,** in `face.toggled` and through it in the `face.arms` summary,
  so a mock-patient session can be tied to the drive it ran and not only
  to the arm. Both drives are "full" as far as `mode` is concerned, which
  is exactly why this was needed.
- **Unchanged, and deliberately so:** face OFF is still a first-class
  state (no driver, no `face_state` traffic, card absent from the DOM —
  the control arm of the CARE study); **the urgency alarm is still not
  wired to the face**, guarded by a test over the whole module surface;
  and the drive is still deterministic — no model call, no randomness, no
  GPU, injectable clock.
- **Still open:** the mock-patient feedback round remains the thing that
  decides whether these expressions read correctly to a person — every
  number in `AFFECT_TARGETS` is a first calibration against a written
  brief, not a validated setting. `FACE_ACTIVITY_RMS` wants a real room
  recording. CDS assessments are still not persisted, so a past
  consultation cannot be replayed through the face with its real affect
  timeline (spec § 6).
- **THE BROW IS EFFECTIVELY CONCERN-ONLY: five of the seven affects draw
  no eyebrows at all**, `neutral` among them. `face3d.js` needs
  `brow_lower` > 0.18, `brow_inner_raise` > 0.28 or `brow_outer_raise` >
  0.4 before it draws the bar, and only `low` and `distressed` clear any
  of those. C6's anger cap holds `brow_lower` at ≤ 0.15, so that route is
  closed by design and the two constraints pull against each other.
  Found by chasing a room report that the face "looked confused" —
  **the table and the reasoning are in the consultation 468 section
  below**, and it is calibration, so it is the owner's call.

### Consultation 468: BBC News in the room — the gate refused, and the face read as confused

**First room check of the 2026-08-01 build** (restarted 21:22; this ran
21:23–21:25). The owner recorded a consultation with BBC News playing in
the background. 99.2 s of audio, face auto-on at the disclosure, drive
`2026-08-01d`, mode `full`.

**The gate refused, and approval was blocked. That is the safety
behaviour working.** Duration-weighted mean ASR confidence **0.549**
against the 0.60 refuse threshold → `quality_outcome = refused`, status
`unreliable_transcript`, and `POST /api/consultations/468/approve`
returned **409**. For scale, genuine consultations in this database run
**0.65–0.84**; the only other refusal, 460, sat at 0.485. Four refusals
in 24 gated consultations to date.

**Two honest caveats about that win, because it was narrower than it
looks:**

- **Only S2 fired.** S1 correctly detected English at p=0.96 across all
  three windows — the audio *was* English, just not a consultation. S3
  and S4 were clean. So a news bulletin is caught by ASR confidence
  alone, and the margin was **0.05**. Clearer TV audio, or a quieter
  room, could plausibly clear 0.60 and be drafted from.
- **Nothing objected to who was speaking.** The declared speaker count
  was 2, diarisation used 2, and `single_voice_detected` was false — so
  two newsreaders were labelled **Doctor** and **Patient**, alternating,
  and every count-based check was satisfied. The declaration confirms
  *how many* voices, never *whose*. The turns read: "the Venezuelan
  government under first Chavez and Nicolás Maduro", "Give us a sense of
  the drug cartels that now operate in Colombia".

**The face was at `neutral` for the entire consultation** — five affect
verdicts, `neutral`, `changed=no` throughout. That is the correct answer:
a news bulletin carries no patient feeling to report, and the affect call
did not invent one from a garbled transcript. **So what the owner read as
"confused" is our neutral face itself**, seen in a room for the first
time since the 2026-08-01b reset to kindalive's species defaults.

**Why it reads that way, measured:**

| | new neutral | old neutral |
|---|---|---|
| `eyelid_upper_raise` | 0.152 | 0.230 |
| `brow_outer_raise` | 0.145 | 0.200 |
| `lip_pucker` (warmth) | 0.120 | 0.201 |
| `lip_press` | 0.195 | 0.104 |
| `nose_wrinkle` | 0.107 | 0.072 |

The borrowed resting chemistry has **lower adrenaline** (0.10 vs 0.20 —
narrower eyes, flatter outer brow), **less oxytocin** (0.20 vs 0.34 —
less warmth) and **six times the testosterone** (0.30 vs 0.05, the
species default), which is what lifts `lip_press` and `nose_wrinkle`.
Every value is inside its C6 cap; nothing is broken. It is simply a
flatter, narrower-eyed, more pressed face than the one it replaced.

**And the finding that matters most, which 468 surfaced by accident: the
face has no eyebrows at all in five of the seven affects.** `face3d.js`
draws the brow bar only when `brow_lower > 0.18`, `brow_inner_raise >
0.28` or `brow_outer_raise > 0.4`:

| affect | brow_lower | brow_inner | brow_outer | bar drawn |
|---|---|---|---|---|
| happy | 0.000 | 0.000 | 0.270 | no |
| positive | 0.000 | 0.031 | 0.252 | no |
| neutral | 0.085 | 0.040 | 0.145 | **no** |
| anxious | 0.095 | 0.141 | 0.216 | no |
| low | 0.122 | 0.302 | 0.118 | yes |
| distressed | 0.116 | 0.298 | 0.107 | yes |
| angry | 0.004 | 0.117 | 0.134 | no |

**The brow is effectively a concern-only feature**, and `neutral` — where
most of a consultation sits — is a browless face with the narrowest eyes
of any state. Browless plus narrow eyes plus a faint mouth curve is a
fair description of "confused". C6's anger caps and the brow threshold
are pulling against each other: the caps hold `brow_lower` under 0.15,
and the renderer wants 0.18 before it draws anything at all.

**All of this is calibration, and it is the owner's call.** Options, none
taken: raise `neutral`'s adrenaline and oxytocin back toward the old
values while keeping the rest of the species defaults; lift
`brow_outer_raise` across the calm states toward the renderer's 0.4; or
accept it and let the mock-patient round decide, which is what that round
is for. **`face3d.js` is vendored and must not be edited** — the fix, if
there is one, is in `AFFECT_TARGETS`. Nothing was changed in response to
this consultation.

### Consultation 467: a NOW question asked of a WHOLE-CONSULTATION document

**The patient opened with good news — an all-clear after colon cancer
surgery — and turned sad halfway through**, talking about his wife's
rheumatoid arthritis, her pain, and whether she needed antidepressants.
His words: *there's a bit of sadness in the story*, *she's quite
miserable*, *I'm sad about that*.

**The verdicts were: happy at 34 s, neutral at 55 s, happy at 89 s, happy
at 116 s, happy at 160 s.** The last of those was judged on a transcript
that already contained "I'm sad about that". (Visible at all because of
the `PATIENT_AFFECT` log — this is the second consultation the log has
explained.)

**Two causes, both addressed:**

1. **The call receives the whole transcript from zero seconds and has no
   reason to weight the last minute above the first**, so it summarised a
   document dominated by the cancer all-clear instead of reporting the
   present moment. Splitting the call out (section below) fixed *which
   prompt* asks the question; it did not make the question about *now*.
2. **The sadness was about his wife.** A model asked how the PATIENT
   feels can reason that the patient's own news is good — which is
   defensible, and wrong for this purpose.

**The fix, in two halves.**

- **`AFFECT_PROMPT` asks a present-moment question.** How the patient
  feels RIGHT NOW, in what they have just said, not across the
  consultation as a whole; earlier parts are context only, because a
  patient can arrive delighted and turn sad or arrive frightened and be
  reassured; and **feelings about other people count — a patient sad
  about a family member's illness is sad**. The seven values and their
  one-line descriptions are unchanged, and the guard (*judge the person,
  not how serious their illness is*) stays verbatim and stays last.
- **The user message carries a recency window** (`affect_message` in
  `app/cds.py`): the whole transcript first, as before, then the last
  `AFFECT_RECENT_TURNS` turns repeated in a labelled block **at the
  end**, because the end of the message is what the model attends to
  most, so the thing being judged goes last. Turns come from the
  transcript's own line structure, not a character count. A transcript
  shorter than the window is sent once rather than repeated twice.
  Nothing else about the call changed: no previous assessment, nothing
  clinical in its context, still fail-soft to neutral.

**`AFFECT_RECENT_TURNS = 4` IS A GUESS.** Nothing has been measured. Four
is a plausible present moment for a transcript that commits roughly
sentence-sized turns, and it wants calibrating against real
consultations — 467 is the first one with a known emotional turn to
calibrate against, and its `PATIENT_AFFECT` log is the material.

**Bench check on a 467-shaped transcript** (the all-clear opening, the
sad turn about the wife, eight turns): the affect call returns **`low`**,
with or without the recency block. Both halves of the fix point the same
way and the prompt rewrite alone was enough on this example — which is
worth knowing, because it means the window's value is not yet doing
observable work and is exactly the kind of thing calibration should test.
A scripted eight-turn transcript is not a room result; the real check is
the next live consultation with an emotional turn in it.

### The affect judgement gets its own model call (2026-08-01)

**Three consultations — 464, 465 and 466 — returned `neutral` on every
pass, including one where the pain radiated to the jaw.** Rewriting the
question (the section below) was not enough on its own.

**What was ruled out first, both checked in the code and both already
correct:**

- **Anchoring on its own previous answer.** It cannot: `patient_affect`
  is never passed back. `CDSEngine.update` builds `prev_text` from
  `differentials`, `questions_to_ask` and `signs_to_check` only, so the
  affect judgement starts fresh every pass.
- **A truncated transcript.** It sees all of it. The user message is the
  whole transcript from zero seconds on every pass, not a window.

**What it did not have was a question it could answer plainly.** It was
item 4 of a six-hundred-word clinical prompt that spends most of its
words telling the model to be conservative, not to churn the list, and to
prefer a short list over speculation.

**This repository has already learned this lesson once, and the record of
it is the module docstring of `app/cds.py`:** the urgency check is a
separate call with its own short prompt and schema because evaluation
showed the combined call failed *in both directions* — the previous
assessment anchored the alarm, and the alarm competed with the revision
task. Affect was the same mistake repeated. **Owner decision 2026-08-01:
split it out, and make the prompt plain.**

- **`AFFECT_PROMPT` and `AFFECT_SCHEMA`** sit beside the urgency pair and
  follow its shape: one required property, the seven-value enum, and a
  short prompt with one job. The last line — *judge the person, not how
  serious their illness is* — is the guard, with a comment above the
  constant saying so: without it the field becomes a proxy for clinical
  urgency and **puts the alarm on the face by a back door**.
- **It takes the transcript and nothing else.** No previous answer, no
  differentials, no urgency verdict, nothing clinical in its context — a
  fresh judgement of the whole consultation every pass.
- **It runs LAST and it is FAIL-SOFT.** A failure logs a warning and
  falls back to `neutral`. **An affect failure must never cost the doctor
  the differentials, the questions or the alarm** — the face is a comfort
  feature and the rest of the pass is the clinical output. Asserted by
  `tests/test_cds.py::test_an_affect_failure_cannot_cost_the_clinical_output`.
- **The returned shape is unchanged.** `patient_affect` merges in at the
  top level exactly where it sat before, so `app/main.py` and the
  `PATIENT_AFFECT` log line needed no change at all and were not touched.
  The old path is gone: the field is out of `ASSESSMENT_SCHEMA` and the
  assessment prompt no longer mentions affect anywhere.

**Timing, measured on this machine over five passes of
`01_chest_pain_en` at growing transcript lengths (303 → 1408 chars), one
warm MedGemma serving all three calls:** assessment **12.22 s** (10.58–
13.59), urgency **4.19 s** (3.66–5.03), affect **0.85 s** (0.80–0.90),
whole pass **17.26 s**. **The third call adds under a second — about 5%
of a pass** — because it emits a single enum token, and its cost does not
grow with transcript length the way the assessment's does. Not logged in
the code: nothing in the app times individual calls today (the eval
harness times whole updates), and this did not seem worth inventing a
place for.

**And it works on the case that prompted it:** the same chest-pain script
that produced `neutral` under the old design returned **`anxious` on all
five passes**. That is a bench measurement on a scripted consultation,
not a room result — the real check is the next live consultation.

**The CDS harness debt now stands against BOTH the seven-value enum and
this split.** It has not been re-run since the five-value, single-call
build. One run is owed, once the enum and the call structure have
stopped changing.

### Two new affect values: happy and angry (2026-08-01d)

**Owner decisions, both 2026-08-01.** The enum goes from five values to
seven — happy, positive, neutral, low, anxious, distressed, angry — in
`ASSESSMENT_SCHEMA`, in `AFFECT_INSTRUCTION` and in `AFFECT_TARGETS`.
`FACE_DRIVE_VERSION` is `2026-08-01d`. The five existing chemistries are
untouched, verified field by field.

- **happy** — the old list named one positive value against three
  negative ones, and there was nowhere for real delight to go: a patient
  given the all-clear after a cancer scare, one who has come partly to
  enjoy the visit, a joke that lands. `positive` stays as the milder step
  below it. **The happy mouth stays CLOSED like every other state**:
  `face3d.js` gives arc eyes above a mouth curve of 0.34, and deep curve
  plus arc eyes reads unmistakably as delight in a dot-matrix face,
  whereas an open mouth would read as *about to speak* in a room where
  this assistant can actually speak. `JAW_REST_CAP` is not lifted for it.
- **angry** — patients are angry often enough (at the wait, at being
  passed around, at not being believed, at being in pain) that with no
  token for it the verdict landed as neutral. In the prompt it is judged
  like every other value, on how the patient FEELS, and explicitly **not**
  a judgement about whether the anger is justified.

**The design rule the angry face encodes, because it is the clearest case
of the not-a-mirror principle:** an angry face at an angry patient is the
worst answer available; **a smile is the second worst, because it reads
as dismissal**; and a blank face reads as stonewalling. So the face holds
**neutral's steadiness with the smile removed and the warmth raised** —
level mouth, open unnarrowed eyes, no brow furrow, more warmth than
neutral carries.

**`angry` is deliberately OUTSIDE the C2 valence ladder.** Anger is a
different axis, not a darker sadness, so ordering it against happy →
distressed would be meaningless. **C13 covers it instead** (mouth flatter
than neutral, warmth higher, `brow_lower` ≤ 0.05, no eye narrowing, no
concern brow), and it is inside C6 and C12 like every other value. 14
criteria, 35 parametrised cases.

**The CDS harness has NOT been re-run against this enum change, and one
is owed.** It is deliberately deferred until the enum has stopped
changing, and is being sequenced separately. The last run is the one in
the section below, against the five-value enum.

### The affect hint asks the wrong question — 465, and the new one (2026-08-01)

**Consultation 465 proved the plumbing works and the question was
wrong.** MedGemma emitted `patient_affect` twice and said **neutral both
times**, while the patient described two weeks of exertional central
chest pain, 20 cigarettes a day, and a father who had a heart attack in
his mid-40s. (That the verdicts were visible at all is the
`PATIENT_AFFECT` log added the same day — see the section below.)

**Neutral was the correct answer to the question that was asked, and that
is the point.** The old paragraph asked for the patient's *outward
emotional presentation* — "how they seem right now, their manner, not
their diagnosis" — and told the model to fall back to `neutral` when
unsure or when there was too little to go on. **The man sounded
composed.** A model reporting manner, with a retreat to neutral
available, had no way to reach any other answer. The fault was in the
question.

**Owner decision, 2026-08-01: the field is now MedGemma's best inference
of how the patient FEELS at that point in time** — the inside, not the
outside. The rewritten paragraph (`AFFECT_INSTRUCTION` in `app/cds.py`,
lifted into its own constant so the guard below cannot be lost in an
edit) asks it to read both how the patient speaks *and* what they are
describing, because someone can sound perfectly composed and still be
frightened, and **a patient who volunteers a family history unprompted is
usually telling you what they are afraid of**. The retreat to neutral is
gone: neutral now means a patient who genuinely seems settled, not one
the model is unsure about, and it is told to commit to its best
inference. The five values are unchanged.

- **The guard, and why it is load-bearing: judge the PERSON, not the
  seriousness of the diagnosis.** Without that sentence the field becomes
  a proxy for clinical urgency — and **the urgency alarm is deliberately
  kept off the face** (the reason is in `app/face.py`'s module docstring:
  an alarmed face would tell the patient something the doctor has not
  decided yet). A frightening differential in someone taking it in their
  stride is not "distressed". A comment above the constant says exactly
  this, so nobody deletes the line as redundant.
- **`patient_affect` is now REQUIRED** in `ASSESSMENT_SCHEMA`. It was
  deliberately optional with absent meaning neutral, but that made an
  absent field and a neutral verdict indistinguishable in the log and in
  the face alike — a model that skipped the question looked exactly like
  one that answered "settled". `tests/test_cds.py` and
  `tests/test_cds_first_call.py` both subtracted the field out of their
  set assertions; they now require it and check it is one of the five
  values. Both run against the live model and pass.
- **`app/face.py` was NOT touched.** The map from patient state to
  expression is already a listener's response rather than a mirror, and
  it stays exactly as calibrated. This was a change to the question, not
  to the answer.

**Harness re-run (`scripts/evaluate_urgency.py`), because this edits the
prompt that also produces the differentials, questions, signs and urgency
escalation.** Result: **9/10, unchanged** — the one FAIL is script-02
dengue, the docket's documented boundary case, which also failed at
baseline. **Fire/silence, first-fire turn, first-fire actions, cleared-
at-end and update counts are IDENTICAL to the stored baseline on all ten
scripts.** What moved is differential stability, both ways
(01 8/9→9/9, 06 7/9→9/9, 08 4/7→6/7 against 04 7/7→6/7, 09 5/6→4/6,
10 8/9→7/9; aggregate 70/81→72/81, and 62/72→65/72 on the nine common
scripts session 4 measured). **One movement is worth an owner's eye: on
09_septic_child the leading final differential changed from "Sepsis" to
"Severe Dengue"** — the alarm still fired at turn 4 with "Hospital
admission" and still cleared, so the safety behaviour is unchanged, but
the label is not the one the script was written around. Reported, not
adjusted. `evals/urgency_results.json` was left at the committed
baseline: whether to re-baseline it is the owner's call. **The run itself
is kept, unmodified, as
`evals/urgency_results_2026-08-01_affect_prompt.json`** — a second file,
not a replacement, so the baseline every comparison is made against stays
the one session 4 wrote. Read it as the state of `16d60fc`: the FEELS
prompt rewrite and the required field, but BEFORE the seven-value enum
and before the affect call was split out — so it is not a baseline for
the current build either. The harness debt is still owed.

### The affect log, and the neutral reset (2026-08-01b)

**The affect verdict is now logged, one line per assessment.** Nothing
anywhere recorded what MedGemma sends in `patient_affect` — not
persisted, not audited, not logged — so **consultation 464 could not be
explained**, and neither could the next one. `app/main.py` now emits, at
the point a completed assessment is read:

```
PATIENT_AFFECT session=<id> at=<audio_s>s value=<affect|ABSENT> changed=<first|yes|no>
```

Three properties are deliberate. It sits **outside the
`entry["face"] is not None` guard**, because face-off is a study arm and
the affect stream is wanted from it too. It logs **every** assessment,
not only changes — a repeated verdict is evidence. And it writes the
literal word **`ABSENT`** when the key is missing, because
`patient_affect` is optional and not in the CDS schema's `required`
list, so a model that omits it otherwise looks identical to one that
judges the patient neutral; that distinction is the whole reason the log
exists. **It is a debugging instrument** — no table, no migration, no
audit row. The durable version (affect persisted with the assessment, so
a consultation can be replayed through the face) is still the separate
job in spec § 6.

**Neutral is now kindalive's own resting chemistry (owner decision,
2026-08-01).** `AFFECT_TARGETS["neutral"]` is the vendored
`SPECIES_DEFAULTS`, untouched, and `PRESET_BASELINES` matches it, so the
deficit-driven muscles measure from kindalive's resting point instead of
one invented here. The reasoning is worth keeping: **most of a
consultation sits at neutral, and that state should be borrowed rather
than designed.** The other four affects moved only as far as keeping the
ladder ordered around it. `FACE_DRIVE_VERSION` is `2026-08-01b`, so the
`face.toggled` and `face.arms` rows separate the two builds. Two
criteria changed with it, both recorded in the spec's § 3 amendment:
C2/C3 now test the **mouth curve** (`lip_corner_pull` minus
`lip_corner_depress`, which is what `face3d.js` actually draws) and are
stricter for it, while C5's warmth floor now **exempts neutral** — an
honest relaxation, because the resting face is borrowed now, not because
the code failed to meet it.

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

**`calibrate_barge_in.py --since YYYY-MM-DD`** (built the same session):
limits every per-device analysis to readings from that date onward, so
the current room configuration is evaluated without the device's history
polluting the spread — the intended cut after any change of volume,
position, or capture constraints. Excluded readings are counted and
dated in the output; a narrowed window is never silent. Default remains
all readings. Live run with `--since 2026-07-29`: the NVIDIA device
still read spread ×16.5 — the collapse was *inside* the window, which is
the finding above confirmed by the tool built to see it.

### THE CAPTURE-CHAIN DECISION (owner, 2026-07-30): EC OFF on the main stream

**Option B of the constraints report, decided by the owner 2026-07-30.**
The main capture stream — the one feeding the meter, the transcriber and
the stored recording — now requests `echoCancellation: false`, with
`noiseSuppression: true` and `autoGainControl: true` pinned EXPLICITLY
at their previously-effective values, so nothing on that stream runs on
a browser default any more (AGC in particular was never chosen by
anyone until now; choosing the status quo is still a choice, and it is
now written down). The single source is `CAPTURE_CHAIN` in `live.html`,
which builds the constraints AND is recorded with every sound-check
reading. The barge-in detector stream is untouched (EC on, NS on, AGC
off, all explicit already). Full raw capture — NS and AGC off too,
option A — is **explicitly deferred to a planned v2 campaign**, because
it invalidates every RMS calibration at once.

**Why:** the echo canceller was deleting the machine's own voice from
the recording — a faithful record of the room should contain it; she was
in the room — and made loopback measurement impossible (an adaptive
filter whose job is to remove exactly the measured signal; the ×13
collapse above). NS and AGC stay because every RMS calibration in the
project was derived through them.

**The epoch line, prominently: every recording made before 2026-07-30
went through Chrome's EC+NS+AGC chain. Their bytes remain the project's
evidence set, unchanged, and their RMS numbers are calibrations OF THAT
CHAIN. Recordings made after this change are EC-free (NS+AGC still on).
The evidence rows — 445, 446–448, 450, #70 — are unaffected in status:
nothing about them is voided, repaired or reinterpreted by this
decision.** Pre-change sound-check rows carry no chain record and the
calibration report marks them incomparable; post-change rows carry
`chain: {ec, ns, agc}`.

**Expected side effect, noted rather than "fixed": the mic level meter
now moves while the machine speaks.** That is honest — the room IS loud
while she talks — and the meter's one-capture invariant is exactly why
it must show it. Do not re-point the meter or filter its display to
make it sit still during playback; a meter that disagrees with what the
server hears is the fault, not the movement.

### Threshold design under the split chains (2026-07-30, REPORT ONLY)

With EC off on the main stream (the decision above),
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

### Barge-in stage 2 (2026-07-30): the dual measurement, built

The owner approved the stage-2 recommendation the same day the room
data proved the need: on the new ec-off chain the loopback is finally
stable (spread ×2.0 over five readings) and D5 side 1 reads predicted
MET — but side 2 fails exactly as the report above anticipated, raw
loopback 0.30–0.58 RMS against quiet speech at 0.056, a tenfold gap no
raw-derived threshold can bridge. Six commits this session; no
dependency changes.

- **Spec Part 10 carries a dated, owner-approved amendment** (appended
  verbatim, superseding nothing silently): the sound check measures
  BOTH streams during one playback. The main stream (EC off) keeps
  giving the true acoustic loopback — still what the doctor-facing
  result reports, because "can the room hear the machine" is a question
  about the room, not about a filter. The detector stream (EC on) gives
  the canceller's RESIDUAL.
- **Implementation:** the check opens the detector-constraints stream
  through the same single acquisition function the detector uses
  (`openDetectorStream` — still exactly two `getUserMedia` calls on the
  page), **before playback starts**, so the unconverged first window —
  the false-stop risk — is captured; it closes on every exit path. The
  same `speech.sound_check` row now carries `residual` (peak, mean, a
  250 ms-window convergence series) or `residual_unavailable` with the
  reason — a missing residual is visible, never a silent zero. The
  doctor-facing message is unchanged; the check stays disabled while
  recording.
- **The threshold now scales by the residual** — the echo the detector
  stream actually hears — with the raw loopback retained as a sanity
  upper bound: `speech.barge_in_scale` clamps a physically-wrong
  residual (> raw) to the raw figure and the server audits
  `speech.barge_in_anomaly`. Rows without a residual fall back to the
  raw scale, which is conservative (its failure direction is a miss —
  hard mute). **`BARGE_IN_ENABLED` remains FALSE; nothing this session
  flips it.**
- **The calibration report** now takes verdicts from residual-bearing
  readings only, grouped (device, chain, measurement mode) — raw-only
  rows, including the five ec-off readings of 2026-07-29/30, are listed,
  marked "no residual — predates the dual measurement", never pooled,
  and still feed the raw-acoustics ratio recommendation. Each dual
  reading gets a convergence line (first window vs settled, and whether
  the first window ALONE would have crossed the threshold — the case
  the sustain requirement exists to cover). The footer no longer claims
  sufficiency when no residual-bearing readings exist (caught against
  the live data, where that was briefly true of every row).

**What the owner runs next:** after the restart, **five fresh
sound-check readings** (same discipline: door shut, patient-level
volume, untouched between taps) on the room's output device — each now
carries the detector-stream residual automatically — then
`uv run python scripts/calibrate_barge_in.py` again. Those five are the
first readings that can produce a residual-based verdict; if both sides
read predicted met, the next step is the D5 scripted room run.

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

## Session 2026-07-30 (owner away): rule frozen, raw view built, ASR experiment

Three pieces of owner-input-free work, all decisions previously made and
recorded. Four commits; no dependency changes.

**1. `OPEN_CLOSED_RULE.md` is committed FROZEN** at the repo root —
copied byte-for-byte from the owner's draft with exactly one edit (the
status blockquote: DRAFT → FROZEN, approved by the owner 2026-07-30).
It is the annex to `PHASE_7C_EVAL_PREREG.md` metric 5; changes from now
on are logged amendments. The prereg's pending TODO is discharged (see
the 7b session 5 section).

**2. The raw-transcript view is BUILT** (`RAW_TRANSCRIPT_VIEW_SPEC.md`,
approved 2026-07-28 with all four decisions; the owner's 2026-07-30
persistence decision supersedes spec §2's out-of-scope for
invariant-dropped segments — they are stored FLAGGED and shown struck
through, because the invariant has eaten transcript before and the view
exists to make such layers visible):

- **New table `raw_segment`** (`app/raw_segments.py`, in
  `schema.ensure_all()`'s ordering; cascades on purge): every
  pre-invariant WhisperX segment, cluster and confidence derived exactly
  as the merge derives them, written beside `save_turns` and BEFORE the
  quality gate — a refused consultation's raw layer is stored too.
  Written once: a re-run of finalisation cannot overwrite the first
  record. ~sentence-sized rows, tens of KB per consultation.
- **Read from STORAGE, never rebuilt** — the endpoint
  (`GET /api/consultations/{cid}/raw-transcript`, same scoping as the
  transcript, available on approved consultations per D3) works with no
  transcriber installed at all, asserted by test. WhisperX is not
  deterministic; a rebuilt view would show a consultation that never
  existed. **Consultations finalised before 2026-07-30 have no stored
  segments and the view says so plainly** — it never falls back to
  re-running anything.
- **Opening is AUDITED** (`transcript.raw_viewed`, once per open,
  including opens that find nothing) — the research signal is whether
  checking happens; together with citation-open records it feeds
  research question 1. The client fetches once per page visit; toggling
  back and forth re-uses that fetch.
- **The review-page toggle** ("Show what was heard" / "Show diarised
  transcript") sits above the transcript pane it acts on (D1), diarised
  by default (D2), not on the live page (D4). The rendering groups raw
  segments under the diarised turn that absorbed them, so a merge that
  joined minutes into one turn shows as one bordered block — the 445/66
  shape at a glance. Display only: no turn numbers, no citation
  targets, no edit path; corrections stay on the diarised view. All
  pinned in `tests/test_raw_transcript.py`.

**3. The ASR-stack experiment** (owner-approved question, parked
2026-07-28): could the final pass run on faster-whisper large-v3 alone,
dropping WhisperX, now the project is English-only?
`scripts/evaluate_asr_stack.py` (offline, read-only, MedGemma unloaded
first, arms strictly sequential) ran both stacks on 16 recordings —
66–70 plus eleven 7a-era WAVs; the four FLAC-archived ones named as
skipped. Raw numbers in `evals/asr_stack_results.json`. The reading:

- **Recognition is competitive.** Scripted-English WER: WhisperX
  0.037/0.048/0.099/0.039 vs faster-whisper 0.161/0.061/0.118/0.035 —
  within ~2 pp on three of four, one 4× outlier (66). 70 (code-switched
  Sinhala) is known-bad in both arms symmetrically (0.96/0.95).
- **The losses are structural, not recognition.** (1) UNDER-SEGMENTATION:
  without the alignment pass, faster-whisper's segment-level timestamps
  merge into coarser turns (13 vs 22 stored on 66, 11 vs 19 on 67) —
  citation granularity, which the note depends on, degrades. (2)
  BOUNDARY DRIFT: 0.4–3.2 s on scripted audio, 5–53 s on 7a-era room
  audio. (3) **THE S2 GATE BREAKS**: arm (b)'s exp(avg_logprob)
  confidence is a different measure that collapses on real room audio —
  448 reads 0.519 and 449 reads 0.499 against the calibrated 0.60
  refuse threshold, so consultations that passed in production would be
  refused. Adopting arm (b) means recalibrating S2 (and the flag tier)
  from scratch on new data.
- **Honest caveats.** Arm (a)'s near-perfect drift/agreement against the
  stored turns is partly CIRCULAR — the stored turns came from the same
  stack. And on 451/454/458/459 BOTH arms fail to reproduce the stored
  record (turn counts 12→4/13, 14→3/2, 18→2/2, 7→2/2; role agreement
  0.03–0.17) — WhisperX non-determinism plus owner corrections, which
  is fresh evidence for the raw view's read-from-storage rule and
  weakens those rows as arbitration between arms.
- **The dependency win is partial.** pyannote — the scarrier dependency
  (the 3.4 pin, the weights_only monkeypatch) — stays in both arms;
  dropping WhisperX removes only its own pins (the ctranslate2
  override's motivation, the torchcodec exclusion).
- **Recommendation (the decision is the owner's): keep WhisperX for
  v1.** The measured costs — coarser citations, boundary drift, an
  invalidated safety-gate calibration — outweigh a partial dependency
  win. If it is ever revisited, test faster-whisper with
  `word_timestamps=True` first (the middle path this experiment did not
  run) and budget the S2 recalibration.

> **CLOSED — owner decision, 2026-07-30: WhisperX stays for v1.** The
> experiment's record (`evals/asr_stack_results.json` and the reading
> above) stands as the evidence. If the question is ever reopened,
> `word_timestamps=True` is the first thing to test, per the
> recommendation. Nothing about this stack is pending.

## Session 2026-07-31 (owner away): flag tier, S1/S3 re-calibration, retrieval report

Decision-complete work, built conservatively ahead of Friday's external
collaborator session. Four commits; no dependency changes.

**1. The transcript-quality gate's FLAG tier is LIVE** (spec §11's
deferred follow-up; thresholds are the owner's recorded 2026-07-25
numbers — S2 < 0.70, S4 gap > 10 s — wired, not invented). A flagged
(not refused) transcript still gets its draft; approval 409s until the
amber acknowledge-gated banner on the review page is acknowledged
(`quality_ack_at`, audited `quality.acknowledged`) — the urgency-banner
pattern exactly, and the flag's reason joins Approve's disabled state
through `refreshApproveGate`, the SINGLE writer, with a structural test
on that property. Semantics pinned by test: refusal is never also a
flag; measured missing speech still refuses (the 2026-07-28 rule is
about refusal and stands); a long SILENT tail now reads amber instead of
nothing; the four good calibration recordings do not flag. Needs the
restart (schema: `quality_ack_at`).

**2. S1 multi-window and S3 within-segment are built, shared, and
MEASURE-ONLY** — the §11 redesigns, with the standing collapse
requirement discharged: `s1_language_windows` and `s3_repetition` in
`app/transcript_quality.py` are the ONLY implementations; `finalize.py`
and the calibration harness inject their model call and share every
decision (the last two-path signal is gone; pinned by test). A terrible
S1 fraction or a saturated S3 share still passes — acting waits on the
owner's thresholds. The re-calibration ran across ALL stored
consultations with turns (66–70 + nineteen 7a-era rows; full table in
`evals/transcript_quality_calibration.json` and the run log). **The
findings, numbers first:**

- **S1's designed metric — the expected-language FRACTION — is DEAD on
  this data: 1.00 everywhere, including #70.** Every 30 s window of the
  code-switched recording detects as English; the consultation is
  code-switched throughout, not just at its opening, so no window is
  majority-Sinhala. The §11 prediction ("English in a minority of
  windows") is falsified — recorded plainly, not tuned away.
- **What DOES separate is the MEDIAN WINDOW PROBABILITY**: the scripted
  good four sit at 0.992; #70's ten windows are all ≤ 0.926, median
  0.902; the healthiest unscripted rows sit 0.943–0.989; and the only
  rows below #70 are 445 (0.792) and 449 (0.783) — both already refused
  by the acting signals. **Candidate threshold for the owner: median
  window probability < 0.93** — catches #70, co-fires only on
  already-refused wrecks, clears every healthy row with a 0.013 margin
  to 457's 0.943. That margin is thin and the sample is one room;
  measure-only remains right.
- **S3's raw within-segment share saturates**: seven healthy recordings
  hit 1.00 through segments of a few tokens ("thank you thank you" as a
  parting). **With a ≥12-token floor it separates cleanly: #70 = 0.727
  against ≤ 0.333 for every other row** — a 2.2× corridor. The floored
  variant (`max_within_segment_share_floored`,
  `TRANSCRIPT_S3_MIN_SEGMENT_TOKENS=12`) is now measured and stored on
  every consultation alongside the raw figure. **Candidate threshold
  for the owner: floored within-segment share > 0.5.**
- Neither candidate acts. Both accumulate on every consultation from
  now on, so the next calibration has real-world rows for free.

**3. Retrieval composition (docket item 12) — measured, nothing ships.**
`scripts/evaluate_retrieval_composition.py` built the three recorded
candidate fixes as harness-only strategies (production's selection
mirrored as the baseline; `app/rag.py` untouched, pinned by test) and
ran all four against the full RAG eval set plus the 450 anaemia case.
Numbers: **every strategy holds 9/9** on the eval set. On the anaemia
case, **the 2026-07-28 misbehaviour does not reproduce on the current
corpus**: the bare "Anaemia" query now tops the CKS iron-deficiency
topic even under production (2 iron + 2 NG203); slot_budget and
citation_diversity both deepen iron to 4+2; specific naming ("Iron
deficiency anaemia") changes nothing further. Two structural
observations worth more than the headline: production's per-source cap
leaves slots EMPTY when few sources retrieve (asthma got 2 of 6
passages; both alternatives fill all six from the same guideline), and
citation_diversity is the safest single change if one is ever wanted
(9/9, equal-or-wider source sets, full slots). **Reading: no change is
needed now — the trigger finding has evaporated under the current
corpus/embedding state. Recommend keeping production and re-running
this harness after any corpus change; the harness is the deliverable.
The decision is the owner's.** Raw numbers in
`evals/retrieval_composition_results.json`.

> **CLOSED — owner decision, 2026-07-30: production retrieval stays as
> it is, and docket item 12 closes with a standing convention:
> `scripts/evaluate_retrieval_composition.py` is re-run after ANY
> corpus change**, alongside the existing RAG eval — composition drift
> is exactly the class of change the 450 finding showed a corpus
> update can cause and un-cause silently.

## Session 2026-08-01: three owner decisions banked, S3 flags

Deliberately small ahead of Friday's collaborator session; lands with
Thursday evening's restart, leaving Friday deployment-free. Three
commits; no schema change; no dependency changes.

- **Two closures recorded as owner decisions, 2026-07-30** (blockquotes
  at their sections): the ASR stack stays WhisperX for v1 (experiment
  closed, record stands, `word_timestamps=True` first if ever reopened),
  and production retrieval stays as it is — docket item 12 closes with
  the standing convention that `evaluate_retrieval_composition.py`
  re-runs after any corpus change.
- **The floored S3 share now ACTS at the flag tier**
  (`TRANSCRIPT_S3_WITHIN_FLAG=0.5`, owner decision 2026-07-30 from the
  measured 2.2× corridor): a within-segment repetition share over 0.5
  among ≥12-token segments flags — amber acknowledge-gated banner, the
  single-writer Approve gate, no new machinery — and never refuses.
  Pinned by test with the re-calibration's real numbers: #70's 0.727
  flags, the good four's 0.267–0.333 do not.
- **S1 stays MEASURE-ONLY, deliberately** — the same day's decision: the
  median-window-probability corridor is 0.013 wide (#70 at 0.902 vs
  0.943 for the closest healthy row), too thin to act on. The reasoning
  and its revisit condition (more stored consultations widening or
  collapsing the corridor) live as a comment at the thresholds in
  `app/transcript_quality.py`; every consultation keeps storing the
  windows and the calibration harness keeps reporting the median.

## Help series (2026-07-31): reader-facing docs in `help/`

A reader-facing help series now lives in `help/`, written by Claude
Cowork in owner-approved verbatim text. Division of labour: **help
explains, HANDOVER records** — those pages are for readers; this
document remains the engineering record. The help files are copied
byte-for-byte from the owner's Documents folder and **must not be
edited in the repo without owner approval**; new articles arrive the
same way.

### When a change makes a help article wrong (owner decision, 2026-08-01)

**This resolves a contradiction, correctly flagged during the Phase 7b
drive rewrite.** Two conventions cannot both be followed literally: that
a behaviour change updates the help series in the same change, and that
help articles are the owner's verbatim approved text and must not be
edited without his approval. Under the first, an implementer rewrites the
page; under the second, they may not.

**The resolution: the implementer FLAGS, the owner WRITES.** A change
that makes an existing help article wrong must say so in its report *and*
in `HANDOVER.md`, **naming the article and stating exactly what is now
untrue in it**. The owner writes the replacement wording himself.
**Implementers never edit `help/` prose without approval** — the flag is
the deliverable, not a draft of the new text.

This is the owner's rule and it applies to every future change, not only
to Phase 7b. **It is one line to change**: if the owner later wants
implementers to draft replacement wording for approval, that is this
paragraph, amended.

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
  keep_alive 30 m. **Reinstalling it: the asset is
  `ollama-linux-amd64.tar.zst`, not the `.tgz` that older notes and blog
  posts still name** — upstream changed packaging around v0.32, and
  `https://ollama.com/download/ollama-linux-amd64.tgz` now redirects to a
  GitHub asset that 404s. Take the `.tar.zst` from the release page and
  verify its SHA-256 against upstream's `sha256sum.txt` before
  extracting:

  ```bash
  curl -L -o ollama.tar.zst \
    https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst
  curl -L https://github.com/ollama/ollama/releases/latest/download/sha256sum.txt \
    | grep ollama-linux-amd64.tar.zst          # compare with sha256sum ollama.tar.zst
  tar --zstd -xf ollama.tar.zst -C ~/.local/opt/ollama   # binary lands at bin/ollama
  ```
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
   by user 182 (the owner's doctor account) via `queue.walk_in_started`.
   Verified against
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

   > **CLOSED — owner decision, 2026-07-30.** All three options were built
   > and measured in `scripts/evaluate_retrieval_composition.py`
   > (2026-07-31 session): every strategy holds the RAG eval at 9/9, and
   > the misbehaviour above does not reproduce on the current corpus.
   > **Production retrieval stays as it is; the composition harness is
   > the standing check, re-run after any corpus change.**

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
  NOT RUN, no data collected.** Trigger: the UCL professor replying with
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
private tailnet at **https://<your-tailnet-host>.ts.net** — HTTPS is
mandatory for remote microphone access (browsers only allow getUserMedia
on secure origins). Since 2026-07-24 the app is ALSO reachable from the
public internet via Tailscale Funnel (owner's decision, external demo) —
see the public-exposure posture section below.

How the pieces fit (each is required):

1. **Tailscale on Windows** (host `mlrig`, tailnet IP `<tailnet-ip>`) — the tailnet
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
   a tailnet certificate at <your-tailnet-host>.ts.net and proxies to
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
- **The invited outside clinician's demo account (id 570) audits as
  `user.registered`, not
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
The active set was five at that point (owner-confirmed): the admin
account, the receptionist account, the owner's doctor account, the
second doctor account, and the invited outside clinician's demo account.
Accounts are deactivated, never deleted — the rows
keep their names for the audit trail.

**The active set is now six** (verified against `app_user` and the audit
log 2026-07-25). The list above was correct when written; approve-to-
activate then did its job and added one:

| | |
|---|---|
| the second receptionist account (id 572) | registered 2026-07-25 11:37:27 from **`<tailnet-ip>` — mlrig's own tailnet address**, approved 37 s later by user 10 (the admin account), first login 11:38:17 from the same address |

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
(`curl.exe https://<your-tailnet-host>.ts.net`) or another tailnet device.

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

Then from any tailnet device: https://<your-tailnet-host>.ts.net
(log in as a doctor; mic permission prompt should appear on the live page).

## Session/environment facts

Native Ubuntu 26.04 on `mlrig`, user `indy`, project at
`/home/indy/Projects/consultation-ai` (migrated off WSL2 2026-08-15).
RTX 4090 (24 GB), Postgres 18.4 + pgvector native on localhost, DB
`consultation_ai` / role `consultation_app` (`.env`), HF token via
`hf` CLI cache (needed for pyannote), Ollama user-space at
`/home/indy/.local/opt/ollama`. GitHub: IndyWH/consultation-ai. The
project owner is a doctor building this to learn — explain technical
decisions in plain terms, and treat clinical-judgement questions as
theirs to decide.

## End of the 2026-08-01 face sessions — what a fresh session needs

Thirty-two commits across the day, all Phase 7b: the face drive rewritten
after 463, the affect log, the neutral reset, two new affect values, the
affect call split out of the assessment prompt, and the 467 present-
moment fix. Suite green at **665**. The phase sections above have the
detail; this is the short list of what is *not* finished.

- **The service was restarted by the owner at 21:22 on 2026-08-01, so
  the day's work IS live.** Verified at 21:28: `consultation-ai`,
  `ollama` and `postgresql@18-main` all active, `/health` ok with
  pgvector, `scripts/migrate.py --check` reports no drift (nothing today
  touched the schema), and every change under `app/` was committed by
  19:59, well before the restart. **The next room check therefore
  measures the new build**: the rewritten drive, the `PATIENT_AFFECT` log
  line, the seven affect values, and the three-call CDS engine with the
  present-moment affect prompt.
- **The CDS harness run is owed**, and the debt now covers three changes:
  the seven-value enum, the affect call's split out of the assessment
  prompt, and the 467 prompt/window change. Last run was against the
  five-value, single-call build (`evals/urgency_results.json`, left at
  the committed baseline deliberately). `scripts/evaluate_urgency.py`,
  ~30 minutes of model time. Since 2026-08-04 a run writes a DATED
  results file beside the baseline by default and prints the diff hint —
  overwriting the baseline requires `--write-baseline` (the six
  in-place-writing harnesses got the same guard;
  `evaluate_sinhala_asr.py` already takes `--out`), so the
  copy-it-out-first dance is no longer needed.
- **`AFFECT_RECENT_TURNS = 4` is a guess with nothing measured behind
  it.** 467's `PATIENT_AFFECT` log is the first material to calibrate
  against. Note the unit: the live transcript has no speaker labels, so a
  "turn" is one committed ASR line, not one exchange.
- **The 467 fix is unverified in a room.** A bench transcript returns
  `low` both with and without the recency block; the next live
  consultation with an emotional turn in it is the real check, and the
  affect log is how to read it.
- **Three small things flagged and deliberately not done**, each the
  owner's call: `tests/test_face_clinical.py` still exercises only the
  original five affect values; `test_cds.py`'s new fail-soft test needs
  no model but inherits that file's module-level Ollama skip, so it does
  not run on a machine without MedGemma; and `.env.example`'s
  `FACE_ACTIVITY_RMS` comment names one of the three surfaces that share
  its `1e-4` default (the spec § 2.2 names all three).

## Carried task (2026-08-01): SECRET_KEY fail-fast guard — DONE 2026-08-04

Came out of a home-network security review run by Claude Cowork on
2026-08-01. No code was touched by that review; this note is the only
change. The task below is queued for a fresh session.

**Discharged 2026-08-04** in commit 74d5e0c (`security: SECRET_KEY
refuses to start on a missing or known key`), implemented exactly as
specified below, with one departure: `help/03-installing-and-running.md`
was NOT updated — help prose is the owner's verbatim text (owner decision
2026-08-01, § *Help series*). The article now understates reality: its
stage 7 says "Start the server, open the browser, create the first
admin", and the server now refuses to start until `SECRET_KEY` is set —
nothing in the article's seven stages mentions `.env` or the key. The
replacement wording comes from the owner, and it belongs with the
"before you expose it" step that waits on the first-admin decision (see
the Phase 2 security section at the end of this file). *Resolved
2026-08-04: the owner-approved rewrite shipped — the Phase 2 section has
the record.*

**What was checked and is fine — do not redo this.** The live service reads
`/home/wajir/consultation-ai/.env`, and the `SECRET_KEY` there is a custom
64-character value (an `openssl rand -hex 32` output), not the code default
and not the `.env.example` default. Verified without displaying the value:
length, hash prefix and verdict only. **No rotation is needed.** Rate
limiting was also reviewed and is correct for the Funnel case: login 10 per
60 s, registration 5 per hour, and `client_ip()` trusts `X-Forwarded-For`
only from a loopback peer and takes the last entry. Nothing to change there.

**What is outstanding.** `app/auth.py` still reads the key as
`os.getenv("SECRET_KEY", "dev-secret-change-me")` — a silent fallback to a
value that becomes public knowledge the day the repo does. The unit file
sets only `WorkingDirectory` and no `EnvironmentFile`, so the key reaches
the app solely through `load_dotenv()` reading `.env` relative to the
working directory. A moved, renamed or lost `.env` would therefore not stop
the service — it would start quietly on the known default. This is a
robustness gap, not a live exposure, but it should close before the repo
goes public and it belongs with the other Phase 2 footguns.

**The change, when it is done.** Replace the silent default with an
import-time fail-fast, after `load_dotenv()`. Refuse to start when the value
is missing, empty, shorter than 32 characters, or one of the placeholders
`change-me` / `dev-secret-change-me`. Raise `RuntimeError` naming which
condition failed and pointing at `openssl rand -hex 32`, never echoing the
value or any part of it.

Known consequence: the suite will fail wherever `auth.py` is imported
without a key set. Fix that in `tests/conftest.py` by setting a valid test
key for the session — **do not weaken the guard to accommodate the tests.**
Add tests that exercise the real import-time path via `monkeypatch` plus
`importlib.reload`, covering missing, empty, both placeholders, a
31-character value and a valid 64-character one, and asserting the error
message does not contain the rejected value. Update `.env.example` and the
`.env` part of `help/03-installing-and-running.md` to state that the app
refuses to start without a real value of at least 32 characters. One commit,
lockfile untouched, suite green first.

After this lands, a deployment with a missing or misplaced `.env` refuses to
start rather than starting on a known key. That is the intent — say so in
the commit message.

**Network-side changes made the same day, for future debugging.** The
OPNsense router now redirects all port-53 traffic on the WiFi segment
(192.168.2.0/24) to its own resolver, because two Google Cast devices were
querying 8.8.8.8 directly and bypassing AdGuard. Tailscale MagicDNS is
explicitly excluded from that redirect (no-rdr rules for 100.100.100.100 and
fd7a:115c:a1e0::53), so tailnet name resolution still works from the WiFi
side. mlrig is on the wired LAN and was not affected by any of it. Note that
the WiFi-to-LAN isolation rule means a device on WiFi cannot reach mlrig
directly, so Tailscale between them relays via DERP rather than connecting
peer-to-peer — working as intended, but it explains any added latency.

## Resolved (2026-08-01): the stray Windows PostgreSQL was an ONLYOFFICE leftover

This closes the open question in **After-reboot startup sequence** above, where the
leftover Windows `postgresql-x64-18` service is described as an unexplained cause of
the 2026-07-10 port-5432 collision. It now has an explanation.

**Where it came from.** An ONLYOFFICE *server* edition install started by mistake on
2026-06-23 — their website leads to the server download rather than the desktop app.
The server itself never completed, but its prerequisites installed and stayed behind:
PostgreSQL 18 (18.1-2), RabbitMQ Server 4.2.1, Erlang OTP 27.3.4.6 and Redis-Windows
7.4.0, all dated 23/06/2026. The only wanted product was ONLYOFFICE Desktop Editors
9.4.0, which is self-contained and never used any of them.

**How it surfaced.** A Windows review on 2026-08-01 found RabbitMQ running as
LocalSystem on every boot with zero client connections, listening on 0.0.0.0 for AMQP
(5672), Erlang distribution (25672) and epmd (4369). Its own log recorded no client
had ever authenticated. Nothing was reachable from outside — inbound is blocked by
default and explicit block rules already existed for all four ports — so this was
waste rather than exposure.

**Removed 2026-08-01** in dependency order: RabbitMQ, Erlang OTP, Redis-Windows,
PostgreSQL 18. Program folders sent to the recycle bin. Roughly 1.2 GB reclaimed and
three services no longer start at boot.

**Consequences worth knowing:**

- `psql.exe` is gone from the Windows side. The WSL client is unaffected — use `psql`
  inside Ubuntu as normal.
- Keep the Hyper-V firewall rule `Block external access - PostgreSQL 5432`. That one
  guards the WSL2 cluster this project actually uses. The RabbitMQ, AMQP and epmd
  block rules are now vestigial but harmless.
- The 5432 collision cannot recur from this cause. The check in the startup section
  still applies if Postgres ever fails to bind, but a Windows PostgreSQL is no longer
  the likely culprit — look at what else grabbed the port.

**Lesson for the next prerequisite install:** the Windows side of this machine is not
where this project runs. Anything that installs a database, a broker or a cache on
Windows is either a mistake or needs a written reason here, because WSL2 mirrored
networking means the two sides share one port space and a silent Windows service can
take a port the app expects.

## Security — Phase 2, the going-public hardening (opened 2026-08-04)

Phase 1 (the 2026-07-31 audit's XSS cluster, registration input bounds,
CSP + nosniff, the Secure cookie flag) landed 2026-07-31 — commits
421cde8, 7b24bec, ce9cfc4, 9ba3b52 — and was verified live. Phase 2
opened 2026-08-04 with the SECRET_KEY fail-fast guard (74d5e0c,
discharging the carried task above) and the gitignore class-block below.
The audit's full findings live in `SECURITY_AUDIT_FINDINGS_2026-07-31.md`
at the repo root, which is deliberately NOT in the repository — that is
the point of the next paragraph.

**The findings-file episode (recorded 2026-08-04).** The findings file
was committed at the owner's rushed instruction on 2026-08-01 as a5ded2f
(`security: commit the 2026-07-31 audit findings (owner decision)`,
Co-Authored-By: Claude Opus 5). The owner reversed that decision on
2026-08-04: the commit was removed from history by rebase BEFORE any
push, so the remote never saw it, and `.gitignore` now blocks the class
(root-level `*FINDINGS*` / `*REVIEW*` markdown — fb10e05). The file
itself still exists on this machine, ignored rather than deleted; it may
name live weaknesses, and this repository's history is destined to be
public. The lesson, plainly: a single-file commit made "at the owner's
instruction" against a standing written rule should be queried once
before executing — the standing rule was written when calm and the
instruction was given in a rush.

**The parked docket (2026-08-04) — the open findings' one durable home.**
Detail lives in `SECURITY_AUDIT_FINDINGS_2026-07-31.md` (local only, per
the episode above); this list is what remains open and who moves next.

- **Finding 8 — rate-limit keying behind Funnel.** `client_ip()` trusts
  `X-Forwarded-For` only from a loopback peer (that boundary is sound),
  but if Funnel does not set the header, every public request collapses
  to the single bucket `"127.0.0.1"` — one attacker's 10 failed
  logins/min then locks out ALL users. OWNER TO VERIFY what Funnel
  actually forwards (a request-echo route, or the `ip` on one login
  audit row); if XFF is absent, key on a Funnel-provided identity header
  or accept that the limiter is global and size it accordingly.
- **Finding 11 — stateless logout.** Logout only deletes the client
  cookie; a captured token stays valid until its 12 h expiry.
  Deactivating the account does revoke (`get_user` filters `active`).
  ACCEPTED for the demo phase.
- **Finding 12 — no recording-size cap.** `app/live.py` accumulates PCM
  in memory with no duration/size bound; the one-live-session-at-a-time
  guard bounds it to a slow DoS by a trusted-ish user. Sketched fix: a
  max-duration guard that auto-stops.
- **torch/transformers dependency-CVE bump.** `pip-audit` against the
  real venv reports 16 known vulnerabilities across torch 2.8.0,
  transformers 4.57.6, nltk and setuptools — every one needs
  attacker-controlled model/checkpoint files, an attacker-controlled
  `nltk.data` resource name, or local access; NONE are reachable from
  the Funnel surface. Bumping torch→2.10+/transformers→5.3+ closes most
  but is a heavy ML-stack change to schedule deliberately (see
  *Troubleshooting* on why this machine treats the ML stack carefully).
  STANDING RULE meanwhile: never load a third-party or untrusted model
  on this machine — that is the exact path these CVEs need.

**Phase 2 items still open after 2026-08-04:** the
inline-script-to-static-js refactor for full CSP `script-src`
protection. The first-admin mechanism and the help/03 rewrite, previously
on this list, are decided and done (entries below).

**First-admin mechanism — DECIDED and closed (owner decision
2026-08-04).** From the slice-1 options, the owner chose CLI bootstrap
over refuse-when-exposed and pending-admin-activate: it is the only
option with no network-reachable path to admin on a fresh deploy, and it
matches the existing break-glass philosophy. Landed the same day: the
break-glass CLI gained `create USERNAME ROLE "Display Name"` (554311f —
getpass password, same validation as registration, active account, shell
access as the trust boundary, audited `user.created`), and the
first-registrant-becomes-admin branch in `auth.create_user` is deleted
entirely (41fd4dd), along with the register endpoint's now-unreachable
non-pending tail that issued a session cookie at registration. Every
public registration is now pending with the validated requested role, no
exception for an empty table — the 2026-07-31 audit's Finding 7
(fresh-deploy footgun) is closed. A test registers against a genuinely
empty `app_user` table and pins it. Fresh-deploy bootstrap, verbatim:
`uv run python scripts/manage_users.py create your-username admin "Your
Name"` (README quickstart step 5, c38a9db).

**help/03 flag — RESOLVED 2026-08-04.** The article's stage 7 had become
wrong twice over ("Start the server, open the browser, create the first
admin" — untrue since 74d5e0c's SECRET_KEY refusal and 41fd4dd's removal
of in-browser first admins). The owner-approved rewrite shipped the same
day as a byte-for-byte copy of the approved file (the only way help/
changes): stage 7 now covers the `.env`/SECRET_KEY step and the CLI
first-admin, and a new "Before you let anyone else reach it" section
carries the exposure guidance.

**Working-tree sanitisation — people and addresses (2026-08-04).** As of
this commit the working tree names no real person except the owner —
account references are role labels (reversible for anyone who later
agrees to be named — owner decision 2026-08-04, roles now rather than
waiting on permission) — and the real tailnet hostname and IP are
placeholders (`https://<your-tailnet-host>.ts.net`, `<tailnet-ip>`); the
bare machine name `mlrig` deliberately stays. Git HISTORY still contains
the old names and address, by accepted decision: rewriting published
history was declined, and the launch-day mitigation is rotating the
Tailscale host so the address in history goes dead — the owner's task on
the launch checklist.

*Correction (2026-09-10):* the pre-flight sweep of 10 Sept found two names the 4 Aug pass missed — a first name used as a doctor-name fixture in `tests/test_speech.py`, replaced by the neutral placeholder the file already used (launch slice 3, `dd0887a`); and a quoted clinician's name inside the amendment log of the frozen `evals/2026-07-25_sinhala_confound_prereg.md`, left in place because that file changes only by the owner's logged amendment — his decision, still open at the flip.

**The pre-public repo-contents review (owner's Documents folder,
2026-07-31) is discharged on its names, usernames and URL items** as of
this slice. Still open from that review at launch time: the Tailscale
host rotation (owner), and nothing else — the findings-file gitignore
and the Phase 2 code items closed in slices 1 and 2 (entries above).

**Slice 4 (2026-08-04): licence, prereg amendment, two 7b debts.**
The licence is AGPL-3.0-or-later (owner decision 2026-07-31 — the repo
carried MIT while the paper's Data availability already said AGPL):
LICENSE is the verbatim GNU text, pyproject carries the SPDX expression,
README and NOTICE state it, and `vendor/kindalive/` deliberately stays
MIT — that is upstream's licence, not ours. The Sinhala confound prereg
no longer names its run trigger (owner decision 2026-08-04, the
pre-public naming policy): changed by LOGGED AMENDMENT in the document's
own new Amendments section, no metric, gate or design content moved.
tests/test_face_clinical.py now covers the seven-value affect enum —
band and total-range across all seven, the ladder gains happy, angry
asserted per test_face_drive's C13 framing, with the two clinical-arm
deviations (band saturation at the ladder top; warmth and furrow pinned
to the resting face) asserted as the arm's designed properties. And the
evaluation harnesses no longer overwrite their baselines — dated file by
default, `--write-baseline` to re-baseline (see the debt-list note).

**Still open on the Phase 7b debt list after this slice:** the CDS
harness re-run against the seven-value enum and the affect split —
sequenced separately, the 09_septic_child leading-differential movement
awaits the owner's adjudication — and the neutral-face calibration
question from consultation 468 (neutral reads as slightly confused to
one viewer): the owner's call, or the mock round decides it.

**Slice 5 (2026-08-04): Docker packaging and the demo script — the last
pre-launch build item, authored; in-container validation owed.**
`DOCKER_DEMO_SPEC.md` landed signed off, with the owner's five decisions
recorded in the document (Ollama both-paths defaulting to host; routine
English live with urgency pre-recorded; the gate refusal demoed on an
owner-recorded clip; approve-to-activate on seeded data; reviewer-grade
first-run polish). The security-relevant piece went first and alone:
`client_ip()` trust is now `TRUSTED_PROXY_CIDRS` (default loopback only
— host behaviour unchanged; unparseable values refuse at import), with
spoof/trust/default tests. The packaging: Dockerfile on Ubuntu 26.04
exactly (the §1.4 dependency scars), uv-frozen from the committed lock,
nothing baked in (no corpus — redistribution — no models, no .env, no
recordings); compose with db init granting CREATEDB + template1 vector
(the §1.5 test-database contract), pulse healthcheck, localhost-only
publish, GPU reservation, and named volumes (audio survives `down`).
Reconciliations against the spec, recorded in the compose commit: the
app's env is OLLAMA_URL (the spec's OLLAMA_HOST is the ollama CLI's
name); TRUSTED_PROXY_CIDRS deliberately unset because no proxy ships;
TTS_ENABLED=false in-container (piper is outside the app by owner
decision 2026-07-25). Demo isolation per §2.1: seed_demo/reset_demo with
the manifest + marker double lock and refusal tests. `DEMO_SCRIPT.md`
carries the ten-minute run of play with its TWO OWNER-SUPPLIED GAPS: the
throwaway non-English clip for the gate-refusal beat, and the choice of
pre-recorded urgency consultation. The real two-voice recordings are NOT
distributed (owner decision 2026-08-04: consent covered recording, not
publication — README says so; scripts and references ship).
CITATION.cff shipped (owner-approved; version/date commented until the
release tag).

**What slice 5 could NOT verify on this machine — Docker is not
installed** (preflight 2026-08-04). Owed before the packaging is called
done, per §1.4's own words: the image BUILD; the in-container suite
(`docker compose run --rm app pytest`, the §1.5 gotcha); the audio path
inside the container (a green host suite proves nothing about the
container's glibc/FFmpeg/CUDA combination); and the §1.7 restart
re-enqueue check in the packaged environment. The install itself is the
owner's (sudo); the exact command block is in the slice-5 report.
(Discharged by slice 6, below, after the owner installed Docker.)

**Slice 6 (2026-08-04): the owed in-container validation — discharged.
All four checks pass; three defects found and fixed, one commit each.**
Machine state for the run: Docker 29.7.1 / Compose v5.4.0 / NVIDIA
container toolkit installed by the owner; host Ollama bound to 0.0.0.0
(Windows firewall blocks 11434 externally — the 5432 pattern); the
consultation-ai service stopped by the owner to free the card (~22.7 GB
free at preflight). Results, in the spec's order:

- **The image builds** (§1.4): 239 s cold, 4.55 GB. Ubuntu 26.04 base as
  committed.
- **The in-container suite** (§1.5): green **forward and reverse** — 654
  passed, 27 skipped, ~2–3 min. The bundled db's init held its contract:
  conftest created and dropped its disposable test database against the
  compose Postgres with no refusal. All 27 skips have honest reasons: 20
  × node absent (client-JS tests; the image ships no Node), 3 × real-TTS
  piper tests under the deliberate TTS_ENABLED=false, 1 × voice model at
  a host path the container cannot see, 3 × corpus not ingested (never
  in the image, §1.2). Ollama-dependent tests did NOT skip — the
  compose-default OLLAMA_URL reached the host Ollama, so MedGemma tests
  ran in-container. One transient reverse-run failure (CDS ReadTimeout)
  occurred only while the host suite was mistakenly run in parallel on
  the same GPU and vanished solo — §1.6's "effectively exclusive"
  warning confirmed by accident, not an ordering bug.
- **The audio path in-container** (§1.4): a fresh-process smoke asserted
  the ordering the torchcodec incident taught us to distrust —
  ctranslate2 not imported before `_preload_cuda_libraries()`, the model
  on **cuda** (full distil-large-v3; the silent CPU fallback explicitly
  ruled out), pip-wheel cuBLAS/cuDNN mapped in /proc/self/maps, and
  tests/data/jfk.wav transcribed exactly. Bonus evidence: the real
  finalisation pipeline ran in-container (MedGemma unload via host
  Ollama, WhisperX, diarisation start) up to the pyannote HF-token wall,
  where it failed loudly onto the consultation row — the §1.2
  documented prerequisite surfacing exactly as designed.
- **Restart re-enqueue** (§1.7): a consultation left `queued` with audio
  on the audio volume was re-enqueued by `docker compose restart app`
  ("Re-enqueued consultation 2 for finalisation"); an `approved` control
  row was not. `reset_demo.py` then deleted exactly the manifest's rows
  (3 demo patients, the 1 demo consultation with its audio file, demo
  account deactivated not deleted) while a deliberately-planted non-demo
  control patient, consultation and audio file survived — the scoping
  check was made non-vacuous on purpose.

The three defects, each with its own commit stating the reasoning:
pg-data must mount at /var/lib/postgresql for the pg18 image (slice 5
wrote the pg17-era path); tzdata joins the image (the base ships no
zoneinfo and the uv-managed CPython has no fallback); and test_speech.py
pins the TTS kill-switch on for its fake-command mechanics tests, with a
new test giving the kill-switch itself its first coverage. uv.lock and
pyproject.toml stayed byte-identical throughout. Host suite green
forward and reverse (681/681) with all fixes. The compose stack was left
**down**; named volumes persist (pg-data, audio, hf-cache, corpus). The
§1.4 "re-validate the audio path inside the image" condition is met and
the packaging is **done**.

**Slice 7 (2026-08-04): help article 09 ships — the guideline corpus.**
`help/09-the-guideline-corpus.md`, owner-approved verbatim (the only way
help/ changes; shipped byte-for-byte, cmp-verified). The corpus
explainer for the research-instrument audience: recipe-not-documents
(licence and staleness), the two ingestion gates and the incidents that
earned them, reshaping the corpus for another setting, and the standing
re-run-the-harness rule after any corpus change. **Incoming links are
owed and deliberately not added**: the natural locations (help/00's
router table and reading order, help/03's stage 6, help/04's go-next
block) were reported to the owner with suggested wording, and the owner
writes whatever help/ prose actually changes. README needs nothing — its
help-series mentions don't enumerate articles. **Gap closed in slice 8
(2026-08-04): the owner approved all four suggested sentences verbatim,
and they are applied — article 09 is reachable from 00, 03 and 04.**

**Slice 10 (2026-08-04): help article 02 ships — the screenshot
walkthrough — and the series' numbering gap closes.**
`help/02-using-it-step-by-step.md` plus eight owner-captured PNGs in
`help/images/`, all owner-approved verbatim and shipped byte-for-byte
(nine files, cmp-verified). Screenshot content is synthetic (the
"Ranjit Perera" acted script) and was checked clean of addresses and
account names before approval. The four incoming links (00's router
table and reading order, 01 and 03 go-next bullets) carried the same
verbatim approval and are applied. Two capture artifacts reported to
the owner rather than edited (the images are approved assets): a
Snipping Tool popup overlays the corner of `02-3-cds-working.png`, and
three shots show the walk-in name variant "Ranjit halfway Perera" from
a different session than the article's main run.

## Migration to native Ubuntu (2026-08-15): WSL2 is gone

The project moved off WSL2 on Windows and onto a native Ubuntu 26.04
install on the same physical machine. **Old:** user `wajir`, home
`/home/wajir`, WSL2 under Windows. **New:** `indy@mlrig`, project at
`/home/indy/Projects/consultation-ai`. NVIDIA driver 595.84 with CUDA
13.2. The owner installed PostgreSQL 18 + pgvector and restored
`consultation_ai` from the WSL `pg_dump` before this session, with role
`consultation_app` granted CREATEDB and pgvector in `template1`.

This session brought the app environment up by hand for the first time
on the new installation. What it did:

- **`uv` reinstalled** (0.12.5, `~/.local/bin`) — it was absent on the
  fresh box.
- **Python environment rebuilt from scratch.** The copied-over `.venv`
  had every path baked to `/home/wajir` and was unusable; deleted and
  rebuilt with `uv sync` from the committed `uv.lock` (40 s, no change
  to `pyproject.toml` or the lock). The CUDA audio path verifies in a
  fresh process — `_preload_cuda_libraries()` then `torch`, the
  deliberate ordering in Troubleshooting, prints `cuda True`.
- **`.env` de-WSL'd.** Two stale paths only — `TTS_MODEL_PATH` and
  `TTS_COMMAND`, both `/home/wajir` → `/home/indy`. Nothing else in that
  file was touched, and it stays gitignored.
- **Piper reinstalled outside the app environment** (`uv tool install
  piper-tts`, 1.6.1), per the 2026-07-25 decision that keeps it out of
  `pyproject.toml`. The pinned `en_GB-alba-medium` voice was
  re-downloaded to `~/.local/share/piper-voices/`; smoke test produced a
  33 KB 22.05 kHz mono WAV.
- **Ollama reinstalled user-space** at `~/.local/opt/ollama`, matching
  the old WSL layout. **The documented tarball URL is dead:** upstream
  stopped shipping `ollama-linux-amd64.tgz` and now ships
  `ollama-linux-amd64.tar.zst` (v0.32.13), so
  `https://ollama.com/download/ollama-linux-amd64.tgz` 307s to a GitHub
  asset that 404s. Took the `.tar.zst` asset instead and verified its
  SHA-256 against upstream's `sha256sum.txt`. Anyone rebuilding this box
  should expect the same. Ollama sees the 4090 (CUDA 13.2, 22.3 GiB
  available, `default_num_ctx=32768`).
- **Both models re-pulled** — the WSL model store was deliberately not
  migrated: `hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M` (16 GB) and
  `embeddinggemma` (621 MB).
- **Database check:** `scripts/migrate.py --check` reports
  `consultation_ai: schema matches the code — no drift`. The restore is
  clean.

**Suite: 683 passed, 0 skipped, 0 failed** (170 s). The prior recorded
baseline was 681/681 (slice-6 in-container validation); the extra two
are tests added since by `a6a6dad` and `c564a13`, not new behaviour.
Note the **zero skips** — nothing self-skipped because Ollama, Postgres,
the corpus and Node are all present on this box. Node v22.22.1 came with
the Ubuntu install, so the client-JS tests that were expected to skip
ran and passed.

Open items, deliberately not attempted here:

- **Hugging Face login.** The HF cache was not migrated. The owner runs
  `uv run hf auth login` himself. **Until then finalisation will fail at
  pyannote — do not press Stop or trigger the finalisation pipeline.**
  The live ASR model `distil-large-v3` (~1.5 GB) is a separate matter:
  it downloads itself from Hugging Face on first live use and needs no
  login.
- **systemd units** for `ollama` and `consultation-ai` — sudo, and the
  owner's job. Until they exist, both run by hand; Ollama is currently a
  `nohup ... ollama serve` writing to `/home/indy/ollama.log`.
- **Tailscale on Linux** — later. The public-exposure posture and
  after-reboot sections above still describe the WSL/Windows setup
  (mirrored networking, the Windows PostgreSQL port clash, the
  `curl.exe` hairpin workaround) and are **stale on this machine**; they
  are left as the record of what was, not instructions for what is.

The app itself was **not** started by this session: the launch command
was blocked by the assistant's permission layer, so the owner starts it
by hand. Manual line, unchanged from the fallback above:
`uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Post-migration operations (2026-08-15) — how the machine runs now

**This section supersedes "After-reboot startup sequence", "Remote
access (Tailscale, set up 2026-07-10)" and "Public-exposure posture
(Tailscale Funnel, 2026-07-24)" for day-to-day use.** Those three stay
in place as the record of the WSL2 era — they describe mirrored
networking, the Windows PostgreSQL port clash and the `curl.exe` hairpin
workaround, none of which exist on this machine. Read them as history,
not as instructions.

The migration is complete and verified: the owner click-tested the full
loop in the browser on 2026-08-15 — login, history intact from the
restored database, and a test consultation carried through Stop to note
synthesis, so finalisation works end to end with the Hugging Face token
cached again.

### After a reboot, nothing needs doing

Everything starts itself. `postgresql`, `ollama`, `consultation-ai` and
`tailscaled` are all enabled systemd units, and **the wake-the-VM step
is gone** — there is no WSL to boot, so no "open a terminal once to
start the machine" ritual. Verify:

```bash
systemctl is-active postgresql@18-main ollama consultation-ai tailscaled
tailscale funnel status
uv run python scripts/migrate.py --check
curl http://127.0.0.1:8000/health
```

One thing that looks alarming and is not: `systemctl is-enabled
postgresql@18-main` reports **`enabled-runtime`**, not `enabled`. That
is normal Ubuntu packaging — the instance is pulled in by the
`postgresql.service` wrapper, which *is* `enabled` and carries
`Wants=postgresql@18-main.service`. Postgres does start at boot. Check
the wrapper, not the instance, before concluding otherwise.

### The two unit files

Both live in `/etc/systemd/system/`, both run as `User=indy`, both
`Restart=on-failure`. `consultation-ai.service` uses an absolute path to
`uv`, because systemd's default PATH does not include `~/.local/bin` —
the same reason `.env` holds an absolute path for Piper.

`/etc/systemd/system/ollama.service`:

```ini
[Unit]
Description=Ollama (user-space install)
After=network-online.target

[Service]
User=indy
ExecStart=/home/indy/.local/opt/ollama/bin/ollama serve
Environment=OLLAMA_KEEP_ALIVE=30m
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/consultation-ai.service`:

```ini
[Unit]
Description=Consultation AI
After=network-online.target postgresql.service ollama.service
Wants=postgresql.service ollama.service

[Service]
User=indy
WorkingDirectory=/home/indy/Projects/consultation-ai
ExecStart=/home/indy/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Builds still go live only after `sudo systemctl restart
consultation-ai`, and the owner runs it.** The app runs without
`--reload`, so edited code is inert until that restart. Say when a
change needs one; do not run it.

### Remote access — native Tailscale, no Windows in the path

Tailscale runs natively on Linux now. The consequences are all
simplifications: no mirrored networking, no Windows interop path, no
`tailscale.exe` under `/mnt/c`, and **no curl hairpin limitation — the
public URL is testable from the machine itself**, which was impossible
under WSL2 and cost real debugging time.

HTTPS terminates at `https://<your-tailnet-host>.ts.net` via
`tailscale funnel --bg 8000`, proxying to `127.0.0.1:8000`. **Funnel
means the public internet, not just the tailnet** — owner decision
2026-08-15, restoring the posture first taken 2026-07-24. Every existing
defence layer is unchanged: auth, rate limiting, RBAC, the security
headers, the SECRET_KEY fail-fast guard and registration approval.

**The address has changed, and that is the point.** The Linux node
registered under a *new* tailnet hostname, because the old Windows node
still holds the old one. So the app has a new public address, and when
the owner deletes the old Windows node from the admin console the old
address dies with it. That is exactly the launch-day mitigation the
go-public gate was carrying — rotating the Tailscale host so the address
embedded in published git history goes dead (see the working-tree
sanitisation entry, 2026-08-04). **It is therefore discharged early, as
a side effect of the migration rather than a launch-day task**, with the
old-node deletion as the one remaining action. The sanitisation rule is
unaffected and still absolute: the real hostname and IP never enter a
committed file — `<your-tailnet-host>.ts.net` and `<tailnet-ip>` are the
placeholders, and the bare machine name `mlrig` stays.

### The suite on this machine

**683 passed, 0 skipped.** The zero matters: on the WSL box a handful of
client-JS tests skipped for want of Node, and the heavy tests skipped
whenever Ollama, Postgres or the corpus were absent. Node ships with
Ubuntu 26.04 (v22.22.1 here), so **the client-JS tests now run wherever
the suite runs**, and this machine has everything else present too.
Nothing self-skips. A skip on this box is now a signal worth chasing,
not background noise.

## Repo sanitisation — the public repo is content-agnostic (2026-08-15)

**Why.** NICE replied in writing to the licensing enquiry (2026-08-15).
Three things it settled, and the slice below is their consequence:

- **Individual research use, including publication, is permitted.** The
  local research instance keeps its full corpus — including the three
  CKS topics — under individual research use. Nothing about what this
  machine ingests, retrieves or reports changes.
- **Shipped software must not instruct NICE-content use.** Software
  published openly must not carry instructions that refer to NICE
  content or encourage its use in the system. So every *instruction-
  class* file in the repository is now publisher-neutral: README, `help/`,
  `scripts/`, `tests/`, `app/`, the Docker files, `NOTICE`'s manifest
  sentence and one sentence of `DOCKER_DEMO_SPEC.md`.
- **Web-scraping nice.org.uk is not permitted.** The ingest script's
  behaviour is unchanged (it fetches whatever a manifest lists), but the
  repository ships no manifest that lists nice.org.uk, and the example
  it does ship is CDC/WHO.

**What deliberately did NOT change — research records keep their source
names.** `evals/`, the phase specs, the mock-consultation material and
every existing HANDOVER entry name NICE guidelines, CKS topics and
guideline codes throughout, and they stay exactly as written. They are
the research record of what was measured against what, and a record that
no longer names its sources is not a record. This is the same distinction
NICE drew: research use (permitted) versus shipped instruction (not).
Anyone tempted to "tidy" a code out of an eval should read this paragraph
first.

**The manifest is now a per-installation file** (commits 750c91e →
846b70b, one per numbered item of the slice, suite green before each):

- `corpus/manifest.yaml` is untracked (`git rm --cached`) and gitignored
  the way `.env` is; the file on this machine is untouched and the live
  instance runs from it exactly as before. **`corpus/manifest.example.yaml`
  is the committed example** — the CDC dengue clinical-care page and the
  WHO dengue fact sheet, copied verbatim, with a header documenting every
  field and stating that each installation lists only sources its
  operator holds the right to use this way, the licence note recording
  that basis.
- **Fresh-clone behaviour** (`app/rag.py`, pinned by
  `tests/test_rag_no_corpus.py`): without a manifest the app starts,
  `corpus_name` is "no corpus configured", `corpus_version` is "-", and
  both answer paths return the ordinary refusal shape — covered false, no
  citations, a one-sentence summary — without embedding, searching or
  calling the LLM. `scripts/ingest_guidelines.py` exits 1 with the
  copy-and-edit instruction before touching the database. With a manifest
  present nothing changed.
- **Docker moved with it, beyond the literal item list, because the build
  would otherwise break on a fresh clone**: the Dockerfile copied
  `corpus/manifest.yaml` into `/opt` for the entrypoint to seed into the
  corpus volume, and `.dockerignore` now excludes that file. The image
  carries the example instead; the entrypoint seeds and refreshes
  `manifest.example.yaml` in the volume, never touches the operator's
  `manifest.yaml`, and prints a plain line when there is none. The
  operator's step is `docker compose run --rm app cp
  corpus/manifest.example.yaml corpus/manifest.yaml`, then edit, then
  ingest — README says so. Consequently `DOCKER_DEMO_SPEC.md` §1.2's
  "Ship `corpus/manifest.yaml`" now means the example manifest, and the
  entrypoint's "committed manifest is authoritative, a newer image's copy
  wins" rule applies to the example only; the spec sentence was left as
  written (a signed-off design record — one sentence in it changed, by
  instruction, and only that one).
- **Two decisions I made rather than asked, flagged here for the owner
  to reverse if wrong:** the Docker entrypoint does *not* auto-copy the
  example into place as `manifest.yaml` (so a Docker first run has no
  corpus until the operator explicitly opts in — the content-agnostic
  reading), and NOTICE's manifest sentence was corrected for accuracy
  while its publisher list ("NICE, CKS, CDC, WHO … fetched for local
  research use") was left for the owner to rule on, since NOTICE is the
  attribution file and the item list did not name it. It appears in the
  sweep list at the end of the slice report.

**Help series.** `help/09-the-guideline-corpus.md` is the owner's
verbatim approved replacement (2026-08-15) — format not documents, local
manifest, the two gates, the no-manifest behaviour; it names no
publisher. `help/03` stage 6 ("a manifest and an ingestion script rebuild
it locally") remains true; it does not mention the copy-the-example step,
which the owner may wish to add — flagged, not edited.

**Harness labels.** `tests/test_retrieval_composition.py`'s synthetic
hits are relabelled "ckd guideline" / "iron topic" / "anaemia guideline"
— labels only, every assertion pins the same counts and sets — and the
harness docstring's finding sentence names sizes and topics rather than
codes. The finding itself, and its evidence, are unchanged and live in
`evals/` under their original names.

**Access posture: the Funnel demo is closed.** The public-demo framing of
the Tailscale Funnel exposure (2026-07-24, restored 2026-08-15 above) is
closed. Access is approve-only, for named research collaborators within
the study — **not a public service**. Approve-to-activate is the gate, as
before; what changes is who is approved: study collaborators, by name.
Read the "Public-exposure posture" and "Remote access" sections above
with that in mind.

**Suite after the slice: 689 passed, 0 skipped** (683 before; six new
no-corpus tests, all light). Verified on this machine: the app starts and
serves the login page with `corpus/manifest.yaml` present, and with the
manifest renamed away `RAGService` gives the no-corpus refusal — manifest
restored afterwards. **The running service was not restarted;** the
`app/rag.py` change is inert in the live process until the owner
restarts it, and it changes nothing for an instance that has a manifest.

**Sweep rulings (owner, 2026-08-15):** of the four instruction-class hits
that survived the slice, `app/rag.py`'s `answer_for_conditions` docstring
and `NOTICE`'s corpus sentence are neutralised (no guideline code, no
publisher); `scripts/evaluate_rag.py`'s comments and the Phase-6 mockup
`docs/mockups/live_mockup.html` are KEPT as research records by owner
decision — do not "tidy" them. `DOCKER_DEMO_SPEC.md` §1.2 now says the
image ships `corpus/manifest.example.yaml` (the operator's manifest is
local, never shipped), and `help/03` stage 6 carries the owner's approved
copy-the-example wording.

## Referral letter v2 — the drafting prompt revised (2026-08-15)

**What changed.** `LETTER_PROMPT` in `app/letters.py` is replaced
verbatim with the owner's approved v2 text (commit af2e985; spec
`REFERRAL_LETTER_V2_SPEC.md` in the owner's Documents, not in the repo;
craft taken from the owner's Meddbase referral-letter method).
`REFERRAL_LETTER_STYLE.md` is rewritten to match (ce57569); it remains
the owner's framework doc and its own rule stands — where it and the
code disagree, the code wins. The method, in one paragraph:

- **Four body paragraphs in a plain spoken register** — why you are
  writing and the history; what you found; what the tests showed;
  background — the way a GP hands a case over at the desk: short
  sentences, one idea each, active voice, "while" not "whilst".
- **Silent-differential selection.** Before writing, the model lists the
  three or four conditions the consultant will weigh in the `reasoning`
  field ONLY; that differential selects and orders every fact and never
  reaches the page.
- **Negatives must earn their place** — separate conditions, record an
  absent red flag, or save the consultant a test; otherwise out.
- **Never comment on the record** — no "was not documented"; omit, or
  placeholder.
- **Plan-only exception for naming a stated concern** — a
  suspected-cancer pathway referral, a red-flag urgency, or a diagnosis
  the consultant is inheriting, only when the note's PLAN states it, in
  one factual sentence citing that Plan line.

**All guarantees unchanged.** This is a prompt-layer change only: the
approved-note-only source, the per-sentence citation and number gates,
tense fidelity (planned ≠ performed ≠ resulted), the expectation
drop-gate, and the masked, uncitable Assessment section are exactly as
they were; `SUGGEST_PROMPT`, the schema, validation and assembly are
untouched. `tests/test_letters.py` and the rest of the suite pass
unmodified (689 passed).

**Verification owed and not yet done.** The prompt is inert in the live
process until the owner restarts the service. Then: regenerate a letter
on a #66-class consultation and diff old against new, with the grounding
stats compared — the owner and Cowork run that pass. Nothing in this
entry claims the v2 letter reads better; that is what the pass is for.

**Tuned 2026-08-15 (owner judgement of the v2 output, after the #66
regenerate-and-diff — LETTER_V2_VERIFICATION.md in the owner's
Documents):** the v2 letter read staccato — a run of one-fact sentences —
paragraph 4 repeated paragraph 1, and one sentence over-read the note
("The patient agrees to this referral", not in it). The prompt now
restates the taste as rules the local model can follow mechanically:
rhythm (fold one finding's qualities into one sentence, vary length,
never a long run of one-fact sentences), a paragraph-4 dedup guard (only
what earlier paragraphs have not said; up to four paragraphs, never
more), and the patient-agreement sentence tightened to a note line that
states it in those terms — the Plan recording a referral is not the
patient's agreement. Prompt-layer only; `REFERRAL_LETTER_STYLE.md`
Register and Structure follow. Verification is the same #66
regenerate-and-diff, owed after restart.

**Micro-tuned 2026-08-15 (owner decision after the v2.1 A/B — the final
tuning iteration; the loop closes here):** v2.1 fixed rhythm and the
agreement sentence but still doubled smoking/hypertension into paragraph
4 and dropped a positive finding ("mild SOB with pain"). Two rule
additions, prompt-layer only: selection cuts negatives, never positives
— every positive the note records goes in the letter; and the
paragraph-4 dedup is hardened into an explicit pre-output check of every
paragraph-4 sentence against paragraphs 1–3, delete the repeat, omit the
paragraph if nothing remains. `REFERRAL_LETTER_STYLE.md` Selection and
item 4 follow. Verification is the same #66 regenerate after restart.

## Phase 7c slice 1 — spec committed, pure state machine landed dark (2026-08-16)

**What landed.** `PHASE_7C_SPEC.md` is in the repo (e490668): the
supervised auto history-taking design, approved by the owner wholesale on
2026-08-16 with D1–D3 and the 1–2 minute golden window decided the same
day and recorded inline. `app/auto_mode.py` (fd83191) is the pure phase
machine of spec §3/§4/§7 — the nine phases, one explicit legal-transition
table, event methods named for what happened, `Transition(from, to,
trigger, at)` records for the audit trail, `AutoModeError` on every
illegal edge, the utterance whitelist as three frozen types with no
free-text member (hard rule 1 by construction), the question-in-GOLDEN
guard that raises, the pause protocol with resume-to-exact-phase and
terminal take-over, and the ratchet set. `tests/test_auto_mode.py`
(1faf4d3) pins those properties: 81 tests, suite 689 → 770 passed.

**No behaviour change.** Nothing imports the module; the running app is
byte-identical in behaviour and needs no restart for this slice. There
are no config constants yet — `AUTO_MODE_ENABLED` and the thresholds
arrive with the wiring in slice 3, and the machine holds no numbers.

**The gate is unchanged.** Everything in 7c builds dark behind
`AUTO_MODE_ENABLED=false`. Enabling it is the owner's act, after
barge-in calibration and the mock-patient-round review — both still
owed; neither is advanced by this slice.

**Two cases the spec leaves open, decided in code, flagged for the
owner and Cowork to confirm or overrule** (spec §6/§7 do not name them;
the choice is recorded in the fd83191 message and the module docstring):

- An urgent alarm re-firing while already `PAUSED_URGENT` is a legal
  self-edge — the machine stays paused, keeps the prior phase, and the
  pending action set widens so one acknowledgement covers everything
  that fired. Chosen because the session keeps listening and the CDS
  keeps revising during a pause, so a re-fire before the doctor answers
  the banner is the normal case, not an edge case.
- `hand_back`, `golden_timer_elapsed` and `agenda_exhausted` are legal
  only from the phases spec §6 names for them (GOLDEN; GOLDEN;
  OPEN/CLOSED). A late golden timer after an early hand-back exit, or a
  hand-back detected in OPEN/CLOSED, raises — the slice-3 wiring must
  consult `controller.phase` (or `is_legal(event)`) rather than fire
  blindly. Strict by default; loosening any of these is a table edit
  plus a test edit, not a design change.

**Not touched:** `help/`, `vendor/`, the two FROZEN documents. The spec's
H1 still reads "(DRAFT for owner approval)" because the approval
instruction was to replace the header blockquote and change nothing
else; the blockquote states the approval. Owner's call whether the H1
should follow.

## Phase 7c slice 2 — auto speak path landed dark (2026-08-16)

**What landed.** The server can now initiate an utterance itself and the
client can play it, through the tap pipeline with no new mechanism —
and NOTHING CALLS IT YET: the controller wiring is slice 3, so the running
app's behaviour is unchanged, the doctor's tap-to-ask path is
byte-identical, and everything still ships dark behind
`AUTO_MODE_ENABLED=false` (the flag itself arrives with slice 3's
wiring). No restart is needed for this slice; the code is inert until
wired.

- `12cc301` — `PHASE_7C_SPEC.md`: two owner confirmations from the
  slice-1 review. The H1 drops "(DRAFT for owner approval)"; §7 records
  that an alarm re-firing while already `PAUSED_URGENT` is a legal
  self-edge (stay paused, keep the prior phase, widen the pending set),
  and the safety condition that binds slice 5: the pause banner must
  show every pending action text at acknowledgement time, so an
  acknowledgement only ever covers what the doctor actually saw.
- `136dd54` — server side. `app/speech.py`: `anything_else` joins
  PHRASES (owner wording, disclosure-gated), `TEMPLATES` holds the two
  owner-approved open-question templates instantiated server-side only
  (no client ref kind — a tap cannot reach them or choose a topic),
  `resolve_utterance()` resolves each whitelist type from
  `app/auto_mode.py` and refuses everything else, `prepare_auto()`
  synthesises through the same cache and cap with
  `ref_detail {"via":"auto","phase":…,"trigger":…}` and the agenda's
  rationale, `presynthesise_phrases()` warms the cache at service start
  (§9). `app/main.py`: `issue_auto_speak()` — same one-at-a-time guard,
  same disclosure lock, same nudge cage, same pending slot, sends
  `auto_speak` from the same builder as `speak_ready`; refusals audited
  `speech.failed` via=auto and raised to the caller; a synthesis fault
  also shown to the client as `speak_refused`. `handle_speak_ended`
  accepts `politeness_abort` for the pending utterance with no window
  open (row without span, slot released, audited
  `speech.politeness_abort`). `END_REASONS` gains `politeness_abort`,
  `urgency_pause`. 37 tests in `tests/test_auto_speak.py`.
- `c0b7f56` — client side. `live.html` handles `auto_speak` through
  `onSpeakReady` (same lifecycle, same Esc/Stop, same pill) with the §5
  politeness re-check immediately before playback. Client executed under
  Node in `tests/test_auto_speak_client.py`; the keystone exclusion
  scenario re-run for an auto-issued utterance on both paths in
  `tests/test_speech_exclusion.py`.

Suite 770 → 812.

**The gate is unchanged.** Barge-in calibration and the mock-patient-round
review are still owed before `AUTO_MODE_ENABLED` ever flips; nothing in
this slice advances either.

**Choices the governing sections left open, decided in code and flagged
for the owner and Cowork:**

- **The politeness-abort threshold** (§5 says "if activity has resumed",
  no number). The client compares its pre-playback RMS against the
  barge-in ABSOLUTE floor it already holds (`BARGE_IN_RMS_THRESHOLD`,
  0.02, uncalibrated, sent in `speech_config` regardless of the detector
  flag) — not the 1e-4 silence floor, which measured room noise
  (0.008–0.011 RMS) exceeds and which would abort every utterance in a
  real room. At-floor aborts (err toward waiting); a null reading (mic
  down) and a zero floor do not. The reading is audited on every abort
  so the mock-patient round can set the number.
- **`speech.politeness_abort` is its own audit event**, on the
  `speech.barge_in` precedent, rather than a `speech.spoken` with a
  reason: `scripts/calibrate_barge_in.py` counts `speech.spoken` as
  utterances that played, and an abort did not play. No `auto.*` events
  were added.
- **Pre-synthesis skips the two doctor-named phrases** (`disclosure`,
  `examination_handover`): the name is filled per session, so there is
  no one text to warm at start; neither is an encourager, which is what
  §9's budget is about. Warming them per session is slice-3 wiring if
  wanted.
- **`issue_auto_speak` does not do the face auto-on at a spoken
  disclosure** (owner decision 2026-07-28, done in `handle_speak`
  today): `handle_face` lives in the connection; the slice-3 wiring that
  issues an auto disclosure calls it, as `handle_speak` does.
- **Refusal semantics on the auto path**: guard refusals (already in
  flight, disclosure not given, nudge cage) raise `SpeechRefused` to the
  caller and are not shown to the client — they are the controller's to
  requeue or a wiring bug; synthesis faults raise AND show
  `speak_refused`, as for a tap.
- **The pre-synthesis task runs whenever the lifespan runs**, including
  `tests/test_live.py`'s one lifespan test on a machine with Piper — a
  handful of cache writes into `SPEECH_CACHE_DIR` that the live app has
  already made. Harmless; noted so nobody is surprised by it.

**Not touched:** `help/`, `vendor/`, the two FROZEN documents. No help
article is made untrue by this slice — nothing user-visible changes
until slice 3.

## Phase 7c slice 3 — turn-taking wired through GOLDEN, dark (2026-08-16)

**What landed.** Auto mode now runs from the doctor's toggle through the
golden minutes — invitation, encouragers on quiet, the end-of-turn
officer, the exit to OPEN — and it is DARK: `AUTO_MODE_ENABLED` ships
false, and with it false the entry's controller is never constructed,
`speech_config` does not grow, no `auto_*` message is sent, an `auto`
toggle is refused and a `quiet` report is ignored (pinned by test). OPEN
and CLOSED are reachable but inert — question flow is slice 4. No UI in
this slice; the slice-6 Auto pill will send the same `{"type":"auto"}`
message the tests send. Needs a restart to be live, but there is nothing
to see until the owner flips the flag, which he must not yet.

- `ff08a1e` — the §12 configuration in the house pattern, mirrored in
  `.env.example`; `AUTO_MODE_ENABLED` states the gate; the timing values
  labelled uncalibrated guesses naming the mock-patient round. In the same
  commit, **amendment A1** appended to `PHASE_7C_EVAL_PREREG.md`
  (FROZEN; amendments allowed by its own rule) with the owner-approved
  wording verbatim: metric 3's golden window is 1–2 minutes, carried as
  `AUTO_GOLDEN_MINUTES_S` and scored against the value in force at the
  run. `OPEN_CLOSED_RULE.md` untouched.
- `18a33d2` — the client quiet reporter (`quietReporter` in `live.html`,
  the nudge's design promoted): reports `{"type":"quiet","quiet_s":N}` at
  each configured threshold and once a second while quiet lasts, only
  while the server has confirmed auto on, configured only from
  `speech_config.auto` (sent only when the gate is up). The three "do not
  generalise the nudge" guard comments retired, each with its why written
  in place; `tests/test_silence_nudge_client.py` updated deliberately —
  the property it now pins is that **the nudge cage still holds outside
  auto mode**, client and server. The nudge object itself is unchanged.
- `8e6f722` — the end-of-turn officer in `app/cds.py`: own prompt (the
  tie-break "when in doubt, not finished" written in), two-boolean
  schema, recent turns last, temperature 0 seed 42 `CDS_NUM_CTX` (never a
  reload), `AUTO_OFFICER_TIMEOUT_S`; never raises — a failed verdict plus
  `turn_finished()`'s silence rule at `AUTO_EOT_FALLBACK_S`.
- `e6b57f7` — the wiring: `handle_auto` (on requires the disclosure lock,
  exactly as speak does; walks OFF → DISCLOSURE → INVITATION; GOLDEN
  starts at the invitation's `speak_ended`), `handle_quiet` (encourager
  rotated on cooldown through `issue_auto_speak`; officer at
  `AUTO_EOT_QUIET_S`, re-asked as quiet grows), `maybe_apply_officer`
  (hand-back exits early; otherwise window run AND turn ended), auto off
  immediate from every state, everything audited (`auto.enabled`,
  `auto.disabled`, `auto.phase` with from/to/trigger/detail,
  `auto.officer_failed`).

Suite 812 → 857 (24 protocol tests for GOLDEN, 16 for the officer, 5
for the reporter).

**Owner decision recorded for this slice (2026-08-16):** the
politeness-abort threshold stays at the barge-in absolute floor
(0.02 RMS) as slice 2 built it, confirmed as the starting value; the
mock-patient round calibrates it from the audited abort readings. The
quiet reporter uses the same floor for "quiet" (see below).

**The gate is unchanged.** Barge-in calibration and the mock-patient-round
review are still owed before `AUTO_MODE_ENABLED` ever flips.

**Where the governing sections did not fully decide, and what the code
does — for the owner and Cowork to confirm or overrule:**

- **The officer runs in GOLDEN too.** §5 says the officer triggers
  "outside GOLDEN", but §6's early exit on hand-back and its "timer
  elapsed AND current turn ended" condition both need its verdict during
  the golden minutes. It runs on quiet ≥ `AUTO_EOT_QUIET_S` in GOLDEN;
  in GOLDEN its verdict is used only for the exit (a hand-back, or the
  turn end once the window has run) — never to ask anything.
- **Officer cadence within one silence:** once per quiet span at the
  EOT threshold, and again each time the quiet has grown by
  `AUTO_EOT_QUIET_S` (3, 6, 9 s…), so a "not finished" does not stick
  through a long silence. Not a spec number; a mechanism detail.
- **The reporter's "quiet" floor is the barge-in absolute floor**, the
  same 0.02 RMS the politeness abort uses — not the nudge's 1e-4 silence
  floor, which measured room noise exceeds and which would keep the
  tracker permanently un-quiet in a real room. Copied into the reporter
  at configure time so the meter loop never names the detector (a
  standing constraint test). Our own playback ending starts a fresh
  quiet span (err toward waiting).
- **Reporter cadence: 1 Hz** after the first threshold while quiet
  lasts, so the server can rotate encouragers on cooldown without the
  client deciding anything. A protocol detail, not a threshold.
- **Enable requires the disclosure already given** (spec §10's pill rule,
  server-side). Consequence: the enable path never speaks the disclosure
  itself; the auto path's face auto-on for a spoken disclosure exists in
  `auto_issue` but is not reached from enable in this slice. If the
  invitation already played before the toggle (the doctor tapped
  Disclosure and the chain spoke it), GOLDEN starts at the toggle and
  the `auto.phase` detail says `{"invitation": "already_completed"}` —
  the metric-3 zero point is then the toggle, not the invitation's end.
  Whether the owner wants the one-tap flow instead (Auto speaks the
  disclosure) is his call; both are a small change.
- **No server-to-client stop exists**, so auto off lets a playing
  encourager finish (≤ a second) or the doctor cuts it with Stop/Esc;
  nothing further is issued. Slice 5's urgency pause will need a stop
  message or the same acceptance.
- **With no committed transcript the officer is not asked** (a model
  judging an empty transcript would be guessing); the silence rule alone
  can move a patient who never spoke once the window has run.
- **`auto_refused` is answered to the client and logged, not audited**
  (nothing was done); `auto.enabled`/`auto.disabled` are audited.
- **`AUTO_OFFICER_TIMEOUT_S` lives in `app/cds.py`** beside the officer;
  the other eight in `app/main.py`. `app/auto_mode.py` stays pure.

**Not touched:** `help/`, `vendor/`, `OPEN_CLOSED_RULE.md`;
`PHASE_7C_EVAL_PREREG.md` only by amendment A1. No help article is made
untrue: nothing user-visible changes with the gate down.

## Phase 7c slice 4 — question phases wired: D1, D2, D3 (2026-08-16)

**What landed.** Auto mode now runs from the one-tap start through the
golden minutes into the question phases and out through the handover
sequence — and it is still DARK behind `AUTO_MODE_ENABLED=false` (with
the gate down nothing below exists; pinned). Needs a restart to be live;
nothing to see until the owner flips the flag, which he must not yet.

- `f83f2c2` — spec truth-ups (owner decisions 2026-08-16): §5 the officer
  also runs in GOLDEN, for the exit only; §10 the Auto pill's ONE-TAP
  rule replaces disabled-until-disclosure; §6 the anything-else refill
  return path and once-per-session.
- `841e76d` — the one-tap start in `handle_auto`: with no disclosure
  given, toggling Auto speaks it through the auto path (face auto-on via
  `handle_face`, as `handle_speak` does), the played-through disclosure
  is recorded as given (spoken) and chains the invitation through the
  auto path, and GOLDEN starts at the invitation's `speak_ended`. A
  cut-off disclosure chains nothing; a failed disclosure fails enabling
  as a unit. Manual-first shapes stay (already-given → pass-through;
  both done → GOLDEN at the toggle, audited). **The slice-3 tests
  pinning "enable requires disclosure already given" were deliberately
  repinned to this rule** — an owner-decided property change, said so in
  the docstrings, not a weakening.
- `2a4a7b2` — the topic call (D1) in `app/cds.py` beside the officer:
  own prompt, `{"topic": string}`, temperature 0 seed 42 `CDS_NUM_CTX`,
  `AUTO_TOPIC_TIMEOUT_S` (2.0, `.env.example`); never raises; an
  unusable phrase (empty, a question, > 8 words / 60 chars) is a failed
  verdict and the caller asks verbatim.
- `c9c5ff9` — the question flow: strict-revise (a post-answer CDS pass
  at once, bypassing `CDS_MIN_NEW_CHARS`; ask only from the fresh
  agenda; one bridging encourager; `AUTO_STRICT_REVISE=false` asks from
  current), the topic-scoped cone (new topic → `tell_me_more` template,
  seen topic → verbatim, OPEN→CLOSED at the first verbatim ask, late new
  topics still opened in CLOSED), pre-synthesis at plan time
  (`AUTO_PRESYNTH`), aborted questions requeued, the doctor's tap
  displacing the queue (`auto.doctor_tap`), the handover sequence with
  the refill return path (`auto.handover`), rows carrying
  `via/phase/trigger/topic/open_form`. Every threshold in force is now
  recorded per run on `auto.enabled` (`thresholds`), so both D2 postures
  are visible in the record. Also a real bug found and fixed on the
  way: the synthesis temp file was per-process, and a background warm
  and a tap on the same phrase collided ("synthesis produced no
  audio"); it is now unique per call.

Suite 857 → 889.

**The gate is unchanged.** Barge-in calibration and the mock-patient-round
review are still owed before `AUTO_MODE_ENABLED` ever flips.

**Where the governing sections did not fully decide, and what the code
does — for the owner and Cowork to confirm or overrule:**

- **Which agenda question is asked:** the top of the fresh agenda, but
  not the same words twice in a row when there is another to ask
  (re-asking is allowed and logged; a ping-pong on identical text is bad
  manners). A silent patient who never answers therefore hears the top
  question, then the second, alternately, until the doctor intervenes.
- **Speech between the revision and the ask is not re-revised:** the ask
  waits for the next turn end (officer) but is drawn from the agenda
  the post-answer pass returned. Under D2's stated tie-break this errs
  toward waiting, not toward re-running the ~17 s pass; if the patient
  answers the queued question before it is asked, the CDS will drop it
  on the next revision after the ask.
- **`AUTO_STRICT_REVISE=false`** plans from the current agenda — except
  when it is empty, where the fresh pass is still required before the
  handover can be concluded (§6: agenda-empty counts only on a
  post-answer revision).
- **The handover phrase moves the machine to HANDOVER when it plays
  through** (not at issue), so a politeness-aborted handover phrase is
  requeued like a question; after HANDOVER the auto run has ended and
  quiet reports do nothing.
- **A tapped agenda question in OPEN/CLOSED sets "awaiting answer"** so
  its answer's turn end triggers the revision; a tapped phrase or a tap
  in GOLDEN is audited but changes no flow state.
- **`affecting_you`** is registered and unused by the automatic flow,
  as instructed.
- **The thresholds-per-run record** lives on `auto.enabled` (there was
  no earlier per-run recording; the prompt assumed one).

**Not touched:** `help/`, `vendor/`, the two FROZEN documents. No help
article is made untrue: nothing user-visible changes with the gate down.

## Phase 7c slice 5 — the urgency pause protocol wired (2026-08-17)

**What landed.** Hard rule 2 is machinery now: an urgent alarm while auto
mode is listening pauses it, cuts what it was saying, shows every
pending action text on a banner in the alarm's home, and waits for the
doctor's RESUME AUTO or TAKE OVER — the ratchet in force. Still DARK
behind `AUTO_MODE_ENABLED=false`, with ONE schema-level exception noted
below. Needs a restart to be live.

- `f37fb42` — the server-initiated stop: `auto_stop` (with the reason)
  handled by the client through exactly the Esc/Stop path; a stop that
  lands before playback declines the play command; server helper
  `cancel_auto_playback` closes the window at the cut, resolves the row
  with the named reason (unstarted → reason, no span), clears the queue,
  and recognises the client's echoed `speak_ended`. Cuts tap or auto.
- `39116ca` — `assessment_snapshot` (`app/assessment_snapshots.py`, in
  the schema ordering after consultations): one row per CDS revision —
  version, the revision's own moment, audio position, urgent, the action
  texts — buffered in the session, persisted at completion beside the
  utterances, cascading on delete including the #469 void-and-purge
  path. Read by nothing yet (metric 7, replay, the review page later).
- `30620f5` — the pause: a pass returning non-empty `urgent_actions`
  while in GOLDEN/OPEN/CLOSED fires `controller.urgent_alarm`, cuts the
  current and queued auto utterances (`urgency_pause`), stands the
  officer down, audits `auto.paused` (texts, every pending text, the
  snapshot version, the transition, re-fire flag) and sends `auto_pause`
  with EVERY pending text; a re-fire widens (the machine's self-edge,
  audited); listening continues; auto off / other phases untouched; the
  face untouched (guard tests unchanged). Golden seconds spent before a
  pause are kept.
- `f568130` — the banner (inside the urgent panel in the sticky row,
  lists every pending text, RESUME AUTO / TAKE OVER under the three
  standing rules), `auto_ack` on the server (`auto.acknowledged` with
  every text covered + snapshot versions, then `auto.resumed` to the
  exact prior phase — with the D2 revision requested — or
  `auto.takeover`, terminal), the ratchet end to end, the reconnect echo
  carrying pending texts, and the review page's display-only list of
  live acknowledgements (`live_acknowledgements`, from the
  `auto.acknowledgements` consultation-linked audit row) beside the
  untouched acknowledge-gated banner.

Suite 889 → 920.

**Owner decision recorded (2026-08-16):** the silent-patient
alternating-questions behaviour from slice 4 is accepted for v1 and
watch-listed for the mock-patient round — no stall guard in this slice.

**Note for the owner — the one change outside the flag.** Once this
build is restarted, `assessment_snapshot` is written on EVERY CDS
revision of every live session, auto mode on or off: one small insert
per ~17 s pass, schema-level, nothing the doctor can see. The table is
created by schema setup at startup like every other.

**The gate is unchanged.** Barge-in calibration and the mock-patient-round
review are still owed before `AUTO_MODE_ENABLED` ever flips.

**Where the governing sections did not fully decide, and what the code
does — for the owner and Cowork to confirm or overrule:**

- **RESUME AUTO in a question phase requests the D2 revision at once.**
  Under the ratchet, that pass re-fires the same action unless the
  transcript by then shows it done or arranged (the CDS's arranged
  latch) — so in practice RESUME is a no-op-and-re-pause until the
  doctor has dealt with the alarm, and TAKE OVER is the button for
  "I'll handle this myself". That is the spec's ratchet as written;
  it is flagged because it will feel sharp in the room. Resuming into
  GOLDEN does not trigger a pass (the pass comes from transcript
  growth as before), so a golden-minutes resume holds until the CDS
  next revises.
- **The banner lives inside the urgent panel** ("same position class as
  the urgent panel it accompanies" read literally: the alarm's reserved
  home). While paused the panel stays even if a later pass clears the
  CDS list, so the banner never floats without its panel and the doctor
  can always acknowledge.
- **`auto_toggled.on` now means "in a live run"** — false after HANDOVER
  and TAKEN_OVER as well as OFF; the client's quiet reporter follows it.
  A fresh Auto tap after either restarts through OFF (audited
  `auto.disabled` via=restart) — the doctor may start a new run.
- **Auto off while paused drops the pause unacknowledged** (the machine's
  slice-1 rule); the alarm itself is still in the CDS panel and flows to
  the review banner at Stop.
- **The live acknowledgement does not pre-acknowledge the review banner**
  (`urgent_ack_at` stays null; approval stays gated). The review page
  shows the live acks as a record beside it — spec §7 says "so the review
  page can show who acknowledged what, when"; it does not say the gate
  changes, so it does not.
- **A cut utterance is never requeued** (unlike a politeness-aborted
  one): after a resume the fresh revision decides what is asked next.
- **`speech.spoken` with `server_stop=true`** audits a played-and-cut
  utterance; an unstarted cut is on its row alone.

**Not touched:** `help/`, `vendor/`, the two FROZEN documents. Help
articles unaffected while the gate is down; the review page's new
live-acknowledgement block appears only for sessions that had one.

## Phase 7c — BUILD COMPLETE across six slices, dark (2026-08-17)

**The phase is built.** Supervised auto history-taking exists end to end
— the pure phase machine, the auto speak path, turn-taking through the
golden minutes, the question phases (D1 topic call, D2 strict-revise, D3
topic-scoped cone), the urgency pause protocol with its ratchet, and the
UI (Auto pill, phase indicator, Handover control, pause banner). **All of
it is DARK behind `AUTO_MODE_ENABLED=false`**: with the flag false the
running app behaves exactly as it did before 7c, with the one
schema-level exception below. Nothing here has been used in a room.

**The gate, stated plainly one more time.** Enabling auto mode is the
OWNER'S act, after barge-in calibration
(`scripts/calibrate_barge_in.py` meeting D5) and the mock-patient-round
review — and NOTHING in this build advances either. The flag is a config
boundary in the `BARGE_IN_ENABLED` pattern; 7c must not arrive by drift.

**What the next restart changes regardless of the flag:** the
`assessment_snapshot` table begins recording one row per CDS revision of
every live session (version, moment, audio position, urgent, action
texts) — a small insert per ~17 s pass, nothing the doctor can see. The
table is created by schema setup at startup like every other.

**The six slices, by commit:**

| slice | commits |
|---|---|
| 1 — spec + pure state machine | `e490668` spec, `fd83191` `app/auto_mode.py`, `1faf4d3` tests, `3238dd6` record |
| 2 — the auto speak path | `12cc301` spec touch-up, `136dd54` server, `c0b7f56` client + keystone, `8945edd` record |
| 3 — turn-taking through GOLDEN | `ff08a1e` config + prereg A1, `18a33d2` quiet reporter, `8e6f722` officer, `e6b57f7` GOLDEN loop, `30b2e27` record |
| 4 — the question phases | `f83f2c2` spec truth-ups, `841e76d` one-tap start, `2a4a7b2` topic call, `c9c5ff9` question flow, `6bf517f` record |
| 5 — the urgency pause protocol | `f37fb42` server stop, `39116ca` snapshots, `30620f5` the pause, `f568130` banner + acks, `fb127d6` record |
| 6 — UI, the resume fix, the record | `87ff105` resume fix + spec, `254831e` Auto pill, `799741f` phase indicator + Handover, this entry |

Suite at the end of the phase: 938 passed (from 689 before slice 1).

**Slice 6.** The RESUME AUTO fix (owner decision 2026-08-17, spec §7
extended verbatim in `87ff105`): on resume no immediate revision is
requested — the alarm-bearing pass's agenda already carries the alarm's
clarifying questions, so clarification gets exactly one answer's chance
before urgency re-evaluates at the next post-answer revision, clearing
the alarm or re-pausing under the ratchet; the slice-5 test that
expected the immediate revision was deliberately repinned. The Auto pill
(`254831e`): beside Sound check and Face, labelled, server-confirmed via
the `auto_toggled` echo, hidden entirely when `speech_config` carries no
auto block, one tap on = the one-tap start, one tap off = immediate. The
phase indicator and the Handover control (`799741f`): every transition
is pushed live as `auto_phase`; the status line names the phase (Golden
minutes / Open questions / Closed questions / Paused — urgent / Handing
over); the Handover control, visible only while listening, starts the
wired anything-else → answer → examination-handover sequence, audited
`auto.doctor_handover`. All three under the standing rules, pinned in
`tests/test_standing_rules.py`.

**Where the governing sections did not fully decide in slice 6:**

- **The doctor's Handover from GOLDEN.** The machine's edge
  `(GOLDEN, handover_requested) → HANDOVER` is immediate and HANDOVER has
  no edge back to OPEN, so from GOLDEN the two phrases are spoken from
  HANDOVER as a fixed sequence with NO agenda-refill return path; from
  OPEN/CLOSED the sequence runs exactly as the agenda-empty path does,
  refill return included, and the machine fires `handover_requested`
  (the doctor asked) when the examination handover plays through. The
  prompt's "the agenda-refill return path applies to it identically"
  therefore holds in the question phases and cannot in GOLDEN without a
  machine change — flagged, not improvised.
- **`auto.doctor_handover`** is the audit event for the doctor's tap (an
  intervention, hard rule 5); `auto.handover` carries `requested_by`
  (`doctor` | `agenda_empty`).
- After a resume the alarm-bearing question may be asked before any
  answer, and a verbatim ask narrows OPEN → CLOSED — so the second pause
  of a ratchet cycle can leave CLOSED and the second resume returns
  there; correct, and pinned.

**help/ — sentences the completed phase makes untrue once the flag
flips (REPORT ONLY; nothing in `help/` was edited; the owner writes any
replacement wording, and nothing in this build waits on it):**

1. `help/01-a-consultations-journey.md` §3 — *"The doctor can tap a
   suggested question and the app asks it aloud — after telling the
   patient, in a fixed disclosure, that it is a computer."* — With auto
   mode on, the app also invites, encourages and asks questions of its
   own choosing with no tap (code-owned phases; the CDS agenda;
   owner-approved templates); the disclosure still comes first, but the
   app itself speaks it at the one-tap start. (The section's sequence
   diagram, "Doctor taps a question", has the same gap.)
2. `help/02-using-it-step-by-step.md` Step 2 — *"Everything lives on this
   one screen. Matching the numbers on the picture:"* and item 3, *"Face
   switch and Stop. The face can be turned on or off at any time; Stop
   ends the consultation and starts the write-up."* — With the flag on,
   the control row also carries the Auto pill (Auto: on/off) and, while
   auto mode is listening, the Hand over control; the status line shows
   the auto phase; the numbered picture and list no longer show
   everything on the screen.
3. `help/02-using-it-step-by-step.md` Step 3 — *"Talk to the patient
   normally. The transcript streams in, questions come and go as they are
   answered, and the differential revises itself as evidence arrives."* —
   With auto mode on, the machine takes the history (invitation, golden
   minutes with encouragers only, then its own questions one at a time,
   then the examination handover) and the doctor supervises; questions
   are asked aloud by the machine, not only tapped.
4. `help/02-using-it-step-by-step.md` Step 3 — *"The banner is a prompt
   to the doctor, not an instruction, and it clears when the transcript
   shows the action arranged."* — With auto mode on, an alarm also PAUSES
   auto mode: the urgent panel then carries the pause banner (every
   pending action text, RESUME AUTO / TAKE OVER) and stays until the
   doctor acknowledges, even if a later revision clears the list; the
   ratchet re-pauses on a re-fire after a resume.
5. `help/04-the-architecture.md` — *"MedGemma 27B does the differential,
   the red-flag watch, the guideline summaries, the note and the letters
   — as separate calls with separate rules, never as one conversation."*
   — Two more calls join that list under auto mode: the end-of-turn
   officer and the topic call (both stateless, temperature 0, same
   context length, fail-soft).
6. `help/05-why-one-consultation-at-a-time.md` — *"One consultation keeps
   that model busy roughly a third of the time."* — Under auto mode's
   strict-revise posture a CDS pass runs after every answer, plus the
   officer and topic calls; the measured third will not hold and needs
   re-measuring before the promise about the alarm is restated.

Nothing in `help/00-introduction.md`, `03`, `06`, `07`, `08` or `09` is
made false: `06`'s guarantees (reference-only speech, server-side
disclosure, code clears the alarm) hold on the auto path by construction,
and `08`'s audit claim gains events rather than losing any.

**Not touched:** `help/`, `vendor/`, `OPEN_CLOSED_RULE.md`;
`PHASE_7C_EVAL_PREREG.md` only by amendment A1 (slice 3).

## Phase 7c closing micro-slice — the help/ wording and the last spec truth-up (2026-08-17)

**The six flagged help/ sentences are resolved.** Five owner-approved
replacements applied verbatim, character for character, reflowed to each
file's line width, nothing else in any article changed (`5c95a43`):
`help/01` §3 (tap-to-ask now also names auto mode; the sequence diagram's
participant reads "Doctor taps — or auto mode plans — a question"),
`help/02` Step 2 item 3 (the Auto switch, the Hand over control, the
status line), `help/02` Step 3 (the assistant taking the history; an alarm
pausing its questioning until acknowledged, re-pausing if the same concern
fires again), `help/04` (MedGemma's two small pacing judgements). The
sixth — `help/05`'s "one consultation keeps that model busy roughly a
third of the time" — is **held, by owner decision**, until the figure is
re-measured in the mock-patient round.

**The GOLDEN-handover spec truth-up recorded** in `PHASE_7C_SPEC.md` §6
(this commit): from GOLDEN a doctor's Handover goes straight to the
handover sequence with no return path — the machine has no edge back from
HANDOVER, and a doctor handing over during the golden minutes is taking
the consultation back; the agenda-refill return applies in the question
phases.

**The phase's written record is now closed.** Spec, prereg amendment A1,
HANDOVER entries per slice, and the help series are consistent with the
build. **The gate is unchanged**: `AUTO_MODE_ENABLED` ships false; enabling
auto mode is the owner's act, after barge-in calibration and the
mock-patient-round review, and nothing in the build advances either. The
next restart begins recording `assessment_snapshot` rows regardless of the
flag (schema-level, nothing the doctor can see).

## Tooling (2026-08-18): `scripts/calibrate_barge_in.py --since` accepts a local timestamp (`YYYY-MM-DDTHH:MM[:SS]`) as well as a date, so same-day calibration batches — before and after a volume or microphone change — are never pooled (`6ab3c1b`); date-only input unchanged, report-only unchanged.

## Barge-in D5 — CLOSED with a NEGATIVE RESULT (2026-08-18)

**Decision (owner, 2026-08-18): the barge-in gate item is closed, not
postponed** — the Sinhala kind of closure, per the pre-agreed rule that
no patient-friendly configuration passes the frozen D5 target (false
stops ≤ 1% of utterances AND ≥ 90% of interruptions caught within
300 ms). `BARGE_IN_ENABLED` stays false for v1; **hard mute is the v1
posture**, and the 7c build already assumes it (one-tap cancel, Esc, the
Auto pill; the doctor wins between utterances). With this closure **the
7c gate reduces to one item: the mock-patient-round review.**

**Evidence.** Three same-day calibration batches on 2026-08-18 — webcam
under the monitor, webcam on top of the monitor, MacBook Air built-ins
(`--since 08:23` / `08:28`, the timestamp form landed the same day,
`6ab3c1b`) — plus the read-only analysis of the stored residual series:

- The browser echo canceller removes only **~5–10 %** of the playback
  echo on every tested path (residual mean 0.048–0.051 vs raw mean
  0.051–0.053 on the monitor path; 0.032–0.039 vs 0.036–0.043 on the
  MacBook). **Residual ≈ raw throughout.**
- The echo is **sustained** through the utterance's loud syllables —
  250 ms window means of 0.05–0.37 RMS held for 250–750 ms, five times
  the 150 ms sustain rule — **not an onset transient.** The series is
  the sound-check phrase's own envelope; the "settled" 0.0001–0.0017
  is the post-playback tail and the 0.003–0.009 minima are inter-word
  pauses, not canceller convergence.
- Any threshold low enough to catch quiet speech (0.056 RMS, the 445
  measurement) sits **inside** the sustained echo band; the report's
  residual-derived thresholds come out at 0.45–0.65 RMS. **D5 side 2
  fails by an order of magnitude on all tested hardware.** Side 1 is
  predicted met only because the threshold is that high.
- Residual peak > raw peak on most MacBook readings (0.24 vs 0.14) is a
  measurement-scale effect, not acoustics: the main analyser reads
  ~43 ms windows with AGC, the detector's ~11 ms windows without, so the
  peaks are not one scale (report fix below).

**Report fixes from the analysis (`52bd13e`):** the calibration
script's "first window → settled" convergence readout, which compared
pre-onset silence with the post-playback tail, is replaced by an honest
series readout (pre-onset window · loudest 250 ms window · final
window, no convergence claim); `speech.barge_in_scale` now treats a
residual peak within ×2 of raw as the expected window-length/AGC effect
(clamped to raw as before, logged, not audited) and keeps the anomaly
audit beyond that bound. Nothing in the app's behaviour changes; the
script remains report-only in a READ ONLY transaction.

**v2 routes recorded, not scheduled:** a directional microphone; and/or
rethinking the playback path so the echo canceller can reference it (the
page's own `Audio` playback is what Chrome's canceller should be
referencing and evidently is not, at these levels). The 50 ms
per-tick instrumentation proposal from the analysis (store the raw
50 ms snapshot lists for both streams, the onset moment and each
analyser's window length) is **parked as optional v2 measurement work.**

**Side findings for the mock-patient round:** the daytime noise floor
reached **0.0135 RMS with the webcam under the monitor** — the 0.02
absolute floor, and the politeness-abort threshold that shares it, keep
only ×1.5 headroom there (**watch item**); and the monitor's up-firing
drivers explain why moving the webcam to the top of the monitor did not
reduce the echo (the same driver path fires at it either way).

## Solo pilot diagnostic — consultations 482–484, 1 Sept 2026 (REPORT ONLY, 2026-09-02)

**A report exists**, outside the repository:
`~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_2026-09-01.md`,
beside the three run logs and `PILOT_DEBRIEF_2026-09-01.md`. It is the
diagnostic the debrief asked for over the owner's three solo pilot runs
of auto mode on 1 Sept (the first time 7c ran in a room; face ON in all
three; `AUTO_MODE_ENABLED=true` during the sitting): the complete
`auto.*`/`speech.*` audit timeline per run relative to `auto.enabled`,
the thresholds in force (every value at its code default; the 25 s
speaker-count bound included), answers to the debrief's F1/F2/F5
questions from the record, a read-only description of the GOLDEN loop's
post-window behaviour and the politeness-abort path with file:line
references, a candidate-defects list (D1–D10) and a
behaved-as-designed list. Nothing in code, tests, config, flags or the
database was changed; `help/` untouched.

**The headline, so a reader does not need the report to know what
happened:** there is no golden timer — the window is a comparison made
only when an officer verdict is applied (`app/main.py:3301-3302`) — and
encourager rotation is unconditional for the whole of GOLDEN
(`main.py:3234`). In 483 the window ran out 19 s before Stop and two
more encouragers followed with no exit; in 482 it ran out 75 s before
Stop (golden seconds correctly kept across two urgency pauses) and five
followed. Because each of our own utterances restarts the client's
quiet span, the quiet never exceeded 8.3 s in any run, the officer was
asked only at 3 s and 6 s of each ≈ 8 s span, and its 5 s silence
fallback is never consulted while it *answers* — so a "not finished"
officer plus the machine's own "Mm-hm." is a livelock that needs no
talking patient. Successful officer verdicts are not audited or logged,
so the record cannot show what the officer said (D2). 484 was stopped
1.06 s after the window ran and is not evidence either way. There were
**zero politeness aborts** in the three runs; the one utterance that
stopped mid-word in 482 was an encourager cut after 450 ms by the
urgency ratchet re-pausing 2.0 s after RESUME AUTO, not traffic. In 483
the speaker-count answer arrived 127 s after Stop, 102 s after the 25 s
bound; it was stored, not applied, and the run-5 ignored-declaration
visibility and approval block are armed (and were exercised end to end
in 482, where the answer was 41 s late). The decisions the report leaves
with the owner are the debrief's seven.

**Commit:** docs-only (this entry). The suite was not run for it — a
HANDOVER-only change touches no code — per the house rule that a
docs-only commit need not carry a suite run.

## Solo pilot fix slice — the owner's seven decisions of 1 Sept 2026, built (2026-09-03)

**What landed.** The seven items of the owner's post-pilot decisions
(recorded in `~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DEBRIEF_2026-09-01.md`
and the diagnostic's D1–D10 beside it), one commit each, the full suite
green before every commit, `PHASE_7C_SPEC.md` truth-upped in the same
commit as the code it describes. `AUTO_MODE_ENABLED` is untouched and
`.env` reads `false`; `PHASE_7C_EVAL_PREREG.md` is untouched — the golden
window stays 90 s and no metric changes; `help/`, `vendor/` and
`OPEN_CLOSED_RULE.md` untouched. **Needs a restart to be live** (the
owner's act, as always). Nothing here advances the gate: enabling auto
mode still waits on barge-in calibration and the mock-patient review.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `02916b5` | every officer verdict audited as `auto.officer_verdict` (D2) | 945 → 947 |
| 2 | `a43a224` | `golden_window_ran`, and the post-window exit rule (D1, D3) | 947 → 952 |
| 3 | `6d93e04` | one "go on" per golden window, after 5 s of quiet (F3) | 952 → 954 |
| 4 | `ee39abe` | a tapped examination handover ends the auto run (D5) | 954 → 957 |
| 5 | `53f54cf` | the resume ratchet's one answer's chance, made real (D4) | 957 → 960 |
| 6 | `9f4a399` | finalisation holds 180 s for the speaker count after an auto run (D6) | 960 → 965 |
| 7 | `21be175` | the golden window counts down on the phase indicator (D7) | 965 → 967 |

Final suite: **967 passed** (from 945 at `82ac5ae`). Every commit message
carries the why; this entry carries the decisions and the seams.

**The owner decisions, restated (all 2026-09-01):**

1. **Every officer verdict is on the record** — `auto.officer_verdict`
   with `quiet_s`, `golden_elapsed_s` when in GOLDEN, `finished_thought`,
   `handed_back`, `failed`, `elapsed_ms`, `phase`, and the transition it
   produced or null. `auto.officer_failed` unchanged beside it.
2. **The window has an end the machine knows about.** `golden_window_ran`
   is set the first time `golden_spent + seconds in GOLDEN ≥
   AUTO_GOLDEN_MINUTES_S` is observed on any quiet report or verdict,
   audited once as `auto.golden_window_ran` (with `golden_s`). Once set:
   no encourager; GOLDEN → OPEN at the first of a verdict with
   `finished_thought`/`handed_back`, or quiet ≥ `AUTO_EOT_FALLBACK_S` —
   on every quiet report, whether or not the officer answered (the
   transition detail says `by: verdict | quiet_fallback`). Before the
   window, unchanged; `golden_spent` still counted across a pause (the
   482 arithmetic 55.7 + 2.0 + 32.6 → 90.3 is pinned on an injected clock).
3. **Encouragers: at most ONE per golden window, `go_on` only, after
   `AUTO_ENCOURAGER_MIN_QUIET_S` (new, 5.0 s), never after the window.**
   The bridge in the question phases keeps one-per-revision and speaks
   the same phrase. `mm-hm` and `i_see` stay registered, tappable and
   pre-synthesised (`speech.ENCOURAGER_IDS` unchanged;
   `speech.ENCOURAGER_ID = "go_on"` is what the flow speaks).
   **`AUTO_ENCOURAGER_COOLDOWN_S` is retired from both paths** — with
   one per window and one per revision (~17 s apart) it bound nowhere,
   and a setting that does nothing is worse than none. It is gone from
   the code, `.env.example`, the thresholds record and spec §12.
4. **A tapped examination handover ends the run** in GOLDEN, OPEN or
   CLOSED: the same `handover_requested` edge, `auto.doctor_handover`
   with `via=tap` (the control now writes `via=control`),
   `auto.handover` with `requested_by=doctor`, the client told the run
   has ended. Slice 4's "a tap in GOLDEN changes no flow state" is
   superseded for this one phrase.
5. **The resume ratchet's one answer's chance.** A CDS pass in flight at
   RESUME AUTO, or launched before the first turn end after it, may not
   re-pause on already-acknowledged actions; audited
   `auto.repause_suppressed` with the assessment version. Only a pass
   started after a post-resume turn end re-pauses. A genuinely new
   action still pauses (widening, as slice 5 pinned); a re-fire while
   already paused is untouched. Slice 5's flagged "RESUME is a
   no-op-and-re-pause until the doctor has dealt with the alarm" is
   thereby closed for the in-flight pass; the sharpness that remains is
   the ratchet as designed.
6. **The speaker-count wait after an auto run is 180 s**
   (`AUTO_SPEAKER_DECLARATION_WAIT_S`, new) instead of 25 s
   (`SPEAKER_DECLARATION_WAIT_S`, now in `.env.example` too, unchanged
   for other consultations). While it holds: the Stop prompt says how
   long, the live status line says it is waiting for the speaker count,
   the review page's finalising status says so, and the consultation
   API carries `awaiting_declaration`. On expiry the run-5
   ignored-declaration path applies unchanged.
7. **The phase indicator counts the golden window down** from the
   server's own numbers (`golden_s` in `speech_config.auto`,
   `golden_spent` on every `auto_phase` push): counting in GOLDEN,
   frozen while PAUSED_URGENT, cleared on exit. No new audit event.

**Spec sections touched:** §3 (taps), §5 (the fallback after the window;
the encourager policy), §6 (the post-window state), §7 (the one answer's
chance), §10 (tapped handover; the speaker wait; the countdown), §11
(`auto.officer_verdict`, `auto.golden_window_ran`), §12 (settings: the
cooldown out, the minimum quiet and the speaker wait in).

**Where the decisions did not fully decide, and what the code does — for
the owner and Cowork to confirm or overrule:**

- **The window's one encourager is spent at issue**, like the nudge: a
  politeness-aborted "go on" is not re-issued. The alternative (spend it
  only when played through) risks the same phrase twice.
- **The tapped handover ends the run at the tap, not at the phrase's
  end**: a cut-off handover phrase is still the doctor's decision. A tap
  while the doctor's own Handover sequence is already under way ends it
  too (the machine will not say the phrase again).
- **"A turn end after the resume" is any turn end the officer judges in
  a listening phase** — in GOLDEN a finished verdict counts even before
  the window (the patient spoke and stopped). The suppression covers
  every action acknowledged this session, not only the last pause's.
- **The auto-run test for the speaker wait is the machine's history
  having an ENABLE transition** — the same fact the `auto.enabled` row
  records — read at Stop; the created audit row says `auto_run` and the
  bound so the consultation carries it. The wait is in-process, as the
  waiter always was: after a restart no waiter exists and no wait
  happens, exactly as before.
- **Tests repinned by decision** (each docstring names it): the
  golden-encourager tests of slice 3 (phrase, threshold, one per window,
  aborted-is-spent), the timer-alone hold (now re-asked inside the
  fallback span), and one slice-3 test — "nothing is spoken in OPEN" —
  which had been passing vacuously since slice 4 because an unplayed
  golden encourager blocked the slot; it now pins what OPEN actually
  says (at most the single bridge, never a rotation). Two structural
  pins gained the new call arguments (`askSpeakers`, the `auto_phase`
  handler). Nothing was weakened or deleted.
- **The pause tests' harness parks `AUTO_ENCOURAGER_MIN_QUIET_S` at 100**
  beside the old threshold, so tests that do not want an encourager get
  none; a test that wants one sets it back to 5.0.

**`help/`:** no article is made untrue. `help/02` Step 3 says the
assistant "encourages" (it still does, once) and Step 4 says the app
"asks one question — how many people spoke — then rebuilds the
transcript" (it still does; it now waits longer for the answer after an
auto run). `help/05`'s held sentence stays held.

**Watch list, carried forward unchanged:**

- **D9** — one officer timeout in 484 at +78.4 (1999 ms) with no CDS
  pass visibly in flight; fail-soft worked; cause unexplained. Item 1
  now records every verdict's `elapsed_ms`, so the next occurrence will
  have neighbours to compare against.
- **D10** — the politeness abort is a single RMS sample with no duration
  term (`live.html`, `politeness.shouldAbort`), unexercised: zero aborts
  on 1 Sept from the top-of-monitor position. The London-traffic
  question stays open rather than answered.
- **The felt length of the 90 s window** — re-judge in the next pilot
  now that the exit works and the indicator counts it down; if still
  too long, the prereg amendment path (an owner-approved logged
  amendment, never a silent edit) is how it changes.
- **The solo-run first-speaker label** — a single cluster already
  defaults to Patient and is flagged (`transcript.single_voice`);
  confirmed working in 484. Solo runs still need Swap when diarisation
  finds two clusters of one voice (482, 483).

## Second machine rebuild — Ubuntu reinstalled on a new drive, service restored (2026-09-04)

**Owner-run, Cowork-guided, one terminal step at a time. No code changed.**
The machine got a fresh Ubuntu 26.04.1 install on a new NVMe root
(full-disk encrypted). The home folder was copied from the old root;
`~/.local` and dotfiles deliberately were not, and `/etc` and
`/var/lib` are new. The old install stays on its own drive as a
bootable fallback and was mounted read-only at `/mnt/oldroot` for the
copies below.

**What the copy did not carry, and what was done about each:**

- **The app venv** came across (7.5 GB) but was dead: its interpreter
  pointed at `~/.local/share/uv/...`, which no longer existed. Deleted
  and rebuilt: `uv` 0.12.9 installed fresh, `uv python install 3.12`
  (3.12.14 — the system Python is 3.14 and unusable for this project),
  `uv sync` from the unchanged lockfile. `torch 2.8.0+cu128, cuda True`.
- **Piper** reinstalled as a uv tool (now 1.8.0; the 2026-08-15 entry
  recorded 1.6.1). Voice `en_GB-alba-medium` re-downloaded to
  `~/.local/share/piper-voices/`; smoke test produced a 91 KB WAV. The
  absolute paths in `.env` are unchanged and correct.
- **Ollama** reinstalled user-space at `~/.local/opt/ollama` from the
  `.tar.zst` asset with the SHA-256 checked against upstream's
  `sha256sum.txt` (0.33.3). Both models re-pulled:
  `hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M` and `embeddinggemma`.
- **The database.** The last dump (2026-08-14) predates everything from
  the referral-letter work onward, so it was NOT used. Instead the
  old install's Postgres 18 cluster (`/var/lib/postgresql/18/main`,
  95 MB, cleanly shut down — no `postmaster.pid`) was copied over the
  fresh cluster with rsync, ownership and mode restored, and Postgres
  started. Same major version (18.4 → 18.6, a minor step, no upgrade
  path needed). `pg_hba.conf` identical old and new; the only
  `postgresql.conf` differences were the installer's locale defaults
  (en_US on the old box, en_GB on the new) — the new file was kept.
  The fresh empty cluster is parked at
  `/var/lib/postgresql/18/main.fresh-2026-09-04`. Verified:
  `migrate.py --check` reports no drift; 49 consultations, latest
  #484 (the 1 Sept solo pilot); 1,301 guideline chunks.
- **Hugging Face** needed no login: `HF_HOME` now points at the second
  NVMe (`/mnt/fastdata/huggingface`, set in `~/.profile`), where the
  cache and token were moved. `hf auth whoami` confirms.
- **Tailscale** identity restored by copying
  `/var/lib/tailscale/tailscaled.state` from the old root, so this
  machine is still `mlrig-1` with the same public URL and Funnel still
  on — no re-sharing, no admin-console work. Wrinkle recorded: if the
  fallback install is ever booted online, both claim the same node and
  the last to connect wins. Harmless for a fallback.
- **The two systemd units** recreated verbatim from the 2026-08-15
  entry, with ONE deliberate addition to `consultation-ai.service`:
  `Environment=HF_HOME=/mnt/fastdata/huggingface`. A systemd service
  does not read `~/.profile`, and the cache is no longer in the
  default `~/.cache` location, so without this line finalisation would
  fail at pyannote. Both units enabled; `postgresql@18-main`, `ollama`
  and `consultation-ai` all active; `/health` ok with pgvector; Whisper
  loaded on cuda; the owner signed in as admin over the public URL.

**Suite: 967 collected — 925 passed, 42 failed on the first run, and the
42 are NOT the rebuild's.** All 42 (`test_barge_in`, `test_cds_first_call`,
`test_face_ws`, `test_speech_autonomy`, `test_speech_exclusion`) fail
with `AttributeError: 'StubSpeech' object has no attribute
'presynthesise_phrases'` at `app/main.py` session start. That path runs
only when `AUTO_MODE_ENABLED` is true, and the suite reads the live
`.env` through `load_dotenv()`. `.env` was switched to
`AUTO_MODE_ENABLED=true` at 07:14 on 3 Sept for the solo pilot — five
hours AFTER the last commit and its green suite — so the old install
would have failed identically; nobody had run the suite since. With the
shell overriding the file (`load_dotenv` never overrides an existing
variable): `AUTO_MODE_ENABLED=false uv run pytest --lf` → **42 passed**.
So: 967/967 with the flag off, and the rebuild is verified.

**Docket item from this (a CC slice, owner go-ahead pending):** the
suite must not depend on the owner's `.env`. Either the pre-7c
`StubSpeech` classes gain `presynthesise_phrases` (a no-op) or
`tests/conftest.py` pins `AUTO_MODE_ENABLED` for the run — and the 7c
tests that need it on should set it themselves. Until that lands, run
the suite as `AUTO_MODE_ENABLED=false uv run pytest` on a box whose
`.env` has auto mode on.

**Loose ends, unchanged:** untracked `.claude/settings.local.json`
still carries the stale `/home/wajir` permission entries from the WSL
era (plus a generous set of `Bash(...)` allows from the previous
rebuild); `/mnt/oldroot` is a manual mount and disappears at reboot;
a deliberate reboot test is still owed on this install, as it was on
the last.

## Solo pilot diagnostic — consultation 485, the first run after the fix slice (REPORT ONLY, 2026-09-07)

**A report exists**, outside the repository: `~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_485_2026-09-03.md` (named for 3 Sept as asked; the run itself was 6 Sept, 23:54–23:58 BST) — the full audit/journal timeline of 485 with the fix slice's new events, answers on the politeness abort (none), the golden exit (by `quiet_fallback`, 0.8 s after the window), the post-exit revision (launched without new transcript, landed with an alarm), the planned-then-displaced question, and the two taps; code findings E1–E9 with file:line at `aa0965a` (the headline: the question phases still have no fallback past a healthy "not finished" officer, so the answer to the tapped question never ended a turn); nothing in code, tests, config, flags or the database changed. Docs-only commit; the suite was not run for it.

## Solo pilot fix slice 2 — the owner's five decisions of 7 Sept 2026, built (2026-09-07)

**What landed.** The five items of the owner's decisions after
consultation 485 (the first run after the fix slice; report
`~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_485_2026-09-03.md`,
candidate defects E1–E4 plus the doctor's-side item), one commit each,
the full suite green before every commit, `PHASE_7C_SPEC.md` truth-upped
in the same commit as the code it describes. `AUTO_MODE_ENABLED` is
untouched and `.env` reads `false`; `PHASE_7C_EVAL_PREREG.md`, `help/`,
`vendor/` and `OPEN_CLOSED_RULE.md` untouched. **Needs a restart to be
live** (the owner's act). Nothing here advances the gate.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `60185d8` | one turn-end rule in every phase (E1) | 967 → 969 |
| 2 | `b6b4763` | our own utterances never erase a judged turn end (E2) | 969 → 971 |
| 3 | `bd567e4` | the ratchet matches actions by meaning, not wording (E3) | 971 → 979 |
| 4 | `fb05398` | a busy model is a wait, not a failure (E4) | 979 → 982 |
| 5 | `94e5eb9` | a visible thinking state and a guarded tap | 982 → 987 |

Final suite: **987 passed** (from 967 at `700c450`). Every commit
message carries the why; this entry carries the decisions and the seams.

**The owner decisions, restated (all 2026-09-07):**

1. **One turn-end rule in every phase.** In OPEN and CLOSED (and the
   doctor's handover sequence), as already in post-window GOLDEN, quiet
   of `AUTO_EOT_FALLBACK_S` ends the patient's turn on the quiet report
   itself, whether or not the officer answered or answered "not
   finished"; a finished/handed-back verdict still ends it sooner. Every
   turn end outside GOLDEN is audited `auto.turn_ended` with
   `by: verdict | quiet_fallback`, `quiet_s`, `phase`, `answer`, and the
   span's verdict when there was one. (485: three "not finished" across
   7 s of silence after an answered question; no revision, no next
   question.)
2. **Our own utterances never erase a judged turn end.** Every quiet
   report now carries `since: "speech" | "playback"` — what began its
   span. A fresh span re-asks the officer either way; `turn_ended` is
   cleared only when the PATIENT began the span or when a question is
   issued. (485: the bridge "Go on." 1 s after the golden exit erased
   the exit's own turn end.)
3. **The ratchet matches actions by meaning.** `app/auto_mode.py`
   gains `normalise_action` / `action_similarity` / `match_action`
   (stdlib only): lower-case, punctuation and whitespace stripped, a
   small stop-word list removed, token-set similarity ≥
   `AUTO_ACTION_MATCH_THRESHOLD` (new, default 0.6, in `.env.example`
   and the per-run thresholds record). Inside the one answer's chance a
   reworded action does not re-pause; a genuinely new one does and
   widens the pending set as slice 5 pinned. Every comparison that
   suppresses a re-pause is audited `auto.action_matched` (both texts,
   score, exact, threshold, version). (485: "Consider hospital
   admission" → "Immediate referral to hospital" → "Same-day specialist
   referral", three pauses.)
4. **A busy model is a wait, not a failure.** While a CDS pass is in
   flight the officer's bound stretches to `AUTO_OFFICER_MAX_WAIT_S`
   (new, default 30 s, in `.env.example` and the thresholds record); the
   deferral is audited `auto.officer_deferred` with the version the pass
   will land as, and the verdict is applied when it arrives (its row
   carries `deferred`). No pass in flight → the 2 s bound and
   `auto.officer_failed` unchanged. (485: 7 of 7 timeouts inside CDS
   pass windows; D9 explained.)
5. **The doctor's side.** The phase indicator shows "preparing a
   question…" from the moment a revision is requested until the question
   is issued (or the handover sequence starts), from a new `auto_plan`
   push (`preparing` → `queued` with text → `idle`, on change). A tap
   while a question is planned or queued is answered with
   `speak_confirm` and displaces nothing; the page shows the queued text
   beside the tapped control with *Ask yours instead* (the same tap with
   `confirm_displace: true`) and *Let Alba ask*; `auto.doctor_tap`
   records `confirmed` true/false and the displaced text; a cancelled tap
   leaves the queue untouched. Taps with nothing planned are unchanged.

**Spec sections touched:** §3 (the guarded tap), §5 (one turn-end rule;
`since`; the officer's stretched bound), §7 (matching by meaning), §10
(the thinking state; the confirmation), §11 (`auto.turn_ended`,
`auto.action_matched`, `auto.officer_deferred`, `deferred`/`stale` on
verdict rows, `confirmed` on tap rows), §12 (the two new settings).

**Where the decisions did not fully decide, and what the code does —
for the owner and Cowork to confirm or overrule:**

- **E2's literal rule was "turn_ended is cleared only when a question is
  issued".** As built, the PATIENT's own voice beginning a fresh span
  still clears it (the client says which it was); only our playback is
  exempt. Reason: a plan landing while the patient has started a new
  thought would otherwise issue at the first 1.75 s report without any
  judgement — the spec's "err toward waiting" tie-break. A report with no
  `since` (an old client) is read as speech.
- **A late officer verdict from a span the patient has left is recorded
  (`stale: true`) and not applied.** New with E4: a 30 s deferral can
  return after the patient has spoken again, and a "finished" from
  before their new words must not end the turn they re-opened. Before
  this slice a stale verdict was applied (the 1 Sept report noted it
  "helps rather than hinders" — true at 2 s, not at 30 s).
- **The matcher's stop-word list** (`auto_mode.ACTION_STOP_WORDS`) is
  small and hand-written: articles, urgency/hedging words (consider,
  immediate, urgent, now, same-day…), "do it" verbs (arrange, obtain,
  refer, send…) and "bedside". Two texts sharing no token never match,
  whatever the letters. Chains are not followed: a reworded action that
  was suppressed is not itself added to the acknowledged set, so a third
  wording is compared against the acknowledged ones only. The threshold
  is the owner's to tune; 0.6 is what the 485 pairs clear (0.615–0.64).
- **"Planned" for the guarded tap includes a running revision** — the
  indicator already says preparing, so the tap gets the same answer
  ("the machine is preparing a question", no text yet). **The tapped
  examination handover is exempt** from the confirmation: it ends the
  run, and there is nothing for the machine to ask after it.
- **The thinking state is derived, not evented:** on every loop tick
  from the wiring's own state (revision / plan task / queued), pushed
  only on change. Latency is one tick (an audio frame, ≈ 0.1–0.2 s).
- **Tests repinned by decision** (each docstring names it): "outside
  GOLDEN the only encourager is the single bridge" (now one bridge per
  revision, bounded by revisions); "no ack-resume loop without an
  answer" (reports kept under 5 s; the tail pins that 5 s of silence
  after the asked question IS the answer's end); the slice-4 tap test
  (confirm before displacing); the client-page reporter pin (the stop
  path names 'playback'); the pure module's stdlib pin (admits `re`).
  The three harness engines accept the officer's bound and the three
  harness clients send `since`. Nothing weakened or deleted.
- **E1's fallback in the handover sequence** (the anything-else answer
  from a GOLDEN handover) applies too, through the same helper.

**`help/`:** no article is made untrue. Worth the owner's eye:
`help/02` step 5 says "Tap the small speaker icon and the assistant asks
that question" — still true; with auto mode on and a question in
preparation the tap now first shows the one-click choice. A clause
there is the owner's call.

**Watch list, carried forward:**

- **The doctor twice perceived an urgency pause as a traffic
  interruption** (1 Sept "stopped midway"; 6 Sept "traffic interrupted
  Alba early / restart") — the pause banner's visibility in the room,
  to watch in the next pilot.
- **D10** — the politeness abort is a single RMS sample, still
  unexercised: zero aborts in 482–485.
- **The felt length of the 90 s window** — re-judge now that the exit
  works and the indicator counts it down (485: 43.5 s of unbroken
  silence in GOLDEN after the second resume, nothing from Alba by
  decision); the prereg amendment path if still too long.
- **The solo-run first-speaker label** — working as designed (single
  cluster → Patient, flagged; 484 and 485).

## Solo pilot diagnostic — consultation 486, the second run after fix slice 2 (REPORT ONLY, 2026-09-07)

**A report exists**, outside the repository: `~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_486.md` — the full timeline of 486 (7 Sept, 07:33–07:44, script 01, slice-2 code live), the per-question latency table (Q1–Q6 mean 27.7 s of which the CDS revision is 74 %; Q7 198.6 s behind a runaway assessment call that held Ollama's single slot for 180 s), the stale question (the agenda kept an asked question at the top across four versions; the pass saw the answer and kept it on the model's literal reading), the "restarts" (auto mode was never restarted — the eight RESUME taps were the ratchet re-pausing on every post-answer pass, as designed), candidate defects F1–F9 with file:line at `94e5eb9`, and what behaved as designed (E1–E4 all visibly working). Nothing in code, tests, config, flags or the database changed. Docs-only commit; the suite was not run for it.

## Solo pilot fix slice 3 — the owner's four decisions after consultation 486, built (2026-09-07)

**What landed.** The four items of the owner's decisions after
consultation 486 (report
`~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_486.md`,
findings F1–F5), one commit each, the full suite green before every
commit, `PHASE_7C_SPEC.md` truth-upped in the same commit as the code it
describes. `AUTO_MODE_ENABLED` is untouched and `.env` reads `false`;
`PHASE_7C_EVAL_PREREG.md`, `help/`, `vendor/` and `OPEN_CLOSED_RULE.md`
untouched. **Needs a restart to be live** (the owner's act). Nothing
here advances the gate.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `0589fbb` | an acknowledged action does not re-pause; the standing strip (F1) | 987 → 989 |
| 2 | `1e39dfc` | a turn must start before it can end; one re-ask at the grace (F5) | 989 → 992 |
| 3 | `606de26` | cap runaway generation; the assessment call's own timeout (F3) | 992 → 999 |
| 4 | `80a3481` | no question is asked twice; the cone by meaning (F4, first half) | 999 → 1002 |

Final suite: **1002 passed** (from 987 at `75fac19`). Every commit
message carries the why; this entry carries the decisions and the seams.

**The owner decisions, restated (all 2026-09-07):**

1. **An acknowledged action does not re-pause.** After RESUME AUTO or
   TAKE OVER, a later pass whose every action matches (E3) something
   pending or acknowledged pauses nothing; each skip is audited
   `auto.repause_skipped_acknowledged` (both texts, score, exact,
   threshold, version). The acknowledged-but-open actions stay on the
   live page's standing strip inside the urgent panel (`auto_standing`,
   pushed on every pass landing and acknowledgement, on change) until
   the pass lists nothing (arranged latches, as today) or the
   consultation ends. A genuinely new action still pauses and widens as
   slice 5 pinned. (486: eight RESUME taps in one run.)
2. **A turn must start before it can end.** After an auto question,
   quiet counts toward a turn end — by fallback or verdict — only once
   the client has reported a span the patient began. No speech inside
   `AUTO_NO_ANSWER_GRACE_S` (new, 12 s) → the same question re-asked once
   (`auto.reask_no_answer`); past a second grace the ordinary path
   proceeds, so silence never traps the run. (486: the 5 s rule ended an
   answer 10.6 s before the patient began it.)
3. **Runaway generation is capped.** Every model call carries
   `num_predict` — `CDS_ASSESSMENT_MAX_TOKENS` 1500,
   `CDS_URGENCY_MAX_TOKENS` 1000, `CDS_AFFECT_MAX_TOKENS` 800,
   `AUTO_OFFICER_MAX_TOKENS` 64, `AUTO_TOPIC_MAX_TOKENS` 48 — and the
   assessment call's own timeout is `CDS_ASSESSMENT_TIMEOUT_S` (new,
   60 s; was the generic 180). A cap hit or timeout is `cds.runaway`
   (call, reason, tokens, elapsed, cap/timeout, failures, version kept)
   and a failed pass: the previous assessment is kept, the urgency
   check still runs on its own call and its alarm still counts, and a
   revision auto mode was waiting for is answered from the agenda it
   already has. (486: a 7,211-token assessment call held the single
   Ollama slot for 180 s; the patient waited 3 min 18 s.)
4. **No question is asked twice; the cone by meaning.** An asked-and-
   answered memory of question texts; a planned question whose
   normalised text equals one in it is skipped (`auto.reask_suppressed`)
   and the next item taken; the F5 re-ask is exempt; a spent agenda hands
   over. The cone's opened-topics set matches by meaning at
   `AUTO_TOPIC_MATCH_THRESHOLD` (new, 0.6). (486: the risk-factors
   question asked twice; "this chest pain" and "the pain" opened twice.)

**Spec sections touched:** §5 (a turn must start before it can end;
runaway caps), §6 (no question twice; the cone's identity), §7
(acknowledged actions do not re-pause; the strip; aliases), §11
(`auto.repause_skipped_acknowledged`, `auto.reask_no_answer`,
`cds.runaway`, `auto.reask_suppressed`), §12 (the new settings).

**Where the decisions did not fully decide, and what the code does —
for the owner and Cowork to confirm or overrule:**

- **F1's chain.** A re-wording that matched joins the acknowledged set
  as an alias (`auto["action_aliases"]`), so 486's chain (admission →
  referral → specialist referral → admission) stays one action; without
  it the third wording would have paused. The pure controller's
  acknowledged set is untouched; its ratchet test
  (`test_the_same_action_refiring_after_a_resume_pauses_again…`) still
  pins that the machine accepts the event — the wiring no longer fires
  it for a matched action.
- **F1 at RESUME:** the strip is pushed at the acknowledgement itself
  (the pending texts are the latest assessment's), not only at the next
  pass. It is not carried on the reconnect echo; a reconnect shows it at
  the next pass landing.
- **F5's re-ask** goes through `auto_issue` with the same utterance and
  `trigger.reask: true`; it needs the slot free (`free`), otherwise it
  waits for the next report. A doctor-tapped question is not covered by
  the grace (the decision names auto questions). The officer is still
  asked at 3 s while awaiting speech — wasteful, harmless; its verdict
  cannot end the turn.
- **F3's runaway on the first pass:** there is no previous assessment
  to keep, so a minimal one carries the urgency check's own result and
  the alarm still pauses. The generic pass-failure log now names the
  exception class (486's message was empty). Runaway rows for the
  officer and topic calls are audited from their failed verdicts. The
  assessment call is bounded end to end (`asyncio.wait_for` plus the
  HTTP timeout), like the officer.
- **F4's "matches"** is exact equality of normalised token sets (score
  1.0), not the 0.6 similarity used for actions and topics: two
  questions on one topic are legitimately different questions, and a
  looser bound would merge "Have you ever had chest pain like this
  before?" with a question about its character. A looser bound is the
  owner's to set; the audit row carries the score either way. A spent
  agenda (every item asked and answered) now hands over — the
  anything-else phrase, then the examination handover — which is the
  logical consequence and is worth watching in the next run.
- **Tests repinned by decision** (each docstring names it): the slice-5
  "ratchet re-arms" tail, the no-ack-resume-loop tail (twice: F1 and
  F5) and the 482-shape tail no longer expect a second pause; four
  harness stubs of `_chat` accept the engine's new keyword arguments.
  Nothing weakened or deleted.

**`help/`:** no article is made untrue. `help/02` still says the
assistant "asks aloud, one question at a time" and that an alarm
"pauses the assistant's" run — both still true; an alarm on an
already-acknowledged action no longer pauses it, and that is a nuance
the owner may want a clause for.

**Watch list, carried forward:**

- **The CDS reading its own parenthetical literally** ("other risk
  factors (e.g., diabetes, high cholesterol)" kept as unanswered after
  the patient named smoking, blood pressure and family history) —
  prompt-level; to revisit with the standing question queue. Item 4
  stops the second asking; it does not change what the model believes.
- **D10** — the politeness abort is a single RMS sample, still
  unexercised: zero aborts in 482–486.
- **Banner visibility** — the doctor read eight RESUME taps as
  "restarting auto mode"; with F1 there will be far fewer pauses, and
  the standing strip is new on the page — to watch in the next pilot.
- **The felt length of the 90 s window** — 486 exited by hand-back at
  63.8 s, so still untested since the exit was fixed; the prereg
  amendment path if too long.

## Standing question queue — slice 1 of 7, the pure module, built (2026-09-07)

**What landed.** The owner-approved spec for the standing question
queue (`AGENDA_QUEUE_SPEC.md`, the owner's proposal after consultation
486: 27.7 s mean from turn end to Alba speaking, 74 % of it the full CDS
pass; a question asked twice; two re-asks in substance) and the first of
its seven build slices (spec §9): the pure `AgendaQueue` module, its
tests, and the four settings. One commit per item, the full suite green
before every commit. `AUTO_MODE_ENABLED` is untouched and `.env` reads
`false`; `PHASE_7C_EVAL_PREREG.md`, `PHASE_7C_SPEC.md`, `help/`,
`vendor/` and `OPEN_CLOSED_RULE.md` untouched. **Nothing here needs a
restart**: nothing in the running app imports the module or reads the
settings.

| # | commit | what | suite |
|---|---|---|---|
| 0 | `7266af9` | `AGENDA_QUEUE_SPEC.md` copied verbatim into the repo root (the `PHASE_7C_SPEC.md` precedent: the spec lives with the code and is kept truth-current) | 1002 |
| 1 | `63fb06a` | `app/agenda_queue.py` — the pure module, inert | 1002 |
| 2 | `6685214` | `tests/test_agenda_queue.py` — 23 tests, each docstring naming its property | 1002 → 1025 |
| 3 | `691a38f` | `AUTO_QUEUE_MAX`, `AUTO_QUEUE_ABSENT_PASSES`, `AUTO_RERANK_TIMEOUT_S`, `AUTO_RERANK_CONTEXT_TURNS` in `app/main.py` and `.env.example`, read by nothing yet | 1025 |

Final suite: **1025 passed** (from 1002 at `e5e959a`).

**What is inert, and why.** The module is a plain in-memory queue —
stdlib plus the existing E3 normaliser from `app/auto_mode.py`, an
injected clock, no FastAPI, no database, no model calls (a test pins the
import surface). The live flow still replaces the agenda wholesale on
every pass and asks from `entry["agenda"]` as slice 3 of the solo pilot
fixes left it; the queue becomes the flow's agenda in slice 2, when
pass completion merges into it, the ask comes from its head, and the
asked-and-answered memory (`auto["asked_answered"]`, F4) becomes the
queue's asked/answered status. The four settings duplicate the module's
defaults so the numbers are in `.env.example` from the start; they are
not in the per-run thresholds record until they are live.

**What the module does (spec §2, as built):**

- `merge(pass_version, questions)` — three outcomes per question:
  match a PENDING item → refresh (`last_seen_version`, `absent_count`
  reset); match an ASKED or ANSWERED item → **discard**, so an asked
  question can never re-enter, whatever the pass says — the guarantee is
  the item's status, not a prompt; match nothing → append. Then D-A
  (unmentioned pending items count an absence; three consecutive →
  dropped, `queue_dropped_absent`), the baseline order (the pass's own
  order for what it listed, then the unlisted survivors in their previous
  order), and D-D (cap at eight pending, lowest ranks dropped,
  `queue_capped`). Returns the events in order, `queue_merged` first
  with added / refreshed / discarded / duplicates counts and ids.
- `consume(item_id=None, by="auto")` — the head, or the tapped item
  (D-E), becomes ASKED. `answered(id)` — ANSWERED. Both raise
  `AgendaQueueError` on a state that does not permit them.
- `apply_rerank(order_ids, drop_ids, ms=)` — pending items only. **Any
  id that is not a known pending item is ignored** and listed in the
  event's `ignored` (the no-invention guard, §3): the re-ranker cannot
  add, resurrect or touch an asked question. Unmentioned pending items
  keep their previous relative order after the ones named.
- Question identity: exact equality of E3 token sets (the F4 rule);
  `question_key` falls back to bare tokens when a text is all stop
  words so nothing carries the empty key. Topic identity:
  `pending_on_topic(topic)` at the topic threshold by meaning.
- `snapshot()` is the JSON-ready view slice 4's panel will show.

**Where the spec did not decide, and what the code does — for the
owner and Cowork to confirm or overrule:**

- **A DROPPED item does not match.** Spec §2 names three outcomes
  (pending → refresh, asked/answered → discard, nothing → append) and
  none for dropped. As built, a question dropped for absence, by the cap
  or by the re-ranker is a fresh proposal if a later pass raises it
  again: a new id, that pass as `first_version`. The alternative — a
  re-ranker drop ("the patient addressed it") treated like answered —
  would extend the never-re-enter guarantee to a model's judgement
  rather than to a fact of the session. A test pins the chosen reading
  and is the place to repin.
- **A refresh keeps the first wording.** The match is on normalised
  token sets, so the pass's wording can differ only in case,
  punctuation and stop words; the item keeps the text first proposed
  (which pre-synthesis may already hold as audio).
- **A question listed twice in one pass counts once** (`duplicates` in
  the event).
- **`answered` is its own event** (`queue_answered`), beyond the five
  the spec's §7 lists, because every state change returns one.
- **Items 1 and 2 are separate commits**, as the build prompt asked
  (one commit per item); CLAUDE.md's "tests land with the behaviour
  they pin" would have put them together.

**The slices ahead (spec §9):**

2. Wiring — pass completion → `merge`; ask-from-queue (§5: pending →
   topic call → verbatim → pre-synthesis → issue at the next quiet; a
   running pass never blocks the ask); the empty rules (empty + pass
   running → one bridge; empty + no pass → request one; empty on a
   fresh post-answer revision → handover); F4's asked-memory becomes the
   queue's asked status; the queue events audited as `auto.queue_*`.
3. Re-ranker — the stateless call in the affect/topic shape, D-B's
   context (`AUTO_RERANK_CONTEXT_TURNS`, capped by characters),
   `AUTO_RERANK_TIMEOUT_S` fail-soft to the current order
   (`auto.rerank_failed`), skipped while a full pass is in flight (D-F),
   `apply_rerank` with its no-invention guard, audited
   `auto.queue_reranked`.
4. Panel and taps — the questions-to-ask panel shows the queue (pending
   in order, asked struck through, dropped hidden and expandable); a tap
   consumes that item (D-E); the preparing state covers re-rank plus
   synthesis. `help/` flagged for the owner's wording.
5. Cadence flag (D-C: (a) now, (b) full pass every second answer
   behind a flag) and the pin that the urgency check runs on its own
   call at every answered turn whatever the cadence; HANDOVER,
   `PHASE_7C_SPEC.md` §5, §6, §9 truth-ups, `help/` flags.
6. GPU discipline (§7a, D-G) — `model.call` audit (kind, queued_ms,
   run_ms, tokens, outcome); the resident live set as an invariant with
   `model.load_during_live`; the priority scheduler (urgency, then the
   short conversational calls, then the full pass, then speculation);
   the second Ollama slot as a measurement experiment only.
7. Speculative pass during the patient's answer, behind a flag, once
   the queue's own effect is measured against the 486 baseline (turn
   end → Alba speaking, per question; mean 27.7 s to beat).

**`help/`:** nothing is made untrue by this slice; nothing on the page
changes until slice 4.

## Standing question queue — slice 2 of 7, the wiring, built (2026-09-08)

**What landed.** Slice 2 of the owner-approved standing question queue
(`AGENDA_QUEUE_SPEC.md` §5, §6, §9 item 2; owner's prompt of 7 Sept, six
items, one commit each): the pure module of slice 1 is now the thing Alba
asks from. Every commit had the full suite green before it
(`AUTO_MODE_ENABLED=false uv run pytest`). `AUTO_MODE_ENABLED` is
untouched and `.env` reads `false`; `PHASE_7C_EVAL_PREREG.md`, `help/`,
`vendor/` and `OPEN_CLOSED_RULE.md` untouched. **Needs a restart to be
live** (the owner's act) — and it is live only behind the flag: with the
flag down `entry["auto"]` is `None`, no queue exists, and nothing in
this slice runs. The bare-minimum-of-slice-4 tap handling and the
slice-5 cadence pin were pulled forward as the prompt asked.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `2a7910c` | one `AgendaQueue` per auto session; every pass that lands while the machine is on merges; `auto.queue_merged` with the counts | 1025 → 1028 |
| 2 | `46b2bb0` | Alba asks from the queue head, consumes by id, marks answered at the turn end; the queue is the asked-memory (slice-3 list retired); `requeue`/`drop` in the module | 1028 → 1033 |
| 3 | `346809d` | asking does not wait for the pass; the three empty rules; `AUTO_STRICT_REVISE` re-meant (`.env.example`, 7c D2 and §9, queue §4) | 1033 → 1038 |
| 4 | `6913ed8` | the doctor's tap and the queue (D-E, the minimum): a pending match is consumed by tap, a novel tap is `add_asked`; the RESUME-from-head pin | 1038 → 1042 |
| 5 | `4eca095` | the number to beat on every question: `turn_end_to_issue_ms` on the row, `auto.question_latency` at `speak_started` | 1042 → 1043 |
| 6 | (this commit) | `AGENDA_QUEUE_SPEC.md` §2, §5, §6, §7, §9 truth-ups; this entry | 1043 |

Final suite: **1043 passed** (from 1025 at `59a2244`). Every commit
message carries the why; this entry carries the decisions and the seams.

**What is now live behind the flag.**

- One queue per session, in the auto dict (`auto["queue"]`), built from
  `AUTO_QUEUE_MAX`, `AUTO_QUEUE_ABSENT_PASSES` and
  `AUTO_TOPIC_MATCH_THRESHOLD`; the two queue numbers now sit in the
  per-run thresholds record (`auto.enabled`). In `maybe_run_cds` every
  pass that lands and is versioned merges into it while the machine is
  on (`_auto_on`: not OFF, HANDOVER, TAKEN_OVER — so PAUSED merges, and
  the alarm-bearing pass has merged before RESUME asks). The merge is
  synchronous and precedes the alarm handling; its audit rows are
  written after the alarm so the pause is never delayed by the record.
- The ask: `_plan_from_queue` takes the head, runs the topic call (cone
  unchanged, the topic stored on the item) and pre-synthesis, and
  remembers the item id in the plan; `_issue_queued` consumes THAT item
  by id before the slot is taken (requeued if the issue fails); the
  answer's turn end (`_end_turn`, answer, the F5 rule) marks it
  answered. `asked_answered`, `asked_open` and `auto.reask_suppressed`
  are gone; the guarantee is the merge's discard.
- Asking does not wait for the pass: `_request_revision` at a turn end
  requests the full pass (strict) AND plans from the head in the same
  call; `_ask_after_pass` (landed and runaway paths) hands over when
  nothing is pending after a post-answer merge, plans if the turn had
  already ended, and otherwise leaves the plan to that turn's end. The
  bridge encourager fires only with nothing to ask.
- The tap: a pending match → `consume(by="tap")`; no match →
  `add_asked` (new, audited `auto.queue_asked_externally`); a re-tap of
  the asked (aborted) item is awaited. The guard and the tapped handover
  are as slice 3 left them.
- The numbers: `turn_ended_at` at every turn end that can permit an ask
  (answer, golden exit, hand-back); `turn_end_to_issue_ms` in the
  question's detail (row `ref_detail` and `speech.requested`);
  `auto.question_latency` at the client's `speak_started` with
  `turn_end_to_issue_ms`, `issue_to_speech_ms`, `turn_end_to_speech_ms`.
  The speech pipeline DOES expose the far end — `speak_started` is the
  client's report of actual playback start, the same message that opens
  the exclusion window — so both numbers are on the record; nothing was
  left to "where it would come from".

**What is not (the slices ahead).**

- No re-ranker (slice 3): the head after a merge is the baseline order.
- The panel still shows the assessment's `questions_to_ask`, not the
  queue (slice 4): the panel and the queue can differ — a question the
  doctor sees may be asked or dropped in the queue; a tap on it is
  handled as above. `snapshot()` is ready and unused.
- No cadence (b) flag (slice 5); (a) is what `AUTO_STRICT_REVISE=true`
  now means, pinned by the one-pass-per-answer test.
- No GPU discipline (slice 6), no speculative pass (slice 7).

**Where the prompt or spec did not fully decide, and what the code
does — for the owner and Cowork to confirm or overrule:**

- **"Created when auto mode is enabled" was read as the flag, not the
  toggle.** The queue is built with the auto dict (which exists exactly
  when `AUTO_MODE_ENABLED` is true) and lives for the session, across a
  toggle off and on, because it is also the asked-memory: a question
  asked in an earlier run of the same session must still be asked. A
  pass landing while the machine is OFF (toggle) does not merge —
  pinned. Consequence: questions the CDS proposed BEFORE the doctor
  switched auto on are not in the queue; the first ask after the golden
  exit then comes from the exit's own pass (the empty rule), as it did
  before the queue. Seeding the queue from the current agenda at
  toggle-on is a one-line alternative if the owner prefers it.
- **The golden exit and a hand-back ask from the queue at once** when
  it has items merged during the golden minutes (spec §5 names only
  answered turn ends). Under the flag the pass is requested too.
- **A pass landing mid-turn plans nothing**; that turn's end plans from
  the head (`_ask_after_pass`). Chosen over planning at the merge so
  that (i) nothing shows as "queued" on the indicator while the patient
  is still answering, and (ii) slice 3's re-rank, which runs at the
  answered turn end, sees the head before the topic call — a plan made
  at the merge would bypass it. Cost: topic call + synthesis (~1–2 s)
  after the turn end instead of ~0. The 486 baseline is 27.7 s.
- **A turn end with nothing asked and nothing queued plans from the
  head** (the non-answer branch of `_end_turn`, question phases only,
  not during the handover sequence). Without it the exit's pass landing
  mid-speech left nobody to plan when that speech ended — the bridge
  test found it.
- **The politeness abort requeues the item at its rank AND keeps the
  prepared plan** (the audio is cached); re-issue consumes it again
  (two `auto.queue_consumed` rows, one `queue_requeued`, one
  `queue_answered`). The "not the same words twice in a row" rule is
  kept in `_plan_from_queue`: when the head's text was the last asked
  and another item is pending, that one is planned. Under the queue it
  fires only when a plan is made anew after an unanswered ask (e.g.
  after a pause cut the aborted-and-requeued question); the re-issue of
  a kept plan is not a plan and is exempt, as the abort test pins.
- **A question cut by an urgency pause stays ASKED** (never re-asked)
  and no answer is awaited for it (`_cancel_officer` clears
  `asked_item_id`); it is not requeued. The old code left `asked_open`
  set across a pause and the next answer credited it; this is the
  cleaner reading and is the place to repin if the owner wants a cut
  question asked again.
- **RESUME AUTO with nothing pending hands over** (the spent-agenda
  rule), rather than requesting a pass — the owner's no-revision-at-
  resume decision outranks the empty rule there.
- **`add_asked` records a tapped question with the panel version it
  was tapped from** (`first_version`), rank −1, never in the order.
  An already-answered question the doctor taps again is theirs to ask
  and is recorded nowhere twice.
- **The queue item's words are resolved for the whitelist** through
  `_agenda_ref`: the pass that last listed it (exact text, else that
  pass's own normalised-equal wording — spoken as that version's
  question verbatim), then the pass that first proposed it; both aged
  out of the 20-version log cannot happen while D-A holds, and if it
  did the item is `drop`ped (new module operation, audited
  `auto.queue_dropped` with the reason) and the next head taken.
- **`turn_end_to_issue_ms` is measured to the decision to speak**, with
  one clock reading, so `issue_to_speech_ms` (synthesis + transport)
  plus it equals `turn_end_to_speech_ms`. The F5 re-ask and the fixed
  phrases carry no number.
- **Tests repinned by decision** (each docstring names it): the 486
  risk-factors test, the cone-collapse test and the spent-agenda test
  read the merge's discards instead of `auto.reask_suppressed`; the
  strict-off test and the two runaway tests land their "agenda in
  hand" as a pass in the golden minutes (a `seed_agenda` is a panel the
  machine never saw land and is NOT in the queue); the strict-revise
  test's docstring says what it still pins; its row-equality pops the
  new timing field. Nothing weakened or deleted. Harness: `land_pass`
  (a pass on transcript growth) in `tests/auto_harness.py` and the
  question file's own copy.

**Findings not changed here (the owner's call):**

- **The cone's topic matcher conflates "your X" topics.** With the E3
  normaliser "your" is not a stop word, so `action_similarity("your
  tablets", "your sleep")` = 0.636 ≥ `AUTO_TOPIC_MATCH_THRESHOLD`
  (0.6): once sleep has been opened, the tablets question is asked
  verbatim rather than open-form. A slice-3 property, seen while
  building the empty-rule test (which sidesteps it with "the tablets").
  Adding "your"/"my" to `ACTION_STOP_WORDS`, or a higher topic
  threshold, are both one-line changes; which, and whether, is the
  owner's.
- **The pause tests' `_fire_pass` helper assumes the landing branch
  completes within one tick** after the engine returns. Placing the
  merge's audit writes before the alarm handling broke three of them
  (the alarm then landed a tick late); moving the writes after the
  alarm restored them. The helper is the fragile thing, not the
  behaviour; noted for whoever next adds an await to that branch.

**`help/`: NOT edited. Sentences the queue makes untrue or incomplete,
quoted, for the owner's wording** (nothing on the page changes until
slice 4, so these are about what the text now claims of the mechanism):

- `help/01-a-consultations-journey.md` §2: "Each update *revises* the
  previous one under rules: condition names stay put, reasoning must
  absorb new evidence, answered questions drop off the list." — still
  true of the assessment's own list; incomplete for auto mode, where
  the list the machine asks from is now a standing queue that the
  passes merge into, an asked question is removed by construction, and
  a question the pass keeps after it was answered is discarded rather
  than asked again.
- `help/01-a-consultations-journey.md` §3: "the app can conduct the
  history-taking itself, inviting, encouraging and asking questions of
  its own choosing" — incomplete: its choosing is now the head of a
  queue that every CDS pass feeds and that never re-offers an asked
  question; and the diagram participant "Doctor taps — or auto mode
  plans — a question" is still true.
- `help/02-using-it-step-by-step.md` step 5: "**Questions to ask.**
  Suggestions that update as the conversation moves. Tap the small
  speaker icon and the assistant asks that question aloud" — still true
  of the panel (it shows the assessment's list until slice 4); now
  incomplete: with auto mode on, tapping a question also takes it off
  the assistant's own queue, and the assistant will not later ask a
  question the doctor has tapped.
- `help/02-using-it-step-by-step.md` step 3: "The transcript streams
  in, questions come and go as they are answered" — true of the panel;
  for the assistant's own asking the truthful sentence would add that
  it asks the next question as soon as the patient finishes, without
  waiting for the assessment to revise (the revision still runs on
  every answer).
- `help/02-using-it-step-by-step.md` step 3: "it invites, listens,
  encourages and asks aloud, one question at a time, while you
  supervise" — still true.
- `help/04-the-architecture.md`: "the two small judgements that pace
  the spoken interview: has the patient finished speaking, and what a
  question is about" — still true for this slice; becomes three with
  slice 3's re-ranker.

**The slices ahead (spec §9):**

3. Re-ranker — the stateless call in the affect/topic shape after each
   answered turn end (before the topic call: the slot is the answered
   branch of `_end_turn`, ahead of `_plan_from_queue`), D-B's context
   (`AUTO_RERANK_CONTEXT_TURNS`, capped by characters),
   `AUTO_RERANK_TIMEOUT_S` fail-soft to the current order
   (`auto.rerank_failed`), skipped while a full pass is in flight (D-F),
   `apply_rerank` with its no-invention guard, audited
   `auto.queue_reranked`. `help/04`'s "two small judgements" then wants
   the owner's third.
4. Panel and taps — the questions-to-ask panel shows `snapshot()`
   (pending in order, asked struck through, dropped hidden and
   expandable); a tap on a queue item consumes it (the tap path already
   does; the panel's references change from version+index to item id
   or stay as they are); the preparing state covers re-rank plus
   synthesis. `help/01` §2/§3 and `help/02` step 5 for the owner's
   wording.
5. Cadence flag (D-C (b): full pass every second answer, re-rank every
   answer) and the pin that the urgency check runs on its own call at
   every answered turn whatever the cadence (today it is inside the
   pass; under (b) it needs its own call on the off answers); HANDOVER,
   `PHASE_7C_SPEC.md` §5, §6, §9 truth-ups, `help/` flags.
6. GPU discipline (§7a, D-G) — `model.call` audit (kind, queued_ms,
   run_ms, tokens, outcome); the resident live set as an invariant with
   `model.load_during_live`; the priority scheduler (urgency, then the
   short conversational calls, then the full pass, then speculation);
   the second Ollama slot as a measurement experiment only.
7. Speculative pass during the patient's answer, behind a flag, once
   the queue's own effect is measured — `auto.question_latency` now
   gives the per-question number; the next solo run's mean against
   27.7 s is the measurement.

**Watch list, carried forward:** the CDS reading its own parenthetical
literally is now harmless to the flow (discarded at the merge) but
still shapes what the model believes; D10 (the politeness abort) is
still unexercised in the room — and now moves a queue item, so the
next abort in a real run is worth reading in the trail; banner
visibility; the felt length of the 90 s window.

## Standing question queue — slice 3 of 7, the re-ranker, built (2026-09-08)

**What landed.** Slice 3 of the owner-approved standing question queue
(`AGENDA_QUEUE_SPEC.md` §3, D-B, D-F, §7, §9 item 3; owner's prompt of
8 Sept, six items, one commit each), plus the two owner decisions of
8 Sept taken from slice 2's findings. `AUTO_MODE_ENABLED` is untouched
and `.env` reads `false`; `PHASE_7C_EVAL_PREREG.md`, `help/`, `vendor/`
and `OPEN_CLOSED_RULE.md` untouched. **Needs a restart to be live** (the
owner's act) — and, as with slice 2, live only behind the flag: with the
flag down `entry["auto"]` is `None` and nothing here runs. The stop-word
change (item 2) is in the shared normaliser, which only auto mode and
the queue read.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `99022a9` | the queue is seeded from the current agenda at toggle-on (owner decision 2026-09-08); `auto.queue_merged` with `seeded: true` | 1043 → 1046 |
| 2 | `10523d5` | possessives are stop words (owner decision 2026-09-08); the two-topic pin; every ratchet test unchanged | 1046 → 1047 |
| 3 | `7166bca` | `CDSEngine.rerank` — the call in the topic call's shape, schema, prompt, excerpt builder, `AUTO_RERANK_MAX_TOKENS` and `AUTO_RERANK_MAX_CHARS`; 19 stubbed-chat tests | 1047 → 1066 |
| 4 | `e8d6753` | the wiring: after each answered turn, fail-soft, the no-invention guard, the race; `auto.queue_reranked`, `auto.rerank_failed`, `auto.rerank_skipped`, `model.call` | 1066 → 1072 |
| 5 | `6776250` | GPU priority, the minimum: the pin that a re-ranker call is never issued while a pass runs, and every call is a `model.call` row | 1072 → 1073 |
| 6 | (this commit) | `AGENDA_QUEUE_SPEC.md` §1, §3, §7, §9 and `PHASE_7C_SPEC.md` §6, §7, §9, §10, §11, §12 truth-ups; this entry; `help/` flags | 1073 |

Final suite: **1073 passed** (from 1043 at `473daea`), run as
`AUTO_MODE_ENABLED=false uv run pytest`. Commits 1–3 are independent and
were verified by their own files each and by one full run with all
three in the tree (1066); commits 4 and 5 each had their own full run
green before them. Every commit message carries the why; this entry
carries the decisions and the seams.

**The two owner decisions, restated (2026-09-08):**

1. **Seed the queue at toggle-on.** When the doctor switches auto mode
   on and the current agenda already holds `questions_to_ask`, they are
   merged into the queue at once as a pass with the current agenda
   version, so the first ask after the golden exit comes from the
   queue's head and does not wait for the exit's own pass. An empty
   agenda at toggle-on is a no-op. The queue still lives for the session
   across a toggle off and on as the asked-memory (slice-2 decision,
   kept): the seed's copy of an asked question is discarded like any
   pass's, so asked stays asked.
2. **Possessives and articles are stop words.** your, my, his, her,
   their, our, its join `ACTION_STOP_WORDS` (the articles were already
   there). "your tablets" and "your sleep" now share no token (0.0; it
   was 0.636, above the 0.6 topic threshold, so the tablets were asked
   verbatim once sleep had been opened). The normaliser is shared by
   the ratchet, the queue's exact match and the cone: the whole suite
   was re-run and every existing ratchet test is unchanged — the 485
   pairs still score 0.64 and 0.778; no threshold arithmetic moved.

**What is now live behind the flag (after a restart).**

- The toggle seeds the queue (`_seed_queue`, after `ctl.enable()`).
- After each ANSWERED turn end in the question phases, if at least two
  items are pending and no full pass is in flight, `CDSEngine.rerank`
  runs on the pending (id, text) pairs and the committed turns since the
  last LANDED pass (at most `AUTO_RERANK_CONTEXT_TURNS`, cut to
  `AUTO_RERANK_MAX_CHARS` from the front), and **the next ask is planned
  after its verdict** — the head Alba asks next is chosen after what the
  patient just said. Bounded by `AUTO_RERANK_TIMEOUT_S` (2 s) with
  `AUTO_RERANK_MAX_TOKENS` (200) as the cap; a timeout, error, cap hit or
  malformed reply leaves the order standing (`auto.rerank_failed`; a cap
  hit is also `cds.runaway`). The verdict is applied through
  `AgendaQueue.apply_rerank`: pending items only, unknown ids ignored and
  listed (`auto.queue_reranked`: before, order, drops with the
  re-ranker's one-word reasons, ignored, unmentioned, ms, excerpt size,
  the protected item). A drop marks the item dropped; it re-enters
  afresh if a later pass raises it (slice-1 decision).
- A pass in flight at the turn end (D-F): no call, `auto.rerank_skipped`
  with `reason: pass_in_flight` and the version the pass will land as,
  and the ask is planned from the head at once, as slice 2 left it. No
  committed turn since the last landed pass: skipped, `no_new_turns`.
  One pending item: nothing to order, no call, no row.
- Every re-ranker call is `model.call` (shape below). The four re-rank
  settings are in the per-run thresholds record (`auto.enabled`).
- The indicator's "preparing" state and the guarded tap's "planned"
  both count a re-rank in flight; a doctor's tap, an urgency pause, auto
  off and a handover cancel it (the tap's answer re-ranks afresh).

**The race, and how it is handled** (the prompt asked for this here).
By design nothing is planned when the verdict lands, because the plan
waits for it. Three things can still plan a question while the call is
out: the full pass requested at the same turn end landing first (a fast
pass, a slow re-rank) — its merge supersedes the verdict (D-F's own
logic) and `_ask_after_pass` plans from the merged head at once; a
doctor's tap that consumed an item (which also cancels the re-rank);
RESUME AUTO planning from the head. When the verdict then lands, the
planned item is **protected**: removed from the drops and put first in
the order, so the verdict shapes the rest of the queue and never
displaces a question whose words may already be audio; the row carries
`protected` and `protected_dropped_by_verdict`. A late verdict computed
on the pre-merge pending set still applies to the post-merge queue: ids
are stable, and items it never saw are "unmentioned" and keep their
order after the ones it named. One seam found by the full suite: the
first cut wrote the `model.call` row BEFORE applying the verdict, and
under the suite's slower database the pass landed inside that await and
planned the un-re-ranked head. The verdict is now applied and the plan
made in the same step the call returns, and the audit rows are written
after — the slice-2 pattern (merge before alarm, rows after). A test
pins the race with the pass gated to land mid-re-rank and a verdict
that would have dropped the planned item.

**Where the prompt or spec did not fully decide, and what the code
does — for the owner and Cowork to confirm or overrule:**

- **The plan waits for the verdict.** "The re-ranker must not delay the
  ask" could be read two ways: (A) re-rank, then plan — the ask is held
  by at most the timeout; or (B) re-rank and plan in parallel — the
  verdict only ever shapes the question after next. Built (A), because
  spec §6 says the preparing state "covers re-rank plus synthesis",
  slice 2 placed the re-rank "before the topic call", and under (B) the
  immediate next question could be one the patient has just addressed —
  the thing the re-ranker exists to prevent. The cost is on the number
  to beat: `turn_end_to_issue_ms` now includes the re-rank (~1 s warm,
  2 s at worst) before the topic call; the 486 baseline is 27.7 s. If
  the owner prefers (B), the change is one line in `_request_revision`
  (plan first, then start the re-rank) and the protection logic already
  handles the verdict landing on a planned item.
- **The skip is its own row** (`auto.rerank_skipped`), chosen over a
  field on the next `auto.queue_reranked` row, which might never come.
- **The pass requested at the same turn end is not held back** for the
  re-ranker: it launches on the next tick, so on Ollama's single slot
  the two calls queue re-ranker first. The re-ranker is therefore never
  behind a pass, but the pass is behind the re-ranker by ~1 s. A
  scheduler with teeth is slice 6.
- **"Since the last full pass landed"** is the transcript parts after the
  count recorded when that pass was LAUNCHED (what it actually saw); a
  failed (runaway) pass does not move the mark.
- **A re-ranker drop does not stick under cadence (a).** Every answer's
  pass may re-propose a just-dropped question, which re-enters as a new
  item (slice-1 decision, unchanged); the drop's practical effect is on
  the ask planned at that turn end, which is the ask that matters. If
  the owner wants drops to hold, the alternatives are the slice-1 one (a
  re-ranker drop treated like answered — extending the never-re-enter
  guarantee to a model's judgement) or a dropped-by-re-ranker memory for
  N passes. To read in the first run's `auto.queue_reranked` and
  `auto.queue_merged` rows before deciding.
- **The reason is held to one word in code** (`cds.one_word`: the first
  alphabetic word, lower case; "addressed" when there is none), whatever
  the model writes.
- **`apply_rerank`'s `before`** now records the order the verdict was
  applied to, drops included; it was read after the drops had left the
  order (the module test's case had no drops, so nothing was pinned
  wrongly).
- **`AUTO_RERANK_TIMEOUT_S` moved** from `app/main.py` to `app/cds.py`,
  where the call is, like the topic timeout; `AUTO_RERANK_CONTEXT_TURNS`
  and `AUTO_RERANK_MAX_CHARS` stay with the wiring that builds the
  excerpt. `AUTO_RERANK_MAX_TOKENS` (200) and `AUTO_RERANK_MAX_CHARS`
  (1500) are UNCALIBRATED GUESSES, marked so in `.env.example`.
- **Tests repinned by decision** (each docstring names it): the D-E
  "novel tap" test's never-held question now comes from an older
  version the seed did not take (the current agenda IS held from the
  toggle); the slice-2 "planned at the turn end" assertion accepts the
  re-rank task as the plan's first step (the pass is still held and the
  question still asked with it in flight); the slice-2 one-pass-per-
  answer pin is extended, not changed (the urgency check still runs
  exactly once per answer; the re-ranker once beside it). Nothing
  weakened or deleted. Both scripted engines gain `rerank()` with
  scripted verdicts and a gate.

**The `model.call` shape** (`AGENDA_QUEUE_SPEC.md` §7a; the re-ranker
first, every call in slice 6): `kind` (`rerank` now; `officer`, `topic`,
`assessment`, `urgency`, `affect` to follow), `queued_ms` (from the
decision to call to the request leaving — 0 until slice 6's scheduler
holds calls back), `run_ms` (the server's own total for the call when it
reports one — Ollama's `total_duration` — else the HTTP round trip),
`elapsed_ms` (the round trip), `tokens` (`{prompt, output}` from
`prompt_eval_count` / `eval_count`, or null), `outcome` (`ok | timeout |
cap | malformed | error`) with `failed` (the reason) when not ok,
`model`, `pass_in_flight` (whether a full pass held the slot when the
call was issued — false for the re-ranker by construction), the session
and `at_audio_s`. `CDSEngine._chat` now wraps `_chat_raw`, which returns
the reply and this metadata, so the other calls can be moved onto the
row without touching their prompts.

**`help/`: NOT edited.** The sentence this slice makes untrue, and the
sentences slice 2 flagged, all for the owner's wording after slice 4:

- `help/04-the-architecture.md`: "MedGemma 27B does the differential,
  the red-flag watch, the guideline summaries, the note and the letters
  — and, when auto mode is enabled, the two small judgements that pace
  the spoken interview: has the patient finished speaking, and what a
  question is about." — now three: the third is which of the waiting
  questions is still worth asking, and in what order, after each answer.
- `help/01-a-consultations-journey.md` §2: "Each update *revises* the
  previous one under rules: condition names stay put, reasoning must
  absorb new evidence, answered questions drop off the list." — still
  true of the assessment's own list; incomplete for auto mode (slice 2).
- `help/01-a-consultations-journey.md` §3: "the app can conduct the
  history-taking itself, inviting, encouraging and asking questions of
  its own choosing" — incomplete: its choosing is the head of a standing
  queue that every pass feeds, re-sorted after each answer (slice 2, and
  now the re-ranker).
- `help/02-using-it-step-by-step.md` step 5: "**Questions to ask.**
  Suggestions that update as the conversation moves. Tap the small
  speaker icon and the assistant asks that question aloud" — still true
  of the panel; incomplete for the tap's effect on the queue (slice 2).
- `help/02-using-it-step-by-step.md` step 3: "The transcript streams
  in, questions come and go as they are answered" — true of the panel;
  the assistant's own asking no longer waits for the assessment (slice 2).
- `help/02-using-it-step-by-step.md` step 3: "it invites, listens,
  encourages and asks aloud, one question at a time, while you
  supervise" — still true.

**The slices ahead (spec §9):**

4. Panel and taps — the questions-to-ask panel shows `snapshot()`
   (pending in order, asked struck through, dropped hidden and
   expandable — a re-ranker drop with its reason now among them); a tap
   on a queue item consumes it (the tap path already does); the
   preparing state covers re-rank plus synthesis (the indicator already
   counts the re-rank). `help/01` §2/§3, `help/02` step 5 and `help/04`
   for the owner's wording.
5. Cadence flag (D-C (b): full pass every second answer, re-rank every
   answer) and the pin that the urgency check runs on its own call at
   every answered turn whatever the cadence. Under (b) the re-ranker's
   drops would hold for a whole answer, which is where its value should
   show; the measurement is the next solo run's
   `auto.question_latency` against 27.7 s.
6. GPU discipline (§7a, D-G) — `model.call` for every call (the shape
   above); the resident live set as an invariant with
   `model.load_during_live`; the priority scheduler (urgency, then the
   short conversational calls — officer, topic, re-ranker — then the
   full pass, then speculation), which is where `queued_ms` becomes a
   number and the pass stops queuing behind nothing; the second Ollama
   slot as a measurement experiment only.
7. Speculative pass during the patient's answer, behind a flag, once
   the queue's own effect is measured.

**Watch list, carried forward and added:** the re-ranker's judgement —
read every `auto.queue_reranked` row of the first solo run against the
transcript (does it drop what was addressed, and only that?), which is
`evals/` material, not a unit test; the added second on the number to
beat (`turn_end_to_issue_ms` now includes the re-rank — compare against
slice 2's per-question rows); the two uncalibrated guesses (`AUTO_RERANK_
MAX_TOKENS`, `AUTO_RERANK_MAX_CHARS`); the CDS reading its own
parenthetical literally (harmless to the flow; the re-ranker's prompt
now carries the lesson explicitly for the pending questions); D10 (the
politeness abort) still unexercised; banner visibility; the felt length
of the 90 s window.

## Pilot diagnostic — consultations 487–490, 9 Sept 2026: the first real-actor runs and the queue's first outing (REPORT ONLY, 2026-09-09)

**A report exists**, outside the repository:
`~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_487-490_2026-09-09.md`
— 487 (cafe, two real voices, auto never enabled), 488 (cafe, the enable
and the countdown), 489 and 490 (the flat, script 01 solo, slice-3 code
live at `6e24542`). What it shows: the owner's role hypothesis does not
hold — 488's auto disclosure was issued and **politeness-aborted at
0.031 RMS against the absolute 0.02 floor**, and an aborted enable
disclosure is never re-issued (G1); the cafe never gave 5 s of quiet, so
the countdown reached 0 once and the one "reset" was the owner's own
toggle (G2, G12); the number to beat is **3.0 s mean turn end → Alba
speaking** against 27.7 s (target met), but the patient waits ≈ 11.6 s
from the last word — the 5 s rule, ≈ 3 s of unrecorded trailing energy
above the floor, and ≈ 3 s of preparation of which 2 s is the topic
call's timeout, lost to the pass on 9 of 10 questions (G4, G6); a fresh
quiet span whose first report equals the previous span's last is
invisible to the server, which re-asked an answered question (G3); the
re-ranker was skipped while a pass was in flight and a question the
patient had answered was asked (G5), and its one verdict dropped the
wrong item, which re-entered on the next pass and was asked; the halving
simulation (2.5 s cuts two answers of nine on the transcript reading,
3.5 s one, neither on the RMS reading) with a recommendation to record
the reporter's span first; and the record does not know the machine or
microphone beyond the sound check's output-device label (G10). Candidate
defects G1–G14 with file:line at `6e24542`; nothing in code, tests,
config, flags or the database changed. Docs-only commit; the suite was
not run for it.

## Pilot fix slice 4 — the owner's eleven decisions after consultations 487–490, built (2026-09-09/10)

**What landed.** The eleven items of the owner's decisions of 9 Sept 2026
(report `~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_487-490_2026-09-09.md`,
findings G1–G14; prompt `~/Downloads/cc_prompt.md`), one commit each, the
full suite green before every commit (`AUTO_MODE_ENABLED=false uv run
pytest`), spec truth-ups in the same commit as the code they describe.
`AUTO_MODE_ENABLED` is untouched and `.env` reads `false`;
`PHASE_7C_EVAL_PREREG.md` untouched (the golden window stays 90 s, the
metric-3 zero point unchanged); `help/`, `vendor/`, `OPEN_CLOSED_RULE.md`
untouched. **Needs a restart to be live** (the owner's act) — and live
only behind the flag, as before.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `7c57618` | G1: a cut-off enable disclosure is retried on the next quiet report, then the machine switches itself off (`too_loud_to_start`); the enable never reports success before the disclosure has played (`starting`) | 1073 → 1077 |
| 2 | `ee7f8cb` | G2: the floor comes from the room — `noise_floor_rms × 3.0`, clamped [0.02, 0.08], per session from the doctor's newest sound check; the flat stays at exactly 0.02 | 1077 → 1087 |
| 3 | `5c7f01e` | G4/G5: the re-ranker and the topic call before the pass (held ≤ 4 s); the re-ranker runs with a pass in flight and with one pending item; a `model.call` row for every pass | 1087 → 1089 |
| 4 | `6e0f4e0` | D1 extension: the topic call returns `lay`; Alba speaks it for a verbatim ask; the original stays the identity; the subject guard (≥ 0.3) | 1089 → 1108 |
| 5 | `622f93a` | Golden encouragers every 4 s of quiet, `go_on`/`tell_me_more_short` alternating, the window ends early after two unanswered | 1108 → 1110 |
| 6 | `363b3eb` | `let_me_think` replaces the bridge; the empty-queue rule as restated; `AUTO_ENCOURAGER_QUIET_S` retired | 1110 → 1112 |
| 7 | `728ecba` | G6: `AUTO_EOT_FALLBACK_S` 3.5, `AUTO_EOT_QUIET_S` 2.0; quiet reports audited (bounded); an RMS trace on every `auto.turn_ended` | 1112 → 1116 |
| 8 | `a85a4df` | G3: the client numbers its spans; the server keys the fresh-span test on the number | 1116 → 1118 |
| 9 | `c1dfec1` | G7: the issue waits for the pre-synthesis (≤ 2 s), then falls back and audits; G8: the re-ask's latency row is marked `reask` with only issue → speech | 1118 → 1121 |
| 10 | `fdd8085` | G9: a tap in GOLDEN is recorded in the queue and answered at the exit; G10: `auto.enabled.client` — user agent, platform, input label, the sound check's two labels | 1121 → 1124 |
| 11 | (this commit) | this entry; `help/` flags | 1124 |

Final suite: **1124 passed** (from 1073 at `de36a0e`). Every commit
message carries the why; this entry carries the seams and the decisions
the owner's text left open.

**What is live after the restart (behind the flag).**

- *The enable.* The auto disclosure (or chained invitation) is an
  "enable chain": a politeness abort is retried on the next quiet report
  (`auto.enable_retry`, attempt and RMS), at most `AUTO_ENABLE_RETRIES`
  (3) attempts in all inside `AUTO_ENABLE_RETRY_WINDOW_S` (30) of the
  first issue; spent → `auto.disabled` reason `too_loud_to_start` with
  RMS, floor and attempts, and the pill told "Too loud to start: 0.031
  against 0.020". The echo at issue is `auto_toggled on starting=true`
  ("Auto: starting…"); the on-echo follows the disclosure's completion.
- *The floor.* `speech.auto_floor` at session start from the newest
  `speech.sound_check` row for the doctor; sent as
  `speech_config.auto.floor`; one number on the page for the reporter
  and the politeness abort; on `auto.enabled` (floor, noise_floor_rms,
  margin, floor_source, floor_clamped, sound_check_age_s) and every
  `speech.politeness_abort` row. Cafe → 0.0255; flat → 0.02; no check →
  0.02 with `floor_source: no_sound_check`.
- *The turn end.* Re-rank → topic call → (pass launches; `auto.pass_held`
  when it waited; `queued_ms` on the pass's `model.call` row, kind
  `pass`) → the ask. The re-ranker runs with a pass in flight
  (`pass_in_flight: true` on its row) and with one item pending;
  `auto.rerank_skipped` keeps only `no_new_turns`.
- *What Alba says.* A verbatim ask is spoken in the topic call's `lay`
  wording when it passes the guard (`lay_similarity` on the row;
  `spoken` and `lay` beside the original on `auto.queue_consumed`;
  `auto.lay_rejected` on a miss, verbatim spoken). In GOLDEN an
  encourager every 4 s of quiet (from the later of the patient's last
  speech and Alba's own phrase end), alternating, one per span; after
  two unanswered the next silence ends the window early
  (`auto.golden_window_ran` reason `unanswered_encouragers`). In the
  question phases "Let me think for a moment." once per wait
  (`auto.thinking`, reason `empty_queue` | `slow_preparation`), never
  the bridge; it does not restart the client's span.
- *The record.* `auto.quiet_report` (bounded: the first of each span,
  then ≤ 1/s), the RMS `trace` on every `auto.turn_ended`,
  `auto.presynth_fallback`, `auto.question_latency.reask`,
  `auto.enabled.client`, `speech.sound_check.input_label`, `span` on
  every report.

**Build decisions taken where the owner's text was silent — for the
owner to confirm or overrule:**

- **G1 — what "AUTO_ENABLE_RETRIES (default 3)" counts.** Built as the
  total number of attempts, the enable's own issue being the first, so
  that "three aborts switch the machine off" holds at the default (the
  test the decision named). If the owner meant three *re-issues* (four
  aborts), the change is one comparison. The window is measured from the
  first issue of each chain step (disclosure, then invitation), not from
  the toggle; both steps retry.
- **G1 — reporting success.** The pill says "Auto: starting…" from the
  toggle until the disclosure has played through, because the client's
  quiet reporter must be armed for the retry to ride on its reports (an
  echo saying off would have left nothing to retry on). The
  already-disclosed enable (invitation only) keeps the plain on-echo.
- **G2 — no recency bound on the sound check.** The newest
  `speech.sound_check` row for the doctor is used whatever its age; the
  age is on `auto.enabled` (`sound_check_age_s`). A check from another
  room days ago would set that room's floor. A bound is the owner's
  number to set if wanted.
- **G4 — the hold applies to every pass launch while a short call is
  out**, not only the answered turn end's pass (a growth pass would hog
  the slot the same way); the officer is not yet scheduled (E4's
  deferral stands) and there is no urgency pre-emption — that remains
  slice 6 of the queue. `auto.pass_held` is written only when a pass was
  actually held (with a fast engine the short calls return inside one
  tick and no row is written). `hold_ms` counts from the moment the pass
  became due and was held, a tick after the short calls began, so it
  reads a little under the bound.
- **G4 — the pass's `model.call` row** carries `queued_ms` and
  `elapsed_ms`; `run_ms` and `tokens` are null until slice 6 gives the
  pass's three calls their own numbers. `version` is on pass rows only.
- **Lay wording — where it applies.** Only the verbatim ask; the
  open-form template ask is unchanged (its topic is already plain). The
  guard is enforced twice: in the wiring (audits `auto.lay_rejected`,
  speaks verbatim) and in `speech.resolve_utterance` as the last line (a
  drifting wording is *refused*, whatever the caller checked). This adds
  a fourth whitelist type, `LayUtterance` — an agenda reference plus a
  guarded wording, no standalone sentence slot; the hard-rule-1 surface
  test is repinned to say so. Spec §4 lists it as a fifth source.
- **Lay wording — one call.** The topic call's schema is now two
  required strings; a reply with a usable `lay` and an unusable `topic`
  still speaks the lay wording (the topic's failure only means no
  open-form ask). The similarity is the shared normaliser's token-set
  ratio; "Do you smoke?" scores 1.0 against itself and 0.3 is an
  uncalibrated guess — the next run's `auto.queue_consumed.spoken` and
  `auto.lay_rejected` rows are the calibration data.
- **Golden encouragers — "one per span".** "Every time the patient has
  been quiet for 4 s" is built as at most one encourager per client
  quiet span (the span restarts at the patient's speech and at Alba's
  phrase end, so the quiet is the span's own length); a politeness abort
  spends it, and the voice that aborted it begins the next span. The
  early end needs a *further qualifying silence* after the second
  unanswered encourager, on a fresh span; with the fallback at 3.5 s and
  the minimum quiet at 4.0 s the exit fires on that same report.
- **"Let me think" — "predicted to exceed".** Built as "has already run
  AUTO_THINK_THRESHOLD_S since the turn end with nothing ready": the
  preparation's worst-case bounds (re-rank 2 s + topic 2 s + synthesis)
  always exceed 3 s, so a true prediction would speak it at every turn
  end. `AUTO_ENCOURAGER_QUIET_S` is retired (it governed only the
  bridge). The phrase is not disclosure-gated (like the encouragers).
  "Never resets the quiet clock" is built on both sides: the client
  keeps its span across the phrase, and the server's judged turn end
  stands; the queued question issues on that span's next report.
- **G6 — the trace travels with every report** (~80 numbers at ≤ 1 Hz),
  not on request, so the `auto.turn_ended` row can carry it at the
  moment of the decision; the golden exit's turn end (in `auto.phase`)
  carries no trace. `AUTO_QUIET_REPORT_AUDIT_S` (1.0) is the bound the
  decision left unnumbered.
- **G3 — a report without a span** (an older page) keeps the old
  `quiet_s < last` test; the two other test harnesses (the golden and
  question files' own `Session` copies) still send no span and so
  exercise that fallback; the shared harness numbers its spans.
- **G7 — the wait blocks the receive loop** for at most
  `AUTO_PRESYNTH_WAIT_S` (2.0, an uncalibrated guess): the reports that
  queue behind it are handled when it returns. The alternative (skip
  this report, try the next) was cheaper on the loop and up to a second
  slower on the ask. `turn_end_to_issue_ms` is read after the wait.
- **G8 — the re-ask row is written, marked `reask: true`**, with only
  `issue_to_speech_ms`; the mean of `turn_end_to_speech_ms` excludes it
  by the mark (the decision allowed either).
- **G9 — several taps in GOLDEN** are all kept (`golden_tapped`) and all
  marked answered at the exit; the flow flags (`awaiting_answer`,
  `turn_ended`, `last_asked_text`) stay the question phases' — no answer
  is awaited in the golden minutes.
- **G10 — the user agent comes from the socket's headers**, the platform
  and current input label from the toggle message, the sound check's
  output and input labels from its row; nulls are recorded, not omitted.
- **Tests repinned by decision** (each docstring names it and the date):
  the one-tap start echo, the pill harness and standing-rules pin
  (`starting`); the two client floor pins and the config equality; the
  D-F skip test, the one-pending-item test, the never-behind-a-pass
  test, the race test (bound shortened), two `model.call` counts filtered
  by kind, the one-pass-per-answer pin extended; the topic call's schema
  and prompt-closing pins, the whitelist surface (four types); the
  minimum-quiet test (4.0), the one-per-window test (replaced by the
  repeated-encourager pin), the aborted-encourager tail, the
  encourager-id set, the phrase table, the pause file's
  across-a-pause encourager test; the bridge tests (four), the empty-
  rule-one test, the reporter's threshold keys; nine numeric pins on
  the old 5.0/3.0. Nothing weakened or deleted. Two harness robustness
  fixes: `live()` waits for the session entry (a pre-existing flake seen
  twice), and `probe()` plays a thinking phrase through and records it
  (`thinking_heard`), `play()` returning what the server said meanwhile.

**What the next run should be read for.**

- *The trailing energy.* Every `auto.turn_ended` row now carries `trace`
  (8 s at 100 ms, newest last) with `floor`: is the ≈ 3 s between the
  transcript's last word and the reporter's span start AGC recovery
  (energy decaying smoothly through the floor), a breath or chair
  (spikes), or the room? The `auto.quiet_report` rows give each span's
  start and `since`. This is what decides 3.5 s versus 2.5 s.
- *The lay wordings spoken.* `auto.queue_consumed.spoken` beside `text`
  on every ask, `lay: true`, and `lay_similarity` on the utterance row;
  every `auto.lay_rejected` with its score — the calibration data for
  `AUTO_LAY_MIN_SIMILARITY` (0.3), and the wordings themselves for the
  owner to judge (does the model add, narrow or widen?).
- *The floor chosen.* `auto.enabled` (floor, noise_floor_rms, margin,
  floor_source, the check's age) and every `speech.politeness_abort`
  (rms against floor): does 0.0255 let the cafe's disclosure play, and
  does the cafe's GOLDEN now see quiet spans at all?
- *The early window ends.* `auto.golden_window_ran.reason` — how often
  `unanswered_encouragers` ends the window, and after how many seconds
  (`golden_s`); against it, whether two encouragers into a quiet
  narrator cut a story short (the transcript around the end).
- *Also:* `auto.pass_held` (how long the pass waits, how often the bound
  releases it) and the topic call's timeout rate now that it goes first;
  `auto.thinking` (which reason, how often, and whether the phrase
  lands into a finished answer as the bridge did); `auto.enable_retry`
  and any `too_loud_to_start`; `auto.presynth_fallback` (whether 2 s is
  enough); the re-ranker's verdicts with `pass_in_flight: true` (does a
  late verdict ever displace a plan — `protected` on the row).

**`help/`: NOT edited.** Every sentence items 1, 4, 5 and 6 make untrue
or incomplete, quoted, with the sentences already flagged in slices 2
and 3 — all for the owner's wording in one sitting:

- `help/02-using-it-step-by-step.md` step 3: "If auto mode is enabled
  and switched on, the assistant takes the history instead — it
  invites, listens, encourages and asks aloud, one question at a time,
  while you supervise and can take over with one tap." — incomplete
  (items 1, 4, 5, 6): switching it on now says "starting" until the
  disclosure has been heard, and the assistant switches itself off if
  the room is too loud to start and says so; during the golden minutes
  it encourages every few seconds of quiet, with two phrasings, and
  begins its questions once two encouragements go unanswered; it asks
  its questions in plain English rather than the panel's clinical
  wording; and between questions it may say "Let me think for a
  moment." — that is not a question.
- `help/02-using-it-step-by-step.md` step 3: "The transcript streams
  in, questions come and go as they are answered" — true of the panel;
  the assistant's own asking does not wait for the assessment (slice 2).
- `help/02-using-it-step-by-step.md` step 5: "**Questions to ask.**
  Suggestions that update as the conversation moves. Tap the small
  speaker icon and the assistant asks that question aloud, in its own
  voice" — still true of a tap (a tap speaks the panel's wording, not
  the lay wording); incomplete since slice 2: with auto mode on, tapping
  a question also takes it off the assistant's own queue, and — item 10
  — that is so in the golden minutes too; and (item 4) when the
  assistant chooses the question itself it may speak a plain-English
  wording of it, with the panel's wording kept as the question's
  identity.
- `help/01-a-consultations-journey.md` §3: "if auto mode is enabled,
  the app can conduct the history-taking itself, inviting, encouraging
  and asking questions of its own choosing while the doctor supervises"
  — incomplete: its choosing is the head of a standing queue that every
  pass feeds, re-sorted after each answer (slices 2, 3); it asks in
  plain English (item 4); its encouraging in the golden minutes is every
  few seconds of quiet and ends the golden minutes early when
  unanswered (item 5).
- `help/01-a-consultations-journey.md` §2: "Each update *revises* the
  previous one under rules: condition names stay put, reasoning must
  absorb new evidence, answered questions drop off the list." — still
  true of the assessment's own list; incomplete for auto mode, where the
  list the machine asks from is a standing queue (slice 2).
- `help/04-the-architecture.md`: "MedGemma 27B does the differential,
  the red-flag watch, the guideline summaries, the note and the letters
  — and, when auto mode is enabled, the two small judgements that pace
  the spoken interview: has the patient finished speaking, and what a
  question is about." — now three judgements (slice 3: which waiting
  questions are still worth asking, in what order), and the second of
  them (item 4) also puts the question into plain English.
- `help/06-safety-by-construction.md` — no sentence made untrue: the
  lay wording is a new source of spoken words, bound to an agenda
  question and guarded in code; the article's claim that the browser
  can supply no words still holds. The owner may want a clause that the
  machine can now re-word a question, and how that is bounded.

**Watch list, carried forward and added:** the re-ranker's judgement
(now consulted far more often — every verdict of the next run against
the transcript, `evals/` material); the lay wordings (above); the felt
length of the window under the new encourager rule; D10 (the politeness
abort) now at the room's floor; banner visibility; the two uncalibrated
re-rank guesses; and the new uncalibrated numbers of this slice —
`AUTO_FLOOR_MARGIN/MIN/MAX`, `AUTO_LAY_MIN_SIMILARITY`,
`AUTO_SHORT_CALLS_HOLD_S`, `AUTO_THINK_THRESHOLD_S`,
`AUTO_PRESYNTH_WAIT_S`, `AUTO_QUIET_REPORT_AUDIT_S`, `AUTO_TRACE_S`.

## Pilot diagnostic — consultation 491, 10 Sept 2026: the first run with fix slice 4 live (REPORT ONLY, 2026-09-10)

**A report exists**, outside the repository:
`~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_491_2026-09-10.md`
— 491 (the flat, mlrig, herath, script 01 solo, `b50a720` live from the
04:42 restart; session `f728e221`, 04:45:30 → Stop 04:50:13). The owner's
four findings read against the record: (1) Alba never spoke the compound
heart-disease sentence — it is the panel's text; she asked "Can you tell me
more about heart disease risk factors?" and, twice, the lay sentence "Are
there any other things that might put you at risk for heart problems?";
(2) the eleven "Let me think" phrases were eight of them re-armed by Alba's
own voice through the microphone, and the queue was empty because the
re-ranker had dropped six of six items as "addressed", all wrongly (0 for 7
across 489–491); (3) nothing was interrupted — 18 utterances complete, no
politeness abort, two urgency pauses; energy of 0.023–0.032 RMS in the last
minute (source unrecorded) restarted the span thirteen times and silenced
Alba for 24 s; (4) MedGemma proposed as many areas as before, the re-ranker
removed them. The slice-4 mechanisms: G3, G4, G7, G8, G10, G11 closed on
this evidence (no topic timeout, five cache-hit issues at 21–36 ms, the
floor and the machine on the record); the enable retry, the encouragers,
GOLDEN taps and the re-ask were not exercised. **The trace answered G6**:
the ≈ 3 s of "trailing energy" after every answer was the transcriber's
commit latency restarting the reporter's span (2.1–3.7 s, mean 2.95 s), not
energy — the traces end within 0.3 s of the last word, abruptly. Candidate
defects H1–H4 with file:line at `b50a720`; calibration questions with their
numbers in §8. Nothing in code, tests, config, flags, prereg, help/, vendor/
or the database changed. Docs-only commit; the suite was not run for it.

- **H1** — "Let me think" re-arms itself: the phrase, heard by the mic at
  0.05–0.23 RMS, restarts the client's span as "speech" (`live.html:903`),
  the server clears the judged turn end (`main.py:4790–4795`), the 3.5 s
  fallback ends a turn with nothing asked and resets `think_used`
  (`main.py:4636`); period 5.1 s until the pass lands; the let_me_think
  exemption (`live.html:1687`) is on the playback-end path only.
- **H2** — the same lay sentence asked twice, 45 s apart, the second after
  its answer: q9 and q11 differ by ", family history", so the queue's
  identity (`agenda_queue.py:105–112`, `289–296`) sees two items and the
  topic call rendered both as one sentence, accepted at 0.539.
- **H3** — the quiet span starts at the transcript's arrival
  (`live.html:2705–2716`), 2.1–3.7 s after the last word: the whole of
  489/490's "trailing energy"; every answer waits ≈ 3 s longer than the rule.
- **H4** — a successful topic call writes no row (`main.py:3953–3963`): the
  three open-form asks' lay wordings, the compound question's among them, are
  not on the record; no `model.call` of kind topic; q12's text never surfaced.

## Pilot fix slice 5 — the owner's decisions after consultation 491, built (2026-09-10)

**What landed.** The five items of the owner's decisions of 10 Sept 2026
(report `~/Documents/Consultation-ai/Solo Pilot Documents/PILOT_DIAGNOSTIC_491_2026-09-10.md`,
findings H1–H4; prompt `~/Downloads/cc_prompt.md`) — the minimum so auto
mode works at a basic level before the repository goes public. One commit
each, the full suite green before every commit. The lay wording, the
compound question, the floor and the thresholds are v1.1 work and were
not touched. `.env` untouched (`AUTO_MODE_ENABLED=false`, and the new
flag is not in it); `PHASE_7C_EVAL_PREREG.md`, `OPEN_CLOSED_RULE.md`,
`help/`, `vendor/` untouched. **Needs a restart to be live** (the
owner's act) — and live only behind the flag, as before.

| # | commit | what | suite |
|---|---|---|---|
| 1 | `c113102` | H1: the machine must not hear its own voice as the patient — client meter guarded while our audio plays and 300 ms after; server reads a "speech" span that began inside our own utterance window as playback, `own_voice` on `auto.quiet_report` | 1124 → 1129 |
| 2 | `b7ed1d1` | the re-ranker re-orders only, never drops; `AUTO_RERANK_DROPS_ENABLED` (default false) guards the old path; `drops_advised` and `drops_enabled` on `auto.queue_reranked`; spec §3/§7 amended | 1129 → 1132 |
| 3 | `17ccb3c` | H3: the quiet span starts at silence — the reporter no longer restarts on a final or a changed partial (the nudge keeps both); `last_word_to_span_start_s`, `commit_latency_s` and friends on `auto.turn_ended` | 1132 → 1136 |
| 4 | `6ea5116` | the suite does not read the live `.env`: conftest pins `AUTO_MODE_ENABLED` off (environment and attribute) unless a test opts in; the three pre-7c speech stubs gain a no-op `presynthesise_phrases` | 1136 (green with `AUTO_MODE_ENABLED=true` in the environment and without, same count) |
| 5 | (this commit) | README § *Auto mode*; this entry | 1136 |

Final suite: **1136 passed** (from 1124 at `8728e6e`), and from this
slice on it is run plainly — `uv run pytest` — whatever the machine's
`.env` says.

**What is live after the restart (behind the flag).**

- *Our own voice.* The client's meter counts no energy as activity while
  `speaking` or in the 300 ms after `stopSpeaking` (`OWN_VOICE_TAIL_MS`,
  live.html); the playback-end path is as it was, so "Let me think" now
  really leaves the span running and every other utterance's end stamps
  `playback`. The server keeps each session's last eight utterance
  windows — `speech.requested` to the utterance's end (`speak_ended`,
  politeness abort, server cut, reconnect) plus `AUTO_OWN_VOICE_TAIL_S`
  (0.3) — and a fresh span stamped `speech` whose start (`now − quiet_s`)
  falls in one is read as playback: `turn_ended` stands, `span_seq` does
  not move, `awaiting_speech` and the golden unanswered count are
  untouched; the report row says `own_voice: true` with the utterance id
  (`false` on every other row).
- *The re-ranker.* `queue.apply_rerank(order, drops, apply_drops=False)`:
  the verdict's drops still pass through the module's no-invention guard
  (unknown ids listed as `ignored`), the known ones are returned as
  `drops_advised` (id, text, reason text) and none is applied. An advised
  item the order names keeps its place; one it does not name follows the
  named ones (`unmentioned`). The row carries `drops` (empty while off),
  `drops_advised`, `drops_enabled`; `auto.enabled` records
  `rerank_drops_enabled`. Nothing else about the re-ranker changed: it
  runs at every answered turn end, with one item pending and with a pass
  in flight, and the plan follows its order.
- *The span.* Keyed on energy and on our playback's end only. The nudge
  still resets on a final and a changed partial. Every quiet report
  records the span's start on the session clock (`auto["span_start"]`),
  every commit records `entry["last_final"]` (the last word's end, the
  audio time it was committed at, when), and every `auto.turn_ended` row
  carries `last_word_end_s`, `span_start_s`, `last_word_to_span_start_s`
  (span start minus last word; ≈ 3 s before this slice, expected near 0
  now), `commit_latency_s` (the transcriber's own: commit minus last word,
  ≥ the 2 s commit margin) and `last_final_age_s`; the two headline keys
  are null when either side is unknown.

**Settings and constants added.** One setting: `AUTO_RERANK_DROPS_ENABLED`
(default false; in `.env.example` with its comment; **not** in `.env`).
Two constants, not settings, by the owner's number: `AUTO_OWN_VOICE_TAIL_S`
= 0.3 in `app/main.py` and `OWN_VOICE_TAIL_MS` = 300 in live.html, pinned
equal by a test.

**Build decisions taken where the owner's text was silent — for the
owner to confirm or overrule:**

- **H1 — the window opens at the request, not at `speak_started`.** The
  prompt named `speech.requested`; it also happens to be the safe end —
  a synthesis cache miss puts up to a second between the two, and the
  meter cannot tell that second from playback. It closes at the
  utterance's end whatever the reason (a politeness abort that never
  played closes at the abort, so its window is only the request's own
  few ms). A window whose end was never seen counts only while its
  utterance is still the pending one, so a lost `speak_ended` can never
  make the machine deaf to every later span.
- **H1 — an own-voice span is a fresh span, like a playback span.** It
  bumps `quiet_span_seq` and resets the officer's per-span state exactly
  as a `since: playback` span does — so in GOLDEN it can earn the next
  encourager, as Alba's own phrase end always could ("the voice that
  aborted it begins the next span"). Nothing new there, but now it holds
  for the trailing energy too.
- **H1 — a barge-in.** The patient speaking over Alba cuts her (the
  detector is untouched); `stopSpeaking('barge_in')` stamps `playback`,
  and the patient's continuing voice begins a `speech` span once the
  300 ms tail has passed. A patient utterance that lies entirely inside
  the tail is invisible to the reporter (never to the transcript). The
  server-side check catches the same shape from an older page.
- **Re-ranker — the protected item.** The planned item is still popped
  from the drops before the module sees them, so it appears on the row as
  `protected_dropped_by_verdict`, not in `drops_advised`. Everything else
  the verdict advised is on the row with its reason, whether or not the
  flag is on.
- **H3 — the turn end may now precede the answer's last commit.** This
  is the point of the change, and its seam: with the span starting at the
  silence, the officer is asked at 2.0 s of real quiet and the fallback
  fires at 3.5 s, while the transcriber commits the answer's last segment
  2–4 s after its last word. The officer's transcript, the re-ranker's
  excerpt and the pass requested at the turn end can all miss the
  answer's last words; the officer's "not finished" on a truncated
  transcript now means something different from before. The row's
  `last_final_age_s` and a *negative* `last_word_to_span_start_s` (the
  latest final predates the span) are how the next run will show it. A
  bound — hold the pass until the transcript has caught up, or ask the
  officer again when a final lands — is the owner's, after the numbers.
- **H3 — `span_start` is recorded on every report,** fresh or not (each
  report of a span re-derives the same instant to within the meter's
  step); the golden exit's turn end still writes `auto.phase`, not
  `auto.turn_ended`, so it carries none of the new numbers.
- **Suite — the pin is two-layered.** `os.environ["AUTO_MODE_ENABLED"] =
  "false"` before any app import (set, not setdefault: neither the shell
  nor `.env` can raise it) and an autouse fixture that sets the attribute
  False before every test; the harnesses' own fixtures set it True after.
  Under the pin the three stubs' `presynthesise_phrases` is never reached
  — it is there for the day a test with a stub opts in.
- **Tests repinned by decision** (each docstring names it and the date):
  the meter-loop pin (the guarded call) and the activity-source pin
  (transcript movement is no longer a reporter source) in
  `test_quiet_reporter_client.py`; the three re-rank tests that read an
  applied drop as evidence (the drop with its reason, the pass-in-flight
  verdict, the single stale item) re-pointed to the flag-on case. Nothing
  weakened or deleted. New files: `tests/test_own_voice.py`,
  `tests/test_transcript_span_client.py` (the final/partial branches of
  `onWsMessage` executed under Node around the shipped reporter). Each
  server-side H1 test and each flag-off re-rank test was checked to fail
  with its fix disabled.

**What the next run should be read for.**

- *`auto.quiet_report` rows with `own_voice: true`* — how many, after
  which utterances (expect the thinking phrase and any utterance whose
  end left a tail above the floor); and `auto.thinking` at most once per
  `auto.turn_ended` — the fits are gone if the count per wait is ≤ 1.
- *`auto.turn_ended.last_word_to_span_start_s`* — its distribution
  (expected near 0; 491 read ≈ 3), the negatives and their
  `last_final_age_s` (the turn ended before the commit — how often, by how
  much), and `commit_latency_s` on its own; against them
  `turn_end_to_speech_ms` on `auto.question_latency` — the number to
  beat should fall by about the 3 s H3 removes. This is what decides
  `AUTO_EOT_FALLBACK_S` (3.5 versus lower), as the 491 report said:
  after H3, not before.
- *`auto.queue_reranked.drops_advised`* against the transcript — the
  re-ranker's judgement now costs nothing, so every verdict of the next
  run is free evidence for `evals/`: does an advised drop ever agree with
  the transcript? The order it gives, likewise.
- *Also:* whether the queue now ever runs empty in the question phases
  (with drops off it should only when every item has been asked); the
  asked-twice shape of H2 (unchanged in this slice — expect it again).

**`help/`: NOT edited.** Nothing in items 1, 3 or 4 makes a sentence
untrue — the articles do not say when the machine judges the patient has
finished, nor that it might hear itself. Item 2 amends one flag already
owed from slices 3 and 4, all for the owner's wording in one sitting:

- `help/04-the-architecture.md`: "MedGemma 27B does … the two small
  judgements that pace the spoken interview: has the patient finished
  speaking, and what a question is about." — three judgements (slice 3),
  the second also puts the question into plain English (slice 4), and
  the third now only **orders** the waiting questions — since 2026-09-10
  it can no longer remove one (the slice-4 flag read "which waiting
  questions are still worth asking, in what order").
- `help/01-a-consultations-journey.md` §3: "asking questions of its own
  choosing" — the slice-4 flag stands ("the head of a standing queue that
  every pass feeds, re-sorted after each answer"), with the same
  correction: re-sorted, never pruned, by that step.
- The slice-4 flags on `help/02-using-it-step-by-step.md` steps 3 and 5,
  `help/01` §2 and `help/06` stand unchanged.

**v1.1, carried forward from the 491 report and the owner's decisions:**

- **Concrete closed questions instead of category questions** — the
  owner's clinical verdict: a GP asks "do you smoke?", not "do you have
  risk factors?". The compound heart-disease question (§2 of the report,
  four places) and the lay wording's widening ("any other things that
  might put you at risk") are the same item seen twice; which layer
  splits, and whether "one sentence" should read "one thing", is the
  owner's.
- **H2 — the same-lay-sentence guard:** a lay sentence equal to one
  already spoken this session is refused (or the original asked
  verbatim); and/or the merge compares a proposal to answered items by
  similarity rather than exact token set — the second changes the
  never-twice guarantee's identity and is the owner's.
- **H4 — the topic call's audit row:** a `model.call` of kind `topic`
  with `topic`, `lay`, `similarity` and elapsed on every call, and the
  merge's `added_items` with text; without it the lay calibration data is
  two rows per run.
- **The floor under fan load:** 0.02 by clamp against bursts of
  0.023–0.032 in the last minute of 491; whether the sound check should
  be taken with the model loaded, or the margin, or the clamp minimum,
  is one decision and the number is 0.032.
- **The re-ranker to `evals/` before it may drop again** (0 for 7 on the
  record; `AUTO_RERANK_DROPS_ENABLED` stays false until then).
- Also from the report's §8: `AUTO_EOT_FALLBACK_S` after H3's numbers;
  `AUTO_LAY_MIN_SIMILARITY` (0.539 accepted a widening); "Let me think"
  once per 25 s wait, or the speculative pass (D-C (b)); the second
  urgency pause 1.3 s after RESUME, as designed, for the owner to weigh
  against D4's intent.

**Watch list, carried forward:** the re-ranker's judgement (now free
evidence); the lay wordings; the felt length of the window; D10 at the
room's floor; banner visibility; the slice-4 numbers not yet stressed
(`AUTO_SHORT_CALLS_HOLD_S`, `AUTO_PRESYNTH_WAIT_S`, `AUTO_ENABLE_RETRIES`,
`AUTO_ENCOURAGER_MAX_UNANSWERED`); and, new, the H3 seam above — a turn
end before the answer's last commit.

## Pre-flight sweep for the public flip (REPORT ONLY, 2026-09-10)

The repository goes public today as OpenConsult. A report-only sweep of
the nine items in the owner's prompt — tracked data, secrets across the
whole history, names and addresses since the 4 Aug sanitisation,
licence and citation, the old name in user-facing text, a literal
fresh-clone quickstart, consultation 469, one table on consultation
492, and the owner's launch checklist — is at
`~/Documents/Consultation-ai/PREFLIGHT_PUBLIC_2026-09-10.md`, outside
the repository, with file:line, commit and query evidence for each
verdict. Nothing was changed, voided or purged; this entry is the only
edit.

The headline, so a reader of this file alone has it: items 1 (tracked
data) and the licence-consistency half of 4 PASS; 2 has one FAIL (the
committed `.env.example` database password is the live one on this
machine — Postgres is loopback-only, so it is a rotation, not an
emergency); 3 finds two names at HEAD for the owner's decision (a
quoted name in the prereg's own amendment log, and a first name used as
a doctor-name fixture in one speech test); 4's CITATION.cff has the old
title and URL, no date and no DOI placeholder, and README carries no
acceptance notice for the two Google models; 5 lists 25 user-facing
strings against the identifiers that wait for v1.1; 6's fresh clone
runs `uv sync` and the SECRET_KEY refusal as documented, but README
never creates the database role or database, 34 `app/` settings are
absent from `.env.example`, and the clone's suite gave 1131 passed, 1
failed (the covered-answer RAG test, which checks the database for a
corpus rather than the manifest), 4 skipped (TTS paths under the old
`/home/wajir`); **7: consultation 469 is voided (14 Aug, class
clinical_safety) but not purged** — the row, 23 turns, 303 raw
segments, the patient row and the 40 MB WAV remain, and the "Purge
voided test data" button skips that class by design
(`app/consultations.py:701`), so the paper's "deleted with everything
derived from it" is not yet true; the two routes are in the report and
the choice is the owner's. The 4 Aug sentence above, "the working tree
names no real person except the owner", is untrue by one line
(`evals/2026-07-25_sinhala_confound_prereg.md:135`) until item 3 is
decided.

## Launch slice — the pre-flight sweep's fixable items, built (2026-09-10)

The nine items the owner decided from
`~/Documents/Consultation-ai/PREFLIGHT_PUBLIC_2026-09-10.md` (the
sweep entry above), one commit each, the suite green before every one
(1136 passed before the slice; 1147 after). Nothing in `.env`, `evals/`,
`help/` or `vendor/` was touched; nothing was rotated, voided or
purged — the two operator actions are written out below for the owner
to run.

| # | commit | what |
|---|---|---|
| 1 | `2db814d` | `scripts/manage_consultations.py purge-one CID` — hard-deletes ONE already-voided consultation of ANY class, including clinical_safety, after the id is typed back: the row and everything that cascades, the patient row if orphaned, every `RECORDINGS_DIR/consultation_CID.*` file, one `data.purged` audit row naming the id, class, reason, operator, per-table counts and file paths; the original void row stays. Refuses anything not voided (the guard is in the DELETE's WHERE). `purge_voided` and its clinical_safety guard are unchanged. Ten tests in `tests/test_purge_one.py`. |
| 2 | `24ad982` | `.env.example` says `CHANGE_ME` for the database password. **The old value is in private history only, was usable on loopback only (Postgres listens on 127.0.0.1), and is rotated on launch day by the commands below.** The Docker default in `docker-compose.yml` / `docker/db-init/` still uses the old string: there it both creates the role and is handed to the app, so it names nothing once the live one is rotated. |
| 3 | `dd0887a` | the doctor-name fixture in `tests/test_speech.py` is "Kildare"; nothing else tracked carries the name (the evals JSON's "victoria secret 2012" lines are public benchmark text). |
| 4 | `c6431b4` | edge-tts removed from `pyproject.toml` and `uv.lock` (the lock diff is that one package; CUDA wheels untouched). Only `scripts/make_tts_sample.py` imported it; the script stays because the 7 July note-quality eval names it, and now exits at import with the one-off invocation (`uv run --with edge-tts …`) and a docstring saying it calls Microsoft's online service. Nothing to add to NOTICE or README. |
| 5 | `d832697` | `.claude/` ignored. |
| 6 | `a59226f` | user-facing name OpenConsult: README H1, NOTICE ×2, PROJECT_PLAN ×2, the seven page titles, the sign-in heading, the nav brand, the FastAPI title, main.py's docstring, two header comments, CLAUDE.md (both names). Identifiers untouched (package, folder, unit, database/role names, logger, URLs — v1.1). No test asserted the old title. |
| 7 | `42f9b09` | CITATION.cff: title OpenConsult, `Herath, M W I`, date-released 2026-09-10, version 1.0.0, repository `IndyWH/OpenConsult`, AGPL-3.0-or-later, `doi: 10.5281/zenodo.PLACEHOLDER` with the replace-after-archiving comment. README § Model terms: MedGemma and embeddinggemma under the Health AI Developer Foundations and Gemma terms, accepted on Hugging Face or by pulling via Ollama, no weights redistributed, the code only calls what the operator's `ollama pull` fetched; one line each for Whisper (MIT; faster-whisper MIT, WhisperX BSD-2-Clause), pyannote (MIT, gated), Piper and the alba voice. |
| 8 | `94b83d1` | README step 2 creates role (CREATEDB), database and the vector extension in it and template1; ffmpeg; the download sizes at first Start and first Stop. `.env.example` now carries every `os.getenv` in `app/` (34 added; a two-set diff is empty both ways). `tests/test_rag.py` skips with three named reasons, the new one "no corpus manifest" (the clone had the live corpus tables copied by conftest and no manifest). `app/speech.py` expands `~` in `TTS_MODEL_PATH` and the command's first word, so the template's paths are `~/.local/…` and true on any account. And a third, found by the clone run itself: `tests/conftest.py` now *sets* `SESSION_COOKIE_SECURE=false` (it setdefault'ed it after `load_dotenv`), because the template now documents the flag explicitly and a template-derived `.env` had failed 33 cookie tests. |
| 9 | this commit | this entry and the correction under the 4 Aug sanitisation paragraph. |

**Fresh clone, the stranger's run** (`git clone` from the local path
into `/tmp/oc-launch`, `cp .env.example .env`, a real SECRET_KEY, this
server's DATABASE_URL, `uv sync` from cache): **1144 passed, 3 skipped,
0 failed** — the three skips are `tests/test_rag.py` with the manifest
reason; the four TTS tests that used to skip now run there.

**Owner decisions surfaced by the slice, not made in it.**

- The four Phase 7b behaviour flags newly documented in `.env.example`
  (`FACE_AUTO_ON_DISCLOSURE`, `AUTO_INVITATION_AFTER_DISCLOSURE`,
  `SILENCE_NUDGE_ENABLED`, `CDS_FIRST_CALL_ON_FIRST_TURN`) are written
  at their code defaults, `true`, per the template's standing convention
  (template = code default). The prompt said "flags off"; switching an
  evaluated behaviour off for fresh installs is a product decision. The
  experimental gates (`AUTO_MODE_ENABLED`, `BARGE_IN_ENABLED`) were
  already false.
- **help/ series line — owed the owner's wording.** Ten files carry
  "*Part of the Consultation AI help series*" (line 3 of `help/00`–`09`)
  and `help/00-introduction.md:5` opens "Consultation AI is a research
  and education platform". Owner-verbatim prose, not edited; the app
  they describe now says OpenConsult on every page.
- Stale but out of scope, for v1.1: the FastAPI `description` in
  `app/main.py` and `pyproject.toml`'s description still say "in Sinhala
  and English"; the orientation section above still says 683 tests.
- The prereg name (correction under the 4 Aug entry) stays until the
  owner amends the frozen file or decides to leave it.

**The owner's commands.** Both are his to run; neither was run.

Consultation 469 (void audit row 2620 stays; a `data.purged` row is
written):

```bash
cd /home/indy/Projects/consultation-ai
uv run python scripts/manage_consultations.py purge-one 469   # type 469 at the prompt
# verify — the WAV:
ls -l data/recordings/consultation_469.wav    # expect: No such file or directory
# verify — the rows (expect 0 0 0 0, then 1 and 1):
psql "$(grep ^DATABASE_URL= .env | cut -d= -f2-)" -c "SELECT (SELECT count(*) FROM consultation WHERE id=469) AS consultation, (SELECT count(*) FROM transcript_turn WHERE consultation_id=469) AS turns, (SELECT count(*) FROM raw_segment WHERE consultation_id=469) AS segments, (SELECT count(*) FROM patient WHERE id=276) AS patient, (SELECT count(*) FROM audit_event WHERE id=2620) AS void_row_kept, (SELECT count(*) FROM audit_event WHERE action='data.purged' AND subject_id=469) AS purged_row;"
```

Database password rotation (role `consultation_app`, the one the app's
DATABASE_URL names; `sudo` wants a terminal of its own):

```bash
cd /home/indy/Projects/consultation-ai
NEW=$(openssl rand -hex 24)
sudo -u postgres psql -c "ALTER ROLE consultation_app PASSWORD '$NEW';"
sed -i "s|^DATABASE_URL=postgresql://consultation_app:[^@]*@|DATABASE_URL=postgresql://consultation_app:${NEW}@|" .env
uv run python scripts/migrate.py --check      # connects with the new password; "no drift" = it works
sudo systemctl restart consultation-ai
curl -fsS http://127.0.0.1:8000/api/monitor/pulse | head -c 300; echo   # the running app connects
```

**Consultation 469 — void verified and purged (owner, 2026-09-10 ~08:30 BST).**
The paper's Declarations say the recording captured on 14 August was deleted
on discovery. Verified today on mlrig by the owner: consultation 469 had been
voided on 2026-08-14 08:57:07 as `clinical_safety`, reason "Not meeting
project criteria" (audit row 2620), but not purged. Purged today with
`manage_consultations.py purge-one 469` (launch slice, 2db814d): consultation
row, 23 transcript turns, 303 raw segments, patient row 276 and
`data/recordings/consultation_469.wav` removed; audit row 2620 kept; a
`data.purged` row written by operator indy. Post-purge query returned
0 / 0 / 0 / 0 / 1 / 1. The Declarations' deletion qualifier now rests on
this entry.
