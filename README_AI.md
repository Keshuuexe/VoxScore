# VoxScore: AI features

VoxScore's AI layer (`voxscore/ai/`) follows the same pattern as Unopsis: an external API
(Groq) for writing, an optional local Hugging Face model loaded lazily, strict guardrails on
everything that goes in and comes out, and a rule-based fallback so a missing key, a slow
network or a bad model answer never becomes an error page.

| Module | Job |
|---|---|
| `groq_client.py` | One `chat()` call to Groq's OpenAI-compatible API with `requests`; one exception type (`GroqUnavailable`) |
| `local_llm.py` | Optional local model (`AI_LOCAL_ENABLED=True` + `requirements-ai.txt`); imports torch only on first use |
| `guardrails.py` | `clean_text`, `find_injection`, `parse_json_object`, `validate_answer/coach/harmony` |
| `prompts.py` | All prompts in one file |
| `tutor.py`, `coach.py`, `harmony.py` | The three features |
| `telemetry.py` | One `AIEvent` row per request (feature, source, model, latency), even on failure |

## Feature 1: Theory tutor (Learn screen)

- **Input:** the user's question, the current lesson, and optionally one of their own scores.
  For a score, only a short text summary is sent (`"G4 (1 beat), A4 (0.5 beat), ..."`, the key
  and the tempo), never audio.
- **Order:** clean → screen for prompt injection (refused before any model sees it) → Groq →
  local model if enabled → the lesson's built-in tip.
- The question is wrapped in `<question>` tags and the system prompt says to treat it as data.

## Feature 2: Practice coach (after a tuner or warmup session)

- **Input:** numbers only: activity, duration, pitch accuracy, rhythm accuracy, tone stability.
- **Output:** strict JSON `{"summary": "...", "tips": ["...", "..."]}`, validated (1–3 tips,
  each capped in length).
- **Fallback:** rule-based tips aimed at the weakest score.

## Feature 3: Harmony suggestions (optional, off by default)

AI-written harmony is a sensitive topic for musicians, so this feature is opt-in and advisory:

- It only runs when the user turns it on in **Profile → Settings** (`Profile.ai_harmony_enabled`, default `False`).
- It only **suggests**: the result is saved as a *pending* part with **Accept** and **Reject**.
  The user's own parts are never changed.
- `validate_harmony()` checks that the AI returned exactly one note per melody note with the
  same start and length, inside the chosen voice's range, and no more than 18 semitones from the
  melody note. Anything else is discarded.
- **Fallback:** `music.harmony_line()`, a diatonic third below the melody in the score's key.

## Guardrails summary

| Risk | Guardrail |
|---|---|
| Prompt injection in a question | `find_injection()` refuses it; the view returns 400 and records `source="refused"` |
| Personal data leaving the machine | `clean_text()` replaces emails and links; audio is never uploaded |
| Malformed model output | Lenient `parse_json_object()`, then strict `validate_*()`; invalid → fallback |
| Cost / abuse | `AI_REQUESTS_PER_MINUTE` per account (default 10), returns 429 |
| Reading another user's data | Every query is filtered by `request.user`; tested in `OwnershipTests` |
| No key / no network / no torch | Every feature has a deterministic fallback, and the page says which source answered |

## Configuration (`.env`)

```
GROQ_API_KEY=                     # free key from https://console.groq.com/keys
GROQ_MODEL=openai/gpt-oss-20b
AI_LOCAL_ENABLED=False            # True needs: pip install -r requirements-ai.txt
AI_LOCAL_MODEL=ibm-granite/granite-3.3-2b-instruct
AI_REQUESTS_PER_MINUTE=10
```

## Tests

`voxscore/tests_ai.py` patches `groq_client.chat`, so no test calls the network. It covers the
guardrails, every fallback path, the off-by-default harmony switch, accept/reject, telemetry,
rate limiting and ownership.

## Next steps

- An evaluation set of theory questions with expected answers, to compare Groq with the local model.
- A harmony quality check (parallel fifths and octaves, voice crossing) before showing a suggestion.
- An `/analytics/` page built on `AIEvent`, as in Unopsis.
