"""Every sentence and name a learner reads on a teaching page, in one
place (spec 12; 15.14 and the details of run 10b; R24). The file of
words of the clinic, openconsult/words.py, holds the tab's name, the
line of the cloud statement and the lines of the log; everything else of
teaching is here, so that the owner can correct the wording here and
tests take a sentence from here.

THE OWNER'S, letter for letter, are marked as his. The drafts that the
details of run 10b give are built as given and marked as the details'.
The rest are drafts of the build, for him to correct on screen. No
sentence here is read by a model: the three questions are fixed words
of the page and go to no model (ruling 13)."""

# ------------------------------------------------------------ the teaching page

TITLE = "Teaching"
# Ruling 1 and 12.5: the line of no affiliation. A draft.
NOT_AFFILIATED = ("The topics are the titles of the RCGP's topic guides. "
                  "OpenConsult is not affiliated with or endorsed by the RCGP.")
# Ruling 22: the page says not to type a real patient's details. A draft.
NO_REAL_PATIENT = "Do not type a real patient's details. Every case here is made up."

BANK_HEADING = "Cases from a clinician's scripts"
COL_CASE, COL_TOPIC, COL_LEVEL, COL_LABEL = "Case", "Topic", "Level", "Label"
CASE_NUMBER = "Case {n}"                                   # the details': a case of the bank is Case 1 to Case 8
BANK_UNREAD_ONE = "One case could not be read and is not offered."
BANK_UNREAD_MANY = "{n} cases could not be read and are not offered."

# The three labels, as the details give them (12.3, rule 5; ruling 3). Drafts until the owner has seen them on screen.
LABELS = {
    "ai": "AI-written, not reviewed by a clinician",
    "script": "Made from a clinician's script. The scenario is not yet reviewed.",
    "approved": "Approved by a clinician",
}
# The three levels (ruling 5): the name, and the line of the details that says what the level is.
LEVEL_NAMES = {"straightforward": "Straightforward", "hidden": "Hidden", "noisy": "Noisy"}
LEVEL_LINES = {
    "straightforward": "Straightforward: the story points to the diagnosis.",
    "hidden": "Hidden: what must not be missed is not the first thing the story suggests.",
    "noisy": "Noisy: another worry or a wrong idea stands in the way.",
}


def bank_unread(count: int) -> str | None:
    """What the page says of files of the bank that did not hold, or None when every one was read."""
    if not count:
        return None
    return BANK_UNREAD_ONE if count == 1 else BANK_UNREAD_MANY.format(n=count)
