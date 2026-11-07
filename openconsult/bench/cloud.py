"""What the two cloud kinds of the bench share (spec 15.13, the details
of runs 9a2 and 9d), in one place and not written twice: the rule that a
kind speaks to its own service's address over https and to no other,
checked before any connection; the stop after a refused key or used-up
credit, after which nothing more is sent (run 9a, rule 9); and the shape
of the row the bench command reads a kind's key by (7.3, rule 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.llm.engine import EngineUnreachable


class AddressRefused(ValueError):
    """The key goes to the service's own address and to no other."""


def own_address(address: str, expected: str) -> str:
    """The address with no trailing slash, when it is the expected one."""
    if address.rstrip("/") != expected.rstrip("/"):
        raise AddressRefused(f"the cloud kind speaks to {expected} alone, not {address}")
    return address.rstrip("/")


def stop_line(status: int) -> str:
    return (f"the service answered HTTP {status}, so the key is refused or the credit is used up; "
            f"nothing more is sent")


class Stops:
    """A kind that stops: once the service refuses the key or the credit
    is used up, every later call raises the joint's unreachable with the
    reason, which the door records and the bench's loops read (the door's
    stopped property). None for every engine of the app."""
    stopped: str | None = None

    def refuse_if_stopped(self) -> None:
        if self.stopped:
            raise EngineUnreachable(self.stopped)

    def stop(self, reason: str) -> None:
        self.stopped = reason


@dataclass(frozen=True)
class CloudKind:
    """A kind of the bench command's registry: its class, and the name
    its key is read by from the key folder's .env."""
    engine: type
    key_name: str
