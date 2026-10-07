# How the engine bench of 7 Oct 2026 was run

OpenConsult is a research and education prototype. It is not a medical device. It is never used
with real patients. Every case in this bench is acted or scripted.

This page gives every version, option and command, so that anyone can repeat the bench, and says
how each public data file was made. `ENG` stands for one folder that held the engines and the
model files. The report is in README.md.

## 1. The machine

One desktop computer.

| | |
|---|---|
| Graphics card | One NVIDIA GeForce RTX 4090, 24 GB (24,564 MiB) |
| NVIDIA driver | 610.57.04 |
| Processor | Intel Core i9-13900K, 32 threads |
| Memory | 94 GB |
| System | Linux, kernel 7.2.5 (an Arch-based system) |
| Also on the card | The desktop session, 563 MiB with no engine up. Nothing else. |

## 2. What ran

| | Version | Where it came from |
|---|---|---|
| Ollama | 0.33.3, as already installed. The newest on 6 Oct 2026, when it was last checked, was 0.35.1 (29 Sep 2026). | The system's package |
| llama.cpp | Release v0.6.0 (5 Oct 2026), the latest that was not a prerelease. Its file nightly-tag.txt names build b11429, commit d81235049384534c167caea52b85a694f6103d14. `llama-server --version`: 0.6.0-dev, build 11429. | The maker's own Linux binaries (below) |
| vLLM | 0.31.0 (5 Oct 2026), the newest release on 6 Oct 2026. With torch 2.13.0+cu132, transformers 5.17.0, xgrammar 0.2.7, compressed-tensors 0.17.0, Python 3.12.14. | PyPI |
| The bench | The code of this repository: `openconsult/bench`, behind the same door to the model as the app (`openconsult/llm`). Standard library only. | This repository |

The engines, the files and the starts are those of the first bench of 6 Oct 2026, word for word.
Nothing was installed or downloaded between the two days.

The llama.cpp archives, from `github.com/ggml-org/llama.cpp/releases/download/b11429/`:

| File | Bytes | sha256 |
|---|---|---|
| llama-b11429-bin-ubuntu-cuda-13.4-x64.tar.gz | 152,519,318 | 8082b7eaa74a714c9fecca19128f751c8e32da763ee8096b8ad1e824da7621d3 |
| cudart-llama-b11429-bin-ubuntu-cuda-13.4-x64.tar.gz | 440,236,630 | 93d18648d815b2bd624d83d82f653e1db97afb478f02064305fe3cf570040a6d |

They started on this driver as they came. Nothing was built from source.

## 3. The model files

| Arm | Model file |
|---|---|
| Ollama (ollama-google-file, ollama-together) | `gemma-4-26B_q4_0-it.gguf` from `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` on Hugging Face, revision d1c082be9cf3c8a514acf63b8761f4b41935842e. sha256 3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d, 14,439,363,584 bytes. |
| llama.cpp (llamacpp-google-file, llamacpp-together) | The same file, the same bytes. |
| vLLM (vllm-repack-compact, vllm-together-compact) | `xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct` on Hugging Face, revision 2096d38dad51a19b8e982b44241c47102a8bbb00. 43 files, 16,457,920,691 bytes. Every large file's sha256 was checked against Hugging Face's list for that revision. |

**Ollama's own tag and Google's file.** OpenConsult uses the tag `gemma4:26b-a4b-it-qat` (digest
2dd70431afed94dd3688d790443768c1487ed086b57147ff083851116ae4c4e4; file sha256 4c856523d61d77922dbc0b26753a6bf6208e5d69d80db0c04dcd776832d054c5, 14,439,361,440 bytes).
Google's file is not the same file: the sha256 values differ and Google's is 2,144 bytes longer.
But the weights are the same. The two files are identical, byte for byte, over their last
14,422,576,128 bytes. They differ only in the header, the first 16.8 MB. Both hold 658 tensors
with the same names, types and shapes (392 F32, 265 Q4_0, 1 Q6_K). In the header, Google's file
adds its base model, licence and tag entries. Ollama's has an entry `general.finetune`. And
`tokenizer.ggml.add_bos_token` is false in Ollama's file and true in Google's. Under Ollama this
changed no token count (section 8). The tag itself was not run in this bench: it met every hard
mark in OpenConsult's own proof run of 4 Oct 2026, and no data of that run is in this folder.

**The vLLM arm ran a version of the model made by an individual.** vLLM cannot read Google's
file. The repack's own page (huggingface.co/xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct) says: "This is an unofficial repack, made and published independently
of Google." It says it holds Google's quantization-aware-trained weights, from
`google/gemma-4-26B-A4B-it-qat-q4_0-unquantized`, and "It does no new quantization." Its own
check of the weights against Google's, as its page gives it:

| Tensors | Groups of 32 | Levels off the source grid | Values bit-identical |
|---|---|---|---|
| Experts, gate and up | 475,791,360 | 0 | 92.6% |
| Experts, down | 237,895,680 | 0 | 92.6% |
| Dense MLP | 16,727,040 | 0 | 92.0–92.5% |
| Attention | 34,693,120 | 0 | 89.7–90.4% |

"All 748 unquantized tensors are byte-identical to the source. The values that are not
bit-identical differ through the bf16 scale (Q4_0 carries a 16-bit float step), by at most 1.1e-2
relative." Its maker tested it "with vLLM 0.30.0 on one NVIDIA L4 (24 GB)", with
`--max-model-len 2048`, text only. It was published on 27 Sep 2026 and had 57 downloads on
6 Oct 2026. This bench ran it on vLLM 0.31.0, on another card, at a context of 16,384.

Why no file from Google for vLLM: vLLM's own page for Gemma 4
(docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html) says: "The 26B-A4B MoE model is
not included — its small expert dimensions (704) cause excessive quality loss with 4-bit
quantization." Google publishes a 4-bit file for this model, the GGUF file above, and the
repack is made from the weights of that same training.

## 4. Installing

    # the model files, each at its fixed revision
    HF_HOME=ENG/hf uvx --from huggingface_hub hf download google/gemma-4-26B-A4B-it-qat-q4_0-gguf \
        gemma-4-26B_q4_0-it.gguf --revision d1c082be9cf3c8a514acf63b8761f4b41935842e --local-dir ENG/models
    sha256sum ENG/models/gemma-4-26B_q4_0-it.gguf
    HF_HOME=ENG/hf uvx --from huggingface_hub hf download xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct \
        --revision 2096d38dad51a19b8e982b44241c47102a8bbb00

    # llama.cpp: the two archives of section 2, unpacked side by side
    tar xzf llama-b11429-bin-ubuntu-cuda-13.4-x64.tar.gz
    tar xzf cudart-llama-b11429-bin-ubuntu-cuda-13.4-x64.tar.gz

    # vLLM, as its installation page gives it
    cd ENG/vllm
    uv venv --python 3.12 --seed --managed-python
    source .venv/bin/activate
    uv pip install vllm==0.31.0 --torch-backend=auto

Nothing was installed for the whole system. Nothing needed administrator rights.

## 5. Starting each engine: the five starts

Every engine listened on this computer only. One engine held the card at a time: at the end of
each engine's turn it was stopped, or its model unloaded, and the card was seen to be free before
the next engine started. Each start below was made afresh in each round.

### Ollama, calls one after another: the service as installed

The arm with the calls one after another went to the Ollama service as installed. It was not
restarted or set up differently. Its model was loaded by the first call of each turn, which is
recorded and not measured, and unloaded at the end of the turn. With the model loaded, Ollama
0.33.3 itself was seen to run:

    llama-server --model <the model file> --port <a port> --host 127.0.0.1 --no-webui --offline
        -c 16384 -np 1 --log-verbosity 4 --no-log-prefix --no-log-timestamps --no-jinja
        --chat-template chatml --mmproj <the projector file> --flash-attn auto -b 1024 -ub 1024
        --context-shift --keep 4

So Ollama 0.33.3 serves this model with llama.cpp's own server, one slot, with Ollama's own code
writing the prompt. How this is known, beyond the process seen on this machine:

- Ollama's source at v0.33.3 has a file `LLAMA_CPP_VERSION` that holds `b10760`
  (github.com/ollama/ollama/blob/v0.33.3/LLAMA_CPP_VERSION).
- Ollama's pull request 16031, merged on 29 May 2026, is titled "runner: Remove CGO engines, use
  llama-server exclusively for GGML models" (github.com/ollama/ollama/pull/16031).
- The installed server reports itself as "version: 0.3.0-dev (build 1, commit 0f3a71be1)". That is
  a llama.cpp commit of 2 Sep 2026. The llama.cpp arm ran build b11429, of 5 Oct 2026.

The model on Google's file was made from the Modelfile that `ollama show --modelfile
gemma4:26b-a4b-it-qat` prints, with two lines changed:

    FROM ENG/models/gemma-4-26B_q4_0-it.gguf       (in place of the tag's own model file)
    FROM <the tag's own projector file>            (unchanged)
    TEMPLATE {{ .Prompt }}
    RENDERER gemma4
    PARSER gemma4
    REQUIRES 0.30.5                                (added: the tag carries it, but the printed Modelfile leaves it out)
    PARAMETER temperature 1
    PARAMETER top_k 64
    PARAMETER top_p 0.95
    LICENSE ...                                    (unchanged)

    ollama create openconsult-bench-gemma4:26b-google-q4_0 -f Modelfile

Checked against the tag: the model layer is Google's file, sha256 3eca3b8f6d7b..., stored
unchanged. The projector, licence and parameter layers have the same sha256 as the tag's.
Template, renderer, parser, parameters, requires, capabilities and details are equal. Ollama
starts its server for it with the same command line, but for the file and the port. So the file
is the only thing that differs.

### Ollama, the two calls together: a second Ollama process

Ollama as installed takes one call at a time: its FAQ gives OLLAMA_NUM_PARALLEL "default 1", and
the service does not set it. So, for the together arm only, a second process of the same binary
and version was started for each round, with its own model folder:

    HOME=ENG/ollama-private/home OLLAMA_HOST=127.0.0.1:11500 OLLAMA_MODELS=ENG/ollama-private/models \
    OLLAMA_NUM_PARALLEL=2 OLLAMA_KEEP_ALIVE=30m ollama serve

The same model was made in it from the same Modelfile lines, from the same file, and the same
checks were made. It ran its server with `-c 32768 -np 2`: two slots of 16,384. Ollama's digest
of a model covers its manifest, which names the blobs in that process's own folder, so this copy
of the same file has a digest of its own: `b7b230964216...` against the service's
`9813ae3a5cf9...`. The arm.json of each Ollama arm carries its own.

### llama.cpp

Calls one after another, one slot:

    llama-server -m ENG/models/gemma-4-26B_q4_0-it.gguf --alias google/gemma-4-26B-A4B-it-qat-q4_0-gguf \
        --host 127.0.0.1 --port 8171 -c 16384 -np 1 -ngl all --no-webui --offline

| Option | Why |
|---|---|
| -m | Google's file. |
| --alias | The name the bench sends as the model. |
| --host, --port | This computer only. |
| -c 16384 | The one context size of OpenConsult. Unset, the server takes the file's own 262,144 and then shrinks it to fit. |
| -np 1 | One slot, so the slot has the whole 16,384. The default is four slots sharing one pool. Ollama also runs one slot. |
| -ngl all | Every layer on the card. |
| --no-webui, --offline | No page, no network. Ollama starts its own copy the same way. |

The together arm: the same with `-c 32768 -np 2`, two slots of 16,384 each.

Left at llama.cpp's own defaults: the chat template inside the file, with jinja; batch sizes
2,048 and 512 (Ollama: 1,024 and 1,024); flash attention auto; context shift off (Ollama: on);
the prompt cache on; no projector loaded, because the bench is text only (Ollama loads it).

### vLLM, with the switch

One start in each round, for both of its arms:

    HF_HOME=ENG/hf HF_HUB_OFFLINE=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 \
    vllm serve ENG/hf/hub/models--xbill9--gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct/snapshots/2096d38dad51a19b8e982b44241c47102a8bbb00 \
        --served-model-name xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct \
        --host 127.0.0.1 --port 8172 --max-model-len 16384 \
        --limit-mm-per-prompt '{"image":0,"audio":0,"video":0}' \
        --enable-per-request-metrics \
        --structured-outputs-config '{"backend": "xgrammar", "disable_any_whitespace": true}'

| Option | Why |
|---|---|
| the snapshot folder | The repack at its fixed revision. |
| --served-model-name | The repack's public name. |
| --host, --port | This computer only. |
| --max-model-len 16384 | The one context size. |
| --limit-mm-per-prompt | As the repack's own page gives it: text only. |
| --enable-per-request-metrics | vLLM's own time to first token and writing time, in each reply. |
| --structured-outputs-config | The one switch (README.md, section 7): the form held by xgrammar, and no free blank space in a formed answer. Off by default. |
| The three variables | Nothing is fetched at start and nothing is sent to anyone. |

Left at vLLM's own defaults: the share of the card, "the default value of 0.92"; the number of
calls it will take at once; prefix caching on; no reasoning parser. vLLM's own start-up log
named the switch as set: `StructuredOutputsConfig(backend='xgrammar', disable_any_whitespace=True)`. The caches of vLLM and
its libraries were kept inside ENG.

## 6. The same call on every engine

Every call went through the same code: the same two prompts (sha256 of the system text as sent:
alarm c98ef427c4e2..., assessment 6cc315afcf2c...; the full hashes are in each arm.json), the same
patient line, the same answer form, the same limits (1,000 tokens for the alarm, 1,500 for the
assessment, 60 seconds each), temperature and seed from the chain, thinking off, a context of
16,384. A pass is two calls: the alarm, then the assessment. The assessment is also given the
names of the earlier differentials. The 13 chains of each case: A1 to A3 at temperature 0 with
seed 42, and B1 to B10 at temperature 0.5 with seeds 1 to 10.

What each engine was sent for one call:

| Part | Ollama (/api/chat) | llama.cpp and vLLM (/v1/chat/completions) |
|---|---|---|
| The two texts | messages: system, user | the same |
| The answer form | format: the JSON schema | response_format: json_schema, with the same schema |
| Thinking off | think: false | chat_template_kwargs: {"enable_thinking": false} |
| Temperature, seed | options.temperature, options.seed | temperature, seed |
| Length limit | options.num_predict | max_tokens |
| Context | options.num_ctx 16384, and truncate: false | set at start; the bench reads the server's own figure and refuses another |
| Not streamed | stream: false | stream: false |

## 7. Every sampling setting

T is the chain's temperature and S its seed.

| Setting | Ollama | llama.cpp | vLLM |
|---|---|---|---|
| temperature, seed | T, S, sent | T, S, sent | T, S, sent |
| top_k | 64, from the tag | 64, sent (the file itself also says 64) | 64, sent (the repack's own settings file also says 64) |
| top_p | 0.95, from the tag | 0.95, sent | 0.95, sent |
| min_p | 0.0, Ollama's default | 0.0, sent. llama.cpp's own default is 0.05. | 0.0, sent |
| repeat penalty | 1.0, Ollama's default | 1.0, sent | 1.0, sent |
| presence, frequency penalty | 0.0, 0.0 | 0.0, 0.0, sent | 0.0, 0.0, sent |
| the rest (typical_p, DRY, XTC, mirostat) | off | off, its defaults | none |
| order of the samplers | llama.cpp's, inside Ollama | penalties; dry; top_n_sigma; top_k; typ_p; top_p; min_p; xtc; temperature | vLLM's own |
| the form is held by | Ollama's format | a grammar made from the schema | xgrammar, with disable_any_whitespace |

The one value set away from an engine's own default is min_p on llama.cpp, to equal Ollama's.
At temperature 0 every engine takes the most likely token, so top_k, top_p and min_p shape only
the ten chains at 0.5. The random numbers behind a seed are each engine's own, so chain B3 on
one engine is not chain B3 on another.

## 8. Proved before the first round

On each of the five starts, one engine on the card at a time, before the first round
(machine/proofs.json): the Ollama service, the second Ollama process, llama.cpp with one slot,
llama.cpp with two slots, and vLLM with the switch.

| Proof | ollama-service | ollama-private | llamacpp-1 | llamacpp-2 | vllm-compact |
|---|---|---|---|---|---|
| No thinking text in a reply | 32 of 32 | 32 of 32 | 32 of 32 | 32 of 32 | 32 of 32 |
| A reply that fits its form | 32 of 32 | 32 of 32 | 32 of 32 | 32 of 32 | 32 of 32 |
| A reply asked for 5 tokens is seen as | cut | cut | cut | cut | cut |
| A call at the full context (tokens in, outcome) | 15,001, ok | 15,001, ok | 15,001, ok | 15,001, ok | 15,002, ok |
| Inputs of about 17,500 and 78,000 tokens | did_not_fit, did_not_fit | did_not_fit, did_not_fit | did_not_fit, did_not_fit | did_not_fit, did_not_fit | did_not_fit, did_not_fit |
| Tokens read less the run of 4 Oct, same 32 calls | 0 | 0 | 0 | 0 | 1 |
| Two short calls at the same moment: alone; together | - | 0.55 s; 0.73 and 0.8 s | - | 0.62 s; 0.88 and 0.9 s | 0.48 s; 0.54 and 0.55 s |

The 32 calls are the first pass of all 16 cases. The one token vLLM reads more is a space: the
repack's template writes the system text as `...SYSTEM <turn|>`, and the template inside
Google's file writes `...SYSTEM<turn|>`. Everything else is wrapped the same way:

    <bos><|turn>system\nSYSTEM<turn|>\n<|turn>user\nUSER<turn|>\n<|turn>model\n<|channel>thought\n<channel|>

On vLLM the switch was also proved in force: in 32 of 32 replies the only blank space outside a string is one single space after a colon or a comma.
Two calls of about 15,000 tokens each, sent together, were both answered on each of the three
starts for two calls at once, so each call had its own 16,384. Before each together arm of the
run, two short calls were sent at the same moment once more and seen to overlap.

## 9. The clock

The seconds of a call are measured by the bench's own door, from just before the engine is
asked to just after the reply is read: the same code and the same clock for every engine. The
seconds of a pass are measured around the whole pass. Sent together, a pass runs from sending
both calls until both are back. Each step began with one call that was recorded and not measured,
so that the model was loaded and warm. The times come only from the calls that a result names.

## 10. The rounds and the steps, in the order they ran

All on 7 Oct 2026, local time, from 07:17 to 15:25, by a driver script with nobody at the desk. Three
rounds; in each round every engine took one turn, in this order: round 1 Ollama, llama.cpp, vLLM;
round 2 llama.cpp, vLLM, Ollama; round 3 vLLM, Ollama, llama.cpp. A turn is three steps: the round's chain at
temperature 0 with the calls one after another, the round's chains at 0.5, and the same chain at
0 with the two calls sent together, on the engine's start for two calls at once. Each engine has
two result folders for the day, one for each way, and each round added its chains to them.

| Round | Engine | Step | Chains | Started | Ended | Minutes | First call, not measured (ms) |
|---|---|---|---|---|---|---|---|
| 1 | Ollama | one after another | A1 | 07:17 | 07:28 | 11.6 | 3,522 |
| 1 | Ollama | one after another | B1, B2, B3 | 07:28 | 08:02 | 34.0 | 854 |
| 1 | Ollama | together | A1 | 08:02 | 08:11 | 9.0 | 654 |
| 1 | llama.cpp | one after another | A1 | 08:11 | 08:23 | 12.0 | 869 |
| 1 | llama.cpp | one after another | B1, B2, B3 | 08:23 | 09:00 | 36.1 | 852 |
| 1 | llama.cpp | together | A1 | 09:00 | 09:09 | 9.3 | 816 |
| 1 | vLLM | one after another | A1 | 09:09 | 09:17 | 7.6 | 1,077 |
| 1 | vLLM | one after another | B1, B2, B3 | 09:17 | 09:42 | 25.5 | 624 |
| 1 | vLLM | together | A1 | 09:42 | 09:49 | 6.2 | 624 |
| 2 | llama.cpp | one after another | A2 | 09:49 | 10:01 | 12.0 | 870 |
| 2 | llama.cpp | one after another | B4, B5, B6 | 10:01 | 10:37 | 36.1 | 854 |
| 2 | llama.cpp | together | A2 | 10:37 | 10:46 | 9.2 | 821 |
| 2 | vLLM | one after another | A2 | 10:47 | 10:54 | 7.7 | 1,075 |
| 2 | vLLM | one after another | B4, B5, B6 | 10:54 | 11:20 | 25.4 | 626 |
| 2 | vLLM | together | A2 | 11:20 | 11:26 | 6.2 | 621 |
| 2 | Ollama | one after another | A2 | 11:26 | 11:37 | 11.6 | 3,454 |
| 2 | Ollama | one after another | B4, B5, B6 | 11:37 | 12:12 | 34.4 | 854 |
| 2 | Ollama | together | A2 | 12:12 | 12:21 | 9.0 | 649 |
| 3 | vLLM | one after another | A3 | 12:21 | 12:29 | 7.7 | 1,077 |
| 3 | vLLM | one after another | B7, B8, B9, B10 | 12:29 | 13:03 | 33.8 | 626 |
| 3 | vLLM | together | A3 | 13:03 | 13:09 | 6.2 | 620 |
| 3 | Ollama | one after another | A3 | 13:09 | 13:21 | 11.6 | 3,399 |
| 3 | Ollama | one after another | B7, B8, B9, B10 | 13:21 | 14:06 | 45.8 | 852 |
| 3 | Ollama | together | A3 | 14:06 | 14:15 | 9.0 | 642 |
| 3 | llama.cpp | one after another | A3 | 14:15 | 14:28 | 12.0 | 871 |
| 3 | llama.cpp | one after another | B7, B8, B9, B10 | 14:28 | 15:15 | 47.9 | 852 |
| 3 | llama.cpp | together | A3 | 15:15 | 15:25 | 9.3 | 820 |

Every step ended with exit 0. No step failed and none was left out. machine/steps.json holds the
same table as data.

## 11. What happened during the run

- Nothing. 487 minutes were logged, once a minute; the screensaver was never running; the
  highest one-minute load was 5.86; stay-awake was on throughout. machine/load.json.
- The sampler of the card's memory was restarted a minute into the first step, so about 10
  seconds of its samples are missing there. The driver was not touched.
- vLLM's typical pass fell a little through the day (3.56, 3.47, 3.43 s) while the other engines held
  still. Its spread is within the steadiness line and changes no verdict.

## 12. What was done to make each engine work

- Ollama: the line `REQUIRES 0.30.5` was added to the Modelfile, as section 5 says. For the
  together arm, the second process of section 5.
- llama.cpp: nothing beyond the options of section 5.
- vLLM: the switch of section 5, and nothing else. Its caches and those of its libraries were
  pointed into ENG with their own variables (XDG_CACHE_HOME, XDG_CONFIG_HOME, VLLM_CACHE_ROOT,
  VLLM_CONFIG_ROOT, TRITON_CACHE_DIR, TORCHINDUCTOR_CACHE_DIR, CUDA_CACHE_PATH, NUMBA_CACHE_DIR).

## 13. How each public file was made

- `cases/`: the cases as the bench read them, copied byte for byte by the bench's exporter, with
  a list of their own; of the recorded transcripts only the rows of consultation 495 are taken.
  They are the same bytes as the cases published with the first bench on 6 Oct.
- `arms/NAME/`: written by the exporter from the arm's result files and its record of calls, with
  the card's memory over the arm's own steps from the sampler's file and the steps file, and the
  arm's measured facts given on the command line. Every public reply was checked against its
  record. The requests are not written.
- `rounds.json`: written by hand from the driver's plan, as data for the tool.
- `figures.json` and `figures.md`: the tool's own output, `openconsult-bench figures --public`,
  run on this folder; the same command on the private result folders gave the same output, byte
  for byte.
- `machine/`: written by a script from the driver's log, the sampler's two files, the minute log
  and the proofs' outputs. Each file says how its figures were measured. The sampler's raw files
  are not published, because they hold process command lines.
- README.md and this page: written by a script from figures.json, machine/*.json, rounds.json and
  the arms' own files. No measured figure is typed by hand. Where a figure is rounded, it is
  worked from the milliseconds and rounded once.
- `bench-of-6-oct/`: copied byte for byte from the public folder of 6 Oct, each file checked by
  its sha256.

## 14. To check the figures, or to run it again

The figures of README.md from this folder alone, with no engine:

    uv sync
    uv run openconsult-bench figures --public engine-bench

The marks of one arm from its replies alone:

    uv run openconsult-bench score --replies engine-bench/arms/vllm-repack-compact/replies.jsonl.gz

To run an arm again on an engine of your own, with the cases of this folder:

    uv run openconsult-bench run --cases engine-bench/cases --out SOME_FOLDER_OUTSIDE_THE_REPO \
        --kind llamacpp --engine http://127.0.0.1:8171 --model google/gemma-4-26B-A4B-it-qat-q4_0-gguf --chains A1
    uv run openconsult-bench score --out SOME_FOLDER_OUTSIDE_THE_REPO

`--kind` is ollama, llamacpp or vllm. `--chains` names the chains to run; without it all 13 run.
Add `--together` for the arm with the two calls sent together. To get the figures of this page
for your own arms, write a rounds file like `rounds.json` for them and run
`openconsult-bench figures --rounds FILE --arm NAME=FOLDER ...`.
