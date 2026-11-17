"""
Music logic, in plain Python with no audio libraries, so every piece is unit-testable.

The browser does the real-time part: static/js/audio.js detects the pitch of the microphone
about 30 times a second and sends a list of frames to the server:

    [{"t": 0.031, "f": 196.2}, {"t": 0.064, "f": 0}, ...]     t in seconds, f in Hz (0 = silence)

This module turns those frames into music:

    frames_to_notes()   pitch frames -> notes snapped to the beat grid ("transcription")
    estimate_key()      notes -> "G major" (Krumhansl-Schmuckler key finding)
    notes_to_abc()      notes -> ABC notation, which abcjs draws as sheet music in the browser
    pitch_accuracy(), rhythm_accuracy(), tone_stability()   the live-feedback scores
    harmony_line()      the rule-based harmony used when the AI assistant is off or unavailable

A note everywhere in VoxScore is {"midi": int, "start": float, "dur": float}, start and dur in
beats from the first downbeat.
"""

import math
import statistics

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

MIN_MIDI, MAX_MIDI = 21, 108          # piano range; anything outside is a detection error
MIN_VOICE_HZ, MAX_VOICE_HZ = 60, 1400  # generous human singing range
MAX_NOTES = 512


# ------------------------------------------------------------------------------ pitch basics

def freq_to_midi(freq):
    """Fractional MIDI number for a frequency: 440 Hz -> 69.0, 466.16 Hz -> 70.0."""
    return 69 + 12 * math.log2(freq / 440.0)


def midi_to_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def midi_to_name(midi, flats=False):
    """60 -> 'C4', 61 -> 'C#4' (or 'Db4' with flats=True)."""
    midi = int(round(midi))
    names = NOTE_NAMES_FLAT if flats else NOTE_NAMES_SHARP
    return f"{names[midi % 12]}{midi // 12 - 1}"


def nearest_note(freq):
    """(nearest MIDI note, cents off it) for a frequency. +cents = sharp."""
    m = freq_to_midi(freq)
    nearest = int(round(m))
    return nearest, round((m - nearest) * 100, 1)


def _voiced(frames):
    out = []
    for fr in frames or []:
        try:
            t, f = float(fr["t"]), float(fr["f"])
        except (KeyError, TypeError, ValueError):
            continue
        if MIN_VOICE_HZ <= f <= MAX_VOICE_HZ and t >= 0:
            out.append((t, f))
    return out


# ---------------------------------------------------------------------------- transcription

def _segments(frames, max_gap=0.12, split_semitones=0.8, min_len=0.08):
    """
    Group consecutive voiced frames into held notes: (start_s, end_s, midi_floats).

    A new note starts after a silence longer than max_gap, or when the pitch moves more than
    split_semitones away from the current note for two frames in a row (one stray frame is
    usually a detection glitch, not a new note).
    """
    voiced = _voiced(frames)
    segments, current = [], []
    i = 0
    while i < len(voiced):
        t, f = voiced[i]
        m = freq_to_midi(f)
        if not current:
            current = [(t, m)]
            i += 1
            continue
        gap = t - current[-1][0]
        center = statistics.median(x[1] for x in current)
        jumped = abs(m - center) > split_semitones
        if jumped and i + 1 < len(voiced):
            # Only split if the NEXT frame agrees with the jump.
            m_next = freq_to_midi(voiced[i + 1][1])
            jumped = abs(m_next - center) > split_semitones and abs(m_next - m) <= split_semitones
        if gap > max_gap or jumped:
            segments.append(current)
            current = [(t, m)]
        elif abs(m - center) > split_semitones:
            pass  # a single stray frame: ignore it
        else:
            current.append((t, m))
        i += 1
    if current:
        segments.append(current)
    frame_step = 0.033
    return [
        (seg[0][0], seg[-1][0] + frame_step, [x[1] for x in seg])
        for seg in segments
        if seg[-1][0] + frame_step - seg[0][0] >= min_len
    ]


def frames_to_notes(frames, bpm, beats_per_bar=4, beat_unit=4, count_in_beats=0, grid=None):
    """
    Transcribe pitch frames into notes on the beat grid.

    `t` in the frames counts from the moment recording started, including any count-in bar,
    so count_in_beats is subtracted to put beat 0 on the first downbeat the user sang on.
    The grid is a sixteenth note by default (0.25 of a quarter-note beat).
    """
    if bpm <= 0:
        raise ValueError("Tempo must be positive.")
    sec_per_beat = 60.0 / bpm
    if grid is None:
        grid = 0.25 * beat_unit / 4  # one sixteenth, expressed in beats
    notes = []
    for start_s, end_s, midis in _segments(frames):
        midi = int(round(statistics.median(midis)))
        if not MIN_MIDI <= midi <= MAX_MIDI:
            continue
        start = start_s / sec_per_beat - count_in_beats
        end = end_s / sec_per_beat - count_in_beats
        if end <= 0:
            continue  # sung during the count-in
        q_start = max(0.0, round(start / grid) * grid)
        q_end = round(end / grid) * grid
        dur = max(grid, q_end - q_start)
        notes.append({"midi": midi, "start": round(q_start, 4), "dur": round(dur, 4),
                      "raw_start": round(start, 4)})
    # Snapping can make neighbours overlap: shorten the earlier note, drop it if nothing is left.
    # The opposite case is a breath or consonant between notes: a gap of one grid step or less
    # is articulation, not a written rest, so the earlier note is held up to the next one.
    cleaned = []
    for n in sorted(notes, key=lambda n: n["start"]):
        if cleaned:
            prev = cleaned[-1]
            gap = n["start"] - (prev["start"] + prev["dur"])
            if gap < 0 or 0 < gap <= grid + 1e-9:
                prev["dur"] = round(n["start"] - prev["start"], 4)
                if prev["dur"] <= 0:
                    cleaned.pop()
        cleaned.append(n)
    return cleaned[:MAX_NOTES]


def strip_raw(notes):
    """The notes without the raw_start field kept for rhythm scoring."""
    return [{"midi": n["midi"], "start": n["start"], "dur": n["dur"]} for n in notes]


def validate_notes(value):
    """
    A clean list of notes, or ValueError. Used for anything the browser or an AI model sends,
    so a malformed edit can never be saved.
    """
    if not isinstance(value, list):
        raise ValueError("Notes must be a list.")
    if len(value) > MAX_NOTES:
        raise ValueError(f"A part can hold at most {MAX_NOTES} notes.")
    clean = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each note must be an object.")
        try:
            midi = int(item["midi"])
            start = float(item["start"])
            dur = float(item["dur"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Each note needs midi, start and dur.")
        if not MIN_MIDI <= midi <= MAX_MIDI:
            raise ValueError(f"Note {midi} is outside the supported range.")
        if start < 0 or not 0 < dur <= 64 or start > 4096:
            raise ValueError("Note timing is out of range.")
        clean.append({"midi": midi, "start": round(start, 4), "dur": round(dur, 4)})
    return sorted(clean, key=lambda n: n["start"])


# ------------------------------------------------------------------------------- key finding

# Krumhansl-Kessler key profiles: how strongly each scale degree belongs to a major/minor key.
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_FLAT_MAJOR_TONICS = {5, 10, 3, 8, 1}       # F, Bb, Eb, Ab, Db
_FLAT_MINOR_TONICS = {2, 7, 0, 5, 10}       # D, G, C, F, Bb minor


def _correlation(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def estimate_key(notes):
    """
    The most likely key for a melody, e.g. "G major" or "E minor"; "" if there are no notes.
    Each pitch class is weighted by how long it is held, then correlated with all 24 keys.
    """
    if not notes:
        return ""
    weights = [0.0] * 12
    for n in notes:
        weights[int(n["midi"]) % 12] += float(n["dur"])
    if not any(weights):
        return ""
    best, best_r = "", -2.0
    for tonic in range(12):
        rotated = weights[tonic:] + weights[:tonic]
        for mode, profile in (("major", _MAJOR_PROFILE), ("minor", _MINOR_PROFILE)):
            r = _correlation(rotated, profile)
            if r > best_r:
                best_r, best = r, (tonic, mode)
    tonic, mode = best
    return f"{key_tonic_name(tonic, mode)} {mode}"


def key_tonic_name(tonic, mode):
    flats = tonic in (_FLAT_MAJOR_TONICS if mode == "major" else _FLAT_MINOR_TONICS)
    return (NOTE_NAMES_FLAT if flats else NOTE_NAMES_SHARP)[tonic]


def parse_key(key_name):
    """'G major' -> (7, 'major'); anything unreadable -> (0, 'major')."""
    try:
        name, mode = key_name.split()
        mode = mode.lower()
        if mode not in ("major", "minor"):
            raise ValueError
        names = {n: i for i, n in enumerate(NOTE_NAMES_SHARP)}
        names.update({n: i for i, n in enumerate(NOTE_NAMES_FLAT)})
        return names[name], mode
    except (ValueError, KeyError, AttributeError):
        return 0, "major"


def scale_pitch_classes(key_name):
    tonic, mode = parse_key(key_name)
    steps = [0, 2, 4, 5, 7, 9, 11] if mode == "major" else [0, 2, 3, 5, 7, 8, 10]
    return [(tonic + s) % 12 for s in steps]


def key_uses_flats(key_name):
    tonic, mode = parse_key(key_name)
    return tonic in (_FLAT_MAJOR_TONICS if mode == "major" else _FLAT_MINOR_TONICS)


# ---------------------------------------------------------------------------- ABC notation

_ABC_LENGTHS = [16, 12, 8, 6, 4, 3, 2, 1]  # sixteenth-note units abcjs draws as one symbol


def _abc_split(units):
    out = []
    for size in _ABC_LENGTHS:
        while units >= size:
            out.append(size)
            units -= size
    return out


def _abc_len(units):
    return "" if units == 1 else str(units)


def _abc_pitch(midi, flats, key_pcs, bar_accidentals):
    """One ABC pitch token, always explicit about accidentals so bar carry-over cannot lie."""
    names = NOTE_NAMES_FLAT if flats else NOTE_NAMES_SHARP
    name = names[midi % 12]
    letter, acc = name[0], name[1:]
    octave = midi // 12 - 1
    if acc == "#":
        prefix = "^"
    elif acc == "b":
        prefix = "_"
    else:
        # A natural note: needs "=" if the key signature or an earlier note in this bar
        # altered the same letter.
        letter_altered_in_key = any(
            (NOTE_NAMES_FLAT if flats else NOTE_NAMES_SHARP)[pc][0] == letter
            and len((NOTE_NAMES_FLAT if flats else NOTE_NAMES_SHARP)[pc]) > 1
            for pc in key_pcs
        )
        prefix = "=" if (letter_altered_in_key or bar_accidentals.get(letter)) else ""
    bar_accidentals[letter] = prefix not in ("", "=")
    if octave >= 5:
        token = letter.lower() + "'" * (octave - 5)
    else:
        token = letter + "," * (4 - octave)
    return prefix + token


def notes_to_abc(notes, title="Melody", bpm=96, beats_per_bar=4, beat_unit=4, key_name=""):
    """
    ABC notation for one part. Notes are snapped to sixteenths, rests fill the gaps, notes
    that cross a bar line are split and tied, and the key signature comes from key_name.
    """
    units_per_beat = 16 // beat_unit
    bar_units = beats_per_bar * units_per_beat
    key_name = key_name or "C major"
    tonic, mode = parse_key(key_name)
    flats = key_uses_flats(key_name)
    key_pcs = scale_pitch_classes(key_name)
    abc_key = key_tonic_name(tonic, mode) + ("m" if mode == "minor" else "")
    header = [
        "X:1",
        f"T:{title}",
        f"M:{beats_per_bar}/{beat_unit}",
        "L:1/16",
        f"Q:1/{beat_unit}={bpm}",
        f"K:{abc_key}",
    ]

    # Build a timeline of (start_unit, length_units, midi or None for rest).
    events, cursor = [], 0
    for n in sorted(notes or [], key=lambda n: n["start"]):
        s = int(round(float(n["start"]) * units_per_beat))
        d = max(1, int(round(float(n["dur"]) * units_per_beat)))
        if s < cursor:
            s = cursor
        if s > cursor:
            events.append((cursor, s - cursor, None))
        events.append((s, d, int(n["midi"])))
        cursor = s + d
    total = max(bar_units, math.ceil(cursor / bar_units) * bar_units)
    if cursor < total:
        events.append((cursor, total - cursor, None))

    body, bar_accidentals, pos = [], {}, 0
    for start, length, midi in events:
        remaining = length
        while remaining > 0:
            room = bar_units - (pos % bar_units)
            take = min(room, remaining)
            pieces = _abc_split(take)
            for i, piece in enumerate(pieces):
                if midi is None:
                    body.append("z" + _abc_len(piece))
                else:
                    tie = "-" if (i < len(pieces) - 1 or remaining - take > 0) else ""
                    body.append(_abc_pitch(midi, flats, key_pcs, bar_accidentals)
                                + _abc_len(piece) + tie)
            pos += take
            remaining -= take
            if pos % bar_units == 0:
                body.append("|")
                bar_accidentals = {}
    if body and body[-1] == "|":
        body[-1] = "|]"
    return "\n".join(header) + "\n" + " ".join(body) + "\n"


# --------------------------------------------------------------------------- feedback scores

def pitch_accuracy(frames, targets=None, tolerance_cents=25):
    """
    Percent of voiced frames that are in tune.

    Without targets: in tune = within tolerance of the NEAREST semitone (tuner mode).
    With targets (a list of MIDI numbers, e.g. a warmup's notes): in tune = within tolerance
    of the nearest TARGET note, so singing a confident wrong note does not count.
    """
    voiced = _voiced(frames)
    if not voiced:
        return None
    good = 0
    for _, f in voiced:
        m = freq_to_midi(f)
        if targets:
            off = min(abs(m - t) for t in targets) * 100
        else:
            off = abs(m - round(m)) * 100
        good += off <= tolerance_cents
    return round(100 * good / len(voiced), 1)


def rhythm_accuracy(notes, grid=0.5):
    """
    Percent score for how close each sung note started to the beat grid (eighth notes by
    default). A note exactly on a grid line scores 100; half a grid step off scores 0.
    """
    offsets = []
    for n in notes or []:
        raw = n.get("raw_start")
        if raw is None or raw < 0:
            continue
        off = abs(raw - round(raw / grid) * grid) / (grid / 2)
        offsets.append(max(0.0, 1 - off))
    if not offsets:
        return None
    return round(100 * sum(offsets) / len(offsets), 1)


def tone_stability(frames):
    """
    A simple stand-in for "tone": how steady the pitch is while a note is held. Average
    spread (standard deviation, in cents) within each held note, mapped so 0 cents = 100 and
    40+ cents = 0. Vibrato lowers it a little, which is acceptable for a first version.
    """
    spreads = []
    for _, _, midis in _segments(frames):
        if len(midis) >= 4:
            spreads.append(statistics.pstdev(midis) * 100)
    if not spreads:
        return None
    avg = sum(spreads) / len(spreads)
    return round(max(0.0, 100 - avg * 2.5), 1)


# ------------------------------------------------------------------------- range and warmups

def voice_type_for_range(low, high):
    """A rough voice type from the lowest and highest comfortable notes (MIDI)."""
    mid = (low + high) / 2
    if mid < 52:
        return "bass"
    if mid < 56:
        return "baritone"
    if mid < 60:
        return "tenor"
    if mid < 64:
        return "alto"
    if mid < 67:
        return "mezzo"
    return "soprano"


def fit_pattern_start(pattern, steps, default_start, low=None, high=None):
    """
    The starting note for a warmup so that the pattern, repeated `steps` times a semitone
    higher each time, stays inside [low, high]. Falls back to default_start without a range.
    """
    if low is None or high is None or not pattern:
        return default_start
    span = max(pattern) - min(pattern) + max(0, steps - 1)
    room = high - low
    if span >= room:
        return low - min(pattern)
    # Start a little above the bottom of the range so the first repetition is comfortable.
    return low - min(pattern) + min(2, room - span)


def pattern_notes(pattern, start_midi, step_index=0):
    return [start_midi + step_index + p for p in pattern]


# --------------------------------------------------------------------------------- harmony

def harmony_line(notes, key_name, interval="third_below"):
    """
    The rule-based harmony: each melody note moved a diatonic third (or sixth) within the key.
    Used when the AI assistant is off, unavailable, or returns something invalid. Same rhythm
    as the melody, so it always lines up.
    """
    pcs = scale_pitch_classes(key_name or estimate_key(notes) or "C major")
    degree_steps = {"third_below": -2, "third_above": 2, "sixth_below": -5}[interval]
    out = []
    for n in notes:
        midi = int(n["midi"])
        # Find the nearest scale degree at or below the melody note.
        m = midi
        while m % 12 not in pcs:
            m -= 1
        idx = pcs.index(m % 12)
        target_pc = pcs[(idx + degree_steps) % 7]
        target = m - (m % 12) + target_pc
        # Put the target on the correct side of the melody note, less than an octave away.
        if degree_steps < 0:
            while target >= m:
                target -= 12
            while target < m - 12:
                target += 12
        else:
            while target <= m:
                target += 12
            while target > m + 12:
                target -= 12
        if MIN_MIDI <= target <= MAX_MIDI:
            out.append({"midi": target, "start": n["start"], "dur": n["dur"]})
    return out


def describe_notes(notes, limit=24, flats=False):
    """A short text version of a melody for AI prompts: 'G4 (1 beat), A4 (0.5 beat), ...'."""
    parts = []
    for n in (notes or [])[:limit]:
        d = n["dur"]
        parts.append(f"{midi_to_name(n['midi'], flats)} ({d:g} beat{'s' if d != 1 else ''})")
    more = len(notes or []) - limit
    return ", ".join(parts) + (f", ... and {more} more" if more > 0 else "")
