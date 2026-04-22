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

## 📡 Embedded Hardware

ESP32 (SparkFun Thing) on a half-size breadboard connected via I²C to a BH1750 ambient light sensor (V322). Measures lux at 16-bit resolution over VCC, GND, SDA, SCL.

| | | |
|:---:|:---:|:---:|
| ![BH1750 sensor](embedded-1.jpg) | ![Single node](embedded-2.jpg) | ![Dual node](embedded-3.jpg) |
| BH1750 module with I²C header pins and color-coded jumper wires. | ESP32 on breadboard wired to BH1750, ready for USB firmware upload. | Two-sensor deployment powered from a single USB wall adapter — used for weekend long-run tests. |

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
## Database and Storage

### Collections:
- sensor_hourly : This collection fetch the snsor data and store it in below fields:
- _id : Uniue ids of record
- date : Date for data store
- hour : From how many hours sensor has capture the values from ast off
- sensor_id : We have two sensors: it shows name of each sesnors 
- luxLast : Lux values in float
- samples : Number of samples in above hours
- updatedAt : Database stored date time in utc

- Page_Logs :
- user_data :

### Triggers
- trg_INS_daily_usage : 
  
- User_Data_Trg_INS

---

## 📝 License

This project is part of the SE4CPS coursework.
