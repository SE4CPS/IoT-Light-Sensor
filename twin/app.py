import os
import hashlib
import json
import uuid
import pytz

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from pymongo import MongoClient, ASCENDING

load_dotenv()

app = Flask(__name__)


# -----------------------------
# MongoDB helpers
# -----------------------------
def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name} in .env")
    return value


def _client() -> MongoClient:
    return MongoClient(_get_required_env("MONGO_URI"))


def _db():
    db_name = os.getenv("DB_NAME", "light_sensor_db")
    return _client()[db_name]


def _readings_collection():
    col = _db()["readings"]
    col.create_index([("device_id", ASCENDING), ("ts", ASCENDING)])
    return col


def _usage_collection():
    return _db()["daily_usage"]


def _admin_collection():
    return _db()["admin_access"]


# -----------------------------
# Utility helpers
# -----------------------------
def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def generate_usage_checksum(doc):
    payload = {
        "uuid": doc.get("uuid"),
        "date": doc.get("date"),
        "on_duration_seconds": doc.get("on_duration_seconds"),
        "off_duration_seconds": doc.get("off_duration_seconds"),
        "updated_at_utc": str(doc.get("updated_at_utc")),
        "time_unit": doc.get("time_unit"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def generate_admin_checksum(doc):
    payload = {
        "username": doc.get("username"),
        "access_at": str(doc.get("access_at")),
        "role": doc.get("role"),
        "uuid": doc.get("uuid"),
        "user_ip_address": doc.get("user_ip_address"),
        "user_agent": doc.get("user_agent"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def _parse_hours(default: int = 24) -> int:
    try:
        h = int(request.args.get("hours", default))
        return max(1, min(168, h))
    except Exception:
        return default


def _parse_limit(default: int = 500) -> int:
    try:
        n = int(request.args.get("limit", default))
        return max(50, min(5000, n))
    except Exception:
        return default


# -----------------------------
# Readings API
# -----------------------------
@app.get("/api/readings")
def api_readings():
    device_id = request.args.get("device_id") or os.getenv("DEVICE_ID", "ls-100-0001")
    hours = _parse_hours(24)
    limit = _parse_limit(1000)

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    query = {
        "device_id": device_id,
        "ts": {"$gte": start, "$lt": end}
    }

    docs = list(
        _readings_collection()
        .find(
            query,
            {
                "_id": 0,
                "ts": 1,
                "lux_pred": 1,
                "lux_obs": 1,
                "cloud_cover": 1,
                "flags": 1,
            },
        )
        .sort("ts", 1)
        .limit(limit)
    )

    readings = []
    for doc in docs:
        ts = doc.get("ts")
        readings.append({
            "ts": ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if ts else None,
            "lux_pred": float(doc.get("lux_pred", 0.0)),
            "lux_obs": float(doc.get("lux_obs", 0.0)),
            "cloud_cover": float(doc.get("cloud_cover", 0.0)),
            "flags": doc.get("flags", {}),
        })

    return jsonify({
        "device_id": device_id,
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "count": len(readings),
        "readings": readings,
    })


# -----------------------------
# Daily usage API
# -----------------------------
@app.route("/api/usage/save", methods=["POST"])
def save_usage():
    data = request.json or {}

    if "date" not in data:
        return jsonify({"success": False, "message": "date is required"}), 400

    usage_collection = _usage_collection()
    existing = usage_collection.find_one({"date": data["date"]})

    now_utc = datetime.now(pytz.UTC)
    on_seconds = safe_int(data.get("onSeconds", 0))
    off_seconds = 86400 - on_seconds

    usage_doc = {
        "uuid": existing.get("uuid") if existing else str(uuid.uuid4()),
        "date": data["date"],
        "on_duration_seconds": on_seconds,
        "off_duration_seconds": off_seconds,
        "updated_at_utc": now_utc,
        "created_at_utc": existing.get("created_at_utc") if existing else now_utc,
        "time_unit": "seconds",
    }

    usage_doc["checksum"] = generate_usage_checksum(usage_doc)

    usage_collection.update_one(
        {"date": data["date"]},
        {"$set": usage_doc},
        upsert=True
    )

    return jsonify({
        "success": True,
        "uuid": usage_doc["uuid"],
        "checksum": usage_doc["checksum"]
    }), 200


@app.get("/api/usage/statistics")
def get_usage_statistics():
    usage_collection = _usage_collection()

    pst = pytz.timezone("America/Los_Angeles")
    today = datetime.now(pst)
    today_str = today.strftime("%Y-%m-%d")

    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_start_str = week_start.strftime("%Y-%m-%d")
    month_start_str = today.strftime("%Y-%m-01")

    week_records = list(
        usage_collection.find({"date": {"$gte": week_start_str, "$lt": today_str}})
    )
    month_records = list(
        usage_collection.find({"date": {"$gte": month_start_str, "$lt": today_str}})
    )
    weekly_seconds = sum(
    safe_int(r.get("on_duration_seconds", r.get("onSeconds", 0)))
    for r in week_records
)
    monthly_seconds = sum(
        safe_int(r.get("on_duration_seconds", r.get("onSeconds", 0)))
        for r in month_records
    )

    return jsonify({
        "daily": 0,
        "weekly": weekly_seconds,
        "monthly": monthly_seconds,
    })


# -----------------------------
# Admin access API
# -----------------------------
@app.route("/api/admin/access", methods=["POST"])
def log_admin_access():
    data = request.json or {}
    username = (data.get("username") or "").strip()

    if not username:
        return jsonify({"success": False, "message": "username is required"}), 400

    admin_collection = _admin_collection()
    now_utc = datetime.now(pytz.UTC)

    admin_doc = {
        "username": username,
        "access_at": now_utc,
        "role": "admin_access",
        "uuid": str(uuid.uuid4()),
        "user_ip_address": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", ""),
    }

    admin_doc["checksum"] = generate_admin_checksum(admin_doc)

    admin_collection.insert_one(admin_doc)

    return jsonify({
        "success": True,
        "uuid": admin_doc["uuid"],
        "checksum": admin_doc["checksum"]
    }), 201


# -----------------------------
# Frontend
# -----------------------------
@app.get("/")
def index():
    device_id = request.args.get("device_id") or os.getenv("DEVICE_ID", "ls-100-0001")
    hours = _parse_hours(24)

    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Light Sensor Timeline</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3"></script>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 22px; }
    .row { display:flex; gap:14px; flex-wrap:wrap; align-items:end; }
    .card { border:1px solid #ddd; border-radius:12px; padding:14px; max-width:1100px; }
    label { font-size: 12px; color:#444; display:block; margin-bottom:6px; }
    input { padding:8px 10px; border:1px solid #ccc; border-radius:10px; }
    button { padding:9px 12px; border:1px solid #333; border-radius:10px; background:#111; color:#fff; cursor:pointer; }
    button:disabled { opacity:0.6; cursor:not-allowed; }
    .meta { color:#666; font-size:12px; margin-top:8px; white-space:pre-wrap; }
    canvas { width:100% !important; height:420px !important; }
  </style>
</head>
<body>
  <div class="card">
    <h2 style="margin:0 0 10px 0;">Light Sensor Timeline</h2>

    <div class="row">
      <div>
        <label>device_id</label>
        <input id="deviceId" value="{{ device_id }}" style="min-width:220px;" />
      </div>
      <div>
        <label>hours</label>
        <input id="hours" type="number" min="1" max="168" value="{{ hours }}" style="width:100px;" />
      </div>
      <div>
        <label>&nbsp;</label>
        <button id="loadBtn">Load</button>
      </div>
    </div>

    <div class="meta" id="meta"></div>
    <div style="margin-top:14px;">
      <canvas id="chart"></canvas>
    </div>
  </div>

<script>
let chart;

function setMeta(txt) {
  document.getElementById("meta").textContent = txt || "";
}

async function loadData() {
  const btn = document.getElementById("loadBtn");
  btn.disabled = true;
  setMeta("Loading...");

  const deviceId = document.getElementById("deviceId").value.trim();
  const hours = Number(document.getElementById("hours").value || 24);

  const url = `/api/readings?device_id=${encodeURIComponent(deviceId)}&hours=${encodeURIComponent(hours)}&limit=2000`;
  const res = await fetch(url);

  if (!res.ok) {
    setMeta(`Error: ${res.status} ${res.statusText}`);
    btn.disabled = false;
    return;
  }

  const data = await res.json();

  const pointsPred = data.readings.map(r => ({ x: r.ts, y: r.lux_pred }));
  const pointsObs = data.readings.map(r => ({ x: r.ts, y: r.lux_obs }));

  const negCount = data.readings.filter(r => r.flags && r.flags.is_negative).length;
  const highCount = data.readings.filter(r => r.flags && r.flags.is_impossible_high).length;
  const stuckCount = data.readings.filter(r => r.flags && r.flags.is_stuck).length;

  setMeta(
`device_id: ${data.device_id}
window:   ${data.start}  →  ${data.end}
count:    ${data.count}
flags:    negative=${negCount}, impossible_high=${highCount}, stuck=${stuckCount}`
  );

  const ctx = document.getElementById("chart").getContext("2d");
  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "lux_pred",
          data: pointsPred,
          tension: 0.15,
          borderWidth: 2,
          pointRadius: 0
        },
        {
          label: "lux_obs",
          data: pointsObs,
          tension: 0.15,
          borderWidth: 2,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true },
        tooltip: { enabled: true }
      },
      scales: {
        x: {
          type: "time",
          time: { tooltipFormat: "PPpp" },
          ticks: { maxRotation: 0 }
        },
        y: {
          title: { display: true, text: "lux" }
        }
      }
    }
  });

  btn.disabled = false;
}

document.getElementById("loadBtn").addEventListener("click", loadData);
loadData();
</script>
</body>
</html>
    """
    return render_template_string(html, device_id=device_id, hours=hours)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)