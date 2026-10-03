# speech_nemotron — the Nemotron speech environment

Research and education prototype. Not a medical device. No real patients
or real patient data.

This folder holds the optional Nemotron live speech path: NVIDIA's
`nemotron-3.5-asr-streaming-0.6b` (speech, en-GB) paired with
`Nemotron-3-Diarization` (who spoke when) through NeMo Speech's
`SpeakerTaggedASR`. The pairing and its settings follow Option 2 of the
diarisation model's `ASR_INTEGRATION_GUIDE.md` (`masked_asr=true`,
`att_context_size=[56,13]`).

It runs in its **own environment**, as a separate process, in the way
Piper TTS does. NeMo brings its own PyTorch, so it never enters the app's
`pyproject.toml` or `uv.lock`, and the app never imports anything from
this folder.

## Build

```bash
speech_nemotron/setup.sh
```

The script clones NeMo Speech at a pinned commit into
`~/.local/share/openconsult-nemotron/Speech` and runs that checkout's
own `uv sync --frozen --python 3.13 --extra asr --extra cu13`. It then
downloads both checkpoints, at pinned revisions, into the Hugging Face
cache (`HF_HOME`). It needs no sudo and can be run again safely. The
environment takes about 6 GB of disk and the checkpoints about 2.6 GB.

## Files

- `setup.sh` builds the environment. The NeMo commit and the model
  revisions are pinned in it.
- `nemotron_stream.py` holds one consultation's streaming state: it
  feeds audio, decides when a line is final, and sets the watermark that
  keeps lines in spoken order. It runs inside the Nemotron environment
  only.

## Licences

Both models are under the OpenMDW-1.1 licence; see `NOTICE`. NeMo Speech
is Apache-2.0. None of the three is vendored into this repository.
