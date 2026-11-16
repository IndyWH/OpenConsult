"""The secure store behind the key module (spec 7.2; 7.3 rule 3; 15.13,
the details of run 9b). Every store here is made: a dict in memory, or a
made package behind the app's own wrapper. No test touches the system's
store, and the guard fails one that tries."""

from __future__ import annotations

import time

import pytest

from openconsult.bench.speech import speechmatics_upload, upload_commands
from openconsult.settings import keys, secure
from openconsult.settings.secure import NoStore, SystemStore
from openconsult.speech.choices import SPEECHMATICS
from openconsult.speech.door import make_door
from tests.made_up_store import MadeStore

NAME = "SPEECHMATICS_API_KEY"


def test_7_2_the_order_of_reading_is_the_store_then_the_environment_then_the_file_and_each_says_where_a_key_came_from(tmp_path):
    store = MadeStore()
    assert keys.find_key(NAME, tmp_path, {}, store) == (None, None)
    (tmp_path / ".env").write_text(f"{NAME}=made-up-from-file\n", encoding="utf-8")
    assert keys.find_key(NAME, tmp_path, {}, store) == ("made-up-from-file", "file")
    environ = {NAME: "made-up-from-environment"}
    assert keys.find_key(NAME, tmp_path, environ, store) == ("made-up-from-environment", "environment")
    store.put(NAME, "made-up-from-store")
    assert keys.find_key(NAME, tmp_path, environ, store) == ("made-up-from-store", "store")
    assert keys.read_key(NAME, tmp_path, environ, store) == "made-up-from-store"
    # A caller that gives no store reads none: the developer's way stands as it was (7.3, rule 3).
    assert keys.read_key(NAME, tmp_path, environ) == "made-up-from-environment" and keys.read_key(NAME, tmp_path, {}) == "made-up-from-file"
    # A store that does not answer holds nothing, and the next place is read.
    assert keys.find_key(NAME, tmp_path, {}, MadeStore(answers=False)) == ("made-up-from-file", "file")


def test_7_2_the_apps_speech_door_reads_its_key_through_the_store_first_at_each_use(tmp_path):
    store = MadeStore()
    door = make_door(tmp_path, SPEECHMATICS, environ={}, store=store)
    assert not door.has_key
    store.put(NAME, "made-up-from-store")
    assert door.has_key                                    # connected while the app runs: it counts at once
    store.take_out(NAME)
    assert not door.has_key                                # and removed: gone at once
    assert not (tmp_path / "speech").exists()              # reading a key starts nothing


class MadePackage:
    """What the app's wrapper asks of the package, made: a store in memory."""

    class Backend:
        pass

    def __init__(self, backend_module: str = "made_up.backend", slow_s: float = 0.0, keeps: bool = True, breaks: bool = False):
        self.held, self.slow_s, self.keeps, self.breaks = {}, slow_s, keeps, breaks
        self.Backend = type("Backend", (), {"__module__": backend_module})

    def get_keyring(self):
        time.sleep(self.slow_s)
        return self.Backend()

    def get_password(self, service, name):
        if self.breaks:
            raise RuntimeError("made-up: the store is locked, key made-up-secret")
        return self.held.get((service, name))

    def set_password(self, service, name, value):
        if self.keeps:
            self.held[(service, name)] = value

    def delete_password(self, service, name):
        del self.held[(service, name)]


def test_7_2_the_wrapper_keeps_reads_back_and_takes_out_a_key_under_the_apps_own_name():
    package = MadePackage()
    store = SystemStore(package)
    assert store.answers() and store.why_not() is None and store.get(NAME) is None
    store.put(NAME, "made-up-key")
    assert store.get(NAME) == "made-up-key" and package.held == {("OpenConsult", NAME): "made-up-key"}
    store.take_out(NAME)
    assert store.get(NAME) is None and package.held == {}
    store.take_out(NAME)                                   # a key that is not there is already out


@pytest.mark.parametrize("package, why", [
    (MadePackage(backend_module="keyring.backends.fail"), "the system has no secure store that this app can reach"),
    (MadePackage(backend_module="keyring.backends.null"), "the system has no secure store that this app can reach"),
    (MadePackage(breaks=True), "the secure store answered with RuntimeError"),
])
def test_details_of_9b_a_store_that_does_not_answer_is_no_store_and_its_reason_never_holds_a_key(package, why):
    store = SystemStore(package)
    assert not store.answers() and store.why_not() == why and "made-up-secret" not in why
    with pytest.raises(NoStore):
        store.get(NAME)
    with pytest.raises(NoStore):
        store.put(NAME, "made-up-key")


def test_details_of_9b_a_store_that_gives_no_answer_in_time_or_does_not_keep_the_key_is_no_store():
    slow = SystemStore(MadePackage(slow_s=1.0), limit_s=0.1)
    started = time.perf_counter()
    assert not slow.answers() and time.perf_counter() - started < 0.8        # the limit holds: a start never hangs on a store
    assert slow.why_not() == "the secure store did not answer within 0 seconds" and secure.ANSWER_LIMIT_S == 5.0
    forgetful = SystemStore(MadePackage(keeps=False))
    with pytest.raises(NoStore, match="did not keep the key"):
        forgetful.put(NAME, "made-up-key")


def test_R18_a_test_that_reaches_the_systems_real_store_fails_and_an_app_built_in_a_test_gets_a_made_one(app):
    import keyring
    for call in (keyring.get_keyring, lambda: keyring.get_password("OpenConsult", NAME),
                 lambda: keyring.set_password("OpenConsult", NAME, "made-up"), lambda: keyring.delete_password("OpenConsult", NAME)):
        with pytest.raises(pytest.fail.Exception, match="real secure store"):
            call()
    assert isinstance(app.state.parts.store, MadeStore) and app.state.parts.store.held == {}
    with pytest.raises(pytest.fail.Exception):
        SystemStore().get(NAME)                             # the app's own wrapper with no made package: the real one, refused


def test_rule_1_of_9a_the_bench_reads_its_key_from_the_key_folder_alone_and_never_from_a_store(tmp_path):
    # The guard above fails any touch of the real store; the bench's reader is given no store at all.
    (tmp_path / ".env").write_text(f"{NAME}=made-up-from-folder\n", encoding="utf-8")
    said = []
    assert upload_commands._key(speechmatics_upload, tmp_path, said.append) == "made-up-from-folder" and said == []
    assert keys.read_key.__defaults__[-1] is None and keys.find_key.__defaults__[-1] is None     # no store unless one is given
