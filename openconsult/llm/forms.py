"""Does an answer fit its form? The small part of JSON schema the forms
use: object, array, string, boolean, number, required, properties,
items, enum, maxItems. Gives the first reason it does not, or None."""

from __future__ import annotations

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
         "integer": int, "number": (int, float)}


def misfit(value, form: dict, where: str = "answer") -> str | None:
    kind = form.get("type")
    if kind in TYPES:
        expected = TYPES[kind]
        if isinstance(value, bool) and kind in ("integer", "number"):
            return f"{where} is a boolean, not a {kind}"
        if not isinstance(value, expected):
            return f"{where} is not a {kind}"
    if "enum" in form and value not in form["enum"]:
        return f"{where} is not one of {form['enum']}"
    if kind == "object":
        for key in form.get("required", []):
            if key not in value:
                return f"{where} lacks {key}"
        for key, sub in form.get("properties", {}).items():
            if key in value:
                reason = misfit(value[key], sub, f"{where}.{key}")
                if reason:
                    return reason
    if kind == "array":
        if "maxItems" in form and len(value) > form["maxItems"]:
            return f"{where} has more than {form['maxItems']} items"
        for i, item in enumerate(value):
            reason = misfit(item, form.get("items", {}), f"{where}[{i}]")
            if reason:
                return reason
    return None
