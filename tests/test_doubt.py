"""Three ways to spot a doubtful drug name, counted alike, and the three
classes (spec 15.9, rulings 2, 16 and 18; the details of part two of 5c).
A made-up script, made-up pages, a made-up list."""

from openconsult.bench.speech import doubt, model_lines, who
from openconsult.bench.speech.reference import build
from tests.made_up_drugs import made_up_list

SCRIPT = "**DOCTOR:** Do you take metforma?\n**PATIENT:** I take metforma and glucoform now and then.\n"
REF = build(SCRIPT)
NAMES = {"metforma": 2, "glucoform": 1}


def page_of(*texts):
    lines = model_lines.lines_of([{"speaker": "S1", "start": float(i), "end": i + 0.9, "text": t} for i, t in enumerate(texts)])
    return who.line_page(lines, REF), lines


A, A_LINES = page_of("Do you take metformo?", "I take dormirex and glucoform now sometimes then.")
B, _ = page_of("Do you take metforma?", "I take metforma and glucoform now and then.")


def test_ruling_2_every_mark_is_put_in_one_of_four_places_and_a_name_with_nothing_in_its_place_is_counted_apart():
    found = doubt.drug_occurrences(A, REF, NAMES)
    assert [(o["name"], o["caught"], o["written"]) for o in found] == [("glucoform", True, "glucoform"), ("metforma", False, "metformo"), ("metforma", False, "dormirex")]
    page_words = {w: i for i, w in enumerate(A.words)}
    way = doubt.counted(A, [{"word": page_words["metformo"]}, {"word": page_words["sometimes"]}, {"word": page_words["now"]}], found)
    assert way["places"] == {"drug_name_wrong": 1, "other_word_wrong": 1, "word_right": 1, "nowhere": 0}
    assert way["names_written_wrongly"] == 2 and way["names_marked"] == 1 and way["names_missing"] == 0
    assert [(m["text"], m["line"], m["place"], m["name"]) for m in way["marks"]] == [
        ("metformo", 1, "drug_name_wrong", "metforma"), ("sometimes", 2, "other_word_wrong", None), ("now", 2, "word_right", None)]
    # A name with nothing in its place, and a word from nowhere.
    C, _ = page_of("Do you take?", "I take metforma and glucoform now and then please.")
    found_c = doubt.drug_occurrences(C, REF, NAMES)
    way_c = doubt.counted(C, [{"word": len(C.words) - 1}], found_c)
    assert way_c["names_missing"] == 1 and way_c["places"]["nowhere"] == 1 and way_c["names_written_wrongly"] == 0


def test_the_list_marks_a_word_close_to_a_name_of_one_word(tmp_path):
    drugs = made_up_list(tmp_path)
    found = doubt.drug_occurrences(A, REF, NAMES)
    way = doubt.by_list(A, found, drugs)
    assert [(m["text"], m["close_to"], m["place"]) for m in way["marks"]] == [("metformo", "metforma", "drug_name_wrong")]
    assert way["names_marked"] == 1 and way["names_written_wrongly"] == 2          # dormirex is a name of the list: no mark
    # A page word in the list only as a brand is listed, so an everyday word that stopped a mark can be seen.
    assert way["brand_only"] == [{"word": 8, "text": "glucoform", "line": 2, "name": "glucoform"}]


def test_the_second_listen_marks_where_two_pages_of_the_same_sound_differ():
    found_a = doubt.drug_occurrences(A, REF, NAMES)
    on_a = doubt.by_second_listen(A, B, found_a)
    assert [(m["text"], m["other"], m["place"]) for m in on_a["marks"]] == [
        ("metformo", "metforma", "drug_name_wrong"), ("dormirex", "metforma", "drug_name_wrong"), ("sometimes", "and", "other_word_wrong")]
    assert on_a["names_marked"] == 2 and on_a["places_with_no_word"] == 0
    found_b = doubt.drug_occurrences(B, REF, NAMES)
    on_b = doubt.by_second_listen(B, A, found_b)
    assert on_b["places"] == {"drug_name_wrong": 0, "other_word_wrong": 0, "word_right": 3, "nowhere": 0}   # the cost of the way
    # A word the other page has and this page lacks has no word to mark.
    C, _ = page_of("Do you take?", "I take metforma and glucoform now and then.")
    on_c = doubt.by_second_listen(C, B, doubt.drug_occurrences(C, REF, NAMES))
    assert on_c["places_with_no_word"] == 1 and on_c["marks"] == []
    assert doubt.SECOND_LISTEN == {"whisperx_pyannote": "nemotron", "nemotron": "whisperx_pyannote"}


def test_ruling_18_the_models_marks_and_whether_the_medicine_it_named_was_right_wrong_or_empty():
    found = doubt.drug_occurrences(A, REF, NAMES)
    kept = [{"line": 1, "heard": "metformo", "meant": "Metforma"}, {"line": 2, "heard": "dormirex", "meant": "glucoform"},
            {"line": 2, "heard": "glucoform now", "meant": ""}]
    way = doubt.by_model(A, kept, found)
    assert [(m["text"], m["place"], m.get("meant_outcome")) for m in way["marks"]] == [
        ("metformo", "drug_name_wrong", "right"), ("dormirex", "drug_name_wrong", "wrong"),
        ("glucoform", "word_right", None), ("now", "word_right", None)]
    assert way["meant"] == {"right": 1, "wrong": 1, "empty": 0} and way["names_marked"] == 2
    empty = doubt.by_model(A, [{"line": 1, "heard": "metformo", "meant": ""}], found)
    assert empty["meant"] == {"right": 0, "wrong": 0, "empty": 1}


def test_ruling_16_the_three_classes_of_a_name_not_caught(tmp_path):
    drugs = made_up_list(tmp_path)
    classes = doubt.classes_of(doubt.drug_occurrences(A, REF, NAMES), drugs)
    assert [(r["name"], r["speech"], r["written"], r["class"]) for r in classes["rows"]] == [
        ("metforma", 1, "metformo", "garbled"), ("metforma", 2, "dormirex", "real_drug_not_spoken")]
    assert (classes["missing"], classes["garbled"], classes["real_drug_not_spoken"]) == (0, 1, 1)
    C, _ = page_of("Do you take?", "I take metforma and glucoform now and then.")
    assert doubt.classes_of(doubt.drug_occurrences(C, REF, NAMES), drugs)["rows"] == [
        {"name": "metforma", "speech": 1, "written": "", "class": "missing"}]
    # One word of a longer name in a drug's place is garbled, not a real drug (the plan review, change 1).
    D, _ = page_of("Do you take night?", "I take metforma and glucoform now and then.")
    assert doubt.classes_of(doubt.drug_occurrences(D, REF, NAMES), drugs)["rows"][0]["class"] == "garbled"
