OpenConsult v2.0, stage 8c: the what-the-model-saw view, with the timeline, and two small fixes

WHAT THIS IS
Stage 8b is built, pushed (0d28f63) and proven in the room on 2 Nov 2026. This is 8c, the view run of 15.12, ruling 11, settled by ruling 28: one read-only page per consultation listing every model call in time order, each opening to what went in, marked by source, and what came back word for word; with a timeline of the calls at its head and the averages per kind of call, so that a slow pass is seen at a glance. Two small fixes ride with it (ruling 28): the Which speaker was you? page must change after the answer, and the retention test's wait for a slow runner. No bench, no mark: the view reads the record and writes nothing but its page. No word a model reads changes. Done when you see: the view of a consultation of the owner's, with its timeline, and one call opened to its parts.
The spec is V2_SPEC.md. Read, in this order: 15.12 rulings 11 and 28; the 15.12 details headed The record (8a), The two letter frames and The passages and the search; 15.8 ruling 1; 15.10 the details headed When a pass runs and The record; 15.11 rulings 2 and 5 (the details a consultation ran with; the background block); section 4 (R2, R11, R15, R18, R20, R25); 5.1 and 5.2; 7.3 rule 4. Then V1_LESSONS.md: the twelve, 3.4. Then HANDOVER.md's entries for 8a and 8b and LOGS/STAGE8B_REPORT.md, its part headed What the view run of ruling 11 should know. Where this prompt and the spec differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients. Every consultation is acted.

MODEL
This runs on Fable 5.1 at high effort. Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log and your report go here. This prompt is here.
      Every file and folder you make in LOGS has a name that begins stage8c- or STAGE8C_.
      LOGS/stage8b-data is 8b's throwaway data folder: 8a's consultations and letters, the 47 documents, the proof's guideline answers. You may copy it whole to LOGS/stage8c-data and work on the copy; you change nothing in stage8b-data. The 47 documents' text is in it: no word of a passage, a note, a letter or a reply enters V2 or any file you write for the report, counts only.
ENG   /mnt/fastdata/openconsult-engine-bench
      Not used in this run. You start or stop no engine. The proof needs no model: the view reads stored calls.
OLDER Every other folder in LOGS whose name begins stage3, stage4, stage5, stage6, stage7, stage8a, stage8b, prompts- or PROMPTS_, and the recordings folder /home/indy/oc-recordings. Read only; the recordings folder you do not open at all. Never open any .env file in LOGS.
V1    /home/indy/Projects/consultation-ai
      Read only. Change nothing. Never read V1/.env or any file that holds a key or a token. v1 has no such view; nothing there is the reference.

THE RULES
1. Check the spec with sha256sum before anything else. It must be:
   87d90be3255638dbe354d05d554f5487af91433a161273a4d9c8d4d1f445a412  V2_SPEC.md
   If it differs, stop and report. The spec on disk is ahead of HEAD by design: HEAD holds 9dbc55ec and the disk holds 8b marked done on 2 Nov and ruling 28. Your first commit is the spec as it stands (15.3; 15.5, ruling 3). Do not change a character of it.
2. Check the branch is v2 and HEAD is 0d28f63. git status --porcelain must print only V2_SPEC.md as modified. If anything else is changed or untracked, stop and report.
3. No git push. No sudo. No service command. Install no system software. uv may reach the package index; nothing else reaches outside this machine. The suite needs no card, no worker, no model, no microphone, no browser and no internet.
4. You never write or change a word a model reads. The prompt, frame, form and withheld files under openconsult/prompts are not touched: prove at the end that every file there has the bytes it had at 0d28f63 (git diff 0d28f63 -- openconsult/prompts prints nothing). The view shows a prompt by its name and hash only, never its text (ruling 28).
5. The view reads the record and writes nothing but its page (R2: nothing it shows is a draft of anything; R18: no test writes outside a temporary folder). It is read only: no control on it changes a row. Its parts are read back from the stored request by the same code that builds each message, for the calls of stages 3 to 7, and from the parts stored by name for the three calls of stage 8 (ruling 11); a stored request the reader cannot take apart is shown whole, marked as not taken apart, with the reason, never guessed at. A test per call kind shows the reader giving back the parts the builder put in, on made calls.
6. Every rule of section 4 this run touches is pinned by one test named with its number. No test of an earlier stage is weakened or deleted; the retention test gains a longer wait and nothing else (ruling 28). What a model says is never asserted in a test (5.2).
7. Before each commit, run the private word check on the staged files. It must print nothing:
   git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
   If it prints a line, stop and report. Never copy the word list, or any word from it, into V2 or into a commit message. Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
8. Each commit: one logical change, the suite green before it, the why in the message. Each commit message ends with this line, after one empty line:
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   That is the only address allowed in a commit message.
9. Size targets of section 5 (no file over 600 lines, no function over 80, page scripts in their own files, state logic in importable files run by tests). If a target cannot be met, report it and say why (5.4). HANDOVER.md must stay under 500 lines; CLAUDE.md under 100.
10. A product or clinical choice that the spec does not settle is not yours: stop and report it, with the choice you would make and why.
11. Do not touch V2_SPEC.md after commit 1. Cowork does not touch it while you run.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 8c: the spec with 8b done and ruling 28
   V2_SPEC.md alone, as it stands on disk, checksum proven as rule 1 says.
Commit 2. Subject: Stage 8c: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_08C.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE8C_PLAN.md. It holds:
1. How every call of a consultation is found in the record, by kind: the pass rows (alarm_call_id, assessment_call_id), the label check, the note, the referral list, the letters, the guideline answers, and any other row that references model_call; the order by model_call.at; what a call that no row references (if any exists) is shown as.
2. The reader per call kind: which function builds the message, and how its parts are read back (the patient line, the background block, the frame's fixed words, the transcript as sent, the note lines as sent, the passages with their sources, the query); the three stage 8 calls from their named parts; the whole-request fallback of rule 5.
3. The page: where it is reached from (the review page and the patient's page, one link each, as ruling 28 says); its head, the timeline (every call drawn from Start to final against the clock, the passes marked, a pass longer than twice the consultation's typical pass marked), the averages per kind of call, and the figures of the consultation.final audit line beside them; its list (job, model and version, seconds, outcome, each opening to the parts marked by source and the reply word for word, the prompt by name and hash); read only; every new sentence in the one file of 15.6; the page script in its own file. Which figures are computed in an importable file run by tests (the averages, the typical pass, the long-pass mark), and the exact rule for typical and for long.
4. The speaker page fix (ruling 28): what the page shows after the answer, how the page learns the answer was taken (the state the page already polls), that the choices go, and its test (an answer taken; a second post refused; the page after the answer holds no choice).
5. The retention test's longer wait: which constant the other stop tests use, and that nothing else of the test changes.
6. The proof on LOGS/stage8c-data, counts only: a consultation of 8a's with its note and letters, and one of 8b's proof with guideline answers, each opening its view with every call listed in time order, each call's parts read back equal to the stored request (the parts joined give the request byte for byte, for the kinds the reader takes apart), the timeline's figures equal to a recount from the rows by plain code.
7. The room run you will leave for the owner, in his hands' order: open the app; a patient's page; a consultation of 2 Nov; the link to its view; the timeline and the averages; open the assessment call of one pass and the guideline call, see the parts by source and the reply; open the note call; back to the review page; then one consultation stopped with the stand-in or by himself, to see the speaker page change after the answer.
8. The commits you will make, in order, and the HANDOVER entry you will write.
9. The tests you will add, each with what it pins. Expected: R2 and R18 (read only; nothing written), R11 (the patient line read back from every call that carries it), R15 (the speaker page after the answer), R20 (model and version shown for every call), R25 (the background block read back only from the two pass calls), ruling 11 (the parts by name for the three stage 8 calls), ruling 28 (the timeline's figures from an importable file; the long-pass rule; the longer wait), 15.8 ruling 1 (no prompt text on the page).
Then stop. Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. BUILD
1. In this order: the readers per call kind, with their tests; the figures of the timeline in an importable file, with their tests; the page and its script, with its tests; the speaker page fix; the retention test's wait; the documents. One commit per item.
2. Prove on this machine on LOGS/stage8c-data as PART 2 item 6 says. Nothing of what the consultations, notes, letters, passages or replies hold goes into any file in V2 or into the report: counts, seconds and booleans only.
3. Before the last commit: git status --porcelain is empty but your commits; nothing private in the added lines (rule 7, and no home path, no ENG path, no machine name, no publisher name); git diff 0d28f63 -- openconsult/prompts prints nothing; the suite green three times; HANDOVER under 500 lines; CLAUDE.md under 100 lines; the README says what this version can now do.

THE REPORT
Write LOGS/STAGE8C_REPORT.md: the spec's checksum as given and committed; the proof that no prompt file changed; how each call kind is found and read back; the timeline's rules (typical, long) with their sources; the proof's counts; every new sentence shown to the user; the tests, each with what it pins; the commits with their hashes; the size targets met or not; the room run steps for the owner, in his hands' order; what the stage has made untrue in any document; and what the letters session of ruling 20 should know. Plain words.

FINAL MESSAGE
Eight lines at most: the spec's checksum as given and committed; that no prompt file changed, proven; the proof's counts in one line; the number of commits and the last hash; the suite's count; that the private word check printed nothing before every commit; then this line for the owner: Tell Cowork: Stage 8c built. Do not push yet.
