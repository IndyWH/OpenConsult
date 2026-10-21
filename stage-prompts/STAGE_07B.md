OpenConsult v2.0, stage 7b: patients and earlier consultations, the background to the model

WHAT THIS IS
Stage 7a is built, pushed (4fdf7c8) and proven in the room: on 21 Oct 2026 the owner found a patient seen before, started a second consultation under them, and saw the earlier note on the live page. This is 7b, the second run of stage 7 (15.11, ruling 10): the background block of ruling 5, already in the repo as three files that no call yet carries, goes to the two calls of the pass while the switch is on, once its bench has passed (8.6; 15.11, ruling 6). The bench runs first, on two cases the owner approved word for word. If every mark holds, the block is wired in, the switch's label changes and the mark of 8.5 shows on the decision support panel. If a mark fails, nothing is wired, the files stay, and the run stops with the figures. Done when you see: the bench report; and, if it passed, the mark on the panel during a second consultation. Also in this run: one small fix from Cowork's check of 7a (the detail of 15.11 headed A small fix for 7b).
The spec is V2_SPEC.md. Read, in this order: section 15.11 whole, rulings and details, above all rulings 3, 5, 6 and 10 and the details headed The background block, The bench of 8.6 and A small fix for 7b; sections 8.3 to 8.6; section 4 (R4, R11, R12, R25); 15.7 the details headed The door and the bench; 15.8 ruling 1; 15.10 the details headed When a pass runs and The record. Then V1_LESSONS.md: the twelve (points 6 and 7), 3.2, 3.3, 3.7. Then HANDOVER.md's entry for 7a and LOGS/STAGE7A_REPORT.md, its part headed What 7b should know. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report and your bench results go here. This prompt is here.
      Every file and folder you make in LOGS has a name that begins stage7b- or STAGE7B_.
      LOGS/approved-prompts-stage7 holds Cowork's copies of the two approved texts, for your cmp.
      LOGS/stage7a-data is 7a's throwaway data folder. You may copy it whole to LOGS/stage7b-data and work on the copy; you change nothing in stage7a-data.
CASES LOGS/stage7b-cases, read only: the two cases of 15.11, ruling 6, approved by the owner on 21 Oct 2026. cases.json lists them with age, sex, the file of today's script, the file of the earlier approved note and its date. Check each file's sha256 against ruling 6 before the run; if one differs, stop and report. Nothing in this folder is changed, and nothing from it enters V2.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files. You do not start or stop vLLM: the owner does, by hand, with LOGS/stage3c_engines.sh. You install nothing there, delete nothing there and change no file there.
OLDER Every other folder in LOGS whose name begins stage3, stage4, stage5, stage6, stage7a, prompts- or PROMPTS_, and the recordings folder /home/indy/oc-recordings. Read only; the recordings folder you do not open at all. Never open any .env file in LOGS.
V1    /home/indy/Projects/consultation-ai
      Read only. Change nothing. Never read V1/.env or any file that holds a key or a token.

THE RULES
1. Check the spec with sha256sum before anything else. It must be:
   a691c13e5df56beb9e307e41054c41962e305976b1f94d631a5cd5c878a8c3df  V2_SPEC.md
   If it differs, stop and report. The spec on disk is ahead of HEAD by two things written on 21 Oct after 7a: the approval of the two cases in ruling 6, and the detail A small fix for 7b. Your first commit is the spec as it stands (15.3). Do not change a character of it.
2. Check the branch is v2 and HEAD is 4fdf7c8. git status --porcelain must print only V2_SPEC.md as modified. If anything else is changed or untracked, stop and report.
3. No git push. No sudo. No service command. Install no system software. uv may reach the package index; nothing else reaches outside this machine. The suite needs no card, no worker, no model, no microphone, no browser, no internet and no converter.
4. You never write or change a word a model reads (15.3; 15.8, ruling 1). The three background files of 7a stay byte for byte: prove with sha256sum against 48875847e78d1830e69a7bd4afccf0a975502af86dc4196189709470cdcf2fe3, 79b41aaff3a95d4ae0b8c0d00e4e82f9fd6a9ce26f47ed711cf1d487dbfc08b7 and c00401b4a0a993c4f639ea9261517ac448106c6b84838e0711a98f26ae7c2b4e, and with cmp against LOGS/approved-prompts-stage7 for the first two. The four prompts, their frames, their forms and the patient line are not touched. The block is placed where ruling 5 says and nowhere else: after the patient line, a blank line, the block, a blank line, then the frame, for the alarm call and for the assessment call, both passes of a consultation, never the note call and never the label check. The bench places it with the same function the app uses, so what is benched is what is sent.
5. The bench of 8.6 is run exactly as the 15.11 detail headed The bench of 8.6 says, with the marks of ruling 6 fixed in the plan before the run as numbers, and it is run before the block is wired into the app. The marks, read from the stored results: a chain fires the alarm when the alarm's actions are non-empty at any pass of the chain; a chain names hypoglycaemia in the top three when, at the chain's last pass, one of the first three differential names matches hypoglycaemia by matching.normalise (hypo alone does not count; low blood sugar counts); subarachnoid haemorrhage is reported the same way for case B but is not a mark. Case A: with the block, at least 12 of 13 chains both name hypoglycaemia in the top three and fire the alarm; without the block, fewer chains do both. Case B: the alarm fires in 13 of 13 chains with the block and in 13 of 13 without. If any mark fails, write the report with the figures and the final message, and stop: do not wire the block, do not change a word, do not run again to get a pass.
6. Every rule of section 4 that this stage touches is pinned by one test named with its number. No test of an earlier stage is weakened or deleted, except that the test of 8.4 from 7a is rewritten to say what is now true: the note call and the label check never get the block, the two calls of the pass get it only when the switch is on, and the stored request holds the message as sent. What a model says is never asserted in a test (5.2); the bench measures it.
7. The data folder for your own runs is LOGS/stage7b-data, never the owner's and never a test folder of an older stage. Tests write only to a temporary folder (R18). Nothing of what any recording holds goes into any file in V2.
8. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Never copy the word list, or any word from it, into V2 or into a commit message. Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
9. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
10. Size targets of section 5 (no file over 600 lines but words.py, accepted under 5.4 in 7a; no function over 80; page scripts in their own files; state logic in importable files run by tests). If a target cannot be met, report it and say why (5.4). HANDOVER.md must stay under 500 lines: move older entries to archive/HANDOVER_ARCHIVE.md.
11. Nothing from the bench goes into V2 but the figures in HANDOVER. No case text, no note text, no reply text and no result file enters the repo.
12. A product or clinical choice that the spec does not settle is not yours: stop and report it, with the choice you would make and why.
13. Do not touch V2_SPEC.md after commit 1. Cowork does not touch it while you run.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 7b: the spec with the two approved cases and the small fix
   V2_SPEC.md alone, as it stands on disk, checksum proven as rule 1 says.
Commit 2. Subject: Stage 7b: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_07B.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE7B_PLAN.md. It holds:
1. The placement: one plain function that takes a message of a call (the patient line and the frame as stage 6 builds them) and the block, and returns the message with the block between the patient line and the frame, a blank line each side; used by cds_pass.messages for both calls when the consultation's earlier_notes_shown is 1 and the block is not None (background.block_for of 7a), and by the bench. The stored request holds the message as sent. The note call and the label check are not touched. Show the exact bytes of one assessment message and one alarm message with the block, from a made note, in the plan.
2. The bench: how openconsult-bench run takes the two cases of CASES (cases.json's earlier_note and earlier_note_date; the approved text parsed by 7a's sections_of and laid out by background.lay_out, so the block is exactly what the app would send), runs each case in two arms, with the block and without, 13 chains each, --together, cuts every 4 turns and the end, on vLLM at 127.0.0.1:8172 started by the owner (prove it answers, serves the model of 3c and has thinking off, as 6b did), results under LOGS/stage7b-bench; the chains in the same way 15.7 ran them. Then the scoring of rule 5, as a plain function over the stored results with its own test on made results, and the table it writes: for each case and arm, chains that fired, chains that named hypoglycaemia in the top three, chains that did both, and for case B chains that named subarachnoid haemorrhage; the typical pass. Say what you expect the run to take (about 20 turns a case, 6 points, 2 calls, 13 chains, 2 arms, 2 cases).
3. The wiring, built only after the marks hold: the switch's second label (words.SWITCH_USES_AS_BACKGROUND, the 7a plan's words, now the sentence shown) chosen by the Start screen; the mark of 8.5 on the decision support panel of the live page while the block is being sent, rendered by panels.js from the state, its words in the one file; the test of 8.4 rewritten as rule 6 says; the stored request proven to hold the block in a whole-consultation test with made doors.
4. The small fix: the app joins the Stop thread at shutdown; the tests of test_stop.py close the app before the database; one test that no thread of the app outlives it.
5. Every new sentence shown to the user, in the one file of 15.6.
6. The room run you will leave for the owner, in his hands' order: vLLM up, the app started, the patient of 20 Oct, New consultation, the switch on with its new label, Start, the mark on the decision support panel, a short consultation, Stop, approve; then the model record on the review page showing that the pass read the background.
7. The commits you will make, in order, and the HANDOVER entry you will write, which records the owner's room run of 7a (21 Oct 2026, his words: Previous note appeared on the right hand side. Good note. Good diarisation.) and the bench's figures.
8. The tests you will add, each with what it pins. Expected: R4, R11, R12, R25, rulings 3, 5, 6 (the scoring on made results) and 10 of 15.11, 8.4 as rewritten, 8.5, D24, V1_LESSONS 3.2 (the stale list of names still before the transcript, the block before both), the small fix.
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. BUILD, THE BENCH FIRST
1. The placement function, background.block_for wired to the bench only, the bench's two arms and the scoring, in one commit, with the suite green. No change to what the app sends yet.
2. The bench, with the owner's vLLM up at 8172. No app and no speech worker of yours runs meanwhile. Its output to LOGS/stage7b-bench.log. Then the scoring. Then the marks of rule 5 beside their numbers. If every mark holds, go on. If any fails: the report with the figures and the final message, and stop.
3. Then, one commit per item: the wiring in cds_pass with the switch, the label and the mark; the small fix; the documents.
4. Prove on this machine on LOGS/stage7b-data (a copy of stage7a-data) with the made doors of the suite that a second consultation under a patient with an approved note and the switch on stores requests that hold the block for the alarm and the assessment and not for the note or the label check, and that with the switch off no request holds it.
5. Before the last commit: git status --porcelain is empty but your commits; nothing private in the added lines (rule 8, and no home path, no ENG path, no machine name); the suite green three times with no thread exception warning; HANDOVER under 500 lines; CLAUDE.md under 100 lines; the README says what this version can now do.

THE REPORT
Write LOGS/STAGE7B_REPORT.md: the spec's checksum as given and committed; the three files' hashes proven; the bench: the four files' checksums as ruling 6 gives them, the engine and its version, the table of item 2 for each case and arm, the marks each held or missed, the typical pass, and whether the block is wired; the placement, with the exact bytes of one message of each call from the proof; every new sentence shown to the user; the tests, each with what it pins; the commits with their hashes; the size targets met or not; the room run steps for the owner, in his hands' order; what the stage has made untrue in any document; and what stage 8 should know. Plain words. No case text and no reply text in the report beyond one differential list and one alarm from case A if a mark failed, with its chain and arm.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the three files' hashes proven; the marks of the bench, each held or missed, and whether the block is wired; the number of commits and the last hash; that the private word check printed nothing before every commit; then this line for the owner: Tell Cowork: Stage 7b built. Do not push yet.
