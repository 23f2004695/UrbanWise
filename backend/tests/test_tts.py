import io
import wave
from types import SimpleNamespace

import pytest

import app as app_module
from services import tts


@pytest.fixture(autouse=True)
def clear_cache():
    tts._audio_cache.clear()


def pcm_response(data=b"\x00\x01" * 100, mime="audio/L16;codec=pcm;rate=24000"):
    blob = SimpleNamespace(data=data, mime_type=mime)
    part = SimpleNamespace(inline_data=blob)
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


class FakeTTS:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.prompts.append((model, contents))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_detect_language():
    assert tts.detect_language("ਹਵਾ") == "pa"
    assert tts.detect_language("हवा") == "hi"
    assert tts.detect_language("air") == "en"


def test_pcm_is_wrapped_as_wav():
    audio = tts._as_wav(b"\x00\x01" * 50, "audio/L16;codec=pcm;rate=16000")
    with wave.open(io.BytesIO(audio)) as w:
        assert w.getframerate() == 16000
        assert w.getnframes() == 50


def test_wav_passes_through():
    assert tts._as_wav(b"RIFFxxxxWAVE", "audio/wav") == b"RIFFxxxxWAVE"


def test_synthesize_names_the_language_and_caches(monkeypatch):
    fake = FakeTTS(pcm_response())
    monkeypatch.setattr(tts, "_get_client", lambda: fake)
    audio, errors = tts.synthesize("• ਲੁਧਿਆਣਾ ਵਿੱਚ PM2.5 ਉੱਚਾ ਹੈ")
    assert audio[:4] == b"RIFF" and errors == []
    model, prompt = fake.prompts[0]
    assert "in Punjabi" in prompt and "•" not in prompt and "PM 2.5" in prompt
    tts.synthesize("• ਲੁਧਿਆਣਾ ਵਿੱਚ PM2.5 ਉੱਚਾ ਹੈ")  # cached: no second call
    assert len(fake.prompts) == 1


def test_synthesize_falls_back_then_gives_up(monkeypatch):
    fake = FakeTTS(RuntimeError("429"), pcm_response())
    monkeypatch.setattr(tts, "_get_client", lambda: fake)
    audio, errors = tts.synthesize("hello")
    assert "429" in errors[0]
    fake = FakeTTS(RuntimeError("429"), RuntimeError("503"))
    monkeypatch.setattr(tts, "_get_client", lambda: fake)
    with pytest.raises(tts.SpeechUnavailable):
        tts.synthesize("hello again")


def test_speak_endpoint(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "synthesize", lambda text: (b"RIFFdata", []))
    res = client.post("/api/speak", json={"text": "ਹਵਾ"})
    assert res.status_code == 200 and res.mimetype == "audio/wav" and res.data == b"RIFFdata"

    def down(text):
        raise tts.SpeechUnavailable("all busy")
    monkeypatch.setattr(app_module, "synthesize", down)
    assert client.post("/api/speak", json={"text": "x"}).status_code == 503
    monkeypatch.setattr(app_module, "synthesize", tts.synthesize)
    assert client.post("/api/speak", json={}).status_code == 400
