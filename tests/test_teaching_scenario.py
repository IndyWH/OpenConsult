"""The whole scenario after the feedback, and nothing of it before (spec
12.3; 15.14, ruling 8 and the details of run 10b: After the feedback).
A made scenario whose second part holds words found nowhere in its
first, and whose first part holds facts the made patient never says:
whatever of either reaches a page before the feedback is found by its
words. No model is asked for real."""

import re

from openconsult.llm.engine import EngineTimeout
from openconsult.teaching import frames
from tests import made_teaching
from tests.conftest import text_of
from tests.test_teaching_feedback import ANSWER, words_in
from tests.test_teaching_frames import said_in, words_of
from tests.test_teaching_questions import answer, at_the_questions

SCENARIO = made_teaching.SCENARIO
PART_TWO = {key: value for key, value in SCENARIO.items() if key not in frames.PART_ONE}
# The examiner's side by its words (each begins with q or z and stands nowhere in the first part), less the one
# finding the made learner asks for and is rightly shown, and less none, the form's own word for a step of the
# plan with no urgency, which is no word of a scenario and stands in every style sheet.
EXAMINER_WORDS = words_of(said_in(PART_TWO)) - {"qexamone", "qfindone", "none"}
# The patient's side beyond the name, the age, the sex and the opening words: never said by the made patient.
UNSAID = ("made-up day", "made-up fever", "made-up strain", "made-up work", "made-up note", "tester", "Speaks plainly")


def nothing_of_the_scenario_in(found: str) -> list[str]:
    """Every word of the examiner's side and every unsaid word of the patient's side that a text holds."""
    low = found.lower()
    return sorted(word for word in EXAMINER_WORDS if word in words_of(low)) + [words for words in UNSAID if words.lower() in low]


def everything_served(client, case: int = 1) -> str:
    """The page of a case, with and without the press for the whole scenario asked of it, and the script and the
    style sheet it names: every byte a browser is given for the case, attributes and addresses included."""
    found = []
    for address in (f"/teaching/cases/{case}", f"/teaching/cases/{case}?whole=yes", f"/teaching/cases/{case}?quiet", "/teaching"):
        answered = client.get(address)
        found += [address, answered.text, repr(dict(answered.headers))]
        for static in re.findall(r'"(/static/teaching[^"]+)"', answered.text):
            found += [static, client.get(static).text]
    return "\n".join(found)


def test_15_14_until_the_feedback_nothing_of_the_examiners_side_and_nothing_unsaid_of_the_patients_is_in_any_page_script_or_address(
        tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [EngineTimeout("made-up: no answer"), ANSWER], held=True)
    cases = app.state.parts.teaching.cases
    # At the questions, with a history, an examination request and its one finding shown, and the rest after Finish.
    served = everything_served(client)
    assert "A made-up line." in served and "Qexamone: qfindone" in served               # what was said and what was asked for is there
    # Finish the examination shows the scenario's other findings, as D10 has it: those words are on the page by then.
    finish_shows = {"qexamtwo", "qfindtwo", "qtestone", "qresultone"}
    assert set(nothing_of_the_scenario_in(served)) == finish_shows
    for question in (1, 2):
        answer(client, question, "A made-up answer.")
        assert set(nothing_of_the_scenario_in(everything_served(client))) == finish_shows
    answer(client, 3, "A made-up answer.")
    # While the feedback is being made, and when it did not come: still nothing more.
    assert cases.get(1)["step"] == "feedback" and set(nothing_of_the_scenario_in(everything_served(client))) == finish_shows
    works.pop()()                                                                      # the made engine does not answer
    assert cases.get(1)["failure"] == "too_slow" and set(nothing_of_the_scenario_in(everything_served(client))) == finish_shows
    assert 'id="show-scenario"' not in client.get("/teaching/cases/1").text and 'id="whole-scenario"' not in client.get("/teaching/cases/1?whole=yes").text


def test_15_14_in_the_history_and_in_the_examination_before_finish_the_page_holds_no_finding_that_was_not_asked_for(tmp_path, clock, machine):
    from tests.test_teaching_examination import came, examining
    app, client, engine = examining(tmp_path, clock, machine, [came(asked=[1])])
    assert nothing_of_the_scenario_in(everything_served(client)) == []                 # the history just ended: nothing at all
    client.post("/teaching/cases/1/examine", data={"n": "1", "text": "Made-up one."})
    served = everything_served(client)
    assert "Qexamone: qfindone" in served and nothing_of_the_scenario_in(served) == []  # the one finding asked for, and no other


def test_15_14_ruling_8_after_the_feedback_one_press_shows_the_whole_scenario_both_parts_in_its_own_words(tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [ANSWER])
    for question in (1, 2, 3):
        answer(client, question, "A made-up answer.")
    raw = client.get("/teaching/cases/1").text
    assert '<a class="button" id="show-scenario" href="/teaching/cases/1?whole=yes#whole-scenario">Show the whole scenario</a>' in raw
    assert raw.find('id="feedback"') < raw.find('id="after-feedback"') and 'id="whole-scenario"' not in raw
    # Without the press the feedback page holds what the feedback shows and no more of the scenario.
    assert "made-up day" not in raw and "qreasonone" not in raw and "zzreasoning" not in raw and "Qsafety" not in raw
    asked = len(engine.calls)
    whole = client.get("/teaching/cases/1?whole=yes").text
    assert len(engine.calls) == asked                                                  # the press asks no model
    part = whole.split('<section class="pane" id="whole-scenario">', 1)[1].split("</section>", 1)[0]
    text = words_in(part)
    # First what the case is in short, the scenario's own first field; then the patient's side; then the examiner's.
    found = [part.find(f'id="{name}"') for name in ("in-short", "patients-side", "examiners-side")]
    assert all(f >= 0 for f in found) and found == sorted(found)
    assert text.startswith("The whole scenario The case in short zzreasoning zzmade zzup The patient's side Who Made Up, 40, female")
    for words in ("Occupation tester", "Manner Speaks plainly.", "Opening words I have a made-up ache.", "Ideas I think it is a made-up strain.",
                  "Concerns I worry about made-up work.", "Expectations I hope for a made-up note.", "Not said unless made easy None.",
                  "The ache began on a made-up day. (told at an open question)", "No made-up fever. (told only when asked)",
                  "Examination Qexamone: qfindone Qexamtwo: qfindtwo", "Results Qtestone: qresultone",
                  "Differential Qdiagone Must not be missed Qdiagtwo Qdiagthree", "Investigations Qinvone: qreasonone",
                  "Plan Qstepone Urgency: urgent Qsteptwo", "Safety-net advice Qsafety qnet.",
                  "Data gathering and diagnosis Qpointone. Qpointtwo. Qpointthree.", "Relating to others Qpointseven. Qpointeight. Qpointnine."):
        assert words in text, words
    # Every word of the scenario is there: nothing of either part is held back.
    assert words_of(said_in(SCENARIO)) <= words_of(text)
    # The feedback stays above it, and the page of the case is one address.
    assert whole.find('id="feedback"') < whole.find('id="whole-scenario"') and text_of(client.get("/teaching/cases/1?whole=no")).count("zzreasoning") == 0
