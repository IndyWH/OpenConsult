"""The tables of 5e (spec 15.9, rulings 27 to 33; the details of 5e), from
the stored results alone, beside the marks of part one and part two: one
row for each of the eight kinds of page, the label check in both
readings, the voice method by its source, the line for Alba, the
uploads, what other values of the draft figures would have given, the
loudness of the recordings, and the two lists a person can listen to.
No figure of the code is changed here: every other value is worked out
from what was stored."""

from __future__ import annotations

import difflib
import statistics
from pathlib import Path

from openconsult.bench.speech import alba, calls, doubt, jobs, model_lines, pages, tables, voice, voicecut, who
from openconsult.bench.speech.banked import Recording
from openconsult.bench.speech.druglist import CLOSE_AT, LEAST_DOUBT_LETTERS, DrugList
from openconsult.bench.speech.reference import Reference, build
from openconsult.consult import note as app_note
from openconsult.llm.jobs import JOBS as APP_JOBS
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.speech.missing import SPEECH_DBFS
from openconsult.speech.loudness import QUIET_DBFS
from openconsult.speech.matching import align
from openconsult.speech.nemotron.wordflow import WORD_CLOSE_S

# The eight kinds of page, in the order of the details, with the words of the tables.
KINDS = (("whisperx_pyannote", "WhisperX with pyannote, at Stop"), ("whisperx_v1_line", "WhisperX given v1's line, at Stop"),
         ("nemotron", "Nemotron, live"), ("nemotron_tied_pair", "the tied Nemotron pair, live"),
         ("speechmatics", "Speechmatics, live"), ("assemblyai", "AssemblyAI, live"),
         ("speechmatics_upload", "Speechmatics, whole recording"), ("assemblyai_upload", "AssemblyAI, whole recording"))
UPLOADS = ("speechmatics_upload", "assemblyai_upload")
OTHER_CLOSENESS = (0.65, 0.70, 0.75, 0.80, 0.85)
OTHER_WORD_CLOSE_S = (0.5, 1.0, 1.5, 2.0)
OTHER_BANDS = (0.05, 0.10, 0.15, 0.20)
NEMOTRON_FRAME_S = 0.08          # one frame of the model, as wordflow's own comment gives it (16 frames are 1.28 s)
PAUSE_S = 0.5                    # a gap between two words this long is a pause, for the loudness
PERCENTILES = (5, 25, 50, 75, 95)


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {"n": len(ordered), **{f"p{p}": ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))] for p in PERCENTILES}}


# ------------------------------------------------------------ who spoke

def app_reading(record: dict | None, reference: Reference) -> dict:
    """The label check as the app sends it, counted word by word on its own rows."""
    if record is None:
        return {"not_run": True}
    rows = record["lines"]
    page = who.line_page(rows, reference)
    labels = {int(n): label for n, label in (record.get("labels") or {}).items()} or None
    return {**who.count(page, reference, labels, rows), "rows": len(rows), "failed": not record["call"]["ok"],
            "failure": record["call"]["failure"], "refused": bool(record.get("refusal")),
            "prompt_tokens": record["call"]["prompt_tokens"], "output_tokens": record["call"]["output_tokens"],
            "seconds": round(record["call"]["wall_ms"] / 1000, 1)}


def voice_by_source(arm: str, name: str, voice_results: dict, lines: list[dict], reference: Reference,
                    own_labels: dict | None, band: float = voice.BAND) -> dict:
    """For each voice the page was read with: the voice's reading and the
    two together (with the bench's own label check, which reads the same
    lines), counted word by word; made again from the stored distances."""
    page, found = who.line_page(lines, reference), {}
    for (v_arm, chain), record in sorted(voice_results.items()):
        if v_arm != arm or not chain.startswith(name + "--from-") or record.get("not_run") or record.get("failure"):
            continue
        readings = {}
        for line in record["lines"]:
            distance = line["distance"]
            if distance is None or line["length_s"] < voice.LEAST_LINE_S:
                readings[line["n"]] = "unsure"
            else:
                readings[line["n"]] = "doctor" if distance < voice.CLUSTER_THRESHOLD - band else (
                    "not_doctor" if distance > voice.CLUSTER_THRESHOLD + band else "unsure")
        by_voice = who.voice_labels(readings)
        found[record["doctor_voice"]] = {"voice": who.count(page, reference, by_voice, lines),
                                         "together": who.count(page, reference, who.together(own_labels, by_voice), lines)}
    return found


# ------------------------------------------------------- the other values

def best_closeness(word: str, drugs: DrugList, cache: dict) -> float:
    if word not in cache:
        near = difflib.get_close_matches(word, drugs.one_word, n=1, cutoff=min(OTHER_CLOSENESS))
        cache[word] = difflib.SequenceMatcher(None, word, near[0]).ratio() if near else 0.0
    return cache[word]


def closeness_table(page, occurrences: list[dict], drugs: DrugList, cache: dict) -> dict:
    """For each other value of the closeness: the drug names written wrongly
    that the list would mark, and the rightly written words it would mark."""
    name_words = {w for occ in occurrences if not occ["caught"] for w in occ["page_words"]}
    wrong_names = sum(1 for occ in occurrences if not occ["caught"] and occ["page_words"])
    found = {}
    for value in OTHER_CLOSENESS:
        marked = [i for i, word in enumerate(page.words)
                  if len(word) >= LEAST_DOUBT_LETTERS and word.isalpha() and drugs.in_list_at(page.words, i) is None
                  and best_closeness(word, drugs, cache) >= value]
        names_marked = sum(1 for occ in occurrences if not occ["caught"] and any(w in marked for w in occ["page_words"]))
        found[f"{value:.2f}"] = {"names_marked": names_marked, "names_written_wrongly": wrong_names,
                                 "right_words_marked": sum(1 for i in marked if page.kind_of.get(i) == "heard" and i not in name_words),
                                 "marks": len(marked)}
    return found


def word_close_table(results: dict) -> dict:
    """The largest gap inside a word that each Nemotron result stored, and
    whether each other value of the close of a word would have cut a word.
    Only the largest gap is stored, so how many words is not known."""
    found = {}
    for (arm, name), result in sorted(results.items()):
        notes = ((result.get("stop") or {}).get("notes") or {})
        if arm != "nemotron" or "largest_gap_inside_word_frames" not in notes:
            continue
        gap_s = round(notes["largest_gap_inside_word_frames"] * NEMOTRON_FRAME_S, 2)
        found[name] = {"largest_gap_s": gap_s, "tokens_after_close_by_time": notes.get("tokens_after_close_by_time"),
                       "would_cut": {f"{v:.1f}": gap_s >= v for v in OTHER_WORD_CLOSE_S}}
    return found


# ------------------------------------------------------------ the loudness

def loudness_of(result: dict, tokens: list[dict]) -> dict:
    """The loudness of the windows inside words and of the windows in
    pauses, by the word times of WhisperX at Stop."""
    windows, window_s = result["loudness"]["dbfs"], result["loudness"]["window_s"]
    timed = [t for t in tokens if t["start"] is not None]
    speech, pause = set(), set()
    for token in timed:
        speech.update(range(int(token["start"] / window_s), int(token["end"] / window_s) + 1))
    for before, after in zip(timed, timed[1:]):
        if after["start"] - before["end"] >= PAUSE_S:
            pause.update(range(int(before["end"] / window_s) + 2, int(after["start"] / window_s) - 1))
    level = lambda i: -120.0 if windows[i] is None else windows[i]            # noqa: E731
    in_speech = [level(i) for i in sorted(speech - pause) if i < len(windows)]
    in_pause = [level(i) for i in sorted(pause - speech) if 0 <= i < len(windows)]
    return {"speech": _percentiles(in_speech), "pause": _percentiles(in_pause),
            "speech_at_or_below": {str(f): sum(1 for v in in_speech if v <= f) for f in (QUIET_DBFS, SPEECH_DBFS)},
            "pause_above": {str(f): sum(1 for v in in_pause if v > f) for f in (QUIET_DBFS, SPEECH_DBFS)},
            "rule_figure_dbfs": QUIET_DBFS, "check_figure_dbfs": SPEECH_DBFS}


def _clock(seconds: float | None) -> str:
    return "?" if seconds is None else f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def listen_lists(name: str, rec_one: dict, tokens: list[dict], reference: Reference) -> dict:
    """The two lists for a person who listens: the words the wider rule
    let through, and the places where every arm agreed against the script."""
    let_through = []
    for arm, row in sorted(rec_one["arms"].items()):
        for page_name in ("stop", "live"):
            for word in (row.get(page_name) or {}).get("rule", {}).get("invented_let_through", []):
                let_through.append({"recording": name, "arm": arm, "page": page_name, "at": _clock(word["piece"][0]),
                                    "word": word["word"], "loudest_dbfs": word["loudest_dbfs"]})
    at_index = {p.spoken: tokens[p.page] for p in align(reference.norms, [t["norm"] for t in tokens])
                if p.page is not None and p.spoken is not None}
    agreed = [{"recording": name, "at": _clock((at_index.get(a["index"]) or {}).get("start")), "speech": a["speech"],
               "script": a["spoken"], "written": a["written"], "touches": a["touches"], "arms": len(a["arms"])}
              for a in sorted(rec_one["agreed"], key=lambda a: (not a["touches"], a["index"])) if a["kind"] == "agreed"]
    return {"let_through": let_through, "agreed": agreed}


# -------------------------------------------- what the app would send

def app_sizes(result: dict, record: dict | None, mapping: dict, per_line: float | None, chars_per_token: float | None) -> dict:
    """The lines the app would send to its label check and the size of that
    call, beside its limits; and the size of the app's own note call, as the
    app numbers and sends the lines at Stop. No call is made for this: the
    label check's tokens are those of the stored call, and the note's are
    worked out from the letters by this run's own measure."""
    rows = calls.app_rows(result)
    label_job, note_job = APP_JOBS["label_check"], APP_JOBS["note"]
    reply_needed = None if per_line is None else round(len(rows) * per_line)
    labelled = [{"n": r["n"], "text": r["text"],
                 "label": {"DOCTOR": "doctor", "PATIENT": "patient"}.get(mapping.get(str(r["speaker"]), ""), "unsure")} for r in rows]
    turns = app_note.turns_of(labelled)
    note_chars = len(jobs.prompt_text("note")) + len(app_note.turns_text(turns))
    note_tokens = None if chars_per_token is None else round(note_chars / chars_per_token)
    return {"label_check": {"lines": len(rows), "request_tokens": (record or {}).get("call", {}).get("prompt_tokens"),
                            "reply_tokens_needed": reply_needed, "reply_limit": label_job.max_tokens,
                            "context": GEMMA_4_QAT.context,
                            "fits": None if reply_needed is None else reply_needed <= label_job.max_tokens},
            "note": {"turns": len(turns), "request_tokens_about": note_tokens, "reply_limit": note_job.max_tokens,
                     "context": GEMMA_4_QAT.context,
                     "fits": None if note_tokens is None else note_tokens + note_job.max_tokens <= GEMMA_4_QAT.context}}


def measures(call_results: dict) -> tuple[float | None, float | None]:
    """This run's own measures: the tokens of one line of a label check's
    reply, and the letters to a token of a request."""
    per_line = [r["call"]["output_tokens"] / len(r["lines"]) for (job, _), r in call_results.items()
                if job in calls.LABEL_JOBS and r["call"]["ok"] and r["call"].get("output_tokens") and r.get("lines")]
    letters = [(len(jobs.prompt_text("note")) + len(r["user"])) / r["call"]["prompt_tokens"] for (job, _), r in call_results.items()
               if job in ("note", "script_note") and r["call"].get("prompt_tokens")]
    return (round(statistics.median(per_line), 2) if per_line else None,
            round(statistics.median(letters), 3) if letters else None)


# ------------------------------------------------------------------ all

def score_all(scored: dict, results: dict, voice_results: dict, call_results: dict, listed: list[Recording],
              script_folders: list[Path], marks_file: dict, drugs: DrugList | None) -> dict:
    per_line, chars_per_token = measures(call_results)
    found = {"recordings": {}, "measures": {"reply_tokens_per_line": per_line, "letters_per_token": chars_per_token},
             "word_close": {"figure_s": WORD_CLOSE_S, "by_recording": word_close_table(results)},
             "figures": {"closeness": CLOSE_AT, "band": voice.BAND, "cluster_threshold": voice.CLUSTER_THRESHOLD}}
    cache: dict = {}
    for recording in listed:
        mine = {arm: r for (arm, name), r in results.items() if name == recording.name}
        if recording.voice_only or not mine:
            continue
        entry = tables.entry_for(marks_file, recording.script_key)
        reference = build(tables.find_script(recording, script_folders), recording.last_speech, recording.read_differently)
        rec_one = scored["recordings"][recording.name]
        rec = {"pages": {}, "speeches": len(reference.speeches)}
        heard_last = 0
        for arm, result in sorted(mine.items()):
            if result.get("failure"):
                rec["pages"][arm] = {"failed": result["failure"]}
                continue
            lines = model_lines.lines_of(pages.stop_pieces(result))
            page = who.line_page(lines, reference)
            if arm in tables.COUNT_FOR_AGREEMENT:
                heard_last = max([heard_last] + [reference.words[page.spoken_of[w]].speech for w in page.heard_indexes()])
            own = call_results.get(("label_check", calls.chain_name(arm, recording.name, None)))
            own_labels = {int(n): label for n, label in ((own or {}).get("labels") or {}).items()} or None
            app = call_results.get(("label_check_app", calls.chain_name(arm, recording.name, None)))
            one = rec_one["arms"][arm]
            mapping = one["stop"]["who_spoke"]["mapping"]
            row = {"who_app": app_reading(app, reference),
                   "voice": voice_by_source(arm, recording.name, voice_results, lines, reference, own_labels),
                   "voice_bands": {f"{band:.2f}": voice_by_source(arm, recording.name, voice_results, lines, reference, own_labels, band)
                                   for band in OTHER_BANDS},
                   "sizes": app_sizes(result, app, mapping, per_line, chars_per_token),
                   "alba": alba.summary((one.get("live") or one["stop"]).get("alba") or []) if arm not in UPLOADS else None}
            if drugs is not None:
                row["closeness"] = closeness_table(page, doubt.drug_occurrences(page, reference, entry.get("drugs", {})), drugs, cache)
            if result.get("upload"):
                up = result["upload"]
                row["upload"] = {"seconds_to_result": up["seconds_to_result"], "counted_s": up["counted_s"], "gone": up["gone"],
                                 "proof": up["proof"], "applied": up["applied"],
                                 "upload_host": (up.get("job") or {}).get("upload_host")}
            rec["pages"][arm] = row
        rec["last_speech_heard"] = heard_last
        wx = mine.get("whisperx_pyannote")
        if wx is not None and not wx.get("failure"):
            tokens = voicecut.timed_tokens(wx, reference)
            rec["loudness"] = loudness_of(wx, tokens)
            rec["listen"] = listen_lists(recording.name, rec_one, tokens, reference)
        found["recordings"][recording.name] = rec
    found["kinds"] = kind_rows(scored, found)
    return found


def _sum(counts: list[dict], key: str) -> int:
    return sum(c.get(key, 0) for c in counts)


def kind_rows(scored: dict, five: dict) -> dict:
    """One row for each of the eight kinds of page, over the recordings."""
    rows = {}
    two = scored.get("part_two") or {"recordings": {}, "arms": {}}
    for arm, title in KINDS:
        ones = [rec["arms"][arm] for rec in scored["recordings"].values() if arm in rec["arms"]]
        good = [one["stop"] for one in ones if "failed" not in one]
        mine = [rec["pages"][arm] for rec in five["recordings"].values() if arm in rec["pages"] and "failed" not in rec["pages"][arm]]
        twos = [rec["arms"][arm] for rec in two["recordings"].values() if arm in rec["arms"]]
        total_two = two["arms"].get(arm, {})
        alba_rows = [r for rec in scored["recordings"].values() if arm in rec["arms"] and "failed" not in rec["arms"][arm]
                     for r in ((rec["arms"][arm].get("live") or rec["arms"][arm]["stop"]).get("alba") or [])]
        sources: dict[str, list] = {}
        for page in mine:
            for source, counted in page["voice"].items():
                sources.setdefault(source, []).append(counted)
        rows[arm] = {
            "title": title, "pages": len(good), "failed": len(ones) - len(good),
            "passages_without_sign": _sum([p["hard"] for p in good], "passages_without_sign"),
            "words_from_silence": _sum([p["hard"] for p in good], "words_from_silence"),
            "wrong_drug": total_two.get("wrong_drug"), "wrong_drug_notes": total_two.get("wrong_drug_notes"),
            "drugs_caught": _sum([p["drugs"] for p in good], "caught"), "drugs_spoken": _sum([p["drugs"] for p in good], "spoken"),
            "facts_not_found_script_found": total_two.get("facts_not_found_script_found"),
            "facts_not_found": total_two.get("facts_not_found"),
            "wrong_speaker": {
                "choice": _sum([t["who"]["counts"]["choice"] for t in twos], "wrong"),
                "label_check_app": _sum([p["who_app"] for p in mine], "wrong"),
                "label_check_app_failed": sum(1 for p in mine if p["who_app"].get("failed") or p["who_app"].get("refused")),
                "label_check_own": _sum([t["who"]["counts"]["label_check"] for t in twos], "wrong"),
                "label_check_own_failed": sum(1 for t in twos if t["label_check"]["failed"] or t["label_check"]["refused"]),
                "voice": {s: _sum([c["voice"] for c in cs], "wrong") for s, cs in sorted(sources.items())},
                "together": {s: _sum([c["together"] for c in cs], "wrong") for s, cs in sorted(sources.items())}},
            "alba": None if arm in UPLOADS else alba.summary(alba_rows)}
    return rows


# ------------------------------------------------------------------ tables

def _alba_cell(found: dict | None) -> str:
    if found is None:
        return "no live text"
    serves, way = found["serves"], found["by_sound"]
    within = way["within"].get(str(alba.SERVES_WITHIN_S), 0)
    typical = "typical: late" if serves["typical"] is None and serves["judged"] else f"typical {serves['typical']} s"
    return (f"{'yes' if serves['yes'] else 'no'} (a reading; by {serves['by']}: {typical}; "
            f"{within} of {way['n']} within {alba.SERVES_WITHIN_S} s by the sound; "
            f"{found['after_reply']} of {found['speeches']} final only after the reply began)")


def first_table(kinds: dict) -> list[str]:
    lines = ["| kind of page | passage missing with no sign | words where nobody spoke | a drug written as another real drug | "
             "drug names caught of spoken | key facts not found that both script notes found | words under the wrong speaker: "
             "choice / label check as the app sends it / label check, the bench's own / voice by source / the two together | "
             "serves Alba |", "|---|---|---|---|---|---|---|---|"]
    for arm, _ in KINDS:
        row = kinds.get(arm)
        if not row or not row["pages"]:
            lines.append(f"| {dict(KINDS)[arm]} | no page{' (failed: ' + str(row['failed']) + ')' if row and row['failed'] else ''} | | | | | | |")
            continue
        w = row["wrong_speaker"]
        notes = row["wrong_drug_notes"] or {"notes": 0, "holding": 0}
        drug = "not scored" if row["wrong_drug"] is None else (
            f"yes, {row['wrong_drug']}; in {notes['holding']} of {notes['notes']} notes" if row["wrong_drug"] else "no")
        by_source = lambda d: ", ".join(f"{s}: {n}" for s, n in d.items()) or "not run"      # noqa: E731
        who_cell = (f"{w['choice']} / {w['label_check_app']} ({w['label_check_app_failed']} of {row['pages']} pages failed) / "
                    f"{w['label_check_own']} ({w['label_check_own_failed']} failed) / {by_source(w['voice'])} / {by_source(w['together'])}")
        lines.append(f"| {row['title']} ({row['pages']} pages{', ' + str(row['failed']) + ' failed' if row['failed'] else ''}) | "
                     f"{tables.yes_no(row['passages_without_sign'])} | {tables.yes_no(row['words_from_silence'])} | {drug} | "
                     f"{row['drugs_caught']} of {row['drugs_spoken']} | {row['facts_not_found_script_found']} "
                     f"(of {row['facts_not_found']} not found) | {who_cell} | {_alba_cell(row['alba'])} |")
    return lines


def as_markdown(five: dict) -> str:
    lines = ["", "# The tables of 5e", "", "## For the patient: one row for each of the eight kinds of page", "",
             *first_table(five["kinds"]), "",
             "The line for Alba of a WhisperX row is from its live text. The voice and the two together are given for "
             "each voice the pages were read with; a voice is never used on the recording it was cut from.", ""]
    lines += ["## The line for Alba, in full", "",
              "| live arm | recording | speeches | by the choice: n, typical, longest, within 0.8 / 1.5 / 3.0 | "
              "by the sound: n, typical, longest, within 0.8 / 1.5 / 3.0 | final only after the reply began | counted apart |",
              "|---|---|---|---|---|---|---|"]
    for name, rec in sorted(five["recordings"].items()):
        for arm, _ in KINDS:
            found = (rec["pages"].get(arm) or {}).get("alba")
            if found:
                cell = lambda w: f"{w['n']}, {w['median']}, {w['longest']}, {' / '.join(str(v) for v in w['within'].values())}"   # noqa: E731
                lines.append(f"| {arm} | {name} | {found['speeches']} | {cell(found['by_choice'])} | {cell(found['by_sound'])} | "
                             f"{found['after_reply']} | {found['apart'] or 'none'} |")
    lines += ["", "## The label check as the app sends it, and what the app would send", "",
              f"One line of a label check's reply: {five['measures']['reply_tokens_per_line']} tokens, measured on this run's "
              f"calls. Letters to a token of a request: {five['measures']['letters_per_token']}. No call was made for the note's size.", "",
              "| recording | kind of page | lines the app sends | request tokens | reply tokens needed | reply limit | fits | the call | "
              "words right / wrong / unsure | the app's note call: turns, request tokens about, fits the context |", "|---|---|---|---|---|---|---|---|---|---|"]
    for name, rec in sorted(five["recordings"].items()):
        for arm, _ in KINDS:
            page = rec["pages"].get(arm)
            if not page or "failed" in page:
                continue
            size, app = page["sizes"], page["who_app"]
            call = "not run" if app.get("not_run") else ("failed: " + str(app["failure"]) if app["failed"] else (
                "refused" if app["refused"] else f"ok, {app['output_tokens']} tokens, {app['seconds']} s"))
            lines.append(f"| {name} | {arm} | {size['label_check']['lines']} | {size['label_check']['request_tokens']} | "
                         f"{size['label_check']['reply_tokens_needed']} | {size['label_check']['reply_limit']} | "
                         f"{size['label_check']['fits']} | {call} | {app.get('right')} / {app.get('wrong')} / {app.get('unsure')} | "
                         f"{size['note']['turns']}, {size['note']['request_tokens_about']}, {size['note']['fits']} |")
    return "\n".join(lines + _more_markdown(five)) + "\n"


def _more_markdown(five: dict) -> list[str]:
    lines = ["", "## The voice method, by source, and the band set again", "",
              "The voice was learnt in the same room, on the same day and with the same microphone as the pages it read: "
              "this is kinder to the method than real life.", "",
              "| recording | kind of page | voice | band | voice: right / wrong / unsure | together: right / wrong / unsure |", "|---|---|---|---|---|---|"]
    for name, rec in sorted(five["recordings"].items()):
        for arm, _ in KINDS:
            page = rec["pages"].get(arm)
            for band, by_source in sorted(((page or {}).get("voice_bands") or {}).items()):
                for source, c in sorted(by_source.items()):
                    lines.append(f"| {name} | {arm} | {source} | {band} | {c['voice']['right']} / {c['voice']['wrong']} / {c['voice']['unsure']} | "
                                 f"{c['together']['right']} / {c['together']['wrong']} / {c['together']['unsure']} |")
    lines += ["", "## The uploads", "", "| recording | service | seconds to the result | seconds the service counted | gone | the proof | "
              "what the service says it applied | the host it named for the file |", "|---|---|---|---|---|---|---|---|"]
    for name, rec in sorted(five["recordings"].items()):
        for arm in UPLOADS:
            up = (rec["pages"].get(arm) or {}).get("upload")
            if up:
                lines.append(f"| {name} | {arm} | {up['seconds_to_result']} | {up['counted_s']} | {up['gone']} | {up['proof']} | "
                             f"{up['applied']} | {up['upload_host'] or 'held with the job'} |")
    lines += ["", "## What other values of the draft figures would have given", "",
              f"No figure of the code was changed: the closeness is {five['figures']['closeness']}, the close of a word "
              f"{five['word_close']['figure_s']} s, the band {five['figures']['band']}.", "",
              "| recording | kind of page | closeness | drug names written wrongly that the list marks | rightly written words it marks |",
              "|---|---|---|---|---|"]
    for name, rec in sorted(five["recordings"].items()):
        for arm, _ in KINDS:
            for value, c in sorted(((rec["pages"].get(arm) or {}).get("closeness") or {}).items()):
                lines.append(f"| {name} | {arm} | {value} | {c['names_marked']} of {c['names_written_wrongly']} | {c['right_words_marked']} |")
    lines += ["", "| recording | the largest gap inside a word, Nemotron | " + " | ".join(f"{v} s would have cut a word" for v in OTHER_WORD_CLOSE_S)
              + " |", "|---|---|" + "---|" * len(OTHER_WORD_CLOSE_S)]
    for name, c in sorted(five["word_close"]["by_recording"].items()):
        lines.append(f"| {name} | {c['largest_gap_s']} s | " + " | ".join("yes" if v else "no" for v in c["would_cut"].values()) + " |")
    lines += ["", "Only the largest gap of a recording is stored, so how many words a smaller value would have cut is not known.", "",
              "## The loudness of the recordings, and whether each reading is whole", ""]
    for name, rec in sorted(five["recordings"].items()):
        lines.append(f"- {name}: the last speech in which an arm with a model of its own heard a word is {rec['last_speech_heard']} "
                     f"of {rec['speeches']}.")
        loud = rec.get("loudness")
        if loud:
            lines.append(f"  Windows inside words: {loud['speech']}; at or below the rule's and the check's figure: {loud['speech_at_or_below']}. "
                         f"Windows in pauses: {loud['pause']}; above each figure: {loud['pause_above']}.")
    lines += ["", "## Two lists for a person who listens", "", "### The words the wider rule let through", ""]
    for name, rec in sorted(five["recordings"].items()):
        lines += [f"- {w['recording']} at {w['at']}, {w['arm']} ({w['page']}): {w['word']} (loudest {w['loudest_dbfs']} dBFS)"
                  for w in (rec.get("listen") or {}).get("let_through", [])]
    lines += ["", "### The places where every arm agreed against the script", ""]
    for name, rec in sorted(five["recordings"].items()):
        lines += [f"- {a['recording']} at {a['at']}, speech {a['speech']}: the script has {a['script']}, {a['arms']} arms wrote "
                  f"{a['written']}{' [' + ', '.join(a['touches']) + ']' if a['touches'] else ''}"
                  for a in (rec.get("listen") or {}).get("agreed", [])]
    return lines
