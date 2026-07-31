"""Security response headers (2026-07-31 audit, Finding 5).

Asserts the headers are actually emitted — and, just as importantly, that
the Content-Security-Policy is never "fixed" by adding `'unsafe-inline'`,
which would make the header look like protection while re-permitting the
injected-script attack app/static/nav.js closes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import CSP, app

client = TestClient(app)


def test_csp_and_nosniff_present_on_a_response():
    response = client.get("/login")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == CSP
    assert response.headers["x-content-type-options"] == "nosniff"


def test_headers_present_on_an_error_response_too():
    """A 404 is served by the same stack; headers must not be a happy-path
    decoration."""
    response = client.get("/no-such-page-xyz")
    assert response.status_code == 404
    assert "content-security-policy" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_headers_present_on_static_assets():
    response = client.get("/static/nav.js")
    assert response.status_code == 200
    assert "content-security-policy" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_policy_carries_the_directives_that_cost_nothing_today():
    for directive in ("object-src 'none'", "base-uri 'self'",
                      "form-action 'self'", "frame-ancestors 'none'"):
        assert directive in CSP


def test_policy_never_permits_inline_script():
    """The regression that matters.

    script-src is absent today because the pages carry ~3,300 lines of
    inline <script> (see the CSP comment in app/main.py). When it is added,
    it must be added WITH the inline blocks moved out — never with
    'unsafe-inline', which would re-open the hole this phase closed.
    """
    assert "unsafe-inline" not in CSP
    assert "unsafe-eval" not in CSP
    if "script-src" in CSP:  # once the inline blocks are extracted
        assert "script-src 'self'" in CSP
