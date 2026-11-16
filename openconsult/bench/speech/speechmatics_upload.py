"""Speechmatics, a whole recording sent once, as the bench reaches it
(spec 15.9, rulings 9 and 28; the details of 5e). Since run 9b the
module is the app's own (openconsult/speech/speechmatics_upload.py),
read here by the bench's commands and tests. Nothing is written twice."""

from openconsult.speech.speechmatics_upload import *  # noqa: F401,F403
from openconsult.speech.speechmatics_upload import (ARM, BASE, DIARIZATION, DOMAIN, EU_HOST, KEY_NAME, LANGUAGE, MODEL,  # noqa: F401
                                                    NAME, NO_SPEAKER, TITLE)
