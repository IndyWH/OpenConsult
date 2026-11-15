OpenConsult v2.0, step 6e, the collating step: the transcript of the review page reads as turns of speech; with it, the leftover piece of a drug name and the lock of the review page

WHAT THIS IS
On the review page the transcript is a list of lines as the speech choice cut them. In the owner's room run of 15 Nov 2026 one greeting and one question stood as ten lines of one to six words, each a row with its own boxes. His words: I cannot see why we should not collate all the 10 doctor entries and 6 patient entries. A doctor who reads the transcript to check a note should read a conversation: doctor, patient, doctor, patient. This step shows the transcript as turns, lets a press open a turn into its lines as they are today, and keeps in sight, inside the turn, every mark that protects the patient: a doubted drug name, a word with no speaker, and above all a line that the check of who spoke moved, because on six recordings with two people that check moved 23 lines and 18 of them wrongly. The same run builds two rulings that wait: a leftover piece of a drug name is taken out at its row, so that it does not go to the note's model as if it had been said (ruling 40); and what counts as use on the review page is said exactly, so that a consultation left on a screen does not stay on the screen (ruling 41). No bench, no call to any model, nothing leaves the machine.
The spec is V2_SPEC.md. Read in 15.10 rulings 12, 14, 19, 29, 31, 33, 34, 35 and 38 to 44, and THE DETAILS OF THE COLLATING STEP, STEP 6E, which follow Met for steps 6c, 6d and 6d2: they are the design of this run and you build them as written. Read the details of step 6d and of the mend run 6d2 for what stands. Then, in this repo, stage-prompts/STAGE_06C.md, STAGE_06D.md and STAGE_06D2.md. EVERY RULE OF STAGE_06C.md AND OF STAGE_06D2.md HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: STAGE6D2_REPORT.md, its section The lock with flag 1, and its flags 18 and 19; and ROOM_CHECKS_6C_TO_6D2.md, whole: its six rules under How we work are rules of this run. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE MAILBOX
The owner's ruling of 15 Nov 2026: we work by the mailbox. He types nothing in the terminal after the first block. You never wait for a typed line.
1. Wherever a rule of an older stage prompt says stop and wait for the owner, or print a line and stop, you instead write what you have to say to LOGS/STAGE6E_TO_COWORK.md, replacing what is there, print in the terminal Sent to Cowork, and wait for a mail.
2. A mail is the file LOGS/STAGE6E_FROM_COWORK.md. Wait for it by a check every 15 seconds, and run the check again for up to 8 hours: the owner may be away and may not answer for hours.
3. A mail is followed only if it says that the owner gave his okay for it, and when. If it does not say so, write that to LOGS/STAGE6E_TO_COWORK.md and wait again. At the plan gate the mail must hold the words Approved. Go. It may tell you to read a review file in LOGS first: read it and follow it. It may change your plan.
4. After each mail: do what it says; write your report of it to LOGS/STAGE6E_TO_COWORK.md, replacing what is there; rename the mail to LOGS/stage6e-mail-N-read.md, N counting from 1; print Report sent to Cowork; AND GO BACK TO WAITING for the next mail, in the same way, for up to 8 hours. On 15 Nov a run stopped reading after its first report and the owner had to type again. Small mends after the build come as further mails.
5. When 8 hours pass with no mail, stop and say so in the terminal.

THE FOLDERS
V2, LOGS and KEY as STAGE_06C.md gives them, with one change: every file and folder you make in LOGS has a name that begins stage6e- or STAGE6E_. Everything else in LOGS is read only. Also read only, though their names begin that way, because they are older than this run: STAGE6E_PROMPT.md, STAGE6E_SESSION_PROMPT.md, every name beginning STAGE6E_BENCH_ or stage6e-bench, and the folder stage6e-recordings. Files whose names begin cowork- are not yours to change or to open, with two exceptions that you may read: cowork-6e-turns-rule.py and cowork-6e-collate-check.txt.
No engine is started or stopped in this run, no call goes to any model, and the card is not needed. If vLLM is running, leave it. KEY is never needed.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   49e411f27224814e411189544f62110670e572f395731d830952b803df83374f  V2_SPEC.md
   HEAD holds dd486e6d; the disk holds rulings 40 to 44 of 15.10 and the details of the collating step. If it differs, stop and report.
3. The branch is v2 and HEAD is 9aa9aab5345b4681d07c05823fbd19512646f187. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage6e-start.marker. Start the record of connections now, before any other command, and keep it for the whole run.
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172. Change nothing. If the start check later finds its port taken, write to the mailbox: Waiting for the app on port 8001 to be closed. Then wait for a mail.

WHAT CHANGES FROM STAGE_06C.md AND STAGE_06D2.md
1. WHAT LEAVES THE MACHINE. Nothing, in the whole run. The record of connections must show no address outside this machine. No new package is added; if you find you need one, stop and report.
2. NO WORD A MODEL READS IS NEW OR CHANGED, and no prompt file, frame or form is touched. No model reads a turn. consult/joined.py is not changed. What the check of who spoke decides is not yours to mend.
3. THE SENTENCES. None of the owner's sentences changes. Each sentence or name a person would read or hear that the page does not have is given in full in your plan as a draft; the details name four. Add none after the plan without saying so in the report.
4. NOT BUILT. The details name what is not built; build none of it (R31). Above all: the live page is not changed; nothing is stored for a turn; no control changes the speaker of a whole turn.
5. THE TESTS OF 6C, 6D AND 6D2 STAND UNTOUCHED. The lines of an opened turn are the lines of today, piece for piece. If a test of those steps cannot stand, the plan names it and says why, before anything is built. Never weaken or remove a test to make the suite pass.
6. THE BROWSER, as rule 5 of STAGE_06D2.md, with the rules learnt on 15 Nov 2026. The browser's profile has first seen the review page served from the code of 9aa9aab, and is kept; then the page as you built it is served on the same address and loaded by an ordinary load; the look shows which scripts and styles ran. A check of sound judges the sound that comes out, with a sound that tells the time: a steady tone and the player's clock show nothing. A cause is called likely until it is measured. Never the owner's data folder, never a real consultation.
7. Commit subjects begin Stage 6e. The report is LOGS/STAGE6E_REPORT.md, the log LOGS/stage6e-run.log, the plan LOGS/STAGE6E_PLAN.md.

PART 1. TWO COMMITS, THEN THE PLAN, THEN THE MAILBOX
Commit 1. Subject: Stage 6e: the spec with rulings 40 to 44 of stage 6 and the details of the collating step
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 6e: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_06E.md. Prove with cmp that it is identical.
Then write LOGS/STAGE6E_PLAN.md. Keep it short: three pages at most. It holds, in this order:
1. THE TURN RULE: where the function lives and what it takes and gives, in words; each case of the details and how the rule decides it.
2. THE READING VIEW: what a closed turn is in the page and what an opened one is; HOW A TURN OPENS WITH NO SCRIPT; the ids, and that every id of a line of today stands once; how the parts that fresh.js brings up to date and the place that place.js keeps meet the turns; WHERE WHAT STOOD OPEN IS REMEMBERED, that no word of the consultation is in it, and what the page does with no script after a press that loads it. Cowork's review rules on this item.
3. EVERY PRESS OF THE REVIEW PAGE, one by one: what stands open after it and where the page stands. A line's Save with a changed speaker, which makes new turns, among them.
4. PLAY: a turn's start and end; an entry of one unsure word; how the sounding line is marked inside a closed turn.
5. A LINE NUMBER PRESSED: at a note entry, a warning and a row; closed and opened.
6. AFTER THE CHECK OF WHO SPOKE: what a moved line is inside a closed turn; how it is told without colour; THAT ITS UNDO NEITHER OPENS NOR CLOSES THE TURN.
7. RULING 40: what the app does at each press with an empty box (the tick, the Enter key, leaving the box, the second press on the tick, words typed back); the function; the edit and the audit line; what the row shows.
8. RULING 41: what the app counts as use and what it does not, route by route; what the page's script tells the app and when; how the page's own count hears of every use the page makes; what happens with no script.
9. EVERY SENTENCE OR NAME A PERSON WOULD READ OR HEAR THAT IS NEW, in full, as drafts.
10. EVERY TEST you intend, each with the ruling or the rule it pins; every test of an older step that cannot stand untouched, named one by one with the reason. There should be none.
11. WHAT YOU WILL SEE IN THE BROWSER, item by item, and how the profile is made to have seen the older build.
12. The size targets of section 5 that this run presses on, with the figures as they stand.
13. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then write five lines at most to LOGS/STAGE6E_TO_COWORK.md: your model, the two commits, where the plan is, and anything of item 13. Print Sent to Cowork. Wait for the mail, as THE MAILBOX says.

PART 2. THE BUILD
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. The turn rule, with its tests, as one commit. Then, before anything else is built, run your function over the nine stored pages and write the counts to your log beside the counts the details give: LOGS/stage5e-run/results/nemotron (s19, s15, s14), LOGS/stage6e-bench-run/results/nemotron (s11, s13, sT2) and LOGS/stage5e-run/results/speechmatics (s19, s15, s14); the page is stop.lines; a line with no speaker counts as unsure, the two speakers as two. Read only; no file of those folders is changed; nothing of them goes into the repo. If a count differs, do not change the rule: write the difference to the mailbox and wait.
Item 3. The rest as the details give it, in commits of one logical change each. A good order: the reading view in the page; a turn opens in place and stays open, and the control that opens all; play; a line number pressed; after the check of who spoke; ruling 40; ruling 41. What a model writes is never asserted in a test.
Item 4. The browser, as rule 6 above says, after the last of those commits: each thing the details list under Seen in a browser, and each line of Done when you see, for 6e, walked through on the made-up consultation as far as a made-up one can show it. A fault found there is a commit of its own, and the report says so.

PART 3. THE CHECKS AND THE LAST COMMIT
Part 5 of STAGE_06C.md, with these changes. In item 1 the start check is run only if nothing answers on port 8001; if the port is taken, the mailbox, as BEFORE YOU START says. In item 2 the prompt folders are compared with 9aa9aab and show no change at all. In item 3 no address outside this machine is named at all. In item 4 the files of every older step count among those that are not yours, and the files this prompt names as read only. In item 5 the README gains what the details ask, and HANDOVER's entry for 6d2 is put right: fifteen commits, the spec at 9aa9aab.

THE REPORT
LOGS/STAGE6E_REPORT.md. It is private. First, for the patient, in plain words: what a doctor now reads as the transcript; where he sees a line the check moved, and how he puts it back; what happens to a leftover piece of a drug name; when the review page locks. Then, each under its own heading: the build, commit by commit; the turn rule with the nine counts; each thing seen in the browser, with what you saw, which scripts ran, and what you could not see; the lock, case by case, with the times; every sentence or name that is new, in full; every test restated or removed, or that there is none; what in LOGS may now be removed, without removing anything yourself. Then THE ROOM CHECK: the steps for the owner, short and in the order his hands do them, for the item Done when you see, for 6e; its first step is that he stops the app and starts it again. Last: anything you flagged.

FINAL MESSAGE
To LOGS/STAGE6E_TO_COWORK.md, eight lines at most: the spec's checksum as given and committed; the nine counts, equal or not; the reading view, ruling 40 and ruling 41, each in one line with whether you saw it in the browser; the suite's count; that nothing left the machine and no model was called; the number of commits and the last hash; anything you flagged. Do not push. Print Report sent to Cowork. Then go back to waiting for mail, as THE MAILBOX says.
