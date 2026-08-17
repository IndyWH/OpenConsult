"""The three standing rules, and the never-swallow audit of the other pages.

The 2026-07-25 audit covered `live.html` only. These check the two pages it did
not reach — the Consultations worklist and the review page — plus the live-slot
refusal, which used to tell a doctor only that something was busy.

The rules, with the incident that produced each:

1. NEVER SWALLOW AN ACTION (2026-07-25, three instances in one evening).
2. A CONTROL THAT CAN ACT MUST NOT LOOK AS IF IT CANNOT (448, the green chip).
3. A CONTROL THE DOCTOR MUST REACH MUST BE WHERE THEY ARE LOOKING (447's Stop
   control, then 449's speaker-count question — the same defect in a new control
   three days later).

All three are an accessibility requirement, not a preference, and the tests
below assert that the REASON survives in each page. A rule stripped of its why
reads as a style opinion and gets traded away — which is why this is asserted
rather than trusted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGES = ("live.html", "review.html", "worklist.html")


def _page(name: str) -> str:
    return Path("app/static") / name and Path(f"app/static/{name}").read_text()


# ------------------------------------------------- the rules are written down

@pytest.mark.parametrize("page", PAGES)
def test_the_standing_rules_are_written_into_the_page(page):
    # Case-insensitive: the pages state the rules in capitals as headings.
    html = _page(page).lower()
    assert "never swallow an action" in html
    assert "must not look as if it cannot" in html
    assert "where they are looking" in html


@pytest.mark.parametrize("page", PAGES)
def test_each_page_keeps_the_reason_for_the_rules(page):
    """The accessibility reason, not just the rule. Stripped of its why, a rule
    reads as a style opinion and gets traded away."""
    html = _page(page)
    assert "dyslexic with ADHD" in html, (
        f"{page} must keep the reason the rules exist")
    assert "no explanation at all" in html


@pytest.mark.parametrize("page", ("review.html", "worklist.html"))
def test_each_page_names_the_incident_behind_the_third_rule(page):
    """Rule 3 was learned twice — 447's Stop control and then 449's
    speaker-count question, in a NEW control days after the first fix. Both are
    named so the next reader does not have to rediscover it in a room."""
    html = _page(page)
    assert "447" in html and "449" in html


# --------------------------------------------- no silent refusals on a control

@pytest.mark.parametrize("page", ("review.html", "worklist.html"))
def test_every_server_call_from_a_control_reports_its_refusal(page):
    """The audit's actual finding on both pages: handlers that awaited a fetch,
    ignored the response, and refreshed. A 409 produced no message anywhere.

    One `act()` helper per page now owns that, so a refusal cannot be dropped;
    this asserts no bare awaited fetch is left behind in a handler.
    """
    html = _page(page)
    assert "async function act(" in html, f"{page} needs one refusal path"
    # A bare `await fetch(` is only legitimate where the result is bound and
    # checked. Anything discarding it is the pattern being removed.
    for match in re.finditer(r"^\s*await fetch\(", html, re.M):
        line = html[match.start():html.index("\n", match.start())]
        pytest.fail(f"{page}: unchecked server call — {line.strip()}")


def test_the_reason_lands_on_the_control_not_only_in_a_banner():
    """Rule 3 applied to error messages. `#err` on the worklist sits above a
    table whose rows can be a screen away, and review.html's banners sit above
    the note while Approve is in the header."""
    worklist = _page("worklist.html")
    assert "control.title = message" in worklist
    assert "control.classList.add('rejected')" in worklist
    review = _page("review.html")
    assert 'id="actionErr"' in review
    assert "if (control) control.title = message;" in review
    # The refusal surface has to live INSIDE the actions box, beside the button.
    actions = review[review.index('id="actionsBox"'):]
    actions = actions[:actions.index("</div>\n    <div") if "</div>\n    <div" in actions
                      else actions.index("</div>")]
    assert 'id="actionErr"' in review[review.index('id="actionsBox"'):
                                      review.index('id="actionsBox"') + 900]


def test_approve_is_gated_at_the_button_for_all_three_acknowledgements():
    """The highest-stakes control on the site. A doctor who presses Approve
    before acknowledging must be told AT THE BUTTON, not only in the banner
    above the note — and all three gates must be represented."""
    review = _page("review.html")
    gate = review[review.index("function refreshApproveGate()"):]
    gate = gate[:gate.index("\n}")]
    assert "urgent-action alert" in gate            # urgency
    assert "only one voice was detected" in gate    # single voice
    assert "declared speaker count was not the one used" in gate  # 450
    assert "the labels changed after this note was drafted" in gate  # stale labels
    assert "approveBtn.title" in gate, "the reason goes on the control"
    assert "approveBtn.disabled = reasons.length > 0;" in gate
    # ...and it is the ONLY writer of that flag, so no renderer can undo it.
    # Comments are stripped first: one of them explains WHY there is a single
    # writer, and that explanation must not have to be deleted to stay green.
    code = "\n".join(line for line in review.splitlines()
                     if not line.lstrip().startswith("//"))
    assert code.count("approveBtn.disabled") == 1


def test_a_rejected_transcript_correction_is_not_left_on_screen():
    """The worst swallow found on the review page: a refused edit stayed
    displayed, looking saved, until something else reloaded and reverted it."""
    review = _page("review.html")
    assert "correction not saved" in review
    assert "if (!ok) body.textContent = t.text;" in review
    # Same for a letter edit, which additionally used to record the refused
    # text locally as though it had been accepted.
    assert "Letter edit not saved" in review
    assert "else area.value = letter.body;" in review


def test_the_read_only_transcript_says_why_it_will_not_open():
    review = _page("review.html")
    assert "Read-only — this consultation has been approved" in review


# ------------------------------------------------------- the live-slot refusal

def test_the_live_slot_refusal_names_what_is_holding_it():
    main = Path("app/main.py").read_text()
    builder = main[main.index("async def _live_slot_refusal("):]
    builder = builder[:builder.index("\n@app")]
    # The patient and the time it was opened...
    assert "active['name']" in builder and "_clock(active.get('added_at'))" in builder
    # ...and what the caller can do about it.
    assert "close their entry from Today" in builder
    # No blocker in today's queue is still explained, not answered with "busy".
    assert "no entry" in builder and "holding it" in builder


def test_the_refusal_is_the_same_at_every_site_that_fires_the_audit_event():
    """Four sites fire live.slot_rejected. Two are HTTP and share the builder;
    the two WebSocket ones name the user holding the stream instead, because
    there the blocker is a live stream rather than a queue entry."""
    main = Path("app/main.py").read_text()
    assert main.count("_live_slot_refusal(") >= 3   # definition + both HTTP sites
    assert "is already recording a live consultation" in main
    assert "already streaming from another tab" in main


def test_the_guard_itself_is_not_weakened():
    """One live consultation at a time is a safety property, not a throughput
    limit: two streams would share the faster-whisper model, and an urgency
    alarm arriving late under contention is a safety regression. This item made
    the refusal legible and nothing more."""
    frontdesk = Path("app/frontdesk.py").read_text()
    # The atomic insert guard is untouched.
    assert "WHERE NOT EXISTS (SELECT 1 FROM queue_entry" in frontdesk
    assert "AND status = 'in_consultation')" in frontdesk
    main = Path("app/main.py").read_text()
    # And the WebSocket wall still refuses and closes.
    assert 'await websocket.close(code=4409)' in main


def test_a_silent_refresh_no_longer_stands_in_for_a_refusal_on_today():
    """today.html used to answer an unexplained 409 with a bare refresh: the tap
    did nothing and said nothing."""
    today = _page("today.html")
    offer = today[today.index("function offerResume("):]
    offer = offer[:offer.index("\n}")]
    assert "alert(" in offer, "an unexplained refusal must still say something"
    assert "opened at" in offer, "say when the blocking entry was opened"
    assert "free the slot" in offer, "say what the doctor can do about it"


# ------------------------------- Phase 7c slice 5: the pause banner's buttons

def test_the_pause_banner_buttons_keep_all_three_standing_rules():
    """RESUME AUTO and TAKE OVER (PHASE_7C_SPEC.md §7, §10), extended under
    the same three rules as every other control on the live page:

    1. Never swallow: each tap sends the acknowledgement or shows why it
       could not; a server refusal (auto_refused) is shown, never dropped.
    2. A control that can act must not look as if it cannot — and the
       reverse: the buttons are disabled WITH THE REASON on themselves
       when the socket is down, and carry a reason when they can act.
    3. Where the doctor is looking: the banner lives inside the urgent
       panel in the sticky row — the alarm's reserved home, on screen at
       every scroll position — never at the bottom of the page.
    Both are labelled, plainly, in words.
    """
    live = _page("live.html")
    # Rule 3: inside the urgent panel, inside the sticky row's left half.
    left = live[live.index('id="stickyLeft"'):live.index('id="stickyRight"')]
    assert 'id="urgentBox"' in left
    urgent = left[left.index('id="urgentBox"'):]
    assert 'id="pauseBanner"' in urgent
    banner = urgent[urgent.index('id="pauseBanner"'):urgent.index('</div>\n      </div>')]
    # Labelled, in words.
    assert 'id="pauseResume"' in banner and ">RESUME AUTO<" in banner
    assert 'id="pauseTakeOver"' in banner and ">TAKE OVER<" in banner
    assert 'title="' in banner.split('id="pauseResume"')[1].split(">")[0]
    assert 'title="' in banner.split('id="pauseTakeOver"')[1].split(">")[0]
    # Every pending action text is listed — the list, not a count.
    assert 'id="pauseList"' in banner
    # Rule 2: the disabled state carries its reason, on the control.
    refresh = live[live.index("function refreshPauseControls()"):]
    refresh = refresh[:refresh.index("\n}")]
    assert "btn.disabled = !connected;" in refresh
    assert "btn.title = !connected" in refresh
    assert "Reconnecting" in refresh
    # ...and refreshSpeechControls (the socket-state writer) drives it.
    speech_controls = live[live.index("function refreshSpeechControls()"):]
    speech_controls = speech_controls[:speech_controls.index("\n}")]
    assert "refreshPauseControls();" in speech_controls
    # Rule 1: a tap either sends or says why; a refusal is shown.
    ack = live[live.index("function acknowledgePause(resolution)"):]
    ack = ack[:ack.index("\n}")]
    assert "ws.send(JSON.stringify({type: 'auto_ack', resolution: resolution}));" in ack
    assert "showSpeakError(" in ack
    assert "pauseResume.addEventListener('click', () => acknowledgePause('resume'));" in live
    assert "pauseTakeOver.addEventListener('click', () => acknowledgePause('take_over'));" in live
    refused = live[live.index("else if (msg.type === 'auto_refused') {"):]
    refused = refused[:refused.index("\n  }")]
    assert "showSpeakError(msg.detail);" in refused
