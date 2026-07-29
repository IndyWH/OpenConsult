# SPEC — Phase 7a, tap-to-ask

Draft for owner approval, 2026-07-25. Claude Cowork. **Nothing to implement until Wajira signs off.**

Companion to `PHASE_7_SPEC.md` § Stage 7a, which stays the authoritative statement of what 7a is *for*.
This file is the *how*, and it exists to make one guarantee concrete: the system can speak into the
room without ever being able to put words in the patient's mouth.

Written against the repo as read on 2026-07-25 (HANDOVER at commit `9ec20a0`). Where it describes
existing internals — frame sizes, what S4 measures, how the session recording is written — CC must
**verify against the code before relying on it** rather than trusting this document.

---

## Part 1 — The guarantee, and the architecture it forces

### 1.1 The rule being satisfied

`PHASE_7_SPEC.md` § 7a: system-spoken utterances are excluded from the patient transcript **by
construction** — never by prompt, never by post-hoc filtering. Echo handling and ASR gating during
playback are part of the requirement, not an optimisation.

The reading that follows from that: whatever separates our voice from the patient's must be
**server-held knowledge of when we were speaking**, not signal quality and not text comparison. AEC
that works 98% of the time is detection, and a rare fabrication is worse than a frequent one because
nobody builds the habit of checking for it.

String comparison against the spoken text is legitimate **as a test assertion** and forbidden **as a
runtime mechanism**. That distinction should be written into the test file's docstring, because it is
exactly the kind of thing a future contributor will "helpfully" promote into the pipeline.

### 1.2 Owner decision taken 2026-07-25: gate-and-cut

The patient must be able to interrupt mid-sentence, and the design must degrade to hard mute rather
than to transcript corruption when conditions are poor. Gate-and-cut does both:

- While the system speaks, the microphone keeps capturing, but that audio reaches **only a
  voice-activity detector**. It cannot reach the transcript, live or final.
- The detector's entire output is one boolean: *someone is speaking*.
- On detection the client stops playback immediately, reports the real stop point to the server, and
  from that point onward audio re-enters the transcript path.

What it costs: roughly 200–400 ms of the interrupting utterance — the first word or half-word spoken
before the cut. The system stopping mid-word is itself a strong cue and people restart. The failure is
**truncation, not fabrication**: on the safe side of the project's guarantee, and visible rather than
silent.

Both detector failure modes degrade safely, which is why this is not a bet:

| Detector behaviour | Consequence |
|---|---|
| Too twitchy (residual echo trips it) | System stops talking when it shouldn't. Irritating; the doctor re-taps; transcript stays correct. |
| Too deaf (interruption missed) | Behaves exactly like hard mute. The fallback is reached automatically, per utterance. |

Hard mute is therefore not a separate design — it is this design with `BARGE_IN_ENABLED=false`. Build
the gating first and prove it; add detection second.

### 1.3 The consequence that matters most: two transcription paths, not one

The live path is not the only place system audio could enter the transcript. `app/finalize.py`
re-transcribes **the whole recording** with WhisperX. Gating only the live path would leave the final
transcript — the one the note is grounded in — carrying our voice.

So exclusion is applied twice, from one persisted source of truth:

1. **Live path:** audio inside a speaking window is never fed to the streaming transcriber.
2. **Final path:** finalisation transcribes a **derived copy** of the WAV with the excluded spans
   zero-filled. WhisperX and pyannote cannot hear what is not there.

**The original recording is never modified.** It stays byte-intact on disk as the faithful record of
the room, and is what the retention sweep and the FLAC-on-approval step operate on. A test should
byte-compare the original before and after finalisation.

### 1.4 An elegant consequence: AEC is only needed by the detector

Because exclusion is structural, the transcript stream never needs echo cancellation. That means
**the existing capture stays untouched** — no new `getUserMedia` constraints, no risk of regressing
ASR quality, no re-validation of the audio path.

Instead, open a **second, detector-only stream** with `echoCancellation: true`, downsampled, never
transmitted anywhere and never written to disk. It exists solely to answer the boolean.

**The mic-status cluster's invariant is preserved and must stay preserved:** the level meter and the
red-pill logic continue to run off the *same* stream the transcriber consumes (HANDOVER, design pass —
"one capture, so the meter cannot disagree with what the server hears"). The detector stream must
never be wired to the meter. Worth a comment in `live.html` saying so.

---

## Part 2 — Protocol

Extends `/ws/transcribe`. `live.html` is the only client and they version together, as today.

### 2.1 What the client may ask for

The client sends a **reference, never text**:

```json
{"type": "speak", "ref": {"kind": "cds_question", "assessment_version": 7, "index": 2}}
{"type": "speak", "ref": {"kind": "phrase", "id": "disclosure"}}
```

The server resolves the reference against its own copy of the CDS agenda or the fixed phrase table and
synthesises **its own** text. A `speak` message carrying a `text` field is rejected outright (4xx /
protocol error, audited).

This is the code-level enforcement of hard rule 1 — questions and acknowledgements only. Nothing the
system can say in 7a is authored at speak time: it is either a question the CDS engine already put on
the agenda, or one of a small fixed set of phrases reviewed in advance. A compromised or buggy client
cannot make it advise, reassure or diagnose, because it has no channel through which to supply words.

A reference to a question that has since been revised off the agenda is **allowed and logged** — the
panel can lag by a turn, and re-asking an answered question is redundant, not unsafe.

### 2.2 The speaking window

1. Server resolves the ref, synthesises, stores the utterance, replies
   `{"type":"speak_ready","utterance_id":"U", "duration_ms":3120, "url":"/api/speech/U.wav"}`.
2. Client fetches and plays. **At actual playback start** (not at request time) it sends
   `{"type":"speak_started","utterance_id":"U","seq":S}` where `S` is the sequence number of the next
   audio frame it will send.
3. Client keeps capturing and keeps sending mic frames throughout. Received audio is never abandoned —
   the resilience principle is unchanged.
4. On playback end: `{"type":"speak_ended","utterance_id":"U","seq":E,"reason":"complete" |
   "barge_in" | "doctor_stop" | "cancelled"}`.
5. Server marks `[S, E + SPEECH_EXCLUSION_TAIL_MS]` excluded, and persists it as a **byte/time span on
   the recording** — the server knows where in the file it was speaking, and that is the durable
   artifact both paths read.

Recording the span as an offset into the WAV (rather than only as sequence numbers) is deliberate:
finalisation works on the file, and sequence-to-offset arithmetic done twice is arithmetic done wrong
once.

### 2.3 Edge cases, all of which must fail closed

| Case | Behaviour |
|---|---|
| `speak_ended` never arrives (drop mid-playback) | Server closes the window at `S + duration_ms + tail`. The synthesised duration is known, so the fallback is exact, not a guess. |
| `speak_started` never arrives | No window, no exclusion, no harm. Utterance logged `failed_to_play`; doctor sees an error state. |
| Reconnect mid-utterance | Playback is cancelled on the client; the window closes by the rule above. Do not resume playback across a reconnect. |
| Grace expiry / `connection_lost` finalisation | Persisted spans still apply — they live in the database, not in the live session object. |
| Two windows overlapping | Impossible by construction: one utterance at a time, queue depth zero. Server rejects `speak` while a window is open. |

The live commit logic gives natural slack here: segments are only committed once they end more than
~2 s before the newest audio, so `speak_started` (sent at playback start) always precedes any attempt
to commit audio from inside the window. CC should confirm that reading against `app/live.py` rather
than assume it.

### 2.4 Interaction with the transcript-quality gate — flagged, needs verification

Zero-filling several seconds per utterance changes the audio the gate measures. **S4 (> 20 s refuses,
> 10 s flags) plausibly measures a silence or gap length**, in which case a run of muted system
utterances could manufacture a spurious `unreliable_transcript` refusal on a perfectly good
consultation.

Required: whatever S4 actually measures, the measurement must be **told about the excluded spans** and
discount them. CC must read `TRANSCRIPT_QUALITY_GATE_SPEC.md` §11 and
`scripts/calibrate_transcript_quality.py` and report what S4 and S2 measure **before** building this,
rather than acting on my inference.

This lands on top of the pending "one shared measurement function" requirement (HANDOVER, carried work
item 2). If the S1/S3 redesign happens first, exclusion-awareness goes into the shared function once.
If 7a happens first, it must not add a *third* code path for the same signal.

---

## Part 3 — Storage, logging and the note boundary

### 3.1 A separate table, on purpose

System utterances go in a new table `system_utterance`, **not** in the turns table with a `system`
role. A separate table is the by-construction version of "the note can never cite our voice": the note
generator receives turns, and system utterances are not turns. There is no enum value to forget to
filter.

Columns (at least): `consultation_id`, `utterance_id`, `text`, `ref_kind`, `ref_detail` (CDS
assessment version + index, or phrase id), `cds_rationale` (the agenda item's rationale as it stood —
hard rule 5 asks for the rationale, not just the question), `requested_at`, `started_offset_ms`,
`ended_offset_ms`, `end_reason`, `cut_latency_ms`, `voice`, `synth_ms`.

Audit events, matching existing naming: `speech.requested`, `speech.spoken`, `speech.barge_in`,
`speech.failed`.

### 3.2 The note and letter paths

Tests must assert, not assume:

- The note generator's input contains no system utterance text.
- No citation can resolve to a system utterance id.
- The plain-text export and the referral letter path likewise (letters draw from the approved note
  only, so this follows, but assert it — the #66 lesson is that gates are per-sentence and explicit).

### 3.3 The review page

System utterances render **inline in the diarised transcript, in a visually distinct grey channel**,
labelled and timestamped, interleaved by time so the consultation reads correctly — but they are not
Doctor or Patient turns, carry no turn number, and are not clickable as citations. The doctor can see
exactly what the machine said and when; the note cannot touch it.

### 3.4 Schema drift — build the pending fix first

7a adds a table. The live-versus-code drift found on 2026-07-25 cost a debugging session, and HANDOVER
carries the agreed fix (shared `app/schema.py::ensure_all()` called by app lifespan, scripts and
`conftest.py`, plus `scripts/migrate.py --check`) at an estimated 2–3 hours, unbuilt.

**Recommendation: build it as commit 0 of 7a.** Adding a table through the same mechanism that just
drifted, while the fix sits specified and unbuilt, is the cheapest possible time to pay for it.

---

## Part 4 — Speech synthesis

- **Piper, fully local, CPU only.** It must not touch the GPU: `app/finalize.py`'s VRAM sequencing
  assumes nothing else is competing for the card, and a 24 GB budget with MedGemma at ~17 GB has no
  room for a guest.
- Voice pinned in config; model path in `.env`; the chosen voice recorded in each utterance row so a
  voice change is visible in the research log.
- **Synthesis cache** keyed by `hash(text) + voice`. Agenda questions repeat across consultations, so
  most taps should be instant; a cold synthesis of a one-sentence question on CPU should be well under
  a second, but measure rather than promise.
- `SPEECH_MAX_UTTERANCE_S` as a hard cap: refuse to synthesise anything longer, which bounds both the
  exclusion window and any pathological agenda string.
- Playback goes through the live page (browser audio), not the server's speakers, so it lands on
  whatever device the room is already using and stays inside the existing HTTPS origin.

---

## Part 5 — UI (`live.html`, existing theme, no new visual language)

- **Tappable question chips** in the CDS panel — each agenda question gets a small speaker affordance.
  One utterance at a time; chips disable while a window is open.
- **A speaking pill** with a **Stop** control, always available and one tap, per hard rule 3. The
  doctor's manual cut is not a fallback for the detector; it is the primary guarantee that the doctor
  always wins.
- **A small phrase tray**: disclosure, invitation ("Please, tell me what's brought you in"),
  encouragers ("mm-hm", "I see", "go on"), examination handover ("Thank you — Dr Herath will examine
  you now"). Cheap to build, and it lets 7a rehearse the 7c behaviour policy by hand — you can run a
  golden-minutes consultation with the doctor as turn-taker and see whether the policy feels right
  before any autonomy exists.
- **No free-text speaking, and no editing a question before it is spoken** (7a). Any edit box is a
  channel for arbitrary utterances and would put rule 1's enforcement back into regex. Owner decision
  D2 below if you want it.
- **Disclosure lock (hard rule 4):** question chips stay disabled until the consultation has a
  recorded disclosure — either the spoken `disclosure` phrase, or the doctor ticking "disclosure
  given" (audited, with user and timestamp). Code-enforced, so it cannot be forgotten in the moment.
- **No Auto toggle in 7a.** That is 7c.

---

## Part 6 — Tests (`tests/test_speech.py`, `tests/test_speech_exclusion.py`)

The guarantee is only as good as its regression tests:

1. **The keystone test.** Build a session whose captured audio *contains the TTS audio* during the
   window. Assert zero transcript content from that span — on the live path and on the finalised
   transcript. This is the one that must never be allowed to go green for the wrong reason.
2. Exclusion arithmetic: tail applied; missing `speak_ended` falls back to `S + duration + tail`;
   out-of-order and late acks; reconnect mid-window.
3. Finalisation: derived copy is zero-filled across the spans; **original WAV byte-identical
   afterwards**.
4. Note boundary: no system text in the note generator's input; no citation resolves to an utterance.
5. Protocol: `speak` with a `text` field rejected; `speak` while a window is open rejected;
   RBAC — only the doctor owning the active consultation may speak, receptionist 403, foreign doctor
   403.
6. Gate interaction: a consultation with N muted spans does not trip the transcript-quality gate.
7. Barge-in: a simulated detector event cuts playback, closes the window with `reason=barge_in`, and
   records `cut_latency_ms`.

---

## Part 7 — Config (`.env.example`)

```
TTS_ENABLED=true
TTS_VOICE=en_GB-...            # pinned; owner decision D3
TTS_MODEL_PATH=
SPEECH_MAX_UTTERANCE_S=20
SPEECH_EXCLUSION_TAIL_MS=200
BARGE_IN_ENABLED=false         # true only after calibration in the room
BARGE_IN_RMS_THRESHOLD=
BARGE_IN_MIN_MS=150
```

`BARGE_IN_ENABLED` ships **false**. It flips only when `scripts/calibrate_barge_in.py` meets both
sides of the D5 target in your actual room at your actual speaker volume.

---

## Part 8 — Build order

Each item is one commit, tests green before each, `git push origin main` after the last.

0. Shared schema module + `migrate.py --check` (the pending fix — see §3.4).
1. `app/speech.py`: Piper, cache, `/api/speech/{id}.wav`, phrase table, ref resolution. No UI.
2. Protocol + live-path exclusion + `system_utterance` table + the keystone test.
3. Finalisation exclusion: derived muted copy, original untouched, gate-interaction test.
4. UI: chips, phrase tray, speaking pill, disclosure lock, transcript channel.
5. Barge-in detector (second stream, envelope-proportional threshold, flag default off) +
   `scripts/calibrate_barge_in.py` reporting both sides of the D5 target.
6. HANDOVER update: the guarantee, the two-path exclusion, the calibration result.
7. Sound check (Part 10) — small, and best built alongside 5 since they share a measurement.

7b (the face) can land alongside 4–6 per `PHASE_7B_KINDALIVE.md`; it needs `DESIGN_SPEC.md` and the
approved mockups, which are in Downloads and not the repo.

---

## Part 9 — Owner decisions

**D1 — Disclosure.** Spoken by the system, or a doctor-confirmed checkbox?
*Recommendation: offer both, require one.* Spoken is cleaner for the demo and puts the machine's own
voice behind the claim; the checkbox covers the doctor who prefers their own words.

**D2 — Free-text or edited utterances in 7a.** *Recommendation: no.* Reference-only keeps rule 1
enforced structurally. If you want editing later, it should arrive with its own spec, because it
changes the enforcement model rather than extending it.

**D3 — Voice.** Pinned `en_GB` Piper voice, your pick after listening to samples. Worth a moment's
thought: the voice is part of what the face study measures, and a voice change mid-study is a
confound.

**D4 — Encourager phrases in 7a.** *Recommendation: yes.* They cost almost nothing and let you feel
the golden-minutes policy with a real patient-actor before committing to 7c.

**D6 — Sound check.** Owner's addition, 2026-07-25, specified in Part 10. Decided: a labelled
control, not a cogwheel; acoustic verification rather than a bare play button; offered but never
blocking.

**D5 — Barge-in acceptance criteria.** *Recommendation, taken 2026-07-25 at the owner's delegation:
a two-sided target, and a ship rule that resolves itself.*

The first thing to say plainly is that **this is a comfort parameter, not a safety parameter**. Because
exclusion is structural (§1.1–1.3), no threshold setting can corrupt a transcript. A false stop costs a
re-tap; a miss costs a few seconds of talking over the patient. Both are manners, not safety. So the
number is chosen on feel and can be retuned later without reopening the guarantee.

A single-sided target would be gamed by making the detector deaf, so specify both and report them as a
pair:

| Measure | Target |
|---|---|
| False stops (detector fires, nobody spoke) | **≤ 1% of utterances** — roughly one spurious stop every five consultations at ~20 utterances each |
| True interruptions caught | **≥ 90%, within 300 ms of speech onset** |

**Ship rule:** both met → `BARGE_IN_ENABLED=true`. Either missed → ship hard mute, and revisit with a
headset or directional mic before trying again. This is the owner's own condition — *if the success
rate is low, stick to hard mute* — made measurable, and it is decided by the calibration run rather
than by anyone's judgement on the day.

`scripts/calibrate_barge_in.py` must therefore measure both sides in the real room at real speaker
volume: N utterances under silence, under room noise (paper, chair, breathing), and with a scripted
interruption at a random point in the utterance. It reports the confusion matrix and the detection
latency distribution. The numbers are **hardware- and room-specific** — re-run on any change of
speakers, microphone or room, and record the result in HANDOVER.

Two cheap mitigations that buy accuracy before any threshold tuning:

- **Envelope-proportional threshold.** The client knows the exact waveform it is rendering, so it can
  predict residual echo magnitude and require mic energy to exceed the current playback envelope by a
  margin, rather than testing against a fixed floor. Cheap, and it attacks the dominant false-trigger
  cause directly.
- **Cut means restart, never resume.** A cut question is re-offered as "cut — tap to repeat" on the
  chip. Resuming a half-delivered question mid-word is more confusing than repeating it, and
  auto-resuming would talk over a patient who genuinely did speak.

---

## Part 10 — Sound check (owner's addition, 2026-07-25)

### 10.1 Why this is a safety feature, not a convenience

7a introduced audio output, and a dead speaker fails **silently**. If the volume is down or the
output device is wrong, playback still succeeds — nothing errors, because nothing failed — and the
patient simply hears nothing. The doctor reads the silence as a patient not answering.

Worse, the exclusion window opens anyway. For the length of that inaudible utterance the microphone
feeds the detector only, so whatever the patient says during it is dropped from the transcript **by
construction**. A dead speaker therefore converts quietly into missing transcript, with nothing on
screen to say so. This is the same shape as every other failure this project has had to design
against: not visibly broken, just wrong.

The existing mic cluster answers "is the room being heard". This answers the other half — "is the
room hearing us".

### 10.2 Design

- **A labelled control beside Start on the live page**: a speaker icon with the words *Sound check*.
  **Not a cogwheel** — settings iconography reads as configuration, not as test, and icon-only
  controls cost a beat on every use.
- **User-initiated by necessity, not only by choice.** Browsers refuse to play audio before a user
  gesture, so a check that ran automatically on page load could not make a sound.
- **What it does**: plays a short fixed phrase (a new phrase id `sound_check`, wording below) through
  the same output path a spoken question uses, measures microphone energy during playback from the
  **existing** capture stream, and then asks the doctor a one-tap question.
- **It reports a level, not a boolean.** Faint means the patient will struggle to hear and barge-in
  will be unreliable; that is different from silence and should read differently.
- **The human answer is authoritative.** The only true test of whether the room heard it is a person
  in the room saying so. The acoustic measurement is corroboration, and it is the part that produces
  a number.

Result classes:

| Result | Condition | What the doctor sees |
|---|---|---|
| Heard, good level | Mic energy clearly above the noise floor, and doctor confirms | Green, with the level |
| Heard, faint | Energy only marginally above the floor, doctor confirms | Amber: the patient may struggle; barge-in will be unreliable at this volume |
| Not heard | No energy above the floor, doctor says no | Red: speaker likely muted, wrong output device, or disconnected |
| Unverified | Doctor declines to answer | Neutral; recorded as unverified rather than as a pass |

**Headphones are a known confound**: with headphones there is no acoustic path back to the
microphone, so energy reads as absent while the doctor says yes. Treat the human answer as
authoritative, record the discrepancy, and do not warn.

### 10.3 Constraints

- **The mic-cluster invariant stands.** Measurement uses the same capture stream the transcriber
  consumes. Do not open a second stream for this.
- **Disabled while recording.** A test phrase played into a live consultation would be a system
  utterance and would have to go through the whole exclusion machinery for no clinical benefit.
  Simpler and safer to allow it only before recording starts.
- **Offered, never blocking.** If no sound check has been done in the session, the first tap of a
  question offers one — one tap to run, one tap to skip. The doctor may have good reason to decline
  and the system does not get to overrule that.

### 10.4 Wording

    Sound check. If you can hear this clearly, press yes.

Deliberately not clinical and not addressed to the patient — it is a check spoken in the room, and
it should sound like one.

### 10.5 Logging, and the reuse that makes this cheap

Audit `speech.sound_check` carrying the measured level, the doctor's answer, the output device label
if the browser exposes it, and the timestamp. A later question about a strange consultation — did
anyone hear the machine? — then has an answer in the record rather than in memory.

**The measured loopback level is exactly the input the barge-in detector needs.** The
envelope-proportional threshold in build order item 5 has to know how loud our own voice comes back
into the microphone; that is the number this check produces. `scripts/calibrate_barge_in.py` should
read the recorded sound-check levels rather than re-measuring from scratch, which is why the two are
best built together.

---
**Amendment, 2026-07-30 (owner-approved): the sound check measures both streams.**
During its playback the sound check now measures BOTH capture streams simultaneously. The main stream (echo cancellation off since 2026-07-30) gives the true acoustic loopback — this remains what the doctor-facing result reports, because "can the room hear the machine" is a question about the room, not about a filter. The barge-in detector stream (echo cancellation on) gives the canceller's RESIDUAL, recorded alongside in the same speech.sound_check audit row, together with enough samples across the utterance to show the canceller's convergence as a curve rather than a point.
Rationale: the barge-in threshold operates on the detector stream, so it must be proportional to the residual there, not to the raw loopback. Measured 2026-07-29/30 on this room's monitor output: raw loopback 0.30–0.58 RMS against quiet real speech at 0.056 RMS — a tenfold gap no raw-derived threshold can bridge, where a residual-derived threshold can, with the raw figure retained as a sanity upper bound. The human answer remains authoritative; the mic meter still reads the main stream only.
---
