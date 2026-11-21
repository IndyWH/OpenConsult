# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-21. Step 9f: the review page opens in a simple view of the note and of the transcript, an edited entry is marked, two lines for two things in the cloud

Run on 21 Nov 2026 by the mailbox, one plan gate (the owner's okay at
08:35, his words: Noted. Choice A.), under Cowork's review of the plan
with changes A to E. The spec is 6d9e048 (sha256 cce162a5...), the
stage prompt 696daae (stage-prompts/STAGE_09F.md). The private report
is STAGE9F_REPORT.md in the log folder. Eighteen commits, none pushed:
fifteen to the first report (78aabbe), one by mail 2, two by mail 3,
this entry's last line among them. The suite: 1420 passed in about
152 s, none skipped (1358 at the start). No model was called, no key
read, nothing left the machine. No prompt file, frame or form changed;
the tables stay at version 13.

THREE THINGS BY MAIL 3 (21 Nov 2026, the owner's word A at 10:41).
- The passage of a guideline in the live page's pop-up, measured in
  the browser on 385ad5e and on this head: the same in every figure
  (margins 14.4 px above and below, ink black, 14.4 px on 21.6 px, the
  window not moved by the press). Nothing changed. On the build of
  before mail 2 it had no margin above, 11.2 px below and the page's
  ink: the fault that f0aa28a closed.
- A page of 130 turns in the simple transcript, at 1280 and 420 px:
  all clear and nothing cut, but a number of three figures was 6 px
  wider, so the speaker's word began 6 px further right from passage
  100. The number has one width for one to three figures (3248873).
- This entry's count of commits.
Noticed there, older than this step and not touched: on the live page
a press on a mark of the Guidelines pane took three to five presses to
open the pop-up, on 385ad5e and on this head alike, in a made
consultation whose page is sent sound by the browser's made
microphone. Likely the pane being drawn afresh under the press; not
measured.

ONE MEND BY MAIL 2 (21 Nov 2026, the owner's word A at 10:10): a
passage of the simple transcript is laid out as v1 showed its
transcript. Its number, the speaker's word and the play stand in a
column of one width at the left; its words in a column of their own,
every wrapped line under the first word; the speaker's word in the
page's ink and heavier. Under 600 px the words stand under the head.
Seen in the browser at 1280 and 420 px for both made pages. The rules
are scoped to #passages, for the passage of a guideline on the live
page has the same class name and had taken three of them.

For the patient. After Stop the doctor reads the note as plain words
under its four headings, whole and wrapped, so that a wrong dose is
seen and not lost among boxes and 20 to 55 line numbers. Each entry
carries one small chip for each turn of speech it rests on; a press
shows that turn in the transcript, marked. An entry that rests on
nothing that was said still says so. An entry the doctor changed
stands on green with the word Edited, in both views.

- Two views of one page (15.13, rulings 46 and 71 to 75; Cowork's
  ruling on the plan's item 2). Each area carries data-view and the
  style sheet shows that view. The note is one piece for both: the
  simple view shows the words the print sheet already had, so no word
  of it is sent twice. The transcript gains a block of passages
  (#passages) before the turns, so its words are sent once more:
  measured on a made page of 240 one-word lines, 297,121 bytes before
  and 327,933 after, 101 bytes a line where a line costs 1,043. The
  advanced view is each area as it stood at 385ad5e, proven piece for
  piece, plus one hidden number in each turn.
- The choice of view is the browser's: noted in the session store when
  the page is left (two names and a time), read once at the next load
  if not older than 15 s, before place.js. With no script each press is
  a link (?note=advanced&transcript=advanced#area), and the app sends
  an area advanced where the page comes back to something that stands
  there alone (a refused Save, lines=open, the check's waits and
  outcome). With no script a Save that was taken comes back simple.
- The number of a turn and the chips: two pure rules in
  consult/reading.py (numbers_of, chips_of); nothing stored, no model
  reads them.
- An entry corrected where it stands (ruling 72), in review.js: a
  click or Enter, a field in place, saved on leaving or Enter through
  the address of today. Nothing typed is lost without a word: after a
  refusal, an error, no answer (30 s) or an ended login the field
  stays open and the entry says why. A press that loads the page waits
  for a save on its way (rows.js) and is dropped if it failed; a
  change of view never hides words not saved, either way (change A).
- The mark of an edited entry (ruling 75): text differs from
  model_text. Green #D3ECD9, ink on it 12.38 to 1; the yellow of a
  doubted name 12.67 to 1; the two are equally light, so the word
  carries the mark. Not in the copy text, the approved text or print.
- Two lines for two things in the cloud (ruling 76): where_lines gives
  each thing a line that begins In the cloud:. Eleven sentences of the
  owner's are proven letter for letter (tests/test_two_cloud_lines.py).
- Two flags of 9c: a transcript that came back with no words has the
  owner's reason (UPLOAD_NO_WORDS); the picture of This machine is
  described to a screen reader by the lines above it.
- web/review.py: its five edits moved to web/review_edits.py; 544
  lines (636 before). GitHub's check lists its 40 slowest tests and
  has a limit of 90 minutes; nothing mended on a guess.

Seen in a real browser (this machine's Chrome, cut off, a profile that
had seen 385ad5e; it ran the built scripts): each line of Done when you
see; every way a save ends; the keyboard alone; the lock held by an
unsaved field; scripts off; a passage's play by the sound that comes
out (within 0.01 s); 420 px. Five faults found there and mended in two
commits (8c965d6, e26e282): the worst, two functions of review.js with
one name, which no test can reach.

Older tests restated, old words kept: five of run 9c (four for the one
long line, one for the old reason). None for the two views.

Flags for the owner, each in the report: the drafts he meets on screen
(Edited; Saved.) and those he does not (the sentences for words not
saved, the reader's sentences); a return to the page within 15 s finds
the view chosen; the 30 s limit and two reasons were added after the
plan; words.py (1,329 lines) and schema.py are over their targets.

Made untrue, and put right: the README (the two views; one line for the
paper), CLAUDE.md's run line. The entry of run 9b moved to the archive.
Not mine to write: the spec's details of 9f still give the reason of a
transcript with no words as a draft, and it is the owner's since his
word of 08:35; and they do not yet hold changes A and B of the plan
review. No help page exists.

Next: the owner's room check of step 9f, one sitting.

## 2026-11-18. Run 9c: one picture of This machine, a tick or a choice that saves by itself, the mends from the room check of run 9b, and the two thresholds of the gate within the owner's bounds

Run on 17, 18 and 20 Nov 2026 by the mailbox, as one run in two halves
(15.13, ruling 58), under the owner's okay given in advance (17 Nov,
23:31) and Cowork's review of the plan. The spec is e9a7ac8 (sha256
78c7d692...), the stage prompt 59521c1 (stage-prompts/STAGE_09C.md).
The private report is STAGE9C_REPORT.md in the log folder, with the
plan and its review beside it. Forty-three commits, none pushed. The
suite: 1358 passed in about 147 s, none skipped (1114 at the start). No
prompt file, frame or form changed: the two prompt folders are as at
18cc922. No engine was started; the Ollama service was not touched.
Half one stood by itself at 85e3f2e, suite 1228, and needed nothing of
half two.

ONE THING BY MAIL 7 (20 Nov 2026), from the owner's look after mail 6
(11:58: the diagram stands, wide and narrow; New patient was at the top
but the page scrolled down to the search). The Patients page opens at
its top with New patient in the window: the search box is given the
keyboard by the page's first script (static/keyboard.js, the field
marked data-keyboard), which does not move the page, and no longer by
the browser's own attribute, which moved the page down to the box when
it stood under the window. Made first on 7a7abae: with twelve rows
waiting the page loaded 711 px down at 1280 by 800 and 1,245 px down at
420 by 700. As built: 0 px in every case, the button in the window,
the keyboard in the box, a typed letter in it. A search that was sent
keeps the browser's attribute and stands as before: the page comes up
at the box, above its results. With no script the page stays at its
top and the box takes the keyboard at a press.

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

Flags for the owner, each in the report: on the Patients page a typed
letter makes the browser bring the search box into the window, and a
reload made from further down comes back to that place, both the
browser's own; the key under the picture is
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

Next: the owner opens the Patients page once on the build of mail 7.
