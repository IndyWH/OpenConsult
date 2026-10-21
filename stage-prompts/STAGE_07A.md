OpenConsult v2.0, stage 7a: patients and earlier consultations, the patient side

WHAT THIS IS
Stage 6 is built, pushed (5783ea9) and proven in the room: on 20 Oct 2026 the owner ran one acted consultation from Start to an approved note. This is 7a, the first run of stage 7 (15.11, ruling 10): the Patients page with the list, the search and the patient's number; the patient's page with corrections that never rewrite an earlier consultation; the Start screen for a patient seen before, with the switch; the earlier-notes panel on the live page; the files of the background block and the code that fills them, built and tested, with no call carrying the block; retention and the Opus recording; one delete that really deletes; the red mark and the alarms in the warnings pane. Done when you see: the owner finds a patient seen before, starts a second consultation under them, and sees the earlier note on the live page. The background to the model is 7b, after its bench, and is not built here.
The spec is V2_SPEC.md. Read, in this order: section 15.11 whole, rulings and details; section 8 whole; 3.2 items 11 and 12; section 4 (R1, R2, R11, R15, R17, R18, R25); 6.3; 7.3; 15.10 the details headed The record, The live page, Stop in order and The review page; 15.8 ruling 1. Then V1_LESSONS.md: the twelve, 3.13, 5, 10.3, 10.4, 10.5. Then HANDOVER.md's entries for 6a and 6b and LOGS/STAGE6B_REPORT.md, its part headed What stage 7 should know. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log and your report go here. This prompt is here.
      Every file and folder you make in LOGS has a name that begins stage7a- or STAGE7A_.
      LOGS/approved-prompts-stage7/background.frame.txt and background.note.txt are Cowork's copies of the two approved texts, for your cmp. The spec is the source; if a copy and the spec differ, stop and report.
      LOGS/stage6b-data is 6b's throwaway data folder, with consultations, notes and recordings from its proof. You may copy it whole to LOGS/stage7a-data and work on the copy; you change nothing in stage6b-data.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files. You do not start or stop vLLM: the owner does, by hand, with LOGS/stage3c_engines.sh. You install nothing there, delete nothing there and change no file there.
OLDER Every other folder in LOGS whose name begins stage3, stage4, stage5, stage6, prompts- or PROMPTS_, and the recordings folder /home/indy/oc-recordings. Read only; the recordings folder you do not open at all. Never open any .env file in LOGS.
V1    /home/indy/Projects/consultation-ai
      Read only. Change nothing. Never read V1/.env or any file that holds a key or a token. Its app/retention.py and the void, unvoid and purge functions of app/consultations.py are the reference for retention and deletion; the code is rewritten to the spec, not copied (6.1, 6.5): v2 has one delete and no void.

THE RULES
1. Check the spec with sha256sum before anything else. It must be:
   9c4b54600409405f47769589f416c8d24d89df8f593c17e9415067ce4938cc5d  V2_SPEC.md
   If it differs, stop and report. The spec on disk is ahead of HEAD by design: HEAD holds 3c1ac7e1 and the disk holds the stage 6 bench ruling of 20 Oct, the stage 4 rulings folded on 21 Oct and the stage 7 brainstorm of 21 Oct. Your first commit is the spec as it stands (15.3; 15.5, ruling 3). Do not change a character of it.
2. Check the branch is v2 and HEAD is 5783ea9. git status --porcelain must print only V2_SPEC.md as modified. If anything else is changed or untracked, stop and report.
3. No git push. No sudo. No service command. Install no system software. uv may reach the package index; nothing else reaches outside this machine. The suite needs no card, no worker, no model, no microphone, no browser, no internet and no converter.
4. You never write or change a word a model reads except by copying the two blocks of 15.11, ruling 5 exactly (15.3; 15.8, ruling 1). They are openconsult/prompts/background.frame.txt and background.note.txt: each block followed by one line break, nothing else. Prove each with sha256sum against 48875847e78d1830e69a7bd4afccf0a975502af86dc4196189709470cdcf2fe3 and 79b41aaff3a95d4ae0b8c0d00e4e82f9fd6a9ce26f47ed711cf1d487dbfc08b7, and with cmp against the copies in LOGS/approved-prompts-stage7. In 7a no model call carries the block: the function that builds it exists and is tested on made notes, and cds_pass does not call it. The four prompts already in the app, their frames and their forms are not touched. The patient line is not touched.
5. The conversion to Opus needs a converter. Name in the plan how it ships on the three systems (a Python package that carries ffmpeg, found by uv, or the system's own ffmpeg on the path), and build the room check's report of it. On this machine use what is present; install nothing with sudo. Tests use a made converter and a one-second made WAV, never a real recording (R18).
6. Every rule of section 4 that this stage touches is pinned by one test named with its number. No test of an earlier stage is weakened or deleted. What a model says is never asserted in a test (5.2).
7. The data folder for your own runs is LOGS/stage7a-data, never the owner's and never a test folder of an older stage. Tests write only to a temporary folder (R18). Nothing of what any recording holds goes into any file in V2.
8. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Never copy the word list, or any word from it, into V2 or into a commit message. Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
9. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
10. Size targets of section 5 (no file over 600 lines, no function over 80, page scripts in their own files, state logic in importable files run by tests). If a target cannot be met, report it and say why (5.4). HANDOVER.md must stay under 500 lines: move older entries to archive/HANDOVER_ARCHIVE.md.
11. A product or clinical choice that the spec does not settle is not yours: stop and report it, with the choice you would make and why.
12. Do not touch V2_SPEC.md after commit 1. Cowork does not touch it while you run.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 7a: the spec as the brainstorm of 21 Oct left it
   V2_SPEC.md alone, as it stands on disk, checksum proven as rule 1 says.
Commit 2. Subject: Stage 7a: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_07A.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE7A_PLAN.md. It holds:
1. The new schema version, column by column, from the detail headed The record: the patient's current details and patient_change; on the consultation the details it ran with, the switch's setting, the recording's format, the date its audio went, the earlier notes shown at Start; audio_deletion; the deletion audit row. A version 5 folder comes forward with its rows, the details it ran with filled from the patient as it stands.
2. The Patients page as the home page, in the order of the detail: the waiting-for-review rows at the top (the stage 6 list moved), the search box, the list with its five columns, New patient. The search request and what it matches (part of a name with case and accents folded, a date of birth, the number exactly). The acted-only statement.
3. The patient's page: the three Edit controls with their audit, the consultations list, the details a consultation ran with and the one line when they changed later, Delete patient disabled with its reason while a consultation remains, New consultation.
4. The Start screen for a patient seen before: the list of approved notes by date, the switch on by default with its 7a label, its setting stored; no list and no switch for a patient with no approved note; the new-patient Start unchanged.
5. The earlier-notes panel on the live page: where it sits (never the zone that holds Stop and the alarm acknowledgement), its folded line per note, up to three, the approved text opened in place with citations stripped, hidden when the switch is off; its page script in its own file.
6. The two files of ruling 5 and the function that builds the block (the last three approved notes before this consultation, deleted ones gone, the date in words, none for an empty section, citations stripped, the cut with its line and BACKGROUND_NOTE_MAX_WORDS set from the longest approved note of 5c part two with a margin), tested on made notes, called by nothing in the pass.
7. Retention: the setting audio_retention_days (default 90; 0 keeps), the sweep at start-up and every 24 hours in the app's own loop, never during a Stop, the audit line per sweep that deleted anything, the date written to the consultation, the player's line of stage 6 then shown. Conversion: the job after Stop's final step, Ogg Opus mono 32 kbps with the voice setting, the duration check with its tolerance named, the WAV removed only after the check, a failure leaving the WAV with its reason shown; how the converter ships (rule 5) and the room check's line for it; Start still offered without it.
8. Deleting: the one function (rows in one transaction, then the file, the audit line with counts and no words; a live consultation refused), Delete patient, the question asked once with the name and the date, and the start-up sweep of orphans.
9. The red mark (the matching function on made text with matching.normalise, whole-word; the mark on the live page and beside the assessment at review; the press to the pop-up) and the alarm lines in the warnings pane (time, state, the press that plays from the last line the pass had read), with the two counts on the Approve control.
10. Every new sentence shown to the user, in the one file of 15.6.
11. The room run you will leave for the owner, in his hands' order: open the app, find consultation 1's patient of 20 Oct in the list and by search, open the patient's page, correct nothing, New consultation, see the earlier note listed and the switch on, Start, read the earlier note in the panel, Stop, approve; then the consultation's page with the Opus file playing from a pressed line; then Delete on a throwaway consultation of his own choosing, and the Log page's lines for the approval and the deletion.
12. The commits you will make, in order, and the HANDOVER entry you will write.
13. The tests you will add, each with what it pins. Expected: R1, R2, R11, R15, R17, R18, R25, rulings 1 to 5 and 7 to 9 of 15.11, 8.3, 8.4 (the note call never gets the block, and in 7a no call does), D22, D23, D25, D44, V1_LESSONS 10.3, 10.4, 10.5.
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. BUILD
1. One commit per item, in this order: the tables; the Patients page with the list and the search; the patient's page with corrections and the details a consultation keeps; the Start screen for a patient seen before and the panel; the two files of ruling 5 and the block function (rule 4, hashes and cmp proven); retention and the conversion; deleting; the red mark and the alarms at review; the documents.
2. Prove on this machine on LOGS/stage7a-data (a copy of stage6b-data brought forward) that a patient with an approved note shows the list and the switch at Start and the panel on the live page; that a second consultation under that patient, run against the made doors of the suite or the owner's vLLM if he has it up, stores the details it ran with and the switch's setting; that a correction to the patient's date of birth leaves the earlier consultation's page showing the old one with the line; that a made WAV converts to Opus and plays from a pressed line on the review page; that the sweep with the setting at 0 deletes nothing and with the setting at 1 day deletes a recording older than that and writes the audit line; that Delete removes every row and the file and leaves the audit line with counts and no words; that the red mark appears on a made pass whose alarm names a differential on the list. Nothing of what those recordings hold goes into any file in V2.
3. Before the last commit: git status --porcelain is empty but your commits; nothing private in the added lines (rule 8, and no home path, no ENG path, no machine name); the suite green three times; HANDOVER under 500 lines; CLAUDE.md under 100 lines with the new commands; the README says what this version can now do.

THE REPORT
Write LOGS/STAGE7A_REPORT.md: the spec's checksum as given and committed; the two files' hashes and cmp proven and the proof that no call carries the block; the schema version and its tables; the constants with their sources (BACKGROUND_NOTE_MAX_WORDS, the duration tolerance, the sweep interval); how the converter ships and what the room check says of it on this machine; every new sentence shown to the user; the tests, each with what it pins; the commits with their hashes; the size targets met or not; the room run steps for the owner, in his hands' order; what the stage has made untrue in any document; and what 7b should know, above all where cds_pass will place the block and where the switch's second label goes. Plain words.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the two files' hashes proven and that no call carries the block; the schema version; how the converter ships; the number of commits and the last hash; that the private word check printed nothing before every commit; then this line for the owner: Tell Cowork: Stage 7a built. Do not push yet.
