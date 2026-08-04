# Pre-registration — decomposing the code-switched Sinhala ASR collapse

Designed 2026-07-25 by Claude Cowork, for owner approval. **NOT RUN. No data collected.**

Trigger to run: the UCL professor replying with interest, or the owner deciding to write up the
code-switched Sinhala clinical ASR benchmark. Not on the Phase 7 path and not a v1 dependency.

**This experiment cannot change the English-only v1 decision and is not intended to.** That decision
rests on the adjudicated finding that four of twelve curated clinical terms survive in no model. This
experiment refines the *explanation* of the collapse, which is a paper contribution, not a product one.

---

## 1. The confound this addresses

Two measured cells currently differ in three ways at once:

| Cell | Delivery | Acoustics + speaker | Content | CER (seniruk-small) |
|---|---|---|---|---|
| OpenSLR SLR52 / SLR30 | read | corpus recordings, corpus speakers | monolingual Sinhala | **0.035** |
| 03_diabetes_review_si | conversational, acted, two voices | owner's room and project mic | code-switched clinical | **0.504** |

Three variables move together: delivery (read vs conversational), acoustics-and-speaker (corpus vs
this project's room, mic and readers), and content (monolingual vs code-switched clinical).

The recordings eval reported the 0.035 → 0.46–0.50 collapse as the headline. That number is real, but
it does not by itself establish *which* factor caused it — and the natural reading, that
code-switching did, is the one claim the data cannot currently support. Any competent reviewer of the
negative result will raise this. The 0/106 English-term recall finding is unaffected by the confound
and stands on its own; only the CER decomposition is at issue.

## 2. Design — two new recordings, three contrasts

**Recording A — read code-switched clinical.** The owner alone reads the full text of
`03_diabetes_review_si.md`, both parts, as read speech. His room, project mic, same capture path.

**Recording B — read monolingual Sinhala.** The owner alone reads approximately 100 monolingual
Sinhala sentences drawn from OpenSLR text. Same room, mic and session as A where possible.

Resulting contrasts, with what each can and cannot claim:

| Contrast | Varies | Held constant | Claim strength |
|---|---|---|---|
| **A vs B** | content only | speaker, room, mic, delivery, session | **Clean.** Isolates code-switched clinical content. This is the contrast that matters most and the one the paper needs. |
| B vs OpenSLR | acoustics + speaker | delivery, content, source text | **Bundled.** Cannot separate room/mic from speaker identity. Report as one factor: this project's recording conditions and reader. |
| A vs 03_diabetes_review_si | delivery + speaker configuration | content, room, mic | **Bundled.** The existing recording is two-voice and acted; A is solo and read. Report as one factor. |

The design is deliberately not fully crossed. There is no conversational-monolingual cell, and the two
bundled contrasts stay bundled. This is accepted because the clean contrast answers the question that
matters. Two optional additions, to be decided only if the primary result is ambiguous:

- **Recording C** — both original readers re-read the 03 script as read speech, which unbundles the
  delivery contrast by holding speaker configuration constant.
- **Recording D** — a conversational monolingual Sinhala consultation, which completes the factorial.

Adding C or D after seeing results must be recorded as a post-hoc extension, not folded in silently.

## 3. Materials and contamination control

Recording B's source sentences must be drawn from OpenSLR portions **not** used in the benchmark
samples (SLR52 n=500 / SLR30 n=250, seed 42), with the selection seed and index range documented
before recording. The benchmark already caught one candidate model that had memorised SLR30; reusing
benchmarked sentences would let memorisation masquerade as acoustic robustness.

Recording A needs its **own frozen as-spoken reference**. The existing 03 reference is a transcript of
acted conversational speech and will not match a read delivery — disfluencies, false starts and
overlap all differ. Do not reuse it.

## 4. Frozen before any model output is viewed

Same discipline as the 2026-07-12 recordings eval, which is why that eval survives scrutiny:

1. Both references corrected to as-spoken and frozen by the owner's verbatim attestation.
2. The curated English-term list for Recording A frozen — reuse the existing 12-term list unchanged so
   results are directly comparable to the adjudication.
3. Model set frozen: the same three carried into adjudication — `seniruk/whisper-small-si`,
   `rrashmini` large-v2, `xlsr-sinhala`. No model added after seeing results; no model dropped.
4. Only then run `scripts/evaluate_sinhala_asr.py`.

## 5. Metrics

Per recording, per model: CER, WER, and for Recording A the mechanical English-term recall against the
frozen 12-term list. Recording B carries no English terms by construction, which is the point.

## 6. Analysis plan and pre-specified decision rules

Report all three contrasts for all three models. No post-hoc model selection.

A contrast is judged **substantial** if it accounts for at least 25% of the total observed gap
(0.035 → 0.504, so a CER difference of ≥ 0.117) in the best-performing model.

Pre-specified interpretations:

- **A ≫ B, and A vs B substantial** → code-switched clinical content is a primary driver. Supports the
  mechanism claim that monolingual fine-tuning destroys Latin-script English token emission, and
  supports the prediction that a monolingual Tamil fine-tune would fail identically.
- **A ≈ B, both high** → content is *not* the driver; the collapse is acoustic, delivery-related, or
  speaker-related. The recordings eval's framing would need correcting, and the Tamil prediction in
  PROJECT_PLAN §10 would need revisiting.
- **B ≫ OpenSLR substantially** → this project's recording conditions and reader carry significant
  weight, which weakens any content-based claim regardless of the A vs B result, and is itself a
  finding about deploying corpus-benchmarked ASR in a real room.
- **03 recording ≫ A substantially** → conversational delivery carries significant weight; consider
  Recording C to unbundle speaker configuration before claiming it.

More than one may hold. The factors are not assumed to be exclusive or additive, and no interaction
claim will be made from this design.

## 7. What is recorded regardless of outcome

The result is appended to `evals/2026-07-12_sinhala_asr_recordings_eval.md` as a further section, so
the confound and its resolution sit with the original finding rather than in a separate document a
reader might miss. If the result contradicts the recordings eval's framing, the correction goes in the
eval record's changelog, not silently into prose.

## 8. Cost

Two solo read recordings, one session. No second reader required, unlike `01_chest_pain_si`, which is
why this remains feasible while Sinhala is otherwise closed. Reference correction and freezing is the
owner's time; the harness, metrics and reporting already exist.

WAVs go in `mock_consultations/recordings/` under the existing naming convention and stay gitignored;
the Git LFS decision remains open.

## 9. Owner decisions before running

1. Approve or amend this design.
2. Confirm the 25% substantiality threshold, or set another, **before** any data is collected.
3. Confirm the model set is the adjudication three and not the full benchmark nine.

---

## Amendments

**2026-08-04 — run trigger generalised.** "Prof Henry Potts" in the
trigger line becomes "the UCL professor", under the pre-public naming
policy (real people other than the owner become role labels — owner
decision 2026-08-04). No metric, gate or design content changed: this
amendment touches one name in the trigger line and nothing else.
