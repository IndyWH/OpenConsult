"""The teaching bench command (spec 15.14, rulings 7 and 14, the details
of run 10a: The bench, Sampling; the README of the bench material; R18;
rules 7 and 8 of the Claude service's runs). A made engine and a made
service stand behind it: no key, no model, no internet. The material is
made up, and what a model writes is never asserted."""

import itertools
import json

import pytest

from openconsult.bench import claude, teaching
from openconsult.bench.claude import KEY_NAME, NO_DIGEST
from openconsult.bench.cli import main
from openconsult.bench.writer import ResultWriter
from openconsult.llm.vllm import VllmEngine
from openconsult.prompts import loader
from openconsult.settings import keys, paths
from openconsult.teaching import frames
from tests.fakes import CALL, chat_reply, describe
from tests.made_teaching import FITS, PATIENT_OK, write_material

MADE_KEY = "made-up-claude-key-10a-0123456789"
HAIKU = "claude-haiku-5-5"
ROUND = 6 + 4 + 4       # the made material: six lines, four requests and four transcripts in its two cases
WRITER = 3


@pytest.fixture
def folders(tmp_path, monkeypatch):
    """Made material, a folder for results, and a made-up app data folder for the bench to check its folder against."""
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "app-data")
    seeds = itertools.count(1000)
    monkeypatch.setattr(frames.secrets, "randbelow", lambda below: next(seeds))
    return write_material(tmp_path / "material"), tmp_path / "out"


def by_job(body):
    return chat_reply(json.dumps(FITS[body["response_format"]["json_schema"]["name"]]))


def vllm_args(server, material, out, *more, answer=by_job):
    describe(server, VllmEngine)
    server.routes["/v1/chat/completions"] = answer
    return ["teaching", "--material", str(material), "--out", str(out), "--arm", "made-vllm", "--kind", "vllm",
            "--engine", server.address, "--model", CALL.tag, *more]


def stored(out, part):
    return {name: row for (folder, name), row in ResultWriter(out).read_all().items() if folder == part}


def test_part_2_item_3_the_trial_is_four_calls_one_of_each_job_and_no_bench_starts_before_it_held(server, folders, capsys):
    material, out = folders
    args = vllm_args(server, material, out)
    assert main(args) == 4 and server.chats() == []                       # no trial in this folder: nothing is sent
    assert "the trial has not held" in capsys.readouterr().out
    assert main([*args, "--trial"]) == 0
    sent = server.chats()
    assert [body["response_format"]["json_schema"]["name"] for body in sent] == [
        "teaching_case", "teaching_patient", "teaching_examination", "teaching_feedback"]
    assert sorted(stored(out, "trial")) == ["actor__01_made__line03__r0__made-vllm", "examination__01_made__request1__r0__made-vllm",
                                            "feedback__01_made__full__r0__made-vllm", "writer__fresh__run01__r0__made-vllm"]
    assert sent[0]["messages"][1]["content"] == "TOPIC: A made-up topic\nLEVEL: straightforward"
    assert sent[1]["messages"][1]["content"].endswith("THE DOCTOR NOW SAYS:\nAny made-up rash?")
    assert sent[2]["messages"][1]["content"].endswith("THE DOCTOR TYPES:\nExamine made-up one and two.")
    assert "TURNS:\n1. Doctor: Tell me about the made-up ache.\n2. Patient: Reference reply one.\n" in sent[3]["messages"][1]["content"]
    assert main([*args, "--trial"]) == 0 and len(server.chats()) == 4       # the trial is not sent a second time
    # A trial whose reply is not the form, or holds thinking, stops everything after it.
    other = out.parent / "other"
    bad = vllm_args(server, material, other, answer=lambda body: chat_reply(json.dumps({"reply": "no list"})))
    assert main([*bad, "--trial"]) == 4 and "the trial did not hold" in capsys.readouterr().out
    assert main(bad) == 4 and len(server.chats()) == 8
    thinking = vllm_args(server, material, out.parent / "thinking", answer=lambda body: (200, {"choices": [{"message": {
        "role": "assistant", "content": json.dumps(FITS[body["response_format"]["json_schema"]["name"]]), "reasoning_content": "made-up thought"},
        "finish_reason": "stop"}], "usage": {"prompt_tokens": 50, "completion_tokens": 20}}))
    assert main([*thinking, "--trial"]) == 4 and "the reply held thinking" in capsys.readouterr().out


def test_readme_every_call_stands_alone_on_the_reference_replies_and_is_stored_whole_one_file_a_call(server, folders, capsys):
    material, out = folders
    args = vllm_args(server, material, out)
    assert main([*args, "--trial"]) == 0 and main(args) == 0
    assert len(server.chats()) == 4 + 2 * ROUND + WRITER                 # two rounds of the three parts, the writer once (the details: The bench)
    actor, writer = stored(out, "actor"), stored(out, "writer")
    assert len(actor) == 12 and len(stored(out, "examination")) == 8 and len(stored(out, "feedback")) == 8 and len(writer) == WRITER
    # A stored file's name: the part, the case, the item, the round and the arm.
    assert {"actor__01_made__line01__r1__made-vllm", "actor__01_made__line04__r2__made-vllm", "actor__02_made__line02__r1__made-vllm"} <= set(actor)
    assert sorted(writer) == ["writer__fresh__run01__r1__made-vllm", "writer__fresh__run02__r1__made-vllm", "writer__fresh__run03__r1__made-vllm"]
    third = actor["actor__01_made__line03__r1__made-vllm"]
    # Line 3 is sent the lines before it with their reference replies, never the engine's own earlier reply.
    assert ("THE CONSULTATION SO FAR:\nDoctor: Tell me about the made-up ache.\nPatient: Reference reply one.\n"
            "Doctor: Any made-up fever?\nPatient: Reference reply two.\n\nTHE DOCTOR NOW SAYS:\nAny made-up rash?") in third["user"]
    assert PATIENT_OK["reply"] not in third["user"] and "Qdiagone" not in third["user"]
    assert "THE CONSULTATION SO FAR:\n(nothing)\n" in actor["actor__01_made__line01__r1__made-vllm"]["user"]
    # The request and the reply as they crossed the wire, the words, the verdict, the limits and what the line expects.
    wire = json.loads(third["request"])
    assert wire["messages"] == [{"role": "system", "content": loader.prompt("teaching_patient")}, {"role": "user", "content": third["user"]}]
    assert teaching.wire_parts(third["request"]) == (third["system"], third["user"])
    assert json.loads(third["reply"])["choices"][0]["message"]["content"] == third["text"] == json.dumps(PATIENT_OK)
    assert third["ok"] and third["answer"] == PATIENT_OK and third["thinking"] is False and third["failure"] is None
    assert (third["part"], third["case"], third["item"], third["round"], third["arm"], third["job"]) == (
        "actor", "01_made", "line03", 1, "made-vllm", "teaching_patient")
    assert (third["max_tokens"], third["timeout_s"], third["engine"], third["model_tag"]) == (300, 30.0, "vllm", CALL.tag)
    assert third["expected"] == {"n": 3, "kind": "absent", "expects_any": [], "forbids": [], "meets": []}
    assert actor["actor__01_made__line04__r1__made-vllm"]["expected"]["hidden_must_stay"] is True
    assert sorted(third["files"]) == ["teaching.layout.json", "teaching_patient.form.json", "teaching_patient.frame.txt", "teaching_patient.prompt.txt"]
    assert third["files"]["teaching_patient.prompt.txt"] == loader.APPROVED_BYTES["teaching_patient"]
    # The case alone carries its own sampling, a fresh seed each, kept in the file and in the request; the others the profile's.
    seeds = [row["sampling"]["seed"] for row in writer.values()]
    assert len(set(seeds)) == WRITER and all(row["sampling"] == {"temperature": 0.7, "seed": json.loads(row["request"])["seed"], "sent": True}
                                             for row in writer.values())
    assert third["sampling"] == {"temperature": 0.0, "seed": 42, "sent": True} and (wire["temperature"], wire["seed"]) == (0.0, 42)
    # A feedback call: the transcript's lines with their reference replies, the requests named, the answer set named.
    marked = stored(out, "feedback")["feedback__01_made__one_red_flag_missed__r2__made-vllm"]
    assert ("TURNS:\n1. Doctor: Tell me about the made-up ache.\n2. Patient: Reference reply one.\n3. Doctor: Any made-up rash?\n"
            "4. Patient: Reference reply three.\n\nEXAMINED:\nExamine made-up one and two.\nExamine a made-up elbow.\n\n"
            "ANSWERS:\nDifferential diagnosis: Made answer one.") in marked["user"]
    assert marked["expected"]["expects_not_met"] == [2] and marked["expected"]["red_flag_points"] == [2] and marked["expected"]["expects_plan"] == [1, 2]
    # The material is read and never changed; nothing is written outside the out folder.
    assert sorted(path.name for path in material.iterdir()) == ["case_01_made.json", "case_02_made.json", "writer_runs.json"]
    assert "sent 31 calls, kept 0, failed 0" in capsys.readouterr().out


def test_rule_7_a_bench_carried_on_sends_no_finished_call_and_no_failed_call_a_second_time(server, folders, capsys):
    material, out = folders

    def one_bad(body):
        job = body["response_format"]["json_schema"]["name"]
        return chat_reply(json.dumps({"asked": "not a list", "not_in_case": []} if job == "teaching_examination" else FITS[job]))

    args = vllm_args(server, material, out)
    assert main([*args, "--trial"]) == 0
    vllm_args(server, material, out, answer=one_bad)
    assert main([*args, "--part", "actor", "--part", "examination", "--rounds", "1", "--case", "01_made"]) == 0
    assert len(server.chats()) == 4 + 4 + 3
    failed = stored(out, "examination")["examination__01_made__request1__r1__made-vllm"]
    assert not failed["ok"] and failed["failure"] == "bad_form" and failed["detail"] == "answer.asked is not a array" and failed["answer"] is None
    assert json.loads(failed["text"]) == {"asked": "not a list", "not_in_case": []}             # what came back is kept whole
    assert "sent 7 calls, kept 0, failed 3" in capsys.readouterr().out
    vllm_args(server, material, out)
    assert main(args) == 0
    assert len(server.chats()) == 4 + 2 * ROUND + WRITER                     # the seven are not sent again, failed or not
    assert "sent 24 calls, kept 7, failed 0" in capsys.readouterr().out
    assert not stored(out, "examination")["examination__01_made__request1__r1__made-vllm"]["ok"]
    assert main(args) == 0 and len(server.chats()) == 4 + 2 * ROUND + WRITER
    # Another arm, engine or model may not write into this folder.
    assert main([*args[:6], "another-arm", *args[7:]]) == 5


def test_R18_the_out_folder_is_refused_under_the_repo_the_data_folder_and_the_key_folder_and_a_bad_arm_name(server, folders, tmp_path, capsys):
    material, out = folders
    for place in (teaching_repo() / "made-out", tmp_path / "app-data" / "out"):
        assert main(vllm_args(server, material, place, "--trial")) == 6
    assert main(vllm_args(server, material, tmp_path / "data" / "out", "--trial", "--data-folder", str(tmp_path / "data"))) == 6
    assert main(vllm_args(server, material, tmp_path / "keys" / "out", "--trial", "--key-folder", str(tmp_path / "keys"))) == 6
    args = vllm_args(server, material, out, "--trial")
    assert main([*args[:6], "Made__Arm", *args[7:]]) == 9
    assert main(vllm_args(server, tmp_path / "no-material", out, "--trial")) == 3
    assert server.chats() == [] and not out.exists()


def teaching_repo():
    from openconsult.bench.cli import REPO
    return REPO


def claude_args(server, material, out, key_folder, *more):
    return ["teaching", "--material", str(material), "--out", str(out), "--arm", "made-claude", "--kind", "claude",
            "--engine", server.address, "--model", HAIKU, "--key-folder", str(key_folder), "--digest", NO_DIGEST, *more]


def serve_claude(server, monkeypatch, answer):
    monkeypatch.setattr(claude, "ADDRESS", server.address)                  # the made service in the service's place
    server.routes["/v1/models?limit=1000"] = (200, {"data": [{"id": HAIKU, "type": "model", "max_input_tokens": 1000000}], "has_more": False})
    server.routes["/v1/messages"] = answer


def message(body, read=1000, written=100):
    name = next(job for job, fits in FITS.items() if sorted(fits) == sorted(body["output_config"]["format"]["schema"]["properties"]))
    return 200, {"id": "msg_made_up", "type": "message", "role": "assistant", "model": body["model"], "stop_reason": "end_turn",
                 "content": [{"type": "text", "text": json.dumps(FITS[name])}], "usage": {"input_tokens": read, "output_tokens": written}}


def messages(server):
    return [body for path, body in server.received if path == "/v1/messages"]


def key_folder_in(where):
    folder = where / "keys"
    folder.mkdir()
    (folder / keys.KEY_FILE).write_text(f"{KEY_NAME}={MADE_KEY}\n", encoding="utf-8")
    return folder


def test_rule_7_the_claude_arm_stops_by_itself_when_its_cost_passes_the_limit_and_is_carried_on(server, folders, tmp_path, capsys, monkeypatch):
    material, out = folders
    key_folder = key_folder_in(tmp_path)
    serve_claude(server, monkeypatch, lambda body: message(body, read=1_000_000, written=0))       # 0.10 US dollars a call at the named prices
    args = claude_args(server, material, out, key_folder)
    assert main([*args, "--trial"]) == 0 and len(messages(server)) == 4
    assert "0.400 US dollars at 0.1 and 0.5 a million tokens" in capsys.readouterr().out
    assert main([*args, "--max-dollars", "0.65"]) == 11                     # the trial's 0.40, then 0.50, 0.60, 0.70: the fourth is not sent
    said = capsys.readouterr().out
    assert len(messages(server)) == 4 + 3 and "passed 0.65; nothing more is sent" in said and MADE_KEY not in said
    assert main([*args, "--max-dollars", "100"]) == 0 and len(messages(server)) == 4 + 2 * ROUND + WRITER       # carried on; none sent twice
    # Claude is sent no temperature and no seed, for the case as for the others; the file says so and holds no key.
    assert all("temperature" not in body and "seed" not in body and body["model"] == HAIKU for body in messages(server))
    fresh = stored(out, "writer")["writer__fresh__run02__r1__made-claude"]
    assert fresh["sampling"]["sent"] is False and fresh["engine"] == "claude" and fresh["model_digest"] == NO_DIGEST
    assert teaching.wire_parts(fresh["request"]) == (loader.prompt("teaching_case"), "TOPIC: Another made-up topic\nLEVEL: hidden")
    assert teaching.reply_parts(fresh["reply"]) == (json.dumps(FITS["teaching_case"]), False)
    assert MADE_KEY not in json.dumps(list(ResultWriter(out).read_all().values())) and (fresh["prompt_tokens"], fresh["output_tokens"]) == (1_000_000, 0)
    assert teaching.dollars(1_000_000, 1_000_000) == pytest.approx(0.60) and (teaching.PRICE_READ, teaching.PRICE_WRITTEN) == (0.10, 0.50)


def test_rule_8_of_run_9d_three_refusals_for_rate_in_a_row_stop_the_arm_each_stored_and_a_refused_key_is_written_apart(
        server, folders, tmp_path, capsys, monkeypatch):
    material, out = folders
    key_folder = key_folder_in(tmp_path)
    serve_claude(server, monkeypatch, message)
    args = claude_args(server, material, out, key_folder)
    assert main([*args, "--trial"]) == 0
    server.routes["/v1/messages"] = (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "made-up: too fast"}}, {"retry-after": "0"})
    assert main(args) == 11
    refused = stored(out, "actor")
    assert len(messages(server)) == 4 + 3 and len(refused) == 3              # three in a row, each a stored failed call; the fourth is not sent
    assert all(not row["ok"] and row["failure"] == "unreachable" and row["detail"].startswith("HTTP 429") for row in refused.values())
    assert "3 times in a row" in capsys.readouterr().out
    # A refused key never reached a model: the call is written apart and is sent when the bench is carried on.
    server.routes["/v1/messages"] = (401, {"type": "error", "error": {"type": "authentication_error", "message": "made-up: bad key"}})
    assert main(args) == 11 and len(messages(server)) == 4 + 3 + 1 and len(stored(out, "actor")) == 3
    apart = sorted(path.name for path in (out / "results" / "actor" / "stopped").iterdir())
    assert apart == ["actor__01_made__line04__r1__made-claude.json"]
    server.routes["/v1/messages"] = message
    assert main(args) == 0
    assert len(messages(server)) == 4 + 3 + 1 + (2 * ROUND + WRITER - 3)     # the three refused for rate are never sent again; the one apart is
    assert stored(out, "actor")["actor__01_made__line04__r1__made-claude"]["ok"] and MADE_KEY not in capsys.readouterr().out


def test_mail_3_a_trial_of_one_part_is_one_call_and_opens_the_bench_of_that_part_alone(server, folders, capsys):
    # The feedback benched again alone (mail 3 of run 10a): its trial is the one call of that job, and no other part may start on it.
    material, out = folders
    args = vllm_args(server, material, out, "--part", "feedback")
    assert main([*args, "--trial"]) == 0
    assert [body["response_format"]["json_schema"]["name"] for body in server.chats()] == ["teaching_feedback"]
    assert sorted(stored(out, "trial")) == ["feedback__01_made__full__r0__made-vllm"]
    assert main(args) == 0 and len(server.chats()) == 1 + 2 * 4
    assert len(stored(out, "feedback")) == 8 and not stored(out, "actor") and not stored(out, "writer")
    assert main(vllm_args(server, material, out)) == 4 and len(server.chats()) == 1 + 2 * 4
    assert "the trial holds 1 calls, not 4" in capsys.readouterr().out
