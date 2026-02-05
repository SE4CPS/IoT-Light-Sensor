# app.py
#
# Simple Flask page that loads MongoDB light sensor readings and shows a timeline chart.
# Uses Chart.js with a time axis.
#
# Requirements:
#   pip install flask pymongo python-dotenv
#
# .env:
#   MONGO_URI=...
#   DB_NAME=light_sensor_db
#   DEVICE_ID=ls-100-0001   # optional

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from pymongo import MongoClient, ASCENDING

load_dotenv()

app = Flask(__name__)


def _get_required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing {name} (check .env)")
    return v


def _client() -> MongoClient:
    return MongoClient(_get_required_env("MONGO_URI"))


def _collection():
    db_name = os.getenv("DB_NAME", "light_sensor_db")
    col = _client()[db_name]["readings"]
    col.create_index([("device_id", ASCENDING), ("ts", ASCENDING)])
    return col


def _parse_hours(default: int = 24) -> int:
    try:
        h = int(request.args.get("hours", default))
        return max(1, min(168, h))  # 1..168 hours
    except Exception:
        return default


def _parse_limit(default: int = 500) -> int:
    try:
        n = int(request.args.get("limit", default))
        return max(50, min(5000, n))
    except Exception:
        return default


@app.get("/api/readings")
def api_readings():
    device_id = request.args.get("device_id") or os.getenv("DEVICE_ID", "ls-100-0001")
    hours = _parse_hours(24)
    limit = _parse_limit(1000)

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    q = {"device_id": device_id, "ts": {"$gte": start, "$lt": end}}
    docs = list(
        _collection()
        .find(q, {"_id": 0, "ts": 1, "lux_pred": 1, "lux_obs": 1, "cloud_cover": 1, "flags": 1})
        .sort("ts", 1)
        .limit(limit)
    )

    # Convert datetime -> ISO8601 string for the browser
    out = []
    for d in docs:
        ts = d.get("ts")
        out.append(
            {
                "ts": ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if ts else None,
                "lux_pred": float(d.get("lux_pred", 0.0)),
                "lux_obs": float(d.get("lux_obs", 0.0)),
                "cloud_cover": float(d.get("cloud_cover", 0.0)),
                "flags": d.get("flags", {}),
            }
        )

    return jsonify(
        {
            "device_id": device_id,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "count": len(out),
            "readings": out,
        }
    )


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
  const pointsObs  = data.readings.map(r => ({ x: r.ts, y: r.lux_obs }));

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
    # Traditional dev run
    app.run(host="127.0.0.1", port=5000, debug=True)