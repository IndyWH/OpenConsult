STAGE 3c of OpenConsult v2.0: the engine setting

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Today every pass waits on Ollama, with its two calls one after the other: about 5 seconds.
After 3c, on a Linux machine with a suitable card, the app tries vLLM first and sends the alarm and the
assessment together: under 3 seconds, and the alarm itself back in about a second. The patient waits less
for the warning that matters. On any other machine nothing changes for the user: Ollama or the cloud, as today.
At start the app also reads the room on the card once, so the guideline search sits where it fits and the
WhisperX choice is never offered where it would die at Stop. This machine says each decision in plain words.
The spec is V2_SPEC.md. Stage 3c is in section 15.8. Read, in this order: rulings 30 to 40, then the part
headed Stage 3c: the engine setting, with its details and its Done when you see, which stands at the end of 15.8
before 15.9. Read 15.7 with it: the door, the joint, the pass and the record that 3c builds on.
Build what the details of 3c say. Each ruling it rests on is named there.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report and your working data folder go here.
      This prompt is here. Every file and folder you make in LOGS has a name that begins stage3c or STAGE3C.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files of the engine bench, as 5d left them: vLLM 0.31.0 and the repack of
      Gemma 4 for vLLM among them. You start and stop vLLM from here, as 5d did, and only in Part 4.
      You write in ENG only what an engine itself writes when it runs and your own run files in a new folder
      ENG/run-3c. You install nothing there, you delete nothing there, and you change no file of 6, 7 or 13 Oct.
CASES /home/indy/Work/openconsult-review/v2-logs/stage3-cases
      Read only. The cases of the engine bench. 3c uses consultation 495 alone, with the bench's own switch for one case.
OLDER Every other folder in LOGS whose name begins stage3-, stage3b, stage5a, stage5b, stage5c1, stage5c2 or stage5d.
      Your own folders, which begin stage3c, are not OLDER. Read only. Write nothing there and delete nothing there. Do not use an older data folder as your own.
      LOGS/stage5c1-data holds a copy of the owner's two keys. Do not open LOGS/stage5c1-data/.env.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
      Never read V1/.env or any other file that holds a key or a token.

WHAT 5d LEFT IN LOGS THAT 3c USES
LOGS/stage5d_engines.sh     how vLLM was started with its room (start vllm-5d), stopped, and seen to be off the card.
                            Copy it to LOGS/stage3c_engines.sh with its run folder ENG/run-3c and its log LOGS/stage3c.log.
                            Do not change the file of 5d.
LOGS/stage5d-vllm-room.txt  vLLM's room in bytes, 1400000000. The copy reads the same figure.
LOGS/STAGE5D_REPORT.md      the report of 5d. Its section on vLLM's room, and the figures of the card, are the source
                            of the constants the details of 3c name.
The model vLLM serves: xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct, revision 2096d38dad51a19b8e982b44241c47102a8bbb00,
with the compact answer form of 15.8, ruling 22, exactly as the bench of 7 Oct and 5d set it. Which of its two
options is set at vLLM's start and which travels in a request is for your plan to say, from the bench's own code and
vLLM's page; you carry over what the bench did, so that the words the model reads are unchanged.
The Ollama service holds gemma4:26b-a4b-it-qat, the model of stage 3, at the digest stage 3 recorded.
Cowork's tool for the Windows faults: LOGS/cowork_winsim.py. It is used in Part 4.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 10, 15.3, 15.4, 15.6, 15.7 and 15.8.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 3 and 8.
   Read the code 3c is built on, and its tests: everything in V2/openconsult/llm, V2/openconsult/consult,
   V2/openconsult/settings and V2/openconsult/words.py; in V2/openconsult/bench the modules vllm.py, together.py,
   chat_engine.py and replay.py; and in V2/openconsult/web the pages and the templates of Settings.
2. Check the spec with sha256sum. It must be:
   7d5a137deac6f37f2b722c312cb9f7da37e6398b6774929f3ced1585418ab687  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is e453c21b21bad597e3d1c874f561495435ca2e52.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Make an empty file LOGS/stage3c-start.marker. Every file you write in LOGS after this is newer than it.
   Write these lists of names, sizes and times of last change. You compare each at the end.
   LOGS/stage3c-older-before.txt: the top level of every OLDER folder. Open no file there.
   LOGS/stage3c-real-before.txt: the owner's real data folder, /home/indy/.local/share/openconsult. Open no file there.
   LOGS/stage3c-eng-before.txt: every file in ENG but its caches and its run folders, with the sha256 of each model file.
   LOGS/stage3c-ollama-before.txt: every model the Ollama service has, each with its digest, and its version.
7. Look, read only, and write what you find in your log:
   whether anything answers on http://127.0.0.1:8000 (that is the v1 service; it should be off);
   whether anything answers on http://127.0.0.1:8172 (that is vLLM; it should be off until Part 4);
   the graphics card's memory, used and free, and every program on it (nvidia-smi);
   whether the Ollama service answers, its version, and what it holds loaded;
   in ENG: vLLM's version from its own program, and the folder of the repack at its revision;
   what the read-only command tailscale funnel status says. Funnel must be off for 3c: that is this prompt's rule,
   as it was 5d's, not a ruling of the spec.
   If that command asks for sudo, do not run it, and write that it could not be read.
   Change nothing. Do not stop here whatever you find: the gate is in Part 4, and it asks for what you found here.
   Never print a token. Never read a file that holds one.

RULES
1. Write only in V2, in LOGS under names that begin stage3c or STAGE3C, and in ENG as THE FOLDERS says.
   Never in V1. Never in CASES or in an OLDER folder. The system's temporary folder is not a breach.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git. Install no system software.
   THE OLLAMA SERVICE. Change no setting of it. Pull, make, change and delete no model in it. Do not upgrade it
   (15.8, ruling 39). You may ask it to load and to unload a model it already holds, and to answer. Nothing else.
   vLLM is started and stopped as 5d did: from ENG, on 127.0.0.1 port 8172, with its room, by your copy of the
   engine script, and only in Part 4. No second Ollama is started in 3c.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1. Port 8001 and the real data folder are for the owner's own use.
   Your working data folder is LOGS/stage3c-data. The results of the proof go to LOGS/stage3c-proof.
6. Until the gate for the card in Part 4 is passed: start no engine and load no model. Parts 1 to 3 need none.
   For your plan you may read pages: the makers' own pages for vLLM and Ollama. uv may reach the package index.
7. KEYS AND TOKENS. 3c needs no key. Read no file named .env, anywhere. Copy none. Open no connection to any cloud service.
8. WHAT LEAVES THE MACHINE. Nothing of ours. No reply and no word of a case. The only connections to the outside
   are the pages read for your plan and uv. vLLM is started as 5d started it, with its usage reports and its reach to
   the model hub switched off.
9. WHAT STAYS PRIVATE. Consultation 495 is public in V2/engine-bench, so its words are not the concern here; the
   concern is the record of calls your proof makes and the replies: no file of results and no line of a log goes into V2.
   The figures of the proof go into HANDOVER.md. The files they come from do not.
   Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
   V2_SPEC.md and the copy of this prompt are committed as they were given to you, and are not meant by that.
10. TEXT THAT A MODEL READS (15.8, ruling 1; 15.3). You never write or change a word a model reads.
    No prompt file changes, the fixed words around the transcript and the patient line do not change, and the two
    prompt hashes of stage 3 stay as they are. The word check of stage 3 must still give 1,898 of 1,898 for each call.
    Sending the two calls together changes the moment of sending, never the words.
11. The rulings are never worked round. If something cannot be done as a ruling says, stop and report.
12. Before each commit, run the private word check on the staged files. It must print nothing:
    git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
    If it prints a line, stop and report. Do not edit a file to make it pass.
    Never copy the word list, or any word from it, into V2 or into a commit message.
13. Each commit: one logical change, the suite green before it, the why in the message.
    No personal names and no host names in a message.
    Each commit message ends with this line, after one empty line (15.6, ruling 3):
    Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
    That is the only address allowed in a commit message.
14. Commands and short results go to LOGS/stage3c.log. Long output never goes into chat.
15. Nothing is built switched off, and nothing is built for a later stage (R31). The list Not built in the details of
    3c is binding: no setting to pick an engine by hand, no start or stop of an engine by the app, no second Ollama,
    no cloud, no connect screen, nothing drawn for the control panel of ruling 38, nothing loaded for the guideline
    search, nothing of Piper. Stage 8 and 5e read the room check's decisions later; 3c records and shows them.
16. Nothing in the base app assumes Linux. The suite needs no graphics card, no engine, no model, no key and no
    internet, and must pass on GitHub's machines. The base app gains no heavy library (5.1).
    The four rules for tests from the Windows checks of 5c hold: a file whose bytes are hashed is written as bytes;
    a path is compared by its parts, never as a string; a database or a file is closed before it is removed, renamed or
    written over; and a text file is opened with its encoding named.
    Keep the list of every place where the three systems differ, and say for each how you know it works.
17. The size targets of spec section 5 hold: no file over 600 lines, no function over 80, tests no larger than the app,
    the suite under a minute, CLAUDE.md under 100 lines, HANDOVER.md under 500. If a target cannot be met, report it
    and say why. Do not squeeze code to fit a number.
18. What a model writes and how fast a machine is are never asserted in the suite. They are measured in Part 4 (5.2).
19. No test of an earlier stage is weakened or deleted. The bench keeps both ways of running a pass for its arms;
    the app has one way, together.
20. A call that fails is kept as failed and is counted. Nothing is asked a second time in silence.
21. No comment, no test name and no message cites a private plan review or this prompt by a private name.
    A comment gives the reason itself, or cites the spec or V1_LESSONS.
22. If a step of Parts 1 to 3 or a check of Part 4 fails, stop and report.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 3c: the spec, with the rulings of the engine choice and of 3c, its row and its details
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 3c: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_03C.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE3C_PLAN.md. It holds:
1. The files you will write or change, each with its job in one line and its expected size.
   The total you expect to add to the app's side and to the tests, set beside today's sizes.
2. What the makers' own pages say today, each with the page's address and the sentence quoted:
   vLLM, for the version in ENG: how a client reads the served model, its largest context, the engine's version and
   the model's digest or revision for the record, and what the health check answers; the two options of the compact
   answer form, which is set at vLLM's start and which travels in a request, and that neither is a word the model reads.
   Ollama: how the service reports the version, the loaded models and a model's digest, as the Ollama engine reads them today.
3. The vLLM engine in the app: what it takes from V2/openconsult/bench/vllm.py and what changes; the request it builds
   from the parts of a call, set beside the request of the bench of 7 Oct, with what differs; how it reads the context
   vLLM reports, and what makes vLLM fit or not fit, each with the reason the app would give. Where the address lives
   in the settings store and its default. How the model's profile names the model for each engine.
4. The order of trying, as code: what is read to know Linux, a suitable card, and each engine's answer; the short wait;
   where the choice is held; what is written to the audit log; and how a failed call during a run stays failed with no switch.
5. The together pass: what moves from V2/openconsult/bench/together.py into the consult folder, how the bench keeps
   both ways, and the proof that the words sent are the same as before: the word check of stage 3, 1,898 of 1,898 for each call.
6. The room check: the constants with their source in the 5d report, line by line. The language model on vLLM is
   18,316 MiB, its highest in 5d; ruling 30's 18,212 was the reading at one start, and the constant is the higher one; the two sums written out with
   the figures of mlrig as a worked example; how the card's memory in use by other programs is read, and how the
   app's own engines and workers are told apart from other programs; what happens on a machine with no card.
7. The three elements of ruling 38: their names, states, reasons and figures, where they are held, and how This machine
   and the audit log read them.
8. Every new or changed sentence shown to a person, in one list with its key in the file of words, so the owner can
   correct the wording. This machine's lines for the language model, the guideline search, speech and both engines missing.
9. The proof on mlrig: each step with its command, what it writes, and the seconds you expect; how the test user is
   set up on the test data folder through the page and logged in, so that This machine can be read, and that the folder is thrown away; how the three chains of
   495 at temperature 0 run through the app's own pass, together, on vLLM, and one chain on Ollama; how the hard marks
   H1 and H2 are counted from the raw files; and the one block for the owner that starts vLLM with its room and the
   one that stops it.
10. Every test you intend, each with the rule, the ruling or the incident it pins (5.2; V1_LESSONS 8.8).
11. The commits you will make, in order.
12. The list for rule 16: where the three systems differ.
13. The move of HANDOVER's older entries to the archive file, so that it stays under 500 lines: which entries move
    and what stays. The corrected sentence from 5d, word for word.
14. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what the details of 3c say. This is the suggested order. Your plan may change the order and say why.
1. The vLLM engine in the llm folder, with its made-up twin for the suite, and the address in the settings store.
   The settings store's line that calls the engine a question for stage 3b is replaced.
2. The order of trying at start, the choice held for the run, the audit line, and both engines missing.
   Start not offered means in 3c that the element records it; there is no Start control until stage 6 and none is drawn now.
3. The together pass as the pass's own way in the consult folder; the bench keeps both ways.
4. The room check with its constants, the three elements, and their lines on This machine and in the audit log.
5. The sentences in the file of words. No sentence is typed anywhere else.
6. The documents, in the last commit, which is made in Part 4 so that the measurements are in it:
   CLAUDE.md: under Running it, the engine order and the room check. It is 99 lines today and must stay under 100.
   README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
   HANDOVER.md: the older entries move to V2/archive/HANDOVER_ARCHIVE.md, then a new entry at the top: what was done,
   the rulings 3c rests on in one line each, the measurements of the proof, and what this stage has made untrue.
   Correct the one sentence from 5d as the details of 3c say. HANDOVER must stay under 500 lines.

PART 4. THE CHECKS
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. A fresh Python with only the base app installed: the app starts, answers and stops, as the GitHub check does.
   Run the start step of the GitHub check as it is: uv run python .github/scripts/start_check.py
   Both engines missing is proven in the suite with made-up engines, not here: on this machine the Ollama service answers.
Item 3. The word check of stage 3 with no model: it must give 1,898 of 1,898 for each call.
Item 4. The Windows faults. Run the suite once under Cowork's tool, from V2:
   PYTHONPATH=/home/indy/Work/openconsult-review/v2-logs uv run pytest -p cowork_winsim
   It must pass. If a test fails there and passes plainly, the test has a Windows fault: put it right.
Item 5. The tables of the database: say whether any changed. None is expected. If one changed, stop and report.

THE GATE FOR THE CARD. Items 6 to 9 start vLLM and load models. Before item 6:
   Ask http://127.0.0.1:8000 once. If anything answers, the v1 service is running.
   Then print exactly this line and stop: Waiting for v1 to be switched off.
   The owner will type: v1 is off. Go.
   If step 7 read that Funnel is on, or could not read it, print exactly this line and stop:
   Waiting for the owner to say that Funnel is off.
   The owner will type: Funnel is off. Go.
   When nothing answers on port 8000: if step 7 found that the Ollama service, its model of stage 3, vLLM in ENG or
   the repack is not on this machine, stop and report. Nothing is fetched or made to make up for it.
   Then ask the Ollama service to unload whatever it holds, and read the card.
   If more than 1,500 MiB of the card is in use, stop and report.
Item 6. Start vLLM with your copy of the engine script. Write in your log its own lines at its start, and the card's
   memory with vLLM alone. Start the app on LOGS/stage3c-data and a test port that is not 8000 or 8001, with --no-browser.
   Set up the test user through the page and log in. Read This machine through the app. It must say that the language
   model runs on vLLM, that Gemma 4 QAT is present, that the guideline search sits on the graphics card, and that the
   WhisperX choice is not available, with the reason. If it says the processor, write the sum and the memory other
   programs held, and go on: that is not a failed check, and the owner reads it in the report.
   Copy the sentences and the audit line into your log. Stop the app.
Item 7. The three chains of consultation 495 at temperature 0, through the app's own pass, together, on vLLM, with the
   bench's switch for one case, the results in LOGS/stage3c-proof. Count the hard marks H1 and H2 from the raw files:
   both must hold in every chain. Write the typical pass and the slowest pass, and set them beside 5d's 2.73 seconds.
   Then stop vLLM with your copy of the script and see the card free.
Item 8. Start the app again as in item 6. This machine must now say Ollama, with the reason in the words of the file
   of words, for example that vLLM did not answer at its address.
   Copy the sentences and the audit line into your log. One chain of 495 at temperature 0 through the same pass on the
   Ollama service: both hard marks must hold. Write the typical pass. Ask the service to unload the model, and see the card free.
Item 9. Ask the bench's run command, which goes through the app's pass, for a result folder inside V2 and inside
   LOGS/stage3c-data: each must be refused, and nothing written. Never aim such a test at the owner's real data folder.
Item 10. Before the last commit, search the tests you added or changed for the four faults of rule 16, and run the
   suite once more under Cowork's tool, as in item 4. Write in your log what you looked at and what you found.
Item 11. The suite once more, plainly, three times. Each must pass.
Item 12. Make the last commit, the documents, with the measurements in it.
Item 13. Nothing private is in V2. In the lines that the commits of this run add
   (git log -p e453c21b21bad597e3d1c874f561495435ca2e52..HEAD, the added lines only): no result file, no reply of a
   model, no sample of the card and no line of a log. Search with a script that prints counts only. Every count must be 0.
   No added line names a folder of this machine that V2 did not name before, and none names the machine.
   Two files are outside that last check, because they are committed as they were given to you:
   V2_SPEC.md and the copy of this prompt.
Item 14. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. The list of the OLDER folders made now equals LOGS/stage3c-older-before.txt, line for line.
   Make the list of the owner's real data folder again. If it differs from its list of the start, write what differs
   and whether any command of yours could have written there. A change that is the owner's own is reported and is not a failed check.
   The list of ENG made now equals LOGS/stage3c-eng-before.txt: no model file and no engine file changed.
   No file named .env was read. Port 8000 and port 8001 were never used by you. No engine of yours runs, and the card is free.
   No setting of the Ollama service changed, and its list of models equals LOGS/stage3c-ollama-before.txt, name for name and digest for digest.
Item 15. Write LOGS/STAGE3C_REPORT.md.
   First, the most important for the patient, in a few plain sentences: on mlrig the app now runs its language model
   on vLLM and sends the two calls of a pass together; the typical pass of the proof, beside 5.11 seconds for the app
   before 3c and 2.73 for 5d; the hard marks held in every chain; and that with vLLM stopped the app falls back to
   Ollama and says so.
   Then, each under its own heading: what This machine said on vLLM and on Ollama, word for word; the audit lines;
   the room check's two sums with the figures of mlrig; vLLM's own lines at its start and the card's memory;
   the proof chain by chain, with the hard marks and the seconds; the word check of stage 3; the commits with their
   hashes; the files with their line counts; any target missed; the tests, each with what it pins; every new sentence
   shown to a person; the list for rule 16; what moved from HANDOVER to the archive;
   the two blocks for the owner, one that starts vLLM with its room and one that stops it, each as one block with
   no quotation marks; what the owner must do for his own check at port 8001, as short ordered steps;
   the sizes of LOGS/stage3c-data, LOGS/stage3c-proof and what 3c added to ENG; and what in LOGS and in ENG may now be
   removed, as one line for each, without removing anything yourself.
   Last: anything you flagged, and what 5e, stage 6, stage 8 and stage 15 should know. Two things belong there:
   that on the Ollama service as installed the two calls queue, so the gain of ruling 31 on Ollama needs the service
   set for two calls at once, for the install advice of stage 15; and that the app does not start vLLM, so until stage 15
   the owner starts it by hand with the block above.

FINAL MESSAGE
Ten lines at most:
what This machine said on vLLM, in one line, and on Ollama, in one line,
the typical pass of the three chains together on vLLM, beside 2.73 and 5.11,
that the hard marks held in every chain, on vLLM and on Ollama,
that the word check of stage 3 gives 1,898 of 1,898 for each call,
that nothing of ours left the machine, that no key and no token was read, and that the Ollama service is as it was,
the number of commits and the last hash,
the number of tests, the suite time, none skipped, and that the suite passed under the Windows tool,
that the private word check printed nothing before every commit,
any target missed and anything you flagged,
then this line for the owner: Tell Cowork: Stage 3c done. Do not push yet.
