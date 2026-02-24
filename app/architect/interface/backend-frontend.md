# Backend → Frontend Interface Contract

**Components:** Flask Backend → Web Dashboard  
**Protocol:** HTTPS  
**Format:** JSON  

## Endpoints

### GET /api/sensor/current

**Query Parameters:**
- `room_id` (required): Room identifier

**Response:**
```json
{
  "room_id": "room-101",
  "lux": 342,
  "state": "ON",
  "timestamp": "2026-02-10T15:30:00Z",
  "freshness_seconds": 3
}
```

**Caching:** 3 seconds (reduce DB load)

### GET /api/history

**Query Parameters:**
- `room_id` (required)
- `limit` (optional, default=50, max=500)
- `start_time` (optional, ISO-8601)
- `end_time` (optional, ISO-8601)

**Response:**
```json
{
  "room_id": "room-101",
  "count": 50,
  "readings": [
    {"lux": 342, "state": "ON", "timestamp": "..."},
    {"lux": 338, "state": "ON", "timestamp": "..."}
  ]
}
```

**Caching:** 30 seconds

### GET /api/stats

**Query Parameters:**
- `room_id` (required)

**Response:**
```json
{
  "room_id": "room-101",
  "avg_lux": 285.5,
  "min_lux": 0,
  "max_lux": 920,
  "total_readings": 28800
}
```

**Caching:** 5 minutes

## CORS

**Allowed Origins:**
- https://gatraj.github.io
- https://iot-light-sensor.onrender.com
- http://localhost:5001 (dev)

**Allowed Methods:**
- GET, OPTIONS

**Allowed Headers:**
- Content-Type, Authorization

## Error Handling

**404 Not Found:**
```json
{
  "error": "Room not found",
  "room_id": "room-999"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error",
  "details": "Database connection failed"
}
```
