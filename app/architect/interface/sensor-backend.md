# Sensor → Backend Interface Contract

**Components:** ESP32 Device → Flask Backend  
**Protocol:** HTTPS  
**Endpoint:** POST /api/events  

## Request Format
```json
{
  "event_type": "light.measurement",
  "device_id": "ls-100-0001",
  "room_id": "room-101",
  "lux": 342.5,
  "state": "ON",
  "timestamp": "2026-02-10T15:30:00Z",
  "meta": {
    "battery_pct": 87,
    "signal_rssi_dbm": -45,
    "firmware_version": "1.0.0"
  }
}
```

## Response Format

**Success (202 Accepted):**
```json
{
  "status": "accepted",
  "event_id": "evt_20260210_001",
  "processed_at": "2026-02-10T15:30:00.123Z"
}
```

**Error (400 Bad Request):**
```json
{
  "error": "Validation failed",
  "details": "lux out of range"
}
```

## Validation Rules

- `lux`: 0 ≤ lux ≤ 120,000
- `state`: "ON" or "OFF"
- `timestamp`: ISO-8601 UTC, ±5 minutes of server time
- `device_id`: Pattern `ls-[0-9]{3}-[0-9]{4}`

## Retry Policy

- Retry on: 500, 502, 503, 504
- Max attempts: 3
- Backoff: Exponential (1s, 2s, 4s)
- Timeout: 10 seconds per request

## Security

- HTTPS required (TLS 1.3)
- Future: API key in Authorization header
