"""
IoT Light Sensor Dashboard — Flask Application
Optimized with best practices: structured logging, centralized error handling,
input validation, and MongoDB Page_Log for exception capture.
"""

from flask import Flask, render_template, jsonify, request
import random
import certifi
import os
import re
import logging
import traceback
from functools import wraps
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pytz
from dotenv import load_dotenv
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_swagger_ui import get_swaggerui_blueprint

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load .env relative to this file so it works regardless of cwd
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "light_sensor_db")
API_COLLECTION_NAME = "API"
VALID_ROOMS = frozenset(["living", "bedroom"])
SECONDS_IN_DAY = 86_400
LUX_LIGHTS_ON_THRESHOLD = 25.0
DAILY_USAGE_AGGREGATE_SENSOR_ID = "all-rooms"
TIMEZONE = "America/Los_Angeles"
MAX_SENSOR_HISTORY = 50
ALLOWED_USER_EMAIL_DOMAINS = frozenset(
    {"gmail.com", "yahoo.com", "outlook.com", "u.pacific.edu"}
)

SENSOR_ROOM_MAP = {
    "sensor-1": "living",
    "sensor-2": "bedroom",
    "esp32_01": "living",
    "esp32_02": "bedroom",
}

SENSOR_BADGE_GROUPS = (
    ("sensor1", ("sensor-1", "esp32_01")),
    ("sensor2", ("sensor-2", "esp32_02")),
)

ROOM_PRIMARY_SENSOR_ID = {
    "living": "esp32_01",
    "bedroom": "esp32_02",
}

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static", static_url_path="/static")

# ---------------------------------------------------------------------------
# MongoDB Connection
# ---------------------------------------------------------------------------

db = None
usage_collection = None
readings_collection = None
sensor_latest_collection = None
sensor_hourly_collection = None
room_collections = {}
admin_collection = None
organization_collection = None
alert_collection = None
device_collection = None
user_data_collection = None
users_collection = None
feedback_collection = None
api_collection = None
page_log_collection = None  # NEW: Exception / page-event logging


def _init_mongo():
    """Initialize MongoDB connection and all collection references."""
    global db, usage_collection, readings_collection, sensor_latest_collection
    global sensor_hourly_collection, room_collections, admin_collection
    global organization_collection, alert_collection, device_collection
    global user_data_collection, users_collection, feedback_collection
    global api_collection, page_log_collection

    if not MONGO_URI:
        logger.warning("MONGO_URI not found in .env file")
        return

    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=10_000,
            tlsCAFile=certifi.where(),
            tls=True,
        )
        client.admin.command("ping")
        db = client[DB_NAME]

        usage_collection = db["daily_usage"]
        readings_collection = db["readings"]
        sensor_latest_collection = db["sensor_latest"]
        sensor_hourly_collection = db["sensor_hourly"]
        room_collections = {r: db[f"room_{r}"] for r in VALID_ROOMS}
        admin_collection = db["admin_access"]
        organization_collection = db["Organization"]
        alert_collection = db["alerts"]
        device_collection = db["devices"]
        user_data_collection = db["user_data"]
        users_collection = db["users"]
        feedback_collection = db["Feedback"]
        api_collection = db[API_COLLECTION_NAME]
        page_log_collection = db["Page_Log"]  # NEW

        logger.info("Connected to MongoDB Atlas")
        logger.info("Collections: %s", ", ".join(db.list_collection_names()))
    except ConnectionFailure as exc:
        logger.error("MongoDB connection failed: %s", exc)
    except Exception as exc:
        logger.error("MongoDB init error: %s", exc)


_init_mongo()

# ---------------------------------------------------------------------------
# Page_Log — Centralized Exception Capture
# ---------------------------------------------------------------------------


def log_to_page_log(
    level: str,
    message: str,
    *,
    endpoint: str = "",
    method: str = "",
    path: str = "",
    status_code: int = 500,
    stack_trace: str = "",
    request_body: dict | None = None,
    ip: str = "",
    user_agent: str = "",
):
    """Write a structured log entry to the Page_Log MongoDB collection.

    This is called automatically by the global error handler and can also be
    invoked manually inside any route for custom event logging.
    """
    if page_log_collection is None:
        logger.warning("Page_Log collection unavailable — skipping DB log")
        return

    pst = pytz.timezone(TIMEZONE)
    now_pst = datetime.now(pst)

    doc = {
        "level": level,
        "message": message,
        "endpoint": endpoint,
        "method": method,
        "path": path,
        "statusCode": status_code,
        "stackTrace": stack_trace,
        "requestBody": request_body,
        "ip": ip,
        "userAgent": user_agent,
        "date": now_pst.strftime("%Y-%m-%d"),
        "time": now_pst.strftime("%H:%M:%S"),
        "timestamp": now_pst.isoformat(),
        "createdAt": datetime.utcnow().isoformat(),
    }
    try:
        page_log_collection.insert_one(doc)
    except Exception as exc:
        logger.error("Failed to write Page_Log: %s", exc)


# ---------------------------------------------------------------------------
# Global Error Handlers — auto-capture every unhandled exception
# ---------------------------------------------------------------------------


@app.errorhandler(400)
def bad_request(error):
    log_to_page_log(
        "WARN",
        str(error),
        endpoint=request.endpoint or "",
        method=request.method,
        path=request.path,
        status_code=400,
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
    )
    return jsonify({"error": "Bad request", "message": str(error)}), 400


@app.errorhandler(404)
def not_found(error):
    log_to_page_log(
        "WARN",
        f"Route not found: {request.path}",
        endpoint=request.endpoint or "",
        method=request.method,
        path=request.path,
        status_code=404,
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
    )
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    tb = traceback.format_exc()
    log_to_page_log(
        "ERROR",
        str(error),
        endpoint=request.endpoint or "",
        method=request.method,
        path=request.path,
        status_code=500,
        stack_trace=tb,
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
    )
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def handle_unhandled(error):
    tb = traceback.format_exc()
    logger.error("Unhandled exception on %s %s: %s", request.method, request.path, error)
    log_to_page_log(
        "CRITICAL",
        str(error),
        endpoint=request.endpoint or "",
        method=request.method,
        path=request.path,
        status_code=500,
        stack_trace=tb,
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
    )
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Decorators — Validation & MongoDB Guard
# ---------------------------------------------------------------------------


def require_json(*required_fields):
    """Validate that the request body is JSON and contains required fields."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"error": "Request body must be JSON"}), 400
            missing = [f for f in required_fields if f not in data]
            if missing:
                return jsonify({"error": f"Missing required fields: {missing}"}), 400
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_mongo(collection_name: str):
    """Return 503 early if the named collection is None."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            coll = globals().get(collection_name)
            if coll is None:
                return jsonify({"success": False, "message": "MongoDB not available"}), 503
            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_room(func):
    """Validate that the room_name path parameter is in VALID_ROOMS."""
    @wraps(func)
    def wrapper(room_name, *args, **kwargs):
        if room_name not in VALID_ROOMS:
            return jsonify({"error": f"Invalid room. Valid rooms: {list(VALID_ROOMS)}"}), 400
        return func(room_name, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pst_now():
    """Current datetime in PST."""
    return datetime.now(pytz.timezone(TIMEZONE))


def _today_str():
    """Today's date string (YYYY-MM-DD) in PST."""
    return _pst_now().strftime("%Y-%m-%d")


def _user_email_domain_allowed(email: str) -> bool:
    """Check if an email address belongs to an allowed domain."""
    addr = (email or "").strip().lower()
    if "@" not in addr:
        return False
    return addr.rsplit("@", 1)[-1] in ALLOWED_USER_EMAIL_DOMAINS


def _daily_usage_aggregate_match():
    """MongoDB filter for whole-dashboard aggregate timer docs."""
    return {
        "$or": [
            {"sensor_id": DAILY_USAGE_AGGREGATE_SENSOR_ID},
            {"sensor_id": ""},
            {"sensor_id": {"$exists": False}},
        ]
    }


def _safe_route(func):
    """Wrap a route so any exception is logged to Page_Log and returned as 500."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Exception in %s: %s", func.__name__, exc)
            log_to_page_log(
                "ERROR",
                str(exc),
                endpoint=func.__name__,
                method=request.method,
                path=request.path,
                status_code=500,
                stack_trace=tb,
                request_body=request.get_json(silent=True),
                ip=request.remote_addr or "",
                user_agent=request.headers.get("User-Agent", ""),
            )
            return jsonify({"success": False, "message": "Internal server error"}), 500
    return wrapper


# ---------------------------------------------------------------------------
# Sensor Simulation
# ---------------------------------------------------------------------------

sensor_history: list[dict] = []
sensor_history_by_id: dict[str, list] = {}
registered_sensors: dict = {}


def generate_sensor_reading() -> float:
    """Simulate a light sensor reading between 0–50 lux.

    Daytime (06:00–18:00) produces higher values; nighttime is dimmer.
    """
    hour = datetime.now().hour
    base = 25 + (15 * (1 - abs(hour - 12) / 6)) if 6 <= hour <= 18 else 10
    noise = random.gauss(0, 5)
    return round(max(0.0, min(50.0, base + noise)), 1)


def get_sensor_status(lux: float) -> dict:
    """Map a lux value to a human-readable status dict."""
    if lux < 15:
        return {"level": "Dark", "color": "#1a1a2e", "icon": "🌙"}
    if lux < 25:
        return {"level": "Dim", "color": "#16213e", "icon": "🌆"}
    if lux < 35:
        return {"level": "Normal", "color": "#e94560", "icon": "☀️"}
    if lux < 50:
        return {"level": "Bright", "color": "#f39c12", "icon": "🌞"}
    return {"level": "Very Bright", "color": "#f1c40f", "icon": "⚡"}


# ---------------------------------------------------------------------------
# Swagger UI
# ---------------------------------------------------------------------------

SWAGGER_URL = "/api/docs"
API_URL = "/swagger/swagger.yaml"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "IoT Light Sensor API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


@app.route("/swagger/swagger.yaml")
def swagger_spec():
    """Serve the OpenAPI YAML specification file."""
    from flask import send_file

    path = os.path.join(app.root_path, "swagger", "swagger.yaml")
    if not os.path.isfile(path):
        return jsonify({"error": "Swagger spec not found"}), 404
    return send_file(path, mimetype="text/yaml")


# ===================================================================
# PAGE ROUTES
# ===================================================================


@app.route("/")
def dashboard():
    """Serve the main dashboard page."""
    return render_template("dashboard.html")


@app.route("/diagram")
def diagram():
    """Serve the architecture diagram as static HTML."""
    from flask import send_file

    tpl = os.path.join(app.root_path, "templates", "diagram.html")
    root = os.path.join(app.root_path, "diagram.html")
    path = tpl if os.path.isfile(tpl) else root
    if not os.path.isfile(path):
        return jsonify({"error": "Diagram page not found"}), 404
    return send_file(path, mimetype="text/html")


# ===================================================================
# SENSOR APIs
# ===================================================================


@app.route("/api/sensor")
@_safe_route
def get_sensor_data():
    """Return a simulated sensor reading."""
    lux = generate_sensor_reading()
    status = get_sensor_status(lux)
    reading = {
        "lux": lux,
        "timestamp": datetime.now().isoformat(),
        "status": status,
    }
    sensor_history.append(reading)
    if len(sensor_history) > MAX_SENSOR_HISTORY:
        del sensor_history[: len(sensor_history) - MAX_SENSOR_HISTORY]
    return jsonify(reading)


@app.route("/api/history")
@_safe_route
def get_history():
    """Return the in-memory sensor reading history."""
    return jsonify(sensor_history)


@app.route("/api/stats")
@_safe_route
def get_stats():
    """Return min/max/avg statistics from the in-memory sensor history."""
    if not sensor_history:
        return jsonify({"avg": 0, "min": 0, "max": 0, "readings": 0})
    lux_values = [r["lux"] for r in sensor_history]
    return jsonify({
        "avg": round(sum(lux_values) / len(lux_values), 1),
        "min": round(min(lux_values), 1),
        "max": round(max(lux_values), 1),
        "readings": len(sensor_history),
    })


@app.route("/api/v1/sensors/register", methods=["POST"])
@_safe_route
@require_mongo("device_collection")
def register_new_sensor():
    """Register a new sensor device in MongoDB."""
    data = request.get_json(silent=True) or {}
    device_collection.insert_one(data)
    return jsonify({"success": True, "data": data}), 201


@app.route("/api/v1/sensors/data", methods=["POST"])
@_safe_route
@require_mongo("usage_collection")
@require_json("lux")
def submit_single_sensor_reading():
    """Accept a lux reading from a physical or simulated sensor."""
    data = request.get_json(silent=True) or {}
    sensor_id = (data.get("sensor_id") or "").strip()
    lux_value = float(data["lux"])

    now_pst = _pst_now()
    today = now_pst.strftime("%Y-%m-%d")

    # Per-device row in daily_usage
    if sensor_id and usage_collection is not None:
        usage_collection.update_one(
            {"date": today, "sensor_id": sensor_id},
            {
                "$set": {
                    "lux": lux_value,
                    "luxUpdatedAt": now_pst.isoformat(),
                    "updatedAt": datetime.utcnow().isoformat(),
                },
                "$setOnInsert": {
                    "date": today,
                    "sensor_id": sensor_id,
                    "onSeconds": 0,
                    "offSeconds": SECONDS_IN_DAY,
                },
            },
            upsert=True,
        )

    # sensor_latest (single doc per sensor)
    if sensor_id and sensor_latest_collection is not None:
        sensor_latest_collection.update_one(
            {"sensor_id": sensor_id},
            {"$set": {
                "lux": lux_value,
                "luxUpdatedAt": now_pst.isoformat(),
                "updatedAt": datetime.utcnow().isoformat(),
                "date": today,
            }},
            upsert=True,
        )

    # sensor_hourly bucket
    if sensor_id and sensor_hourly_collection is not None:
        inc_doc = {"samples": 1}
        if lux_value >= LUX_LIGHTS_ON_THRESHOLD:
            inc_doc["bright_samples"] = 1
        sensor_hourly_collection.update_one(
            {"date": today, "hour": int(now_pst.hour), "sensor_id": sensor_id},
            {
                "$inc": inc_doc,
                "$set": {
                    "luxLast": lux_value,
                    "updatedAt": datetime.utcnow().isoformat(),
                },
            },
            upsert=True,
        )

    # Room collection update
    room_name = SENSOR_ROOM_MAP.get(sensor_id) if sensor_id else None
    if room_name and room_name in room_collections and room_collections[room_name] is not None:
        room_collections[room_name].update_one(
            {"date": today},
            {
                "$set": {
                    "avgLux": lux_value,
                    "sensor_id": sensor_id,
                    "luxUpdatedAt": now_pst.isoformat(),
                    "updatedAt": datetime.utcnow().isoformat(),
                },
                "$setOnInsert": {"date": today, "onSeconds": 0},
            },
            upsert=True,
        )

    return jsonify({"success": True, "data": {
        "date": today,
        "lux": lux_value,
        "sensor_id": sensor_id,
        "room": room_name,
        "luxUpdatedAt": now_pst.isoformat(),
    }})


@app.route("/api/v1/sensors/<sensor_id>/status", methods=["GET"])
@_safe_route
def get_sensor_status_v1(sensor_id):
    """Return the latest cached status for a given sensor_id."""
    items = sensor_history_by_id.get(sensor_id, [])
    if not items:
        return jsonify({"success": False, "error": "No data for sensor"}), 404
    latest = items[-1]
    return jsonify({
        "success": True,
        "sensor_id": sensor_id,
        "status": latest["status"],
        "last_reading": {"lux": latest["lux"], "timestamp": latest["timestamp"]},
    })


@app.route("/api/v1/sensors/latest", methods=["GET"])
@_safe_route
def get_latest_sensor_reading():
    """Latest lux plus today's on/off durations from daily_usage."""
    if usage_collection is None and readings_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    today_str = _today_str()

    # Find latest reading with lux
    latest, source = None, None
    if usage_collection is not None:
        latest = usage_collection.find_one(
            {"lux": {"$ne": None}},
            sort=[("luxUpdatedAt", -1), ("updatedAt", -1), ("_id", -1)],
        )
        source = "daily_usage" if latest else None
    if latest is None and readings_collection is not None:
        latest = readings_collection.find_one(
            {"lux": {"$ne": None}},
            sort=[("luxUpdatedAt", -1), ("updatedAt", -1), ("_id", -1)],
        )
        source = "readings" if latest else None

    sid = ((latest or {}).get("sensor_id") or "").strip()

    # Find today's usage doc
    usage_today = None
    if usage_collection is not None:
        for filt in [
            {"date": today_str, "sensor_id": sid} if sid else None,
            {"date": today_str, "sensor_id": DAILY_USAGE_AGGREGATE_SENSOR_ID},
            {"$and": [{"date": today_str}, _daily_usage_aggregate_match()]},
        ]:
            if filt is None:
                continue
            usage_today = usage_collection.find_one(filt)
            if usage_today:
                break

    if not latest and not usage_today:
        return jsonify({"success": False, "message": "No readings found"}), 404

    lux_val = (latest or {}).get("lux") or (usage_today or {}).get("lux")
    sensor_id = sid or ((usage_today or {}).get("sensor_id") or "")
    ref = usage_today or latest or {}
    on_sec = int(ref.get("onSeconds", 0) or 0)
    off_sec = int(ref.get("offSeconds", 0) or 0)
    if off_sec <= 0:
        off_sec = max(0, SECONDS_IN_DAY - on_sec)

    lights_on = None
    if lux_val is not None:
        try:
            lights_on = float(lux_val) >= LUX_LIGHTS_ON_THRESHOLD
        except (TypeError, ValueError):
            pass

    return jsonify({
        "success": True,
        "data": {
            "source": source or "daily_usage",
            "sensor_id": sensor_id,
            "lux": lux_val,
            "lightsOn": lights_on,
            "date": ref.get("date", today_str),
            "onSeconds": on_sec,
            "offSeconds": off_sec,
            "luxUpdatedAt": ref.get("luxUpdatedAt", ""),
            "updatedAt": ref.get("updatedAt", ""),
        },
    })


@app.route("/api/v1/sensors/badges", methods=["GET"])
@_safe_route
@require_mongo("sensor_latest_collection")
def get_sensor_badges():
    """Latest lux per logical sensor for dashboard pills."""
    data = {}
    for key, ids in SENSOR_BADGE_GROUPS:
        label = "Sensor 1" if key == "sensor1" else "Sensor 2"
        docs = list(sensor_latest_collection.find({"sensor_id": {"$in": list(ids)}}))
        best = max(docs, key=lambda d: d.get("luxUpdatedAt", ""), default=None)

        if not best:
            data[key] = {"label": label, "sensor_id": "", "lux": None, "lightsOn": None, "luxUpdatedAt": ""}
            continue

        lux = best.get("lux")
        lights_on = None
        if lux is not None:
            try:
                lights_on = float(lux) >= LUX_LIGHTS_ON_THRESHOLD
            except (TypeError, ValueError):
                pass

        data[key] = {
            "label": label,
            "sensor_id": (best.get("sensor_id") or "").strip(),
            "lux": lux,
            "lightsOn": lights_on,
            "luxUpdatedAt": best.get("luxUpdatedAt", ""),
        }
    return jsonify({"success": True, "data": data})


@app.route("/api/v1/sensors/hourly_graph", methods=["GET"])
@_safe_route
@require_mongo("sensor_hourly_collection")
def get_hourly_sensor_graph():
    """24-point series (0–1) per logical sensor from sensor_hourly collection."""
    date_str = (request.args.get("date") or "").strip()
    if not date_str or not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return jsonify({"success": False, "message": "Missing or invalid date (YYYY-MM-DD)"}), 400

    out = {
        "sensor1": [0.0] * 24,
        "sensor2": [0.0] * 24,
        "totals": {
            "sensor1": {"samples": 0, "brightSamples": 0},
            "sensor2": {"samples": 0, "brightSamples": 0},
        },
    }

    for group_key, ids in SENSOR_BADGE_GROUPS:
        tk = "sensor1" if group_key == "sensor1" else "sensor2"
        arr = out[tk]

        # Hourly breakdown
        for row in sensor_hourly_collection.aggregate([
            {"$match": {"date": date_str, "sensor_id": {"$in": list(ids)}}},
            {"$group": {"_id": "$hour", "samples": {"$sum": "$samples"}, "bright": {"$sum": "$bright_samples"}}},
        ]):
            h = row.get("_id")
            try:
                hi = int(h)
            except (TypeError, ValueError):
                continue
            if 0 <= hi <= 23:
                s = int(row.get("samples") or 0)
                b = int(row.get("bright") or 0)
                arr[hi] = round(min(1.0, b / s), 4) if s > 0 else 0.0

        # Daily totals
        for tot in sensor_hourly_collection.aggregate([
            {"$match": {"date": date_str, "sensor_id": {"$in": list(ids)}}},
            {"$group": {"_id": None, "sm": {"$sum": "$samples"}, "br": {"$sum": "$bright_samples"}}},
        ]):
            out["totals"][tk]["samples"] = int(tot.get("sm") or 0)
            out["totals"][tk]["brightSamples"] = int(tot.get("br") or 0)

    return jsonify({"success": True, "data": out})


# ===================================================================
# USAGE APIs
# ===================================================================


@app.route("/api/usage/reset", methods=["POST"])
@_safe_route
@require_mongo("usage_collection")
def reset_usage():
    """Clear only today's daily_usage rows (PST). Previous days are preserved."""
    today = _today_str()
    result = usage_collection.delete_many({"date": today})
    return jsonify({
        "success": True,
        "message": "Today's usage cleared",
        "date": today,
        "deletedCount": result.deleted_count,
    })


@app.route("/api/usage/save", methods=["POST"])
@_safe_route
@require_mongo("usage_collection")
@require_json("date")
def save_usage():
    """Save daily usage data."""
    data = request.json
    sid = (data.get("sensor_id") or "").strip() or DAILY_USAGE_AGGREGATE_SENSOR_ID
    on_sec = data.get("onSeconds", 0)

    usage_collection.update_one(
        {"date": data["date"], "sensor_id": sid},
        {"$set": {
            "date": data["date"],
            "sensor_id": sid,
            "onSeconds": on_sec,
            "offSeconds": SECONDS_IN_DAY - on_sec,
            "updatedAt": datetime.utcnow().isoformat(),
        }},
        upsert=True,
    )
    return jsonify({"success": True})


@app.route("/api/usage/<date>")
@_safe_route
def get_usage(date):
    """Get usage for a specific date."""
    empty = {"_id": "", "date": date, "sensor_id": "", "onSeconds": 0, "offSeconds": SECONDS_IN_DAY,
             "lux": None, "updatedAt": "", "luxUpdatedAt": ""}
    if usage_collection is None:
        return jsonify(empty)
    record = usage_collection.find_one({"date": date})
    if not record:
        return jsonify(empty)
    return jsonify({
        "_id": str(record.get("_id", "")),
        "date": record["date"],
        "sensor_id": record.get("sensor_id", ""),
        "onSeconds": record.get("onSeconds", 0),
        "offSeconds": record.get("offSeconds", 0),
        "lux": record.get("lux"),
        "updatedAt": record.get("updatedAt", ""),
        "luxUpdatedAt": record.get("luxUpdatedAt", ""),
    })


@app.route("/api/usage/statistics")
@_safe_route
def get_usage_statistics():
    """Weekly and monthly on-seconds excluding today (tracked live in frontend)."""
    now = _pst_now()
    today_str = now.strftime("%Y-%m-%d")
    days_since_sunday = (now.weekday() + 1) % 7
    week_start_str = (now - timedelta(days=days_since_sunday)).strftime("%Y-%m-%d")
    month_start_str = now.strftime("%Y-%m-01")

    weekly_seconds = 0
    monthly_seconds = 0

    if usage_collection is not None:
        agg_match = _daily_usage_aggregate_match()
        for label, start in [("week", week_start_str), ("month", month_start_str)]:
            records = list(usage_collection.find({
                "$and": [{"date": {"$gte": start, "$lt": today_str}}, agg_match]
            }))
            total = sum(r.get("onSeconds", 0) for r in records)
            if label == "week":
                weekly_seconds = total
            else:
                monthly_seconds = total

    return jsonify({"daily": 0, "weekly": weekly_seconds, "monthly": monthly_seconds})


# ===================================================================
# ROOM APIs
# ===================================================================


@app.route("/api/room/<room_name>/save", methods=["POST"])
@_safe_route
@validate_room
@require_json("date")
def save_room_usage(room_name):
    """Save daily usage data for a specific room."""
    data = request.json
    sensor_id = (data.get("sensor_id") or "").strip() or ROOM_PRIMARY_SENSOR_ID.get(room_name, "")

    coll = room_collections.get(room_name)
    if coll is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    coll.update_one(
        {"date": data["date"]},
        {"$set": {
            "date": data["date"],
            "onSeconds": data.get("onSeconds", 0),
            "avgLux": data.get("avgLux", 0),
            "updatedAt": datetime.utcnow().isoformat(),
            "sensor_id": sensor_id,
        }},
        upsert=True,
    )
    return jsonify({"success": True, "room": room_name})


@app.route("/api/room/<room_name>/<date>")
@_safe_route
@validate_room
def get_room_usage(room_name, date):
    """Get usage for a specific room on a specific date."""
    empty = {"_id": "", "room": room_name, "date": date, "sensor_id": "",
             "onSeconds": 0, "avgLux": 0, "updatedAt": "", "luxUpdatedAt": ""}
    coll = room_collections.get(room_name)
    if coll is None:
        return jsonify(empty)
    record = coll.find_one({"date": date})
    if not record:
        return jsonify(empty)
    return jsonify({
        "_id": str(record.get("_id", "")),
        "room": room_name,
        "date": record["date"],
        "sensor_id": record.get("sensor_id", ""),
        "onSeconds": record.get("onSeconds", 0),
        "avgLux": record.get("avgLux", 0),
        "updatedAt": record.get("updatedAt", ""),
        "luxUpdatedAt": record.get("luxUpdatedAt", ""),
    })


@app.route("/api/room/<room_name>/statistics")
@_safe_route
@validate_room
def get_room_statistics(room_name):
    """Weekly and monthly statistics for a specific room."""
    now = _pst_now()
    today_str = now.strftime("%Y-%m-%d")
    week_start_str = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    month_start_str = now.strftime("%Y-%m-01")

    weekly_seconds = 0
    monthly_seconds = 0

    coll = room_collections.get(room_name)
    if coll is not None:
        week_records = list(coll.find({"date": {"$gte": week_start_str, "$lt": today_str}}))
        weekly_seconds = sum(r.get("onSeconds", 0) for r in week_records)
        month_records = list(coll.find({"date": {"$gte": month_start_str, "$lt": today_str}}))
        monthly_seconds = sum(r.get("onSeconds", 0) for r in month_records)

    return jsonify({"room": room_name, "weekly": weekly_seconds, "monthly": monthly_seconds})


@app.route("/api/rooms/all/<date>")
@_safe_route
def get_all_rooms_usage(date):
    """Get usage for all rooms on a specific date."""
    result = {}
    for room_name in VALID_ROOMS:
        coll = room_collections.get(room_name)
        if coll is not None:
            record = coll.find_one({"date": date})
            if record:
                result[room_name] = {
                    "sensor_id": record.get("sensor_id", ""),
                    "onSeconds": record.get("onSeconds", 0),
                    "avgLux": record.get("avgLux", 0),
                }
                continue
        result[room_name] = {"sensor_id": "", "onSeconds": 0, "avgLux": 0}
    return jsonify({"date": date, "rooms": result})


@app.route("/api/rooms/reset", methods=["POST"])
@_safe_route
def reset_all_rooms():
    """Clear only today's room documents (PST). Previous days are preserved."""
    today = _today_str()
    total = 0
    for room_name in VALID_ROOMS:
        coll = room_collections.get(room_name)
        if coll is not None:
            total += coll.delete_many({"date": today}).deleted_count
    return jsonify({
        "success": True,
        "message": "Today's room data cleared",
        "date": today,
        "deletedCount": total,
    })


# ===================================================================
# ADMIN APIs
# ===================================================================


@app.route("/api/admin/access", methods=["POST"])
@_safe_route
@require_mongo("admin_collection")
@require_json("username")
def log_admin_access():
    """Log admin access details to MongoDB."""
    data = request.json or {}
    username = data["username"].strip()
    if not username:
        return jsonify({"success": False, "message": "Admin username is required"}), 400

    login_type = (data.get("loginType") or "personal").strip()
    org_name = (data.get("organizationName") or "").strip()
    if login_type == "organization" and not org_name:
        return jsonify({"success": False, "message": "Organization name is required"}), 400

    now_pst = _pst_now()

    admin_collection.insert_one({
        "username": username,
        "loginType": login_type,
        "organizationName": org_name if login_type == "organization" else "",
        "accessedAt": datetime.utcnow().isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get("User-Agent", ""),
        "path": "/info",
    })

    if login_type == "organization" and organization_collection is not None:
        organization_collection.insert_one({
            "adminName": username,
            "organizationName": org_name,
            "date": now_pst.strftime("%Y-%m-%d"),
            "time": now_pst.strftime("%H:%M:%S"),
            "timestamp": now_pst.isoformat(),
            "createdAt": datetime.utcnow().isoformat(),
        })

    return jsonify({"success": True})


# ===================================================================
# ALERT APIs
# ===================================================================


@app.route("/api/alerts", methods=["POST"])
@_safe_route
@require_mongo("alert_collection")
def create_alert():
    """Create an alert when lights are on for longer than threshold."""
    data = request.json or {}
    room_id = (data.get("room_id") or "unknown").strip()
    duration_seconds = int(data.get("durationSeconds") or 0)
    alert_type = data.get("type", "duration_over_40min")
    date = data.get("date") or _today_str()

    # Deduplicate
    if alert_collection.find_one({"room_id": room_id, "date": date, "type": alert_type}):
        return jsonify({"success": True, "skipped": True})

    alert_collection.insert_one({
        "alert_id": str(uuid.uuid4()),
        "room_id": room_id,
        "date": date,
        "durationSeconds": duration_seconds,
        "type": alert_type,
        "createdAt": datetime.utcnow().isoformat(),
    })
    return jsonify({"success": True})


# ===================================================================
# USER LOGIN APIs
# ===================================================================


@app.route("/api/user/login", methods=["POST"])
@_safe_route
@require_mongo("users_collection")
@require_json("email", "password")
def user_login():
    """Register on first login; validate password on subsequent logins."""
    data = request.json or {}
    email = data["email"].strip()
    password = data["password"].strip()

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return jsonify({"success": False, "message": "Invalid email id"}), 400
    if not _user_email_domain_allowed(email):
        return jsonify({
            "success": False,
            "message": "Use an allowed email domain: gmail.com, yahoo.com, outlook.com, or u.pacific.edu.",
        }), 400
    if not password:
        return jsonify({"success": False, "message": "Password is required"}), 400

    existing_user = users_collection.find_one({"email": email})

    if existing_user is None:
        users_collection.insert_one({
            "email": email,
            "passwordHash": generate_password_hash(password),
            "createdAt": datetime.utcnow().isoformat(),
        })
    else:
        pw_hash = existing_user.get("passwordHash", "")
        if not pw_hash or not check_password_hash(pw_hash, password):
            return jsonify({"success": False, "message": "Invalid password"}), 401

    if user_data_collection is not None:
        user_data_collection.insert_one({
            "email": email,
            "loggedInAt": datetime.utcnow().isoformat(),
            "ip": request.remote_addr,
            "userAgent": request.headers.get("User-Agent", ""),
        })

    return jsonify({"success": True})


# ===================================================================
# FEEDBACK APIs
# ===================================================================


@app.route("/api/feedback", methods=["POST"])
@_safe_route
@require_mongo("feedback_collection")
@require_json("text")
def save_feedback():
    """Store user feedback (report an issue)."""
    text = (request.json.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "message": "Feedback text is required"}), 400

    now_pst = _pst_now()
    feedback_collection.insert_one({
        "text": text,
        "date": now_pst.strftime("%Y-%m-%d"),
        "time": now_pst.strftime("%H:%M:%S"),
        "timestamp": now_pst.isoformat(),
        "createdAt": datetime.utcnow().isoformat(),
    })
    return jsonify({"success": True})


# ===================================================================
# DEVICE LOGGING
# ===================================================================


@app.route("/api/device/log", methods=["POST"])
@_safe_route
@require_mongo("device_collection")
def log_device():
    """Log device details when room or gauge lights are turned on."""
    data = request.json or {}
    action_type = data.get("action_type", "unknown")
    room_id = data.get("room_id", "")
    room_name = data.get("room_name", "")
    is_room = action_type == "room_light_on"

    now_pst = _pst_now()

    device_collection.insert_one({
        "action_type": action_type,
        "room_id": room_id if is_room else None,
        "room_name": room_name if is_room else None,
        "date": now_pst.strftime("%Y-%m-%d"),
        "time": now_pst.strftime("%H:%M:%S"),
        "timestamp": now_pst.isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get("User-Agent", ""),
        "createdAt": datetime.utcnow().isoformat(),
    })
    return jsonify({"success": True})


# ===================================================================
# PAGE_LOG — Manual Query Endpoint
# ===================================================================


@app.route("/api/page-logs", methods=["GET"])
@_safe_route
@require_mongo("page_log_collection")
def get_page_logs():
    """Retrieve recent Page_Log entries (latest 50). Query ?level=ERROR to filter."""
    level_filter = (request.args.get("level") or "").strip().upper()
    query = {"level": level_filter} if level_filter else {}
    docs = list(
        page_log_collection.find(query, {"_id": 0})
        .sort("createdAt", -1)
        .limit(50)
    )
    return jsonify({"success": True, "count": len(docs), "logs": docs})


# ===================================================================
# API MANIFEST
# ===================================================================

DOCUMENTED_APIS = [
    ("GET", "/", "Dashboard page"),
    ("GET", "/diagram", "Architecture diagram page"),
    ("GET", "/api/docs", "Swagger UI (interactive API docs)"),
    ("GET", "/api/sensor", "Simulated sensor reading"),
    ("POST", "/api/v1/sensors/register", "Register sensor device"),
    ("POST", "/api/v1/sensors/data", "Submit lux sensor reading"),
    ("GET", "/api/v1/sensors/{sensor_id}/status", "Sensor status by ID"),
    ("GET", "/api/v1/sensors/latest", "Latest lux from daily_usage"),
    ("GET", "/api/v1/sensors/badges", "Per-sensor status for dashboard pills"),
    ("GET", "/api/v1/sensors/hourly_graph", "Hourly graph from sensor_hourly"),
    ("POST", "/api/usage/save", "Save daily usage"),
    ("GET", "/api/usage/{date}", "Get usage for date"),
    ("GET", "/api/usage/statistics", "Weekly and monthly stats"),
    ("POST", "/api/room/{room}/save", "Save room usage"),
    ("GET", "/api/room/{room}/{date}", "Get room data for date"),
    ("GET", "/api/room/{room}/statistics", "Room weekly and monthly stats"),
    ("GET", "/api/rooms/all/{date}", "All rooms for date"),
    ("POST", "/api/admin/access", "Log admin access"),
    ("POST", "/api/alerts", "Create long-on alert"),
    ("POST", "/api/user/login", "User login (email and password)"),
    ("POST", "/api/feedback", "Report an issue"),
    ("POST", "/api/device/log", "Log device when lights turn on"),
    ("GET", "/api/page-logs", "Retrieve recent Page_Log entries"),
]


def _sync_api_manifest():
    """Write the documented API list into the API collection."""
    if api_collection is None:
        return
    lines = [f"{m} {p}  --  {d}" for m, p, d in DOCUMENTED_APIS]
    try:
        api_collection.replace_one(
            {"name": "api_manifest"},
            {
                "name": "api_manifest",
                "apisText": "\n".join(lines),
                "lineCount": len(DOCUMENTED_APIS),
                "updatedAt": datetime.utcnow().isoformat(),
            },
            upsert=True,
        )
        logger.info("API manifest: stored %d documented routes", len(DOCUMENTED_APIS))
    except Exception as exc:
        logger.error("Failed to sync API manifest: %s", exc)


_sync_api_manifest()

# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":
    # Seed sensor history with 20 simulated readings
    for i in range(20):
        lux = generate_sensor_reading()
        sensor_history.append({
            "lux": lux,
            "timestamp": (datetime.now() - timedelta(seconds=(20 - i) * 3)).isoformat(),
            "status": get_sensor_status(lux),
        })

    app.run(debug=True, port=5001)