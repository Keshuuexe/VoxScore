"""
VoxScore's data model.

    Profile          one per user: vocal range, voice type, and the AI harmony opt-in
    WarmupExercise   the global warmup library (a cappella, Western, Indian classical, other)
    PracticeSession  one practice run (tuner, warmup or studio take) and its scores
    Score            a song project in the Studio: tempo, time signature, key
    Part             one voice in a Score (melody, harmony...), notes stored as JSON
    AIEvent          one row per AI request, for rate limiting and a future analytics page

Every user-owned row has a `user` (directly or through its Score), and every view filters on
it, so one account can never read another's recordings or scores.

Notes are stored as JSON rather than a Note table: a part is always read and written whole
(transcribe, edit, play back), and a list of
    {"midi": 67, "start": 0.0, "dur": 1.0}
dicts (start and dur in beats) is exactly the shape the browser and voxscore/music.py use.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse

from . import music


class Profile(models.Model):
    class VoiceType(models.TextChoices):
        UNKNOWN = "", "Not tested yet"
        BASS = "bass", "Bass"
        BARITONE = "baritone", "Baritone"
        TENOR = "tenor", "Tenor"
        ALTO = "alto", "Alto"
        MEZZO = "mezzo", "Mezzo-soprano"
        SOPRANO = "soprano", "Soprano"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="profile")
    # Lowest and highest comfortable notes as MIDI numbers (60 = middle C). Null = not tested.
    range_low = models.PositiveSmallIntegerField(null=True, blank=True)
    range_high = models.PositiveSmallIntegerField(null=True, blank=True)
    voice_type = models.CharField(max_length=12, choices=VoiceType.choices, blank=True)
    # The AI harmony assistant is OFF until the user turns it on (wireframe screen 7).
    ai_harmony_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile of {self.user}"

    @property
    def range_label(self):
        if self.range_low is None or self.range_high is None:
            return "Not tested yet"
        return f"{music.midi_to_name(self.range_low)} – {music.midi_to_name(self.range_high)}"

    def set_range(self, low, high):
        low, high = sorted((int(low), int(high)))
        self.range_low, self.range_high = low, high
        self.voice_type = music.voice_type_for_range(low, high)


class WarmupExercise(models.Model):
    class Tradition(models.TextChoices):
        ACAPPELLA = "acappella", "A cappella"
        WESTERN = "western", "Western"
        INDIAN = "indian", "Indian classical"
        OTHER = "other", "Other global"

    class Focus(models.TextChoices):
        RANGE = "range", "Range"
        BREATH = "breath", "Breath"
        AGILITY = "agility", "Agility"
        BLEND = "blend", "Blend and tuning"
        RESONANCE = "resonance", "Resonance"

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    tradition = models.CharField(max_length=12, choices=Tradition.choices)
    focus = models.CharField(max_length=12, choices=Focus.choices)
    minutes = models.PositiveSmallIntegerField(default=3)
    instructions = models.TextField()
    # The pattern as semitones above the starting note, e.g. [0, 2, 4, 5, 7, 5, 4, 2, 0].
    pattern = models.JSONField(default=list)
    # Optional syllable per note ("Sa Re Ga" or "Do Re Mi" or "ah"), space-separated.
    syllables = models.CharField(max_length=200, blank=True)
    # Starting note when the user's range is unknown (MIDI; 60 = C4).
    default_start = models.PositiveSmallIntegerField(default=60)
    # How many times the pattern repeats, each time a semitone higher.
    steps = models.PositiveSmallIntegerField(default=5)
    tempo_bpm = models.PositiveSmallIntegerField(default=80)

    class Meta:
        ordering = ["tradition", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("warmup-session", args=[self.slug])

    def start_note_for(self, profile):
        """A starting note that keeps the whole exercise inside the user's range, if known."""
        return music.fit_pattern_start(self.pattern, self.steps, self.default_start,
                                       profile.range_low if profile else None,
                                       profile.range_high if profile else None)


class PracticeSession(models.Model):
    class Kind(models.TextChoices):
        TUNER = "tuner", "Tuner"
        WARMUP = "warmup", "Warmup"
        STUDIO = "studio", "Studio"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="practice_sessions")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    warmup = models.ForeignKey(WarmupExercise, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    seconds = models.PositiveIntegerField(default=0)
    # 0-100 percentages, computed on the server from the pitch frames the browser sends.
    pitch_accuracy = models.FloatField(null=True, blank=True)
    rhythm_accuracy = models.FloatField(null=True, blank=True)
    tone_stability = models.FloatField(null=True, blank=True)
    # The AI coach's short summary, written on request.
    coach_feedback = models.TextField(blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.get_kind_display()} session by {self.user} on {self.created:%Y-%m-%d}"


class Score(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="scores")
    title = models.CharField(max_length=120, default="Untitled song")
    tempo_bpm = models.PositiveSmallIntegerField(default=96)
    beats_per_bar = models.PositiveSmallIntegerField(default=4)
    beat_unit = models.PositiveSmallIntegerField(default=4)
    # Key as detected from the first part, e.g. "G major". Blank until something is sung.
    key_name = models.CharField(max_length=20, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("score-editor", args=[self.pk])

    @property
    def time_signature(self):
        return f"{self.beats_per_bar}/{self.beat_unit}"


class Part(models.Model):
    class Source(models.TextChoices):
        SUNG = "sung", "Sung"
        AI = "ai", "AI suggestion"
        EDITED = "edited", "Edited"

    score = models.ForeignKey(Score, on_delete=models.CASCADE, related_name="parts")
    name = models.CharField(max_length=40, default="Melody")
    order = models.PositiveSmallIntegerField(default=0)
    notes = models.JSONField(default=list)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.SUNG)
    # An AI suggestion stays pending until the user accepts it; rejected ones are deleted.
    pending = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created"]

    def __str__(self):
        return f"{self.name} ({self.score})"

    def abc(self):
        """ABC notation for this part alone, which abcjs turns into sheet music in the browser."""
        s = self.score
        return music.notes_to_abc(self.notes, title=self.name, bpm=s.tempo_bpm,
                                  beats_per_bar=s.beats_per_bar, beat_unit=s.beat_unit,
                                  key_name=s.key_name)


class AIEvent(models.Model):
    """One AI request: which feature, whether a model answered or a fallback did, how long."""

    class Feature(models.TextChoices):
        TUTOR = "tutor", "Theory tutor"
        COACH = "coach", "Practice coach"
        HARMONY = "harmony", "Harmony suggestion"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    feature = models.CharField(max_length=10, choices=Feature.choices)
    # "groq", "local", "rules" (fallback), "refused" (guardrail) or "rate_limited".
    source = models.CharField(max_length=14)
    model_name = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.feature} via {self.source}"
