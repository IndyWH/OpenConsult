"""Barge-in calibration report — Phase 7a session 3 (PHASE_7A_SPEC.md D5).

REPORT ONLY. This script changes nothing: no thresholds are set, no flag
is flipped, no row is written. It reads the `speech.sound_check` audit
rows — where every loopback measurement is stored flat and raw precisely
for this consumer (spec Part 10.5) — and reports both sides of the D5
target with the measured numbers, per output device. Readings taken on
different output devices are NOT comparable (a level without its path is
not a measurement — the 27/15/4 dB lesson), which is why every grouping
here is by device.

The D5 target, verbatim from the spec (a two-sided pair, so the detector
cannot be "improved" by making it deaf):

    False stops (detector fires, nobody spoke)   <= 1% of utterances
    True interruptions caught                    >= 90%, within 300 ms

What this script can honestly do with sound-check rows is state whether
the recorded loopback geometry PREDICTS each side met at the current
settings, and with how much headroom. The behavioural numbers themselves
come from scripted runs in the room once the owner enables the detector
for a test session; when `speech.barge_in` rows exist, their observed
cut latencies are folded into the report. Where the data is too thin to
say anything, the report says that, plainly, instead of extrapolating.

It also checks whether the recorded readings support recommendations for
the sound check's good/faint ratios — currently uncalibrated guesses,
env-tunable (`SOUND_CHECK_GOOD_RATIO`, `SOUND_CHECK_FAINT_RATIO`).
Recommending is this script's job; SETTING them is the owner's.

Safety: reads inside a READ ONLY transaction, so the no-writes guarantee
is enforced by Postgres rather than by discipline (the
calibrate_transcript_quality convention).

Usage:
    uv run python scripts/calibrate_barge_in.py
    uv run python scripts/calibrate_barge_in.py --since 2026-07-30
    uv run python scripts/calibrate_barge_in.py --since 2026-08-18T14:30
    uv run python scripts/calibrate_barge_in.py --since 2026-08-18T14:30:00

`--since` limits every per-device analysis to readings from that moment
onward, so the CURRENT room configuration can be evaluated without the
device's whole history polluting the spread — the intended cut after any
change of volume, position, or capture-stream constraints (readings
across such a change are not comparable, the same lesson as the device
grouping). It takes a date, `YYYY-MM-DD` — from that day onward, exactly
as before — or a timestamp, `YYYY-MM-DDTHH:MM` or `YYYY-MM-DDTHH:MM:SS`,
in LOCAL time: calibration sessions iterate within a day (a volume
change, a microphone moved), and readings across such a change must not
pool, so a batch needs cutting at the minute it began, not at midnight.
When the flag excludes readings the report says how many and from when,
so a narrowed window is always visible in the output rather than silent.
Default remains all readings.
"""

from __future__ import annotations

import argparse
import datetime
import math
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from app import schema, speech  # noqa: E402

load_dotenv()

# The D5 target (spec Part 9), restated in code so the report and the
# spec cannot drift apart silently.
D5_FALSE_STOP_MAX = 0.01
D5_CATCH_MIN = 0.90
D5_CATCH_WITHIN_MS = 300

# The client samples the detector every 50 ms (live.html); a cut can
# therefore fire no earlier than the sustain requirement plus one tick.
CLIENT_TICK_MS = 50

# Decision constants for the PREDICTED verdicts. Stated here rather than
# buried: fewer than MIN_READINGS on one device is not a calibration;
# loopback readings spread wider than MAX_SPREAD suggest the volume or
# the path changed between readings; the absolute floor should clear the
# measured noise floor by NOISE_CLEARANCE (~6 dB) before quiet-room noise
# stops predicting false stops; and interrupting speech should clear the
# worst-case threshold by SPEECH_HEADROOM before a catch is predicted.
MIN_READINGS = 5
MAX_SPREAD = 3.0
NOISE_CLEARANCE = 2.0
SPEECH_HEADROOM = 2.0

# The quietest REAL speech measured on this system's own recordings:
# consultation 445's audio read 0.056 RMS at 4:44, 0.068 at 8:04, 0.089
# at 7:11 and 0.153 in loud passages (HANDOVER, the 445 section). The
# conservative end is the reference an interruption must beat.
REFERENCE_SPEECH_RMS = 0.056

NO_DEVICE = "(no output device recorded — predates the device-label fix; not comparable)"
NO_CHAIN = ("(no capture-chain record — predates the chain field, "
            "2026-07-30; not comparable)")
NO_RESIDUAL = "no residual — predates the dual measurement"


def chain_label(row: dict) -> str | None:
    """Compact label for the capture chain a reading was made through, or
    None when the row predates the chain record.

    The device-label lesson, applied to the processing chain: a level
    without the chain that produced it is not a measurement either (the
    2026-07-29 finding — the same room and volume read x13 apart because
    an adaptive canceller sat in the path). Readings are comparable ONLY
    within one device AND one chain, and this report never pools across
    either.
    """
    chain = row.get("chain")
    if not isinstance(chain, dict):
        return None
    def onoff(value: object) -> str:
        return "on" if value else "off"
    return (f"ec={onoff(chain.get('ec'))} ns={onoff(chain.get('ns'))} "
            f"agc={onoff(chain.get('agc'))}")


# --- data -------------------------------------------------------------------

def fetch_rows() -> tuple[list[dict], list[dict]]:
    """(sound-check rows, utterance-end rows), oldest first, READ ONLY."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT a.at, u.username, a.detail FROM audit_event a"
                " LEFT JOIN app_user u ON u.id = a.user_id"
                " WHERE a.action = 'speech.sound_check' ORDER BY a.id")
            checks = [{"at": r[0], "username": r[1], **(r[2] or {})}
                      for r in cur.fetchall()]
            cur.execute(
                "SELECT a.at, a.action, a.detail FROM audit_event a"
                " WHERE a.action IN ('speech.spoken', 'speech.barge_in')"
                " ORDER BY a.id")
            ends = [{"at": r[0], "action": r[1], **(r[2] or {})}
                    for r in cur.fetchall()]
    return checks, ends


def measurement_mode(row: dict) -> str:
    """"dual" when the row carries a detector-stream residual (Part 10
    amendment), else "raw-only". Verdicts come from dual readings ONLY:
    the threshold operates on the detector stream, and a raw-only row
    says nothing about the residual there."""
    residual = row.get("residual")
    if isinstance(residual, dict) and residual.get("peak_rms") is not None:
        return "dual"
    return "raw-only"


def group_readings(
        checks: list[dict]) -> dict[tuple[str, str | None, str], list[dict]]:
    """Readings keyed by (output device, capture chain, measurement mode).

    Two readings land in the same group — and may therefore be averaged,
    spread-checked or recommended from — only when ALL THREE match. A
    None chain (pre-2026-07-30 rows) forms its own group per device and
    is reported as incomparable, exactly as the pre-device-label rows
    are; raw-only rows (no residual — including the five ec-off readings
    of 2026-07-29/30) are likewise never pooled with dual readings.
    """
    groups: dict[tuple[str, str | None, str], list[dict]] = {}
    for row in checks:
        key = (row.get("device_label") or NO_DEVICE, chain_label(row),
               measurement_mode(row))
        groups.setdefault(key, []).append(row)
    return groups


def _reading_date(row: dict) -> datetime.date:
    at = row.get("at")
    if hasattr(at, "date"):
        return at.date()
    return datetime.date.fromisoformat(str(at)[:10])


def _reading_local_time(row: dict) -> datetime.datetime:
    """The reading's moment in LOCAL wall-clock time, naive — what a
    timestamp `--since` is compared against. Database rows carry an aware
    timestamptz and are converted; naive datetimes and ISO strings are
    taken as local already (a date-only string is that day's midnight)."""
    at = row.get("at")
    if isinstance(at, datetime.datetime):
        return at.astimezone().replace(tzinfo=None) if at.tzinfo else at
    text = str(at)
    if len(text) <= 10:
        return datetime.datetime.combine(datetime.date.fromisoformat(text), datetime.time())
    parsed = datetime.datetime.fromisoformat(text)
    return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed


def parse_since(text: str) -> datetime.date | datetime.datetime:
    """The --since value: a date (YYYY-MM-DD) or a local timestamp
    (YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS). Anything else is an
    argparse error, not a guess. A date stays a `date` so the whole-day
    behaviour is exactly what it was; a timestamp is a naive local
    `datetime`, cut at the minute a same-day calibration batch began."""
    if "T" not in text and " " not in text:
        return datetime.date.fromisoformat(text)
    parsed = datetime.datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        raise ValueError("--since is local time; do not give an offset")
    return parsed


def since_label(since: datetime.date | datetime.datetime | None) -> str:
    if isinstance(since, datetime.datetime):
        return since.isoformat(timespec="seconds" if since.second else "minutes")
    return str(since)


def split_since(rows: list[dict],
                since: datetime.date | datetime.datetime | None,
                ) -> tuple[list[dict], list[dict]]:
    """(kept, excluded) by reading moment; since=None keeps everything.

    A date keeps every reading ON that day and later (unchanged since the
    flag was added); a timestamp keeps readings AT that local moment and
    later — the same-day cut a calibration batch needs."""
    if since is None:
        return rows, []
    if isinstance(since, datetime.datetime):
        kept = [r for r in rows if _reading_local_time(r) >= since]
        excluded = [r for r in rows if _reading_local_time(r) < since]
        return kept, excluded
    kept = [r for r in rows if _reading_date(r) >= since]
    excluded = [r for r in rows if _reading_date(r) < since]
    return kept, excluded


def acoustic_readings(rows: list[dict]) -> list[dict]:
    """Readings where sound actually travelled speaker → room → mic.

    Headphone readings (no acoustic path) carry no loopback information;
    so does anything whose peak never cleared the silence floor.
    """
    silent = speech.SOUND_CHECK_SILENT_RMS
    return [r for r in rows
            if r.get("discrepancy") != "no_acoustic_path_headphones_likely"
            and (r.get("peak_rms") or 0.0) >= silent]


# --- the two sides of D5, predicted from the recorded geometry --------------

def _db(ratio: float) -> str:
    return f"{20 * math.log10(ratio):.1f} dB" if ratio > 0 else "-inf dB"


def assess_device(readings: list[dict], *, margin: float, abs_floor: float,
                  min_ms: int) -> dict:
    """Predicted verdict for one group's DUAL (residual-bearing) readings.

    Part 10 amendment: verdicts come from the RESIDUAL — the echo the
    detector stream actually hears — with the raw loopback reported
    alongside as the sanity upper bound, never as the verdict's basis.
    Returns {"side_a": ..., "side_b": ..., "numbers": ...} where each side
    is True (predicted met), False (predicted not met) or None
    (insufficient data), with the reasons spelled out as text.
    """
    numbers: dict = {"n": len(readings)}
    if len(readings) < MIN_READINGS:
        why = (f"only {len(readings)} usable residual-bearing reading(s) — "
               f"{MIN_READINGS} needed before this device is calibrated")
        return {"side_a": None, "side_b": None,
                "side_a_why": [why], "side_b_why": [why], "numbers": numbers}

    residuals = [float(r["residual"]["peak_rms"]) for r in readings]
    raws = [float(r["peak_rms"]) for r in readings]
    floors = [max(float(r.get("noise_floor_rms") or 0.0),
                  speech.SOUND_CHECK_SILENT_RMS) for r in readings]
    numbers.update(
        resid_min=min(residuals), resid_median=statistics.median(residuals),
        resid_max=max(residuals),
        raw_min=min(raws), raw_median=statistics.median(raws),
        raw_max=max(raws),
        floor_max=max(floors), floor_median=statistics.median(floors),
        spread=max(residuals) / max(min(residuals), 1e-9))
    # The threshold the client will actually hold during the loudest part
    # of playback, and the floor it holds during quiet parts — plus the
    # raw-derived figure it replaced, kept visible as the upper bound.
    numbers["threshold_loud"] = max(abs_floor,
                                    margin * numbers["resid_median"])
    numbers["threshold_worst"] = max(abs_floor, margin * numbers["resid_max"])
    numbers["raw_bound_worst"] = max(abs_floor, margin * numbers["raw_max"])

    # Side A — false stops. Two predicted causes: the residual of our own
    # playback on the detector stream (controlled by the margin over it,
    # IF the residual is consistent reading to reading) and room noise
    # crossing the absolute floor.
    side_a_why, side_a = [], True
    if numbers["spread"] > MAX_SPREAD:
        side_a = False
        side_a_why.append(
            f"residual readings spread x{numbers['spread']:.1f} "
            f"(max {MAX_SPREAD:.1f}) — the canceller's leavings are not "
            "stable between readings, so no threshold predicted from them "
            "is either")
    else:
        side_a_why.append(
            f"residual consistent (spread x{numbers['spread']:.1f}); "
            f"threshold sits x{margin:.1f} ({_db(margin)}) above the echo "
            "the detector stream actually hears")
    noise_clear = abs_floor / numbers["floor_max"]
    numbers["noise_clearance"] = noise_clear
    if noise_clear < NOISE_CLEARANCE:
        side_a = False
        side_a_why.append(
            f"absolute floor {abs_floor:.4f} is only x{noise_clear:.1f} "
            f"({_db(noise_clear)}) above the worst measured noise floor "
            f"{numbers['floor_max']:.4f} — room noise alone is predicted to "
            f"fire it (need x{NOISE_CLEARANCE:.1f})")
    else:
        side_a_why.append(
            f"absolute floor {abs_floor:.4f} clears the worst noise floor "
            f"{numbers['floor_max']:.4f} by x{noise_clear:.1f} ({_db(noise_clear)})")

    # Side B — catches within 300 ms. The latency budget is structural
    # (sustain + one client tick); the level side asks whether real speech
    # clears the worst-case threshold with headroom.
    side_b_why, side_b = [], True
    predicted_latency = min_ms + CLIENT_TICK_MS
    numbers["predicted_latency_ms"] = predicted_latency
    if predicted_latency > D5_CATCH_WITHIN_MS:
        side_b = False
        side_b_why.append(
            f"BARGE_IN_MIN_MS={min_ms} + one {CLIENT_TICK_MS} ms tick = "
            f"{predicted_latency} ms — cannot cut within "
            f"{D5_CATCH_WITHIN_MS} ms")
    else:
        side_b_why.append(
            f"earliest cut {predicted_latency} ms after onset "
            f"(sustain {min_ms} + tick {CLIENT_TICK_MS}) — inside the "
            f"{D5_CATCH_WITHIN_MS} ms target")
    headroom = REFERENCE_SPEECH_RMS / numbers["threshold_worst"]
    numbers["speech_headroom"] = headroom
    if headroom < SPEECH_HEADROOM:
        side_b = False
        side_b_why.append(
            f"quiet real speech ({REFERENCE_SPEECH_RMS} RMS, the 445 "
            f"measurement) is only x{headroom:.1f} above the worst-case "
            f"threshold {numbers['threshold_worst']:.4f} — soft-spoken "
            f"interruptions are predicted missed (need x{SPEECH_HEADROOM:.1f})")
    else:
        side_b_why.append(
            f"quiet real speech ({REFERENCE_SPEECH_RMS} RMS) clears the "
            f"worst-case threshold {numbers['threshold_worst']:.4f} by "
            f"x{headroom:.1f}")

    return {"side_a": side_a, "side_b": side_b,
            "side_a_why": side_a_why, "side_b_why": side_b_why,
            "numbers": numbers}


def series_summary(reading: dict, threshold_loud: float) -> dict | None:
    """An honest readout of one dual reading's residual series — the 250 ms
    window means the client stores (live.html, RESIDUAL_WINDOW_MS):

    - `pre_onset`: series[0], the first 250 ms. The residual stream is
      opened BEFORE playback starts, so this window is mostly silence
      before the first syllable — NOT the canceller's first sight of the
      echo, and nothing about convergence can be read from it.
    - `loudest`: the largest 250 ms mean, with its window index — the
      sustained echo level the detector would actually sit under during
      the utterance's loud syllables.
    - `final`: series[-1], the last window, which lies after playback has
      ended (the sample runs duration + 250 ms) — the post-playback tail,
      NOT a settled canceller.

    Replaced `convergence_summary` (2026-08-18): that readout called
    series[0] "first window/unconverged" and min(series) "settled", so it
    compared two silences and implied a convergence it could not see; the
    read-only analysis of the 2026-08-18 batches showed the series is the
    utterance's own speech envelope with residual ≈ raw throughout. This
    summary makes no convergence claim. `loudest_exceeds` says whether the
    loudest window mean sits at or above the residual-derived threshold —
    the sustained (not onset) false-stop risk.
    """
    series = (reading.get("residual") or {}).get("series") or []
    if not series:
        return None
    values = [float(v) for v in series]
    loudest_index = max(range(len(values)), key=values.__getitem__)
    return {"pre_onset": values[0], "loudest": values[loudest_index],
            "loudest_index": loudest_index, "final": values[-1],
            "windows": len(values),
            "loudest_exceeds": values[loudest_index] >= threshold_loud}


# --- sound-check ratio recommendations --------------------------------------

def recommend_ratios(readings: list[dict]) -> dict | None:
    """Recommended good/faint ratios from confirmed-heard readings, or
    None when the data does not support a recommendation.

    Basis: readings the doctor answered "yes" to are examples of a setup
    that audibly works, so their measured peak/floor ratios say where a
    working room actually sits. "Good" is placed at half the median
    confirmed ratio (clearly inside working territory), "faint" at a
    fifth (well below typical, still above the floor), floored at 1.2 —
    all of which is a proposal for the owner, not a setting.
    """
    confirmed = [r for r in readings if r.get("answer") == "yes"
                 and (r.get("ratio") or 0) > 1.0]
    if len(confirmed) < MIN_READINGS:
        return None
    ratios = sorted(float(r["ratio"]) for r in confirmed)
    if ratios[-1] / ratios[0] > 4.0:
        return None   # too inconsistent to summarise honestly
    median = statistics.median(ratios)
    return {"n": len(confirmed), "min": ratios[0], "median": median,
            "max": ratios[-1],
            "good": max(1.5, round(median * 0.5, 1)),
            "faint": max(1.2, round(median * 0.2, 1))}


# --- report -----------------------------------------------------------------

def _verdict(met: bool | None) -> str:
    return {True: "predicted MET", False: "predicted NOT MET",
            None: "INSUFFICIENT DATA"}[met]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Barge-in calibration report (D5) — report only.")
    parser.add_argument(
        "--since", metavar="YYYY-MM-DD[THH:MM[:SS]]", type=parse_since,
        default=None,
        help="analyse only readings from this moment onward, per device: a "
             "date (that day onward) or a local timestamp (that minute "
             "onward) — use after any change of volume, position or capture "
             "constraints; calibration sessions iterate within a day, and "
             "readings across such a change must not pool; excluded readings "
             "are counted in the output")
    args = parser.parse_args(argv or [])

    schema.ensure_all()
    checks, ends = fetch_rows()

    margin = speech.BARGE_IN_MARGIN
    abs_floor = speech.BARGE_IN_RMS_THRESHOLD
    min_ms = speech.BARGE_IN_MIN_MS

    print("Barge-in calibration report (D5) — REPORT ONLY, nothing changed")
    print("=" * 70)
    print(f"Settings in force: BARGE_IN_ENABLED={speech.BARGE_IN_ENABLED}"
          f"  margin=x{margin}  abs_floor={abs_floor} RMS  min_ms={min_ms}")
    if args.since is not None:
        print(f"Window: readings from {since_label(args.since)} onward only "
              "(--since); anything older is excluded per device, and said so.")
    print(f"D5 target: false stops <= {D5_FALSE_STOP_MAX:.0%} of utterances"
          f"  AND  >= {D5_CATCH_MIN:.0%} of interruptions caught within"
          f" {D5_CATCH_WITHIN_MS} ms\n")

    if not checks:
        print("No speech.sound_check rows in the audit log at all.")
        print("There is nothing to calibrate from yet.\n")

    thin_devices: list[tuple[str, int]] = []
    dual_groups_assessed = 0
    for (device, chain, mode), all_rows in group_readings(checks).items():
        rows, excluded = split_since(all_rows, args.since)
        usable = acoustic_readings(rows)
        headphones = sum(1 for r in rows
                         if r.get("discrepancy") == "no_acoustic_path_headphones_likely")
        print(f"Output device: {device}")
        print(f"  capture chain: {chain or NO_CHAIN}")
        print(f"  measurement: {'dual (raw + detector-stream residual)' if mode == 'dual' else NO_RESIDUAL}")
        print(f"  readings: {len(rows)} total, {len(usable)} with an acoustic"
              f" path ({headphones} headphone/no-path, "
              f"{len(rows) - len(usable) - headphones} other)")
        if excluded:
            if isinstance(args.since, datetime.datetime):
                stamp = lambda r: _reading_local_time(r).isoformat(timespec="minutes")  # noqa: E731
            else:
                stamp = lambda r: str(_reading_date(r))  # noqa: E731
            first, last = stamp(excluded[0]), stamp(excluded[-1])
            print(f"  EXCLUDED by --since {since_label(args.since)}: {len(excluded)} "
                  f"reading(s) from {first}..{last} — not in any number below")
        for r in rows:
            db = f"{r['ratio_db']:.0f} dB" if r.get("ratio_db") is not None else "—"
            resid = (r.get("residual") or {}).get("peak_rms")
            resid_txt = f" res={resid:.5f}" if resid is not None else ""
            print(f"    {str(r['at'])[:19]}  {r.get('username') or '?':<12}"
                  f" result={r.get('result', '?'):<12} answer={r.get('answer', '?'):<5}"
                  f" floor={r.get('noise_floor_rms', 0) or 0:.5f}"
                  f" peak={r.get('peak_rms', 0) or 0:.5f}{resid_txt}  {db}")
        if device == NO_DEVICE:
            print("  These readings cannot support any threshold: nothing "
                  "recorded which audio path produced them.\n")
            continue
        if chain is None:
            print("  These readings cannot support any threshold: nothing "
                  "recorded which capture chain produced them (pre-2026-07-30 "
                  "rows went through Chrome's echo canceller, which is what "
                  "the x13 collapse was). Never pooled with any other group.\n")
            continue
        if mode != "dual":
            print(f"  {NO_RESIDUAL} (Part 10 amendment): the threshold "
                  "operates on the detector stream, and these rows say "
                  "nothing about the residual there. Raw acoustics listed; "
                  "no verdict comes from them and they are never pooled "
                  "with dual readings.")
            recommendation = recommend_ratios(usable)
            if recommendation:
                print(f"  Sound-check ratio recommendation (raw acoustics, "
                      f"still valid — from {recommendation['n']} "
                      f"confirmed-heard readings, ratios "
                      f"{recommendation['min']:.1f}/{recommendation['median']:.1f}"
                      f"/{recommendation['max']:.1f} min/median/max):")
                print(f"      SOUND_CHECK_GOOD_RATIO={recommendation['good']}   "
                      f"(currently {speech.SOUND_CHECK_GOOD_RATIO})")
                print(f"      SOUND_CHECK_FAINT_RATIO={recommendation['faint']}  "
                      f"(currently {speech.SOUND_CHECK_FAINT_RATIO})")
            print()
            continue

        verdicts = assess_device(usable, margin=margin, abs_floor=abs_floor,
                                 min_ms=min_ms)
        n = verdicts["numbers"]
        if n.get("resid_median") is not None:
            print(f"  residual peak RMS (detector stream): min {n['resid_min']:.5f}"
                  f" / median {n['resid_median']:.5f} / max {n['resid_max']:.5f}"
                  f" (spread x{n['spread']:.1f})")
            print(f"  raw loopback peak RMS (main stream):  min {n['raw_min']:.5f}"
                  f" / median {n['raw_median']:.5f} / max {n['raw_max']:.5f}")
            print(f"  residual-derived threshold: {n['threshold_loud']:.5f} loud"
                  f" / {n['threshold_worst']:.5f} worst — raw-derived sanity"
                  f" upper bound {n['raw_bound_worst']:.5f}")
            # The residual series, per reading, read honestly (2026-08-18):
            # pre-onset window, loudest 250 ms window, post-playback tail.
            # No convergence is inferred — the series is the utterance's
            # own envelope through the canceller, and residual ≈ raw.
            for r in usable:
                curve = series_summary(r, n["threshold_loud"])
                if curve is None:
                    continue
                verdict_txt = ("AT/ABOVE the residual-derived threshold "
                               f"({n['threshold_loud']:.5f}) — a sustained echo, "
                               "not an onset transient, is the false-stop risk"
                               if curve["loudest_exceeds"] else
                               f"below the residual-derived threshold "
                               f"({n['threshold_loud']:.5f})")
                print(f"    series {str(r['at'])[:19]}: pre-onset window "
                      f"{curve['pre_onset']:.5f} (mostly silence before playback)"
                      f" · loudest 250 ms window {curve['loudest']:.5f} "
                      f"(window {curve['loudest_index'] + 1} of {curve['windows']})"
                      f" · final window {curve['final']:.5f} (post-playback tail);"
                      f" loudest window {verdict_txt}")
        print(f"  D5 side 1 — false stops <= {D5_FALSE_STOP_MAX:.0%}: "
              f"{_verdict(verdicts['side_a'])}")
        for why in verdicts["side_a_why"]:
            print(f"      {why}")
        print(f"  D5 side 2 — >= {D5_CATCH_MIN:.0%} caught within "
              f"{D5_CATCH_WITHIN_MS} ms: {_verdict(verdicts['side_b'])}")
        for why in verdicts["side_b_why"]:
            print(f"      {why}")
        both = verdicts["side_a"] and verdicts["side_b"]
        print(f"  BOTH SIDES on this device: "
              f"{_verdict(both if None not in (verdicts['side_a'], verdicts['side_b']) else None)}")
        print("  (Predicted from residual geometry. The behavioural numbers "
              "come from scripted runs in the room; this report cannot "
              "manufacture them.)")

        recommendation = recommend_ratios(usable)
        if recommendation:
            print(f"  Sound-check ratio recommendation (from "
                  f"{recommendation['n']} confirmed-heard readings, ratios "
                  f"{recommendation['min']:.1f}/{recommendation['median']:.1f}"
                  f"/{recommendation['max']:.1f} min/median/max):")
            print(f"      SOUND_CHECK_GOOD_RATIO={recommendation['good']}   "
                  f"(currently {speech.SOUND_CHECK_GOOD_RATIO}, a guess)")
            print(f"      SOUND_CHECK_FAINT_RATIO={recommendation['faint']}  "
                  f"(currently {speech.SOUND_CHECK_FAINT_RATIO}, a guess)")
            print("      Setting them is the owner's; these are what the "
                  "recorded numbers support.")
        else:
            print("  Sound-check ratios: not enough consistent confirmed-heard "
                  "readings to recommend values — the current ones remain "
                  "uncalibrated guesses.")
        dual_groups_assessed += 1
        if len(usable) < MIN_READINGS:
            thin_devices.append((f"{device} [{chain}]", len(usable)))
        print()

    barge_ends = [e for e in ends if e["action"] == "speech.barge_in"]
    spoken = sum(1 for e in ends if e["action"] == "speech.spoken")
    print(f"Observed utterance ends so far: {spoken} spoken/stopped,"
          f" {len(barge_ends)} barge-in cut(s).")
    if barge_ends:
        latencies = sorted(int(e["cut_latency_ms"]) for e in barge_ends
                           if e.get("cut_latency_ms") is not None)
        if latencies:
            within = sum(1 for v in latencies if v <= D5_CATCH_WITHIN_MS)
            print(f"  observed cut latencies (ms): {latencies}"
                  f" — {within}/{len(latencies)} within {D5_CATCH_WITHIN_MS} ms")
        print("  NOTE: audit rows carry no truth labels — whether each cut "
              "was a real interruption or a false stop is known only to "
              "whoever ran the session. The confusion matrix comes from the "
              "owner's scripted runs, tallied against their script.")
    print()

    print("What to do next" )
    print("-" * 70)
    if thin_devices or not checks or dual_groups_assessed == 0:
        need = ", ".join(f"{d} ({n}/{MIN_READINGS})" for d, n in thin_devices) \
            or ("every device — no residual-bearing readings exist yet "
                "(verdicts need the dual measurement, live since 2026-07-30)")
        print(f"1. Take more sound-check readings AT NORMAL ROOM VOLUME on the "
              f"device the room actually uses — too few so far: {need}. Each "
              "reading now carries the detector-stream residual "
              "automatically; then re-run this script.")
    else:
        print("1. Readings are sufficient. If the verdicts above say both "
              "sides are predicted met, the next step is a scripted room run "
              "(utterances under silence, under room noise, and with a "
              "scripted interruption) tallied against the script, per D5.")
    print("2. BARGE_IN_ENABLED stays FALSE until BOTH sides of the D5 target "
          "are met — and flipping it is the owner's act, recorded in "
          "HANDOVER, not a side effect of this report.")
    print("3. The numbers are hardware- and room-specific: re-run after any "
          "change of speakers, microphone or room (spec D5).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
