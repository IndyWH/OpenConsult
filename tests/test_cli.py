"""The command: start, the taken port, reset-password
(spec 15.6; D26; ruling 6; V1_LESSONS 7.6)."""

import socket

import pytest

from openconsult import words
from openconsult.cli import main
from openconsult.patients.users import MIN_PASSWORD
from openconsult.settings.store import LISTEN_ON
from tests.conftest import PASSWORD, log_in, set_up


class Said:
    def __init__(self):
        self.lines = []

    def __call__(self, line):
        self.lines.append(line)

    @property
    def text(self):
        return "\n".join(self.lines)


def never_serve(app, host, port):
    raise AssertionError("the app must not start")


def test_7_6_a_taken_port_is_said_in_plain_words_and_the_app_stops(tmp_path):
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind((LISTEN_ON, 0))
    holder.listen()
    port = holder.getsockname()[1]
    said = Said()
    try:
        code = main(["--data-folder", str(tmp_path), "--port", str(port)], say=said, serve=never_serve)
    finally:
        holder.close()
    assert code == 1
    assert words.PORT_TAKEN.format(port=port) in said.text
    assert not (tmp_path / "openconsult.db").exists()


def test_ruling_6_the_command_gives_no_way_to_listen_beyond_this_computer(tmp_path, machine):
    served = {}

    def serve(app, host, port):
        served.update(host=host, port=port)

    said = Said()
    assert main(["--data-folder", str(tmp_path), "--port", "0", "--no-browser"], say=said, serve=serve, machine=machine) == 0
    assert served["host"] == "127.0.0.1"
    assert words.RUNNING.format(address="http://127.0.0.1:0") in said.text
    with pytest.raises(SystemExit):
        main(["--host", "0.0.0.0", "--data-folder", str(tmp_path)], say=said, serve=serve, machine=machine)


def answers(*replies):
    replies = iter(replies)
    return lambda prompt: next(replies)


def test_d26_the_reset_command_changes_the_password_and_nothing_else(logged_in, app, tmp_path):
    before = app.state.parts.users.get()
    said = Said()
    code = main(["reset-password", "--data-folder", str(tmp_path)],
                say=said, ask=answers("third-password", "third-password"))
    assert code == 0 and words.RESET_DONE in said.text
    users = app.state.parts.users
    assert users.verify("third-password") and not users.verify(PASSWORD)
    after = users.get()
    assert (after.title, after.name) == (before.title, before.name)
    assert app.state.parts.audit.lines()[0].event == "password.reset"
    # The running app sees the reset: every login has ended.
    assert logged_in.get("/").headers["location"] == "/login?why=password_changed"
    assert log_in(logged_in, "third-password").status_code == 303


@pytest.mark.parametrize("replies, message", [
    (("seven77", "seven77"), words.RESET_SHORT.format(least=MIN_PASSWORD)),
    (("eight888", "eight889"), words.RESET_DIFFER),
])
def test_d26_the_reset_command_refuses_a_short_or_mismatched_password(client, app, tmp_path, replies, message):
    set_up(client)
    said = Said()
    code = main(["reset-password", "--data-folder", str(tmp_path)], say=said, ask=answers(*replies))
    assert code == 1 and message in said.text
    assert app.state.parts.users.verify(PASSWORD)
    assert app.state.parts.audit.lines()[0].event == "user.set_up"


def test_d26_the_reset_command_says_when_there_is_no_user_yet(client, tmp_path):
    said = Said()
    assert main(["reset-password", "--data-folder", str(tmp_path / "empty")], say=said, ask=answers()) == 1
    assert words.RESET_NO_USER in said.text
    client.get("/first-run")  # the app has made its database, but no user yet
    assert main(["reset-password", "--data-folder", str(tmp_path)], say=said, ask=answers()) == 1
    assert said.lines[-1] == words.RESET_NO_USER


def test_d26_the_reset_command_takes_no_password_on_the_command_line(tmp_path):
    with pytest.raises(SystemExit) as stopped:
        main(["reset-password", "a-password", "--data-folder", str(tmp_path)], say=Said(), ask=answers())
    assert stopped.value.code == 2


def test_15_9_the_commands_name_their_choice_and_none_named_is_whisperx(tmp_path):
    # --choice takes the four names; anything else is refused by the command itself.
    with pytest.raises(SystemExit) as stopped:
        main(["self-test", "--choice", "made-up", "--data-folder", str(tmp_path)], say=Said())
    assert stopped.value.code == 2
    seen = []

    def make_speech(folder, choice):
        seen.append(choice.name)
        from openconsult.speech.door import Door
        return Door(choice, make_worker=lambda: None, installed=lambda: False)

    main(["self-test", "--data-folder", str(tmp_path)], say=Said(), make_speech=make_speech, sleep=lambda s: None)
    main(["self-test", "--choice", "assemblyai", "--data-folder", str(tmp_path)], say=Said(), make_speech=make_speech,
         sleep=lambda s: None)
    assert seen == ["whisperx_pyannote", "assemblyai"]
