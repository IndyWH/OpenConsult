"""The tables of the test of 5d, from what the judge gives (spec 15.9,
the details of 5d; 15.8 ruling 26): the same bytes from the same
results, never written over. The first table is the most important for
the patient: a row for each way of the language model with each speech
choice, a column for each embedding setup, and in each cell works, not
working with the first line missed, or not judged with the line. Every
figure of the card is in MiB, as the sampler writes it."""

from __future__ import annotations

import json
from pathlib import Path

from openconsult.bench.shared.judge import EMBEDDINGS, SPEECH, WAYS, WHERE
from openconsult.bench.writer import Refused

WAY_WORDS = {"ollama-one": "Ollama, one after another", "ollama-together": "Ollama, together (the private process)",
             "vllm-one": "vLLM, one after another", "vllm-together": "vLLM, together"}
SPEECH_WORDS = {"nemotron": "Nemotron", "whisperx": "WhisperX with pyannote"}
EMBED_WORDS = {"first": "the first EmbeddingGemma", "second": "EmbeddingGemma 2"}
COLUMNS = [f"{m}-{w}" for m in EMBEDDINGS for w in WHERE]


def _s(value, places=2) -> str:
    return "-" if value is None else f"{value:.{places}f}"


def cell(setup: dict | None) -> str:
    if setup is None:
        return "not run"
    if setup["works"] is True:
        return "works"
    if setup["works"] is False:
        return f"not working (line {setup['first_missed']})"
    return f"not judged (line {', '.join(str(n) for n in setup['not_judged'])})"


def first_table(found: dict) -> list[str]:
    by = {(s["way"], s["speech"], f"{s['embedding']}-{s['where']}"): s for s in found["setups"]}
    head = "| way of the language model, speech choice | " + " | ".join(
        f"{EMBED_WORDS[c.split('-')[0]]} on the {c.split('-')[1]}" for c in COLUMNS) + " |"
    lines = [head, "|---|" + "---|" * len(COLUMNS)]
    for way in WAYS:
        for speech in SPEECH:
            cells = [cell(by.get((way, speech, c))) for c in COLUMNS]
            lines.append(f"| {WAY_WORDS[way]}, {SPEECH_WORDS[speech]} | " + " | ".join(cells) + " |")
    return lines


def counts_lines(found: dict) -> list[str]:
    lines = []
    for engine in ("ollama", "vllm"):
        c = found["counts"][engine]
        lines.append(f"On {'Ollama' if engine == 'ollama' else 'vLLM'}: {c['works']} setups work, {c['not working']} do not, "
                     f"{c['not judged']} not judged.")
    return lines


def steadiness_table(found: dict) -> list[str]:
    lines = ["| way | base line before (s) | after (s) | difference (s) | line three judged against |",
             "|---|---|---|---|---|"]
    for way in WAYS:
        s = found["steadiness"][way]
        against = f"{_s(s['mean'])} s" if s["judged"] else f"not judged: {s['reason']}"
        lines.append(f"| {WAY_WORDS[way]} | {_s(s['before'])} | {_s(s['after'])} | {_s(s['difference'])} | {against} |")
    return lines


def setup_rows(setups: list[dict]) -> list[str]:
    lines = ["| setup | word | line 1 | line 2 | line 3: typical pass, alone, longer (s) | "
             "line 4: typical wait, alone, lines (setup, alone) | slowest pass (s) | alarm's answer (s) | Stop (s) | "
             "after Stop (s) | search (s) | late starts | words that differ |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in setups:
        l1, l2, l3, l4 = (s["lines"][n] for n in "1234")
        m = s["measured"]
        four = (f"{_s(l4['setup']['typical_s'])}, {_s(l4['base']['typical_s'])}, {l4['setup']['lines']}, {l4['base']['lines']}"
                if l4.get("setup") and l4.get("base") else "-")
        lines.append(f"| {s['name']} | {s['word']} | {'met' if l1['met'] else 'missed: ' + str(l1['reason'])} | "
                     f"{'met' if l2['met'] else 'missed: ' + str(l2['reason'])} | "
                     f"{_s(l3['typical_s'])}, {_s(l3['base_s'])}, {_s(l3.get('longer_s'))}"
                     f"{'' if l3['met'] is not None else ' (not judged)'} | {four}"
                     f"{'' if l4['met'] is not False else ' (missed)'}{'' if l4['met'] is not None else ' (not judged)'} | "
                     f"{_s(m['slowest_pass_s'])} | {_s(m['alarm_answer_s'])} | {_s(m['stop_s'])} | "
                     f"{_s(m['after_stop_typical_s'])} | {_s(m['search_median_s'], 3)} | {m['late_starts'] if m['late_starts'] is not None else '-'} | "
                     f"{m.get('words_differ_from_alone') if m.get('words_differ_from_alone') is not None else '-'} |")
    return lines


def reasons_lines(setups: list[dict]) -> list[str]:
    lines = []
    for s in setups:
        if s["works"] is False:
            lines.append(f"- {s['name']}: not working, line {s['first_missed']}: {s['lines'][str(s['first_missed'])]['reason']}")
        elif s["works"] is None:
            lines.append(f"- {s['name']}: not judged, line {', '.join(str(n) for n in s['not_judged'])}: "
                         + "; ".join(str(s["lines"][str(n)]["reason"]) for n in s["not_judged"]))
    return lines or ["(every setup works)"]


def halves_table(setups: list[dict]) -> list[str]:
    lines = ["| setup | stretch (s of the recording) | first half: wait, lines (setup; alone) | second half: wait, lines (setup; alone) | growth (setup; alone) |",
             "|---|---|---|---|---|"]
    for s in setups:
        l4 = s["lines"]["4"]
        if not l4.get("setup"):
            continue
        a, b = l4["setup"], l4["base"]
        lines.append(f"| {s['name']} | {l4['stretch_s'][0]:.1f} to {l4['stretch_s'][1]:.1f} | "
                     f"{_s(a['first_half_s'])}, {a['first_half_lines']}; {_s(b['first_half_s'])}, {b['first_half_lines']} | "
                     f"{_s(a['second_half_s'])}, {a['second_half_lines']}; {_s(b['second_half_s'])}, {b['second_half_lines']} | "
                     f"{_s(a['growth_s'])}; {_s(b['growth_s'])} |")
    return lines


def card_table(setups: list[dict]) -> list[str]:
    lines = ["| setup | step | in all, highest (MiB) | for each program, highest (MiB) |", "|---|---|---|---|"]
    for s in setups:
        for step, figures in (s["measured"].get("card") or {}).items():
            programs = ", ".join(f"{Path(name).parts[-4] if len(Path(name).parts) > 4 else name} {mib}"
                                 for name, mib in figures["programs_mib_max"].items())
            lines.append(f"| {s['name']} | {step} | {figures['used_mib_max'] if figures['used_mib_max'] is not None else '-'} | {programs or '-'} |")
    return lines


def _speech_cell(summary: dict | None) -> str:
    return "-" if summary is None else f"{summary['lines']}, {_s(summary['stop_s'])}"


def _embed_cell(summary: dict | None) -> str:
    if summary is None:
        return "-"
    return f"{_s(summary['median_s'], 3)}, {summary['searches']}, {summary['failed']}, {summary['late_starts']}"


def base_lines(found: dict) -> list[str]:
    lines = ["| base line | before | after |", "|---|---|---|"]
    b, a = found["base_before"], found["base_after"]
    for way in WAYS:
        lines.append(f"| {WAY_WORDS[way]}, typical pass (s) | {_s(b['lm'][way])} | {_s(a['lm'][way])} |")
    for choice in SPEECH:
        lines.append(f"| {SPEECH_WORDS[choice]} alone: live lines, Stop (s) | "
                     f"{_speech_cell(b['speech'][choice])} | {_speech_cell(a['speech'][choice])} |")
    for key in COLUMNS:
        model, where = key.split("-")
        lines.append(f"| {EMBED_WORDS[model]} on the {where} alone: search (s), searches, failed, late | "
                     f"{_embed_cell(b['embed'][key])} | {_embed_cell(a['embed'][key])} |")
    for key in COLUMNS:
        model, where = key.split("-")
        index = b["index"][key]
        lines.append(f"| {EMBED_WORDS[model]} on the {where}: 250 pieces into vectors (s) | "
                     f"{'-' if index is None else _s(index['seconds'])} | (once) |")
    return lines


def as_markdown(found: dict) -> str:
    lines = ["# The test of 5d: the three models together on one card", "",
             "A setup works when it meets all four lines of ruling 23; not working names the first line it missed; "
             "not judged means line three or four could not be judged and no other line was missed. "
             "A way round is listed apart and counted as no setup. Every card figure is in MiB.", "",
             "## For the patient, first", "", *first_table(found), "", *counts_lines(found), "",
             "## Why, for every setup that does not work or is not judged", "", *reasons_lines(found["setups"]), "",
             "## The pointer: the same setup with the embedding model on the processor", ""]
    for name, twin in sorted(found["pointers"].items()):
        lines.append(f"- {name}: {twin['twin']} reads {twin['word']}" if twin else f"- {name}: no twin on the processor was run")
    lines += ["", "## The ways round, kept apart", ""]
    lines += setup_rows(found["wayrounds"]) if found["wayrounds"] else ["(no way round was run)"]
    lines += ["", "## The base lines, and the steadiness of each way", "", *steadiness_table(found), "", *base_lines(found), "",
              "## The four lines for every setup, with what else was measured", "", *setup_rows(found["setups"]), "",
              "## Line four, the two halves", "", *halves_table(found["setups"] + found["wayrounds"]), "",
              "## The card at each step, in MiB", "", *card_table(found["setups"] + found["wayrounds"]), ""]
    return "\n".join(lines)


def write(folder: Path, found: dict) -> list[Path]:
    """tables.json and tables.md, each written once, never over a file."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    targets = {folder / "tables.json": json.dumps(found, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
               folder / "tables.md": as_markdown(found)}
    for target in targets:
        if target.exists():
            raise Refused(f"{target} exists and is never written over")
    for target, content in targets.items():
        target.write_text(content, encoding="utf-8", newline="\n")      # the same bytes on every system
    return list(targets)
