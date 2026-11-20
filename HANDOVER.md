# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-18. Run 9c: one picture of This machine, a tick or a choice that saves by itself, the mends from the room check of run 9b, and the two thresholds of the gate within the owner's bounds

Run on 17, 18 and 20 Nov 2026 by the mailbox, as one run in two halves
(15.13, ruling 58), under the owner's okay given in advance (17 Nov,
23:31) and Cowork's review of the plan. The spec is e9a7ac8 (sha256
78c7d692...), the stage prompt 59521c1 (stage-prompts/STAGE_09C.md).
The private report is STAGE9C_REPORT.md in the log folder, with the
plan and its review beside it. Forty-one commits, none pushed. The
suite: 1357 passed in about 147 s, none skipped (1114 at the start). No
prompt file, frame or form changed: the two prompt folders are as at
18cc922. No engine was started; the Ollama service was not touched.
Half one stood by itself at 85e3f2e, suite 1228, and needed nothing of
half two.

FOUR THINGS BY MAIL 6 (20 Nov 2026; 7b1164e to 73ffdf3), from the
owner's room check of that morning on 262f018, which passed every step
(his own folder came forward to version 13).
- The arrows of the picture show the path chosen (his words at 10:06,
  his word A at 10:14; a change to the picture of ruling 56). An arrow
  was a small sign in each gap between two columns. Now every arrow is
  a line from the edge of one box to the edge of the next, with a head
  (panel.arrows_of): solid during the consultation, Microphone, the
  transcription box chosen, the language model box chosen,
  Consultation; dashed after Stop where the tick for better accuracy
  counts, Microphone to Speechmatics and Speechmatics to the language
  model chosen. A box off the path has no line. Under the picture a
  key (PANEL_KEY, Cowork's draft), its dashed part only with a dashed
  line. No script and no colour tells them apart: the template draws
  each line twice in SVG and the style sheet shows one. Side by side a
  line runs in the gutter between its columns, the solid 18 px under a
  box's top and the dashed 40 px. Under 760 px each box has a row of
  its own and the lines run down a rail beside the boxes, the solid on
  the left and the dashed pair on the right (my proposal, built as the
  mail asked). Lines and key are hidden from a screen reader.
- New patient stands at the top of the Patients page (10:31), above
  the rows waiting and the list. The link in the top bar stays.
- A transcript that came back and could not be used (10:57) has his
  two lines above the note, awaited and proven (UPLOAD_UNUSED_AWAITED,
  UPLOAD_UNUSED); his sentence that none came back stays where none
  did. No new column: the record holds what the service says it
  applied only where its reply was read (whole.came_back).
- After the tick of a long statement the line Saved. is in the window
  (Cowork's detail): place.js moves the window only when that line is
  not whole in it, clear of the app's bar as measured (190 px tall at
  420 px wide).
Seen in the browser (looks mail6-1 and mail6-2): every line measured
on the screen for the six paths at 1280 and 420 px, each from its box's
edge to its box's edge, none through a box, over a word or across
another; Saved. in the window at both widths; the unused transcript's
line changing with no load; New patient in the first window with 1001
patients at 1280 px. Restated, old words kept: one line of test_panel.

SIX SMALL THINGS BY MAIL 5 (20 Nov 2026; c67b906 to 31973db), each the
owner's word with its time, the first five to flags of mails 2 to 4.
- The line above the picture is in his shape (18 Nov, 08:03): the
  lines of where_lines, which the notice reads too. His: In the cloud:
  nothing. Cowork's details are drafts: one line a heading; two things
  in the cloud each with a capital; no line for nothing run here.
- The model line of a final transcript the service made is his (08:05).
- One line, not two, under a wider tick (08:06): LESS_HEAD ends It
  takes effect at the next consultation., and the control's ordinary
  line is not shown with it; it stands alone in every other case.
- A recording the service took that gave no transcript (08:11) has
  his two lines above the note, awaited and proven (UPLOAD_NONE_AWAITED,
  UPLOAD_NONE); none when not proven, where his warning says it.
- A consultation deleted while its recording's delete is awaited
  (08:14): Delete is never refused. The table recording_left (VERSION
  13) keeps the job's name, the delete's status and each try cut to
  what, status, gone, why and try; never a body. The thread asking
  goes on; else one starts at the press; the next start finishes it
  (whole.prove_left). Then the name is dropped and one line of the log
  says so, naming no patient. With the words gone, a 200 proves
  nothing at a later start; a 404 or a 410 proves as ever.
- Cowork's draft: the review page says the gate's two values among
  the details it ran with (GATE_RAN_WITH).
Seen in the browser in one look: the six paths at 1280 and 420 px, the
one line, the no-transcript line changing with the window not moved,
a consultation deleted in the wait and the app started again. Restated,
old words kept: test_panel, test_where_it_runs, test_less_no_tick.

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

THE NOTICE OF A PATH THAT SENDS LESS, IN THE OWNER'S SHAPE (c6e0eca;
his words of 18 Nov, 07:07 to 07:25, by mail 4; ruling 48). My draft
line he did not follow. From the doctor's side the notice now names
the two jobs as the picture does: his head (Saved. No new tick is
asked, because less leaves this computer than you agreed to.; longer
since mail 5, above), a line
that begins On this computer:, a line that begins In the cloud: with
what goes there. His lines are in the file of words letter for
letter (LESS_HEAD, JOBS_HERE, JOB_IN_CLOUD, GOES); one is Cowork's
draft, not yet seen by him: transcription. Nothing goes to
Speechmatics. The cloud boxes of the picture say the same sentences
in place of my drafts (On the path you chose ...): one function,
settings/statement.py goes_sentence, gives them to both. The full
statement stays one press away under the notice, closed, with no
script and no tick. On a later view the two lines stand without the
head. Seen in the browser for his own case and for the other two
paths of the table. Three tests that pinned the old words restated
(test_less_no_tick, test_path_settings, test_panel).

STOP DOES NOT WAIT FOR THE DELETE OF A RECORDING OR FOR ITS PROOF
(85ecea5; the owner's ruling of 18 Nov, 06:55, by mail 3: a doctor
wants the note as soon as Stop is pressed).
- The limit: the delete and each ask after it wait 30 s at most, not
  300; the second try of ruling 49 as it was (5 s later, 10 s).
- As soon as the transcript from the whole recording is stored, Stop
  goes on. The delete, the two asks and their second tries run beside
  it on a thread of their own (consult/whole.py: prove, _prove) and
  write each answer to the record as it comes. The sending is logged
  at its end, the delete in its own line when it is judged
  (recording.deleted, or recording.delete_not_proven as before).
- Above the note, one of three lines by the record's state
  (whole.proof_state: awaited, proven, not_proven): the owner's new
  sentence while the answer is awaited; his line of ruling 53; its
  first sentence alone with his warning of ruling 41. While awaited
  the page asks /consultations/N/sent (static/sent.js) and, when the
  answer has come, takes the changed parts from the app's own page
  (/sent/page) by fresh.js: no load, the window held. Neither ask is
  use. With no script, one line with a link. Approve is not held.
- At the next start (WholeRecording.finish_open, from build_app) every
  recording the service took whose delete is neither proven nor
  judged is finished beside the start: the delete first where none
  was answered; an answered ask never again; one silent try gets its
  second and no more. One already judged is not asked about again.
- The record: recording_upload.judged_at, in version 12.
- The bench's upload waits for its proof as before (run_upload,
  prove=True) and reads the same delete, asks and limits.
- Seen in the browser against a made service: the asks answered 20 s
  late, the review page stood 7.4 s after Stop with the note and the
  awaited line, and the line changed at 47 s with no load and the
  window not moved (0 px); the asks never answered: at 92 s the first
  sentence alone and the warning with no load, the count on Approve
  from 2 to 3, the text in the window held where it stood; scripts
  off: the line with its link.
- Older tests restated: the line of the log in two tests of
  test_recording_after_stop (one line said the sending and the delete
  together); the limit of a first ask in two tests of test_second_ask
  (30 s, where none was given); and a wait for the delete in the
  tests that read its record.

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
  in the record. The first asks kept the upload's 300 s until mail 3
  (below: 30 s).
- The mark's line (52): on the review page After Stop the recording
  went to Speechmatics. wherever the request that carried it was made
  and the record cannot show that nothing left; left out only where
  no connection was opened at all, or the request was never made. The
  record gained that fact: THE TABLES ARE VERSION 12, four columns:
  recording_upload.request and judged_at, and the two thresholds on a
  consultation (Cowork's word: they all join 12). A folder of version
  11 comes forward.
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

Version 13 stands (Cowork's word by mail 6): mail 5 said the new table
joins version 12, but the app was started from this tree on 19 Nov
(bytecode of 19:16 in the repo). At a later start a kept job is proven
only by a 404 or a 410: stands as built, Cowork's word.

Flags for the owner, each in the report: on the Patients page the
search box takes the keyboard at load, and where it stands under the
first window the browser moves the page to it, so New patient is then
above the window (seen at 420 by 700 px; at 1280 by 800 with three
rows waiting it is in the first window); the key under the picture is
hidden from a screen reader with the lines (my reading); a refused
value leaves the field showing the saved one; the details
say a speech choice's models are in the data folder, and they are in
the hub's own cache, so Local models counts the environment and says
so; the self-test of Speechmatics as a speech choice is no longer on
This machine; version 12 came in half one; the app now reads the
secure store for both keys at every start, where before it read only
the keys of the chosen path. words.py and schema.py are over their
targets.

Made untrue, and put right: the README (the picture, its two lines,
its arrows and key, the speech model, Local models, the Start screen,
New patient at the top, the two thresholds, a consultation deleted
while a delete is awaited), CLAUDE.md's run line. Not mine to write:
the spec's details of run 9c say that half one changes no table, and
the spec does not yet hold the owner's words of 20 Nov, the lines of
the picture among them. No help page exists.

Next: the owner's look after mail 6, a few steps with no consultation
(THE LOOK AFTER MAIL 6 in the report).

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
