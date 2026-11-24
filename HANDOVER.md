# HANDOVER

The record for OpenConsult v2: decisions and measurements, newest first.
It stays under 500 lines. Older entries move to HANDOVER_ARCHIVE.md.
The spec is V2_SPEC.md. The record for v1 is the HANDOVER.md on the main branch.

## 2026-11-24. Run 10a: the four prompts of teaching as files, their jobs in the door, and the bench of teaching on both models. Report only: nothing a learner can see

Run on 23 and 24 Nov 2026 by the mailbox (a usage limit stood between
the two days). Mail 1 (the owner's okay at 09:03 UTC on 23 Nov): his
own change to CLAUDE.md and the bench-commands skill are committed
first. Mail 2 (11:35 UTC): Approved. Go., the plan as written. The spec
is bac1b98 (sha256 2f9e3558...), the stage prompt 0ff23a0
(stage-prompts/STAGE_10A.md). The private report is STAGE10A_REPORT.md
in the log folder. Eleven commits to the first report, none pushed,
the last of them the move of the entry of run 9c to the archive, so
that this file stays under 500 lines; five more by mail 3 and three
by mail 4, this entry's lines among them. The suite: 1477 passed in
about 152 s, none skipped (1420 at the start, 1470 at the first
report, 1480 after mail 3). OpenConsult is a research and education
prototype; every scenario is made up.

BY MAIL 4 (24 Nov 2026, the owner's okay at 12:24 UTC): THE FEEDBACK
HAS ITS ORIGINAL PROMPT AND FORM AGAIN, by the owner's word: the work
does not stay on this point at this stage, and the build moves on. The
private report is STAGE10A_REPORT_3.md. This paragraph is how things
stand; mail 3's below is what was tried.
- The two handed files of the brainstorm are back byte for byte
  (sha256 80a77975... and 4a2aff46..., no shown_by); the prompts
  folder holds, file for file, the bytes it held before mail 3.
  Ruling 13 of spec 15.14 names these two checksums and is true again.
- What of the rule stays (openconsult/teaching/shown.py): a number
  that is not a turn of the doctor's is dropped from every list of
  turns and from the signposting; signposting is false when no turn
  is left; a marking point that did not come back is not met, and one
  that came back twice only if every entry is; nothing is ever turned
  from not met to met. Dropping a turn never changes met: the form
  cannot tell a point shown by an answer from one shown in the
  consultation. Run 10b's page shows by this rule.
- THE KNOWN FAULT, carried forward. On Gemma the feedback credits a
  red flag the learner did not ask about: hard mark five stands. The
  first bench scored again by the rule as it is now (the stored
  replies untouched; a red flag not asked about, shown as met): Gemma
  on vLLM 8 of 36 feedbacks, Gemma on Ollama 5 of 18, Claude Haiku 0
  of 36. A turn that is not the doctor's, which the rule drops before
  a learner sees it: 2 of 36, 2 of 18 and 18 of 36. A point that was
  met and is shown as not met: 0, 0 and 2 of 36. WHAT IS OFFERED IS
  THE OWNER'S TO RULE BEFORE ANYONE BUT HIM USES TEACHING.

BY MAIL 3 (24 Nov 2026, the owner's okay at 11:39 UTC): THE FEEDBACK
TIGHTENED AND BENCHED AGAIN. The private report is
STAGE10A_REPORT_2.md. It was undone in its prompt, its form and two
parts of its rule by mail 4, above; the counts of its bench stand as
measured. Below it is the first bench, as it stood.
- The feedback's prompt and form are the owner's of 11:34 UTC: only a
  turn that begins with Doctor may be listed, a point that says to
  ask is met only by a question about that very thing, and each point
  names where it is shown (shown_by: turns, examined, answers, none).
  The two files replace the pinned ones byte for byte. SPEC 15.14,
  RULING 13, NAMES THE OLD sha256 OF BOTH AND IS UNTRUE IN THAT; Cowork
  amends it after the run. The frame and the layouts are unchanged.
- The rule by code, the owner's: no learner's line, no credit
  (openconsult/teaching/shown.py). Between the model's answer and the
  page: a number that is not a turn of the doctor's is dropped; a
  point met by its turns with none left, or shown by nothing, is not
  met; a point that did not come back is not met; nothing is ever
  turned from not met to met. Run 10b's page shows by it.
- The scoring counts the feedback RAW (as the model answered) and
  SHOWN (by that rule). Hard mark five is judged on SHOWN. A part of
  the bench can be tried and benched alone (--part with --trial).
- The feedback alone, the same cases, transcripts and marks: 36 calls
  on vLLM, 18 on Ollama, 36 on Claude, none failed, no thinking.
  HARD MARK FIVE, SHOWN (a red flag the learner did not ask about,
  shown as met): Gemma on vLLM 6 of 36 (RAW 7), Gemma on Ollama 4 of
  18 (RAW 6), Claude Haiku 1 of 36 (RAW 1). Before: 8 of 36, 5 of 18
  and 0 of 36 as red flags credited. Where it still crosses, the model
  names a real line of the learner's that asks something wider, or
  says the point is shown by an answer: the rule cannot mend that.
- A turn that is not the doctor's, RAW only, which the rule drops:
  vLLM 0, Ollama 3 of 18, Claude 9 of 36 (18 of 36 before).
- The opposite harm, a point that was met and is shown as not met:
  Gemma none; Claude 7 of 36 replies (2 before), RAW and SHOWN alike;
  the rule itself made none of them.
- A feedback takes 3.4 s typical on vLLM, 6.1 on Ollama, 3.9 on
  Claude; the Claude arm cost 0.03 US dollars.

For the learner. A learner who is taught something wrong is harmed
(12.3), so both models were put through the same test before any page
stands on the prompts, with six hard marks set before any run (15.14,
ruling 14). Code can count three of them. Hard mark four (the
examination never says nothing is there where the scenario holds a
finding): crossed by no arm. The counted part of hard mark six (no
dose in the plan of a fresh case): crossed by no arm. HARD MARK FIVE
(the feedback never credits a red flag that was not asked about, and
never points to a line that does not exist) IS CROSSED ON EVERY ARM,
as the bench's README counts it:
- Gemma 4 QAT on vLLM: 10 of 36 feedback replies. A red flag credited
  though the learner never asked about it in 8; a turn number that
  does not exist in 2.
- Gemma 4 QAT on Ollama (one round): 6 of 18. A red flag credited in
  5; a turn that does not exist in 1, a patient's turn in 1.
- Claude Haiku 5.5: 18 of 36. No red flag credited. In all 18 a
  point's turns name a turn of the patient, not of the doctor; every
  such turn exists in the consultation.
So by ruling 14 no model is offered for the feedback as the prompts
stand. That is the owner's to rule on; nothing was changed to make a
mark hold. Hard marks one to three (the actor) and whether a fresh
case is clinically right are Cowork's to read from the stored files:
535 replies of the actor and 78 fresh cases.

- The words (15.14, rulings 10 to 13; 15.8, ruling 1): thirteen files
  in the prompts folder byte for byte, pinned by the sha256 of their
  bytes: a prompt, a frame and a form for teaching_case,
  teaching_patient, teaching_examination and teaching_feedback, and
  teaching.layout.json, every pattern by which a part of a scenario is
  written into a frame. No older prompt, frame or form changed.
- The loader gains layout() and fill_once(): a fill in one pass, so
  braces a learner typed are never taken for a later slot. The older
  fill is left alone.
- The four jobs (R30): 4,000 tokens and 180 s; 300 and 30 s twice;
  2,500 and 120 s. Measured beside them: the longest case 3,073
  tokens (Claude; 1,683 on Ollama), the longest patient's reply 131,
  the longest feedback 1,037; no call cut, none over its time. The
  four sentences for a failed job are drafts.
- openconsult/teaching/frames.py (R24) builds the words of each job.
  The actor is given part one of a scenario alone (ruling 10), pinned
  on a made scenario. Nothing else of teaching is built: no page,
  route, table or setting (R31), pinned for this run.
- THE SAMPLING OF A FRESH CASE DEPARTS FROM SPEC 10.4, by the details
  of run 10a; the owner was told on 23 Nov 2026. On a local model the
  case is asked at temperature 0.7 with a seed drawn afresh, kept in
  the stored request; every other job keeps 0 and 42. Claude is sent
  neither.
- The bench (openconsult-bench teaching, teaching-score; their line
  is in the bench-commands skill): Cowork's six scenarios with fixed
  learner lines and 26 fresh cases, private, never in the repo. 340
  calls on vLLM, 185 on Ollama, 340 on Claude; no failed call, no
  reply with thinking, no form refused. The proof of the words: 853
  stored requests, each holds its prompt file letter for letter, and
  the arms were sent the same words (336 calls compared).
- The learner's wait, a patient's reply, typical and slowest: vLLM
  0.2 and 0.5 s; Ollama 0.4 and 1.9 s; Claude 1.3 and 2.4 s. A fresh
  case: 6.4, 8.7 and 13.4 s typical. A feedback: 2.7, 5.1 and 3.6 s.
- Counted, not hard marks: an absent line answered with a fact in 5
  of 214 replies on vLLM and 13 of 214 on Claude; the first line
  saying the opening words again in 4 on vLLM and none on Claude; a
  point expected met that came back not met: none on Gemma, 2 on
  Claude. The two rounds: on vLLM 22 of 107 patient's replies and 17
  of 18 feedbacks differ at temperature 0 and seed 42; why is not
  measured.
- Claude's cost at 0.10 and 0.50 US dollars a million tokens (the
  spec's figures of 6 and 14 Nov 2026): the arm 0.13 dollars; one
  whole teaching case (one case, 30 replies, 3 examinations, one
  feedback) 76,165 tokens read and 5,504 written, about 1.0 US cent
  by the bench's means, 1.1 by a straight line to 30 lines.
- Six older tests restated, by mail 2: the door's refusal now pinned
  on a made name; the two lists of the app's jobs; in test_prompts.py
  the counts 22 to 30 and 30 to 43 and 46 new capital words.
- GitHub's check gains a step that shows, for its twelve slowest
  tests, the three phases, the processes started and the functions
  that held most of the call. It measures and mends nothing.
- The engines: vLLM started and stopped by the owner's script, the
  model unloaded from Ollama at the end; left as found.

Made untrue by this run. Spec 10.4 (temperature 0 and seed 42 with no
exception): Cowork amends it. The details of run 10a under Documents
(CLAUDE.md gains the bench's line): overtaken by mail 1, the line is in
the skill. CLAUDE.md's run line no longer walks through the pages: the
owner's cut of 23 Nov, kept. The README is not changed: teaching mode
is still to come.

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
