# SPEC — Finalisation transcript-quality gate

Draft v2 for owner approval, 2026-07-25. Claude Cowork.
Supersedes v1 of the same date. Commits into the repo as `TRANSCRIPT_QUALITY_GATE_SPEC.md`.

Promoted from the deferred review docket to a pre-Phase-7 build item by owner decision, 2026-07-25,
as a consequence of declaring Consultation AI English-only for v1.

**Scope decision, 2026-07-25 (owner): lean core only.** v1 measures all four signals and refuses on
two of them. Flagging, approval gating and admin surfacing are a second commit, once real numbers
exist. v1 is deliberately smaller than v1 of this spec proposed.

> **REVISED 2026-07-25 after the calibration run. Read §11 first.**
> The calibration invalidated this spec's choice of which two signals act. §11 supersedes the signal
> selection in §3, the outcomes in §5, the configuration in §6 and the tests in §8, and records the
> owner-set thresholds. Sections 1 to 10 are left unchanged rather than rewritten, so the reasoning
> that was replaced stays visible alongside what replaced it.

---

## 1. Why this exists

Consultation #70. Sinhala audio went through the English-forced finalisation pipeline. The pipeline
did not fail. It produced a **fluent hallucinated English translation** — repetition loops, average
ASR confidence 0.49, the last 33 seconds silently dropped — and generated a normal-looking draft SOAP
note from it, which was presented in the review UI like any other and **approved**.

Every existing defence missed it: the note grounding gate passed because the claims *were* cited, to
turns that were themselves fabricated; the ⚠ confidence flag keys on per-turn confidence for
load-bearing content, not on whether the transcript as a whole is trustworthy; diarisation and role
assignment succeeded, which made the output look more credible rather than less.

The failure sits one level above anything the project currently checks: **the note was faithful to a
transcript that was not faithful to the audio.**

This is not a Sinhala problem, which matters now that Sinhala is out of scope. Whisper's repetition
loops occur on silence and near-silence in English. Low confidence occurs in a noisy room or with a
strong accent. Silent truncation is a mic or file problem. And the in-English precedent already
exists: consultation **#78**, where a mic-check produced a wholly fabricated angina consultation.
The note grounding gate catches that particular one now, but the failure class does not need a second
language to appear.

What declaring English-only does change: there is no supported non-English path and no prospect of
one in v1, so non-English audio has nothing to fall back on. The gate is the only thing standing
between a non-English speaker at the public demo and a fluent fabricated clinical record.

## 2. Design principle

Parallel to the note grounding gate, reusing the project's existing split of voices:

> The note is the doctor's document. The banner is the system speaking. The two must not blur.

The gate never edits, annotates or degrades note text. It refuses to produce a draft, or (from the
second commit) raises a banner above one. It does not fix the transcript, translate it, or re-run
with a different model — it detects and declares.

Boundary with an existing docket item: the *plausibility-range defence for clinical numbers*
(HbA1c 8.4 → "84", RR 18 → "80" on confident turns) stays a separate item. That is about individual
values inside a trustworthy transcript; this is about whether the transcript is trustworthy at all.

## 3. The four signals

All deterministic code in `app/finalize.py`, computed after transcription and diarisation and
**before** the note call — so a refusal costs no MedGemma time. **All four are measured and stored on
every consultation from v1, including when nothing fires**, because that is how the calibration data
for the second commit accumulates for free.

**S1 — Language mismatch.** WhisperX/faster-whisper already return a detected language and
probability. Compare against `TRANSCRIPT_EXPECTED_LANGUAGE` (`en` for v1). The #70 signature and the
strongest signal available. → **acts in v1**

**S2 — Low average confidence.** Mean per-segment ASR confidence across the transcript, weighted by
segment duration so a long garbled stretch is not cancelled by a short clean one. #70 scored 0.49.
→ measured in v1, acts in the second commit

**S3 — Repetition loops.** Degenerate repetition is Whisper's documented failure mode and was present
in #70. Detection: flag when any 4-word n-gram accounts for more than a threshold share of total
tokens, or an identical segment text repeats more than N times consecutively. The most *specific*
hallucination signal of the four — clean consultations essentially never trip it. → **acts in v1**

**S4 — Audio truncation.** Compare the last committed segment's end timestamp against WAV duration;
flag a gap beyond tolerance. Partially overlaps the existing `connection_lost` banner, which covers a
*known* drop; S4 covers a silent one. → measured in v1, acts in the second commit

## 4. Thresholds are not set in this spec — deliberately

Every number is a clinical-safety trade-off between a fabricated note reaching a doctor and a
legitimate consultation being blocked. **The first implementation task is a calibration script, not a
gate.**

`scripts/calibrate_transcript_quality.py` — run over the **five** existing real recordings,
consultations 66–70, and report per consultation: detected language and probability,
duration-weighted average confidence, worst repetition ratio, truncation gap.

That gives **four** known-good English consultations (66–69) and one known-bad Sinhala one
(#70 = 03_diabetes_review_si). Corrected 2026-07-25: an earlier draft of this spec said six
recordings by double-counting #70, which is itself the Sinhala recording.

Two consequences of n=4 that bear on the design rather than the arithmetic:

- Four good rows cannot constrain a continuous threshold. This is independent support for the
  lean-core decision — S2 and S4 must not act on four data points, and every consultation run after
  v1 ships adds a row for free.
- Consultations #66 and #68 captured off-script reader speech after the scripted close. The owner's
  2026-07-17 ruling truncates ASR-scoring references at the scripted close but leaves the recordings
  untouched, so that speech is genuinely in the audio and will move the confidence and truncation
  numbers. Report both figures for those two: over the full audio, and truncated at the scripted
  close. Do not silently pick one.

Wajira then sets the **S1 and S3** thresholds with that table in front of him; those two are all v1
needs. S2 and S4 thresholds wait for the second commit, by which time every consultation run since
will have contributed a measured row. Chosen values and reasoning go in the eval record.

Provisional values for the *calibration run only*, not for shipping: language-detect probability 0.5,
repetition ratio 0.15, average confidence 0.55, truncation tolerance 5 s.

If the five good recordings cluster close to a provisional threshold, that threshold is wrong and the
signal may not be usable alone — itself a finding worth recording.

## 5. Outcomes

**v1 — refusal on S1 or S3, independently.**

Settled by owner decision 2026-07-25: language mismatch **refuses** rather than drafting-with-a-banner.
With Sinhala out of scope there is no later path and nothing to salvage from a wrong-language
transcript — it is not a degraded document, it is a different one. A note drafted from a hallucinated
translation is the #70 harm exactly.

Refuse means: no draft note generated, status `unreliable_transcript`, review page shows the diarised
transcript under a red banner naming the signal that fired and stating no note was drafted. Transcript
and audio are retained — this is evidence, not rubbish. The doctor can read it; an admin can void it.
Same shape as the note grounding gate's refusal.

No co-occurrence rule in v1. It is unnecessary: #70 trips S1 and S3 independently, so the regression
fixture passes on either signal alone. A "two or more signals" rule would require S2/S4 thresholds
and so belongs with them in the second commit.

**Second commit — flagging on S2 or S4.**

Recorded now so the second commit inherits it, not re-litigated then: a Flag **blocks approval until
acknowledged** — 409 server-side, timestamped acknowledgement, the urgency-banner mechanism.
#70's actual failure was approval without friction, so this is the difference between a warning and a
guarantee. Amber banner, note drafted normally.

## 6. Configuration

`.env`, defaults in `.env.example`, per project convention:

```
TRANSCRIPT_EXPECTED_LANGUAGE=en
TRANSCRIPT_GATE_ENABLED=true
TRANSCRIPT_MIN_LANGUAGE_PROB=<set after calibration>
TRANSCRIPT_MAX_REPETITION_RATIO=<set after calibration>
```

**Enabled by default, including during the public demo** (owner decision 2026-07-25): a refusal in
front of an audience is embarrassing, a fabricated clinical note in front of an audience is worse and
harder to explain.

`TRANSCRIPT_GATE_ENABLED=false` must leave behaviour exactly as today, so it can be switched off
without a code change, and must log loudly when disabled. It is a break-glass switch, not a demo
convenience.

## 7. Persistence and audit

- New columns on `consultation`: `quality_signals` (JSON — all four measured values, always recorded),
  `quality_outcome` (`pass` / `refused`; `flagged` reserved for the second commit).
- Add status `unreliable_transcript` for refusals only. Refused consultations must **not** read as
  `failed` — the pipeline worked, the audio did not. Worklist badge should say so.
- Red banner reuses the urgency treatment in `theme.css`. No new colour semantics: red still means the
  system is stopping you.
- Audit: `consultation.quality_refused`, detail carrying which signals fired with their measured
  values. A count-safe event, so `errors_last_hour` stays untouched and the monitor pulse can later
  gain a `quality_refusals_today` counter — a count, per the pulse's structural rule.
- Admin surfacing of the measured signals waits for the second commit; until then the values are read
  from the database directly when setting S2/S4 thresholds.

## 8. Tests

`tests/test_transcript_quality.py`:

- **The #70 transcript as a regression fixture: it must refuse.** The single most important test in
  the file — the incident, encoded. Assert it refuses on S1 and on S3 independently.
- Each of the four good English recordings (66–69) must pass the gate once thresholds are set. If any
  fails, the threshold is wrong and goes back to Wajira.
- S1 and S3 unit-tested independently on synthetic transcripts.
- S2 and S4 are computed and stored correctly even though they do not act.
- `TRANSCRIPT_GATE_ENABLED=false` reproduces today's behaviour.
- Approve returns 409 on a refused consultation and there is no note to approve.
- The gate runs before the note call: assert MedGemma is never invoked on a refusal.

## 9. Out of scope

Re-running with a different model on mismatch; translation of non-English transcripts; live-path
language warnings during the consultation (worth doing later — warning the doctor at 30 seconds beats
warning them at Stop — but it is a separate change to `live.py` and the WebSocket protocol, which
versions with `live.html`); per-value plausibility checking, which stays on the docket as its own item.

## 10. Remaining owner decision

One, and not until the calibration table exists: the S1 and S3 thresholds (§4).

Settled 2026-07-25 and recorded above so they are not reopened: lean-core scope; refusal for language
mismatch; flags block approval when flagging ships; gate enabled during the public demo.

---

## 11. Revision 2026-07-25 — calibration findings and signal swap

Supersedes §3's signal selection, §5's outcomes, §6's configuration and §8's tests. Sections 1–10 are
retained unchanged so the superseded reasoning stays visible next to its correction, per this
project's convention.

`scripts/calibrate_transcript_quality.py` run 2026-07-25 over consultations 66–70. Turn data read from
Postgres; audio touched only for language detection and duration.

| Cid | Script | Window | Segs | S1 lang (p) | S2 wtd | S2 unwtd | S3 4-gram | S3 run | S4 gap s |
|---|---|---|---|---|---|---|---|---|---|
| 66 | 01_chest_pain_en | full | 22 | en (0.99) | 0.798 | 0.778 | 0.011 | 1 | 0.1 |
| 66 | 01_chest_pain_en | to scripted close | 21 | ″ | 0.798 | 0.781 | 0.011 | 1 | 0.0 |
| 67 | 02_febrile_child_en | full | 19 | en (0.98) | 0.804 | 0.775 | 0.012 | 1 | 1.3 |
| 68 | 03_diabetes_review_en | full | 27 | en (0.98) | 0.810 | 0.784 | 0.010 | 1 | 4.4 |
| 68 | 03_diabetes_review_en | to scripted close | 27 | ″ | 0.810 | 0.784 | 0.010 | 1 | 0.0 |
| 69 | 04_asthma_en | full | 25 | en (0.98) | 0.785 | 0.751 | 0.011 | 1 | 0.7 |
| 70 | 03_diabetes_review_si | full | 29 | en (0.90) | 0.505 | 0.494 | 0.064 | 1 | 33.3 |

### What the calibration invalidated

**S1 as specified would have passed #70.** Language detection on a single window returns English at
p = 0.90 for the Sinhala recording. This is not a harness fault: the script opens
"Good morning, Mrs. Fernando. වාඩි වෙන්න. diabetes check-up එකට නේද ආවෙ?", so the first window sees a
code-switched consultation at its most English-looking. Transcript-side detection cannot substitute,
because #70's stored transcript *is* fluent English — that is the failure being detected. Any working
version of S1 must sample the audio at multiple points.

**S3's cross-segment run length is dead.** Maximum consecutive identical segment texts is 1 in all
five recordings, including #70. The repetition documented in the #70 deviation report occurs *within*
segments, so the sub-signal as specified measures the wrong axis. The surviving 4-gram share separates
only 0.064 against 0.010–0.012 — a 5× ratio on small absolutes, too thin to refuse on.

**#68's contamination cannot be excluded by turn boundary.** Diarisation merged the scripted close and
the off-script "I don't read the script but I do naturally" into a single 54-second segment
(turn 26, 349.2–403.6 s), so #68's confidence and repetition figures are identical across both
windows by necessity; only S4 differs. Excluding that speech would need sample-level truncation at a
timestamp, which is not worth building for one recording. #66 truncates cleanly at turn 21.

### What it validated

| Signal | Good four (66–69) | #70 | Separation |
|---|---|---|---|
| S2 duration-weighted confidence | 0.785 – 0.810 | 0.505 | 0.280, nothing in between |
| S4 truncation gap | 0.1 – 4.4 s | 33.3 s | 7.6× the worst legitimate value |

The §4 concern that n = 4 cannot constrain a continuous threshold is weaker than stated: the four good
recordings cluster inside a 0.025 band on S2, leaving a wide empty corridor for a threshold. That is
the most favourable calibration outcome available from this sample.

### Decision (owner, 2026-07-25)

**The acting signals swap.** S2 and S4 act. S1 and S3 are redesigned and re-calibrated before either is
trusted to act. The signals this spec chose to act on were the two the data does not support, and the
two it demoted to measurement are the two that separate the incident cleanly.

### Thresholds (owner-set, 2026-07-25)

| Signal | Refuse | Flag |
|---|---|---|
| S2 duration-weighted mean confidence | below **0.60** | below **0.70** |
| S4 truncation gap | above **20 s** | above **10 s** |

Rationale. The S2 refusal threshold sits 0.185 below the worst good recording and 0.095 above #70,
deliberately biased toward missing a bad recording rather than blocking a good one — a refusal in
front of a patient or an audience is a real cost. S4's flag threshold clears #68's legitimate 4.4 s
off-script tail by better than 2×.

Caveats, to be revisited rather than inherited: four good recordings, one room, one microphone, two
readers, all scripted. A genuinely noisy consultation or a strong unfamiliar accent has never been
measured on this system. Because all four signals are stored on every consultation from v1, that data
accumulates without further work — revisit both thresholds once real-world rows exist.

### v1 build scope

**Refuse tiers only.** The flag tier requires the acknowledge-gated banner, the 409 approval block and
its UI, which is a second code path and precisely what the lean-core decision was meant to defer.
#70 refuses on S2 and on S4 independently, so deferring the flag tier leaves nothing about the
incident open. Flag thresholds are recorded above and their config keys exist, unused, so the
follow-up sets values rather than inventing them.

Owner may override this and take both tiers in v1.

### S1 and S3 redesign, for the follow-up

**S1, multi-window.** Detect language on k windows spread evenly across the audio (start with k = 10,
30 s each, or every 60 s for longer recordings — settle it at calibration). Threshold on the
*fraction* of windows detected as the expected language, not on any single window's probability. #70
should show English in a minority of windows. Re-run the calibration script to set the fraction.

**S3, within-segment.** Compute repetition inside each segment's text and take the maximum across
segments, rather than counting identical whole segments. Keep the cross-segment run-length figure as a
reported value, since it costs nothing, but do not threshold on it.

Neither may act until re-calibrated against consultations 66–70.

### Test changes

§8's regression assertion is replaced: **#70 must refuse on S2 and on S4 independently.** It must
*not* be asserted to refuse on S1 or S3 — under the current design it does not, and encoding that
expectation would hide the finding. The four good recordings must pass with the thresholds above.

### Configuration (replaces §6)

```
TRANSCRIPT_GATE_ENABLED=true
TRANSCRIPT_MIN_AVG_CONFIDENCE_REFUSE=0.60
TRANSCRIPT_TRUNCATION_REFUSE_S=20
# specified, not yet acting — set in the follow-up commit
TRANSCRIPT_MIN_AVG_CONFIDENCE_FLAG=0.70
TRANSCRIPT_TRUNCATION_FLAG_S=10
# deferred pending redesign and re-calibration
TRANSCRIPT_EXPECTED_LANGUAGE=en
```

### #70 as a fixture

`keep_for_research` was set on #70 on 2026-07-25, protecting its audio from the retention sweep. It is
the regression fixture for this gate and the object of study in
`evals/2026-07-25_sinhala_confound_prereg.md`. **It must never be purged.** Its correct end state is
voided and preserved — out of clinical worklists, retained in full on disk.
