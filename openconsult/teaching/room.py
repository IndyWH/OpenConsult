"""How long a teaching case may grow (spec 15.14, the details of run
10b: The history; R30). The feedback reads the whole scenario and the
whole consultation in one request, the largest of a case, so its room
decides how many lines a history can hold. The page says so before the
length is reached and never lets a learner type a history whose
feedback could not be read.

Counted from the stored calls of the bench of run 10a, by the tokens
each engine reported itself for its requests, set beside the characters
of each request: the feedback's request takes about 132 + 0.237 x
characters tokens on Gemma (vLLM and Ollama alike) and 1,106 + 0.349 x
characters on Claude Haiku. The window is 16,384 tokens (the profile's
context, which the app asks of every engine), less the feedback's own
2,500 tokens of reply: 13,884. One bound serves every engine, by the
tighter: at 33,000 characters the request is about 12,600 tokens on
Claude and 7,960 on Gemma. The bench never asked for a feedback longer
than 10,471 characters: a longer one fits, and is not measured."""

from __future__ import annotations

from openconsult.llm.jobs import job
from openconsult.prompts import loader
from openconsult.teaching import frames
from openconsult.teaching.cases import ANSWERS

FEEDBACK_JOB = "teaching_feedback"
FEEDBACK_BOUND = 33_000        # characters of the feedback's request: its prompt and its filled frame
LINE_MOST = 1_000              # one line of the history, or one examination request
ANSWER_MOST = 1_500            # one of the three answers
EXAMINED_ROOM = 3_000          # every examination request of a case together
# What the history leaves for what comes after it: the examination and the three answers.
AFTER_HISTORY = EXAMINED_ROOM + len(ANSWERS) * ANSWER_MOST
# The patient's reply may take 300 tokens (its job's limit): at Gemma's 0.237 tokens a character, about 1,300 characters.
REPLY_ROOM = 1_300
GETTING_LONG = 2_500           # under this much room the page says that only a few more lines fit
NO_ANSWERS = {name: "" for name in ANSWERS}


def feedback_chars(scenario: dict, conversation: list[tuple[str, str]]) -> int:
    """The characters of the feedback's request as the frames would build it for this history, before any
    examination or answer."""
    return len(loader.prompt(job(FEEDBACK_JOB).prompt)) + len(frames.feedback_message(scenario, conversation, [], NO_ANSWERS))


def history_room(scenario: dict, conversation: list[tuple[str, str]]) -> int:
    """The characters the history may still grow by."""
    return FEEDBACK_BOUND - AFTER_HISTORY - feedback_chars(scenario, conversation)


def line_fits(scenario: dict, conversation: list[tuple[str, str]], line: str) -> bool:
    """Whether one more line, with the longest reply its job allows, still leaves the feedback its room."""
    return history_room(scenario, [*conversation, ("doctor", line), ("patient", "")]) >= REPLY_ROOM


def getting_long(scenario: dict, conversation: list[tuple[str, str]]) -> bool:
    return history_room(scenario, conversation) < GETTING_LONG


def examination_fits(examined: list[str], request: str) -> bool:
    """Whether one more examination request stays within the room kept for all of them."""
    return sum(len(text) for text in examined) + len(request) <= EXAMINED_ROOM
