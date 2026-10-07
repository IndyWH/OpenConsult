# The two parts kept from the bench of 6 Oct 2026

These files are as they were written on 6 Oct 2026, copied byte for byte from the public folder
of that day, and were scored by the rules of that day: in their marks.json candidate means every
hard mark over all 13 chains, and the line for faster was 1 second. By the rules of the bench of
7 Oct 2026 (README.md, section 3) candidate means every hard mark on the chains at temperature 0,
and faster means half a second in every round.

- `arms/vllm-repack`: the vLLM arm that ran without the switch, with its 14 failed chains, all at
  temperature 0.5. It is the evidence for the switch (README.md, section 7).
- `arms/ollama-repeat`, `arms/llamacpp-repeat`, `arms/llamacpp-repeat-no-cache`, `arms/vllm-repeat`,
  `arms/vllm-repeat-batch-invariant`: the repeat test (README.md, section 8). Its vLLM arms ran
  without the switch.

No other arm of the first bench is published. The seconds inside these kept files are those of
6 Oct. They are not set beside the seconds of 7 Oct, because the seconds of the first bench could
not be trusted (README.md, section 12).
