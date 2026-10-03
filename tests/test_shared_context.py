"""No model request in app/ carries a context length typed in directly.

Ollama reloads the model whenever num_ctx changes between calls, so every
call to the app's model uses the one shared setting, app.cds.CDS_NUM_CTX
(session 5, owner decision; the letters joined on 3 Oct 2026, owner
decision, after Task 3m measured their typed-in 8192 costing a reload
each way and pushing embeddinggemma out of the GPU).

What is pinned: in every module under app/, every place a num_ctx is
given — a "num_ctx" dict entry, a num_ctx= keyword, an
x["num_ctx"] = assignment — takes the shared name CDS_NUM_CTX and nothing
else. The scan is shown to reach the four known call sites and to catch
each of the three forms when a number is typed in, so it cannot pass by
finding nothing. Needs no model.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
SHARED = "CDS_NUM_CTX"


def _num_ctx_values(tree: ast.AST) -> list[ast.expr]:
    """Every expression given as a num_ctx, in the three forms."""
    found: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            found += [value for key, value in zip(node.keys, node.values)
                      if isinstance(key, ast.Constant) and key.value == "num_ctx"]
        elif isinstance(node, ast.Call):
            found += [kw.value for kw in node.keywords if kw.arg == "num_ctx"]
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (isinstance(target, ast.Subscript)
                        and isinstance(target.slice, ast.Constant)
                        and target.slice.value == "num_ctx" and node.value is not None):
                    found.append(node.value)
    return found


def _is_shared(value: ast.expr) -> bool:
    return ((isinstance(value, ast.Name) and value.id == SHARED)
            or (isinstance(value, ast.Attribute) and value.attr == SHARED))


def _scan() -> dict[str, list[ast.expr]]:
    out: dict[str, list[ast.expr]] = {}
    for path in sorted(APP.rglob("*.py")):
        values = _num_ctx_values(ast.parse(path.read_text(), filename=str(path)))
        if values:
            out[str(path.relative_to(APP.parent))] = values
    return out


def test_every_num_ctx_in_app_is_the_shared_setting():
    sites = _scan()
    # The scan reached the known call sites (CDS engine, note, guideline
    # summary, letters); if it found none of them it would prove nothing.
    assert {"app/cds.py", "app/notes.py", "app/rag.py", "app/letters.py"} <= set(sites)
    offenders = [f"{path}:{value.lineno}: {ast.unparse(value)}"
                 for path, values in sites.items() for value in values
                 if not _is_shared(value)]
    assert offenders == [], f"num_ctx not taken from {SHARED}: {offenders}"


def test_the_scan_catches_a_typed_in_context_in_each_form():
    """The adversarial check: a number typed in, in each form the scan
    covers, is found and is not the shared setting."""
    for source in ('options = {"temperature": 0.0, "num_ctx": 8192}',
                   'options = dict(temperature=0.0, num_ctx=8192)',
                   'options["num_ctx"] = 8192'):
        values = _num_ctx_values(ast.parse(source))
        assert len(values) == 1, source
        assert not _is_shared(values[0]), source
    assert all(_is_shared(v) for v in _num_ctx_values(ast.parse(
        'a = {"num_ctx": CDS_NUM_CTX}; b = dict(num_ctx=cds.CDS_NUM_CTX)')))
