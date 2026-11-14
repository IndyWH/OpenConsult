# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

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

## 2026-11-10. Stage 5e: the speech bench on three new recordings, both passes of the two cloud services

Built and run in one session on 10 Nov 2026 under the owner's approval of
the plan. THE FIGURES COUNT: three recordings of 21 Oct 2026, real voices
(545, 355 and 387 s). Nothing of 5e is built into the app but the opening
commit (R31). The tables are stage5e-tables3 in the private log folder;
the private report is STAGE5E_REPORT.md beside them.

The spec, committed once, not a character changed: 233ec9b (sha256
66469965...). The stage prompt is e56af10 (stage-prompts/STAGE_05E.md).

The opening commit (9e8cfc1): the live page asks the browser for sound at
48,000 samples a second and says so when it is not given; no fallback.

The bench (4147c6f to d4efa9e): a key folder apart from the workers' data
folder; each service's upload arm with the delete and its proof; the wait
to first shown defined again; the line for Alba; the doctor's voice cut
from a recording's own page and never used on that recording; the label
check as the app sends it beside the bench's own; the tables of 5e.

The run. 18 live results and 6 uploads, none failed; every upload deleted
and proven gone, and asked for again afterwards with the two gate clips
(Speechmatics 5 jobs, AssemblyAI 4): nothing held. The driver's first pass
gave speech-calls no --data-folder, so its seven steps ended at once with
no call made; a second pass made the 126 calls on vLLM. The engine was
found down and left down. Scored twice, the same byte for byte.

For the patient, over the three recordings: no kind of page had a passage
missing with no sign or a word where nobody spoke. AssemblyAI live wrote
one drug as another real drug three times, and both notes held it; no
other kind did. Drug names caught of 61 spoken: WhisperX 50, Nemotron 18,
the tied pair 8, Speechmatics live 58 and whole 60, AssemblyAI live 56
and whole 61. Words under the wrong speaker by the choice itself:
WhisperX 47, Nemotron 2, the tied pair 3, Speechmatics live 5 and whole
11, AssemblyAI live 257 and whole 0. The label check left more words under the wrong speaker than the choice
alone on every kind but AssemblyAI live, and as the app sends it today it failed on all three Speechmatics live pages (613 to 785
lines; the reply would need 8,000 to 10,000 tokens of a limit of 3,000).
The line for Alba: no live arm serves; almost every patient speech was
final only after the doctor's reply began.

Read by hand, the line for Alba was wrong three ways and was fixed
(32c32dd, d4efa9e): a pause inside a short reply taken for the patient's;
words matching no speech between the line and the reply; a sound going on
after the line was final. Both script notes of script 14 lack facts 14-03
and 14-16: the notes lack them, the rule is not wrong.

Flags. The suite is 881 tests in 73 s, over the target of one minute.
Speechmatics' reply does not itself prove the medical domain was applied;
the job's own record holds it. AssemblyAI names a host for the uploaded
file that is not EU by name. Nemotron's largest gap inside a word was
1.92 s, close to the 2.0 s figure. speech-calls without --data-folder
refuses its own results folder. The private check found one run of six
common dosing words of a script in V2_SPEC.md and in a test of 8 Nov,
neither written by this run.

Made untrue: CLAUDE.md's speech commands and the README's line of the
live page, both corrected in this commit. No help page names the sample
rate; none is made untrue.

## 2026-11-08. Run 9e: the letter check reads prescription frequencies as figures; the README says how the cloud model was chosen

Built in one session on 8 Nov 2026 under the owner's approval of the
plan. Run 9e is 15.13 rulings 21 and 24; no call to any service, no
bench run, nothing offered on any page (R31). The plan and the recount
are STAGE9E_PLAN.md and stage9e-recount.out in the private log folder.

The spec, committed once, not a character changed: 36354c4 (sha256
4e45032a...). The run prompt is 492be72 (stage-prompts/STAGE_09E.md).

The frequency rule (c42875f). letter_check.numbers_in, the one reader of
a text's figures for a sentence and for its cited lines, reads the
frequencies of a prescription as figures both ways: od, om, mane, nocte
and once as 1; bd and twice as 2; tds as 3; qds as 4; whole words only
(abdomen holds no bd). One choice the spec did not spell out, put in the
plan and approved: on (omni nocte) is also the English preposition, and
read everywhere it marked 38 true sentences in the 65 stored letters of
run 9d2 (1 of A, 6 of B, 6 of C, 25 of D) and took M3 of D from 13 to 0
of 13; so on is a frequency only after a dose, a figure then a unit (mg,
g, mcg, ml, units, iu, tablet, puff, drop), the unit within three tokens
(20 mg up to on). A frequency the lines do not give is still a figure
outside them, marked as ruling 20 says. 3 tests; the suite 828.

The recount, run 9d2's 65 stored letters through the check at c42875f,
no call made: M3 of A 13 and 11 of 13 (run 9d2 13 and 0 of 13); letters
marked on A 2 (run 9d2 13), the two the sentence that gives the
unchanged doses (metformin 1 g, amlodipine 5 mg, atorvastatin 20 mg,
omeprazole 20 mg) cited to the Plan line that names those medicines
without their doses, which the check is right to point at; B, C and D
unchanged (C's one marked letter stands, D's M3 13 of 13). Every other
figure of the table as run 9d2 left it.

The README (this commit): Cowork's section on how the cloud model was
chosen (ruling 21), 84 lines, inserted byte for byte after the list and
before the prototype line, proven by code (the bytes found once, the
file without them equal to the committed one); the private word check
printed nothing. HANDOVER's run 8d entry moved to the archive to stay
under 500 lines.

Made untrue: the 9d2 entry's last line (the README section came with
this run); the figure 13 of 13 marked on A in STAGE9D2_REPORT.md,
STAGE9D2_LETTERS.md and ruling 24 stands as run 9d2's record, with the
recount beside it. Carried, unchanged: for 9b the line Why this model on
the connect screen (ruling 21); for 9c the control's disabled reason
(ruling 23); for 5e the live-or-not of each cloud transcription service.
Open for the owner: the rule on model-specific prompt lines (ruling 22)
waits for a real complaint; Alba in cloud mode is ruled (ruling 23).

