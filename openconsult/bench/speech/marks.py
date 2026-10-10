"""The marks of part one (spec 13.3 marks 1 to 4; 15.9 rulings 1, 12, 13,
16; V1_LESSONS 1.5). All by code from a stored result and the reference;
no model marks anything. Each mark gives lists for reading and counts
beside them; code does not judge whether a meaning changed."""

from __future__ import annotations

import re

from openconsult.bench.speech.pages import Page, loudest_in, pauses_of
from openconsult.bench.speech.reference import Reference, occurrences
from openconsult.speech.loudness import QUIET_DBFS
from openconsult.speech.matching import normalise
from openconsult.speech.missing import LEAST_WORDS, Gap, Stretch

# The words that count as a negation (V1_LESSONS 1.5; 13.3 mark 2).
NEGATIONS = frozenset("no not never none nothing nobody nowhere neither nor without don't doesn't didn't can't "
                      "cannot couldn't won't wouldn't shouldn't isn't aren't wasn't weren't haven't hasn't hadn't "
                      "mustn't needn't".split())
_NUMBER = re.compile(r"^\d+(\.\d+)?$")
_BRACKETS = re.compile(r"([A-Za-z][\w-]*)\s*\(([A-Za-z][\w-]*)\)")


def _outcome(page: Page, index: int) -> str:
    """heard, replaced or missing, for one reference word."""
    at = page.at_spoken.get(index)
    return "missing" if at is None else page.kind_of[at]


def _window(page: Page, first: int, last: int, n_spoken: int, end_s: float) -> tuple[float, float, bool]:
    """The time of a passage: from the piece of the last heard page word
    before it to the piece of the first heard word after it. When both sit
    in one piece no stretch can see inside it, and the window is that piece."""
    before = [page.at_spoken[i] for i in range(first - 1, -1, -1) if _outcome(page, i) == "heard"][:1]
    after = [page.at_spoken[i] for i in range(last + 1, n_spoken) if _outcome(page, i) == "heard"][:1]
    if before and after and page.word_piece[before[0]] == page.word_piece[after[0]]:
        piece = page.pieces[page.word_piece[before[0]]]
        return piece["start"], piece["end"], True
    start = page.pieces[page.word_piece[before[0]]]["end"] if before else 0.0
    end = page.pieces[page.word_piece[after[0]]]["start"] if after else end_s
    return start, end, False


def passages(page: Page, reference: Reference, agreed: set[int], safety_nets: list[int], gaps: list[Gap],
             gap_page: Page | None, stretches: list[Stretch], end_s: float, least: int = LEAST_WORDS) -> list[dict]:
    """Hard mark 1. A run of spoken words the page does not hold, in which
    at least `least` more words were spoken than the page holds in their
    place. A gap covers it when one of its live words stands at a spoken
    word of the run; a stretch when it overlaps the run's time."""
    found, run = [], []
    for index in range(len(reference.words) + 1):
        if index < len(reference.words) and index not in agreed and _outcome(page, index) != "heard":
            run.append(index)
            continue
        if run:
            in_place = sum(1 for i in run if _outcome(page, i) == "replaced")
            if len(run) - in_place >= least:
                found.append(_passage(page, reference, run, in_place, safety_nets, gaps, gap_page, stretches, end_s))
        run = []
    return found


def _passage(page, reference, run, in_place, safety_nets, gaps, gap_page, stretches, end_s) -> dict:
    start, end, same = _window(page, run[0], run[-1], len(reference.words), end_s)
    gap_hits = []
    for gap in gaps:
        live_words = range(gap.first_live_word, gap.first_live_word + len(gap.words))
        if gap_page and any(gap_page.spoken_of.get(w) in run for w in live_words):
            gap_hits.append([gap.start_s, gap.end_s])
    stretch_hits = [[s.start_s, s.end_s] for s in stretches if not same and s.start_s < end and s.end_s > start]
    speeches = sorted({reference.words[i].speech for i in run})
    return {"words": [reference.words[i].norm for i in run], "speeches": speeches, "spoken": len(run),
            "in_place": in_place, "missing": len(run) - in_place,
            "safety_net": any(s in safety_nets for s in speeches), "window": [round(start, 3), round(end, 3)],
            "same_piece": same, "gap": gap_hits, "stretch": stretch_hits, "sign": bool(gap_hits or stretch_hits)}


def words_from_silence(page: Page, windows: list[float | None], window_s: float, slack_s: float) -> list[dict]:
    """Hard mark 2. A page word standing where nothing was spoken, whose
    piece, widened by the choice's slack, lies wholly inside a pause."""
    pauses = pauses_of(windows, window_s)
    found = []
    for word, kind in page.kind_of.items():
        if kind != "nowhere":
            continue
        piece = page.pieces[page.word_piece[word]]
        start, end = piece["start"] - slack_s, piece["end"] + slack_s
        for p_start, p_end in pauses:
            if start >= p_start and end <= p_end:
                found.append({"word": page.words[word], "piece": [piece["start"], piece["end"], piece["text"]],
                              "pause": [p_start, p_end]})
                break
    return found


def rule_did(page: Page, refused: list[dict], reference: Reference, windows, window_s, slack_s: float) -> dict:
    """Ruling 12: the real words the rule refused, and the invented words
    it let through by looking wider. The refused lines are aligned in time
    order with the page, so their words are classed in context."""
    merged = sorted([(p["start"], p["text"], False) for p in page.pieces]
                    + [(r["line"]["start"], r["line"]["text"], True) for r in refused], key=lambda t: t[0])
    tokens, is_refused = [], []
    for _, text, flag in merged:
        words = normalise(text, reference.joinable)
        tokens += words
        is_refused += [flag] * len(words)
    from openconsult.speech.matching import align
    real = [tokens[p.page] for p in align(reference.norms, tokens)
            if p.page is not None and is_refused[p.page] and p.kind in ("heard", "replaced")]
    let_through = []
    if slack_s > 0:
        for word, kind in page.kind_of.items():
            piece = page.pieces[page.word_piece[word]]
            loudest = loudest_in(windows, window_s, piece["start"], piece["end"])
            if kind == "nowhere" and (loudest is None or loudest <= QUIET_DBFS):
                let_through.append({"word": page.words[word], "piece": [piece["start"], piece["end"], piece["text"]],
                                    "loudest_dbfs": loudest})
    return {"real_words_refused": real, "refused_lines": len(refused), "invented_let_through": let_through}


def differ(page: Page, reference: Reference, agreed: set[int]) -> dict:
    """Mark 2: every place the page differs from what was spoken, with
    the words around it, and on their own the negations lost and added
    and the numbers changed."""
    places, lost, added, numbers = [], [], [], []
    norms = reference.norms
    for pair in page.pairs:
        if pair.kind == "heard" or pair.spoken in agreed:
            continue
        spoken = norms[pair.spoken] if pair.spoken is not None else None
        written = page.words[pair.page] if pair.page is not None else None
        centre = pair.spoken if pair.spoken is not None else _nearest_spoken(page, pair.page)
        context = " ".join(norms[max(0, centre - 3):centre + 4]) if centre is not None else ""
        speech = reference.words[pair.spoken].speech if pair.spoken is not None else None
        time = page.pieces[page.word_piece[pair.page]]["start"] if pair.page is not None else None
        place = {"kind": pair.kind, "spoken": spoken, "written": written, "speech": speech, "context": context, "time": time}
        places.append(place)
        if spoken in NEGATIONS and written not in NEGATIONS:
            lost.append(place)
        if written in NEGATIONS and spoken not in NEGATIONS:
            added.append(place)
        if spoken is not None and _NUMBER.match(spoken) and written != spoken:
            numbers.append(place)
    return {"places": places, "negations_lost": lost, "negations_added": added, "numbers_changed": numbers}


def _nearest_spoken(page: Page, word: int) -> int | None:
    for other in range(word - 1, -1, -1):
        if other in page.spoken_of:
            return page.spoken_of[other]
    return None


def _bracket_pairs(page: Page, names: set[str]) -> set[str]:
    """The names written in the bracket form X (Y) where both are names
    of the script: generic and brand, both spoken, count as caught."""
    found = set()
    for piece in page.pieces:
        for x, y in _BRACKETS.findall(piece["text"]):
            nx, ny = " ".join(normalise(x)), " ".join(normalise(y))
            if nx in names and ny in names:
                found |= {nx, ny}
    return found


def drug_names(page: Page, reference: Reference, names: dict[str, int], in_line: list[str]) -> dict:
    """Mark 3 (ruling 16). Each time a name is spoken: on the page as a
    whole word, or what stands in its place. A plural or possessive ending
    counts as caught and is flagged; the bracket form counts as caught."""
    norm_names = {" ".join(normalise(n)): n for n in names}
    bracketed = _bracket_pairs(page, set(norm_names))
    in_line_norm = {" ".join(normalise(n)) for n in in_line}
    spoken_names = {n for n in norm_names if occurrences(reference, n)}
    rows = []
    for norm, name in sorted(norm_names.items()):
        for first, last in occurrences(reference, norm):
            kinds = [_outcome(page, i) for i in range(first, last + 1)]
            written = [page.words[page.at_spoken[i]] for i in range(first, last + 1) if i in page.at_spoken]
            row = {"name": name, "speech": reference.words[first].speech, "in_v1_line": norm in in_line_norm,
                   "caught": all(k == "heard" for k in kinds), "written": " ".join(written), "how": "heard"}
            if not row["caught"] and len(written) == 1 and written[0] in (norm + "s", norm + "'s", norm + "es"):
                row.update(caught=True, how="plural or possessive")
            elif not row["caught"] and norm in bracketed and len(bracketed & spoken_names) >= 2:
                row.update(caught=True, how="bracket form")
            elif not row["caught"]:
                row["how"] = "garbled" if written else "missing"
            rows.append(row)
    return {"rows": rows, "spoken": len(rows), "caught": sum(r["caught"] for r in rows),
            "in_line": {"spoken": sum(r["in_v1_line"] for r in rows), "caught": sum(r["caught"] and r["in_v1_line"] for r in rows)},
            "not_in_line": {"spoken": sum(not r["in_v1_line"] for r in rows),
                            "caught": sum(r["caught"] and not r["in_v1_line"] for r in rows)}}


def who_spoke(page: Page, reference: Reference) -> dict:
    """Mark 4. The choice's labels matched to DOCTOR and PATIENT by best
    fit, as the doctor's answer to Who spoke? would; then words right,
    wrong and with no speaker."""
    counts: dict[str, dict[str, int]] = {}
    for word, spoken in page.spoken_of.items():
        label = page.pieces[page.word_piece[word]]["speaker"]
        if label is not None:
            counts.setdefault(str(label), {}).setdefault(reference.words[spoken].speaker, 0)
            counts[str(label)][reference.words[spoken].speaker] += 1
    top = sorted(counts, key=lambda l: -sum(counts[l].values()))[:2]
    mapping: dict[str, str] = {}
    if len(top) == 1:
        mapping[top[0]] = max(counts[top[0]], key=counts[top[0]].get)
    elif len(top) == 2:
        a, b = top
        straight = counts[a].get("DOCTOR", 0) + counts[b].get("PATIENT", 0)
        crossed = counts[a].get("PATIENT", 0) + counts[b].get("DOCTOR", 0)
        mapping = {a: "DOCTOR", b: "PATIENT"} if straight >= crossed else {a: "PATIENT", b: "DOCTOR"}
    right = wrong = none = 0
    for word, spoken in page.spoken_of.items():
        label = page.pieces[page.word_piece[word]]["speaker"]
        if label is None:
            none += 1
        elif mapping.get(str(label)) == reference.words[spoken].speaker:
            right += 1
        else:
            wrong += 1
    return {"mapping": mapping, "right": right, "wrong": wrong, "no_speaker": none, "labels": sorted(counts)}
