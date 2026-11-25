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

from openconsult import words

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


START = "Start"
NOT_IN_LIST = "That case is not in the list."
# Why the press that starts a case does not start one, said on the control itself (R15; 10.4).
CANNOT_START = "A case cannot start: {reason}"
CANNOT_START_NO_ANSWER = "A case cannot start: the language model does not answer on {engine}."
CANNOT_START_NOT_CONNECTED = "A case cannot start: Claude is not connected. Connect it in Settings."
CANNOT_START_NO_TICK = ("A case cannot start in cloud mode: the statement for your choices is not ticked. "
                        "Read and tick it in Settings.")

# Under the mark Cloud at the top of a teaching page, in cloud mode. THE OWNER'S, letter for letter (ruling 15):
CLOUD_TYPED = "What you type goes to Claude."
# and under it the cost, the details' draft, from the bench of run 10a (ruling 19).
CLOUD_COST = "A teaching case costs about 1 US cent."

# ------------------------------------------------------------------- a case

NEW_CASE = "A new case"                                    # the heading of a case that is not of the bank
PRESENTED = "{name}, {age}, {sex}"                         # the patient is presented (12.1, step 2)
SPEAKS_FOR = "Speaking for the child: {parent}"            # the details': a parent who speaks for a child
PATIENT, YOU = "Patient", "You"
# Served for a page whose script has not run; the script takes the line away.
NO_SCRIPT = "This page's script did not run. Send each line before you leave the page."
# A press from a page that was no longer up to date: nothing is stored, and the page says so (R15).
STALE = "That press came from a page that was no longer up to date. This is where the case stands now."
STALE_TYPED = "You had typed: {text}"                      # where the box those words were typed in is no longer there

# The history (the details: The history).
NEXT_LINE = "Your next line"
SEND = "Send"
TYPE_A_LINE = "Type a line first."
PATIENT_ANSWERING = "The patient is answering..."
END_HISTORY = "End the history"                            # the details'
END_HISTORY_LINE = "After this the patient cannot be asked more."
END_WITH_WORDS = "You have typed a line and not sent it. Send it, or clear the box, before you end the history."
HISTORY_LONG = "This history is getting long. Only a few more lines fit. Then end the history."
HISTORY_FULL = "This history is full: the language model cannot read more. End the history to go on."
LINE_TOO_LONG = "This line is too long. Shorten it to {most} characters or fewer."
# A call that failed, as a learner reads the sentence of its job (R30): nothing is asked a second time by itself.
REPLY_FAILED = "The patient's reply did not come: {reason}. Your line is still in the box. Send it again when you are ready."
# Said by the page's script, which holds no sentence of its own.
LOGIN_ENDED = "Your login has ended. Your words are still in the box. Log in again in another tab, then send them."
NO_ANSWER = "OpenConsult did not answer. Your words are still in the box."


# The examination (12.1, step 4; D10; the details: The examination).
EXAMINATION = "Examination"
EXAMINATION_INTRO = "Type what you would examine. You may send more than once."
EXAMINE_BOX = "What would you examine?"
TYPE_A_REQUEST = "Type what you would examine first."
EXAMINATION_WAITING = "The case's findings are being looked up..."
YOU_TYPED = "You typed:"
# THE OWNER'S, letter for letter (rulings 16 and 21): beside an examination or a test that the case does not hold.
NO_FINDING = "The case gives no finding for this."
NOT_AN_EXAMINATION = "That is not an examination or a bedside test. Investigations come next."      # the details'
NOTHING_TO_SHOW = "Nothing could be shown for this request. Try it in other words."
FINISH_EXAMINATION = "Finish the examination"              # the details'
FINISH_LINE = "This shows the case's other findings and brings the first question."
FINISH_WITH_WORDS = "You have typed something and not sent it. Send it, or clear the box, before you finish the examination."
OTHER_FINDINGS = "The case's other findings"
NO_OTHER_FINDING = "The case holds no other finding."      # the details'
NO_FINDING_AT_ALL = "This case holds no examination finding."      # the details'
REQUEST_TOO_LONG = "This request is too long. Shorten it to {most} characters or fewer."
EXAMINATION_FULL = "No more requests can be read for this case. Finish the examination to go on."
EXAMINATION_FAILED = ("The examination could not be read: {reason}. Your words are still in the box, and no finding is shown "
                      "for them.")


def reason(failure: str) -> str:
    """Why a model call failed, in the words the page of calls already uses for the door's outcomes."""
    return words.CALL_OUTCOMES[failure]


def most(number: int) -> str:
    return f"{number:,}"


def bank_unread(count: int) -> str | None:
    """What the page says of files of the bank that did not hold, or None when every one was read."""
    if not count:
        return None
    return BANK_UNREAD_ONE if count == 1 else BANK_UNREAD_MANY.format(n=count)
