"""Gemini-powered text: the parent circular and the assistant.

The backend decides the facts (AQI, decisions, GRAP stage); Gemini only words
them. Output is checked for the right scripts, and there is always a fallback.
"""

import json
import os
import re
import threading
import time
import unicodedata

from cachetools import TTLCache

from services.advisory import grap_stage

# Tried in order. Chosen by testing on 8 Oct 2026: gemini-3.5-flash gave clean
# Hindi/Punjabi reliably; the "latest" alias was often overloaded (503/504);
# the lite model is fast but sometimes mixes scripts (the check below rejects that).
MODELS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]

# Unicode blocks for each language. Latin is allowed everywhere for "AQI", "PE",
# "GRAP" and names; the danda (।) lives in the Devanagari block but is also used
# in Punjabi.
DEVANAGARI = (0x0900, 0x097F)
GURMUKHI = (0x0A00, 0x0A7F)
DANDA = {"\u0964", "\u0965"}


def _foreign_letters(text, block=None, extra=frozenset()):
    """Letters/marks outside Latin and `block`. Catches mixed-in Hindi, Gujarati,
    Arabic, Hebrew, Korean… which models occasionally produce."""
    bad = set()
    for ch in text:
        if not unicodedata.category(ch)[0] in "LM":
            continue
        code = ord(ch)
        if code < 0x0250 or ch in extra:  # Basic Latin + Latin-1/Extended (é, ñ…)
            continue
        if block and block[0] <= code <= block[1]:
            continue
        bad.add(ch)
    return bad


def _has_letters_in(text, block):
    return any(block[0] <= ord(ch) <= block[1] for ch in text)


# English terms allowed inside the Hindi/Punjabi versions.
LATIN_OK = {"AQI", "PE", "PM", "PM2", "PM10", "GRAP", "I", "II", "III", "IV", "N95"}
MAX_LATIN_SHARE = 0.15  # leaves room for a school name kept in English


def _latin_share(text):
    """Share of letters in English words other than LATIN_OK (e.g. 'Dear Parents')."""
    letters = sum(1 for ch in text if unicodedata.category(ch)[0] in "LM")
    latin = sum(len(w) for w in re.findall(r"[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*", text)
                if w.upper() not in LATIN_OK)
    return latin / letters if letters else 1.0


CIRCULAR_SCHEMA = {
    "type": "object",
    "properties": {
        "en": {"type": "string"},
        "hi": {"type": "string"},
        "pa": {"type": "string"},
    },
    "required": ["en", "hi", "pa"],
}

_circular_cache = TTLCache(maxsize=200, ttl=1800)
_cache_lock = threading.Lock()
_client = None

# Stop trying further fallback models after this long, so a request stays
# under AWS API Gateway's 29 s limit and the user gets the friendly fallback.
CHAIN_DEADLINE_S = 20


class AIUnavailable(Exception):
    """No model produced a usable answer."""


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise AIUnavailable("GEMINI_API_KEY is not set")
        from google import genai
        from google.genai import types
        # One attempt per model; we fall back to another model instead of waiting.
        _client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=15_000, retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
    return _client


def _models():
    """GEMINI_MODEL (if set) goes first, then the defaults."""
    override = os.getenv("GEMINI_MODEL")
    return [override] + [m for m in MODELS if m != override] if override else list(MODELS)


# ---------- circular ----------

SEVERITY = ["go", "caution", "limit", "cancel"]

# How serious the day is overall, so the notice and its tips stay proportionate.
OVERALL = {
    "go": "No change to the normal schedule.",
    "caution": "Normal schedule, with extra care for children with asthma or breathing problems.",
    "limit": "Some outdoor activities move indoors or are shortened.",
    "cancel": "Outdoor activities are cancelled.",
}


def _hour_12(hhmm):
    hour = int(hhmm[:2])
    suffix = "am" if hour < 12 else "pm"
    return f"{(hour % 12) or 12}:{hhmm[3:]} {suffix}"


def circular_facts(day, school_name):
    """The only facts the notice may state, derived from the School Mode plan."""
    slots = [s for s in day["slots"] if s["aqi"] is not None]
    worst = max((s["aqi"] for s in slots), default=None)
    strictest = max((s["decision"] for s in slots), key=SEVERITY.index, default="go")
    return {
        "school_name": school_name.strip() or "Our school",
        "date": day["date"],
        "worst_aqi": worst,
        # Use School Mode's day-average GRAP stage when present.
        "grap_stage": day["grap_stage"] if "grap_stage" in day else (grap_stage(worst) if worst is not None else None),
        "overall": OVERALL[strictest],
        "severity": strictest,
        "activities": [
            {
                "activity": s["label"],
                "time": _hour_12(s["time"]),
                "forecast_aqi": s["aqi"],
                "air_quality": s["category"],
                "decision": s["verdict"],
                "guidance": s["advice"],
            }
            for s in slots
        ],
    }


TIP_GUIDE = {
    "go": "reassuring tips, e.g. keep an eye on children who cough or wheeze",
    "caution": "gentle tips, e.g. children with asthma should carry their inhaler and take it easy",
    "limit": "practical tips, e.g. a well-fitted mask for the journey, a water bottle, limit outdoor play after school",
    "cancel": "firm tips, e.g. N95 masks outdoors, keep children indoors after school, watch for breathing problems",
}


def _circular_prompt(facts):
    return (
        "You write warm, clear notices from Indian schools to parents about air quality.\n"
        "Write ONE notice using ONLY the facts below. Never invent numbers, dates, "
        "activities, events or policies.\n"
        "Format, with line breaks between parts:\n"
        "1. A greeting to parents.\n"
        "2. One opening sentence with the date and the overall plan (see 'overall').\n"
        "3. One short line per activity, in natural language: what happens and why, "
        "mentioning its AQI. Do not copy the 'guidance' text word for word.\n"
        f"4. Two tips for parents, matching how serious the day is: {TIP_GUIDE[facts['severity']]}.\n"
        "5. Sign-off: 'Principal, <school name>'.\n"
        "Keep it under 110 words, calm and not alarmist. Mention the GRAP stage "
        "only if it is not null.\n"
        "Return JSON with three versions of the same notice. Each must read naturally "
        "to a parent who only reads that language:\n"
        "- en: English. Greeting 'Dear Parents,'; dates like '9 October 2026'; times like '8:00 am'.\n"
        "- hi: Hindi, entirely in Devanagari. Greeting 'प्रिय अभिभावकगण,'; Hindi month "
        "names (e.g. '9 अक्टूबर 2026'); times like 'सुबह 8 बजे', 'दोपहर 2 बजे'.\n"
        "- pa: Punjabi, entirely in Gurmukhi (never Shahmukhi or Devanagari). Greeting "
        "'ਪਿਆਰੇ ਮਾਪਿਓ,'; Punjabi month names (e.g. '9 ਅਕਤੂਬਰ 2026'); times like "
        "'ਸਵੇਰੇ 8 ਵਜੇ', 'ਦੁਪਹਿਰ 2 ਵਜੇ'.\n"
        "In hi and pa, the only English words allowed are 'AQI', 'PE' and 'GRAP'; "
        "write the school name in that language's script. Use Western digits (0-9).\n\n"
        f"FACTS:\n{json.dumps(facts, ensure_ascii=False, indent=1)}"
    )


def _scripts_ok(notice):
    """Each version must be written entirely in its own script (plus Latin)."""
    en, hi, pa = (notice.get(k) or "" for k in ("en", "hi", "pa"))
    return (
        bool(en) and not _foreign_letters(en)
        and _has_letters_in(hi, DEVANAGARI) and not _foreign_letters(hi, DEVANAGARI)
        and _has_letters_in(pa, GURMUKHI) and not _foreign_letters(pa, GURMUKHI, DANDA)
        and _latin_share(hi) <= MAX_LATIN_SHARE and _latin_share(pa) <= MAX_LATIN_SHARE
    )


def template_circular(facts):
    """English-only notice used when Gemini is unavailable."""
    lines = [f"Dear Parents,", ""]
    if facts["worst_aqi"] is not None:
        stage = f", GRAP Stage {facts['grap_stage']}" if facts["grap_stage"] else ""
        lines.append(
            f"The air quality forecast for {facts['date']} shows AQI up to "
            f"{facts['worst_aqi']}{stage}. To protect children's health:"
        )
        for a in facts["activities"]:
            lines.append(f"- {a['activity']} ({a['time']}): {a['decision']}. {a['guidance']}")
    lines += [
        "",
        "Please send your child with a well-fitted mask and a water bottle, and "
        "limit outdoor play after school.",
        "",
        f"Principal, {facts['school_name']}",
    ]
    return "\n".join(lines)


def generate_circular(facts):
    """Returns {en, hi, pa, model, fallback}. Never raises for model problems."""
    cache_key = json.dumps(facts, sort_keys=True, ensure_ascii=False)
    with _cache_lock:
        hit = _circular_cache.get(cache_key)
    if hit is not None:
        return hit

    errors = []
    try:
        client = _get_client()
        from google.genai import types
        started = time.monotonic()
        for model in _models():
            if time.monotonic() - started > CHAIN_DEADLINE_S:
                errors.append(f"{model}: skipped, out of time")
                break
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=_circular_prompt(facts),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CIRCULAR_SCHEMA,
                        temperature=0.3,
                    ),
                )
                notice = json.loads(res.text)
                if not _scripts_ok(notice):
                    errors.append(f"{model}: wrong script in output")
                    continue
                result = {**{k: notice[k].strip() for k in ("en", "hi", "pa")},
                          "model": res.model_version or model, "fallback": False}
                with _cache_lock:
                    _circular_cache[cache_key] = result
                # Earlier models' failures are still worth logging.
                return {**result, "errors": errors} if errors else result
            except Exception as exc:  # API errors, bad JSON, timeouts
                errors.append(f"{model}: {str(exc)[:120]}")
    except AIUnavailable as exc:
        errors.append(str(exc))

    return {
        "en": template_circular(facts), "hi": None, "pa": None,
        "model": None, "fallback": True, "errors": errors,
    }


# ---------- assistant ----------

MAX_HISTORY = 10
MAX_MESSAGE_CHARS = 500

ASSISTANT_RULES = """You are UrbanWise, a friendly air-quality assistant for Indian cities.
Answer the user's question using ONLY the DATA below (live data for their city).

Rules:
- Quote the relevant numbers (AQI, times, fire counts) from the DATA. Never invent
  numbers, places, events or forecasts that are not in the DATA.
- If the DATA cannot answer the question, say so briefly and suggest what it can tell them.
- AQI is on India's CPCB scale: 0-50 Good, 51-100 Satisfactory, 101-200 Moderate,
  201-300 Poor, 301-400 Very Poor, 401-500 Severe.
- Exposure rule of thumb (Berkeley Earth): breathing 22 µg/m³ of PM2.5 for 24 hours
  ≈ 1 cigarette. Exercise roughly doubles to quadruples how much is inhaled.
- Smoke Trail results are likely contributing sources, not exact shares; say "likely".
- incoming_smoke_next_48h predicts smoke from current fires reaching the city. Times
  are UTC; convert to the city's local time (India is UTC+5:30) and say "around".
- Give practical, proportionate advice. Do not diagnose or give medical treatment.
  Only if the user mentions symptoms or a health condition, suggest seeing a doctor.
- Reply in the same language as the user's latest message (English, Hindi in
  Devanagari, or Punjabi in Gurmukhi). Write Hindi and Punjabi entirely in their own
  script; only "AQI", "PM2.5", "PM10" and "GRAP" may stay in English letters.
- Keep it short: at most 4 sentences, or a few lines starting with "• ".
  Plain text only, no markdown (no **, #, or tables).
- Only discuss air quality, weather-related health and the UrbanWise features.
  Politely decline anything else."""


def clean_history(history):
    """Keep the last MAX_HISTORY well-formed turns; drop anything else."""
    turns = []
    for t in history if isinstance(history, list) else []:
        if not isinstance(t, dict) or t.get("role") not in ("user", "assistant"):
            continue
        text = str(t.get("text") or "").strip()[:1000]
        if text:
            turns.append({"role": t["role"], "text": text})
    return turns[-MAX_HISTORY:]


def _strip_markdown(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)       # **bold**
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)  # headings
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.M)  # bullets
    return text.strip()


def reply_language(message):
    """Which script the reply should be in, judged from the user's message."""
    if _has_letters_in(message, GURMUKHI):
        return "pa"
    if _has_letters_in(message, DEVANAGARI):
        return "hi"
    return None  # English or mixed: no script check


def _reply_script_ok(reply, language):
    if language == "pa":
        return not _foreign_letters(reply, GURMUKHI, DANDA) and _latin_share(reply) <= MAX_LATIN_SHARE
    if language == "hi":
        return not _foreign_letters(reply, DEVANAGARI) and _latin_share(reply) <= MAX_LATIN_SHARE
    return True


def _was_cut_off(res):
    candidates = getattr(res, "candidates", None) or []
    reason = getattr(candidates[0], "finish_reason", None) if candidates else None
    return "MAX_TOKENS" in str(reason or "")


def assistant_reply(message, history, context):
    """Returns {reply, model, fallback}; never raises for model problems."""
    errors = []
    try:
        client = _get_client()
        from google.genai import types
        contents = [
            types.Content(role="user" if t["role"] == "user" else "model",
                          parts=[types.Part(text=t["text"])])
            for t in clean_history(history)
        ]
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
        system = (f"{ASSISTANT_RULES}\n\nDATA (JSON):\n"
                  f"{json.dumps(context, ensure_ascii=False, separators=(',', ':'))}")
        started = time.monotonic()
        for model in _models():
            if time.monotonic() - started > CHAIN_DEADLINE_S:
                errors.append(f"{model}: skipped, out of time")
                break
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=contents,
                    # No max_output_tokens: thinking models spend most of a small
                    # limit on internal reasoning and the visible answer gets cut off.
                    config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
                )
                if _was_cut_off(res):
                    errors.append(f"{model}: reply cut off (MAX_TOKENS)")
                    continue
                reply = _strip_markdown(res.text or "")
                if not reply:
                    errors.append(f"{model}: empty reply")
                    continue
                if not _reply_script_ok(reply, reply_language(message)):
                    errors.append(f"{model}: wrong script in reply")
                    continue
                result = {"reply": reply, "model": res.model_version or model, "fallback": False}
                return {**result, "errors": errors} if errors else result
            except Exception as exc:
                errors.append(f"{model}: {str(exc)[:120]}")
    except AIUnavailable as exc:
        errors.append(str(exc))
    return {
        "reply": "Sorry, the assistant is busy right now. Please try again in a minute. "
                 "Everything else on the dashboard is still live.",
        "model": None, "fallback": True, "errors": errors,
    }
