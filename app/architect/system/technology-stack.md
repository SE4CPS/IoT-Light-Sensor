# Technology Stack & Versions

**Project:** IoT Light Sensor  
**Sprint:** 3  
**Last Updated:** February 10, 2026  

---

## Overview

Complete technology stack for IoT Light Sensor system with exact versions, justifications, and scaling considerations.

---

## Hardware Components

### Edge Device (Room Node)

| Component | Model/Version | Purpose | Cost | Justification |
|-----------|--------------|---------|------|---------------|
| **Microcontroller** | ESP32-WROOM-32 (Thing Plus) | Main processor | $20 | WiFi built-in, dual-core 240MHz, deep sleep (10μA), 520KB RAM |
| **Light Sensor** | VEML7700 | Ambient light measurement | $5 | Direct lux output (0-120k), I²C interface, no calibration needed |
| **Power Sensor** | INA260 | Current/voltage monitoring | $6 | Measures actual power draw, I²C interface, ±15A range |
| **Motion Sensor** | Mini PIR | Occupancy detection | $3 | Passive detection, low power, digital output |
| **Light Control** | MOSFET IRL520 | Switch 12V lights | $2 | Logic-level gate (3.3V), 10A max, PWM dimmable |
| **Lights** | 12V DC Flood (4x) | Room illumination | $15 | 600mA each, 2.4A total, 28.8W |
| **Power Supply** | 12V DC Adapter | Device power | $8 | Safe prototyping (no AC mains) |

**Total Cost per Room:** ~$59

**Alternatives Considered:**
- **OPT3001** (TI) vs **VEML7700** (Vishay): Both excellent; VEML7700 chosen for team's Qwiic connector availability
- **Arduino** vs **ESP32**: ESP32 chosen for WiFi, dual-core, and better power management
- **Zigbee/LoRa** vs **WiFi**: WiFi chosen for existing infrastructure, easier debugging

---

## Software Stack

### Backend

| Component | Version | Purpose | Justification |
|-----------|---------|---------|---------------|
| **Python** | 3.11+ | Programming language | Async improvements, 10-60% faster than 3.10, type hints |
| **Flask** | 3.0+ | Web framework | Lightweight, flexible, easy learning curve, mature ecosystem |
| **Gunicorn** | 21.0+ | WSGI server | Production-grade, multi-worker, process management, auto-restart |
| **PyMongo** | 4.6+ | MongoDB driver | Official driver, connection pooling, async support (future) |
| **python-dotenv** | 1.0+ | Config management | Environment variables, 12-factor app pattern |
| **jsonschema** | 4.21+ | Data validation | JSON Schema standard, comprehensive validation |
| **pytest** | 8.0+ | Testing framework | Fixtures, parametrize, mocking, coverage integration |
| **pytest-cov** | 4.1+ | Test coverage | Coverage reports, fail-under threshold (80%) |
| **pylint** | 3.0+ | Code quality | Static analysis, PEP8 compliance, fail-under 8.0 |
| **Flask-CORS** | 4.0+ | CORS handling | Cross-origin requests for dashboard |
| **Flask-Limiter** | 3.5+ | Rate limiting | Prevent abuse, 1000 req/hour per device |

**requirements.txt:**
```
Flask==3.0.2
gunicorn==21.2.0
pymongo==4.6.1
python-dotenv==1.0.1
jsonschema==4.21.1
pytest==8.0.0
pytest-cov==4.1.0
pylint==3.0.3
Flask-CORS==4.0.0
Flask-Limiter==3.5.0
```

**Why Flask (vs Django, FastAPI)?**
- ✅ Simple, lightweight (no unnecessary features)
- ✅ Fast learning curve (team can contribute quickly)
- ✅ Flexible (no forced ORM or structure)
- ✅ Sufficient for MVP (1-100 devices)
- ❌ Django: Too heavy, opinionated, slower development
- ⚠️ FastAPI: Consider for Phase 2 (native async, auto docs)

---

### Database

| Component | Version | Purpose | Justification |
|-----------|---------|---------|---------------|
| **MongoDB** | 7.0+ | Primary database | Time-series optimized, flexible schema, horizontal scaling |
| **MongoDB Atlas** | Cloud | Managed hosting | Auto-backups, replica sets, monitoring, no ops overhead |

**Configuration:**
- **Cluster Tier:** M0 (Free) → M10 (Production)
- **Region:** AWS us-west-2 (Oregon)
- **Replica Set:** 3 nodes (Primary + 2 Secondary)
- **Storage:** 10GB → 100GB auto-scaling
- **Backups:** Daily snapshots, 7-day retention

**Why MongoDB (vs PostgreSQL, InfluxDB)?**
- ✅ Flexible schema (IoT data evolves)
- ✅ Time-series collections (optimized for sensor data)
- ✅ JSON native (no ORM needed)
- ✅ Horizontal scaling (sharding for 1000+ devices)
- ❌ PostgreSQL: Rigid schema, migrations needed
- ❌ InfluxDB: Over-engineered for MVP, less familiar

---

### Frontend

| Component | Version | Purpose | Justification |
|-----------|---------|---------|---------------|
| **HTML5** | - | Structure | Standard, semantic markup |
| **CSS3** | - | Styling | Flexbox, Grid, responsive design |
| **JavaScript** | ES6+ | Interactivity | Fetch API, async/await, modules |
| **Chart.js** | 4.4+ | Data visualization | Line charts, responsive, easy API |

**Hosting:**
- **GitHub Pages** (Free, CDN, HTTPS)

**Why Vanilla JS (vs React, Vue)?**
- ✅ No build step needed
- ✅ Fast development for simple dashboard
- ✅ Lightweight (< 10KB)
- ⚠️ React/Vue: Consider for Phase 2 if UI complexity grows

---

### Infrastructure

| Component | Version/Tier | Purpose | Cost | Justification |
|-----------|-------------|---------|------|---------------|
| **Render.com** | Free → Starter | App hosting | $0 → $7/mo | Auto-deploy, HTTPS, health checks, easy setup |
| **GitHub Actions** | Free | CI/CD | $0 | Integrated with repo, matrix builds, secrets management |
| **GitHub** | Free | Version control | $0 | Industry standard, collaboration, issue tracking |
| **UptimeRobot** | Free | Monitoring | $0 | 5-min health checks, Slack alerts, 99.9% uptime SLA |

**Why Render.com (vs Heroku, AWS, GCP)?**
- ✅ Git push = auto-deploy
- ✅ Free tier for MVP
- ✅ HTTPS automatic
- ✅ Simple configuration
- ❌ Heroku: More expensive ($7 → $25)
- ❌ AWS EC2: Manual setup, harder to learn
- ⚠️ AWS/GCP: Consider for Phase 3 (1000+ devices)

---

## Development Tools

| Tool | Version | Purpose |
|------|---------|---------|
| **VS Code** | 1.85+ | IDE |
| **PlantUML Extension** | 2.18+ | UML diagram rendering |
| **Python Extension** | 2024.0+ | Python IntelliSense, debugging |
| **Git** | 2.40+ | Version control |
| **Postman** | 10.0+ | API testing |
| **MongoDB Compass** | 1.42+ | Database GUI |

---

## Embedded Firmware (ESP32)

| Component | Version | Purpose | Justification |
|-----------|---------|---------|---------------|
| **Arduino IDE** | 2.2+ | Development environment | Beginner-friendly, library manager |
| **ESP32 Board Package** | 2.0.14+ | ESP32 support | Official Espressif package |
| **WiFi Library** | Built-in | Network connectivity | ESP32 native library |
| **Wire Library** | Built-in | I²C communication | Arduino standard library |
| **HTTPClient** | Built-in | HTTP requests | POST to Flask API |
| **ArduinoJson** | 6.21+ | JSON serialization | Efficient, low memory footprint |

**Alternative:** PlatformIO (more advanced, better dependency management)

---

## Scaling Plan

### Phase 0: MVP (1 device)

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| Render.com | Free tier (512MB RAM) | $0 |
| MongoDB Atlas | M0 Free (512MB storage) | $0 |
| GitHub Actions | 2000 min/month | $0 |
| **Total** | | **$0** |

**Capacity:** 1 device, 28,800 events/day, 1GB storage (90 days)

---

### Phase 1: Small Deployment (10 devices)

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| Render.com | Starter (512MB RAM, always-on) | $7 |
| MongoDB Atlas | M10 (10GB storage, replica set) | $57 |
| GitHub Actions | 2000 min/month | $0 |
| **Total** | | **$64** |

**Capacity:** 10 devices, 288,000 events/day, 10GB storage

---

### Phase 2: Medium Deployment (100 devices)

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| Render.com | Professional (2GB RAM, 1 CPU) | $25 |
| MongoDB Atlas | M20 (100GB storage) | $275 |
| Redis Cache | 256MB | $10 |
| GitHub Actions | 3000 min/month | $0 |
| **Total** | | **$310** |

**Capacity:** 100 devices, 2.88M events/day, 100GB storage

**Enhancements:**
- Redis caching (3s current state, 30s history)
- 8 Gunicorn workers
- Connection pooling (100 connections)

---

### Phase 3: Large Deployment (1000+ devices)

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| AWS EKS | 3x t3.medium nodes | $150 |
| MongoDB Atlas | M30 (1TB storage, sharded) | $920 |
| Redis Cache | 1GB | $30 |
| Kafka Event Bus | 3 brokers | $200 |
| Load Balancer | ALB | $20 |
| **Total** | | **$1,320** |

**Capacity:** 1000+ devices, 28.8M events/day, 1TB storage

**Architecture Changes:**
- Kubernetes cluster (10+ pods)
- Kafka event bus (replace in-memory)
- Horizontal auto-scaling
- Multi-region deployment
- CDN for dashboard (CloudFront)

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| **API Response Time** | < 200ms | ~150ms |
| **Database Query** | < 50ms | ~30ms |
| **Event Processing** | < 500ms | ~450ms |
| **Dashboard Load** | < 2s | ~1.5s |
| **Uptime** | > 99.5% | 99.9% |
| **Battery Life** | > 30 days | 30 days ✅ |

---

## Communication Protocols

| Protocol | Version | Use Case | Port |
|----------|---------|----------|------|
| **HTTPS** | 1.1/2.0 | ESP32 → Flask API | 443 |
| **MongoDB Wire** | 6.0 | Flask → MongoDB | 27017 (TLS) |
| **I²C** | - | ESP32 → Sensors | - |
| **PWM** | - | ESP32 → MOSFET | - |

---

## References

**Official Documentation:**
- Python: https://docs.python.org/3/
- Flask: https://flask.palletsprojects.com/
- MongoDB: https://www.mongodb.com/docs/
- ESP32: https://docs.espressif.com/
- PlantUML: https://plantuml.com/

**Course Materials:**
- COMP 233 Module 6: Architectural Design
- https://se4cps.github.io/lab/comp-233/

---

**Status:** Complete  
**Last Updated:** February 10, 2026  
**Maintainer:** Architecture Team
