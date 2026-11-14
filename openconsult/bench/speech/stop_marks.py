"""The marks of step 6c, from stored results alone (spec 15.10, ruling 22
and the details of step 6c: The bench of parts against whole, The bench
of Claude Haiku; 15.13 ruling 8). The label check read whole and in
parts, and the drug-name call, each page counted by the bench's own
counting of 5e (who.count, doubt.by_model) against the script: for the
local model, and for a cloud model beside it. P1 and P2 judge the parts
against the whole on the local model; H1, H2 and D1 to D3 hold a cloud
model to the local model's own line. Every stored reply is judged afresh
by the app's own check as it stands today (15.10 ruling 24; the details
of 6c2: The count again): the labels and the refusal stored with a
result were worked out by the rule of their day and are never read.
Counts only: no word of a page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import banked, calls, doubt, model_lines, pages, tables, who
from openconsult.bench.speech.commands import REPO
from openconsult.bench.speech.reference import build
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult import joined
from openconsult.consult.labels import check_labels
from openconsult.settings import paths

# P2: the parts may leave one more word under the wrong speaker for every this many words on the pages judged.
WORDS_FOR_ONE = 200
TAKEN, REFUSED, FAILED = "taken", "refused", "failed"
COUNTS = ("right", "wrong", "unsure", "nowhere")
RULE_COUNTS = ("named_twice", "dropped", "made_unsure_lines", "made_unsure_words")


RULE = "15.10 ruling 24"


class NotThePage(Exception):
    """A stored call whose text is not the text built again from the stored page."""


def judge(record: dict, lines: list[dict], in_parts: bool) -> tuple[str, dict[int, str] | None, dict]:
    """A stored reading judged afresh: how it ended, the labels of the
    page or none, and the counts of ruling 24. The page is cut again as
    the bench cut it and each stored reply goes through the app's check;
    first the stored text of every call is proven to be the text built
    again from the page, byte for byte."""
    parts = calls.halves(lines) if in_parts else [{"k": 1, "lines": lines, "overlap": 0}]
    asked = [p["call"] for p in record["parts"]] if in_parts else [record["call"]]
    user = [model_lines.lines_text(joined.numbered(part)) for part in parts]
    if (record["user"] if in_parts else [record["user"]]) != user or len(asked) != len(parts):
        raise NotThePage(f"{record.get('job')} on {record.get('arm')}, {record.get('recording')}")
    found = [check_labels(call["answer"], len(part["lines"])) if call["ok"] else None for part, call in zip(parts, asked)]
    answered = [(part, f) for part, f in zip(parts, found) if f is not None]
    counts = {"named_twice": sum(f[2]["named_twice"] for _, f in answered), "dropped": sum(f[2]["dropped"] for _, f in answered),
              "parts": len(parts), "parts_answered": len(answered), "parts_refused": sum(1 for _, f in answered if f[0] is None)}
    if len(answered) < len(parts):
        return FAILED, None, {**counts, "made_unsure": []}
    labels = joined.merge(parts, [f[0] for f in found])
    # A line made unsure is counted from the part its label is taken from, never from a part that carried it.
    made_unsure = sorted(part["lines"][i - 1]["n"] for part, f in answered for i in f[2]["made_unsure"] if i > part["overlap"])
    return (TAKEN if labels is not None else REFUSED), labels, {**counts, "made_unsure": made_unsure if labels is not None else []}


def words_on(page, lines: list[dict], numbers: list[int]) -> int:
    """The words that stand on these lines where something was spoken: the
    words who.count counts as unsure because of them."""
    on = set(numbers)
    return sum(1 for word in range(len(page.words))
               if page.spoken_of.get(word) is not None and lines[page.word_piece[word]]["n"] in on)


def reading(record: dict | None, lines: list[dict], page, reference, in_parts: bool = False) -> dict:
    """One reading of the label check on a page: how it ended by today's
    rule, its words under the right speaker, the wrong speaker and unsure,
    the lines named twice and the numbers dropped in its replies, the
    words on lines the rule made unsure, and for a reading in parts how
    many parts answered and how many were refused."""
    if record is None:
        return {"present": False}
    state, labels, counts = judge(record, lines, in_parts)
    made_unsure = counts.pop("made_unsure")
    found = {"present": True, "state": state, **who.count(page, reference, labels, lines),
             "named_twice": counts["named_twice"], "dropped": counts["dropped"], "made_unsure_lines": len(made_unsure),
             "made_unsure_words": words_on(page, lines, made_unsure),
             "other_keys": sum(1 for answer in _answers(record) for entry in (answer or {}).get("lines", [])
                               if set(entry) - {"line", "label"})}
    if in_parts:
        found.update(parts=counts["parts"], parts_answered=counts["parts_answered"], parts_refused=counts["parts_refused"])
    return found


def _answers(record: dict) -> list:
    return [p["call"].get("answer") for p in record["parts"]] if "parts" in record else [record["call"].get("answer")]


def drug_reading(record: dict | None, page, occurrences: list[dict]) -> dict:
    """The drug-name call on a page: whether it answered, the drug names
    written wrongly and how many it marked, its marks by place, and the
    entries code kept and dropped."""
    if record is None:
        return {"present": False}
    counted = doubt.by_model(page, record.get("kept") or [], occurrences)
    return {"present": True, "ok": bool(record["call"]["ok"]), "written_wrongly": counted["names_written_wrongly"],
            "marked": counted["names_marked"], "places": counted["places"], "kept": len(record.get("kept") or []),
            "dropped": len(record.get("dropped") or [])}


def model_readings(arm: str, name: str, whole: dict, parts: dict, drug: dict, lines, page, reference, occurrences) -> dict:
    chain = f"{arm}--{name}"
    return {"whole": reading(whole.get(("label_check", chain)), lines, page, reference),
            "parts": reading(parts.get(("label_check_parts", chain)), lines, page, reference, in_parts=True),
            "drug": drug_reading(drug.get(("drug_name", chain)), page, occurrences)}


def score_all(stored: dict, local: dict, local_whole: dict, local_parts: dict, cloud: dict | None,
              listed: list[banked.Recording], script_folders: list[Path], marks_file: dict) -> dict:
    """Every page of the stored results with each reading there is, the
    sums by kind of page, and the marks."""
    rows = []
    for (arm, name), result in sorted(stored.items()):
        if result.get("failure"):
            continue
        recording = banked.named(listed, name)
        reference = build(tables.find_script(recording, script_folders), recording.last_speech, recording.read_differently)
        lines = model_lines.lines_of(pages.stop_pieces(result))
        page = who.line_page(lines, reference)
        occurrences = doubt.drug_occurrences(page, reference, tables.entry_for(marks_file, recording.script_key).get("drugs", {}))
        row = {"arm": arm, "recording": name, "lines": len(lines), "words": len(page.words),
               "local": model_readings(arm, name, local_whole, local_parts, local, lines, page, reference, occurrences)}
        if cloud is not None:
            row["cloud"] = model_readings(arm, name, cloud, cloud, cloud, lines, page, reference, occurrences)
        rows.append(row)
    return {"rule": RULE, "pages": rows, "kinds": by_kind(rows), "marks": marks_of(rows)}


def _taken(rows: list[dict], model: str, name: str) -> list[dict]:
    return [r for r in rows if model in r and r[model][name].get("state") == TAKEN]


def _wrong(rows: list[dict], model: str, name: str, key: str = "wrong") -> int:
    return sum(r[model][name].get(key, 0) for r in rows)


def _page(row: dict) -> str:
    return f"{row['arm']} {row['recording']}"


def marks_of(rows: list[dict]) -> dict:
    """P1 and P2 where the local parts reading is there; H1, H2 and D1 to
    D3 where a cloud model's readings are. A page whose local whole reply
    was not taken is reported and not judged."""
    judged = _taken(rows, "local", "whole")
    marks: dict = {"judged": len(judged), "judged_words": sum(r["words"] for r in judged),
                   "not_judged": [_page(r) for r in rows if r not in judged]}
    if any(r["local"]["parts"]["present"] for r in rows):
        missed = [_page(r) for r in judged if r["local"]["parts"].get("state") != TAKEN]
        allowance = marks["judged_words"] // WORDS_FOR_ONE
        whole_wrong, parts_wrong = _wrong(judged, "local", "whole"), _wrong(judged, "local", "parts")
        marks["P1"] = {"holds": not missed, "pages_missed": missed}
        marks["P2"] = {"holds": parts_wrong <= whole_wrong + allowance, "whole_wrong": whole_wrong, "parts_wrong": parts_wrong,
                       "allowance": allowance, "line": whole_wrong + allowance}
        # For the owner to see, and no part of the mark: the same sum with the words on lines made unsure counted as wrong.
        whole_made, parts_made = (_wrong(judged, "local", name, "made_unsure_words") for name in ("whole", "parts"))
        marks["P2_if_made_unsure_were_wrong"] = {
            "holds": parts_wrong + parts_made <= whole_wrong + whole_made + allowance, "whole_made_unsure_words": whole_made,
            "parts_made_unsure_words": parts_made, "whole_wrong": whole_wrong + whole_made, "parts_wrong": parts_wrong + parts_made,
            "line": whole_wrong + whole_made + allowance}
    if any("cloud" in r for r in rows):
        in_parts = _taken(rows, "local", "parts")
        missed_whole = [_page(r) for r in judged if r["cloud"]["whole"].get("state") != TAKEN]
        missed_parts = [_page(r) for r in in_parts if r["cloud"]["parts"].get("state") != TAKEN]
        marks["H1"] = {"holds": not missed_whole and not missed_parts, "whole_missed": missed_whole, "parts_missed": missed_parts,
                       "parts_pages": len(in_parts)}
        whole = {"local": _wrong(judged, "local", "whole"), "cloud": _wrong(judged, "cloud", "whole")}
        parts = {"local": _wrong(in_parts, "local", "parts"), "cloud": _wrong(in_parts, "cloud", "parts")}
        marks["H2"] = {"holds": whole["cloud"] <= whole["local"] and parts["cloud"] <= parts["local"], "whole": whole, "parts": parts}
        drugs = {model: [r[model]["drug"] for r in rows if r[model]["drug"]["present"]] for model in ("local", "cloud")}
        total = lambda model, key: sum(d[key] for d in drugs[model])   # noqa: E731
        right = lambda model: sum(d["places"]["word_right"] for d in drugs[model])   # noqa: E731
        marks["D1"] = {"holds": len(drugs["cloud"]) == len(rows) and all(d["ok"] for d in drugs["cloud"]),
                       "answered": sum(1 for d in drugs["cloud"] if d["ok"]), "pages": len(rows)}
        marks["D2"] = {"holds": total("cloud", "marked") >= total("local", "marked"), "local": total("local", "marked"),
                       "cloud": total("cloud", "marked"), "written_wrongly": total("local", "written_wrongly")}
        marks["D3"] = {"holds": right("cloud") <= right("local"), "local": right("local"), "cloud": right("cloud")}
        marks["invents_nothing"] = {
            model: {"label_entries_with_more_than_a_number_and_a_label": sum(
                        r[model][name].get("other_keys", 0) for r in rows for name in ("whole", "parts")),
                    "drug_entries_dropped": total(model, "dropped"), "drug_entries_kept": total(model, "kept")}
            for model in ("local", "cloud")}
    return marks


def by_kind(rows: list[dict]) -> dict:
    """The sums of each kind of page, for each model and reading there is."""
    kinds: dict = {}
    for row in rows:
        kind = kinds.setdefault(row["arm"], {"pages": 0, "lines": 0, "words": 0})
        kind["pages"] += 1
        kind["lines"] += row["lines"]
        kind["words"] += row["words"]
        for model in ("local", "cloud"):
            for name in ("whole", "parts"):
                found = row.get(model, {}).get(name, {})
                if found.get("present"):
                    sums = kind.setdefault(f"{model}_{name}", {TAKEN: 0, **{c: 0 for c in COUNTS + RULE_COUNTS}})
                    sums[TAKEN] += found["state"] == TAKEN
                    for count in COUNTS + RULE_COUNTS:
                        sums[count] += found[count]
            drug = row.get(model, {}).get("drug", {})
            if drug.get("present"):
                sums = kind.setdefault(f"{model}_drug", {"answered": 0, "written_wrongly": 0, "marked": 0, "word_right": 0,
                                                         "other_word_wrong": 0, "nowhere": 0, "dropped": 0})
                sums["answered"] += drug["ok"]
                for key in ("written_wrongly", "marked", "dropped"):
                    sums[key] += drug[key]
                for place in ("word_right", "other_word_wrong", "nowhere"):
                    sums[place] += drug["places"][place]
    return kinds


# ------------------------------------------------------------ the tables

def _cells(found: dict) -> str:
    if not found.get("present"):
        return "not run | | | | | "
    return f"{found['state']} | {found['right']} | {found['wrong']} | {found['unsure']} | {found['named_twice']} | {found['dropped']}"


def as_markdown(scored: dict) -> str:
    marks, lines = scored["marks"], ["# The marks of step 6c, from the stored results", "", words.BENCH_STOP_MARKS_RULE.format(rule=scored["rule"]), ""]
    lines.append(f"Pages judged: {marks['judged']}, {marks['judged_words']} words. Not judged: {', '.join(marks['not_judged']) or 'none'}.")
    for name in ("P1", "P2", "P2_if_made_unsure_were_wrong", "H1", "H2", "D1", "D2", "D3"):
        if name in marks:
            rest = ", ".join(f"{key} {value}" for key, value in marks[name].items() if key != "holds")
            lines.append(f"- {name}: {'holds' if marks[name]['holds'] else 'MISSED'}. {rest}")
    if "invents_nothing" in marks:
        lines.append(f"- Invents nothing: {json.dumps(marks['invents_nothing'])}")
    models = [m for m in ("local", "cloud") if any(m in row for row in scored["pages"])]
    for model in models:
        lines += ["", f"## Who spoke, by page: {model}", "",
                  "| Page | Lines | Words | Whole | Right | Wrong | Unsure | Named twice | Dropped | Parts | Right | Wrong | Unsure | Named twice | Dropped |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {_page(r)} | {r['lines']} | {r['words']} | {_cells(r[model]['whole'])} | {_cells(r[model]['parts'])} |"
                  for r in scored["pages"]]
        lines += ["", f"## Who spoke, by kind of page: {model}", "",
                  "| Kind | Pages | Words | Whole taken | Wrong | Unsure | Of them made unsure by the rule | Named twice | Dropped "
                  "| Parts taken | Wrong | Unsure | Of them made unsure by the rule | Named twice | Dropped |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for kind, found in scored["kinds"].items():
            whole, parts = found.get(f"{model}_whole"), found.get(f"{model}_parts")
            cell = lambda s: (f"{s[TAKEN]} | {s['wrong']} | {s['unsure']} | {s['made_unsure_words']} | {s['named_twice']} | {s['dropped']}"   # noqa: E731
                              if s else "not run | | | | | ")
            lines.append(f"| {kind} | {found['pages']} | {found['words']} | {cell(whole)} | {cell(parts)} |")
        lines += ["", f"## Drug names, by kind of page: {model}", "",
                  "| Kind | Answered | Written wrongly | Marked | Marks on a word written rightly | On another word written wrongly "
                  "| Where nothing was spoken | Dropped |", "|---|---|---|---|---|---|---|---|"]
        for kind, found in scored["kinds"].items():
            drug = found.get(f"{model}_drug")
            if drug:
                lines.append(f"| {kind} | {drug['answered']} | {drug['written_wrongly']} | {drug['marked']} | {drug['word_right']} | "
                             f"{drug['other_word_wrong']} | {drug['nowhere']} | {drug['dropped']} |")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------- the command

def _calls(folder: Path | None) -> dict:
    return ResultWriter(Path(folder) / "calls").read_all() if folder and (Path(folder) / "calls" / "results").is_dir() else {}


def speech_stop_marks(local: Path, parts: Path | None, cloud: Path | None, whole: Path | None, recordings_folder: Path,
                      script_folders: list[Path], marks_path: Path, write: Path, say: Callable = print) -> int:
    """The one command: the pages and the local readings under local, the
    local parts reading under parts, a cloud model's readings under cloud
    (whole: the local whole reading when it was run again). The tables go
    under write, never over a file. Reads only what is stored."""
    try:
        listed = banked.load_list(recordings_folder)
    except banked.BadList as bad:
        say(words.BENCH_BAD_LIST.format(reason=bad))
        return 3
    try:
        ResultWriter(Path(write), forbidden=(REPO, paths.default_data_folder(), *banked.folders_of(listed)))   # a check of the folder only
    except Refused as refused:
        say(words.BENCH_FOLDER_REFUSED.format(place=str(refused).split("under ")[-1]))
        return 6
    stored = ResultWriter(Path(local)).read_all()
    marks_file = json.loads(Path(marks_path).read_text(encoding="utf-8"))
    try:
        scored = score_all(stored, _calls(local), _calls(whole or local), _calls(parts), _calls(cloud) if cloud else None, listed,
                           [Path(f) for f in script_folders], marks_file)
        written = tables.write(Path(write), scored, as_markdown(scored))
    except NotThePage as call:
        say(words.BENCH_NOT_THE_PAGE.format(call=call))
        return 9
    except tables.ScriptNotFound as missing:
        say(words.BENCH_BAD_LIST.format(reason=missing))
        return 8
    except Refused as refused:
        say(words.BENCH_WRITE_EXISTS.format(path=str(refused).split(" exists")[0]))
        return 6
    say(words.BENCH_SCORED.format(results=len(scored["pages"]), arms=len(scored["kinds"]), folder=written[0].parent))
    return 0


def add_command(sub, say: Callable) -> None:
    """The parser of speech-stop-marks, kept beside its command."""
    p = sub.add_parser("speech-stop-marks")
    p.add_argument("--local", required=True, help="the results folder of speech-run with the local model's calls under it")
    p.add_argument("--parts", help="the folder of the local model's parts reading")
    p.add_argument("--cloud", help="the folder of a cloud model's three readings")
    p.add_argument("--whole", help="the folder of the local whole reading, when it was run again")
    p.add_argument("--recordings", required=True, help="the folder holding recordings.json")
    p.add_argument("--scripts", action="append", required=True, help="a folder of scripts; may be given more than once")
    p.add_argument("--marks", required=True, help="the file of drug names, test names and safety nets")
    p.add_argument("--write", required=True, help="where scores.json and report.md go; never written over")
    path = lambda value: Path(value) if value else None   # noqa: E731
    p.set_defaults(fn=lambda a: speech_stop_marks(Path(a.local), path(a.parts), path(a.cloud), path(a.whole), Path(a.recordings),
                                                  [Path(f) for f in a.scripts], Path(a.marks), Path(a.write), say=say))
