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
  the differential it names marked red, and a quiet clock; the live page
  asks the browser for sound at 48,000 samples a second and says so when
  the browser does not give it; the sound is
  recorded as the microphone gives it and kept as Opus after Stop; at Stop
  the app asks which speaker was the doctor, checks for missing speech
  against the sound, has the language model read the final transcript
  once and mark the drug names it doubts, drafts the note from the
  transcript with every entry's line numbers checked by code, and shows
  the review page: the draft note first, each entry editable and each
  line number a press that shows the line, the model's last differentials
  beside the assessment and marked as not part of the note, Approve with
  the counts of warnings and alarms, Refuse, the warnings and the alarms
  each a press from the sound, and the transcript with a player for the
  recording, where a word or a speaker can be corrected and the note
  drafted again. A doubted drug name is shown in three places, on its
  line, as a warning and on every note entry that draws on that line,
  always as the words that were heard and never as a guess, and one line
  says that a name with no mark is not proven right. The check of who
  spoke no longer runs by itself: one control on the review page, Check
  who spoke, asks the language model for it, every change is marked and
  can be undone one line at a time or all at once, and the page says so
  above the note when who spoke has changed since the note was written.
  An approved note is read-only and
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
  was wired; a fifth and a sixth bench, of four prompt edits and one
  rule of the check, kept the rule (an expectation sentence in the
  pronoun form is read by the check) and held the prompt edits both
  times, the owner rewording two sentences between them, because the
  marks fell each time; the edits stopped there, and the letters run on
  the prompts the fourth bench left. A Guidelines section of Settings takes guideline documents
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
  about four seconds a search, so it is not in the app. Every
  consultation has a read-only page, What the model saw, reached from
  its review page and from the patient's page: a timeline of every model
  call from Start to final with the passes marked and a slow pass seen at
  a glance, the seconds per kind of call, and each call in time order
  opened to what went in, marked by its source (the patient line, the
  earlier notes as background, the fixed words of the frame by file
  name, the transcript as sent, the note lines, the passages with their
  sources, the query), the reply word for word, and the prompt by name
  and hash, never its text.
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

## The cloud language model, and how it was chosen

On a machine with a suitable NVIDIA card, OpenConsult runs its language
model on that machine: Gemma 4, through vLLM or Ollama, and nothing a
patient says leaves the computer. On any other machine, and on every
Mac, the language model runs in the cloud, and the app says so before
the first consultation. This is how the cloud model was chosen, in
November 2026. Every figure below comes from the same four benches the
local model had run: the 16 acted cases of stage 3 (13 chains each), the
two made follow-up cases, the four approved notes and their letters, and
the fifteen guideline queries. The cloud model was sent the same words,
byte for byte, and judged by the same code.

**Ollama cloud, Gemma 4 31B, 6 November.** The bench stopped at its
first call. The service does not hold a model to the JSON form the
request carries, so the reply came back outside the form and the app's
door refused it, as it refuses every such reply. Every pass of a
consultation on that service would have failed. Its own page confirmed
it afterwards: structured outputs are not supported in its cloud. It was
dropped the same morning, and a rule was added: no service is planned
on until its own page says it holds a form, and the first act of any run
on a new service is one real call with the app's own form.

**DeepInfra, Gemma 4 26B, 6 November.** The gate call passed on the
first try. 4,729 calls; one failed, a call that passed the 60 second
limit. Every emergency alarm fired in every chain; nothing invented
reached a letter or a guideline summary. But in 12 of 13 letters of one
case the model wrote blood results with units the note did not give, so
the check replaced those sentences, and the letters bench missed three
marks the local model held. A pass took 6.5 seconds in the middle,
against 2.8 on the local card; 241 passes of 1,889 took over 10
seconds and 36 over 20. The service's faster tier was tested and was not
faster in a way a patient would feel. Cost: about 3 US cents for a
15-minute consultation. The host gives no version or digest for the
model it serves, so a later run cannot be proven to be the same build.

**Claude Haiku 5.5, 7 and 8 November.** The gate call needed three tries
before one passed: the service wants every object of a form marked as
taking no other property, does not hold a limit on a list's length, and
refuses the temperature field on its current API version, so the
thirteen chains sample at the service's own default. It also adds a
short instruction of its own about the format to every request, whose
words are not published; on the alarm call that instruction and the form
cost 391 tokens. The first full run, on 7 November, failed 108 calls of
4,438, every one of them our own doing: the model wrote four or five
urgent actions where our alarm form allowed three, and five paragraphs
where the letter form allowed four, and the door refused the whole
reply. The owner ruled the same evening that the length of a list is
never a reason to refuse a reply, since how many things must happen now
is a fact of the presentation and not a choice of ours, and that the
letter check marks a figure it cannot find in the note for the doctor
to look at, instead of removing the sentence. The second full run, on 8
November, under those rules: 4,685 calls, none failed. Every emergency
alarm fired in 13 of 13 chains on all seven emergency cases; no alarm
fired on any routine case. Nothing invented reached any of 65 letters:
no unit the note did not give, no line number, no ungrounded allergy.
Nothing invented reached any guideline summary. The misses that remain
are small: one referral list of 13 named one specialty of two; the
summaries ran over 150 words on four queries; and the check marks a
sentence in every letter of one case because the model wrote four times
a day where the note wrote qds, which the check did not yet read as the
same figure. A pass took 4.5 seconds in the middle and 12.8 at the
slowest; one pass of 1,898 took over 10 seconds. Cost: about 9 US cents
for a 15-minute consultation. The service does not keep what is sent by
default and does not train on it. Like the host above, it gives no
digest, so a later run cannot be proven to be the same build.

**The ruling, 7 and 8 November.** Claude Haiku 5.5 is the cloud language
model of v2.0, as it stands, with the owner's words: the figures stand
and it is offered. DeepInfra is not offered; its bench kind stays in the
repo for comparison. The figures that settled it were the wait and the
letters: 4.5 seconds against 6.5, with one slow pass in 1,898 against
241; and no invented unit in 65 letters against 12 in 13. The cost, three
times the host's, was not weighed against a patient's wait. The owner
also ruled that Alba's auto mode is offered wherever the language model
answers fast enough and the transcription is live, which the cloud model
meets on these figures, pending its own auto-mode bench.

What this comparison cannot say: which model picks the better
differential or asks the better next question. The four benches measure
floors (does the alarm fire, is anything invented) and faithfulness to
the note, not clinical judgement. That is the question of the
preclinical study, which runs on the local model.

OpenConsult is a research and education prototype. It is not a medical
device. It must never be used with real patients or real patient data.

Licence: AGPL-3.0-or-later. See LICENSE and NOTICE.
