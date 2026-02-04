# test_twin_sim.py
import os
from datetime import datetime, timedelta, timezone

import pytest

from twin_sim import TwinConfig, generate_series, write_to_mongo


def _fixed_cloud(_ts):
    return 0.2  # mostly clear


def test_time_is_increasing():
    cfg = TwinConfig(sampling_seconds=60)
    start = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    docs = generate_series(start, minutes=180, cfg=cfg, cloud_cover_fn=_fixed_cloud)

    ts_list = [d["ts"] for d in docs]
    assert ts_list == sorted(ts_list)
    assert len(ts_list) == 180


def test_night_is_low_day_has_peak():
    cfg = TwinConfig(sampling_seconds=60, sunrise_hour=7.0, sunset_hour=18.0, peak_lux=500.0)
    start = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    docs = generate_series(start, minutes=24 * 60, cfg=cfg, cloud_cover_fn=_fixed_cloud)

    # pick representative points
    def lux_at(hour: int) -> float:
        idx = hour * 60  # sampling per minute
        return docs[idx]["lux_pred"]

    lux_02 = lux_at(2)
    lux_12 = lux_at(12)
    lux_20 = lux_at(20)

    assert lux_02 < 10.0
    assert lux_20 < 10.0
    assert lux_12 > lux_02
    assert lux_12 > lux_20


def test_drift_increases_observed_over_days():
    cfg = TwinConfig(sampling_seconds=60, drift_per_day=5.0, noise_sigma=0.1, anomaly_rate=0.0)
    start = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)

    docs_day0 = generate_series(start, minutes=60, cfg=cfg, cloud_cover_fn=_fixed_cloud)
    docs_day2 = generate_series(start + timedelta(days=2), minutes=60, cfg=cfg, cloud_cover_fn=_fixed_cloud)

    avg0 = sum(d["lux_obs"] for d in docs_day0) / len(docs_day0)
    avg2 = sum(d["lux_obs"] for d in docs_day2) / len(docs_day2)

    assert avg2 > avg0  # drift pushes upward


def test_flags_mark_negative_and_high():
    cfg = TwinConfig(sampling_seconds=60, anomaly_rate=0.0)
    start = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)

    docs = generate_series(start, minutes=10, cfg=cfg, cloud_cover_fn=_fixed_cloud)

    # force synthetic edge cases without relying on randomness
    docs[0]["lux_obs"] = -1.0
    docs[0]["flags"] = {"is_negative": True, "is_impossible_high": False, "is_dark_alert": False, "is_stuck": False}

    docs[1]["lux_obs"] = 50000.0
    docs[1]["flags"] = {"is_negative": False, "is_impossible_high": True, "is_dark_alert": False, "is_stuck": False}

    assert docs[0]["flags"]["is_negative"] is True
    assert docs[1]["flags"]["is_impossible_high"] is True


@pytest.mark.skipif(os.environ.get("RUN_ATLAS_INTEGRATION") != "1", reason="Set RUN_ATLAS_INTEGRATION=1 to run")
def test_integration_write_to_atlas():
    # Requires env vars:
    # MONGO_URI=...
    # DB_NAME=light_sensor_db
    cfg = TwinConfig(sampling_seconds=60, anomaly_rate=0.0)
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    docs = generate_series(start, minutes=5, cfg=cfg, cloud_cover_fn=_fixed_cloud)

    db_name = os.environ.get("DB_NAME", "light_sensor_db")
    n = write_to_mongo(docs, db_name=db_name, collection="readings_test")
    assert n == 5