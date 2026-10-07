## Who is a candidate (Rule A, ruling 18)

- ollama-google-file: Candidate (every hard mark met on the chains at temperature 0, none failed): yes
  The stress test at 0.5, apart: 10 chains; hard marks missed: none; failed: none. It bars nothing.
- llamacpp-google-file: Candidate (every hard mark met on the chains at temperature 0, none failed): yes
  The stress test at 0.5, apart: 10 chains; hard marks missed: none; failed: none. It bars nothing.
- vllm-repack-compact: Candidate (every hard mark met on the chains at temperature 0, none failed): yes
  The stress test at 0.5, apart: 10 chains; hard marks missed: none; failed: none. It bars nothing.
- ollama-together: Candidate (every hard mark met on the chains at temperature 0, none failed): yes
- llamacpp-together: Candidate (every hard mark met on the chains at temperature 0, none failed): yes
- vllm-together-compact: Candidate (every hard mark met on the chains at temperature 0, none failed): yes

## Is an arm faster (Rule B, rulings 17 and 21)

The day was steady: the typical pass of ollama-google-file was 5.13, 5.07, 5.12 s in the three rounds, within 0.06 s (the line is 0.25 s).

- llamacpp-google-file (5.12, 5.12, 5.12 s) against ollama-google-file (5.13, 5.07, 5.12 s): 0.01 s shorter, then 0.05 s longer, then 0.01 s longer. Not called faster: under 0.50 s in at least one round. A figure, not a win.
- vllm-repack-compact (3.56, 3.47, 3.43 s) against ollama-google-file (5.13, 5.07, 5.12 s): 1.57 s shorter, then 1.61 s shorter, then 1.69 s shorter. Faster by the rule: at least 0.50 s shorter in each of the three rounds.
- llamacpp-together (3.83, 3.81, 3.85 s) against ollama-together (3.76, 3.76, 3.75 s): 0.07 s longer, then 0.05 s longer, then 0.10 s longer. Not called faster: under 0.50 s in at least one round. A figure, not a win.
- vllm-together-compact (2.78, 2.78, 2.77 s) against ollama-together (3.76, 3.76, 3.75 s): 0.98 s shorter, then 0.99 s shorter, then 0.98 s shorter. Faster by the rule: at least 0.50 s shorter in each of the three rounds.
- ollama-together (3.76, 3.76, 3.75 s) against ollama-google-file (5.13, 5.07, 5.12 s): 1.37 s shorter, then 1.31 s shorter, then 1.37 s shorter. Faster by the rule: at least 0.50 s shorter in each of the three rounds.
- llamacpp-together (3.83, 3.81, 3.85 s) against ollama-google-file (5.13, 5.07, 5.12 s): 1.30 s shorter, then 1.26 s shorter, then 1.26 s shorter. Faster by the rule: at least 0.50 s shorter in each of the three rounds.
- vllm-together-compact (2.78, 2.78, 2.77 s) against ollama-google-file (5.13, 5.07, 5.12 s): 2.35 s shorter, then 2.30 s shorter, then 2.35 s shorter. Faster by the rule: at least 0.50 s shorter in each of the three rounds.

## The seconds, round by round

Typical = the median of the passes of consultation 495 in the round's chain at temperature 0, in seconds. Beside it the median over all cases, each call's median, the tokens written in the chain, and the milliseconds for each token written, all in and writing only.

| arm | round | chain | typical | slowest | all cases | alarm | assessment | tokens written | ms/token all in | ms/token writing |
|---|---|---|---|---|---|---|---|---|---|---|
| ollama-google-file | 1 | A1 | 5.13 | 5.40 | 4.74 | 1.12 | 3.50 | 106,390 | 6.45 | 5.93 |
| ollama-google-file | 2 | A2 | 5.07 | 5.34 | 4.72 | 1.12 | 3.50 | 106,390 | 6.43 | 5.92 |
| ollama-google-file | 3 | A3 | 5.12 | 5.36 | 4.72 | 1.12 | 3.50 | 106,390 | 6.44 | 5.92 |
| llamacpp-google-file | 1 | A1 | 5.12 | 5.47 | 4.90 | 1.27 | 3.59 | 108,649 | 6.52 | 5.95 |
| llamacpp-google-file | 2 | A2 | 5.12 | 5.47 | 4.90 | 1.27 | 3.59 | 108,649 | 6.52 | 5.95 |
| llamacpp-google-file | 3 | A3 | 5.12 | 5.47 | 4.90 | 1.27 | 3.59 | 108,649 | 6.52 | 5.95 |
| vllm-repack-compact | 1 | A1 | 3.56 | 3.67 | 3.13 | 0.75 | 2.32 | 84,796 | 5.33 | 5.22 |
| vllm-repack-compact | 2 | A2 | 3.47 | 3.68 | 3.13 | 0.73 | 2.34 | 85,071 | 5.33 | 5.22 |
| vllm-repack-compact | 3 | A3 | 3.43 | 3.50 | 3.13 | 0.74 | 2.33 | 85,112 | 5.33 | 5.22 |
| ollama-together | 1 | A1 | 3.76 | 4.16 | 3.67 | 1.46 | 3.65 | 106,160 | 7.04 | 6.17 |
| ollama-together | 2 | A2 | 3.76 | 4.16 | 3.68 | 1.46 | 3.67 | 106,160 | 7.05 | 6.17 |
| ollama-together | 3 | A3 | 3.75 | 4.16 | 3.68 | 1.46 | 3.67 | 106,160 | 7.04 | 6.17 |
| llamacpp-together | 1 | A1 | 3.83 | 4.07 | 3.75 | 1.65 | 3.73 | 108,402 | 7.15 | 6.20 |
| llamacpp-together | 2 | A2 | 3.81 | 3.96 | 3.71 | 1.67 | 3.70 | 108,407 | 7.14 | 6.20 |
| llamacpp-together | 3 | A3 | 3.85 | 4.07 | 3.73 | 1.65 | 3.71 | 108,402 | 7.16 | 6.21 |
| vllm-together-compact | 1 | A1 | 2.78 | 2.89 | 2.54 | 0.93 | 2.53 | 84,462 | 6.02 | 5.86 |
| vllm-together-compact | 2 | A2 | 2.78 | 2.90 | 2.56 | 0.94 | 2.54 | 84,782 | 6.01 | 5.86 |
| vllm-together-compact | 3 | A3 | 2.77 | 2.90 | 2.57 | 0.93 | 2.55 | 85,263 | 6.00 | 5.85 |

Over all chains at each temperature: tokens written, ms for each token all in and writing only.

- ollama-google-file: at 0.0: 319,170 tokens, 6.44 and 5.92 ms; at 0.5: 1,056,104 tokens, 6.44 and 5.92 ms.
- llamacpp-google-file: at 0.0: 325,947 tokens, 6.52 and 5.95 ms; at 0.5: 1,091,959 tokens, 6.53 and 5.96 ms.
- vllm-repack-compact: at 0.0: 254,979 tokens, 5.33 and 5.22 ms; at 0.5: 848,915 tokens, 5.93 and 5.83 ms.
- ollama-together: at 0.0: 318,480 tokens, 7.04 and 6.17 ms.
- llamacpp-together: at 0.0: 325,211 tokens, 7.15 and 6.20 ms.
- vllm-together-compact: at 0.0: 254,507 tokens, 6.01 and 5.86 ms.

## From the replies

- ollama-google-file: chains failed none. Replies cut mid-sentence alarm at 0.5: 16; assessment at 0.5: 7. Counted apart none. Empty lists at 0.5: 3; kept at 0.5: 3. Time critical with no action at 0.0, whole: 12; at 0.5, cut: 14; at 0.5, whole: 39. Same answer in every chain at 0: 16 cases.
- llamacpp-google-file: chains failed none. Replies cut mid-sentence alarm at 0.0: 6; alarm at 0.5: 34; assessment at 0.5: 1. Counted apart none. Empty lists none; kept none. Time critical with no action at 0.0, cut: 6; at 0.5, cut: 23. Same answer in every chain at 0: 16 cases.
- vllm-repack-compact: chains failed none. Replies cut mid-sentence alarm at 0.5: 20; assessment at 0.5: 1. Counted apart none. Empty lists none; kept none. Time critical with no action at 0.0, whole: 10; at 0.5, cut: 3; at 0.5, whole: 60. Same answer in every chain at 0: 0 cases.
- ollama-together: chains failed none. Replies cut mid-sentence none. Counted apart none. Empty lists none; kept none. Time critical with no action at 0.0, whole: 9. Same answer in every chain at 0: 16 cases.
- llamacpp-together: chains failed none. Replies cut mid-sentence alarm at 0.0: 5. Counted apart none. Empty lists none; kept none. Time critical with no action at 0.0, cut: 5. Same answer in every chain at 0: 1 cases.
- vllm-together-compact: chains failed none. Replies cut mid-sentence none. Counted apart none. Empty lists none; kept none. Time critical with no action at 0.0, whole: 8. Same answer in every chain at 0: 0 cases.

The pass at which the alarm first shows, by temperature (count of chains):

| case | ollama-google-file | llamacpp-google-file | vllm-repack-compact | ollama-together | llamacpp-together | vllm-together-compact |
|---|---|---|---|---|---|---|
| 01 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
| 03 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3 | at 0.0: never: 3 | at 0.0: never: 3 |
| 04 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3 | at 0.0: never: 3 | at 0.0: never: 3 |
| 05 | at 0.0: never: 3; at 0.5: never: 9; at 0.5: pass 8: 1 | at 0.0: never: 3; at 0.5: never: 6; at 0.5: pass 4: 2; at 0.5: pass 8: 2 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3 | at 0.0: never: 3 | at 0.0: never: 3 |
| 06 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
| 07 | at 0.0: pass 4: 3; at 0.5: pass 4: 1; at 0.5: pass 8: 9 | at 0.0: pass 8: 3; at 0.5: pass 4: 6; at 0.5: pass 8: 4 | at 0.0: pass 8: 3; at 0.5: pass 8: 10 | at 0.0: pass 8: 3 | at 0.0: pass 4: 3 | at 0.0: pass 8: 3 |
| 08 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
| 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
| 11 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3 | at 0.0: never: 3 | at 0.0: never: 3 |
| 12 | at 0.0: pass 8: 3; at 0.5: pass 12: 1; at 0.5: pass 8: 9 | at 0.0: pass 4: 3; at 0.5: pass 4: 9; at 0.5: pass 8: 1 | at 0.0: pass 12: 2; at 0.0: pass 8: 1; at 0.5: pass 12: 2; at 0.5: pass 16: 1; at 0.5: pass 20: 1; at 0.5: pass 4: 1; at 0.5: pass 8: 5 | at 0.0: pass 8: 3 | at 0.0: pass 4: 3 | at 0.0: pass 12: 2; at 0.0: pass 8: 1 |
| 13 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3; at 0.5: never: 10 | at 0.0: never: 3 | at 0.0: never: 3 | at 0.0: never: 3 |
| 14 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 4: 9; at 0.5: pass 8: 1 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
| 15 | at 0.0: pass 8: 3; at 0.5: pass 4: 6; at 0.5: pass 8: 4 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 1; at 0.0: pass 8: 2; at 0.5: pass 4: 5; at 0.5: pass 8: 5 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
| 495 | at 0.0: pass 3: 3; at 0.5: pass 2: 5; at 0.5: pass 3: 4; at 0.5: pass 4: 1 | at 0.0: pass 2: 3; at 0.5: pass 2: 9; at 0.5: pass 3: 1 | at 0.0: pass 2: 3; at 0.5: pass 2: 7; at 0.5: pass 3: 3 | at 0.0: pass 3: 3 | at 0.0: pass 2: 3 | at 0.0: pass 2: 3 |
| T1 | at 0.0: pass 8: 3; at 0.5: pass 12: 1; at 0.5: pass 4: 4; at 0.5: pass 8: 5 | at 0.0: pass 8: 3; at 0.5: pass 4: 10 | at 0.0: pass 8: 3; at 0.5: pass 12: 1; at 0.5: pass 4: 2; at 0.5: pass 8: 7 | at 0.0: pass 8: 3 | at 0.0: pass 4: 1; at 0.0: pass 8: 2 | at 0.0: pass 8: 3 |
| T2 | at 0.0: pass 8: 3; at 0.5: pass 4: 9; at 0.5: pass 8: 1 | at 0.0: pass 4: 3; at 0.5: pass 4: 10 | at 0.0: pass 4: 3; at 0.5: pass 12: 3; at 0.5: pass 4: 4; at 0.5: pass 8: 3 | at 0.0: pass 8: 3 | at 0.0: pass 4: 3 | at 0.0: pass 4: 3 |
