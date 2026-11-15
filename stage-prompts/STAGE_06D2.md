OpenConsult v2.0, step 6d, the mend run (6d2): the first play, a name typed and left, the page keeps its place, and the check of who spoke is seen

WHAT THIS IS
Step 6d built the row where a doctor hears a doubted drug name, types the right name over it and ticks it. The owner ran it in the room on 15 Nov 2026. It did what it is for: the language model marked 15 names, he corrected five at their rows, and the note drafted again held the right medicine. But the page failed under his hands four times. The play buttons were silent until the page had been loaded again. A name he typed was lost when he clicked outside the box. After each press the page moved by itself, past the next row. And the check of who spoke changed 29 lines while all he saw was a faded button. For a patient this matters plainly: a name a doctor typed and believes saved, but which is not, leaves the wrong medicine in the note; and a change of 29 speakers that the doctor does not see cannot be judged by him. This run mends those four things and nothing else. No bench, no call to any model, nothing leaves the machine.
The spec is V2_SPEC.md. Read in 15.10 rulings 11, 18, 19, 26, 28, 29, 33, 34 and 37, and THE DETAILS OF THE MEND RUN OF STEP 6D, 6D2, which follow the details of step 6d: they are the design of this run and you build them as written. Read the details of step 6d for what stands, its last item included. Then, in this repo, stage-prompts/STAGE_06C.md and STAGE_06D.md. EVERY RULE OF STAGE_06C.md HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: STAGE6D_REPORT.md with its flags, and STAGE6D_PLAN_REVIEW.md. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE FOLDERS
V2, LOGS and KEY as STAGE_06C.md gives them, with one change: every file and folder you make in LOGS has a name that begins stage6d2- or STAGE6D2_. Everything else in LOGS is read only, the files and folders of 6d included. Files whose names begin cowork- are not yours to change or to open: cowork-6d-room-check.txt holds lines of the owner's acted consultation and is not for you.
No engine is started in this run, no call goes to any model, and the card is not needed. KEY is never needed.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   81faf6ff9115abe40ff3913ff07bcd520b4788081236317975b4d6485558c99c  V2_SPEC.md
   HEAD holds f8a75a3b; the disk holds rulings 32 to 37 of 15.10, the corrections that go with them, and the details of the mend run. If it differs, stop and report.
3. The branch is v2 and HEAD is 33c8c9ad7521c04958688f9b444aef7b3180ad7b. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage6d2-start.marker. Start the record of connections now, before any other command, and keep it for the whole run.
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172. Change nothing. If the start check later finds its port taken, print exactly: Waiting for the app on port 8001 to be closed. Then stop; the owner will type: Closed. Go.

WHAT CHANGES FROM STAGE_06C.md
1. WHAT LEAVES THE MACHINE. Nothing, in the whole run. The record of connections must show no address outside this machine. No new package is added; if you find you need one, stop and report.
2. NO WORD A MODEL READS IS NEW OR CHANGED, and no prompt file, frame or form is touched. What the check of who spoke decides is not yours to mend: the owner saw it move three lines to the wrong speaker, and that is noted for a later step.
3. THE SENTENCES. None of the owner's sentences changes. If you find you need a sentence a person would read that the page does not have, give it in full in your plan as a draft, and add none after the plan without saying so in the report.
4. NOT BUILT. The details name what is not built; build none of it (R31). Above all: nothing of the transcript's layout beyond the place of a changed line's words and its Undo, because the next step draws the transcript again; no browser and no script engine in the suite.
5. THE BROWSER. The four mends are of a page under a doctor's hands, and the suite cannot see them. So you see each one in a real browser, as in 6d: the suite's made-up consultation served on this machine alone, a made sound, a temporary folder, the suite's own made-up login. Never the owner's data folder, never a real consultation. For the first play you must make the fault first and then see it gone: the page shown while the recording is still a WAV, the recording converted after, then the first press of play without loading the page.
6. Commit subjects begin Stage 6d2. The report is LOGS/STAGE6D2_REPORT.md, the log LOGS/stage6d2-run.log.

PART 1. TWO COMMITS, THEN THE PLAN, THEN STOP
Commit 1. Subject: Stage 6d2: the spec with rulings 32 to 37 of stage 6 and the details of the mend run
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 6d2: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_06D2.md. Prove with cmp that it is identical.
Then write LOGS/STAGE6D2_PLAN.md. Keep it short: two pages at most. It holds, in this order:
1. THE FIRST PLAY: what happens today, step by step, in the Stop thread, the recording's address and the page's player; your mend; what the browser's own play control does before and after; what happens with no script.
2. LEAVING THE BOX: what the script sends and when; the press keep and what the app does with it; HOW THE PRESS THAT TOOK THE DOCTOR OUT OF THE BOX IS NEVER LOST (play on another row; the row's own tick; a press on Draft the note again; a click on nothing); HOW THE PAGE SHOWS WHAT A LOAD WOULD SHOW after the save, with no load by the doctor; what happens when the save is refused or fails. Cowork's review rules on this item.
3. THE ENTER KEY AND THE TICK: that both are as built, proven by their tests standing untouched.
4. THE KEPT WORDS: every file and line that goes, or the case in which they must stay.
5. THE PAGE KEEPS ITS PLACE: each press of the review page, one by one, and where the page stands after it; the keyboard's place; what happens with no script.
6. THE CHECK OF WHO SPOKE: where the page stands after the press, during each wait and at the end, with and without a script; how the running and outcome sentences and Undo all are shown; how a changed line is shown, and how it is told without colour.
7. Every sentence a person would read that is new or changed, in full. There may be none.
8. EVERY TEST you intend, each with the ruling or the rule it pins; every test restated or removed, named one by one with the reason.
9. WHAT YOU WILL SEE IN THE BROWSER, mend by mend, and how you make the first play's fault before you mend it.
10. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then print five lines at most, and stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 2. THE BUILD
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. As the details give it, in commits of one logical change each. A good order: the first play; the press keep in the app, with its tests; leaving the box in the page's script, and the kept words gone; the page keeps its place; the check of who spoke is seen. What a model writes is never asserted in a test.
Item 3. The browser, as rule 5 above says, after the last of those commits: each mend seen, and each line of Done when you see, for 6d2, walked through on the made-up consultation as far as a made-up one can show it. A mend found wanting there is a commit of its own, and the report says so.

PART 3. THE CHECKS AND THE LAST COMMIT
Part 5 of STAGE_06C.md, with these changes. In item 2 the prompt folders are compared with 33c8c9a and show no change at all. In item 3 no address outside this machine is named at all. In item 4 the files of 6c, 6c2 and 6d count among those that are not yours. In item 5 the README gains what the details ask.

THE REPORT
LOGS/STAGE6D2_REPORT.md. It is private. First, for the patient, in plain words: what a doctor's hands now meet at a row of a doubted drug name, in the order his hands do it, and what he now sees after the check of who spoke. Then, each under its own heading: the build, commit by commit; each of the four mends with what you saw in the browser and what you could not see; every sentence that is new or changed, in full, or that there is none; every test restated or removed; what in LOGS may now be removed, without removing anything yourself. Then THE ROOM CHECK: the steps for the owner, short and in the order his hands do them, for the item Done when you see, for 6d2. Last: anything you flagged.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; each of the four mends in one line, with whether you saw it in the browser; the suite's count; that nothing left the machine and no model was called; the number of commits and the last hash; anything you flagged; then this line for the owner: Tell Cowork: Step 6d2 built. Do not push yet.
