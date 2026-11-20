"""The control panel of This machine (spec 15.13, rulings 6 and 56 and the
details of run 9c; 15.8, ruling 38; R15). One picture, made here by one
piece of code from what the app holds, shown at step 2 of the first run
and at the top of Settings: four columns from left to right, Microphone,
Transcription, Language model, Consultation; in each of the two middle
columns one box for this computer and one for the cloud service.

Each box is an element in the shape 3c gave a decision: a name, a state,
a reason that names a sentence in the file of words, and its figures
for the audit log. Three states, told by a sign and a word as well as
by colour: ready, not set up, cannot run here. The path the doctor
chose is marked; nothing here chooses or switches a path (10.4).

Nothing is asked for a view of the picture: no connection is tested, no
engine asked, no worker started. A box says when the test it rests on
was made, and never a time the app does not have. What a cloud box says
goes to its service is what goes on the path as chosen, and nothing
else: a line shows only when it is true (ruling 5)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from openconsult import words
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import AFTER_STOP, LIVE, NOTHING, goes_sentence, goes_to, where_lines  # noqa: F401 - goes_to is read from here too
from openconsult.speech.choices import CHOICES, WHISPERX_PYANNOTE

READY, NOT_SET_UP, CANNOT_RUN = "ready", "not_set_up", "cannot_run"
MICROPHONE, SPEECH_LOCAL, SPEECHMATICS_BOX, MODEL_LOCAL, CLAUDE_BOX, CONSULTATION = (
    "microphone", "speech_local", "speechmatics", "model_local", "claude", "consultation")
CONNECT, TEST, CHOOSE = "connect", "test", "choose"
DURING = "during"                   # a solid line, of the consultation; a dashed one is AFTER_STOP, as what goes to a service is


@dataclass(frozen=True)
class Action:
    kind: str                       # connect, test or choose: the one action of a box
    address: str
    fields: tuple = ()              # a press sends these to the address; none: a link


@dataclass(frozen=True)
class Box:
    name: str
    column: str
    row: int                        # 0: this computer, or the column's one box; 1: the cloud service
    state: str
    reason: str                     # a key of words.PANEL_REASONS
    fill: dict = field(default_factory=dict)
    figures: dict = field(default_factory=dict)
    model: str | None = None        # the model the box would run, named inside it
    cloud: bool = False
    on_path: bool = False           # on the path the doctor chose: the heavier border
    chosen: bool = False            # one of the two choices of the path: the word Chosen
    also: str | None = None         # Used after Stop
    when: tuple = ()                # when each test it rests on was made
    goes: str | None = None         # a cloud box: what goes to its service on the path as chosen
    action: Action | None = None
    link: tuple | None = None       # the Consultation box: where its reason is mended
    note: str | None = None         # the first run: where a path is chosen

    @property
    def title(self) -> str:
        return words.PANEL_BOXES[self.name]

    @property
    def state_words(self) -> str:
        """The state in words, for the box's face. The Consultation box,
        ready, says what it is ready for, as the Start control would."""
        if self.name == CONSULTATION and self.state == READY:
            return words.PANEL_READY_TO_START
        return words.PANEL_STATES[self.state]

    @property
    def sign(self) -> str:
        return words.PANEL_SIGNS[self.state]

    @property
    def sentence(self) -> str:
        return words.PANEL_REASONS[self.reason].format(**self.fill)

    @property
    def audit_detail(self) -> str:
        shown = ", ".join(f"{key} {value}" for key, value in self.figures.items())
        return f"{words.PANEL_STATES[self.state]}. {self.sentence}" + (f" Figures: {shown}." if shown else "")


@dataclass(frozen=True)
class Arrow:
    """A line from the edge of one box to the edge of the next, with a
    head at its end (the owner's ruling of 20 Nov 2026): solid for what
    happens during the consultation, dashed for what happens after Stop."""
    start: str                      # the box it leaves
    end: str                        # the box its head touches
    kind: str                       # during or after_stop
    gutter: int                     # 1: after Microphone; 2: after Transcription; 3: after Language model
    from_row: int
    to_row: int

    @property
    def shape(self) -> str:
        """How it runs between two columns side by side: straight, or by a
        corner down to the cloud row or up from it."""
        return "straight" if self.from_row == self.to_row else "down" if self.from_row < self.to_row else "up"


@dataclass(frozen=True)
class Panel:
    boxes: tuple
    arrows: tuple
    path_lines: tuple               # above the picture: what runs here and what in the cloud on the path chosen

    def box(self, name: str) -> Box:
        return next(box for box in self.boxes if box.name == name)

    @property
    def columns(self) -> list[dict]:
        """The columns in the order of the path, each with its boxes: the
        order a screen reader meets them in."""
        return [{"name": name, "title": words.PANEL_COLUMNS[name], "n": n, "boxes": [box for box in self.boxes if box.column == name]}
                for n, name in enumerate(words.PANEL_COLUMNS, start=1)]

    @property
    def after_stop(self) -> bool:
        """Whether a dashed line is drawn: the recording goes after Stop."""
        return any(arrow.kind == AFTER_STOP for arrow in self.arrows)

    @property
    def key(self) -> tuple:
        """Under the picture: a sample of each kind of line that is drawn,
        with its words. The dashed part only where a dashed line is."""
        return tuple((kind, words.PANEL_KEY[kind]) for kind in ((DURING, AFTER_STOP) if self.after_stop else (DURING,)))


def arrows_of(path: ChosenPath, boxes: tuple) -> tuple:
    """The lines of the path chosen (the owner's ruling of 20 Nov 2026).
    During the consultation: the microphone, the transcription box
    chosen, the language model box chosen, the consultation. After Stop,
    where the tick for better accuracy counts: the recording from the
    microphone to Speechmatics, and its transcript from there to the
    language model chosen, which drafts the note from it. A box that is
    not on the path has no line."""
    by_name = {box.name: box for box in boxes}
    speech = SPEECHMATICS_BOX if path.speechmatics_live else SPEECH_LOCAL
    model = CLAUDE_BOX if path.claude else MODEL_LOCAL
    steps = [(MICROPHONE, speech, DURING), (speech, model, DURING), (model, CONSULTATION, DURING)]
    if path.recording_after_stop:
        steps += [(MICROPHONE, SPEECHMATICS_BOX, AFTER_STOP), (SPEECHMATICS_BOX, model, AFTER_STOP)]
    columns = list(words.PANEL_COLUMNS)
    return tuple(Arrow(start, end, kind, columns.index(by_name[start].column) + 1, by_name[start].row, by_name[end].row)
                 for start, end, kind in steps)


def _when(stamp) -> tuple[str, str]:
    at = datetime.fromisoformat(stamp) if isinstance(stamp, str) else stamp
    return f"{at.day} {at:%b %Y}", f"{at:%H:%M}"


def microphone_box(p) -> Box:
    done = p.first_run.done_at("microphone")
    if done is None:
        return Box(MICROPHONE, "microphone", 0, NOT_SET_UP, "mic_not_tested", figures={"tested": "no"}, on_path=True,
                   action=Action(TEST, "/first-run/microphone"))
    date, time = _when(done)
    return Box(MICROPHONE, "microphone", 0, READY, "mic_tested", {"date": date, "time": time}, {"tested": done}, on_path=True,
               when=(words.PANEL_TESTED_ON.format(date=date, time=time),), action=Action(TEST, "/first-run/microphone"))


def speech_local_box(p, path: ChosenPath, first_run: bool) -> Box:
    from openconsult.web.consult import local_model_in_use
    name = local_model_in_use(p)
    choice = CHOICES[name]
    chosen = path.transcription == THIS_COMPUTER
    common = dict(model=choice.title, on_path=chosen, chosen=chosen)
    figures = {"model": name, "installed": "yes" if p.doors[name].installed else "no"}
    if p.machine.case != "suitable":
        return Box(SPEECH_LOCAL, "transcription", 0, CANNOT_RUN, "as_said", {"sentence": p.machine.sentence}, {"machine": p.machine.case}, **common)
    if choice is WHISPERX_PYANNOTE and not p.decisions.whisperx_choice.green:
        return Box(SPEECH_LOCAL, "transcription", 0, CANNOT_RUN, "as_said", {"sentence": p.decisions.whisperx_choice.sentence}, figures, **common)
    if not p.doors[name].installed:
        return Box(SPEECH_LOCAL, "transcription", 0, NOT_SET_UP, "speech_not_installed", {"model": choice.title, "name": name}, figures, **common)
    last = p.self_tests.last(name)
    test = Action(TEST, "/first-run/self-test")
    if last is None:
        return Box(SPEECH_LOCAL, "transcription", 0, NOT_SET_UP, "speech_no_self_test", {"model": choice.title},
                   {**figures, "self-test": "not run"}, action=test, **common)
    date, time = _when(last["at"])
    if not last["passed"]:
        fill = {"model": choice.title, "date": date, "time": time, "reason": last["detail"].get("reason") or ""}
        return Box(SPEECH_LOCAL, "transcription", 0, NOT_SET_UP, "speech_self_test_failed", fill,
                   {**figures, "self-test": f"failed {last['at']}"}, action=test, **common)
    return Box(SPEECH_LOCAL, "transcription", 0, READY, "speech_ready", {"model": choice.title, "date": date, "time": time},
               {**figures, "self-test": last["at"]}, when=(words.PANEL_TESTED_ON.format(date=date, time=time),),
               action=test if chosen or first_run else Action(CHOOSE, "/settings/path/transcription", (("transcription", THIS_COMPUTER),)), **common)


def model_local_box(p, path: ChosenPath, first_run: bool) -> Box:
    chosen = path.language_model == THIS_COMPUTER
    common = dict(model=words.PANEL_LOCAL_MODEL, on_path=chosen, chosen=chosen)
    if p.machine.case != "suitable":
        return Box(MODEL_LOCAL, "language_model", 0, CANNOT_RUN, "as_said", {"sentence": p.machine.sentence}, {"machine": p.machine.case}, **common)
    decision = p.decisions.language_model
    if not decision.green:
        return Box(MODEL_LOCAL, "language_model", 0, NOT_SET_UP, "engine_not_set_up", {"sentence": decision.sentence}, decision.figures, **common)
    choose = Action(CHOOSE, "/settings/path/language-model", (("language_model", THIS_COMPUTER),))
    return Box(MODEL_LOCAL, "language_model", 0, READY, "as_said", {"sentence": decision.sentence}, decision.figures,
               when=(words.PANEL_ENGINE_ASKED,), action=None if chosen or first_run else choose, **common)


def cloud_box(p, path: ChosenPath, service: str, first_run: bool) -> Box:
    """A cloud service: ready when it is connected and its last test
    passed, or its key is from the secure store, where it passed its
    test when it was saved, and was not tested since the start, which
    the box then says on its face; not set up with no key, or with a key
    that never passed a test; cannot run with the reason when its last
    test failed."""
    state = p.connections.state(service)
    title, kind = words.SERVICE_TITLES[service], words.PANEL_KINDS[service]
    name, column = (CLAUDE_BOX, "language_model") if service == CLAUDE else (SPEECHMATICS_BOX, "transcription")
    field_name, which = ("language_model", "language-model") if service == CLAUDE else ("transcription", "transcription")
    chosen = (path.claude if service == CLAUDE else path.speechmatics_live)
    goes = goes_to(path, service)
    common = dict(model=words.PANEL_CLAUDE_MODEL if service == CLAUDE else None, cloud=True, on_path=chosen, chosen=chosen,
                  # What goes to it on the path chosen: the owner's sentence, from the one function that also makes
                  # the notice of a path that sends less (ruling 48; his words of 18 Nov 2026).
                  also=words.PANEL_USED_AFTER_STOP if goes == AFTER_STOP else None, goes=goes_sentence(path, service))
    figures = {"key": state.where or "none", "last test": "none" if state.last is None else "passed" if state.last.ok else state.last.reason}
    connect = Action(CONNECT, f"/connect/{service}")
    test = Action(TEST, f"/connect/{service}", (("key", ""),))             # the connect screen's own test of the key in use
    fill = {"service": title, "kind": kind}
    if not state.has_key:
        return Box(name, column, 1, NOT_SET_UP, "cloud_not_connected", fill, figures, when=(words.NOT_CONNECTED,), action=connect, **common)
    if state.last is not None and not state.last.ok:
        failed = words.MACHINE_TEST_FAILED.format(time=f"{state.last_at:%H:%M}", reason=state.last.sentence)
        return Box(name, column, 1, CANNOT_RUN, "cloud_test_failed", fill, figures, when=(failed,), action=test, **common)
    if not state.connected:
        return Box(name, column, 1, NOT_SET_UP, "cloud_not_tested", fill, figures, when=(words.NOT_TESTED_YET,), action=test, **common)
    when = words.MACHINE_CONNECTED.format(time=f"{state.last_at:%H:%M}") if state.last is not None else words.NOT_TESTED_YET
    choose = Action(CHOOSE, f"/settings/path/{which}", ((field_name, service),))
    return Box(name, column, 1, READY, "cloud_ready", fill, figures, when=(when,), action=test if chosen or first_run else choose, **common)


def consultation_box(p, path: ChosenPath) -> Box:
    """Ready to start, or the first reason, by the same function as the
    Start control, from what the app holds at this moment. It rests only
    on tests that were made: where the path needs a service that was not
    tested since the start, the box says that and is not ready."""
    from openconsult.web.consult import start_state
    state = start_state(p, ask_engine=False)
    when = [words.PANEL_SERVICE_TESTED.format(service=words.SERVICE_TITLES[service], time=f"{p.connections.state(service).last_at:%H:%M}")
            for service in path.needed_while_it_runs if p.connections.state(service).last is not None]
    if not path.claude and p.machine.case == "suitable":
        when.insert(0, words.PANEL_ENGINE_ASKED)
    common = dict(on_path=True, when=tuple(when))
    if state.problem:
        return Box(CONSULTATION, "consultation", 0, NOT_SET_UP if state.lead else CANNOT_RUN, "as_said", {"sentence": state.problem},
                   {"start": "not offered"}, link=state.lead, **common)
    untested = next((service for service in path.needed_while_it_runs if p.connections.state(service).last is None), None)
    if untested is not None:
        return Box(CONSULTATION, "consultation", 0, NOT_SET_UP, "consultation_not_tested", {"service": words.SERVICE_TITLES[untested]},
                   {"start": f"{untested} not tested since the start"}, link=(f"/connect/{untested}", words.SERVICE_TITLES[untested]), **common)
    return Box(CONSULTATION, "consultation", 0, READY, "consultation_ready", {}, {"start": "offered"}, **common)


def record_at_start(p) -> None:
    """The boxes as they stand when the app starts, written once to the
    audit log, each with its state, its sentence and its figures, as the
    decisions of the start are (15.8, ruling 38). What changes a box
    afterwards has an audit line of its own: a test of a connection, a
    key kept or removed, the microphone test, a self-test, a setting."""
    for box in build(p).boxes:
        p.audit.record(f"panel.{box.name}", box.audit_detail)


def build(p, first_run: bool = False) -> Panel:
    """The picture as it stands now. first_run: step 2 of the first run,
    where there is no user yet and so no change of path: no box offers
    Choose there."""
    path = p.stored.path(p.machine.case)
    boxes = (microphone_box(p), speech_local_box(p, path, first_run), cloud_box(p, path, SPEECHMATICS, first_run),
             model_local_box(p, path, first_run), cloud_box(p, path, CLAUDE, first_run), consultation_box(p, path))
    if first_run:
        boxes = tuple(replace(box, note=words.PANEL_CHOOSE_IN_SETTINGS) if box.state == READY and not box.on_path else box for box in boxes)
    # Above the picture, in the owner's shape (his word of 18 Nov 2026, 08:03): what runs on this computer and what in
    # the cloud on the path chosen, from the function the notice of a path that sends less reads.
    return Panel(boxes, arrows_of(path, boxes), where_lines(path))
