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
- `uv run pytest` — 16 tests; heavy ones self-skip if Ollama/Postgres/
  corpus are absent.
- Postgres 18 + pgvector, database `consultation_ai`, credentials in the
  gitignored `.env` (see `.env.example`).

## Phase status vs PROJECT_PLAN.md

| Phase | Status | Notes |
|---|---|---|
| 0 — Foundations | **Done except recordings** | Env, Postgres, app, tests all in. Seventeen mock scripts written: 10 English (5 routine, 4 red-flag variants, 1 held-out), 2 Sinhala/English code-switched (`_si`, for the Phase 5 ASR recordings eval), 5 UK private-GP (`_uk`, CDS restraint + buried-red-flag urgency) — see `mock_consultations/README.md`. Real two-voice recordings scheduled for the coming weekend; a disposable TTS sample stands in meanwhile. |
| 1 — Streaming transcription | **Done** | Voice-tested; lag inside the 2–5 s target. |
| 2 — Post-consultation note | **Done, pending real-audio validation** | Full pipeline + review UI + eval. TTS-sample-tested; real recordings will exercise ASR-confidence flagging properly. |
| 3 — Live CDS | **Done** | Including urgency escalation, evaluated 8/9 with one documented boundary case (see docket). |
| 4 — RAG guidelines | **Done** | 9/9 eval; fidelity spot-check logged; corpus is UK/CDC/WHO starter content. |
| 5 — Sinhala | **Benchmark stage done (2026-07-10)** | 9 candidates benchmarked on two OpenSLR test sets; stock Whisper (incl. our final-pass large-v3) is unusable for Sinhala; best is the `seniruk/whisper-small-si` fine-tune (CER 0.035 on both sets). Recordings-eval procedure pre-registered. See `evals/2026-07-10_sinhala_asr_benchmark.md`. |
| 6 — Users/roles/front desk | **Core built and manually verified** | Auth (scrypt + signed-cookie sessions), three tabs per the agreed structure, walk-in queue, server-side RBAC (receptionist 403s on all clinical content — automated tests pass), audit log, approved-consultations read-only, full loop wired queue→live→review→approve→archive. **Verified 2026-07-10 (project owner, in-browser):** two-role click-through of the full loop, plus adversarial checks — receptionist hitting clinical URLs directly (403 confirmed), doctor attempting queue add/reorder (403 confirmed), edit attempts on an approved consultation (409 / read-only UI confirmed). Remaining build work: Docker Compose packaging, demo script, design pass. **Post-verification additions (2026-07-10, browser-testing findings):** doctor walk-in action (`queue.walk_in_started`); server-sourced patient banner on the live page (wrong-patient prevention — identity never read from URL text); queue-entry lifecycle for abandoned sessions — Resume, Close-without-consultation (`queue.cancelled`, receptionist too), and a concurrency guard so a doctor can't stack a second live consultation over an active one. |

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
app/mock_scripts.py    mock-script parser (turns)
app/static/live.html   live page; review.html  review page
corpus/manifest.yaml   committed provenance for the gitignored corpus
scripts/               ingest_guidelines, simulate_cds, make_tts_sample,
                       evaluate_{urgency,rag,notes,sinhala_asr}
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
click-to-verify in the UI. Flagging is deterministic code, not model
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
- Ollama is a user-space install (`~/.local/opt/ollama`), run by the
  `ollama.service` systemd unit since 2026-07-10 (as is the app, via
  `consultation-ai.service` — see the startup sequence below). Models
  keep_alive 30 m.
- sudo needs a real terminal (the assistant's shell can't prompt); batch
  root steps into one command for the user.

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
   contraindicated" vs CG95's "unless clear evidence of allergy").
4. **Two-hats loop-test notes** (2026-07-07, project owner playing both
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
- **Next:** score the weekend's real recordings with the SAME harness
  (`--manifest` mode; long-form chunked decoding auto-activates) per
  the pre-registered procedure in the eval record — references, curated
  English-term lists frozen before viewing outputs, transliteration
  adjudication by the project owner, decision rule already written.
  Only if the winner falls short on real audio: fine-tune on the 4090.
  Then: translation layer (Gemma/NMT benchmark, plan §4) and
  dual-language transcript storage — the `FinalTranscript` model in the
  plan already anticipates si/en pairs.

## CDS restraint dimension — scripts written, harness pending

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

- **Phase 0 (close out):** record the 5 routine scripts, two voices, per
  `mock_consultations/README.md`; drop WAVs in
  `mock_consultations/recordings/`; decide Git LFS.
- **Phase 2 (validate on real audio):** run each recording through the
  Stop→review flow; check diarisation/roles, confidence flags (first real
  test), and note quality vs marking schemes; append a real-audio section
  to the note-quality eval.
- **Phase 5:** benchmark done (see status table); next step is the
  pre-registered recordings eval once the weekend recordings exist. The two
  `_si` code-switched scripts and their draft refs are written and ready to
  record.
- **CDS restraint dimension:** UK `_uk` scripts (11–15) written with marking
  schemes; wire them into the urgency dict once recorded, and build the
  differential-breadth metric (see the CDS restraint section above).
- **Phase 6:** core is built and manually verified (auth + roles, queue,
  three tabs, RBAC, audit log; click-through and adversarial checks done
  2026-07-10 — see status table). Next: Docker Compose packaging, the
  two-role demo script, and the design pass.
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

Then from any tailnet device: https://mlrig.tail93fa1d.ts.net
(log in as a doctor; mic permission prompt should appear on the live page).

## Session/environment facts

WSL2 Ubuntu 26.04, RTX 4090 (24 GB), Postgres 18 + pgvector on localhost,
DB `consultation_ai` / role `consultation_app` (`.env`), HF token via
`hf` CLI cache (needed for pyannote), Ollama user-space at
`~/.local/opt/ollama`. GitHub: IndyWH/consultation-ai. The project owner
is a doctor building this to learn — explain technical decisions in
plain terms, and treat clinical-judgement questions as theirs to decide.
