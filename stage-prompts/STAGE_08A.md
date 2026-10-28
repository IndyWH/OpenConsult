OpenConsult v2.0, stage 8a: the referral letters

WHAT THIS IS
Stage 7 is built, pushed (19ea8e0) and proven in the room on 21 and 25 Oct 2026. This is 8a, the first run of stage 8 (15.12, ruling 13): the referral list on the review page after Approve, the letter drafted from the approved note only, the letter check in code, the letters' record, and the bench of the two new prompts on four approved notes, run first; nothing is wired until its marks hold, as 7b did. Done when you see: one letter drafted from an approved note, the row of 15.4. The guideline panel is 8b and is not built here.
The spec is V2_SPEC.md. Read, in this order: section 15.12 whole, rulings 1 to 4, 8, 10, 11 and 13 and every detail; 3.1 item 7; section 4 (R2, R4, R5, R11, R15, R18, R20, R30, R31); 6.1 and 6.3; 15.8 ruling 1; 15.10 rulings 4 and 11 and the detail headed The review page; 15.11 rulings 2 and 5 (the details a consultation ran with; the background block, which the letter calls never get, D24). Then V1_LESSONS.md: the twelve, 3.4, 3.7, 6.2, 13. Then HANDOVER.md's entries for 7a and 7b and LOGS/STAGE7B_REPORT.md, its part headed What stage 8 should know. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log and your report go here. This prompt is here.
      Every file and folder you make in LOGS has a name that begins stage8a- or STAGE8A_.
      LOGS/approved-prompts-stage8/letter.prompt.txt and referrals.prompt.txt are Cowork's copies of the two approved texts, for your cmp. The spec is the source; if a copy and the spec differ, stop and report. guideline.prompt.txt in the same folder is 8b's and is not touched.
      LOGS/stage8a-cases holds the four approved notes of the bench (A and B by reference to stage7b-cases, C and D in the folder) and cases.json. Read only. No word of them enters V2.
      LOGS/stage7b-data is 7b's throwaway data folder, with consultations, approved notes and recordings from its proof. You may copy it whole to LOGS/stage8a-data and work on the copy; you change nothing in stage7b-data.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files. You do not start or stop vLLM: the owner does, by hand, with LOGS/stage3c_engines.sh. You install nothing there, delete nothing there and change no file there.
OLDER Every other folder in LOGS whose name begins stage3, stage4, stage5, stage6, stage7, prompts- or PROMPTS_, and the recordings folder /home/indy/oc-recordings. Read only; the recordings folder you do not open at all. Never open any .env file in LOGS.
V1    /home/indy/Projects/consultation-ai
      Read only. Change nothing. Never read V1/.env or any file that holds a key or a token. Its app/letters.py (the numbered note, the citable lines, the per-sentence check, the assembled letter) and the letters part of app/static/review.html are the reference; the code is rewritten to the spec, not copied (6.1, 6.5): v2 has one call for the list in two kinds, the title in the salutation, the refusal, and SQLite.

THE RULES
1. Check the spec with sha256sum before anything else. It must be:
   c5833101645c09700a5748c74a847df233f536efeaa7b18c5b7b02d2ab8d288d  V2_SPEC.md
   If it differs, stop and report. The spec on disk is ahead of HEAD by design: HEAD holds 89943dd7 and the disk holds stage 7 marked done on 25 Oct and the stage 8 brainstorm of 28 Oct. Your first commit is the spec as it stands (15.3; 15.5, ruling 3). Do not change a character of it.
2. Check the branch is v2 and HEAD is 19ea8e0. git status --porcelain must print only V2_SPEC.md as modified. If anything else is changed or untracked, stop and report.
3. No git push. No sudo. No service command. Install no system software. uv may reach the package index; nothing else reaches outside this machine. The suite needs no card, no worker, no model, no microphone, no browser and no internet.
4. You never write or change a word a model reads except by copying the two prompts of 15.12, rulings 3 and 8 exactly. They are openconsult/prompts/letter.prompt.txt and referrals.prompt.txt: each block followed by one line break, nothing else. Prove each with sha256sum against b2e5e816185b0cc249feb69f7f328749c3f9e3b615ef1556df5b3c4ec20f4624 and 5eab5bb56333fd5c4643dd482caa04afc9cb8a2c2ae922d69192ecaed5632962, and with cmp against the copies in LOGS/approved-prompts-stage8. The two frames of the detail headed The two letter frames are fixed words in two frame files, built as the detail says and nowhere else; put their exact bytes in the plan. The patient line opens both messages (R11); the background block never reaches either call (D24). The six prompts and frames already in the app are not touched.
5. The bench runs first, on the owner's vLLM, which he starts by hand before he approves the plan. The marks are the numbers of 15.12, ruling 10, fixed in the plan before the run and judged by code from the stored results alone: no letter refused, 13 of 13 per case; the placeholder absent in at least 12 of 13; no citation into Assessment and no number outside the cited lines, 13 of 13; an expectation sentence only in the letters of the notes that have the line (B, C, D) and in none of A's; the stated referral found with its plan line 13 of 13 (C: gastroenterology; D: ENT and dermatology, two items); A and B give an empty stated list 13 of 13. If a mark fails, stop with nothing wired: commit the bench and the scoring, hold the rest as a patch in LOGS as 7b did, write the report, and end with the line for the owner. Do not loosen a mark and do not change a word of a prompt.
6. The letter check is code, as 15.12 ruling 4 and its detail say, tested on made letters and made notes: every rule of the check has a test that shows it catching the thing it is for. What a model says is never asserted in a test (5.2).
7. Every rule of section 4 that this stage touches is pinned by one test named with its number. No test of an earlier stage is weakened or deleted.
8. The data folder for your own runs is LOGS/stage8a-data, never the owner's and never a test folder of an older stage. Tests write only to a temporary folder (R18). Nothing of what any note, letter or reply holds goes into any file in V2.
9. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Never copy the word list, or any word from it, into V2 or into a commit message. Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
10. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
11. Size targets of section 5 (no file over 600 lines, no function over 80, page scripts in their own files, state logic in importable files run by tests). If a target cannot be met, report it and say why (5.4). HANDOVER.md must stay under 500 lines: move older entries to archive/HANDOVER_ARCHIVE.md.
12. A product or clinical choice that the spec does not settle is not yours: stop and report it, with the choice you would make and why.
13. Do not touch V2_SPEC.md after commit 1. Cowork does not touch it while you run.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 8a: the spec as the brainstorm of 28 Oct left it
   V2_SPEC.md alone, as it stands on disk, checksum proven as rule 1 says.
Commit 2. Subject: Stage 8a: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_08A.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE8A_PLAN.md. It holds:
1. The new schema version, column by column, from the detail headed The record: referral_item, letter, letter_edit, letter_approval; the data folder brought forward with its rows.
2. The two frame files, byte for byte, and the function that numbers the approved text of note_approval (headings numbered and never citable; the Assessment lines masked for the letter call and shown for the list call; the numbers the same in both).
3. The list call: when it runs (once, at the first opening of the review page after Approve; again after a new approval), the form it asks for, how code sorts the items into stated, suggested and demoted by the cited plan line and the specialty's word, the item name a specialty, and what is stored.
4. The letter call and the check: the form; the per-sentence check with each rule named; LETTER_GROUNDED_HALF beside CITATION_HALF; the placeholder; the refusal and its reason; the salutation, the Re line and the sign-off by code, with where each word comes from; the counts stored and shown.
5. The page: the Referral letters section of the review page in the order of the detail; the letter's own page; every new sentence shown to the user, in the one file of 15.6; the page script in its own file.
6. The bench: the command, the four cases from LOGS/stage8a-cases, 13 chains, on vLLM through the door with the app's own functions (the same numbering, the same frames, the same check), the result folders, the scoring command from the stored results alone, and the marks as numbers (rule 5). The scoring tested on made results.
7. The room run you will leave for the owner, in his hands' order: open the app, find the consultation of 20 Oct with its approved note, see the Referral letters section with its items in two kinds, change a title, press Draft the letter, read the letter with its counts, edit one paragraph, Approve, copy it; then name a specialty on the same note and draft a second letter; then the Log page's lines.
8. The commits you will make, in order, and the HANDOVER entry you will write.
9. The tests you will add, each with what it pins. Expected: R2, R4, R5, R11, R15, R18, R20, R30, rulings 1, 2, 4 and 8 of 15.12 and the detail of the check, D24 (no block in a letter call), V1_LESSONS 3.4 (the patient line on both calls).
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. BUILD
1. In this order: the tables; the two prompt files (rule 4, hashes and cmp proven) and the frames and the numbering; the list call and the sorting by code; the letter call and the check; the bench command and the scoring; THEN THE BENCH RUN, and stop if a mark fails (rule 5); then the page; then the documents. One commit per item.
2. Prove on this machine on LOGS/stage8a-data (a copy of stage7b-data brought forward) that the review page of a consultation with an approved note shows the Referral letters section after Approve and not before; that a letter drafted against the owner's vLLM stores the note lines sent, the body as the model gave it, the body as the check left it and the counts; that a made letter with a sentence citing an Assessment line, a sentence with a number not in its lines, and a planned test written as a result gets the placeholder in each place; that a made letter with fewer than half its sentences grounded is refused with the reason; that Approve makes the letter read-only and the copy text is the letter alone; that name a specialty drafts without a list call. Nothing of what those notes or letters hold goes into any file in V2.
3. Before the last commit: git status --porcelain is empty but your commits; nothing private in the added lines (rule 9, and no home path, no ENG path, no machine name); the suite green three times; HANDOVER under 500 lines; CLAUDE.md under 100 lines with the new commands; the README says what this version can now do.

THE REPORT
Write LOGS/STAGE8A_REPORT.md: the spec's checksum as given and committed; the two prompts' hashes and cmp proven; the two frames byte for byte; the schema version and its tables; the bench's table (per case: chains, refused, placeholders, Assessment citations, numbers outside the lines, expectation sentences, stated items found with their lines) and each mark held or missed, with the command that recomputes it from the stored results; one letter per case, word for word, for the owner to read (in the report, which is private); the constants with their sources; every new sentence shown to the user; the tests, each with what it pins; the commits with their hashes; the size targets met or not; the room run steps for the owner, in his hands' order; what the stage has made untrue in any document; and what 8b should know, above all how the review page is arranged now, how the model_call row and the named parts are stored (ruling 11), and where the embedding worker of the bench kit sits for 8b to bring into the app. Plain words.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; the two prompts' hashes proven; the schema version; the bench's marks, held or missed, as numbers; the number of commits and the last hash; that the private word check printed nothing before every commit; then this line for the owner: Tell Cowork: Stage 8a built. Do not push yet.
