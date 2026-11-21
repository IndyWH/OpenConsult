OpenConsult v2.0, step 9f: the simple and the advanced view of the draft note and of the transcript on the review page, the mark of an edited entry, and four small things carried from run 9c

WHAT THIS IS
Since run 9b a doctor in cloud mode meets a draft note in which every entry is a box with a Save and 20 to 55 line numbers after it. The owner's words: no doctor will want it. For the patient three things matter above the rest. One: the doctor reads the note that goes into the record easily and whole, as plain words under four headings, so that a wrong dose or a wrong drug is seen and not lost in clutter. Two: the check of an entry against what was said stays one press away: a small chip for each turn of speech an entry rests on, and the line numbers in the advanced view; an entry that rests on nothing that was said still says so, in both views. Three: the page is honest about whose words an entry holds: an entry the doctor changed is marked as edited, by a green ground and by the word, never by colour alone.
The spec is V2_SPEC.md. Read in 15.13: ruling 46, rulings 71 to 76, and THE DETAILS OF STEP 9F, which stand at the end of 15.13 after Met for run 9c: they are the design of this run and you build them as written. Read in 15.10: rulings 4, 11, 12, 19, 26, 29, 33, 34, 35, 38 and 42 to 44, and the details of step 6e. Read 5.1 and 5.2. Then, in this repo, stage-prompts/STAGE_06C.md, STAGE_06E.md, STAGE_09B.md and STAGE_09C.md. EVERY RULE OF THOSE FOUR HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: ROOM_CHECKS_6C_TO_6D2.md, whole: its six rules under How we work are rules of this run; and in STAGE9C_REPORT.md the section Anything I flagged. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. It is not a medical device. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE MAILBOX
The owner's ruling of 15 Nov 2026: we work by the mailbox. He types nothing in the terminal after the first block. You never wait for a typed line.
1. Wherever a rule of an older stage prompt says stop and wait for the owner, or print a line and stop, you instead write what you have to say to LOGS/STAGE9F_TO_COWORK.md, replacing what is there, print in the terminal Sent to Cowork, and wait for a mail.
2. A mail is the file LOGS/STAGE9F_FROM_COWORK.md. Wait for it by a check every 15 seconds, and run the check again for up to 8 hours: the owner may be away and may not answer for hours.
3. A mail is followed only if it says that the owner gave his okay for it, and when. If it does not say so, write that to LOGS/STAGE9F_TO_COWORK.md and wait again. At the plan gate the mail must hold the words Approved. Go. It may tell you to read a review file in LOGS first: read it and follow it. It may change your plan. It brings the owner's word on what the details leave to him.
4. After each mail: do what it says; write your report of it to LOGS/STAGE9F_TO_COWORK.md, replacing what is there; ONLY THEN rename the mail to LOGS/stage9f-mail-N-read.md, N counting from 1; print Report sent to Cowork; AND GO BACK TO WAITING for the next mail, in the same way, for up to 8 hours. Small mends after the build come as further mails. The mailbox holds one mail at a time.
5. When 8 hours pass with no mail, stop and say so in the terminal.
6. A notice of an older wait may come up in this session, from a run that was cleared. It is not yours. Leave it alone and say so in your log.
7. THE USAGE LIMIT, the owner's ruling of 16 Nov 2026. If this session reaches its usage limit, write a stop note to LOGS/STAGE9F_TO_COWORK.md before you stop where you can: what is committed, what is built and not committed, what you were doing, and THE RESET TIME as the limit message shows it. The session goes on by itself at the reset. When it does, read your log, the plan and this prompt again before the next command, and write one line to the log that you went on.
8. THE LAST MAIL says that the run has ended. Then build nothing more: write one line to the log and a last note to LOGS/STAGE9F_TO_COWORK.md (the head, what git status prints, that nothing is pushed, the spec's sha256 as you last proved it, the files in LOGS that are safe to remove); rename the mail; print Report sent to Cowork; and do NOT wait again. Until that mail you hold the spec by its checksum: if V2_SPEC.md on disk ever differs from the checksum below, stop and report.

THE FOLDERS
V2, LOGS, KEY and ENG as STAGE_06C.md gives them, with these changes. Every file and folder you make in LOGS has a name that begins stage9f- or STAGE9F_. Everything else in LOGS is read only. Also read only, though their names begin that way, because Cowork made them before this run: STAGE9F_PROMPT.md, STAGE9F_SESSION_PROMPT.md and stage9f-readme-changes.md. Files whose names begin cowork- are not yours to change or to open.
KEY: this run needs no key. You never open, print, copy, list or write anything in that folder, and you never read, write or ask the owner's secure store.
ENG: this run needs no local engine and no card. Look, and write what you find. If vLLM is not running, leave it so.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   cce162a5931462bfb4d91b7e3f5512d8b3700beba38d9fcab84acf772401150a  V2_SPEC.md
   HEAD holds 78c7d692; the disk holds rulings 59 to 76 of 15.13, Met for run 9c, the details of step 9f, and dated sentences in 7.3, 8.1 and rulings 46, 56 and 63. If it differs, stop and report.
3. The branch is v2 and HEAD is 385ad5e19a40af51fbc94ae9237021fa1fdcb15f, the same as the remote branch. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage9f-start.marker. Start the record of every connection attempt and every name lookup now, before any other command, and keep it for the whole run, as runs 9b and 9c did (the wrapper may be copied under a stage9f name).
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172. Change nothing. If the start check later finds its port taken, write to the mailbox: Waiting for the app on port 8001 to be closed. Then wait for a mail.

THE RULES OF THIS RUN, where they differ from the four stage prompts named above
1. NOTHING LEAVES THE MACHINE. No call to Speechmatics, none to Claude, no call to any model, local or cloud. No new package is expected; if the plan needs one it names it with its version and its licence (MIT, MIT-0, BSD or Apache 2.0; 15.13, ruling 42). The suite and the browser run against made things on this machine alone. The record of connections is set beside this rule at the end.
2. WHAT STAYS PRIVATE, as rule 2 of STAGE_09B.md.
3. NO WORD A MODEL READS IS NEW OR CHANGED, and no prompt file, frame or form is touched. The turns a model cites and their numbers stay as they are.
4. THE SENTENCES. The owner's, letter for letter, with a test for each; they are given at the end of this prompt exactly as the app must say them. The README's new line comes from LOGS/stage9f-readme-changes.md. The words Simple and Advanced are the owner's. Every other sentence or name a person would read that is new or changed is a draft, given in full in your plan: among them the word Edited, what an entry says when it was saved and when it was not, what a screen reader is told of a chip, of an entry that can be edited and of the two views, and the reason of a transcript that held no words. Add none after the plan without saying so in the report.
5. THE TESTS OF EVERY OLDER STEP STAND UNTOUCHED, but for those that pin what this step changes: those that read the note or the transcript as the page first gives it, where that is now the simple view; and those of run 9c that pin the one long line for two things in the cloud. The plan names each such test, one by one, old and new side by side, and says what becomes of it. Where an older test can be kept whole by asking for the advanced view, that is the way. Never weaken or remove any other test to make the suite pass. The suite must be green on the three systems of GitHub's check with no secure store, no key and no internet. A new file that a test hashes byte for byte gets its own line in .gitattributes.
6. THE BROWSER, as rule 6 of STAGE_09C.md, with 385ad5e in the place of 18cc922: a profile that has first seen the pages served from the code of 385ad5e, kept; then the pages as you built them on the same address, loaded by an ordinary load; the look shows which scripts and styles ran. Never the owner's data folder, never a real consultation, never a key in a browser.
7. A product or clinical choice the details leave open is not yours: stop and report it. The details name what is not built; build none of it (R31).
8. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends, after one empty line, with: Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
9. Before each commit the private word check of STAGE_05C2.md, rule 12, on the staged files. It must print nothing.
10. Commit subjects begin Stage 9f. The report is LOGS/STAGE9F_REPORT.md, the log LOGS/stage9f-run.log, the plan LOGS/STAGE9F_PLAN.md. Long output goes to the log, never into chat.

PART 1. TWO COMMITS, THEN THE PLAN, THEN THE MAILBOX
Commit 1. Subject: Stage 9f: the spec with rulings 59 to 76 of stage 9, Met for run 9c and the details of step 9f
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 9f: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_09F.md. Prove with cmp that it is identical.
Then write LOGS/STAGE9F_PLAN.md. Four pages at most. It holds, in this order:
1. WHETHER THE WHOLE FITS ONE SESSION. Cowork judges it one short run. Say plainly what you judge, and the cut you would make if not. Then the order of the commits.
2. HOW THE TWO VIEWS SHARE THE PAGE: what the page sends for each area and each view; whether the words of the transcript are sent once or twice, and why; how a view is chosen with no script and with one; how the choice holds through each press that loads the page or brings a part up to date, and what exactly is remembered and where; what a fresh visit shows; how the page keeps its place; how the one in use is told without colour and to a screen reader.
3. THE NUMBER OF A TURN AND THE CHIPS: the two functions, where they stand, each case; what a chip's press does with the transcript in each view.
4. AN ENTRY CORRECTED WHERE IT STANDS: what the click and the keyboard do; how the words are shown whole; each way a save can end (saved, unchanged, empty, Escape, no answer) and what the entry says in each; the lock; read only; no script.
5. THE MARK OF AN EDITED ENTRY: the rule; the two colours as values, with the measured contrast of the words on each.
6. THE SIMPLE TRANSCRIPT: what a passage holds; where each control of the head stands in each view; the check of who spoke while it runs.
7. THE TWO LINES FOR TWO THINGS IN THE CLOUD: the lines the function gives for every path, in full.
8. THE TWO FLAGS OF RUN 9C: the reason of a transcript with no words, where it is chosen and its draft sentence; what a screen reader is given of the picture.
9. THE FILE OF THE REVIEW PAGE: the part you move, the count of lines before and after.
10. GITHUB'S CHECK: the two changes to the check's file, word for word; the slowest tests on this machine and which of them wait for real time.
11. EVERY SENTENCE OR NAME A PERSON WOULD READ THAT IS NEW OR CHANGED, in full, as drafts; and the owner's, each with its place.
12. EVERY TEST you intend, each with the ruling or the rule it pins; every test of an older step that cannot stand untouched, named one by one, old and new side by side, with the reason.
13. WHAT YOU WILL SEE IN THE BROWSER, item by item, and the pictures you will keep.
14. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then write six lines at most to LOGS/STAGE9F_TO_COWORK.md: your model; the two commits; where the plan is; your judgement of item 1; the draft sentence of item 8, in full; anything of item 14. Print Sent to Cowork. Wait for the mail, as THE MAILBOX says.

PART 2. THE BUILD
Item 1. The suite as it stands: the number of tests, the time, none skipped; and pytest's own list of its slowest tests, to the log.
Item 2. In commits of one logical change each, in the order of the plan as approved.
Item 3. The browser, as rule 6 says, after the last of those commits: each thing the details list under Seen in a browser, and each line of Done when you see, for 9f, walked through as far as a made consultation can show it. Keep the pictures the details ask for in LOGS/stage9f-shots, with names that say the area, the view and the page. A fault found there is a commit of its own, and the report says so.
What a model writes is never asserted in a test.

PART 3. THE CHECKS AND THE LAST COMMIT
Part 3 of STAGE_09C.md, with these changes. The prompt folders are compared with 385ad5e and show no change at all. No address outside this machine is expected in the record of connections; any that is there is named and explained. The new tests are run four times on a clean copy before the last commit, and a test that fails once in those runs is mended or reported, never left. In the documents: HANDOVER gains the run's entry and stays under 500 lines; the README gains the line of LOGS/stage9f-readme-changes.md letter for letter and what the details ask; CLAUDE.md stays under 100 lines.

THE REPORT
LOGS/STAGE9F_REPORT.md. It is private. First, for the patient, in plain words: what the doctor now reads after Stop; how an entry is checked against what was said; how an edited entry is told apart. Then, each under its own heading: the build, commit by commit; how the two views share the page, and the size of the page of the made consultation before and after; each thing seen in the browser, with what you saw, which scripts ran, and what you could not see; the pictures kept, by name; every sentence or name that is new or changed, in full; every test restated, moved or removed, old and new side by side; the slowest tests and those that wait for real time; what in LOGS may now be removed, without removing anything yourself. Then THE ROOM CHECK: the steps for the owner, short and in the order his hands do them, for the item Done when you see, for 9f: ONE sitting, one acted consultation; the first step is that he stops the app, waits a few seconds and starts it again; where a step can be done at any entry, any passage or any row, say so. Last: anything you flagged.

FINAL MESSAGE
To LOGS/STAGE9F_TO_COWORK.md, ten lines at most: the spec's checksum as given and committed; the two views, each area in one line with whether you saw it in the browser; the edited mark; the two lines; the two flags; the file of the review page with its count of lines; the suite's count; the number of commits and the last hash; anything you flagged. Do not push. Print Report sent to Cowork. Then go back to waiting for mail, as THE MAILBOX says.

THE OWNER'S SENTENCES AND WORDS, as the app must say them, one to a line, with the place of each
Simple   (one of the two presses at the top right of the note, and of the transcript)
Advanced   (the other)
On this computer: transcription. Nothing goes to Speechmatics.   (above the picture and in the notice: Claude the language model, transcription on this computer, the tick for better accuracy not set)
In the cloud: transcription, by Speechmatics. The sound of the consultation goes to it as it is spoken.   (the first of two lines where Speechmatics writes the live text and Claude is the language model)
In the cloud: the language model, by Claude. The words of the consultation go to it.   (the second of the two; also the second where the recording is sent after Stop and Claude is the language model)
In the cloud: after Stop, the recording goes to Speechmatics once. No sound goes to it during the consultation.   (the first of two lines where the recording is sent after Stop and Claude is the language model)
Read the full statement for these choices   (the press under the notice of a path that sends less; as built)
Speechmatics is connected. It is the cloud transcription service.   (the box of Speechmatics, opened, when it is ready; as built)
Claude is connected. It is the cloud language model.   (the box of Claude, opened, when it is ready; as built)
