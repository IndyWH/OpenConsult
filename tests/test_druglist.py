"""The UK drug list (spec 15.9, ruling 2; the details of part two of 5c;
the plan review's change 1; 9.4; R18; rule 16 of the stage prompt). A
made-up month; the suite never reaches the internet."""

import io
import json
from pathlib import Path

import pytest

from openconsult.bench import cli
from openconsult.bench.speech import commands2, druglist
from openconsult.bench.writer import Refused
from openconsult.settings import paths
from tests.made_up_drugs import ROWS, csv_text, made_up_list, write_csv


def test_the_rule_that_makes_the_list_on_a_made_up_month(tmp_path):
    listed = druglist.make_list(write_csv(tmp_path / "pca_202607.csv"), "202607")
    names = {n["name"]: n for n in listed["names"]}
    assert names["metforma"] == {"name": "metforma", "kind": "generic", "rows": 2}      # the salt dropped; the brand's row counts too
    assert names["glucoform"]["kind"] == "brand" and names["night calm"]["kind"] == "brand"
    assert names["dormirex"]["kind"] == "generic"                                       # pamoate, a salt, dropped
    assert "light mineral parafil" in names and "lidocaina" in names and "adrenalina" in names   # with: two names
    assert names["sodium chloride"]["kind"] == "generic"                                # all salt words: kept whole
    for left_out in ("bandage", "made up bandage", "made up food", "tin", "nameless", "sodium", "chloride", "with", "light"):
        assert left_out not in names
    assert listed["rows"] == 10 and listed["rows_kept"] == 7                   # the short name's row is kept; its name is left out
    assert listed["dropped"] == {"chapters": {"21": 1}, "sections": {"0913": 1}, "no_substance": 1}
    assert listed["prep_class"] == {"1": {"own_generic_equivalent": 5, "not": 0}, "2": {"own_generic_equivalent": 0, "not": 2}}
    assert listed["names_count"] == 8 and listed["one_word_names"] == 5 and listed["longer_names"] == 3
    assert (listed["month"], listed["licence"]) == ("202607", "Open Government Licence v3.0")
    assert listed["file_sha256"] and listed["file_bytes"] > 0
    # The month is checked against every row; a file lacking a column is refused.
    wrong_month = write_csv(tmp_path / "other.csv", [ROWS[0][:0] + ("202606",) + ROWS[0][1:]])
    with pytest.raises(druglist.BadFile, match="not 202607"):
        druglist.make_list(wrong_month, "202607")
    (tmp_path / "short.csv").write_text("YEAR_MONTH,BNF_PRESENTATION_NAME\n202607,x\n", encoding="utf-8")
    with pytest.raises(druglist.BadFile, match="lacks the columns"):
        druglist.make_list(tmp_path / "short.csv", "202607")


def test_the_fetch_writes_bytes_through_the_urlopen_given_and_never_over_a_file(tmp_path):
    data = ("﻿" + csv_text()).encode("utf-8")

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    asked = []

    def urlopen(url):
        asked.append(url)
        return Answer(data)

    target = tmp_path / "pca_202607.csv"
    found = druglist.fetch("https://made-up.example/pca_202607.csv", target, urlopen=urlopen)
    assert asked == ["https://made-up.example/pca_202607.csv"] and target.read_bytes() == data
    assert found["bytes"] == len(data) and found["sha256"] == __import__("hashlib").sha256(data).hexdigest()
    with pytest.raises(Refused):
        druglist.fetch("https://made-up.example/pca_202607.csv", target, urlopen=urlopen)
    assert len(asked) == 1
    listed = druglist.make_list(target, "202607")
    out = druglist.write_list(tmp_path / "drug_list.json", listed)
    assert json.loads(out.read_text(encoding="utf-8"))["names_count"] == 8
    with pytest.raises(Refused):
        druglist.write_list(out, listed)


def test_ruling_2_closeness_against_whole_names_of_one_word(tmp_path):
    drugs = made_up_list(tmp_path)
    words = "i take metformo and glucoform at night calm and right after light meals with tin".split()
    marks = druglist.doubtful_by_list(words, drugs)
    by_word = {words[m["word"]]: m for m in marks}
    assert by_word["metformo"]["close_to"] == "metforma"                     # close at 0.75 or more
    assert "glucoform" not in by_word or "close_to" not in by_word["glucoform"]   # a name in the list is never in doubt
    assert "tin" not in by_word and "take" not in by_word                     # fewer than 5 letters: never
    # "night" and "calm" stand in order as the whole brand name: in the list, and listed as brand only.
    assert by_word["night"] == {"word": 6, "brand_only": "night calm"} and "calm" not in by_word   # calm: four letters
    # "right" is close to "light", a word of a longer name, and to no name of one word: NOT marked.
    assert "right" not in by_word
    assert "light" not in by_word                                            # alone, light is not a whole name, and close to no one-word name
    assert drugs.in_list_at(words, 6) == "night calm" and drugs.in_list_at(words, 7) == "night calm"
    assert drugs.in_list_at("light meals".split(), 0) is None
    assert drugs.in_list_at("light mineral parafil".split(), 2) == "light mineral parafil" and drugs.is_whole_name(["night", "calm"])
    assert not drugs.is_whole_name(["night"]) and drugs.close_to("metforma") == "metforma" and drugs.close_to("zzzzzz") is None


def test_R18_the_command_refuses_the_forbidden_folders_before_anything_is_fetched(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    asked, said = [], []

    def urlopen(url):
        asked.append(url)
        raise AssertionError("never reached")

    from tests.made_up_recordings import made_up_recordings
    folder = made_up_recordings(tmp_path / "rec")
    for place in (commands2.REPO / "x", tmp_path / "owner-data" / "o", folder / "o"):
        assert commands2.speech_drugs("202607", "https://made-up.example/x.csv", place, say=said.append, urlopen=urlopen,
                                      recordings_folder=folder) == 6
    assert asked == [] and said[-1].startswith("Results may not go under")
    seen = []
    monkeypatch.setattr(commands2, "speech_drugs", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["speech-drugs", "--month", "202607", "--from", "https://made-up.example/x.csv", "--out", str(tmp_path / "d")]) == 0
    assert seen[0][:2] == ("202607", "https://made-up.example/x.csv") and seen[0][2] == Path(tmp_path / "d")
