"""
python manage.py seed_demo

Creates (or resets) the demo account so the dashboard, profile chart and Studio have
something to show on a fresh install and in the demo video:

    username: demo      password: voxscore-demo

The demo song is "Twinkle, Twinkle, Little Star" (traditional, public domain). Safe to run
more than once: it rebuilds only the demo account's own rows.
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from voxscore import music
from voxscore.models import Part, PracticeSession, Profile, Score, WarmupExercise

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "voxscore-demo"

# Twinkle, Twinkle (first two phrases) in G major, one note per beat except the held notes.
TWINKLE = [67, 67, 74, 74, 76, 76, 74, None, 72, 72, 71, 71, 69, 69, 67, None]


def twinkle_notes():
    notes, beat = [], 0.0
    for i, midi in enumerate(TWINKLE):
        if midi is None:
            continue
        held = i + 1 < len(TWINKLE) and TWINKLE[i + 1] is None
        notes.append({"midi": midi, "start": beat, "dur": 2.0 if held else 1.0})
        beat += 2.0 if held else 1.0
    return notes


class Command(BaseCommand):
    help = "Create or reset the demo account (demo / voxscore-demo) with sample data."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=DEMO_USERNAME,
                                                   defaults={"email": "demo@example.com"})
        user.set_password(DEMO_PASSWORD)
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.set_range(48, 69)  # C3 - A4
        profile.ai_harmony_enabled = False
        profile.save()

        Score.objects.filter(user=user).delete()
        PracticeSession.objects.filter(user=user).delete()

        melody = twinkle_notes()
        score = Score.objects.create(user=user, title="Twinkle, Twinkle (demo)", tempo_bpm=96,
                                     key_name=music.estimate_key(melody))
        Part.objects.create(score=score, name="Melody", order=0, notes=melody)

        # Three weeks of practice with gently improving scores, for the profile chart.
        rng = random.Random(7)
        warmups = list(WarmupExercise.objects.all())
        now = timezone.now()
        for days_ago in range(20, -1, -1):
            if days_ago in (15, 11, 6):
                continue  # a few rest days
            progress = (20 - days_ago) / 20
            kind = rng.choice(["tuner", "warmup", "warmup", "studio"])
            session = PracticeSession.objects.create(
                user=user, kind=kind,
                warmup=rng.choice(warmups) if kind == "warmup" and warmups else None,
                seconds=rng.randint(240, 900),
                pitch_accuracy=round(58 + 25 * progress + rng.uniform(-5, 5), 1),
                rhythm_accuracy=round(60 + 20 * progress + rng.uniform(-6, 6), 1) if kind == "studio" else None,
                tone_stability=round(62 + 18 * progress + rng.uniform(-5, 5), 1),
            )
            # auto_now_add ignores a value passed to create(), so backdate with update().
            PracticeSession.objects.filter(pk=session.pk).update(
                created=now - timedelta(days=days_ago, hours=rng.randint(0, 5)))

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Reset'} demo account: {DEMO_USERNAME} / {DEMO_PASSWORD}"))
