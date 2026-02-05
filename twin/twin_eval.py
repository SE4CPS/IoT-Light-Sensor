# twin_eval.py
#
# Reads digital twin data from MongoDB Atlas and evaluates behavior:
# - error metrics between predicted and observed
# - percent within tolerance band
# - peak time sanity (midday peak)
# - anomaly counts (negative, impossible high)
#
# Requires:
#   pip install pymongo python-dotenv
#
# .env:
#   MONGO_URI=...
#   DB_NAME=light_sensor_db

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()


def _get_required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing {name} (check .env)")
    return v


def _client() -> MongoClient:
    return MongoClient(_get_required_env("MONGO_URI"))


def fetch_readings(
    device_id: str,
    start: datetime,
    end: datetime,
    collection: str = "readings",
) -> List[Dict]:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    db_name = os.getenv("DB_NAME", "light_sensor_db")
    col = _client()[db_name][collection]
    col.create_index([("device_id", ASCENDING), ("ts", ASCENDING)])

    q = {"device_id": device_id, "ts": {"$gte": start, "$lt": end}}
    return list(col.find(q, {"_id": 0}).sort("ts", 1))


def mae(errors: List[float]) -> float:
    return sum(abs(e) for e in errors) / max(1, len(errors))


def rmse(errors: List[float]) -> float:
    return (sum(e * e for e in errors) / max(1, len(errors))) ** 0.5


def percent_within_band(obs: List[float], pred: List[float], tol: float) -> float:
    within = 0
    for o, p in zip(obs, pred):
        if abs(o - p) <= tol:
            within += 1
    return 100.0 * within / max(1, len(obs))


def peak_hour(pred_series: List[Dict]) -> Tuple[int, float]:
    """
    Returns (hour_of_peak, peak_pred_lux).
    """
    best = None
    for d in pred_series:
        p = float(d.get("lux_pred", 0.0))
        ts = d["ts"]
        if best is None or p > best[1]:
            best = (ts.hour, p)
    return best if best else (-1, 0.0)


def evaluate(readings: List[Dict], tol_lux: float = 25.0) -> Dict:
    if not readings:
        return {"ok": False, "reason": "no data"}

    pred = [float(d["lux_pred"]) for d in readings]
    obs = [float(d["lux_obs"]) for d in readings]
    errors = [o - p for o, p in zip(obs, pred)]

    flags = [d.get("flags", {}) for d in readings]
    neg = sum(1 for f in flags if f.get("is_negative"))
    high = sum(1 for f in flags if f.get("is_impossible_high"))
    stuck = sum(1 for f in flags if f.get("is_stuck"))

    pk_hour, pk_val = peak_hour(readings)

    # Simple “sanity” conditions (adjust for your building)
    peak_ok = 10 <= pk_hour <= 14  # midday window
    within = percent_within_band(obs, pred, tol=tol_lux)

    return {
        "ok": True,
        "count": len(readings),
        "mae": round(mae(errors), 3),
        "rmse": round(rmse(errors), 3),
        "within_tol_percent": round(within, 2),
        "tol_lux": tol_lux,
        "peak_hour_pred": pk_hour,
        "peak_pred_lux": round(pk_val, 2),
        "peak_hour_ok": peak_ok,
        "anomalies": {
            "negative": neg,
            "impossible_high": high,
            "stuck": stuck,
        },
    }


def main() -> None:
    device_id = os.getenv("DEVICE_ID", "ls-100-0001")

    # Evaluate last 24 hours (UTC)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(hours=24)

    readings = fetch_readings(device_id=device_id, start=start, end=end, collection="readings")
    report = evaluate(readings, tol_lux=25.0)

    print("Twin Evaluation Report")
    print("----------------------")
    for k, v in report.items():
        print(f"{k}: {v}")

    if report.get("ok") and report.get("peak_hour_ok") is False:
        print("\nNOTE: Peak hour looks unusual. If this were real sensor data, check:")
        print("- wrong timezone / wrong timestamps")
        print("- sensor moved indoors/outdoors")
        print("- room blinds/lighting schedule changed")


if __name__ == "__main__":
    main()