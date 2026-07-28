# SPEC — raw transcription view on the review page

Draft for owner approval, 2026-07-28. Claude Cowork. Nothing to implement until Wajira signs off.

## 1. Why

The diarised transcript is not a record of what was heard. It is a processed artifact. WhisperX transcribes the audio, pyannote clusters the voices, a merge joins consecutive segments from the same cluster, and a rule assigns Doctor and Patient.

Three of the defects found in the week of 21 to 28 July lived in those steps and not in the recognition:

- In consultation 445 the merge produced a single turn spanning 204 seconds, and the silence invariant discarded all of it to remove 12.7 seconds of muted audio.
- In recording 66 a single cluster caused the merge to join a 300-second consultation into one turn.
- In every Phase 7a consultation before 28 July, role assignment split one voice across two labels, so patient speech was attributed to the doctor.

The note is grounded in the diarised transcript. So the doctor is accountable for a document that rests on a layer they cannot see. This view lets them see it.

There is a second reason, and it is a research reason. The system already records whether a doctor opened a claim's cited transcript turn before approving. Recording whether they opened the raw view is the same class of signal, and it feeds research question 1 — does the human in the loop actually look.

## 2. What it shows

The WhisperX final-pass segments, as they were before the speaker merge and before role assignment.

Not the live transcript from the room. That is a different recogniser on a rolling buffer, it is rough by design, and it is not what the note rests on.

Not the segments discarded by the silence invariant. Those are worth surfacing one day, but they can contain hallucinated fragments from silence and would need their own labelling. Out of scope here.

## 3. Where the data comes from

**The segments must be read from storage. They must never be reconstructed by re-running the pipeline.**

WhisperX is not deterministic across runs on the same audio. Measured on 28 July: turn counts moved by up to five on recordings 67, 69 and 70 when re-transcribed. A raw view rebuilt on demand would therefore show something that never existed, presented as the record of what was heard. That is worse than not having the view at all.

CC must first establish whether pre-merge segments are persisted today. If they are not, persist them at finalisation as part of this work, alongside the turns they became.

## 4. Hard requirements

- **Display only.** Raw segments carry no turn number, are not clickable as citations, and no citation chip can resolve to one. A test asserts that a citation can never resolve to a raw segment.
- **The diarised view stays the record.** All corrections — text and speaker label — are made on the diarised view only. The raw view is a lens, not a second version of the truth.
- **No editing of any kind** in the raw view.
- **The relationship must be visible.** Each raw segment shows its timestamp, and the view makes clear where segments were joined into a single turn. Seeing the join is the whole point: it is what would have shown 445 and 66 at a glance.

## 5. The control

A labelled toggle, not an icon. It says what it does in words. Suggested wording: *Show what was heard* and, when active, *Show diarised transcript*.

The three standing rules apply in full. The control must be where the doctor is looking rather than at the top of a scrolling page. It must say what it does on itself. It must not accept a tap and do nothing.

The toggle changes the transcript pane only. It does not move or hide the note.

## 6. Instrumentation

Audit `transcript.raw_viewed` with the consultation id, the user, and the timestamp.

This is not logging for its own sake. Together with the existing citation-open records it answers a question nobody has data on: when a doctor checks, what do they check, and does checking predict catching a planted error. Record it from the start, because a study run later cannot recover behaviour that was not captured at the time.

## 7. What it must not become

A claim that nobody measures. "The raw transcript is available" is worth nothing on its own, in the same way that "a clinician reviews every output" is worth nothing on its own. The instrumentation in section 6 is what makes the difference, and it is not optional.

## 8. Tests

1. No citation can resolve to a raw segment.
2. The raw view exposes no edit path, for text or for speaker label.
3. Raw segments are read from storage. A test fails if the view triggers transcription.
4. A consultation whose merge joined several segments into one turn renders those segments separately in the raw view, with the join visible.
5. `transcript.raw_viewed` is audited on open, once per open.

## 9. Owner decisions

**D1 — Where the toggle sits.** Above the transcript pane, or in the page header beside Regenerate and Copy. Recommendation: above the transcript pane, because it acts on that pane only.

**D2 — Default state.** Diarised by default, in every case. Recommendation: yes. The diarised view is the record and the raw view is the check.

**D3 — Should the raw view be available on approved consultations.** Recommendation: yes, read-only, because the value of an audit trail is that it survives approval.

**D4 — Should it also appear on the live page.** Recommendation: no, not in this piece of work. The live transcript is already the rough one, and a second view in the room adds a decision at the worst moment.
