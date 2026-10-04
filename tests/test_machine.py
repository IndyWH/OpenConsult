"""This machine: the card, its memory and the sentence (spec 6.4, 15.6, D19)."""

import subprocess
from types import SimpleNamespace

import pytest

from openconsult import words
from openconsult.settings.machine import NEEDED_GB, Card, describe, read_machine

RTX_4090 = Card("NVIDIA GeForce RTX 4090", 24564)
SMALL = Card("NVIDIA GeForce RTX 4060", 8188)

CASES = [
    ("Linux", [RTX_4090], "suitable", {}),
    ("Linux", [SMALL], "smaller", {"gb": 8, "needed": NEEDED_GB}),
    ("Windows", [], "none", {}),
    ("Darwin", [], "mac", {}),
    ("Linux", None, "unreadable", {}),
]


@pytest.mark.parametrize("system, cards, case, fill", CASES)
def test_15_6_the_sentence_for_each_kind_of_machine(system, cards, case, fill):
    # The owner corrects the wording on screen, so the test checks which
    # case was chosen and takes the sentence from words.py.
    machine = describe(system, "x86_64", cards)
    assert machine.case == case
    assert machine.sentence == words.MACHINE[case].format(**fill)


def test_15_6_a_card_that_cannot_be_read_is_said_plainly_and_does_not_stop_the_app():
    def hangs(*a, **k):
        raise subprocess.TimeoutExpired(a[0], 1)

    def fails(*a, **k):
        return SimpleNamespace(returncode=1, stdout="")

    def rubbish(*a, **k):
        return SimpleNamespace(returncode=0, stdout="no such thing\n")

    for run in (hangs, fails, rubbish):
        machine = read_machine("Linux", "x86_64", which=lambda name: "/usr/bin/" + name, run=run)
        assert machine.case == "unreadable"
        assert machine.card_line == words.CARD_UNREADABLE


def test_6_4_the_largest_of_several_cards_counts():
    machine = describe("Linux", "x86_64", [SMALL, RTX_4090, SMALL])
    assert machine.case == "suitable"
    assert machine.card == RTX_4090
    assert machine.card_line == words.CARD_LINE.format(name=RTX_4090.name, gb=24)


def test_15_6_the_card_is_read_from_the_driver_tool_and_its_absence_means_no_card():
    def two_cards(command, **kwargs):
        assert "nvidia-smi" in command[0]
        return SimpleNamespace(
            returncode=0,
            stdout="NVIDIA GeForce RTX 4060, 8188\nNVIDIA RTX A6000, 49140\n",
        )

    found = read_machine("Windows", "AMD64", which=lambda name: r"C:\Windows\System32\nvidia-smi.exe", run=two_cards)
    assert found.case == "suitable" and found.card.name == "NVIDIA RTX A6000"
    absent = read_machine("Linux", "x86_64", which=lambda name: None, run=two_cards)
    assert absent.case == "none" and absent.card_line == words.CARD_NONE
    mac = read_machine("Darwin", "arm64", which=lambda name: "/opt/nvidia-smi", run=two_cards)
    assert mac.case == "mac"
