"""A changed path that sends less than one already ticked asks for no new
tick (spec 15.13, ruling 48, with ruling 5; the details of run 9c;
Cowork's review of the plan, point c). At the room check of 17 Nov 2026
the owner had ticked the statement for both cloud services, moved the
language model to this computer, and was asked for a new tick though
less was leaving. The test is made on sentences: each line of What is
sent and of each service's part. A new thing sent, a new service or a
changed word still asks."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import sentences_of, statement_for, words_checksum
from openconsult.settings.stored import Stored
from tests.conftest import refusal_on, text_of
from tests.made_up_store import MadeStore
from tests.test_cloud_consultation import BOTH_KEYS, cloud_app
from tests.test_connect_screens import SUITABLE, made_app
from tests.test_start import TICKS

# The six paths, by what leaves: L nothing; R the recording after Stop; S live sound; C the words; CR; CS.
PATHS = {"L": ChosenPath(THIS_COMPUTER, THIS_COMPUTER), "R": ChosenPath(THIS_COMPUTER, THIS_COMPUTER, True),
         "S": ChosenPath(THIS_COMPUTER, SPEECHMATICS), "C": ChosenPath(CLAUDE, THIS_COMPUTER),
         "CR": ChosenPath(CLAUDE, THIS_COMPUTER, True), "CS": ChosenPath(CLAUDE, SPEECHMATICS)}
# The table of the plan of run 9c, item 3. Rows: the statement last ticked. For each, the paths that then ask for no tick.
NO_TICK = {None: "L", "R": "L R", "S": "L S", "C": "L C", "CR": "L R C CR", "CS": "L S C CS"}
CELLS = [(ticked, now, now in NO_TICK[ticked].split()) for ticked in NO_TICK for now in PATHS]
# Restated on the owner's shape of 18 Nov 2026 (mail 4 of run 9c). OLD, my draft, one line: Less leaves this computer
# than you agreed to, so no new tick is asked. This is what leaves now. NEW, his: the head, then what runs on this
# computer and what runs in the cloud, a line each; the full statement closed under them.
# Restated again on his word of 20 Nov 2026, 08:06 (mail 5): one line, not two. OLD: his head of 18 Nov, Saved. No new
# tick is asked, because less leaves this computer than you agreed to., with the control's own line (Saved. It takes
# effect at the next consultation.) above it. NEW: the one line below, and the control's line not shown with it.
LESS = "Saved. No new tick is asked, because less leaves this computer than you agreed to. It takes effect at the next consultation."
HERE_S = "On this computer: the language model. Nothing goes to Claude."
CLOUD_S = "In the cloud: transcription, by Speechmatics. The sound of the consultation goes to it as it is spoken."


def stored_in(tmp_path, clock) -> tuple[Stored, Audit]:
    db = open_database(tmp_path / "openconsult.db")
    audit = Audit(db, clock)
    return Stored(db, audit, clock), audit


@pytest.mark.parametrize("ticked, now, covered", CELLS, ids=[f"ticked {t or 'none'}, now {n}" for t, n, _ in CELLS])
def test_15_13_ruling_48_for_every_pair_of_paths_whether_the_tick_is_asked(tmp_path, clock, ticked, now, covered):
    stored, audit = stored_in(tmp_path, clock)
    if ticked is not None:
        made = statement_for(PATHS[ticked])
        stored.tick_statement(made.sha256, PATHS[ticked], made)
    assert stored.covers(statement_for(PATHS[now])) is covered


def test_15_13_ruling_48_what_is_kept_with_a_tick_is_the_two_lists_as_sentences_and_no_heading_no_stays_and_no_tick(tmp_path, clock):
    both = statement_for(PATHS["CS"])
    kept = sentences_of(both)
    assert len(kept) == 28 and all(s.endswith(".") for s in kept)
    lines = (*both.sent, *(line for _, part in both.parts for line in part))
    assert all(any(line.startswith(sentence) for sentence in kept) for line in lines)      # every line begins with a kept sentence
    assert all(any(sentence in line for line in lines) for sentence in kept)               # and every kept sentence stands in a line
    twice = "OpenConsult cannot check this for you."                                       # said of each service, kept once
    assert sum(len(sentence) for sentence in kept) + len(twice) == sum(len(line) - line.count(". ") for line in lines)   # no letter lost
    assert "They go to the language model service." in kept and "OpenConsult cannot check this for you." in kept
    for outside in (both.heading, both.intro, both.tick, both.prototype, *both.stays, words.CLOUD_SENT_HEADING,
                    *(heading for heading, _ in both.parts)):
        assert outside not in kept and not any(outside in sentence for sentence in kept)
    # Rulings 5 and 39: the two lines that stand with or without their last sentence come out right by sentence.
    words_alone = set(sentences_of(statement_for(PATHS["C"])))
    assert "The words spoken in the consultation." in words_alone and "They go to the language model service." not in words_alone
    assert words_alone <= set(kept)
    recording = set(sentences_of(statement_for(PATHS["R"])))
    assert not any("20 US cents" in s for s in recording) and any("20 US cents" in s for s in kept)


def test_15_13_ruling_48_a_new_thing_sent_and_a_new_service_still_ask(tmp_path, clock):
    stored, audit = stored_in(tmp_path, clock)
    both = statement_for(PATHS["CS"])
    stored.tick_statement(both.sha256, PATHS["CS"], both)
    assert not stored.covers(statement_for(PATHS["R"]))                                    # the whole recording is a new thing sent
    assert not stored.covers(statement_for(PATHS["CR"]))
    stored, audit = stored_in(tmp_path / "s", clock)
    sound = statement_for(PATHS["S"])
    stored.tick_statement(sound.sha256, PATHS["S"], sound)
    assert not stored.covers(statement_for(PATHS["C"])) and not stored.covers(statement_for(PATHS["CS"]))   # Claude is a new service


@pytest.mark.parametrize("name", ["CLOUD_STAYS_NAME", "CLOUD_INTRO", "CLOUD_TICK_SOUND", "CLOUD_HEADING_RECORDING", "CLOUD_SENT_AGE",
                                  "CLOUD_SPEECHMATICS_WHOLE_COST"])
def test_15_13_ruling_48_a_changed_word_wherever_it_stands_asks_every_other_path_again(tmp_path, clock, monkeypatch, name):
    stored, audit = stored_in(tmp_path, clock)
    both = statement_for(PATHS["CS"])
    stored.tick_statement(both.sha256, PATHS["CS"], both)
    before = words_checksum()
    assert stored.covers(statement_for(PATHS["S"])) and stored.covers(statement_for(PATHS["C"]))
    # One word changed by a later release: in What stays, a heading, a tick's own words, a line: wherever.
    monkeypatch.setattr(words, name, getattr(words, name) + " Made-up change.")
    assert words_checksum() != before
    assert not stored.covers(statement_for(PATHS["S"])) and not stored.covers(statement_for(PATHS["C"]))
    # The path that was ticked asks again whenever its own text changed, as before (ruling 5).
    assert stored.covers(statement_for(PATHS["CS"])) is (statement_for(PATHS["CS"]).sha256 == both.sha256)


def test_15_13_ruling_48_a_folder_that_ticked_before_this_run_holds_a_checksum_alone_and_is_asked_once_more(tmp_path, clock):
    stored, audit = stored_in(tmp_path, clock)
    both, sound = statement_for(PATHS["CS"]), statement_for(PATHS["S"])
    stored.tick_statement(both.sha256, PATHS["CS"])                                        # as run 9b kept a tick: the checksum alone
    assert stored.covers(both) and not stored.covers(sound) and not stored.covers(statement_for(PATHS["C"]))
    stored.tick_statement(sound.sha256, PATHS["S"], sound)                                 # asked once: that tick keeps the sentences
    assert stored.covers(sound) and not stored.covers(both)
    # A tick with a checksum alone leaves nothing kept from an earlier one.
    stored.tick_statement(both.sha256, PATHS["CS"], both)
    stored.tick_statement("0" * 64, PATHS["CS"])
    assert not stored.covers(sound) and not stored.covers(both)


def test_15_13_ruling_48_a_path_that_sends_less_is_saved_under_the_wider_tick_with_both_checksums_and_the_page_shows_what_leaves(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    both, sound, model = (statement_for(PATHS[name]) for name in ("CS", "S", "C"))
    client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": model.sha256})
    client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "understand": "yes", "sha256": both.sha256})
    saved = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER, "place": "keep"})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=less&at=language-model"
    assert p.stored.path("suitable") == PATHS["S"] and p.stored.ticked_sha256 == both.sha256           # the tick that stands stays the wider one
    assert (p.audit.lines()[0].event, p.audit.lines()[0].detail) == ("statement.covered", (
        "language model this_computer, transcription speechmatics, recording after Stop no; saved under the wider tick; "
        f"sha256 of this path's statement {sound.sha256}; sha256 of the statement ticked {both.sha256}"))
    assert words.EVENTS["statement.covered"] in text_of(client.get("/log"))
    # Right after the save: under the control that was changed, with no tick; Saved beside it; and on the page once.
    after = client.get(saved.headers["location"])
    section = after.text.split('<section class="pane" id="language-model">', 1)[1].split("</section>", 1)[0]
    assert 'id="less-language-model"' in section and LESS in section and words.PATH_SAVED not in section and LESS == words.LESS_HEAD
    assert section.index(LESS) < section.index(HERE_S) < section.index(CLOUD_S) and not hasattr(words, "PATH_SENDS_LESS")
    assert sound.heading in section and all(line in text_of(after) for line in sound.sent) and sound.tick not in text_of(after)
    assert text_of(after).count(LESS) == 1 and 'name="sha256"' not in after.text and 'id="cloud-statement"' not in after.text
    # On a later view: where a statement to tick would stand, read only: what runs where, once, and no head, since
    # nothing was saved by this view.
    # Restated on mail 5 of run 9c (the owner's word of 18 Nov 2026, 08:03). OLD: each of the two lines once on the
    # page. NEW: twice, here and above the picture of This machine, which says the same two lines for the path chosen.
    later = client.get("/settings")
    assert 'id="statement-covered"' in later.text and text_of(later).count(HERE_S) == 2 and text_of(later).count(CLOUD_S) == 2
    covered = text_of(later).split('id="statement-covered"', 1)[1].split("</section>", 1)[0]
    assert covered.count(HERE_S) == 1 and covered.count(CLOUD_S) == 1
    assert LESS not in text_of(later) and 'name="understand"' not in later.text
    # The wider path asks nothing on the way back, while its words are unchanged; and then nothing more is shown.
    back = client.post("/settings/path/language-model", data={"language_model": CLAUDE})
    assert back.status_code == 303 and back.headers["location"].startswith("/settings?done=path&at=language-model")
    assert p.stored.path("suitable") == PATHS["CS"] and LESS not in text_of(client.get("/settings"))
    assert HERE_S not in text_of(client.get("/settings")) and "On this computer:" not in text_of(client.get("/settings"))
    assert len([l for l in p.audit.lines() if l.event == "statement.ticked"]) == 2
    # A path that sends something new from there still waits for its tick: the recording after Stop.
    client.post("/settings/path/transcription", data={"transcription": THIS_COMPUTER})                 # C under CS: less
    waits = client.post("/settings/better-accuracy", data={"better_accuracy": "yes"})
    assert waits.status_code == 200 and words.PATH_NOT_SAVED_YET in text_of(waits) and refusal_on(waits.text, "save-better-accuracy") == ""
    assert not p.stored.path("suitable").better_accuracy


def test_15_13_ruling_48_start_is_offered_on_a_path_under_a_wider_tick_and_the_consultation_records_its_own_paths_checksum(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=SUITABLE, held=BOTH_KEYS)
    p = app.state.parts
    both, sound = statement_for(PATHS["CS"]), statement_for(PATHS["S"])
    p.stored.set_path("suitable", PATHS["CS"])
    p.stored.tick_statement(both.sha256, PATHS["CS"], both)
    client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    page = client.get("/consultations/start/1")
    assert words.START_STATEMENT not in text_of(page)
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303
    row = p.consultations.get(1)
    assert (row["language_model_path"], row["transcription_path"]) == (THIS_COMPUTER, SPEECHMATICS)
    assert row["statement_sha256"] == sound.sha256 != p.stored.ticked_sha256                # its own path's, not the wider one that was ticked
    p.running[1].close()
