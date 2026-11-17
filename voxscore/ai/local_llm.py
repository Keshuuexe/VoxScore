"""
An optional local Hugging Face model, same pattern as Unopsis's local_llm.py.

Off by default (AI_LOCAL_ENABLED=False). When switched on, the model named by
settings.AI_LOCAL_MODEL is loaded with `transformers` the first time a request needs it; the
first load downloads the weights into the Hugging Face cache (never into the repository).

Why lazy: importing torch costs seconds and hundreds of MB, and PythonAnywhere's free plan
cannot hold it at all. The import happens inside _load(); if torch/transformers are missing,
LocalModelUnavailable is raised and the caller falls back to Groq or the rules.
"""

import threading

from django.conf import settings


class LocalModelUnavailable(Exception):
    """torch/transformers are not installed, local AI is switched off, or the load failed."""


_lock = threading.Lock()
_loaded = {}  # {"name", "tokenizer", "model", "device"}


def model_name():
    return getattr(settings, "AI_LOCAL_MODEL", "ibm-granite/granite-3.3-2b-instruct")


def is_enabled():
    return bool(getattr(settings, "AI_LOCAL_ENABLED", False))


def is_loaded():
    return bool(_loaded)


def _load():
    if not is_enabled():
        raise LocalModelUnavailable("Local AI is switched off (AI_LOCAL_ENABLED=False).")
    if _loaded:
        return _loaded
    with _lock:
        if _loaded:
            return _loaded
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise LocalModelUnavailable(
                "torch and transformers are not installed (pip install -r requirements-ai.txt)."
            ) from exc

        name = model_name()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        cpu_dtype = getattr(torch, getattr(settings, "AI_LOCAL_CPU_DTYPE", "bfloat16"), torch.bfloat16)
        dtype = torch.float16 if device == "cuda" else cpu_dtype
        try:
            tokenizer = AutoTokenizer.from_pretrained(name)
            model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=dtype)
        except Exception as exc:  # network down, wrong name, out of memory...
            raise LocalModelUnavailable(f"Could not load {name}: {exc}") from exc
        model.to(device)
        model.eval()
        _loaded.update(name=name, tokenizer=tokenizer, model=model, device=device)
        return _loaded


def generate(chat, max_new_tokens=None, max_seconds=None):
    """Run one chat through the local model and return the reply text (greedy decoding)."""
    loaded = _load()
    import torch

    tokenizer, model = loaded["tokenizer"], loaded["model"]
    inputs = tokenizer.apply_chat_template(
        chat, add_generation_prompt=True, return_tensors="pt", return_dict=True,
        enable_thinking=False,
    ).to(loaded["device"])
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens or getattr(settings, "AI_LOCAL_MAX_NEW_TOKENS", 220),
            do_sample=False,
            max_time=max_seconds or getattr(settings, "AI_LOCAL_MAX_SECONDS", 60),
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
