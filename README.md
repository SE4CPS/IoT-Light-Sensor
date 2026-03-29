# Indoor Light Notification System

[![API Status](https://img.shields.io/badge/API-Live-brightgreen)](https://iot-light-sensor-zumx.onrender.com/api/docs)
[![Swagger](https://img.shields.io/badge/Swagger-Docs-85EA2D?logo=swagger)](https://iot-light-sensor-zumx.onrender.com/api/docs)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-black?logo=flask)](https://flask.palletsprojects.com/)

This repository contains a small, end to end indoor monitoring system that tracks room light usage, visualizes the current state, and notifies users when lights are left on for too long.

---

## 🚀 Quick Links

- **[Live API Documentation](https://iot-light-sensor-zumx.onrender.com/api/docs)** - Interactive Swagger UI
- **[Production API](https://iot-light-sensor-zumx.onrender.com)** - Live endpoint
- **[GitHub Pages](https://se4cps.github.io/IoT-Light-Sensor/)** - Project website

---

## Project Goals

- Upstream indoor light sensor data to a backend service  
- Display the light status of a room on a dashboard  
- Notify the user if a light remains **ON for more than 12 hours**

---

## 📡 API Documentation

### Base URLs
- **Production**: `https://iot-light-sensor-zumx.onrender.com`
- **Swagger UI**: https://iot-light-sensor-zumx.onrender.com/api/docs

### Quick Test
```bash
curl https://iot-light-sensor-zumx.onrender.com/api/usage/statistics
```

---

## Core Data Model
```json
{
  "meta": {
    "entity": "room_light_event",
    "version": "1.0",
    "source": "indoor light sensor"
  },
  "data": {
    "room_id": "string | integer",
    "light_state": "ON | OFF",
    "timestamp": "ISO-8601"
  }
}
```

---

## 🏗️ Tech Stack

- **Backend**: Flask 3.1.3, Python 3.9+
- **Database**: MongoDB Atlas
- **Deployment**: Render.com
- **API Documentation**: Swagger/OpenAPI 3.0
- **CI/CD**: GitHub Actions

---

## 📝 License

This project is part of the SE4CPS coursework.
