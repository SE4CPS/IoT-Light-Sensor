# twin_sim.py
#
# Digital twin for a light sensor:
# - Loads MONGO_URI / DB_NAME from .env (local) or environment (CI)
# - Simulates predicted vs observed lux over time (day curve + clouds + noise + drift)
# - Writes documents to MongoDB Atlas
#
# Requirements:
#   pip install pymongo python-dotenv
#
# Local .env (DO NOT COMMIT):
#   MONGO_URI=...
#   DB_NAME=light_sensor_db

import os
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

# Load .env if present (local dev). In CI, env vars come from secrets.
load_dotenv()


@dataclass(frozen=True)
class TwinConfig:
    room_id: str = "room-101"
    device_id: str = "ls-100-0001"
    model_version: str = "twin-v1"
    sampling_seconds: int = 60  # one reading per minute

    # Lux curve characteristics
    night_lux: float = 2.0
    peak_lux: float = 450.0
    sunrise_hour: float = 7.0
    sunset_hour: float = 18.0

    # Noise and drift
    noise_sigma: float = 8.0          # gaussian noise on observed readings
    drift_per_day: float = 2.0        # observed sensor drifts upward per day
    anomaly_rate: float = 0.01        # chance to inject an anomaly per reading

    # Simple alert rule (example)
    alert_lux_threshold: float = 10.0

    # Sanity limits for flags
    impossible_high_lux: float = 20000.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _fractional_hour(ts: datetime) -> float:
    return ts.hour + ts.minute / 60.0 + ts.second / 3600.0


def predicted_lux(ts: datetime, cloud_cover: float, cfg: TwinConfig) -> float:
    """
    Predict lux using a smooth day curve:
      - night lux outside sunrise..sunset
      - sine curve between sunrise and sunset (peaks at midday)
      - cloud_cover in [0,1] attenuates intensity
    """
    h = _fractional_hour(ts)
    if h < cfg.sunrise_hour or h > cfg.sunset_hour:
        return cfg.night_lux

    span = cfg.sunset_hour - cfg.sunrise_hour
    x = (h - cfg.sunrise_hour) / span  # 0..1
    daylight_shape = math.sin(math.pi * x)  # 0 at sunrise/sunset, 1 at midday

    attenuation = 1.0 - 0.75 * _clamp(cloud_cover, 0.0, 1.0)
    lux = cfg.night_lux + (cfg.peak_lux - cfg.night_lux) * daylight_shape * attenuation
    return max(0.0, lux)


def observed_lux(pred_lux: float, day_index: int, cfg: TwinConfig) -> float:
    """
    Observed lux = predicted + drift + noise + occasional anomaly injection.
    """
    drift = cfg.drift_per_day * day_index
    noise = random.gauss(0.0, cfg.noise_sigma)
    obs = pred_lux + drift + noise

    if random.random() < cfg.anomaly_rate:
        kind = random.choice(["stuck_low", "stuck_high", "spike", "negative"])
        if kind == "stuck_low":
            obs = 0.0
        elif kind == "stuck_high":
            obs = cfg.peak_lux * 2.0
        elif kind == "spike":
            obs = pred_lux + cfg.peak_lux * 3.0
        elif kind == "negative":
            obs = -50.0

    return obs


def classify_reading(lux: float, cfg: TwinConfig) -> Dict[str, bool]:
    """
    Simple, explicit flags suitable for a teaching system.
    """
    is_negative = lux < 0.0
    is_impossible_high = lux > cfg.impossible_high_lux
    is_dark_alert = (lux >= 0.0) and (lux < cfg.alert_lux_threshold)
    return {
        "is_negative": is_negative,
        "is_impossible_high": is_impossible_high,
        "is_dark_alert": is_dark_alert,
    }


def generate_series(
    start_ts: datetime,
    minutes: int,
    cfg: TwinConfig,
    cloud_cover_fn: Optional[Callable[[datetime], float]] = None,
) -> List[Dict]:
    """
    Generate documents for MongoDB:
      - ts (datetime, UTC)
      - lux_pred, lux_obs
      - flags
      - cloud_cover
    """
    if start_ts.tzinfo is None:
        start_ts = start_ts.replace(tzinfo=timezone.utc)

    total_points = int((minutes * 60) / cfg.sampling_seconds)
    out: List[Dict] = []
    prev_obs: Optional[float] = None

    for i in range(total_points):
        ts = start_ts + timedelta(seconds=i * cfg.sampling_seconds)
        day_index = (ts.date() - start_ts.date()).days

        cloud_cover = float(cloud_cover_fn(ts)) if cloud_cover_fn else random.random()
        cloud_cover = _clamp(cloud_cover, 0.0, 1.0)

        pred = predicted_lux(ts, cloud_cover, cfg)
        obs = observed_lux(pred, day_index, cfg)

        flags = classify_reading(obs, cfg)

        # very simple stuck detector based on exact equality
        is_stuck = False
        if prev_obs is not None and abs(obs - prev_obs) < 1e-12:
            is_stuck = True
        prev_obs = obs

        doc = {
            "room_id": cfg.room_id,
            "device_id": cfg.device_id,
            "model_version": cfg.model_version,
            "ts": ts,
            "cloud_cover": cloud_cover,
            "lux_pred": float(pred),
            "lux_obs": float(obs),
            "flags": {**flags, "is_stuck": is_stuck},
        }
        out.append(doc)

    return out


def _get_required_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name} (check .env)")
    return val


def get_mongo_client() -> MongoClient:
    uri = _get_required_env("MONGO_URI")
    # Server selection is lazy; creating the client is cheap.
    return MongoClient(uri)


def write_to_mongo(docs: Iterable[Dict], collection: str = "readings") -> int:
    """
    Writes docs to MongoDB Atlas in DB_NAME (from .env/env).
    Returns number of inserted docs.
    """
    db_name = os.getenv("DB_NAME", "light_sensor_db")

    client = get_mongo_client()
    db = client[db_name]
    col = db[collection]

    # Helpful indexes for time-series querying
    col.create_index([("device_id", ASCENDING), ("ts", ASCENDING)])
    col.create_index([("room_id", ASCENDING), ("ts", ASCENDING)])

    docs_list = list(docs)
    if not docs_list:
        return 0

    res = col.insert_many(docs_list, ordered=True)
    return len(res.inserted_ids)


def main() -> None:
    """
    Default run: generate 24 hours of 1-minute readings and write to MongoDB.
    """
    cfg = TwinConfig()

    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    docs = generate_series(start_ts=start, minutes=24 * 60, cfg=cfg)

    n = write_to_mongo(docs, collection="readings")
    db_name = os.getenv("DB_NAME", "light_sensor_db")
    print(f"Inserted {n} docs into {db_name}.readings")


if __name__ == "__main__":
    main()