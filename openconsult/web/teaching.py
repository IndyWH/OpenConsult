"""The pages of teaching mode (spec 12; 15.14 and the details of run 10b;
R24): the one module of pages that teaching has. Its addresses are its
own, all under /teaching, and it reaches teaching through the one
object of openconsult/teaching/play.py. Every page is behind the login.

The name of a bank file and the id inside it name the diagnosis: a page
knows a case of the bank by its number alone. A page of a case is given
what may be shown at its step and nothing else of the scenario."""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.llm.choose import SHORT_WAIT_S
from openconsult.settings.path import CLAUDE
from openconsult.settings.statement import statement_for
from openconsult.teaching import feedback, room, words as t
from openconsult.teaching.cases import ANSWERS, EXAMINATION, FEEDBACK, HISTORY, LEVELS, QUESTIONS, WRITING
from openconsult.teaching.cases import DONE as DONE_STEP
from openconsult.teaching.play import DONE, REFUSED
from openconsult.teaching.scenario import examined_blocks, findings, other_findings, speaks_for
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
SETTINGS_STATEMENT = "/settings#cloud-statement"
# A page that waits for work the app does beside it asks again by itself, this often, with no script.
WAIT_ASKS_EVERY_S = 2
SURPRISE = "surprise"              # the value of Surprise me in the menu: no title of a topic
WAITS = "waits"                    # in the address of a waiting page's own ask: what the page waits for
GONE = "/teaching?gone=yes#your-cases"      # a press for a kept case that is no longer there: the list, which says so


def bank_rows(teaching) -> list[dict]:
    """The cases of the bank as the page lists them: number, topic, level and label, and nothing else of a file.
    press is the token of this row's press on this view of the page: the same press twice starts one case (R15)."""
    return [{"number": case.number, "name": t.CASE_NUMBER.format(n=case.number), "topic": case.topic,
             "level": t.LEVEL_NAMES[case.level], "label": t.LABELS[case.label], "press": secrets.token_urlsafe(12)}
            for case in teaching.bank.cases]


def cloud_lines() -> tuple[str, str]:
    """Under the mark Cloud on a teaching page (ruling 15): the owner's sentence, then the cost."""
    return t.CLOUD_TYPED, t.CLOUD_COST


def language_model(p) -> str:
    """The language model chosen in Settings, as for every job (the details: Which model answers)."""
    return p.stored.path(p.machine.case).language_model


def cannot_start(p) -> tuple[str, str | None] | None:
    """Why a case cannot start now, for the control that was pressed (R15;
    10.4), with the address where it is mended, or None when it can.
    This computer: no engine was fit at start, or the engine does not
    answer now. Claude: not connected; the statement of the path not
    ticked, or ticked before it held the line for teaching (rulings 7
    and 15); or its connection failing now. Nothing is ever tried on the
    other model."""
    path = p.stored.path(p.machine.case)
    if path.claude:
        if not p.connections.state(CLAUDE).has_key:
            return t.CANNOT_START_NOT_CONNECTED, "/connect/claude"
        if not p.stored.covers(statement_for(path)):
            return t.CANNOT_START_NO_TICK, SETTINGS_STATEMENT
        tested = p.connections.test(CLAUDE)
        if tested is not None and not tested.ok:
            return t.CANNOT_START.format(reason=tested.sentence), "/connect/claude"
    elif not p.decisions.start_offered:
        return t.CANNOT_START.format(reason=p.decisions.language_model.sentence), None
    elif not p.engine.status(p.door.profile.tag, SHORT_WAIT_S).running:
        return t.CANNOT_START_NO_ANSWER.format(engine=words.ENGINE_NAMES.get(p.engine.name, p.engine.name)), None
    return None


def levels_view(chosen: str) -> list[dict]:
    """The three levels, each with its line, and which one is picked."""
    return [{"value": name, "line": t.LEVEL_LINES[name], "chosen": name == chosen} for name in LEVELS]


def new_case_view(p, chosen: dict | None = None) -> dict:
    """The form of a new case: the 26 topics of the menu after Surprise me,
    and the three levels, each with its line; the level picked is the
    default of Settings, straightforward until it is changed (ruling 5).
    chosen: what a refused press had picked, kept as picked."""
    chosen = chosen or {}
    level = chosen.get("level") if chosen.get("level") in LEVELS else p.stored.teaching_level
    return {"topics": [{"title": topic, "chosen": topic == chosen.get("topic")} for topic in p.teaching.bank.topics],
            "levels": levels_view(level), "press": secrets.token_urlsafe(12)}


def _day(stamp: str) -> str:
    return words.plain_date(datetime.fromisoformat(stamp))


def flag_view(flag: dict) -> dict:
    return {"id": flag["id"], "date": _day(flag["flagged_at"]), "topic": flag["topic"], "level": t.LEVEL_NAMES[flag["level"]],
            "label": t.LABELS[flag["label"]], "note": flag["note"]}


def settings_view(p) -> dict:
    """The section Teaching of Settings (7.3; 15.13, ruling 55): the
    default level, and the cases a learner has flagged as wrong, each
    with the day it was flagged, its topic, its level, its label and the
    learner's note. No timer: it arrives with spoken teaching (ruling 6)."""
    return {"levels": levels_view(p.stored.teaching_level), "flags": [flag_view(flag) for flag in p.teaching.cases.flags()]}


def your_cases(teaching) -> list[dict]:
    """Every case begun on this computer, newest first (ruling 22): its
    date, its topic, its level, its label, whether it is finished, and
    the press that opens it or goes on with it where it stands."""
    rows = []
    for case in teaching.cases.listed():
        finished = case["step"] == DONE_STEP
        rows.append({"id": case["id"], "date": words.plain_date(datetime.fromisoformat(case["started_at"])), "topic": case["topic"],
                     "level": t.LEVEL_NAMES[case["level"]], "label": t.LABELS[case["label"]],
                     "state": t.FINISHED if finished else t.NOT_FINISHED, "press": t.OPEN if finished else t.GO_ON})
    return rows


def _teaching_page(request: Request, user, refused: tuple[str, str] | None = None, lead: str | None = None,
                   chosen: dict | None = None, asking: int | None = None, notice: str | None = None):
    """lead: where the reason of a refusal is mended, drawn as a link beside it.
    asking: the kept case whose delete has been pressed once: its row
    shows the one question, with what goes and that it cannot be undone."""
    p = parts(request)
    cases = your_cases(p.teaching)
    asked = request.query_params.get("asking", "")
    asking = int(asked) if asking is None and asked.isdigit() else asking
    for case in cases:
        if case["id"] == asking:
            case["question"] = t.DELETE_QUESTION.format(date=case["date"])
    if notice is None and not refused:
        said = {"deleted": t.CASE_DELETED, "gone": t.STALE}
        notice = next((words_ for name, words_ in said.items() if request.query_params.get(name) == "yes"), None)
    context = dict(user=user, active="teaching", t=t, bank=bank_rows(p.teaching), unread=t.bank_unread(p.teaching.bank.unread),
                   new_case=new_case_view(p, chosen), cases=cases, notice=notice,
                   mark=cloud_lines() if language_model(p) == CLAUDE else None, lead=lead, page_path="/teaching")
    if refused:
        return refuse(request, "teaching.html", refused[0], refused[1], **context)
    return render(request, "teaching.html", **context)


@router.get("/teaching")
async def teaching_page(request: Request, user=Depends(guards.logged_in)):
    """The teaching page, in the order of the details: the line of no
    affiliation, the line on a real patient's details, then the cases."""
    return _teaching_page(request, user)


@router.post("/teaching/cases")
async def start_case(request: Request, user=Depends(guards.logged_in)):
    """The press that starts a case: one of the bank, by its number, or a
    fresh one for a topic and a level. Where no model can be reached, or
    in cloud mode without the tick, it says so on the control and
    starts nothing."""
    p = parts(request)
    fields = await form_fields(request)
    if "topic" in fields:
        return await _start_fresh(request, user, p, fields)
    number = fields.get("number", "")
    case = p.teaching.bank.case(int(number)) if number.isdigit() else None
    if case is None:
        return _teaching_page(request, user, ("start-bank", t.NOT_IN_LIST))
    press = fields.get("press") or secrets.token_urlsafe(12)
    started = p.teaching.cases.by_press(press)
    if started is None:
        problem = await asyncio.to_thread(cannot_start, p)
        if problem is not None:
            return _teaching_page(request, user, (f"start-{case.number}", problem[0]), lead=problem[1])
        started = p.teaching.start_bank(case.number, press, language_model(p))
    raise Redirect(f"/teaching/cases/{started}")


async def _start_fresh(request: Request, user, p, fields: dict):
    """A fresh scenario for the topic and the level picked (ruling 10).
    Surprise me draws one of the 26 here, by chance. The case's row is
    made at once and the page of the case says that it is being written."""
    topic, level = fields.get("topic", ""), fields.get("level", "")
    chosen = {"topic": topic, "level": level}
    if topic != SURPRISE and topic not in p.teaching.bank.topics:
        return _teaching_page(request, user, ("start-fresh", t.PICK_A_TOPIC), chosen=chosen)
    if level not in LEVELS:
        return _teaching_page(request, user, ("start-fresh", t.PICK_A_LEVEL), chosen=chosen)
    press = fields.get("press") or secrets.token_urlsafe(12)
    started = p.teaching.cases.by_press(press)
    if started is None:
        problem = await asyncio.to_thread(cannot_start, p)
        if problem is not None:
            return _teaching_page(request, user, ("start-fresh", problem[0]), lead=problem[1], chosen=chosen)
        if topic == SURPRISE:
            topic = secrets.choice(p.teaching.bank.topics)
        started = p.teaching.start_fresh(topic, level, press, language_model(p))
    raise Redirect(f"/teaching/cases/{started}")


def case_view(row: dict) -> dict:
    """What every page of a case shows at its top: the case's name, its
    topic, its level and its label; and, once there is a scenario, the
    patient as presented: the name, the age and the sex, a parent who
    speaks for a child, and the opening words. Not the occupation and
    not the manner."""
    view = {"id": row["id"], "heading": t.CASE_NUMBER.format(n=row["bank_number"]) if row["source"] == "bank" else t.NEW_CASE,
            "topic": row["topic"], "level": t.LEVEL_NAMES[row["level"]], "label": t.LABELS[row["label"]]}
    scenario = row["scenario"]
    if scenario is None:
        return view
    patient, parent = scenario["patient"], speaks_for(scenario)
    return {**view, "presented": t.PRESENTED.format(name=patient["name"], age=patient["age"], sex=patient["sex"]),
            "speaks_for": t.SPEAKS_FOR.format(parent=parent) if parent else None, "opening_words": scenario["opening_words"]}


def turns_view(turns: list[dict]) -> list[dict]:
    """The history as the page shows it. The learner's lines carry the
    learner's own count, 1, 2, 3: the model's turn 2k-1 is the learner's
    line k, since a line is stored only with its reply. The patient's
    replies carry no number, and facts_used is never given to a page."""
    return [{"doctor": turn["speaker"] == "doctor", "line": (turn["n"] + 1) // 2, "text": turn["text"]} for turn in turns]


def questions_view(row: dict) -> dict:
    """The three questions as the page shows them (12.1, step 5): those
    answered, each with the learner's answer as typed, and the one that
    stands now, alone. The words of the questions are the page's own."""
    step, answers = row["step"], {name: row[f"answer_{name}"] for name in ANSWERS}
    asked = QUESTIONS.index(step) if step in QUESTIONS else len(QUESTIONS)
    view = {"answered": [{"question": t.QUESTIONS[i], "answer": answers[ANSWERS[i]]} for i in range(asked)]}
    if step in QUESTIONS:
        view["question"] = {"n": asked + 1, "words": t.QUESTIONS[asked], "of": t.QUESTION_OF.format(n=asked + 1)}
    return view


def _case_page(request: Request, user, case_id: int, refused: tuple[str, str] | None = None, typed: dict | None = None,
               notice: str | None = None):
    """The case where it stands: one address for every step, and the row's
    step decides what is shown. typed: words that were sent with a press
    and not stored, put back into their box. The mark Cloud stands on it
    while its own language model is Claude, whatever Settings says by now."""
    teaching = parts(request).teaching
    row = teaching.cases.get(case_id)
    if row is None:
        raise Redirect("/teaching")
    turns = teaching.cases.turns(case_id)
    view = {**case_view(row), "step": row["step"], "turns": turns_view(turns), "next_line": len(turns) // 2 + 1}
    if row["step"] == HISTORY and room.getting_long(row["scenario"], [(turn["speaker"], turn["text"]) for turn in turns]):
        view["long"] = t.HISTORY_LONG
    if row["step"] not in (WRITING, HISTORY):
        examined = teaching.cases.examined(case_id)
        view.update(examined=examined_blocks(row["scenario"], examined), next_request=len(examined) + 1)
        if row["step"] != EXAMINATION:
            # The rest of the scenario's findings reach the page only once the examination is finished (D10).
            view.update(no_findings=not findings(row["scenario"]), other_findings=other_findings(row["scenario"], examined))
            view.update(questions_view(row))
    if row["step"] in (WRITING, FEEDBACK):
        # Being made beside the page, which asks again by itself; or it did not come, and one press makes it again.
        view["making"] = teaching.making(case_id)
        if not view["making"]:
            sentence = t.CASE_NOT_WRITTEN if row["step"] == WRITING else t.FEEDBACK_FAILED
            view["write_failed" if row["step"] == WRITING else "feedback_failed"] = sentence.format(reason=t.reason(row["failure"] or t.STOPPED))
    if row["step"] == DONE_STEP:
        # Built from the stored answer by the rule, at every view; no model is asked again (ruling 22).
        view["feedback"] = feedback.built(row["scenario"], [(turn["speaker"], turn["text"]) for turn in turns],
                                          teaching.cases.answers(row), row["feedback"])
        view["flag"] = teaching.cases.flag_of(case_id)
        if request.query_params.get("whole") == "yes":
            # The whole scenario, by one press, and only now that the feedback has been made (ruling 8).
            view["whole"] = row["scenario"]
    # The mark stands on a case until its feedback has been made: after it nothing typed there goes to Claude
    # (the owner's okay of 25 Nov 2026).
    in_cloud = row["language_model"] == CLAUDE and row["step"] != DONE_STEP
    context = dict(user=user, active="teaching", t=t, case=view, typed=typed or {}, notice=notice, line_most=room.LINE_MOST,
                   answer_most=room.ANSWER_MOST, mark=cloud_lines() if in_cloud else None,
                   page_path=f"/teaching/cases/{case_id}", timed_by_script=True, refresh_every=WAIT_ASKS_EVERY_S if view.get("making") else None,
                   # A page that waits for its feedback asks again at an address with no # part: an address with one,
                   # asked a second time, is a place inside the page the browser has, and it loads nothing (the owner's
                   # room check of 25 Nov 2026: the feedback was made and the page went on saying that it was being
                   # made). The address says that it is the wait's own ask, so that the app can send the browser on to
                   # the feedback when it has come (case_page).
                   refresh_to=f"/teaching/cases/{case_id}?quiet&{WAITS}={FEEDBACK}" if row["step"] == FEEDBACK else None)
    if refused:
        return refuse(request, "teaching_case.html", refused[0], refused[1], **context)
    return render(request, "teaching_case.html", **context)


def _stale(request: Request, user, case_id: int, box_step: str, box: str, text: str):
    """A press from a page that was no longer up to date: nothing was
    stored, and the page comes back where the case stands and says so
    (R15). What was typed goes back into its box; where that box is no
    longer on the page, the words are said beside the notice."""
    row = parts(request).teaching.cases.get(case_id)
    same_box = row is not None and row["step"] == box_step
    lost = text.strip() and not same_box
    return _case_page(request, user, case_id, typed={box: text} if same_box else None,
                      notice=t.STALE + (" " + t.STALE_TYPED.format(text=text.strip()) if lost else ""))


@router.get("/teaching/cases/{case_id}")
async def case_page(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """The case where it stands. Where this is the own ask of a page that
    waits for its feedback, and the wait is over, the browser is sent on
    to the place of the page that shows what came: the feedback, or the
    sentence that it did not come with its press. So a learner who left
    the page alone is looking at the feedback when it is there."""
    if request.query_params.get(WAITS) == FEEDBACK:
        teaching = parts(request).teaching
        row = teaching.cases.get(case_id)
        if row is not None and row["step"] == DONE_STEP:
            raise Redirect(f"/teaching/cases/{case_id}#feedback")
        if row is not None and row["step"] == FEEDBACK and not teaching.making(case_id):
            raise Redirect(f"/teaching/cases/{case_id}#feedback-failed")
    return _case_page(request, user, case_id)


def _number(fields: dict, name: str) -> int:
    return int(fields[name]) if fields.get(name, "").isdigit() else 0


@router.post("/teaching/cases/{case_id}/say")
async def say(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """A line of the history, with the number it will get. Stored with the
    patient's reply, or not at all: a refusal comes back on the Send
    control with the line still in its box."""
    fields = await form_fields(request)
    text = fields.get("text", "")
    outcome = await asyncio.to_thread(parts(request).teaching.say, case_id, _number(fields, "line"), text)
    if outcome.state == DONE:
        # To the page with no place named: the box of the next line asks for the keyboard itself, and a browser gives
        # it, and brings it into the window, only where the address names no other place (seen with scripts off).
        raise Redirect(f"/teaching/cases/{case_id}")
    if outcome.state == REFUSED:
        return _case_page(request, user, case_id, refused=("say-send", outcome.problem), typed={"say": text})
    return _stale(request, user, case_id, HISTORY, "say", text)


@router.post("/teaching/cases/{case_id}/end-history")
async def end_history(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """End the history: one press, no way back. The box travels with the
    press, so a line typed and not sent refuses it."""
    text = (await form_fields(request)).get("text", "")
    outcome = parts(request).teaching.end_history(case_id, text)
    if outcome.state == DONE:
        raise Redirect(f"/teaching/cases/{case_id}")
    if outcome.state == REFUSED:
        return _case_page(request, user, case_id, refused=("end-history", outcome.problem), typed={"say": text})
    return _stale(request, user, case_id, HISTORY, "say", text)


@router.post("/teaching/cases/{case_id}/examine")
async def examine(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """What the learner would examine, with the number the request will
    get. The page then shows the scenario's own findings for it."""
    fields = await form_fields(request)
    text = fields.get("text", "")
    outcome = await asyncio.to_thread(parts(request).teaching.examine, case_id, _number(fields, "n"), text)
    if outcome.state == DONE:
        raise Redirect(f"/teaching/cases/{case_id}")
    if outcome.state == REFUSED:
        return _case_page(request, user, case_id, refused=("examine-send", outcome.problem), typed={"examine": text})
    return _stale(request, user, case_id, EXAMINATION, "examine", text)


@router.post("/teaching/cases/{case_id}/finish-examination")
async def finish_examination(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """Finish the examination: one press. The rest of the findings are shown and the first question comes."""
    text = (await form_fields(request)).get("text", "")
    outcome = parts(request).teaching.finish_examination(case_id, text)
    if outcome.state == DONE:
        raise Redirect(f"/teaching/cases/{case_id}")       # the box of the first question takes the keyboard
    if outcome.state == REFUSED:
        return _case_page(request, user, case_id, refused=("finish-examination", outcome.problem), typed={"examine": text})
    return _stale(request, user, case_id, EXAMINATION, "examine", text)


@router.post("/teaching/cases/{case_id}/answer")
async def answer(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """The answer to the question that stands, by its number. An empty
    answer is not taken. After the third the feedback is made, once."""
    fields = await form_fields(request)
    text, question = fields.get("text", ""), _number(fields, "question")
    outcome = parts(request).teaching.answer(case_id, question, text)
    if outcome.state == DONE:
        # The next question's box takes the keyboard; after the third there is no box, and the page comes back at the
        # questions, where it says that the feedback is being made.
        raise Redirect(f"/teaching/cases/{case_id}" + ("#questions" if question == len(QUESTIONS) else ""))
    if outcome.state == REFUSED:
        return _case_page(request, user, case_id, refused=("answer-send", outcome.problem), typed={"answer": text})
    return _stale(request, user, case_id, QUESTIONS[question - 1] if 1 <= question <= len(QUESTIONS) else "", "answer", text)


@router.post("/teaching/cases/{case_id}/flag")
async def flag_case(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """Flag this case as wrong (12.3, rule 7), after its feedback, with a
    note that may be left empty. The flag is kept with the scenario and
    listed in Settings."""
    note = (await form_fields(request)).get("note", "")
    outcome = parts(request).teaching.flag(case_id, note)
    if outcome.state == DONE:
        raise Redirect(f"/teaching/cases/{case_id}#after-feedback")
    if outcome.state == REFUSED:
        return _case_page(request, user, case_id, refused=("flag", outcome.problem), typed={"flag": note})
    return _case_page(request, user, case_id, notice=t.STALE)


@router.post("/teaching/cases/{case_id}/delete")
async def delete_case(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """Delete a kept case (ruling 22): the question once, at its row, then
    the deletion: the case with every line, reply, finding shown, answer
    and feedback, and every stored model call of it, in one go.

    The question must stand where the learner is looking (R15; 15.10,
    ruling 34; the owner's room check of 25 Nov 2026, where the page
    went to its top and the question was out of sight). So the first
    press leads to the teaching page at that row: with no script by the
    row's own place in the address; with the page's script, which keeps
    the window where it was, by no place at all."""
    teaching = parts(request).teaching
    fields = await form_fields(request)
    if teaching.cases.get(case_id) is None:
        raise Redirect(GONE)
    if fields.get("confirm") != "yes":
        raise Redirect(f"/teaching?asking={case_id}" + ("" if fields.get("place") == "keep" else f"#kept-{case_id}"))
    outcome = await asyncio.to_thread(teaching.delete, case_id)
    if outcome.state == REFUSED:
        return _teaching_page(request, user, refused=(f"delete-{case_id}", outcome.problem))
    raise Redirect("/teaching?deleted=yes#your-cases" if outcome.state == DONE else GONE)


@router.get("/teaching/flags/{flag_id}")
async def flag_page(request: Request, flag_id: int, user=Depends(guards.logged_in)):
    """A flagged case, from Settings: its facts, the learner's note, and
    the scenario as it stood when the case was played, whole."""
    flag = parts(request).teaching.cases.flag_row(flag_id)
    if flag is None:
        raise Redirect("/settings#teaching")
    parent = speaks_for(flag["scenario"])
    view = {**flag_view(flag), "scenario": flag["scenario"], "speaks_for": t.SPEAKS_FOR.format(parent=parent) if parent else None}
    return render(request, "teaching_flag.html", user=user, active="settings", t=t, flag=view)


@router.post("/teaching/flags/{flag_id}/remove")
async def remove_flag(request: Request, flag_id: int, user=Depends(guards.logged_in)):
    """Remove the flag, in Settings: the flag goes, with its copy of the scenario and its note."""
    removed = parts(request).teaching.remove_flag(flag_id)
    raise Redirect("/settings?done=flag-removed#teaching" if removed else "/settings#teaching")


@router.post("/settings/teaching-level")
async def save_level(request: Request, user=Depends(guards.logged_in)):
    """The default level of a new case. A choice in Settings saves by
    itself (15.13, ruling 47): the page's script sends this form when the
    choice changes; with no script its Save does. Audited from what to what."""
    from openconsult.web import routes
    p = parts(request)
    fields = await form_fields(request)
    if fields.get("level") not in LEVELS:
        return routes._settings_page(request, user, ("save-teaching-level", t.PICK_A_LEVEL))
    p.stored.set_teaching_level(fields["level"])
    raise Redirect("/settings?done=teaching-level" + ("" if fields.get("place") == "keep" else "#teaching"))


@router.post("/teaching/cases/{case_id}/again")
async def again(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """Make again what did not come, by this press alone: nothing is asked a second time by itself (R30)."""
    outcome = parts(request).teaching.again(case_id)
    if outcome.state == DONE:
        raise Redirect(f"/teaching/cases/{case_id}#questions")
    return _stale(request, user, case_id, "", "", "")
