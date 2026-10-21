# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.
- So far this version runs acted consultations from a patient list to an
  approved note. The Patients page lists every acted patient, last seen
  first, with a number, and one search box finds one by part of a name, a
  date of birth or the number; the patient's page corrects a name, a date
  of birth or a sex with every change audited, and an earlier consultation
  keeps the details it ran with. A consultation starts under a patient seen
  before with their earlier approved notes listed and a switch, on by
  default, that sends the last three to the two calls of every pass as
  background, marked on the panel and at review, and shows them, folded,
  on the live page; the words appear live beside the model's
  differentials, questions and signs, the alarm in its three states with
  the differential it names marked red, and a quiet clock; the sound is
  recorded as the microphone gives it and kept as Opus after Stop; at Stop
  the app asks which speaker was the doctor, checks who spoke each line
  with the language model, checks for missing speech against the sound,
  drafts the note from the transcript with every entry's line numbers
  checked by code, and shows the review page: the draft note first, each
  entry editable and each line number a press that shows the line, the
  model's last differentials beside the assessment and marked as not part
  of the note, Approve with the counts of warnings and alarms, Refuse, the
  warnings and the alarms each a press from the sound, and the transcript
  with a player for the recording, where a word or a speaker can be
  corrected and the note drafted again. An approved note is read-only and
  audited; the copy gives the note alone. Recordings are deleted after a
  retention time the doctor sets, default 90 days; one Delete removes a
  consultation's recording, transcript and note and leaves an audit line
  of counts. The background to the model was measured before it was kept,
  on two made follow-up cases with the marks set first. Alba, the guideline
  search and the teaching mode come later. Underneath: one user and a
  login, This machine, the language model engine chosen once at start
  (vLLM first on Linux with a suitable graphics card, Ollama otherwise)
  with the two calls of a pass sent together, the room on the card read
  once, the recording converter found once (ffmpeg carried by the
  imageio-ffmpeg package, or the computer's own), and speech in four ways
  behind one door: WhisperX with pyannote, Nemotron, Speechmatics and
  AssemblyAI, each proven by a self-test on a bundled clip; a replay bench
  that feeds a banked recording through that door as if live and scores it
  against the script; and a bench of the three models together on one
  card. Every bench figure so far is from a rehearsal on old recordings and
  machine voices; none counts.
- The engine bench is in engine-bench: the same cases through Ollama, llama.cpp and vLLM, with every reply and every figure.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
