"""What every cloud language model engine holds to, for the app and the
bench alike (spec 15.13, the details of runs 9a2, 9d and 9b): an engine
speaks to its own service's address over https and to no other, checked
before any connection is opened, so a key never goes anywhere else.
"""

from __future__ import annotations


class AddressRefused(ValueError):
    """The key goes to the service's own address and to no other."""


def own_address(address: str, expected: str) -> str:
    """The address with no trailing slash, when it is the expected one."""
    if address.rstrip("/") != expected.rstrip("/"):
        raise AddressRefused(f"the cloud kind speaks to {expected} alone, not {address}")
    return address.rstrip("/")
