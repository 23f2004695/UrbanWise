"""Text-to-speech via Gemini, for languages the user's device can't speak.

Most phones and laptops have no Punjabi voice, so the browser can't read
Punjabi answers aloud. Checked on 8 Oct 2026: gemini-3.8-flash-lite-tts reads
Gurmukhi text correctly (verified by transcribing its audio back).
"""

import hashlib
import io
import re
import threading
import time
import wave

from cachetools import TTLCache

from services.ai import AIUnavailable, _get_client
from services.errors import BadRequest

TTS_MODELS = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]
VOICE = "Kore"
MAX_CHARS = 1200
LANGUAGE_NAMES = {"pa": "Punjabi", "hi": "Hindi", "en": "Indian English"}

# Keep recent audio so replays are free, capped by size (~0.5–3 MB per answer).
_audio_cache = TTLCache(maxsize=40 * 1024 * 1024, ttl=6 * 3600, getsizeof=len)
_cache_lock = threading.Lock()
DEADLINE_S = 22  # stay under AWS API Gateway's 29 s limit across fallbacks


class SpeechUnavailable(Exception):
    pass


def detect_language(text):
    if re.search(r"[਀-੿]", text):
        return "pa"
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    return "en"


def clean_for_speech(text):
    text = text[: MAX_CHARS * 2].replace("•", "").replace("PM2.5", "PM 2.5")
    return re.sub(r"\s+", " ", text).strip()[:MAX_CHARS]


def _as_wav(data, mime_type):
    """Gemini returns either a complete WAV or raw 16-bit PCM (audio/L16)."""
    if data[:4] == b"RIFF":
        return data
    match = re.search(r"rate=(\d+)", mime_type or "")
    rate = int(match.group(1)) if match else 24000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    return buf.getvalue()


def synthesize(text):
    """Returns (wav_bytes, errors). Raises SpeechUnavailable if no model works."""
    text = clean_for_speech(text)
    if not text:
        raise BadRequest("text is required")
    key = hashlib.sha256(text.encode()).hexdigest()
    with _cache_lock:
        cached_audio = _audio_cache.get(key)
    if cached_audio is not None:
        return cached_audio, []

    language = LANGUAGE_NAMES[detect_language(text)]
    errors = []
    try:
        client = _get_client()
        from google.genai import types
        started = time.monotonic()
        for model in TTS_MODELS:
            if time.monotonic() - started > DEADLINE_S / 2:
                errors.append(f"{model}: skipped, out of time")
                break
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=f"Read this aloud in {language}, in a calm, clear, friendly voice:\n{text}",
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE),
                            ),
                        ),
                    ),
                )
                blob = res.candidates[0].content.parts[0].inline_data
                audio = _as_wav(blob.data, blob.mime_type)
                with _cache_lock:
                    _audio_cache[key] = audio
                return audio, errors
            except Exception as exc:
                errors.append(f"{model}: {str(exc)[:120]}")
    except AIUnavailable as exc:
        errors.append(str(exc))
    raise SpeechUnavailable("; ".join(errors))
