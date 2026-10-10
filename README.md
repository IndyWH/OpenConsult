# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.
- So far v2 starts, sets up its one user, describes the machine it runs on,
  can reach the local language model through its one door with every call
  recorded, and has one door to speech with its first choice, WhisperX with
  pyannote, and a self-test that transcribes a bundled clip. It cannot run a
  consultation yet.
- The engine bench is in engine-bench: the same cases through Ollama, llama.cpp and vLLM, with every reply and every figure.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
