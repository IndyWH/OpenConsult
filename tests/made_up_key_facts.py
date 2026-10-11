"""A made-up key-fact file of the same form as Cowork's, for the suite.
Made up: no fact, drug or sentence of any script of the rehearsal."""

from __future__ import annotations

import json
from pathlib import Path

MADE_UP = {
    "_about": "made up for the suite, in the form of the key-fact file",
    "kinds_in_order": ["red_flag", "drug", "negative", "safety_net", "positive", "examination", "plan"],
    "negation_words_added": ["nil", "denies", "denied", "deny", "absent", "negative", "non", "against", "avoid", "afebrile"],
    "scripts": {
        "MU": {
            "file": "made_up.md",
            "sha256": "0" * 64,
            "speeches": 6,
            "facts": [
                {"id": "MU-01", "kind": "negative", "fact": "no pain at rest", "said_in": [1, 2],
                 "needs": [["at rest", "resting"]], "negated": True, "unless": ["relieved"]},
                {"id": "MU-02", "kind": "examination", "fact": "blood pressure 150 over 95", "said_in": [3],
                 "needs": [["bp", "blood pressure"]], "numbers": [["150"], ["95"]], "negated": False},
                {"id": "MU-03", "kind": "safety_net", "fact": "straight to the hospital if the pain comes at rest", "said_in": [5],
                 "needs": [["hospital", "a and e", "emergency department"]], "negated": False, "sections": ["plan"]},
                {"id": "MU-04", "kind": "positive", "fact": "father had a heart attack", "said_in": [6],
                 "needs": [["father", "dad"], ["heart attack", "mi"]], "negated": False},
                {"id": "MU-05", "kind": "drug", "fact": "metforma one gram twice a day", "said_in": [2],
                 "needs": [["metforma"]], "numbers": [["1", "1000"]], "negated": False},
            ],
        }
    },
}


def write_made_up(folder: Path) -> Path:
    path = Path(folder) / "key_facts.json"
    path.write_text(json.dumps(MADE_UP, indent=1), encoding="utf-8")
    return path
