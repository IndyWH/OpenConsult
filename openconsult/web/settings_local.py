"""The parts of the settings page that are about this computer alone
(spec 7.3; 15.13, the details of run 9c): the choice between its two
speech models. Under Transcription, where This computer is chosen:
Nemotron, or WhisperX with pyannote. Nemotron is the choice until the
doctor changes it (15.9, ruling 34). A model that is not installed, or
that the room check does not allow, is shown disabled with the reason
on the control (7.3, rule 1). The choice saves by itself (ruling 47),
is audited from what to what, takes effect at the next consultation,
and a consultation records the choice it ran with, as it always did."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields

router = APIRouter()
LOCAL_MODELS = (NEMOTRON, WHISPERX_PYANNOTE)


def cannot_choose(p, choice) -> str | None:
    """Why a speech model of this computer cannot be chosen, for the
    control itself: the room check's own sentence where the card has no
    room for the WhisperX choice; else that it is not installed, with
    the command as it stands (ruling 57)."""
    if choice is WHISPERX_PYANNOTE and not p.decisions.whisperx_choice.green:
        return p.decisions.whisperx_choice.sentence
    if not p.doors[choice.name].installed:
        return words.SPEECH_MODEL_NOT_INSTALLED.format(name=choice.name)
    return None


def speech_model_view(p) -> dict | None:
    """The choice as the page draws it, or None where it is not offered:
    the transcription runs in the cloud, or this machine can run no
    speech model of its own."""
    from openconsult.web.consult import local_model_in_use
    if p.stored.path(p.machine.case).speechmatics_live or p.machine.case != "suitable":
        return None
    in_use = local_model_in_use(p)
    return {"choices": [{"value": choice.name, "words": choice.title, "checked": choice.name == in_use, "reason": cannot_choose(p, choice),
                         "note": words.NEMOTRON_US_ENGLISH if choice is NEMOTRON else None} for choice in LOCAL_MODELS]}


def plain_size(size: int) -> str:
    """A size on the disk as a person reads it: GB with one decimal from
    1 GB up, else whole MB, in the units of 1000 a disk is sold by."""
    if size >= 10 ** 9:
        return f"{size / 10 ** 9:.1f} GB"
    if size >= 10 ** 6:
        return f"{size / 10 ** 6:.0f} MB"
    return words.LOCAL_LESS_THAN_1_MB


def local_models(p) -> list[dict]:
    """The section Local models (7.3; 15.13, ruling 57): each thing the app
    has installed in the data folder, with its size on the disk, and the
    language model as the engine chosen at start reports it. A list that
    is read: nothing in it can be pressed before the installers of stage
    15. The first view begins the measuring of the sizes and does not
    wait for it. A speech choice's environment is in the data folder; its
    models are in this computer's own cache of the hub, which the hub
    finds by itself, and are not counted here: the row says so."""
    from openconsult.guidelines import environment as guidelines_environment
    from openconsult.speech import environment as speech_environment
    folder = p.settings.data_folder
    things = [(choice.name, words.LOCAL_SPEECH_ROW.format(model=choice.title), p.doors[choice.name].installed,
               speech_environment.folder(folder, choice), words.LOCAL_MODELS_ELSEWHERE) for choice in LOCAL_MODELS]
    things.append(("guideline_search", words.LOCAL_GUIDELINE_ROW, guidelines_environment.installed(folder),
                   guidelines_environment.folder(folder), None))
    p.sizes.begin({name: where for name, _, installed, where, _ in things if installed})
    rows = []
    for name, title, installed, _, more in things:
        if not installed:
            line = words.LOCAL_NOT_INSTALLED
        else:
            size = p.sizes.of(name)
            line = words.LOCAL_MEASURING if size is None else words.LOCAL_INSTALLED.format(size=plain_size(size))
            line += f" {more}" if more else ""
        rows.append({"name": name, "title": title, "line": line})
    if p.machine.case == "suitable":
        decision = p.decisions.language_model
        line = (words.LOCAL_LANGUAGE_MODEL.format(model=words.PANEL_LOCAL_MODEL, engine=decision.fill["engine"], version=decision.fill["version"])
                if decision.green else decision.sentence)
        rows.append({"name": "language_model", "title": words.LOCAL_LANGUAGE_MODEL_ROW, "line": line})
    return rows


@router.post("/settings/speech-model")
async def save_speech_model(request: Request, user=Depends(guards.logged_in)):
    from openconsult.web import cloud, routes
    from openconsult.web.consult import local_model_in_use
    p = parts(request)
    fields = await form_fields(request)
    view = speech_model_view(p)
    if view is None:
        raise Redirect("/settings#transcription")           # not offered here: no such control
    picked = next((c for c in view["choices"] if c["value"] == fields.get("speech_model")), None)
    if picked is None:
        return routes._settings_page(request, user, ("save-speech-model", words.PICK_ONE))
    if picked["reason"]:
        return routes._settings_page(request, user, ("save-speech-model", picked["reason"]))
    p.stored.set_speech_model(picked["value"], was=local_model_in_use(p))
    raise Redirect(cloud._saved(fields, "speech-model", "transcription"))
