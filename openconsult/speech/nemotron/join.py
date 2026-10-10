"""The join of the Nemotron choice (spec 15.9, ruling 8; ruling 4): words
with their times from the English model, stretches of speech with their
speakers from the speaker model, and out come lines. A plain function
with no library, imported by the worker and by the suite by path. It
can never change, add or remove a word: the words out are the words in,
in order, whatever the labels. A word that no stretch covers, or that
two speakers cover equally, has no speaker; it is never given the
nearest stretch, as the join of Task 15 did."""

from __future__ import annotations

# A line closes at a sentence's end, at a change of speaker, or at a
# pause this long between words. The pause is v1's sent_break_sec, a draft
# for the owner (the 5b plan review).
PAUSE_S = 1.0
SENTENCE_END = (".", "?", "!")
# A frame of the speaker model's output counts as speech at or above this
# probability: the model's own binarisation point.
SPEECH_AT = 0.5


def stretches_of(probabilities: list[list[float]], frame_s: float, speakers: int) -> list[dict]:
    """Runs of frames at or above SPEECH_AT, per speaker slot, as stretches
    {start, end, speaker}. Only the first `speakers` slots count: the
    number is given, never worked out (V1_LESSONS 2.1); a slot beyond it
    makes no stretch, so its words have no speaker."""
    stretches = []
    slots = len(probabilities[0]) if probabilities else 0
    for slot in range(min(int(speakers), slots)):
        start = None
        for index, frame in enumerate(probabilities):
            on = frame[slot] >= SPEECH_AT
            if on and start is None:
                start = index
            elif not on and start is not None:
                stretches.append({"start": round(start * frame_s, 3), "end": round(index * frame_s, 3), "speaker": f"S{slot + 1}"})
                start = None
        if start is not None:
            stretches.append({"start": round(start * frame_s, 3), "end": round(len(probabilities) * frame_s, 3),
                              "speaker": f"S{slot + 1}"})
    return stretches


def speaker_of(word: dict, stretches: list[dict]) -> str | None:
    """The speaker whose stretches overlap the word longest; none when no
    stretch overlaps it or two speakers overlap it equally."""
    overlap: dict[str, float] = {}
    for stretch in stretches:
        covered = min(float(word["end"]), float(stretch["end"])) - max(float(word["start"]), float(stretch["start"]))
        if covered > 0:
            overlap[str(stretch["speaker"])] = overlap.get(str(stretch["speaker"]), 0.0) + covered
    if not overlap:
        return None
    best = max(overlap.values())
    leaders = [speaker for speaker, seconds in overlap.items() if abs(seconds - best) < 1e-9]
    return leaders[0] if len(leaders) == 1 else None


def join(words: list[dict], stretches: list[dict]) -> list[dict]:
    """Lines {speaker, start, end, text, words} from words {word, start,
    end} in order and stretches {start, end, speaker}."""
    lines: list[dict] = []
    previous = None
    for word in words:
        speaker = speaker_of(word, stretches)
        labelled = {"word": str(word["word"]), "start": float(word["start"]), "end": float(word["end"]), "speaker": speaker}
        opens = (previous is None or speaker != lines[-1]["speaker"]
                 or labelled["start"] - previous["end"] >= PAUSE_S or previous["word"].endswith(SENTENCE_END))
        if opens:
            lines.append({"speaker": speaker, "start": labelled["start"], "end": labelled["end"],
                          "text": labelled["word"], "words": [labelled]})
        else:
            line = lines[-1]
            line["end"] = max(line["end"], labelled["end"])
            line["text"] += " " + labelled["word"]
            line["words"].append(labelled)
        previous = labelled
    return lines
