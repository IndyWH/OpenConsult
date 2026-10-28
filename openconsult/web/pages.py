"""Rendering, the form reader, and the one refusal helper (R15).

Every refusal shows on the control that was pressed: the page is sent
back with the message in that control's own slot. The helper checks the
message landed, so a refusal can never be lost (V1_LESSONS 5.1).
"""

from __future__ import annotations

import email
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from openconsult import words

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)


class LostRefusal(Exception):
    """The page has no slot for this control, so the message would vanish."""


@dataclass(frozen=True)
class Refusal:
    control: str
    message: str


async def form_fields(request: Request) -> dict[str, str]:
    """The fields of a plain form post, with the standard library."""
    body = (await request.body()).decode("utf-8", errors="replace")
    return dict(parse_qsl(body, keep_blank_values=True))


async def multipart_fields(request: Request, limit: int | None = None) -> tuple[dict[str, str], dict[str, tuple[str, bytes]], bool]:
    """The fields and the files of a multipart form post, with the standard
    library's email parser: no library added for one upload (8b). Gives
    (fields, files, too_big); a body over the limit is not parsed."""
    body = await request.body()
    if limit is not None and len(body) > limit:
        return {}, {}, True
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        return dict(parse_qsl(body.decode("utf-8", errors="replace"), keep_blank_values=True)), {}, False
    message = email.message_from_bytes(b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    fields, files = {}, {}
    for part in message.walk():
        if part.is_multipart():
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            files[name] = (filename, payload)
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields, files, False


def render(request: Request, template: str, status: int = 200,
           page_path: str | None = None, timed_by_script: bool = False, refresh_every: int | None = None,
           **context) -> HTMLResponse:
    """page_path is the address the page's own timed move goes to. A page
    sent back from a form post gives its own GET address, so the move
    never lands on an address that takes no GET. A page timed by its own
    script (typing as use, ruling 12) gets the seconds and no meta tag."""
    seconds_left = getattr(request.state, "seconds_left", None)
    refresh = None if seconds_left is None or timed_by_script else seconds_left + 1
    page = _env.get_template(template).render(
        words=words,
        statement=words.STATEMENT,
        path=page_path or request.url.path,
        # refresh_every 0 means none: a page that waits on the doctor never moves by itself.
        refresh=(refresh_every or None) if refresh_every is not None else refresh,
        seconds_left=seconds_left,
        **context,
    )
    return HTMLResponse(page, status_code=status)


def refuse(request: Request, template: str, control: str, message: str, **context) -> HTMLResponse:
    """The page again, with the message under the control pressed."""
    refusal = Refusal(control, message)
    response = render(request, template, status=400, refused=refusal, **context)
    body = response.body.decode("utf-8")
    slot = f'id="{control}-refusal"'
    if slot not in body or _escaped(message) not in body:
        raise LostRefusal(control)
    return response


def _escaped(text: str) -> str:
    return _env.from_string("{{ t }}").render(t=text)
