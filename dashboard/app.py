from flask import Flask, render_template, jsonify, request
import random
import certifi
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

app = Flask(__name__, static_folder='static', static_url_path='/static')

# MongoDB Atlas Connection
MONGO_URI = "mongodb+srv://SEI4-0:uopsensor@cluster0.oryfr44.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "light_sensor_db"

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

@app.route('/api/sensor')
def get_sensor_data():
    """Get current sensor reading"""
    lux = generate_sensor_reading()
    status = get_sensor_status(lux)
    timestamp = datetime.now().isoformat()
    
    reading = {
        "lux": round(lux, 1),
        "timestamp": timestamp,
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
        return jsonify({"avg": 0, "min": 0, "max": 0, "readings": 0})
    
    lux_values = [r["lux"] for r in sensor_history]
    return jsonify({
        "avg": round(sum(lux_values) / len(lux_values), 1),
        "min": round(min(lux_values), 1),
        "max": round(max(lux_values), 1),
        "readings": len(sensor_history)
    })

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
    """Get daily, weekly, and monthly statistics"""
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    week_start_str = week_start.strftime('%Y-%m-%d')
    month_start_str = today.strftime('%Y-%m-01')
    
    daily_seconds = 0
    weekly_seconds = 0
    monthly_seconds = 0
    
    if usage_collection is not None:
        # Today
        today_record = usage_collection.find_one({"date": today_str})
        if today_record:
            daily_seconds = today_record.get('onSeconds', 0)
        
        # This week
        week_records = list(usage_collection.find({
            "date": {"$gte": week_start_str, "$lte": today_str}
        }))
        weekly_seconds = sum(r.get('onSeconds', 0) for r in week_records)
        
        # This month
        month_records = list(usage_collection.find({
            "date": {"$gte": month_start_str, "$lte": today_str}
        }))
        monthly_seconds = sum(r.get('onSeconds', 0) for r in month_records)
    
    return jsonify({
        "daily": daily_seconds,
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
