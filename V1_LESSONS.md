# Lessons from v1, for building v2

Written by Cowork, 4 Oct 2026. This file is for Cowork and Claude Code. It is not for Wajira to read through. V2_SPEC.md is his document; this is the working memory behind it.

Read it before any stage. Each lesson says what happened, where the evidence is, and what v2 does about it.

OpenConsult is a research and education prototype. Never real patients.

## How this was made

Six read-only passes over v1 at commit b4cd9b9 and over the v1.1 record:

1. HANDOVER.md lines 1 to 3050, read in full.
2. HANDOVER.md lines 3040 to 5720, read in full.
3. HANDOVER.md lines 5660 to 8602, read in full.
4. V1_1_PLAN.md, REVIEW_495_496.md, CODE_REVIEW_2026-10-01.md and the task reports 3F, 3I, 3L, 13, 14, 15, 16, 17.
5. A structural audit of app/, app/static/, scripts/ by counting, not guessing.
6. An audit of the 88 test files.
7. LESSONS_FOR_V2.md, written in the v1 repo by the Task 19 session on 4 Oct (commit b2e61d0). It is folded in as section 15, so v2 has one lessons file.

Cowork spot-checked the key figures against the repo and the plan. Nothing in v1 was run or changed.

Marks used below:

- **[U]** rests on a Claude Code report that Cowork has not yet checked (Tasks 13 to 18).
- **H** followed by a number is an approximate line in v1's HANDOVER.md.

## The twelve that matter most

1. **The room finds what the suite cannot.** Five room runs in July each found a serious defect no test would have caught. Auto mode was then built over six stages with no room run, and the first run livelocked. v2: a room run after the first thin part of every stage, not at the end.
2. **A model verdict must never be able to block the consultation.** The turn end was gated on a model call, and Alba went silent. v2: code decides, from sound. A model may shorten a wait and never lengthen it.
3. **Prompts do not enforce rules. Code does.** Repeated questions, re-fired alarms and the note with no content all survived prompt fixes. v2: the rule lives in code, and the prompt only helps.
4. **The model never saw Alba's questions, age or sex.** Both gaps caused clinical failures (run 495, the boy with torsion). v2: every call gets the patient line and, in auto mode, each answer beside its question.
5. **Correct-looking output hid wrong inputs.** Notes scored well over mislabelled transcripts. Approved transcripts lack whole passages. v2: check each stage against its own truth, and compare the final transcript with the live one.
6. **Feeding the model its own earlier answer anchors it.** 8 of 13 against 13 of 13 on ectopic pregnancy. v2: a fresh read every pass, earlier output only as names.
7. **One run proves nothing.** Temperature 0 with a fixed seed is not reproducible. v2: 13 chains, marks fixed before the run.
8. **Features built and switched off still cost.** Barge-in is about 1,060 lines plus 1,228 lines of tests, and it is off. v2: nothing is ported switched off. It is built when it ships.
9. **History was written into the code.** About a third of app lines are comments or docstrings, and more than half of the comment blocks are history. v2: one or two lines of why. The story goes in the record.
10. **Half the largest file is auto mode, inside one function.** 3,328 lines, 62 nested functions, two dictionaries with 82 keys. v2: a class with named fields and one handler module for each concern.
11. **Tests grew by layer, not by rule.** 1,103 tests; 188 read source files as text; 137 never call application code. A suite of about 250 to 280 would pin every rule and incident. v2: one test for each rule or incident, at the boundary.
12. **The tests and harnesses could write to real records.** The suite overwrote 83 recordings, and two real consultations are lost. v2: every data path in a test is a temporary folder, with a guard that fails if it is not.

---

## 1. Transcript and speech

**1.1 Keep the machine's voice out by construction.** v1 mutes the live buffer during playback, zero-fills a copy for the final pass, and stores what was spoken in its own table. It held in the first room run (448: 7 utterances, none in the note). H389 to H470, H1055. v2: keep exactly this shape. Text comparison is only ever a test, never the mechanism.

**1.2 A safety filter deleted six minutes.** In 445 the filter dropped any segment that overlapped a muted span. It ran after the speaker merge, so it threw away a 204 second turn to remove 12.69 seconds. A test had pinned the bug as the requirement. H711 to H772. Task 19 then changed v1 so that only the muted words are dropped, never a whole segment. v2: remove Alba's words word by word. Any defence that deletes needs a proportion rule.

**1.3 The merge, role and filter logic was untestable.** It sat inside a function that needs WhisperX loaded. It amplified errors twice (445, then recording 66: 22 turns merged into 1). H1319 to H1340. v2: these are pure functions with their own tests.

**1.4 The final transcript silently drops passages. [U]** Task 17: WhisperX dropped runs of 7 to 47 words on six of seven recordings, 300 words in all, including the action half of two safety nets. Task 18: the cause is the clinical hint text given to the final pass since 17 July, with batched decoding. 13 of 59 stored consultations have gaps of 5 s or more; seven are approved. Removing the hint costs drug names (45 to 37 of 53). The quality gate only catches speech missing at the end. Task 19 removed the hint from the final pass and added a gap check at Stop (gaps of 5 s or more, against the live transcript). The safety nets of 462 and 475 came back. Drug and test names fell back to 37 of 53. v2: a gap check whatever the speech model. Every change to the speech path is tested on whole recordings for dropped speech.

**1.5 Every speech stack reverses clinical meaning, and word error rate hides it. [U]** Task 17: no murmurs was lost and Paracetamol doesn't was reversed in all four arms. Meaning-changing rows were 31, 43, 34 and 71 at error rates of 9.67, 9.67, 10.37 and 17.09 %. In the live run 495, queasy was heard as greasy and the model built malabsorption on it. v2: benches score meaning-changing rows, lost negations and deletions. The clinician checks the reading.

**1.6 The live transcript invents words in silence.** Whisper wrote Thank you. about fifteen times in 445, on the live path only. Confidence cannot catch it; loudness separates it by more than ten times. H783 to H839. v2: no speech choice may commit text from silence. Gate the live path by energy. This matters more now, because Alba acts on live text.

**1.7 The final pass is not reproducible.** Turn counts moved by 2 to 5 on identical audio. H1310, H2852. v2: store the raw segments at Stop, the dropped ones flagged. Never rebuild a stored transcript.

**1.8 Browser audio settings were never chosen.** Echo cancellation, noise suppression and automatic gain were all on by default. Four sound checks in 32 seconds read 0.148, 0.182, 0.014 and 0.025. Every loudness threshold was calibrated on processed sound. H2588 to H2712. v2: set all three explicitly at capture, record them with every recording, and only then calibrate anything.

**1.9 Gate thresholds belong to one speech engine.** faster-whisper's confidence read 0.519 on a consultation that had passed on WhisperX. Nemotron gives no confidence at all. H2905. v2: each speech choice declares what it can provide. The gate is recalibrated for each, or flags where it cannot measure.

**1.10 The quality gate works.** 468, a news broadcast, was refused at 0.549 against 0.60. H2132. v2: keep refuse and flag. One measuring function, shared with its calibration bench. No setting without behaviour: v1 shipped keys that nothing read.

**1.11 The speech stack is held up by pins and a patch.** Three dependency overrides, a process-wide patch of torch.load (finalize.py line 476), and an import-order rule. A package that was installed and never imported produced empty transcripts with no error. H3142 to H3168. v2: each speech choice in its own environment and process. Nothing patches a library globally.

**1.12 One heavy job at a time.** Two Stops once started two finalisations on one 24 GB card. H3299. v2: one worker for heavy jobs, which picks up queued jobs after a restart. Received audio is never abandoned.

## 2. Speaker labels

**2.1 Three settings in one day, all wrong somewhere.** A fixed count of 2 split one voice (446, 447, 448). A range fixed two and broke 66. A declared count gave 8 of 8. First speaker is the doctor failed because the machine speaks first. H1118 to H1305. v2: never infer the count or the role. Ask. Alba's turns are known to the server.

**2.2 The answer arrived too late and was thrown away.** 450: the tap came 11 s late and was silently discarded. 483: it came 127 s after Stop, past a 25 s limit, and was stored but not used. H1483, H5705. v2: ask before finalising starts and wait for the answer. No short timeout on a human answer that changes the transcript.

**2.3 Labels are unreliable on every stack. [U]** Task 17: pyannote put 75.5 % of words with the right speaker (22.5 % on 462), the Nemotron live pair 62.2 %. v2: nothing safety-relevant depends on a label. Keep the per-line correction and Swap.

**2.4 Notices that could be false.** Only one voice was detected was untrue for 66. H1280. v2: a notice says what the system did, not what it believes about the room.

## 3. Model calls and prompts

**3.1 One judgement in each call. Bookkeeping in code.** Urgency failed five ways when combined, and became its own stateless call. Affect repeated the mistake as item 4 of a long clinical prompt, and read neutral every time; split out, it was right 5 of 5 in 0.85 s. H140, H2278 to H2341. v2: short single-purpose calls.

**3.2 A fresh read, earlier output as names only.** On 495 over 13 chains: revising its own answer, ectopic pregnancy was considered in 8; with no earlier answer, 13 but the list churned (50 changes against 7); with a stale list of names before the transcript, 13, 13 and 13 with churn of 20. Tasks 3b, 3c, 3d. v2: as the spec says. Pass facts, never earlier reasoning.

**3.3 A kept conversation is less safe and no faster.** Task 3f on Gemma 4 QAT: the alarm named a pregnancy test in 12 of 13; one chain copied its own empty action list for ten passes. 5.3 s against 4.9 s. Re-reading 9,000 tokens took 0.12 s. v2: send the whole transcript every pass. Never allow silent truncation of the context.

**3.4 Without age and sex the model raises wrong-sex emergencies.** Script 10, a boy of 15 with torsion: 13 of 13 chains listed ectopic pregnancy or an ovarian condition, 9 in an urgent action. With the line, none. Letters stated a wrong age in 13 of 13. Tasks 5, 5b, 5c. v2: required at entry, on every call, in every bench.

**3.5 The model never sees the answer form.** Task 5e: the note came back empty because the form is enforced outside the model's view, and empty lists are legal. Requiring one history entry gave 13 of 13 full notes. v2: describe the answer shape in the prompt, set minimum items, retry once, and show a clear failure state. This is still open for the note (spec decision D3).

**3.6 Checks must state the true reason.** The record check flagged MI at age 60 in 13 of 13, because the patient said sixty in words. One note wrote 68yo for 58, her weight. The citation check passes any turn that exists. v2: checks read number words. A citation proves a source exists, not that the claim is true; do not overclaim it.

**3.7 Prompt edits move unrelated outputs.** Reordering questions moved stability from 67 of 72 to 62 of 72. An affect edit changed another script's leading diagnosis. H1916, H2442. v2: every prompt or model change re-runs the bench.

**3.8 Each model needs its own profile.** Gemma with thinking on: 0 of 5 passes landed. Another model with thinking off: empty answers. Two models wrote the answer keys in alphabetical order, so the reasoning came after the list. The end-of-turn call flipped its answer between models (not finished 20 of 20 on one, finished 18 on the other). Task 3i. v2: when a model is chosen in settings, the app probes it: thinking, key order, caps, a short call. A model that fails the probe is refused on the control.

**3.9 Hard clinical marks before speed.** Five fast models took about 5 s a pass. Two of them missed ectopic pregnancy in most or all chains. Task 3i. v2: a model enters the list on clinical marks first.

**3.10 Caps and timeouts on every call.** In 486 one call wrote 7,211 tokens and held the only slot for 180 s; the next question took 198.6 s. H6147. v2: every call has an output cap and a timeout and fails soft. One priority order from the start: alarm, then Alba's question, then the assessment.

**3.11 Five timeouts, six default strings.** Five places build a request to Ollama. Timeouts range from 2 s to 600 s. The model default is typed in 6 files. Letters used a different context size and forced reloads (5.7 s against 2.5 s). v2: one module, one table of jobs. Each job names its prompt file, answer form, timeout, cap and failure policy. One result type.

**3.12 Stamp every output.** The review page prints a fixed model name. No model is stored with a note. Ollama moved a model tag on 30 Sept and speed changed. v2: tag, digest, prompt file hash and speech choice stored with every output and every bench result.

**3.13 Store what the model saw.** Benches used the final transcript; the live one was never stored. Live 495 never got a pregnancy test from the alarm; the bench gave 13 of 13. v1 never stored assessments at all. v2: each pass stores its input, the answer, tokens and timings.

**3.14 Alarm states the screen cannot show.** Time-critical with no action shows nothing (6 of 143 passes on 495). An alarm that drops out vanished; the review page still loses it. v2: alarm history is held in code. The flag-without-action state has a defined display. The review page shows earlier alarms.

## 4. Alba and auto mode

These come from consultations 482 to 496. The v2 loop is a new design. These are the behaviours it must not lose and the faults it must not bring back.

### Turn-taking

**4.1 Silence is decided in code, from sound only.** 482 and 483 livelocked: the silence fallback was never consulted while the model call was still answering. 485: three not-finished verdicts across 7 s of silence. H5670, H5949. v2: one silence rule in every phase. A model may shorten the wait, never extend it.

**4.2 Alba's own voice must not count as the patient.** Fixed three times. Her encouragers restarted the quiet timer. Go on erased a turn end. Let me think was heard by the microphone and re-armed itself: 8 of 11 were self-triggered. H7131. v2: from day one, the meter ignores sound during playback plus 300 ms, and Alba's speech never clears a judged turn end.

**4.3 Time silence from sound, not from text arriving.** The patient waited about 11.6 s when the log said 3.0 s. The transcriber's own commit, 2.1 to 3.7 s late, was restarting the timer. H6833, H7131. v2: the clock runs on audio. And one new seam matters more in v2: the turn can end before the last words of the answer are transcribed. Wait for the final text of the answer before making the next question.

**4.4 A turn must start before it can end.** 486: the rule ended an answer 10.6 s before the patient began it. H6096. v2: silence counts only after the patient has spoken. After 12 s with no speech, ask once more. Then move on, so silence never traps the run.

**4.5 Events, not inferences.** A question was re-asked because two quiet reports happened to carry the same value. v2: the page sends numbered speech-start and speech-end events.

**4.6 Fillers made things worse.** The bridge phrase landed into finished answers. Its replacement looped. H7131. v2: at most one short acknowledgement in a wait, and it must not touch turn state. This governs the acknowledgement in spec 9.6.

**4.7 The opening story.** Reworked three times. The end state works: a hard timer the machine itself watches, a visible countdown, an early exit after two unanswered encouragers, and the seconds kept across a pause. H6862. v2: port that end state.

**4.8 Thresholds were tuned before the cause was measured.** v2: record last word to turn end on every turn first. Then tune.

### Choosing the question

**4.9 Only code stopped repeats.** 486: a question was asked twice; the model saw the answer and kept the question. 491: two items differing by two words were asked 45 s apart. H6096, H7131. v2: giving every question and answer helps. Keep a code check as well: refuse a question that matches one already spoken, judged on the words actually spoken.

**4.10 One concrete thing in each question.** His verdict: a GP asks do you smoke, not do you have risk factors. The rewrite step widened questions further. H7348. v2: the prompt asks for one concrete thing in plain words. No rewrite call.

**4.11 A fast model call was given the power to delete.** The re-ranker dropped six of six items wrongly (0 for 7) and the queue emptied. H7143. v2: the queue is gone. The same rule applies to any judgement that the history is complete: bench it before it can stop the questions.

**4.12 The next question waited on the full pass.** 486: 27.7 s mean from turn end to Alba, 74 % of it the pass. H6232. v2 puts a model call back in this path on purpose, so it must be a small dedicated call with a cap and a timeout, and it outranks the assessment.

**4.13 What the model happened to think of.** 495: ten questions, none on the last period or pregnancy; blood in stools asked three times. 496: allergies never asked. v2: the signposted areas, chosen by the model for this patient, with code keeping track of which have been opened.

**4.14 A defined end.** v2: if the model returns nothing, try once more, then hand over. Never loop a filler.

**4.15 Doctor taps.** Keep: a tapped question counts as asked; a tap while Alba has a question ready offers ask yours or let Alba ask; a tapped handover ends the run. H6010.

### Alarm, disclosure, sound check

**4.16 The pause re-fired on rewordings.** One clinical action came back in three wordings and paused three times. 486: eight taps on Resume. H5949, H6096. v2: an acknowledged alarm never pauses again. Only a new one does. The alarm's identity is held in code, not regenerated as free text.

**4.17 On before the disclosure was heard.** 488, in a café: the disclosure was cut short and never repeated, and the page said auto mode was on. H6833. v2: show starting until the disclosure has played through; retry up to 3 times in 30 s; then switch off and say why.

**4.18 A fixed noise floor fails outside the room it was measured in.** v2: one floor for the room, taken from the sound check with the model loaded. Record the device.

**4.19 The speaking rule works.** The page sends a reference and the server resolves it; free text is rejected and audited. v2: Alba's question is authored on the server. The check on it runs on the server.

## 5. The interface

**5.1 Writing the rule down did not prevent the fourth instance.** Four swallowed actions in a week. The same defect came back in a new control three days after the first fix. H897 to H932. v2: the three rules are enforced by construction. One action helper puts every refusal on the control that was pressed. Controls the doctor must reach live in one fixed zone.

**5.2 Tests passed all through the incidents.** A test asserted the Stop control existed while it was scrolled out of sight. The suite itself records that its position checks passed throughout 449 and the control was still unusable. v2: page logic is executed in tests, not string-matched. That needs the scripts in importable files with the state logic pure.

**5.3 Only known in-progress states spin.** The live page showed processing for ever after a refusal. H774. v2: a spinner continues only for a named in-progress state.

**5.4 One long message handler.** live.html handles 27 message types in one 177-line chain, with 100 top-level variables. v2: a table of handlers, one file for each feature, and a small shared file for fetch, actions and escaping.

## 6. Code structure, measured

| Fact | Figure |
|---|---|
| app Python | 15,116 lines |
| app/main.py | 5,654 lines: 3,405 code, 1,067 comment, 827 docstring |
| ws_transcribe | 3,328 lines, 62 nested functions |
| Auto mode inside main.py | about 2,800 lines, 49 % of the file |
| Shared state | a session dictionary with 32 keys and an auto dictionary with 50, indexed about 570 times |
| Audit calls in main.py | 97, taking 459 lines; the session id is repeated 44 times |
| Database | 8 schema fragments, 7 copies of the same connect helper, 84 places that open a new connection, 25 ALTER statements |
| Settings | 138 reads in 21 files, 112 names, 124 of them fixed at import |
| Prompts | 11 prompts and 10 answer forms as strings in 6 files |
| Comments and docstrings | about a third of app lines; 54 % of comment blocks carry history |
| Functions | median 12 lines; 88 % are 40 lines or fewer; 22 exceed 80 |
| Pages | live.html has 2,496 lines of script inside the page |

**6.1 What it would save.** Estimates from the audit:

| Change | Lines saved, about |
|---|---|
| Single user: roles, registration, rate limits, queue, pulse, three pages | 2,180, plus 1,900 of tests |
| History out of the code | 1,500 to 2,000, plus 500 in live.html |
| One question at a time: queue, re-ranker, topic call, lay wording | 1,610, plus 2,694 of tests |
| Barge-in deleted, not ported | 1,060, plus 1,228 of tests |
| One database module on SQLite | 500 to 600 |
| One language model module | 250 to 300 |
| One acknowledgement mechanism for the review banners | 250 |
| One recorder for audit rows | 200 |
| One settings store | 150 of code; 360 lines of comment become descriptions |
| A small shared kit for the benches | 200 |

**6.2 The arrangement v2 takes from this.**

- An app factory. Nothing lives in process-wide state, so tests never patch a global. v1's suite once passed only in one order because a stub was left on a global.
- The live consultation is a class with named fields. One handler module for each concern: connection, transcript, assessment, speech, face, auto mode. Messages are dispatched from a table.
- One database module: one connection, one schema file, three helpers. Migrations by version number.
- One recorder for audit rows. It stamps the consultation and the audio time itself.
- One language model module with the job table (3.11).
- One settings store, read at the start of each consultation.
- One acknowledgement mechanism: one table, one endpoint, one banner.
- Audio is written to disk as it arrives. v1's sequence, acknowledge and resume protocol for dropped connections is not carried.
- One shared kit for benches: replay, scoring, the guarded writer.

**6.3 What v1 did well. Copy it.**

- auto_mode.py: a pure state machine with an explicit table of legal moves, no input or output.
- live.py: already a class with named fields.
- Pure checks split from the model call: the note gate, the letter check, the message builders.
- The quality gate's measuring functions, shared with their calibration.
- Small stores of 100 to 150 lines for one table each.
- Contracts: verdicts that never raise, output caps, the alarm call surviving a failed assessment, one context size, text to the voice on standard input, one escape function.

## 7. Install, settings, platform

**7.1 v1 cannot install on a Mac.** NVIDIA libraries are hard requirements. v2: the base app has none. Heavy libraries are in the speech environments only.

**7.2 Linux-only assumptions found.** A library preload that searches the Linux folder layout and silently does nothing on Windows. The voice command is split in a way that eats backslashes in Windows paths. Data folders are relative to wherever the app was started. Two libraries (soundfile, tzdata) arrive only by accident. v2: one device chooser; declared dependencies; data in the user's data folder; the voice run as a worker, not a new process for each sentence.

**7.3 A model that needs a login blocks a fresh install.** pyannote. v2: no gated model on the default path. Where a choice needs one, the steps are on the control.

**7.4 Packaging written without running it had three defects.** v2: a clean-machine install test on all three systems is a release gate. The app has a first-run self-test: it transcribes a short bundled clip and checks the words. v1 has such a clip already (tests/data/jfk.wav).

**7.5 Environments do not travel.** A copied environment had every path baked in. Rebuilding from the lock file took 40 s. v2: the lock file is committed; all paths come from the settings store.

**7.6 A foreign program on a fixed port broke the app.** v2: SQLite removes the database half. For the app's own port, pick a free one and say plainly if there is a clash.

**7.7 A setting for every guess.** 105 settings; auto mode alone had 36 to 38, many labelled as guesses. One flag had to be off for a study arm or the arm silently broke. v2: few settings. No threshold without a measured source. Nothing ships dark behind a flag.

**7.8 Temp files collided.** Two syntheses of the same phrase wrote the same temp file. v2: unique temp files, then an atomic rename.

## 8. Tests

| Fact | Figure |
|---|---|
| Test functions | 1,103, in 86 test files of 26,870 lines (88 files and 27,513 lines with the harness and the shared setup) |
| Auto mode and speech | 51 % of tests |
| Read source files as text | 188 tests; 159 only string-match |
| Never call application code | 137 tests |
| Assert a constant equals itself | 42 tests |
| For switched-off or report-only features | about 110 tests |
| Read private session state | 98 of 164 harness tests |
| Same helper redefined | one database check 34 times; one user maker 17 times |
| Sleeps | 47 sites; about 1,800 interpreter launches for fake speech |

**8.1 Why it grew.** Each build stage tested its own layer. Later stages tested the same property again through the socket. With never weaken or delete, nothing was ever merged. v2: test a property once, at the lowest boundary that can pin it.

**8.2 Tests that earn their place.** A leak-detecting transcriber for the transcript rule. A twin test that proves the check can fail. A test driven by the state machine's own table. The escape function run on a real payload. A fabricated note refused. v2: copy these patterns.

**8.3 Rules that were weaker than they looked.** Alarm never wired to the face was pinned only by scanning names and text. v2: pin it by behaviour.

**8.4 The harness idea is right; its build was wrong.** tests/auto_harness.py plays a whole session against a scripted model. Incidents 482 to 491 are all timing interactions that unit tests cannot reach. v2: one copy, as fixtures. An injected clock and an in-process fake voice, so no sleeps and no new processes. Assert only on what crosses the boundary: messages to the page, stored rows, event names. Scripts are timelines, so a recorded incident replays as data.

**8.5 The suite read the developer's own settings.** 42 failures from one flag in the live settings file. v2: tests never read the user's settings. A settings object is built for each test.

**8.6 Silent skips.** About 424 tests skip without a database and 33 without Node, with no sign. v2: SQLite removes the first. An unintended skip fails the GitHub check.

**8.7 Model output asserted in tests.** 11 tests assert what the model said, against v1's own rule. v2: benches only.

**8.8 The policy.**

Write:
1. One test for each rule or incident, named for it, with a twin that proves it can fail where a silent pass is possible.
2. Table-driven tests for the state machine and the gates.
3. Behaviour at boundaries: messages, stored rows, results of pure functions.
4. One scenario for each auto-mode incident, through the one harness.
5. Exact-wording tests only for words spoken to the patient.

Never write:
1. A test that reads a source file, a page, a settings file or another test.
2. A constant asserted against itself.
3. An assert on private state, log wording, prompt wording, call order or the full set of keys in a record.
4. A test of what a model, a speech engine or the voice produced.
5. A test for a feature that is off.
6. A second test of a property already pinned lower down.

**8.9 Size.** About 250 to 280 tests and 5,000 to 6,000 lines would pin every rule and incident found. Single user and the dropped queue reduce that further.

## 9. Benches

**9.1 Thirteen chains, counts not percentages.** Task 3: 8 of 63 identical requests differed. One run never reached ectopic pregnancy and the next led with it. v2: keep the method of 3 chains at temperature 0 and 10 at 0.5.

**9.2 Marks fixed before the run worked.** Twice a change was rejected by rules fixed beforehand (the kept window, the note line). v2: keep.

**9.3 Keyword rules and expectations were sometimes wrong.** Last period missed last normal period. One mark expected silence that no model gave, and was dropped. v2: the clinician sets the expected behaviour for each case; rules carry lists of synonyms; failures are re-read clinically.

**9.4 Benches must be unable to write to records.** v2: results go outside the repo by default. Baselines cannot be overwritten. Checksums before and after.

**9.5 The bench set was chosen wrongly, twice. [U]** A survey missed the compressed recordings. Old recordings predate the capture change. One file is silent after 165 s. Claude Code cannot listen, so probably spoken that way was a guess. v2: a list for the new recordings with the script, the speakers, the capture settings, a checksum and the words as actually spoken, checked by ear.

**9.6 The reference arm is re-run on the same day.** Model tags move. v2: digest with every result.

**9.7 Measure before diagnosing. One change in each arm.** The review guessed that reading the transcript was slow. Task 3 measured 93 % writing and 4 % reading.

**9.8 Check each stage against its own truth.** Good notes hid wrong labels. v2: the transcript, the labels, the assessment and the note are each scored on their own.

## 10. Security and data

**10.1 Tests once ran against the live database.** 489 test accounts, about 131 of them admins with one shared password, were found in it. H4141. v2: a test database is always a throwaway file.

**10.2 Exposure forced a whole defence stack.** Approval of users, rate limits, proxy trust rules, a public pulse. v2: the app listens on this computer only. The secret is generated at first run. No registration.

**10.3 Files and rows drifted apart.** 28 recordings with no row. v2: the row is created first. A sweep at start-up reports orphans.

**10.4 A voided record was unvoided twice by accident.** A written lesson did not stop it; a guard in code did. v2: a repeated incident gets a guard.

**10.5 Delete must really delete.** The launch sweep found a consultation voided but not purged. v2: one delete that removes the audio, the transcript and the note, and leaves an audit row.

**10.6 Hygiene from the first commit.** v1 retrofitted it, after private details had already been committed. v2: sensitive file classes are ignored from commit one. The example settings hold no real value.

## 11. Process and documents

**11.1 Six stages built dark, then the first room run failed.** 7c took the suite from 689 to 938 tests before any room use. H5483. v2: one room run after the first thin part of each stage.

**11.2 Every stage decided things the spec had not.** Then tests were re-pinned. v2: specify only what the next room run will exercise. The brainstorm at the start of each stage and sub-stage is where this is settled.

**11.3 Specs lived outside the repo.** Three were lost and rebuilt from the code. One session ran an earlier draft of its prompt. v2: the spec is committed before the code. Prompts for Claude Code are files in the folder.

**11.4 Unchecked reports compounded.** Tasks 13 to 18 ran in a day. Task 15's errors forced Task 17, which reversed its conclusion. v2: no bench is built on a report Cowork has not checked.

**11.5 Unpushed work piled up.** Seventeen commits waited, and the service ran old code. v2: small units, each with a check on the screen and a push.

**11.6 Documents drifted at every change.** Help pages went untrue. The record doubled as the manual and reached 8,602 lines. v2: one current document. History lives in git. Each task lists what it makes untrue.

**11.7 What worked.** Report-only diagnosis with file and line, then his decisions, then one commit for each. Cowork recomputing from raw files caught slips by Claude Code and by itself. His ideas were measured, not assumed.

## 12. Built, then switched off or closed

| What | What happened | v2 |
|---|---|---|
| Barge-in | Built, calibrated, closed negative: the browser removes only 5 to 10 % of the playback echo | Hard mute, a Stop that is always visible |
| The face engine | Five sessions and a rewrite in four days. It smiled through a chest pain history. After the rewrite the engine's own dynamics were unused | Keep the look. Drive it from a plain table. See spec decision D43 |
| Sound check as a measurement campaign | Two of three thresholds were guesses | One play and confirm. The human answer rules |
| Sinhala | Closed negative | Not carried |
| faster-whisper alone for the final pass | 13 turns against 22, drift of 5 to 53 s | Any speech choice must give word timings |
| Signal S1 | Measured only | Not carried until it acts |
| The public pulse | Read a cached value for a day and produced a confident wrong report | Not carried |
| Docker as the install route | Three defects on first real run | The installer |

## 13. Open items v2 inherits

- The empty note, the number-word check, the reason shown on the review page. The note is the one call without the patient line.
- The silent alarm state. Dropped alarms on the review page.
- Script 12 false alarm; restraint scripts 11 and 12. These are prompt work.
- Dropped passages: fixed in v1 by Task 19 (not yet checked by Cowork). Seven approved records still hold their old transcripts. One gap, in consultation 79, is unexplained. [U]
- Drug names: 37 of 53 without the hint. Not solved.
- Recordings 68 and 161 are lost.
- The Nemotron switch is unchecked and unpushed. [U]
- The note, letter and guideline evaluations have not been re-run on Gemma 4.
- Qwen's key order.

## 15. From the speech work of 3 and 4 October (LESSONS_FOR_V2.md)

The points below are the ones not already covered above. Figures are as that file gives them. Where it marks a point not verified, so does this.

**15.1 An invisible error is worse than a visible one.** A dropped passage cannot be seen on review. A misspelt drug name can. v2: errors are made visible. The gap check at Stop is a requirement whatever the speech model.

**15.2 The hint was checked for the wrong thing.** It raised drug and test names from 37 to 45 of 53. It also dropped speech for eleven weeks: 13 of 59 stored consultations had gaps of 5 s or more, 264 s in all, 7 of them approved. The hint caused 12 of the gaps, in 10 consultations. The planned check looked at drug names only. v2: see 1.4.

**15.3 Drug names are not solved.** Without the hint, gliclazide was missed 3 of 3. Ideas not yet tested: correct names when the note is written; check against a drug list after transcription; the hint with timestamps on (losses fell from 6 to 1 on the ten readings); decode a short piece again without the hint.

**15.4 A claim in the help pages needs a test behind it.** The help said a transcript with missing speech is refused. Only speech missing at the end was.

**15.5 Recordings.** Written once, never overwritten. Backed up apart from the app. A guard fails any test run that touches them.

**15.6 Capture decides the bench.** Echo cancellation on the stored stream was turned off on 29 July. On the July recordings Nemotron looked far worse than WhisperX (24 meaning changes against 10); on seven later readings the gap almost closed (34 against 31). That capture caused the difference is not verified. v2: store the capture settings with each recording; bench only on recordings made with the current capture.

**15.7 How to bench speech.** Select recordings from the database, not by file type. A script gives a true error rate; without one a bench can only count disagreement. Where every model agrees against the script, treat it as spoken that way. One recording is not a test. Feed a file in live-sized pieces; do not play it through a speaker. Write each note at least twice.

**15.8 Nemotron, as measured.** The models fit: 20.6 of 24 GiB with Gemma 4, its embedding model and both live Nemotron models. About 37 times faster than real time. Run live, 0.03 s of work is left at Stop. The paired setup is the weakest (71 meaning changes); the English model alone gave 34 and dropped no lines. Live, it heard the second voice 4 to 11 s late on four recordings, only at Stop on one, and never on two. Licences: the English model is under the NVIDIA Open Model License, the other two under OpenMDW-1.1. v2: if Nemotron is used, the English model runs on its own for the words. Check the licences before anything is bundled.

**15.9 One user, one known voice.** v2 has one user, so the doctor's voice can be enrolled once and every line labelled doctor or not doctor. An idea to bench (spec decision D53).

**15.10 The wait at Stop.** 17.8 s on one consultation: 10.2 s for the audio pipeline, 2.5 s for the model switch. About 26 GiB is needed for Gemma 4 and the audio models together, more than the card. In Task 19 WhisperX could not load beside Gemma 4. Not yet tested: keeping WhisperX and pyannote loaded beside Gemma 4. The embedding model could run on the CPU (not verified).

**15.11 Laptops (not verified).** Nemotron speech runs on Apple and AMD laptops through lighter runtimes, not through NVIDIA's own toolkit. Those runtimes are young; one export has no word timings.

**15.12 Not yet done.** Live two-actor consultations on Nemotron. Auto-mode timing in a room with Nemotron. A bench that judges the note written from each set of speaker labels. The scripted bench repeated with the fixed WhisperX against Nemotron English alone.

## 14. Where the sources disagree

- Whisper final-pass word error: 3.65 % on Task 15's set, 9.67 % on Task 17's.
- Task 15 says 84 files of 11 s; Task 16 says 83 fixtures plus one real recording.
- Task 15 excluded 495 and 496 by account; Task 16 disputes it.
- Comment share: the audit counted 30.9 %; Cowork's own count gave 33.6 %. Both say about a third.
