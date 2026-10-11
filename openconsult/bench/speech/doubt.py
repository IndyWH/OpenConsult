"""Three ways to spot a doubtful drug name, counted alike, and the three
classes of a name that was not caught (spec 15.9, rulings 2, 16 and 18;
the details of part two of 5c). The list, the second listen and the
language model each give marks on words of the page. Every mark is put in
one of four places: on a drug name that was spoken and written wrongly, on
another word that was written wrongly, on a word that was written rightly,
or on a word standing where nothing was spoken. A name with nothing in its
place cannot be marked and is counted apart. The list and the second listen
are worked out by code from the stored results and the stored list; the
language model's marks come from its stored replies."""

from __future__ import annotations

from openconsult.bench.speech import marks
from openconsult.bench.speech.druglist import DrugList, doubtful_by_list
from openconsult.bench.speech.pages import Page
from openconsult.bench.speech.reference import Reference, occurrences
from openconsult.speech.matching import align, normalise

PLACES = ("drug_name_wrong", "other_word_wrong", "word_right", "nowhere")
CLASSES = ("missing", "garbled", "real_drug_not_spoken")
# The second listen pairs the two local choices' pages at Stop (the details).
SECOND_LISTEN = {"whisperx_pyannote": "nemotron", "nemotron": "whisperx_pyannote"}


def drug_occurrences(page: Page, reference: Reference, names: dict) -> list[dict]:
    """Each time a drug name of the marks file is spoken: the page words in
    its place, and whether part one counts it as caught."""
    rows = marks.drug_names(page, reference, names, [])["rows"]
    found, at = [], 0
    for norm in sorted({" ".join(normalise(n)) for n in names}):
        for first, last in occurrences(reference, norm):
            row = rows[at]
            at += 1
            page_words = [page.at_spoken[i] for i in range(first, last + 1) if i in page.at_spoken]
            found.append({"name": row["name"], "spoken": norm, "first": first, "last": last, "speech": row["speech"],
                          "caught": row["caught"], "how": row["how"], "page_words": page_words,
                          "written": " ".join(page.words[w] for w in page_words)})
    return found


def place_of(page: Page, word: int, name_words: dict[int, int]) -> str:
    kind = page.kind_of.get(word)
    if kind == "nowhere":
        return "nowhere"
    if kind == "heard":
        return "word_right"
    return "drug_name_wrong" if word in name_words else "other_word_wrong"


def counted(page: Page, found: list[dict], occurrences_found: list[dict], extra=None) -> dict:
    """The marks of one way in their four places, and of the drug names
    written wrongly how many the way marked."""
    name_words = {w: index for index, occ in enumerate(occurrences_found) for w in occ["page_words"]}
    places = {place: 0 for place in PLACES}
    listed = []
    for mark in found:
        word = mark["word"]
        place = place_of(page, word, name_words)
        places[place] += 1
        listed.append({**mark, "text": page.words[word], "line": page.word_piece[word] + 1, "place": place,
                       "name": occurrences_found[name_words[word]]["name"] if word in name_words else None})
    wrong = [occ for occ in occurrences_found if not occ["caught"] and occ["page_words"]]
    marked_words = {m["word"] for m in found}
    marked = [occ for occ in wrong if any(w in marked_words for w in occ["page_words"])]
    return {"places": places, "marks": listed, "names_written_wrongly": len(wrong), "names_marked": len(marked),
            "names_missing": sum(1 for occ in occurrences_found if not occ["caught"] and not occ["page_words"]),
            **(extra or {})}


# ------------------------------------------------------------- the three ways

def by_list(page: Page, occurrences_found: list[dict], drugs: DrugList) -> dict:
    found = doubtful_by_list(page.words, drugs)
    in_doubt = [m for m in found if "close_to" in m]
    brand_only = [{"word": m["word"], "text": page.words[m["word"]], "line": page.word_piece[m["word"]] + 1, "name": m["brand_only"]}
                  for m in found if "brand_only" in m]
    return counted(page, in_doubt, occurrences_found, {"brand_only": brand_only})


def by_second_listen(page: Page, other: Page, occurrences_found: list[dict]) -> dict:
    """The places where this page and the other page of the same sound
    differ, with no script: a mark on each page word that stands in place
    of a word of the other page or where the other page has nothing; a
    word the other page has and this page lacks has no word to mark."""
    found, lacking = [], 0
    for pair in align(other.words, page.words):
        if pair.kind in ("replaced", "nowhere"):
            found.append({"word": pair.page, "other": other.words[pair.spoken] if pair.spoken is not None else None})
        elif pair.kind == "missing":
            lacking += 1
    return counted(page, found, occurrences_found, {"places_with_no_word": lacking})


def by_model(page: Page, kept: list[dict], occurrences_found: list[dict]) -> dict:
    """The language model's kept entries as marks on the page words of their
    line that are among the heard words; for a mark on a drug name written
    wrongly, whether the medicine it named was the right one, a wrong one,
    or left empty."""
    found = []
    for entry in kept:
        heard = set(normalise(entry["heard"]))
        line_index = int(entry["line"]) - 1
        for word in range(len(page.words)):
            if page.word_piece[word] == line_index and page.words[word] in heard:
                found.append({"word": word, "meant": entry.get("meant", "")})
    result = counted(page, found, occurrences_found)
    meant = {"right": 0, "wrong": 0, "empty": 0}
    by_word = {w: occ for occ in occurrences_found for w in occ["page_words"]}
    for mark in result["marks"]:
        if mark["place"] != "drug_name_wrong":
            continue
        said = " ".join(normalise(mark["meant"]))
        outcome = "empty" if not said else ("right" if said == by_word[mark["word"]]["spoken"] else "wrong")
        mark["meant_outcome"] = outcome
        meant[outcome] += 1
    result["meant"] = meant
    return result


# -------------------------------------------------------------- the classes

def classes_of(occurrences_found: list[dict], drugs: DrugList) -> dict:
    """Each drug name not caught: missing, garbled, or a real drug that is
    not the one spoken (ruling 16), listed with its line."""
    rows = []
    for occ in occurrences_found:
        if occ["caught"]:
            continue
        written = occ["written"].split()
        if not written:
            kind = "missing"
        elif drugs.is_whole_name(written) and " ".join(written) != occ["spoken"]:
            kind = "real_drug_not_spoken"
        else:
            kind = "garbled"
        rows.append({"name": occ["name"], "speech": occ["speech"], "written": occ["written"], "class": kind})
    return {"rows": rows, **{kind: sum(1 for r in rows if r["class"] == kind) for kind in CLASSES}}
