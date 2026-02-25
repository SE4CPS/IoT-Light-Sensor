from flask import Flask, render_template, jsonify, request
import random
import certifi
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import pytz

app = Flask(__name__, static_folder='static', static_url_path='/static')

# MongoDB Atlas Connection
MONGO_URI = ""
DB_NAME = ""

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
    print("✅ Connected to MongoDB Atlas")
except ConnectionFailure as e:
    print(f"⚠️ MongoDB not available. Error: {e}")
    db = None
    usage_collection = None
except Exception as e:
    print(f"⚠️ MongoDB connection error: {e}")
    db = None
    usage_collection = None

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
    
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
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

if __name__ == '__main__':
    for i in range(20):
        lux = generate_sensor_reading()
        sensor_history.append({
            "lux": round(lux, 1),
            "timestamp": (datetime.now() - timedelta(seconds=(20-i)*3)).isoformat(),
            "status": get_sensor_status(lux)
        })
    
    app.run(debug=True, port=5001)
