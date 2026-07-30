# Open/closed question classification rule — annex to PHASE_7C_EVAL_PREREG.md (metric 5)

> **FROZEN — approved by the owner 2026-07-30.** An annex to
> PHASE_7C_EVAL_PREREG.md metric 5, required before the first 7c run.
> Changes from now on are logged amendments.

## What is classified

Every system-asked question in a 7c run, taken from `system_utterance`.
Encouragers ("Mm-hm", "I see", "Go on") are not questions and are
excluded. The invitation and the silence nudge are excluded too — they
are fixed phrases, not agenda questions, and appear in every run.

## The rule

Code **OPEN** when the expected answer is free narrative — the patient
chooses what to say and how much. Typical shapes: "Tell me more about
…", "How has this affected …", "What's the pain like?", "Describe …",
"What do you think is going on?", and standalone invitations such as
"Anything else?"

Code **CLOSED** when the expected answer is yes/no, a quantity, a time,
a named item, or a choice among offered options. Typical shapes: "Do
you …", "Have you …", "Any [symptom]?", "When did it start?", "How many
…", "How long …", "Is it sharp or dull?" Note that "how many" and "how
long" are closed despite beginning with "how" — they ask for a number.

## Edge rules, decided now so they are not decided per case

1. **Compound utterances**: code the final question asked — patients
   answer the last thing they hear.
2. **Offered options** ("is it worse walking or resting?") are closed,
   even when the patient could answer expansively.
3. **Leading questions** ("you haven't had any blackouts, have you?")
   are closed.
4. **Residual ambiguity**: if the rater still cannot decide after
   applying the above, code CLOSED. This is deliberate: the cone
   expects open questions early, so coding ambiguity as closed biases
   *against* golden-minutes compliance looking better than it is.

## Procedure

One rater codes all questions presented in randomised order with
timestamps and consultation thirds hidden — blind to position, per the
pre-registration. The coding sheet records question text, code, and
whether edge rule 4 was used; rule-4 counts are reported alongside the
metric so heavy reliance on the tie-breaker is visible rather than
buried.
