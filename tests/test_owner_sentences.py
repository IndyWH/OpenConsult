"""The owner's sentences of run 9c (spec 15.13, rulings 52 and 53; rule 4 of
the run's prompt). On 17 Nov 2026 he took eight drafts of run 9b that say
where sound, words or a key go as his own, letter for letter, and gave
the line of the cloud mark on the review page. Each stands here as the
stage prompt gives it and is proven against the file of words: none is
changed without his word."""

from __future__ import annotations

import pytest

from openconsult import words

OWNERS = [
    ("ruling 53, one: the live page, when the speech stops", lambda: words.ALARM_NOT_LISTENING,
     "The emergency alarm has stopped listening."),
    ("ruling 53, two: the label of the tick under Transcription", lambda: words.BETTER_ACCURACY,
     "Better accuracy: after Stop, send the whole recording to Speechmatics once, for the final transcript."),
    ("ruling 53, three: a press at Stop after a lost connection", lambda: words.SEND_WHOLE,
     "Send the recording once for the whole transcript."),
    ("ruling 53, three: the other press", lambda: words.GO_ON_WITHOUT, "Go on without it."),
    ("ruling 53, four: above the note, the delete confirmed", lambda: words.UPLOAD_MADE,
     "The final transcript was made by Speechmatics from the whole recording. It was deleted there, and Speechmatics confirmed "
     "that it is gone."),
    ("ruling 53, four: the first of its two sentences alone, when the delete is not proven", lambda: words.UPLOAD_MADE_ONLY,
     "The final transcript was made by Speechmatics from the whole recording."),
    ("ruling 53, five: after Stop, while the recording is away", lambda: words.STAGE_LINES["upload"],
     "Sending the recording to Speechmatics and waiting for the transcript: {seconds} s."),
    ("ruling 53, six: the microphone test", lambda: words.MIC_NOT_SENT, "This sound is not stored and is not sent anywhere."),
    ("ruling 53, seven: Connections, a key in the secure store", lambda: words.KEY_WHERE["store"],
     "The key is in this computer's secure store."),
    ("ruling 53, seven: Connections, a key from the environment", lambda: words.KEY_WHERE["environment"],
     "The key comes from the environment the app was started in."),
    ("ruling 53, seven: Connections, a key from the file", lambda: words.KEY_WHERE["file"],
     "The key comes from the file .env in the data folder."),
    ("ruling 53, seven: a connect screen, after a passed test", lambda: words.KEY_SAVED,
     "Connected. The key is kept in this computer's secure store."),
    ("ruling 53, eight: Connections, after Remove", lambda: words.KEY_REMOVED,
     "Removed. The key is no longer in this computer's secure store."),
    ("ruling 52: the mark's line on the review page", lambda: words.CLOUD_MARK_RECORDING_SENT,
     "After Stop the recording went to Speechmatics."),
]


@pytest.mark.parametrize("place, held, given", OWNERS, ids=[place for place, _, _ in OWNERS])
def test_15_13_rulings_52_and_53_each_sentence_of_the_owner_stands_in_the_file_of_words_letter_for_letter(place, held, given):
    assert held() == given, place


def test_15_13_ruling_53_the_line_above_the_note_with_the_delete_not_proven_is_the_first_sentence_of_the_other():
    assert words.UPLOAD_MADE.startswith(words.UPLOAD_MADE_ONLY + " ") and words.UPLOAD_MADE.count(". ") == 1
