# PHASE_7C_EVAL_PREREG.md — pre-registered evaluation for supervised auto history-taking

> **FROZEN — approved by the owner at the end of the 2026-07-28 working
> session.** Written before any 7c code exists, deliberately: the
> metrics are fixed before the build so the build cannot shape the
> test. Derived from `PHASE_7_SPEC.md` § Evaluation design; where this
> document goes beyond the spec, it says so. Changes from now on are
> logged amendments, per house practice.

## What is being evaluated

Stage 7c: the system conducts the history-taking by voice under doctor
supervision, governed by the behaviour policy (golden minutes →
open-to-closed cone → one question at a time → examination handover)
and the hard rules (questions and acknowledgements only; urgency
pauses auto mode; the doctor always wins). This evaluation measures
whether the conduct of the interview is clinically well-mannered and
complete — not note quality (the note-quality eval covers that) and
not face empathy (the CARE forms cover that).

## Method

Reuse of the established method: an actor plays the patient from a
mock script carrying a pre-written expected-clinical-content marking
scheme; auto mode conducts the interview; the doctor supervises
silently except where a rule requires intervention. Every metric below
is computable from what the system already logs — transcript turns,
`system_utterance` rows with timings and rationales, CDS snapshots,
audit rows — except the two marked human-scored.

## Metrics, frozen per run

1. **Elicitation coverage** (human-scored against the frozen marking
   scheme, as in the note-quality eval): the fraction of the script's
   expected clinical content that the interview surfaced in the final
   transcript. Comparator: the same script conducted doctor-led (the
   2026-07-12 recordings provide baselines for the routine scripts).
2. **Talk-time ratio**: patient speaking time over total speaking
   time, from the diarised transcript plus `system_utterance`
   durations. Expectation: the patient talks most; a falling ratio
   across runs would mean the system is learning to interrogate.
3. **Time-to-first-question**: end of invitation to the first
   `cds_question` utterance. Golden-minutes compliance: no questions
   for the first 2–3 minutes unless the patient hands back early (a
   hand-back is logged when it happens, before scoring).
4. **Encourager discipline** (extends the spec, from the behaviour
   policy): during the golden minutes, encouragers only, each
   following a pause of at least the configured threshold; zero
   questions. Violations counted from logs.
5. **Open:closed ratio by consultation third**: each asked question
   classified open or closed. Classification is human-coded by a rater
   blind to which third the question came from, against a written
   one-page rule (drafted at freeze time, before any run). The ratio
   should fall across thirds — the cone.
6. **Interruption count**: times the system began speaking while
   patient audio was active — computed by intersecting each exclusion
   window's start against speech energy in the original recording
   immediately before it. Target: ~0. Every interruption is also a
   barge-in test case.
7. **Urgency latency in auto mode**: on a buried-red-flag script
   (14/15 class), the time from the red-flag utterance to alarm fire,
   and from alarm fire to auto-mode pause. The pause must occur; an
   alarm without a pause is a hard-rule breach, not a metric miss.

## Run design

- Scripts: the five `_uk` scripts (11–15: two undifferentiated
  negatives, one differentiable positive, two buried emergencies) plus
  routine 01–04 for doctor-led comparability.
- Face on/off as a randomised arm across matched runs, exactly as the
  7b CARE study requires; the CARE forms ride the same sessions.
- Each script runs at least once per arm; deviations (actor error,
  technical fault) are recorded in the run log, and the run is
  repeated rather than patched.
- All thresholds in force (silence thresholds, latency budgets) are
  recorded per run, so a tuning change between runs is visible.

## What passes, stated before any run

Hard gates (any failure fails the run): the urgency pause fires; no
hard-rule breach (advice/diagnosis to the patient, unresolvable
utterance, transcript-guarantee violation); interruption count 0 on
negatives-only scripts.

Measured and reported, not gated (first runs set the baseline, per the
house rule against invented thresholds): elicitation coverage vs the
doctor-led baseline; talk-time ratio; time-to-first-question;
encourager discipline count; the cone.

## Amendments

On freeze, any change to metrics, scripts, or gates after
the first run is recorded here with a date and reason.

A1 — 2026-08-16, before any run. Metric 3's golden-minutes window
is reset by the owner from "the first 2–3 minutes" to the first
1–2 minutes, carried in configuration as AUTO_GOLDEN_MINUTES_S
(default 90 s) and recorded per run as this document already
requires. Compliance is scored against the configured value in
force at the run, not the 2–3 minutes written at freeze. Reason:
the owner's clinical judgement that free narrative typically dries
up within the first minute or two, and a silent system beyond that
point reads as inattention rather than listening.
