"""The number format of EmbeddingGemma 2 for each device (spec 15.9,
ruling 25): bfloat16 on the card, float32 on the processor. Google's own
page says never float16, which gives wrong vectors with no error. This
table is the only place a format is chosen; the worker turns the name
into its library's type, and the suite reads the table with no library."""

from __future__ import annotations

DTYPES = {"cuda": "bfloat16", "cpu": "float32"}
FORBIDDEN = "float16"


def dtype_name(device: str) -> str:
    """The format's name for a device, or a refusal for a device not in the table."""
    try:
        return DTYPES[device]
    except KeyError:
        raise ValueError(f"no number format is chosen for the device {device!r}") from None
