"""Tests for the screens, accounts and JSON endpoints (wireframe screens 1-9)."""

import io
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import music
from .models import Part, PracticeSession, Profile, Score, WarmupExercise
from .tests_music import sung_frames


class AuthTests(TestCase):
    def test_home_is_public_and_dashboard_is_not(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, reverse("login") + "?next=" + reverse("dashboard"))

    def test_signup_creates_profile_and_logs_in(self):
        r = self.client.post(reverse("signup"), {
            "username": "newsinger", "email": "", "password1": "a-Long-pass-123", "password2": "a-Long-pass-123",
        })
        self.assertRedirects(r, reverse("dashboard"))
        user = get_user_model().objects.get(username="newsinger")
        self.assertTrue(Profile.objects.filter(user=user, ai_harmony_enabled=False).exists())
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_logout_is_post_only(self):
        user = get_user_model().objects.create_user("s", password="pw-123456789")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))


class ScreenTests(TestCase):
    """Every wireframe screen renders for a signed-in user."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("singer", password="pw-123456789")
        self.client.force_login(self.user)
        self.score = Score.objects.create(user=self.user, title="My song", key_name="G major")
        Part.objects.create(score=self.score, notes=[{"midi": 67, "start": 0, "dur": 1}])

    def test_all_screens(self):
        warmup = WarmupExercise.objects.first()
        urls = [
            reverse("dashboard"), reverse("tuner"), reverse("warmup-list"),
            reverse("warmup-session", args=[warmup.slug]), reverse("studio-record"),
            reverse("score-record", args=[self.score.pk]), reverse("score-editor", args=[self.score.pk]),
            reverse("learn-home"), reverse("learn", args=["sargam"]), reverse("profile"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_warmup_library_is_seeded_and_filters(self):
        self.assertGreaterEqual(WarmupExercise.objects.count(), 10)
        r = self.client.get(reverse("warmup-list"), {"tradition": "indian"})
        self.assertContains(r, "Sargam alankar")
        self.assertNotContains(r, "Lip trill sirens")

    def test_warmup_is_transposed_into_the_users_range(self):
        Profile.objects.update_or_create(user=self.user, defaults={"range_low": 48, "range_high": 64})
        r = self.client.get(reverse("warmup-session", args=["arpeggio-1358"]))
        self.assertContains(r, "fits your range")

    def test_editor_shows_ai_panel_off_by_default(self):
        r = self.client.get(reverse("score-editor", args=[self.score.pk]))
        self.assertContains(r, "Turn on in Profile settings")
        self.assertContains(r, "Optional")

    def test_settings_turn_ai_harmony_on(self):
        self.client.post(reverse("profile"), {"ai_harmony_enabled": "on"})
        self.assertTrue(Profile.objects.get(user=self.user).ai_harmony_enabled)
        r = self.client.get(reverse("score-editor", args=[self.score.pk]))
        self.assertContains(r, "Suggest a harmony part")


class OwnershipTests(TestCase):
    """One account can never open or change another account's scores."""

    def setUp(self):
        owner = get_user_model().objects.create_user("owner", password="pw-123456789")
        self.score = Score.objects.create(user=owner, title="Private")
        self.part = Part.objects.create(score=self.score, notes=[])
        intruder = get_user_model().objects.create_user("intruder", password="pw-123456789")
        self.client.force_login(intruder)

    def test_cannot_open_edit_export_or_delete(self):
        self.assertEqual(self.client.get(reverse("score-editor", args=[self.score.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("score-export", args=[self.score.pk, "abc"])).status_code, 404)
        r = self.client.post(reverse("part-save", args=[self.part.pk]), "{}", content_type="application/json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.post(reverse("score-delete", args=[self.score.pk])).status_code, 404)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())


class JsonEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("singer", password="pw-123456789")
        self.client.force_login(self.user)

    def post(self, name, data, *args):
        return self.client.post(reverse(name, args=args), json.dumps(data), content_type="application/json")

    def test_transcribe_creates_score_part_and_session(self):
        frames = sung_frames([67, 69, 71, 67], bpm=100, count_in_beats=4)
        r = self.post("studio-transcribe", {"frames": frames, "bpm": 100, "beats_per_bar": 4,
                                            "beat_unit": 4, "count_in_beats": 4, "title": "Take 1"})
        self.assertEqual(r.status_code, 200, r.content)
        score = Score.objects.get(user=self.user)
        self.assertEqual(r.json()["url"], score.get_absolute_url())
        self.assertEqual(score.title, "Take 1")
        self.assertEqual([n["midi"] for n in score.parts.get().notes], [67, 69, 71, 67])
        self.assertTrue(score.key_name)
        self.assertEqual(PracticeSession.objects.get(user=self.user).kind, "studio")

    def test_transcribe_adds_a_part_to_an_existing_score(self):
        score = Score.objects.create(user=self.user, tempo_bpm=100)
        Part.objects.create(score=score, notes=[{"midi": 60, "start": 0, "dur": 1}])
        r = self.post("studio-transcribe", {"frames": sung_frames([64, 65], bpm=100), "score": score.pk,
                                            "part_name": "Alto"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(score.parts.values_list("name", flat=True)), ["Melody", "Alto"])

    def test_transcribe_silence_is_a_clear_error(self):
        r = self.post("studio-transcribe", {"frames": [{"t": 0.1, "f": 0}], "bpm": 90})
        self.assertEqual(r.status_code, 422)
        self.assertFalse(Score.objects.exists())

    def test_bad_json_is_rejected(self):
        r = self.client.post(reverse("studio-transcribe"), "not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_part_save_validates_and_returns_abc(self):
        score = Score.objects.create(user=self.user, key_name="C major")
        part = Part.objects.create(score=score, notes=[])
        r = self.post("part-save", {"notes": [{"midi": 60, "start": 0, "dur": 4}]}, part.pk)
        self.assertIn("C16", r.json()["abc"])
        part.refresh_from_db()
        self.assertEqual(part.source, Part.Source.EDITED)
        bad = self.post("part-save", {"notes": [{"midi": 999, "start": 0, "dur": 1}]}, part.pk)
        self.assertEqual(bad.status_code, 400)

    def test_session_save_scores_against_targets(self):
        r = self.post("session-save", {"kind": "warmup", "warmup": "five-note-scale-ah",
                                       "frames": sung_frames([62]), "targets": [60], "seconds": 30})
        self.assertEqual(r.json()["pitch"], 0.0)
        self.assertEqual(PracticeSession.objects.get().warmup.slug, "five-note-scale-ah")

    def test_range_save_sets_voice_type(self):
        r = self.post("range-save", {"low": 43, "high": 64})
        self.assertEqual(r.json()["voice_type"], "Baritone")
        self.assertEqual(self.post("range-save", {"low": 60, "high": 61}).status_code, 400)


class SeedDemoTests(TestCase):
    def test_seed_demo_is_repeatable(self):
        call_command("seed_demo", stdout=io.StringIO())
        call_command("seed_demo", stdout=io.StringIO())
        demo = get_user_model().objects.get(username="demo")
        self.assertEqual(Score.objects.filter(user=demo).count(), 1)
        self.assertEqual(Score.objects.get(user=demo).key_name, "G major")
        self.assertTrue(self.client.login(username="demo", password="voxscore-demo"))


class AbcRenderTests(TestCase):
    def test_part_abc_uses_the_scores_settings(self):
        user = get_user_model().objects.create_user("u", password="pw-123456789")
        score = Score.objects.create(user=user, tempo_bpm=72, beats_per_bar=3, key_name="D major")
        part = Part.objects.create(score=score, name="Lead", notes=[{"midi": 62, "start": 0, "dur": 3}])
        abc = part.abc()
        self.assertIn("M:3/4", abc)
        self.assertIn("K:D", abc)
        self.assertIn("T:Lead", abc)
        self.assertEqual(music.estimate_key(part.notes), "D major")
