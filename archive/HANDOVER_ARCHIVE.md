# HANDOVER archive

The older entries of HANDOVER.md, moved here as it passed 500 lines
(spec 5.3). Newest first. Not read by default.

## 2026-10-13. Stage 3c: the engine setting

Built and run on 13 Oct 2026. The plan was reviewed by Cowork the same
day (three changes and five answers); all are in. The proof ran on the
one machine with the v1 service off and Funnel off. The report is
STAGE3C_REPORT.md in the private log folder.

The rulings it builds, one line each (spec 15.8):
- 30: on Linux with a suitable card the engine is vLLM first, Ollama the
  fallback everywhere; vLLM is asked on Linux only, and its room is set
  where it is started (1,400,000,000 bytes of cache for 16,384 tokens).
- 31: the two calls of a pass are sent together on every engine, as the
  pass's own way; the bench keeps one after another for its arms.
- 32: EmbeddingGemma 2 sits on the card when the first sum fits, else on
  the processor; nothing is loaded for it yet.
- 33: Nemotron is the speech choice on a shared card; the WhisperX choice
  is offered only when the second sum fits, else shown as not available.
- 35: all of it in one session, before 5e; the engine bench not run again.
- 36: three things read once at start, never during a consultation; one
  plain sentence for each decision on This machine, the figures in the
  audit log.
- 37: vLLM asked once with the short wait, then Ollama; the choice held
  for the run; a failed call fails and says so with no switch; both
  missing means Start is not offered (the element records it) and the
  app still runs; the app starts no engine.
- 38: each decision is a named element with a state, a reason and its
  figures; nothing is drawn.
- 39: Ollama stays at 0.33.3; nothing of the service changed.
- 40: the suite needs no card, no engine and no model; made-up ones stand in.

What was built (the app without the bench 7,062 lines, from 6,491; the
tests 10,004, from 9,537):
- llm/chat_engine.py and llm/vllm.py, moved from the bench: the vLLM
  engine behind the joint with the request of 7 Oct; the compact answer
  form is set where vLLM is started, so nothing travels in a request.
  The shared engine refuses a call only when the server's context is
  smaller than the call's; the bench's run command refuses an arm unless
  the server runs at exactly 16,384 (the plan review).
- llm/profile.py names the model for each engine in its one place:
  Ollama's own tag, the default, and the repack of ruling 7 on vLLM.
- llm/choose.py: the order of trying, the fit rule (answers, holds the
  model, context at least 16,384), and the stand-in engine when none is fit.
- settings/store.py: ollama_address and vllm_address (127.0.0.1:8172),
  fixed at start; no setting to pick an engine by hand.
- settings/decisions.py and settings/room.py: the three elements, the
  constants with their 5d sources (the language model 18,316 MiB on vLLM
  and 16,568 on the service, Nemotron 3,384, the WhisperX choice 2,452
  live and 9,464 at Stop, EmbeddingGemma 2 1,010, a margin of 1,000),
  the two sums, the programs on the card read with nvidia-smi, the app's
  own engines told apart by name (vllm, ollama, as 5d's sampler recorded
  them), one audit line for each element with the card's total and free.
- consult/cds_pass.py: run_pass sends the two calls at the same moment,
  the alarm first; bench/one_after_another.py keeps the other way.
- web: the language model row, the guideline search row and the speech
  choice row, from the held decisions, on a suitable card only (the
  Ollama lines of 15.7 became the one line); no engine asked at a view.
- bench/cli.py: run and repeat take --data-folder, refused as a result
  folder (R18), and the refusal exits 6.
- words.py: 20 new sentences and 2 changed (the language model row, the home page), drafts for the owner.

Decided in the plan review (Cowork, 13 Oct), as decisions of this stage:
the two context rules kept apart (at least for the app, exactly for an
arm); on a Mac, a small card or no card the three rows are not shown and
the elements are held in state; the audit log's lines at start are the
decisions, and three tests compare against them; the alarm is submitted
first and both calls are in flight at once; the test user's password of
the proof is a throwaway kept in the log folder only.

Measurements, 13 Oct 2026, RTX 4090, v1 off:
- 556 tests, 19.6 to 19.8 s, none skipped; green under Cowork's Windows
  tool (20.95 s). No file over 600 lines (the largest bench/shared/
  judge.py 527, unchanged), no function over 80 (the longest 64). CLAUDE.md
  99 lines. The word check of stage 3: 1,898 of 1,898 for each call
  (143 + 182 + 598 + 975), mismatches 0; the 121 calls a call of task 5's
  own script run also matched, 4,038 of 4,038 in all.
- A fresh Python with the base app alone (18 packages, no torch) starts,
  answers and stops; the GitHub start step as it is passed.
- On vLLM (started by the script copy with its room; 23.3 s to answer;
  18,212 MiB on the card, 18,912 in all): This machine said the language
  model runs on vLLM 0.31.0 with Gemma 4 QAT present, the guideline
  search on the graphics card, and the WhisperX choice not available
  because the card has no room for its pass at Stop. The sums on this machine:
  70 + 18,316 + 3,384 + 1,010 + 1,000 = 23,780 of 24,564 (784 to spare);
  70 + 18,316 + 1,010 + 9,464 + 1,000 = 29,860 (5,296 over).
- The three chains of 495 at temperature 0 through the app's pass,
  together, on vLLM: 33 passes, no call failed, H1 and H2 met in every
  chain (both first at pass 2); the typical pass 2.78 s (chains 2.79,
  2.81, 2.75), the slowest 3.08 s; beside 5d's 2.73 and the app's 5.11
  before 3c. The record carries vllm 0.31.0, the repack's name and the
  revision 2096d38d.
- With vLLM stopped: This machine said the language model runs on Ollama
  0.33.3, because vLLM did not answer at its address, Gemma 4 QAT
  present; the same two room sentences (sums 22,040 and 28,120). One
  chain of 495 on the service, together: 11 passes, no call failed, H1
  at pass 2 and H2 at pass 3; the typical pass 4.99 s, the slowest 5.34:
  the service queues the two calls, so nothing is gained there until it
  is set for two at once (OLLAMA_NUM_PARALLEL), the install advice of
  stage 15.
- The run command refused a result folder inside the repo and inside
  the test data folder, exit 6, nothing written.
- Nothing left the machine: vLLM ran with its usage reports and its reach
  to the hub off; no key and no token was read; the Ollama service is
  as it was, model for model and digest for digest; no model file or
  engine file in the engine folder changed. The private word check
  printed nothing before every commit.

Made untrue by this stage: CLAUDE.md's running lines (the engine order,
the room check, --data-folder on run), fixed in this commit; the
README's line and the home page's sentence, fixed in this commit; the
Ollama lines of 15.7 and the settings store's line about stage 3b, which
3c replaced as the details say. The 5d entry's one wrong sentence is
corrected above (2.77 to 3.29 s alone; 0.89 s on vLLM together with the
first EmbeddingGemma on the processor; at most 0.07 s between halves),
and the same in the 5d report. The two 5c entries moved to the archive.

Departures from the plan: the engine sentences went into words.py with
commit 3 and the room sentences with commit 5, not in one commit; the
language model's row on This machine came with commit 3, the two room
rows with commit 6.

For stage 15: the app does not start vLLM, so until the installer the
owner starts it by hand with the block in the report; on the Ollama
service as installed the two calls queue, so the gain of ruling 31 on
Ollama needs the service set for two calls at once; a vLLM whose process
name on the card held neither "vllm" nor "ollama" would be counted as
another program and as its own need, and the sums would put the
guideline search on the processor. For 5e and stage 6: the WhisperX
decision is parts.decisions.whisperx_choice; Start is offered only when
parts.decisions.start_offered. For stage 8: the guideline search's place
is parts.decisions.guideline_search. For stage 9: the three elements are
the data of the control panel of ruling 38.

Next: the owner's check at port 8001 (the steps are in the report), then
push; the GitHub check must be green on all three systems. Then Cowork
checks the report from the raw files.

## 2026-10-13. Stage 5d: the three models together on one graphics card

Built and run on 13 Oct 2026. The plan was reviewed by Cowork the same day
(five changes); all are in. A report only: nothing of the app changed, no
engine setting was built (R31), and the owner has no check of his own to
run for 5d. The report is STAGE5D_REPORT.md in the private log folder.

The rulings it answers, one line each:
- 15.8 ruling 29: the engine is chosen only after all three models have
  been tested together on the card; this is that test.
- 15.9 ruling 23: a setup works when it meets four lines (all on the card
  and nothing moved; no call fails and 495's hard marks hold; the typical
  pass less than 0.5 s longer than alone; the live transcript keeps up,
  less than 1.0 s more wait); not working names the first line missed.
- 15.9 ruling 24: EmbeddingGemma on the processor is a full arm, on both
  engines; a setup that fails with it on the card points to its twin.
- 15.9 ruling 25: both EmbeddingGemma models are tested; version 2 runs as
  a worker of the bench in an environment of its own, from a lock file.

What was built (openconsult/bench/shared, 1,783 lines; 1,289 lines of tests):
the 11 lists of names as a file, hashed and marked -text; the two ways to
an embedding (the service, with keep_alive and num_gpu 0 for the
processor; the worker of EmbeddingGemma 2 over the speech frames); the
searches every 5 s and the side reading of 250 public pieces; the watch of
Ollama's list, the engine's health and the card's programs; three switches
of the speech replay (the started file, the moment Stop was asked, a pause
before Stop); the judge of the four lines and the tables, the same bytes
twice; five commands, each refusing the repo, a data folder and the
recordings. The worker's environment is 63 packages at the versions in
its lock; pillow and torchvision are in it because the model's processor
imports them even text-only.

Measured, on the one machine, 32 setups between two sets of base lines,
then the way round on each engine (every figure of the card in MiB):
- Every setup with Nemotron works, 16 of 16, on Ollama and on vLLM, with
  either embedding model on the card or on the processor. Every setup
  with the WhisperX choice is not working at line one, 16 of 16: it runs
  live beside the other two (2,306 to 2,452 on the card) and runs out of
  memory at Stop, when its Stop models load (its pass at Stop reached
  9,464 with the language model off).
- The way round at Stop works on both engines: the language model is taken
  off the card when Stop is asked and put back after it. Ollama: unloaded
  in under a second, Stop 8.06 s, the chain after Stop 5.07 s typical.
  vLLM: the engine stopped in 1.0 s, Stop 8.08 s, the engine back in 23 s.
  Both met all four lines. Kept apart in the tables, never counted.
- Sharing the card costs, typical pass alone against shared with
  Nemotron: Ollama one after another 5.11 against 4.80 to 4.83; the
  private Ollama 3.76 against 3.84 to 3.93; vLLM one after another 3.45
  against 3.46 to 3.54; vLLM together 2.73 against 2.82 to 2.84. With the
  WhisperX choice live the cost is up to 0.28 s. No setup came within 0.2 s
  of the half-second line.
- The live transcript kept up everywhere: Nemotron's typical wait 2.23 to
  2.25 s against 2.18 to 2.20 alone; the WhisperX choice 3.29 to 4.03
  against 2.77 to 3.29 alone (the largest difference 0.89 s, on vLLM
  together with the first EmbeddingGemma on the processor), and the
  growth between halves never more than 0.07 s over alone.
- The base lines of the four ways were 0.00, 0.01, 0.00 and 0.09 s apart,
  all within the steadiness rule of 0.25 s. 1,132 searches, none late,
  none failed. No model was ever split or evicted. No call failed; the
  hard marks held in every chain.
- vLLM's room: --kv-cache-memory-bytes 1,400,000,000 gives a cache of
  16,531 tokens at a context of 16,384 (1.01x), and the engine takes
  18,212 of the card at start. A call of 15,002 tokens came back; 17,500
  and 78,000 were refused with the engine's own message; the two longest
  calls of 495 sent at once both came back. The largest pass of this run
  read and wrote 2,812 tokens; the public bench's largest, 4,104.
- The card at its fullest: 23,251 of 24,564 (vLLM one after another, the
  first EmbeddingGemma on the card, as Nemotron starts). The language model holds
  16,526 to 16,568 in the service, 17,246 to 17,288 in the private Ollama,
  18,212 to 18,316 in vLLM. Nemotron 3,172 to 3,384.
- EmbeddingGemma on the processor frees 1,083 (the first) or 1,010
  (version 2) of the card. A search of one list alone: the first 0.102 s
  on the card, 0.140 on the processor; version 2 0.064 and 0.105. In a
  setup, 0.105 to 0.159 on the card and 0.113 to 0.250 on the processor.
  250 pieces into vectors: the first 2.98 s on the card and 16.35 on the
  processor; version 2 0.36 and 16.54.
- The judge was wrong once and was fixed from the stored results: the
  worker of EmbeddingGemma 2 lives only while its searches run, which end
  with the chains, and the judge had read its planned exit as a model
  moved. The driver was wrong once too: its vLLM restart emptied the
  service two seconds after Stop, which cost the first try of vLLM's way
  round its first line; that step alone was run again with the driver
  fixed, and the first try is kept beside it. Both are in the report.
- Nothing left the machine: the workers' connection records hold only
  the bench's own calls to the service on this machine. No key and no
  token was read; the one fetch ran with no token. The Ollama service is
  as it was, model for model and digest for digest.

Made untrue: the sum of 13 Oct in ruling 24, that the three models on
vLLM are a few hundred MiB over the card, is a sum and not a measurement;
measured, they fit with Nemotron and either embedding model on the card,
1,313 to spare at the fullest. CLAUDE.md's running lines were shortened
to keep the file under 100 lines: the three app commands are one line,
speech-voice and speech-calls share a line, and the optional switches of
speech-voice, speech-drugs, speech-calls and speech-score are not shown
(their help pages show them). README.md's "so far" names the second bench.

Departures from the plan: the tidy-up of reads names utf-8 in five reads,
not four; the plan's commits 9 and 10 (the tables; the commands and the
sentences) became one, because the tables are what the judge command
writes; the sampler's two files and the load log are shared with the
proofs of Part 4, so their first lines are from before the run. The
suite: 521 tests in 19 to 21 s, none skipped, green under Cowork's
Windows tool. No size target was missed.

For the session on the engine choice: every Nemotron setup works on both
engines, vLLM together is the fastest way (2.73 s alone, 2.82 shared) and
Ollama one after another the slowest (5.11); the WhisperX choice needs
the way round at Stop on either engine, about 8 s with the language model
off and, on vLLM, 23 s more for the engine to come back, or a lighter
Stop. For the stage that builds the guideline search: the worker of
EmbeddingGemma 2 is cheaper on the card (1,010 against 1,083) and faster
(0.064 against 0.102 s a search; 0.36 against 2.98 s for 250 pieces); on
the processor both take about 16 s for 250 pieces, so an index is built
on the card. For the stage that installs: the search's form and the
passage's form are in bench/shared/searches.py, and a vector has 768
numbers in both models.

## 2026-10-11. Stage 5c, part two: what is done with the transcripts, and the full rehearsal

Built on 11 Oct 2026. The plan was reviewed by Cowork the same day (five
changes); all are in. The checks and the rehearsal ran on 11 Oct with the
v1 service off. The rehearsal is a rehearsal: no figure from it counts
(spec 13.4 rule 2; 15.9 ruling 6).

What was done:
- Fix one: the Nemotron worker's last word before a silence is passed on
  once the model has decoded WORD_CLOSE_S past its last token (a plain
  class, speech/nemotron/wordflow.py, loaded by path as the join is), so
  the line's own wait of 3.0 s can run in silence. The figure is 2.0 s,
  not the plan's 1.0: on the card the model gave one word of the clip its
  two tokens 16 frames (1.28 s) apart across two decoding steps, and one
  second could have cut it in two. The Stop reply's notes carry the counts
  that prove no word was split. The tied pair has its own stream and does
  not change.
- Fix two: the wait to first shown runs from the line's start; the true
  times serve every arm; the true start goes to the first line of a speech
  and the true end to its last (bench/speech/waits.py, tables.py). Part
  one's 18 results rescored: only the wait differs.
- The lines a model reads (bench/speech/model_lines.py): from the smallest
  timed pieces at Stop, two neighbours joined when the first does not end a
  sentence, both carry the same label and less than 1.0 s lies between; a
  piece never split; turns as v1 joins them; v1's two role words and
  Unknown (ruling 22); the words around a transcript exactly as the details
  give them, pinned byte for byte.
- The three jobs of the bench (bench/speech/jobs.py, prompts/): the
  owner's three prompts byte for byte, hashed before they are read and
  marked -text; the forms, the note's being v1's as it stands; the limits as
  named figures; through the door's one new method, ask_own, with the same
  limits, form check and record; the app's table of jobs untouched (the
  word check of stage 3: 4,038 of 4,038 before and after).
- The voice method (bench/speech/voice.py, voice/worker.py): the doctor's
  voice learnt from a listed recording marked voice_only, each line given
  its distance from that voice by pyannote's wespeaker model loaded by path
  with the hub's network off; the reading made on the bench's side from
  two figures around the pinned pipeline's clustering threshold (0.7046,
  a band of 0.1) and a line under 1.0 s unsure; the list gains
  doctor_voice and voice_only; the replay refuses a voice-only recording.
- Who spoke, four readings side by side (bench/speech/who.py): the choice,
  the label check, the voice, and together, each counted word by word.
- The UK drug list (bench/speech/druglist.py; speech-drugs): one month of
  the Prescription Cost Analysis fetched and made into a list of whole
  names, generic without salt and form words, brand from the front of a
  product that is not its own generic equivalent, split at a bracket, a
  slash, a plus and the words with and and; dressings, appliances and the
  two nutrition sections left out; the class codes counted, not leaned on.
- The three ways to spot a doubtful drug name and the three classes
  (bench/speech/doubt.py), the key facts (keyfacts.py), the notes' five
  counts and the chance (notes.py), the calls (calls.py) and the tables of
  part two (tables2.py), with the one scoring command taking the key-fact
  file and the drug list where part two's results are there.
- Three commands: speech-voice, speech-drugs, speech-calls; speech-score
  gains --key-facts and --drug-list (CLAUDE.md).

The rulings of spec 15.9 for part two, each in one line:
2. The three ways benched as a report only; nothing marks a name on a page.
   Done for the rehearsal.
4. The voice (D53) and the words (ruling 17) benched, together and apart;
   nothing built into the app. Done for the rehearsal.
15. The notes written twice from each page and twice from the script.
    Done.
16. A real drug that is not the one spoken counted, with the list, for
    every choice, as a whole name of the list. Done.
17, 18, 19. The three prompts byte for byte (sha256 pinned). Done.
20. The key facts applied by code; the lists are Cowork's. Done.
22. A turn with no speaker is Unknown. Done.
21. Part two as its own run, with the cycle of 15.3. This is it.

Decided in the plan review (Cowork, 11 Oct), as decisions of this stage:
a drug is a whole name of the list, never one word of a longer name; the
driver never loads the language model beside a speech model and marks the
calls failed if a worker is still alive; the short form n/7, n/52, n/12 is
days, weeks or months only when n is 24 or less; the voice figure is a
distance; the nearest entry is none when no entry meets a single group.
Decided while building: WORD_CLOSE_S is 2.0 s (above); foods are the
sections the drug file names Oral nutrition and Enteral nutrition (0913,
0914), not 0904; speech-drugs takes the recordings and data folders so it
refuses them; a failed call is failed and not refused.

Measurements, 11 Oct 2026, RTX 4090, v1 off:
- 451 tests, 16.4 s, none skipped. App code 6,464 lines without the
  bench (12,703 with it), tests 8,185. Largest file speech/nemotron/
  models.py, 516 lines; no function over 80. CLAUDE.md 99 lines.
- The two environments built into the working folder from the warm cache
  in 11 s and 1 s (7.2 GB and 5.5 GB); the two local self-tests passed,
  22 of 22 each, before the run and again after it. The word check of
  stage 3: 4,038 of 4,038 calls rebuilt exactly before and after the
  door's change.
- Fix one on the card: 60 s each of zeros, noise at -50 and at -30 dBFS,
  no line; the clip then 30 s of silence with no Stop until the end, 22 of
  22 words, the last line final 3.09 s after its end and 28 s before Stop;
  the largest gap between two tokens of one word 16 frames, no token after
  a close by time. Recording 477: the last word's line final 3.21 s after
  its end, 191 s before Stop (part one: at Stop, 194 s). The new Nemotron
  pages beside the old: 462 94 lines and 661 words on both, 0 words
  differ; 473 117 to 114 lines, 741 to 742 words, 3 differ; 477 51 to 50
  lines, 359 words, 0; the made recording 92 to 90 lines, 971 words, 0;
  the longest wait to final 3.2 to 3.4 s on every recording (the made
  recording 4.22 to 3.24).
- Fix two: part one's 18 results rescored with the new code, 3,838 leaves
  of scores.json differ and every one is under the wait; 36 lines of
  report.md, every one a wait. The least true wait to final is above zero
  on every arm; to first shown it reads below zero on the one-transcript
  choices (a line's first two words can stand in an earlier partial).
- The drug list: July 2026, 235,494,243 bytes, 533,087 rows, fetched in
  8 s; 3,801 names (2,679 of one word, 1,122 longer; 1,181 generic, 2,620
  brand) made in 5 s; 19 of script 19's 20 drug names in it.
- The minute of the doctor's voice: 39.3 s, 37.3 s of speech, peak -0.97
  dBFS, typical -22.3, no sample clips.
- The rehearsal (13:22 to 13:51, 29 min, nobody attending): Nemotron's
  four results in 23 min; the voice method on the five pages of the made
  recording in 6 s, and the plain not-run record on the nine pages of the
  old recordings; 64 calls in 6 min, 1 failed (the doubtful drug names on
  Nemotron's page of the made recording, cut at 1,500 tokens), 0 refused;
  the tables twice from the stored results, byte for byte the same. The
  connection records of the speech steps are empty. The card: Nemotron
  4,022 MiB, the voice worker 1,396, the language model 17,444 at its
  highest; never both at once.
- The calls: the label check median 9.9 s, longest 16.9; output median
  1,411 tokens, longest 2,665 of 3,000 (about 21 tokens a line, not the
  13 the limit was set from). The doubtful drug names median 0.6 s,
  longest 10.1 (the cut one). The notes median 4.8 s, longest 8.2; output
  median 736, longest 1,284. The notes from the scripts median 4.1 s.
- Read as a doubter (item 14): the scoring of figures counted a note's
  own turn citations and read 5-10 as 510, fixed in c03b5de (361 figures
  "not spoken" over 28 notes became 34); the tied pair's pages of 462 and
  477 carry one speaker label, so their notes were given one turn and
  cited turns that do not exist (every entry); on the made recording
  AssemblyAI wrote glipizide for gliclazide three times early on, and the
  language model then flagged the three later, right, gliclazide as
  doubtful and named glipizide as the medicine meant; the list way marks
  everyday words close to a brand (perfect, diabetes); a garbled name at
  a closeness of 0.72 is missed at the figure of 0.75; no reply was
  refused and no reasoning was cut.
- The private word check printed nothing before every commit. Nothing
  private is in V2: the private check's counts are all 0.

After Cowork's check, 11 Oct 2026 (STAGE5C2_FIX.md):
- A note's shorthand is read as words before a key fact or a drug name is
  looked for (a slash between words, a sign before a figure, 3x, a range,
  a hyphen read both ways), on both sides of a rule; the app's matching
  and every mark of part one stay as they are (6207dfd).
- The first table of part two says on how many pages a reading ran, and
  not run where it ran on none, and whether a drug written as another
  real drug reached the note, in how many of the notes (6488e7e).
- Cowork corrected five rules of the key-fact file (13-01, 01-04, 01-18,
  15-13, 19-23); the tables to read are stage5c2-rehearsal-tables-v4,
  made once with the three fixes, byte for byte the same twice.
- Windows, 13 Oct: one test removed the folder of calls with the made-up
  door's database still open. The fault was in the test; the app is unchanged.

Made untrue by this stage:
- CLAUDE.md, Running it: the three new commands and the two options;
  fixed in this commit. The README's line; fixed in this commit.
- V2_SPEC.md 15.9, the details of part two: WORD_CLOSE_S is 2.0 s, not
  the join's pause; the drug file's columns (27, ICB in place of STP, one
  new) and the lack of a class-code table on the portal's pages, so the
  rule tells generic from branded by the data; the licence sentence is not
  on the dataset page; the foods' sections. Cowork folds these in.
- The plan's figure for the card (18,000 MiB): the language model took
  17,444 MiB at its highest.

For 5d: the language model with its 16,384 context took 17,444 MiB
on the card; the voice worker under 1,396 MiB. For 5e: the two figures of
the voice method and the closeness figure of the list are drafts, to be
set again from the stored distances and marks on the new recordings; the
wait to first shown can read below zero against the true start on the
one-transcript choices (a line's first two words can stand in an earlier
partial), a limit of the measure to put right. For stage 6: the four
readings' counts on the old recordings say what the label check alone
does on a real voice, and the made recording's say nothing of the voice
method (a man's and a woman's machine voice).

Next: the owner's check (uv sync, then the four self-tests on his real
data folder), then push; the GitHub check must be green on all three
systems. Then Cowork checks the report from the raw files.

## 2026-10-11. Stage 5c, part one: the replay bench and the transcript marks

Built on 10 and 11 Oct 2026. The plan was reviewed by Cowork on 10 Oct
(ten changes); all are in. The checks and the rehearsal ran on 11 Oct
with the v1 service off. The rehearsal is a rehearsal: no figure from it
counts (spec 13.4 rule 2; 15.9 ruling 6).

What was done:
- The rule against words from silence looks as wide as a choice's times
  allow (ruling 12): Declares gains time_slack_s (Nemotron 1.0 s, the
  rest 0), refuse_quiet looks that far to each side and refuses only if
  the whole stretch is quiet; while sound is still being fed a stretch
  that reaches past it counts as not quiet, and at Stop nothing is still
  to come, so a quiet last line is refused for every choice. Two tests of
  5b feed more quiet sound before their made-up lines, same assertions.
- The matching of words lives in the app (speech/matching.py): capitals
  and punctuation ignored; apostrophes, then hyphens and split words, then
  numbers, then units, then the British and American spellings in one
  table made the same, in that fixed order; a slash between figures is
  over; a figure against its unit is split. The alignment classes each
  page word as heard, in place of a spoken word, or from nowhere.
- The check for missing speech (speech/missing.py; 11.5 rule 2; D45;
  ruling 13): five or more live words the transcript at Stop lacks; two
  seconds or more of sound above -30 dBFS (not yet measured on raw sound)
  that no line covers, quiet gaps under 0.5 s joined. Stage 6 shows it.
- The speech bench (bench/speech): the banked list and its reader (a
  checksum that differs, a name not listed or a list not whole is refused
  before any sound is read; consent held by code, ruling 14); the
  reference from a script with the cut and the notes; the replay through
  the door in 0.25 s pieces, each fed when its sound has ended, with
  everything the door gives kept, the moments, and the loudness windows;
  the marks (passages with or without a sign, words from silence, what
  the rule did, words that differ with negations and numbers, drug and
  test names as whole words with the bracket form, who spoke by best
  fit, the wait, how exact the times are, the signs counted); agreement
  against the script from the arms with a model of their own only, a
  word every arm left out still counting; the tables, byte for byte the
  same from the same results, never written over.
- The two arms of the bench (ruling 15): the tied Nemotron pair, v1's
  pairing on the 5b frame in the Nemotron environment, its late text
  changes kept in the result's notes and never sent as a revision; and
  WhisperX with v1's line, the line given to the live model only and
  hashed into every result. Neither is in the app's table of choices;
  the command refuses their names.
- The conversion of the sound's rate in the three local workers
  (speech/common/resample.py): scipy's own filter for a change by three,
  61 taps, Kaiser 5.0, its state carried across pieces; 16,000 or 48,000
  taken, any other rate refused.
- Three commands: speech-fetch, speech-run, speech-score (CLAUDE.md).
- The suite gains a guard on where recordings are kept (R18), with its
  twin. After Cowork's check the guard tells a changed file by the sha256
  of its bytes as well as its size and time: a coarse file clock gave a
  clean copy "DID NOT RAISE" on the twin once in two runs.
- A segment's speaker at Stop on a tie between two clusters is now no
  speaker (spec 15.9 ruling 4: unsure, never guessed), and the answer no
  longer follows the hash order (found by scoring the rehearsal twice).
- The bench's files are the same bytes on the three systems: the tables
  are written with "\n" line ends, and v1's line is marked -text in
  .gitattributes so Git never changes a byte of what is hashed (ruling 3).
- The GitHub check was red on Windows at 41025f2, in four tests only: a
  made-up script written in text mode no longer matched its checksum, and
  a path was compared as a string with a slash. The script is now written
  as bytes and the path compared by its parts. The owner's push is the proof.

The rulings of spec 15.9 for 5c, part one, each in one line:
12. The wider rule, with the figures as named constants; Nemotron's first
    word of the clip now reaches the page (it was refused in 5b). Done.
13. A passage is 5 words or more, a pause 2 s or more: in the marks. Done.
14. No old recording left the machine: the list says so for each, the
    bench refused the six cloud tries before any worker, the records are
    empty; the made recording (two machine voices, script 19) went to the
    two EU addresses. Done.
15. Six arms ran: the four choices, the tied pair, WhisperX with v1's line
    (the line byte for byte, hash c72f4adc...). The other extras are part two.
16. Drug names counted as whole words, the bracket form caught, names in
    v1's line apart; a wrong name that is a real drug is part two.
17 to 20. Part two. Nothing built.
21. Part one as its own run, with the cycle of 15.3. This is it.

Decided in the plan review (Cowork, 10 Oct), as decisions of this stage:
at Stop the wider stretch is cut at the end of the sound; the matching
lives in the app and the app never imports the bench; a piece is fed
when its sound has ended; a gap covers a passage by words and a stretch
by time, and a passage whose neighbours sit in one piece is unseeable by
a stretch; agreement is the same written word from every arm with a model
of its own, at least three, and a word every arm left out is not
agreement; the fixed order of the matching's steps; the tied pair's late
changes travel in the stopped reply's notes; the arguments reaching the
WhisperX models are recorded in the checks; the connection recorder sits
on the worker's Python from the driver's side (a sitecustomize named in
PYTHONPATH), with no code in V2.

Measurements, 10 and 11 Oct 2026, RTX 4090, v1 off:
- 400 tests, 16.0 s, none skipped. App code 6,328 lines without the
  bench (10,469 with it), tests 6,774. Largest file speech/nemotron/
  models.py, 500 lines; no function over 80. CLAUDE.md 99 lines.
- The two environments built into the working folder from the warm cache
  in 11 s and under 1 s (7.2 GB and 5.5 GB); every model found at its
  pinned revision, nothing downloaded; the tied pair's 3.5 model found
  in the shared cache at v1's revision ea30d66d (2.37 GB).
- The four self-tests on the working folder passed, 22 of 22 each.
  Nemotron's first word, And at 0.08 to 0.16 s, was accepted (5b: refused).
  The WhisperX models received no initial_prompt, prefix or hotwords; the
  arm with v1's line gave the line to the live model and nothing to the
  pass at Stop. No local worker opened a connection or looked up a name;
  each cloud worker reached its EU host and nothing else.
- Silence (60 s each of zeros, noise at -50 and at -30 dBFS, measured
  -inf, -49.5 and -29.6 dBFS): none of the four local arms wrote a word,
  live or at Stop; nothing to refuse.
- The conversion, in both environments: a 1 kHz tone at -20 dBFS came
  through at -19.99; a 12 kHz tone came through at -87.3 (67 dB down),
  the loudest bin below 8 kHz at -84.3 dBFS (4 kHz); lengths equal. The
  clip at 48,000 through the four local arms: 22 of 22 live and at Stop
  on three; the tied pair 22 at 48,000 and 21 at 16,000 (American for
  Americans).
- The three old recordings became WAV with flac -d (MD5 verified) and
  their samples equal ffmpeg's independent decode. The made recording:
  361.5 s, peak -0.75 dBFS, typical -21.6, no clipped sample, pauses at
  -75 dBFS or quieter; its cut runs to speech 8 at 56.7 s.
- The bench refused, before anything was fed: a wrong checksum, a file
  not listed, a result folder in the repo, in the data folder and where
  recordings are kept; a result asked for a second time; six cloud tries
  on old recordings and the cut, with empty connection records.
- The rehearsal (00:37 to 02:23, 1 h 45 min, nobody attending): six arms,
  18 results, every arm exit 0, no failure; every result carries the
  list's checksum; the cloud arms sent 361.47 s each (the made recording)
  and nothing else; the local workers' connection records are empty; the
  card peaked at 10,309 MiB. No arm wrote a word into silence that the
  rule let stand; no real word was refused; the one refused line (one
  word, Speechmatics, in a pause) was invented. Two passages missing with
  no sign, both on the tied pair, which is not in the app. Nemotron let
  nine invented words through by looking wider; its diarisation found one
  cluster only on two of the three old recordings. WhisperX's one
  segment end 2.9 s early made a false sign. In 477's three minutes of
  digital silence no arm wrote anything; Nemotron's last line stayed
  pending until Stop (194 s). v1's line changed no drug-name figure.
  No figure counts; the report in the log folder has them all.
- Scoring the same 18 results twice gave two different tables (who
  spoke on 477): a segment's speaker at Stop came from a set, and a tie
  followed the hash seed. Fixed in turns.py: on a tie, no speaker. Scored
  again twice after the fix, byte for byte the same; on 477 the two
  WhisperX arms moved ten words from the right speaker to no speaker,
  and no other figure in the tables changed.
- The private word check printed nothing before every commit. The two
  keys' values appear in no file of LOGS newer than the start marker, in
  the working tree or in the commits (counts 0).

Made untrue by this stage:
- CLAUDE.md, Running it: the three bench commands; fixed in this commit.
  The README's line; fixed in this commit.
- V2_SPEC.md 15.9, the details of 5c: "sound that has not been fed yet
  counts as not quiet" now holds while sound is still fed, and at Stop
  the stretch is cut (plan review change 1); the agreement rule counts
  only the arms with a model of their own and a word every arm left out
  is not agreement (change 5); the tied pair's late changes travel in
  notes (change 7); the matching lives in the app (change 2). Cowork
  folds these in.
- The plan's figure for the card (9,000 MiB): the rehearsal peaked at
  10,309 MiB, during WhisperX's Stop on the made recording.

For part two: the key-fact lists and the UK drug list (spec); the tied
pair's late changes (9 lines over the four recordings, 8 of them on the
made recording, no word lacking on the page); the arms' times beside the
figures of the wider rule (Nemotron's speech ends up to 1.33 s late, 3 of
84 beyond its 1.0 s; the tied pair's starts up to 1.09 s late; the exact
choices within 0.5 s but for WhisperX's one segment end 2.9 s early); the
signs (one right, three false, each explained in the report; the -30 dBFS
figure of the check has not been measured on raw sound, and a recording's
quiet words sat under it where a passage went unsigned); whether a
pending line should close after some seconds of silence (owner).

Next: the owner's check (uv sync, then the four self-tests on his real
data folder), then push; the GitHub check must be green on all three
systems. Then Cowork checks the report from the raw files, and the prompt
for part two is written.

## 2026-10-10. Stage 5b: the Nemotron choice and the two cloud choices

Built on 10 Oct 2026. The plan was reviewed by Cowork the same day (nine
changes and one addition to Part 4); all are in. The checks on the card
and against the two services ran on 10 Oct with the v1 service off.

What was done:
- Three more speech choices behind the door of 5a (openconsult/speech):
  Nemotron on the card, Speechmatics and AssemblyAI through their EU
  addresses. Each is proven by the self-test of 5a, each command names
  its choice (--choice), and This machine has one line for each.
- The door: a choice whose labels are live is told the number of
  speakers at open and the number goes to the worker; a choice with one
  transcript gets at Stop every line the door already gave, with the
  last ones made final, from the door's own record by id (11.1). Stop
  never refuses over a count that differs from the one at open: both
  counts are recorded (the last words are said at Stop). A revision
  from a service changes a label and nothing else, and never costs a
  line. New failures by name: no_key, key_refused, no_credit,
  no_internet, service_down, limit_reached, address_refused,
  connection_lost. The WhisperX choice behaves as before.
- The keys: one module (settings/keys.py) reads SPEECHMATICS_API_KEY
  and ASSEMBLYAI_API_KEY from the process environment, then from .env
  in the data folder; a key goes into its own worker's environment and
  nowhere else, and every worker's environment has every other key's
  name taken out. .env.example is committed with empty values.
- The cloud frame (speech/common/cloud.py), on websockets 17.2, the one
  library added to the base app: the EU address is a named constant,
  dial refuses any other before a connection, main takes no argument
  and reads no environment value for it; the certificate and the host
  are checked by the library's default context with no argument that
  could weaken it; a dead line is noticed within 50 s (ping 20, pong
  20, close 10, the library's own defaults) and is connection_lost;
  nothing reconnects. A made-up service on loopback stands in for both
  services in the suite; the suite never reaches the internet.
- Speechmatics: StartRecognition with the enhanced model, the medical
  domain, speaker diarization, partials on, the session's rate,
  max_speakers from 2 up, no additional_vocab. One line per run of
  label from an AddTranscript; UU is no speaker. EndOfStream, then
  EndOfTranscript. The service sends Info (its usage and its region)
  before RecognitionStarted; the worker reads past it.
- AssemblyAI: the parameters in the query, model universal-3-6-pro
  named, speaker_labels, domain medical-v1, max_speakers as given, no
  keyterms_prompt, no format_turns (the model always formats). The
  Begin echo is checked field by field; a field the echo does not carry
  is recorded as not echoed. A Turn that ends is one line; PENDING and
  UNKNOWN are no speaker; a SpeakerRevision gives id and label only.
  Terminate, then Termination. A wrong key is answered after the
  handshake with an Error frame (1008) and a close.
- Nemotron (ruling 8): one worker, one environment built from a
  committed lock with NeMo at v1's commit 1688cc3d, torch 2.12.0 from
  PyPI, Python 3.12. The English model alone writes the words at the
  revision and the setting of Task 17's third arm ([70, 13]); the
  speaker model beside it, at v1's revision, in the Low latency row of
  its card (1.04 s). Each has its own features (v1's splice), chunker
  and cache; nothing of v1's pairing. The join (nemotron/join.py) is a
  plain function: a word that no stretch covers, or that two speakers
  cover equally, has no speaker; a line closes at a sentence's end, a
  change of speaker or a pause of 1.0 s, or by time at 3.0 s.
- Carried from 5a: the home page's line; a death's reason is one plain
  sentence (codes stripped, traceback and warning lines skipped, a cut
  first line of the log window dropped, a library's own log lines and a
  worker's [note] lines never taken); the worker-side frames shared by
  every worker folder (speech/common/frames.py). Eighteen comments
  that cited private plan reviews now give their reason (ruling 11).

The rulings of spec 15.9 for 5b, each in one line:
8. The English model alone writes the words; the speaker model only
   says who spoke; item 6 proved the words identical with and without
   it; the join can change no word. Done.
9. The EU address only, medical on, labels live, no word list: pinned
   word for word against the made-up service and proven on the real
   connections (items 11 to 13). Done.
10. AssemblyAI stays; what it keeps is for the bench report and stage
    9. Nothing built; the self-test's sentence says the clip leaves.
11. The tidy-up commit opened the stage. Done.

Decided in the plan review (Cowork, 10 Oct), as decisions of this stage:
the number given at open is sent to AssemblyAI as max_speakers as given
and to Speechmatics from 2 up, with no headroom; a label beyond a number
a service could not be given stands as the service gave it; Stop never
refuses over a count; a revision never costs a line; a worker holds its
own key and no other; the certificate is always checked; the dead-line
figures are the library's own; AssemblyAI's text is formatted without
format_turns (its migration page); the home page's line is the review's
draft; the Nemotron environment is not Task 17's (Python 3.12 and torch
from PyPI here; 3.13 and NVIDIA's index there), the model, revision and
setting the same. Decided while building: a field the Begin echo does
not carry is not a difference (it echoes no max_speakers); the workers
log the opening sent and the first reply as [note] lines.

Measurements, 10 Oct 2026, RTX 4090, v1 off:
- 346 tests, 16.1 s, none skipped. App code 5,864 lines without the
  bench, tests 5,492. Largest file speech/nemotron/models.py, 497
  lines; no function over 80. CLAUDE.md 99 lines.
- The Nemotron environment: 159 packages locked, 156 installed on
  Linux, 5.5 GB, built in 22 s from a warm cache; the second run
  audited and changed nothing in 0.3 s. Both models found in the shared
  cache at their pinned revisions, none downloaded.
- Nemotron self-test passed: 21 of 22 words live and at Stop (the same
  lines). The first word, And, came at 0.08 to 0.16 s, in the clip's
  opening silence, and the rule refused it at -43 dBFS: the model's
  frame times can run ahead of the first word. Load 6.9 s, then the
  warm-up. Lines 2.19 to 3.18 s after their last word; Stop 0.04 s; the
  slowest step 0.18 s. Four lines of 4, 2, 7 and 8 words. The card's
  highest sample 4,321 MiB. The English model alone gave the same 22
  words, word for word. Silence and noise (zeros, -50, -30 dBFS, 60 s
  each): no word, nothing to refuse. The connection record was empty.
  Killed mid-clip: died with the exit code, no second start, a new open
  worked.
- Speechmatics self-test passed, 22 of 22; open 0.1 to 0.16 s; a line
  4.7 to 4.9 s after its last word (the service's default max_delay);
  Stop 0.18 s; 11 lines (ten of one word, one of twelve), every word
  S1, every confidence 1.0; RecognitionStarted after an Info with
  region eu. AssemblyAI self-test passed, 22 of 22; open 0.85 s; lines
  1.2 and 2.1 s after their last word; Stop 1.1 to 1.4 s; 3 lines (5, 2
  and 15 words) with confidences 0.994, 0.705 and 0.981; the middle
  line PENDING live and revised to A at Stop. The connection records
  hold only the EU host's lookup and connection, three lines each.
  Silence and noise, 180 s to each: no word. A wrong key: Speechmatics
  HTTP 401, AssemblyAI an Error frame 1008; both the plain sentence,
  one attempt. Killed mid-clip: as Nemotron. Sound sent: about 234 s to
  Speechmatics, 218 s to AssemblyAI, the clip and made sound only.
- The keys' values appear in no file under the working data folder,
  the log, the plan, the report or the repo (counts 0).
- This machine on the working data folder: Nemotron installed and
  passed, Speechmatics passed, AssemblyAI passed, each with its date.
- The WhisperX self-test on 5a's folder passed with this code, 22 of 22.
- The private word check printed nothing before every commit.

Made untrue by this stage:
- CLAUDE.md, Running it: --choice on the two commands; the README's
  line. Both fixed in this commit.
- V2_SPEC.md 15.9, the details of 5b: "the number is given to the
  worker" holds, but a service may not take it (Speechmatics below 2)
  or may not echo it (AssemblyAI); the list of new failures lacks
  connection_lost; a line now has an id; the Begin echo rule is as
  decided above. Cowork folds these in.
- The plan's figure for the Nemotron card memory (4,000 MiB) was met
  (4,321 at the highest sample, with the clip; 5a's WhisperX took 7,600).

For stage 6: a cloud worker's connection is opened at the door's open,
so Start pays 0.1 to 0.9 s; a dead line is noticed within 50 s; the
Nemotron English model's first word can be timed in silence before it,
so the rule may refuse a real first word; AssemblyAI's labels come
PENDING for a short turn and are revised at Stop; Speechmatics gives
one line per word early in a session.

Next: the owner's check (install-speech --choice nemotron, the four
self-tests, the app on 8001: This machine shows the rows), then push;
the GitHub check must be green on all three systems. Then the 5c
brainstorm.

## 2026-10-10. Stage 5a: the transcription door

Built on 9 and 10 Oct 2026. The plan was reviewed by Cowork on 9 Oct
(seven changes) and the build again at the gate for the card (six
changes); both are in. The checks on the card ran on 10 Oct with the v1
service off.

What was done:
- One door to transcription (openconsult/speech): open at the sound's
  rate, feed, stop with the number of speakers given. Every call gives
  lines of text, each with a speaker or none, a start, an end and a
  confidence or none (11.4), or a failure with its reason: not
  installed, died, no answer, worker error, bad reply, no session,
  session open, rate not supported, bad speakers. It never raises into
  the app, and tries nothing else (10.4). Every result carries the stamp:
  the choice, its models with their revisions or checksums, and its
  library versions (R20).
- The rule against words from silence, in the door, as a plain function:
  the loudness of every piece fed, in 100 ms windows on the session
  clock; a line is refused when even its loudest window is at or below
  QUIET_DBFS = -40 dBFS. It runs on live lines, on the text not yet
  final, on the last live lines made final at Stop, and on the raw
  segments before the merge. What it refuses is kept and marked.
- The worker frame: v1's frames kept word for word, a reader thread in
  place of select, each start with its own queue and event; a made-up
  worker runs as a real subprocess in the suite on the three systems.
- The first choice, WhisperX with pyannote, as a worker run only by its
  own environment's Python: the live stream on faster-whisper
  distil-large-v3 (v1's buffer and commit margin), and at Stop the
  live buffer transcribed once more so the last seconds are final, then
  WhisperX large-v3 with word times and pyannote 3.1 with the count
  given. No text is given to any model. The merge of raw segments into
  turns is a plain function in the base app; raw segments are kept as
  they came, flagged refused or not.
- The environment lives in the data folder, built from the committed
  lock file by openconsult install-speech, which then finds or fetches
  every model at a pinned revision or checksum. The worker runs with the
  hub's network off and loads from disk only; the voice activity model
  is loaded by path, not by name. No model downloads without a click.
- The self-test: the clip in 250 ms pieces at real time, Stop with one
  speaker, at least 20 of the 22 expected words in order, live and at
  Stop. openconsult self-test runs it; the result is stored in the new
  table speech_self_test (version 3); This machine shows the two rows
  on a suitable card.
- The base app gains no library. NOTICE gains the environment's direct
  libraries, the models it fetches, and the clip.

The rulings of spec 15.9, each in one line:
1. Two hard marks for a speech choice: the bench of 5c and 5e. Nothing
   built; the rule against words from silence is the app's side of the
   second mark.
2. A misheard drug name is marked, never corrected silently: stage 6
   and the bench. Nothing built.
3. No speech model is given a line of drug names: v1's line is not
   carried; the record of item 8 shows no prompt, prefix or hotwords.
4. An unsure line is shown as unsure: stage 6. Nothing built.
5. Two cloud services enter the bench: 5b. Nothing built.
6. Stage 5 in five steps; this is 5a. Done when This machine says the
   choice is installed and the self-test passed: it does.
7. The sound as the microphone gives it: the door takes the rate with
   the session (the new recordings are 48 kHz); the real worker takes
   16,000 in 5a. Conversion is 5c's.

Decided in the plan review of 9 Oct (Cowork), as decisions of this stage:
the models are fetched at install, never by the worker; the sound's rate
travels with the session; the last live lines are made final at Stop;
no made-up confidence, so a turn with no scored word has none (v1 gave
0.5: the gate of stage 6 must expect none); no test for a control a
later stage builds; the archive is archive/HANDOVER_ARCHIVE.md; the
clip's source is proven (whisper.cpp's sample, identical by checksum).
Decided at the gate (Cowork): the pass at Stop asks the network nothing;
a second open never throws sound away; a count below one is refused by
the door; the stamp says only what is known (pyannote's inner models are
stamped with the revision their main ref loads, read from disk); names
and comments cite what they pin; the worker's log never holds what was
said (its libraries held to warnings and above).

Measurements, 10 Oct 2026, RTX 4090, v1 off:
- 255 tests, 6.4 s, none skipped. App code 4,063 lines without the
  bench (6,138 with it), tests 4,165. Largest file
  speech/whisperx/models.py, 399 lines; no function over 80. CLAUDE.md
  99 lines.
- The environment: 123 packages locked, 119 installed on Linux, 7.2 GB,
  built in 10 s from a warm uv cache; the second run audited and
  changed nothing in 3.0 s. Every model found in the caches, none
  downloaded. Every library permissive except the nvidia-* wheels
  (NVIDIA's proprietary CUDA licence).
- The self-test passed: 22 of 22 words live and at Stop. The worker
  loaded in 2.9 s. The one live line that was final before Stop came
  3.0 s after its sound ended; the last line was made final at Stop in
  0.07 s. The pass at Stop took 2.1 s: load 1.0, transcribe 0.3, align
  0.5, diarise 0.3. Nothing refused. The card's highest sample 7,600 MiB
  (every 2 s). A second run with every connection and name lookup in the
  worker recorded: the record was empty. The worker's log holds none of
  the clip's words.
- Silence: 60 s of zeros, of white noise at -50 dBFS and of white noise
  at -30 dBFS, live and at Stop: neither model wrote a word, so the rule
  had nothing to refuse, the -30 dBFS noise included. Measured levels
  -inf, -50.0 and -30.0 dBFS. A measurement for 5e, not a pass mark.
- v1's 445 figure, the source of the threshold, was an RMS over each
  filler line's whole span; the rule uses the loudest 100 ms window of a
  line, which is the stricter measure for refusing.
- No text to a model: the live model's transcribe is called with
  language en, beam 5, vad_filter, no condition on previous text and
  nothing else; every prompt built is the bare start sequence (start of
  transcript, English, transcribe; plus no timestamps for WhisperX), with
  prefix None and hotwords None; WhisperX's options carry initial_prompt
  None, prefix None, hotwords None.
- The worker killed mid-clip: the next feed failed with died, the exit
  code and the log's last line; feed and stop after it said no session;
  no second worker was started; a new open loaded a new worker and the
  whole clip went through.
- The private word check printed nothing before every commit.

Made untrue by this stage:
- CLAUDE.md, Running it: the two new commands; the archive's path. The
  README's line. Both fixed in this commit.
- V2_SPEC.md 11.1 and 15.9 say the pass at Stop runs on the recording:
  in 5a the worker keeps the sound it was fed and runs the pass on that;
  stage 6 may hand it the file. 15.9 says the library versions are v1's:
  the speech libraries are, and 43 helper packages resolved newer. The
  spec is silent on the self-test's pass rule (20 of 22) and on the
  rate carried with the session. Cowork folds these in.
- The plan's figure for the threshold on raw sound is still owed to 5e.

Next: the owner's check (install-speech, self-test, the app on 8001:
This machine shows the two rows), then push; the GitHub check must be
green on all three systems. Then the 5b brainstorm. For stage 6: the
gate must expect a confidence of none; the worker's log and the sound
the worker keeps belong to no consultation yet.

## 2026-10-07. Stage 3b: the engine bench

Built over 6 and 7 Oct 2026 and published on 7 Oct, after the owner ruled
that the bench of 7 Oct is the one public bench (spec 15.8, ruling 24).
The two local publish commits of the first bench came out of the history
first, in one rebase, with a bundle of the repo kept outside it.

What was done, 6 Oct:
- Two small items first. An empty list keeps the earlier list: when an
  assessment reply fits its form but its list of differentials is empty,
  and an earlier list exists, the pass gives the earlier entries whole,
  says that the list was kept, and hands the same names to the next pass.
  The record still holds the model's own reply. At the first pass empty
  stays empty. And the terminal's second line now says the browser will
  open by itself; the old line stays for --no-browser.
- The pass is three plain functions: the two messages, the sending, the
  settling. run_pass calls them in the same order and behaves as before.
- Two more engines, llama.cpp and vLLM, as modules of the bench behind
  the joint of stage 3 (bench/chat_engine.py, llamacpp.py, vllm.py). The
  bench command takes the kind of engine, its address and the name it
  knows the model by. The app cannot reach them and has no switch for
  one; a test in a fresh Python proves it. No setting was built.
- In the bench: the two calls of a pass sent together; the repeat test;
  the exporter, which writes an arm's public form and never writes over
  a published file; and the marks worked out again from published
  replies (score --replies).
What was done, 7 Oct:
- Candidate means ruling 18: every hard mark met on the chains at
  temperature 0, read from the data and never from a chain's name, and
  none of them failed. The chains at 0.5 are a stress test, counted the
  same way and reported apart. The 18 marks over 13 chains do not change.
- bench/figures.py and the command openconsult-bench figures: the rules
  of 7 Oct in the repo's own tool. The typical pass of a round, Rule B at
  half a second in every round, the steadiness of the day on Ollama's own
  rounds, the tokens written and the time for each token, and the counts
  from the replies: failed chains, replies cut mid-sentence, empty and
  kept lists, time critical with no action, the first alarm, the same
  answer in every chain at 0. It works from the public folder alone and
  gives the same figures from the private result folders. The rounds and
  the arms' roles are data (engine-bench/rounds.json). Every figure in
  seconds is rounded half up from the milliseconds, once. The compare
  command, its line of 1 second and the 13-chain candidate went.
- The exporter takes the card's memory over an arm's own steps (--steps),
  because the arms took turns through the day.
- Published in engine-bench: the report, how the bench was run, the
  cases, the six arms of 7 Oct, rounds.json, the tool's figures as data,
  the machine's figures as small data files, and bench-of-6-oct with the
  two kept parts of the first bench. 71 files, 4.2 MB.
- No library added. NOTICE has nothing to add.

The rulings of spec 15.8, each in one line:
1. Every prompt a model reads is put to the owner word for word. No
   prompt changed; the two hashes are as v1's.
2. The engine bench is published. Done: engine-bench.
3. The v1 service is off. Nothing to do here.
4. What the plan review of stage 3 settled is in the spec. Nothing here.
5. An empty list keeps the earlier list. Done, in the pass.
6. Showing the app somewhere else: stage 6's brainstorm. Nothing built.
7. The vLLM arm ran the repack by xbill9, at its fixed revision. Done.
8. The calls of a pass are also sent together, as a measurement. Done.
9. Does an engine give the same answer twice: the repeat test, 6 Oct. Done.
10. What counts as faster, as first fixed. Replaced by 17 and 18.
11. Every case the bench reads is published. Done.
12. The words in the terminal at the start. Done.
13. The together arm on Ollama ran on a second Ollama process. Done.
14. Ollama runs llama.cpp inside it. Said in the report.
15. The two travel cases are published unchanged, with a note. Done.
16. The push was held and vLLM got a second arm, with the switch. Done.
17. Faster means half a second, in every round. In the tool.
18. Temperature 0 decides who is a candidate. In the tool.
19. The full bench ran again on 7 Oct. Done.
20. The together arms ran the three chains at temperature 0. Done.
21. Three rounds, the order rotating; steadiness on Ollama. Done.
22. vLLM ran with the switch only; two figures per engine. Done.
23. The first bench waited for the second. Done.
24. One public bench, the bench of 7 Oct. Done.
25. What the public folder holds. Done, as written.
26. Anyone can rerun the figures: openconsult-bench figures. Done.
27. How the two commits came out: bundle, then one rebase. Done.
28. The first lines of the report in the owner's words; the docs script
    checks each figure in them against the tool. Done.

Decided in the plan reviews (Cowork), as decisions of this stage:
- 6 Oct: the kept list holds the earlier entries whole, marked kept; a
  failed assessment call is not an empty list. vLLM 0.31.0 and llama.cpp
  v0.6.0, the newest on the day. In the repeat test the earlier list came
  from the reference arm's chain A1. Nothing public names a path, a user
  or a host; the word check reads the unpacked text of each packed file.
- 7 Oct: the card over an arm's own steps is the pooled median. A reply
  that did not end ok or cannot be read as its form is counted apart,
  never as cut. A difference below zero is written as longer. The kept
  files of 6 Oct are as written then, and the note in bench-of-6-oct says
  what candidate meant that day. No figure from an arm that is not in
  the folder. Seconds are rounded half up from the milliseconds, once.

For stage 6:
- Whether the screen keeps the earlier list through a failed assessment
  call is the owner's ruling then. Nothing is built for it.
- Sending the two calls together shortens the pass on every engine, but
  the alarm itself comes back later (1.46 s against 1.12 s on Ollama),
  and on Ollama it needs OLLAMA_NUM_PARALLEL=2, which the service does
  not set. The app still sends one after another.
- The stray quote (ruling 16) goes to the session on the two carried
  prompts. The engine choice has a brainstorm of its own: a compact form
  for Ollama or llama.cpp, and the speech model beside the language model
  on the card, were not tested.

Measurements. The bench's figures are from engine-bench/README.md.
- 199 tests, 4.5 s, none skipped (191 before). App code about 2,260 lines
  without the bench; the bench 2,064; tests 3,190. Largest file
  bench/figures.py, 407 lines. CLAUDE.md 99 lines.
- The run of 7 Oct: 768 chains, 14,016 calls, every call ok, no chain
  failed; 07:17 to 15:25, nobody at the desk, the screensaver never seen
  in 487 minutes.
- Every hard mark met on every engine at both temperatures. Over 13
  chains llama.cpp missed two soft marks (S10 13, 9 and S14 6).
- The typical pass of 495 by round, one after another: Ollama 5.13,
  5.07, 5.12 s; llama.cpp 5.12, 5.12, 5.12; vLLM 3.56, 3.47, 3.43. Sent
  together: 3.76, 3.76, 3.75; 3.83, 3.81, 3.85; 2.78, 2.78, 2.77. The day
  was steady: Ollama's rounds 0.06 s apart.
- Rule B: vLLM faster by the rule, 1.57, 1.61 and 1.69 s shorter than
  Ollama one after another and 0.98, 0.99, 0.98 s shorter together.
  llama.cpp not faster either way (0.01 shorter to 0.05 longer; 0.07 to
  0.10 longer together). Every together arm is more than 1.25 s shorter
  than Ollama one after another in every round.
- At temperature 0 vLLM wrote 254,979 tokens against 319,170 on Ollama
  and 325,947 on llama.cpp (20 % fewer), at 5.33 ms a token against 6.44
  and 6.52 (17 % less). About half of its gain is the switch.
- Replies cut mid-sentence at 0.5: Ollama 23, llama.cpp 35, vLLM 21 of
  2,920; at 0: 0, 6, 0. The vLLM arm of 6 Oct without the switch: 14
  chains failed, all at 0.5. Time critical with no action: 65, 29, 73.
- The same answer in all three chains at 0: 16 of 16 cases on Ollama
  and llama.cpp, 0 on vLLM. The repeat test of 6 Oct, sets of ten all the
  same, of 12: Ollama 2; llama.cpp 3, and 12 with its prompt cache off;
  vLLM 0, and 10 with batch invariance on.
- The card, pooled over each arm's own steps: Ollama 17,139 MiB (70 %),
  llama.cpp 15,591 (63 %), vLLM 23,137 (94 %, its fixed share). Starts:
  llama.cpp 2.0 s, vLLM 25.8 s; Ollama's first call with the model not
  loaded 3.4 to 3.5 s.
- Empty lists: 3 on Ollama, each kept, all at 0.5; none elsewhere.
- The private word check printed nothing before every commit but the
  published folder's, where its 61 lines are all in case and reply files
  and equal the list Cowork read at the gate.

Made untrue by this stage:
- CLAUDE.md, Running it: the bench commands, now with figures and export
  and the kinds of engine. README: the line that points to engine-bench.
  Both fixed in this commit.
- V2_SPEC.md 15.8, the details of 6 Oct: the reference arm is not
  published (ruling 25 says so); compare.json and compare.md no longer
  exist; the typical pass of ruling 10 is replaced by that of 17. Ruling 7
  and 15.7 ruling 5 were corrected by the owner on 6 Oct. 15.8 ruling 24
  gives the card as 23,137 and 17,139 MiB: that is the pooled median over
  the arm's own steps, which the tool and the exporter now use.
- V1_LESSONS 9.1 says temperature 0 with a fixed seed is not
  reproducible. On 7 Oct it was, on Ollama and llama.cpp, on 16 of 16
  cases over three chains hours apart; on vLLM it was not.

Next: the owner reads the report and pushes; the GitHub check must be
green on all three systems. Then, if he wishes, his answer to issue 1 in
his own words. Owed before stage 6: the session in which the owner and
Cowork read the two carried prompts word for word.

## 2026-10-04. Stage 3: the language model door

What was done:
- Every call to the language model goes through one door (openconsult/llm):
  a table of two jobs, the assessment and the alarm, each with its prompt
  file, answer form, limit on length (1,500 and 1,000 tokens) and limit on
  time (60 s each). One result: an answer, or a failure with its reason:
  too slow, too long, unreachable, bad form, or did not fit. Nothing is
  retried and nothing else is tried.
- The door writes the record of every call itself, table model_call at
  version 2: when, the job, the engine and its version, the model's tag
  and digest, the hash of the prompt sent, exactly what was sent, the raw
  reply, the tokens, the times and the outcome. It lives in the data
  folder only. A version 1 folder comes forward with nothing lost.
- The two prompts cross from v1 word for word as files in
  openconsult/prompts, with their forms and the fixed words around the
  transcript as frames; one loader; the app and the bench read the same
  files. Their hashes equal v1's recorded values and a test pins them.
- One pass (openconsult/consult): the alarm first, then the assessment,
  both with the patient line, the assessment with the earlier names as a
  stale list; the bookkeeping in code; a failed alarm is a third state,
  not judged, never read as no alarm.
- The joint between the door and an engine carries the parts of a call and
  one plain reply. The Ollama engine behind it uses the standard library.
- The app opens the browser by itself once it answers; --no-browser.
- This machine says whether Ollama runs and whether Gemma 4 QAT is
  present, on a machine with a suitable card only.
- The bench kit (openconsult/bench): the case list with checksums, 13
  chains, the replay through the same door, a writer that never writes
  over a result, the scoring with the marks of Tasks 5 and 5b, the word
  check, and the command openconsult-bench. Cases and results live in the
  private log folder; the repo holds the code and the marks only.
- No library added. NOTICE has nothing to add.

The rulings of spec 15.7, each in one line:
1. The stage 2 leftovers are in 15.6. Nothing to do here.
2. The browser opens by itself once the app answers; --no-browser for the
   tests and the GitHub check; no screen is not an error. Done.
3. The same marks: the word check rebuilt 1,898 of 1,898 assessment and
   1,898 of 1,898 alarm calls of arm D exactly, and the 13-chain run met
   every hard mark (7 of 7), both time marks and 8 of 9 soft marks. Done.
4. Gemma 4 QAT only; the joint is built so Claude and Qwen fit later with
   no change to the jobs. Done.
5. The engine bench is stage 3b. The bench takes any engine's address. Nothing else here.

Decided in the plan review of 4 Oct 2026 (Cowork), as decisions of this stage:
- The door sends "truncate": false. Measured that day: by default this
  Ollama (0.33.3) cut a 77,585-token input to 8,195 tokens, half the
  context, and answered as if nothing had happened; with the field it
  refuses with HTTP 400 exceed_context_size_error, which the door records
  as did_not_fit. The word check compares the message, model, think and
  options one by one and then the whole body with that one key removed.
  v1 runs with Ollama's default.
- The record holds the sha256 of the system message as sent, equal to
  v1's recorded value (the file's text less its final line break).
- What crosses the joint is the parts of a call, not Ollama's shape;
  keep_alive 30m lives in the Ollama engine.
- The two This machine lines show only on a machine with a suitable card;
  elsewhere nothing about Ollama is shown and Ollama is not asked.
- The soft marks stand as the numbers fixed against arm N in Task 5b
  (03, 04, 11, 13 at most 1 chain fired; 05 at most 4; script 12 at most
  13 and a median of at most 5 updates; restraint 13, 14, 15 at least 12;
  cleared at least 12 on each emergency script). Arm D's figure is shown
  beside each as v1 today.
- A failed alarm call is a third state in the pass result: not judged,
  with the reason. A script chain with any failed call is a failed chain;
  on 495 and the travel cases a failed pass meets no rule.
- The two time marks were set for a three-call pass; v2's pass is two
  calls (no affect call, which took part in no mark). Reported as written.
- R21's check names no publisher: the prompts hold no guideline word and
  every capitalised word in a prompt is on a known list in the test.
- The sampling override on the door is reachable from the bench only. It
  is not a setting. The engine's address is one fixed value in the store.
- browser.py sits at the top of the package beside cli.py.
- HOME_SO_FAR and the This machine lines are drafts for the owner.

For stages 6 and 12: the door's call waits until the reply comes. The
live consultation must not wait on it in the page's own loop, and a call
already sent cannot be taken back, only its result dropped. Nothing is
built for this now. Stage 6 also ties each model_call row to its
consultation (version 3) and shows a failed call's reason on screen.

Measurements:
- 141 tests, 3.5 s, none skipped (98 test functions; the parametrised
  cases counted as pytest counts them).
- App code about 2,230 lines in openconsult without the bench; the bench
  about 780; the start check 79. Templates and the style sheet 265.
  Tests 2,070 lines. Largest file bench/score.py, 292 lines; largest
  function, its marks table, 64 lines. CLAUDE.md 99 lines.
- The word check, no model: 1,898 of 1,898 assessment and 1,898 of 1,898
  alarm calls of arm D rebuilt exactly (495 and travel from Task 5, the
  13 scripts from Task 5b); Task 5's single-run script calls 242 of 242.
- The run: 16 cases, 13 chains each, 208 chains, 1,898 passes, 3,796
  calls, none failed, no cap hit, no thinking text; 2 h 24 min; the
  card's memory 17,379 to 17,846 MiB. Ollama 0.33.3; Gemma 4 QAT digest
  2dd70431...c4e4, as Tasks 5 and 5b; the two prompt hashes as v1's.
- Marks: hard 7 of 7; time 2 of 2 (495 median pass 4.63 s, slowest
  7.01 s, two calls); soft 8 of 9. The miss is S15 on script 15: 11
  chains of 13 passed the restraint verdict against a mark of 12 (arm N
  and arm D 13). In chains A2 and A3 the assessment at the last update
  gave an empty differential list, so no leader could be judged; the
  alarm fired and cleared in all 13. Task 5b saw four such empty lists
  in arm D, three of them on script 15. The owner and Cowork decide.
- The private word check printed nothing before every commit.
- A1, A2 and A3 gave the same answers throughout on 2 of 16 cases:
  temperature 0 with seed 42 is not reproducible on this machine
  (V1_LESSONS 9.1, seen again).

Made untrue by this stage:
- CLAUDE.md, Running it: the switch and the bench commands added here.
  README: now says the door exists. Both fixed in this commit.
- V2_SPEC.md 15.7, the details: "the model's profile holds ... keep_alive"
  is no longer so (it lives in the Ollama engine); "a request in Ollama's
  shape" nowhere, but the joint is now the plain parts; the two This
  machine lines are on a suitable card only; the record's prompt hash is of
  the text sent. Cowork folds these into the spec at the next brainstorm.
- Spec 15.7 says the assessment's frames and the alarm's frame live in
  the prompts folder as "the fixed words": they are the three .frame.txt files.

Next: the owner's check on port 8001 (the browser opens by itself; This
machine shows the two lines), then push; the GitHub check must be green
on all three systems. Then the stage 3b brainstorm, the engine bench.

## 2026-10-04. Stage 2: the skeleton

What was done:
- The app starts. One person accepts the statement, sees This machine,
  sets up a title, a name and a password, and logs in. The settings page
  has This machine and You. The log page shows the audit log. The reset
  command resets the password. Nothing of a patient, a model or sound.
- One package, openconsult, on Python 3.12 with the lock file committed.
  Libraries: fastapi, uvicorn, jinja2; for tests pytest and httpx2. All
  pure Python or prebuilt wheels; nothing needs a compiler or a card.
- SQLite, from Python's own library. Four tables at version 1:
  schema_version, app_user, audit_log, first_run. Triggers make the audit
  log append-only.
- A GitHub check on Linux, Windows and macOS at every push to v2:
  install from the lock, run the suite, start the app, check it answers,
  stop it. Outside steps pinned: actions/checkout v7.0.1 at
  3d3c42e5aac5ba805825da76410c181273ba90b1; astral-sh/setup-uv v9.0.0 at
  c771a70e6277c0a99b617c7a806ffedaca235ff9; uv 0.12.10.

The rulings of spec 15.6, each in one line:
1. CLAUDE.md now says only documents are limited at the root. Done.
2. CITATION.cff is stage 16. Nothing to do here.
3. Every commit from stage 2 ends with the co-author line. Done.
4. The statement comes first and is audited; no user before it. Done.
5. The 30 minute lock, a named value in logins.py; a consultation holds
   it off through a flag stage 6 will set. Done.
6. The app listens on 127.0.0.1 only, with no flag to change it. Done.
7. The You section: title, name, password, current password first,
   every change audited from what to what. Done.
8. v1's look, the style sheet cut from 195 to about 90 lines. Done.
9. Cloud services with a free trial: later stages. Nothing here.
10. The engine choice: stage 3 brainstorm. Nothing here.

Decided in the plan review of 4 Oct 2026 (Cowork), as decisions of this stage:
- The settings store holds only the data folder and the port; no table,
  no page and no change method until a page-changeable setting exists.
- No page script in stage 2. The refusal helper is server-side Python:
  the page is sent back with the message under the control pressed, and
  the helper raises if the message would land nowhere.
- The wrong-password wait: 1 second after the first wrong try, doubling,
  capped at 5 minutes, cleared by a right password or a restart. A design
  choice, not a measurement; named in logins.py with the review as source.
- A card is suitable when its memory rounds to 24 GB or more.
- After set-up the user goes to the login page.
- The Mac sentence and the card-could-not-be-read sentence are drafts.
- A reset in another process ends the app's logins through a generation
  number on the user row; each login remembers the one it was made under.
- The This machine step is done when its Continue is pressed.
- No test holds its own copy of a sentence. Every sentence is in
  openconsult/words.py; tests take it from there or check which case the
  code chose. The owner corrects wording in that one file.
- The lock clears a screen nobody is using: every page behind the login
  carries a plain refresh instruction to itself with ?quiet after the
  time left. A ?quiet request never counts as use. If another tab kept
  the login alive the page waits again for the time left; otherwise the
  lock line is written then and the page goes to login with the reason.

For stage 6: when a page has text being typed, typing must count as use.
That needs a page script and is that stage's work. The quiet refresh also
re-renders a page, so a page with a form in progress needs the script to
hold the refresh off while typing. The consultation_running flag on
Logins is the hook for the live page.

Three fixes after Cowork's check, same day (stage-prompts/STAGE_02_FIXES.md):
- A page sent back by a form post now names its own GET address for the
  timed move, so a refused Settings form left alone locks to the login
  page and writes the lock line, instead of ending on a 405.
- A wrong current password in Settings is written to the log and counts
  on the same growing wait as the login page; while the wait runs both
  forms refuse and change nothing. The refusal sentence now says the wait.
- No test runs the real nvidia-smi: the command takes the machine like
  its saying and serving functions, and its test gives a made-up one.

Measurements (after the fixes):
- 76 tests, 1.9 s, none skipped. The twins and the parametrised cases
  are counted as pytest counts them.
- App code about 1,350 lines in 20 Python files; largest routes.py, 209 lines.
  Templates and the style sheet, 261 lines. Tests 959 lines.
- Largest function: well under 80 lines. No file near 600.
- The private word check printed nothing before every commit.

Not in the plan: the plan's commits 10 and 11 became one commit, because
the login tests need a set-up user and the only honest way to one is
through the first-run screens. Two drafted sentences were not used:
"Accept the statement first." and "OpenConsult is already set up.",
because a form sent at the wrong step goes back to the right step
instead.

Made untrue by this stage:
- CLAUDE.md, Running it: rewritten here. README: no longer says the app
  does not run. Both are fixed in this commit.
- V2_SPEC.md 15.6 "the settings store ... a change is written to the
  audit log": true from the first page-changeable setting, not in stage 2.
  And "plain pages, with their scripts in their own files": there are no
  scripts yet. Cowork folds both into the spec at the next brainstorm.

Next: the owner's check on port 8001, then push; the GitHub check must be
green on all three systems. Then the stage 3 brainstorm.

## 2026-10-04. Stage 1: the v2 branch is opened

What was done:
- A new branch, v2, in its own folder. It shares no history with main.
- Three commits: the spec and the lessons; the licence, the notice and the
  ignore list; CLAUDE.md, this file, a holding README and the stage prompt.
- No code. Nothing runs yet.

Decided by the owner on 4 Oct 2026 (spec 15.5):
- The spec is approved. It changes only by a dated ruling of his.
- A privacy pass before anything is public. Nothing committed names a
  family member, a colleague, a home or a place.
- One spec, and it lives in this folder.
- The licence stays as v1: AGPL-3.0-or-later.

Waiting for later stages:
- The community files (CONTRIBUTING, SECURITY, the code of conduct,
  CITATION.cff, the issue templates) cross from v1 in stage 16, before the
  join of spec 14.3.
- NOTICE gains an entry in the same commit as each third-party component.

Made untrue by this stage: nothing.

Next: stage 2, the skeleton, after its brainstorm.
