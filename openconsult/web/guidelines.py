"""The Guidelines section of Settings (spec 15.12, ruling 5; 7.3 rules 1
and 4; R15; R21): the loaded documents with their titles, publishers,
passage counts and dates, Remove on each, and Add with a file from this
computer, its title, its publisher and the one statement. Every refusal
lands on the control pressed; with no worker installed, Add is disabled
with the reason. Every add and remove is audited by the rows."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.guidelines import loading
from openconsult.guidelines.embedder import state_line
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import multipart_fields

router = APIRouter()
ADD = "add-guideline"
REFUSALS = {"kind": words.GUIDELINE_FILE_KIND, "no_passages": words.GUIDELINE_NO_PASSAGES}


def _date(stamp: str) -> str:
    return words.plain_date(datetime.fromisoformat(stamp))


def section_data(request: Request) -> dict:
    """What the section shows: the sources, the worker's line, whether Add
    is disabled and why, and the notice of the last add or remove."""
    p = parts(request)
    sources = [{**s, "added": _date(s["added_at"])} for s in p.sources.loaded()]
    disabled = None if p.embedder.installed else words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=p.embedder.ready())
    done = request.query_params.get("done", "")
    notice = None
    if done == "guideline_added":
        notice = words.GUIDELINE_ADDED.format(passages=request.query_params.get("passages", "0"),
                                              seconds=request.query_params.get("seconds", "0"))
    elif done == "guideline_removed":
        notice = words.GUIDELINE_REMOVED
    return {"sources": sources, "worker_line": state_line(p.embedder), "add_disabled": disabled, "notice": notice,
            "counts": p.sources.counts()}


def _settings(request: Request, user, control: str, message: str):
    from openconsult.web.routes import _settings_page
    return _settings_page(request, user, (control, message))


def _refusal_for(refused: loading.Refused) -> str:
    if refused.reason == "too_big":
        return words.GUIDELINE_FILE_TOO_BIG.format(limit=loading.UPLOAD_LIMIT_BYTES // 1_000_000)
    if refused.reason == "worker":
        return words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=refused.detail)
    if refused.reason == "embed_failed":
        return words.GUIDELINE_EMBED_FAILED.format(reason=refused.detail)
    return REFUSALS[refused.reason]


@router.post("/settings/guidelines/add")
async def add(request: Request, user=Depends(guards.logged_in)):
    p = parts(request)
    fields, files, too_big = await multipart_fields(request, limit=loading.UPLOAD_LIMIT_BYTES + 100_000)
    if too_big:
        return _settings(request, user, ADD, words.GUIDELINE_FILE_TOO_BIG.format(limit=loading.UPLOAD_LIMIT_BYTES // 1_000_000))
    name, data = files.get("file", ("", b""))
    if not name or not data:
        return _settings(request, user, ADD, words.GUIDELINE_FILE_MISSING)
    if not fields.get("title", "").strip():
        return _settings(request, user, ADD, words.GUIDELINE_TITLE_MISSING)
    if not fields.get("publisher", "").strip():
        return _settings(request, user, ADD, words.GUIDELINE_PUBLISHER_MISSING)
    if fields.get("statement") != "yes":
        return _settings(request, user, ADD, words.GUIDELINE_TICK_NEEDED)
    if not p.embedder.installed:
        return _settings(request, user, ADD, words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=p.embedder.ready()))
    added = loading.add_document(p.sources, p.embedder, name, data, fields["publisher"], "page", title=fields["title"])
    if isinstance(added, loading.Refused):
        return _settings(request, user, ADD, _refusal_for(added))
    _index_changed(p)
    raise Redirect(f"/settings?done=guideline_added&passages={added.passages}&seconds={added.seconds}")


@router.post("/settings/guidelines/{source_id}/remove")
async def remove(request: Request, source_id: int, user=Depends(guards.logged_in)):
    """One press removes the document and its passages, audited; a
    document that is not loaded is no control, so back to the page."""
    p = parts(request)
    source = p.sources.source(source_id)
    if source is None or source["removed_at"] is not None:
        raise Redirect("/settings")
    p.sources.remove_source(source_id)
    _index_changed(p)
    raise Redirect("/settings?done=guideline_removed")


def _index_changed(p) -> None:
    """The search's index in memory reads the rows again after a change."""
    p.guidelines.index.refresh()
