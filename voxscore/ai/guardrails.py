"""
Guardrails around every model call: what goes in, and what is allowed back out.

1. PREPROCESSING (clean_text). Questions and score titles are user-typed: normalise them,
   drop control characters and markup, replace e-mail addresses and links (never useful to a
   music tutor, and they should not leave the machine), and cut to MAX_INPUT_CHARS.

2. INPUT SCREENING (find_injection). Text that tries to talk to the model ("ignore previous
   instructions", chat-template tokens, "you are now...") is refused before any model sees it.

3. OUTPUT VALIDATION (parse_json_object + validate_*). Models break their output format: prose
   around the JSON, code fences, notes outside the human voice, a 500-word "tip". Output is
   parsed leniently, then validated strictly; anything that does not validate is replaced by
   the rule-based fallback, so a broken model answer can never reach the page or the database.
"""

import json
import re
import unicodedata

from .. import music

MAX_INPUT_CHARS = 600
MAX_ANSWER_CHARS = 1500
MAX_TIP_CHARS = 200
MAX_TIPS = 3

_TAG_RE = re.compile(r"<[^>]{0,500}>")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def clean_text(text, max_chars=MAX_INPUT_CHARS):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = "".join(ch for ch in text if ch in "\n\t " or unicodedata.category(ch)[0] != "C")
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub("[link]", text)
    text = _EMAIL_RE.sub("[email]", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + " ..."
    return text


_INJECTION_PATTERNS = [
    (r"\b(ignore|disregard|forget)\b.{0,40}\b(instructions?|prompts?|rules|above|previous)\b",
     "asks the model to ignore its instructions"),
    (r"\b(system|developer)\s+(prompt|message|mode)\b", "mentions the system prompt"),
    (r"\byou are (now|no longer)\b", "tries to give the model a new role"),
    (r"\b(act|pretend|roleplay) as\b", "tries to give the model a new role"),
    (r"\bjailbreak|\bdo anything now\b", "known jailbreak wording"),
    (r"<\|?(im_start|im_end|system|assistant|user|endoftext|eot_id)\|?>", "chat-template token"),
    (r"\[/?INST\]|<<SYS>>|###\s*(instruction|system)", "chat-template token"),
    (r"\b(reveal|print|show|repeat)\b.{0,30}\b(prompt|instructions|api key|secret)\b",
     "asks for hidden instructions or secrets"),
]
_INJECTION_RES = [(re.compile(p, re.IGNORECASE | re.DOTALL), why) for p, why in _INJECTION_PATTERNS]


def find_injection(text):
    """The reasons `text` looks like a prompt-injection attempt; an empty list if it does not."""
    reasons = []
    for pattern, why in _INJECTION_RES:
        if pattern.search(text or "") and why not in reasons:
            reasons.append(why)
    return reasons


_FENCE_RE = re.compile(r"```(?:json)?", re.IGNORECASE)


def parse_json_object(text):
    """The first JSON object found in a model's reply, or None (lenient on purpose)."""
    if not text:
        return None
    text = _FENCE_RE.sub("", str(text))
    start = text.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start:i + 1])
                    except ValueError:
                        break
                    return value if isinstance(value, dict) else None
        start = text.find("{", start + 1)
    return None


def _short(value, limit):
    if not isinstance(value, str):
        return ""
    value = _SPACE_RE.sub(" ", value).strip()
    if len(value) > limit:
        value = value[:limit].rsplit(" ", 1)[0] + "..."
    return value


def validate_answer(text):
    """A tutor answer: plain text, non-empty, capped. None if unusable."""
    answer = _short(text, MAX_ANSWER_CHARS)
    return answer or None


def validate_coach(obj):
    """A clean {"summary", "tips": [str, ...]} dict, or None."""
    if not isinstance(obj, dict):
        return None
    summary = _short(obj.get("summary"), 300)
    tips = obj.get("tips")
    if not summary or not isinstance(tips, list):
        return None
    tips = [_short(t, MAX_TIP_CHARS) for t in tips if isinstance(t, str)]
    tips = [t for t in tips if t][:MAX_TIPS]
    if not tips:
        return None
    return {"summary": summary, "tips": tips}


def validate_harmony(obj, melody, low=36, high=84):
    """
    A harmony part the app can safely save, or None.

    The model must return {"notes": [...]} with exactly one note per melody note, at the same
    start and duration (so the part lines up), each within the given voice range and no more
    than an octave and a half from the melody note it harmonises.
    """
    if not isinstance(obj, dict) or not isinstance(obj.get("notes"), list):
        return None
    try:
        notes = music.validate_notes(obj["notes"])
    except ValueError:
        return None
    if len(notes) != len(melody):
        return None
    for h, m in zip(notes, sorted(melody, key=lambda n: n["start"])):
        if abs(h["start"] - m["start"]) > 1e-3 or abs(h["dur"] - m["dur"]) > 1e-3:
            return None
        if not low <= h["midi"] <= high or abs(h["midi"] - m["midi"]) > 18:
            return None
    return notes
