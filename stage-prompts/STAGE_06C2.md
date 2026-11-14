OpenConsult v2.0, step 6c, the second run (6c2): the rule of the reply, the count again, then the build at Stop

WHAT THIS IS
The first run of step 6c stopped after its first act on 13 Nov 2026: the bench of parts missed its mark P1, and nothing of the app was built. The reason was not the parts. On pages where one line holds both speakers the model named that line twice, as patient and then as doctor, and the app's rule threw the whole reply away. The owner ruled the same day (15.10, ruling 24): such a line is shown as unsure and the reply is kept; a number that is not on the page is dropped; a reply that misses a line is still refused. The prompt of the check is not changed by a word. This run changes that rule, counts the stored replies again with no new call, and, if the two marks hold, does everything the first run did not reach: the build at Stop and the bench of Claude Haiku. From the patient's side nothing has changed yet: a doctor still gets no mark on a doubtful drug name, and the check of who spoke still runs by itself at Stop, where it made well labelled pages worse. This run is what changes both.
The spec is V2_SPEC.md. Read in 15.10 ruling 24 and THE DETAILS OF THE SECOND RUN OF THE STEP, 6C2, which follow the details of step 6c; then everything stage-prompts/STAGE_06C.md tells you to read. EVERY RULE OF STAGE_06C.md HOLDS IN THIS RUN except where this prompt changes it. Then, in LOGS: STAGE6C_PLAN.md and STAGE6C_PLAN_REVIEW.md, which stand for the build and for the bench of Claude Haiku, every point of the review included; STAGE6C_REPORT.md and STAGE6C_PARTS.md. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.2 at high effort. Say in your first line which model you are. If you are not Fable 5.2, stop there.

THE FOLDERS
V2, LOGS, KEY and ENG as STAGE_06C.md gives them, with one change: every file and folder you make in LOGS has a name that begins stage6c2- or STAGE6C2_. Everything else in LOGS is read only, the files and folders of the first run included: copy what you reuse under a stage6c2- name.

BEFORE YOU START
1. Read V2/CLAUDE.md and the newest entry of V2/HANDOVER.md.
2. Check the spec with sha256sum. It must be:
   6ace90ba9427db71562accb26caac1164ef40ae39b5639c6a6d419279fa494f9  V2_SPEC.md
   HEAD holds cf560f65; the disk holds ruling 24 of 15.10 and the details of the second run. If it differs, stop and report.
3. The branch is v2 and HEAD is a2dc27e079791aa889bd81093af8ae96ea03fad5. git status --porcelain prints one line only: V2_SPEC.md modified. Otherwise stop and report.
4. Make an empty file LOGS/stage6c2-start.marker. Start the record of connections now, before any other command, and keep it for the whole run.
5. Look, read only, and write what you find in your log: whether anything answers on 127.0.0.1 at ports 8000, 8001 and 8172; the card's memory. Change nothing. This run starts no engine and needs no card.

WHAT CHANGES FROM STAGE_06C.md
1. PART 2 OF THAT PROMPT IS REPLACED by the count again, below. No engine is started in this run and no call goes to the local model: the stored replies are judged again. The gate for the card is not needed. If the start check finds its port taken, print exactly: Waiting for the app on port 8001 to be closed. Then stop; the owner will type: Closed. Go.
2. THE RULE OF THE REPLY is ruling 24, as the details of the second run give it: one function for the app and the bench. The stored result files of 5e and of the first run hold labels and refusals worked out by the old rule; the count again must judge each stored answer afresh and never read those stored fields. No stored file is changed.
3. THE PLAN OF 6C STANDS for Part 3 and Part 4, with its review. You do not write it again. Where ruling 24 or the details of the second run change a line of it, the change stands and your short plan names it.
4. Commit subjects begin Stage 6c2. The report is LOGS/STAGE6C2_REPORT.md, the log LOGS/stage6c2-run.log.

PART 1. TWO COMMITS, THEN A SHORT PLAN, THEN STOP
Commit 1. Subject: Stage 6c2: the spec with ruling 24 of stage 6 and the details of the second run
   V2_SPEC.md alone, as it stands on disk, checksum proven.
Commit 2. Subject: Stage 6c2: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_06C2.md. Prove with cmp that it is identical.
Then write LOGS/STAGE6C2_PLAN.md. One page. It holds, in this order:
1. The change of check_labels: what it gives back, every caller in the app and in the bench, and each test with what it pins, the tests of the old rule that are rewritten named one by one.
2. The count again: the commands with their exact words and folders; how each stored answer is judged afresh; what speech-stop-marks gains to do it.
3. Every line of STAGE6C_PLAN.md that ruling 24 or the details of the second run change, and nothing else of that plan.
4. Anything in the spec or in this prompt that is wrong, silent or in conflict: do not fix it yourself.
Then print five lines at most, and stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it.

PART 2. THE RULE AND THE COUNT AGAIN
Item 1. The suite as it stands: the number of tests, the time, none skipped.
Item 2. The rule of the reply with its tests. One commit.
Item 3. The count again, from the stored replies of LOGS/stage5e-run and LOGS/stage6c-parts alone, into LOGS/stage6c2-marks; then a second time into another folder: the two must be the same, byte for byte. Nothing is sent anywhere.
Item 4. Write LOGS/STAGE6C2_COUNT.md: P1 and P2 by the new rule; by kind of page the words under the wrong speaker and the words unsure, whole and in parts; how many lines were named twice and how many numbers were dropped in each reading; and beside them the figures by the old rule from STAGE6C_PARTS.md. Read your own count as a doubter would.
Item 5. If P1 or P2 is missed: build nothing more. Make the last commit of Part 5 for what stands, and let your final message begin with this line for the owner: Tell Cowork: the count again missed its mark. If both hold, go on without waiting.

PART 3. THE BUILD
Part 3 of STAGE_06C.md, by the plan of 6c and its review. The mend of the gate's refusal after a restart is a commit of its own before the drug-name stage (the review, point 3). A line with no speaker from the choice is as the review's point 2 says.

PART 4. THE BENCH OF CLAUDE HAIKU
Part 4 of STAGE_06C.md, by the plan of 6c and its review. Before the first call to the service: the local figures for H1 and H2, whole and in parts, by the new rule, written into LOGS/STAGE6C2_PLAN.md as numbers; and the private word check on the text to be sent, as a count, which must be 0 (the review, point 4). The results go to LOGS/stage6c2-haiku. Haiku's replies are judged by the new rule, as the local model's are.

PART 5. THE CHECKS AND THE LAST COMMIT
Part 5 of STAGE_06C.md. In item 2 the prompt folders are compared with 8c53d89 as there. In item 4 the files of the first run count among those that are not yours.

THE REPORT
LOGS/STAGE6C2_REPORT.md, as THE REPORT of STAGE_06C.md asks, with one change: after the opening for the patient comes the count again, the two marks by the new rule with the old rule's figures beside them, in place of the bench of parts.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the count again, held or missed, with the two sums; the build, with the suite's count; Claude Haiku on each job, passed or missed, with the mark missed; the calls sent, what they cost, and that nothing went to any other host and no key was read by you; the number of commits and the last hash; anything you flagged; then this line for the owner: Tell Cowork: Step 6c2 built. Do not push yet.
