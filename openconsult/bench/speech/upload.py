"""The pass at Stop of a cloud speech service, as the bench reaches it
(spec 15.9, rulings 9, 28 and 31; the details of 5e). Since run 9b the
upload itself is the app's own (openconsult/speech/upload.py; 15.13, the
details of the run: the recording sent after Stop), read here by the
bench's commands, by the second service's module, which is the bench's
alone, and by the bench's tests. Nothing of it is written twice."""

from openconsult.speech.upload import *  # noqa: F401,F403
from openconsult.speech.upload import _NoRedirect, _delete_and_prove, _urllib_send  # noqa: F401
