# IoT Light Sensor System - Architecture Documentation

## Table of Contents
- [System Overview](#system-overview)
- [Architecture Layers](#architecture-layers)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [API Documentation](#api-documentation)
- [Deployment Architecture](#deployment-architecture)
- [Security Architecture](#security-architecture)

---

## System Overview

The IoT Light Sensor System is a full-stack application that monitors indoor light levels across multiple rooms, provides real-time visualization, and sends notifications when lights remain on for extended periods (>12 hours). The system follows a layered architecture pattern based on the IoT Reference Architecture (ISO/IEC 30141).

### Key Features
- Real-time light intensity monitoring using BH1750/VEML7700 sensors
- Multi-room support (living, bedroom, kitchen, bathroom, office, garage)
- RESTful API backend with 21 endpoints
- Interactive dashboard with live data visualization
- Automated notifications for energy conservation
- Digital Twin simulation for testing and development
- Comprehensive security with input validation and authentication

### Technology Stack
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Hardware** | ESP32 + BH1750/VEML7700 | Light sensor with WiFi connectivity |
| **Backend** | Flask 3.1.3 + Python 3.11 | REST API server |
| **Database** | MongoDB Atlas | Sensor data storage |
| **Frontend** | HTML5 + JavaScript (Vanilla) | Dashboard UI |
| **Deployment** | Render.com | Cloud hosting platform |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
| **Documentation** | Swagger/OpenAPI 3.0 | API specification |

---

## Architecture Layers

### 1. Perception Layer (IoT Sensors)
**Components:**
- ESP32 microcontroller (WiFi-enabled)
- BH1750 light sensor (I2C interface, 1-65535 lux range)
- VEML7700 light sensor (alternative, 0-120,000 lux range)

**Responsibilities:**
- Read ambient light levels every 5 seconds
- Convert lux readings to ON/OFF state based on threshold (500 lux)
- Attach ISO 8601 timestamps to sensor events
- Transmit data to backend via HTTP POST

**Data Format:**
```json
{
  "device_id": "sensor_001",
  "room": "living",
  "lux": 752.5,
  "light_state": "ON",
  "timestamp": "2026-04-10T18:30:15Z"
}
```

**Power Optimization:**
- Deep sleep mode between readings (saves 95% power)
- WiFi connection pooling
- Battery-aware transmission frequency

---

### 2. Network Layer (Communication)
**Protocol:** HTTP/HTTPS (REST)
**Transport:** WiFi 802.11 b/g/n

**Endpoints:**
- `POST /api/v1/sensors/data` - Submit sensor readings
- `POST /api/device/log` - Device event logging
- `POST /api/v1/sensors/register` - Device registration

**Security:**
- JWT token authentication (implemented in Sprint 9)
- TLS/SSL encryption in production
- Rate limiting: 100 requests/minute per device
- Input validation using Marshmallow schemas

**Error Handling:**
- Retry logic: 3 attempts with exponential backoff
- Offline buffering: Store up to 100 readings locally
- Connection timeout: 10 seconds

---

### 3. Application Layer (Backend)
**Framework:** Flask 3.1.3
**Architecture Pattern:** Layered (MVC-style)

#### 3.1 API Endpoints (21 total)

**Category 1: Dashboard (2 endpoints)**
- `GET /` - Home page
- `GET /api/docs` - Swagger UI documentation

**Category 2: Sensors (5 endpoints)**
- `POST /api/v1/sensors/data` - Submit sensor data
- `GET /api/v1/sensors/data` - Retrieve sensor readings
- `GET /api/v1/sensors/latest` - Get latest reading per room
- `POST /api/v1/sensors/register` - Register new device
- `GET /api/v1/sensors/list` - List all registered sensors

**Category 3: Usage Statistics (4 endpoints)**
- `GET /api/usage/statistics` - Overall usage stats
- `GET /api/usage/history` - Historical usage data
- `GET /api/usage/daily` - Daily aggregated data
- `POST /api/usage/save` - Save usage record

**Category 4: Room Management (5 endpoints)**
- `GET /api/room/<room>/status` - Current room status
- `GET /api/room/<room>/history` - Room-specific history
- `POST /api/room/<room>/save` - Save room state
- `GET /api/rooms/all` - All rooms summary
- `GET /api/rooms/active` - Rooms with lights on

**Category 5: Admin & Logging (5 endpoints)**
- `POST /api/device/log` - Device logging (protected)
- `GET /api/admin/access` - Admin dashboard (protected)
- `POST /api/feedback` - User feedback
- `POST /api/alerts` - Alert notifications
- `GET /api/health` - Health check endpoint

#### 3.2 Business Logic Components

**Notification Engine:**
```python
def check_notification_threshold(room_id):
    # Query MongoDB for continuous light-on duration
    duration_hours = calculate_duration(room_id)
    
    if duration_hours >= 12:
        trigger_notification(
            room=room_id,
            message=f"Light has been on for {duration_hours} hours",
            priority="high"
        )
```

**Data Validation:**
- Input sanitization using Marshmallow schemas
- NoSQL injection prevention (parameterized queries)
- XSS protection (HTML escaping with bleach library)
- Length limits: device_id (50 chars), feedback (1000 chars)

**Error Responses:**
- 400 Bad Request - Invalid input
- 401 Unauthorized - Missing/invalid token
- 403 Forbidden - Insufficient permissions
- 404 Not Found - Resource doesn't exist
- 500 Internal Server Error - Server failure

---

### 4. Data Layer (Persistence)
**Database:** MongoDB Atlas (Cloud-hosted)
**Connection:** PyMongo 4.6.0

#### Collections Schema

**sensors_data:**
```javascript
{
  _id: ObjectId,
  device_id: String,
  room: String,  // enum: living, bedroom, kitchen, bathroom, office, garage
  lux: Number,
  light_state: String,  // enum: ON, OFF
  timestamp: ISODate,
  created_at: ISODate,
  metadata: {
    sensor_model: String,
    calibration_offset: Number
  }
}
```

**device_logs:**
```javascript
{
  _id: ObjectId,
  device_id: String,
  event: String,
  severity: String,  // enum: info, warning, error, critical
  timestamp: ISODate,
  authenticated_user: String,
  source_ip: String
}
```

**usage_statistics:**
```javascript
{
  _id: ObjectId,
  room: String,
  date: ISODate,
  light_on_duration_hours: Number,
  average_lux: Number,
  peak_lux: Number,
  readings_count: Number,
  energy_estimated_kwh: Number
}
```

#### Indexes
```javascript
// Performance optimization
db.sensors_data.createIndex({ "timestamp": -1 })
db.sensors_data.createIndex({ "room": 1, "timestamp": -1 })
db.sensors_data.createIndex({ "device_id": 1 })

// Aggregation pipeline support
db.usage_statistics.createIndex({ "room": 1, "date": -1 })
```

#### Data Retention
- Raw sensor data: 90 days rolling window
- Aggregated statistics: 2 years
- Device logs: 1 year
- Automatic cleanup via TTL indexes

---

### 5. Presentation Layer (Frontend)
**Stack:** HTML5 + Vanilla JavaScript + CSS3
**Design Pattern:** Responsive (mobile-first with Flexbox)

#### Dashboard Components

**1. Live Status Cards (per room):**
```html
<div class="room-card">
  <h3>Living Room</h3>
  <div class="lux-reading">752 lux</div>
  <div class="status on">Light ON</div>
  <div class="duration">On for 3 hours</div>
</div>
```

**2. Historical Charts:**
- Chart.js for time-series visualization
- 24-hour rolling window
- Auto-refresh every 30 seconds

**3. Notification Panel:**
- Real-time alerts via fetch API polling
- Dismissible notifications
- Priority color coding (green/yellow/red)

#### API Integration
```javascript
// Fetch latest sensor data
async function updateDashboard() {
  const response = await fetch('/api/v1/sensors/latest');
  const data = await response.json();
  
  // Update UI
  data.forEach(room => {
    updateRoomCard(room);
  });
}

// Poll every 30 seconds
setInterval(updateDashboard, 30000);
```

---

### 6. Digital Twin Layer
**Purpose:** Simulation and testing without physical hardware

**Components:**
- Simulated sensor data generator
- Time-accelerated testing (12 hours in 2 minutes)
- Anomaly injection for edge case testing
- Load testing (50+ virtual sensors)

**Implementation:**
```python
# twin/app.py
def generate_sensor_reading(room, hour_of_day):
    """Simulate realistic light patterns based on time"""
    if 6 <= hour_of_day <= 18:
        base_lux = random.uniform(400, 900)  # Daytime
    else:
        base_lux = random.uniform(0, 100)    # Nighttime
    
    return {
        "room": room,
        "lux": base_lux,
        "light_state": "ON" if base_lux > 500 else "OFF",
        "timestamp": datetime.utcnow().isoformat()
    }
```

---

## Data Flow

### 1. Normal Operation Flow
```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   ESP32      │   HTTP  │   Flask API  │  PyMongo│   MongoDB    │
│  + BH1750    ├────────>│  Validation  ├────────>│    Atlas     │
│   Sensor     │  POST   │  Business    │  Insert │  Collection  │
└──────────────┘  JSON   └──────┬───────┘         └──────────────┘
                                │
                                │ Notify if >12h
                                ▼
                         ┌──────────────┐
                         │ Notification │
                         │   Service    │
                         └──────────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │  Dashboard   │
                         │   (Browser)  │
                         └──────────────┘
```

### 2. Notification Trigger Flow
```
1. Sensor reading stored → MongoDB
2. Background job queries duration:
   SELECT room, MIN(timestamp) as first_on
   FROM sensors_data
   WHERE light_state = 'ON'
   GROUP BY room
3. Calculate: hours_on = NOW() - first_on
4. IF hours_on >= 12:
   - POST /api/alerts
   - Email/Push notification
   - Dashboard alert banner
```

### 3. Dashboard Refresh Flow
```
Browser ─> GET /api/v1/sensors/latest
           │
           ├──> Flask queries MongoDB
           │    (last reading per room)
           │
           └──> Return JSON:
                [{room: "living", lux: 750, state: "ON", duration: "3h"}]
           
Browser ─> Update UI cards
        └> Schedule next refresh (30s)
```

---

## Deployment Architecture

### Production Environment (Render.com)

```
┌─────────────────────────────────────────────────────┐
│                   Render.com Platform                │
│                                                       │
│  ┌──────────────────────────────────────────────┐  │
│  │  Web Service: iot-light-sensor.onrender.com  │  │
│  │                                                │  │
│  │  - Auto-deploy from GitHub (production branch)│  │
│  │  - Python 3.11 runtime                         │  │
│  │  - Gunicorn WSGI server (4 workers)            │  │
│  │  - Health checks every 5 minutes               │  │
│  │  - Auto-restart on failure                     │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
           │                             ▲
           │ TLS/SSL                     │
           ▼                             │
┌──────────────────────┐      ┌──────────────────────┐
│   MongoDB Atlas      │      │   GitHub Actions     │
│   (Cloud Database)   │      │   CI/CD Pipeline     │
│                      │      │                      │
│  - M0 Free Tier      │      │  1. Run tests        │
│  - Auto-backup daily │      │  2. Build            │
│  - IP Whitelist      │      │  3. Deploy           │
└──────────────────────┘      └──────────────────────┘
```

### Environment Variables
```bash
# Render.com Configuration
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/iot_sensors
JWT_SECRET_KEY=<random-256-bit-key>
FLASK_ENV=production
LOG_LEVEL=INFO
ALLOWED_ORIGINS=https://iot-light-sensor.onrender.com
RATE_LIMIT_ENABLED=true
```

### CI/CD Pipeline (.github/workflows/tests.yml)
```yaml
name: Test and Deploy
on:
  push:
    branches: [production]
  pull_request:
    branches: [production]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run security tests
        run: pytest dashboard/tests/test_input_validation.py
      - name: Run API tests
        run: pytest dashboard/tests/test_api.py
      
  deploy:
    needs: test
    if: github.ref == 'refs/heads/production'
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Render deploy
        run: curl ${{ secrets.RENDER_DEPLOY_HOOK }}
```

---

## Security Architecture

### 1. Authentication & Authorization
**JWT Token Flow:**
```
1. Device Registration:
   POST /api/v1/sensors/register
   {device_id, model, room}
   
   Response: {token: "eyJhbGc..."}

2. Authenticated Request:
   POST /api/device/log
   Headers: {Authorization: "Bearer eyJhbGc..."}
   
   Server validates:
   - Token signature
   - Expiration (24 hours)
   - Device permissions
```

**Role-Based Access Control (RBAC):**
- `device` role: Can POST sensor data, logs
- `admin` role: Can access /api/admin/*, view all data
- `user` role: Can view dashboard, submit feedback

### 2. Input Validation
**Marshmallow Schemas:**
```python
class SensorDataSchema(Schema):
    device_id = fields.Str(
        required=True,
        validate=[
            validate.Length(max=50),
            validate.Regexp(r'^[a-zA-Z0-9_-]+$')
        ]
    )
    room = fields.Str(
        required=True,
        validate=validate.OneOf([
            'living', 'bedroom', 'kitchen', 
            'bathroom', 'office', 'garage'
        ])
    )
    lux = fields.Float(
        required=True,
        validate=validate.Range(min=0, max=100000)
    )
```

### 3. Security Tests (18 total)
- NoSQL injection prevention (3 tests)
- XSS attack prevention (3 tests)
- Input length validation (3 tests)
- Character whitelisting (3 tests)
- Command injection prevention (2 tests)
- Path traversal prevention (2 tests)
- Error message security (2 tests)

### 4. Security Headers
```python
@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response
```

---

## Performance Metrics

| Metric | Target | Current | Notes |
|--------|--------|---------|-------|
| API Response Time | <500ms | 320ms | 95th percentile |
| Database Query Time | <200ms | 145ms | Aggregations |
| Dashboard Load Time | <2s | 1.8s | Initial render |
| Sensor Data Latency | <10s | 7s | End-to-end |
| Uptime | 99.5% | 99.7% | Last 30 days |
| Concurrent Users | 50 | - | Load tested |

---

## Scalability Roadmap

### Phase 1: Current (Single Instance)
- 1 Flask instance
- MongoDB Atlas M0 (512MB)
- Support: 10 sensors, 1000 req/hour

### Phase 2: Horizontal Scaling
- Multiple Flask instances (load balanced)
- MongoDB Atlas M10 (2GB)
- Redis caching layer
- Support: 50 sensors, 10,000 req/hour

### Phase 3: Microservices
- Separate services: Ingestion, Analytics, Notifications
- Kubernetes deployment
- Event-driven architecture (MQTT/Kafka)
- Support: 500+ sensors, 100,000+ req/hour

---

## Repository Structure
```
IoT-Light-Sensor/
├── app/
│   └── embedded/          # ESP32 firmware
│       ├── BH1750_sensor2/
│       └── VEML7700_sensor/
├── dashboard/
│   ├── app.py            # Flask API server
│   ├── schemas.py        # Input validation
│   ├── swagger/
│   │   └── swagger.yaml  # API specification
│   ├── templates/
│   │   └── dashboard.html
│   ├── tests/
│   │   ├── test_input_validation.py
│   │   └── SECURITY_TESTING.md
│   └── requirements.txt
├── twin/
│   └── app.py            # Digital twin simulator
├── documentation/
│   └── architecture/
├── .github/workflows/
│   └── tests.yml         # CI/CD pipeline
└── README.md
```

---

## API Documentation

**Interactive Documentation:**
- Swagger UI: https://iot-light-sensor.onrender.com/api/docs
- OpenAPI Spec: https://se4cps.github.io/IoT-Light-Sensor/

**Quick Start:**
```bash
# Submit sensor reading
curl -X POST https://iot-light-sensor.onrender.com/api/v1/sensors/data \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "device_id": "sensor_001",
    "room": "living",
    "lux": 752.5,
    "light_state": "ON",
    "timestamp": "2026-04-10T18:30:15Z"
  }'

# Get latest readings
curl https://iot-light-sensor.onrender.com/api/v1/sensors/latest
```

---

## Contributors
- **Shradha Pujari** - API Architect, Security Lead
- **SE4CPS Team** - Full-stack development

## License
MIT License - See LICENSE file for details

## Support
- GitHub Issues: https://github.com/SE4CPS/IoT-Light-Sensor/issues
- Slack: #all-iot-light-sensor
