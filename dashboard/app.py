from flask import Flask, render_template, jsonify, request, send_file
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

# ================== CONFIG ==================
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

app = Flask(__name__, static_folder='static', static_url_path='/static')

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'light_sensor_db')

pst = pytz.timezone('America/Los_Angeles')

# ================== HELPERS ==================
def now_pst():
    return datetime.now(pst)

def now_iso():
    return datetime.now().isoformat()

def success(data=None):
    return jsonify({"success": True, "data": data or {}})

def error(message, code=400):
    return jsonify({"success": False, "message": message}), code

# ================== DB ==================
def init_db():
    if not MONGO_URI:
        print("⚠️ MONGO_URI not found")
        return None
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=10000,
            tls=True,
            tlsCAFile=certifi.where()
        )
        client.admin.command('ping')
        print("✅ Connected to MongoDB")
        return client[DB_NAME]
    except Exception as e:
        print(f"⚠️ MongoDB Error: {e}")
        return None

db = init_db()

def col(name):
    return db[name] if db else None

usage_collection = col('daily_usage')
sensor_latest_collection = col('sensor_latest')
sensor_hourly_collection = col('sensor_hourly')
users_collection = col('users')
user_data_collection = col('user_data')

# ================== SWAGGER ==================
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
    path = os.path.join(app.root_path, 'swagger', 'swagger.yaml')
    if not os.path.isfile(path):
        return error("swagger spec not found", 404)
    return send_file(path, mimetype='text/yaml')

# ================== SENSOR ==================
def generate_sensor_reading():
    hour = datetime.now().hour
    base = 25 if 6 <= hour <= 18 else 10
    return max(0, min(50, base + random.gauss(0, 5)))

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# ================== SENSOR DATA ==================
@app.route("/api/v1/sensors/data", methods=["POST"])
def submit_sensor():
    if not usage_collection:
        return error("MongoDB not available", 503)

    data = request.get_json(silent=True) or {}

    if "lux" not in data:
        return error("Missing lux")

    try:
        lux = float(data["lux"])
    except:
        return error("Invalid lux")

    sensor_id = (data.get("sensor_id") or "").strip()

    now = now_pst()
    today = now.strftime('%Y-%m-%d')

    usage_collection.update_one(
        {"date": today, "sensor_id": sensor_id},
        {
            "$set": {
                "lux": lux,
                "updatedAt": now_iso(),
                "luxUpdatedAt": now.isoformat()
            },
            "$setOnInsert": {
                "onSeconds": 0,
                "offSeconds": 86400
            }
        },
        upsert=True
    )

    return success({
        "sensor_id": sensor_id,
        "lux": lux,
        "date": today
    })

# ================== LATEST ==================
@app.route('/api/v1/sensors/latest')
def latest():
    if not usage_collection:
        return error("MongoDB not available", 503)

    record = usage_collection.find_one(
        {"lux": {"$ne": None}},
        sort=[("luxUpdatedAt", -1)]
    )

    if not record:
        return error("No data found", 404)

    return success({
        "sensor_id": record.get("sensor_id"),
        "lux": record.get("lux"),
        "date": record.get("date"),
        "onSeconds": record.get("onSeconds", 0)
    })

# ================== USER LOGIN ==================
@app.route('/api/user/login', methods=['POST'])
def login():
    if not users_collection or not user_data_collection:
        return error("MongoDB not available", 503)

    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email:
        return error("Email required")

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error("Invalid email")

    if not password:
        return error("Password required")

    user = users_collection.find_one({"email": email})

    if not user:
        users_collection.insert_one({
            "email": email,
            "passwordHash": generate_password_hash(password),
            "createdAt": now_iso()
        })
    else:
        if not check_password_hash(user.get("passwordHash", ""), password):
            return error("Invalid password", 401)

    user_data_collection.insert_one({
        "email": email,
        "loggedInAt": now_iso(),
        "ip": request.remote_addr
    })

    return success()

# ================== USAGE ==================
@app.route('/api/usage/<date>')
def usage(date):
    if not usage_collection:
        return error("MongoDB not available", 503)

    record = usage_collection.find_one({"date": date})

    if not record:
        return success({
            "date": date,
            "onSeconds": 0,
            "offSeconds": 86400
        })

    return success({
        "date": record["date"],
        "onSeconds": record.get("onSeconds", 0),
        "offSeconds": record.get("offSeconds", 0),
        "lux": record.get("lux")
    })

# ================== RESET ==================
@app.route('/api/usage/reset', methods=['POST'])
def reset():
    if not usage_collection:
        return error("MongoDB not available", 503)

    today = now_pst().strftime('%Y-%m-%d')
    result = usage_collection.delete_many({"date": today})

    return success({
        "deleted": result.deleted_count,
        "date": today
    })

# ================== RUN ==================
if __name__ == '__main__':
    app.run(debug=True, port=5001)