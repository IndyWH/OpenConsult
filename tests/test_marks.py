"""The marks of part one on made-up words (spec 13.3 marks 1 to 4; 15.9
rulings 1, 12, 13 and 16; V1_LESSONS 1.5). No model, no recording."""

from openconsult.bench.speech import marks
from openconsult.bench.speech.pages import build_page, pages_of, pauses_of
from openconsult.bench.speech.reference import build
from openconsult.speech.missing import Gap, Stretch

SCRIPT = ("**DOCTOR:** If you get this pain at rest, go straight to the hospital, to the emergency department. Understood?\n"
          "**PATIENT:** Understood. I take metformin, gliclazide and co-codamol, eighty milligrams.\n"
          "**DOCTOR:** Heart sounds are normal, no murmurs. Blood pressure one hundred and fifty over ninety five.\n"
          "**PATIENT:** I couldn't really feel it properly.\n")
REF = build(SCRIPT)
REST = "I take metformin, gliclazide and co-codamol, eighty milligrams. Heart sounds are normal, no murmurs. Blood pressure one hundred and fifty over ninety five. I couldn't really feel it properly."


def piece(start, end, text, speaker=None):
    return {"start": start, "end": end, "text": text, "speaker": speaker}


def page_of(*pieces, name="stop"):
    return build_page(name, list(pieces), REF)


def test_ruling_13_a_passage_is_five_or_more_spoken_words_the_page_does_not_hold():
    # Nine words dropped after "at rest,": a passage, in a safety-net speech, with no sign.
    dropped = page_of(piece(0.0, 2.0, "If you get this pain at rest,", "A"),
                      piece(6.0, 7.0, "Understood? Understood.", "A"), piece(7.0, 12.0, REST, "B"))
    found = marks.passages(dropped, REF, set(), [1], [], None, [], 8.0)
    assert len(found) == 1 and found[0]["words"][:3] == ["go", "straight", "to"] and found[0]["missing"] == 9
    assert found[0]["safety_net"] and found[0]["speeches"] == [1] and found[0]["sign"] is False
    assert found[0]["window"] == [2.0, 6.0] and found[0]["same_piece"] is False
    # Five words garbled into five others are not a passage; four dropped are not.
    garbled = page_of(piece(0.0, 4.0, "If you get this pain at rest, go stray tour that hospice to the emergency department understood"), piece(4.0, 9.0, REST))
    assert marks.passages(garbled, REF, set(), [], [], None, [], 8.0) == []
    four = page_of(piece(0.0, 4.0, "If you get this pain at rest, go straight to the hospital department understood"), piece(4.0, 9.0, REST))
    assert marks.passages(four, REF, set(), [], [], None, [], 8.0) == []
    # Seven dropped with two in their place: 5 missing, a passage.
    seven = page_of(piece(0.0, 4.0, "If you get this pain at rest, go wrong word department understood"), piece(4.0, 9.0, REST))
    assert [(p["spoken"], p["in_place"], p["missing"]) for p in marks.passages(seven, REF, set(), [], [], None, [], 8.0)] == [(7, 2, 5)]
    # An agreed place is taken as spoken that way: it does not start a passage.
    assert marks.passages(seven, REF, set(range(7, 14)), [], [], None, [], 8.0) == []


def test_hard_mark_1_a_passage_with_a_sign_is_told_from_one_without():
    dropped = page_of(piece(0.0, 2.0, "If you get this pain at rest,"), piece(6.0, 7.0, "Understood? Understood."),
                      piece(7.0, 12.0, REST))
    live = page_of(piece(0.0, 2.0, "If you get this pain at rest,"),
                   piece(2.0, 6.0, "go straight to the hospital to the emergency department"), name="live")
    gap = Gap(("go", "straight", "to", "the", "hospital", "to", "the", "emergency", "department"), 2.0, 6.0, 7)
    by_gap = marks.passages(dropped, REF, set(), [], [gap], live, [], 8.0)[0]
    assert by_gap["sign"] and by_gap["gap"] == [[2.0, 6.0]] and by_gap["stretch"] == []
    by_stretch = marks.passages(dropped, REF, set(), [], [], None, [Stretch(2.5, 5.5)], 8.0)[0]
    assert by_stretch["sign"] and by_stretch["stretch"] == [[2.5, 5.5]]
    elsewhere = marks.passages(dropped, REF, set(), [], [], None, [Stretch(6.5, 9.0)], 8.0)[0]
    assert elsewhere["sign"] is False
    # Words before and after in one piece: a stretch cannot see inside it.
    inside = page_of(piece(0.0, 7.0, "If you get this pain at rest, understood? Understood."), piece(7.0, 12.0, REST))
    unseen = marks.passages(inside, REF, set(), [], [], None, [Stretch(2.0, 6.0)], 8.0)[0]
    assert unseen["same_piece"] and unseen["sign"] is False and unseen["window"] == [0.0, 7.0]
    # A wrong gap, whose live words stand elsewhere, is no sign for this passage.
    wrong = Gap(("if", "you", "get", "this", "pain"), 0.0, 2.0, 0)
    assert marks.passages(dropped, REF, set(), [], [wrong], live, [], 8.0)[0]["sign"] is False


def test_ruling_13_a_word_from_silence_lies_wholly_in_a_pause_looking_as_wide_as_the_times_allow():
    quiet, loud = None, -20.0
    windows = [loud] * 10 + [quiet] * 40 + [loud] * 10          # a pause from 1.0 to 5.0 s
    assert pauses_of(windows, 0.1) == [(1.0, 5.0)]
    assert pauses_of([loud] * 10 + [quiet] * 19 + [loud] * 10, 0.1) == []      # 1.9 s is no pause
    assert pauses_of([-45.0] * 25, 0.1) == [(0.0, 2.5)]                          # at or below -40 is quiet
    page = page_of(piece(0.0, 1.0, "If you get this pain at rest, go straight to the hospital, to the emergency department. Understood?"),
                   piece(2.0, 2.5, "Thank you."), piece(4.5, 5.0, "Bye."), piece(5.0, 8.0, "Understood. " + REST))
    exact = marks.words_from_silence(page, windows, 0.1, slack_s=0.0)
    assert [w["word"] for w in exact] == ["thank", "you", "bye"] and exact[0]["pause"] == [1.0, 5.0]
    wide = marks.words_from_silence(page, windows, 0.1, slack_s=1.0)
    assert [w["word"] for w in wide] == ["thank", "you"]         # 3.5 to 6.0 is not inside the pause
    # A spoken word in the pause is not a word from silence.
    spoken = page_of(piece(2.0, 2.5, "If you"))
    assert marks.words_from_silence(spoken, windows, 0.1, slack_s=0.0) == []


def test_ruling_12_real_words_refused_and_invented_words_let_through_are_counted():
    windows = [-20.0] * 10 + [None] * 40 + [-20.0] * 10
    page = page_of(piece(0.0, 1.0, "If you get this pain at rest"), piece(2.0, 2.5, "Thank you."),
                   piece(5.0, 6.0, "go straight to the hospital"))
    refused = [{"line": {"start": 1.0, "end": 1.6, "text": "go straight"}, "loudest_dbfs": None},
               {"line": {"start": 3.0, "end": 3.4, "text": "Bye bye"}, "loudest_dbfs": None}]
    did = marks.rule_did(page, refused, REF, windows, 0.1, slack_s=1.0)
    assert did["real_words_refused"] == ["go", "straight"] and did["refused_lines"] == 2
    assert [w["word"] for w in did["invented_let_through"]] == ["thank", "you"]
    assert marks.rule_did(page, refused, REF, windows, 0.1, slack_s=0.0)["invented_let_through"] == []


def test_V1_LESSONS_1_5_negations_lost_and_added_and_numbers_changed_are_counted():
    page = page_of(piece(0.0, 2.0, "If you get this pain at rest, go straight to the hospital, to the emergency department. Understood? "
                                   "Understood. I take metformin, gliclazide and co-codamol, 80 mg."),
                   piece(2.0, 3.0, "Heart sounds are normal, normalist. Blood pressure 115 over 95."),
                   piece(3.0, 4.0, "I can really feel it properly, no doubt."))
    found = marks.differ(page, REF, set())
    kinds = [(p["kind"], p["spoken"], p["written"]) for p in found["places"]]
    assert ("replaced", "150", "115") in kinds and ("replaced", "couldn't", "can") in kinds
    assert [p["spoken"] for p in found["negations_lost"]] == ["no", "couldn't"]
    assert [p["written"] for p in found["negations_added"]] == ["no"]
    assert [(p["spoken"], p["written"]) for p in found["numbers_changed"]] == [("150", "115")]
    assert all(p["speech"] in (3, 4) for p in found["places"] if p["spoken"]) and found["places"][0]["context"]
    # An agreed place is left out of the lists.
    agreed = {REF.norms.index("no")}
    assert "no" not in [p["spoken"] for p in marks.differ(page, REF, agreed)["negations_lost"]]


def test_13_3_mark_3_drug_names_are_matched_as_whole_words_and_the_bracket_form_counts_as_caught():
    names = {"metformin": 1, "gliclazide": 1, "co-codamol": 1, "triptan": 0}
    page = page_of(piece(0.0, 2.0, "I take metformins, glyclazide and co codamol, 80mg."))
    found = marks.drug_names(page, REF, names, in_line=["metformin", "gliclazide"])
    rows = {r["name"]: r for r in found["rows"]}
    assert rows["metformin"]["caught"] and rows["metformin"]["how"] == "plural or possessive"
    assert not rows["gliclazide"]["caught"] and rows["gliclazide"]["written"] == "glyclazide" and rows["gliclazide"]["how"] == "garbled"
    assert rows["co-codamol"]["caught"] and rows["co-codamol"]["how"] == "heard"      # split words joined
    assert found["spoken"] == 3 and found["caught"] == 2
    assert found["in_line"] == {"spoken": 2, "caught": 1} and found["not_in_line"] == {"spoken": 1, "caught": 1}
    missing = marks.drug_names(page_of(piece(0.0, 1.0, "I take and")), REF, names, [])
    assert {r["name"]: r["how"] for r in missing["rows"]} == {"co-codamol": "missing", "gliclazide": "missing", "metformin": "missing"}
    # Whole words: sumatriptan on the page does not count for triptan.
    ref = build("**DOCTOR:** try a triptan today\n")
    page = build_page("stop", [piece(0.0, 1.0, "try a sumatriptan today")], ref)
    assert marks.drug_names(page, ref, {"triptan": 1}, [])["rows"][0]["how"] == "garbled"
    # The bracket form: both names spoken, written as X (Y): both caught.
    ref = build("**DOCTOR:** You are on semaglutide now.\n**PATIENT:** The Ozempic injection?\n")
    page = build_page("stop", [piece(0.0, 2.0, "You are on Semaglutide (Ozempic) now. The injection?")], ref)
    found = marks.drug_names(page, ref, {"semaglutide": 1, "Ozempic": 1}, [])
    assert {r["name"]: (r["caught"], r["how"]) for r in found["rows"]} == {"Ozempic": (True, "bracket form"), "semaglutide": (True, "heard")}
    alone = build_page("stop", [piece(0.0, 2.0, "You are on Semaglutide (Humalog) now. The injection?")], ref)
    assert {r["name"]: r["how"] for r in marks.drug_names(alone, ref, {"semaglutide": 1, "Ozempic": 1}, [])["rows"]} == {"Ozempic": "missing", "semaglutide": "heard"}


def test_13_3_mark_4_labels_are_matched_to_doctor_and_patient_by_best_fit():
    page = page_of(piece(0.0, 2.0, "If you get this pain at rest, go straight to the hospital", "S2"),
                   piece(2.0, 3.0, "Understood. I take metformin", "S1"),
                   piece(3.0, 4.0, "Heart sounds are normal", "S2"),
                   piece(4.0, 5.0, "I couldn't really feel it", None),
                   piece(5.0, 5.5, "properly", "S3"))
    found = marks.who_spoke(page, REF)
    assert found["mapping"] == {"S2": "DOCTOR", "S1": "PATIENT"} and found["labels"] == ["S1", "S2", "S3"]
    assert (found["right"], found["wrong"], found["no_speaker"]) == (20, 1, 5)
    swapped = page_of(piece(0.0, 2.0, "If you get this pain at rest", "B"), piece(2.0, 3.0, "I take metformin", "A"))
    assert marks.who_spoke(swapped, REF)["mapping"] == {"B": "DOCTOR", "A": "PATIENT"}
    one = page_of(piece(0.0, 2.0, "If you get this pain at rest", "X"))
    assert marks.who_spoke(one, REF)["mapping"] == {"X": "DOCTOR"}


def test_the_pages_of_a_result_are_the_raw_segments_at_stop_and_the_live_lines():
    result = {"pieces": [{"lines": [{"start": 0.0, "end": 1.0, "text": "If you get"}]}],
              "stop": {"lines": [{"start": 0.0, "end": 2.0, "text": "If you get this pain", "speaker": "S0"}],
                       "last_live": [{"start": 1.0, "end": 2.0, "text": "this pain"}],
                       "raw": [{"start": 0.0, "end": 1.0, "text": "If you get", "refused": False,
                                "words": [{"word": "If", "speaker": "S0"}]},
                               {"start": 1.0, "end": 2.0, "text": "this pain", "refused": False, "words": []},
                               {"start": 5.0, "end": 5.5, "text": "Thank you.", "refused": True, "words": []}]}}
    pages = pages_of(result, REF)
    assert [p["text"] for p in pages["stop"].pieces] == ["If you get", "this pain"]      # the refused segment is out
    assert pages["stop"].pieces[0]["speaker"] == "S0" and pages["stop"].pieces[1]["speaker"] is None
    assert [p["text"] for p in pages["live"].pieces] == ["If you get", "this pain"]
    assert pages["stop"].words == ["if", "you", "get", "this", "pain"] and pages["stop"].word_piece == [0, 0, 0, 1, 1]
    one_transcript = {"pieces": [], "stop": {"lines": [{"start": 0.0, "end": 1.0, "text": "If you", "speaker": "A"}],
                                              "last_live": [], "raw": []}}
    assert list(pages_of(one_transcript, REF)) == ["stop"]
