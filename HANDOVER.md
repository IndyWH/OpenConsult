# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-16. Run 9b: cloud mode. A consultation can run on Claude and Speechmatics, said before anything leaves, marked while it runs; a recording can be sent once after Stop and is deleted there

Run on 16 Nov 2026 by the mailbox, as one run in two halves (15.13,
ruling 35), under the owner's okay of the plan (00:52) and Cowork's
review of it; three questions went by mail and were answered. The spec
is a17ed6c (sha256 8c5a7e85...), the stage prompt c7419b0
(stage-prompts/STAGE_09B.md). The private report is STAGE9B_REPORT.md in
the log folder, with the plan, its review and the first act beside it.
Twenty-two commits, none pushed. The suite: 1114 passed in about
111 s, none skipped (985 at the start). No prompt file, frame or form changed: the two
prompt folders are as at 0631413. vLLM was left as found; the Ollama
service was not touched.

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

Next: the owner's room check of 9b, two sittings, the first step of
each to stop the app and start it again.

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

## 2026-11-15. Step 6d2, the mend run: the first play is heard, a name typed and left is kept, the page keeps its place, and the check of who spoke is seen

Run on 15 Nov 2026 under the owner's approval of the plan and Cowork's
review of it (ten points; all are in), then two mails from Cowork with
his okay the same day. The spec is 9aa9aab (sha256 dd486e6d...; first
6abc2bd, 81faf6ff..., then 42e42b7, 2978b9cf...), the stage prompt
bac357e (stage-prompts/STAGE_06D2.md). The private report is
STAGE6D2_REPORT.md in the log folder, with the plans and the review
beside it. Fifteen commits, 33c8c9a to 9aa9aab: the fifteenth, after
the owner's second room check, wrote Met for steps 6c, 6d and 6d2 into
the spec. No model was called, no engine started, and nothing left the
machine. (Put right in step 6e: this entry said fourteen commits and
the spec at 42e42b7.)

For the patient. In the room run of 15 Nov the row of a doubted drug
name did what it is for, and the page failed under the doctor's hands
four times. A name he typed and believed saved, but which was not,
would have left the wrong medicine in the note; and a change of 29
speakers that he did not see could not be judged by him. Now the first
press of play gives sound. A name typed in a row is in the transcript
line as soon as he leaves the box, with the tick still faded; Enter
saves and ticks. After a press the page stays where it was. And when
he presses Check who spoke the page stays at the top of the transcript
and says there what the check did, with the control that undoes it all.

The four mends (15.10 rulings 33, 34 and 37 and the details of 6d2).
- The first play. The review page is shown before the Stop thread
  converts the WAV, so the player held the head of a file that was then
  removed; the same address gave the Ogg and the browser stalled with
  no error. The page now names the file it was shown with, one
  read-only address gives the file's name as it is now, and at a press
  the script takes the recording afresh when the name has changed. The
  browser's own play control asks the same. The conversion is as it
  was. With no script the sound plays after a load, as before.
- Leaving the box. The row's form takes a third press, keep, sent by
  the page's script in the background when the focus leaves a box whose
  words changed: the function the tick uses, and no settling. Keep on a
  settled mark changes nothing; an empty box and a read-only page are
  refused at the row. The press that took the doctor out of the box is
  never lost: a play plays; the row's own tick or Enter sends one act;
  any other press that loads the page is held until every keep has
  answered. The app's answer is the page itself, and fresh.js puts its
  marked parts (data-part) in place; a part holding unsaved words or an
  unsaved choice is left whole. A keep that is refused or not answered
  is said at the row and a held press is dropped. kept.js is gone.
- The place. A press on a form marked data-stay (a row, Save and Undo
  on a line, Swap, Undo all, Save on a note entry) still loads the
  page; place.js notes the control and its height in the window for
  that one load, and puts both back, with the keyboard on the control.
  A row then asks for no anchor. With no script a row comes back at its
  anchor, now clear of the app's bar.
- The check of who spoke. The press, each wait and the end come back at
  the transcript's anchor, by the address alone; each wait's address
  differs by a count so that the browser loads it. The running and
  outcome sentences are in ordinary type with Undo all beside the
  outcome. A changed line says so at its start, with its Undo, and
  carries a solid edge. No sentence of the owner's changed.
- The lock (ruling 12; the plan review, point 3). use.js asks the page
  whether any field differs from what the app gave it, instead of
  remembering that something was typed; takes the seconds left from a
  keep's answer; and adds the one second the script-less pages have.
One test went with kept.js; one gained three assertions; none weakened.
Two tests were made to wait for the Stop thread's conversion step: one
had failed 3 times in 8 on Cowork's clean copy (cd147a3, tests only).

Three more mends, after the owner's room check on the build of dd88d5d
(rulings 38 and 39; the details, Three more mends).
- WHAT THE ROOM CHECK FOUND: the page was new and the browser ran its
  own stored copies of older scripts, because the app served its
  static files with nothing that tells a browser when a copy is too
  old. So the first play and leaving the box never ran in the room.
  Older than this run, and it would have met every doctor after every
  update. Now every script and style address carries a mark, the start
  of the sha256 of the file's bytes (pages.static_address), the
  recorder worklet too, and the static files are served no-cache.
  Proven with one browser profile kept between looks: after the page
  of 33c8c9a, the page of cd147a3 ran the old player.js, use.js and
  review.js from the browser's store; the final code ran its own.
- One second early: each press on a line or a row starts one second
  before the line, not below zero (review.PLAY_LEAD_S); the end stays.
- Measured with a made sound that tells the time, by the samples that
  leave the player: with the recording in pieces of one second (as the
  app converts) and of a tenth, the sound began at the asked place in
  all 72 presses, to 10 ms. So the pieces are not why a row sounded
  late, and the converter is unchanged. Not measured: a loudspeaker's
  own start; the speech choice's line times, which wait for a later
  step. One press of 72 ended 0.7 s early; not seen again, not explained.
- One click on a row's box selects all its words.
The suite is 964 tests in 86 s, none skipped. The start check passed at
dd88d5d and was not run after it: the owner's app was on its port.

Seen in a browser by the build model: this machine's own Chrome 157,
headless, with a throwaway profile, a dead proxy and no name lookups,
driven with real mouse and key events on a made-up consultation of the
suite with a made sound of ten minutes. The first play's fault was made
on the code as it stood (the time stood still, no error) and was gone
after the mend. Each line of Done when you see, for 6d2, held there,
the last time by the sound itself and not the player's clock.
Not seen: a hand's timing, real speech, Firefox or Safari, a screen
reader. The owner's room check is the check that counts.

One new sentence, a draft, in two forms: This name was not saved:
OpenConsult did not answer. It is still in the box. And: This name was
not saved: OpenConsult answered with an error ({status}). It is still
in the box.

Flags. FOUND AND NOT MENDED, FOR A RULING: the lock can fail to fall on
the review page. A request for the recording counts as use, and the
page's count does not hear of it. After sound is played, or the note
is copied, the page's own check can come early; the page is shown
again, its own request for the recording puts the lock off, and so on
without end. Older than this run. The mend in use.js covers a kept
name and the plain page, not this. Also: a play that still fails after
the address was taken again is silent, as built; a tick's press loads
the page, so a playing sound stops, as built; with the app not
answering, a row's own tick gives the browser's error page, as every
press does; words.py is 949 lines, over its target as before.

Made untrue, and put right in this commit: CLAUDE.md's run line and the
README's account of the row and of the check. Not mine to write, in the
spec: nothing found. No help page exists. The two oldest entries here,
run 9e and stage 5e, moved to the archive.

Next: the owner's room check of 6d2 again, in a browser that has run
an older build; a ruling on the lock; then the collating step (ruling
35), then 9b.

## 2026-11-14. Step 6d: a doubted drug name is corrected and ticked at its warning; Claude Sonnet benched on the drug names, two marks held and the third missed by 5

Run on 14 Nov 2026 under the owner's approval of the plan and Cowork's
review of it (twelve points; all are in). The spec is 1b9a678 (sha256
f8a75a3b...), the stage prompt 1f6cee0 (stage-prompts/STAGE_06D.md).
The private report is STAGE6D_REPORT.md in the log folder, with the
plan and its review beside it. Thirteen commits, none pushed.

For the patient. In the room run of 14 Nov the mark led the doctor to
a wrong drug in the note, and then the page led his hand to the wrong
place twice. Now each doubted drug name is one row among the warnings,
and the row is where he works: he plays the line, types the right name
over a wrong one, and ticks it. The tick also settles a name that was
heard rightly, and a second press opens it again. The correction goes
into the transcript line; the note is then drafted again with one
press, shown a second time under the rows, and is never corrected in
place, because the right drug can change the clinical picture. No sign
stands on the note entries any more. A pressed line plays that line
and stops. No guess is shown anywhere; the drug the model named stays
in the record.

The build (15.10 rulings 26 to 29 and the details of step 6d).
- Tables of version 10: a mark gains its words as they now stand
  (they begin as the words heard, which never change), the time it was
  settled, and the first and last line it was heard on. A version 9
  folder comes forward with every row, none settled.
- The row is a form of its own and works with no script: Line n, the
  words with the doubted words as a field, play, the tick. The field
  looks like the highlighted words until it takes the cursor.
- The tick keeps what the field holds. Where the words differ the line
  is corrected by the function its own box uses: the edit, the audit
  line, Draft the note again offered. A settled mark shows no
  highlight on its line and is not counted on Approve; its row stays.
- Words in more than one place are all corrected, and every such
  place is highlighted in the row before the press. Words over two
  lines go on the first; the piece on a later line is taken out.
- A line left with no words stays, with its number, speaker, times and
  sound, and says so beside its box. Its box may be saved empty so
  that its speaker can be set; a line that holds words is still never
  emptied there. The note's turns leave it out, and the check of who
  spoke already did: no model reads an empty line. For a page with no
  empty line the note's text is the bytes it was, pinned by its sha256.
- The row never shrinks: play and Line n are read from the lines the
  name was heard on, never from typed words.
- The tick is never told by colour alone: a thin tick in an empty ring
  with a broken edge, 3.6 to 1 on the pane, or a heavy tick on a
  filled disc with a dark whole edge; its name, its title and
  aria-pressed say the state.
- Words typed into one row and not yet ticked are kept by a small page
  script when another row is ticked, in the browser's own store, never
  sent; dropped when ticked, at Approve and when the tab closes.
- Read-only (after Approve, and while a check of who spoke runs): the
  field cannot be typed in and a press is answered at the row.
- Every press that plays a line carries its start and end; the alarm's
  press and the player's own controls play on.
The suite is 948 tests in 80 s, none skipped; the start check passes.

Seen in a browser by the build model, on a made-up consultation of
the suite served on this machine: typed words survived another row's
tick and were then posted and dropped; a pressed line stopped within
20 ms of its end; after a pause or a move with the player's own
controls the sound played on; the alarm's press played on. Two mends
came of it (the player's own bar told by the seeking event; the stop
set by a timer). Not seen: greyscale or forced colours by eye; the
states were read from the computed styles.

The bench of Claude Sonnet 5.5 on the drug-name call alone (rulings 25
and 30): the 24 stored pages as text, each asked twice, 48 calls, all
answered, none cut, none failed, 124,060 tokens read and 8,494
written, 0.33 dollars at 2 and 10 a million, 130 s, no wait for the
rate. For this model the kind switches thinking off with the service's
own field between_tools (the type disabled is refused); no reply holds
a thinking block. Counted twice, the same bytes. Judged on the first
round, beside the local model and Claude Haiku:
- D1 HOLDS: 24 of 24 (24, 24).
- D2 HOLDS: 108 of the 122 names written wrongly marked (93, 94).
- D3 MISSED BY 5: 32 marks on a word written rightly against a line
  of 27 (27, 244).
- Entries dropped by code: 2 of 141 (3 of 130, 6 of 182).
- On the pages of the default cloud speech service, live: 1 of 2 names
  marked (0, 1), 6 marks on a right word (4, 30).
- The second round, for the report: 111 names, 19 marks on a right
  word, which is under the line. Of 139 entries 127 are the same in
  both rounds; all 108 names of round one are marked again; of the 32
  right words 9 are marked again.
- Read as a doubter: no name the local model marked did Sonnet miss
  (93 both, 15 Sonnet alone, 14 neither). By entries, 8 mark only
  right words against the local model's 6 (Haiku 37). 11 of the 32
  stand on a drug name of the script written rightly, and 11 come from
  two long entries on one kind of page. Where it named a drug on a
  name written wrongly it was wrong 2 times of 108 (3 of 93; Haiku 30
  of 94). The app shows no named drug.
THE DRUG-NAME MARKS IN CLOUD MODE WAIT FOR THE OWNER'S RULING. No word
of a prompt was changed, nothing was run again, and nothing is built
for cloud mode: the Claude kind is the bench's alone.

What left the machine: the text of the 24 pages, to the Claude service
and to no other host, as the approved prompt, one message and the form
in each of 48 requests, proven from the stored requests; the same
bytes the local model and Claude Haiku were sent. The private word
check on that text before the first call: 0. No key was read by the
build model. No engine was started.

Flags. The suite cannot run a page script (no browser, no script
engine), so the kept-words script is pinned on the page's side only
and was run in a browser by hand. Two tests were restated for the new
table version and the press's new name; five for the row and the signs; none
weakened. Two stray commands of mine ran outside the record of
connections and did nothing; one run of the suite met a temporary file
of mine and was run again. words.py is 945 lines,
over the target as before. The oldest entry here, run 9d2, moved to
the archive.

Made untrue, and put right in this commit: CLAUDE.md's run and bench
lines, the README's account of a doubted drug name and its dated
section on the cloud model. Not mine to write, in the spec: the
headline of 15.10 ruling 6 (press the line and type the name); the
details of step 6d where the plan review changed them (the request the
kind sends today; the row read from the lines the mark stands on);
15.13 ruling 24, which speaks of four benches. No help page exists.

Next: the owner's ruling on the drug-name marks in cloud mode; and his
room run of 6d, with Check who spoke carried from 6c.
