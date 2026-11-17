from django.contrib import admin

from .models import AIEvent, Part, PracticeSession, Profile, Score, WarmupExercise


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "voice_type", "range_low", "range_high", "ai_harmony_enabled")


@admin.register(WarmupExercise)
class WarmupExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "tradition", "focus", "minutes", "tempo_bpm")
    list_filter = ("tradition", "focus")
    search_fields = ("name", "instructions")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "warmup", "created", "pitch_accuracy", "rhythm_accuracy",
                    "tone_stability")
    list_filter = ("kind",)


class PartInline(admin.TabularInline):
    model = Part
    extra = 0
    fields = ("name", "order", "source", "pending")


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "key_name", "tempo_bpm", "updated")
    search_fields = ("title",)
    inlines = [PartInline]


@admin.register(AIEvent)
class AIEventAdmin(admin.ModelAdmin):
    list_display = ("feature", "source", "model_name", "latency_ms", "user", "created")
    list_filter = ("feature", "source")
