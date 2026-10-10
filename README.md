# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.
- So far this version starts, sets up its one user, describes the machine it
  runs on, can reach the local language model, and can turn speech into text
  in four ways: WhisperX with pyannote, Nemotron, Speechmatics and AssemblyAI,
  each proven by a self-test on a bundled clip. It cannot run a consultation
  yet.
- The engine bench is in engine-bench: the same cases through Ollama, llama.cpp and vLLM, with every reply and every figure.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
