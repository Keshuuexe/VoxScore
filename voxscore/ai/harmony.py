"""
AI feature 3 (OPTIONAL, off by default): harmony part suggestions in the Score editor.

AI-written harmony is a sensitive topic for musicians, so this feature:
  * only runs if the user has switched it on (Profile.ai_harmony_enabled),
  * only ever SUGGESTS: the result is saved as a pending Part the user must accept or reject,
  * never changes the user's own parts.

Groq writes the part as strict JSON; guardrails.validate_harmony() checks that it lines up
note-for-note with the melody and stays in range. If anything fails, music.harmony_line()
(a diatonic third below) is suggested instead, and the page says so.
"""

from .. import music
from . import groq_client, guardrails, prompts

VOICES = {
    # name: (low, high) MIDI
    "alto": (53, 74),
    "tenor": (48, 69),
    "bass": (40, 62),
}


def suggest(melody_part, voice="alto"):
    """{"notes", "source", "model", "note"} for a harmony under `melody_part`. Never raises."""
    score = melody_part.score
    melody = sorted(melody_part.notes, key=lambda n: n["start"])
    low, high = VOICES.get(voice, VOICES["alto"])
    key_name = score.key_name or music.estimate_key(melody)
    note = ""
    if not melody:
        return {"notes": [], "source": "rules", "model": "", "note": "The melody has no notes yet."}
    if len(melody) > 120:
        note = "The melody is long, so the simple harmony rule was used instead of the AI."
    else:
        try:
            reply = groq_client.chat(
                prompts.build_harmony_messages(melody, key_name, voice, low, high),
                max_tokens=1500, temperature=0.2,
            )
            notes = guardrails.validate_harmony(guardrails.parse_json_object(reply["text"]),
                                                melody, low, high)
            if notes:
                return {"notes": notes, "source": "groq", "model": reply["model"], "note": ""}
            note = "The AI's harmony didn't line up with the melody, so a simple third below was used."
        except groq_client.GroqUnavailable as exc:
            note = f"{exc} A simple third below the melody was used instead."
    return {"notes": music.harmony_line(melody, key_name), "source": "rules", "model": "",
            "note": note}
