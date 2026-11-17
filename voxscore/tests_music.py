"""Unit tests for voxscore/music.py: no database, no browser, just the music logic."""

from django.test import SimpleTestCase

from . import music


def sung_frames(midis, bpm=120, count_in_beats=0, beats_each=1, detune_cents=0, step=0.033):
    """Fake pitch frames as the browser would send them: one held note per beat, short gaps."""
    spb = 60 / bpm
    frames, t = [], 0.0
    while t < count_in_beats * spb:
        frames.append({"t": round(t, 3), "f": 0})
        t += step
    for i, m in enumerate(midis):
        start = (count_in_beats + i * beats_each) * spb
        t = start + 0.02
        while t < start + beats_each * spb - 0.06:
            frames.append({"t": round(t, 3), "f": music.midi_to_freq(m + detune_cents / 100)})
            t += step
    return frames


class PitchBasicsTests(SimpleTestCase):
    def test_a440_is_midi_69(self):
        self.assertAlmostEqual(music.freq_to_midi(440), 69)
        self.assertEqual(music.midi_to_name(69), "A4")
        self.assertEqual(music.midi_to_name(60), "C4")
        self.assertEqual(music.midi_to_name(61, flats=True), "Db4")

    def test_nearest_note_reports_cents(self):
        midi, cents = music.nearest_note(music.midi_to_freq(64.2))
        self.assertEqual(midi, 64)
        self.assertAlmostEqual(cents, 20, delta=0.5)


class TranscriptionTests(SimpleTestCase):
    def test_melody_is_transcribed_on_the_beat(self):
        melody = [67, 69, 71, 67]
        notes = music.frames_to_notes(sung_frames(melody), bpm=120)
        self.assertEqual([n["midi"] for n in notes], melody)
        self.assertEqual([n["start"] for n in notes], [0.0, 1.0, 2.0, 3.0])
        self.assertTrue(all(n["dur"] == 1.0 for n in notes))

    def test_count_in_is_skipped(self):
        notes = music.frames_to_notes(sung_frames([60, 62], count_in_beats=4), bpm=120,
                                      count_in_beats=4)
        self.assertEqual(notes[0]["start"], 0.0)
        self.assertEqual([n["midi"] for n in notes], [60, 62])

    def test_slightly_flat_singing_rounds_to_the_intended_note(self):
        notes = music.frames_to_notes(sung_frames([65], detune_cents=-30), bpm=100)
        self.assertEqual(notes[0]["midi"], 65)

    def test_a_single_glitch_frame_does_not_split_a_note(self):
        frames = sung_frames([64], bpm=60)
        frames[10]["f"] = music.midi_to_freq(76)  # one octave-error frame
        notes = music.frames_to_notes(frames, bpm=60)
        self.assertEqual(len(notes), 1)

    def test_silence_gives_no_notes(self):
        self.assertEqual(music.frames_to_notes([{"t": 0.1, "f": 0}] * 20, bpm=90), [])

    def test_malformed_frames_are_ignored(self):
        self.assertEqual(music.frames_to_notes([{"t": "x"}, None, {"f": 300}], bpm=90), [])

    def test_bad_tempo_raises(self):
        with self.assertRaises(ValueError):
            music.frames_to_notes([], bpm=0)


class KeyTests(SimpleTestCase):
    def test_g_major_melody(self):
        notes = [{"midi": m, "start": i, "dur": 1} for i, m in enumerate([67, 71, 74, 72, 69, 66, 67])]
        self.assertEqual(music.estimate_key(notes), "G major")

    def test_a_minor_melody(self):
        notes = [{"midi": m, "start": i, "dur": d}
                 for i, (m, d) in enumerate([(69, 2), (72, 1), (76, 2), (74, 1), (72, 1), (71, 1), (69, 3)])]
        self.assertEqual(music.estimate_key(notes), "A minor")

    def test_empty(self):
        self.assertEqual(music.estimate_key([]), "")

    def test_parse_key_falls_back_to_c_major(self):
        self.assertEqual(music.parse_key("nonsense"), (0, "major"))
        self.assertEqual(music.parse_key("Bb major"), (10, "major"))


class AbcTests(SimpleTestCase):
    def test_header_and_bar_lines(self):
        abc = music.notes_to_abc([{"midi": 60, "start": 0, "dur": 4}], bpm=100, key_name="C major")
        self.assertIn("M:4/4", abc)
        self.assertIn("K:C", abc)
        self.assertIn("Q:1/4=100", abc)
        self.assertIn("C16 |]", abc)

    def test_gaps_become_rests_and_long_notes_are_tied_over_the_bar(self):
        abc = music.notes_to_abc([{"midi": 62, "start": 1, "dur": 5}], key_name="C major")
        self.assertIn("z4 D12- | D8", abc)

    def test_accidental_is_cancelled_later_in_the_bar(self):
        abc = music.notes_to_abc([{"midi": 61, "start": 0, "dur": 1}, {"midi": 60, "start": 1, "dur": 1}],
                                 key_name="C major")
        self.assertIn("^C4 =C4", abc)

    def test_octaves(self):
        abc = music.notes_to_abc([{"midi": 72, "start": 0, "dur": 1}, {"midi": 48, "start": 1, "dur": 1}],
                                 key_name="C major")
        self.assertIn("c4 C,4", abc)

    def test_minor_key_signature(self):
        self.assertIn("K:Em", music.notes_to_abc([], key_name="E minor"))


class FeedbackScoreTests(SimpleTestCase):
    def test_in_tune_singing_scores_high(self):
        self.assertEqual(music.pitch_accuracy(sung_frames([60, 64])), 100.0)

    def test_out_of_tune_singing_scores_low(self):
        self.assertEqual(music.pitch_accuracy(sung_frames([60], detune_cents=45)), 0.0)

    def test_targets_catch_a_confident_wrong_note(self):
        frames = sung_frames([62])
        self.assertEqual(music.pitch_accuracy(frames), 100.0)
        self.assertEqual(music.pitch_accuracy(frames, targets=[60]), 0.0)

    def test_no_voice_gives_none(self):
        self.assertIsNone(music.pitch_accuracy([]))
        self.assertIsNone(music.tone_stability([]))
        self.assertIsNone(music.rhythm_accuracy([]))

    def test_rhythm_is_perfect_on_the_grid(self):
        self.assertEqual(music.rhythm_accuracy([{"raw_start": 1.0}, {"raw_start": 2.5}]), 100.0)

    def test_steady_tone_scores_high(self):
        self.assertGreaterEqual(music.tone_stability(sung_frames([60], bpm=40)), 95)


class RangeAndHarmonyTests(SimpleTestCase):
    def test_voice_types(self):
        self.assertEqual(music.voice_type_for_range(40, 62), "bass")
        self.assertEqual(music.voice_type_for_range(57, 79), "soprano")

    def test_warmup_fits_the_users_range(self):
        pattern, steps = [0, 4, 7, 12], 5
        start = music.fit_pattern_start(pattern, steps, 60, low=48, high=67)
        self.assertGreaterEqual(start, 48)
        self.assertLessEqual(start + 12 + steps - 1, 67)

    def test_no_range_uses_default(self):
        self.assertEqual(music.fit_pattern_start([0, 2], 3, 57), 57)

    def test_third_below_in_c_major(self):
        melody = [{"midi": m, "start": i, "dur": 1} for i, m in enumerate([64, 65, 67, 72])]
        harmony = music.harmony_line(melody, "C major")
        self.assertEqual([n["midi"] for n in harmony], [60, 62, 64, 69])
        self.assertEqual([n["start"] for n in harmony], [0, 1, 2, 3])

    def test_third_below_stays_in_key_with_sharps(self):
        melody = [{"midi": 71, "start": 0, "dur": 1}, {"midi": 67, "start": 1, "dur": 1}]
        harmony = music.harmony_line(melody, "G major")
        self.assertEqual([n["midi"] for n in harmony], [67, 64])


class ValidateNotesTests(SimpleTestCase):
    def test_accepts_and_sorts(self):
        notes = music.validate_notes([{"midi": "62", "start": 1, "dur": 1}, {"midi": 60, "start": 0, "dur": 1}])
        self.assertEqual([n["midi"] for n in notes], [60, 62])

    def test_rejects_bad_input(self):
        for bad in ["x", [1], [{"midi": 200, "start": 0, "dur": 1}],
                    [{"midi": 60, "start": -1, "dur": 1}], [{"midi": 60, "start": 0, "dur": 0}],
                    [{"midi": 60}]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                music.validate_notes(bad)
