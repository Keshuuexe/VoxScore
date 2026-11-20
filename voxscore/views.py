"""
The VoxScore screens, one view per wireframe screen.

    /                               home              landing page (signed in -> dashboard)
    /accounts/login|signup|logout/  (auth_views.py)   Screen 1
    /dashboard/                     dashboard         Screen 2
    /practice/                      tuner             Screen 3  tuner + live feedback
    /practice/warmups/              warmup-list       Screen 4  library with filters
    /practice/warmups/<slug>/       warmup-session    Screen 5  guided warmup
    /studio/                        studio-record     Screen 6  record a new melody
    /studio/<pk>/record/            score-record      Screen 6  record another part on a score
    /studio/<pk>/                   score-editor      Screen 7  sheet music + edits
    /learn/<slug>/                  learn             Screen 8  (tutor POST is in ai_views.py)
    /profile/                       profile           Screen 9

The browser posts JSON to a few endpoints (saving a session, transcribing a take, saving note
edits). Those return JSON and are login-only like everything else. Every query goes through
the signed-in user, so one account can never see another's data.
"""

import json
from datetime import timedelta

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import lessons, music
from .forms import SettingsForm, TutorForm
from .models import Part, PracticeSession, Profile, Score, WarmupExercise

MAX_FRAMES = 30 * 60 * 10   # ten minutes of pitch frames at ~30 per second
MAX_BODY_BYTES = 2_000_000

# Keys offered in the Studio and the editor's key menu.
KEY_CHOICES = [f"{music.key_tonic_name(t, mode)} {mode}" for mode in ("major", "minor")
               for t in range(12)]


# ------------------------------------------------------------------------------- helpers

def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _json_body(request):
    """The request's JSON body as a dict, or None if it is missing, too big or malformed."""
    if len(request.body) > MAX_BODY_BYTES:
        return None
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _bad(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _int(value, default, low, high):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def practice_streak(user, today=None):
    """Consecutive days, ending today or yesterday, with at least one practice session."""
    today = today or timezone.localdate()
    days = set(
        timezone.localtime(dt).date()
        for dt in PracticeSession.objects.filter(
            user=user, created__date__gte=today - timedelta(days=366)
        ).values_list("created", flat=True)
    )
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


# ------------------------------------------------------------------------- home + dashboard

# The homepage's opening melody (an original phrase): C major, three bars of quarter notes.
HERO_MELODY = [60, 64, 67, 72, 71, 67, 69, 65, 64, 62, 64, 60]
HERO_BPM = 104


def hero_staff(melody=HERO_MELODY):
    """
    Positions for drawing `melody` on a treble staff in the homepage SVG.

    Staff lines sit at y = 30, 40, 50, 60, 70 (E4 on the bottom line); each step of the scale
    moves a note 5 units. Stems go up below the middle line (B4) and down from it, ledger lines
    are added below the staff, and a barline follows every fourth note, as in printed music.
    """
    letter_index = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}  # natural notes only (C major)
    notes, barlines = [], []
    for i, midi in enumerate(melody):
        step = (midi // 12 - 1) * 7 + letter_index[midi % 12]   # MIDI 60 = C4, octave 4
        y = 70 - (step - 30) * 5            # step 30 = E4, the bottom line
        x = 160 + i * 66
        stem_up = step < 34                  # 34 = B4, the middle line
        ledgers = [ly for ly in range(80, y + 1, 10)]
        notes.append({
            "x": x, "y": y, "stem_up": stem_up, "ledgers": ledgers, "delay": 250 + i * 110,
            "stem_x": x + 6 if stem_up else x - 6,
            "stem_y2": y - 34 if stem_up else y + 34,
        })
        if i % 4 == 3 and i < len(melody) - 1:
            barlines.append(x + 33)
    return {
        "notes": notes, "barlines": barlines, "end": notes[-1]["x"] + 36,
        "travel": notes[-1]["x"] - notes[0]["x"] + 20,
        "melody": [{"midi": m, "start": i, "dur": 1} for i, m in enumerate(melody)],
        "bpm": HERO_BPM,
    }


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "voxscore/home.html", {"hero": hero_staff()})


@login_required
def dashboard(request):
    """Screen 2: two big choices (Practice, Studio) plus recent work and the streak."""
    recent_scores = Score.objects.filter(user=request.user).annotate(n_parts=Count("parts"))[:3]
    recent_sessions = (PracticeSession.objects.filter(user=request.user)
                       .select_related("warmup")[:3])
    return render(request, "voxscore/dashboard.html", {
        "active": "dashboard",
        "recent_scores": recent_scores,
        "recent_sessions": recent_sessions,
        "streak": practice_streak(request.user),
    })


# ------------------------------------------------------------------------------- practice

@login_required
def tuner(request):
    """Screen 3: tuner, live pitch/rhythm/tone bars, metronome, drone and note player."""
    return render(request, "voxscore/tuner.html", {
        "active": "practice", "tab": "tuner",
        "drone_notes": music.NOTE_NAMES_SHARP,
    })


@login_required
def warmup_list(request):
    """Screen 4: the warmup library, filtered by tradition, focus and search text."""
    exercises = WarmupExercise.objects.all()
    tradition = request.GET.get("tradition", "")
    focus = request.GET.get("focus", "")
    q = request.GET.get("q", "").strip()[:60]
    if tradition in WarmupExercise.Tradition.values:
        exercises = exercises.filter(tradition=tradition)
    if focus in WarmupExercise.Focus.values:
        exercises = exercises.filter(focus=focus)
    if q:
        exercises = exercises.filter(name__icontains=q) | exercises.filter(instructions__icontains=q)
    return render(request, "voxscore/warmup_list.html", {
        "active": "practice", "tab": "warmups",
        "exercises": exercises.distinct(),
        "traditions": WarmupExercise.Tradition.choices,
        "focuses": WarmupExercise.Focus.choices,
        "tradition": tradition, "focus": focus, "q": q,
    })


@login_required
def warmup_session(request, slug):
    """Screen 5: one guided warmup, transposed into the user's range when it is known."""
    exercise = get_object_or_404(WarmupExercise, slug=slug)
    profile = get_profile(request.user)
    start = exercise.start_note_for(profile)
    return render(request, "voxscore/warmup_session.html", {
        "active": "practice",
        "exercise": exercise,
        "profile": profile,
        "start_midi": start,
        "start_name": music.midi_to_name(start),
        "warmup_data": {
            "slug": exercise.slug,
            "pattern": exercise.pattern,
            "syllables": exercise.syllables.split(),
            "steps": exercise.steps,
            "start": start,
            "bpm": exercise.tempo_bpm,
        },
    })


@login_required
@require_POST
def session_save(request):
    """
    POST JSON {kind, warmup?, seconds, frames, targets?} from the tuner or a warmup.
    Scores the session on the server and returns them, plus the session id for the coach.
    """
    data = _json_body(request)
    if data is None:
        return _bad("Expected a JSON body.")
    kind = data.get("kind")
    if kind not in (PracticeSession.Kind.TUNER, PracticeSession.Kind.WARMUP):
        return _bad("Unknown session kind.")
    frames = data.get("frames") or []
    if not isinstance(frames, list) or len(frames) > MAX_FRAMES:
        return _bad("Frames must be a list of at most ten minutes of audio.")
    targets = data.get("targets") or None
    if targets is not None:
        try:
            targets = [int(t) for t in targets][:512]
        except (TypeError, ValueError):
            return _bad("Targets must be MIDI numbers.")
    warmup = None
    if kind == PracticeSession.Kind.WARMUP:
        warmup = WarmupExercise.objects.filter(slug=str(data.get("warmup", ""))).first()

    session = PracticeSession.objects.create(
        user=request.user, kind=kind, warmup=warmup,
        seconds=_int(data.get("seconds"), 0, 0, 36000),
        pitch_accuracy=music.pitch_accuracy(frames, targets),
        tone_stability=music.tone_stability(frames),
    )
    return JsonResponse({
        "ok": True, "id": session.pk,
        "pitch": session.pitch_accuracy, "tone": session.tone_stability,
    })


# --------------------------------------------------------------------------------- studio

@login_required
def studio_record(request, pk=None):
    """Screen 6: set tempo/meter and record. With pk, records another part on that score."""
    score = get_object_or_404(Score, pk=pk, user=request.user) if pk else None
    parts = list(score.parts.filter(pending=False)) if score else []
    return render(request, "voxscore/studio_record.html", {
        "active": "studio",
        "score": score,
        "existing_parts": parts,
        "abc_parts": [p.abc() for p in parts],
        "key_choices": KEY_CHOICES,
        "record_data": {
            "id": score.pk, "bpm": score.tempo_bpm, "beatsPerBar": score.beats_per_bar,
            "beatUnit": score.beat_unit, "parts": [p.notes for p in parts],
        } if score else None,
    })


@login_required
@require_POST
def studio_transcribe(request):
    """
    POST JSON {frames, bpm, beats_per_bar, beat_unit, count_in_beats, title, score?, part_name,
    seconds}. Turns the take into notes, saves them as a Part (on a new or existing Score),
    logs a studio PracticeSession, and returns the editor URL.
    """
    data = _json_body(request)
    if data is None:
        return _bad("Expected a JSON body.")
    frames = data.get("frames") or []
    if not isinstance(frames, list) or len(frames) > MAX_FRAMES:
        return _bad("Frames must be a list of at most ten minutes of audio.")

    score = None
    if data.get("score"):
        score = Score.objects.filter(pk=_int(data["score"], 0, 0, 10**9), user=request.user).first()
        if score is None:
            return _bad("Score not found.", status=404)
    bpm = score.tempo_bpm if score else _int(data.get("bpm"), 96, 30, 240)
    beats_per_bar = score.beats_per_bar if score else _int(data.get("beats_per_bar"), 4, 1, 12)
    beat_unit = score.beat_unit if score else (4 if data.get("beat_unit") not in (8, "8") else 8)
    count_in = _int(data.get("count_in_beats"), 0, 0, 12)

    notes = music.frames_to_notes(frames, bpm, beats_per_bar, beat_unit, count_in)
    if not notes:
        return _bad("No singing was detected. Check the microphone and try again.", status=422)

    if score is None:
        title = (str(data.get("title") or "").strip() or "Untitled song")[:120]
        key_choice = str(data.get("key") or "auto")
        key_name = (key_choice if key_choice in KEY_CHOICES
                    else music.estimate_key(notes))
        score = Score.objects.create(user=request.user, title=title, tempo_bpm=bpm,
                                     beats_per_bar=beats_per_bar, beat_unit=beat_unit,
                                     key_name=key_name)
    part_name = (str(data.get("part_name") or "").strip()
                 or ("Melody" if not score.parts.exists() else f"Part {score.parts.count() + 1}"))
    Part.objects.create(score=score, name=part_name[:40], order=score.parts.count(),
                        notes=music.strip_raw(notes), source=Part.Source.SUNG)
    score.save(update_fields=["updated"])

    PracticeSession.objects.create(
        user=request.user, kind=PracticeSession.Kind.STUDIO,
        seconds=_int(data.get("seconds"), 0, 0, 36000),
        pitch_accuracy=music.pitch_accuracy(frames),
        rhythm_accuracy=music.rhythm_accuracy(notes),
        tone_stability=music.tone_stability(frames),
    )
    return JsonResponse({"ok": True, "url": score.get_absolute_url(), "notes": len(notes),
                         "key": score.key_name})


@login_required
def score_editor(request, pk):
    """Screen 7: the score as sheet music, note editing, parts, and the optional AI panel."""
    score = get_object_or_404(Score, pk=pk, user=request.user)
    parts = list(score.parts.all())
    profile = get_profile(request.user)
    return render(request, "voxscore/score_editor.html", {
        "active": "studio",
        "score": score,
        "parts": parts,
        "accepted_parts": [p for p in parts if not p.pending],
        "pending_parts": [p for p in parts if p.pending],
        "profile": profile,
        "key_choices": KEY_CHOICES,
        "editor_data": {
            "score": score.pk,
            "bpm": score.tempo_bpm,
            "beatsPerBar": score.beats_per_bar,
            "beatUnit": score.beat_unit,
            "key": score.key_name,
            "parts": [{"id": p.pk, "name": p.name, "notes": p.notes, "abc": p.abc(),
                       "pending": p.pending, "source": p.source} for p in parts],
        },
    })


@login_required
@require_POST
def part_save(request, pk):
    """POST JSON {notes, name?} replaces a part's notes after editing (Undo lives in the browser)."""
    part = get_object_or_404(Part, pk=pk, score__user=request.user)
    data = _json_body(request)
    if data is None:
        return _bad("Expected a JSON body.")
    try:
        notes = music.validate_notes(data.get("notes"))
    except ValueError as exc:
        return _bad(str(exc))
    part.notes = notes
    if data.get("name"):
        part.name = str(data["name"]).strip()[:40] or part.name
    if part.source == Part.Source.SUNG:
        part.source = Part.Source.EDITED
    part.save()
    part.score.save(update_fields=["updated"])
    return JsonResponse({"ok": True, "abc": part.abc()})


@login_required
@require_POST
def part_delete(request, pk):
    part = get_object_or_404(Part, pk=pk, score__user=request.user)
    score = part.score
    part.delete()
    flash.info(request, f"Deleted the part “{part.name}”.")
    return redirect(score)


@login_required
@require_POST
def part_accept(request, pk):
    """Accept a pending AI suggestion: it becomes an ordinary part the user owns."""
    part = get_object_or_404(Part, pk=pk, score__user=request.user, pending=True)
    part.pending = False
    part.save(update_fields=["pending"])
    flash.success(request, f"Added “{part.name}” to your score.")
    return redirect(part.score)


@login_required
@require_POST
def part_reject(request, pk):
    part = get_object_or_404(Part, pk=pk, score__user=request.user, pending=True)
    score = part.score
    part.delete()
    flash.info(request, "Suggestion removed.")
    return redirect(score)


@login_required
@require_POST
def score_update(request, pk):
    """Rename the score or change its key (the form above the score)."""
    score = get_object_or_404(Score, pk=pk, user=request.user)
    title = request.POST.get("title", "").strip()
    if title:
        score.title = title[:120]
    key_name = request.POST.get("key_name", "").strip()
    if key_name:
        tonic, mode = music.parse_key(key_name)
        score.key_name = f"{music.key_tonic_name(tonic, mode)} {mode}"
    score.save()
    return redirect(score)


@login_required
@require_POST
def score_delete(request, pk):
    score = get_object_or_404(Score, pk=pk, user=request.user)
    score.delete()
    flash.info(request, f"Deleted “{score.title}”.")
    return redirect("profile")


@login_required
def score_export(request, pk, fmt):
    """Download the score as ABC (opens in MuseScore via abc2xml, or any ABC tool) or JSON."""
    if fmt not in ("abc", "json"):
        raise Http404("Unknown export format.")
    score = get_object_or_404(Score, pk=pk, user=request.user)
    parts = score.parts.filter(pending=False)
    filename = "".join(c for c in score.title if c.isalnum() or c in " -_").strip() or "score"
    if fmt == "abc":
        body = "\n".join(p.abc().replace("X:1", f"X:{i + 1}", 1) for i, p in enumerate(parts))
        response = HttpResponse(body, content_type="text/vnd.abc; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}.abc"'
        return response
    payload = {
        "title": score.title, "tempo_bpm": score.tempo_bpm,
        "time_signature": score.time_signature, "key": score.key_name,
        "parts": [{"name": p.name, "notes": p.notes} for p in parts],
    }
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{filename}.json"'
    return response


# ---------------------------------------------------------------------------------- learn

@login_required
def learn(request, slug=None):
    """Screen 8: lessons, plus the tutor form (answered by ai_views.tutor_ask)."""
    lesson = lessons.get(slug or "")
    scores = Score.objects.filter(user=request.user)[:20]
    return render(request, "voxscore/learn.html", {
        "active": "learn",
        "lessons": lessons.LESSONS,
        "lesson": lesson,
        "form": TutorForm(initial={"topic": lesson["slug"]}, scores=scores),
        "example_names": [music.midi_to_name(m) for m in lesson["example"]],
    })


# -------------------------------------------------------------------------------- profile

def _accuracy_chart(sessions, width=520, height=160):
    """
    Points for a simple SVG line chart of pitch accuracy per session (oldest left).
    Drawn server-side as an SVG polyline, so the page needs no chart library.
    """
    values = [s.pitch_accuracy for s in sessions if s.pitch_accuracy is not None]
    if len(values) < 2:
        return None
    step = width / (len(values) - 1)
    points = " ".join(f"{i * step:.1f},{height - v / 100 * height:.1f}" for i, v in enumerate(values))
    return {"points": points, "width": width, "height": height,
            "first": values[0], "last": values[-1], "count": len(values)}


@login_required
def profile(request):
    """Screen 9: vocal range, accuracy over time, practice history, saved scores, settings."""
    prof = get_profile(request.user)
    days = _int(request.GET.get("days"), 30, 7, 365)
    since = timezone.now() - timedelta(days=days)
    recent = PracticeSession.objects.filter(user=request.user, created__gte=since)
    if request.method == "POST":
        settings_form = SettingsForm(request.POST)
        if settings_form.is_valid():
            prof.ai_harmony_enabled = settings_form.cleaned_data["ai_harmony_enabled"]
            prof.save(update_fields=["ai_harmony_enabled"])
            flash.success(request, "AI harmony suggestions are now "
                          + ("on." if prof.ai_harmony_enabled else "off."))
            return redirect("profile")
    else:
        settings_form = SettingsForm(initial={"ai_harmony_enabled": prof.ai_harmony_enabled})
    return render(request, "voxscore/profile.html", {
        "active": "profile",
        "profile": prof,
        "days": days,
        "chart": _accuracy_chart(list(recent.order_by("created"))),
        "averages": recent.aggregate(pitch=Avg("pitch_accuracy"), rhythm=Avg("rhythm_accuracy"),
                                     tone=Avg("tone_stability")),
        "history": recent.select_related("warmup")[:15],
        "scores": Score.objects.filter(user=request.user).annotate(n_parts=Count("parts")),
        "settings_form": settings_form,
        "streak": practice_streak(request.user),
    })


@login_required
@require_POST
def range_save(request):
    """POST JSON {low, high} (MIDI) from the range test on the profile page."""
    data = _json_body(request)
    if data is None:
        return _bad("Expected a JSON body.")
    low = _int(data.get("low"), None, music.MIN_MIDI, music.MAX_MIDI)
    high = _int(data.get("high"), None, music.MIN_MIDI, music.MAX_MIDI)
    if low is None or high is None or abs(high - low) < 5:
        return _bad("Sing a low note and a high note at least a few notes apart.")
    prof = get_profile(request.user)
    prof.set_range(low, high)
    prof.save()
    return JsonResponse({"ok": True, "range": prof.range_label,
                         "voice_type": prof.get_voice_type_display()})
