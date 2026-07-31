"""Stored-XSS regression guards for the innerHTML sinks (2026-07-31 audit).

The shipped JavaScript is EXECUTED under Node — the
tests/test_silence_nudge_client.py convention — rather than pattern-matched,
so these tests assert what a browser would actually render. Each one lifts
the real row-building expression out of the page verbatim, drives it with a
hostile value in the field an attacker controls, and requires the result to
be inert markup.

Findings covered: 1 (public registration → admin session, the Critical), 2
(patient/doctor names crossing into other users' sessions), 4 (the audit
log's own record), 10 (the letter spinner).

If someone drops an esc() from one of these sinks, the matching test fails
with the payload rendered live.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")

STATIC = Path("app/static")

# The classic stored payload: no <script> tag needed, fires on render.
PAYLOAD = '<img src=x onerror=alert(1)>'
# The attribute-context payload: breaks out of a class="..." if quotes live.
QUOTE_PAYLOAD = '" onmouseover="alert(1)'


def _esc_source() -> str:
    """The shipped esc() helper, verbatim from nav.js."""
    source = (STATIC / "nav.js").read_text()
    start = source.index("function esc(value)")
    return source[start:source.index("\n}\n", start) + 3]


def _snippet(filename: str, start_marker: str, end_marker: str = ";") -> str:
    """One shipped expression, lifted verbatim from a page."""
    source = (STATIC / filename).read_text()
    start = source.index(start_marker)
    return source[start:source.index(end_marker, start) + len(end_marker)]


def _run(script: str) -> dict:
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _render(setup: str, snippet: str, target: str) -> str:
    """Execute a lifted snippet with the real esc() and return the HTML."""
    return _run(
        f"{_esc_source()}\n{setup}\n{snippet}\n"
        f"console.log(JSON.stringify({{html: {target}}}));"
    )["html"]


def _assert_inert(html: str) -> None:
    """The payload must be present as characters and absent as markup."""
    assert "<img" not in html, f"payload rendered live as markup: {html}"
    assert "&lt;img src=x onerror=alert(1)&gt;" in html, html


# --------------------------------------------------------------- the helper

def test_esc_neutralises_markup_and_quotes():
    out = _run(
        f"{_esc_source()}\n"
        "console.log(JSON.stringify({"
        f"  payload: esc({json.dumps(PAYLOAD)}),"
        f"  quotes: esc({json.dumps(QUOTE_PAYLOAD)}),"
        "  amp: esc('a & b'), nullish: esc(null), undef: esc(undefined),"
        "  number: esc(7)}));"
    )
    assert out["payload"] == "&lt;img src=x onerror=alert(1)&gt;"
    assert out["quotes"] == "&quot; onmouseover=&quot;alert(1)"
    assert out["amp"] == "a &amp; b"
    # Nullish renders empty, never the string "null"/"undefined".
    assert out["nullish"] == "" and out["undef"] == ""
    assert out["number"] == "7"


# ------------------------------------------------- Finding 1 (the Critical)

def test_users_row_renders_registered_payload_inert():
    """A display_name/username set by PUBLIC registration renders inert on
    the admin's Users page — the page they must open to triage it."""
    setup = (
        "const u = {id: 1, display_name: %s, username: %s, role: 'doctor',"
        " created_at: '2026-07-31 09:00', last_login_at: null};"
        "const statusChip = '<span class=\"chip status\">awaiting approval</span>';"
        "const tr = {};"
    ) % (json.dumps(PAYLOAD), json.dumps(PAYLOAD))
    html = _render(setup, _snippet("users.html", "tr.innerHTML ="), "tr.innerHTML")
    _assert_inert(html)
    # Our own chip markup is intentional and must survive.
    assert '<span class="chip status">awaiting approval</span>' in html


# ------------------------------------------------------------- Finding 2

def test_today_row_renders_patient_name_payload_inert():
    """The queue name field is typed by a receptionist and renders in the
    doctor's session, re-fired by the 5 s refresh."""
    setup = (
        "function isActive() { return true; }"
        "let displayNo = 0;"
        "const demo = '42, F';"
        "const entry = {name: %s, status: 'waiting'};"
        "const tr = {};"
    ) % json.dumps(PAYLOAD)
    html = _render(
        setup,
        _snippet("today.html", "tr.innerHTML = `<td>${isActive(entry)"),
        "tr.innerHTML",
    )
    _assert_inert(html)


def test_today_status_cannot_break_out_of_the_class_attribute():
    setup = (
        "function isActive() { return true; }"
        "let displayNo = 0;"
        "const demo = '';"
        "const entry = {name: 'Ada', status: %s};"
        "const tr = {};"
    ) % json.dumps(QUOTE_PAYLOAD)
    html = _render(
        setup,
        _snippet("today.html", "tr.innerHTML = `<td>${isActive(entry)"),
        "tr.innerHTML",
    )
    # The raw payload must not survive: its quotes are what would end the
    # class attribute and start an event-handler one.
    assert QUOTE_PAYLOAD not in html, f"broke out of the attribute: {html}"
    assert "&quot; onmouseover=&quot;alert(1)" in html, html


def test_worklist_row_renders_name_and_void_reason_inert():
    """patient_name, doctor_name and the free-text void reason all reach
    other users' sessions from this table."""
    setup = (
        "const c = {id: 7, status: 'awaiting_review', patient_name: %s,"
        " doctor_name: %s, started_at: '2026-07-31', voided_at: '2026-07-31',"
        " voided_by: %s, void_reason: %s, audio_bytes: null};"
        "const label = 'awaiting review';"
        "const admin = true;"
        "const tr = {};"
    ) % ((json.dumps(PAYLOAD),) * 4)
    html = _render(
        setup,
        _snippet("worklist.html", "const status = c.voided_at",
                 "+ '<td></td>';"),
        "tr.innerHTML",
    )
    _assert_inert(html)


# ------------------------------------------------------------- Finding 4

def test_audit_row_renders_detail_payload_inert():
    """JSON.stringify does not escape `<`, so a payload inside any audited
    free text used to break out of the <code> element."""
    setup = (
        "const r = {at: '2026-07-31T09:00:00+00:00', username: %s,"
        " role: 'admin', action: 'consultation.voided',"
        " subject_type: 'consultation', subject_id: 70,"
        " detail: {reason: %s}};"
        "const tr = {};"
    ) % (json.dumps(PAYLOAD), json.dumps(PAYLOAD))
    html = _render(setup, _snippet("audit.html", "tr.innerHTML ="), "tr.innerHTML")
    _assert_inert(html)
    # The <code> wrapper is ours and must survive.
    assert "<code>" in html and "</code>" in html


# ------------------------------------------------------------ Finding 10

def test_letter_spinner_renders_specialty_inert():
    setup = "const wait = {}; const specialty = %s;" % json.dumps(PAYLOAD)
    html = _render(setup, _snippet("review.html", "wait.innerHTML ="),
                   "wait.innerHTML")
    _assert_inert(html)


# --------------------------------------------------- static regression net

def test_no_sink_interpolates_a_server_value_bare():
    """Belt and braces: the bare interpolations must not come back.

    Scoped to the innerHTML statement itself — the same field interpolated
    into a confirm() string or a fetch() URL is not a markup sink, and
    flagging those would train the reader to ignore this test.
    """
    bare = {
        ("users.html", "tr.innerHTML =", ";"):
            ["${u.display_name}", "${u.username}", "${u.role}"],
        ("today.html", "tr.innerHTML = `<td>${isActive(entry)", ";"):
            ["${entry.name}", "${entry.status}",
             "${entry.status.replace('_',' ')}"],
        ("worklist.html", "const status = c.voided_at", "+ '<td></td>';"):
            ["${c.patient_name}", "${c.doctor_name}", "${c.void_reason}",
             "${c.status}"],
        ("audit.html", "tr.innerHTML =", ";"):
            ["${r.username || '—'}", "${r.action}",
             "${r.detail ? JSON.stringify(r.detail) : ''}"],
        ("review.html", "wait.innerHTML =", ";"): ["${specialty}"],
    }
    for (filename, start, end), patterns in bare.items():
        sink = _snippet(filename, start, end)
        for pattern in patterns:
            assert pattern not in sink, (
                f"{filename}: {pattern} reaches innerHTML unescaped — "
                f"wrap it in esc()")
