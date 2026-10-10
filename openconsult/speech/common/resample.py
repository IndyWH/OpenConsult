"""The conversion of the sound's rate inside a local worker (spec 15.9,
the details of 5c; carried from 5a). The new recordings are 48,000
samples a second and the local models take 16,000. The filter is the
one scipy's own resample_poly designs for a change of rate by three:
firwin, 61 taps, the cut-off at one third of the input's Nyquist (8 kHz),
a Kaiser window at beta 5.0 (about 54 dB in the stopband), applied with
lfilter so its state carries from one piece to the next and the pieces
join with no seam; then every third sample is kept, the phase carried
too. The group delay is 30 input samples (0.625 ms). Any rate other than
16,000 or 48,000 is refused by the worker. This file is imported by path
by the workers; it needs numpy and scipy, which both speech environments
hold, and the app never imports it."""

from __future__ import annotations

TARGET_RATE = 16000
RATES = (16000, 48000)
TAPS = 61                 # scipy's own: 2 * 10 * max(up, down) + 1 for down 3
KAISER_BETA = 5.0         # scipy's own window for resample_poly


class RateNotSupported(Exception):
    pass


class Resampler:
    """One session's converter: bytes of 16-bit PCM at rate_in go in,
    int16 samples at TARGET_RATE come out, piece after piece."""

    def __init__(self, rate_in: int, rate_out: int = TARGET_RATE):
        import numpy as np
        self._np = np
        if int(rate_in) not in RATES:
            raise RateNotSupported(rate_in)
        self.rate_in, self.rate_out = int(rate_in), int(rate_out)
        self.factor = self.rate_in // self.rate_out
        if self.factor > 1:
            from scipy.signal import firwin, lfilter, lfilter_zi
            self._lfilter = lfilter
            self._taps = firwin(TAPS, 1.0 / self.factor, window=("kaiser", KAISER_BETA))
            self._state = lfilter_zi(self._taps, 1.0) * 0.0
            self._phase = 0

    def convert(self, pcm: bytes):
        """int16 samples at the target rate for one piece of PCM bytes."""
        np = self._np
        samples = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2")
        if self.factor == 1:
            return samples.copy()
        filtered, self._state = self._lfilter(self._taps, 1.0, samples.astype(np.float64), zi=self._state)
        kept = filtered[self._phase::self.factor]
        self._phase = (self._phase - len(samples)) % self.factor
        return np.clip(np.rint(kept), -32768, 32767).astype("<i2")
