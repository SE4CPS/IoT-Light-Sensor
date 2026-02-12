cat > app/architect/api/endpoints.md << 'EOF'
# API Endpoints Documentation

**Version:** 1.0  
**Base URL:** `https://iot-light-sensor.onrender.com`  
**Protocol:** HTTPS (TLS 1.3)  
**Format:** JSON  
**Sprint:** 3  

---

## Overview

RESTful API for IoT Light Sensor system with 7 endpoints for sensor data ingestion, querying, and usage statistics.

---

## Table of Contents

1. [Sensor Endpoints](#sensor-endpoints)
2. [Dashboard Endpoints](#dashboard-endpoints)
3. [Usage Endpoints](#usage-endpoints)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Authentication](#authentication)

---

## Sensor Endpoints

### POST /api/events

**Purpose:** Accept sensor events from ESP32 devices

**Authentication:** None (API key in future)

**Request Headers:**
```http
Content-Type: application/json
```

**Request Body:**
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
    "firmware_version": "1.0.0",
    "power_mw": 2400,
    "motion_detected": true
  }
}
```

**Success Response (202 Accepted):**
```json
{
  "status": "accepted",
  "event_id": "evt_20260210_001",
  "processed_at": "2026-02-10T15:30:00.123Z"
}
```

**Error Responses:**

**400 Bad Request** - Invalid schema or out-of-range values
```json
{
  "error": "Validation failed: lux must be between 0 and 120000",
  "details": "Received lux: 150000",
  "timestamp": "2026-02-10T15:30:00Z"
}
```

**401 Unauthorized** - Invalid device_id (future)
```json
{
  "error": "Unauthorized device",
  "details": "Device 'ls-100-9999' not registered",
  "timestamp": "2026-02-10T15:30:00Z"
}
```

**500 Internal Server Error** - Processing failure
```json
{
  "error": "Internal server error",
  "details": "Database connection failed",
  "timestamp": "2026-02-10T15:30:00Z"
}
```

**Validation Rules:**
- `lux`: 0 ≤ lux ≤ 120,000
- `state`: Must be "ON" or "OFF"
- `timestamp`: ISO-8601 UTC format
- `timestamp`: Within ±5 minutes of server time
- `device_id`: Pattern `ls-[0-9]{3}-[0-9]{4}`
- `room_id`: Pattern `room-[0-9]{3}`

**Rate Limit:** 1000 requests/hour per device

---

## Dashboard Endpoints

### GET /api/sensor/current

**Purpose:** Get current sensor reading for a room

**Query Parameters:**
- `room_id` (required): Room identifier (e.g., "room-101")

**Example Request:**
```http
GET /api/sensor/current?room_id=room-101 HTTP/1.1
Host: iot-light-sensor.onrender.com
```

**Success Response (200 OK):**
```json
{
  "room_id": "room-101",
  "lux": 342,
  "state": "ON",
  "timestamp": "2026-02-10T15:30:00Z",
  "freshness_seconds": 3,
  "battery_pct": 87,
  "power_mw": 2400,
  "motion_detected": true
}
```

**Error Response (404 Not Found):**
```json
{
  "error": "Room not found or no data available",
  "room_id": "room-999",
  "timestamp": "2026-02-10T15:30:00Z"
}
```

**Caching:** 3 seconds

---

### GET /api/history

**Purpose:** Get historical sensor readings

**Query Parameters:**
- `room_id` (required): Room identifier
- `limit` (optional, default=50, max=500): Number of readings
- `start_time` (optional): ISO-8601 start timestamp
- `end_time` (optional): ISO-8601 end timestamp

**Example Request:**
```http
GET /api/history?room_id=room-101&limit=50 HTTP/1.1
```

**Success Response (200 OK):**
```json
{
  "room_id": "room-101",
  "count": 50,
  "readings": [
    {
      "lux": 342,
      "state": "ON",
      "timestamp": "2026-02-10T15:30:00Z",
      "power_mw": 2400
    },
    {
      "lux": 338,
      "state": "ON",
      "timestamp": "2026-02-10T15:29:57Z",
      "power_mw": 2400
    }
  ],
  "has_more": true
}
```

**Caching:** 30 seconds

---

### GET /api/stats

**Purpose:** Get aggregated statistics for a room

**Query Parameters:**
- `room_id` (required): Room identifier

**Example Request:**
```http
GET /api/stats?room_id=room-101 HTTP/1.1
```

**Success Response (200 OK):**
```json
{
  "room_id": "room-101",
  "avg_lux": 285.5,
  "min_lux": 0,
  "max_lux": 920,
  "total_readings": 28800,
  "avg_power_mw": 2350,
  "energy_wh": 230.4,
  "time_range": {
    "start": "2026-02-09T00:00:00Z",
    "end": "2026-02-10T15:30:00Z"
  }
}
```

**Caching:** 5 minutes

---

## Usage Endpoints

### GET /api/usage/{date}

**Purpose:** Get daily usage statistics for a specific date

**Path Parameters:**
- `date` (required): Date in YYYY-MM-DD format

**Query Parameters:**
- `room_id` (required): Room identifier

**Example Request:**
```http
GET /api/usage/2026-02-10?room_id=room-101 HTTP/1.1
```

**Success Response (200 OK):**
```json
{
  "date": "2026-02-10",
  "room_id": "room-101",
  "on_seconds": 28800,
  "off_seconds": 57600,
  "on_hours": 8.0,
  "usage_percentage": 33.33,
  "energy_wh": 230.4,
  "cost_usd": 0.035
}
```

---

### POST /api/usage/save

**Purpose:** Save or update daily usage statistics

**Request Body:**
```json
{
  "date": "2026-02-10",
  "room_id": "room-101",
  "on_seconds": 28800,
  "off_seconds": 57600
}
```

**Success Response (201 Created):**
```json
{
  "status": "saved",
  "date": "2026-02-10",
  "room_id": "room-101"
}
```

---

### GET /api/usage/statistics

**Purpose:** Get usage statistics across time periods

**Query Parameters:**
- `room_id` (required): Room identifier
- `period` (optional, default="daily"): "daily" | "weekly" | "monthly"

**Example Request:**
```http
GET /api/usage/statistics?room_id=room-101&period=weekly HTTP/1.1
```

**Success Response (200 OK):**
```json
{
  "room_id": "room-101",
  "period": "weekly",
  "statistics": {
    "total_on_hours": 56,
    "total_off_hours": 112,
    "avg_on_hours_per_day": 8.0,
    "usage_percentage": 33.33,
    "total_energy_kwh": 1.6,
    "estimated_cost_usd": 0.24
  }
}
```

---

## Error Handling

### Standard Error Response Format

All error responses follow this structure:
```json
{
  "error": "Error message here",
  "details": "Additional details if available",
  "timestamp": "2026-02-10T15:30:00Z",
  "request_id": "req_abc123"
}
```

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful GET request |
| 201 | Created | Successful POST (resource created) |
| 202 | Accepted | Event accepted for processing |
| 400 | Bad Request | Invalid schema, out of range, malformed JSON |
| 401 | Unauthorized | Invalid API key or device_id |
| 404 | Not Found | Room not found, no data available |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Database failure, unexpected error |

---

## Rate Limiting

### Limits

| Endpoint | Rate Limit | Per |
|----------|-----------|-----|
| POST /api/events | 1000 requests | hour per device |
| GET /api/* | 10000 requests | hour per IP |

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1707580800
```

### Rate Limit Exceeded Response (429)
```json
{
  "error": "Rate limit exceeded",
  "details": "Limit: 1000 requests/hour. Try again in 3600 seconds.",
  "retry_after": 3600,
  "timestamp": "2026-02-10T15:30:00Z"
}
```

---

## Authentication

### Current (MVP)

- **POST /api/events:** No authentication (open endpoint)
- **GET /api/*:** No authentication (public data)

### Future (Production)

**API Key per Device:**
```http
POST /api/events HTTP/1.1
Authorization: Bearer sk_live_abc123xyz
Content-Type: application/json
```

**JWT for Dashboard Users:**
```http
GET /api/sensor/current?room_id=room-101 HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## CORS Policy

**Allowed Origins:**
- `https://gatraj.github.io` (demo dashboard)
- `https://iot-light-sensor.onrender.com` (production)
- `http://localhost:5001` (development)

**Allowed Methods:**
- GET, POST, OPTIONS

**Allowed Headers:**
- Content-Type, Authorization

---

## Versioning

**Current Version:** v1  
**Version Header:** `API-Version: 1.0`

Future versions will use URL prefix: `/api/v2/`

---

## Health Check

### GET /health

**Purpose:** Check API and database health

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-10T15:30:00Z",
  "database": "connected",
  "recent_events": 145,
  "uptime_seconds": 86400
}
```

**Response (500 Unhealthy):**
```json
{
  "status": "unhealthy",
  "timestamp": "2026-02-10T15:30:00Z",
  "database": "disconnected",
  "error": "Connection timeout"
}
```

---

## Examples

### Complete Sensor Event Flow

**1. ESP32 sends reading:**
```bash
curl -X POST https://iot-light-sensor.onrender.com/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "light.measurement",
    "device_id": "ls-100-0001",
    "room_id": "room-101",
    "lux": 342.5,
    "state": "ON",
    "timestamp": "2026-02-10T15:30:00Z"
  }'
```

**2. Dashboard polls current state:**
```bash
curl https://iot-light-sensor.onrender.com/api/sensor/current?room_id=room-101
```

**3. Get historical data:**
```bash
curl "https://iot-light-sensor.onrender.com/api/history?room_id=room-101&limit=100"
```

---

**Status:** Complete  
**Sprint:** 3  
**Last Updated:** February 10, 2026  
**Maintainer:** Backend Team
EOF
