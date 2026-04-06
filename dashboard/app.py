from flask import Flask, render_template, jsonify, request
import random
import certifi
import os
import re
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pytz
from dotenv import load_dotenv
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_swagger_ui import get_swaggerui_blueprint

# Load .env from this file's directory so MONGO_URI works regardless of cwd (e.g. gunicorn, IDE)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

app = Flask(__name__, static_folder='static', static_url_path='/static')

# MongoDB Atlas Connection (loaded from .env file for security)
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'light_sensor_db')

# MongoDB collection name for storing the full API route list as text
API_COLLECTION_NAME = 'API'

if not MONGO_URI:
    print("⚠️ MONGO_URI not found in .env file")
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
else:
    try:
        client = MongoClient(
            MONGO_URI, 
            serverSelectionTimeoutMS=10000,
            tlsCAFile=certifi.where(),
            tls=True
        )
        client.admin.command('ping')
        db = client[DB_NAME]
        usage_collection = db['daily_usage']
        readings_collection = db['readings']
        sensor_latest_collection = db['sensor_latest']
        sensor_hourly_collection = db['sensor_hourly']
        
        # Room-specific collections
        room_collections = {
            'living': db['room_living'],
            'bedroom': db['room_bedroom'],
        }

        # Admin access/log collection
        admin_collection = db['admin_access']
        # Organization login collection (admin + organization + date/time)
        organization_collection = db['Organization']
        # Alert collection for long-on durations / warnings
        alert_collection = db['alerts']
        # Device collection for logging device details when lights are turned on
        device_collection = db['devices']
        # User login / user data collection (email, login time, etc.)
        user_data_collection = db['user_data']
        # User auth collection (email + password hash)
        users_collection = db['users']
        # Feedback / report an issue collection
        feedback_collection = db['Feedback']
        # Plain-text manifest of documented APIs (fixed list, not from url_map)
        api_collection = db[API_COLLECTION_NAME]

        print("✅ Connected to MongoDB Atlas")
        print("📦 Room collections: living, bedroom")
        print("📦 Admin collection: admin_access")
        print("📦 Organization collection: Organization")
        print("📦 Device collection: devices")
        print("📦 User data collection: user_data")
        print("📦 Users collection: users")
        print("📦 Feedback collection: Feedback")
        print(f"📦 API manifest collection: {API_COLLECTION_NAME}")
    except ConnectionFailure as e:
        print(f"⚠️ MongoDB not available. Error: {e}")
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
    except Exception as e:
        print(f"⚠️ MongoDB connection error: {e}")
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


# Swagger UI Configuration
SWAGGER_URL = '/api/docs'
API_URL = '/swagger/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "IoT Light Sensor API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/swagger/swagger.yaml')
def swagger_spec():
    from flask import send_file
    # Use app root so this works on Render regardless of process working directory
    path = os.path.join(app.root_path, 'swagger', 'swagger.yaml')
    if not os.path.isfile(path):
        return jsonify({"error": "swagger spec not found"}), 404
    return send_file(path, mimetype='text/yaml')

# Simulated sensor data storage
sensor_history = []

sensor_history_by_id = {}

#Keeping track of all registered sensors
registered_sensors = {}

# Embedded sensor-to-room mapping for per-room lux updates
# Dashboard + simulators use sensor-1/2; ESP32 firmware often uses esp32_01, etc.
SENSOR_ROOM_MAP = {
    "sensor-1": "living",
    "sensor-2": "bedroom",
    "esp32_01": "living",
    "esp32_02": "bedroom",
}

# Header badges: each slot accepts any of these sensor_id strings (newest lux wins).
SENSOR_BADGE_GROUPS = (
    ("sensor1", ("sensor-1", "esp32_01")),
    ("sensor2", ("sensor-2", "esp32_02")),
)

# Lux at or above this level counts as “bright / lights on” (badges, hourly graph).
LUX_LIGHTS_ON_THRESHOLD = 25.0

# daily_usage: one doc per (date, sensor_id). Dashboard timer uses sensor_id "all-rooms";
# each device POST uses its own sensor_id so lux/onSeconds do not overwrite each other.
DAILY_USAGE_AGGREGATE_SENSOR_ID = "all-rooms"


def _daily_usage_aggregate_match():
    """Match Mongo docs that store the whole-dashboard onSeconds (User View “All Rooms”)."""
    return {
        "$or": [
            {"sensor_id": DAILY_USAGE_AGGREGATE_SENSOR_ID},
            {"sensor_id": ""},
            {"sensor_id": {"$exists": False}},
        ]
    }


def generate_sensor_reading():
    """Simulate a light sensor reading (0-50 lux)"""
    hour = datetime.now().hour
    if 6 <= hour <= 18:
        base = 25 + (15 * (1 - abs(hour - 12) / 6))
    else:
        base = 10
    noise = random.gauss(0, 5)
    return max(0, min(50, base + noise))

def get_sensor_status(lux):
    """Determine status based on light level"""
    if lux < 15:
        return {"level": "Dark", "color": "#1a1a2e", "icon": "🌙"}
    elif lux < 25:
        return {"level": "Dim", "color": "#16213e", "icon": "🌆"}
    elif lux < 35:
        return {"level": "Normal", "color": "#e94560", "icon": "☀️"}
    elif lux < 50:
        return {"level": "Bright", "color": "#f39c12", "icon": "🌞"}
    else:
        return {"level": "Very Bright", "color": "#f1c40f", "icon": "⚡"}

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/diagram')
def diagram():
    # Serve as static HTML — do not pass through Jinja. Path placeholders like
    # /api/usage/{date} are valid REST notation but can break Jinja on some
    # versions (500 on Render). This page has no template variables.
    from flask import send_file
    tpl = os.path.join(app.root_path, 'templates', 'diagram.html')
    root = os.path.join(app.root_path, 'diagram.html')
    path = tpl if os.path.isfile(tpl) else root
    if not os.path.isfile(path):
        return jsonify({"error": "diagram page not found"}), 404
    return send_file(path, mimetype='text/html')

@app.route('/api/sensor')
def get_sensor_data():
    """Get current sensor reading"""
    lux = generate_sensor_reading()
    status = get_sensor_status(lux)
    timestamp = datetime.now().isoformat()
    

#Sensor Data API
def now_iso():
    return datetime.now().isoformat()

def keep_last_n(history_list, n=50):
    if len(history_list) > n:
        del history_list[:-n]

#Register new sensor
@app.route("/api/v1/sensors/register", methods=["POST"])
def register_new_sensor():
    data = request.get_json(silent=True) or {}
    try:
        device_collection.insert_one(data)
        return jsonify({"success": True, "data": data}), 201
    except Exception as e:
        print(f"⚠️ Failed to register device: {e}")
        return jsonify({"success": False, "message": "Failed to log admin access", "data":data}), 500


@app.route("/api/v1/sensors/data", methods=["POST"])
def submit_single_sensor_reading():
    data = request.get_json(silent=True) or {}
    try:
        if usage_collection is None:
            return jsonify({"success": False, "message": "MongoDB not available"}), 503

        if "lux" not in data:
            return jsonify({"success": False, "message": "Missing lux value"}), 400

        sensor_id = (data.get("sensor_id") or "").strip()
        lux_value = float(data["lux"])

        pst = pytz.timezone('America/Los_Angeles')
        now_pst = datetime.now(pst)
        today = now_pst.strftime('%Y-%m-%d')

        # Per-device row in daily_usage (same sensor→room mapping as room_living / room_bedroom).
        if usage_collection is not None and sensor_id:
            usage_collection.update_one(
                {"date": today, "sensor_id": sensor_id},
                {
                    "$set": {
                        "lux": lux_value,
                        "luxUpdatedAt": now_pst.isoformat(),
                        "updatedAt": datetime.now().isoformat(),
                    },
                    "$setOnInsert": {
                        "date": today,
                        "sensor_id": sensor_id,
                        "onSeconds": 0,
                        "offSeconds": 86400,
                    },
                },
                upsert=True,
            )

        if sensor_id and sensor_latest_collection is not None:
            sensor_latest_collection.update_one(
                {"sensor_id": sensor_id},
                {"$set": {
                    "lux": lux_value,
                    "luxUpdatedAt": now_pst.isoformat(),
                    "updatedAt": datetime.now().isoformat(),
                    "date": today,
                }},
                upsert=True,
            )

        if sensor_id and sensor_hourly_collection is not None:
            hour_slot = int(now_pst.hour)
            inc_doc = {"samples": 1}
            if lux_value >= LUX_LIGHTS_ON_THRESHOLD:
                inc_doc["bright_samples"] = 1
            sensor_hourly_collection.update_one(
                {"date": today, "hour": hour_slot, "sensor_id": sensor_id},
                {
                    "$inc": inc_doc,
                    "$set": {
                        "luxLast": lux_value,
                        "updatedAt": datetime.now().isoformat(),
                    },
                },
                upsert=True,
            )

        # Sensor 1 → room_living, Sensor 2 → room_bedroom (see SENSOR_ROOM_MAP). Always store latest lux.
        room_name = SENSOR_ROOM_MAP.get(sensor_id) if sensor_id else None
        if room_name and room_name in room_collections and room_collections[room_name] is not None:
            room_collections[room_name].update_one(
                {"date": today},
                {
                    "$set": {
                        "avgLux": lux_value,
                        "sensor_id": sensor_id,
                        "luxUpdatedAt": now_pst.isoformat(),
                        "updatedAt": datetime.now().isoformat(),
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
            "luxUpdatedAt": now_pst.isoformat()
        }}), 200
    except Exception as e:
        print(f"⚠️ Failed to submit reading: {e}")
        return jsonify({"success": False, "message": "Failed to log admin access", "data":data}), 500
   
    
    
#Get sensor status
@app.route("/api/v1/sensors/<sensor_id>/status", methods=["GET"])
def get_sensor_status_v1(sensor_id):
    items = sensor_history_by_id.get(sensor_id, [])
    if not items:
        return jsonify({"success": False, "error": "No data for sensor"}), 404

    latest = items[-1]

    return jsonify({
        "success": True,
        "sensor_id": sensor_id,
        "status": latest["status"],
        "last_reading": {
            "lux": latest["lux"],
            "timestamp": latest["timestamp"]
        }
    })




# ===== MongoDB Usage API =====

@app.route('/api/usage/reset', methods=['POST'])
def reset_usage():
    """Clear only today's daily_usage row (PST). Previous days are kept."""
    if usage_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"})
    pst = pytz.timezone('America/Los_Angeles')
    today_str = datetime.now(pst).strftime('%Y-%m-%d')
    result = usage_collection.delete_many({"date": today_str})
    return jsonify({
        "success": True,
        "message": "Today's usage cleared; previous days unchanged",
        "date": today_str,
        "deletedCount": result.deleted_count,
    })

@app.route('/api/usage/save', methods=['POST'])
def save_usage():
    """Save daily usage data"""
    data = request.json
    
    if not data or 'date' not in data:
        return jsonify({"error": "Invalid data"}), 400

    sensor_id = (data.get('sensor_id') or '').strip() if isinstance(data, dict) else ''
    sid = sensor_id or DAILY_USAGE_AGGREGATE_SENSOR_ID

    usage_data = {
        "date": data['date'],
        "sensor_id": sid,
        "onSeconds": data.get('onSeconds', 0),
        "offSeconds": 86400 - data.get('onSeconds', 0),
        "updatedAt": datetime.now().isoformat()
    }

    if usage_collection is not None:
        usage_collection.update_one(
            {"date": data['date'], "sensor_id": sid},
            {"$set": usage_data},
            upsert=True
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "MongoDB not available"})

@app.route('/api/usage/<date>')
def get_usage(date):
    """Get usage for a specific date"""
    if usage_collection is not None:
        record = usage_collection.find_one({"date": date})
        if record:
            return jsonify({
                "_id": str(record.get('_id', '')),
                "date": record['date'],
                "sensor_id": record.get('sensor_id', ''),
                "onSeconds": record.get('onSeconds', 0),
                "offSeconds": record.get('offSeconds', 0),
                "lux": record.get('lux', None),
                "updatedAt": record.get('updatedAt', ''),
                "luxUpdatedAt": record.get('luxUpdatedAt', '')
            })
    return jsonify({
        "_id": "",
        "date": date,
        "sensor_id": "",
        "onSeconds": 0,
        "offSeconds": 86400,
        "lux": None,
        "updatedAt": "",
        "luxUpdatedAt": ""
    })


@app.route('/api/v1/sensors/latest', methods=['GET'])
def get_latest_sensor_reading():
    """Latest lux plus today's on/off durations from daily_usage (or readings fallback)."""
    if usage_collection is None and readings_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    try:
        pst = pytz.timezone('America/Los_Angeles')
        today_str = datetime.now(pst).strftime('%Y-%m-%d')

        latest = None
        source = None
        if usage_collection is not None:
            latest = usage_collection.find_one(
                {"lux": {"$ne": None}},
                sort=[("luxUpdatedAt", -1), ("updatedAt", -1), ("_id", -1)]
            )
            source = "daily_usage" if latest else None
        if latest is None and readings_collection is not None:
            latest = readings_collection.find_one(
                {"lux": {"$ne": None}},
                sort=[("luxUpdatedAt", -1), ("updatedAt", -1), ("_id", -1)]
            )
            source = "readings" if latest else None

        sid = ((latest or {}).get("sensor_id") or "").strip()
        usage_today = None
        if usage_collection is not None:
            if sid:
                usage_today = usage_collection.find_one({"date": today_str, "sensor_id": sid})
            if not usage_today:
                usage_today = usage_collection.find_one(
                    {"date": today_str, "sensor_id": DAILY_USAGE_AGGREGATE_SENSOR_ID}
                )
            if not usage_today:
                usage_today = usage_collection.find_one(
                    {"$and": [{"date": today_str}, _daily_usage_aggregate_match()]}
                )

        if not latest and not usage_today:
            return jsonify({"success": False, "message": "No readings found"}), 404

        lux_val = (latest or {}).get("lux")
        if lux_val is None and usage_today is not None:
            lux_val = usage_today.get("lux")

        sensor_id = sid or ((usage_today or {}).get("sensor_id") or "")

        if usage_today:
            on_sec = int(usage_today.get("onSeconds", 0) or 0)
            off_sec = int(usage_today.get("offSeconds", 0) or 0)
            if off_sec <= 0:
                off_sec = max(0, 86400 - on_sec)
            duration_date = usage_today.get("date", today_str)
            lux_updated = (usage_today.get("luxUpdatedAt") or (latest or {}).get("luxUpdatedAt") or "")
            updated_at = (usage_today.get("updatedAt") or (latest or {}).get("updatedAt") or "")
            if source is None:
                source = "daily_usage"
        elif latest:
            on_sec = int(latest.get("onSeconds", 0) or 0)
            off_sec = int(latest.get("offSeconds", 0) or 0)
            if off_sec <= 0:
                off_sec = max(0, 86400 - on_sec)
            duration_date = latest.get("date", today_str)
            lux_updated = latest.get("luxUpdatedAt", "") or ""
            updated_at = latest.get("updatedAt", "") or ""
        else:
            on_sec = 0
            off_sec = 86400
            duration_date = today_str
            lux_updated = ""
            updated_at = ""

        lights_on = None
        if lux_val is not None:
            try:
                lights_on = float(lux_val) >= LUX_LIGHTS_ON_THRESHOLD
            except (TypeError, ValueError):
                lights_on = None

        return jsonify({
            "success": True,
            "data": {
                "source": source,
                "sensor_id": sensor_id,
                "lux": lux_val,
                "lightsOn": lights_on,
                "date": duration_date,
                "onSeconds": on_sec,
                "offSeconds": off_sec,
                "luxUpdatedAt": lux_updated,
                "updatedAt": updated_at,
            }
        })
    except Exception as e:
        print(f"⚠️ Failed to fetch latest reading: {e}")
        return jsonify({"success": False, "message": "Failed to fetch latest reading"}), 500


@app.route('/api/v1/sensors/badges', methods=['GET'])
def get_sensor_badges():
    """Latest lux per logical sensor (Sensor 1 / Sensor 2) for dashboard pills."""
    if sensor_latest_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503
    try:
        data = {}
        for key, ids in SENSOR_BADGE_GROUPS:
            label = "Sensor 1" if key == "sensor1" else "Sensor 2"
            docs = list(sensor_latest_collection.find({"sensor_id": {"$in": list(ids)}}))
            best = None
            for d in docs:
                if best is None:
                    best = d
                else:
                    a = d.get("luxUpdatedAt") or ""
                    b = best.get("luxUpdatedAt") or ""
                    if a > b:
                        best = d
            if not best:
                data[key] = {
                    "label": label,
                    "sensor_id": "",
                    "lux": None,
                    "lightsOn": None,
                    "luxUpdatedAt": "",
                }
                continue
            lux = best.get("lux")
            lux_updated = best.get("luxUpdatedAt") or ""
            sid = (best.get("sensor_id") or "").strip()
            lights_on = None
            if lux is not None:
                try:
                    lights_on = float(lux) >= LUX_LIGHTS_ON_THRESHOLD
                except (TypeError, ValueError):
                    lights_on = None
            data[key] = {
                "label": label,
                "sensor_id": sid,
                "lux": lux,
                "lightsOn": lights_on,
                "luxUpdatedAt": lux_updated,
            }
        return jsonify({"success": True, "data": data})
    except Exception as e:
        print(f"⚠️ Failed to fetch sensor badges: {e}")
        return jsonify({"success": False, "message": "Failed to fetch sensor badges"}), 500


@app.route('/api/v1/sensors/hourly_graph', methods=['GET'])
def get_hourly_sensor_graph():
    """24-point series (0–1) per logical sensor from MongoDB sensor_hourly (POST /data buckets)."""
    date_str = (request.args.get('date') or '').strip()
    if not date_str or not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return jsonify({"success": False, "message": "Missing or invalid date (YYYY-MM-DD)"}), 400
    if sensor_hourly_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503
    try:
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
            pipeline = [
                {"$match": {"date": date_str, "sensor_id": {"$in": list(ids)}}},
                {
                    "$group": {
                        "_id": "$hour",
                        "samples": {"$sum": "$samples"},
                        "bright": {"$sum": "$bright_samples"},
                    }
                },
            ]
            for row in sensor_hourly_collection.aggregate(pipeline):
                h = row.get("_id")
                if h is None:
                    continue
                try:
                    hi = int(h)
                except (TypeError, ValueError):
                    continue
                if hi < 0 or hi > 23:
                    continue
                s = int(row.get("samples") or 0)
                b = int(row.get("bright") or 0)
                arr[hi] = round(min(1.0, b / s), 4) if s > 0 else 0.0

            tot_pipeline = [
                {"$match": {"date": date_str, "sensor_id": {"$in": list(ids)}}},
                {
                    "$group": {
                        "_id": None,
                        "sm": {"$sum": "$samples"},
                        "br": {"$sum": "$bright_samples"},
                    }
                },
            ]
            tot_rows = list(sensor_hourly_collection.aggregate(tot_pipeline))
            if tot_rows:
                out["totals"][tk]["samples"] = int(tot_rows[0].get("sm") or 0)
                out["totals"][tk]["brightSamples"] = int(tot_rows[0].get("br") or 0)
        return jsonify({"success": True, "data": out})
    except Exception as e:
        print(f"⚠️ Failed hourly_graph: {e}")
        return jsonify({"success": False, "message": "Failed to load hourly graph"}), 500


@app.route('/api/usage/statistics')
def get_usage_statistics():
    """Get weekly and monthly statistics EXCLUDING today (today is tracked live in frontend)"""
    # Use PST timezone to match frontend
    pst = pytz.timezone('America/Los_Angeles')
    today = datetime.now(pst)
    today_str = today.strftime('%Y-%m-%d')
    
    # Calculate week start as SUNDAY (Python weekday: Mon=0, Sun=6)
    # So days since Sunday = (weekday + 1) % 7

    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_start_str = week_start.strftime('%Y-%m-%d')
    month_start_str = today.strftime('%Y-%m-01')
    
    weekly_seconds = 0
    monthly_seconds = 0
    
    if usage_collection is not None:
        # Only aggregate timer docs — exclude per-sensor daily_usage rows to avoid double-counting.
        week_records = list(usage_collection.find({
            "$and": [
                {"date": {"$gte": week_start_str, "$lt": today_str}},
                _daily_usage_aggregate_match(),
            ]
        }))
        weekly_seconds = sum(r.get('onSeconds', 0) for r in week_records)

        month_records = list(usage_collection.find({
            "$and": [
                {"date": {"$gte": month_start_str, "$lt": today_str}},
                _daily_usage_aggregate_match(),
            ]
        }))
        monthly_seconds = sum(r.get('onSeconds', 0) for r in month_records)
    
    return jsonify({
        "daily": 0,  # Not used - frontend tracks today live
        "weekly": weekly_seconds,
        "monthly": monthly_seconds
    })

# ===== Room-Specific Usage API =====

VALID_ROOMS = ['living', 'bedroom']

# Default sensor_id stored on room docs (same logical devices as SENSOR_ROOM_MAP / SENSOR_BADGE_GROUPS).
ROOM_PRIMARY_SENSOR_ID = {
    "living": "esp32_01",
    "bedroom": "esp32_02",
}


@app.route('/api/room/<room_name>/save', methods=['POST'])
def save_room_usage(room_name):
    """Save daily usage data for a specific room"""
    if room_name not in VALID_ROOMS:
        return jsonify({"error": f"Invalid room. Valid rooms: {VALID_ROOMS}"}), 400
    
    data = request.json
    if not data or 'date' not in data:
        return jsonify({"error": "Invalid data"}), 400

    sensor_id = (data.get('sensor_id') or '').strip() if isinstance(data, dict) else ''
    if not sensor_id:
        sensor_id = ROOM_PRIMARY_SENSOR_ID.get(room_name, "")

    room_data = {
        "date": data['date'],
        "onSeconds": data.get('onSeconds', 0),
        "avgLux": data.get('avgLux', 0),
        "updatedAt": datetime.now().isoformat(),
        "sensor_id": sensor_id,
    }
    
    if room_name in room_collections and room_collections[room_name] is not None:
        room_collections[room_name].update_one(
            {"date": data['date']},
            {"$set": room_data},
            upsert=True
        )
        return jsonify({"success": True, "room": room_name})
    return jsonify({"success": False, "message": "MongoDB not available"})

@app.route('/api/room/<room_name>/<date>')
def get_room_usage(room_name, date):
    """Get usage for a specific room on a specific date"""
    if room_name not in VALID_ROOMS:
        return jsonify({"error": f"Invalid room. Valid rooms: {VALID_ROOMS}"}), 400
    
    if room_name in room_collections and room_collections[room_name] is not None:
        record = room_collections[room_name].find_one({"date": date})
        if record:
            return jsonify({
                "_id": str(record.get('_id', '')),
                "room": room_name,
                "date": record['date'],
                "sensor_id": record.get('sensor_id', ''),
                "onSeconds": record.get('onSeconds', 0),
                "avgLux": record.get('avgLux', 0),
                "updatedAt": record.get('updatedAt', ''),
                "luxUpdatedAt": record.get('luxUpdatedAt', '')
            })
    return jsonify({
        "_id": "",
        "room": room_name,
        "date": date,
        "sensor_id": "",
        "onSeconds": 0,
        "avgLux": 0,
        "updatedAt": "",
        "luxUpdatedAt": ""
    })

@app.route('/api/room/<room_name>/statistics')
def get_room_statistics(room_name):
    """Get weekly and monthly statistics for a specific room"""
    if room_name not in VALID_ROOMS:
        return jsonify({"error": f"Invalid room. Valid rooms: {VALID_ROOMS}"}), 400
    
    pst = pytz.timezone('America/Los_Angeles')
    today = datetime.now(pst)
    today_str = today.strftime('%Y-%m-%d')
    
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    week_start_str = week_start.strftime('%Y-%m-%d')
    month_start_str = today.strftime('%Y-%m-01')
    
    weekly_seconds = 0
    monthly_seconds = 0
    
    if room_name in room_collections and room_collections[room_name] is not None:
        # This week excluding today
        week_records = list(room_collections[room_name].find({
            "date": {"$gte": week_start_str, "$lt": today_str}
        }))
        weekly_seconds = sum(r.get('onSeconds', 0) for r in week_records)
        
        # This month excluding today
        month_records = list(room_collections[room_name].find({
            "date": {"$gte": month_start_str, "$lt": today_str}
        }))
        monthly_seconds = sum(r.get('onSeconds', 0) for r in month_records)
    
    return jsonify({
        "room": room_name,
        "weekly": weekly_seconds,
        "monthly": monthly_seconds
    })

@app.route('/api/rooms/all/<date>')
def get_all_rooms_usage(date):
    """Get usage for all rooms on a specific date"""
    result = {}
    for room_name in VALID_ROOMS:
        if room_name in room_collections and room_collections[room_name] is not None:
            record = room_collections[room_name].find_one({"date": date})
            if record:
                result[room_name] = {
                    "sensor_id": record.get('sensor_id', ''),
                    "onSeconds": record.get('onSeconds', 0),
                    "avgLux": record.get('avgLux', 0)
                }
            else:
                result[room_name] = {"sensor_id": "", "onSeconds": 0, "avgLux": 0}
        else:
            result[room_name] = {"sensor_id": "", "onSeconds": 0, "avgLux": 0}
    return jsonify({"date": date, "rooms": result})

@app.route('/api/rooms/reset', methods=['POST'])
def reset_all_rooms():
    """Clear only today's room documents (PST). Previous days are kept."""
    pst = pytz.timezone('America/Los_Angeles')
    today_str = datetime.now(pst).strftime('%Y-%m-%d')
    total = 0
    for room_name in VALID_ROOMS:
        if room_name in room_collections and room_collections[room_name] is not None:
            r = room_collections[room_name].delete_many({"date": today_str})
            total += r.deleted_count
    return jsonify({
        "success": True,
        "message": "Today's room data cleared; previous days unchanged",
        "date": today_str,
        "deletedCount": total,
    })

# ===== Admin Access Logging =====

@app.route('/api/admin/access', methods=['POST'])
def log_admin_access():
    """Log admin access details (username, time, metadata)"""
    if admin_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({"success": False, "message": "Admin username is required"}), 400

    login_type = (data.get('loginType') or 'personal').strip()
    organization_name = (data.get('organizationName') or '').strip()
    if login_type == 'organization' and not organization_name:
        return jsonify({"success": False, "message": "Organization name is required"}), 400

    pst = pytz.timezone('America/Los_Angeles')
    now_pst = datetime.now(pst)

    doc = {
        "username": username,
        "loginType": login_type,
        "organizationName": organization_name if login_type == 'organization' else '',
        "accessedAt": datetime.now().isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get('User-Agent', ''),
        "path": "/info",
    }
    try:
        admin_collection.insert_one(doc)

        # If admin logged in through organization, also store in Organization collection
        if login_type == 'organization' and organization_collection is not None:
            organization_collection.insert_one({
                "adminName": username,
                "organizationName": organization_name,
                "date": now_pst.strftime('%Y-%m-%d'),
                "time": now_pst.strftime('%H:%M:%S'),
                "timestamp": now_pst.isoformat(),
                "createdAt": datetime.now().isoformat(),
            })

        return jsonify({"success": True})
    except Exception as e:
        print(f"⚠️ Failed to log admin access: {e}")
        return jsonify({"success": False, "message": "Failed to log admin access"}), 500


# ===== Alert Logging (Lights on > 40 minutes) =====

@app.route('/api/alerts', methods=['POST'])
def create_alert():
    """Create an alert when lights are on for longer than threshold (e.g., 40+ minutes)."""
    if alert_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    room_id = (data.get('room_id') or 'unknown').strip()
    duration_seconds = int(data.get('durationSeconds') or 0)
    alert_type = data.get('type', 'duration_over_40min')
    date = data.get('date') or datetime.now(pytz.timezone('America/Los_Angeles')).strftime('%Y-%m-%d')

    # Avoid duplicate alerts for the same room/day/type
    existing = alert_collection.find_one({
        "room_id": room_id,
        "date": date,
        "type": alert_type
    })
    if existing:
        return jsonify({"success": True, "skipped": True})

    doc = {
        "alert_id": str(uuid.uuid4()),
        "room_id": room_id,
        "date": date,
        "durationSeconds": duration_seconds,
        "type": alert_type,
        "createdAt": datetime.now().isoformat(),
    }
    try:
        alert_collection.insert_one(doc)
        return jsonify({"success": True})
    except Exception as e:
        print(f"⚠️ Failed to create alert: {e}")
        return jsonify({"success": False, "message": "Failed to create alert"}), 500


# ===== User Login / User Data (Dashboard access) =====

@app.route('/api/user/login', methods=['POST'])
def user_login():
    """Register on first login; validate password on subsequent logins."""
    if user_data_collection is None or users_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return jsonify({"success": False, "message": "Invalid email id"}), 400
    if not isinstance(password, str) or not password.strip():
        return jsonify({"success": False, "message": "Password is required"}), 400

    password = password.strip()

    try:
        existing_user = users_collection.find_one({"email": email})
    except Exception as e:
        print(f"⚠️ Failed to lookup user: {e}")
        return jsonify({"success": False, "message": "Login failed. Try again."}), 500

    if existing_user is None:
        # First login → create user
        try:
            users_collection.insert_one({
                "email": email,
                "passwordHash": generate_password_hash(password),
                "createdAt": datetime.now().isoformat(),
            })
        except Exception as e:
            print(f"⚠️ Failed to create user: {e}")
            return jsonify({"success": False, "message": "Failed to create user"}), 500
    else:
        # Subsequent login → validate password
        password_hash = existing_user.get("passwordHash") or ""
        if not password_hash or not check_password_hash(password_hash, password):
            return jsonify({"success": False, "message": "Invalid password"}), 401

    doc = {
        "email": email,
        "loggedInAt": datetime.now().isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get('User-Agent', ''),
    }
    try:
        user_data_collection.insert_one(doc)
        return jsonify({"success": True})
    except Exception as e:
        print(f"⚠️ Failed to save user login: {e}")
        return jsonify({"success": False, "message": "Failed to save login"}), 500


# ===== Feedback / Report an Issue =====

@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    """Store user feedback (report an issue) in the feedback collection with date and time."""
    if feedback_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({"success": False, "message": "Feedback text is required"}), 400

    pst = pytz.timezone('America/Los_Angeles')
    now_pst = datetime.now(pst)

    doc = {
        "text": text,
        "date": now_pst.strftime('%Y-%m-%d'),
        "time": now_pst.strftime('%H:%M:%S'),
        "timestamp": now_pst.isoformat(),
        "createdAt": datetime.now().isoformat(),
    }

    try:
        feedback_collection.insert_one(doc)
        return jsonify({"success": True})
    except Exception as e:
        print(f"⚠️ Failed to save feedback: {e}")
        return jsonify({"success": False, "message": "Failed to save feedback"}), 500


# ===== Device Logging (When Lights Are Turned On) =====

@app.route('/api/device/log', methods=['POST'])
def log_device():
    """Log device details when room lights or gauge lights are turned on."""
    if device_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    action_type = data.get('action_type', 'unknown')  # 'room_light_on' or 'gauge_light_on'
    room_id = data.get('room_id', '')  # Only present for room lights
    room_name = data.get('room_name', '')  # Human-readable room name
    
    # Use PST timezone to match frontend
    pst = pytz.timezone('America/Los_Angeles')
    now_pst = datetime.now(pst)
    
    doc = {
        "action_type": action_type,
        "room_id": room_id if action_type == 'room_light_on' else None,
        "room_name": room_name if action_type == 'room_light_on' else None,
        "date": now_pst.strftime('%Y-%m-%d'),
        "time": now_pst.strftime('%H:%M:%S'),
        "timestamp": now_pst.isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get('User-Agent', ''),
        "createdAt": datetime.now().isoformat(),
    }
    
    try:
        device_collection.insert_one(doc)
        return jsonify({"success": True})
    except Exception as e:
        print(f"⚠️ Failed to log device: {e}")
        return jsonify({"success": False, "message": "Failed to log device"}), 500


# Documented API list (22 total: OpenAPI paths + Swagger UI; same as diagram / Info modal).
DOCUMENTED_APIS = [
    ('GET', '/', 'Dashboard page'),
    ('GET', '/diagram', 'Architecture diagram page'),
    ('GET', '/api/docs', 'Swagger UI (interactive API docs)'),
    ('GET', '/api/sensor', 'Simulated sensor reading'),
    ('POST', '/api/v1/sensors/register', 'Register sensor device'),
    ('POST', '/api/v1/sensors/data', 'Submit lux sensor reading'),
    ('GET', '/api/v1/sensors/{sensor_id}/status', 'Sensor status by ID'),
    ('GET', '/api/v1/sensors/latest', 'Latest lux from daily_usage'),
    ('GET', '/api/v1/sensors/badges', 'Per-sensor status for dashboard pills'),
    ('GET', '/api/v1/sensors/hourly_graph', 'Hourly graph from sensor_hourly (query date)'),
    ('POST', '/api/usage/save', 'Save daily usage'),
    ('GET', '/api/usage/{date}', 'Get usage for date'),
    ('GET', '/api/usage/statistics', 'Weekly and monthly stats'),
    ('POST', '/api/room/{room}/save', 'Save room usage'),
    ('GET', '/api/room/{room}/{date}', 'Get room data for date'),
    ('GET', '/api/room/{room}/statistics', 'Room weekly and monthly stats'),
    ('GET', '/api/rooms/all/{date}', 'All rooms for date'),
    ('POST', '/api/admin/access', 'Log admin access'),
    ('POST', '/api/alerts', 'Create long-on alert'),
    ('POST', '/api/user/login', 'User login (email and password)'),
    ('POST', '/api/feedback', 'Report an issue'),
    ('POST', '/api/device/log', 'Log device when lights turn on'),
]


def sync_api_routes_text_to_mongodb():
    """Write the documented API list as plain text into the API collection (fixed manifest, not url_map)."""
    if api_collection is None:
        return
    lines = [f'{m} {p}  --  {d}' for m, p, d in DOCUMENTED_APIS]
    text = '\n'.join(lines)
    try:
        api_collection.replace_one(
            {'name': 'api_manifest'},
            {
                'name': 'api_manifest',
                'apisText': text,
                'lineCount': len(DOCUMENTED_APIS),
                'updatedAt': datetime.now().isoformat(),
            },
            upsert=True,
        )
        print(f"📦 Collection '{API_COLLECTION_NAME}': stored {len(DOCUMENTED_APIS)} documented APIs as text")
    except Exception as e:
        print(f"⚠️ Failed to sync {API_COLLECTION_NAME} collection: {e}")


sync_api_routes_text_to_mongodb()

if __name__ == '__main__':
    for i in range(20):
        lux = generate_sensor_reading()
        sensor_history.append({
            "lux": round(lux, 1),
            "timestamp": (datetime.now() - timedelta(seconds=(20-i)*3)).isoformat(),
            "status": get_sensor_status(lux)
        })
    
    app.run(debug=True, port=5001)
