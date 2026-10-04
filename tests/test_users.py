"""The one user and the ported password hash (spec 6.1, 7.1, 15.6)."""

import pytest

from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.patients.users import (
    AlreadySetUp, Users, password_problem, verify_password,
)

# Made by v1's hash_password for the password below, salt fixed.
V1_HASH = (
    "scrypt$00112233445566778899aabbccddeeff$"
    "8cc0de9218d3d6723ae203a934c046cf2bb9aa70723c2cf4b1cf06ca35c89adb"
    "2684deb3f9719277742dab52a6a46adf5831f07ae075229fca420a7bb68a8692"
)


@pytest.fixture
def users(tmp_path):
    db = open_database(tmp_path / "openconsult.db")
    audit = Audit(db)
    return Users(db, audit), audit


def test_6_1_the_password_hash_ported_from_v1_verifies_a_v1_hash():
    assert verify_password("correct horse battery", V1_HASH)
    assert not verify_password("correct horse", V1_HASH)
    assert not verify_password("correct horse battery", "not a hash")


def test_15_6_a_password_under_8_characters_is_refused():
    assert password_problem("seven77", "seven77") == "short"
    assert password_problem("eight888", "eight889") == "differ"
    assert password_problem("eight888", "eight888") is None


def test_15_6_there_is_only_one_user(users):
    users, _ = users
    users.set_up("Dr", "Example", "first-password")
    with pytest.raises(AlreadySetUp):
        users.set_up("Dr", "Other", "second-password")
    assert users.get().name == "Example"


def test_15_6_no_password_ever_reaches_the_log(users):
    # Pins spec 15.6: the recorder never writes a password or a secret.
    users, audit = users
    users.set_up("Dr", "Example", "first-password")
    assert users.verify("first-password")
    users.change_details("Dr", "Sample")
    users.change_password("second-password")
    users.reset_password("third-password")
    assert not users.verify("first-password")
    assert users.verify("third-password")
    text = " ".join(f"{line.event} {line.detail}" for line in audit.lines())
    for secret in ("first-password", "second-password", "third-password"):
        assert secret not in text
    assert [line.event for line in audit.lines()] == [
        "password.reset", "password.changed", "name.changed", "user.set_up",
    ]
