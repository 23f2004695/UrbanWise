import os
import re
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from services.advisory import DEFAULT_SLOTS, in_delhi_ncr, school_plan
from services.ai import MAX_MESSAGE_CHARS, assistant_reply, circular_facts, generate_circular
from services.air import UpstreamError, get_air, get_school_hours, search_places
from services.context import city_context
from services.errors import BadRequest
from services.ratelimit import RateLimiter
from services.smoke_trail import get_smoke_forecast, get_smoke_trail
from services.radar import get_radar
from services.snapshot import get_snapshot
from services.tts import SpeechUnavailable, synthesize

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # no endpoint needs more

# Gemini calls are slow and quota-limited: (requests, per seconds) per visitor.
LIMITS = {
    "chat": RateLimiter(12, 60),
    "circular": RateLimiter(6, 60),
    "speak": RateLimiter(10, 60),
}


def _client_id():
    # Behind CloudFront/API Gateway the real client is the first forwarded address.
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr or "unknown"


def _rate_limit(name):
    if not LIMITS[name].allow(_client_id()):
        return jsonify(error="Too many requests. Please wait a minute and try again."), 429
    return None


def _body():
    body = request.get_json(silent=True)
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise BadRequest("JSON body must be an object")
    return body


def _times(body):
    times = body.get("times") or {}
    if not isinstance(times, dict):
        raise BadRequest("times must be an object")
    return times


def _coords(source=None):
    """Read and validate lat/lon (query params by default); raises BadRequest."""
    source = request.args if source is None else source
    try:
        lat = float(source["lat"])
        lon = float(source["lon"])
    except (KeyError, TypeError, ValueError):
        lat = lon = None
    if lat is None or lon is None:
        raise BadRequest("lat and lon are required")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):  # also rejects NaN
        raise BadRequest("lat/lon out of range")
    return lat, lon


def _slots(overrides=None):
    """School slots, with optional {assembly|pe|dismissal: "HH:MM"} overrides
    (query params by default). The forecast is hourly, so times round down."""
    overrides = request.args if overrides is None else overrides
    slots = []
    for slot in DEFAULT_SLOTS:
        value = overrides.get(slot["id"])
        if value:
            match = isinstance(value, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value)
            if not match:
                raise BadRequest(f"{slot['id']} must be a time like 08:30")
            slot = {**slot, "time": f"{match.group(1)}:00"}
        slots.append(slot)
    return slots


@app.errorhandler(BadRequest)
def bad_request(err):
    return jsonify(error=str(err)), 400


@app.errorhandler(HTTPException)
def http_error(err):
    return jsonify(error=err.description), err.code


@app.errorhandler(Exception)
def unexpected(err):
    # Never leak internals to the browser; the details go to the log.
    app.logger.exception("Unhandled error: %s", err)
    return jsonify(error="Something went wrong. Please try again."), 500


@app.errorhandler(UpstreamError)
def upstream_failed(err):
    app.logger.warning("Upstream error: %s", err)
    return jsonify(error="A data provider is unavailable. Please try again shortly."), 502


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/air")
def air():
    lat, lon = _coords()
    return jsonify(get_air(lat, lon))


@app.get("/api/school")
def school():
    lat, lon = _coords()
    hours, today = get_school_hours(lat, lon)
    tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    return jsonify(days=school_plan(hours, [today, tomorrow], _slots()))


@app.post("/api/circular")
def circular():
    body = _body()
    lat, lon = _coords(body)
    school_name = str(body.get("school_name") or "")[:80]
    slots = _slots(_times(body))
    if limited := _rate_limit("circular"):
        return limited

    hours, today = get_school_hours(lat, lon)
    tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    wanted = body.get("date") or tomorrow
    if wanted not in (today, tomorrow):
        raise BadRequest("date must be today or tomorrow")
    [day] = school_plan(hours, [wanted], slots)

    facts = circular_facts(day, school_name, grap_applies=in_delhi_ncr(lat, lon))
    result = generate_circular(facts)
    for err in result.pop("errors", []):
        app.logger.warning("Circular generation: %s", err)
    return jsonify({**result, "facts": facts})


@app.post("/api/chat")
def chat():
    body = _body()
    lat, lon = _coords(body)
    message = str(body.get("message") or "").strip()
    if not message:
        raise BadRequest("message is required")
    if len(message) > MAX_MESSAGE_CHARS:
        raise BadRequest(f"message must be at most {MAX_MESSAGE_CHARS} characters")
    slots = _slots(_times(body))
    place_name = str(body.get("place_name") or "this city")[:80]
    if limited := _rate_limit("chat"):
        return limited

    context = city_context(lat, lon, place_name, slots)
    result = assistant_reply(message, body.get("history"), context)
    for err in result.pop("errors", []):
        app.logger.warning("Assistant: %s", err)
    return jsonify(result)


@app.get("/api/smoke-forecast")
def smoke_forecast():
    lat, lon = _coords()
    return jsonify(get_smoke_forecast(lat, lon))


@app.get("/api/radar")
def radar():
    lat, lon = _coords()
    return jsonify(get_radar(lat, lon))


@app.get("/api/smoke-trail")
def smoke_trail():
    lat, lon = _coords()
    return jsonify(get_smoke_trail(lat, lon))


@app.post("/api/speak")
def speak():
    body = _body()
    text = str(body.get("text") or "")
    if not text.strip():
        raise BadRequest("text is required")
    if limited := _rate_limit("speak"):
        return limited
    try:
        audio, errors = synthesize(text)
    except SpeechUnavailable as exc:
        app.logger.warning("Speech: %s", exc)
        return jsonify(error="Speech is unavailable right now. Please try again shortly."), 503
    for err in errors:
        app.logger.warning("Speech: %s", err)
    return Response(audio, mimetype="audio/wav", headers={"Cache-Control": "private, max-age=21600"})


@app.get("/api/snapshot")
def snapshot():
    return jsonify(get_snapshot())


@app.get("/api/geocode")
def geocode():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        raise BadRequest("q must be at least 2 characters")
    return jsonify(results=search_places(query))


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", 5050)), debug=True)
