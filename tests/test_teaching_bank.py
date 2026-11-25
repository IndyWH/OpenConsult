"""The bank of scenarios and the topic menu (spec 12.5; 15.14, rulings 1
to 4, 17 and 23, and the details of run 10b: The bank and the topics,
handed over as files). The nine files are Cowork's, made from a
clinician's scripts, and are held to their bytes. Every other scenario
here is made up, and no model is asked."""

import copy
import hashlib
import json

import pytest

from openconsult.teaching import bank as bank_module
from openconsult.teaching.bank import read_bank, read_topics
from tests import made_teaching

# The nine files as Cowork handed them on 25 Nov 2026 (the list at the end of stage-prompts/STAGE_10B.md). The owner's
# approval of a case later changes one word of that case's file and its one checksum here, in one commit (ruling 3).
HANDED = {
    "card_11_tired_all_the_time.json": "7db55b72ad64433df0cb2437ebd198eb35714ca31de52a7846777e6976126db9",
    "card_12_dizziness.json": "905f913d16b05b19114f521546265c253595080af937b92a1e2075c9237bc530",
    "card_13_migraine.json": "ae8f1156e472fb87bc79299e0a5fe3a728983600b5689fd8f145b418914c755f",
    "card_14_giant_cell_arteritis.json": "2f976f83c5cd43a3cacd858ff1088b55d934de8a2b780f466fda5b024cacdf39",
    "card_15_cauda_equina.json": "c3f8964526e6eafdb98b18ef4aa62b77c882cd59c62b4b180780b6cded3b4bd3",
    "card_16_urti_antibiotic_demand.json": "f186df20de5df333a9c95388733ee95e3b30d330e7b80fd96d568e16a045560c",
    "card_17_perimenopause.json": "c3a95d487fdb966694797121c8180e3be81c7daaed17285e730928d4bc9a6ce3",
    "card_18_ectopic_pregnancy.json": "c31977e2a9849d70678696f79445b0369ca38bb60bac3a2f03bbcc27790f3e7d",
    "topics.json": "b9ad23fd6ce16461a84bab428e2f6f5ad3dcdd66482928a8554af3b71af71dd3",
}
TOPICS = {"clinical": ["A made-up topic", "Another made-up topic"], "life_stage": ["A third made-up topic"]}


def made_folder(tmp_path, cards: dict):
    """A bank folder in the shape of Cowork's: topics.json and one file for each card, by the name given."""
    folder = tmp_path / "bank"
    folder.mkdir()
    (folder / "topics.json").write_text(json.dumps(TOPICS), encoding="utf-8")
    for name, card in cards.items():
        (folder / name).write_text(card if isinstance(card, str) else json.dumps(card), encoding="utf-8")
    return folder


def card(case_id: str = "zz_made_diagnosis", **changes) -> dict:
    made = made_teaching.case(case_id)
    del made["bench"]
    return {**made, **changes}


def test_15_14_rulings_2_and_17_the_nine_files_of_the_bank_are_the_handed_bytes():
    found = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(bank_module.FOLDER.glob("*.json"))}
    assert found == HANDED


def test_15_14_ruling_1_the_menu_is_the_26_titles_in_the_order_of_the_file_and_the_bank_is_eight_cases_in_the_order_of_the_file_names():
    topics, bank = read_topics(), read_bank()
    assert len(topics) == 26 and len(set(topics)) == 26
    assert (topics[0], topics[21], topics[22], topics[25]) == (
        "Allergy and clinical immunology", "Urgent and unscheduled care", "Children and young people", "People at the end of life")
    assert bank.topics == topics and bank.unread == 0 and [case.number for case in bank.cases] == list(range(1, 9))
    # Each is held to the form of the case, to a level of the three, to a topic of the menu and to a label of two.
    names = sorted(name for name in HANDED if name != "topics.json")
    for case, name in zip(bank.cases, names):
        held = json.loads((bank_module.FOLDER / name).read_text(encoding="utf-8"))
        assert (case.topic, case.level, case.label, case.scenario) == (held["topic"], held["level"], held["label"], held["scenario"])
        assert case.topic in topics and case.level in ("straightforward", "hidden", "noisy") and case.label in ("script", "approved")
    assert bank.case(2).topic == "Neurology" and bank.case(9) is None and bank.case(0) is None


@pytest.mark.parametrize("broken", [
    "{ not json",                                                    # not JSON
    json.dumps(["a", "list"]),                                       # not a case at all
    card(level="easy"),                                              # a level that is not one of the three
    card(topic="A topic that is not on the menu"),                   # a topic that is not of the list
    card(label="ai"),                                                # a label that is not one of the bank's two
    card(scenario={**made_teaching.SCENARIO, "facts": "not a list"}),          # a scenario that is not the form of the case
    {key: value for key, value in card().items() if key != "scenario"},      # no scenario
], ids=["not JSON", "not a case", "level", "topic", "label", "form", "no scenario"])
def test_15_14_a_file_that_does_not_hold_is_not_offered_and_is_counted_and_takes_no_number(tmp_path, broken):
    folder = made_folder(tmp_path, {"card_01_made.json": card(), "card_02_broken.json": broken, "card_03_made.json": card(label="approved")})
    bank = read_bank(folder)
    assert bank.unread == 1 and [(case.number, case.label) for case in bank.cases] == [(1, "script"), (2, "approved")]


def test_15_14_ruling_4_a_tenth_file_joins_by_being_put_there(tmp_path):
    cards = {f"card_{n:02d}_made.json": card() for n in range(1, 10)}
    folder = made_folder(tmp_path, cards)
    assert len(read_bank(folder).cases) == 9
    later = copy.deepcopy(card(topic="Another made-up topic", level="noisy"))
    (folder / "card_10_made.json").write_text(json.dumps(later), encoding="utf-8")
    bank = read_bank(folder)
    assert len(bank.cases) == 10 and (bank.case(10).topic, bank.case(10).level) == ("Another made-up topic", "noisy")
    assert [case.number for case in bank.cases] == list(range(1, 11))


def test_15_14_the_pages_are_given_nothing_of_a_files_name_its_id_its_source_or_its_notes(tmp_path):
    made = card("zz_wordofid", source="zzsource of the made file", not_in_script=["zznote one"], left_out=["zzleft out"])
    bank = read_bank(made_folder(tmp_path, {"card_77_zzfilename.json": made}))
    given = repr(bank)                                               # everything the bank hands on, as text
    assert "Made Up" in given and "Qdiagone" in given                # the scenario itself is there, for the case's own row
    for word in ("zz_wordofid", "wordofid", "zzsource", "zznote", "zzleft", "zzfilename", "card_77"):
        assert word not in given
    assert set(vars(bank.cases[0])) == {"number", "topic", "level", "label", "scenario"}
