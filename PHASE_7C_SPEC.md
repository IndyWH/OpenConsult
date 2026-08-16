# PHASE_7C_SPEC.md — Supervised auto history-taking

> **APPROVED by the owner 2026-08-16, wholesale.** Design by
> Claude Cowork from a full recon of the live 7a/7b code; decision
> points D1–D3 and the 1–2 minute golden window were decided by
> the owner the same day and are recorded inline. Everything in
> this phase builds DARK behind AUTO_MODE_ENABLED=false; enabling
> it is the owner's act, after the frozen gate is met (barge-in
> calibrated, mock-patient-round review). Parent documents:
> PHASE_7_SPEC.md, PHASE_7C_EVAL_PREREG.md + OPEN_CLOSED_RULE.md
> (both FROZEN).

## 1. What 7c is, and what it inherits

The system conducts the history-taking itself: invitation, silence
through the golden minutes with encouragers only, open questions, then
closed questions, then an explicit examination handover — while the
doctor supervises and can intervene at any moment. The LLM chooses
content only WITHIN the current phase; the phase machine is code and
the LLM never advances it.

All seven Phase 7 hard rules apply unchanged. Three are load-bearing
here and get their enforcement stated up front:

- **Rule 1 (questions and acknowledgements only)** is met by
  construction, not by prompt: auto mode has NO free-text path to TTS.
  Every utterance is a fixed phrase, an owner-approved template
  instantiated with a topic string, or an agenda question verbatim
  (§4). The existing server guard that rejects any `speak` carrying
  raw text extends to the auto path.
- **Rule 2 (urgency pauses auto mode)** becomes real machinery: pause,
  doctor acknowledgement, resume-auto or take-over, ratchet on re-fire
  (§7). Today the live alarm is display-only; 7c builds the live ack.
- **Rule 3 (the doctor always wins)** is met in the hard-mute world by
  one-tap cancel and one-tap auto-off, both instant; voice barge-in
  stays behind `BARGE_IN_ENABLED` (ships false) until the calibration
  run decides it (§8).

## 2. Ship posture — dark by construction

`AUTO_MODE_ENABLED` ships **false**. Flipping it is the owner's act,
after the frozen gate is met: barge-in calibrated, and the
mock-patient-round review. Everything below builds and tests dark.
7c must not arrive by drift; this spec makes the gate a config
boundary, in the same pattern as `BARGE_IN_ENABLED`.

## 3. Architecture

One new module, `app/auto_mode.py`, holding an `AutoModeController`
owned by the `LiveSession`. It is a plain state machine — no threads,
no timers of its own; it is driven by the events the session already
produces (committed transcript growth, CDS revisions, quiet reports
from the client, playback lifecycle messages) plus a monotonic clock
read at each event.

States: `OFF → DISCLOSURE → INVITATION → GOLDEN → OPEN → CLOSED →
HANDOVER`, plus `PAUSED_URGENT` (reachable from GOLDEN/OPEN/CLOSED)
and `TAKEN_OVER` (terminal for the session's auto run). Transitions
are code-owned; every transition is audited with its trigger.

Auto mode reuses the existing speak pipeline end to end: the server
synthesises (Piper subprocess, cache, 20 s cap), sends the client an
`auto_speak` message shaped like today's `speak_ready`, and the client
plays it and reports `speak_started`/`speak_ended` exactly as now — so
the transcript-exclusion guarantee (zero-filled transcriber buffer
between the server's own byte counts, derived-copy muting at
finalisation) applies to auto utterances with no new mechanism. The
one-utterance-at-a-time guard, the disclosure lock and the
`SPEECH_MAX_UTTERANCE_S` cap all carry over unchanged.

Doctor taps still work in auto mode. A tap cancels any queued auto
utterance, speaks the tapped question, and is logged as a doctor
intervention (hard rule 5); the controller treats the answer that
follows like any other.

## 4. What the system may say — the utterance whitelist

Four sources, nothing else reaches TTS:

1. **Fixed phrases** (already shipped, owner-verbatim): disclosure,
   invitation, the three encouragers, silence nudge, examination
   handover. No wording changes in this phase.
2. **Agenda questions verbatim** — the current `questions_to_ask`
   entries from the versioned `AgendaLog`, exactly as the CDS wrote
   them. These are the CLOSED-phase workhorse.
3. **Open-question templates**, owner-approved wording, instantiated
   with a topic string — e.g. `Can you tell me more about {topic}?`,
   `How has {topic} been affecting you?`. These serve the OPEN phase
   and the cone.
4. **The invitation-class follow-up** `Is there anything else you
   wanted to talk about today?` before handover (also a fixed phrase,
   owner wording to approve).

**D1 — DECIDED 2026-08-16: the tiny topic call.** The template needs
a short noun phrase ("the chest pain") distilled from an agenda
question. This comes from a new tiny model call at ask time — own
prompt, tight schema `{"topic": string}`, stateless, fail-soft, in
the exact shape of the affect call (~1 s warm, same `CDS_NUM_CTX` so
no reload). Fail-soft behaviour is to ask the agenda question
verbatim instead — still correct, just less open. The CDS
`ASSESSMENT_PROMPT` and its revision rules are untouched. (The
alternative — a `topic` field in the assessment schema — was
declined because it touches the stable CDS prompt.)

## 5. Turn-taking — quiet detection, end of turn, politeness

**Measurement stays client-side, authority stays server-side** — the
silence-nudge pattern, generalised. The live page's existing ~10 fps
RMS loop feeds a quiet-window tracker (the `nudge` object's design,
promoted into a first-class reporter): when quiet exceeds the
configured thresholds it reports `{"type":"quiet", "quiet_s": N}` to
the server; the server decides what, if anything, to say. The three
"do not generalise the nudge" guard comments are retired deliberately
in the same commit that builds their replacement.

Two thresholds, both env-tunable, both labelled uncalibrated guesses
until the mock-patient round:

- `AUTO_ENCOURAGER_QUIET_S` (default 1.75, the spec's ~1.5–2 s): in
  GOLDEN, a pause this long earns one encourager, rotated from the
  three, with a cooldown (`AUTO_ENCOURAGER_COOLDOWN_S`, default 8) so
  encouragers never machine-gun. Zero questions in GOLDEN is enforced
  in the controller — a question request in GOLDEN is a coding error
  and raises, it is not filtered.
- `AUTO_EOT_QUIET_S` (default 3.0): outside GOLDEN, a pause this long
  triggers the **end-of-turn officer** — a tiny stateless model call
  (affect-call shape) over the recent committed transcript answering
  one schema: `{"finished_thought": bool, "handed_back": bool}`.
  Fail-soft: on error or timeout, treat a longer silence
  (`AUTO_EOT_FALLBACK_S`, default 5.0) as finished. "Handed back"
  (explicit hand-backs like "that's all" / "what do you think?") is
  logged when detected, as the prereg requires for metric 3 scoring.

  The officer also runs during GOLDEN, where its verdict is used
  only for the exit decision — hand-back, or turn-end at the
  timer — and never to ask. Section 5's earlier "outside GOLDEN"
  wording was imprecise (recorded 2026-08-16 at slice-3 review).

**Politeness abort (interruption count ~0 by construction).** The
server never orders playback into live speech: an `auto_speak` is only
issued while the quiet window is still open, and the client re-checks
its own RMS immediately before starting playback — if activity has
resumed, it declines to play and reports `speak_ended` with a new
reason `politeness_abort`. The utterance is requeued, not lost. This
makes prereg metric 6's target structural rather than aspirational.

**Err toward waiting** is the tie-break everywhere, verbatim from the
parent spec: a slow system is polite; an interrupting one fails the
eval.

## 6. Question flow and the cone

**GOLDEN.** Starts when the invitation's `speak_ended` arrives (the
prereg's metric-3 zero point). Runs `AUTO_GOLDEN_MINUTES_S` (default
90; owner range 1–2 min — **owner decision 2026-08-16**, superseding
the parent spec's 2–3 minutes; the frozen prereg's metric-3 wording
is updated by logged amendment A1, owner-approved, applied in the
slice that lands this setting). Encouragers only. Early exit to OPEN
on an explicit hand-back; otherwise exit when the timer has elapsed
AND the current turn has ended (never cut a patient off at a timer
boundary).

**D2 — DECIDED 2026-08-16: strict-revise.** The parent spec says:
one question at a time, wait for the answer, let the CDS revise on
each answer. A full CDS pass is ~17 s (three sequential calls), and
segments commit ~2 s behind live — so waiting for a fresh agenda
after every answer paces the interview at roughly one question per
20–25 s. That is accepted for the first runs: after an answer ends,
auto mode triggers a CDS pass (dropping the 150-char growth threshold
to run per answer) and asks only from the fresh agenda, bridging the
wait with at most one encourager. Immune to asking what was just
answered; the prereg measures manners, not pace; the parent spec's
tie-break is "err toward waiting". `AUTO_STRICT_REVISE` stays
flippable so the mock-patient round can compare postures as a
recorded per-run threshold, per the prereg's requirement that tuning
changes between runs stay visible.

**D3 — DECIDED 2026-08-16: the topic-scoped mini-cone.** Each new
agenda topic is asked open-form once (template + topic), and every
subsequent question on that topic uses the agenda question verbatim
(usually closed-shaped). The global OPEN state then only really
governs the first minutes, and the open:closed ratio falls naturally
as topics mature — the shape the behaviour policy describes a GP
actually producing. It degrades gracefully: if the topic call fails
soft (D1), the question is asked verbatim and simply codes as
whatever it is under the frozen open/closed rule. (A global
OPEN→CLOSED switch was declined as clinically cruder.)

**HANDOVER.** When the agenda is empty after a revision, or the
doctor taps Handover: speak the anything-else follow-up once, take
the answer, then the examination-handover phrase, and auto mode ends
(state HANDOVER; standard mode keeps listening and transcribing).
The agenda-empty condition only counts on a post-answer revision —
never on a stale version.
If the anything-else answer refills the agenda on its
post-answer revision, the flow returns to the question phases
and handover waits; the anything-else phrase is spoken at most
once per session.

## 7. Urgency pause protocol

When `maybe_run_cds` produces a non-empty `urgent_actions` while the
controller is in GOLDEN/OPEN/CLOSED: cancel current and queued auto
utterances (reason `urgency_pause`), enter `PAUSED_URGENT`, and keep
listening and transcribing — pause, not termination. The live page
shows a pause banner with the alarm and two buttons:

- **RESUME AUTO** — acknowledges the alarm (audited, with the alarm's
  action text and timings) and returns to the phase it left. The
  agenda naturally reprioritises toward the alarm because the CDS
  already writes clarifying questions for urgent actions; no separate
  reprioritisation mechanism is invented.
- **TAKE OVER** — acknowledges and drops to standard mode
  (`TAKEN_OVER`). One tap, immediate.

**Ratchet:** the controller keeps the set of acknowledged urgent
action texts for the session; a re-fire of the same action after a
resume pauses again and needs a fresh acknowledgement — no automatic
ack-resume loop. An alarm still unresolved at Stop flows into the
review page's acknowledge-gated banner exactly as today; a live ack
is recorded so the review page can show who acknowledged what, when.

Confirmed by the owner 2026-08-16 after slice-1 review: an alarm
re-firing while already PAUSED_URGENT is a legal self-edge — the
machine stays paused, keeps the prior phase, and the pending
action set widens so one acknowledgement covers everything that
fired. The safety condition this creates binds slice 5: the pause
banner must display every pending action text at acknowledgement
time, so an acknowledgement only ever covers what the doctor
actually saw.

**Assessment snapshots.** Prereg metric 7 (red-flag utterance → alarm
fire → pause) needs per-revision timing that today only exists as a
log line. 7c adds the small assessment-snapshot table already named
as debt in PHASE_7B_FACE_DRIVE_SPEC §6: consultation id, version,
timestamp, urgent flag, and the pause/ack audit rows reference it.
This also gives replay a spine.

## 8. Barge-in and the doctor-always-wins posture

The measured facts stand: raw loopback 0.30–0.58 RMS against 0.056
quiet speech, residual ≈ raw, D5 unmet, `BARGE_IN_ENABLED` false.
7c therefore ships on the **hard-mute posture**: during playback the
transcriber's buffer is silence (existing mechanism) and voice
barge-in is not claimed. The doctor always wins via controls that are
always one tap away: Esc / the speaking pill's Stop (cancels the
current utterance — exists today), the Auto pill (auto off,
immediate), Take over on the pause banner. Utterances are also short
by construction (`SPEECH_MAX_UTTERANCE_S` caps the window).

If the daylight calibration later finds a passing volume, flipping
`BARGE_IN_ENABLED` upgrades rule 3 to voice cancellation with no 7c
code change — the detector stream, envelope thresholds and
`barge_in` end-reason all already exist. The calibration run decides;
this spec does not.

Between utterances the microphone is fully live (exclusion windows
only span playback), so doctor speech outside playback is heard,
transcribed and treated as intervention context. Known limitation,
stated honestly: the live transcript is unlabelled, and role
attribution at finalisation uses the falsified first-speaker
heuristic; auto mode adds machine turns (excluded) but does not fix
doctor/patient labelling. That stays with the scheduled
role-disagreement channel; the review page's correction loop is the
v1 remedy, as with #469.

## 9. Latency budget

- Encourager < 1 s: fixed phrases are pre-synthesised into the disk
  cache at service start (cache hit = 0 ms synth; play command is a
  WS message and a cached fetch).
- Question ≤ ~2 s from end-of-turn: the top agenda question (and its
  open-form variant when D1's topic call has run) is pre-synthesised
  during the patient's turn — synthesis cost moves off the critical
  path; what remains at end-of-turn is the officer call (~1 s) and
  playback start. Under D2(a) strict-revise, the budget applies from
  fresh-agenda-ready to question, and the gap from answer to question
  is the CDS pass — reported per run, not hidden.
- The officer and topic calls reuse `CDS_NUM_CTX` so MedGemma is
  never reloaded (an `num_ctx` change costs ~4–10 s).
- All thresholds in force are recorded per run, as the prereg
  requires.

## 10. UI

House pattern throughout; the three standing interface rules apply
and `test_standing_rules.py` extends to the new controls.

- Auto pill in the control row beside Sound check and Face:
  labelled, server-confirmed (an auto_toggled echo, face-toggle
  precedent), audited, hidden entirely when AUTO_MODE_ENABLED is
  false. One tap starts the auto session: if the disclosure has
  not yet been given, toggling Auto speaks it through the auto
  path (face auto-on included), chains the invitation, and GOLDEN
  begins at the invitation's speak_ended — the metric-3 zero
  point. If the disclosure and invitation were already done
  manually, GOLDEN begins at the toggle, and the audit detail
  says so. (Owner decision 2026-08-16, replacing the earlier
  disabled-until-disclosure rule.)
- **Phase indicator** on the status line while auto is on (Golden
  minutes / Open questions / Closed questions / Paused — urgent /
  Handing over), so the supervising doctor always knows what the
  machine thinks it is doing.
- **Pause banner** (§7) in the sticky row, where the doctor is
  already looking — same position class as the urgent panel it
  accompanies.
- The speaking pill and Esc behave exactly as in 7a.

## 11. Logging and schema

- `system_utterance` rows gain nothing structural: auto utterances
  reuse the table, with `ref_detail` carrying `{"via":"auto",
  "phase":..., "trigger":{"quiet_s":...,"handed_back":...}}` and
  `cds_rationale` populated from the agenda version as today. New
  `end_reason` values: `politeness_abort`, `urgency_pause`.
- Audit events: `auto.enabled`, `auto.disabled`, `auto.phase`
  (with from/to/trigger), `auto.paused`, `auto.acknowledged`,
  `auto.resumed`, `auto.takeover`, `auto.handover`,
  `auto.officer_failed` (fail-soft visibility).
- New table: `assessment_snapshot` (§7).
- Every metric in the frozen prereg maps to these sources:
  1 elicitation coverage — final transcript vs marking scheme
  (human); 2 talk-time — diarised turns + utterance durations;
  3 time-to-first-question — invitation `speak_ended` →
  first `cds_question` `requested_at`; 4 encourager discipline —
  GOLDEN-phase utterance rows with `quiet_s` triggers, zero
  questions asserted from the same rows; 5 open:closed — question
  texts exported (randomised, thirds hidden) by a small report
  script; 6 interruptions — exclusion-window starts against speech
  energy in the untouched WAV, plus `politeness_abort` counts;
  7 urgency latency — assessment snapshots + pause/ack audit rows.

## 12. Configuration (all owner-tunable, house pattern)

| Setting | Default | Note |
|---|---|---|
| `AUTO_MODE_ENABLED` | `false` | The gate. Owner's flip, after barge-in calibration + mock-patient review |
| `AUTO_GOLDEN_MINUTES_S` | `90` | Owner range 1–2 min (decided 2026-08-16; prereg amendment A1) |
| `AUTO_ENCOURAGER_QUIET_S` | `1.75` | Uncalibrated guess |
| `AUTO_ENCOURAGER_COOLDOWN_S` | `8` | Uncalibrated guess |
| `AUTO_EOT_QUIET_S` | `3.0` | Uncalibrated guess |
| `AUTO_EOT_FALLBACK_S` | `5.0` | Officer fail-soft silence |
| `AUTO_OFFICER_TIMEOUT_S` | `2.0` | Then fall back |
| `AUTO_PRESYNTH` | `true` | Pre-synthesise top question |
| `AUTO_STRICT_REVISE` | `true` | D2 posture, flippable for comparison runs |

Every setting mirrored in `.env.example` with a one-line comment;
uncalibrated values labelled as guesses naming the run that will
inform them (the mock-patient round).

## 13. Tests

`tests/test_auto_mode.py` (+ `test_auto_mode_ws.py` if the protocol
tests want their own file), pinning properties:

- Phase transitions: every legal edge, and the illegal ones raise.
- Zero questions in GOLDEN is enforced by construction (raises).
- The whitelist: nothing reaches synthesis that is not a phrase id, a
  registered template + topic, or an agenda-version question; a
  free-text attempt is refused and audited (extends the existing
  `speak`-with-text guard test).
- Urgency pause: alarm in auto → utterances cancelled, state
  `PAUSED_URGENT`, listening continues; resume returns to the prior
  phase; take-over drops out; the ratchet demands a fresh ack on a
  same-action re-fire; unresolved-at-Stop flows to the review banner.
- Politeness abort requeues, never drops, and never plays into
  reported activity.
- Officer fail-soft: model error → fallback silence rule, audited,
  never an exception into the session.
- One-utterance-at-a-time, disclosure lock, `SPEECH_MAX_UTTERANCE_S`
  hold in auto mode (regression pins on carried-over guards).
- Auto off is immediate from every state.
- Exclusion guarantee unchanged: the keystone `test_speech_exclusion`
  scenario re-run through an auto-issued utterance.

Model-dependent behaviour (officer quality, topic quality, the cone
in practice) belongs to `evals/` and the mock-patient round, not unit
tests — house rule.

## 14. Build slices (one CC prompt each, one commit per item)

1. **State machine, pure.** `app/auto_mode.py` + `test_auto_mode.py`,
   no wiring: states, transitions, whitelist types, ratchet set.
   Suite green with the module unused.
2. **Auto speak path.** Server-initiated `auto_speak` through the
   existing pipeline; `politeness_abort` reason; phrase pre-synthesis
   at start; `ref_detail` via/phase/trigger fields; audit events.
3. **Turn-taking.** Client quiet reporter (nudge generalised, guard
   comments retired), officer call + fail-soft, encourager loop in
   GOLDEN wired end to end. Dark behind `AUTO_MODE_ENABLED`. Same
   commit appends prereg amendment A1 (owner-approved wording) to
   PHASE_7C_EVAL_PREREG.md's Amendments section.
4. **Question phases.** D1 topic mechanism, D2 cadence, D3 cone,
   pre-synthesis of the top question, HANDOVER sequence.
5. **Urgency pause.** Controller pause/resume/take-over + ratchet,
   pause banner, live ack audit, `assessment_snapshot` table,
   review-page continuity.
6. **UI + config + record.** Auto pill, phase indicator,
   `.env.example` block, HANDOVER.md entry stating the gate
   explicitly (built dark; enabling waits on barge-in calibration and
   the mock-patient review), help/ flag list for any article the
   change makes untrue (owner writes replacements).

Each slice: suite green before commit, tests pin properties, nothing
weakened, `help/` never edited.

## 15. Out of scope and standing risks

Out of scope, restated: AI examination, advice/diagnosis/reassurance
to the patient, unsupervised operation, real patients, Sinhala.
The face needs nothing new (it already listens); the urgency alarm
stays unwired from the face (test-guarded). The transcript-quality
gate already discounts exclusion spans in S4; more machine talk means
more muted audio, so the S-metrics interplay is watched in the first
runs rather than re-tuned in advance. Wording of the two new fixed
phrases (anything-else follow-up; any phase-indicator labels spoken
aloud — none planned) is owner-approved before they ship.
