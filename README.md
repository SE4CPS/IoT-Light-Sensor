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

## 📡 Embedded System (ESP32 Light Sensor)
## 📡 Embedded Hardware
***ESP32 Microcontroller w/ BH1750 Light Sensor***

This embedded system collects ambient light data using a sensor connected to an ESP32 and sends it to a backend server over Wi-Fi.

At a high level:

1. The ESP32 reads light intensity (lux) from the sensor
2. Adds a timestamp using NTP
3. Sends the data to the backend API
4. If offline, stores data locally and retries later

**Microcontroller — ESP32 (SparkFun Thing):** Built-in Wi-Fi + Bluetooth, 16 MB flash, 520 KB SRAM, Handles sensor reading + communication

**Sensor — BH1750 (Ambient Light Sensor):** Measures brightness in lux, 16-bit resolution via I²C

### Wiring (I²C)
| Sensor Pin | ESP32 Pin |
| ---------- | --------- |
| VCC        | 3.3V      |
| GND        | GND       |
| SDA        | GPIO16    |
| SCL        | GPIO17    |

  ⚠️ Note: I²C pins are configurable, but this project uses GPIO16 (SDA) and GPIO17 (SCL).

<img width="1840" height="1000" alt="Lux Sensor — BH1750" src="https://github.com/user-attachments/assets/d5ab7577-bea8-48c8-8f04-9003d413ee3c" />

| | | |
|:---:|:---:|:---:|
| ![BH1750 sensor](embedded-1.jpg) | ![Single node](embedded-2.jpg) | ![Dual node](embedded-3.jpg) |
| BH1750 module with I²C header pins and color-coded jumper wires. | ESP32 on breadboard wired to BH1750, ready for USB firmware upload. | Two-sensor deployment powered from a single USB wall adapter — used for weekend long-run tests. |

### 🛠️ Arduino IDE Setup
1. Install ESP32 Support
 (_Arduino IDE → Preferences_)
- Add to Additional Board Manager URLs:https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
2. Install Board Package
(_Tools → Board → Boards Manager_)
- Search: ESP32
- Install: ESP32 by Espressif Systems
3. Select Board
(_Tools → Board → ESP32 Arduino_)
- Choose: ESP32 Dev Module or SparkFun ESP32 Thing
4. Select Port
(_Tools → Port_)
- Mac: /dev/cu.usbserial-xxxx
- Windows: COM3, COM4, etc.
5. Serial Monitor
_(Tools → Serial Monitor)_
- Set baud rate: 115200

### Key Features
**1. Secure API Communication**
- Sends HTTPS requests to:
- ```/api/v1/sensors/data ```(sensor data)
- ``` /api/device/log ``` (error logging)

**2. Offline Storage (SPIFFS)**
- Stores failed readings in ```/data.txt```

**3. OTA Updates**
- Supports Over-the-Air firmware updates
- No physical access required after deployment
```
#include <ArduinoOTA.h>
ArduinoOTA.begin();
ArduinoOTA.handle();
```
***Sensor Type***

Of the 4 sensor types (Photodiode, Phototransistor, LDR, Digital Lux), we chose Digital Lux for the following benefits:
- High accuracy w/ calibrated, noise resistant digital measurements
- Fairly low power consumption
- Minimal circuit complexity out of all sensor types for easy integration, maintenance, and long-term operation
- Measures lux for analyzing light in a room

Click on the following link to learn more about the differences between sensor types: [Light Sensor Types & Characteristics](https://docs.google.com/document/d/1zIgJxN_gNXGTvkLemSUc5l2nPyyrzfW7cB-apdO-95M/edit?usp=sharing)

***WiFi Setup***

To set up the WiFi for the ESP32 microcontroller, the following was required:
- MAC Address
- SSID
- Password

```C++
#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(2000);

  uint8_t mac[6];
  WiFi.macAddress(mac);

  Serial.print("WiFi MAC: ");
  for (int i = 0; i < 6; i++) {
    if (mac[i] < 16) Serial.print("0");
    Serial.print(mac[i], HEX);
    if (i < 5) Serial.print(":");
  }
  Serial.println();

  int n = WiFi.scanNetworks();
  bool found = false;

  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == "PacDeviceReg") {
      found = true;
      Serial.println("PacDeviceReg FOUND");
      Serial.print("RSSI: ");
      Serial.println(WiFi.RSSI(i));
      Serial.print("Channel: ");
      Serial.println(WiFi.channel(i));
      Serial.print("Encryption type: ");
      Serial.println(WiFi.encryptionType(i));
    }
  }

  if (!found) {
    Serial.println("PacDeviceReg NOT FOUND");
  }
}

void loop() {}
```
The team had worked with the University of the Pacific's IT team to be given the permission and information needed to successfully.

***[WIP] Over-The-Air (OTA) Functionality***

The ESP32 supports over-the-air capabilities, allowing the embedded device to update wirelessly using an internet connection. This is not currently implemented, but we have the necessary tools researched and ready should the project be continued in the future:
- [Arduino IDE Software](https://www.arduino.cc/en/software/)
- OpenSSL Library
- .pem Certificate (File in repository)
- USB Drive to install initial code to ESP32

This webpage goes through setting up OTA step-by-step: [Setting Up ESP32 OTA](https://coolplaydev.com/esp32-ota-update)

---

### Example Payload
```
{
  "sensor_id": "esp32_02",
  "room": "living_room",
  "timestamp": "2026-04-22T17:30:00Z",
  "lux": 320
}
```
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
![QR Code](http_iot-light-sensoruop_onerender_com.png)
---

## 📝 License

This project is part of the SE4CPS coursework.
