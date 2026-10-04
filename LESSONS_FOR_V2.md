# Lessons for v2 from the speech work of 3 and 4 October 2026

These lessons come mainly from Tasks 13 to 18 of v1.1. They are for the v2 rewrite.
The report named after each lesson is kept outside this repository.
OpenConsult is a research and education prototype, not a medical device.
Every recording named here is scripted or acted. None is a real patient.

## 1. Judge by clinical outcome
Word error rate is not the measure. Count what changes the meaning for the patient:
a lost negation, dropped advice, a wrong drug or dose. Then ask what reaches the note.

Source: TASK15_SPEECH_BENCH.md, TASK17_SCRIPTED_BENCH.md.

## 2. An invisible error is worse than a visible one
A dropped passage cannot be seen on review. A misspelt drug name can.
v2 must make errors visible. A gap check at Stop is a requirement, whatever the speech model.

Source: TASK17_SCRIPTED_BENCH.md, TASK18_DROPPED_SPEECH.md.

## 3. The clinical prompt deleted speech for eleven weeks
A prompt added to the final pass on 17 July raised drug and test names from 37 to 45 right out of 53, on ten scripted readings.
It also made WhisperX skip the start of some 30 s pieces of audio.
13 of 59 stored consultations had gaps of 5 s or more, 264 s in all. 7 were approved.
The prompt caused 12 of the gaps, in 10 consultations, 175 s in all. The rest had other causes, and one is unexplained.
The dropped speech included safety-net advice. Nobody saw it, because nothing marks missing speech.
The planned check of the change looked at drug names only. Nothing looked for dropped speech until Task 17.
Rule for v2: every change to the speech path is tested on whole recordings for dropped speech.

Source: TASK18_DROPPED_SPEECH.md; the plan for the check is in evals/2026-07-17_recordings_inventory_deviation.md.

## 4. Drug names are not solved
Without the prompt, gliclazide was missed 3 times out of 3. The fixed final pass gives 37 of 53 names, as before the prompt.
Ideas not yet tested: correct names at the note stage, check against a drug list after transcription,
the prompt with timestamps on (losses fell from 6 to 1 on the ten readings), decode a short piece again without the prompt.

Source: TASK18_DROPPED_SPEECH.md; the count after the fix is from Task 19.

## 5. Mute words, never segments
The rule that keeps the assistant's voice out of the transcript dropped whole segments,
and with them the patient's words between her sentences.
In v2 the assistant asks one question at a time, so this matters more.

Source: TASK18_DROPPED_SPEECH.md.

## 6. A claim in the help pages needs a test behind it
The help said a transcript with missing speech is refused. Only missing speech at the end was.

Source: TASK18_DROPPED_SPEECH.md.

## 7. The test suite overwrote real recordings
One test wrote an 11 s clip into the live recordings folder. From 24 July it overwrote live files.
83 files were test clips. Two real consultations lost their audio.
One of them has a probable copy among the mock recordings. The other has none.
Rules for v2: tests never touch live data, and a guard fails the run if they do.
Recordings are written once and never overwritten. Recordings are backed up apart from the app.

Source: TASK16_RECORDINGS.md.

## 8. Capture quality decides the benchmark
Echo cancellation on the stored stream was turned off on 29 July.
Earlier recordings are poor (not verified: no report measured recording quality).
On the July recordings Nemotron looked far worse than WhisperX: 24 meaning changes against 10.
On seven later readings the gap almost closed: 34 against 31.
That capture caused the difference is not verified. The July bench also had two later recordings, and other things differed.
Rules for v2: store the capture settings with each recording.
Benchmark only on recordings made with the current capture.

Source: TASK15_SPEECH_BENCH.md, TASK16_RECORDINGS.md, TASK17_SCRIPTED_BENCH.md.

## 9. How to benchmark speech
Select recordings from the database, not by file type. A search for WAV missed the best recordings, stored as flac.
A script gives a true error rate. Without one, a bench can only count disagreement.
Readers leave the script. Where every model agrees against the script, treat it as spoken that way.
One recording is not a test.
Feed a file in live-sized chunks. Do not play it through a speaker.
A language model does not always write the same note twice, even at temperature 0.
In one bench the first run never matched the second. In others, three runs were identical.
Write each note at least twice to measure chance.

Source: TASK15_SPEECH_BENCH.md, TASK16_RECORDINGS.md, TASK17_SCRIPTED_BENCH.md; the note runs are from TASK5C_LETTERS.md, TASK3L_TIMING.md and TASK3M_LETTERS.md.

## 10. Nemotron, as measured on 3 and 4 October 2026
Models: nemotron-speech-streaming-en-0.6b, nemotron-3.5-asr-streaming-0.6b, Nemotron-3-Diarization.
It fits: 20.6 of 24 GiB with Gemma 4, its embedding model and both live Nemotron models loaded. It runs about 37 times faster than real time.
Run live, it leaves 0.03 s of work at Stop, so no model switch is needed.
Words, on 7 scripted two-voice recordings with good capture, errors that change the meaning:
WhisperX 31, the live Whisper model 43, Nemotron English alone 34, Nemotron 3.5 paired with diarisation 71.
Nemotron English alone dropped no lines. WhisperX dropped passages, because of the prompt.
The paired setup is the weakest. If Nemotron is used, run the English model on its own for the words.
Speakers, share of words under the right speaker: pyannote 75.5 percent, Nemotron over the whole recording 72.6, Nemotron live and paired 62.2.
Live, it heard the second voice 4 to 11 s late on four recordings, only at Stop on one, and on two never.
Speaker labelling is weak in every setup. The first-speaker rule is fragile.
Idea for v2: v2 has one user, so the doctor's voice can be enrolled once and every line labelled doctor or not doctor.
Licences: the English model is under the NVIDIA Open Model License. The other two are under OpenMDW-1.1.

Source: TASK13_NEMOTRON.md, TASK14_NEMOTRON_WER.md, TASK17_SCRIPTED_BENCH.md.

## 11. The wait at Stop
Task 3l measured 17.8 s on one consultation: 10.2 s for the audio pipeline and 2.5 s for the model switch.
The switch was built when the language model filled the card. Gemma 4 is smaller.
Task 3l estimated about 26 GiB for Gemma 4 and the audio models together, more than the 24 GiB card.
In Task 19 WhisperX could not load while Gemma 4 and its embedding model were loaded.
Not yet tested: keep WhisperX and pyannote loaded beside Gemma 4.
The embedding model can run on the CPU, which frees memory on the card (not verified; it takes 1.0 GiB on the card).

Source: TASK3L_TIMING.md; the failed load is from Task 19.

## 12. Laptops and installers
Not verified: none of the Task 13 to 18 reports covers this lesson.
Nemotron speech runs on Apple and AMD laptops through GGUF or ONNX runtimes, not through NVIDIA's own toolkit.
Those runtimes are young. One ONNX export has no word timestamps.
An installer needs three builds, one per system. Signing costs money on macOS and Windows.
PostgreSQL cannot sensibly ship inside an executable. v2 needs an embedded database.

## 13. Not yet done
Live consultations with two actors on the Nemotron pipeline.
Auto mode timing in a room with Nemotron.
A bench that judges the note written from each set of speaker labels.
A repeat of the scripted bench with the fixed WhisperX against Nemotron English alone.
Task 19 ran the fixed WhisperX on these readings for drug names only. The meaning count was not repeated.

Source: TASK13_NEMOTRON.md, TASK17_SCRIPTED_BENCH.md.

## 14. Open decisions for the owner
Should the app refuse to overwrite an existing recording.
Should the audio of one lost consultation be restored from its copy among the mock recordings.
Should the approved transcripts that have gaps be regenerated.
One gap, in consultation 79, is still unexplained.
v1.0 on GitHub has the dropped-speech fault. A note to users is owed.

Source: TASK16_RECORDINGS.md, TASK18_DROPPED_SPEECH.md.
