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
follows like any other. A tapped examination handover ends the run
(§10, owner decision 2026-09-01). **A tap while a question is planned
or queued does not displace it silently** (owner decision 2026-09-07,
after consultation 485): the server answers with `speak_confirm`
carrying the queued question's text, the page shows a one-click choice
beside the tapped control — *ask yours instead* (the same tap re-sent
with `confirm_displace`) or *let Alba ask* — and a cancelled tap leaves
the queue untouched; the `auto.doctor_tap` row records `confirmed`
(true or false) and the displaced text. Taps with nothing planned are
unchanged. The tapped examination handover is exempt: it ends the run,
and there is nothing for the machine to ask after it.

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
5. **An agenda question in lay wording** (owner decision 2026-09-09,
   the D1 extension below): the same agenda reference as source 2, spoken
   in the topic call's plain-English wording of THAT question, admitted
   only through a code-enforced subject guard — never free text, never a
   question the agenda did not hold.

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

**D1 extended — lay wording (owner decision 2026-09-09, after
consultation 486's "risk factors like hypertension" lesson).** The topic
call returns two fields for the planned question: `topic` (as above) and
`lay` — the SAME question in plain spoken English a patient with no
medical knowledge understands: one sentence, no medical terms, no
examples in brackets, nothing the question did not ask. For a verbatim
ask Alba speaks the lay wording; the queue item, the doctor's panel and
the never-twice guarantee keep the original text as the question's
identity, and the record carries both (`spoken` beside the original on
`auto.queue_consumed`; `lay: true`, `question` and `lay_similarity` in
the utterance's `ref_detail`). Code-enforced guard, in the speech
layer's resolver as the last line and in the wiring before it: the lay
wording must share its subject with the original under the shared
normaliser — token-set similarity at or above `AUTO_LAY_MIN_SIMILARITY`
(0.3, an uncalibrated guess) — or the original is spoken verbatim and
`auto.lay_rejected` is audited with both texts and the score. An
unusable wording (`clean_lay_wording`: brackets, more than one sentence,
a statement, over-long), a timeout or a failed call → verbatim, as
today. The open-form template ask is unchanged (its topic is already
plain); the lay wording replaces only the verbatim ask.

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

- `AUTO_ENCOURAGER_QUIET_S` (default 1.75, the spec's ~1.5–2 s): the
  quiet that earns the single bridging encourager in the question
  phases while the D2 revision runs (one per revision). Zero
  questions in GOLDEN is enforced in the controller — a question
  request in GOLDEN is a coding error and raises, it is not filtered.
  **RETIRED 2026-09-09** (owner decision, "Let me think" and the
  empty-queue rule): the bridge in the question phases is replaced
  entirely by the thinking phrase `let_me_think` ("Let me think for a
  moment."), spoken at most once per wait, only when the patient's turn
  has ended and no question is ready — either the queue is empty and a
  pass is in flight (or has just been requested), or the planned
  question's preparation has already run `AUTO_THINK_THRESHOLD_S` (3.0)
  since the turn end with nothing ready (the "predicted to exceed" of
  the decision, built as "has already exceeded": the preparation's
  worst-case bounds always exceed 3 s, so a true prediction would speak
  it at every turn end). It is not a question — it does not count as
  asked, does not touch the queue, and never resets the quiet clock:
  the client does not restart its span at its end, and the server's
  judged turn end stands — audited `auto.thinking` with the reason
  (`empty_queue` | `slow_preparation`). The golden encourager rule
  below is untouched by it.

  **The encourager policy (owner decision 2026-09-01, after the solo
  pilot: "we need to get rid of the mm-hm").** In GOLDEN, at most ONE
  encourager per golden window, the phrase `go_on` only, issued only
  once the quiet has reached `AUTO_ENCOURAGER_MIN_QUIET_S` (default
  5.0 s), spent at issue (a politeness abort drops it), and never once
  the window has run (§6). The bridge in the question phases keeps its
  one-per-revision rule and speaks the same phrase. This replaces the
  rotation through three phrases on an 8 s cooldown
  (`AUTO_ENCOURAGER_COOLDOWN_S`, retired): a cooldown was the only
  brake on a loop that ran for the whole of GOLDEN, and each
  encourager restarted the client's quiet span, so the quiet could
  never reach the officer's fallback (482, 483). `mm-hm` and `i_see`
  stay registered, tappable and pre-synthesised — unused by the
  automatic flow, not deleted, like the `affecting_you` template.

  **Golden window encouragers, revised (owner decision 2026-09-09,
  after consultations 487–490; this reverses the one-per-window rule
  above).** In GOLDEN, before the window has run, an encourager may be
  spoken every time the patient has been quiet for
  `AUTO_ENCOURAGER_MIN_QUIET_S` (now 4.0 s), the quiet counted from the
  later of the patient's last speech and the end of Alba's own last
  phrase (the client's span restarts at both, so this is the span's own
  length), at most one per quiet span, spent at issue. Two phrasings
  alternate: `go_on` ("Go on.") and `tell_me_more_short` ("Please, tell
  me more."), the new phrase registered and pre-synthesised. After
  `AUTO_ENCOURAGER_MAX_UNANSWERED` (2) encouragers with no patient
  speech between them, the NEXT qualifying silence sets
  `golden_window_ran` early — audited `auto.golden_window_ran` with
  `reason: unanswered_encouragers` — so the questions begin exactly as
  when the seconds elapse (§6: the exit on the fallback quiet). Patient
  speech between encouragers resets the count. None once the window has
  run, by either end. The 1 Sept brakes stay: the minimum quiet, none
  after the window; the unanswered count is the loop's end.
- `AUTO_EOT_QUIET_S` (default 3.0; **2.0 from 2026-09-09**): outside
  GOLDEN, a pause this long triggers the **end-of-turn officer** — a
  tiny stateless model call (affect-call shape) over the recent
  committed transcript answering one schema: `{"finished_thought":
  bool, "handed_back": bool}`. Fail-soft: on error or timeout, treat a
  longer silence (`AUTO_EOT_FALLBACK_S`, default 5.0; **3.5 from
  2026-09-09**) as finished. "Handed back" (explicit hand-backs like
  "that's all" / "what do you think?") is logged when detected, as the
  prereg requires for metric 3 scoring.

  **The turn-end quiet rule to 3.5 s, with the evidence recorded (owner
  decision 2026-09-09, after consultations 489/490, finding G6).** Over
  nine clean answers the patient waited a mean 11.6 s from the last word
  to Alba's voice: the 5 s rule, ≈ 3 s of untranscribed trailing energy
  above the floor after every answer (cause unrecorded — AGC recovery is
  the candidate), and ≈ 3 s of preparation. The diagnostic's simulation
  on those turns put 3.5 s at one answer of nine cut on the pessimistic
  (transcript) reading and none on the optimistic (RMS) reading, 2.5 s
  at two; the owner chose 3.5 (`AUTO_EOT_FALLBACK_S`) with
  `AUTO_EOT_QUIET_S` 2.0. Instrumentation, so the next run can say what
  the trailing energy is: the client keeps a ring of its ~10 fps RMS
  readings for the last `AUTO_TRACE_S` (8.0) seconds and sends it with
  every quiet report — with the reading the report was taken at and the
  floor — and every `auto.turn_ended` row carries the latest trace
  (`trace`, newest sample last, `trace_step_ms`, `trace_quiet_s`,
  `trace_age_ms`); the reports themselves are audited
  (`auto.quiet_report`: quiet_s, span, since, rms, floor, fresh) at a
  bounded rate — the first report of every span always, then at most
  one per `AUTO_QUIET_REPORT_AUDIT_S` (1.0). The golden exit's own turn
  end travels in its `auto.phase` detail as before and carries no trace.

  The officer also runs during GOLDEN, where its verdict is used
  only for the exit decision — hand-back, or turn-end at the
  timer — and never to ask. Section 5's earlier "outside GOLDEN"
  wording was imprecise (recorded 2026-08-16 at slice-3 review).

  **A busy model is a wait, not a failure (owner decision 2026-09-07,
  pilot 485 defect E4).** Ollama serves the one model one request at a
  time, and in 485 all seven officer timeouts fell inside a CDS pass's
  call windows (healthy calls took 618–833 ms) — the officer was blind
  for the whole of every revision, and only its fail-soft silence rule
  let the flow reach a turn end in OPEN at all. While a CDS pass is in
  flight the officer's bound stretches to `AUTO_OFFICER_MAX_WAIT_S`
  (default 30 s) instead of `AUTO_OFFICER_TIMEOUT_S`; the deferral is
  audited as `auto.officer_deferred` with the version the pass will
  land as, and the verdict is applied when it arrives (its
  `auto.officer_verdict` row carries `deferred`). With no pass in flight
  the 2 s bound and `auto.officer_failed` are unchanged. A verdict that
  arrives after the patient has begun a fresh span of their own is
  recorded (`stale: true`, no transition) and not applied — a "finished"
  from before their new words never ends the turn they re-opened.

  **Runaway generation is capped (owner decision 2026-09-07, after
  consultation 486, finding F3).** Every model call — assessment,
  urgency, affect, officer, topic — carries a maximum output
  (`num_predict`): `CDS_ASSESSMENT_MAX_TOKENS` (1500, about three times
  the ≈ 500 a normal pass produces), `CDS_URGENCY_MAX_TOKENS` (1000),
  `CDS_AFFECT_MAX_TOKENS` (800), `AUTO_OFFICER_MAX_TOKENS` (64),
  `AUTO_TOPIC_MAX_TOKENS` (48); and the assessment call's own timeout is
  `CDS_ASSESSMENT_TIMEOUT_S` (60 s; it was the generic 180 s). In 486
  one assessment call generated 7,211+ tokens for the whole 180 s on
  Ollama's single slot, five deferred officer calls died behind it and
  the patient waited 3 min 18 s. A call that hits its cap or timeout is
  audited `cds.runaway` with tokens and elapsed and is a failed pass:
  the previous assessment is kept, the urgency check still runs on its
  own call so an alarm is never lost, a revision auto mode was waiting
  for is answered from the agenda it already has (the flow is never
  held by a pass that cannot land), and deferred officer calls fall to
  their E4 bound as designed.

  **After the golden window has run, the fallback applies whether
  or not the officer answered** (owner decision 2026-09-01, pilot
  defect D3): quiet of `AUTO_EOT_FALLBACK_S` ends the turn on the
  quiet report itself. As built in slice 3 the fallback applied
  only to a FAILED officer, so a healthy officer answering "not
  finished" to every ask — with the machine's own encouragers
  wiping the quiet span every ~8 s — held the golden minutes open
  indefinitely (consultation 483), while a failing officer exited
  at 5 s. The inversion is closed.

  **One turn-end rule in every phase (owner decision 2026-09-07, after
  consultation 485, defect E1).** In OPEN and CLOSED — and in the
  doctor's handover sequence — as already in post-window GOLDEN, quiet
  of `AUTO_EOT_FALLBACK_S` ends the patient's turn on the quiet report
  itself, whether or not the officer has answered or answered "not
  finished"; a verdict of `finished_thought` or `handed_back` still ends
  it sooner. Every turn end outside GOLDEN is audited as
  `auto.turn_ended` with `by: verdict | quiet_fallback` (§11). As built
  in slice 4 the question phases honoured a healthy "not finished"
  indefinitely: in 485 the patient answered the tapped question and the
  officer said "not finished" three times across 7 s of silence, so the
  answer never ended a turn, no revision was requested and no next
  question came before Stop — the 483 inversion, closed in GOLDEN on
  1 Sept, was still open one phase later.

  **A turn must start before it can end (owner decision 2026-09-07,
  after consultation 486, finding F5).** After an auto question is
  issued, quiet counts toward a turn end only once the client has
  reported patient speech since that question (the reporter already
  says what began each span; the server keeps a spoke-since-question
  flag per issued question). In 486 the 5 s rule ended the "answer" of
  a question 10.6 s before the patient began it, so the revision ran on
  a transcript without the answer and "Go on." was said into the gap.
  If no patient speech arrives within `AUTO_NO_ANSWER_GRACE_S` (default
  12 s) the question is re-asked once (audited `auto.reask_no_answer`;
  a deliberate re-ask, exempt from the no-question-twice rule of §6);
  if silence continues past a second grace the ordinary turn-end path
  proceeds, so silence can never trap the run. A politeness-aborted
  question asked nothing and awaits nothing.

  **Our own utterances never erase a judged turn end (owner decision
  2026-09-07, defect E2).** Every quiet report carries what began its
  span — `since: "speech"` (room energy at or above the floor) or
  `since: "playback"` (our own utterance ending). A fresh span re-asks
  the officer either way, but a judged turn end (`turn_ended`) is cleared
  only when the patient began the span or when a question is issued;
  the bridge encourager, the golden encourager and any other auto
  utterance leave it standing. In 485 the bridge 1 s after the golden
  exit erased the exit's own turn end, so the first ask needed a second
  judgement in a silent room — which, under the officer's "not finished"
  tie-break, might never have come.

**Politeness abort (interruption count ~0 by construction).** The
server never orders playback into live speech: an `auto_speak` is only
issued while the quiet window is still open, and the client re-checks
its own RMS immediately before starting playback — if activity has
resumed, it declines to play and reports `speak_ended` with a new
reason `politeness_abort`. The utterance is requeued, not lost. This
makes prereg metric 6's target structural rather than aspirational.

**The floor comes from the room (owner decision 2026-09-09, after
consultation 488, finding G2).** The number both the politeness abort
and the client's quiet reporter compare against — "this is speech, not
room noise" — was the one absolute `BARGE_IN_RMS_THRESHOLD` (0.02), and
a cafe sits above it: the sound check's quiet-room peak was 0.0085, the
owner's own speech averaged 0.0216, the enable's disclosure aborted at
0.0314, and 94 s of GOLDEN never saw 3 s of quiet. Now each auto
session's floor is derived at session start from the doctor's newest
sound check (the calibration surface that already exists): its
`noise_floor_rms` × `AUTO_FLOOR_MARGIN` (3.0), clamped to
[`AUTO_FLOOR_MIN` (0.02), `AUTO_FLOOR_MAX` (0.08)] —
`speech.auto_floor`, pure. The quiet flat (0.0031) yields exactly 0.02,
so nothing changes there; the cafe yields 0.0255; a very loud room clamps
at the max; no sound check falls back to `AUTO_FLOOR_MIN` and the record
says so (`floor_source: no_sound_check`). The floor is sent to the client
in `speech_config.auto.floor` (one number for the reporter and the abort;
the absolute floor stands in only when none arrived), recorded on
`auto.enabled` (`floor`, `noise_floor_rms`, `margin`, `floor_source`,
`floor_clamped`, the sound check's age) and on every
`speech.politeness_abort` row (`floor`, beside the reading). No recency
bound is applied to the sound check used; its age is on the row for the
owner to judge. The three numbers are uncalibrated guesses.

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

**The post-window state (owner decision 2026-09-01, pilot defects D1
and D3).** There is no timer object; the window is the arithmetic
`golden_spent + seconds in GOLDEN`, kept across an urgency pause. The
first time that arithmetic reaches `AUTO_GOLDEN_MINUTES_S` on ANY
quiet report or officer verdict in GOLDEN, the per-run flag
`golden_window_ran` is set and audited once
(`auto.golden_window_ran`, with `golden_s`). Once set: no encourager
is issued in GOLDEN (each one restarted the client's quiet span and
was the livelock's engine in 482 and 483), and GOLDEN → OPEN (the
`golden_timer_elapsed` edge) fires at the first of an officer verdict
with `finished_thought` or `handed_back`, or quiet of
`AUTO_EOT_FALLBACK_S` — evaluated on every quiet report, not only
when a verdict is applied, and whether or not the officer answered.
The window's end is now visible in the record even when it does not
coincide with an exit. Before the window, behaviour is as above.
**A window can end early** (owner decision 2026-09-09, §5): after
`AUTO_ENCOURAGER_MAX_UNANSWERED` unanswered encouragers, the next
qualifying silence sets `golden_window_ran` before the seconds have
elapsed. The record tells the two ends apart on the
`auto.golden_window_ran` row: `reason` is `elapsed` or
`unanswered_encouragers`, and for the early end `golden_s` is short of
`window_s` and the row carries the encourager and unanswered counts.
The exit that follows is the same `golden_timer_elapsed` edge either
way; the reason lives on the window row, not the phase row.

**D2 — DECIDED 2026-08-16: strict-revise; re-meant 2026-09-07 by the
standing question queue (`AGENDA_QUEUE_SPEC.md` §4, §5, D-C option
a).** The parent spec says: one question at a time, wait for the
answer, let the CDS revise on each answer. As first built, auto mode
triggered a CDS pass after every answer (dropping the 150-char growth
threshold to run per answer) and asked ONLY from the fresh agenda,
bridging the ~17 s wait with at most one encourager — accepted for the
first runs as immune to asking what was just answered. Consultation 486
measured the cost: 27.7 s mean from turn end to the next question, 74 %
of it the pass. Now the machine asks from the standing queue and the
pass never blocks the ask: at an answered turn end the next question is
planned at once from the queue's head; the pass is requested in
parallel and its merge changes the head for the ask after. Immunity to
re-asking what was answered is the queue's discard, not the wait.
`AUTO_STRICT_REVISE` now says only whether that full pass is requested
on every answer (true, the recommended cadence: the urgency check runs
exactly as often as before) or not (false: a pass is still requested
when the queue has nothing pending); it no longer says whether asking
waits. It stays flippable so the mock-patient round can compare
postures as a recorded per-run threshold, per the prereg's requirement
that tuning changes between runs stay visible. The bridge encourager
remained for the one case that still waits — nothing pending and a pass
running — until 2026-09-09, when the thinking phrase replaced it (§5).

**The empty-queue rule, as the owner restated it (2026-09-09).** Queue
empty at an answered turn end → say `let_me_think` once and wait for
the pass in flight (or request one); if its merge adds new pending items
→ ask from the head; if it adds nothing → the anything-else phrase once
(as today), then the examination handover. Later CDS questions stay on
the panel for the doctor to ask or tap.

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

**No question is asked twice (owner decision 2026-09-07, after
consultation 486, finding F4, first half; the asked-memory became the
standing question queue the same day, `AGENDA_QUEUE_SPEC.md` §2).** The
machine asks from the session's standing queue, not from the agenda
snapshot: every pass that lands while the machine is on merges its
`questions_to_ask` into the queue, and a question that matches — the E3
normaliser, exact token-set equality — an item already ASKED or
ANSWERED is discarded at the merge, whatever the pass says, so it is
never pending again and never planned again. An item is ASKED when its
question is issued (consumed by id: the planned item, not whatever is
head by then) or when the doctor taps it, and ANSWERED when its
answer's turn ends; a politeness-aborted ask goes back to pending at
its rank, and the deliberate re-ask for want of an answer (§5) is the
same item, still asked. If nothing is pending after a post-answer
revision has merged, the queue is spent and the handover sequence
follows. In 486 the agenda kept "Do you have any other risk factors…"
at the top across four versions and it was asked twice. (The slice-3
asked-and-answered list and `auto.reask_suppressed` are retired.)
**The cone's topic identity** (D3 above) uses the same normaliser with
its own threshold, `AUTO_TOPIC_MATCH_THRESHOLD` (default 0.6): "this
chest pain" and "the pain" are one topic, and the chest pain is opened
once. **Possessives are stop words** (owner decision 2026-09-08, after
slice 2 of the standing question queue found the matcher conflating
"your X" topics): your, my, his, her, their, our and its carry nothing
in the shared normaliser, so "your tablets" and "your sleep" share no
token and are two topics — before, they scored 0.636 and the tablets
were asked verbatim once sleep had been opened. The ratchet's pairs
(§7) are unchanged by it.

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
From GOLDEN, a doctor's Handover goes straight to the handover
sequence with no return path — the machine has no edge back from
HANDOVER, and a doctor handing over during the golden minutes is
taking the consultation back. The agenda-refill return applies in
the question phases. (Recorded 2026-08-17 at slice-6 review.)

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
  On resume no immediate revision is requested: the alarm-bearing
  pass's agenda is the freshest there is and already carries the
  alarm's clarifying questions, so clarification gets exactly one
  answer's chance before urgency re-evaluates at the next
  post-answer revision — clearing the alarm or re-pausing under the
  ratchet. (Owner decision 2026-08-17, replacing the
  immediate-re-revision behaviour built in slice 5.)
- **TAKE OVER** — acknowledges and drops to standard mode
  (`TAKEN_OVER`). One tap, immediate.

**Ratchet:** the controller keeps the set of acknowledged urgent
action texts for the session; a re-fire of the same action after a
resume pauses again and needs a fresh acknowledgement — no automatic
ack-resume loop. An alarm still unresolved at Stop flows into the
review page's acknowledge-gated banner exactly as today; a live ack
is recorded so the review page can show who acknowledged what, when.

**The one answer's chance, made real (owner decision 2026-09-01,
pilot defect D4).** In 482 the CDS pass already in flight when RESUME
AUTO was acknowledged landed 2.0 s later with the same action still
unarranged and re-paused, cutting an encourager after 450 ms — the
stutter the owner heard. A pass that was in flight at the resume, or
was launched before the first turn end that follows the resume, may
NOT re-pause on actions the doctor has already acknowledged; only a
pass started after at least one patient answer following the resume
may re-pause under the ratchet. The suppression is audited as
`auto.repause_suppressed` with the assessment version. A genuinely
new action text in such a pass still pauses (widening the pending
set, as slice 5 pinned), and a re-fire while already `PAUSED_URGENT`
is untouched.

**An acknowledged action does not re-pause (owner decision 2026-09-07,
after consultation 486, finding F1).** Once the doctor has acknowledged
a pending action — RESUME AUTO or TAKE OVER — a later pass that
re-issues the same action (same by the normalised match below) does
not pause the flow again. In 486 every one of seven post-answer passes
re-issued the acknowledged "Bedside ECG" with the hospital action
re-worded five ways, and the ratchet as first written paused on each:
eight RESUME taps, every question planned from the resume handler.
Nothing about the alarm clears silently: the acknowledged-but-open
actions stay on the live page in a persistent strip inside the urgent
panel (`auto_standing`, pushed on every pass landing and every
acknowledgement) until the transcript shows them arranged (the pass
then lists nothing — `arranged` latches, as today) or the consultation
ends. A genuinely new action — no match against pending or
acknowledged — still pauses and widens the pending set, as slice 5
pinned. A re-wording that matched joins the acknowledged set as an
alias of what it matched, so a chain of re-wordings (486: admission →
referral → specialist referral → admission) stays one action. Every
skipped re-pause is audited
`auto.repause_skipped_acknowledged` with both texts and the score; the
one answer's chance below keeps its own `auto.repause_suppressed` row
for the in-flight case. The sentence "a re-fire of the same action
after a resume pauses again and needs a fresh acknowledgement" above is
superseded by this paragraph.

**The ratchet matches actions by meaning, not wording (owner decision
2026-09-07, pilot 485 defect E3).** In 485 the CDS re-worded the hospital
action on every pass — "Consider hospital admission", "Immediate referral
to hospital", "Same-day specialist referral" — and a ratchet keyed on
exact text read each as genuinely new: three pauses, one 8 s after a
RESUME on a pass in flight at the resume, one cutting the doctor's own
tapped question. A candidate action is now the same pending action if a
normalised comparison matches an already-pending or already-acknowledged
action: lower-cased, punctuation and whitespace stripped, a small
stop-word list removed (urgency and hedging words, "do it" verbs,
articles, "bedside" — and, from 2026-09-08, possessives; the same
normaliser serves the cone and the queue, §6), and a token-set
similarity at or above
`AUTO_ACTION_MATCH_THRESHOLD` (default 0.6; `app/auto_mode.py`,
`match_action`, stdlib only). A reworded action does not re-pause inside
the one answer's chance; only a genuinely new action does, and it still
widens the pending set as slice 5 pinned. Every comparison that
suppresses a re-pause is audited as `auto.action_matched` with both
texts and the score (§11). Two texts sharing no token never match.

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
- Question ≤ ~2 s from end-of-turn, plus the re-ranker: the next
  question is planned from the standing queue's head at the turn end
  (topic call ~1 s, then synthesis, a cache hit when pre-synthesised);
  what remains is playback start. After an ANSWER the plan follows the
  re-ranker's verdict (`AGENDA_QUEUE_SPEC.md` §3: bounded by
  `AUTO_RERANK_TIMEOUT_S`, 2 s, ~1 s warm), so the head is chosen after
  what the patient just said. The CDS pass is no longer in the gap (D2
  as re-meant: it runs in parallel and its merge shapes the ask after)
  — and since 2026-09-09 (owner decision, pilot 489/490 G4) it launches
  only AFTER the re-ranker and the topic call have returned, bounded by
  `AUTO_SHORT_CALLS_HOLD_S`, so the short calls no longer lose Ollama's
  single slot to it (9 of 10 topic calls timed out behind the pass in
  489/490; 3.0 s mean turn end → speaking, 2 s of it that timeout).
  486's baseline to beat is a 27.7 s mean from turn end to Alba
  speaking.
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
  disabled-until-disclosure rule.) **The toggle seeds the standing
  queue** (owner decision 2026-09-08): the current agenda's
  `questions_to_ask` — passes landed while the machine was off are the
  doctor's panel and never merged — are merged at once as a pass with
  the current agenda version (`auto.queue_merged`, `seeded: true`), so
  the first ask after the golden exit comes from the queue's head and
  does not wait for the exit's own pass; an empty agenda is a no-op,
  and a toggle off and on keeps asked items asked (the seed's copy is
  discarded like any pass's). **A cut-off enable disclosure is retried,
  then the machine switches itself off** (owner decision 2026-09-09,
  after consultation 488, finding G1): the enable's disclosure — or the
  chained invitation — politeness-aborted is re-issued on the next quiet
  report, at most `AUTO_ENABLE_RETRIES` attempts in all (the enable's own
  issue is the first) inside `AUTO_ENABLE_RETRY_WINDOW_S` of the first
  issue, each re-issue audited `auto.enable_retry` with the attempt number
  and the abort's RMS; with the tries spent the machine switches itself
  off — `auto.disabled` with reason `too_loud_to_start`, the measured RMS
  and the floor — and the pill is told in plain words ("Too loud to start:
  0.031 against 0.020"). The enable never reports success while the
  disclosure has not played through: the `auto_toggled` echo at issue
  carries `starting: true` (the pill reads "Auto: starting…", the
  client's reporter is armed so its reports can carry the retry) and the
  on-echo follows the disclosure's completion. In 488 the disclosure was
  aborted 105 ms after issue at 0.031 RMS against the 0.02 floor, nothing
  re-issued it, and the machine sat in DISCLOSURE, on and silent, for 41 s.
- **Phase indicator** on the status line while auto is on (Golden
  minutes / Open questions / Closed questions / Paused — urgent /
  Handing over), so the supervising doctor always knows what the
  machine thinks it is doing. **With the golden window's remaining
  seconds** (owner decision 2026-09-01, pilot defect D7: "90 seconds"
  was being counted from the Auto toggle, but the machine's zero is
  the invitation's end): `AUTO_GOLDEN_MINUTES_S` (sent in
  `speech_config.auto` as `golden_s`) minus the `golden_spent` the
  server puts on every `auto_phase` push minus the time since GOLDEN
  was entered — counting down in GOLDEN, frozen while PAUSED_URGENT,
  cleared on exit. No new audit event.
- **The thinking state on the indicator** (owner decision 2026-09-07,
  pilot 485, item 5): "preparing a question" from the moment a revision
  is requested until the question is issued (or the handover sequence
  starts), from the server's `auto_plan` push (`preparing` → `queued`
  with the text → `idle`, sent on change, derived from the wiring's own
  state on every tick). In 485 the doctor tapped his own question 0.9 s
  after the machine had queued one, with nothing on screen to say so.
- **The guarded tap** (§3): the confirmation is shown inline beside the
  control the doctor tapped, in words, with the reason on each button;
  a choice made moot (the question issued or dropped) is taken away.
- **Pause banner** (§7) in the sticky row, where the doctor is
  already looking — same position class as the urgent panel it
  accompanies.
- The speaking pill and Esc behave exactly as in 7a.
- **The speaker-count wait after an auto run** (owner decision
  2026-09-01, pilot defect D6): finalisation of a consultation in
  which auto mode was enabled holds for the doctor's "Who spoke?"
  answer up to `AUTO_SPEAKER_DECLARATION_WAIT_S` rather than the
  25 s bound — in two of three pilot runs the supervising doctor
  answered after the bound and the answer was stored, not applied.
  While it holds, the Stop prompt, the live status line and the
  review page's finalising status all say they are waiting for the
  speaker count and for how long; the consultation API carries
  `awaiting_declaration`. Answering or Skip releases it at once; on
  expiry the run-5 ignored-declaration visibility and approval block
  apply unchanged.
- **A tapped examination handover ends the auto run** (owner decision
  2026-09-01, pilot defect D5). The doctor's one-tap "Thank you — Dr …
  will examine you now" in GOLDEN, OPEN or CLOSED is the handover: the
  same `handover_requested` edge the Handover control fires, audited
  `auto.doctor_handover` with `via=tap` (the control writes
  `via=control`) and `auto.handover` with `requested_by=doctor`; the
  officer, any queued ask and any handover sequence under way are
  stood down and the client is told the run has ended. Slice 4 had a
  tapped phrase change no flow state, so in 482 the machine said
  "Mm-hm." 1.8 s after the doctor had handed over. The run ends at the
  tap, not at the phrase's end: a cut-off phrase is still the doctor's
  decision. Outside the listening phases a tapped handover remains
  just a tap.

## 11. Logging and schema

- `system_utterance` rows gain nothing structural: auto utterances
  reuse the table, with `ref_detail` carrying `{"via":"auto",
  "phase":..., "trigger":{"quiet_s":...,"handed_back":...}}` and
  `cds_rationale` populated from the agenda version as today. New
  `end_reason` values: `politeness_abort`, `urgency_pause`.
- Audit events: `auto.enabled`, `auto.disabled` (with `reason` and the
  measured RMS, floor and attempts when the machine switched itself off
  — `too_loud_to_start`, owner decision 2026-09-09, G1),
  `auto.enable_retry` for every re-issue of the enable's disclosure or
  chained invitation after a politeness abort (the phrase, the attempt
  number, the abort's RMS, the floor, the quiet; G1), `auto.phase`
  (with from/to/trigger), `auto.paused`, `auto.acknowledged`,
  `auto.resumed`, `auto.takeover`, `auto.handover`,
  `auto.officer_failed` (fail-soft visibility),
  `auto.quiet_report` for the client's quiet reports at a bounded rate
  (quiet_s, span, since, rms, floor, fresh, the phase; owner decision
  2026-09-09, G6/G11), and `auto.turn_ended` gains the client's RMS
  `trace` of the last `AUTO_TRACE_S` seconds with its step and age (G6),
  `auto.thinking` for every "Let me think for a moment." (the reason —
  `empty_queue` | `slow_preparation` — the quiet, the seconds since the
  turn end, what was pending and whether a pass was in flight; owner
  decision 2026-09-09),
  `auto.golden_window_ran` (once per run: the window's end, with
  `golden_s`, whichever report or verdict first observed it — owner
  decision 2026-09-01; with `reason: elapsed | unanswered_encouragers`
  and, for the early end, the encourager and unanswered counts — owner
  decision 2026-09-09), and
  `auto.doctor_tap` gains `confirmed` (owner decision 2026-09-07: true
  when the doctor confirmed displacing a planned or queued question,
  false when nothing was planned) beside `displaced`,
  `auto.officer_deferred` when an officer is asked while a CDS pass is in
  flight — `quiet_s`, the phase, `pass_version`, `max_wait_s` (owner
  decision 2026-09-07, pilot 485 E4; the verdict row that follows carries
  `deferred`, or `stale: true` if the patient spoke again meanwhile),
  the standing queue's events (`AGENDA_QUEUE_SPEC.md` §7), each with the
  module's flat details and the session: `auto.queue_merged` on every
  pass that lands while the machine is on (added, refreshed, discarded
  with the items, dropped_absent, capped, pending, the version),
  `auto.queue_dropped_absent`, `auto.queue_capped`, `auto.queue_consumed`
  (the item, `by: auto | tap`, the utterance id), `auto.queue_answered`,
  `auto.queue_requeued` (a politeness-aborted ask back at its rank) and
  `auto.queue_dropped` (the wiring gave an item up, with the reason) —
  `auto.reask_suppressed` (slice 3) is retired, the discard at the merge
  having taken its place (owner decision 2026-09-07, pilot 486 F4 and the
  standing question queue); `auto.queue_merged` carries `seeded: true`
  for the merge at toggle-on (owner decision 2026-09-08); the re-ranker's
  rows (`AGENDA_QUEUE_SPEC.md` §3, §7): `auto.queue_reranked` (before,
  order, drops with reasons, ignored, ms, the protected item),
  `auto.rerank_failed` (reason, outcome, elapsed_ms), `auto.rerank_skipped`
  (`pass_in_flight` | `no_new_turns`) and `model.call` for every
  re-ranker call (kind, queued_ms, run_ms, elapsed_ms, tokens, outcome,
  pass_in_flight — the shape slice 6 of the queue extends to every call),
  the number to beat (`AGENDA_QUEUE_SPEC.md` §7): every auto question's
  `speech.requested` row and `system_utterance.ref_detail` carry
  `turn_end_to_issue_ms` from the turn end that permitted it, and
  `auto.question_latency` is written at the client's `speak_started` for
  that question with `turn_end_to_issue_ms`, `issue_to_speech_ms` and
  `turn_end_to_speech_ms` (486 baseline: 27.7 s mean turn end → speaking),
  `cds.runaway` when a model call hits its output cap or its timeout —
  the call, the reason (`cap` | `timeout`), tokens, elapsed_ms, the cap
  or timeout, the failure count and the assessment version kept (owner
  decision 2026-09-07, pilot 486 F3),
  `auto.reask_no_answer` when an auto question is re-asked once for want
  of any patient speech inside `AUTO_NO_ANSWER_GRACE_S` — the text, the
  quiet, the grace and the new utterance id (owner decision 2026-09-07,
  pilot 486 F5),
  `auto.repause_skipped_acknowledged` for every acknowledged action a
  later pass re-issued without a pause — `candidate`, `matched`,
  `score`, `exact`, the threshold and the version (owner decision
  2026-09-07, pilot 486 F1),
  `auto.action_matched` for every comparison that suppresses a re-pause
  — `candidate`, `matched`, `score`, `exact`, the threshold and the
  assessment version (owner decision 2026-09-07, pilot 485 E3),
  `auto.turn_ended` for every turn end judged outside GOLDEN — `by:
  verdict | quiet_fallback`, `quiet_s`, the phase, whether it was an
  answer's end (`answer`), and the span's verdict when there was one
  (owner decision 2026-09-07, pilot 485 E1; the golden exit's own turn
  end travels in its `auto.phase` detail as before), and
  `auto.officer_verdict` for EVERY officer verdict — quiet_s, the
  golden window elapsed when in GOLDEN, finished_thought,
  handed_back, the failure if any, elapsed_ms, the phase, and the
  transition it produced or null (owner decision 2026-09-01, after
  the solo pilot's defect D2: a healthy "not finished" left no trace,
  so the runs that never left the golden minutes could not be read
  from the record).
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
| `AUTO_ENCOURAGER_QUIET_S` | — | RETIRED 2026-09-09: the bridge it governed is replaced by the thinking phrase |
| `AUTO_THINK_THRESHOLD_S` | `3.0` | Owner decision 2026-09-09: "Let me think for a moment." once per wait when a planned question's preparation has run this long past the turn end with nothing ready (and at once when the queue is empty and a pass is running) |
| `AUTO_ENCOURAGER_MIN_QUIET_S` | `4.0` | Owner decision 2026-09-09 (was 5.0, the 1 Sept one-per-window rule): a golden encourager every time the patient has been this quiet, one per span, two phrasings alternating |
| `AUTO_ENCOURAGER_MAX_UNANSWERED` | `2` | Owner decision 2026-09-09: after this many unanswered encouragers, the next qualifying silence ends the golden window early |
| `AUTO_EOT_QUIET_S` | `2.0` | Owner decision 2026-09-09 (pilot 489/490 G6; was 3.0): the officer's trigger |
| `AUTO_EOT_FALLBACK_S` | `3.5` | Owner decision 2026-09-09 (pilot 489/490 G6; was 5.0): the turn-end quiet rule and the officer's fail-soft |
| `AUTO_TRACE_S` / `AUTO_QUIET_REPORT_AUDIT_S` | `8.0` / `1.0` | Owner decision 2026-09-09 (G6): the client's RMS trace length on every `auto.turn_ended`, and the quiet reports' audit rate bound |
| `AUTO_OFFICER_TIMEOUT_S` | `2.0` | Then fall back — with no CDS pass in flight |
| `AUTO_OFFICER_MAX_WAIT_S` | `30` | Owner decision 2026-09-07 (pilot E4): the officer's bound while a CDS pass is in flight |
| `AUTO_PRESYNTH` | `true` | Pre-synthesise top question |
| `AUTO_STRICT_REVISE` | `true` | D2 posture, flippable for comparison runs |
| `AUTO_ACTION_MATCH_THRESHOLD` | `0.6` | Owner decision 2026-09-07 (pilot E3): the ratchet's token-set similarity for "the same action" |
| `CDS_ASSESSMENT_MAX_TOKENS` / `CDS_URGENCY_MAX_TOKENS` / `CDS_AFFECT_MAX_TOKENS` | `1500` / `1000` / `800` | Owner decision 2026-09-07 (pilot F3): output caps on the pass's three calls |
| `AUTO_OFFICER_MAX_TOKENS` / `AUTO_TOPIC_MAX_TOKENS` | `64` / `48` | The short calls' caps |
| `CDS_ASSESSMENT_TIMEOUT_S` | `60` | The assessment call's own timeout (was 180) |
| `AUTO_TOPIC_MATCH_THRESHOLD` | `0.6` | Owner decision 2026-09-07 (pilot F4): the cone's token-set similarity for "the same topic" |
| `AUTO_RERANK_TIMEOUT_S` / `AUTO_RERANK_MAX_TOKENS` / `AUTO_RERANK_CONTEXT_TURNS` / `AUTO_RERANK_MAX_CHARS` | `2.0` / `200` / `6` / `1500` | The standing queue's re-ranker (`AGENDA_QUEUE_SPEC.md` §3, D-B; slice 3, 2026-09-08): its timeout, output cap, and the excerpt's turns and characters; the cap and the characters are uncalibrated guesses. The queue's own numbers (`AUTO_QUEUE_MAX`, `AUTO_QUEUE_ABSENT_PASSES`) are in that spec |
| `AUTO_NO_ANSWER_GRACE_S` | `12` | Owner decision 2026-09-07 (pilot F5): silence after an auto question with no patient speech — one re-ask at this, the ordinary path past a second |
| `AUTO_FLOOR_MARGIN` / `AUTO_FLOOR_MIN` / `AUTO_FLOOR_MAX` | `3.0` / `0.02` / `0.08` | Owner decision 2026-09-09 (pilot 488 G2): the session's politeness-abort and quiet-reporter floor is the sound check's `noise_floor_rms` × margin, clamped; uncalibrated guesses (`app/speech.py`) |
| `AUTO_LAY_MIN_SIMILARITY` | `0.3` | Owner decision 2026-09-09 (D1 extension): the lay wording's token-set similarity to the original question, below which the original is spoken verbatim; uncalibrated guess (`app/speech.py`) |
| `AUTO_SHORT_CALLS_HOLD_S` | `4.0` | Owner decision 2026-09-09 (pilot 489/490 G4): the full pass requested at a turn end waits for the re-ranker and the topic call, at most this long from when they began (`AGENDA_QUEUE_SPEC.md` §3, §7a) |
| `AUTO_ENABLE_RETRIES` / `AUTO_ENABLE_RETRY_WINDOW_S` | `3` / `30` | Owner decision 2026-09-09 (pilot 488 G1): a politeness-aborted enable disclosure or chained invitation is re-issued on the next quiet report — at most this many attempts in all, inside this window of the first issue; then `too_loud_to_start` |
| `AUTO_SPEAKER_DECLARATION_WAIT_S` | `180` | Owner decision 2026-09-01 (pilot D6): the speaker-count wait at Stop for a consultation in which auto mode was enabled, instead of `SPEAKER_DECLARATION_WAIT_S` (25 s, unchanged otherwise); on expiry the ignored-declaration path applies unchanged |

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
