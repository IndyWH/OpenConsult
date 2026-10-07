# The engine bench of 7 Oct 2026: Ollama, llama.cpp and vLLM on the same cases

OpenConsult is a research and education prototype. It is not a medical device. It is never used
with real patients. Every case in this bench is acted or scripted.

Run on 7 Oct 2026. It answers issue 1 of this repository.

## 1. What a pass is, and the result

OpenConsult listens to an acted consultation. Every few turns it asks a language model two
things: is anything urgent (the alarm), and what could this be (the assessment). The two calls
together are one pass: the time of a pass is the time the patient waits for both answers. One
run of one case, from its first turn to its last, is a chain. The day had three rounds. In each
round every engine ran once, and the order changed from round to round.

1. The clinical marks hold on all three engines. At the temperature the app uses, every hard mark was met and no chain failed.
2. vLLM is faster. Its typical pass took 3.5 seconds, against 5.1 seconds on Ollama.
3. llama.cpp is not faster. Its typical pass took 5.1 seconds, the same as Ollama.
4. Sending the two calls of a pass together shortens the wait on every engine: 3.8 seconds on Ollama, 3.8 on llama.cpp, 2.8 on vLLM.
5. vLLM ran a version of the model made by an individual, with one switch that makes its answers shorter. About half of its gain comes from the shorter answer, and half from a faster engine. It holds 94 % of the card's memory, against 70 % for Ollama.
6. OpenConsult still runs on Ollama. No engine is changed on this bench alone.

Where the figures in these lines come from: each time is the middle one of the engine's three
rounds at temperature 0, to one decimal place; each share of the card is the typical memory in
use during the engine's own steps, out of the card's 24,564 MiB. Section 14 gives the one
command that works out again, from the replies in this folder, every figure of this page that
comes from the replies of 7 Oct. The figures that come from the machine are in machine/, and
those of 6 Oct in bench-of-6-oct/.

| Engine, way | Rounds 1, 2, 3 (s) | The middle one, to one place | Share of the card |
|---|---|---|---|
| Ollama | 5.13, 5.07, 5.12 | 5.1 | 70 % |
| llama.cpp | 5.12, 5.12, 5.12 | 5.1 | 63 % |
| vLLM | 3.56, 3.47, 3.43 | 3.5 | 94 % |
| Ollama, together | 3.76, 3.76, 3.75 | 3.8 | 73 % |
| llama.cpp, together | 3.83, 3.81, 3.85 | 3.8 | 66 % |
| vLLM, together | 2.78, 2.78, 2.77 | 2.8 | 94 % |

## 2. What this bench is, and what it is not

- One machine. One graphics card, an NVIDIA RTX 4090 with 24 GB. One model, Gemma 4 26B A4B,
  in its 4-bit form. One user: one call at a time, or the two calls of one pass together.
- One day, 7 Oct 2026, from 07:17 to 15:25, with nobody at the desk. Each
  engine ran three times, once in each round, and the order of the engines changed from round to
  round, so that the hour of the day could not favour one of them. Two runs of the same arm still
  differ by chance, so a small difference between two arms is not a finding.
- Ollama and llama.cpp ran one and the same file, Google's own. Its weights are, byte for byte,
  the weights behind Ollama's own tag; only the file's header differs (HOW_IT_WAS_RUN.md, section 3).
- vLLM cannot read that file. **The vLLM arm ran a version of the model made by an individual**,
  `xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct` (huggingface.co/xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct). Its page says it is "an unofficial repack, made
  and published independently of Google", that it holds Google's own trained weights, and that
  "It does no new quantization." Its own check found every weight level on Google's grid and
  89.7 to 92.6 % of the values bit-identical, the rest differing "by at most 1.1e-2 relative".
  It was tested by its maker on an older vLLM, another card and a small context. So the vLLM arm
  measures the engine and that version together, and cannot tell them apart.
- **vLLM ran with one switch**, which forbids free blank space in a formed answer
  (`disable_any_whitespace`, off by default; the form held by xgrammar). Section 7 says why, and
  what the switch does to the answers.
- Why there is no file from Google for vLLM. vLLM's own page for Gemma 4 says: "The 26B-A4B MoE
  model is not included — its small expert dimensions (704) cause excessive quality loss with
  4-bit quantization." (docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html) Google
  publishes a 4-bit file for this model, the one the other two arms ran, and the repack is made
  from the weights of that same training. The marks of the arm are the measurement.
- **What the llama.cpp arm compares.** Ollama 0.33.3 runs llama.cpp's own server inside it. With
  the model loaded, the Ollama service on this machine was seen running a `llama-server` process,
  and Ollama's source names the llama.cpp build it carries
  (github.com/ollama/ollama/blob/v0.33.3/LLAMA_CPP_VERSION). So the llama.cpp arm is not a
  different engine from the Ollama arm. It is llama.cpp's newest release, spoken to directly,
  with the chat template inside the model file, against the older llama.cpp build inside Ollama,
  with Ollama's own code writing the prompt and Ollama's settings.
- **Ollama's own tag.** OpenConsult uses Ollama's own tag of the model. This bench ran Ollama on
  Google's file instead, so that Ollama and llama.cpp read one file. The own tag met every hard
  mark in OpenConsult's own proof run of 4 Oct 2026, and no data of that run is in this folder.
- Every call on every engine was the same: the same two prompts, the same patient line, the same
  answer form, the same limits, thinking off, a context of 16,384. Proved again on each of the
  five engine starts before the first round: no thinking text, replies fit their form, a
  full-context call is accepted, an oversize input is refused and not cut (machine/proofs.json;
  HOW_IT_WAS_RUN.md, section 8).

## 3. The rules fixed before the run

- **The marks.** The 18 marks of OpenConsult's own bench, with their pass lines, fixed before the
  first bench and unchanged since: seven hard, nine soft, two on time. Section 4 lists them.
- **Rule A, who is a candidate.** The app sends temperature 0 with seed 42 and nothing else, so
  the patient only ever meets temperature 0. An engine is a candidate if every hard mark is met on
  its three chains at temperature 0 and none of those chains failed. The ten chains at
  temperature 0.5 are a stress test: counted the same way, reported apart, and they bar nothing.
- **Rule B, what counts as faster.** The typical pass of a round is the median of the 11 passes of
  consultation 495 in that round's chain at temperature 0. An engine is called faster in a way
  that matters to the patient only if it is a candidate and its typical pass is at least 0.50 s
  shorter than Ollama's in each of the three rounds, the engine against Ollama in the same round.
  A smaller difference, or one that holds in some rounds only, is a figure and not a win.
- **The steadiness of the day.** If Ollama's own typical pass, calls one after another, differs
  between its three rounds by more than 0.25 s, the day was too unsteady and no engine is called
  faster.
- **Seven judgements.** llama.cpp and vLLM, each one after another against Ollama one after
  another, and each sent together against Ollama sent together; and every arm sent together,
  Ollama's own included, against Ollama one after another, which is what the app does today.
- **Two figures for each engine.** The wait, which is what the patient feels, and the time for
  each token written, which shows the engine's own speed apart from the length of its answers.

## 4. The clinical marks

Each case ran as 13 chains on each engine: 3 at temperature 0 with seed 42 and 10 at temperature
0.5 with seeds 1 to 10. 768 chains and 14,016 calls in all on 7 Oct; every call ended ok and no
chain failed on any engine at either temperature.

**At temperature 0, the deciding figures.** A figure is the number of chains, of 3. The soft marks
have their lines over 13 chains, so over 3 they are given as values only.

| | Rule | Mark, over 3 chains | Ollama | llama.cpp | vLLM | Ollama, together | llama.cpp, together | vLLM, together |
|---|---|---|---|---|---|---|---|---|
| H1 | Consultation 495: ectopic pregnancy is on the list at some pass | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| H2 | 495: the alarm names a pregnancy test or hCG | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| H3 | Travel case 1: dengue is on the list by turn 20 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| H4 | Travel case 2: malaria is on the list by turn 16 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| H5 | Travel case 2: the alarm has fired by turn 16 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| H6 | Each of the seven emergency scripts fires (01, 06, 07, 08, 10, 14, 15) | 3 on each | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 |
| H7 | Male cases: chains that name pregnancy, ectopic, ovarian or hCG (T2, 01, 05, 06, 07, 10, 12, 15) | 0 on each | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 |
| S8 | 495: ectopic pregnancy is first on the list at the last pass | value only | 3 | 3 | 3 | 3 | 3 | 3 |
| S9 | 495: asks about the last period, pregnancy or contraception | value only | 3 | 3 | 3 | 3 | 3 | 3 |
| S10 | Travel cases 1 and 2: asks about travel by turn 12 | value only | 3, 3 | 3, 3 | 3, 3 | 3, 3 | 3, 2 | 3, 3 |
| S11 | Travel case 2: no urgent action at turn 28 | value only | 3 | 3 | 3 | 3 | 3 | 3 |
| S12 | Routine scripts where the alarm fires (03, 04, 05, 11, 13) | value only | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0 |
| S13 | Script 12: chains where the alarm fires | value only | 3 | 3 | 3 | 3 | 3 | 3 |
| S14 | Script 12: median updates with an alarm | value only | 5 | 7 | 3 | 4 | 7 | 3 |
| S15 | Restraint scripts that pass their verdict (11, 12, 13, 14, 15) | value only | 0, 0, 3, 3, 3 | 0, 0, 3, 3, 3 | 0, 0, 3, 3, 3 | 0, 0, 3, 3, 3 | 0, 0, 3, 3, 3 | 0, 0, 3, 3, 3 |
| S16 | Emergency scripts cleared at the last update | value only | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 | 3, 3, 3, 3, 3, 3, 3 |
| | Every hard mark met, no chain failed | | yes | yes | yes | yes | yes | yes |

**The stress test at 0.5, apart.** A figure is the number of chains, of 10. It bars nothing.

| | Rule | Mark, over 10 chains | Ollama | llama.cpp | vLLM |
|---|---|---|---|---|---|
| H1 | Consultation 495: ectopic pregnancy is on the list at some pass | 10 | 10 | 10 | 10 |
| H2 | 495: the alarm names a pregnancy test or hCG | 10 | 10 | 10 | 10 |
| H3 | Travel case 1: dengue is on the list by turn 20 | 10 | 10 | 10 | 10 |
| H4 | Travel case 2: malaria is on the list by turn 16 | 10 | 10 | 10 | 10 |
| H5 | Travel case 2: the alarm has fired by turn 16 | 10 | 10 | 10 | 10 |
| H6 | Each of the seven emergency scripts fires (01, 06, 07, 08, 10, 14, 15) | 10 on each | 10, 10, 10, 10, 10, 10, 10 | 10, 10, 10, 10, 10, 10, 10 | 10, 10, 10, 10, 10, 10, 10 |
| H7 | Male cases: chains that name pregnancy, ectopic, ovarian or hCG (T2, 01, 05, 06, 07, 10, 12, 15) | 0 on each | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 |
| S8 | 495: ectopic pregnancy is first on the list at the last pass | value only | 10 | 10 | 10 |
| S9 | 495: asks about the last period, pregnancy or contraception | value only | 10 | 10 | 10 |
| S10 | Travel cases 1 and 2: asks about travel by turn 12 | value only | 10, 9 | 10, 6 | 10, 10 |
| S11 | Travel case 2: no urgent action at turn 28 | value only | 10 | 10 | 10 |
| S12 | Routine scripts where the alarm fires (03, 04, 05, 11, 13) | value only | 0, 0, 1, 0, 0 | 0, 0, 4, 0, 0 | 0, 0, 0, 0, 0 |
| S13 | Script 12: chains where the alarm fires | value only | 10 | 10 | 10 |
| S14 | Script 12: median updates with an alarm | value only | 4.00 | 6.00 | 3.00 |
| S15 | Restraint scripts that pass their verdict (11, 12, 13, 14, 15) | value only | 0, 0, 10, 10, 10 | 0, 0, 10, 10, 10 | 0, 0, 10, 10, 10 |
| S16 | Emergency scripts cleared at the last update | value only | 10, 10, 10, 10, 10, 10, 10 | 10, 10, 10, 10, 10, 10, 10 | 10, 10, 10, 10, 10, 10, 10 |
| | Chains that failed | | 0 | 0 | 0 |

**Over all 13 chains**, as OpenConsult's own bench counts them, for comparison.

| | Rule | Mark, over 13 chains | Ollama | llama.cpp | vLLM |
|---|---|---|---|---|---|
| H1 | Consultation 495: ectopic pregnancy is on the list at some pass | 13 | 13 | 13 | 13 |
| H2 | 495: the alarm names a pregnancy test or hCG | 13 | 13 | 13 | 13 |
| H3 | Travel case 1: dengue is on the list by turn 20 | 13 | 13 | 13 | 13 |
| H4 | Travel case 2: malaria is on the list by turn 16 | 13 | 13 | 13 | 13 |
| H5 | Travel case 2: the alarm has fired by turn 16 | 13 | 13 | 13 | 13 |
| H6 | Each of the seven emergency scripts fires (01, 06, 07, 08, 10, 14, 15) | 13 on each | 13, 13, 13, 13, 13, 13, 13 | 13, 13, 13, 13, 13, 13, 13 | 13, 13, 13, 13, 13, 13, 13 |
| H7 | Male cases: chains that name pregnancy, ectopic, ovarian or hCG (T2, 01, 05, 06, 07, 10, 12, 15) | 0 on each | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0, 0, 0 |
| S8 | 495: ectopic pregnancy is first on the list at the last pass | at least 12 | 13 | 13 | 13 |
| S9 | 495: asks about the last period, pregnancy or contraception | at least 12 | 13 | 13 | 13 |
| S10 | Travel cases 1 and 2: asks about travel by turn 12 | at least 10 each | 13, 12 | 13, 9, **missed** | 13, 13 |
| S11 | Travel case 2: no urgent action at turn 28 | at least 10 | 13 | 13 | 13 |
| S12 | Routine scripts where the alarm fires (03, 04, 05, 11, 13) | at most 1, 1, 4, 1, 1 | 0, 0, 1, 0, 0 | 0, 0, 4, 0, 0 | 0, 0, 0, 0, 0 |
| S13 | Script 12: chains where the alarm fires | at most 13 | 13 | 13 | 13 |
| S14 | Script 12: median updates with an alarm | at most 5 | 4 | 6, **missed** | 3 |
| S15 | Restraint scripts that pass their verdict (11, 12, 13, 14, 15) | at least 0, 0, 12, 12, 12 | 0, 0, 13, 13, 13 | 0, 0, 13, 13, 13 | 0, 0, 13, 13, 13 |
| S16 | Emergency scripts cleared at the last update | at least 12 on each | 13, 13, 13, 13, 13, 13, 13 | 13, 13, 13, 13, 13, 13, 13 | 13, 13, 13, 13, 13, 13, 13 |
| T17 | 495: typical pass, seconds | at most 6.0 | 4.97 | 5.17 | 3.78 |
| T18 | 495: slowest pass, seconds | at most 8.0 | 5.48 | 5.63 | 4.24 |
| | Hard marks met | 7 | 7 of 7 | 7 of 7 | 7 of 7 |
| | Soft marks met | 9 | 9 of 9 | 7 of 9 | 9 of 9 |
| | Chains that failed, of 208 | | 0 | 0 | 0 |
| | Empty lists in replies | | 3 | 0 | 0 |
| | Earlier list kept | | 3 | 0 | 0 |

What stands out:

- Every hard mark was met on every engine at both temperatures. No chain failed.
- The soft marks over 13 chains: Ollama and vLLM met all nine; llama.cpp missed S10, S14
  (S10: 13, 9 against a line of at least 10 each; S14: 6 against a line of at most 5).
- Script 12, the dizziness case, is where the engines differ most: the median number of updates
  with an alarm (S14) at temperature 0 is 5 on Ollama, 7 on llama.cpp and 3 on vLLM.
- Empty lists of differentials, which the app fills with the earlier list: Ollama 3 (each kept),
  llama.cpp 0, vLLM 0. All of Ollama's were at temperature 0.5.
- The alarm on consultation 495 first showed at pass 3 on Ollama, at pass 2 on llama.cpp and at
  pass 2 on vLLM, in all three chains at temperature 0. Section 8 has the first alarm of every case.

## 5. The seconds, round by round

A pass is the alarm call and then the assessment call, timed by the bench's own clock, the same
for every engine. The typical pass is the median of the 11 passes of consultation 495 in the
round's chain at temperature 0. Beside it: the slowest of those 11, the median over the passes of
all 16 cases in that chain, the median of each call, the tokens written in the chain, and the
milliseconds for each token written, all in (the whole wait over the tokens) and writing only
(the engine's own writing time over the tokens).

| Arm | Round | Chain | Typical pass of 495 | Slowest, 495 | Typical pass, all cases | Alarm call | Assessment call | Tokens written in the chain | ms for each token, all in | ms for each token, writing only |
|---|---|---|---|---|---|---|---|---|---|---|
| Ollama | 1 | A1 | 5.13 | 5.40 | 4.74 | 1.12 | 3.50 | 106,390 | 6.45 | 5.93 |
| Ollama | 2 | A2 | 5.07 | 5.34 | 4.72 | 1.12 | 3.50 | 106,390 | 6.43 | 5.92 |
| Ollama | 3 | A3 | 5.12 | 5.36 | 4.72 | 1.12 | 3.50 | 106,390 | 6.44 | 5.92 |
| llama.cpp | 1 | A1 | 5.12 | 5.47 | 4.90 | 1.27 | 3.59 | 108,649 | 6.52 | 5.95 |
| llama.cpp | 2 | A2 | 5.12 | 5.47 | 4.90 | 1.27 | 3.59 | 108,649 | 6.52 | 5.95 |
| llama.cpp | 3 | A3 | 5.12 | 5.47 | 4.90 | 1.27 | 3.59 | 108,649 | 6.52 | 5.95 |
| vLLM | 1 | A1 | 3.56 | 3.67 | 3.13 | 0.75 | 2.32 | 84,796 | 5.33 | 5.22 |
| vLLM | 2 | A2 | 3.47 | 3.68 | 3.13 | 0.73 | 2.34 | 85,071 | 5.33 | 5.22 |
| vLLM | 3 | A3 | 3.43 | 3.50 | 3.13 | 0.74 | 2.33 | 85,112 | 5.33 | 5.22 |
| Ollama, together | 1 | A1 | 3.76 | 4.16 | 3.67 | 1.46 | 3.65 | 106,160 | 7.04 | 6.17 |
| Ollama, together | 2 | A2 | 3.76 | 4.16 | 3.68 | 1.46 | 3.67 | 106,160 | 7.05 | 6.17 |
| Ollama, together | 3 | A3 | 3.75 | 4.16 | 3.68 | 1.46 | 3.67 | 106,160 | 7.04 | 6.17 |
| llama.cpp, together | 1 | A1 | 3.83 | 4.07 | 3.75 | 1.65 | 3.73 | 108,402 | 7.15 | 6.20 |
| llama.cpp, together | 2 | A2 | 3.81 | 3.96 | 3.71 | 1.67 | 3.70 | 108,407 | 7.14 | 6.20 |
| llama.cpp, together | 3 | A3 | 3.85 | 4.07 | 3.73 | 1.65 | 3.71 | 108,402 | 7.16 | 6.21 |
| vLLM, together | 1 | A1 | 2.78 | 2.89 | 2.54 | 0.93 | 2.53 | 84,462 | 6.02 | 5.86 |
| vLLM, together | 2 | A2 | 2.78 | 2.90 | 2.56 | 0.94 | 2.54 | 84,782 | 6.01 | 5.86 |
| vLLM, together | 3 | A3 | 2.77 | 2.90 | 2.57 | 0.93 | 2.55 | 85,263 | 6.00 | 5.85 |

- **The day was steady.** Ollama's typical pass, calls one after another, was 5.13, 5.07, 5.12 s in the
  three rounds: 0.06 s apart, within the 0.25 s line.
- **Rule B, the seven judgements**, each difference worked from the milliseconds:

| Arm | Held against | Shorter by, in rounds 1, 2, 3 | Faster by the rule |
|---|---|---|---|
| llama.cpp | Ollama | 0.01 s shorter, then 0.05 s longer, then 0.01 s longer | no: a figure, not a win |
| vLLM | Ollama | 1.57 s shorter, then 1.61 s shorter, then 1.69 s shorter | yes |
| llama.cpp, together | Ollama, together | 0.07 s longer, then 0.05 s longer, then 0.10 s longer | no: a figure, not a win |
| vLLM, together | Ollama, together | 0.98 s shorter, then 0.99 s shorter, then 0.98 s shorter | yes |
| Ollama, together | Ollama | 1.37 s shorter, then 1.31 s shorter, then 1.37 s shorter | yes |
| llama.cpp, together | Ollama | 1.30 s shorter, then 1.26 s shorter, then 1.26 s shorter | yes |
| vLLM, together | Ollama | 2.35 s shorter, then 2.30 s shorter, then 2.35 s shorter | yes |

- **The wait and the engine's own speed.** At temperature 0 vLLM wrote 254,979 tokens where Ollama
  wrote 319,170 and llama.cpp 325,947: 20 % fewer than Ollama. That is the switch of section 7.
  Ollama and llama.cpp wrote a token in the same time (6.44 and 6.52 ms all in). vLLM wrote one in
  5.33 ms, 17 % less than Ollama. So vLLM's shorter wait has two parts of about the same size:
  fewer tokens, and less time for each token.
- Over all 13 chains, for comparison with a bench that does not use rounds: the typical pass of
  495 over 143 passes was 4.97 s on Ollama, 5.17 s on llama.cpp and 3.78 s on vLLM.

## 6. The two calls of a pass sent together

Each engine also ran the three chains at temperature 0 of every case with the alarm and the
assessment sent at the same moment, one such chain in each round. The pass then runs from
sending until both are back.

| | Ollama | llama.cpp | vLLM |
|---|---|---|---|
| Typical pass of 495, the two calls sent together (rounds 1, 2, 3) | 3.76, 3.76, 3.75 | 3.83, 3.81, 3.85 | 2.78, 2.78, 2.77 |
| The same engine, one after another, the same rounds | 5.13, 5.07, 5.12 | 5.12, 5.12, 5.12 | 3.56, 3.47, 3.43 |
| Shorter than itself one after another, by round | 1.37, 1.31, 1.37 | 1.29, 1.31, 1.27 | 0.78, 0.69, 0.66 |
| Shorter than Ollama one after another, by round (the app today) | 1.37, 1.31, 1.37 | 1.30, 1.26, 1.26 | 2.35, 2.30, 2.35 |
| Alarm call, typical, the chain at 0 of each round: together | 1.46, 1.46, 1.46 | 1.65, 1.67, 1.65 | 0.93, 0.94, 0.93 |
| Alarm call: one after another | 1.12, 1.12, 1.12 | 1.27, 1.27, 1.27 | 0.75, 0.73, 0.74 |
| Assessment call: together | 3.65, 3.67, 3.67 | 3.73, 3.70, 3.71 | 2.53, 2.54, 2.55 |
| Assessment call: one after another | 3.50, 3.50, 3.50 | 3.59, 3.59, 3.59 | 2.32, 2.34, 2.33 |
| Typical pass, all cases: together | 3.67, 3.68, 3.68 | 3.75, 3.71, 3.73 | 2.54, 2.56, 2.57 |
| Typical pass, all cases: one after another | 4.74, 4.72, 4.72 | 4.90, 4.90, 4.90 | 3.13, 3.13, 3.13 |
| ms for each token written, all in: together / one after another | 7.04 / 6.44 | 7.15 / 6.52 | 6.01 / 5.33 |
| Every hard mark met at temperature 0, no chain failed | yes | yes | yes |

- Sending together shortens the pass on every engine, by more than a second against Ollama one
  after another in every round. Between the three engines, all sending together, vLLM is faster by
  the rule and llama.cpp is not (the judgements of section 5).
- **The alarm itself comes back later.** Sent together, the alarm call takes longer than when it
  is sent first and alone: 1.46 against 1.12 s on Ollama, 1.65 against 1.27 s on
  llama.cpp, 0.93 against 0.75 s on vLLM, in round 1. The assessment arrives sooner, because it no
  longer waits for the alarm, and so the pass ends sooner.
- Ollama as installed takes one call at a time. Its together arm ran on a second Ollama process
  started with Ollama's own setting for two calls at once (OLLAMA_NUM_PARALLEL=2) and its own copy
  of the same model file, which is why its arm.json shows another digest. llama.cpp was started
  with two slots. vLLM needed no change. HOW_IT_WAS_RUN.md, section 5.
- The marks: every together arm met every hard mark at temperature 0 and no chain failed. The
  soft values that differ from the same engine one after another, over the same three chains:
  Ollama: S14 (5 against 4); llama.cpp: S10 (3, 3 against 3, 2); vLLM: none. With three chains, one chain moves a count.
- OpenConsult still sends its two calls one after another. Nothing in the app changes on this
  bench alone.

## 7. The switch and the stray quote

The model sometimes writes a plain double quote inside its reasoning, to quote a word; nearly
always in the sentence that says there are no red flags. Inside the answer form a plain double
quote ends the text. After it the model can only write blank space or go on to the next part of
the form.

- On Ollama and llama.cpp the reply survives: llama.cpp's server allows very little blank space
  there, and Ollama runs that server. The reasoning is cut mid-sentence and the reply is counted
  as fine. On 7 Oct, at temperature 0.5: Ollama 23 replies cut, llama.cpp 35, vLLM 21, of 2,920 each.
  At temperature 0: Ollama 0, llama.cpp 6, vLLM 0; in the together arms 0, 5 and 0.
- vLLM by default allows blank space without limit, so the reply ran on in blank space until its
  length limit and was stopped there, and the chain failed. That is what happened on 6 Oct, in
  the vLLM arm that ran without the switch: 14 chains failed, of 208, all at temperature 0.5, none at
  temperature 0 (bench-of-6-oct/arms/vllm-repack; its 14 stopped replies are counted apart from
  the cut ones). Those files are as they were written on 6 Oct, and were scored by the rules of
  that day: in them candidate means every hard mark over all 13 chains, so its marks.json says
  the arm was not a candidate. Under Rule A of this bench the same arm is a candidate: every hard
  mark was met on its three chains at temperature 0 and none of them failed.
- The switch (`disable_any_whitespace`, with the form held by xgrammar) forbids that blank space.
  With it, on 7 Oct, no chain failed. The switch did not cure the quote: the reasoning is still
  cut, as on the other two engines, and the reply survives.
- The switch also makes the answers shorter, because no blank space is written between the parts
  of the form: at temperature 0 vLLM wrote 254,979 tokens with the switch against 310,179 without it
  on 6 Oct, and 319,170 on Ollama. That is where about half of vLLM's gain comes from. Ollama has
  no such switch, and whether llama.cpp can be given the same compact form was not tested.
- Passes where the alarm says that something time critical is possible and names no action, on
  7 Oct: Ollama 65 (12 at temperature 0; 14 with a cut reply), llama.cpp 29 (6 at temperature 0;
  29 with a cut reply), vLLM 73 (10 at temperature 0; 3 with a cut reply). On llama.cpp every such
  pass goes with a cut reply. On Ollama and vLLM most come in a whole reply. The stray quote was
  seen on all three engines.

## 8. Does an engine give the same answer twice?

**The repeat test, 6 Oct 2026.** At temperature 0 with a fixed seed, the same words should give the
same answer. On 6 Oct six calls were each sent ten times on each engine, first ten in a row, then
with a different call in between each time. A figure is how many of the ten replies were the same
as the first, character for character, the first included. This test was not run again on 7 Oct;
its result of 6 Oct stands. **Its vLLM arms ran without the switch.**

| The call | Sent | Ollama | llama.cpp | llama.cpp, prompt cache off | vLLM | vLLM, batch invariance on |
|---|---|---|---|---|---|---|
| 495, last pass, alarm | ten in a row | 1 of 10 | 1 of 10 | 10 of 10 | 1 of 10 | 10 of 10 |
| 495, last pass, alarm | another call in between | 1 of 10 | 1 of 10 | 10 of 10 | 4 of 10 | 10 of 10 |
| 495, last pass, assessment | ten in a row | 1 of 10 | 1 of 10 | 10 of 10 | 1 of 10 | 1 of 10 |
| 495, last pass, assessment | another call in between | 10 of 10 | 10 of 10 | 10 of 10 | 1 of 10 | 10 of 10 |
| Travel case 2, turn 16, alarm | ten in a row | 1 of 10 | 1 of 10 | 10 of 10 | 5 of 10 | 10 of 10 |
| Travel case 2, turn 16, alarm | another call in between | 1 of 10 | 1 of 10 | 10 of 10 | 2 of 10 | 10 of 10 |
| Travel case 2, turn 16, assessment | ten in a row | 1 of 10 | 1 of 10 | 10 of 10 | 1 of 10 | 1 of 10 |
| Travel case 2, turn 16, assessment | another call in between | 10 of 10 | 10 of 10 | 10 of 10 | 9 of 10 | 10 of 10 |
| Script 15, last update, alarm | ten in a row | 1 of 10 | 1 of 10 | 10 of 10 | 6 of 10 | 10 of 10 |
| Script 15, last update, alarm | another call in between | 1 of 10 | 1 of 10 | 10 of 10 | 1 of 10 | 10 of 10 |
| Script 15, last update, assessment | ten in a row | 1 of 10 | 1 of 10 | 10 of 10 | 5 of 10 | 10 of 10 |
| Script 15, last update, assessment | another call in between | 1 of 10 | 10 of 10 | 10 of 10 | 1 of 10 | 10 of 10 |
| Sets where all ten were the same | of 12 | 2 | 3 | 12 | 0 | 10 |

- Ollama and llama.cpp behave alike. Ten in a row, the first reply differs from the other nine,
  and the other nine are the same as each other.
- llama.cpp's own page for its server says its prompt cache can make results nondeterministic.
  Started with that cache off, llama.cpp gave the same reply ten times out of ten in all twelve
  sets. Ollama's pages offer no switch for that cache, and nothing was tried on Ollama.
- vLLM gave up to ten different replies in ten. With its batch invariance switch on, which its
  page calls beta, ten of twelve sets were the same ten times.

**On 7 Oct**, over the three chains at temperature 0 of each case: the chains gave the same
differential names and the same alarm actions at every pass on 16 of 16 cases on Ollama, 16 on
llama.cpp and 0 on vLLM, calls one after another; sent together, 16, 1 and 0. The three chains of each
engine ran hours apart, one in each round, each after a fresh start of the engine or a fresh load
of the model.

**The pass at which the alarm first shows**, at temperature 0, calls one after another. Where the
three chains differ, each pass is given with its count of chains. A pass of consultation 495 is
one of its 11 recorded transcripts; a pass of a script is the turn at which it is cut.

| Case | Ollama | llama.cpp | vLLM |
|---|---|---|---|
| 495 | pass 3 | pass 2 | pass 2 |
| T1 | pass 8 | pass 8 | pass 8 |
| T2 | pass 8 | pass 4 | pass 4 |
| 01 | pass 4 | pass 4 | pass 4 |
| 06 | pass 4 | pass 4 | pass 4 |
| 07 | pass 4 | pass 8 | pass 8 |
| 08 | pass 4 | pass 4 | pass 4 |
| 10 | pass 4 | pass 4 | pass 4 |
| 14 | pass 4 | pass 4 | pass 4 |
| 15 | pass 8 | pass 4 | pass 4 (1); pass 8 (2) |
| 12 | pass 8 | pass 4 | pass 12 (2); pass 8 (1) |
| 03 | never | never | never |
| 04 | never | never | never |
| 05 | never | never | never |
| 11 | never | never | never |
| 13 | never | never | never |

## 9. The card's memory

MiB in use on the 24,564 MiB card, sampled every 5 seconds and pooled over each arm's own steps, because
the arms took turns through the day. The desktop's own use (563 MiB with no engine up) is included.

| Arm | Lowest | Typical (median) | Highest | Samples | Share of the card |
|---|---|---|---|---|---|
| Ollama | 14,713 | 17,139 | 17,289 | 1,779 | 70 % |
| llama.cpp | 15,539 | 15,591 | 15,591 | 1,866 | 63 % |
| vLLM | 23,027 | 23,137 | 23,137 | 1,288 | 94 % |
| Ollama, together | 563 | 17,859 | 17,859 | 322 | 73 % |
| llama.cpp, together | 16,169 | 16,201 | 16,201 | 331 | 66 % |
| vLLM, together | 23,137 | 23,137 | 23,137 | 223 | 94 % |

These are not like for like. Ollama loads the model's image part, about 1.2 GB, though the bench
is text only; llama.cpp was started without it. The second Ollama process, for two calls at once,
holds two slots, as does llama.cpp's start for the together arm. vLLM takes a fixed share of the
card whatever the model needs: the default, 0.92, was used, so its figure is that share and not
the model's need. The speech model of OpenConsult must fit on the same card beside the language
model; that was not measured here (section 13).

## 10. From start to first answer

A doctor feels this at the start of a clinic. The model files were already in the machine's file
cache at every start.

| Engine | From starting the engine to its first answer |
|---|---|
| Ollama | The service was already running and was never restarted. The first call of each of its turns, with the model not loaded, took 3,399 to 3,522 ms. |
| llama.cpp | Ready after 2.0 s on every start in the run, with one slot and with two; its first start of the day, for the proofs, took 3.0 s. Then a first call of 816 to 871 ms. |
| vLLM | Ready after 25.8 s on each of its three starts in the run; its first start of the day, for the proofs, took 26.3 s. Then a first call of 620 to 1,077 ms. |

machine/starts.json has every start and machine/steps.json every step's first call.

## 11. The machine on the day

Once a minute the machine's load, its three busiest processes, the processes on the card and
whether the desktop's screensaver was running were written down (machine/load.json).

- 487 minutes logged. The screensaver was running in 0 of them. The desktop could not
  blank, lock or start its screensaver: stay-awake was on throughout.
- The highest one-minute load was 5.86; no minute reached a load of 8 on the 32-thread machine.
- Processes at 50 % of a core or more, by minutes: llama-server 358; localsearch-ext 4; VLLM::EngineCor 3; vllm 1; openconsult-ben 1.
  The names are as the system gives them, cut at 15 characters. llama-server is both Ollama's
  server and llama.cpp's.
- On the card, by samples: llama-server 359; VLLM::EngineCore 127; beside them the desktop.
- Nobody was at the desk.

## 12. A first bench ran on 6 Oct 2026, and was set aside

The same three engines ran the same cases on 6 Oct 2026. Its seconds could not be trusted: its
arms ran at different hours of one day, one after another; a
screensaver that draws on the same card slowed the first minutes; and a review of the finished
arms, made on the same machine while the last arm was still running, slowed part of it. So the
whole bench was run again on 7 Oct, in one sitting, in three rounds with the order of the engines
changing, with nobody at the desk. The bench of 7 Oct is the published result.

Two parts of 6 Oct are kept in this folder, in bench-of-6-oct, because 7 Oct did not repeat
them: the repeat test (section 8), and the vLLM arm that ran without the switch, with its 14
failed chains, as the evidence for the switch (section 7). Their files are byte for byte as they
were written on 6 Oct, and they were scored by the rules of that day: in their marks.json
candidate means every hard mark over all 13 chains, and the line for faster was 1 second. No
other data of 6 Oct is published.

## 13. What was not tested

- **A compact answer form for Ollama or llama.cpp.** vLLM's switch makes its answers about a fifth
  shorter. Ollama has no such switch, and whether llama.cpp can be given the same form is not
  known. Until it is, the wait on vLLM and the wait on the other two are not measured on equal
  terms; the time for each token written is given beside the wait so that the engine's own speed
  can be read apart from the length of its answers.
- **The speech model beside the language model.** OpenConsult transcribes live on the same card.
  vLLM holds 94 % of the card by default and Ollama 70 %. Whether the speech model fits beside each,
  and what that does to the seconds, was not measured.
- More than one user at a time. This bench has one user.
- Another card, another machine, another system, another model.
- A newer Ollama. OpenConsult uses 0.33.3, and that is what was measured. The notes of Ollama 0.34.4
  say: "Structured outputs on thinking models now apply in a single pass, making them faster and
  more reliable." (github.com/ollama/ollama/releases/tag/v0.34.4)
- vLLM with a model file from Google, because there is none for this model at 4 bits; and vLLM's
  other route for this model, 8-bit weights worked out at load time, which its page names.
- vLLM without the switch on a steady day. Its one run without the switch is the arm of 6 Oct.
- vLLM 0.30.0, the version the repack's maker tested.
- The full arms with llama.cpp's prompt cache off, or with vLLM's batch invariance on. Those
  switches were tried in the repeat test of 6 Oct only.
- A third call in a pass. OpenConsult will later ask a third question in each pass. Only the two
  calls that exist today were sent together.
- A long consultation. The longest input was 1,742 tokens, of 16,384.
- Images. The bench is text only.
- The repeat test on 7 Oct.

## 14. How to check this, or to run it again

Everything the bench read and everything the models replied is in this folder. The figures of
this page that come from the replies of 7 Oct come from the repository's own tool, which works
from this folder alone, with no engine and no private file:

    uv sync
    uv run openconsult-bench figures --public engine-bench

It prints the candidates, the steadiness of the day, the seven judgements, the seconds round by
round and the counts from the replies, and it gives the same output as `figures.md`. The data it
reads: `rounds.json`, which says which chain belongs to which round and which arm plays which
role, and the replies of each arm. The marks of one arm alone:

    uv run openconsult-bench score --replies engine-bench/arms/vllm-repack-compact/replies.jsonl.gz

The figures of sections 9 to 11 come from the files in machine/. The repeat table of section 8
comes from the repeat.json files in bench-of-6-oct/, and the figures of the vLLM arm of 6 Oct
from its replies there.

| File or folder | Holds |
|---|---|
| `cases/` | The 16 cases, with a list and their checksums (section 15). |
| `arms/NAME/arm.json` | The engine and its version, the model and its digest, the hashes of the two prompts, the chains, the counts, the first and last call, the card's memory over the arm's own steps, and the arm's measured facts. |
| `arms/NAME/replies.jsonl.gz` | One line for each call: case, chain, point, job, how it ended, tokens read and written, the seconds, the pass's seconds, whether the earlier list was kept, and the reply's text. |
| `arms/NAME/marks.json` | The 18 marks, each chain's scoring, the marks at temperature 0 and at 0.5, the empty replies and the kept lists. An arm sent together has three chains, so the 18 marks over 13 chains cannot be met in it and its hard_met reads false. Its deciding figures are at_temperature_0 and candidate. |
| `arms/NAME/times.json` | Each call and each pass: the median and the slowest. |
| `rounds.json` | The rounds, their chains, and the arms' roles, as data. |
| `figures.json`, `figures.md` | The tool's output, as data and as printed. |
| `machine/` | What came from the machine and not from the replies: the steps, the starts, the card, the load, the proofs. Each file says how it was measured. |
| `bench-of-6-oct/` | The two kept parts of 6 Oct (section 12), byte for byte, with a note. |

The requests are not stored. They can be built again from the cases, the two prompts in
`openconsult/prompts` and the code. HOW_IT_WAS_RUN.md gives every version, option and command,
so that the bench can be run again on an engine of your own.

## 15. The cases

Sixteen cases, each acted or scripted, in `cases/` with their checksums: the 11 recorded live
transcripts of consultation 495, an acted consultation whose script is public; two scripted
returned-traveller cases; and 13 scripted consultations, seven of them emergencies, five routine,
one dizziness. The bench sends the model only the lines a speaker says, without speaker labels or
stage directions.

The two travel cases are published byte for byte as the bench read them. Their headers hold
three working notes written before the run: that the file is not part of the repository, a
proposal about the alarm, and that the pass marks were still to be set. The bench sends only
the lines a speaker says, so the model never saw a header. The marks are those of section 4.
