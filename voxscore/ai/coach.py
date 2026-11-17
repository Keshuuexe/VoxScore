"""
AI feature 2: the practice coach. After a session, the user can ask for a short summary and
tips based on that session's pitch, rhythm and tone scores.

Only numbers go to the model (no audio, no personal data). Groq writes; if it cannot, or its
JSON does not validate, the rule-based coach below answers instead.
"""

from . import groq_client, guardrails, prompts

TIPS = {
    "pitch": [
        "Sing along with the drone first and listen for the 'beating' sound to stop.",
        "Slow down: hold each note for two beats and watch the tuner needle settle.",
        "Hum the note before singing it on a vowel, then keep the same placement.",
    ],
    "rhythm": [
        "Clap the rhythm with the metronome before singing it.",
        "Turn on the count-in and start breathing on beat 4 of the count-in bar.",
        "Lower the tempo by 10 BPM until every note lands on the click.",
    ],
    "tone": [
        "Support long notes with steady breath from the belly, not the throat.",
        "Try lip trills on the same pattern to even out your airflow.",
        "Keep the vowel shape the same for the whole note.",
    ],
}


def _stats(session):
    return {
        "Activity": session.get_kind_display()
        + (f" ({session.warmup.name})" if session.warmup_id else ""),
        "Duration (seconds)": session.seconds,
        "Pitch accuracy": session.pitch_accuracy,
        "Rhythm accuracy": session.rhythm_accuracy,
        "Tone stability": session.tone_stability,
    }


def rule_based(session):
    scores = {
        "pitch": session.pitch_accuracy, "rhythm": session.rhythm_accuracy,
        "tone": session.tone_stability,
    }
    known = {k: v for k, v in scores.items() if v is not None}
    if not known:
        return {"summary": "No singing was detected in this session.",
                "tips": ["Check the microphone permission, then sing a little louder."]}
    weakest = min(known, key=known.get)
    best = max(known, key=known.get)
    summary = (f"Your strongest area was {best} ({known[best]:.0f}%). "
               f"Focus next on {weakest} ({known[weakest]:.0f}%).")
    return {"summary": summary, "tips": TIPS[weakest][:2]}


def feedback(session):
    """{"summary", "tips", "source", "model"} for one PracticeSession. Never raises."""
    try:
        reply = groq_client.chat(prompts.build_coach_messages(_stats(session)), max_tokens=300)
        result = guardrails.validate_coach(guardrails.parse_json_object(reply["text"]))
        if result:
            return {**result, "source": "groq", "model": reply["model"]}
    except groq_client.GroqUnavailable:
        pass
    return {**rule_based(session), "source": "rules", "model": ""}
