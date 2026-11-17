OpenConsult v2.0, run 9c: the control panel of This machine, a tick or a choice in Settings that saves by itself, the rest of the settings menu that does not wait for a later stage, and the mends from the room check of run 9b

WHAT THIS IS
Since run 9b a doctor can run a consultation in cloud mode. The owner's room check of 17 Nov 2026 met and passed it, and showed what still stands between a doctor and a safe use of it. For the patient three things matter above the rest. One: before a consultation the doctor sees on ONE picture whether the path chosen is ready and whether sound or words leave the computer; today that is said in three places and nothing is drawn. Two: a setting the doctor believes is set is set: a tick or a choice saves by itself, and a choice that sends something new off the computer is saved only by the tick under its statement, never without it. Three: the page never claims what it cannot show: a delete is called confirmed only when it is, the mark says went only when the recording went, and no line names a speech model that did not write the transcript on the page.
The spec is V2_SPEC.md. Read 7.1, 7.2 and 7.3. Read in 15.13 rulings 5, 6, 23, 29, 33, 36 to 45 and 46 to 58, Met for run 9b, and THE DETAILS OF RUN 9C, which stand at the end of 15.13: they are the design of this run and you build them as written. Read in 15.8 rulings 36 to 38 with their details. Then, in this repo, stage-prompts/STAGE_06C.md, STAGE_06E.md and STAGE_09B.md. EVERY RULE OF STAGE_06C.md, OF STAGE_06E.md AND OF STAGE_09B.md HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: ROOM_CHECKS_6C_TO_6D2.md, whole: its six rules under How we work are rules of this run; and in STAGE9B_REPORT.md the sections Each thing seen in the browser and Anything I flagged. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. It is not a medical device. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE MAILBOX
The owner's ruling of 15 Nov 2026: we work by the mailbox. He types nothing in the terminal after the first block. You never wait for a typed line.
1. Wherever a rule of an older stage prompt says stop and wait for the owner, or print a line and stop, you instead write what you have to say to LOGS/STAGE9C_TO_COWORK.md, replacing what is there, print in the terminal Sent to Cowork, and wait for a mail.
2. A mail is the file LOGS/STAGE9C_FROM_COWORK.md. Wait for it by a check every 15 seconds, and run the check again for up to 8 hours: the owner may be away and may not answer for hours.
3. A mail is followed only if it says that the owner gave his okay for it, and when. If it does not say so, write that to LOGS/STAGE9C_TO_COWORK.md and wait again. At the plan gate the mail must hold the words Approved. Go. It may tell you to read a review file in LOGS first: read it and follow it. It may change your plan. It brings the owner's word on what the details leave to him.
4. After each mail: do what it says; write your report of it to LOGS/STAGE9C_TO_COWORK.md, replacing what is there; ONLY THEN rename the mail to LOGS/stage9c-mail-N-read.md, N counting from 1; print Report sent to Cowork; AND GO BACK TO WAITING for the next mail, in the same way, for up to 8 hours. Small mends after the build come as further mails.
5. When 8 hours pass with no mail, stop and say so in the terminal.
6. A notice of an older wait may come up in this session, from a run that was cleared. It is not yours. Leave it alone and say so in your log.
7. THE USAGE LIMIT, the owner's ruling of 16 Nov 2026. If this session reaches its usage limit, write a stop note to LOGS/STAGE9C_TO_COWORK.md before you stop where you can: what is committed, what is built and not committed, what you were doing, and THE RESET TIME as the limit message shows it. The session goes on by itself at the reset. When it does, read your log, the plan and this prompt again before the next command, and write one line to the log that you went on.

THE FOLDERS
V2, LOGS, KEY and ENG as STAGE_06C.md gives them, with these changes. Every file and folder you make in LOGS has a name that begins stage9c- or STAGE9C_. Everything else in LOGS is read only. Also read only, though their names begin that way, because Cowork made them before this run: STAGE9C_PROMPT.md, STAGE9C_SESSION_PROMPT.md and stage9c-readme-changes.md. Files whose names begin cowork- are not yours to change or to open.
KEY: the rule of STAGE_09A.md holds word for word. You never open, print, copy, list or write its .env or anything else in that folder. A key reaches a command in one way only: the command is given that folder as the place of the key file and reads the key inside its own process. No copy of a key is made anywhere, and you never read, write or ask the owner's secure store.
ENG: the machine was started afresh on the evening of 17 Nov 2026. Look, and write what you find. This run needs no local engine: if vLLM is not running, leave it so. The rule of 15.13, ruling 1 holds if a check should need it, and only by your approved plan.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   78c7d692b93159bab312500dee1a993fe8828540eb4736a67fbf36eb9ba4f70a  V2_SPEC.md
   HEAD holds 53a2b6d5; the disk holds rulings 46 to 58 of 15.13, the details of run 9c, five lines of 7.3 with a dated sentence more each. If it differs, stop and report.
3. The branch is v2 and HEAD is 18cc92207d57a3b6fd55b13858cfb8faf0713f8c, the same as the remote branch. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage9c-start.marker. Start the record of every connection attempt and every name lookup now, before any other command, and keep it for the whole run, as run 9b did (its wrapper may be copied under a stage9c name).
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172; the card's memory in use. Change nothing. If the start check later finds its port taken, write to the mailbox: Waiting for the app on port 8001 to be closed. Then wait for a mail.

THE RULES OF THIS RUN, where they differ from the three stage prompts named above
1. WHAT LEAVES THE MACHINE, and nothing else does. To the EU address of Speechmatics that the app's own test of a connection uses, and to no other: that test made 30 times, 20 seconds apart, for the second measurement of the details; it opens a session, sends no sound and closes. The key is read from KEY inside the process. A refused key, used-up credit or three tries in a row with no answer end it, and the report says so. NO CALL IS MADE TO CLAUDE in this run. No new package is expected; if the plan needs one it names it with its version and its licence (MIT, MIT-0, BSD or Apache 2.0; 15.13, ruling 42). Everything else, the suite and the browser included, runs against made services on this machine. The record of connections is set beside this rule at the end.
2. WHAT STAYS PRIVATE, as rule 2 of STAGE_09B.md.
3. NO WORD A MODEL READS IS NEW OR CHANGED, and no prompt file, frame or form is touched.
4. THE SENTENCES. The owner's, letter for letter, with a test for each: the mark's line on the review page (ruling 52): After Stop the recording went to Speechmatics. And THE EIGHT OF RULING 53, which already stand in the file of words; they are given at the end of this prompt exactly as that file must hold them, and none is changed. The README's sentence comes from LOGS/stage9c-readme-changes.md. Every other sentence or name a person would read that is new or changed is a draft, given in full in your plan. Add none after the plan without saying so in the report.
5. THE TESTS OF EVERY OLDER STEP STAND UNTOUCHED, but for those that pin what rulings 47 to 52 change: a Save press on a control that now saves by itself; a tick asked for every changed path; one ask alone after a delete; the Start screen that waits for its tests; the mark's line on the review page; the line on confidence. The plan names each such test, one by one, old and new side by side, and says what becomes of it. Never weaken or remove any other test to make the suite pass. The suite must be green on the three systems of GitHub's check with no secure store, no key and no internet. A new file that a test hashes byte for byte gets its own line in .gitattributes, as why_this_model.md has since 18cc922.
6. THE BROWSER, as rule 7 of STAGE_09B.md, with 18cc922 in the place of 0631413: a profile that has first seen the pages served from the code of 18cc922, kept; then the pages as you built them on the same address, loaded by an ordinary load; the look shows which scripts and styles ran. Never the owner's data folder, never a real consultation, never a real key in a browser.
7. A product or clinical choice the details leave open is not yours: stop and report it. The details name what is not built; build none of it (R31). The lowest and the highest value of each of the two thresholds are the owner's: propose them in the plan with your reason and build them only as the mail at the plan gate gives them.
8. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends, after one empty line, with: Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
9. Before each commit the private word check of STAGE_05C2.md, rule 12, on the staged files. It must print nothing.
10. Commit subjects begin Stage 9c. The report is LOGS/STAGE9C_REPORT.md, the log LOGS/stage9c-run.log, the plan LOGS/STAGE9C_PLAN.md. Long output goes to the log, never into chat.

PART 1. TWO COMMITS, THEN THE PLAN, THEN THE MAILBOX
Commit 1. Subject: Stage 9c: the spec with rulings 46 to 58 of stage 9 and the details of the run
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 9c: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_09C.md. Prove with cmp that it is identical.
Then write LOGS/STAGE9C_PLAN.md. Five pages at most. It holds, in this order:
1. WHETHER THE WHOLE FITS ONE SESSION. The owner ruled one run in two halves (ruling 58). Say plainly what you judge, and the cut you would make if not. Then the order of the commits, half one and half two, and what stands by itself at the half.
2. A SAVE BY ITSELF (ruling 47): each control that saves on its change and each that keeps its Save; the script and what the page does where it has not run; how the page keeps its place; what the page says while a statement waits and after a save.
3. NO NEW TICK FOR LESS (ruling 48): what is kept with a tick; the test by sentence; a table of every pair of paths, from each to each, with tick asked or not; a folder that ticked before this run.
4. THE SECOND ASK AFTER A DELETE (ruling 49): where it sits, its 5 seconds, what the record holds, the new limit of time of the stage at Stop.
5. THE START SCREEN (ruling 51): how the result reaches the page without the page moving; how the app itself refuses a press that comes before the tests have answered.
6. THE MARK'S LINE, THE LINE ON CONFIDENCE, THE ROUND BUTTONS: each in a few lines, with the cause as you read it in the code.
7. THE TWO MEASUREMENTS: how each is made, what it sends, and what figure would count as a fault of the app.
8. THE CONTROL PANEL (rulings 6 and 56): the elements, and for each box where each fact comes from; each state of each box with its sentence; how the chosen path is drawn and told without colour; how a box opens with no script; each action and where it leads; the first run beside Settings; a narrow window; the order a screen reader meets it in; what stays in the small table.
9. THE SECTION LOCAL MODELS, THE SPEECH MODEL OF THIS COMPUTER, THE TWO THRESHOLDS: what each shows and holds; for each threshold the lowest and the highest value you propose, with your reason, FOR THE OWNER.
10. THE TABLES OF VERSION 12.
11. EVERY SENTENCE OR NAME A PERSON WOULD READ THAT IS NEW OR CHANGED, in full, as drafts; and the owner's, each with its place.
12. EVERY TEST you intend, each with the ruling or the rule it pins; every test of an older step that cannot stand untouched, named one by one, old and new side by side, with the reason.
13. WHAT YOU WILL SEE IN THE BROWSER, item by item.
14. The size targets of section 5 that this run presses on, with the figures as they stand.
15. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then write six lines at most to LOGS/STAGE9C_TO_COWORK.md: your model; the two commits; where the plan is; your judgement of item 1; the bounds you propose in item 9, in one line; anything of item 15. Print Sent to Cowork. Wait for the mail, as THE MAILBOX says.

PART 2. THE BUILD
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. HANDOVER first: move older entries to archive/HANDOVER_ARCHIVE.md so that the run's lines fit, and put its entry for run 9b right, as the details say. One commit.
Item 3. Half one, in commits of one logical change each, in the order of the plan as approved. The two measurements are made in this half, each written to its own file in LOGS, and a mend follows only where the figures show a fault of the app.
Item 4. THE HALF. The suite green. One line in HANDOVER that half one stands by itself. Write four lines to LOGS/stage9c-half.md: the commits so far, the suite's count, the figures of the two measurements in one line each. Do not wait: go on.
Item 5. Half two, in the same way.
Item 6. The browser, as rule 6 says, after the last of those commits: each thing the details list under Seen in a browser, and each line of Done when you see, for 9c, walked through as far as made services can show it. A fault found there is a commit of its own, and the report says so.
What a model writes is never asserted in a test.

PART 3. THE CHECKS AND THE LAST COMMIT
Part 5 of STAGE_06C.md, with the changes Part 3 of STAGE_09B.md gives, and these. The prompt folders are compared with 18cc922 and show no change at all. Every address outside this machine is named and set beside rule 1, with the count of calls to each. The new tests are run four times on a clean copy before the last commit, and a test that fails once in those runs is mended or reported, never left. In the documents: HANDOVER gains the run's entry; the README gains the change of LOGS/stage9c-readme-changes.md letter for letter and what the details ask; CLAUDE.md stays under 100 lines; .env.example is brought into step if anything of it has changed.

THE REPORT
LOGS/STAGE9C_REPORT.md. It is private. First, for the patient, in plain words: what the doctor sees on the picture before a consultation; what saving by itself changes and what still needs a tick; what the page says about a recording that was sent after Stop. Then, each under its own heading: the build, commit by commit; the two measurements with their figures; each thing seen in the browser, with what you saw, which scripts ran, and what you could not see; the picture as the app draws it, for each state of each box, in words; the table of every pair of paths with tick asked or not, as the app decides it; every sentence or name that is new or changed, in full, the drafts that speak of where sound, words or a key go set apart; every test restated, moved or removed, old and new side by side; what left the machine, address by address; what in LOGS may now be removed, without removing anything yourself. Then THE ROOM CHECK: the steps for the owner, short and in the order his hands do them, for the item Done when you see, for 9c: ONE sitting, one acted consultation; the first step is that he stops the app, waits a few seconds and starts it again; where a step can be done at any row or any line, say so. Last: anything you flagged.

FINAL MESSAGE
To LOGS/STAGE9C_TO_COWORK.md, ten lines at most: the spec's checksum as given and committed; half one and half two, each in one line with whether you saw it in the browser; the two measurements, one line each; the suite's count; what left the machine, in one line; the number of commits and the last hash; anything you flagged. Do not push. Print Report sent to Cowork. Then go back to waiting for mail, as THE MAILBOX says.

THE SKETCH THE OWNER APPROVED (ruling 56), as a figure in plain text. His own machine is the example: both paths on this computer, the tick for better accuracy set, Claude not connected.

   Microphone          Transcription             Language model           Consultation

 [ Microphone    ] --> [ This computer     ] --> [ This computer    ] --> [ Consultation   ]
   Ready                 Ready, Nemotron           Ready, Gemma 4           Ready to start
   tested today          Chosen                    Chosen

                       [ Speechmatics, cloud ]   [ Claude, cloud    ]
                         Ready, connected          Not set up
                         Used after Stop

 Signs: a tick and Ready; a dash and Not set up; a cross and Cannot run here, with the reason.
 The chosen path: a heavier border, the word Chosen, and the arrows.
 A box, pressed, opens one sentence and one action. For the Claude box above:
   Claude is not connected. It is the cloud language model, for a computer that cannot run its own.   [ Connect ]
 The sentences in the figure are drafts. The shape is the owner's.

THE EIGHT SENTENCES OF RULING 53, as the file of words must hold them, one to a line, with the place of each
The emergency alarm has stopped listening.   (the live page, when the speech stops: a lost connection, or the speech choice of this computer stopped)
Better accuracy: after Stop, send the whole recording to Speechmatics once, for the final transcript.   (the label of the tick under Transcription)
Send the recording once for the whole transcript.   (a press at Stop after a lost connection)
Go on without it.   (the other press)
The final transcript was made by Speechmatics from the whole recording. It was deleted there, and Speechmatics confirmed that it is gone.   (above the note; the first of its two sentences alone when the delete is not proven)
Sending the recording to Speechmatics and waiting for the transcript: {seconds} s.   (after Stop, while the recording is away)
This sound is not stored and is not sent anywhere.   (the microphone test)
The key is in this computer's secure store.   (Connections)
The key comes from the environment the app was started in.   (Connections)
The key comes from the file .env in the data folder.   (Connections)
Connected. The key is kept in this computer's secure store.   (a connect screen, after a passed test)
Removed. The key is no longer in this computer's secure store.   (Connections, after Remove)
