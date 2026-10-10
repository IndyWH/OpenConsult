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
# The two local-model lines, shown only on a machine with a suitable card
# (spec 15.7; elsewhere Ollama is not even asked). Drafts for the owner.
ROW_OLLAMA = "Ollama"
ROW_MODEL = "Local model"
OLLAMA_RUNNING = "Running, version {version}"
OLLAMA_NOT_RUNNING = "Not running"
MODEL_PRESENT = "Gemma 4 QAT is present."
MODEL_ABSENT = "Gemma 4 QAT is not present."
MODEL_UNKNOWN = "Not known, because Ollama is not running."
CARD_NONE = "None found"
CARD_UNREADABLE = "Could not be read"

# The header and the home page.
APP_NAME = "OpenConsult"
NAV_HOME = "Home"
NAV_SETTINGS = "Settings"
NAV_LOG = "Log"
NAV_LOGOUT = "Log out"
HOME_TITLE = "Home"
HOME_SO_FAR = (
    "So far this version starts, sets up its one user, describes the machine it runs on, "
    "can reach the local language model, and can turn speech into text in four ways: "
    "WhisperX with pyannote, Nemotron, Speechmatics and AssemblyAI. "
    "It cannot run a consultation yet."
)

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


def plain_time(seconds: int) -> str:
    """"1 second", "8 seconds", "5 minutes"."""
    if seconds >= 60 and seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return "1 second" if seconds == 1 else f"{seconds} seconds"

# The settings page.
SETTINGS_TITLE = "Settings"
SECTION_MACHINE = "This machine"
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
SPEECH_BUILT = "The speech environment is ready."
SPEECH_ALREADY_BUILT = "The speech environment was already complete. Nothing was changed."
SPEECH_BUILD_FAILED = "The speech environment could not be built: {reason}"
UV_MISSING = "The program uv was not found on this computer. Install it, then run this command again."
MODEL_FOUND = "Found {model} ({size})."
MODEL_FETCHED = "Downloaded {model} ({size})."
MODEL_FAILED = "The model {model} could not be fetched: {reason}"
MODEL_MISSING = "The model {model} is not on this computer. Run openconsult install-speech."
MODELS_READY = "Every model is on this computer."
RATE_NOT_SUPPORTED = "This speech choice takes sound at 16,000 samples a second, not {rate}."
# The self-test (D46). Drafts.
SELF_TEST_RUNNING = (
    "Running the self-test: 11 seconds of a public speech of 1961, fed as the live page "
    "will send it, then the transcript at Stop."
)
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
# The two WhisperX rows, on a suitable card only (15.9). Drafts.
ROW_SPEECH = "Speech"
ROW_SELF_TEST = "Self-test"
SPEECH_INSTALLED = "WhisperX with pyannote is installed."
SPEECH_NOT_INSTALLED = "WhisperX with pyannote is not installed."
SELF_TEST_NOT_RUN = "Not yet run."
SELF_TEST_NOT_POSSIBLE = "Not run, because the speech choice is not installed."
SELF_TEST_PASSED = "Passed on {date} at {time}."
SELF_TEST_FAILED = "Failed on {date} at {time}: {reason}"
