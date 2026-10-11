"""A made-up month of the drug file and a made-up drug list for the suite.
Every name here is made up: none is a drug, and none is a word of any
script. The columns are those the rule needs and a few it does not."""

from __future__ import annotations

import io
import json
from pathlib import Path

from openconsult.bench.speech import druglist

COLUMNS = ["YEAR_MONTH", "REGION_NAME", "BNF_PRESENTATION_CODE", "BNF_PRESENTATION_NAME", "SUPPLIER_NAME",
           "GENERIC_BNF_EQUIVALENT_NAME", "BNF_CHEMICAL_SUBSTANCE", "BNF_SECTION_CODE", "BNF_CHAPTER_CODE",
           "PREP_CLASS", "ITEMS"]
ROWS = [
    # a generic product: its own generic equivalent
    ("202607", "Made-up region", "0601022B0AAABAB", "Metforma hydrochloride 500mg tablets", "A maker",
     "Metforma hydrochloride 500mg tablets", "Metforma hydrochloride", "060102", "06", "1", "10"),
    # a branded product of the same substance: the brand at its front
    ("202607", "Made-up region", "0601022B0BBABAB", "Glucoform 500mg tablets", "A maker",
     "Metforma hydrochloride 500mg tablets", "Metforma hydrochloride", "060102", "06", "2", "3"),
    # a two-word generic name, and a brand of two words that are everyday words
    ("202607", "Made-up region", "0403030X0BBABAB", "Night Calm 25mg capsules", "A maker",
     "Dormirex pamoate 25mg capsules", "Dormirex pamoate", "040303", "04", "2", "1"),
    ("202607", "Made-up region", "0403030Y0AAAAAA", "Light mineral parafil 10ml", "A maker",
     "Light mineral parafil 10ml", "Light mineral parafil", "010101", "01", "1", "2"),
    # a name with "with": two names of its own
    ("202607", "Made-up region", "1502010J0AAAAAA", "Lidocaina with adrenalina 1% injection", "A maker",
     "Lidocaina with adrenalina 1% injection", "Lidocaina with adrenalina", "150201", "15", "1", "4"),
    # a name whose words are all salt and form words is kept whole
    ("202607", "Made-up region", "0902021X0AAAAAA", "Sodium chloride 0.9% infusion", "A maker",
     "Sodium chloride 0.9% infusion", "Sodium chloride", "090202", "09", "1", "5"),
    # left out: an appliance (chapter 21), a food (section 0913), a short name, no substance
    ("202607", "Made-up region", "21010000000AAAA", "Made-up bandage 5cm", "A maker", "", "Made-up bandage", "210100", "21", "3", "1"),
    ("202607", "Made-up region", "0904010A0AAAAAA", "Made-up food drink 200ml", "A maker", "Made-up food drink 200ml", "Made-up food", "091301", "09", "1", "1"),
    ("202607", "Made-up region", "0905010T0AAAAAA", "Tin 10mg tablets", "A maker", "Tin 10mg tablets", "Tin", "090501", "09", "1", "1"),
    ("202607", "Made-up region", "0905010U0AAAAAA", "Nameless 10mg tablets", "A maker", "Nameless 10mg tablets", "", "090501", "09", "1", "1"),
]


def csv_text(rows=ROWS) -> str:
    out = io.StringIO()
    out.write(",".join(COLUMNS) + "\r\n")
    for row in rows:
        out.write(",".join(row) + "\r\n")
    return out.getvalue()


def write_csv(path: Path, rows=ROWS) -> Path:
    path.write_bytes(("﻿" + csv_text(rows)).encode("utf-8"))      # an encoding mark at the start, as a portal may give
    return path


def made_up_list(tmp_path: Path) -> druglist.DrugList:
    path = write_csv(tmp_path / "pca_202607.csv")
    return druglist.DrugList(druglist.make_list(path, "202607"))


def write_list(tmp_path: Path) -> Path:
    path = write_csv(tmp_path / "pca_202607.csv")
    target = tmp_path / "drug_list.json"
    target.write_text(json.dumps(druglist.make_list(path, "202607")), encoding="utf-8")
    return target
