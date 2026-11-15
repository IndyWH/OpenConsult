# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-15. Step 6d2, the mend run: the first play is heard, a name typed and left is kept, the page keeps its place, and the check of who spoke is seen

Run on 15 Nov 2026 under the owner's approval of the plan and Cowork's
review of it (ten points; all are in), then two mails from Cowork with
his okay the same day. The spec is 42e42b7 (sha256 2978b9cf...; first
6abc2bd, 81faf6ff...), the stage prompt bac357e
(stage-prompts/STAGE_06D2.md). The private report is STAGE6D2_REPORT.md
in the log folder, with the plans and the review beside it. Fourteen
commits, none pushed. No model was called, no engine started, and
nothing left the machine.

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

## 2026-11-14. Step 6c2: the reply's rule changed, the count again held, the build at Stop made; Claude Haiku passed who spoke and missed one mark on drug names

Run on 14 Nov 2026 under the owner's approval of the short plan and
Cowork's review of it; the plan of 6c and its review stood for the
build and for the bench. The spec is ec05f70 (sha256 6ace90ba...), the
stage prompt 712f612 (stage-prompts/STAGE_06C2.md). The private report
is STAGE6C2_REPORT.md in the log folder, with STAGE6C2_COUNT.md, the
two plans and their reviews beside it. Thirteen commits, none pushed.

For the patient. At Stop the language model now reads the final
transcript once and marks the drug names it doubts. The doctor sees
each mark in three places: the doubted words on their line, a warning,
and a sign on every note entry that draws on that line, also when the
note wrote the name differently. One line says that a name with no
mark is not proven right. No guess is shown on any page the doctor
works on; the drug the model named stays in the record. The check of
who spoke no longer runs by itself at Stop, where it made well
labelled pages worse: the doctor asks for it with one control on the
review page, sees every change marked, and can undo one or all.

The rule of the reply (15.10 ruling 24), one function for the app and
the bench. A line named twice with two labels is unsure and the reply
is kept; named twice with one label it takes it; a number that is not
on the page is dropped; a line not named still refuses the reply. The
two counts are kept with each run and each bench result.

The count again, from the stored replies alone, no call: 72 replies
judged afresh, the stored labels never read, twice the same bytes.
- P1 HOLDS: 48 parts of 48 taken, on 24 pages of 24 judged.
- P2 HOLDS: words under the wrong speaker 643 in parts against 682
  whole; allowance 99 (19,976 words); the line 781.
- The words made unsure by the rule, apart: 19 whole (1 line), 150 in
  parts (6 lines), all on one kind of page. Counted as wrong in both
  readings P2 still holds, by 7 words (793 against 800); with only the
  parts' counted and the line left at 781 it would not.
- Five replies are judged differently by the two rules, the one and
  the four that ruling 24 names; on the 67 replies the old rule took
  the new rule gives the same label on every line. Only the kind of
  page with the longest lines moves: whole 299 wrong and 19 unsure,
  parts 249 and 176. Lines named twice 1 and 6; numbers dropped 0, 1.
- Page by page the parts leave fewer words wrong on 8, more on 7, the
  same on 9: P2 holds, the parts are not better.

The build. Tables of version 9 (the runs of the check, each changed
line with its label before and after, the drug-name call, the marks;
the edits gain the kind check); a version 8 folder comes forward with
every row, a check that answered at Stop counting as already run. Stop
in order: the lines, which speaker was you, the checks for missing
speech, the gate, the drug-name call, the note. The drug-name prompt
and form moved byte for byte to the app's prompts folder (89fcdc35...,
4574f7e5...); the frame is the label check's bytes (44f10e08...). The
job has 3,000 tokens and 90 s. The check on the review page reads the
joined lines, a page over 160 in parts, all or nothing; it writes its
labels at the end and all at once; a run cut short by a restart is
ended as failed. The mend the plan review asked for is in: the note
stage reads the gate's refusal from the stored warnings. The page of
the calls names both calls and leaves the named drug out. The suite is
928 tests in 78 s, none skipped; the start check passes.

The bench of Claude Haiku 5.5 on both jobs (ruling 22), the 24 stored
pages as text: 96 calls, all answered, none cut, 204,040 tokens read
and 78,729 written, 0.06 dollars, 320 s, no wait for the rate. Counted
twice, the same bytes, every reply judged by the new rule.
- Who spoke. H1 HOLDS: every page taken, whole and in parts. H2 HOLDS:
  576 words wrong against the local model's 682 whole, 551 against 643
  in parts.
- Drug names. D1 HOLDS: 24 of 24. D2 HOLDS: 94 of the 122 names
  written wrongly marked, the local model 93. D3 MISSED: 244 marks on
  a word written rightly against the local model's 27.
- Invents nothing: no label entry holds more than a number and a
  label; 6 drug entries dropped by code against 3.
- Read as a doubter: D3 counts page words, and Haiku copies longer
  stretches (64 entries of three words or more against 21), so 244 is
  not 244 false alarms. But by entries it is still worse: 37 entries
  with every marked word written rightly against 6, and 38 marks on a
  drug name written rightly against 6. Of its 244, 76 stand on a
  number, a unit or a word of dose and time. Where it named a drug on
  a name written wrongly it was wrong 30 times of 94; the local model
  3 of 93. The app shows no named drug.
THE TWO JOBS ARE NOT OFFERED IN CLOUD MODE UNTIL THE OWNER HAS RULED.
No word of a prompt was changed and nothing was run again. Nothing is
built for cloud mode: the Claude kind is the bench's alone.

What left the machine: the text of the 24 pages, to the Claude service
and to no other host, as the approved prompt, one message and the
form in each of 96 requests, proven from the stored requests. The
private word check on that text before the first call: 0. No key was
read by the build model. No engine was started; the card was not used.

Flags. Stop without the check and the check on the review page are one
commit, not two: every test of a changed label needed the check to run
somewhere. The page of the calls learnt the drug-name call in the
commit that added the call, so that the named drug was never shown
between commits. Each kept entry is a mark, so a reply that lists one
place twice shows two rows. After every change of a check is undone
the page gives no count and says only that the check has run. Drafts
added and not in the plan: the reason of a refused part (part 2 of 3:
missing 4) and three lines of the bench. The record of connections
began at check 4; five small Python commands of mine ran outside it
(named in the report). One file of the log folder that is not this
run's changed while it waited for approval, in the second the review
was written. words.py is 934 lines, over the target of 600 as before;
the bench's command file is back under it. The two oldest entries
here, runs 9d and 9a2, moved to the archive.

Made untrue, and put right in this commit: CLAUDE.md's run and bench
lines, the README's account of Stop. Not mine to write: the README's
dated section on how the cloud model was chosen speaks of four
benches, and Claude Haiku has now run two more and missed a mark on
one; the spec's 15.13 ruling 24 likewise. No help page exists yet.

Next: the owner's ruling on Claude Haiku and the drug names; and his
room run of 6c: a medicine name the speech choice writes wrongly, the
page saying Checking the drug names, the mark in its three places, the
name typed and the mark gone; then Check who spoke, the count, Undo
all, and the line above the note with Draft the note again.

## 2026-11-13. Stage 6c: the parts missed their first mark, so the build at Stop was not made

Run on 13 Nov 2026 under the owner's approval of the plan and Cowork's
review of it. The spec is bb74d01 (sha256 cf560f65...), the stage prompt
0fc4c52 (stage-prompts/STAGE_06C.md). The private report is
STAGE6C_REPORT.md in the log folder, with STAGE6C_PARTS.md, the plan and
its review beside it. The step has three acts: the bench of parts
against whole, the build, the bench of Claude Haiku. The first act
missed P1, so by the details of the step the run stopped there.

For the patient. Nothing changes on any page. At Stop the app still
asks which speaker was you and still runs the check of who spoke by
itself, as before this run. No drug name is marked. Rulings 37 and 39
of 15.9 and 18 to 23 of 15.10 are not built.

The bench of parts against whole. The local model on vLLM 0.31.0,
digest 2096d38d..., proven the same engine and model as the stored whole
reading of 5e. The 24 stored pages of 5e, each cut in two with the
app's own function, the part size half the page rounded up, 10 lines
carried: 48 calls, all answered, none cut (the longest reply 1,168
tokens of 3,000; a call 3.7 s typical, 6.2 s the slowest). Counted
twice from the stored results, the same byte for byte.
- P1, every part answers and no reply is refused on each page whose
  whole reply was taken: MISSED. 4 part replies were refused by the
  app's own check, on 3 pages; 2 of those pages are among the 23
  judged. Each refused reply named every line it was sent; three gave a
  line number twice, one gave a number one past the last line.
- P2, words under the wrong speaker in parts no more than whole plus one
  word in 200: held as counted, 394 against 598, the line 693. That sum
  is kind to the parts, because a page not taken counts no word as
  wrong. On the 21 pages both readings were taken on: 394 in parts
  against 383 whole, the line 470.
By kind of page, words under the wrong speaker whole and in parts:
AssemblyAI live 215 and none taken (0 of 3 pages; whole 2 of 3);
AssemblyAI whole recording 20 and 2; Nemotron 48 and 50; the tied pair
37 and 35; Speechmatics live 61 and 84; Speechmatics whole recording 63
and 79; the WhisperX choice 77 and 72. The local figures of the plan,
read from the stored results and checked by Cowork: 598 words under the
wrong speaker on the 23 pages judged; drug names 93 marked of 122
written wrongly, 27 marks on a word written rightly, 3 entries dropped.

What it cannot say. Halves of a page of six to nine minutes are a
harder test than the app's parts of 120 lines: no page of 5e has more
than 160 joined lines, so the app would have cut none of them. All four
refusals are on one kind of page, the kind with the longest lines, whose
whole reading was refused on one page of three in 5e for the same
reason. Whether a part of 120 lines on a truly long page is refused as
often, no page of the bank can show.

What stands in the repo. Two commits of code, 951147b and cbe2cf3:
consult/joined.py holds the rule for the lines a model reads, moved
from the bench unchanged, and the cut and the merge of a page in parts;
the bench gains the job label_check_parts and the command
speech-stop-marks. No page of the app, no table and no prompt file
changed: the drug-name files did not move. Not built: all of Part 3,
the mend of the gate's refusal after a restart that the plan review
asked for, and the bench of Claude Haiku. Nothing was sent to any
service, no key was read by the build model, and the run cost nothing.
The two jobs are not offered in cloud mode: they are not built.

Flags. The cut and the merge in consult/joined.py are reached by the
bench alone until the owner rules (R31): said here, not removed. The
first try of the bench command was refused before any call, because
speech-calls needs a data folder apart from its results folder. The
record of connections began with the plan; three runs of the suite and
one private script ran before it. Every name in the record is this
machine. In the log folder one file not of this run changed while the
run waited for approval, at the second Cowork's review was written; the
engine script's own log changed by one start and one stop. The engine
was found down and left down. After a restart at the note stage the
Stop thread does not remember the gate's refusal; not mended. The suite
is 890 tests in 74 s, over the target of one minute.

Made untrue: CLAUDE.md's bench lines, put right in this commit. The
details of step 6c in the spec read as if the parts pass; that is
Cowork's to write on the owner's ruling. The README and the home page
stay true: the check of who spoke still runs at Stop.

## 2026-11-13. Stage 5e2: a second look at AssemblyAI on its updated medical mode

Run on 13 Nov 2026 under the owner's approval of the plan and Cowork's
review of it (15.9, ruling 35). THE FIGURES COUNT: the three recordings of
21 Oct 2026, the settings of 10 Nov, not one changed. No code of the app
or the bench changed, and no test. The spec is e4c5c14 (sha256
ac50fcbc...), the stage prompt 3520e14 (stage-prompts/STAGE_05E2.md). The
private report is STAGE5E2_REPORT.md in the log folder, its tables
stage5e2-tables and stage5e2-tables-b beside it.

The run. AssemblyAI alone: 6 live results in two rounds and 3 uploads,
none failed; 57 calls on vLLM, none failed; scored twice, the same byte
for byte. Every upload deleted and proven gone, and asked for again with
the gate's clip (4 transcripts): nothing held. That the uploaded sound
file itself is gone, no answer of the service proves. The engine was
found down and left down. Nothing went to another host; no key was read
by the build model. About 0.66 dollars by the page's price.

For the patient, beside 10 Nov. A drug written as another real drug:
live 3 on 10 Nov, 3 in round one today and 4 in round two, both notes
holding it each time; the whole recording 0 on both days. Drug names
caught of 61: live 56, then 57 and 57; whole 61 and 61. Words under the
wrong speaker by the choice: live 257 on all three pages, whole 0.
Patient speeches that run on into the doctor's words: 29 of 49 on every
live page. No passage missing with no sign and no word where nobody
spoke, on any page.

What it cannot say. Every reply names the same model, mode, domain and
API version as on 10 Nov, and the service's pages give the update a day
and no hour, so a reply cannot tell the old mode from the updated one.
The two live pages of today differ from each other in 5 places of about
2,480 words, and from 10 Nov in 4: as much as each other.

Flags. The service's page now advises two longer silence settings for
medical sound; the bench sends neither, and they were not tried. On 10
Nov's live page one more drug's name stands that the scoring did not
count as a drug written as another; not changed. The build model removed
a byte-code cache folder in the log folder that may not have been its
own. The suite is 881 tests in 74 s, over the target of one minute.

Made untrue: nothing in the repo. The spec's line that the default cloud
speech service waits for this run is Cowork's to write on the owner's
ruling.
