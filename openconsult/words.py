"""Every sentence the app shows to the user, in one place, so the owner
can correct the wording here and nowhere else. Tests take a sentence
from this file; none holds its own copy, so a wording change is one
change (spec 5.2).

The statement, the tick and the three This machine sentences are the
owner's side's words, used exactly. The rest are drafts for him to
correct on screen.
"""

STATEMENT = (
    "OpenConsult is a research and education prototype. It is not a medical device. "
    "It must never be used with real patients or real patient data. "
    "Every consultation in it is acted or scripted."
)
STATEMENT_TICK = "I agree. I will never use OpenConsult with real patients or real patient data."

# This machine. The key is the case the code chose.
MACHINE = {
    "suitable": "This computer can run OpenConsult's models itself. Nothing spoken needs to leave it.",
    "smaller": (
        "This card has {gb} GB. Running everything on this computer needs {needed} GB, "
        "so OpenConsult will start on cloud models."
    ),
    "none": "No suitable NVIDIA graphics card was found. OpenConsult will use cloud models on this computer.",
    "mac": "This is a Mac. OpenConsult will use cloud models on this computer.",
    "unreadable": "The NVIDIA graphics card could not be read. OpenConsult will use cloud models on this computer.",
}
CARD_LINE = "{name}, {gb} GB"
# The language model's line, shown only on a machine with a suitable card
# (spec 15.7; elsewhere no engine is asked). Drafts for the owner.
ROW_MODEL = "Language model"
MODEL_PRESENT = "Gemma 4 QAT is present."
MODEL_ABSENT = "Gemma 4 QAT is not present."
# The two rows of the room check, on a suitable card only (15.8, rulings 32, 33, 36).
ROW_GUIDELINE_SEARCH = "Guideline search"
ROW_SPEECH_CHOICE = "Speech choice"
# The decisions of the start (15.8, rulings 36 to 38): one sentence for
# each, with the reason in words and no figures. Drafts for the owner.
ENGINE_NAMES = {"vllm": "vLLM", "ollama": "Ollama"}
UNFIT = {
    "no_answer": "{engine} did not answer at its address",
    "no_model": "{engine} is running but does not hold Gemma 4 QAT",
    "small_context": "{engine} is running but its context is too small for a consultation",
}
NONE_ASKED = "no local engine is asked on this computer"
REASONS = {
    "engine_running": "The language model runs on {engine} {version}. {model}",
    "engine_fallback": "The language model runs on {engine} {version}, because {reason}. {model}",
    # The both-missing line of ruling 37; the pointer to the connect screen is stage 9.
    "engine_none": "No local language model is running, and no cloud model is connected yet. {why}.",
    # Where the guideline search sits (ruling 32) and whether the WhisperX choice is offered (ruling 33).
    "guideline_card": "The guideline search will run on the graphics card.",
    "guideline_processor": ("The guideline search will run on the processor, because the card has no room "
                            "for it beside the language model and the speech model."),
    "guideline_no_card": ("The guideline search will run on the processor, because this computer has no "
                          "suitable graphics card."),
    "whisperx_available": "Nemotron is the speech choice. The WhisperX with pyannote choice is available.",
    "whisperx_no_room": ("Nemotron is the speech choice. The WhisperX with pyannote choice is not available, "
                         "because the card has no room for its pass at Stop beside the language model."),
    "whisperx_no_card": ("Nemotron is the speech choice. The WhisperX with pyannote choice is not available, "
                         "because this computer has no suitable graphics card."),
    # The recording converter (15.11 ruling 7), on every machine.
    "converter_package": "Recordings are kept as Opus with ffmpeg {version}, which comes with OpenConsult.",
    "converter_system": "Recordings are kept as Opus with this computer's own ffmpeg, {path}.",
    "converter_none": "No converter was found, so recordings stay as WAV. Start is still offered.",
}
ROW_CONVERTER = "Recording converter"
CARD_NONE = "None found"
CARD_UNREADABLE = "Could not be read"

# The header and the home page.
APP_NAME = "OpenConsult"
NAV_HOME = "Patients"
NAV_SETTINGS = "Settings"
NAV_LOG = "Log"
NAV_LOGOUT = "Log out"
NAV_NEW_PATIENT = "New patient"
HOME_TITLE = "Home"
HOME_SO_FAR = (
    "So far this version runs acted consultations from a patient list to an approved note: find a patient seen "
    "before or add a new one, start a consultation under them with their earlier approved notes on your screen, "
    "and talk; the words appear live with the differentials, the alarm, the differential the alarm names marked red, "
    "and a quiet clock; at Stop it asks which speaker was you, checks for missing speech, marks the drug names "
    "the language model doubts, drafts the note with its line numbers checked, keeps the recording as Opus, and "
    "shows the review page: the note, the last differentials of the model beside the assessment, the warnings and "
    "the alarms, the transcript with its player and the control Check who spoke; you correct, draft again, copy "
    "and approve. Corrections to a patient never "
    "rewrite an earlier consultation; recordings are deleted after the retention days; Delete really deletes."
)
HOME_WAITING = "Waiting at Stop"
# The Patients page (spec 15.11 ruling 1; 8.1; R1, R17): the list, last seen first, and the one search box. Drafts.
PATIENTS_TITLE = "Patients"
FIELD_SEARCH = "Name, date of birth or number"
SEARCH = "Search"
SEARCH_NONE = "No patient matches {query}."
NO_PATIENTS = "No patient yet."
COL_NAME = "Name"
COL_DATE_OF_BIRTH = "Date of birth"
COL_SEX = "Sex"
COL_LAST_SEEN = "Last seen"
COL_NUMBER = "Number"
NEVER_SEEN = "Not yet seen"
# The patient's page (15.11 ruling 2; 8.1; R2, R15). Drafts.
PATIENT_TITLE = "Patient"
NUMBER_LINE = "number {id}"
DETAILS = "Details"
SAVE_DETAIL = "Save"
DETAIL_UNCHANGED = "Nothing changed."
CONSULTATIONS = "Consultations"
NO_CONSULTATIONS = "No consultation yet."
STATE_WORDS = {"approved": "approved", "review": "waiting for review", "refused": "a refused note",
               "running": "running", "at_stop": "waiting at Stop"}
NEW_CONSULTATION = "New consultation"
RAN_WITH = "Seen as"
PATIENTS_PAGE_LINK = "The patient's page"
DETAILS_CORRECTED = "The patient's details were corrected on {date}. This consultation keeps the details it ran with."
# Deleting (15.11 ruling 8; D44; R15). Drafts.
DELETE = "Delete"
DELETE_CONSULTATION = "Delete this consultation"
DELETE_CONSULTATION_QUESTION = ("Delete the consultation of {name} on {date}? The recording, the transcript and the note "
                                "will be gone. This cannot be undone.")
YES_DELETE = "Yes, delete"
KEEP = "Keep"
DELETE_PATIENT = "Delete patient"
DELETE_PATIENT_BLOCKED = "Cannot delete while a consultation remains. Delete each consultation first."
DELETE_PATIENT_QUESTION = "Delete {name}, number {id}? This cannot be undone."
PATIENT_DELETED = "Patient {id} was deleted."
HOME_WAITING_LINE = "{name}, started {when}"
CONTINUE_CONSULTATION = "Continue"

# The new-patient form and the Start screen (spec 8.2; 15.10 ruling 9; R1, R11, R17; D38). Drafts.
PATIENT_NEW_TITLE = "New patient"
PATIENT_ACTED_LINE = "Every patient here is acted. Never enter a real patient or real patient data."
FIELD_PATIENT_NAME = "Name"
FIELD_DATE_OF_BIRTH = "Date of birth"
FIELD_SEX = "Sex"
SEX_WORDS = {"F": "Female", "M": "Male"}
PATIENT_NAME_MISSING = "Enter the patient's name."
DATE_OF_BIRTH_MISSING = "Enter the date of birth."
DATE_OF_BIRTH_BAD = "The date of birth is not a date, is in the future, or is more than 120 years ago."
SEX_MISSING = "Choose the sex."
SAVE_PATIENT = "Save and go to Start"
START_TITLE = "Start a consultation"
AGE_LINE = "{age} years old"
AGE_ONE = "1 year old"
AGE_BABY = "under 1 year old"
TICK_RIGHT_PATIENT = "This is the right patient."
TICK_ACTED = "This consultation is acted. Nobody in it is a real patient."
FIELD_INTENDED = "Intended time"
MINUTES = "{minutes} minutes"
ROW_SPEECH_IN_USE = "Speech"
START = "Start"
TICK_BOTH = "Tick both boxes to start."
START_NO_MODEL = "Start is not offered: {reason}"
START_MODEL_UNREACHABLE = "Start is not offered: the language model does not answer on {engine}."
START_NO_SPEECH = (
    "Start is not offered: a local speech choice is needed, and none can be used. {reason} "
    "The cloud choices come with stage 9."
)
SPEECH_REASONS = {
    "nemotron_not_installed": "Nemotron is not installed.",
    "whisperx_not_installed": "WhisperX with pyannote is not installed.",
    "whisperx_no_room": "The WhisperX with pyannote choice is not available on this card.",
    "no_card": "This computer has no suitable graphics card for a local speech choice.",
}
NO_SUCH_PATIENT = "There is no patient with that number."
# The Start screen for a patient seen before (15.11 ruling 3; 8.2; D25). Drafts.
EARLIER_NOTES = "Earlier notes, approved"
EARLIER_NOTE_LINE = "{number}, {date}: {line}"
# The switch's labels (ruling 3): 7a's, when the notes reached the doctor's screen and no model, kept as its
# record; 7b's, shown since the bench of 8.6 and ruling 11, when the same switch also sends them to the two calls.
SWITCH_SHOWS_ON_SCREEN = "Show the earlier notes on your screen during this consultation."
SWITCH_USES_AS_BACKGROUND = "Use the earlier notes as background for the model and show them on your screen."

# The live page (spec 15.10, The live page; rulings 1, 2 and 10; R9, R15, R20, R29). Drafts.
LIVE_TITLE = "Consultation"
STOP = "Stop"
STOPPING = "Stopping..."
PANEL_TRANSCRIPT = "Transcript"
PANEL_ASSESSMENT = "Differentials, questions and signs"
PANEL_ALARM = "Alarm"
DIFFERENTIALS = "Differentials"
QUESTIONS = "Questions to ask"
SIGNS = "Signs to check"
SPEAKER_WORD = "Speaker {n}"
LISTENING = "Listening."
SPEECH_STARTING = "Starting the speech worker."
WAITING_FOR_WORDS = "No words yet."
PASS_RUNNING = "The model is reading the transcript."
FROM_EARLIER_PASS = "From the earlier pass."
PASS_FAILED = "This pass's assessment failed: {reason}"
ALARM_NONE = "No alarm."
ALARM_FIRED = "Time critical: act now."
ALARM_NO_ACTION = "The model thinks this may be time critical but has not said what to do."
ALARM_NOT_JUDGED = "The alarm was not judged this pass: {reason}"
ALARM_ARRANGED = "The urgent step is already done or arranged."
SHOW_REASONING = "Why"
EARLIER_ALARMS = "Earlier alarms"
ACKNOWLEDGE = "Seen"
ACKNOWLEDGED = "Seen"
CLOCK_USED = "{used} of {intended}"
CLOCK_OVER = "Over the intended time."
MODEL_LINE = "Speech: {speech}. Language model: {model} on {engine} {version}."
SPEECH_STOPPED = "The speech choice has stopped: {reason} The recording goes on."
MIC_REFUSED = "The microphone could not be opened: {reason}"
# Spec 15.9, ruling 32: said at Start when the browser does not give the rate asked. A draft.
RATE_NOT_GIVEN = ("This browser did not give sound at 48,000 samples a second ({found}). This consultation may not be "
                  "transcribed: stop it and try a current Chrome, Edge, Firefox or Safari.")
SOCKET_LOST = "The connection to OpenConsult was lost. Trying again."
SOCKET_BACK = "Connected again."
# The earlier-notes panel (15.11 ruling 4). Drafts.
PANEL_EARLIER_NOTES = "Earlier notes, approved"
OPEN_NOTE = "Open"
FOLD_NOTE = "Fold"
NO_EARLIER_NOTES = "No earlier approved note."
# The mark of 8.5, on the decision support panel while the block is sent, and at review beside the model's differentials.
EARLIER_NOTES_IN_USE = "Earlier notes in use."
# The red mark (15.11 ruling 9). Drafts.
ALARM_NAMED = "Named in the alarm. Press to see why."
CLOSE = "Close"

# Stop, in order (spec 15.10, Stop in order; ruling 7; V1_LESSONS 1.12, 2.2). Drafts.
STOPPING_TITLE = "Stopping"
STAGE_LINES = {
    "speech": "Finishing the transcript.",
    "who_spoke": "Waiting for your answer.",
    "answered": "Your answer is taken. Checking for missing speech.",
    "checks": "Checking for missing speech.",
    "gate": "Checking the transcript.",
    "drug_name": "Checking the drug names.",
    "note": "Drafting the note.",
}
STOP_ALREADY = "Stop was pressed. The transcript is being finished."
WHO_SPOKE_TITLE = "Which speaker was you?"
WHO_SPOKE_INTRO = "Pick the speaker that was you. The other was the patient."
SPEAKER_OPTION = "Speaker {n}: {words}"
CANNOT_TELL = "I cannot tell"
ANSWER = "Continue"
PICK_ONE = "Pick one."
APP_RESTARTED = "OpenConsult was restarted while this consultation ran, so it was stopped as it stood."
FIGURES_LINE = "Word to page {wait} s typical; pass {pass_s} s typical; Stop to final {stop_s} s."
FIGURE_NOTE = " Note {note_s} s."

# The final transcript page (spec 15.10, 6a; ruling 8). Drafts.
FINAL_TITLE = "Final transcript"
WARNINGS = "Warnings"
NO_WARNINGS = "No warnings."
LABEL_CHANGED = "changed by the check"
LABEL_UNSURE = "unsure"
LABEL_REVISED = "label revised by the service"
LABEL_WORDS = {"doctor": "Doctor", "patient": "Patient", "unsure": "Unsure"}
LOW_CONFIDENCE_MARK = "low confidence {score}"
WARN_MISSING_PASSAGE = "Heard live and missing from the final transcript, at {start} to {end} s: {words}"
WARN_UNCOVERED = "Speech with no words written, from {start} to {end} s."
WARN_NO_SPEAKER = "Line {n} has no speaker."
WARN_LOW_CONFIDENCE = "Line {n} is low confidence ({score})."
WARN_CONFIDENCE_NOT_MEASURED = "Confidence was not measured: {choice} gives no score."
WARN_LABEL_CHECK_REFUSED = "The check of who spoke was refused: {reason}. No label was changed by it."
WARN_LABEL_CHECK_FAILED = "The check of who spoke did not run: {reason} No label was changed by it."
# The drug-name marks on the review page (15.10 ruling 20; 15.9 ruling 39). The owner's sentences, letter for letter.
CHECK_THIS_NAME = "Check this name"
WARN_DRUG_MARK = "Line {n}: {heard} may be a drug name that was misheard."
DRUG_SIGN = "Drug name to check: line {n}"
DRUG_MARKED = "The language model marked {count} drug names it doubts. Press a marked line to hear the word, then type the name."
DRUG_MARKED_NONE = "The language model marked no drug name on this page."
DRUG_NOT_PROVEN = ("A drug name with no mark is not proven right. The model can miss a misheard name, most of all when one real "
                   "drug is written for another. Check every drug name in the note before you approve.")
DRUG_CHECK_FAILED = "The check of drug names did not run: {reason} No drug name is marked."
# A draft, for the owner to correct (the details of step 6c, The sentences).
DRUG_MARKED_ONE = "The language model marked 1 drug name it doubts. Press the marked line to hear the word, then type the name."
# Above the note when the check, or an Undo of it, changed who spoke after the note was written (15.10 ruling 18). The owner's.
NOTE_SPEAKERS_CHANGED = "Who spoke has changed since this note was written. Draft the note again to write it from the speakers as they stand now."
# The who-spoke check on the review page (15.10 ruling 19; 15.9 ruling 37). The owner's sentences, letter for letter.
CHECK_WHO_SPOKE = "Check who spoke"
CHECK_WHO_SPOKE_LINE = ("The language model reads the transcript and changes the speaker where the words point to the other person. "
                        "This helps when many lines are under the wrong speaker. It can make a well labelled page worse. "
                        "Every change is marked and can be undone.")
CHECK_RUNNING = "Checking who spoke. This can take up to a minute."
CHECK_CHANGED = "The check changed the speaker on {count} lines. Each one is marked below."
CHECK_UNDO_ALL = "Undo all the changes of the check"
CHECK_CHANGED_NONE = "The check changed no speaker."
CHECK_ALREADY_RAN = "The check of who spoke has already run on this transcript."
# Drafts, for the owner to correct (the details of step 6c, The sentences; the plan of 6c, drafts 3 and 10).
CHECK_CHANGED_ONE = "The check changed the speaker on 1 line. It is marked below."
CHECK_RESTARTED = "OpenConsult was restarted while the check ran."
WARN_SPEECH_FAILED = "The speech choice failed at Stop: {reason} The transcript is what was heard live."
WARN_TOO_SHORT = (
    "The transcript holds {words} words, fewer than {least}: too short to hold a consultation. "
    "No note will be drafted."
)
WARN_EMPTY = "Nothing was heard. No note will be drafted."
WARNING_SENTENCES = {
    "missing_passage": WARN_MISSING_PASSAGE, "uncovered_speech": WARN_UNCOVERED, "no_speaker": WARN_NO_SPEAKER,
    "low_confidence": WARN_LOW_CONFIDENCE, "confidence_not_measured": WARN_CONFIDENCE_NOT_MEASURED,
    "too_short": "{detail}", "empty": WARN_EMPTY,
}

# The note and the review page (spec 15.10, rulings 4, 6, 8, 11 and 12; R2, R15, R20; 8.8). Drafts.
SECTION_WORDS = {"subjective": "Subjective", "objective": "Objective", "assessment": "Assessment", "plan": "Plan"}
REVIEW_TITLE = "Review"
NOTE_HEADING = "Draft note"
NOTE_DRAFT_LINE = "A draft. Nothing is final until you approve it."
MODELS_DIFFERENTIALS = "The model's last differentials. Not part of the note."
NO_DIFFERENTIALS = "The model gave none."
APPROVE = "Approve"
REFUSE = "Refuse"
WARNINGS_COUNT = "{count} warnings"
WARNING_ONE = "1 warning"
COPY_NOTE = "Copy the note"
COPIED = "Copied."
COPY_FAILED = "Could not copy: {reason}"
DRAFT_THE_NOTE = "Draft the note"
DRAFT_AGAIN = "Draft the note again from the corrected transcript"
DRAFT_AGAIN_NEEDS_EDIT = "Nothing has been edited, so there is nothing to draft again."
NO_NOTE_YET = "No note has been drafted for this consultation."
NOTE_GATE_REFUSED = "No note was drafted: {reason}"
NOTE_CALL_FAILED = "The note could not be drafted: {reason}"
NOTE_REFUSED_CITATIONS = (
    "The draft was refused: only {cited} of {total} entries cite a line of the transcript, fewer than half. "
    "The draft was discarded."
)
ENTRY_UNCITED = "cites no line of the transcript"
SHOW_LINE = "Show line {n}"
APPROVED_LINE = "Approved on {date} at {time}. The note is read-only."
REFUSED_LINE = "You refused this draft on {date} at {time}."
NOTE_READ_ONLY = "The note is approved and read-only."
ALREADY_APPROVED = "The note is already approved."
NOTHING_TO_APPROVE = "There is no note to approve."
ALREADY_REFUSED = "This draft is already refused."
EARLIER_DRAFTS = "{count} earlier draft is kept in the record."
EARLIER_DRAFTS_MANY = "{count} earlier drafts are kept in the record."
WARN_LABEL_CHANGED = "Line {n}: the check changed the speaker to {label}."
# The alarm lines in the warnings pane (15.11 ruling 9; R9, R29). Drafts.
ALARMS = "Alarms"
ALARMS_COUNT = "{count} alarms"
ALARM_ONE = "1 alarm"
NO_ALARMS = "No alarm fired."
ALARM_LINE = "At {time}: {state}."
ALARM_STATE_FIRED = "fired, with actions"
ALARM_STATE_NO_ACTION = "fired, with no action"
ALARM_STATE_ACKNOWLEDGED = ", acknowledged"
PLAY_FROM_ALARM = "Play from where it fired"
HOME_REVIEW = "Waiting for review"
REVIEW = "Review"
SAVE_ENTRY = "Save"
SAVE_LINE = "Save"
UNDO_LABEL = "Undo"
SWAP = "Swap doctor and patient"
LABEL_SET_BY_YOU = "set by you"
PICK_LABEL = "Pick Doctor, Patient or Unsure."
ENTRY_EMPTY = "An entry cannot be empty. Edit its words instead."
NOTE_NOT_EDITABLE = "This draft is refused, so its entries cannot be edited. Edit the transcript and draft the note again."
NOT_CHANGED_BY_CHECK = "The check did not change this line's speaker, so there is nothing to undo."
# The referral letters (spec 15.12, rulings 1, 2, 4 and 8; R2, R5, R15, R20). Drafts.
# The placeholder is also the words the letter prompt tells the model to write; the check writes this one.
LETTER_PLACEHOLDER = "[to be completed by the referring doctor]"
# The parts code writes, never the model (ruling 1): the title from the item, the three details the consultation
# ran with (15.11 ruling 2), the one user's title and name.
LETTER_SALUTATION = "Dear Consultant {title},"
LETTER_RE = "Re: {name}, born {born}, {sex}"
LETTER_SIGN_OFF = "Yours faithfully,"
# The Referral letters section of the review page, after Approve (ruling 2; the detail The page).
LETTERS_HEADING = "Referral letters"
SUGGESTIONS_LINE = "These are the model's suggestions, not advice. The note does not state them."
NO_REFERRALS = "The note states no referral, and the model suggests none."
LIST_FAILED = "The referral list could not be made: {reason}"
LIST_AGAIN = "Make the list again"
LIST_STANDS = "The referral list is made."
URGENCY_WORDS = {"urgent": "urgent", "routine": "routine"}
FIELD_TITLE_OF_CONSULTANT = "Consultant's title"
SAVE_TITLE = "Save"
TITLE_EMPTY = "Enter the consultant's title, for example Physician."
TITLE_UNCHANGED = "Nothing changed."
NOTE_LINE = "Line {n} of the note"
DRAFT_THE_LETTER = "Draft the letter"
OPEN_THE_LETTER = "Open the letter"
ITEM_DRAFTED = "Drafted"
ITEM_APPROVED = "Approved"
ITEM_REFUSED = "Refused"
ITEM_REFUSED_BY_CHECK = "Refused by the check"
ITEM_FAILED = "Not drafted: the call failed"
NAME_A_SPECIALTY = "Name a specialty"
FIELD_SPECIALTY = "Specialty"
SPECIALTY_EMPTY = "Enter the specialty."
# The letter's own page (rulings 1 and 4; R2, R15, R20).
LETTER_TITLE = "Referral letter: {specialty}"
LETTER_DRAFT_LINE = "A draft, written from the approved note only. Nothing is final until you approve it."
LETTER_COUNTS = ("{total} sentences; {grounded} grounded in the note; {placeholders} replaced by the placeholder; "
                 "{dropped} expectation sentences dropped; {allergies} allergy sentences dropped; {marked} figures to check.")
# Beside a sentence kept as written whose figure the cited note lines do not give (15.13, ruling 20): page furniture,
# never part of the letter's text, never copied.
LETTER_FIGURE_CHECK = "figure not in the note, please check"
LETTER_REFUSED = ("The letter was refused: only {grounded} of {total} sentences are grounded in the note, fewer than half. "
                  "Draft it again, or write the letter yourself.")
LETTER_CALL_FAILED = "The letter could not be drafted: {reason}"
LETTER_APPROVED_LINE = "Approved on {date} at {time}. The letter is read-only."
LETTER_REFUSED_LINE = "You refused this letter on {date} at {time}."
LETTER_READ_ONLY = "The letter is approved and read-only."
LETTER_ALREADY_APPROVED = "The letter is already approved."
LETTER_NOTHING_TO_APPROVE = "There is no letter to approve."
LETTER_ALREADY_REFUSED = "This letter is already refused."
LETTER_NOT_EDITABLE = "This letter cannot be edited. Draft it again."
PARAGRAPH_EMPTY = "A paragraph cannot be empty."
SAVE_PARAGRAPH = "Save"
DRAFT_LETTER_AGAIN = "Draft the letter again"
APPROVE_LETTER = "Approve"
REFUSE_LETTER = "Refuse"
COPY_LETTER = "Copy the letter"
NO_LETTER_TEXT_YET = "The letter is not approved, so there is no text to copy yet."
EARLIER_LETTERS = "{count} earlier draft of this letter is kept in the record."
EARLIER_LETTERS_MANY = "{count} earlier drafts of this letter are kept in the record."
BACK_TO_REVIEW = "Back to the review page"
LETTER_MODEL_LINE = "Language model: {model} on {engine} {version}."
# The player (spec 8.8; D51). Drafts.
PLAYER = "The recording"
PLAY_FROM_LINE = "Play from here"
PLAY_STRETCH = "Play this stretch"
LOUDNESS = "Loudness along the recording. Press to go there."
AUDIO_GONE = "The recording from {date} is no longer on this computer."
AUDIO_NOT_SUPPORTED = "This browser cannot play the recording."
# The conversion to Opus after Stop (15.11 ruling 7; R30). Drafts.
CONVERSION_FAILED = "The recording was kept as WAV: {reason}"
CONVERSION_NO_CONVERTER = "no converter was found on this computer."
CONVERSION_NO_WAV = "the WAV file was not there."
CONVERSION_NOT_PLAYABLE = "the Opus file could not be played back."
CONVERSION_LENGTH_DIFFERS = "the Opus file plays for {opus} s and the WAV for {wav} s."

# The guideline panel and the Guidelines section of Settings (spec 15.12, rulings 5 and 6; R3, R15; 7.3 rules 1 and 4).
# Drafts for the owner. The panel answers from the loaded documents alone and says when they have nothing.
PANEL_GUIDELINES = "Guidelines"
GUIDELINE_NO_CORPUS = "No guideline document is loaded. Add one in Settings, under Guidelines. Nothing was asked of the model."
GUIDELINE_NOT_INSTALLED = "The guideline search is not installed on this computer. Run openconsult install-guidelines."
GUIDELINE_WORKER_FAILED = "The guideline search is not running: {reason}"
GUIDELINE_WAITING = "Waiting for the first differentials."
GUIDELINE_SEARCHING = "Searching the loaded guidelines for {names}."
GUIDELINE_FOR = "For {names}:"
GUIDELINE_NOT_COVERED = "The loaded guidelines do not cover {names}."
GUIDELINE_MODEL_SAID = "The model's reason: {sentence}"
GUIDELINE_FAILED = "The guideline summary could not be made: {reason}"
GUIDELINE_INDEX_MODEL = ("The loaded passages were built with another embedding model, so they were not searched. "
                         "Remove and add the documents again.")
GUIDELINE_FROM_EARLIER = "From an earlier pass; a new search is running."
GUIDELINE_PROVENANCE = "From {sources} documents, {passages} passages, the latest added on {date}."
GUIDELINE_CITED = "Cited:"
GUIDELINE_SOURCE_LINE = "{title}, {publisher}"
GUIDELINE_PASSAGE_TITLE = "Passage {n}"
SECTION_GUIDELINES = "Guidelines"
GUIDELINES_INTRO = ("The documents the guideline panel answers from. It answers from these alone, never from the model's "
                    "memory, and says when they do not cover a topic. OpenConsult never fetches a document itself.")
NO_GUIDELINES = "No guideline document is loaded."
COL_TITLE = "Title"
COL_PUBLISHER = "Publisher"
COL_PASSAGES = "Passages"
COL_ADDED = "Added"
REMOVE_GUIDELINE = "Remove"
ADD_GUIDELINE = "Add"
FIELD_GUIDELINE_FILE = "A file on this computer: HTML, PDF or plain text"
FIELD_GUIDELINE_TITLE = "Title"
FIELD_GUIDELINE_PUBLISHER = "Publisher"
GUIDELINE_STATEMENT_TICK = "I hold the right to use this document this way."
GUIDELINE_ADDED = "Added: {passages} passages in {seconds} s."
GUIDELINE_REMOVED = "Removed."
GUIDELINE_FILE_MISSING = "Choose a file."
GUIDELINE_TITLE_MISSING = "Enter the title."
GUIDELINE_PUBLISHER_MISSING = "Enter the publisher."
GUIDELINE_TICK_NEEDED = "Tick the statement to add the document."
GUIDELINE_FILE_KIND = "The file must be HTML, PDF or plain text."
GUIDELINE_FILE_TOO_BIG = "The file is over {limit} MB."
GUIDELINE_NO_PASSAGES = "No passage of 40 words or more could be read from this file. Nothing was added."
GUIDELINE_EMBED_FAILED = "The passages could not be embedded: {reason} Nothing was added."
GUIDELINE_ADD_NEEDS_WORKER = "Add is not available: {reason}"
GUIDELINE_WORKER_LINE = "The guideline search: {state}."
WHERE_WORDS = {"card": "the graphics card", "processor": "the processor"}
WORKER_STATES = {
    "ready": "running on {where}, {model}",
    "starting": "starting on {where}",
    "not_installed": "not installed; run openconsult install-guidelines",
    "failed": "not running: {reason}",
    "stopped": "stopped",
}
GUIDELINE_WORKER_NOT_READY = "The guideline search's worker is not ready."
# openconsult install-guidelines (the detail The embedding worker in the app; ruling 9; the plan review of 8b). Drafts.
RERANKER_FETCHING = "Fetching the reranker into {folder}, with no token, at the revision its page names now."
RERANKER_FOUND = "Found the reranker at revision {revision} ({size})."
RERANKER_FETCHED = "Downloaded the reranker at revision {revision} ({size}); the revision and the weights' hash are pinned beside it."
RERANKER_GATED = "The reranker could not be fetched: the hub asks for an account, a token or a licence. Nothing was written."
RERANKER_FETCH_FAILED = "The reranker could not be fetched: {reason}"
GUIDELINES_INSTALLED = "The guideline search is installed. Start OpenConsult, and add documents under Settings, Guidelines."
# The loader command of the bench kit (ruling 18), said in the terminal. Counts only.
LOAD_NEEDS_PUBLISHER = "guideline-load needs --publisher, the publisher's name, which is never written into OpenConsult itself."
LOAD_NEEDS_STATEMENT = "guideline-load needs --statement-accepted: the statement of the Guidelines section, given as the owner's."
LOAD_FOLDER_REFUSED = ("guideline-load loads into a bench folder given by its path. To load into your own data folder, with "
                       "OpenConsult closed, give it by its path and add --into-my-data-folder.")
LOAD_REPO_REFUSED = "guideline-load never loads into the repository: give a data folder by its path."
LOAD_APP_RUNNING = ("OpenConsult looks to be running on this folder: a consultation is live or stopping. Close it first. "
                    "Nothing was loaded.")
LOAD_FILE = "{name}: {kind}, {passages} passages ({outside} outside 40 to 350 words), {seconds} s."
LOAD_FILE_REFUSED = "{name}: not loaded: {reason}"
LOAD_DONE = "Loaded {files} of {given} files: {passages} passages, {outside} outside 40 to 350 words, {seconds} s."

# The first run.
FIRST_RUN_STATEMENT_TITLE = "Before you start"
FIRST_RUN_MACHINE_TITLE = "This machine"
FIRST_RUN_MACHINE_INTRO = "OpenConsult looked at this computer. Here is what it found."
FIRST_RUN_USER_TITLE = "Set yourself up"
FIRST_RUN_USER_INTRO = "OpenConsult uses your title and name wherever it names the doctor."
CONTINUE = "Continue"
SAVE = "Save"
ROW_SYSTEM = "System"
ROW_CARD = "Graphics card"
FIELD_TITLE = "Title (for example Dr). Leave it empty if you have none."
FIELD_NAME = "Name"
FIELD_PASSWORD = "Password (at least {least} characters)"
FIELD_PASSWORD_AGAIN = "Password again"
TICK_TO_CONTINUE = "Tick the box to continue."
NAME_MISSING = "Enter your name."
PASSWORD_SHORT = "The password needs at least {least} characters."
PASSWORDS_DIFFER = "The two passwords do not match."
NOT_THIS_COMPUTER = "Set-up works only from the computer OpenConsult runs on."

# Logging in.
LOGIN_TITLE = "Log in"
FIELD_LOGIN_PASSWORD = "Password"
LOG_IN = "Log in"
WHY = {
    "plain": "Enter your password.",
    "set_up": "Your details are saved. Enter your password to start.",
    "locked": "OpenConsult locked itself after 30 minutes with no use. Enter your password to carry on.",
    "logged_out": "You have logged out.",
    "password_changed": "The password was changed. Enter the new one.",
    "ended": "Your last login has ended. Enter your password.",
}
WRONG_PASSWORD = "Wrong password. Try again in {wait}."
NOT_YET = "Not yet. Try again in {wait}."

# Refusals at the door, as plain text.
WRONG_HOST = "OpenConsult answers only when addressed as this computer: {address}"
WRONG_ORIGIN = "This request did not come from OpenConsult's own pages, so it was not done."


def plain_age(age: int) -> str:
    if age == 0:
        return AGE_BABY
    return AGE_ONE if age == 1 else AGE_LINE.format(age=age)


def plain_date(day) -> str:
    """21 Oct 1990."""
    return f"{day.day} {day:%b %Y}"


def plain_time(seconds: int) -> str:
    """"1 second", "8 seconds", "5 minutes"."""
    if seconds >= 60 and seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return "1 second" if seconds == 1 else f"{seconds} seconds"

# The settings page.
SETTINGS_TITLE = "Settings"
SECTION_MACHINE = "This machine"
SECTION_THRESHOLDS = "Thresholds"
# The retention setting (15.11 ruling 7; 7.3). Drafts.
FIELD_RETENTION_DAYS = ("Days a recording is kept after its consultation, then deleted by the app. "
                        "0 keeps every recording until its consultation is deleted. The default is {default}.")
RETENTION_SAVED = "Saved. The next sweep uses it."
RETENTION_BAD = "Enter a whole number of days, 0 or more."
SECTION_YOU = "You"
SECTION_PASSWORD = "Change password"
FIELD_CURRENT_PASSWORD = "Current password"
FIELD_NEW_PASSWORD = "New password (at least {least} characters)"
FIELD_NEW_PASSWORD_AGAIN = "New password again"
CHANGE_PASSWORD = "Change password"
SAVED = "Saved."
PASSWORD_CHANGED = "The password is changed. Any other login has ended."
WRONG_PASSWORD_NOTHING_CHANGED = "Wrong password. Nothing was changed. Try again in {wait}."
NEW_PASSWORD_SHORT = "The new password needs at least {least} characters."
NEW_PASSWORDS_DIFFER = "The two new passwords do not match."

# Typing as use (15.10 ruling 12): the page asks for the time left; nothing is shown.

# What the model saw (spec 15.12, rulings 11 and 28; 15.8 ruling 1; R2,
# R20). One page per consultation, read only. Drafts for the owner.
MODEL_SAW_LINK = "What the model saw"
MODEL_SAW_TITLE = "What the model saw"
MODEL_SAW_INTRO = ("The record read back: every model call of this consultation in time order, what went into each, "
                   "marked by its source, and what came back word for word. Nothing on this page changes anything.")
MODEL_SAW_NO_CALLS = "No model call is recorded for this consultation."
BACK_TO_CONSULTATION = "The consultation's page"
TIMELINE_HEADING = "Timeline"
TIMELINE_START, TIMELINE_STOP, TIMELINE_FINAL = "Start", "Stop", "final"
TIMELINE_LENGTH = "Start to final: {seconds} s."
TIMELINE_PASS = "pass {n}"
TIMELINE_LONG = "long, {seconds} s"
TIMELINE_TYPICAL = "Typical pass {seconds} s, the median; a pass over twice it is marked long."
TIMELINE_LONG_PASSES = "Marked long: {passes}."
TIMELINE_NO_PASS = "No pass ran."
AVERAGES_HEADING = "Seconds per kind of call"
AVERAGE_LINE = "{kind}: {count} calls, {mean} s on average, {slowest} s at most{failed}"
AVERAGE_FAILED = ", {failed} failed"
FINAL_FIGURES = "The final line: {line}"
FINAL_FIGURES_NONE = "No consultation.final line was written for this consultation."
AFTER_FINAL_HEADING = "After the final transcript"
AFTER_FINAL_LINE = "{kind} at {when}, {lead} after final"
LEAD_WORDS = {"seconds": ("1 second", "{n} seconds"), "minutes": ("1 minute", "{n} minutes"),
              "hours": ("1 hour", "{n} hours"), "days": ("1 day", "{n} days")}
CALLS_HEADING = "The calls, in time order"
CALL_KINDS = {"alarm": "pass {n}, the alarm", "assessment": "pass {n}, the assessment", "label_check": "the check of who spoke",
              "drug_name": "the check of drug names",
              "note": "note draft {n}, {asked}", "referrals": "the referral list", "letter": "letter {n}, {specialty}",
              "guideline": "guideline summary after pass {n}"}
CALL_CHECK_PART = "the check of who spoke, part {n} of {parts}"
CALL_ASKED_BY = {"stop": "at Stop", "draft": "by Draft the note", "again": "by Draft again"}
CALL_UNKNOWN_KIND = "a call of the job {job}"
CALL_LINE = "{time}: {kind}, {seconds} s, {outcome}."
CALL_OUTCOMES = {"ok": "answered", "too_slow": "too slow", "too_long": "the reply was cut at its limit",
                 "unreachable": "the engine could not be reached", "bad_form": "the reply did not fit its form",
                 "did_not_fit": "the input did not fit the context"}
CALL_NO_ROW = "No row of the record refers to this call; it is tied to the consultation by its own row alone."
CALL_SEARCH_MS = "The search before this call took {ms} ms."
CALL_FAILURE = "Failure: {detail}"
CALL_TOKENS = "Tokens: {read} read, {written} written."
KIND_WORDS = {"alarm": "alarm", "assessment": "assessment", "guideline": "guideline summary", "label_check": "check of who spoke",
              "drug_name": "check of drug names",
              "note": "note", "referrals": "referral list", "letter": "letter"}
WENT_IN_HEADING = "What went in, by source"
SOURCE_LABELS = {"patient_line": "The patient line, written by code from the details the consultation ran with",
                 "background": "The background block: the earlier approved notes, as background",
                 "frame": "The fixed words of {file}",
                 "transcript": "The transcript as sent, as the speech choice gave it",
                 "stale": "The earlier pass's differentials, names only",
                 "lines": "The numbered lines as sent, with no speaker",
                 "turns": "The turns as sent, with their speaker words",
                 "note_lines": "The note lines as sent, from the approved note",
                 "specialty": "The specialty, from the referral item",
                 "query": "The query, from the top two differentials",
                 "passages": "The passages sent, from the loaded guidelines, each with its source"}
PASSAGE_SENT = "[{n}] {title}, {publisher}{trail}; similarity {similarity}{cited}"
PASSAGE_TRAIL = ": {trail}"
PASSAGE_CITED = "; cited"
CAME_BACK_HEADING = "What came back, word for word"
# The drug-name call's reply (15.10 rulings 6 and 23). Drafts, for the owner to correct.
DRUG_NAMED_NOT_SHOWN = "The drug the model named is kept in the record and is not shown on this page."
DRUG_REPLY_NOT_SHOWN = "The reply could not be read as its form, so it is not shown on this page. It is kept in the record."
NO_REPLY = "Nothing came back."
PROMPT_LINE_SAME = "Prompt: {name}, sha256 {hash}. The file of that name in the repository today has the same hash."
PROMPT_LINE_DIFFERS = "Prompt: {name}, sha256 {hash}. The file of that name in the repository today differs."
PROMPT_LINE_NONE = "Prompt: sha256 {hash}. No prompt file for this job is in the repository today."
NOT_TAKEN_APART = "Not taken apart: {reason} What was sent is shown whole."
NOT_TAKEN_APART_REASONS = {"not_json": "the stored request is not JSON.",
                           "no_user_text": "no user text was found in the stored request.",
                           "no_patient_line": "the first paragraph is not the patient line the consultation's details give.",
                           "frame_not_found": "the frame's fixed words were not found.",
                           "rebuild_differs": "the parts read back do not give the request byte for byte.",
                           "unknown_job": "the view does not know this job."}

# The log page.
LOG_TITLE = "Log"
COL_WHEN = "When"
COL_WHAT = "What"
COL_DETAILS = "Details"
LOG_EMPTY = "Nothing yet."
EVENTS = {
    "statement.accepted": "Statement accepted",
    "user.set_up": "User set up",
    "login": "Logged in",
    "login.wrong_password": "Wrong password",
    "logout": "Logged out",
    "lock": "Locked after 30 minutes with no use",
    "title.changed": "Title changed",
    "name.changed": "Name changed",
    "password.changed": "Password changed",
    "password.reset": "Password reset from the command",
    "decision.language_model": "Language model chosen at start",
    "decision.guideline_search": "Guideline search placed at start",
    "decision.whisperx_choice": "WhisperX choice judged at start",
    "decision.converter": "Recording converter found at start",
    "setting.changed": "Setting changed",
    "audio.deleted": "Recordings deleted by the retention sweep",
    "recording.converted": "Recording converted to Opus",
    "recording.conversion_failed": "Recording kept as WAV: conversion failed",
    "recording.orphan": "A recording file with no consultation was found",
    "patient.saved": "Patient saved",
    "patient.changed": "Patient's details corrected",
    "patient.deleted": "Patient deleted",
    "consultation.deleted": "Consultation deleted: the recording, the transcript and the note",
    "consultation.started": "Consultation started: the right patient and an acted consultation confirmed",
    "consultation.stopped": "Consultation stopped",
    "speakers.answered": "Which speaker was you: answered",
    "consultation.final": "Consultation final",
    "alarm.acknowledged": "Alarm seen",
    "note.drafted": "Note drafted",
    "note.refused_by_check": "Note refused by the citation check: fewer than half the entries cite a line",
    "note.failed": "Note could not be drafted",
    "note.approved": "Note approved",
    "note.refused": "Note refused by the doctor",
    "entry.edited": "Note entry edited by the doctor",
    "transcript.edited": "Transcript words edited by the doctor",
    "label.set": "Speaker label set by the doctor",
    "label.undone": "The check's change of a speaker label undone by the doctor",
    "drug_names.checked": "The drug names checked at Stop",
    "speakers.check_asked": "The check of who spoke asked for",
    "speakers.check_ended": "The check of who spoke ended",
    "speakers.check_undone_all": "Every change of the check undone by the doctor",
    "labels.swapped": "Doctor and patient swapped on every line",
    "referrals.listed": "Referral list made from the approved note",
    "referrals.failed": "Referral list could not be made",
    "referral.title_changed": "Consultant's title changed on a referral item",
    "referral.named": "Referral item named by the doctor",
    "letter.drafted": "Referral letter drafted",
    "letter.refused_by_check": "Referral letter refused by the check: fewer than half the sentences grounded",
    "letter.failed": "Referral letter could not be drafted",
    "letter.edited": "Referral letter paragraph edited by the doctor",
    "letter.approved": "Referral letter approved",
    "letter.refused": "Referral letter refused by the doctor",
    "guideline.added": "Guideline document added",
    "guideline.removed": "Guideline document removed",
    "guideline.summary": "Guideline summary made from the loaded documents",
    "guideline.not_covered": "Guideline summary refused: the loaded documents do not cover the differentials",
    "guideline.failed": "Guideline summary could not be made",
}

# The command. Plain ASCII, for every terminal.
RUNNING = "OpenConsult is running at {address}"
# The owner's wording (spec 15.8, ruling 12), said when the browser will open by itself.
BROWSER_WILL_OPEN = (
    "Your browser will open by itself. If it does not, open that address in a browser "
    "on this computer. Press Ctrl+C to stop."
)
# Said for a start with --no-browser.
OPEN_IT = "Open that address in a browser on this computer. Press Ctrl+C to stop."
BROWSER_NOT_OPENED = "The browser could not be opened by itself. Open the address above."
DATA_FOLDER = "Data folder: {folder}"
PORT_TAKEN = (
    "Port {port} is already in use on this computer, so OpenConsult did not start. "
    "Stop the other program, or start OpenConsult with --port and another number."
)
NEWER_DATABASE = "The data folder was made by a newer OpenConsult, so this one cannot open it."
ASK_NEW_PASSWORD = "New password: "
ASK_NEW_PASSWORD_AGAIN = "New password again: "
RESET_DONE = "The password is changed. Any open login has ended."
RESET_SHORT = "The password needs at least {least} characters. Nothing was changed."
RESET_DIFFER = "The two passwords do not match. Nothing was changed."
RESET_NO_USER = "No user is set up yet. Start OpenConsult and set one up first."

# The speech worker (spec 15.9). The reasons a call to the speech door
# gives back. Drafts for the owner.
WORKER_NOT_STARTED = "The speech worker could not be started: {reason}"
WORKER_REFUSED = "The speech worker could not load its models: {message}"
WORKER_SAID_NOTHING = "it gave no reason"
WORKER_DIED = "The speech worker stopped with exit code {code}."
WORKER_DIED_SAYING = "The speech worker stopped with exit code {code}. Its last words: {last}"
WORKER_NO_ANSWER = "The speech worker did not answer within {seconds} seconds."
WORKER_NOT_READY = "The speech worker is not ready."
# The speech door and the command that installs a speech choice. Drafts.
CHOICE_TITLE = "WhisperX with pyannote"
SPEECH_NEEDS_INSTALL = "The speech choice is not installed. Run openconsult install-speech first."
DOOR_NO_SESSION = "No session is open."
DOOR_SESSION_OPEN = "A session is already open."
DOOR_BAD_SPEAKERS = "The number of speakers must be 1 or more, not {speakers}."
DOOR_BAD_REPLY = "The speech worker's answer could not be read: {reason}"
SPEECH_BUILDING = (
    "Building the speech environment for WhisperX with pyannote in {folder}. "
    "This downloads about 7 GB the first time."
)
SPEECH_BUILDING_NEMOTRON = (
    "Building the speech environment for Nemotron in {folder}. "
    "This downloads about 6 GB the first time, and the two models about 2.7 GB."
)
CLOUD_NEEDS_NO_INSTALL = (
    "{service} needs no install: it runs with the base app alone. "
    "Put the key in the .env file in the data folder and run the self-test."
)
SPEECH_BUILT = "The speech environment is ready."
SPEECH_ALREADY_BUILT = "The speech environment was already complete. Nothing was changed."
SPEECH_BUILD_FAILED = "The speech environment could not be built: {reason}"
UV_MISSING = "The program uv was not found on this computer. Install it, then run this command again."
MODEL_FOUND = "Found {model} ({size})."
MODEL_FETCHED = "Downloaded {model} ({size})."
MODEL_FAILED = "The model {model} could not be fetched: {reason}"
MODEL_MISSING = "The model {model} is not on this computer. Run openconsult install-speech."
MODELS_READY = "Every model is on this computer."
RATE_NOT_SUPPORTED = "This speech choice takes sound at 16,000 or 48,000 samples a second, not {rate}."
# The self-test (D46). Drafts.
SELF_TEST_RUNNING = (
    "Running the self-test: 11 seconds of a public speech of 1961, fed as the live page "
    "will send it, then the transcript at Stop."
)
SELF_TEST_RUNNING_CLOUD = (
    "Running the self-test on {service}: 11 seconds of a public speech of 1961 leave this computer "
    "for the service's EU address, fed as the live page will send it, then Stop."
)
SELF_TEST_SAME_LINES = "Live and at Stop are the same lines for this choice."
SELF_TEST_RESULT_PASSED = "The self-test passed. Heard live: {live}. At Stop: {stop}."
SELF_TEST_RESULT_FAILED = "The self-test failed: {reason} Heard live: {live}. At Stop: {stop}."
SELF_TEST_TOO_FEW_LIVE = "Only {heard} of the {total} expected words were heard live, in order; {needed} are needed."
SELF_TEST_TOO_FEW_STOP = "Only {heard} of the {total} expected words were heard at Stop, in order; {needed} are needed."
SELF_TEST_CLIP_CHANGED = (
    "The test clip is not the one that came with OpenConsult (its checksum differs), "
    "so the self-test did not run."
)
# The cloud choices (spec 7.2; 15.9, the details of 5b). Drafts.
NO_KEY = (
    "No key for {service} was found. Put {name} in the .env file in the data folder, "
    "or in the environment, and try again."
)
KEY_REFUSED = "{service} refused the key. Check the key and try again."
NO_CREDIT = "{service} refused to start: the account has no credit left."
NO_INTERNET = "{service} could not be reached. Check the internet connection and try again."
SERVICE_DOWN = "{service} is not answering. Try again later."
LIMIT_REACHED = "{service} refused to start: a limit on the account was reached."
ADDRESS_REFUSED = "{detail} is not the EU address of {service}, so nothing was sent to it."
CONNECTION_LOST = "The connection to {service} was lost. Nothing more was sent, and the session has ended."
DOOR_SPEAKERS_NEEDED = "This speech choice must be told the number of speakers when the session opens."
# This machine: one line for each choice (15.9). Drafts.
ROW_NEMOTRON = "Nemotron"
ROW_SPEECHMATICS = "Speechmatics"
ROW_ASSEMBLYAI = "AssemblyAI"
NEMOTRON_NOT_INSTALLED = "Not installed."
NEMOTRON_NOT_RUN = "Installed. The self-test has not been run yet."
NEMOTRON_PASSED = "Installed. The self-test passed on {date} at {time}."
NEMOTRON_FAILED = "Installed. The self-test failed on {date} at {time}: {reason}"
CLOUD_NO_KEY = "No key yet."
CLOUD_NOT_RUN = "A key is present. The self-test has not been run yet."
CLOUD_PASSED = "The self-test passed on {date} at {time}."
CLOUD_FAILED = "The self-test failed on {date} at {time}: {reason}"
# The two WhisperX rows, on a suitable card only (15.9). Drafts.
ROW_SPEECH = "Speech"
ROW_SELF_TEST = "Self-test"
SPEECH_INSTALLED = "WhisperX with pyannote is installed."
SPEECH_NOT_INSTALLED = "WhisperX with pyannote is not installed."
SELF_TEST_NOT_RUN = "Not yet run."
SELF_TEST_NOT_POSSIBLE = "Not run, because the speech choice is not installed."
SELF_TEST_PASSED = "Passed on {date} at {time}."
SELF_TEST_FAILED = "Failed on {date} at {time}: {reason}"

# The speech bench (spec 15.9, the details of 5c). Said in the terminal
# by openconsult-bench. Drafts for the owner.
BENCH_RECORDING_CHANGED = ("The recording {name} is not the file the list describes: {reason}. "
                           "Nothing was fed.")
BENCH_NOT_LISTED = "{name} is not in the banked list, so the bench will not touch it."
BENCH_BAD_LIST = "The banked list cannot be used: {reason}"
BENCH_BAD_WAV = "The recording {name} could not be read as WAV, 16-bit, one channel at the listed rate: {reason}"
BENCH_NO_CLOUD_CONSENT = ("The consent for {name} does not cover {service}, so its sound was not sent. "
                          "No connection was opened.")
BENCH_RESULT_EXISTS = "A result for {arm} on {name} exists and is never written over. Skipped."
BENCH_FOLDER_REFUSED = "Results may not go under {place}."
BENCH_FEEDING = "Feeding {name} ({seconds} s at {rate} samples a second) to {arm}, as if live."
BENCH_RESULT_WRITTEN = "Written: {path}"
BENCH_FAILED = "{arm} on {name} failed at {at}: {detail} The failure is kept."
BENCH_SCORED = "Scored {results} results of {arms} arms. Tables written to {folder}."
BENCH_ARM_NEEDS_ENVIRONMENT = ("The arm {arm} runs in the environment of {choice}, which is not installed in the "
                               "data folder. Run openconsult install-speech --choice {choice} first.")
BENCH_WRITE_EXISTS = "{path} exists and is never written over."
BENCH_MODEL_FETCH = "Fetching the models of the arm {arm} with the environment of {choice}."
# The two arms that belong to the bench (ruling 15), as their results name them.
ARM_TIED_PAIR = "Nemotron, the tied pair (bench only)"
ARM_V1_LINE = "WhisperX with v1's line (bench only)"

# The voice method of the speech bench (spec 15.9, the details of part two of 5c). Drafts for the owner.
BENCH_VOICE_LEARNING = "Learning the doctor's voice from {name}."
BENCH_VOICE_SCORING = "Marking each line of {arm} on {name} as the doctor's voice or not, from the sound."
BENCH_VOICE_NOT_RUN = "The voice method was not run for {name}: the list names no recording of the doctor's voice alone."
BENCH_VOICE_NEEDS_VOICE_ONLY = ("{name} names {voice} as the doctor's voice, but that recording is not marked as the voice alone, "
                                "so nothing was run.")
BENCH_VOICE_ONLY_REFUSED = "{name} holds the doctor's voice alone and is never fed as a consultation."
BENCH_VOICE_DONE = "The voice method ran on {run} pages, was not run on {not_run}, failed on {failed}; {kept} results were already there."

# The UK drug list of the speech bench. Drafts for the owner.
BENCH_DRUGS_FETCHING = "Fetching the month {month} from {url}."
BENCH_DRUGS_FETCHED = "Fetched {size}, sha256 {sha256}, to {path}."
BENCH_DRUGS_BAD_FILE = "The file could not be used: {reason}"
BENCH_DRUGS_MADE = "The drug list holds {names} names from {rows} rows of {month}. Written: {path}"

# The calls of the speech bench to the language model. Drafts for the owner.
BENCH_BAD_JOB = "{job} is not a job of the bench; the jobs are {jobs}."
BENCH_ENGINE_ABSENT = "The language model {model} cannot be reached at {address}, so no call was made."
BENCH_ENGINE_FOUND = "The language model: version {version}, {model}, digest {digest}."
BENCH_CALL_ASKING = "Asking the model: {job} on {arm}, {name}{round}."
BENCH_CALL_FAILED = "The call for {job} on {arm}, {name} failed: {failure}: {detail} The failure is kept."
BENCH_CALL_REFUSED = "The reply for {job} on {arm}, {name} was refused: {reason} No label changes."
BENCH_CALLS_DONE = "Made {made} calls, {failed} failed; {kept} results were already there."
BENCH_NOT_THE_PAGE = "The stored call for {call} was not made from the page as it is stored, so nothing was counted."
BENCH_NO_KEY_FOUND = "No key named {name} is in the environment or in {path}, so nothing was sent."
BENCH_ADDRESS_REFUSED = "Nothing was sent: {reason}."
BENCH_CALLS_STOPPED = "STOP: {reason}. The result for {job} on {arm}, {name} is written apart, to run again."
BENCH_STOP_MARKS_RULE = "Every reply is judged by the rule of {rule}."
BENCH_NEEDS_FILE = "The results of part two are here, so {option} is needed: {what}."
BENCH_SCORED_TWO = "Scored part two as well: {pages} pages, {calls} calls, {voice} voice results."

# The voice cut from the recordings (15.9, ruling 33). Drafts.
BENCH_VOICE_CUT = "The voice {voice} was cut from {name}: {seconds} s in {stretches} stretches."
BENCH_VOICE_OWN = "The voice {voice} was cut from {name} itself, and is never used on its own recording."
# The pass at Stop of a cloud service, the bench's alone (15.9, ruling 28; the details of 5e). Drafts.
BENCH_UPLOAD_SENDING = "Sending {name} whole to {service}, at {address}."
BENCH_UPLOAD_RESULT = "{service} gave its result after {seconds} s; it counted {counted} s of sound."
BENCH_UPLOAD_GONE = "Deleted at {service}, and asked again: {answer}."
BENCH_UPLOAD_NOT_PROVEN = ("STOP: the upload of {name} to {service} could not be proven deleted: {answer}. "
                           "Nothing more is sent.")
BENCH_NO_WHOLE_CONSENT = "The recording {name} may not be sent whole to {service}: its consent does not say so."
BENCH_UPLOAD_NO_KEY = "{service} needs --key-folder, the folder whose .env holds {name}."
BENCH_UPLOAD_GATE_PASSED = "The gate call to {service} passed: the clip came back, was deleted, and is gone."
BENCH_UPLOAD_GATE_FAILED = "The gate call to {service} did not pass: {heard} of the clip's {of} words came back. It was deleted."
BENCH_UPLOAD_HELD = "{service}: {jobs} jobs asked for again, {held} still held. Written: {path}"
ARM_SPEECHMATICS_UPLOAD = "Speechmatics, whole recording"
ARM_ASSEMBLYAI_UPLOAD = "AssemblyAI, whole recording"

# The test of 5d: the three models together on one card (spec 15.9, the
# details of 5d). Said in the terminal by openconsult-bench. Drafts for the owner.
EMBED_BUILDING = "Building the environment of EmbeddingGemma 2 in {folder}. This takes a few minutes."
EMBED_BUILT = "The environment of EmbeddingGemma 2 is ready."
EMBED_ALREADY_BUILT = "The environment of EmbeddingGemma 2 was already complete. Nothing was changed."
EMBED_BUILD_FAILED = "The environment of EmbeddingGemma 2 could not be built: {reason}"
EMBED_FETCHING = "Fetching EmbeddingGemma 2 at its {revision} revision into {folder}, with no token."
EMBED_FOUND = "Found EmbeddingGemma 2 at revision {revision} ({size})."
EMBED_FETCHED = "Downloaded EmbeddingGemma 2 at revision {revision} ({size})."
EMBED_GATED = "EmbeddingGemma 2 could not be fetched: the hub asks for an account, a token or a licence. Nothing was written."
EMBED_FETCH_FAILED = "EmbeddingGemma 2 could not be fetched: {reason}"
EMBED_NOT_INSTALLED = "The embedding worker is not installed in {folder}. Run openconsult install-guidelines first."
EMBED_WORKER_FAILED = "The embedding worker could not start: {reason}"
EMBED_WORKER_SAYS = "The embedding worker says: device {device}, number format {dtype}, {model} at {revision}."
EMBED_PLACED = "The embedding model {embedding} was asked for on the {where}; it says: {info}"
EMBED_SEARCH = "The embedding model {embedding} on the {where}: search {n} of {names} names took {seconds} s."
EMBED_LATE = "Search {n} started {late} s late: the search before it had not ended."
EMBED_EMPTY = "Search {n}: the list has no name, so nothing was sent."
EMBED_FAILED = "Search {n} failed: {reason} The failure is kept."
EMBED_INDEX = ("The side reading: {pieces} pieces of about {words} words, from {files} public files, "
               "sent {batch} at a time, took {seconds} s.")
EMBED_WATCHING = "Watching: Ollama's list, {engine}'s health and the card's programs every {every} s until {file} appears."
EMBED_WATCHED = "Watched {readings} readings. Written: {path}"
EMBED_JUDGED = "Judged {setups} setups, {base} base lines of the language model and {wayround} ways round. Tables written to {folder}."
EMBED_JUDGE_NEEDS_WRITE = "shared-judge needs --write, or --ask-wayround."
EMBED_NO_FEED = "The feed never began: {file} did not appear. No search was made."
