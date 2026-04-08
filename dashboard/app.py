from flask import Flask, render_template, jsonify, request
import random
import certifi
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pytz
from dotenv import load_dotenv
import uuid
import traceback
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')

# =============================
# MongoDB Connection
# =============================

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'light_sensor_db')

if not MONGO_URI:
    print("⚠️ MONGO_URI not found in .env")
    db = None
    usage_collection = None
    room_collections = {}
    admin_collection = None
    alert_collection = None
    device_collection = None
    user_data_collection = None
    users_collection = None
    page_logs_collection = None
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

        room_collections = {
            'living': db['room_living'],
            'bedroom': db['room_bedroom'],
            'kitchen': db['room_kitchen'],
            'bathroom': db['room_bathroom'],
            'office': db['room_office'],
            'garage': db['room_garage']
        }

        admin_collection = db['admin_access']
        alert_collection = db['alerts']
        device_collection = db['devices']
        user_data_collection = db['user_data']
        users_collection = db['users']
        page_logs_collection = db['page_logs']

        print("✅ MongoDB Atlas Connected")

    except ConnectionFailure as e:
        print(f"⚠️ MongoDB connection failed: {e}")
        db = None


# =============================
# Sensor Simulation
# =============================

sensor_history = []

def generate_sensor_reading():

    hour = datetime.now().hour

    if 6 <= hour <= 18:
        base = 25 + (15 * (1 - abs(hour - 12) / 6))
    else:
        base = 10

    noise = random.gauss(0, 5)

    return max(0, min(50, base + noise))


def get_sensor_status(lux):

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


# =============================
# Dashboard Pages
# =============================

@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/diagram')
def diagram():
    return render_template('diagram.html')


# =============================
# Sensor APIs
# =============================

@app.route('/api/sensor')
def get_sensor_data():

    lux = generate_sensor_reading()
    status = get_sensor_status(lux)

    reading = {
        "lux": round(lux, 1),
        "timestamp": datetime.now().isoformat(),
        "status": status
    }

    sensor_history.append(reading)

    if len(sensor_history) > 50:
        sensor_history.pop(0)

    return jsonify(reading)


@app.route('/api/history')
def get_history():
    return jsonify(sensor_history)


@app.route('/api/stats')
def get_stats():

    if not sensor_history:
        return jsonify({
            "avg": 0,
            "min": 0,
            "max": 0,
            "readings": 0
        })

    lux_values = [r["lux"] for r in sensor_history]

    return jsonify({
        "avg": round(sum(lux_values) / len(lux_values), 1),
        "min": round(min(lux_values), 1),
        "max": round(max(lux_values), 1),
        "readings": len(sensor_history)
    })


# =============================
# Page Logging
# =============================

@app.route('/api/page/log', methods=['POST'])
def log_page_activity():

    if page_logs_collection is None:
        return jsonify({"success": False}), 503

    data = request.json or {}

    pst = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pst)

    doc = {
        "event": data.get("event", "page_visit"),
        "page": data.get("page", "unknown"),
        "action": data.get("action", ""),
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "ip": request.remote_addr,
        "userAgent": request.headers.get("User-Agent"),
        "metadata": data.get("metadata", {})
    }

    page_logs_collection.insert_one(doc)

    return jsonify({"success": True})


# =============================
# Device Logs
# =============================

@app.route('/api/device/log', methods=['POST'])
def log_device():

    if device_collection is None:
        return jsonify({"success": False}), 503

    data = request.json or {}

    pst = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pst)

    doc = {
        "action_type": data.get("action_type"),
        "room_id": data.get("room_id"),
        "room_name": data.get("room_name"),
        "date": now.strftime('%Y-%m-%d'),
        "time": now.strftime('%H:%M:%S'),
        "timestamp": now.isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get("User-Agent")
    }

    device_collection.insert_one(doc)

    return jsonify({"success": True})


# =============================
# Admin Access Logs
# =============================

@app.route('/api/admin/access', methods=['POST'])
def log_admin_access():

    if admin_collection is None:
        return jsonify({"success": False}), 503

    data = request.json or {}

    doc = {
        "username": data.get("username"),
        "accessedAt": datetime.now().isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get("User-Agent"),
        "path": "/info"
    }

    admin_collection.insert_one(doc)

    return jsonify({"success": True})


# =============================
# Alerts
# =============================

@app.route('/api/alerts', methods=['POST'])
def create_alert():

    if alert_collection is None:
        return jsonify({"success": False}), 503

    data = request.json or {}

    pst = pytz.timezone('America/Los_Angeles')

    doc = {
        "alert_id": str(uuid.uuid4()),
        "room_id": data.get("room_id"),
        "durationSeconds": data.get("durationSeconds"),
        "type": data.get("type", "duration_over_40min"),
        "date": datetime.now(pst).strftime('%Y-%m-%d'),
        "createdAt": datetime.now().isoformat()
    }

    alert_collection.insert_one(doc)

    return jsonify({"success": True})


# =============================
# User Login
# =============================

@app.route('/api/user/login', methods=['POST'])
def user_login():

    if user_data_collection is None or users_collection is None:
        return jsonify({"success": False}), 503

    data = request.json or {}

    email = data.get("email")
    password = data.get("password")

    existing = users_collection.find_one({"email": email})

    if existing is None:

        password_hash = generate_password_hash(password)

        users_collection.insert_one({
            "email": email,
            "password_hash": password_hash,
            "createdAt": datetime.now().isoformat()
        })

        user_data_collection.insert_one({
            "email": email,
            "loggedInAt": datetime.now().isoformat()
        })

        return jsonify({"success": True})

    if check_password_hash(existing["password_hash"], password):

        user_data_collection.insert_one({
            "email": email,
            "loggedInAt": datetime.now().isoformat()
        })

        return jsonify({"success": True})

    return jsonify({"success": False}), 401


# =============================
# Error Logging
# =============================

@app.errorhandler(Exception)
def log_error(error):

    if page_logs_collection is not None:

        doc = {
            "event": "error",
            "error_type": type(error).__name__,
            "message": str(error),
            "stack_trace": traceback.format_exc(),
            "path": request.path,
            "method": request.method,
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.remote_addr,
            "userAgent": request.headers.get("User-Agent")
        }

        page_logs_collection.insert_one(doc)

    return jsonify({"error": "Internal server error"}), 500


# =============================
# Run Server
# =============================

if __name__ == '__main__':

    for i in range(20):

        lux = generate_sensor_reading()

        sensor_history.append({
            "lux": round(lux, 1),
            "timestamp": (datetime.now() - timedelta(seconds=(20-i)*3)).isoformat(),
            "status": get_sensor_status(lux)
        })

    app.run(debug=True, port=5001)