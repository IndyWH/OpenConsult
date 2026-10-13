STAGE 5d of OpenConsult v2.0: the three models loaded together on one graphics card

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 5 is about speech. It is built in five steps, 5a to 5e. This is 5d, the fourth.
In a consultation three models work at once on one graphics card: the language model, the speech model,
and the embedding model of the guideline search. If they do not all fit, or if they slow each other down,
the patient waits longer for the next question and the doctor's alarm comes late.
5d loads the three together on this machine and measures two things: whether they fit, and what sharing
the card costs in seconds. It does so on Ollama and on vLLM, with each of the two local speech choices,
with two embedding models, and with the embedding model on the card and on the processor.
It is a report only. It builds no engine setting and nothing in the app. The owner chooses the engine afterwards, from the report.
The spec is V2_SPEC.md. Stage 5 is section 15.9 of it. Read that section first:
rulings 1 to 25, then the details of 5d, which stand after the part on 5c. Rulings 23, 24 and 25 are the rulings of 5d.
Read ruling 29 of section 15.8 with them: it is the ruling that asks for this test.
Build what the details of 5d say. Each ruling it rests on is named there.
This prompt gives the order of work and the rules. Where the two differ, the spec wins: stop and report.
OpenConsult is a research and education prototype. Never real patients.

MODEL
This stage runs on Fable 5.1 at high effort.
Say in your first line which model you are. If you are not Fable 5.1, stop there.

THE FOLDERS
V2    /home/indy/Projects/OpenConsult2
      The repo. Branch v2. All code and all commits are made here.
LOGS  /home/indy/Work/openconsult-review/v2-logs
      Private. Your plan, your log, your report, your working data folder and the results of the test go here.
      This prompt is here. Every file and folder you make in LOGS has a name that begins stage5d or STAGE5D.
ENG   /mnt/fastdata/openconsult-engine-bench
      The engines and the model files of the engine bench, as you left them on 7 Oct 2026: llama.cpp, vLLM 0.31.0,
      the repack of Gemma 4 for vLLM, and the folder of the second, private Ollama with its own copy of the model.
      You start and stop engines from here as on 7 Oct. You write in ENG only what an engine itself writes when it
      runs (its caches and settings, as on 7 Oct) and your own run files in a new folder ENG/run-5d.
      You install nothing there, you delete nothing there, and you change no file of 6 or 7 Oct.
REC   /home/indy/Work/openconsult-review/v2-logs/stage5c2-recordings
      Read only. The recordings of part two of 5c with their list. 5d replays one of them, recording 473.
      consultation_473.wav   sha256 947bc8e4a4e5fe5c3b2223b09d2fad07d663e4779f9994fad747536ee00c5732
      recordings.json        sha256 48179ff010fa4a1f06df69f4c4195744ddb0d8a9987fb3c07ac44cb025f5fc9b
      The made recording's 60-second cut, made_19_cut60, is used for the short proof of Part 4 alone. Nothing else there is replayed.
      The cut is a reading of script 19, which is private until the owner publishes it.
OLDER Every other folder in LOGS whose name begins stage5a, stage5b, stage5c1 or stage5c2.
      Read only. Write nothing there and delete nothing there.
      LOGS/stage5c1-data holds a copy of the owner's two keys. Do not open LOGS/stage5c1-data/.env.
      Do not use an older data folder as your own: 5d builds its own.
CASES /home/indy/Work/openconsult-review/v2-logs/stage3-cases
      Read only. The cases of the engine bench. 5d uses consultation 495 alone, with the bench's own switch for one case.
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
      Never read V1/.env or any other file that holds a key or a token.
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. The record of v1's benches. Change nothing there. Run nothing there.
The folder of old recordings, recordings-backup-2026-10-04, is not needed. Open nothing in it.

WHAT YOU AND COWORK LEFT IN LOGS THAT 5d USES
Your own files of the bench of 7 Oct. Read them, and copy what you need under new names that begin stage5d.
Do not change the files of 7 Oct themselves.
   stage3b_bench2_engines.sh   how each engine was started, stopped and seen to be off the card
   stage3b_bench2_gpu.sh       the sampler of the card and the load log
   stage3b_bench2_run.sh       the driver: steps that can be started again, and what happens when one fails
   stage3b_run_compact.sh      your driver of 6 Oct: how the machine's own switch for staying awake was read, set and set back
   stage3b_bench2_proofs.py and stage3b_bench2_overlap.py   the proofs made on each start
   STAGE3B_BENCH2_REPORT.md    the report of that bench
   stage3b.log, at the line that begins with vLLM's own start-up figures: what vLLM said on 6 Oct that it needs
The models of 7 Oct, which 5d uses unchanged:
   On the Ollama service: openconsult-bench-gemma4:26b-google-q4_0
      digest 9813ae3a5cf9ef2c1f20472d76c3b012b7b0a7bab2285c2f825244331d1db89c
   On the second, private Ollama: the same tag, digest b7b2309642163e7ca6042374fd653f3725c1e81cfe447c501bcdbbd43242d9a8
   On vLLM: xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct, revision 2096d38dad51a19b8e982b44241c47102a8bbb00,
      started with the one switch of 7 Oct for a compact answer (spec 15.8, ruling 22).
Cowork's tool for the Windows faults: LOGS/cowork_winsim.py. You used it on 13 Oct. It is used again in Part 4.
Your reports of 5c are LOGS/STAGE5C1_REPORT.md and LOGS/STAGE5C2_REPORT.md. Read in each what it says 5d should know.

WHAT TO READ IN V1
V1/app/rag.py
   _embed_query: the words that go before a search, and the call to the embedding model.
   answer_for_conditions and search: a search is one call for each condition, with the condition's name as the question.
V1/scripts/ingest_guidelines.py
   embed_documents: the form of a passage, and the batches of 16.
Nothing else of v1's guideline search is carried. No corpus, no index, no summary and no page.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 10, 11, 13.4, 15.3, 15.4, 15.7, 15.8 and 15.9.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 3, 7, 8 and 9.
   Read the code 5d is built on, and its tests: everything in V2/openconsult/bench and V2/openconsult/llm,
   and in V2/openconsult/speech the door, the worker, the environment and the choices.
2. Check the spec with sha256sum. It must be:
   634dc386886b3827b4aa2e3915f3605dff57d3f162a2b5c7f06d152ad3ab6187  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is 06add92e860ef38342897f4afb3de01c46a8a47e.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Make an empty file LOGS/stage5d-start.marker. Every file you write in LOGS after this is newer than it.
   Check the two files of REC named above with sha256sum. If one differs or is missing, stop and report.
   Write these lists of names, sizes and times of last change. You compare each at the end.
   LOGS/stage5d-rec-before.txt: every file in REC.
   LOGS/stage5d-older-before.txt: the top level of every OLDER folder. Open no file there.
   LOGS/stage5d-real-before.txt: the owner's real data folder, /home/indy/.local/share/openconsult. Open no file there.
   LOGS/stage5d-cache-before.txt: this machine's shared model cache.
   LOGS/stage5d-eng-before.txt: every file in ENG but its caches and its run folders, with the sha256 of each model file.
   LOGS/stage5d-read-before.sha256: the sha256 of every file in CASES and of each file of 7 Oct in LOGS that you read.
7. Look, read only, and write what you find in your log:
   whether anything answers on http://127.0.0.1:8000 (that is the v1 service; it should be off);
   the graphics card's memory, used and free, and every program on it (nvidia-smi);
   the free space on the disk that holds LOGS and on the disk that holds ENG;
   whether the Ollama service answers, its version, what it holds loaded, and every model it has, each with its digest.
   Keep that list as LOGS/stage5d-ollama-before.txt. These two must be in it:
   openconsult-bench-gemma4:26b-google-q4_0 and embeddinggemma;
   in ENG: vLLM's version from its own program, the folder of the repack at its revision, and the folder of the
   private Ollama with its model;
   whether the models of the WhisperX choice and of the Nemotron choice are in this machine's shared model cache,
   each with its revision and size;
   whether the machine is set to stay awake, and whether a screensaver is running;
   what the read-only command tailscale funnel status says. The spec asks that Funnel is off for 5d (15.9, ruling 6).
   If that command asks for sudo, do not run it, and write that it could not be read.
   Change nothing. Do not stop here whatever you find: the gate is in Part 4, and it asks for what you found here.
   Never print a token. Never read a file that holds one.

RULES
1. Write only in V2, in LOGS under names that begin stage5d or STAGE5D, and in ENG as THE FOLDERS says.
   Never in V1. Never in OLD. Never in REC, in CASES or in an OLDER folder.
   Two things are not a breach: the system's temporary folder, and the machine's own switch for staying awake,
   which the driver may set for the long run and must set back after it.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
   Install no system software.
   THE OLLAMA SERVICE. Change no setting of it. Pull, make, change and delete no model in it.
   You may ask it to load and to unload a model it already holds, and to answer. Nothing else.
   The second, private Ollama is started and stopped as on 7 Oct: from ENG, on 127.0.0.1 port 11500,
   with its own folder for models, taking two calls at once (spec 15.8, ruling 13). It is not the owner's service.
   vLLM is started and stopped as on 7 Oct: from ENG, on 127.0.0.1 port 8172. Every engine listens on 127.0.0.1 only.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1. Port 8001 and the real data folder are for the owner's own use.
   Your working data folder is LOGS/stage5d-data. The results of the test go to LOGS/stage5d-run.
   The results of the short proof go to LOGS/stage5d-proof.
6. Until the gate for the card in Part 4 is passed: start no engine, load no model on the card or on the processor,
   build no speech environment and no embedding environment, and fetch no model. Parts 1 to 3 need none of these.
   The fresh Python of Part 4, item 2, holds the base app alone and is not meant by this rule.
   No speech model is downloaded in 5d: every one is already on this machine.
   One model is fetched from outside in the whole run: EmbeddingGemma 2, in Part 4, item 6.
   For your plan you may read pages: the makers' own pages for vLLM, Ollama, EmbeddingGemma 2 and
   sentence-transformers. Reading a page is not fetching a model.
   uv may reach the package index when it writes a lock file and when it builds an environment from one.
7. KEYS AND TOKENS. 5d needs no key. Read no file named .env, anywhere. Copy none.
   Open no connection to either cloud speech service.
   Never read, print or pass on a Hugging Face token. The usual library sends a stored token by itself:
   make the fetch of EmbeddingGemma 2 with that switched off, and show in your plan how.
   If the fetch then asks for an account, a token or a click on a licence, stop and report.
   Do not look for another source of the model.
8. WHAT LEAVES THE MACHINE. Nothing of ours. No sound, no transcript, no reply and no word of a case.
   Every engine and every model runs on this machine.
   The only connections to the outside are: the pages read for your plan; the one fetch of EmbeddingGemma 2;
   and uv. None of them sends anything of ours.
   While a setup runs, the workers of the bench open no connection to the outside. Record it as in 5c, and prove it.
   vLLM is started as on 7 Oct, with its usage reports and its reach to the model hub switched off. Your start of
   7 Oct set them in the engine's environment: keep them, and show the start with them in your plan.
   The Ollama service is the owner's own and cannot be recorded without sudo. Do not try. Say so in your report.
9. WHAT STAYS PRIVATE. Recording 473 is two people reading a script. No word that was said in it goes into V2,
   into a commit or into chat. The same holds for every page a speech choice writes in this run,
   from recording 473 and from the 60-second cut, and for every word of script 19.
   What you find goes into your log and your report in LOGS. Chat gets counts and figures.
   No file of results, no sample of the card and no line of a log goes into V2.
   The figures of 5d go into HANDOVER.md, as for every step. The files they come from do not.
   Nothing you write for a commit names a folder of this machine that V2 does not name already, and nothing names the machine.
   V2_SPEC.md and the copy of this prompt are committed as they were given to you, and are not meant by that.
10. TEXT THAT A MODEL READS (spec 15.8, ruling 1; 15.3). You never write or change a word a model reads.
    No prompt file changes, and the two prompt hashes of stage 3 stay as they are.
    A search is sent in v1's form and in no other. Before the name of a condition stand exactly these words,
    with one space after the colon at their end:
    task: search result | query:
    A passage, for the side reading alone, is sent in v1's form: the word title, a colon and a space, the file's name,
    then a space, an upright bar and a space, then the word text, a colon and a space, and the piece.
    The names of the conditions are those of the public bench, as the details of 5d say. You write none yourself.
    If you need a word that this prompt and the details do not give, stop and report.
    No speech choice is given any text, as before.
11. The rulings are never worked round. If something cannot be done as a ruling says, stop and report.
    One case is named in ruling 24, and it is settled in Part 4, item 7, with the model alone on the machine:
    if Ollama's own list of loaded models does not show the first EmbeddingGemma where it was asked for, stop and report.
    Do not put it there by another way. In the long run it is different: a model that is not where its setup
    asked misses line one, and the driver goes on (rule 22).
12. Before each commit, run the private word check on the staged files. It must print nothing:
    git diff --cached --name-only -z | xargs -0 grep -n -i -w -F -f /home/indy/Work/openconsult-review/v2-logs/private-words.txt
    If it prints a line, stop and report. Do not edit a file to make it pass.
    Never copy the word list, or any word from it, into V2 or into a commit message.
13. Each commit: one logical change, the suite green before it, the why in the message.
    No personal names and no host names in a message.
    Each commit message ends with this line, after one empty line (spec 15.6, ruling 3):
    Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
    That is the only address allowed in a commit message.
14. Commands and short results go to LOGS/stage5d.log. Long output never goes into chat.
15. Nothing is built switched off, and nothing is built for a later stage (R31).
    Nothing of 5d is built into the app. The app cannot reach the embedding worker, the searches, the judging of
    the four lines or any engine but its own: no command of the app names them and no setting can. Tests pin it.
    Nothing changes in V2/openconsult/speech, V2/openconsult/llm, V2/openconsult/consult or V2/openconsult/prompts.
    If you judge that something there must change, say what and why in your plan, and wait.
    The guideline search of the app is stage 8. 5d builds no index, no corpus and no lookup.
16. Nothing in the base app assumes Linux. The bench's commands, the scoring, the made-up workers and the suite
    must run on Windows and macOS. The suite needs no graphics card, no engine, no speech library,
    no embedding model, no key, no internet and no recording. It must pass on GitHub's machines.
    The base app gains no heavy library: no PyTorch, no numpy and nothing that brings them (spec 5.1; V1_LESSONS 7.1).
    The worker of EmbeddingGemma 2 needs such libraries, so it runs in an environment of its own,
    built from a lock file in the repo, as the speech workers are (spec 6.2).
    Four rules for tests, from the Windows checks of 5c: a file whose bytes are hashed is written as bytes;
    a path is compared by its parts, never as a string; a database or a file is closed before it is removed,
    renamed or written over, and before the folder that holds it is removed; and a text file is opened with its
    encoding named. A file that is hashed is marked in .gitattributes so that Git never changes a byte of it.
    Keep the list of every place where the three systems differ, and say for each how you know it works.
17. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
18. What a model writes, what a speech model hears and how fast a machine is are never asserted in the suite.
    They are measured in Part 4 (spec 5.2).
19. In the shared model cache, delete nothing, change nothing and add nothing.
    EmbeddingGemma 2 goes into LOGS/stage5d-data, and its worker loads it from there with the network off.
20. The four speech choices behave as they do today. No test of an earlier stage is weakened or deleted.
21. Recordings are read, never written. A result is never written over. The bench refuses to write its results
    into the repo, into the owner's own data folder, into the data folder it was given for its workers,
    or into a folder that holds recordings.
22. A call that fails is kept as failed and is counted. Nothing is asked a second time in silence.
    In the long run a setup that does not fit, or a part of it that will not start, is a result and not a reason
    to stop: it is kept with its reason, the card is freed, and the driver goes on.
23. No comment, no test name and no message cites a private plan review or this prompt by a private name.
    A comment gives the reason itself, or cites the spec or V1_LESSONS.
24. THE CARD IS SHARED ONLY BY WHAT A SETUP NAMES. While a setup or a base line runs, nothing else of yours is on
    the card and nothing else of yours is busy on the machine. Between two setups everything is unloaded
    and the card is seen to be free before the next begins.
    While the long run goes, you look at one log file at long intervals, a quarter of an hour or more,
    and you run nothing else. The owner will have left the machine alone.
25. If a step of Parts 1 to 3 or a check of Part 4 fails, stop and report. A check that asks for one example of
    something is not failed when there is none to find: say that there was none.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 5d: the spec, with part two of 5c folded in, the rulings of 5d and its details
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 5d: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_05D.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE5D_PLAN.md. It holds:
1. The files you will write or change, each with its job in one line and its expected size.
   The total you expect to add to the app's side and to the tests, set beside today's sizes.
2. What the makers' own pages say today, each with the page's address and the sentence quoted:
   vLLM, for the version in ENG: the two options that set its room (the share of the card, and the size of the cache
   in bytes), their defaults, and what each does when another program is on the card. Set the installed program's own
   help text beside the page.
   Ollama: what its list of loaded models gives for a model, and which of its fields say where the model sits;
   what the call for embeddings takes; and whatever its pages say of the option num_gpu. On 13 Oct Cowork found that
   option in one example only, with no meaning given.
   EmbeddingGemma 2, on Google's own page on Hugging Face: its licence; whether the page asks for an account or a
   click before a download; the revision you will pin; the files and their sizes; how the text part alone is loaded,
   in the page's own words; the number formats it allows and forbids; and the words it puts before a search.
   sentence-transformers and the libraries under it: the versions that know this model.
3. vLLM's room. Which of the two options you use, and why. How the least room for a context of 16,384 tokens is found:
   the steps, the most starts you will make, and what in vLLM's own lines at its start tells you. The two proofs
   of the details. What you expect the figure to be, from the lines of 6 Oct in stage3b.log.
4. The four ways of the language model. For each: the exact start line or the exact call, set beside its line of
   7 Oct, with what differs. The model, its digest, the port, the context. How each is stopped and the card seen to be free.
5. The first EmbeddingGemma through the Ollama service. The call for a search on the card and on the processor,
   each written out in full. How long the model is kept loaded. The proof from Ollama's own list for each of the two.
   What is done between two setups so that the model is truly loaded again in its new place.
6. The worker of EmbeddingGemma 2. Its environment: where the lock file lives in V2, the Python, the libraries
   with their versions and licences, and the size you expect on disk. How the model is fetched once into
   LOGS/stage5d-data at the pinned revision, and how the worker then loads it with the network off.
   How only the text part is loaded. The device and the number format on the card and on the processor,
   and the test that pins that float16 is never used. How the bench talks to the worker, what the worker
   says about itself, and how it is stopped. The made-up worker of the suite.
7. The searches. The 11 lists of names: how they are taken from the public bench in V2/engine-bench
   (the arm ollama-google-file, consultation 495, chain A1, the assessment of each of the 11 passes),
   where the lists live in V2 as a file, and the test that proves the file is what the public data holds.
   The exact bytes sent for one name, for each of the two models, written out in full.
   Each name goes in a call of its own, for both models. The check of a vector, and what a vector that fails it counts as.
   The rule of every 5 seconds, and what happens when a search takes longer than that:
   a second search never begins before the first has ended, and each late start is counted. A list with no name.
8. One setup, from the free card to the free card: each step with its command and the seconds you expect.
   How the replay of the recording, the three chains and the searches run side by side, each by its own command,
   and how their clocks are set beside each other afterwards. The chain after Stop.
   What reads Ollama's list, vLLM's health and the card's list of programs, how often, and where each reading is kept.
   The folder of a setup's results, file by file.
   What is done when a part of a setup will not load or will not start.
9. The base lines, before and after, and the steadiness rule of the details, with one worked example.
   What line three does for a way that lacks one of its two base lines. The pace of the searches in a base line.
10. The four lines as code. For each line one made-up setup that meets it and one that misses it, with the reason
    the report would give. For line three: the typical pass and the base line it is set against.
    For line four: which stored field of the speech results serves for Nemotron and which for the WhisperX choice,
    and why it is the same field in the setup and in the base line; how the stretch in which the language model
    is busy is found from the stored times; how the lines of that stretch are picked in the setup and in the base line;
    the two halves; and the two tests of 1.0 second, each with a worked example.
    How a speech worker's own word that it ran out of memory, live or at Stop, is read, and which line a Stop
    with no final transcript misses. The three words of the report: works, not working, and not judged, with the line.
    What line four does for a speech choice that lacks one of its two base lines.
11. The way round that is tried, for the WhisperX choice at Stop: what in the results calls for it, on which engine,
    how the language model is taken off the card and put back on each engine, what is timed, and how line one
    is read with the one exception the details give. How the report keeps a way round apart from a setup,
    and how it points from a setup that did not work to the same setup with EmbeddingGemma on the processor.
    The ideas that are not tried, as the details list them, and what vLLM's own lines say a context of 8,192 tokens would free.
12. The side reading: how the 250 pieces are cut, from which public files, and the proof that no private text is in them.
13. The commands of 5d, with their exact words, and what each writes and where.
    The one command that judges the stored results and writes the tables.
14. The private files of the run, in LOGS: the starts and stops of the engines, the sampler, the load log and the driver.
    The driver's steps in order: the base lines with the side reading, the 32 setups, the base lines again,
    and then the way round where the results call for it.
    The order of the setups, and why. The minutes you expect for each kind of step, and the hours in all.
    How a step that failed is kept, how the run can be started again without doing a finished step twice,
    and how the driver outlives your session.
15. One table of what you expect on the card, in MiB, at each step of each kind of setup, written before anything
    is measured: the language model, the embedding model, the speech worker at its highest, and what is left.
    Say which setups you expect not to fit. The card's own sampler writes MiB: never call those figures GB.
16. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2; V1_LESSONS 8.8).
17. Every new sentence the bench will show to a person, in one list, so the owner can correct the wording.
18. The commits you will make, in order.
19. The list for rule 16: where the three systems differ.
20. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
21. Whether 5d fits in one session. The long run takes hours: say how you wait for it, and what a new session
    would have to read to carry on from the driver's log if this one ended.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what the details of 5d say. This is the suggested order. Your plan may change the order and say why.
1. One tidy-up commit, of tests only. Four reads of a JSON file in tests/test_voice.py, tests/test_speech_tables.py and
   tests/test_speech_arms.py name no encoding. Name utf-8 in each. No assert changes.
2. The 11 lists of names as a file, the form of a search, and the check of a vector.
3. The two ways to an embedding model: the call to Ollama, and the worker of EmbeddingGemma 2 with its lock file
   and its made-up twin. Load and fetch nothing yet. NOTICE gains EmbeddingGemma 2 with its licence, and each
   library the new worker brings, in the commit that adds the worker.
4. The command that makes the searches, every 5 seconds, and the side reading.
5. What reads the lists and the card, and the judging of the four lines, the steadiness rule and the way round.
6. The command that writes the tables.
7. The private files of the run, in LOGS. Start nothing yet.
8. The documents, in the last commit, which is made in Part 4, item 17, so that the measurements are in it:
   CLAUDE.md: under Running it, the new commands. It is 99 lines today and must stay under 100: make room, lose nothing a builder needs.
   README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
   HANDOVER.md: a new entry at the top. What was done, the rulings 5d rests on in one line each,
   the measurements, and what this stage has made untrue. It is 360 lines today and must stay under 500.

PART 4. THE CHECKS
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. A fresh Python with only the base app installed: the app starts, answers and stops, and no speech library
   and no embedding library can be imported.
   Run the start step of the GitHub check as it is: uv run python .github/scripts/start_check.py
   In the same fresh Python, the bench command prints its help, and the judging of 5d runs on made-up results.
Item 3. The tables of the database: say whether any changed. None is expected. If one changed, stop and report.
Item 4. The Windows faults. Run the suite once under Cowork's tool, from V2:
   PYTHONPATH=/home/indy/Work/openconsult-review/v2-logs uv run pytest -p cowork_winsim
   It must pass. If a test fails there and passes plainly, the test has a Windows fault: put it right.

THE GATE FOR THE CARD. Items 5 to 10 build environments, start engines and load models. Before item 5:
   Ask http://127.0.0.1:8000 once. If anything answers, the v1 service is running.
   Then print exactly this line and stop: Waiting for v1 to be switched off.
   The owner will type: v1 is off. Go.
   If step 7 read that Funnel is on, or could not read it, print exactly this line and stop:
   Waiting for the owner to say that Funnel is off.
   The owner will type: Funnel is off. Go.
   When nothing answers on port 8000: if step 7 found that the Ollama service, one of its two models,
   a speech model of the two local choices, vLLM in ENG, the repack, or the private Ollama with its model
   is not on this machine, stop and report. Nothing is fetched or made to make up for it.
   Then ask the Ollama service to unload whatever it holds, and read the card.
   If more than 1,500 MiB of the card is in use, stop and report.
Item 5. Build the WhisperX environment and the Nemotron environment with the app's own command, into LOGS/stage5d-data.
   Write the times and the sizes on disk in your log. Then the self-test of each of the two choices on that folder. Each must pass.
Item 6. Build the environment of the worker of EmbeddingGemma 2, and fetch the model: the one fetch of 5d.
   If it asks for an account, a token or a click, stop and report.
   Write in your log: the address, the revision, the size and the sha256 of the weights file, and the licence as the page gives it.
   Then, alone on the machine, the worker on the card and then on the processor: one list of names each.
   Write the device, the number format, the check of the vectors, the seconds, and the card's memory with the worker loaded.
   Every connection attempt and every name lookup of the worker is recorded while it runs: the record must be empty.
Item 7. The first EmbeddingGemma through the Ollama service, alone on the machine: on the card, then on the processor.
   One list of names each. For each, copy into your log what Ollama's own list of loaded models says of the model,
   and the card's memory. If the list does not show the model wholly on the card when it was asked for there,
   or wholly on the processor when it was asked for there, print exactly this line and stop:
   Ollama did not put the model where it was asked.
Item 8. vLLM's room. Find the least room as your plan says, and make the two proofs.
   Write in your log every start you made with vLLM's own lines, the figure you settle on, and the card's memory with vLLM alone at that figure.
   Then each of the four ways once, alone: the engine's version, the model's digest, the context of 16,384,
   and one chain of consultation 495. Stop each engine and see the card free.
Item 9. One short proof before the long run, to find a broken step. Its results go to LOGS/stage5d-proof.
   Four short setups on the 60-second cut, each with one chain in place of three. Three on Ollama one after another:
   Nemotron with the first EmbeddingGemma on the card; Nemotron with EmbeddingGemma 2 on the processor;
   and the WhisperX choice with the first EmbeddingGemma on the processor.
   One on vLLM one after another, at the room of item 8: Nemotron with the first EmbeddingGemma on the processor.
   Run the four through the driver itself, in that order, so that its going on after a setup that did not fit is seen.
   The proof shows five things and no more: that every part starts and runs beside the others, on each engine;
   that every file of a setup is written; that the command for the tables reads them; what happens when the pass
   at Stop of the WhisperX choice meets the language model on the card; and that the driver goes on after a failure.
   It is not a setup of the details: the chain may still be running when the cut ends, and there are no base lines,
   so lines three and four must read as not judged.
   Run the command that writes the tables on the proof's folder. Read what it wrote against the stored files.
   If the WhisperX choice ran out of memory at Stop, check that the tables say so under line one.
   Ask each new command of 5d for a result folder inside V2, inside LOGS/stage5d-data and inside REC,
   and for one result a second time: each must be refused, and nothing written.
   Unload everything and see the card free.
Item 10. THE GATE FOR THE MACHINE. The long run needs the machine to itself for hours.
   Print exactly these two lines, with your own figure for the hours, and stop:
   Ready for the long run. It needs about N hours with nobody at the machine.
   Type this when the machine is free for the run: The machine is free. Go.
   The owner will switch the monitor off and close his other programs. He starts the run when it suits him.
Item 11. THE LONG RUN. When he has typed it: look whether a screensaver is running.
   If one is, print exactly this line and stop: A screensaver is running.
   The owner will end it and type again: The machine is free. Go.
   Look whether the machine is set to stay awake. If it is not, the driver sets that with the machine's own
   switch for the run and sets it back at the end, as your driver of 6 Oct did. If it is, leave it as found.
   While that switch is set the machine starts no screensaver of its own: say in your plan how you know.
   Write in your log what you found and what was done.
   Start the sampler and the driver, so that they outlive your session, and print exactly this line:
   The test of 5d has started.
   The driver runs, in this order: the base lines, with the side reading once; the 32 setups; the base lines again;
   and then the way round, on each engine where the results call for it.
   It frees the card before every step and sees that it is free.
   A sampler writes the card's memory every 2 seconds, in all and for each program on it (nvidia-smi, read only),
   and the load log names the three busiest programs once a minute.
   Every connection attempt and every name lookup of the workers is recorded: those records must be empty.
   The driver needs nobody. Wait for it to end, as rule 24 says.
Item 12. When the driver has ended: stop the sampler; see that no engine of yours runs, that the Ollama service holds
   nothing loaded, that the card is free, and that the switch for staying awake is as you found it. Write in your log which steps ran, which were kept as failed and why,
   and whether the load log shows a screensaver or a busy program that was not part of the test, with the setups it touched.
Item 13. Judge the results and write the tables, with the one command, from the stored results alone.
   Run that command a second time into another folder in LOGS: the two sets of tables must be the same, byte for byte.
Item 14. Read your own tables as a doubter would. Open the stored files and check by hand, where there is one:
   a setup that the tables say works, on each of its four lines; a setup that missed each of the four lines,
   with its reason; a model that Ollama's list showed split or gone; a way of the language model whose two base lines
   differ by more than 0.25 seconds, and that its setups read as not judged; the way round,
   and that the tables never count it as a setup; a search that started late.
   Set the card's memory of three setups against the sampler's own file.
   Set your table of item 15 of the plan, what you expected, beside what was measured, and say where you were wrong.
   Write what you found in your report. If the judging is wrong, say so plainly.
Item 15. Before the last commit, search the tests you added or changed for the four faults of rule 16,
   and run the suite once more under Cowork's tool, as in item 4. Write in your log what you looked at and what you found.
Item 16. The suite once more, plainly, three times. Each must pass.
Item 17. Make the last commit, the documents, with the measurements in it.
Item 18. Nothing private is in V2. In the lines that the commits of this run add
   (git log -p 06add92e860ef38342897f4afb3de01c46a8a47e..HEAD, the added lines only): no sound file, no result file,
   no sample of the card, no line of a log, and no run of six words in a row from any page that a speech choice
   wrote in this run, from recording 473 or from the 60-second cut. Search with a script that prints counts only.
   Every count must be 0. The script of recording 473 is one of the public cases, so the search is of added lines
   alone, and never of the whole tree.
   No added line names a folder of this machine that V2 did not name before, and none names the machine.
   Two files are outside that last check, because they are committed as they were given to you:
   V2_SPEC.md and the copy of this prompt.
Item 19. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. The two files of REC have their checksums, and the list of REC made now equals
   LOGS/stage5d-rec-before.txt, line for line. The same for the list of the OLDER folders.
   The files of LOGS/stage5d-read-before.sha256 still pass sha256sum -c.
   Make the lists of the owner's real data folder and of the shared model cache again. If one differs from its
   list of the start, write what differs and whether any command of yours could have written there.
   The owner may have used his own app meanwhile: a change that is his is reported and is not a failed check.
   The list of ENG made now equals LOGS/stage5d-eng-before.txt: no model file and no engine file changed.
   No file named .env was read. Port 8000 and port 8001 were never used by you.
   No setting of the Ollama service changed, and its list of models equals LOGS/stage5d-ollama-before.txt, name for name and digest for digest.
Item 20. Write LOGS/STAGE5D_REPORT.md.
   First, the most important for the patient, in one table. A row for each of the eight pairs of a way of the
   language model and a speech choice. A column for each of the four embedding setups. In each cell: works,
   not working with the number of the first line it missed, or not judged with the number of the line.
   Under the table, in plain sentences: on Ollama, which setups work; on vLLM, which setups work;
   what sharing the card costs in seconds on each, as the typical pass alone and shared;
   and whether the live transcript kept up.
   Then, for every setup that does not work: the reason; the same setup with EmbeddingGemma on the processor,
   where there is one, and whether that works; the way round at Stop, if it was run, with its result against the
   four lines; and the ideas that were not tried, each marked as not measured.
   Say in plain words what the test did not measure: the load is heavier than a real consultation,
   and the time of a search is the model's part of a search, with no lookup in an index.
   Then, each under its own heading:
   did the run go from start to end, and which step failed, if any;
   vLLM's room, with its proofs;
   the base lines, and the steadiness of each way;
   the four lines for every setup, as the bench wrote them, and with them the slowest pass, the time of the alarm's
   answer, the chain after Stop, the searches that started late, and the words that differ from the page of the speech choice alone;
   the card's memory at each step, in all and for each program, in MiB;
   EmbeddingGemma on the card and on the processor, for each of the two models: the memory it frees and the time of a search,
   alone and in a setup;
   the side reading on building an index;
   the WhisperX choice at Stop: the seconds, the memory, and what happened to the other models;
   what vLLM's own lines say a context of 8,192 tokens would free, as an idea that was not measured;
   what item 14 found, with your table of what you expected beside what was measured;
   the commits with their hashes; the files with their line counts; any target missed;
   the tests, each with what it pins; every new sentence shown to a person; the list for rule 16;
   that the owner has no check of his own to run for 5d, because nothing of the app changed, or what he must run if something did;
   the sizes of LOGS/stage5d-data, LOGS/stage5d-run and what 5d added to ENG;
   and what in LOGS and in ENG may now be removed, as one line for each, without removing anything yourself.
   The report holds everything that the details of 5d name. If something there could not be measured, say so in its place.
   Last: anything you flagged, and what the session on the engine choice, stage 6 and stage 8 should know.

FINAL MESSAGE
Twelve lines at most:
whether the run went from start to end, and any step that failed,
on Ollama, how many of its 16 setups work, how many do not, and how many were not judged; the same for vLLM,
what sharing the card costs in seconds, on each engine,
vLLM's room,
EmbeddingGemma on the processor: the memory it frees and the time of a search,
the way round at Stop, if it was run, and what it showed,
that nothing of ours left the machine, that no key and no token was read, and that the Ollama service is as it was,
the number of commits and the last hash,
the number of tests, the suite time, none skipped, and that the suite passed under the Windows tool,
that the private word check printed nothing before every commit,
any target missed and anything you flagged,
then this line for the owner: Tell Cowork: Stage 5d done. Do not push yet.
