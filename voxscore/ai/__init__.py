"""
The AI layer of VoxScore, built the same way as Unopsis's.

    guardrails.py   cleaning, prompt-injection screening, JSON parsing and validation
    prompts.py      every prompt in one place (tutor, coach, harmony)
    groq_client.py  the external API (Groq, OpenAI-compatible chat completions)
    local_llm.py    an optional local Hugging Face model, loaded lazily with `transformers`
    tutor.py        AI feature 1: the music theory tutor (Learn screen)
    coach.py        AI feature 2: the practice coach (session summary with tips)
    harmony.py      AI feature 3, OPTIONAL and off by default: harmony part suggestions
    telemetry.py    one AIEvent row per request

Every feature follows the same order: clean the input, screen it, call Groq, try the local
model if enabled, validate the answer, and fall back to a rule-based answer if anything fails.
So the site never shows an error page because a model was slow, missing or wrong.

Nothing here imports torch at start-up. The local model is only loaded on the first request
that needs it, and only if AI_LOCAL_ENABLED=True, so `manage.py check`, the tests and a
PythonAnywhere deployment all work without it. See README_AI.md.
"""
