"""The scores and the tables of part two, from the stored results alone
(spec 15.9, the details of part two of 5c; 15.8 ruling 26). One command
makes them, and makes them again the same, byte for byte: nothing here
reads a clock or a random number. The most important for the patient
comes first, for each speech choice: whether any drug was written as
another real drug, how many key facts were not found for its pages and
were found in both notes from the script, and the words each of the four
readings of who spoke put under the wrong speaker."""

from __future__ import annotations

import statistics
from pathlib import Path

from openconsult.bench.speech import calls, doubt, keyfacts, model_lines, notes, pages, tables, voice, who
from openconsult.bench.speech.banked import Recording
from openconsult.bench.speech.druglist import DrugList
from openconsult.bench.speech.reference import Reference, build

ROUNDS = (1, 2)
WAYS = ("list", "second_listen", "model")


def _call(call_results: dict, job: str, arm: str, name: str, round_n: int | None = None) -> dict | None:
    return call_results.get((job, calls.chain_name(arm, name, round_n)))


def _labels(record: dict | None) -> dict[int, str] | None:
    if not record or not record.get("labels"):
        return None
    return {int(n): label for n, label in record["labels"].items()}


def _voice_readings(record: dict | None) -> dict[int, str] | None:
    """The readings made again from the stored distances and the figures of the code."""
    if not record or record.get("not_run") or record.get("failure"):
        return None
    return {ln["n"]: voice.reading_of(ln["distance"], ln["length_s"]) for ln in record["lines"]}


def _note_counts(record: dict | None, transcript_words: list[str], n_turns: int, facts: list[dict], negations,
                 drugs: DrugList | None, spoken: list[str], never_right: list[str]) -> dict | None:
    if not record or not record.get("note"):
        return None
    return notes.five_counts(record["note"], transcript_words, n_turns, facts, negations, drugs, spoken, never_right)


def _not_found(first: dict | None, second: dict | None) -> dict[str, list[dict]]:
    """A fact is not found for a page when it is changed, part or missing
    in at least one of the two notes; with its nearest entry from the note
    that holds the most of its groups."""
    found: dict[str, list[dict]] = {}
    for counts in (first, second):
        for fact in (counts or {}).get("key_facts", []):
            found.setdefault(fact["id"], []).append(fact)
    not_found = {}
    for fact_id, outcomes in found.items():
        if any(f["outcome"] != "found" for f in outcomes) or len(outcomes) < 2:
            nearest = max((f for f in outcomes), key=lambda f: (f["nearest"] or {}).get("groups_met", 0))
            not_found[fact_id] = {**nearest, "outcomes": [f["outcome"] for f in outcomes]}
    return not_found


def score_page(arm: str, name: str, result: dict, recording: Recording, reference: Reference, entry: dict,
               stop_pages: dict[str, dict], voice_results: dict, call_results: dict, key_facts: keyfacts.KeyFacts | None,
               drugs: DrugList | None, script_notes: dict | None) -> dict:
    lines = model_lines.lines_of(pages.stop_pieces(result))
    page = who.line_page(lines, reference)
    occurrences = doubt.drug_occurrences(page, reference, entry.get("drugs", {}))
    label_record = _call(call_results, "label_check", arm, name)
    drug_record = _call(call_results, "drug_name", arm, name)
    voice_record = voice_results.get((arm, name))
    scored = {"lines": len(lines), "words": len(page.words),
              "who": who.four_readings(lines, reference, _labels(label_record), _voice_readings(voice_record)),
              "label_check": {"refused": bool(label_record and label_record.get("refusal")),
                              "failed": bool(label_record and not label_record["call"]["ok"]),
                              "refusal": (label_record or {}).get("refusal"), "present": label_record is not None},
              "voice": _voice_summary(voice_record), "ways": {}, "classes": None, "notes": {}}
    if drugs is not None:
        scored["ways"]["list"] = doubt.by_list(page, occurrences, drugs)
        scored["classes"] = doubt.classes_of(occurrences, drugs)
    other = doubt.SECOND_LISTEN.get(arm)
    if other and other in stop_pages:
        other_page = who.line_page(model_lines.lines_of(pages.stop_pieces(stop_pages[other])), reference)
        scored["ways"]["second_listen"] = doubt.by_second_listen(page, other_page, occurrences)
    if drug_record is not None:
        scored["ways"]["model"] = {**doubt.by_model(page, drug_record.get("kept") or [], occurrences),
                                   "dropped": len(drug_record.get("dropped") or []), "failed": not drug_record["call"]["ok"]}
    facts = key_facts.facts_of(recording.script_key, recording.last_speech, _skipped(recording)) if key_facts else []
    never_right = sorted({occ["name"] for occ in occurrences} - {occ["name"] for occ in occurrences if occ["caught"]})
    rounds = {}
    for round_n in ROUNDS:
        record = _call(call_results, "note", arm, name, round_n)
        rounds[round_n] = _note_counts(record, page.words, len(model_lines.turns_of(lines)), facts,
                                       key_facts.negations if key_facts else frozenset(), drugs,
                                       list(entry.get("drugs", {})), never_right)
        rounds[round_n] = {"present": record is not None, "failed": bool(record and not record["call"]["ok"]), **(rounds[round_n] or {})}
    not_found = _not_found(rounds[1], rounds[2])
    for fact_id, fact in not_found.items():
        fact["script_missed"] = fact_id in (script_notes or {}).get("not_found", {})
    scored["notes"] = {"rounds": {str(r): rounds[r] for r in ROUNDS}, "not_found": not_found,
                       "chance": notes.chance(rounds[1].get("key_facts", []), rounds[2].get("key_facts", []))
                       if rounds[1].get("key_facts") and rounds[2].get("key_facts") else None}
    return scored


def _skipped(recording: Recording) -> tuple[int, ...]:
    return tuple(int(note["speech"]) for note in recording.read_differently if note.get("skipped"))


def _voice_summary(record: dict | None) -> dict:
    if not record or record.get("not_run"):
        return {"not_run": True}
    if record.get("failure"):
        return {"failed": record["failure"]}
    readings = {ln["n"]: voice.reading_of(ln["distance"], ln["length_s"]) for ln in record["lines"]}
    distances = [ln["distance"] for ln in record["lines"] if ln["distance"] is not None]
    return {"doctor": sum(1 for r in readings.values() if r == "doctor"),
            "not_doctor": sum(1 for r in readings.values() if r == "not_doctor"),
            "unsure": sum(1 for r in readings.values() if r == "unsure"), "lines": len(readings),
            "distance": _typical(distances), "learnt": record.get("learnt"), "figures": record.get("figures")}


def script_note_counts(name: str, recording: Recording, reference: Reference, entry: dict, call_results: dict,
                       key_facts: keyfacts.KeyFacts | None, drugs: DrugList | None) -> dict:
    facts = key_facts.facts_of(recording.script_key, recording.last_speech, _skipped(recording)) if key_facts else []
    rounds = {}
    for round_n in ROUNDS:
        record = _call(call_results, "script_note", calls.SCRIPT_ARM, name, round_n)
        counts = _note_counts(record, reference.norms, len(reference.speeches), facts,
                              key_facts.negations if key_facts else frozenset(), drugs, list(entry.get("drugs", {})), [])
        rounds[round_n] = {"present": record is not None, "failed": bool(record and not record["call"]["ok"]), **(counts or {})}
    return {"rounds": {str(r): rounds[r] for r in ROUNDS}, "not_found": _not_found(rounds[1], rounds[2]),
            "chance": notes.chance(rounds[1].get("key_facts", []), rounds[2].get("key_facts", []))
            if rounds[1].get("key_facts") and rounds[2].get("key_facts") else None}


def score_all(results: dict, voice_results: dict, call_results: dict, listed: list[Recording], script_folders: list[Path],
              marks_file: dict, key_facts: keyfacts.KeyFacts | None, drugs: DrugList | None) -> dict:
    """Every recording that has results: its pages, and the notes from its script."""
    by_recording: dict[str, dict[str, dict]] = {}
    for (arm, name), result in results.items():
        by_recording.setdefault(name, {})[arm] = result
    scored = {"recordings": {}, "arms": {}, "calls": call_summary(call_results),
              "drug_list": {"month": drugs.month, "names": drugs.count, "longer_names": len(drugs.longer)} if drugs else None}
    for recording in listed:
        if recording.name not in by_recording:
            continue
        entry = tables.entry_for(marks_file, recording.script_key)
        reference = build(tables.find_script(recording, script_folders), recording.last_speech, recording.read_differently)
        pages_at_stop = {arm: r for arm, r in by_recording[recording.name].items() if not r.get("failure")}
        script_notes = script_note_counts(recording.name, recording, reference, entry, call_results, key_facts, drugs)
        rec = {"script": recording.script_key, "machine_voices": recording.machine_voices, "script_notes": script_notes, "arms": {}}
        for arm, result in sorted(pages_at_stop.items()):
            if arm in calls.SHARES_STOP:
                continue
            rec["arms"][arm] = score_page(arm, recording.name, result, recording, reference, entry, pages_at_stop,
                                          voice_results, call_results, key_facts, drugs, script_notes)
        scored["recordings"][recording.name] = rec
    scored["arms"] = arm_summary(scored["recordings"])
    return scored


def arm_summary(recordings: dict) -> dict:
    summary: dict[str, dict] = {}
    for name, rec in sorted(recordings.items()):
        for arm, page in sorted(rec["arms"].items()):
            total = summary.setdefault(arm, {"recordings": [], "wrong_drug": 0, "facts_not_found_script_found": 0,
                                             "facts_not_found": 0, "wrong_speaker": {r: 0 for r in who.READINGS},
                                             "label_checks_refused": 0, "label_checks_failed": 0})
            total["recordings"].append(name)
            if page["classes"]:
                total["wrong_drug"] += page["classes"]["real_drug_not_spoken"]
            total["facts_not_found"] += len(page["notes"]["not_found"])
            total["facts_not_found_script_found"] += sum(1 for f in page["notes"]["not_found"].values() if not f["script_missed"])
            for reading in who.READINGS:
                counts = page["who"]["counts"][reading]
                total["wrong_speaker"][reading] += counts.get("wrong", 0)
            total["label_checks_refused"] += int(page["label_check"]["refused"])
            total["label_checks_failed"] += int(page["label_check"]["failed"])
    return summary


def call_summary(call_results: dict) -> dict:
    """For each job: the seconds and the tokens, typical and longest, and
    every reply that reached a limit, was refused or failed."""
    by_job: dict[str, list[dict]] = {}
    for (job, _), record in sorted(call_results.items()):
        by_job.setdefault(job, []).append(record)
    summary = {}
    for job, records in by_job.items():
        called = [r["call"] for r in records]
        summary[job] = {"calls": len(called), "ok": sum(1 for c in called if c["ok"]),
                        "failed": {c["failure"]: sum(1 for d in called if d["failure"] == c["failure"]) for c in called if not c["ok"]},
                        "refused": sum(1 for r in records if r.get("refusal")),
                        "seconds": _typical([c["wall_ms"] / 1000 for c in called]),
                        "output_tokens": _typical([c["output_tokens"] for c in called if c.get("output_tokens") is not None]),
                        "prompt_tokens": _typical([c["prompt_tokens"] for c in called if c.get("prompt_tokens") is not None])}
    return summary


def _typical(values: list) -> dict:
    if not values:
        return {"n": 0, "median": None, "longest": None}
    return {"n": len(values), "median": round(statistics.median(values), 3), "longest": round(max(values), 3)}


# ------------------------------------------------------------------ tables

def first_table(scored: dict) -> list[str]:
    lines = ["| speech choice | a drug written as another real drug | key facts not found, found in both notes from the script | "
             "words under the wrong speaker: choice / label check / voice / together | recordings |", "|---|---|---|---|---|"]
    for arm, total in sorted(scored["arms"].items()):
        wrong = total["wrong_speaker"]
        lines.append(f"| {arm} | {tables.yes_no(total['wrong_drug'])} | {total['facts_not_found_script_found']} "
                     f"(of {total['facts_not_found']} not found) | {wrong['choice']} / {wrong['label_check']} / {wrong['voice']} / "
                     f"{wrong['together']} | {', '.join(total['recordings'])} |")
    return lines


def facts_table(rec: dict, key_facts_kinds: tuple, name: str) -> list[str]:
    lines = []
    for arm, page in sorted(rec["arms"].items()):
        not_found = page["notes"]["not_found"]
        if not not_found:
            lines.append(f"- {arm} on {name}: every key fact found in both notes.")
            continue
        lines.append(f"- {arm} on {name}: {len(not_found)} not found.")
        order = {kind: i for i, kind in enumerate(key_facts_kinds)}
        for fact_id, fact in sorted(not_found.items(), key=lambda f: (order.get(f[1]["kind"], 99), f[0])):
            near = fact["nearest"]
            shown = f"{near['section']}: {near['text']}" if near else "none"
            mark = " [also not found from the script]" if fact["script_missed"] else ""
            lines.append(f"  - {fact['kind']} {fact_id}, {fact['fact']}: {' / '.join(fact['outcomes'])}{mark}; nearest entry: {shown}")
    return lines


def _ways_lines(arm: str, page: dict) -> list[str]:
    lines = []
    for way in WAYS:
        found = page["ways"].get(way)
        if not found:
            continue
        p = found["places"]
        extra = ""
        if way == "model":
            extra = f"; meant right {found['meant']['right']}, wrong {found['meant']['wrong']}, empty {found['meant']['empty']}; entries dropped {found['dropped']}"
        if way == "second_listen":
            extra = f"; places with no word {found['places_with_no_word']}"
        if way == "list":
            extra = f"; words in the list only as a brand {len(found['brand_only'])}"
        lines.append(f"  - {way}: marked {found['names_marked']} of {found['names_written_wrongly']} drug names written wrongly "
                     f"({found['names_missing']} with nothing in their place); marks on a drug name wrong {p['drug_name_wrong']}, "
                     f"another word wrong {p['other_word_wrong']}, a word right {p['word_right']}, a word from nowhere {p['nowhere']}{extra}")
        for mark in found["marks"]:
            if mark["place"] != "drug_name_wrong":
                lines.append(f"    - on {mark['text']} (line {mark['line']}): {mark['place']}")
    return lines


def page_lines(arm: str, page: dict) -> list[str]:
    counts = page["who"]["counts"]

    def reading(name):
        c = counts[name]
        return "not run" if c.get("not_run") else f"right {c['right']}, wrong {c['wrong']}, unsure {c['unsure']}"

    lines = [f"**{arm}**: {page['lines']} lines, {page['words']} words.",
             f"- Who spoke: the choice {reading('choice')}; the label check {reading('label_check')}"
             f"{' (refused)' if page['label_check']['refused'] else ''}{' (failed)' if page['label_check']['failed'] else ''}; "
             f"the voice {reading('voice')}; together {reading('together')}; words from nowhere {counts['choice']['nowhere']}."]
    v = page["voice"]
    if "lines" in v:
        lines.append(f"- The voice method: doctor {v['doctor']}, not doctor {v['not_doctor']}, unsure {v['unsure']} of {v['lines']} lines; "
                     f"distance median {v['distance']['median']}, largest {v['distance']['longest']}.")
    if page["classes"]:
        c = page["classes"]
        lines.append(f"- Drug names not caught: missing {c['missing']}, garbled {c['garbled']}, a real drug not the one spoken {c['real_drug_not_spoken']}.")
        for row in c["rows"]:
            lines.append(f"  - {row['name']} (speech {row['speech']}): {row['class']}{', written ' + row['written'] if row['written'] else ''}")
    lines += _ways_lines(arm, page)
    for round_n, counts_r in sorted(page["notes"]["rounds"].items()):
        if not counts_r.get("key_facts") and not counts_r.get("present"):
            lines.append(f"- Note, round {round_n}: no note.")
            continue
        if counts_r.get("failed"):
            lines.append(f"- Note, round {round_n}: the call failed.")
            continue
        outcomes = [f["outcome"] for f in counts_r["key_facts"]]
        d = counts_r.get("drugs") or {}
        lines.append(f"- Note, round {round_n}: facts found {outcomes.count('found')}, changed {outcomes.count('changed')}, part {outcomes.count('part')}, "
                     f"missing {outcomes.count('missing')}; figures not spoken {len(counts_r['figures_not_spoken'])}; "
                     f"reasoning cut {counts_r['reasoning_cut']}; entries with bad turns {len(counts_r['bad_turns'])} of {counts_r['entries']}; "
                     f"right name for a drug the page never wrote rightly {sum(d.get('right_name_present', {}).values())} of {len(d.get('right_name_present', {}))}; "
                     f"names of the list not spoken {len(d.get('names_not_spoken', []))}; entries saying unclear {d.get('unclear_entries', 0)}.")
        for figure in counts_r["figures_not_spoken"]:
            lines.append(f"  - figure not spoken: {figure['figure']}{' ' + figure['unit'] if figure['unit'] else ''} in {figure['section']}: {figure['text']}")
        for item in d.get("names_not_spoken", []):
            lines.append(f"  - name not spoken: {item['name']} in {item['section']}: {item['text']}")
    if page["notes"]["chance"]:
        ch = page["notes"]["chance"]
        lines.append(f"- The two notes differ in the outcome of {ch['differ']} of {ch['facts']} facts.")
    return lines


def as_markdown(scored: dict) -> str:
    kinds = scored.get("kinds") or ("red_flag", "drug", "negative", "safety_net", "positive", "examination", "plan")
    lines = ["", "# Part two: what is done with the transcripts", "", "THIS IS A REHEARSAL. NO FIGURE IN IT COUNTS.", "",
             "## For the patient, first", "", *first_table(scored), ""]
    if scored.get("drug_list"):
        d = scored["drug_list"]
        lines += [f"The drug list is of {d['month']}, {d['names']} names, {d['longer_names']} of them of more than one word. "
                  "A drug that people call by one word of a longer name is not found by that word.", ""]
    lines += ["## The key facts not found, by kind and then in the order spoken", ""]
    for name, rec in sorted(scored["recordings"].items()):
        lines += facts_table(rec, kinds, name)
        s = rec["script_notes"]["not_found"]
        lines.append(f"- the notes from the script of {name}: {len(s)} not found in one of the two" + (f": {', '.join(sorted(s))}" if s else "") + ".")
    lines.append("")
    for name, rec in sorted(scored["recordings"].items()):
        lines += [f"## {name} (script {rec['script']}{', machine voices' if rec['machine_voices'] else ''})", ""]
        for arm, page in sorted(rec["arms"].items()):
            lines += page_lines(arm, page) + [""]
    lines += ["## The calls", ""]
    for job, c in sorted(scored["calls"].items()):
        lines.append(f"- {job}: {c['calls']} calls, {c['ok']} answered, failed {c['failed'] or 'none'}, refused {c['refused']}; "
                     f"seconds median {c['seconds']['median']}, longest {c['seconds']['longest']}; "
                     f"output tokens median {c['output_tokens']['median']}, longest {c['output_tokens']['longest']}; "
                     f"prompt tokens longest {c['prompt_tokens']['longest']}.")
    return "\n".join(lines) + "\n"
