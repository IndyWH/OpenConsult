"""The SECRET_KEY import-time fail-fast guard (app/auth.py, 2026-08-04).

Each case sets the environment and reloads app.auth, so what is asserted
is the module-level guard the service actually hits at startup — not a
re-implementation of it. load_dotenv is neutralised for the reload: the
scenario under test is precisely the deployment whose .env is missing or
misplaced, and on the development machine a real .env would otherwise
refill the variable behind the test's back. For the non-missing cases the
explicit environment value wins over .env anyway (load_dotenv never
overrides), so nothing else changes.
"""

import importlib
import os

import dotenv
import pytest

from app import auth

# The valid session key conftest.py set before any app import — restored
# (with a reload) after every test so the rest of the suite never sees a
# half-reloaded auth module.
_SESSION_KEY = os.environ["SECRET_KEY"]


@pytest.fixture()
def reload_with(monkeypatch):
    """Reload app.auth with SECRET_KEY set to `value` (None = unset)."""
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)

    def attempt(value):
        if value is None:
            monkeypatch.delenv("SECRET_KEY", raising=False)
        else:
            monkeypatch.setenv("SECRET_KEY", value)
        return importlib.reload(auth)

    yield attempt
    # monkeypatch tears down after this fixture, so restore explicitly:
    # a valid key back in the environment, then a clean reload.
    os.environ["SECRET_KEY"] = _SESSION_KEY
    importlib.reload(auth)


def test_missing_key_refuses_to_start(reload_with):
    with pytest.raises(RuntimeError) as exc:
        reload_with(None)
    msg = str(exc.value)
    assert "SECRET_KEY is not set" in msg
    assert "openssl rand -hex 32" in msg


def test_empty_key_refuses_to_start(reload_with):
    with pytest.raises(RuntimeError) as exc:
        reload_with("")
    msg = str(exc.value)
    assert "SECRET_KEY is empty" in msg
    assert "openssl rand -hex 32" in msg


@pytest.mark.parametrize("placeholder", ["change-me", "dev-secret-change-me"])
def test_placeholder_key_refuses_to_start(reload_with, placeholder):
    with pytest.raises(RuntimeError) as exc:
        reload_with(placeholder)
    msg = str(exc.value)
    assert "placeholder" in msg
    assert "openssl rand -hex 32" in msg
    # Never echo the rejected value. "change-me" is a substring of
    # "dev-secret-change-me", so this one assertion covers both.
    assert "change-me" not in msg


def test_31_character_key_refuses_to_start(reload_with):
    value = "hunter2-hunter2-hunter2-hunter2"
    assert len(value) == 31  # one short of the minimum, by construction
    with pytest.raises(RuntimeError) as exc:
        reload_with(value)
    msg = str(exc.value)
    assert "shorter than 32 characters" in msg
    assert "openssl rand -hex 32" in msg
    # Never echo the rejected value or any part of it.
    assert value not in msg
    assert "hunter2" not in msg


def test_valid_64_character_key_starts(reload_with):
    value = "ab12" * 16
    assert len(value) == 64
    module = reload_with(value)
    # The reload really ran the guard and bound the accepted value.
    assert module.SECRET_KEY == value
