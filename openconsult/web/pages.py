"""Rendering, the form reader, and the one refusal helper (R15).

Every refusal shows on the control that was pressed: the page is sent
back with the message in that control's own slot. The helper checks the
message landed, so a refusal can never be lost (V1_LESSONS 5.1).
"""

from __future__ import annotations

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


def render(request: Request, template: str, status: int = 200, **context) -> HTMLResponse:
    seconds_left = getattr(request.state, "seconds_left", None)
    page = _env.get_template(template).render(
        words=words,
        statement=words.STATEMENT,
        path=request.url.path,
        refresh=None if seconds_left is None else seconds_left + 1,
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
