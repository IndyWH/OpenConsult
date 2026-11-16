"""The system's own secure store for the keys of the cloud services (spec
7.2; 15.13, the details of run 9b): Credential Manager on Windows,
Keychain on macOS, the Secret Service on Linux, reached through the
keyring package. This is the only module that imports that package,
and it does so only when a store is asked, so the app starts where the
package finds nothing.

A key is put here by the connect screen alone, after it has passed its
test; Remove takes it out. Nothing else is ever kept here, and no file
is ever used in the store's place by the app itself.

A store that does not answer is no store: where the package finds
none, where its call fails, where it does not keep what it was given,
or where it gives no answer within ANSWER_LIMIT_S (a locked store that
waits on a window nobody sees must never hang the start of the app or
a page). Each of these is NoStore, with the reason in plain words and
never a key."""

from __future__ import annotations

import threading

SERVICE = "OpenConsult"      # the name the system's store files the keys under
# A design choice, not a measurement: an unlocked store answers in milliseconds.
ANSWER_LIMIT_S = 5.0


class NoStore(Exception):
    """No secure store answers on this computer, or it did not do what was asked."""


def _package():
    import keyring
    return keyring


class SystemStore:
    def __init__(self, package=None, limit_s: float = ANSWER_LIMIT_S):
        self._package = package            # a test gives a made package; the app gives none and the real one is loaded at the first use
        self._limit_s = limit_s

    def _ask(self, what: str, *args):
        """One call of the package on a thread of its own, so that the
        limit holds whatever the system's store does."""
        found: dict = {}

        def run() -> None:
            try:
                package = self._package or _package()
                backend = package.get_keyring()
                # The package's own stand-ins for no store: one refuses every call, the other forgets what it is given.
                if type(backend).__module__ in ("keyring.backends.fail", "keyring.backends.null"):
                    raise NoStore("the system has no secure store that this app can reach")
                found["value"] = getattr(package, what)(SERVICE, *args)
            except NoStore as none:
                found["error"] = none
            except Exception as failed:  # noqa: BLE001 - whatever the system's store raised, it did not answer
                found["error"] = NoStore(f"the secure store answered with {type(failed).__name__}")
            except BaseException as stopped:  # noqa: BLE001 - not an answer of the store: handed to the caller as it is
                found["error"] = stopped

        thread = threading.Thread(target=run, name="secure-store", daemon=True)
        thread.start()
        thread.join(self._limit_s)
        if thread.is_alive():
            raise NoStore(f"the secure store did not answer within {self._limit_s:.0f} seconds")
        if "error" in found:
            raise found["error"]
        return found.get("value")

    def get(self, name: str) -> str | None:
        """The key under the name, or None when the store holds none."""
        return self._ask("get_password", name) or None

    def put(self, name: str, value: str) -> None:
        """Keep the key, and read it back: a store that did not keep it is no store."""
        self._ask("set_password", name, value)
        if self._ask("get_password", name) != value:
            raise NoStore("the secure store did not keep the key")

    def take_out(self, name: str) -> None:
        """Remove the key; a key that is not there is already out."""
        if self.get(name) is not None:
            self._ask("delete_password", name)

    def answers(self) -> bool:
        try:
            self.get("OPENCONSULT_STORE_CHECK")
        except NoStore:
            return False
        return True

    def why_not(self) -> str | None:
        """The reason no store answers, or None when one does."""
        try:
            self.get("OPENCONSULT_STORE_CHECK")
        except NoStore as none:
            return str(none)
        return None
