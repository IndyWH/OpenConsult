# OpenConsult v2 (in development)

This branch is where OpenConsult v2.0 is being built.

- The working app, v1, is on the main branch.
- The plan for v2 is in V2_SPEC.md.
- So far this version runs acted consultations from a patient list to an
  approved note and its referral letters. The Patients page lists every
  acted patient, last seen first, with a number, and one search box finds one by part of a name, a
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
  audited; the copy gives the note alone. After Approve, a Referral
  letters section lists the referrals the note states and, under a line
  saying they are the model's suggestions and not advice, the ones it
  suggests, each with the consultant's title in a field the doctor can
  change; one press drafts a letter from the approved note only, with the
  assessment withheld from the model, and code checks every sentence
  against the note lines it cites, replacing a failed one with a
  placeholder, dropping an allergy sentence the note does not support,
  and refusing a letter under half grounded; the letter has its own page,
  each paragraph editable, with Approve (then read-only, and one copy
  gives the letter alone) and Refuse, and a specialty the doctor names
  gets a letter with no list. The letter prompts were benched four times
  on four approved notes, the owner ruling after each, before the page
  was wired. A Guidelines section of Settings takes guideline documents
  from files on this computer (HTML, PDF or plain text), each with its
  title, its publisher and one statement that the doctor holds the right
  to use it this way, splits each by its headings into passages of 40
  to 350 words, embeds them with EmbeddingGemma 2 in a worker of its own
  on the graphics card or the processor, and lists them with Remove;
  the corpus ships empty and the app never fetches a document itself.
  The Guidelines pane on the live page answers from those passages alone:
  after a pass whose top two differentials change, a search over the
  loaded passages and one summary call, the summary with each [n] mark a
  press that opens its passage with its source's title and publisher, the
  cited sources and the counts of the corpus under it, or the one line
  that the loaded guidelines do not cover those names; a failed call
  changes nothing of the pass or the alarm, and with no document loaded
  nothing is asked. It was benched first on fifteen approved queries, 13
  chains each: the summary cited only passages it was given in every
  chain and refused every made-up topic, and ran over 150 words on two
  queries, which the owner ruled to keep as the measure of this model's
  word limit. A reranker was benched beside it and held its own marks,
  but on the card beside the engines it would sit on the processor at
  about four seconds a search, so it is not in the app.
  Recordings are deleted after a
  retention time the doctor sets, default 90 days; one Delete removes a
  consultation's recording, transcript and note and leaves an audit line
  of counts. The background to the model was measured before it was kept,
  on two made follow-up cases with the marks set first. Alba and the teaching mode come later. Underneath: one user and a
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
