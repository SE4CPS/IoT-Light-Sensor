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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')

# MongoDB Atlas Connection (loaded from .env file for security)
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'light_sensor_db')

if not MONGO_URI:
    print("⚠️ MONGO_URI not found in .env file")
    db = None
    usage_collection = None
    room_collections = {}
    admin_collection = None
    alert_collection = None
    device_collection = None
    user_data_collection = None
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
        
        # Room-specific collections
        room_collections = {
            'living': db['room_living'],
            'bedroom': db['room_bedroom'],
            'kitchen': db['room_kitchen'],
            'bathroom': db['room_bathroom'],
            'office': db['room_office'],
            'garage': db['room_garage']
        }

        # Admin access/log collection
        admin_collection = db['admin_access']
        # Alert collection for long-on durations / warnings
        alert_collection = db['alerts']
        # Device collection for logging device details when lights are turned on
        device_collection = db['devices']
        # User login / user data collection (email, login time, etc.)
        user_data_collection = db['user_data']
        
        print("✅ Connected to MongoDB Atlas")
        print("📦 Room collections: living, bedroom, kitchen, bathroom, office, garage")
        print("📦 Admin collection: admin_access")
        print("📦 Device collection: devices")
        print("📦 User data collection: user_data")
    except ConnectionFailure as e:
        print(f"⚠️ MongoDB not available. Error: {e}")
        db = None
        usage_collection = None
        room_collections = {}
        admin_collection = None
        alert_collection = None
        device_collection = None
        user_data_collection = None
    except Exception as e:
        print(f"⚠️ MongoDB connection error: {e}")
        db = None
        usage_collection = None
        room_collections = {}
        admin_collection = None
        alert_collection = None
        device_collection = None
        user_data_collection = None

# Simulated sensor data storage
sensor_history = []

sensor_history_by_id = {}

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
    return render_template('diagram.html')

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
        
@app.route("/api/v1/sensors/data", methods=["POST"])
def submit_single_sensor_reading():
    data = request.get_json(silent=True) or {}

    sensor_id = data.get("sensor_id")
    lux = data.get("lux")

    if not sensor_id or not isinstance(sensor_id, str):
        return jsonify({"success": False, "error": "Missing or invalid 'sensor_id'"}), 400

    try:
        lux = float(lux)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Missing or invalid 'lux'"}), 400

    timestamp = data.get("timestamp") or now_iso()

    reading = {
        "sensor_id": sensor_id,
        "lux": round(lux, 1),
        "timestamp": timestamp,
        "status": get_sensor_status(lux)
    }

    sensor_history_by_id.setdefault(sensor_id, []).append(reading)
    keep_last_n(sensor_history_by_id[sensor_id], 50)

    # keep your original global history working
    sensor_history.append(reading)
    keep_last_n(sensor_history, 50)

    return jsonify({"success": True, "reading": reading}), 201

# ===== MongoDB Usage API =====

@app.route('/api/usage/reset', methods=['POST'])
def reset_usage():
    """Reset all usage data"""
    if usage_collection is not None:
        usage_collection.delete_many({})
        return jsonify({"success": True, "message": "All data cleared"})
    return jsonify({"success": False, "message": "MongoDB not available"})

@app.route('/api/usage/save', methods=['POST'])
def save_usage():
    """Save daily usage data"""
    data = request.json
    
    if not data or 'date' not in data:
        return jsonify({"error": "Invalid data"}), 400
    
    usage_data = {
        "date": data['date'],
        "onSeconds": data.get('onSeconds', 0),
        "offSeconds": 86400 - data.get('onSeconds', 0),
        "updatedAt": datetime.now().isoformat()
    }
    
    if usage_collection is not None:
        usage_collection.update_one(
            {"date": data['date']},
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
                "date": record['date'],
                "onSeconds": record.get('onSeconds', 0),
                "offSeconds": record.get('offSeconds', 0)
            })
    return jsonify({"date": date, "onSeconds": 0, "offSeconds": 86400})

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
        # This week EXCLUDING today (frontend adds live dailySeconds)
        week_records = list(usage_collection.find({
            "date": {"$gte": week_start_str, "$lt": today_str}
        }))
        weekly_seconds = sum(r.get('onSeconds', 0) for r in week_records)
        
        # This month EXCLUDING today (frontend adds live dailySeconds)
        month_records = list(usage_collection.find({
            "date": {"$gte": month_start_str, "$lt": today_str}
        }))
        monthly_seconds = sum(r.get('onSeconds', 0) for r in month_records)
    
    return jsonify({
        "daily": 0,  # Not used - frontend tracks today live
        "weekly": weekly_seconds,
        "monthly": monthly_seconds
    })

# ===== Room-Specific Usage API =====

VALID_ROOMS = ['living', 'bedroom', 'kitchen', 'bathroom', 'office', 'garage']

@app.route('/api/room/<room_name>/save', methods=['POST'])
def save_room_usage(room_name):
    """Save daily usage data for a specific room"""
    if room_name not in VALID_ROOMS:
        return jsonify({"error": f"Invalid room. Valid rooms: {VALID_ROOMS}"}), 400
    
    data = request.json
    if not data or 'date' not in data:
        return jsonify({"error": "Invalid data"}), 400
    
    room_data = {
        "date": data['date'],
        "onSeconds": data.get('onSeconds', 0),
        "avgLux": data.get('avgLux', 0),
        "updatedAt": datetime.now().isoformat()
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
                "room": room_name,
                "date": record['date'],
                "onSeconds": record.get('onSeconds', 0),
                "avgLux": record.get('avgLux', 0)
            })
    return jsonify({"room": room_name, "date": date, "onSeconds": 0, "avgLux": 0})

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
                    "onSeconds": record.get('onSeconds', 0),
                    "avgLux": record.get('avgLux', 0)
                }
            else:
                result[room_name] = {"onSeconds": 0, "avgLux": 0}
        else:
            result[room_name] = {"onSeconds": 0, "avgLux": 0}
    return jsonify({"date": date, "rooms": result})

@app.route('/api/rooms/reset', methods=['POST'])
def reset_all_rooms():
    """Reset all room usage data"""
    for room_name in VALID_ROOMS:
        if room_name in room_collections and room_collections[room_name] is not None:
            room_collections[room_name].delete_many({})
    return jsonify({"success": True, "message": "All room data cleared"})

# ===== Admin Access Logging =====

@app.route('/api/admin/access', methods=['POST'])
def log_admin_access():
    """Log admin access details (username, time, metadata)"""
    if admin_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    username = (data.get('username') or '').strip() or 'unknown'

    doc = {
        "username": username,
        "accessedAt": datetime.now().isoformat(),
        "ip": request.remote_addr,
        "userAgent": request.headers.get('User-Agent', ''),
        "path": "/info",
    }
    try:
        admin_collection.insert_one(doc)
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
    """Save user login to user_data collection (email + metadata). Password is not stored."""
    if user_data_collection is None:
        return jsonify({"success": False, "message": "MongoDB not available"}), 503

    data = request.json or {}
    email = (data.get('email') or '').strip()
    # We do not store the password in the database for security
    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

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

if __name__ == '__main__':
    for i in range(20):
        lux = generate_sensor_reading()
        sensor_history.append({
            "lux": round(lux, 1),
            "timestamp": (datetime.now() - timedelta(seconds=(20-i)*3)).isoformat(),
            "status": get_sensor_status(lux)
        })
    
    app.run(debug=True, port=5001)
