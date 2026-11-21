"""The notice under a control when a changed path sends less than one
already ticked (spec 15.13, ruling 48), in the owner's shape and words of
18 Nov 2026 (mail 4 of run 9c). He did not follow the draft line and
asked, from the doctor's point of view: what if the statement says what
is local and what is going to the cloud. So the notice names the two
jobs, as the picture does: the head; a line that begins On this
computer; a line that begins In the cloud, with what goes there. The
same sentences stand in the cloud boxes of the picture, from one
function, so that a doctor reads one wording everywhere."""

from __future__ import annotations

import re

import pytest

from openconsult import words
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER
from openconsult.settings.statement import goes_sentence, goes_to, statement_for, where_lines
from openconsult.web import panel
from tests.conftest import text_of
from tests.test_less_no_tick import NO_TICK, PATHS
from tests.test_machine_status import box_of
from tests.test_panel import BOTH_KEYS, made

# THE OWNER'S, letter for letter (his words of 18 Nov 2026, 07:07 to 07:25).
# The head restated on his word A of 20 Nov 2026, 08:06 (mail 5 of run 9c): one line, not two. OLD, his head of 18 Nov,
# under the control's ordinary line, so that two lines began Saved.: Saved. No new tick is asked, because less leaves
# this computer than you agreed to. NEW, the one line the page shows in that case, letter for letter:
HEAD = "Saved. No new tick is asked, because less leaves this computer than you agreed to. It takes effect at the next consultation."
HERE_MODEL = "On this computer: the language model. Nothing goes to Claude."
HERE_BOTH = "On this computer: the language model and transcription."
CLOUD_SPEECH = "In the cloud: transcription, by Speechmatics. The sound of the consultation goes to it as it is spoken."
CLOUD_MODEL = "In the cloud: the language model, by Claude. The words of the consultation go to it."
CLOUD_AFTER_STOP = "In the cloud: after Stop, the recording goes to Speechmatics once. No sound goes to it during the consultation."
# COWORK'S DRAFT after his pattern, which the owner has not seen.
HERE_SPEECH_DRAFT = "On this computer: transcription. Nothing goes to Speechmatics."
# The notice of each path that can be saved under a wider tick: the path, the wider tick, the control that is
# changed with what is sent, and its two lines.
COVERED = [
    ("S", "CS", "language-model", "/settings/path/language-model", {"language_model": THIS_COMPUTER}, (HERE_MODEL, CLOUD_SPEECH)),
    ("R", "CR", "language-model", "/settings/path/language-model", {"language_model": THIS_COMPUTER}, (HERE_BOTH, CLOUD_AFTER_STOP)),
    ("C", "CR", "better-accuracy", "/settings/better-accuracy", {}, (HERE_SPEECH_DRAFT, CLOUD_MODEL)),
    ("C", "CS", "transcription", "/settings/path/transcription", {"transcription": THIS_COMPUTER}, (HERE_SPEECH_DRAFT, CLOUD_MODEL)),
]
# What a cloud box says goes to it. His sentences, with a capital where one begins the line; Nothing goes to
# Speechmatics. is the draft named above.
BOX_SPEECH = {"live": "The sound of the consultation goes to it as it is spoken.",
              "after_stop": "After Stop, the recording goes to Speechmatics once. No sound goes to it during the consultation.",
              "nothing": "Nothing goes to Speechmatics."}
BOX_MODEL = {"live": "The words of the consultation go to it.", "nothing": "Nothing goes to Claude."}
OLD_DRAFTS = ("Less leaves this computer than you agreed to, so no new tick is asked.", "This is what leaves now.", "On the path you chose")


def notice_of(page: str, at: str) -> str:
    return page.split(f'<div class="statement-shown" id="less-{at}">', 1)[1].split("</details>", 1)[0]


def picture_lines(page: str) -> list[str]:
    """The lines above the picture of This machine, as the page holds them."""
    above = page.split('<div class="panel-where" id="panel-path">', 1)[1].split("</div>", 1)[0]
    return re.findall(r'<p class="sentence">([^<]*)</p>', above)


# The line above the picture for each of the six paths (mail 5 of run 9c). THE OWNER'S, letter for letter: the lines
# named above, and for the path with nothing in the cloud his two of 18 Nov 2026, 08:03.
CLOUD_NOTHING = "In the cloud: nothing."
# Restated on the owner's word B of 21 Nov 2026 (15.13, ruling 76; step 9f): each thing in the cloud has a line of its
# own that begins In the cloud:, in his words of 18 Nov. OLD, Cowork's details of run 9c, drafts he had not seen: at
# most one line for each heading; two things in the cloud followed one another on that one line, the transcription or
# the recording first, then the language model, each sentence beginning with a capital:
#   CS, one line: In the cloud: Transcription, by Speechmatics. The sound of the consultation goes to it as it is
#       spoken. The language model, by Claude. The words of the consultation go to it.
#   CR, its second line: In the cloud: After Stop, the recording goes to Speechmatics once. No sound goes to it during
#       the consultation. The language model, by Claude. The words of the consultation go to it.
# NEW: one line for each thing, each the heading and then his sentence with a small letter. Unchanged: where nothing
# runs on this computer the line On this computer: is left out; and that line alone for CR is still Cowork's draft.
HERE_SPEECH_ALONE_DRAFT = "On this computer: transcription."
ABOVE_THE_PICTURE = {"L": (HERE_BOTH, CLOUD_NOTHING), "R": (HERE_BOTH, CLOUD_AFTER_STOP), "S": (HERE_MODEL, CLOUD_SPEECH),
                     "C": (HERE_SPEECH_DRAFT, CLOUD_MODEL), "CR": (HERE_SPEECH_ALONE_DRAFT, CLOUD_AFTER_STOP, CLOUD_MODEL),
                     "CS": (CLOUD_SPEECH, CLOUD_MODEL)}


@pytest.mark.parametrize("name", list(ABOVE_THE_PICTURE))
def test_his_word_of_18_nov_the_line_above_the_picture_says_what_runs_here_and_what_in_the_cloud_for_each_of_the_six_paths(tmp_path, clock, name):
    lines = ABOVE_THE_PICTURE[name]
    assert where_lines(PATHS[name]) == lines
    # OLD: at most one line for each heading, On this computer first; never a line with neither; In the cloud: once.
    # NEW: at most one line On this computer, first; then one line In the cloud for each thing that is there, and one
    # where nothing is; never a line with neither.
    in_cloud = max(1, sum(goes_to(PATHS[name], service) != "nothing" for service in (SPEECHMATICS, CLAUDE)))
    assert [line.split(":")[0] for line in lines] in (["On this computer"] + ["In the cloud"] * in_cloud, ["In the cloud"] * in_cloud)
    assert all(line.count("On this computer:") + line.count("In the cloud:") == 1 for line in lines)
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    page = text_of(client.get("/settings"))
    assert picture_lines(page) == list(lines) and panel.build(app.state.parts).path_lines == lines
    # The draft sentence is gone from the page and from the file of words.
    assert "The path you chose" not in page and not hasattr(words, "PANEL_PATH_LINE") and not hasattr(words, "PANEL_PATH_BY")
    # A path whose own statement is ticked shows the lines above the picture alone: no notice of a path that sends less.
    # OLD: In the cloud: once on the page. NEW: once for each line of the cloud.
    assert 'id="less-' not in page and page.count("In the cloud:") == in_cloud


def test_his_word_of_18_nov_the_path_with_nothing_in_the_cloud_letter_for_letter_and_the_same_at_step_2_of_the_first_run(tmp_path, clock):
    assert where_lines(PATHS["L"]) == ("On this computer: the language model and transcription.", "In the cloud: nothing.")
    assert words.IN_THE_CLOUD_NOTHING == "nothing."
    # Step 2 of the first run draws the same picture: a machine with a suitable card begins on this computer for both.
    app, client, *_ = made(tmp_path, clock, user=False)
    client.post("/first-run/statement", data={"agree": "yes"})
    step = text_of(client.get("/first-run"))
    assert picture_lines(step) == ["On this computer: the language model and transcription.", "In the cloud: nothing."]


@pytest.mark.parametrize("name, wider, at, address, sent, lines", COVERED)
def test_ruling_48_the_notice_of_a_path_that_sends_less_in_the_owners_shape_and_words_of_18_nov(tmp_path, clock, name, wider, at, address, sent, lines):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[wider])
    p = app.state.parts
    ticked = statement_for(PATHS[wider])
    p.stored.tick_statement(ticked.sha256, PATHS[wider], ticked)                 # the wider statement, ticked with its sentences kept
    saved = client.post(address, data=sent)
    assert saved.status_code == 303 and saved.headers["location"].startswith(f"/settings?done=less&at={at}")
    assert p.stored.path("suitable") == PATHS[name] and p.stored.ticked_sha256 == ticked.sha256      # saved, and no new tick
    page = client.get(saved.headers["location"])
    notice = notice_of(text_of(page), at)
    # Three parts, in this order: the head, what runs on this computer, what runs in the cloud with what goes to it.
    said = re.findall(r'<p class="(?:less-head|where-line)">([^<]*)</p>', notice)
    assert said == [HEAD, *lines] and words.LESS_HEAD == HEAD
    assert 'role="status"' in notice.split("<details", 1)[0]
    # One line begins Saved., and it is his: the control's ordinary line is not shown above it (his word of 20 Nov).
    assert re.findall(r">\s*(Saved\.[^<]*)<", text_of(page)) == [HEAD] and f'id="saved-{at}"' not in page.text
    assert words.PATH_SAVED not in text_of(page) and words.PATH_SAVED == "Saved. It takes effect at the next consultation."
    # The full statement of the path stays one press away under the notice: closed until pressed, by the browser's own
    # disclosure, so with no script; and it holds no tick.
    full = notice.split("</div>", 1)[1]
    assert full.lstrip().startswith(f'<details class="statement-full"><summary>{words.LESS_FULL_STATEMENT}</summary>') and " open" not in full.split(">", 1)[0]
    own = statement_for(PATHS[name])
    assert own.heading in full and all(line in full for line in own.sent) and own.tick not in text_of(page)
    assert "<input" not in notice and "<button" not in notice and 'id="cloud-statement"' not in page.text
    # The same two lines and no other stand on the page, and the old draft nowhere. Restated on mail 5 of run 9c
    # (his word of 18 Nov, 08:03). OLD: each line once on the page. NEW: twice, in the notice and above the picture,
    # which now says the same two lines for the path chosen, from the same function.
    assert all(text_of(page).count(line) == 2 for line in lines) and text_of(page).count("On this computer:") == 2
    assert text_of(page).count("In the cloud:") == 2 and not any(old in text_of(page) for old in OLD_DRAFTS)
    assert picture_lines(text_of(page)) == list(lines)
    # On a later view the two lines stand where a statement to tick would stand, with the statement closed under
    # them; the head does not, since that view saved nothing.
    later = text_of(client.get("/settings"))
    assert picture_lines(later) == list(lines)
    apart = later.split('<div class="statement-shown" id="less-apart">', 1)[1].split("</details>", 1)[0]
    assert re.findall(r'<p class="(?:less-head|where-line)">([^<]*)</p>', apart) == list(lines) and HEAD not in later and "<input" not in apart


def test_his_word_of_20_nov_the_controls_ordinary_line_stands_alone_wherever_a_change_is_not_saved_under_a_wider_tick(tmp_path, clock):
    ordinary = "Saved. It takes effect at the next consultation."
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS["CS"])
    p = app.state.parts

    def saved_lines(answer) -> list[str]:
        return re.findall(r">\s*(Saved\.[^<]*)<", text_of(client.get(answer.headers["location"])))

    # Under a wider tick: the one line, his.
    less = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    assert saved_lines(less) == [HEAD]
    # The wider path on the way back, which is ticked itself: the ordinary line, alone.
    back = client.post("/settings/path/language-model", data={"language_model": CLAUDE})
    assert back.headers["location"].startswith("/settings?done=path&at=language-model") and saved_lines(back) == [ordinary]
    # A path with nothing in the cloud: the ordinary line, alone, beside the control that was changed.
    client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    plain = client.post("/settings/path/transcription", data={"transcription": THIS_COMPUTER})
    assert p.stored.path("suitable") == PATHS["L"] and saved_lines(plain) == [ordinary]
    assert f'id="saved-transcription" role="status">{ordinary}</p>' in text_of(client.get(plain.headers["location"]))
    # A choice saved by the tick of its own statement, a wider one: the ordinary line, alone.
    wider = statement_for(PATHS["R"])
    p.stored.tick_statement("0" * 64, PATHS["L"])                                # no tick stands for any path now
    ticked = client.post("/settings/better-accuracy", data={"better_accuracy": "yes", "understand": "yes", "sha256": wider.sha256})
    assert p.stored.path("suitable") == PATHS["R"] and saved_lines(ticked) == [ordinary]
    # An address that says less on a page whose path is not saved under a wider tick: never his line, never both.
    assert re.findall(r">\s*(Saved\.[^<]*)<", text_of(client.get("/settings?done=less&at=transcription"))) == [ordinary]


def test_ruling_48_the_owners_lines_of_18_nov_letter_for_letter_and_only_the_three_paths_of_the_table_are_ever_shown_so():
    assert where_lines(PATHS["S"]) == (HERE_MODEL, CLOUD_SPEECH)
    assert where_lines(PATHS["R"]) == (HERE_BOTH, CLOUD_AFTER_STOP)
    assert where_lines(PATHS["C"]) == (HERE_SPEECH_DRAFT, CLOUD_MODEL)
    assert (words.ON_THIS_COMPUTER, words.IN_THE_CLOUD) == ("On this computer:", "In the cloud:")
    # The paths that can stand under a wider tick, by the table of ruling 48: these three and no other.
    under_a_wider_tick = {now for ticked, covered in NO_TICK.items() if ticked for now in covered.split() if now not in ("L", ticked)}
    assert under_a_wider_tick == {"S", "R", "C"}
    # The old draft is gone from the file of words: its name, and its words in any sentence the file holds.
    assert not hasattr(words, "PATH_SENDS_LESS") and not hasattr(words, "PANEL_GOES")

    def texts(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in list(value.keys()) + list(value.values()):
                yield from texts(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                yield from texts(item)

    held = [text for name in dir(words) if name.isupper() for text in texts(getattr(words, name))]
    assert len(held) > 500 and not any(old in text for text in held for old in OLD_DRAFTS)


@pytest.mark.parametrize("name, speechmatics, claude", [
    ("L", "nothing", "nothing"), ("R", "after_stop", "nothing"), ("S", "live", "nothing"),
    ("C", "nothing", "live"), ("CR", "after_stop", "live"), ("CS", "live", "live"),
])
def test_ruling_48_each_cloud_box_says_what_goes_to_it_in_the_owners_sentence_for_each_of_the_six_paths(tmp_path, clock, name, speechmatics, claude):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    page = text_of(client.get("/settings"))
    assert f'<p class="box-goes">{BOX_SPEECH[speechmatics]}</p>' in box_of(page, "speechmatics")
    assert f'<p class="box-goes">{BOX_MODEL[claude]}</p>' in box_of(page, "claude")
    made_panel = panel.build(app.state.parts)
    assert (made_panel.box("speechmatics").goes, made_panel.box("claude").goes) == (BOX_SPEECH[speechmatics], BOX_MODEL[claude])
    assert (goes_to(PATHS[name], SPEECHMATICS), goes_to(PATHS[name], CLAUDE)) == (speechmatics, claude)
    assert not any(old in page for old in OLD_DRAFTS)
    # A sentence of a box that says something goes to the service stands in the notice's line for the cloud, and one
    # that says nothing goes to it in the line for this computer where that job alone runs here: one wording.
    lines = " ".join(where_lines(PATHS[name]))
    for service, goes, sentence in ((SPEECHMATICS, speechmatics, BOX_SPEECH[speechmatics]), (CLAUDE, claude, BOX_MODEL[claude])):
        if goes == "live":
            assert sentence in lines
        elif goes == "after_stop":
            # Restated on mail 5 of run 9c. OLD: the sentence follows the heading with a small letter, always. NEW: so
            # where it is the one thing in the cloud; where Claude is there too, each sentence begins with a capital.
            # Restated again on the owner's word B of 21 Nov 2026 (15.13, ruling 76; step 9f). OLD, of mail 5:
            #   first = sentence[0] if claude == "live" else sentence[0].lower()
            # NEW: with a small letter always, for the sentence stands after the heading of a line of its own.
            assert f"In the cloud: {sentence[0].lower()}{sentence[1:]}" in lines


def test_ruling_48_the_notice_and_the_boxes_read_one_function_so_the_two_can_never_differ(tmp_path, clock, monkeypatch):
    # One made change in the one place: the box and the notice both show it.
    changed = {SPEECHMATICS: {**words.GOES[SPEECHMATICS], "live": "Made-up sentence for sound."},
               CLAUDE: {**words.GOES[CLAUDE], "nothing": "Made-up sentence for nothing."}}
    monkeypatch.setattr(words, "GOES", changed)
    assert goes_sentence(PATHS["S"], SPEECHMATICS) == "Made-up sentence for sound." and goes_sentence(PATHS["S"], CLAUDE) == "Made-up sentence for nothing."
    assert where_lines(PATHS["S"]) == ("On this computer: the language model. Made-up sentence for nothing.",
                                       "In the cloud: transcription, by Speechmatics. Made-up sentence for sound.")
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS["CS"])
    p = app.state.parts
    ticked = statement_for(PATHS["CS"])
    p.stored.tick_statement(ticked.sha256, PATHS["CS"], ticked)
    saved = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    page = text_of(client.get(saved.headers["location"]))
    notice = notice_of(page, "language-model")
    assert "Made-up sentence for nothing." in notice and "Made-up sentence for sound." in notice
    assert '<p class="box-goes">Made-up sentence for sound.</p>' in box_of(page, "speechmatics")
    assert '<p class="box-goes">Made-up sentence for nothing.</p>' in box_of(page, "claude")
    # And the box takes its sentence from that function, not from the file of words by itself.
    import inspect
    source = inspect.getsource(panel)
    assert "goes_sentence(path, service)" in source and "words.GOES" not in source
