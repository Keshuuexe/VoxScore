# VoxScore

**Train your voice, score your songs.** INFO 490 startup project by Keshav Arya.

VoxScore is an all-in-one web app for singers: a tuner with live pitch, rhythm and tone feedback,
a metronome, tuning drones, a warmup library from a cappella, Western, Indian classical and
other traditions, and a Studio that turns a sung melody into sheet music you can edit and build
into an arrangement. An AI theory tutor and practice coach help along the way, and AI harmony
suggestions are available as an **optional** feature that is off by default.

- Django project: `voxsite` (settings, URLs)
- Django app: `voxscore` (models, views, music logic, AI layer)
- Built with the same structure as Unopsis: split settings, secrets in `.env`, a committed
  seeded `db.sqlite3`, an `ai/` package with guardrails and fallbacks, and GitHub Actions CI.

---

## Setup

Requires **Python 3.11+**.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Mac / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your local .env (git-ignored, never committed)
copy .env.example .env            # Windows
# cp .env.example .env            # Mac / Linux
#    then replace SECRET_KEY with a fresh value:
python -c "import secrets; print(secrets.token_urlsafe(50))"

# 4. The database is already in the repo (warmup library + demo account). Apply any newer migrations:
python manage.py migrate

# 5. Run it
python manage.py runserver
```

Open http://127.0.0.1:8000/ and log in with the demo account, or create your own:

| Username | Password |
|---|---|
| `demo` | `voxscore-demo` |

`python manage.py seed_demo` resets the demo account at any time.

> **Microphone:** browsers only allow the microphone on `https://` sites or on `localhost` /
> `127.0.0.1`. Use one of those addresses when testing locally.

---

## The screens (from the wireframes)

| # | Screen | URL | What works |
|---|---|---|---|
| 1 | Log in / Sign up | `/accounts/login/`, `/accounts/signup/` | Django auth with VoxScore's templates; sign-up creates a profile and logs in |
| 2 | Dashboard | `/dashboard/` | Practice and Studio cards, recent work, practice streak, quick tuner |
| 3 | Practice: Tuner | `/practice/` | Live note + cents needle, pitch/rhythm/tone bars, metronome, drone, note player; saves the session and offers AI coach tips |
| 4 | Warmup library | `/practice/warmups/` | 11 warmups, search, filter by tradition and focus |
| 5 | Warmup session | `/practice/warmups/<slug>/` | Plays each step, transposed to your range; live pitch line vs target notes; scores against the targets |
| 6 | Studio: Record | `/studio/` | Tempo, meter, key, count-in; records against the click and draws the pitch trace on the beat grid |
| 7 | Score editor | `/studio/<id>/` | Sheet music (abcjs), play back, edit note pitch/length, undo/redo, record more parts, export; optional AI harmony panel |
| 8 | Learn | `/learn/<topic>/` | 7 short lessons with playable examples; AI tutor that can use your own recordings |
| 9 | Profile | `/profile/` | Range test and voice type, accuracy chart, practice history, saved scores, AI settings |

---

## How the sing-to-sheet-music pipeline works

1. **Browser** (`static/js/audio.js`): the Web Audio API reads the microphone and an
   autocorrelation pitch detector produces a frame about every 33 ms: `{"t": seconds, "f": Hz}`.
   Only these numbers are sent to the server, never audio.
2. **Server** (`voxscore/music.py`):
   - `frames_to_notes()` groups frames into held notes (ignoring one-frame glitches), takes the
     median pitch, removes the count-in, and snaps each note to a sixteenth-note grid.
   - `estimate_key()` finds the key with the Krumhansl–Schmuckler key profiles.
   - `notes_to_abc()` writes ABC notation: rests in gaps, ties across bar lines, explicit
     accidentals, and the key signature.
3. **Browser** again: [abcjs](https://www.abcjs.net/) draws the ABC as sheet music.

Everything in `music.py` is plain Python and covered by `voxscore/tests_music.py`.

---

## AI features

See **[README_AI.md](README_AI.md)** for the full design. In short:

| Feature | Where | Model | Fallback |
|---|---|---|---|
| Theory tutor | Learn | Groq (`openai/gpt-oss-20b`), then optional local HF model | The lesson's built-in tip |
| Practice coach | After a tuner or warmup session | Groq | Rule-based tips for the weakest score |
| Harmony suggestions (**optional, off by default**) | Score editor | Groq | A diatonic third below the melody |

To turn the AI on, add a free Groq key from https://console.groq.com/keys to `.env`:

```
GROQ_API_KEY=your-key-here
```

Without a key, every feature still works using its fallback, and the page says so.

---

## Project structure

```
VoxScore/
├── manage.py
├── requirements.txt            # Django, django-environ, requests
├── requirements-ai.txt         # optional: torch + transformers for the local model
├── .env.example                # copy to .env
├── db.sqlite3                  # committed: warmup library + demo account
├── voxsite/                    # the Django project
│   ├── settings/{base,development,production}.py
│   ├── secrets_environment.py  # reads .env
│   └── urls.py, wsgi.py, asgi.py
├── voxscore/                   # the app
│   ├── models.py               # Profile, WarmupExercise, PracticeSession, Score, Part, AIEvent
│   ├── music.py                # pitch, transcription, key, ABC, scoring, harmony rule
│   ├── lessons.py              # Learn content
│   ├── views.py                # screens 2-9 + JSON endpoints
│   ├── auth_views.py           # screen 1
│   ├── ai_views.py             # tutor, coach, harmony
│   ├── ai/                     # groq_client, local_llm, guardrails, prompts, tutor, coach, harmony, telemetry
│   ├── management/commands/seed_demo.py
│   ├── migrations/             # 0002 seeds the warmup library
│   └── tests.py, tests_music.py, tests_ai.py
├── templates/                  # base.html, registration/, voxscore/
├── static/                     # css/voxscore.css, js/{audio,tuner,warmup,recorder,editor,profile}.js, img/
└── .github/workflows/ci.yml
```

## Tests and CI

```bash
python manage.py test                                         # 68 tests, run offline
python manage.py check --settings=voxsite.settings.production
```

GitHub Actions runs both checks, the tests, a missing-migrations check and `collectstatic` on
every push and pull request to `main`. It also fails if `.env` is committed or `db.sqlite3` is missing.

## Deploying to PythonAnywhere

1. Clone the repo, create a virtualenv and `pip install -r requirements.txt` (not `requirements-ai.txt`).
2. Create `.env` with a new `SECRET_KEY`, `ALLOWED_HOSTS=<you>.pythonanywhere.com`, and optionally `GROQ_API_KEY`.
3. In the Web tab, point the WSGI file at `voxsite.wsgi` (it uses production settings), set the
   static files mapping `/static/` → `<repo>/staticfiles`, then run
   `python manage.py collectstatic --settings=voxsite.settings.production`.

## Known limits of this first version

- Transcription handles **one voice at a time** (build arrangements part by part).
- The "tone" score measures pitch steadiness on held notes, a simple first stand-in for tone quality.
- Editing is note by note through the note strip; dragging notes on the staff is a future step.
- Export is ABC and JSON. MuseScore can import ABC with a plugin; MusicXML export is a future step.
