"""
The AI features as Django views (the logic lives in voxscore/ai/).

    POST /learn/<slug>/ask/                 tutor-ask        feature 1: theory tutor
    POST /practice/sessions/<pk>/coach/     session-coach    feature 2: practice coach (JSON)
    POST /studio/<pk>/harmony/              harmony-suggest  feature 3: OPTIONAL harmony part

All login-only, all scoped to the signed-in user's own data, and all counted against
settings.AI_REQUESTS_PER_MINUTE per account, because model calls are the most expensive thing
this site does and the external API is rate-limited per key.
"""

import time

from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import lessons, music
from .ai import coach, harmony, telemetry, tutor
from .forms import TutorForm
from .models import Part, PracticeSession, Score
from .views import get_profile


def over_limit(user):
    """True if `user` has used up this minute's AI requests. Counts the current one."""
    limit = getattr(settings, "AI_REQUESTS_PER_MINUTE", 10)
    key = f"ai-rate:{user.pk}:{int(time.time() // 60)}"
    cache.add(key, 0, timeout=120)
    try:
        count = cache.incr(key)
    except ValueError:  # the key expired between add and incr
        cache.set(key, 1, timeout=120)
        count = 1
    return count > limit


@login_required
@require_POST
def tutor_ask(request, slug):
    lesson = lessons.get(slug)
    scores = Score.objects.filter(user=request.user)[:20]
    form = TutorForm(request.POST, scores=scores)
    result, status = None, 200
    if not form.is_valid():
        status = 400
    elif over_limit(request.user):
        with telemetry.record("tutor", request.user) as ev:
            ev.done("rate_limited")
        result = {"answer": "", "source": "rate_limited",
                  "note": "Too many AI requests this minute. Wait a moment and try again."}
        status = 429
    else:
        score = None
        if form.cleaned_data.get("score"):
            score = Score.objects.filter(pk=form.cleaned_data["score"], user=request.user).first()
        with telemetry.record("tutor", request.user) as ev:
            result = tutor.answer(form.cleaned_data["question"], lesson["slug"], score)
            ev.done(result["source"], result.get("model", ""))
        if result["source"] == "refused":
            status = 400
    return render(request, "voxscore/learn.html", {
        "active": "learn",
        "lessons": lessons.LESSONS,
        "lesson": lesson,
        "form": form,
        "result": result,
        "question": request.POST.get("question", ""),
        "example_names": [music.midi_to_name(m) for m in lesson["example"]],
    }, status=status)


@login_required
@require_POST
def session_coach(request, pk):
    session = get_object_or_404(PracticeSession, pk=pk, user=request.user)
    if over_limit(request.user):
        with telemetry.record("coach", request.user) as ev:
            ev.done("rate_limited")
        return JsonResponse({"ok": False, "error": "Too many AI requests this minute."}, status=429)
    with telemetry.record("coach", request.user) as ev:
        result = coach.feedback(session)
        ev.done(result["source"], result.get("model", ""))
    session.coach_feedback = result["summary"] + "\n" + "\n".join(f"- {t}" for t in result["tips"])
    session.save(update_fields=["coach_feedback"])
    return JsonResponse({"ok": True, **result})


@login_required
@require_POST
def harmony_suggest(request, pk):
    """
    Optional feature: only works when the user has switched AI harmony on in their profile.
    The suggestion is saved as a PENDING part; the editor shows Accept / Reject.
    """
    score = get_object_or_404(Score, pk=pk, user=request.user)
    if not get_profile(request.user).ai_harmony_enabled:
        flash.warning(request, "AI harmony suggestions are off. You can turn them on in your profile.")
        return redirect(score)
    melody = score.parts.filter(pending=False).first()
    if melody is None:
        flash.warning(request, "Record a melody first.")
        return redirect(score)
    if over_limit(request.user):
        with telemetry.record("harmony", request.user) as ev:
            ev.done("rate_limited")
        flash.warning(request, "Too many AI requests this minute. Wait a moment and try again.")
        return redirect(score)
    voice = request.POST.get("voice", "alto")
    if voice not in harmony.VOICES:
        voice = "alto"
    with telemetry.record("harmony", request.user) as ev:
        result = harmony.suggest(melody, voice)
        ev.done(result["source"], result.get("model", ""))
    if not result["notes"]:
        flash.warning(request, result["note"] or "No harmony could be suggested.")
        return redirect(score)
    Part.objects.create(
        score=score, name=f"{voice.title()} (suggested)", order=score.parts.count(),
        notes=result["notes"], source=Part.Source.AI, pending=True,
    )
    if result["note"]:
        flash.info(request, result["note"])
    return redirect(score)
