"""The merge of raw segments into speaker turns, ported from v1's
finalize.py as a plain function (V1_LESSONS 1.3). A raw segment is what
the pass at Stop gave: text, start, end, and words with a start, an end,
a score and a speaker where the models gave them."""

from __future__ import annotations

from openconsult.speech.lines import Line


def speaker_of(segment: dict) -> str | None:
    """The cluster most of the segment's words belong to, or none."""
    speakers = [w.get("speaker") for w in segment.get("words", []) if w.get("speaker")]
    return max(set(speakers), key=speakers.count) if speakers else None


def scores_of(segment: dict) -> list[float]:
    return [float(w["score"]) for w in segment.get("words", []) if "score" in w]


def merge_into_turns(raw_segments: list[dict]) -> list[Line]:
    """Consecutive segments of one cluster become one turn, except when
    the whole pass came back as a single cluster: then the segment
    boundaries are kept, because there is nothing to join on and the
    merge once made one 300-second turn of 22 (v1, recording 66).

    A turn's confidence is the mean score of its scored words, or none
    when no word was scored. v1 gave 0.5 there; v2 does not make one up,
    because a confidence is a score or none (spec 11.4; 11.5 rule 5)."""
    clusters = {speaker_of(s) for s in raw_segments if speaker_of(s)}
    single_cluster = len(clusters) <= 1
    turns: list[dict] = []
    for segment in raw_segments:
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        speaker = speaker_of(segment)
        scores = scores_of(segment)
        if turns and not single_cluster and turns[-1]["speaker"] == speaker:
            previous = turns[-1]
            previous["text"] += " " + text
            previous["end"] = float(segment["end"])
            previous["scores"] += scores
        else:
            turns.append({"speaker": speaker, "start": float(segment["start"]),
                          "end": float(segment["end"]), "text": text, "scores": scores})
    return [Line(t["speaker"], t["start"], t["end"], t["text"], _mean(t["scores"])) for t in turns]


def _mean(scores: list[float]) -> float | None:
    return round(sum(scores) / len(scores), 3) if scores else None


def as_line(segment: dict) -> Line:
    """One raw segment as a line, unmerged: for the rule and the record."""
    scores = scores_of(segment)
    return Line(speaker_of(segment), float(segment["start"]), float(segment["end"]),
                (segment.get("text") or "").strip(), _mean(scores))
