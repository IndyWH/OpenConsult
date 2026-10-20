# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.
- So far this version runs one acted consultation from Start to a final
  transcript: the name, date of birth and sex of an acted patient go in, the
  doctor confirms the consultation is acted, presses Start and talks; the
  words appear live beside the model's differentials, questions and signs,
  the alarm in its three states, and a quiet clock; the sound is recorded as
  the microphone gives it; at Stop the app asks which speaker was the doctor,
  checks who spoke each line with the language model, checks for missing
  speech against the sound, and shows the final transcript with its
  warnings. The note and the review page come next (6b). Underneath: one
  user and a login, This machine, the language model engine chosen once at
  start (vLLM first on Linux with a suitable graphics card, Ollama otherwise)
  with the two calls of a pass sent together, the room on the card read once,
  and speech in four ways behind one door: WhisperX with pyannote, Nemotron,
  Speechmatics and AssemblyAI, each proven by a self-test on a bundled clip;
  a replay bench that feeds a banked recording through that door as if live
  and scores it against the script; and a bench of the three models together
  on one card. Every bench figure so far is from a rehearsal on old recordings
  and machine voices; none counts.
- The engine bench is in engine-bench: the same cases through Ollama, llama.cpp and vLLM, with every reply and every figure.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
