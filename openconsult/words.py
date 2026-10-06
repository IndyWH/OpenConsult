"""Every sentence the app shows to the user, in one place, so the owner
can correct the wording here and nowhere else. Tests take a sentence
from this file; none holds its own copy (plan review, change 1).

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
# (plan review of stage 3, change 2). Drafts for the owner.
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
    "and can reach the local language model. It cannot run a consultation yet."
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
