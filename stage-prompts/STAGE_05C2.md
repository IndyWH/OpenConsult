STAGE 5c, PART TWO, of OpenConsult v2.0: what is done with the transcripts, and the full rehearsal

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 5 is about speech. It is built in five steps, 5a to 5e. This is 5c, the third, and 5c is built in two runs.
This is part two. Part one built the replay bench: a banked recording goes through each speech choice as if it
were live, and code scores the transcript against the script. It was rehearsed, and its 18 results are stored.
Part two measures what can be done with a transcript. From the patient's side it asks three things.
Who spoke each line, when the speech choice is not sure: can the doctor's own voice tell, and can the language model tell from the words?
Which drug names on the page are in doubt, so that the doctor is shown a mark and never a silent correction?
What reaches the note: which key facts of a consultation are lost or changed on the way from the sound to the note?
Part two answers them on the stored transcripts of part one, as a rehearsal. No figure from it counts.
It opens with two fixes that part one found: one in the Nemotron worker and one in the scoring of the wait.
Nothing of part two is built into the app. No page, no consultation, no recording from a microphone and no Alba yet.
The spec is V2_SPEC.md. Stage 5 is section 15.9 of it. Read that section first:
rulings 1 to 22, the details of the stage, of 5a, of 5b and of part one of 5c, and then the details of part two of 5c.
Build what the details of part two say. Each ruling it rests on is named there.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report, your working data folder and the rehearsal's results go here.
      This prompt is here.
P1    Six folders in LOGS that part one left: stage5c1-recordings, stage5c1-rehearsal, stage5c1-voices,
      stage5c1-proof, stage5c1-rehearsal-tables-after-fix and stage5c1-data.
      Read only. Part two reads and copies from the first five and writes nothing in any of the six. Delete nothing there.
      LOGS/stage5c1-data holds a copy of the owner's two keys. Do not open LOGS/stage5c1-data/.env.
      Do not use LOGS/stage5c1-data as your data folder: part two builds its own.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
      Never read V1/.env or any other file that holds a key or a token.
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. The record of v1's benches. Change nothing there. Run nothing there.
The folder of old recordings, recordings-backup-2026-10-04, is not needed in part two. Open nothing in it.

WHAT COWORK HAS LEFT FOR YOU IN LOGS
LOGS/stage5c-prompts/label_check.prompt.txt
   sha256 262d1ef805d4b7a27a1823a71dd649b78d2cdb84da5ce570c8d7cd3d91de557a   (ruling 17)
LOGS/stage5c-prompts/drug_name.prompt.txt
   sha256 89fcdc35d7a6ea4ddf7cd9e1b7e96c3118fd7810013e857bd83f6bc7c3939963   (ruling 18)
LOGS/stage5c-prompts/note.prompt.txt
   sha256 adf0b5e73963ae198b1d4df55aedbfd92aec0c0f69117c459e78a9d3ec31f2e8   (ruling 19)
   The three prompts, each with one line break after its last line. The same texts stand in the spec
   between two fence lines, under their rulings. The note prompt holds characters that are not plain ASCII:
   copy bytes, never retype.
LOGS/stage5c-cases/key_facts.json
   sha256 95a6cf260effe22baefd55e3b8c3d09194ef658602e33d9cc712764316bfbdf4
   The key facts for scripts 01, 13, 15 and 19 (ruling 20). Its first entry says how to read it.
   Use it as it is. If you find a fact wrong against its script, report it. Do not correct it.
   It names the drugs of script 19, so it stays in LOGS and never goes into V2.
   The suite uses a made-up file of the same form.
LOGS/stage5c-cases/doctor_minute.txt
   sha256 7c64ad4781cf3e54754c1dcf1c99527f3b2e1389c786c4012bc202b74418e786
   The text for the minute of the doctor's voice alone (the details of part two: The voice method). 159 words.
   No model reads it. A machine voice reads it aloud, and the voice method learns the voice from that sound.
LOGS/stage5c-cases/speech_marks.json
   sha256 1c21012b3ef867a0290079d5cd8583fda7a5a13231e060c7f04f796638e54360
   As in part one, unchanged. It stays in LOGS.
LOGS/stage5c-cases/part_one_files.sha256
   sha256 c9264130a0714abe29c6265179d80698eb23c59da23aeddf1a5e158ff0388c3e
   The checksums of 35 files that part one left in P1: the recordings with their list, the voice,
   the 18 results of the rehearsal, the 4 results of the short proof, and the two files of the tables.
LOGS/stage4-scripts/19_medication_review_uk.md
   sha256 1388c5fd6d4fe1c6f058903dceceda4e2bf455e9a7f37fc6a5c6035ce34024f6
   Script 19. It is private until the owner publishes it. It never goes into V2.
Scripts 01, 13 and 15 are public, in V2/engine-bench/cases.
Your own tools of part one are in LOGS and may be used again or copied under a new name beginning stage5c2:
the script that made the made recording, the recorder of connections, the private check and the driver.
Your report of part one is LOGS/STAGE5C1_REPORT.md. Read its last sections: what part two should know, and what was fixed after Cowork's check.

WHAT TO READ IN V1 AND IN OLD
V1/app/notes.py
   NOTE_PROMPT: its value, with one line break after it, must have the sha256 of the note prompt given above. Prove it in your plan.
   NOTE_SCHEMA: the form of the note, carried as it stands.
   format_turns, and how the call is put together: the heading TRANSCRIPT: and one line for each turn.
   What v1 does to a note after the call (its check of the turns and its gate) is not carried.
V1/app/finalize.py
   Where a turn is given the role Doctor or Patient. Those are the two role words of v1.
OLD/TASK5D_NOTE.md and OLD/task5d-notes.jsonl
   How v1.1 benched the note with this prompt and Gemma 4, and 390 notes it wrote. Use them for one thing:
   how long a note is, to check the limit of 3,000 tokens. Run nothing of it.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 10, 11, 13, 15.3, 15.4, 15.7 and 15.9, and rulings 1, 16 and 26 of 15.8.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 1, 2, 3, 7, 8, 9 and 15.
   Read the code part two is built on, and its tests: everything in V2/openconsult/speech,
   V2/openconsult/bench, V2/openconsult/llm and V2/openconsult/prompts.
2. Check the spec with sha256sum. It must be:
   4fe489801050f6d494f3c2e2b761871ac11ab07b30ff069544a5d5bec4ef384b  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is 232d833c7b9635b3e598903b6fde0160f62f7026.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Make an empty file LOGS/stage5c2-start.marker. Every file you write in LOGS after this is newer than it.
   Check the files of P1 against LOGS/stage5c-cases/part_one_files.sha256 with sha256sum -c, run from LOGS.
   If one differs or is missing, stop and report.
   Write four lists of names, sizes and times of last change. You compare each at the end.
   LOGS/stage5c2-p1-before.txt: every file in the first five folders of P1.
   LOGS/stage5c2-p1-data-before.txt: the top level of LOGS/stage5c1-data only. Open no file there.
   LOGS/stage5c2-real-before.txt: the owner's real data folder, /home/indy/.local/share/openconsult. Open no file there.
   LOGS/stage5c2-cache-before.txt: this machine's shared model cache.
7. Look, read only, and write what you find in your log:
   whether anything answers on http://127.0.0.1:8000 (that is the v1 service; it should be off);
   the graphics card's memory, used and free (nvidia-smi);
   the free space on the disk that holds LOGS;
   whether Ollama answers on this machine, its version, and whether gemma4:26b-a4b-it-qat is present, with its digest;
   whether the models of the WhisperX choice and of the Nemotron choice are in this machine's shared model cache,
   each with its revision and size;
   where Piper is on this machine and its version.
   Change nothing. Do not stop here whatever you find: the gate is in Part 4, and it asks for what you found here.
   Never print a token. Never read a file that holds one.

RULES
1. Write only in V2 and in LOGS, and in LOGS never inside a folder of P1. Never in V1. Never in OLD.
   One thing is not a breach: the system's temporary folder.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
   Install no system software. Pull, delete, create and change no model in Ollama.
   You may ask Ollama to load and to unload gemma4:26b-a4b-it-qat, and nothing else.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1. Port 8001 and the real data folder are for the owner's own check.
   Your own working data folder is LOGS/stage5c2-data. The recordings of part two and their list go to
   LOGS/stage5c2-recordings. The results of part two go to LOGS/stage5c2-rehearsal.
   There is one exception, named in this prompt: the list of names of step 6 above.
6. Until the gate for the card in Part 4 is passed: load no model on the graphics card, build no speech environment,
   make no call to the language model, and fetch no model, no voice and no data file. Parts 1 to 3 need none of these.
   No speech model and no voice is downloaded in part two: every one is already on this machine.
   One data file is fetched from outside in the whole run: the month of the drug list, in Part 4, item 9.
   For your plan you may read the pages of the portal that describe that file. Reading a page is not fetching the file.
7. THE KEYS. Part two needs no key. Read no file named .env, anywhere. Copy none.
   Open no connection to either cloud speech service. If you find that a step needs one, stop and report.
8. WHAT LEAVES THE MACHINE. Nothing of ours. No sound, no transcript, no note and no word of a script.
   The language model is the local one, through Ollama on this machine.
   The only connections to the outside are: the portal's pages, read for your plan; the fetch of the drug list's file;
   and uv, when it builds an environment from a lock file. None of them sends anything of ours.
9. WHAT STAYS PRIVATE. No word that a person said in a recording goes into V2, into a commit or into chat.
   The same holds for the transcripts, for the notes written from them, for the key-fact file,
   and for every word of script 19. You may read them in LOGS to check the scoring.
   What you find goes into your log and your report in LOGS. Chat gets counts.
   The made-up files of the suite are made up: they hold no fact, no drug and no sentence of script 19.
10. TEXT THAT A MODEL READS (spec 15.8, ruling 1; 15.3). You never write or change a word a model reads.
    The three prompts are the three files Cowork left: copy them byte for byte and prove the copies.
    The words placed around a transcript are exactly those the details of part two give, under
    What follows each prompt, the role words included. The names in the three forms are those the details give.
    If you need a word that the details do not give, stop and report.
    No prompt file of stage 3 changes, and its two prompt hashes stay as they are.
    No speech choice of the app is given any text, as before.
11. The rulings are never worked round. If something cannot be done as a ruling says, stop and report.
12. Before each commit, run the private word check on the staged files. It must print nothing:
    git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
    If it prints a line, stop and report. Do not edit a file to make it pass.
    Never copy the word list, or any word from it, into V2 or into a commit message.
13. Each commit: one logical change, the suite green before it, the why in the message.
    No personal names and no host names in a message.
    Each commit message ends with this line, after one empty line (spec 15.6, ruling 3):
    Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
    That is the only address allowed in a commit message.
14. Commands and short results go to LOGS/stage5c2.log. Long output never goes into chat.
15. Nothing is built switched off, and nothing is built for a later stage (R31).
    Nothing of part two is built into the app. The app cannot reach the three jobs of the bench, the voice method,
    the drug list or the second listen: they are not in the app's table of jobs or of speech choices,
    no command of the app names them, and no setting can. Tests pin it.
    In V2/openconsult/speech the only change of behaviour is the fix in the Nemotron worker.
    If you judge that anything else there must change, say what and why in your plan.
    The door to language models may gain what the bench needs to hand it a job of its own, and no more.
    The two jobs of the app are sent exactly as today: prove in your plan that not one byte of their requests changes.
16. Nothing in the base app assumes Linux. The bench's commands, the scoring, the made-up workers and the suite
    must run on Windows and macOS. The suite needs no graphics card, no speech library, no language model, no key,
    no internet, no recording, no Piper and no drug list from outside. It must pass on GitHub's machines.
    The base app gains no heavy library: no PyTorch, no numpy and nothing that brings them (spec 5.1; V1_LESSONS 7.1).
    The voice method needs such libraries, so it runs as a worker of the bench in the WhisperX environment,
    as the tied pair runs in Nemotron's. If you judge that the bench needs a library the base app does not have,
    say which and why in your plan, and wait.
    Two rules for tests, from the Windows check of part one: a file whose bytes are hashed is written as bytes,
    and a path is compared by its parts, never as a string. A file that is hashed is marked in .gitattributes
    so that Git never changes a byte of it. Keep the list of every place where the three systems differ,
    and say for each how you know it works.
17. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
18. What a model writes, and what a speech model hears, is never asserted in the suite. It is measured in Part 4 (spec 5.2).
19. In the shared model cache, delete nothing, change nothing and add nothing.
20. THE FOUR CHOICES OF 5a AND 5b BEHAVE AS THEY DO TODAY, but for the one fix the spec orders in the Nemotron worker.
    The tied pair is not changed. No test of 5a, 5b or part one is weakened or deleted.
    If a test must change because of the fix or because of the corrected wait, say which and why in your plan.
21. Recordings are read, never written. A result is never written over. The bench refuses to write its results
    into the repo, into the owner's own data folder, into the data folder it was given for its workers,
    or into a folder that holds recordings. A stored result of part one is never changed: part two works on copies.
22. A call that fails is kept as failed and is counted. Nothing is asked a second time in silence.
23. No comment, no test name and no message cites a private plan review or this prompt by a private name.
    A comment gives the reason itself, or cites the spec or V1_LESSONS.
24. If a step fails, stop and report. A check that asks for one example of something is not failed
    when there is none to find: say that there was none.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 5c part two: the spec, with part one folded in and the details of part two
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 5c part two: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_05C2.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE5C2_PLAN.md. It holds:
1. The files you will write or change, each with its job in one line and its expected size.
   The total you expect to add to the app and to the tests, set beside today's sizes.
2. Fix one, Nemotron's last line before a silence. Where the last word and the last line wait today, with the lines of code.
   The change. What closes a line after it, case by case. How you know that the fix never splits a word in two
   and never changes, adds or loses a word. Whether any other arm's worker shares the code you change:
   the tied pair must not change. The tests. How Part 4 proves it on the card.
3. Fix two, the wait. The corrected rule of the details of part one, with one worked example of each wait.
   How a live line is given its speech for every arm. How the first and the last line of a speech are found.
   The proof: part one's 18 results scored again with the new code, set beside part one's tables.
   In the marks of part one, nothing but the wait may differ.
4. The lines a model reads, and the turns: the rule of the details, with one worked example on made-up words for
   pieces of one word, for sentence pieces, for long turns, for a piece with no speaker, and for a pause.
   The test that the words that come out are the words that went in.
5. The three jobs of the bench. Where the three prompt files live in V2, the proof that each is the same bytes
   as Cowork's file and as the text between the fence lines of the spec, and for the note also as v1's constant.
   The line in .gitattributes. The three forms as files. How a job of the bench goes through the one door
   to language models with its own prompt, form and limits, without entering the app's table of jobs,
   and the proof that the two jobs of the app are sent as today.
   The limits as named figures with their sources. Check the two sources the details give, from files and with no
   call to a model: the longest note of Task 5d, and the lines of the longest page of part one's results.
   The exact text that is sent for one small made-up page, for each of the three jobs, written out in full:
   the system text and the user text, and for the note a turn of each role, one with no speaker among them.
   Where the calls of the bench are recorded.
6. The label check: when a reply is refused, and what is counted.
7. The voice method: the model, with its name, revision and licence as the WhisperX environment holds it
   (pyannote's voice model, as your report of part one lists it);
   how it is loaded from disk with no connection; the worker, and how it runs in that environment behind a command of the bench;
   how the minute is learnt; how the likeness of a line is measured; the two figures and the 1.0 second, as named
   constants with their sources; the new field of the banked list; the form of its result; the card's memory you expect.
8. The UK drug list. Read the portal's pages for this, and fetch no data file yet. The dataset's page is
   https://opendata.nhsbsa.net/dataset/prescription-cost-analysis-pca-monthly-data
   Give: its licence line, quoted; the exact address of the file for the month you will fetch, which is the latest
   month the portal offers on the day (it was July 2026 when Cowork looked; a later month is as good);
   and that no account and no key is asked. If one is asked, stop there and report.
   The names of the columns, and the class codes in the portal's own words. On 11 Oct 2026 Cowork read these columns
   for an earlier month, and you confirm them for yours: YEAR_MONTH, REGION_NAME, REGION_CODE, STP_NAME, STP_CODE,
   DISPENSER_ACCOUNT_TYPE, BNF_PRESENTATION_CODE, BNF_PRESENTATION_NAME, SNOMED_CODE, SUPPLIER_NAME, UNIT_OF_MEASURE,
   GENERIC_BNF_EQUIVALENT_CODE, GENERIC_BNF_EQUIVALENT_NAME, BNF_CHEMICAL_SUBSTANCE_CODE, BNF_CHEMICAL_SUBSTANCE,
   BNF_PARAGRAPH_CODE, BNF_PARAGRAPH, BNF_SECTION_CODE, BNF_SECTION, BNF_CHAPTER_CODE, BNF_CHAPTER, PREP_CLASS,
   PRESCRIBED_PREP_CLASS, ITEMS, TOTAL_QUANTITY, NIC.
   The rule that makes the list, as the details give it: which rows, which words of a name, what is left out,
   and the words for a salt or a form that you drop, as one named list.
   Where the fetched file and the list are kept, in LOGS. The line for NOTICE. The made-up file the suite uses.
   Part 4 shows the size of the file, the number of names, 30 names drawn with a fixed seed,
   and which of the drug names of script 19 are in the list.
9. The three ways to spot a doubtful drug name: each rule, with one worked example on made-up words.
   For the list: how closeness is measured, and the named figure. For the second listen: how two pages of the same
   sound are set against each other without the script. For all three: what counts as marked, and what counts as a
   mark on a word that was written rightly.
10. The three classes of a drug name that was not caught, with one worked example each.
11. The notes: the turns and the roles; the two rounds; and each of the five counts of the details, with one worked
    example. For figures: how a dose in other units and the short forms for days, weeks and months count as spoken.
12. The key facts: how the file is read; the four outcomes, each with a worked example, among them a negative
    that was lost, a figure that was changed, and a fact that is looked for in named sections only;
    the nearest entry; a reading that is not whole; and the mark for a fact that the notes from the script also missed.
13. The commands of part two, with their exact words, and what each writes and where.
    The one command that scores the stored results and writes the tables of the report.
14. The recordings of part two: how the files of P1 are copied and proved; the minute of the doctor's voice,
    made as the made recording was; and the list of part two, field by field for what is new.
    How the minute is listed, so that the bench can learn the voice from it and can never replay it as a consultation.
15. The full rehearsal: its steps in order; the driver, which must run with nobody there; the minutes you expect;
    what it does when a step or a call fails; the card's memory you expect at each step; and how you make sure that
    the speech models are off the card before the language model is loaded.
16. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2; V1_LESSONS 8.8).
17. Every new sentence the bench will show to a person, in one list, so the owner can correct the wording.
18. The commits you will make, in order.
19. The list for rule 16: where the three systems differ.
20. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
21. Whether part two fits in one session. If you judge it does not, name the point where you would split it.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what the details of part two say. This is the suggested order. Your plan may change the order and say why.
1. Fix one, in the Nemotron worker, with its tests. Do not load a model yet.
2. Fix two, the wait, with its tests.
3. The lines a model reads, and the turns.
4. The three jobs of the bench: the prompt files, the forms, and the way through the door, with a made-up engine for the suite.
5. The voice method: the worker and its command. Do not load a model yet.
6. The label check and its counting. The four readings of who spoke.
7. The drug list: the command that fetches and makes it. Do not fetch yet. The three ways and the three classes.
8. The notes and their five counts, with the key facts.
9. The commands of part two, with the one that scores and writes the tables.
10. The documents, in the last commit, which is made in Part 4, item 17, so that the measurements are in it:
    CLAUDE.md: under Running it, the new commands. It is 99 lines today and must stay under 100: make room, lose nothing a builder needs.
    README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
    NOTICE: the source of the drug list and its licence, in the commit that adds the command.
    HANDOVER.md: a new entry at the top. What was done, the rulings part two rests on in one line each,
    the measurements, and what this stage has made untrue. It is 465 lines today and must stay under 500:
    move the oldest entries to archive/HANDOVER_ARCHIVE.md.

PART 4. THE CHECKS
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. A fresh Python with only the base app installed: the app starts, answers and stops, and no speech library can be imported.
   Run the start step of the GitHub check as it is: uv run python .github/scripts/start_check.py
   In the same fresh Python, the bench command prints its help, and the scoring of part two runs on made-up results.
Item 3. The tables of the database: say whether any changed. None is expected. If one changed, stop and report.
Item 4. The wait, proved on part one's results. Score the 18 results of P1 with the new code into a new folder in LOGS,
   reading them where they lie, and set the marks of part one beside LOGS/stage5c1-rehearsal-tables-after-fix.
   Where there is no result of part two, the command still writes the marks of part one, and it needs no drug list for them.
   Nothing but the wait may differ. Write in your log what differs. If any other mark of part one differs, stop and report.
   On the made recording a wait that is measured from a true time cannot be below zero:
   write the least of them for each arm, and if one is below zero, say why.

THE GATE FOR THE CARD. Items 5 to 13 build two speech environments and load models. Before item 5:
   Ask http://127.0.0.1:8000 once. If anything answers, the v1 service is running.
   Then print exactly this line and stop: Waiting for v1 to be switched off.
   The owner will type: v1 is off. Go.
   When nothing answers on port 8000: if step 7 found that a speech model of the two local choices, Piper,
   the doctor's voice file in LOGS/stage5c1-voices, Ollama or its model gemma4:26b-a4b-it-qat is not on this machine,
   stop and report. Nothing is fetched to make up for it.
   Then ask Ollama to unload gemma4:26b-a4b-it-qat if it is loaded, and nothing else, and read the card's free memory.
   The language model must not be on the card while a speech model is.
   If the free memory is less than your plan's figure plus 1,000 MiB, stop and report.
Item 5. Build the WhisperX environment and the Nemotron environment with the app's own command, into LOGS/stage5c2-data.
   Write the times and the sizes on disk in your log. Then the self-test of each of the two choices on that folder. Each must pass.
Item 6. Fix one, on the card. Feed to the Nemotron choice, straight through its door with a script of your own in LOGS:
   60 seconds of made silence, then 60 seconds of made noise at -50 dBFS, then 60 seconds at -30 dBFS, with Stop after each.
   No line may be accepted. Then the test clip followed by 30 seconds of made silence, with no Stop until the end:
   write the moment the last word of the clip was spoken, the moment its line was final, and the difference.
   The line must be final within 6 seconds of its last word, long before Stop. If not, stop and report.
Item 7. The recordings of part two. Copy the sound files, the two files of true times and nothing else from
   LOGS/stage5c1-recordings into LOGS/stage5c2-recordings, and prove each copy by its checksum.
   Make the minute of the doctor's voice there, from LOGS/stage5c-cases/doctor_minute.txt, with the doctor's voice
   of the made recording and in the same way: 48,000 samples a second, quiet at both ends, never played through a speaker.
   Look at it with code: its length, its loudest and its typical loudness, and whether it clips.
   Write the list of part two there: the five entries of part one, changed in one thing only; the minute, marked as
   machine voices, with consent for this computer only. The one thing: the made recording and its cut each gain the
   new field, which names the minute as the recording that holds the doctor's voice alone. The three old recordings name none.
Item 8. The results part two works from. Copy the 14 results of P1 that are not Nemotron's into LOGS/stage5c2-rehearsal,
   in the places the bench expects, and prove each copy by its checksum against LOGS/stage5c-cases/part_one_files.sha256.
Item 9. The drug list. Fetch the month your plan named, with your command, into LOGS. Make the list.
   Write in your log: the address, the size and the sha256 of the file, the number of names,
   30 names drawn with a fixed seed, and for each of the 20 drug names that LOGS/stage5c-cases/speech_marks.json
   gives for script 19 whether it is in the list.
   If the portal asks for an account or a key, stop and report. Do not look for another source.
Item 10. One short proof before the long run, on the 60-second cut, in the order of the rehearsal.
   This is only to find a broken step before the rehearsal. Its results are kept apart from the rehearsal's.
   Feed the cut to the Nemotron arm with the bench's own command. Count the words that differ between its new page
   and the page of the cut that part one stored in LOGS/stage5c1-proof. If more than 5 differ, stop and report.
   Run the voice method on the stored page of the cut from LOGS/stage5c1-proof (WhisperX), read from a copy.
   Ask each new command of part two for a result folder inside V2, inside LOGS/stage5c2-data and inside
   LOGS/stage5c2-recordings, and for one result a second time: each must be refused, and nothing written.
   Stop every speech worker and read the card's memory.
   Then, with the language model loaded and no speech model on the card, on that same page:
   one label check, one call for doubtful drug names and one note.
   Write, as counts and never as words: the lines of the page, how many the voice method marked doctor, not doctor
   and unsure, whether each reply fitted its form, and the seconds and the tokens of each call.
   Then ask Ollama to unload the model.
Item 11. THE FULL REHEARSAL. Start the driver, and print exactly this line: The rehearsal of part two has started.
   The driver runs the steps of the details in their order, one heavy job at a time.
   It first makes sure that the language model is not on the card. Then:
   Nemotron again on the four recordings, with the bench's own command, into LOGS/stage5c2-rehearsal;
   the voice method on the five pages of the made recording (WhisperX at Stop, Nemotron, the tied pair and the two
   services), and for each of the three old recordings the plain record that it was not run, because their
   entries name no recording of the doctor's voice alone;
   then every speech worker is stopped, and the card's memory is read;
   then, with the language model, the label check and the call for doubtful drug names on each of the 14 pages,
   the notes in two rounds, and the notes from the scripts.
   The list and the second listen for doubtful drug names need no model: the scoring works them out.
   A sampler writes the card's memory use to LOGS every 2 seconds (nvidia-smi, read only).
   Every connection attempt and every name lookup of the Nemotron worker and of the voice worker is recorded while
   it runs: those records must be empty.
   The driver needs nobody. If a step or a call fails, its failure is kept and the driver goes on.
   Expect about an hour and a quarter. Wait for the driver to end. Look at its log at long intervals,
   not in a tight loop, and start nothing else on the card meanwhile.
Item 12. Nemotron, old and new. Write in your log, for recording 477: the last word heard, the moment its line
   was final, and the wait. It must be under 6 seconds. If it is not, stop and report.
   Set the new four results beside the old four of P1: the number of lines, the words, and the longest wait
   for a final line, for each. The fix is meant to change when a line closes and where it is cut, and never a word.
   Count the words that differ between the old page and the new page of each recording.
   If more than 5 differ on any recording, put it first among what you flagged in your report, with the lines.
Item 13. Score the rehearsal and write the tables, with the one command, from the stored results alone.
   Run that command a second time into another folder in LOGS: the two sets of tables must be the same, byte for byte.
   Then ask Ollama to unload the model.
Item 14. Read your own tables as a doubter would. Open the stored files and check by hand, where there is one:
   a line the label check put under the wrong speaker, and one it called unsure; a reply the code refused;
   a line the voice method marked wrongly; a drug name each of the three ways marked rightly, and a mark on a word
   that was written rightly; a drug name in each of the three classes; a key fact with each of the four outcomes;
   a figure in a note that the scoring calls not spoken; a note whose reasoning the scoring says stops in the middle
   of a sentence; and a pair of notes that differ.
   Write what you found in your report, in LOGS. If the scoring is wrong, say so plainly.
   For every key fact that both notes from a script failed to find, say whether the note lacks it or the rule is wrong,
   with the fact's id. Do not correct the file: Cowork does.
Item 15. The self-tests once more, of the WhisperX choice and of the Nemotron choice, on LOGS/stage5c2-data,
   with the code as it now is. Each must pass.
Item 16. Before the last commit, search the tests you added or changed for the two faults of rule 16:
   a file written in text mode whose bytes are hashed, and a path compared as a string.
   Write in your log what you looked at and what you found.
Item 17. Make the last commit, the documents, with the measurements in it.
Item 18. Nothing private is in V2. In the working tree and in every commit of this run
   (git log -p 232d833c7b9635b3e598903b6fde0160f62f7026..HEAD): no sound file, no result file, no note, no banked list,
   no drug list, no file from LOGS/stage5c-cases, and no run of six words in a row from the spoken text of script 19
   or from the text of the doctor's minute. Search with a script that prints counts only. Every count must be 0.
Item 19. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. The files of P1 still pass sha256sum -c against part_one_files.sha256,
   and the list of the first five folders of P1 made now equals LOGS/stage5c2-p1-before.txt, line for line.
   The list of the owner's real data folder made now equals LOGS/stage5c2-real-before.txt, line for line.
   The list of the top level of LOGS/stage5c1-data made now equals LOGS/stage5c2-p1-data-before.txt.
   The list of the shared model cache made now equals LOGS/stage5c2-cache-before.txt: nothing was added, deleted
   or changed there. No file named .env was read.
   Port 8000 and port 8001 were never used by you.
Item 20. Write LOGS/STAGE5C2_REPORT.md. Its first line says: THIS IS A REHEARSAL. NO FIGURE IN IT COUNTS.
   Then the most important for the patient, for each speech choice that gave a page, in one table:
   was any drug written as another real drug, yes or no, and how many times;
   how many key facts were not found for its pages and were found in both notes from the script;
   how many words each of the four readings of who spoke put under the wrong speaker.
   Then, for the owner to read by exception: the key facts that were not found, by kind in the order of the details
   and then in the order spoken, each with the entry of the note that holds the most of its groups.
   This list is private and stays in LOGS.
   Then, each under its own heading:
   did the rehearsal run from start to end, and which step or call failed, if any;
   the two fixes with their proofs (items 4, 6 and 12);
   the tables of every count, as the bench wrote them;
   what item 14 found;
   the drug list (item 9);
   the voice method, with the card's memory at its highest;
   the calls, for each of the three jobs: the seconds and the tokens, the typical and the longest,
   and any reply that reached its limit of length or of time, or that the code refused;
   the card's memory at its highest in each step;
   the commits with their hashes; the files with their line counts; any target missed;
   the tests, each with what it pins; every new sentence shown to a person; the list for rule 16;
   the exact commands for the owner's own check, as one block with no quotation marks, in the order he runs them:
   uv sync, then the self-test of each of the four choices on his real data folder;
   the sizes of LOGS/stage5c2-data, LOGS/stage5c2-rehearsal and LOGS/stage5c2-recordings;
   and what in LOGS may now be removed, as one line for each, without removing anything yourself.
   Last: anything you flagged, and what 5d and 5e should know.

FINAL MESSAGE
Twelve lines at most:
that this was a rehearsal and no figure counts,
whether the rehearsal ran from start to end, and any step or call that failed,
that the two fixes are in, with the wait of Nemotron's last line on recording 477,
for each speech choice: whether any drug was written as another real drug,
that nothing of ours left the machine, that no key was read, and that no cloud speech service was reached,
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
that V1 HEAD, the folders of part one and the owner's real data folder are unchanged, and that ports 8000 and 8001 were never used,
any target missed,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 5c part two done. Do not push yet.
