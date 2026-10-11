"""The scores of every arm and recording, and the tables of the report,
from the stored results alone (spec 15.9, the details of 5c; 15.8 ruling
26). One command makes them, and makes them again the same, byte for
byte: nothing here reads a clock or a random number. The most important
for the patient comes first: for each arm, whether any passage was
missing with no sign, and whether any word was written in silence."""

from __future__ import annotations

import json
from pathlib import Path

from openconsult.bench.speech import marks, waits
from openconsult.bench.speech.banked import Recording, sha256_of
from openconsult.bench.speech.pages import Page, build_page, live_pieces, pages_of
from openconsult.bench.speech.reference import Reference, agreement, build, names_as_cut, safety_nets_as_cut
from openconsult.bench.writer import Refused
from openconsult.speech.lines import Line
from openconsult.speech.matching import normalise
from openconsult.speech.missing import missing_from_final, uncovered_speech

# The arms with a model of their own, whose pages count for agreement
# against the script (13.4 rule 5): one page each, the page at Stop.
COUNT_FOR_AGREEMENT = ("whisperx_pyannote", "nemotron", "nemotron_tied_pair", "speechmatics", "assemblyai")
WHISPERX_ARMS = ("whisperx_pyannote", "whisperx_v1_line")


class ScriptNotFound(Exception):
    pass


def find_script(recording: Recording, folders: list[Path]) -> str:
    """The script by name in the folders given, with the list's checksum."""
    for folder in folders:
        path = Path(folder) / recording.script
        if path.is_file():
            if sha256_of(path) != recording.script_sha256:
                raise ScriptNotFound(f"{recording.script} in {folder} has not the checksum the list gives")
            return path.read_text(encoding="utf-8")
    raise ScriptNotFound(f"{recording.script} is in none of the script folders")


def true_times_of(recording: Recording) -> dict[int, tuple[float, float]] | None:
    """The true start and end of each speech, for a made recording whose
    list names its times file (beside the recording, read only)."""
    name = recording.entry.get("true_times")
    if not name:
        return None
    data = json.loads((recording.folder / name).read_text(encoding="utf-8"))
    return {int(s["number"]): (float(s["start"]), float(s["end"])) for s in data["speeches"]}


def _lines_of(page: Page) -> list[Line]:
    return [Line(p["speaker"], p["start"], p["end"], p["text"], None) for p in page.pieces]


def _refused_of(result: dict) -> list[dict]:
    return [r for piece in result["pieces"] for r in piece["refused"]] + list(result["stop"]["refused"])


def score_page(arm: str, page: Page, live: Page | None, result: dict, reference: Reference, agreed: set[int],
               entry: dict, true_times) -> dict:
    """Every mark of part one on one page."""
    windows, window_s = result["loudness"]["dbfs"], result["loudness"]["window_s"]
    slack = float(result["time_slack_s"])
    end_s = len(windows) * window_s
    gaps = missing_from_final(_lines_of(live), _lines_of(page)) if live is not None and page.name == "stop" else []
    stretches = uncovered_speech(windows, window_s, _lines_of(page))
    safety = safety_nets_as_cut(reference, entry.get("safety_net_speeches", []))
    scored = {
        "passages": marks.passages(page, reference, agreed, safety, gaps, live, stretches, end_s),
        "words_from_silence": marks.words_from_silence(page, windows, window_s, slack),
        "rule": marks.rule_did(page, _refused_of(result), reference, windows, window_s, slack),
        "differ": marks.differ(page, reference, agreed),
        "drugs": marks.drug_names(page, reference, entry.get("drugs", {}), entry.get("v1_line_drugs", [])),
        "tests": marks.drug_names(page, reference, entry.get("tests", {}), entry.get("v1_line_tests", [])),
        "signs": waits.signs_counted(page, reference, agreed, gaps, live, stretches, end_s),
        "gaps": [{"words": list(g.words), "start": g.start_s, "end": g.end_s} for g in gaps],
        "stretches": [[s.start_s, s.end_s] for s in stretches],
        "words": len(page.words),
    }
    if page.name == "stop":
        scored["who_spoke"] = marks.who_spoke(page, reference)
    if page.name == "live" or not result["stop"]["raw"]:
        # The line page for the wait is the live lines of every arm, so a
        # line finds its speech and the true times serve every arm (fix two).
        line_page = page if page.name == "live" else build_page("live", live_pieces(result), reference)
        scored["wait"] = waits.waits(result, reference, line_page, true_times)
    if true_times:
        scored["times"] = waits.exactness_made(page, reference, true_times, slack)
    scored["hard"] = {"passages_without_sign": sum(1 for p in scored["passages"] if not p["sign"]),
                      "words_from_silence": len(scored["words_from_silence"]),
                      "real_words_refused": len(scored["rule"]["real_words_refused"])}
    return scored


def late_changes_of(result: dict, reference: Reference) -> dict:
    """The tied pair's late changes: how many lines changed late, and how
    many words the page lacks for it (plan of part one, change 7)."""
    changes = (result["stop"].get("notes") or {}).get("late_changes") or []
    by_id = {line["id"]: line for line in result["stop"]["lines"]}
    lacking = 0
    for change in changes:
        line = by_id.get(change["id"])
        if line is not None:
            lacking += max(0, len(normalise(change["text"], reference.joinable)) - len(normalise(line["text"], reference.joinable)))
    return {"lines_changed_late": len({c["id"] for c in changes}), "words_page_lacks": lacking}


def score_recording(recording: Recording, results: dict[str, dict], script_text: str, entry: dict) -> dict:
    """One recording across its arms: the agreement first, then each page."""
    reference = build(script_text, recording.last_speech, recording.read_differently)
    true_times = true_times_of(recording)
    pages = {arm: pages_of(result, reference) for arm, result in results.items() if not result["failure"]}
    counting = {arm: (pages[arm]["stop"].pairs, pages[arm]["stop"].words) for arm in COUNT_FOR_AGREEMENT if arm in pages}
    agreed_places = agreement(reference, counting)
    agreed = {a.index for a in agreed_places if a.kind == "agreed"}
    scored = {"recording": recording.name, "script": recording.script_key, "machine_voices": recording.machine_voices,
              "whole": recording.whole, "last_speech": recording.last_speech, "spoken_words": len(reference.words),
              "names_as_cut": {n: len(o) for n, o in names_as_cut(reference, entry.get("drugs", {})).items()},
              "agreed": [_agreed_row(a, reference, entry) for a in agreed_places], "arms": {}}
    wx_times = None
    if "whisperx_pyannote" in pages and not true_times:
        wx_times = waits.word_times_from_whisperx(results["whisperx_pyannote"], reference)
    for arm, result in sorted(results.items()):
        if result["failure"]:
            scored["arms"][arm] = {"failed": result["failure"]}
            continue
        live = pages[arm].get("live")
        row = {name: score_page(arm, page, live, result, reference, agreed, entry, true_times)
               for name, page in pages[arm].items()}
        if wx_times is not None and arm not in WHISPERX_ARMS:
            row["stop"]["times"] = waits.exactness_old(pages[arm]["stop"], reference, wx_times, float(result["time_slack_s"]))
        if arm == "nemotron_tied_pair":
            row["late_changes"] = late_changes_of(result, reference)
        scored["arms"][arm] = row
    return scored


def _agreed_row(agreed, reference: Reference, entry: dict) -> dict:
    word = reference.words[agreed.index]
    names = {w for n in list(entry.get("drugs", {})) + list(entry.get("tests", {})) for w in normalise(n)}
    touches = []
    if word.norm in marks.NEGATIONS:
        touches.append("negation")
    if marks._NUMBER.match(word.norm):
        touches.append("number")
    if word.norm in names:
        touches.append("drug or test name")
    if word.speech in entry.get("safety_net_speeches", []):
        touches.append("safety net")
    return {"index": agreed.index, "speech": word.speech, "spoken": agreed.spoken, "written": agreed.written,
            "kind": agreed.kind, "arms": list(agreed.arms), "touches": touches}


def entry_for(marks_file: dict, script_key: str) -> dict:
    entry = dict(marks_file["scripts"].get(script_key, {}))
    entry["v1_line_drugs"] = marks_file.get("v1_line", {}).get("drugs", [])
    entry["v1_line_tests"] = marks_file.get("v1_line", {}).get("tests", [])
    return entry


def score_all(results: dict[tuple[str, str], dict], recordings: list[Recording], script_folders: list[Path],
              marks_file: dict) -> dict:
    """Every recording that has results, with its arms."""
    by_recording: dict[str, dict[str, dict]] = {}
    for (arm, name), result in results.items():
        by_recording.setdefault(name, {})[arm] = result
    scored = {"recordings": {}, "arms": {}}
    for recording in recordings:
        if recording.name not in by_recording:
            continue
        entry = entry_for(marks_file, recording.script_key)
        scored["recordings"][recording.name] = score_recording(
            recording, by_recording[recording.name], find_script(recording, script_folders), entry)
    scored["arms"] = arm_summary(scored["recordings"])
    return scored


def arm_summary(recordings: dict) -> dict:
    """For each arm, over every recording: the two hard marks and what the
    rule refused, from the page the doctor would have."""
    summary: dict[str, dict] = {}
    for name, scored in sorted(recordings.items()):
        for arm, row in sorted(scored["arms"].items()):
            total = summary.setdefault(arm, {"recordings": [], "failed": [], "passages_without_sign": 0,
                                             "words_from_silence": 0, "real_words_refused": 0, "invented_let_through": 0})
            if "failed" in row:
                total["failed"].append(name)
                continue
            total["recordings"].append(name)
            page = row.get("stop") if arm != "whisperx_v1_line" else row.get("live")
            if page is None:
                continue
            for key in ("passages_without_sign", "words_from_silence", "real_words_refused"):
                total[key] += page["hard"][key]
            total["invented_let_through"] += len(page["rule"]["invented_let_through"])
            if "late_changes" in row:
                total["late_changes"] = {k: total.get("late_changes", {}).get(k, 0) + v for k, v in row["late_changes"].items()}
    return summary


# ------------------------------------------------------------------ tables

def yes_no(n: int) -> str:
    return f"yes, {n}" if n else "no"


def first_table(scored: dict) -> list[str]:
    lines = ["| arm | passage missing with no sign | word written in silence | real words the rule refused | invented words let through | recordings | failed |",
             "|---|---|---|---|---|---|---|"]
    for arm, total in sorted(scored["arms"].items()):
        late = total.get("late_changes")
        note = f" (late changes: {late['lines_changed_late']} lines, {late['words_page_lacks']} words lacking)" if late else ""
        lines.append(f"| {arm}{note} | {yes_no(total['passages_without_sign'])} | {yes_no(total['words_from_silence'])} | "
                     f"{total['real_words_refused']} | {total['invented_let_through']} | {', '.join(total['recordings']) or 'none'} | "
                     f"{', '.join(total['failed']) or 'none'} |")
    return lines


def agreed_table(rec: dict) -> list[str]:
    rows = sorted(rec["agreed"], key=lambda a: (not a["touches"], a["index"]))
    if not rows:
        return ["No place where every arm that counts agrees against the script."]
    lines = ["| speech | spoken | written by every arm | kind | touches |", "|---|---|---|---|---|"]
    for a in rows:
        lines.append(f"| {a['speech']} | {a['spoken']} | {a['written'] if a['written'] is not None else '(left out)'} | "
                     f"{a['kind']} | {', '.join(a['touches']) or ''} |")
    return lines


def _typ(t: dict) -> str:
    return "none" if t["n"] == 0 else f"median {t['median']} s, longest {t['longest']} s over {t['n']}"


def page_table(arm: str, name: str, page: dict) -> list[str]:
    drugs, tests, who = page["drugs"], page["tests"], page.get("who_spoke")
    lines = [f"**{arm}, page {name}**: {page['words']} words on the page.",
             f"- Passages: {len(page['passages'])}, without a sign {page['hard']['passages_without_sign']}, "
             f"in a safety net {sum(1 for p in page['passages'] if p['safety_net'])}, "
             f"unseeable by a stretch (both sides in one piece) {sum(1 for p in page['passages'] if p['same_piece'])}.",
             f"- Words from silence: {len(page['words_from_silence'])}.",
             f"- The rule: refused lines {page['rule']['refused_lines']}, real words refused {len(page['rule']['real_words_refused'])}, "
             f"invented words let through {len(page['rule']['invented_let_through'])}.",
             f"- Words that differ: {len(page['differ']['places'])}; negations lost {len(page['differ']['negations_lost'])}, "
             f"added {len(page['differ']['negations_added'])}; numbers changed {len(page['differ']['numbers_changed'])}.",
             f"- Drug names caught: {drugs['caught']} of {drugs['spoken']} (in v1's line {drugs['in_line']['caught']} of "
             f"{drugs['in_line']['spoken']}, not in it {drugs['not_in_line']['caught']} of {drugs['not_in_line']['spoken']}). "
             f"Test names caught: {tests['caught']} of {tests['spoken']}.",
             f"- Signs of the check: right {page['signs']['right']}, false {page['signs']['false']}; "
             f"gaps {len(page['gaps'])}, stretches {len(page['stretches'])}."]
    if who:
        lines.append(f"- Who spoke: right {who['right']}, wrong {who['wrong']}, no speaker {who['no_speaker']}; labels {who['mapping']}.")
    if "wait" in page:
        wait = page["wait"]
        lines.append(f"- The wait: to final {_typ(wait['to_final'])}; to first shown {_typ(wait['to_first'])}; "
                     f"never shown {wait['never_shown']}"
                     + (f"; to final from the true end {_typ(wait['to_final_true'])}" if wait["to_final_true"]["n"] else "")
                     + (f"; to first shown from the true start {_typ(wait['to_first_true'])}" if wait.get("to_first_true", {}).get("n") else "")
                     + ".")
    if "times" in page:
        t = page["times"]
        lines.append(f"- How exact the times are: median {t['median_abs']} s, largest {t['largest_abs']} s, "
                     f"beyond the figure of {t['figure_s']} s: {t['beyond_figure']} of {2 * t['n']}.")
    for p in page["passages"]:
        lines.append(f"  - passage, speech {p['speeches']}, {p['missing']} missing of {p['spoken']}, sign {p['sign']}"
                     f"{', safety net' if p['safety_net'] else ''}{', unseeable' if p['same_piece'] else ''}: {' '.join(p['words'])}")
    for w in page["words_from_silence"]:
        lines.append(f"  - from silence: {w['word']} in {w['piece']} within pause {w['pause']}")
    for r in drugs["rows"]:
        if not r["caught"] or r["how"] != "heard":
            lines.append(f"  - drug {r['name']} (speech {r['speech']}): {r['how']}{', written ' + r['written'] if r['written'] else ''}")
    for p in page["differ"]["negations_lost"] + page["differ"]["negations_added"] + page["differ"]["numbers_changed"]:
        lines.append(f"  - {p['kind']}: spoken {p['spoken']}, written {p['written']} (speech {p['speech']}; {p['context']})")
    return lines


def as_markdown(scored: dict) -> str:
    lines = ["# The speech bench: part one", "",
             "THIS IS A REHEARSAL. NO FIGURE IN IT COUNTS.", "",
             "On a machine-voice recording the two voices are a male and a female machine voice, so who spoke is easy there.", "",
             "## For the patient, first", "", *first_table(scored), ""]
    for name, rec in sorted(scored["recordings"].items()):
        how_read = "" if rec["whole"] else f", read to speech {rec['last_speech']}"
        voices = ", machine voices" if rec["machine_voices"] else ""
        lines += [f"## {name} (script {rec['script']}{voices}{how_read})", "",
                  f"{rec['spoken_words']} spoken words in the reference as cut.", "", "### Agreed against the script", "",
                  *agreed_table(rec), ""]
        for arm, row in sorted(rec["arms"].items()):
            if "failed" in row:
                lines += [f"**{arm}**: failed at {row['failed']['at']}: {row['failed']['failure']}: {row['failed']['detail']}", ""]
                continue
            if "late_changes" in row:
                lines += [f"**{arm}**: late changes {row['late_changes']}", ""]
            for page_name in sorted(row):
                if page_name in ("stop", "live"):
                    lines += page_table(arm, page_name, row[page_name]) + [""]
    return "\n".join(lines) + "\n"


def write(folder: Path, scored: dict, text: str) -> list[Path]:
    """scores.json and report.md, each written once, never over a file."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    targets = {folder / "scores.json": json.dumps(scored, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
               folder / "report.md": text}
    for target in targets:
        if target.exists():
            raise Refused(f"{target} exists and is never written over")
    for target, content in targets.items():
        target.write_text(content, encoding="utf-8", newline="\n")      # the same bytes on every system
    return list(targets)
