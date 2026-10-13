"""The decisions of the start (spec 15.8, rulings 36 and 38). Each is a
named element with a state, green or red, a reason that names a sentence
in the file of words, and its figures. They are kept in the app's state
for the run, written once to the audit log with their figures, and shown
on This machine as sentences with no figures. Nothing is drawn: the
panel of stage 9 reads the same elements.
"""

from __future__ import annotations

from dataclasses import dataclass

from openconsult import words
from openconsult.llm.choose import Choice

LANGUAGE_MODEL, GUIDELINE_SEARCH, WHISPERX_CHOICE = "language_model", "guideline_search", "whisperx_choice"


@dataclass(frozen=True)
class Element:
    name: str
    green: bool
    reason: str        # a key of words.REASONS
    fill: dict         # what the sentence is filled with (names and versions, never figures in MiB)
    figures: dict      # for the audit log and the record

    @property
    def sentence(self) -> str:
        return words.REASONS[self.reason].format(**self.fill)

    @property
    def audit_detail(self) -> str:
        shown = ", ".join(f"{key} {value}" for key, value in self.figures.items())
        return f"{self.sentence} Figures: {shown}."


@dataclass(frozen=True)
class Decisions:
    elements: dict

    @property
    def language_model(self) -> Element:
        return self.elements[LANGUAGE_MODEL]

    @property
    def start_offered(self) -> bool:
        """Ruling 37: with no engine fit, Start is not offered. In 3c there is
        no Start control; the element records it for stage 6."""
        return self.language_model.green


def language_model_element(choice: Choice, profile_tag: str | None) -> Element:
    """Green with the engine and its version; the fallback's reason when
    the first engine was passed over; red when none is fit."""
    figures = {"engine": choice.name or "none"}
    for t in choice.tried:
        figures[f"{t.name} asked at"] = t.address
        figures[f"{t.name} answer"] = _said(t)
    chosen = choice.chosen
    if chosen is None:
        why = "; ".join(_why(t) for t in choice.tried) or words.NONE_ASKED
        return Element(LANGUAGE_MODEL, False, "engine_none", {"why": why}, figures)
    figures.update({"version": chosen.status.version, "tag": profile_tag,
                    "digest": chosen.status.digest, "context": chosen.status.context})
    fill = {"engine": words.ENGINE_NAMES[chosen.name], "version": chosen.status.version,
            "model": words.MODEL_PRESENT}
    earlier = [t for t in choice.tried if t.unfit is not None]
    if earlier:
        fill["reason"] = "; ".join(_why(t) for t in earlier)
        return Element(LANGUAGE_MODEL, True, "engine_fallback", fill, figures)
    return Element(LANGUAGE_MODEL, True, "engine_running", fill, figures)


def _why(tried) -> str:
    return words.UNFIT[tried.unfit].format(engine=words.ENGINE_NAMES[tried.name])


def _said(tried) -> str:
    s = tried.status
    if not s.running:
        return "did not answer"
    model = "model present" if s.model_present else "model absent"
    return f"version {s.version}, {model}, context {s.context if s.context is not None else 'set by the call'}"
