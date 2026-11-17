"""
AI feature 1: the music theory tutor (Learn screen, wireframe screen 8).

Order: clean -> screen for prompt injection -> Groq -> local model (if enabled) -> the
lesson's built-in answer. Always returns a dict and never raises:

    {"answer": str, "source": "groq" | "local" | "rules" | "refused",
     "model": str, "note": str}
"""

from .. import lessons, music
from . import groq_client, guardrails, local_llm, prompts


def recording_context(score):
    """What the tutor is told about one of the user's own scores (first part only)."""
    part = score.parts.filter(pending=False).first() if score else None
    if part is None:
        return None
    return {
        "title": guardrails.clean_text(score.title, 80),
        "key": score.key_name,
        "tempo": score.tempo_bpm,
        "notes": music.describe_notes(part.notes, flats=music.key_uses_flats(score.key_name)),
    }


def answer(question, topic_slug="", score=None):
    lesson = lessons.get(topic_slug)
    cleaned = guardrails.clean_text(question)
    if not cleaned:
        return {"answer": "", "source": "refused", "model": "", "note": "Type a question first."}
    reasons = guardrails.find_injection(cleaned)
    if reasons:
        return {"answer": "", "source": "refused", "model": "",
                "note": "That looks like an attempt to give the tutor instructions ("
                        + ", ".join(reasons) + "), so it wasn't answered."}

    chat = prompts.build_tutor_messages(cleaned, lesson["title"], recording_context(score))
    notes = []
    try:
        reply = groq_client.chat(chat, max_tokens=400)
        text = guardrails.validate_answer(reply["text"])
        if text:
            return {"answer": text, "source": "groq", "model": reply["model"], "note": ""}
        notes.append("Groq's answer was empty.")
    except groq_client.GroqUnavailable as exc:
        notes.append(str(exc))

    if local_llm.is_enabled():
        try:
            text = guardrails.validate_answer(local_llm.generate(chat))
            if text:
                return {"answer": text, "source": "local", "model": local_llm.model_name(),
                        "note": " ".join(notes)}
        except local_llm.LocalModelUnavailable as exc:
            notes.append(str(exc))
        except Exception as exc:  # a generation error must not become a 500
            notes.append(f"Local model error: {exc.__class__.__name__}")

    return {"answer": lesson["fallback"], "source": "rules", "model": "",
            "note": "No AI model was available, so this is the lesson's built-in tip. "
                    + " ".join(notes)}
