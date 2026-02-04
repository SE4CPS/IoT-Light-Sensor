# twin_sim.py
import os
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from pymongo import MongoClient, ASCENDING


@dataclass(frozen=True)
class TwinConfig:
    room_id: str = "room-101"
    device_id: str = "ls-100-0001"
    model_version: str = "twin-v1"
    sampling_seconds: int = 60

    # Lux characteristics
    night_lux: float = 2.0
    peak_lux: float = 450.0
    sunrise_hour: float = 7.0
    sunset_hour: float = 18.0

    # Noise and drift
    noise_sigma: float = 8.0          # random noise
    drift_per_day: float = 2.0        # gradual drift of sensor observed lux
    anomaly_rate: float = 0.01        # fraction of points that may become anomalies

    # Simple alert rule (example)
    alert_lux_threshold: float = 10.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _fractional_hour(ts: datetime) -> float:
    return ts.hour + ts.minute / 60.0 + ts.second / 3600.0


def predicted_lux(ts: datetime, cloud_cover: float, cfg: TwinConfig) -> float:
    """
    Day curve using a smooth sine between sunrise and sunset.
    cloud_cover in [0,1] reduces daylight intensity.
    """
    h = _fractional_hour(ts)
    if h < cfg.sunrise_hour or h > cfg.sunset_hour:
        return cfg.night_lux

    # Map sunrise..sunset -> 0..pi
    span = cfg.sunset_hour - cfg.sunrise_hour
    x = (h - cfg.sunrise_hour) / span
    daylight_shape = math.sin(math.pi * x)  # 0 at sunrise/sunset, 1 at midday

    # Clouds attenuate (simple model)
    attenuation = 1.0 - 0.75 * _clamp(cloud_cover, 0.0, 1.0)
    lux = cfg.night_lux + (cfg.peak_lux - cfg.night_lux) * daylight_shape * attenuation
    return max(0.0, lux)


def observed_lux(pred_lux: float, day_index: int, cfg: TwinConfig) -> float:
    """
    Observed lux = predicted + drift + noise, with occasional anomalies.
    """
    drift = cfg.drift_per_day * day_index
    noise = random.gauss(0.0, cfg.noise_sigma)
    obs = pred_lux + drift + noise

    # Occasionally inject an anomaly
    if random.random() < cfg.anomaly_rate:
        choice = random.choice(["stuck_low", "stuck_high", "spike", "negative"])
        if choice == "stuck_low":
            obs = 0.0
        elif choice == "stuck_high":
            obs = cfg.peak_lux * 2.0
        elif choice == "spike":
            obs = pred_lux + cfg.peak_lux * 3.0
        elif choice == "negative":
            obs = -50.0

    return obs


def classify_reading(lux: float, cfg: TwinConfig) -> Dict[str, bool]:
    """
    Basic rule flags. Keep it simple and explicit.
    """
    is_negative = lux < 0.0
    is_impossible_high = lux > 20000.0  # depends on sensor, keep conservative
    is_dark_alert = lux >= 0.0 and lux < cfg.alert_lux_threshold
    return {
        "is_negative": is_negative,
        "is_impossible_high": is_impossible_high,
        "is_dark_alert": is_dark_alert,
    }


def generate_series(
    start_ts: datetime,
    minutes: int,
    cfg: TwinConfig,
    cloud_cover_fn=None,
) -> List[Dict]:
    """
    Generate readings for N minutes at cfg sampling interval.
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
        pred = predicted_lux(ts, cloud_cover, cfg)
        obs = observed_lux(pred, day_index, cfg)

        flags = classify_reading(obs, cfg)

        # simple stuck detection using delta
        is_stuck = False
        if prev_obs is not None:
            is_stuck = abs(obs - prev_obs) < 1e-6
        prev_obs = obs

        doc = {
            "room_id": cfg.room_id,
            "device_id": cfg.device_id,
            "model_version": cfg.model_version,
            "ts": ts,
            "cloud_cover": _clamp(cloud_cover, 0.0, 1.0),
            "lux_pred": float(pred),
            "lux_obs": float(obs),
            "flags": {**flags, "is_stuck": is_stuck},
        }
        out.append(doc)

    return out


def get_mongo_client() -> MongoClient:
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("Missing MONGO_URI environment variable")
    return MongoClient(uri)


def write_to_mongo(docs: Iterable[Dict], db_name: str, collection: str = "readings") -> int:
    client = get_mongo_client()
    db = client[db_name]
    col = db[collection]

    # helpful indexes
    col.create_index([("device_id", ASCENDING), ("ts", ASCENDING)])
    col.create_index([("room_id", ASCENDING), ("ts", ASCENDING)])

    docs_list = list(docs)
    if not docs_list:
        return 0

    res = col.insert_many(docs_list, ordered=True)
    return len(res.inserted_ids)


def main() -> None:
    # Example: write 1 day at 1 minute sampling
    db_name = os.environ.get("DB_NAME", "light_sensor_db")
    cfg = TwinConfig()

    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    docs = generate_series(start_ts=start, minutes=24 * 60, cfg=cfg)

    n = write_to_mongo(docs, db_name=db_name, collection="readings")
    print(f"Inserted {n} docs into {db_name}.readings")


if __name__ == "__main__":
    main()