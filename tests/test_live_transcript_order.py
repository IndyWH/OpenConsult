"""The live transcript must read in the order the room happened.

Consultation 450: the Assistant line at 2:25 rendered ABOVE the patient line at
2:24, so the consultation read as though the machine had spoken first.

Arrival order is not time order and cannot be. The live path re-transcribes a
rolling buffer and commits a segment only once it ends more than ~2 s before the
newest audio (`app/live.py`), so a transcript line always arrives a couple of
seconds after the words were said — while a spoken utterance is logged the
instant playback starts. Appending in arrival order therefore puts the machine
ahead of the patient every time it speaks.

These tests EXECUTE the shipped `insertByTime` from `live.html` under Node with
a tiny DOM stub, rather than asserting that the source contains something. The
project has no browser in its suite and the rest of the page is checked by
source inspection; ordering is arithmetic, so it can be run for real, and a test
that runs the function is worth more than one that recognises it. Self-skips
where Node is absent, the same convention as the Ollama- and Postgres-dependent
tests.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")


def _extract_insert_by_time() -> str:
    """The shipped function, lifted verbatim from the page."""
    source = Path("app/static/live.html").read_text()
    start = source.index("function insertByTime(")
    end = source.index("\n}", start) + 2
    return source[start:end]


_HARNESS = """
// Minimal DOM: an ordered child list is all insertByTime touches.
function makeNode(tag) {
  return {
    tag, dataset: {}, children: [],
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(node, before) {
      const at = before === null ? this.children.length
                                 : this.children.indexOf(before);
      this.children.splice(at < 0 ? this.children.length : at, 0, node);
      return node;
    },
    querySelectorAll(sel) {
      if (sel !== 'p[data-t]') throw new Error('unexpected selector ' + sel);
      return this.children.filter(c => c.tag === 'p' && 't' in c.dataset);
    },
  };
}

const transcriptEl = makeNode('div');
const partialEl = makeNode('span');          // must always stay last
transcriptEl.appendChild(partialEl);

__INSERT_BY_TIME__

function add(label, seconds) {
  const p = makeNode('p');
  p.label = label;
  insertByTime(p, seconds);
}

for (const [label, seconds] of ARRIVALS) add(label, seconds);

console.log(JSON.stringify({
  order: transcriptEl.children.filter(c => c.tag === 'p').map(c => c.label),
  partialIsLast: transcriptEl.children[transcriptEl.children.length - 1] === partialEl,
}));
"""


def _run(arrivals: list[tuple[str, float]]) -> dict:
    script = (f"const ARRIVALS = {json.dumps(arrivals)};\n"
              + _HARNESS.replace("__INSERT_BY_TIME__", _extract_insert_by_time()))
    done = subprocess.run([NODE, "-e", script], capture_output=True, text=True,
                          timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_450s_out_of_order_arrival_reads_in_time_order():
    """THE regression, with 450's own timings. The Assistant utterance at 2:25
    is logged the moment it plays; the patient's 2:24 line is committed a couple
    of seconds later and therefore ARRIVES second."""
    result = _run([("patient 2:19", 139.0),
                   ("assistant 2:25", 145.0),
                   ("patient 2:24", 144.0)])   # arrives last, belongs before
    assert result["order"] == ["patient 2:19", "patient 2:24", "assistant 2:25"]


def test_a_line_arriving_far_out_of_order_still_lands_correctly():
    result = _run([("t=100", 100.0), ("t=200", 200.0), ("t=300", 300.0),
                   ("t=5", 5.0)])
    assert result["order"] == ["t=5", "t=100", "t=200", "t=300"]


def test_in_order_arrivals_are_unchanged():
    """The common case must not be disturbed by the fix."""
    result = _run([("a", 1.0), ("b", 2.0), ("c", 3.0), ("d", 4.0)])
    assert result["order"] == ["a", "b", "c", "d"]


def test_equal_timestamps_keep_arrival_order():
    """Stable insertion: a spoken utterance and a transcript line stamped the
    same second must not swap places on every re-render."""
    result = _run([("first", 60.0), ("second", 60.0), ("third", 60.0)])
    assert result["order"] == ["first", "second", "third"]


def test_the_partial_line_stays_last():
    """The grey in-progress guess belongs at the bottom whatever arrives."""
    result = _run([("a", 10.0), ("b", 1.0)])
    assert result["partialIsLast"] is True


def test_both_channels_go_through_the_ordering():
    """A future contributor adding a third channel should have to think about
    it: neither path may append directly again."""
    source = Path("app/static/live.html").read_text()
    for function in ("addFinal", "addSpoken"):
        body = source[source.index(f"function {function}("):]
        body = body[:body.index("\n}")]
        assert "insertByTime(" in body, f"{function} must order by time"
        assert "transcriptEl.insertBefore" not in body, (
            f"{function} must not append directly — that is how 450 happened")
    # And nothing else inserts into the transcript behind its back.
    direct = re.findall(r"transcriptEl\.insertBefore\(", source)
    assert len(direct) == 1, (
        "exactly one insertion point: insertByTime")
