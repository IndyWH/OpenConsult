# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-18. Run 9c: one picture of This machine, a tick or a choice that saves by itself, the mends from the room check of run 9b, and the two thresholds of the gate within the owner's bounds

Run on 17 and 18 Nov 2026 by the mailbox, as one run in two halves
(15.13, ruling 58), under the owner's okay given in advance (17 Nov,
23:31) and Cowork's review of the plan. The spec is e9a7ac8 (sha256
78c7d692...), the stage prompt 59521c1 (stage-prompts/STAGE_09C.md).
The private report is STAGE9C_REPORT.md in the log folder, with the
plan and its review beside it. Twenty-three commits, none pushed. The
suite: 1273 passed in about 129 s, none skipped (1114 at the start). No
prompt file, frame or form changed: the two prompt folders are as at
18cc922. No engine was started; the Ollama service was not touched.
Half one stood by itself at 85e3f2e, suite 1228, and needed nothing of
half two.

The two thresholds of the gate (7.3) were built last (158339f), when
the owner's bounds came by mail 2 on 18 Nov at 06:39: the fewest words
a note is drafted from, 30 to 300, default 60; the score under which
a line is marked as low confidence, 0.40 to 0.80, default 0.60
(settings/thresholds.py, with the reason for each bound). Each is a
typed field under Thresholds with its own Save; a value outside the
bounds is refused on the control; a change is audited. A consultation
takes both at Start into its own row, and its gate and its review
page read them there: a change in Settings never reaches one that has
begun. A row from before holds neither and reads the defaults. Seen
in the browser: saved, refused one step outside each bound, each
bound taken, and three made consultations each judged by the values
it started with while Settings held others.

For the patient. Before a consultation the doctor sees on one picture
whether the path chosen is ready and what leaves the computer: four
columns, Microphone, Transcription, Language model, Consultation, each
box Ready, Not set up or Cannot run here, the chosen path marked, and
each cloud box saying what goes to it on that path, or that nothing
does. A setting the doctor believes is set is set: a tick or a choice
saves by itself, and a choice that sends something new off the
computer is saved only by the tick under its statement. The page no
longer claims what it cannot show: the mark says went only where the
recording can have gone, a delete is called confirmed only when it
is, and no line names a speech model for a transcript another made.

Half one, the mends (15.13, rulings 47 to 53).
- The owner's sentences (52, 53): fourteen lines proven letter for
  letter against the file of words (tests/test_owner_sentences.py).
- The second ask after a delete (49; speech/upload.py): an ask that
  brought no answer at all is made once more, 5 s later, with a limit
  of 10 s, never a third time; an answered ask never again. Both tries
  in the record. The first asks keep the upload's 300 s.
- The mark's line (52): on the review page After Stop the recording
  went to Speechmatics. wherever the request that carried it was made
  and the record cannot show that nothing left; left out only where
  no connection was opened at all, or the request was never made. The
  record gained that fact: THE TABLES ARE VERSION 12, three columns:
  recording_upload.request, and the two thresholds on a consultation
  (Cowork's word: they join 12). A folder of version 11 comes forward.
- The gate judges by the speech choice that made the final transcript
  (consult/stop.py), and the model line names both where the service
  made it.
- A save by itself (47; static/settings.js, place.js): the two
  choices, the speech model, the tick for better accuracy and a
  statement's own tick. A choice that needs a statement comes back
  with it and the line that it is not saved yet; nothing of it is
  kept. Every form is served with a Save that works with no script.
- No new tick for less (48; settings/stored.py, statement.py): with a
  tick the app keeps the sentences of What is sent and of each
  service's part, and one checksum of every word a statement can be
  built from. A path whose sentences all stood in the ticked one is
  saved under the wider tick, audited with both checksums; a changed
  word anywhere asks again. Every pair of paths is a test.
- The Start screen at once (51; web/start_tests.py, static/start.js):
  the tests run beside the page; a press that names a run still
  running is refused by the app; a run answered within 60 s is used;
  else tested at the press. With the tick alone Start does not wait.
- The round buttons: a radio gets what a tick box gets (theme.css).
- The README's paragraph, with Cowork's four sentences (50).

Half two (15.13, rulings 6, 56 and 57; 7.3).
- The control panel (web/panel.py; the macro control_panel): one
  picture at step 2 of the first run and at the top of Settings. A
  box is the browser's own disclosure: one sentence, one action,
  Connect, Test or Choose; no Download, no box for Alba. Nothing is
  tested or asked for a view. The boxes go to the audit log once at
  start. The small table keeps the system, the card, the guideline
  search and the converter.
- The speech model of this computer (web/settings_local.py): Nemotron
  or WhisperX with pyannote, under Transcription. Chosen, it alone is
  used; never saved, the app reads as before.
- Local models: what is installed with its size on the disk, read
  only (settings/installed.py); sizes measured once in a run.

Measurements, as counts.
- The port after a stop: 40 stops of a made consultation served as
  the command serves it, a page connected as a browser holds it. In
  all 40 the process ended 0.15 to 0.27 s after Ctrl-C and a server
  could bind within 0.12 s, but the app's own check before a start
  called the port taken until 60.2 to 64.0 s, held by two or three
  closed connections waiting out their time in the system. A fault of
  the check, which bound with no reuse option: mended (85e3f2e). With
  the mend, 4 stops: free after 0.07 to 0.12 s.
- The test of the Speechmatics connection, 30 times, 20 s apart, at
  its EU address, no sound: 30 passed, 0.12 to 0.21 s, middle 0.14;
  the worker up in 0.03 s. No fault of the app shown; nothing changed.
- What left the machine: eu.rt.speechmatics.com, 30 connections. No
  other name in any step. No call to Claude.
- Seen in a real browser against made services: a profile that had
  seen 18cc922 ran only the scripts as built; each save by itself with
  the page's place kept; a statement waiting, ticked, and the page
  loaded again; less saved with no tick; the round buttons at two
  widths; the Start screen shown in 8 ms and filled in after 0.6, 3.1
  and 10 s; the picture for each path, on a fresh folder and in
  Settings; a made consultation with the tick, the delete confirmed,
  not proven, and proven at a second try. Two faults found there and
  mended in a commit of their own.

A fault of this run, found by its own record of connections at the end
checks and closed in a commit of its own (2b94c65). Two older tests
undo their own patches in their middle and build the app again; the
suite's guards were set by the same patcher and came off with them.
Since the panel writes its boxes to the audit log at start, the app
asks the secure store for its two key names at every start, so in
seven runs of the suite those two tests asked the machine's real
store (8 connections to the session bus in each run; no value
printed, written or sent; no test of a connection made). The guards
now have a patcher of their own, and a test pins it.

Older tests restated, each to prove the same fact where it now stands:
for rulings 47, 48, 51 and 52 seven tests of run 9b; for the panel the
tests of the rows of This machine (test_machine_status,
test_speech_machine, test_connect_screens); and two the plan did not
foresee: test_db_v11 (it ended at today's version) and test_pages
(the count of the audit lines written at start).

Flags for the owner, each in the report: the review page does not say
which two values a consultation was judged with, except the fewest
words in a refusal's own sentence; a refused value leaves the field
showing the saved one; the first asks after a delete keep 300 s
each; the details
say a speech choice's models are in the data folder, and they are in
the hub's own cache, so Local models counts the environment and says
so; the self-test of Speechmatics as a speech choice is no longer on
This machine; version 12 came in half one; the app now reads the
secure store for both keys at every start, where before it read only
the keys of the chosen path. words.py and schema.py are over their
targets.

Made untrue, and put right: the README (the picture, the speech
model, Local models, the Start screen, the two thresholds),
CLAUDE.md's run line. Not mine to write: the spec's details of run 9c
say that half one changes no table. No help page exists.

Next: the owner's room check of 9c, one sitting, the first step to
stop the app and start it again.

## 2026-11-16. Run 9b: cloud mode. A consultation can run on Claude and Speechmatics, said before anything leaves, marked while it runs; a recording can be sent once after Stop and is deleted there

Run on 16 Nov 2026 by the mailbox, as one run in two halves (15.13,
ruling 35), under the owner's okay of the plan (00:52) and Cowork's
review of it; three questions went by mail and were answered. The spec
is a17ed6c (sha256 8c5a7e85...), the stage prompt c7419b0
(stage-prompts/STAGE_09B.md). The private report is STAGE9B_REPORT.md in
the log folder, with the plan, its review and the first act beside it.
Twenty-four commits since 0631413: the twenty-two of the run (the last
11275de), the spec with Met (8438975) and the line for Windows
(18cc922). The suite: 1114 passed in about 111 s, none skipped (985 at
the start). No prompt file, frame or form changed: the two prompt
folders are as at 0631413. vLLM was left as found; the Ollama service
was not touched.
Pushed by the owner on 17 Nov 2026. Met on 17 Nov 2026 by his room
check in two sittings (15.13, Met for run 9b). GitHub's check is green
on the three systems at 18cc922: the Windows check had failed on one
test, the hash of why_this_model.md, for the line ends, and its line in
.gitattributes mended it.

For the patient. Until this run nothing a patient said could leave the
computer, and a computer with no suitable card could not run a
consultation at all. Now it can, on two cloud services, and the app
says so three times over: in a statement, built for the doctor's own
choices and ticked before Start is offered, of what is sent, what stays
and what each service keeps; in a Cloud mark on the Start screen, the
live page and the review page for the whole of a consultation; and in
the record. When the connection is lost the page says at once that the
emergency alarm has stopped listening. A recording that is sent after
Stop is deleted at the service as soon as the transcript is back, the
service is asked again, and the doctor is told whether it is gone.

What was built (15.13, rulings 25 to 35 and the details of 9b).
- Keys (7.2). The connect screens for Claude and Speechmatics test a
  pasted key before it is kept, and keep it in the system's secure
  store alone (the keyring package, MIT, with eight behind it; cffi
  under MIT-0 by the owner's reading). Read order: store, environment,
  the file .env. No store that answers in 5 s: nothing saved. Each
  reason of a failed test stands on its screen. Connections in
  Settings: Test, Remove. The test is six words to each of Claude's
  two models, or a session opened and ended with no sound; 10 s.
- The path (7.3; 10.3). Two settings and one tick: the language model
  and the transcription, each on this computer or at its one service,
  and Better accuracy. With no suitable card both begin in the cloud.
  A cloud choice is refused without its connection and without the
  statement for the path as it would stand ticked; a changed word
  asks for the tick again (a checksum). A consultation holds the path
  it started with and no call falls back to another (10.4).
- Claude behind the app's door: Claude Haiku 5.5 for every job, Claude
  Sonnet 5.5 for the drug-name call alone (ruling of 15 Nov). The
  engine moved from the bench to llm; the bench keeps its effort, its
  waiting and its stops. What the model saw says what Claude adds.
- Speechmatics live, at its EU address. AssemblyAI is no choice of the
  app; its worker and its choice are the bench's alone (ruling 28).
- A lost connection (ruling 29): said at once, the recording goes on,
  tried again every 10 s, each session's speakers asked about apart,
  the stretch with no transcript a warning, and at Stop two presses:
  send the recording once, or go on without it.
- The recording after Stop (15.9, rulings 36 and 42; consult/whole.py):
  by the tick or by the one press, once, as recording.wav to the EU
  host alone; the stage with its seconds; delete, asked again, both
  answers kept; three lines for the review page: made and gone, made
  and not proven gone (the owner's sentence), not made. A failure is
  never followed by a second sending.
- The first run (7.1): connect the language model, connect
  transcription, the self-test from its page, the microphone test (not
  stored, not sent), each with Not now. A folder set up before them meets them
  once, at its first login (the owner's choice, by mail).
- The page Why this model, Cowork's draft byte for byte (ruling 30).
- The tables are version 11: the path and the statement's checksum on a
  consultation; speech_session; recording_upload; first_run_left. A
  folder of version 10 comes forward with every row.

Measurements, as counts.
- The first act, before any commit: Speechmatics on three recordings,
  live and whole, as on 10 Nov. Six results, no failure. 904.8 s live
  and 903.0 s whole, about 0.39 US dollars by the list prices. Results
  6.3, 5.3 and 11.2 s after the upload. Deletes 4 of 4, each proven.
  Settings as on 10 Nov; the service's build line had moved. Both hard
  marks held on all six pages: 0 and 0.
- Five real calls, each once. The alarm call to Claude Haiku: 1,511
  tokens read, 361 written, 4.0 s. The drug-name call to Claude Sonnet
  on one stored page: 3,258 read, 120 written, 6.2 s, 4 entries kept.
  The app's test of Claude: two requests of 18 and 4 tokens, 0.9 and
  1.3 s. Its test of Speechmatics: a session in 0.17 s, no sound. The
  gate clip through the app's upload: result in 2.66 s, 22 of 22
  words, deleted. Language model cost 0.0081 US dollars.
- What left the machine: api.anthropic.com (8 connections),
  eu.rt.speechmatics.com (5 sessions), eu1.asr.api.speechmatics.com
  (43 connections). No other name in any step.
- Seen in a real browser against made services: a profile that had
  seen 0631413 ran only the scripts as built; each connect screen
  through failed and passed tests; the statement and its tick; the
  mark; a session lost and found again in 10.2 to 10.3 s; the question
  at Stop; the first run on a fresh folder; the tick, with a good
  upload, a failed one and a delete not proven. The Start screen shows
  in 0.3 s when the services answer and in 10.3 s when one does not.

A fault of this run, found by its own record of connections and closed
in a commit of its own: four older tests build the app in a fresh
Python, outside the suite's guards, and from the store's commit on that
child asked the machine's real secure store for the app's names (211
children in 22 steps; no value printed, written or sent). conftest now
hands every child the package's switch for no store, and a test pins it.

Flags for the owner, each in the report: the proof of a delete (the job
answered 200 with no words right after its delete, 404 a minute later;
the app calls that gone; a stricter rule is his); the Start screen
tests the connections at each showing (a page-first screen is proposed,
not built); a folder set up before this run cannot Start until the
self-test passes from its page; the file .env of the data folder gives
the app a key before anything is connected. words.py and schema.py are
over their targets.

Made untrue, and put right in this commit: the README (what this
version does; three speech choices; Cowork's two changes to the dated
section, byte for byte), CLAUDE.md's run lines, .env.example, and this
file's entry for 6e in four places. Not mine to write, in the spec: the
owner's words of 16 Nov that came with the review and the mails.
Cowork writes them in. No help page exists.

The room check was met on 17 Nov 2026 (above). Next: 9c.

## 2026-11-15. Step 6e, the collating step: the transcript of the review page reads as turns of speech; a leftover piece of a drug name is taken out at its row; what counts as use is said exactly

Run on 15 Nov 2026 by the mailbox, under the owner's okay of the plan
(18:47, his word: Go!) and Cowork's review of it (twelve points; all are
in). The spec is 211041a (sha256 49e411f2...), committed again with Met
for the step as 0631413; the stage prompt fa8fa2a
(stage-prompts/STAGE_06E.md). The private report is STAGE6E_REPORT.md in
the log folder, with the plan and its review beside it. Thirteen
commits, all pushed. No model was called, no engine started or stopped,
nothing left the machine. No new table and no new package.

For the patient. In the room run of 15 Nov one greeting and one question
stood as ten lines of one to six words, each a row with its own boxes. A
doctor who reads the transcript to check a note now reads a conversation:
doctor, patient, doctor, patient. Every mark that protects the patient
stays in sight inside the turn: a doubted drug name, a word with no
speaker, and above all a line that the check of who spoke moved, because
on six recordings with two people that check moved 23 lines, 18 of them
wrongly. A leftover piece of a medicine name no longer goes to the
note's model as if it had been said. And a consultation left on a screen
no longer stays on the screen.

The reading view (15.10 rulings 35 and 42 to 44; the details of 6e).
- One rule, consult/reading.py, pure: neighbouring lines shown under one
  speaker are one turn; an unsure run of three words or fewer between two
  lines of one speaker sits inside that turn; every other unsure run is
  an entry of its own. A line counts by the speaker it is shown with
  (ruling 14). Nothing is stored and no model reads a turn.
- THE RULE ON THE NINE STORED PAGES, by the app's own function: Nemotron
  s19, s15, s14, s11, s13, sT2 give 49, 32, 39, 44, 47 and 29 entries
  with 7, 9, 7, 4, 6 and 0 unsure lines folded in; Speechmatics live s19,
  s15, s14 give 43, 27 and 31. All nine equal the figures of the details.
- A turn is the browser's own disclosure element, sent closed: its
  summary holds the speaker, the first and last line number, one press
  that plays the turn (from one second before its first line to the
  latest end among its lines), and the words, a piece for each line with
  that line's marks. A press opens the turn's lines in place, with no
  script. The lines are not changed by a byte: a test pins the sha256 of
  every line's piece on three made-up pages as 9aa9aab gave them.
- Each piece is a marked part beside its line, so a kept name shows
  inside a closed turn with no load. A keep that changes the entries (an
  unsure run crossing three words) leaves the turns as they stand until
  the next load.
- With a script, what stood open is open after every press that loads
  the page: review.js notes the numbers of the open lines when the page
  is left, never a word, and opens the turns that hold them before
  place.js puts the place back. One control, Open all the lines, beside
  Swap; with no script a link (?lines=open). A turn that holds unsaved
  words is not closed by that control nor by the doctor's own press, and
  says so. With no script every turn is closed again after a load, and
  his own press does close such a turn.
- The app sends a turn open in one case more: a Save or Undo on a line
  that it refuses, so that the sentence in its slot is seen (R15).
- A line number pressed marks the line's words inside its closed turn
  and opens nothing. A line the check moved stands inside its turn in a
  box with a heavy edge, after the words changed by the check and its
  own Undo, a button tied to a form with the line's undo address.

Ruling 40. An empty box with the tick or Enter takes the doubted words
out of the line by the function a correction uses and settles the mark,
which keeps the point the words left. A second press opens it with an
empty box; words typed back go in at the point, never inside a word; the
point moves with the letters around it when the line is edited
elsewhere. Leaving an empty box sends nothing. A keep with an empty
field, which only a stale page sends, is refused as built.

Ruling 41. The recording and the question for its file are never use
(guards.logged_in_not_use). Every press on the review page is use, as
typing is, told at most once in 30 s; sound tells while it plays and
once more when it stops; each answer sets the page's count; the copy of
the note tells too. The timed move never comes while sound plays or a
field is unsaved. NOT MENDED, AS THE DETAILS SAY: with no script the
review page has no timed move (as built since 6b) and the browser's
player is not heard by the app, so the lock falls 30 minutes after the
last press that loaded a page, also while sound plays.

Tests. 985 in 94 s, none skipped; 21 are new. One test of 6d is
restated, as the plan and its review name it: its first three
assertions pinned that a tick with an empty field is refused, which
ruling 40 reverses; they now pin the ruling, the name says so, and its
second half is as written. No other test of 6c, 6d or 6d2 is touched.

Seen in a browser by the build model: this machine's Chrome 157,
headless, cut off from outside, real mouse and key events, a made-up
consultation with a sound that tells the time, and one profile that had
first loaded the page of 9aa9aab: after the update every script that ran
was the file as built, by its bytes. By the sound: a turn of six lines,
two of them 0.08 s long, played from 18.99 to 28.00 of an asked 19.0 to
28.0. Each line of Done when you see, for 6e, held. The lock, at a lock
time of 20 s: nothing pressed, the login page at 20.8 s; one turn
played, 20.3 s after the sound ended; an unsaved box held the page. At
40 s: a sound of 100 s held the page, the login page 40.3 s after it
stopped; presses every 5 s held it, and the lock fell 40 s after the
last tell. Not seen: a hand's timing, real speech, Firefox or Safari, a
screen reader. The owner's room check is the check that counts.

New words, all drafts: Open all the lines; Close all the lines; Press
to open or close the lines of this turn. (a screen reader's description
of a turn); Play this turn; Taken out of the line.; This turn holds
words that are not saved. Save them first.

Flags. The tells come at most once in 30 s, so the lock can fall up to
30 s short of 30 minutes after the last press, as for typing since 6b.
The turns' script stands in review.js, not in a file of its own as the
plan had it: a test of 6d2 pins the review page's scripts by name. In a
closed turn two things a line shows are out of sight until it is
opened: the sentence of a line with no words, and the label the check
gave a word that had no first speaker. The letter's own page has a copy
its count does not hear; outside ruling 41, left. words.py is 958
lines, over its target as before.

Made untrue, and put right in this commit: CLAUDE.md's run line, the
README's account of the transcript, and this file's entry for 6d2.
The spec is in step: where the review of the plan changed the details
of 6e (a turn's play ends at the latest end among its lines; no taking
of the whole transcript after a keep; his own press does not close a
turn with unsaved words; every press is use), Cowork wrote them in with
0631413. No help page exists. The three oldest entries here,
step 6c2, stage 6c and stage 5e2, moved to the archive.

The room check was met: the owner's room check of the evening of 15 Nov
2026, on the build of 9d8be35, is the spec's Met line for the step
(0631413). Next: 9b.
