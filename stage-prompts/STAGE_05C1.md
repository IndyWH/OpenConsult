STAGE 5c, PART ONE, of OpenConsult v2.0: the replay bench and the transcript marks

WHAT THIS IS
OpenConsult v2.0 is a rewrite, built on the branch v2 in its own folder.
Stage 5 is about speech. It is built in five steps, 5a to 5e. This is 5c, the third, and 5c is built in two runs.
This is part one. 5a and 5b built the one door through which every word of speech reaches the app,
and four speech choices behind it.
Part one builds the replay bench: a banked recording goes through that same door as if it were live,
everything the door gives is kept, and code scores the transcript against the script.
From the patient's side: the bench is how the owner will choose which speech choice hears his patients.
It must show two things above all. Whether any passage a patient said went missing with nothing on the page to show it.
And whether any word was written that nobody said.
In part one the bench is rehearsed on old recordings and on one recording made with machine voices.
It is a rehearsal. No figure from it counts.
No page, no consultation, no recording from a microphone, no call to a language model and no Alba yet.
The spec is V2_SPEC.md. Stage 5 is section 15.9 of it. Read that section first:
rulings 1 to 21, the details of the stage, of 5a and of 5b, and then the details of 5c.
Build what the details of 5c say for part one. Part two is a later run with its own prompt: build nothing of it.
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
V1    /home/indy/Projects/consultation-ai
      Read only. A reference. Change nothing. The only git command allowed there is:
      git -C /home/indy/Projects/consultation-ai rev-parse HEAD
      Never read V1/.env or any other file that holds a key or a token.
OLD   /home/indy/Work/openconsult-review/v1.1-logs
      Read only. The record of v1's speech benches. Change nothing there. Run nothing there.
REC   /home/indy/Work/openconsult-review/recordings-backup-2026-10-04
      Read only. The old recordings, as banked on 4 Oct 2026. Change nothing there. Write nothing there.
      You may open three files in it and no other:
      consultation_462.flac   sha256 ed021c38fc8f82ae7c40c947bc10d67e8ae6e4a2cee65e9086e306bbcd6c45ca   script 01, whole
      consultation_473.flac   sha256 09d3164f50e947c1f42ab76aa173752ba3f163c7c2a369cc35282c02b1d732f5   script 15, whole
      consultation_477.flac   sha256 2fc3c5973ae78dc2928ac566205fa06eee4ec986218495bec8839df6a8b627e0   script 13, to speech 26
      Check each with sha256sum before you use it. If one differs, stop and report.
      Each has two speakers. Each is FLAC, 16 bit, one channel, 16,000 samples a second.

WHAT COWORK HAS LEFT FOR YOU IN LOGS
LOGS/stage5c-cases/speech_marks.json
   sha256 1c21012b3ef867a0290079d5cd8583fda7a5a13231e060c7f04f796638e54360
   For scripts 01, 13, 15 and 19: the drug names spoken with the number of times each is said,
   the names of tests, the speeches that hold a safety net, and the names that are in v1's line.
   Its first entry says how to read it. Use it as it is. If you find it wrong against a script, report it. Do not correct it.
   It names the drugs of script 19, so in part one it stays in LOGS and never goes into V2.
   The suite uses a made-up file of the same form.
LOGS/stage5c-prompts/v1_live_line.txt
   sha256 c72f4adcebbc7907cb6ad55b21c7bc1484f3aa5d2d428d70cf537cf0b2bb9981
   v1's line, with one line break after it. The same text stands in the details of 5c between two fence lines.
LOGS/stage4-scripts/19_medication_review_uk.md
   sha256 1388c5fd6d4fe1c6f058903dceceda4e2bf455e9a7f37fc6a5c6035ce34024f6
   Script 19, the medication review. It is private until the owner publishes it. It never goes into V2.
Scripts 01, 13 and 15 are already public, in V2/engine-bench/cases, the same bytes as in V1/mock_consultations.

WHAT TO READ IN V1 AND IN OLD
V1/speech_nemotron/worker.py, nemotron_stream.py, setup.sh and README.md
   v1's Nemotron worker. It runs the PAIR: the 3.5 model tied to the speaker model.
   In part one that pair is one arm of the bench, and only of the bench (spec 15.9, rulings 8 and 15).
   setup.sh pins the NeMo commit and the revisions of the models.
V1/app/transcription.py
   The constant CLINICAL_INITIAL_PROMPT, and how the live model is given it. That is v1's line (ruling 3).
   Its default value, with one line break after it, must have the sha256 given above. Prove it in your plan.
V1/app/speech.py and V1/NOTICE, the parts on Piper
   How v1 keeps Piper at arm's length, which voice it uses and where the voice file is.
OLD/TASK17_SCRIPTED_BENCH.md and OLD/TASK17_PROMPT.md
   How Task 17 ran four arms on seven scripted recordings, how it cut the reference for 477,
   and what it found. Part one's bench is its successor. Read the report. Run nothing of it.
OLD/TASK18_DROPPED_SPEECH.md
   What the line did to the pass at Stop, and why v2 gives it to the live model only, and only in one arm.
OLD/TASK16_RECORDINGS.md
   What is known of each old recording: its script, its date, its capture.
v1 has its own Nemotron environment in the home folder. Do not use it and do not change it.

BEFORE YOU START
1. Read V2/CLAUDE.md and V2/HANDOVER.md.
   Read V2/V2_SPEC.md sections 4, 5, 6, 11, 13, 15.3, 15.4 and 15.9.
   Read V2/V1_LESSONS.md: the twelve that matter most, then sections 1, 2, 7, 8, 9 and 15.
   Read the code of 5a and 5b: everything in V2/openconsult/speech, and their tests.
   Read the bench kit of stages 3 and 3b: everything in V2/openconsult/bench, and its tests.
   Part one is built on both and in their way.
2. Check the spec with sha256sum. It must be:
   72b3b2ab135177070a0760dbdd370908b9b51167d9e54b8badae066a587c6d86  V2_SPEC.md
   If it differs, stop and report. Do not go on.
3. Check V2. The branch is v2. HEAD is 6676391e3681b4af05b7b56d27e4e3601e52921b.
   git status --porcelain shows one line only: V2_SPEC.md modified.
   If anything else is changed or untracked, stop and report.
4. Run the one allowed command in V1. It must give b2e61d0705ec593cfde70638429e287e68c56f1c.
   Keep the value. You check it again at the end.
5. Check that uv is installed: uv --version. If it is not, stop and report.
6. Make an empty file LOGS/stage5c1-start.marker. Every file you write in LOGS after this is newer than it.
   Write a list of every file in REC with its size and its time of last change, into LOGS/stage5c1-rec-before.txt.
   Write the same kind of list of the owner's real data folder, /home/indy/.local/share/openconsult,
   into LOGS/stage5c1-real-before.txt: names, sizes and times only. Open no file there. You compare both lists at the end.
7. Look, read only, and write what you find in your log:
   whether anything answers on http://127.0.0.1:8000 (that is the v1 service; it should be off);
   the graphics card's memory, used and free (nvidia-smi);
   the free space on the disk that holds LOGS;
   whether the models of the WhisperX choice and of the Nemotron choice are in this machine's shared model cache,
   and whether v1's 3.5 model is there, each with its revision and size;
   which tool on this machine can turn FLAC into WAV with nothing lost (for example ffmpeg or flac), and its version;
   where Piper is on this machine, its version, and where v1's voice file is.
   Change nothing. Do not stop here whatever you find: the gates are in Part 4.
   Never print a token. Never read a file that holds one.

RULES
1. Write only in V2 and in LOGS. Never in V1. Never in OLD. Never in REC.
   Two things are not a breach: what rule 19 allows in the shared model cache, and the system's temporary folder.
2. Do not change one character of V2_SPEC.md or V1_LESSONS.md. If the spec is wrong or silent, report it.
3. If a choice is a product or clinical judgement, stop and report it. Do not decide it.
4. No git push. No sudo. No service command. Nothing in V1 is written, not even by git.
   Install no system software. Pull, delete, create and change no model in Ollama.
5. Never use the owner's real data folder, and never use port 8000 or port 8001.
   Port 8000 is v1. Port 8001 and the real data folder are for the owner's own check.
   Your own working data folder is LOGS/stage5c1-data. The rehearsal's results go to LOGS/stage5c1-rehearsal.
   The recordings you make or convert, and the banked list of the rehearsal, go to LOGS/stage5c1-recordings.
   There are two exceptions, and both are named in this prompt: the list of names of step 6 above,
   and one copy of one file at the gate for the keys in Part 4.
6. Until the gate for the card in Part 4 is passed: load no model on the graphics card,
   build no speech environment, and download no model. Parts 1 to 3 need none of these.
   Until the gate for the keys in Part 4 is passed: open no connection to either cloud service.
   Parts 1 to 3 need none: the made-up service of 5b stands in for both, inside the suite.
   A voice for Piper is fetched only in Part 4, item 9, into LOGS/stage5c1-voices, and nowhere else.
7. THE KEYS. The owner's two keys are secrets. Never print one. Never read the file that holds them into chat,
   into your log, into your report or into a commit. Never put a key on a command line.
   You may count lines in that file by name. You may not show a value.
   No key, and no part of one, goes into V2, into any log, into the plan, into a result file or into the report.
8. THE ADDRESS. Nothing in 5b's rule changes. Sound goes to a cloud service through its EU address and through no other.
   The four rules of ruling 9 hold for every cloud arm of the bench: the EU address only, the medical option on,
   who spoke live, and no word list. The bench adds no option and takes none away.
9. WHAT LEAVES THE MACHINE (ruling 14). The only sound you send to a cloud service is:
   the made recording, which is machine voices reading script 19, and the test clip of the self-test.
   NO OLD RECORDING IS EVER SENT TO A CLOUD SERVICE. Not a second of it. Not to test anything.
   The old readers were never asked. Code holds this rule (the details of 5c: Consent is held by code), and you hold it too.
   No word that a person said in a recording goes into V2, into a commit or into chat.
   You may read the private result files to check the scoring. What you find there goes into your log
   and your report in LOGS, and nowhere else.
10. TEXT THAT A MODEL READS. No speech choice of the app is given any text: no prompt, no hint, no list of words,
    no custom dictionary, no key terms (rulings 3 and 9). There is one exception, and it belongs to the bench alone:
    the arm WhisperX with v1's line (rulings 3 and 15). That line is v1's, byte for byte.
    You never write or change a word a model reads (spec 15.3). You copy it and prove the copy.
    No prompt file of stage 3 changes. The two prompt hashes of stage 3 stay as they are.
    Part one makes no call to a language model at all.
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
14. Commands and short results go to LOGS/stage5c1.log. Long output never goes into chat.
15. Nothing is built switched off, and nothing is built for a later stage (R31).
    The list of what part one does not build is in the details of 5c in the spec. Read it before you plan.
    One thing may look like it breaks this rule and does not: the check for missing speech.
    The bench needs it now, for hard mark 1. Stage 6 only shows its result on a page.
16. Nothing in the base app assumes Linux. The door, the bench command, the scoring, the made-up workers and the suite
    must run on Windows and macOS. The suite needs no graphics card, no speech library, no key, no internet,
    no recording and no Piper. It must pass on GitHub's machines.
    The base app gains no heavy library: no PyTorch, no numpy and nothing that brings them (spec 5.1; V1_LESSONS 7.1).
    If you judge that the bench needs a library the base app does not have, say which and why in your plan, and wait.
    Keep the list of every place where the three systems differ, and say for each how you know it works.
17. The size targets of spec section 5 hold: no file over 600 lines, no function over 80,
    tests no larger than the app, the suite under a minute.
    If a target cannot be met, report it and say why. Do not squeeze code to fit a number.
18. What a speech model or a service hears is never asserted in the suite. It is measured in Part 4 (spec 5.2).
19. In the shared model cache, delete nothing and change nothing that is already there. You may add v1's 3.5 model to it.
20. THE FOUR CHOICES OF 5a AND 5b BEHAVE AS THEY DO TODAY, but for the two changes the spec orders:
    a session at 48,000 samples a second is now taken by the local workers, and the rule against words
    from silence looks as wide as a choice's times allow. No test of 5a or 5b is weakened or deleted.
    If a test must change because of those two changes, say which and why in your plan.
21. The app cannot reach an arm that belongs to the bench. The tied pair and WhisperX with v1's line are not
    in the table of speech choices, no command of the app names them, and no setting can. Tests pin it.
22. Recordings are read, never written. The bench opens a recording for reading only.
    A result is never written over. The bench refuses to write its results into the repo, into the owner's own
    data folder, into the data folder it was given for its workers, or into a folder that holds recordings.
23. No comment, no test name and no message cites a private plan review or this prompt by a private name.
    A comment gives the reason itself, or cites the spec or V1_LESSONS.
24. If a step fails, stop and report. A check that asks for one example of something is not failed
    when there is none to find: say that there was none.

PART 1. TWO COMMITS BEFORE THE PLAN
Commit 1. Subject: Stage 5c part one: the spec as the 5c brainstorm left it
   V2_SPEC.md only. The spec is committed before the code (V1_LESSONS 11.3).
Commit 2. Subject: Stage 5c part one: the stage prompt
   Copy this file to V2/stage-prompts/STAGE_05C1.md. Prove with cmp that it is identical.

PART 2. THE PLAN, THEN STOP
Write your plan to LOGS/STAGE5C1_PLAN.md. It holds:
1. The files you will write or change, each with its job in one line and its expected size.
   The total you expect to add to the app and to the tests, set beside today's sizes.
2. The banked list: its form, field by field, with one example entry. How the bench refuses a file whose checksum
   differs, a file that is not in the list, and a write where recordings are kept. The guard and its test.
3. Consent held by code: where the list says what a recording's consent covers, where the bench refuses,
   and the test that pins that no worker is started and no connection is opened for a recording that may not leave the machine.
4. The reference: how a script becomes the spoken words with their speakers and speech numbers;
   how the list's notes on speeches read differently change it; how a reading that is not whole is cut after its last speech.
   How a place where every arm agrees against the script is found and reported (13.4, rule 5; the details of 5c: The reference).
   How the drug names and the safety nets of a reading that is not whole are counted from the reference as cut.
5. The replay: how a file is read and fed, piece by piece, at the speed it was spoken;
   what is kept for every piece, at Stop and for the whole recording, as the form of one result file, field by field,
   with the loudness of the sound in the door's own windows;
   how the moment a line's first words showed and the moment it was final are taken, without changing the door;
   what happens when the door gives a failure in the middle of a recording;
   how a run that was stopped carries on with the arms that have no result yet.
6. Sound files: how WAV is read with what the base app has. How the three old recordings become WAV
   in LOGS/stage5c1-recordings, with which tool, and how you prove that nothing was lost.
7. The conversion of the sound's rate, in each of the three local workers (WhisperX, Nemotron, the tied pair):
   the library and the function, with its version and its filter; why the sound stays right
   (nothing above 8 kHz folded back); what a rate other than 16,000 or 48,000 gets;
   and how Part 4 will prove the conversion on made sound.
8. The wider rule: the new thing a choice declares; the figures as named constants with their sources,
   for the four choices and for the two arms of the bench; exactly how the rule's stretch is widened,
   for a line and for text not yet final; what the rule does when the wider stretch reaches past the sound fed so far
   (the details of 5c say: that sound counts as not quiet); and every test of 5a and 5b that is touched.
9. The check for missing speech: the two plain functions, what each takes and gives, the named figures with their
   sources, where the functions live, and their tests. Say plainly what the check on the sound cannot see.
10. The two arms that belong to the bench.
    The tied pair: what is carried from v1's worker and what is written fresh; the 3.5 model with its name,
    revision, size and licence, and the command that fetches it; how it runs in the Nemotron environment of 5b
    behind the same door; what it declares; and the tests that pin that the app cannot reach it.
    WhisperX with v1's line: where the line is kept as a file; the proof that the file, v1's constant and the text
    between the fence lines of the spec are the same bytes; exactly how the live model is given it and the pass
    at Stop is not; how only the bench can ask for it; where the line's hash is kept with every result of the arm;
    and how the test of 5a that pins no text to a Whisper model stays as it is.
11. The scoring, mark by mark, as the details of 5c set it out. For each: the rule in two lines, the named figures,
    and one small worked example with made-up words. Above all:
    the matching, with the table of spellings, and how numbers, units and names with a hyphen are made the same;
    a passage, by the rule of the details (at least 5 more words spoken than the page holds in their place);
    a word from silence: how a pause is found from the stored loudness, what the smallest timed piece of each
    choice is, and how the choice's times widen the test;
    a real word that the rule refused, and an invented word that it let through;
    the list of words that count as a negation, and what counts as a number changed;
    how a drug name and a test name are matched as whole words, and how AssemblyAI's form with brackets counts as caught;
    how the choice's labels are matched to doctor and patient;
    the wait; and how exact a choice's times are, on the made recording and on an old one.
    For the arm WhisperX with v1's line: how its live lines are set beside the live lines of WhisperX.
12. The made recording: the two voices, each with its name, its source, its licence quoted from its own card,
    and where its file will be kept; how Piper is run at arm's length, as the tool on this machine that v1 uses;
    how sound at 22,050 samples a second becomes 48,000; the pauses; the form of the file of true times;
    the length you expect. The script that makes it lives in LOGS, not in V2.
13. The commands of the bench, with their exact words, and what each writes and where.
    The one command that scores the stored results and writes the tables of the report.
14. The rehearsal: the list of its four recordings; the six arms; the order; the minutes you expect;
    the driver, which must run with nobody there; and what it does when one arm fails.
15. Every test you intend, each with the rule, the ruling or the incident it pins (spec 5.2; V1_LESSONS 8.8).
16. Every new sentence the app or the bench will show to a person, in one list, so the owner can correct the wording.
17. The commits you will make, in order.
18. The list for rule 16: where the three systems differ.
19. What Part 4 will load on the graphics card, in what order, and the memory you expect at the highest point.
    What Part 4 will send to each cloud service, in seconds of sound, and what that costs of the free credit.
20. Anything in the spec that is wrong, silent or in conflict. Do not fix it yourself.
21. Whether part one fits in one session. If you judge it does not, name the point where you would split it.
Then print five lines at most, and stop.
Wait for the owner. He will type: Approved. Go.
He may first tell you to read a review file in LOGS. If so, read it and follow it. It may change your plan.

PART 3. THE BUILD
Build what the details of 5c say for part one. This is the suggested order. Your plan may change the order and say why.
1. The wider rule (ruling 12), with the new thing each choice declares. The four choices and their tests.
2. The check for missing speech, as plain functions with their tests.
3. The banked list, its reader, the guard, and consent held by code.
4. The reference from a script, with the cut and the notes on speeches read differently.
5. The replay through the door, with a made-up worker behind it for the suite, and the result file.
6. The scoring, one mark at a time, each with its tests on made-up words.
7. The conversion of the sound's rate in the local workers. Do not load a model yet.
8. The two arms that belong to the bench, and the tests that pin that the app cannot reach them.
9. The commands of the bench, with the one that scores and writes the tables.
10. The documents, in the last commit, which is made in Part 4, item 18, so that the measurements are in it:
    CLAUDE.md: under Running it, the new commands. It is 99 lines today and must stay under 100: make room, lose nothing a builder needs.
    README.md: the line that says what this version can do so far. Draft it. The owner corrects it.
    NOTICE: anything added, in the commit that adds it.
    HANDOVER.md: a new entry at the top. What was done, rulings 12 to 21 in one line each, the measurements,
    and what this stage has made untrue. It is 452 lines today and must stay under 500:
    move the oldest entries to archive/HANDOVER_ARCHIVE.md.

PART 4. THE CHECKS
CHECKS WITH MADE SOUND. Silence, noise, a tone, and the test clip at another rate are not recordings,
   and they are not in the banked list. Feed them with a script of your own, kept in LOGS, straight through
   the door of the arm, as the checks of 5a and 5b did. The bench's replay is for recordings in the list only.
Item 1. The suite is green. Give the number of tests, the time, and the number skipped, which must be none.
Item 2. A fresh Python with only the base app installed: the app starts, answers and stops, and no speech library can be imported.
   Run the start step of the GitHub check as it is: uv run python .github/scripts/start_check.py
   In the same fresh Python, the bench command prints its help, and the scoring runs on one made-up result.
Item 3. If the tables of the database changed: open a database made by today's code at version 3, with a made-up user in it,
   using the new code. The user must still log in. On a temporary folder, never on the real one. If no table changed, say so.

THE GATE FOR THE CARD. Items 4 to 11 build the two speech environments and load models. Before item 4:
   Ask http://127.0.0.1:8000 once. If anything answers, the v1 service is running.
   Then print exactly this line and stop: Waiting for v1 to be switched off.
   The owner will type: v1 is off. Go.
   When nothing answers on port 8000, read the card's free memory. You may then ask Ollama to unload
   gemma4:26b-a4b-it-qat, and nothing else. If the free memory is still less than your plan's figure
   plus 1,000 MiB, stop and report.
Item 4. Build the WhisperX environment and the Nemotron environment with the app's own command, into LOGS/stage5c1-data.
   Fetch the 3.5 model for the tied pair with your bench command. Write the times and the sizes on disk in your log.
Item 5. The two local choices still pass their self-test. Run the self-test of the WhisperX choice and of the
   Nemotron choice on LOGS/stage5c1-data. Each must pass. For Nemotron, write in your log the first word of the clip,
   the time the model gave it, and whether the rule accepted it. With the wider rule it must be accepted.
   If it is not, stop and report.
Item 6. Silence, with the wider rule. Feed 60 seconds of made silence, then 60 seconds of made noise at -50 dBFS,
   then 60 seconds at -30 dBFS, and Stop after each, to each of the four local arms:
   WhisperX, Nemotron, the tied pair, and WhisperX with v1's line. No line may be accepted.
   Write in your log what each model wrote and what the rule refused. If any text is accepted, stop and report.
Item 7. The conversion. With made sound at 48,000 samples a second, through the conversion of each of the three local workers:
   a tone of 1 kHz must come through at its own loudness, within 1 dB;
   a tone of 12 kHz must come through at least 40 dB quieter, and nothing new may appear below 8 kHz;
   the length in seconds must be the same.
   Then the test clip, turned into 48,000 samples a second by your own script in LOGS, through each of the
   four local arms: write the words heard beside the words heard at 16,000.
Item 8. Turn the three old recordings into WAV in LOGS/stage5c1-recordings. Prove that nothing was lost:
   the samples of the WAV equal the samples the FLAC holds. Write the banked list of the rehearsal there,
   with every field the details of 5c name. What is not known of an old recording is written as: not known.
   For the three old recordings the consent covers recording and tests on this computer.
   It does NOT cover a cloud service, and the list says so for each of the three.
   For 477 the last speech read is speech 26 of script 13, on the word of Task 17's report. Item 16 confirms it.
Item 9. Fetch the second voice for Piper into LOGS/stage5c1-voices. Make the made recording, with your script in LOGS.
   Look at it with code, not with a speaker: write its length, its loudest and its typical loudness,
   whether it clips, and the loudness of its quiet parts.
   Add it to the banked list, marked as machine voices, with consent that covers the two cloud services.
   With the same script, cut a second file from it: from its start to the end of the last speech that ends
   within the first 60 seconds. Give that cut its own entry in the list, marked as machine voices and as a cut,
   with the last speech read, and with consent for this computer only.
Item 10. The bench refuses what it must refuse, on the real files. Each must be refused before anything is fed:
   a recording whose checksum in the list is wrong; a file that is not in the list;
   a result folder inside V2, inside LOGS/stage5c1-data, and inside LOGS/stage5c1-recordings.
Item 11. One short proof before the long run. Feed the 60-second cut to each of the four local arms, and score it.
   This is only to find a broken arm before the rehearsal. Write what each heard.
   Its results are kept apart from the rehearsal's. Then ask for one of those results a second time:
   the bench must refuse to write over it.

THE GATE FOR THE KEYS. Items 12 to 14 reach the two cloud services. Before item 12:
   The owner's two keys are in a file named .env in his real data folder. On this machine that is
   /home/indy/.local/share/openconsult/.env
   Count, without showing any value, the lines that give each name a value:
   grep -c -E '^SPEECHMATICS_API_KEY=.+' /home/indy/.local/share/openconsult/.env
   grep -c -E '^ASSEMBLYAI_API_KEY=.+' /home/indy/.local/share/openconsult/.env
   If the file is absent, or either count is not 1, print exactly this line and stop: Waiting for the two keys.
   The owner will type: Keys are in. Go.
   When both counts are 1, make the one copy that rule 5 allows, and nothing else in that folder:
   cp /home/indy/.local/share/openconsult/.env /home/indy/Work/openconsult-review/v2-logs/stage5c1-data/.env
   then chmod 600 on the copy. Never print or show a line of either file.
   Only the app's own module for keys, and your counting script of item 21, read the copy.
Item 12. The two cloud choices still pass their self-test, on LOGS/stage5c1-data. Each must pass.
Item 13. Consent, with the keys present. Ask the bench for each of the three old recordings on each of the two cloud arms:
   six tries. Each must be refused with the reason that the recording's consent does not cover a cloud service,
   before any worker is started. Record every connection attempt and every name lookup made during the six tries,
   as in 5b: the record must be empty. Then ask for the 60-second cut on one cloud arm: refused in the same way.
Item 14. THE REHEARSAL. Start the driver, and print exactly this line: The rehearsal of part one has started.
   The made recording goes through all six arms. The three old recordings go through the four local arms only.
   One arm at a time on the card. A sampler writes the card's memory use to LOGS every 2 seconds (nvidia-smi, read only).
   The driver needs nobody. If an arm fails, its failure is kept and the driver goes on to the next arm.
   Expect about two hours. Wait for the driver to end. Look at its log at long intervals,
   not in a tight loop, and start nothing else on the card meanwhile.
   Every connection attempt and every name lookup of each local worker is recorded while it runs:
   those records must be empty. For each cloud worker the record must hold its EU address and nothing else.
   For each cloud arm, the seconds of sound it was sent must equal the length of the made recording,
   and its result file must name the made recording's checksum and no other. If not, stop and report.
Item 15. Score the rehearsal and write the tables, with the one command, from the stored results alone.
   Run that command a second time into another folder in LOGS: the two sets of tables must be the same, byte for byte.
Item 16. Read your own tables as a doubter would. For each arm and recording, open the result file and check by hand,
   where there is one: a passage the scoring calls missing, a word it calls from silence, a drug name it calls
   caught and one it calls not caught, a line whose speaker it calls wrong, and a sign of the check for missing speech.
   Write what you found in your report. If the scoring is wrong, say so plainly.
   477 has about three minutes of digital silence after the reading ends: say what every arm wrote there.
   Confirm from the results that the last words every arm heard in 477 belong to speech 26 of script 13.
Item 17. The four self-tests once more, on LOGS/stage5c1-data, with the code as it now is. Each must pass.
Item 18. Make the last commit, the documents, with the measurements in it.
Item 19. Nothing private is in V2. In the working tree and in every commit of this run
   (git log -p 6676391e3681b4af05b7b56d27e4e3601e52921b..HEAD): no sound file, no result file, no banked list,
   no file from LOGS/stage5c-cases, and no run of six words in a row from the spoken text of script 19.
   Search with a script that prints counts only. Every count must be 0.
Item 20. git status --porcelain is empty. git log --oneline lists your commits on v2.
   V1 HEAD is the value you kept. The list of REC made now equals LOGS/stage5c1-rec-before.txt, line for line.
   The list of the owner's real data folder made now equals LOGS/stage5c1-real-before.txt, line for line.
   Nothing in the shared model cache was deleted or changed: list what you added to it.
   Port 8000 and port 8001 were never used by you.
Item 21. Write LOGS/STAGE5C1_REPORT.md. Its first line says: THIS IS A REHEARSAL. NO FIGURE IN IT COUNTS.
   Then the most important finding for the patient, for each of the six arms, in one table:
   was any passage missing with no sign, yes or no, and how many; was any word written in silence, yes or no, and how many;
   how many real words the rule refused. Then:
   did the rehearsal run from start to end, and which arm on which recording failed, if any;
   the tables of every mark, as the bench wrote them; what item 16 found;
   the first word of the clip on Nemotron (item 5); the silence checks (item 6); the conversion (item 7);
   what was refused in items 10, 11 and 13; the records of connections of items 13 and 14;
   how exact each choice's times were, set beside the figures of the wider rule;
   the signs of the check for missing speech: how many were right and how many were false, for each arm;
   the models with their names, revisions, sizes and licences; the two voices with their licences;
   anything added to the libraries; the card's memory at its highest; the seconds of sound sent to each service;
   the commits with their hashes; the files with their line counts; any target missed;
   the tests, each with what it pins; every new sentence shown to a person; the list for rule 16;
   the exact commands for the owner's own check, as one block with no quotation marks, in the order he runs them:
   uv sync, then the self-test of each of the four choices on his real data folder;
   the sizes of LOGS/stage5c1-data, LOGS/stage5c1-rehearsal and LOGS/stage5c1-recordings,
   a line saying that stage5c1-data holds a copy of the keys, and the one command that removes that copy alone.
   Part two needs the environments, the recordings and the results: remove nothing else.
   Last: anything you flagged, and what part two should know.
   THE KEYS APPEAR NOWHERE. After the report is written, with a script that reads the copy and prints counts only,
   search for each key's value: every file in LOGS that is newer than LOGS/stage5c1-start.marker, but not the copy itself;
   the whole working tree of V2; and git log -p 6676391e3681b4af05b7b56d27e4e3601e52921b..HEAD.
   Every count must be 0. Add the counts to the report, and search the report once more.

FINAL MESSAGE
Twelve lines at most:
that this was a rehearsal and no figure counts,
whether the rehearsal ran from start to end, and any arm that failed,
for the six arms: any passage missing with no sign, any word written in silence,
that no old recording left the machine, and that sound went to the two EU addresses and nowhere else,
that the keys appear nowhere (item 21),
the number of commits and the last hash,
the number of tests, the suite time, none skipped,
that the private word check printed nothing before every commit,
that V1 HEAD, the folder of old recordings and the owner's real data folder are unchanged, and that ports 8000 and 8001 were never used,
any target missed,
anything you flagged,
then this line for the owner: Tell Cowork: Stage 5c part one done. Do not push yet.
