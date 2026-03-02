# Embedded Sensor API Endpoints Documentation

**Version:** 1.0.0  
**Date:** February 25, 2026  
**Device:** ESP32 Thing Plus IoT Light Sensor  
**Protocol:** HTTPS/REST over WiFi 802.11 b/g/n  

---

## Table of Contents

1. [Overview](#overview)
2. [Base Configuration](#base-configuration)
3. [Sensor Hardware Endpoints](#sensor-hardware-endpoints)
4. [Backend API Endpoints](#backend-api-endpoints)
5. [Data Schemas](#data-schemas)
6. [Error Handling](#error-handling)
7. [Examples](#examples)

---

## Overview

This document defines the API endpoints for the ESP32 IoT Light Sensor system, which monitors room lighting using multiple sensors and communicates with a cloud backend.

**Hardware Components:**
- ESP32 Thing Plus microcontroller
- BH1750 light sensor (I²C 0x23)
- INA238 power monitor (I²C 0x45)
- PIR motion sensor (GPIO 13)
- MOSFET IRL520 light controller (PWM GPIO 14)

**Communication:**
- Protocol: HTTPS (TLS 1.3)
- Format: JSON
- Direction: ESP32 → Backend API
- Frequency: Configurable (3s - 60s intervals)

---

## Base Configuration

### Network Configuration

```yaml
Protocol: HTTPS
Port: 443
Transport: TCP
Encryption: TLS 1.3
Content-Type: application/json
User-Agent: ESP32-LightSensor/1.0.0
```

### API Base URL

```
Production:  https://iot-light-sensor.onrender.com
Staging:     https://iot-light-sensor-staging.onrender.com
Local Dev:   http://localhost:5000
```

### Device Configuration

```cpp
#define DEVICE_ID "ls-100-0001"           // Format: ls-XXX-XXXX
#define ROOM_ID "CTC-114"                 // Format: ABC-123
#define FIRMWARE_VERSION "1.0.0"          // Semver format
#define POSTING_INTERVAL_MS 3000          // 3 seconds
```

---

## Sensor Hardware Endpoints

### 1. BH1750 Light Sensor (I²C)

**Endpoint Type:** Hardware Interface  
**Protocol:** I²C  
**Address:** 0x23 (default) or 0x5C

#### Read Light Level

```cpp
Function: float readLuxLevel()
Returns: Light intensity in lux (1-65535)
Measurement Time: 120ms (High Resolution Mode)
Power: 120 μA active, <1 μA power-down
```

**Implementation:**
```cpp
#include <Wire.h>
#include <BH1750.h>

BH1750 lightMeter;

void setup() {
  Wire.begin(21, 22);  // SDA=21, SCL=22 for ESP32 Thing Plus
  lightMeter.begin(BH1750::ONE_TIME_HIGH_RES_MODE_2);
}

float readLuxLevel() {
  float lux = lightMeter.readLightLevel();
  
  // Validate range
  if (lux < 0) return -1;  // Error
  if (lux > 65535) lux = 65535;
  if (lux < 1) lux = 1;
  
  return lux;
}
```

**Returns:**
- **Success:** Float value (1.0 - 65535.0 lux)
- **Error:** -1.0 (sensor read failure)

**Response Time:** 120ms

---

### 2. INA238 Power Monitor (I²C)

**Endpoint Type:** Hardware Interface  
**Protocol:** I²C  
**Address:** 0x45 (default, configurable 0x40-0x4F)

#### Read Power Metrics

```cpp
Function: struct PowerData readPowerMetrics()
Returns: Voltage, current, power measurements
Measurement Time: ~5ms
Power: 300 μA active
```

**Data Structure:**
```cpp
struct PowerData {
  float voltage_v;    // Volts (0-85V range)
  float current_ma;   // Milliamps
  float power_mw;     // Milliwatts
};
```

**Implementation:**
```cpp
#include <Adafruit_INA238.h>

Adafruit_INA238 ina238;

void setup() {
  Wire.begin(21, 22);
  ina238.begin(0x45);
  ina238.setShuntResistor(0.01);  // 10mΩ shunt
}

PowerData readPowerMetrics() {
  PowerData data;
  
  data.voltage_v = ina238.readBusVoltage();      // V
  data.current_ma = ina238.readCurrent() * 1000; // mA
  data.power_mw = ina238.readPower() * 1000;     // mW
  
  // Validate
  if (data.voltage_v < 0 || data.voltage_v > 85) {
    data.voltage_v = 0;
  }
  
  return data;
}
```

**Returns:**
- **voltage_v:** 0.0 - 85.0 V
- **current_ma:** 0.0 - 20000.0 mA
- **power_mw:** 0.0 - 1700000.0 mW

**Response Time:** ~5ms

---

### 3. PIR Motion Sensor (GPIO)

**Endpoint Type:** Hardware Interface  
**Protocol:** Digital GPIO  
**Pin:** GPIO 13

#### Read Motion Status

```cpp
Function: bool readMotionSensor()
Returns: true if motion detected, false otherwise
Response Time: Immediate
Power: 60 μA standby
```

**Implementation:**
```cpp
#define PIR_PIN 13

void setup() {
  pinMode(PIR_PIN, INPUT);
}

bool readMotionSensor() {
  return (digitalRead(PIR_PIN) == HIGH);
}

// With debouncing (recommended)
bool readMotionWithDebounce() {
  static unsigned long lastChange = 0;
  static bool lastState = false;
  const unsigned long DEBOUNCE_MS = 200;
  
  bool current = (digitalRead(PIR_PIN) == HIGH);
  unsigned long now = millis();
  
  if (current != lastState && (now - lastChange) > DEBOUNCE_MS) {
    lastState = current;
    lastChange = now;
  }
  
  return lastState;
}
```

**Returns:**
- **true:** Motion detected
- **false:** No motion

**Response Time:** Immediate (debounced: 200ms)

---

### 4. MOSFET Light Controller (PWM)

**Endpoint Type:** Hardware Interface  
**Protocol:** PWM (Pulse Width Modulation)  
**Pin:** GPIO 14

#### Set Light Brightness

```cpp
Function: void setLightLevel(int percentage)
Parameters: percentage (0-100)
Response Time: Immediate
```

**Implementation:**
```cpp
#define MOSFET_PIN 14
#define PWM_CHANNEL 0
#define PWM_FREQUENCY 5000  // 5 kHz
#define PWM_RESOLUTION 8    // 8-bit (0-255)

void setup() {
  ledcSetup(PWM_CHANNEL, PWM_FREQUENCY, PWM_RESOLUTION);
  ledcAttachPin(MOSFET_PIN, PWM_CHANNEL);
  setLightLevel(0);  // Start OFF
}

void setLightLevel(int percentage) {
  // Clamp to valid range
  if (percentage < 0) percentage = 0;
  if (percentage > 100) percentage = 100;
  
  // Convert to PWM value (0-255)
  int pwmValue = map(percentage, 0, 100, 0, 255);
  ledcWrite(PWM_CHANNEL, pwmValue);
}

// Convenience functions
void turnLightOn() {
  setLightLevel(100);
}

void turnLightOff() {
  setLightLevel(0);
}

int getCurrentLightLevel() {
  int pwmValue = ledcRead(PWM_CHANNEL);
  return map(pwmValue, 0, 255, 0, 100);
}
```

**Parameters:**
- **percentage:** 0-100 (integer)

**Returns:** void

**Response Time:** Immediate

---

## Backend API Endpoints

### 1. POST /api/events

**Purpose:** Send sensor readings to backend  
**Direction:** ESP32 → Backend  
**Frequency:** Every 3-60 seconds (configurable)  
**Method:** POST  
**Authentication:** None (MVP)

#### Request

**URL:**
```
POST https://iot-light-sensor.onrender.com/api/events
```

**Headers:**
```http
Content-Type: application/json
User-Agent: ESP32-LightSensor/1.0.0
```

**Body:**
```json
{
  "room_id": "CTC-114",
  "device_id": "ls-100-0001",
  "light_state": "ON",
  "lux": 342.5,
  "timestamp": "2026-02-25T10:30:00Z",
  "meta": {
    "battery_pct": 87,
    "voltage_v": 11.8,
    "current_ma": 203.5,
    "power_mw": 2401.3,
    "motion_detected": true,
    "firmware_version": "1.0.0",
    "rssi_dbm": -65,
    "uptime_seconds": 86400,
    "light_control_pct": 100
  }
}
```

**Field Descriptions:**

| Field | Type | Required | Range/Format | Description |
|-------|------|----------|--------------|-------------|
| `room_id` | string | Yes | `^[A-Z]{3}-\d{3}$` | Room identifier |
| `device_id` | string | Yes | `^ls-\d{3}-\d{4}$` | Device identifier |
| `light_state` | string | Yes | `ON` or `OFF` | Light state (derived from lux ≥ 10) |
| `lux` | number | Yes | 1-65535 | Light level from BH1750 |
| `timestamp` | string | Yes | ISO-8601 UTC | Event timestamp |
| `meta.battery_pct` | integer | No | 0-100 | Battery percentage |
| `meta.voltage_v` | number | No | 0-85 | Bus voltage from INA238 |
| `meta.current_ma` | number | No | 0-20000 | Current in milliamps |
| `meta.power_mw` | number | No | 0-1700000 | Power in milliwatts |
| `meta.motion_detected` | boolean | No | true/false | PIR sensor state |
| `meta.firmware_version` | string | No | Semver | Firmware version |
| `meta.rssi_dbm` | integer | No | -100 to 0 | WiFi signal strength |
| `meta.uptime_seconds` | integer | No | ≥ 0 | Device uptime |
| `meta.light_control_pct` | integer | No | 0-100 | MOSFET PWM setting |

#### Response

**Success (202 Accepted):**
```json
{
  "status": "accepted",
  "event_id": "evt_20260225_103000_001",
  "processed_at": "2026-02-25T10:30:00.450Z"
}
```

**Error (400 Bad Request):**
```json
{
  "error": {
    "code": "MISSING_FIELD",
    "message": "Missing required field",
    "field": "room_id"
  }
}
```

**Error (422 Unprocessable Entity):**
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Data validation failed",
    "field": "lux",
    "value": 70000,
    "constraint": "maximum",
    "expected": 65535
  }
}
```

#### Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 202 | Accepted | Event queued for processing |
| 400 | Bad Request | Invalid JSON or missing fields |
| 422 | Unprocessable Entity | Data validation failed |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Database disconnected |

#### Implementation

```cpp
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

const char* API_BASE_URL = "https://iot-light-sensor.onrender.com";

bool postSensorEvent() {
  HTTPClient http;
  
  // Read all sensors
  float lux = readLuxLevel();
  String lightState = (lux >= 10) ? "ON" : "OFF";
  PowerData power = readPowerMetrics();
  bool motion = readMotionWithDebounce();
  int lightControl = getCurrentLightLevel();
  
  // Get NTP timestamp
  time_t now;
  time(&now);
  char timestamp[30];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));
  
  // Build JSON
  StaticJsonDocument<512> doc;
  doc["room_id"] = "CTC-114";
  doc["device_id"] = "ls-100-0001";
  doc["light_state"] = lightState;
  doc["lux"] = lux;
  doc["timestamp"] = timestamp;
  
  JsonObject meta = doc.createNestedObject("meta");
  meta["battery_pct"] = getBatteryPercentage();
  meta["voltage_v"] = power.voltage_v;
  meta["current_ma"] = power.current_ma;
  meta["power_mw"] = power.power_mw;
  meta["motion_detected"] = motion;
  meta["firmware_version"] = "1.0.0";
  meta["rssi_dbm"] = WiFi.RSSI();
  meta["uptime_seconds"] = millis() / 1000;
  meta["light_control_pct"] = lightControl;
  
  String payload;
  serializeJson(doc, payload);
  
  // HTTP POST
  http.begin(String(API_BASE_URL) + "/api/events");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "ESP32-LightSensor/1.0.0");
  http.setTimeout(10000);  // 10 seconds
  
  int httpCode = http.POST(payload);
  
  if (httpCode == 202) {
    Serial.println("✓ Event posted");
    http.end();
    return true;
  } else {
    Serial.printf("✗ POST failed: %d\n", httpCode);
    http.end();
    return false;
  }
}
```

**Retry Logic:**
```cpp
bool postEventWithRetry(int maxRetries = 3) {
  for (int attempt = 1; attempt <= maxRetries; attempt++) {
    if (postSensorEvent()) {
      return true;
    }
    
    if (attempt < maxRetries) {
      int delayMs = 1000 * attempt;  // Exponential backoff: 1s, 2s, 3s
      Serial.printf("Retry %d/%d in %dms\n", attempt, maxRetries, delayMs);
      delay(delayMs);
    }
  }
  
  return false;
}
```

**Response Time:** < 500ms (target)  
**Timeout:** 10 seconds  
**Retry:** 3 attempts with exponential backoff (1s, 2s, 3s)

---

### 2. POST /api/devices

**Purpose:** Register device on first boot  
**Direction:** ESP32 → Backend  
**Frequency:** Once (first boot only)  
**Method:** POST  
**Authentication:** None (MVP)

#### Request

**URL:**
```
POST https://iot-light-sensor.onrender.com/api/devices
```

**Headers:**
```http
Content-Type: application/json
User-Agent: ESP32-LightSensor/1.0.0
```

**Body:**
```json
{
  "device_id": "ls-100-0001",
  "room_id": "CTC-114",
  "device_type": "light_sensor",
  "firmware_version": "1.0.0",
  "hardware": {
    "mcu": "ESP32 Thing Plus",
    "sensors": ["BH1750", "INA238", "PIR"],
    "wifi_mac": "AA:BB:CC:DD:EE:FF",
    "light_control": "MOSFET IRL520"
  }
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | Yes | Unique device identifier |
| `room_id` | string | Yes | Assigned room |
| `device_type` | string | Yes | Device type (always "light_sensor") |
| `firmware_version` | string | Yes | Firmware version (semver) |
| `hardware.mcu` | string | Yes | Microcontroller model |
| `hardware.sensors` | array | Yes | List of sensor models |
| `hardware.wifi_mac` | string | Yes | WiFi MAC address |
| `hardware.light_control` | string | Yes | Light control method |

#### Response

**Success (201 Created):**
```json
{
  "status": "registered",
  "device_id": "ls-100-0001",
  "provisioned_at": "2026-02-25T10:00:00Z"
}
```

**Already Registered (409 Conflict):**
```json
{
  "error": {
    "code": "DEVICE_ALREADY_REGISTERED",
    "message": "Device already registered",
    "device_id": "ls-100-0001",
    "provisioned_at": "2026-01-15T08:00:00Z"
  }
}
```

#### Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 201 | Created | Device registered successfully |
| 409 | Conflict | Device already exists (treat as success) |
| 400 | Bad Request | Invalid data |
| 500 | Internal Server Error | Server error |

#### Implementation

```cpp
bool registerDevice() {
  HTTPClient http;
  
  String macAddress = WiFi.macAddress();
  
  StaticJsonDocument<512> doc;
  doc["device_id"] = "ls-100-0001";
  doc["room_id"] = "CTC-114";
  doc["device_type"] = "light_sensor";
  doc["firmware_version"] = "1.0.0";
  
  JsonObject hardware = doc.createNestedObject("hardware");
  hardware["mcu"] = "ESP32 Thing Plus";
  
  JsonArray sensors = hardware.createNestedArray("sensors");
  sensors.add("BH1750");
  sensors.add("INA238");
  sensors.add("PIR");
  
  hardware["wifi_mac"] = macAddress;
  hardware["light_control"] = "MOSFET IRL520";
  
  String payload;
  serializeJson(doc, payload);
  
  http.begin(String(API_BASE_URL) + "/api/devices");
  http.addHeader("Content-Type", "application/json");
  
  int httpCode = http.POST(payload);
  
  // Both 201 and 409 are success cases
  if (httpCode == 201 || httpCode == 409) {
    Serial.println("✓ Device registered");
    http.end();
    return true;
  }
  
  Serial.printf("✗ Registration failed: %d\n", httpCode);
  http.end();
  return false;
}

// Check first boot flag
bool isFirstBoot() {
  // Read from EEPROM or SPIFFS
  return true;  // Placeholder
}

void markAsRegistered() {
  // Write to EEPROM or SPIFFS
}

// Usage in setup()
void setup() {
  // ... other setup ...
  
  if (isFirstBoot()) {
    registerDevice();
    markAsRegistered();
  }
}
```

**Response Time:** < 500ms  
**Timeout:** 15 seconds

---

### 3. GET /api/devices/{device_id}/commands (Optional)

**Purpose:** Poll for remote control commands  
**Direction:** Backend → ESP32  
**Frequency:** Every 60 seconds (if implemented)  
**Method:** GET  
**Authentication:** None (MVP)

#### Request

**URL:**
```
GET https://iot-light-sensor.onrender.com/api/devices/ls-100-0001/commands
```

**Headers:**
```http
Accept: application/json
User-Agent: ESP32-LightSensor/1.0.0
```

#### Response

**Command Available (200 OK):**
```json
{
  "command": "set_brightness",
  "value": 75,
  "timestamp": "2026-02-25T10:30:00Z",
  "command_id": "cmd_12345"
}
```

**No Commands (200 OK):**
```json
{
  "command": null
}
```

**Command Types:**

| Command | Value | Action |
|---------|-------|--------|
| `set_brightness` | 0-100 | Set light to percentage |
| `turn_on` | null | Turn light fully on (100%) |
| `turn_off` | null | Turn light fully off (0%) |
| `toggle` | null | Toggle between on/off |

#### Implementation

```cpp
void checkForCommands() {
  HTTPClient http;
  
  String url = String(API_BASE_URL) + "/api/devices/ls-100-0001/commands";
  http.begin(url);
  http.addHeader("Accept", "application/json");
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String response = http.getString();
    StaticJsonDocument<256> doc;
    deserializeJson(doc, response);
    
    const char* command = doc["command"];
    
    if (command == nullptr) {
      // No commands
      http.end();
      return;
    }
    
    int value = doc["value"] | 0;
    
    if (strcmp(command, "set_brightness") == 0) {
      setLightLevel(value);
      Serial.printf("Command: Set brightness to %d%%\n", value);
    } 
    else if (strcmp(command, "turn_on") == 0) {
      turnLightOn();
      Serial.println("Command: Turn ON");
    } 
    else if (strcmp(command, "turn_off") == 0) {
      turnLightOff();
      Serial.println("Command: Turn OFF");
    } 
    else if (strcmp(command, "toggle") == 0) {
      int current = getCurrentLightLevel();
      setLightLevel(current > 0 ? 0 : 100);
      Serial.println("Command: Toggle");
    }
  }
  
  http.end();
}

// Call in loop (every 60 seconds)
void loop() {
  static unsigned long lastCommandCheck = 0;
  
  if (millis() - lastCommandCheck > 60000) {
    checkForCommands();
    lastCommandCheck = millis();
  }
}
```

---

## Data Schemas

### Sensor Event Schema (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["room_id", "device_id", "light_state", "lux", "timestamp"],
  "properties": {
    "room_id": {
      "type": "string",
      "pattern": "^[A-Z]{3}-\\d{3}$",
      "description": "Room identifier (e.g., CTC-114)"
    },
    "device_id": {
      "type": "string",
      "pattern": "^ls-\\d{3}-\\d{4}$",
      "description": "Device identifier (e.g., ls-100-0001)"
    },
    "light_state": {
      "type": "string",
      "enum": ["ON", "OFF"],
      "description": "Light state derived from lux"
    },
    "lux": {
      "type": "number",
      "minimum": 1,
      "maximum": 65535,
      "description": "Light level from BH1750"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp"
    },
    "meta": {
      "type": "object",
      "properties": {
        "battery_pct": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        },
        "voltage_v": {
          "type": "number",
          "minimum": 0,
          "maximum": 85
        },
        "current_ma": {
          "type": "number",
          "minimum": 0,
          "maximum": 20000
        },
        "power_mw": {
          "type": "number",
          "minimum": 0,
          "maximum": 1700000
        },
        "motion_detected": {
          "type": "boolean"
        },
        "firmware_version": {
          "type": "string",
          "pattern": "^\\d+\\.\\d+\\.\\d+$"
        },
        "rssi_dbm": {
          "type": "integer",
          "minimum": -100,
          "maximum": 0
        },
        "uptime_seconds": {
          "type": "integer",
          "minimum": 0
        },
        "light_control_pct": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        }
      }
    }
  }
}
```

### Device Registration Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["device_id", "room_id", "device_type", "firmware_version"],
  "properties": {
    "device_id": {
      "type": "string",
      "pattern": "^ls-\\d{3}-\\d{4}$"
    },
    "room_id": {
      "type": "string",
      "pattern": "^[A-Z]{3}-\\d{3}$"
    },
    "device_type": {
      "type": "string",
      "enum": ["light_sensor"]
    },
    "firmware_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "hardware": {
      "type": "object",
      "required": ["mcu", "sensors"],
      "properties": {
        "mcu": { "type": "string" },
        "sensors": {
          "type": "array",
          "items": { "type": "string" }
        },
        "wifi_mac": {
          "type": "string",
          "pattern": "^([0-9A-F]{2}:){5}[0-9A-F]{2}$"
        },
        "light_control": { "type": "string" }
      }
    }
  }
}
```

---

## Error Handling

### HTTP Error Codes

| Code | Name | Cause | ESP32 Action |
|------|------|-------|--------------|
| 400 | Bad Request | Invalid JSON/missing fields | Log error, retry with corrected data |
| 422 | Unprocessable Entity | Validation failed | Log error, check sensor readings |
| 429 | Too Many Requests | Rate limit exceeded | Increase posting interval |
| 500 | Internal Server Error | Server error | Retry with exponential backoff |
| 503 | Service Unavailable | Database down | Retry after 60 seconds |

### Retry Strategy

```cpp
// Exponential backoff
int delays[] = {1000, 2000, 4000};  // 1s, 2s, 4s

for (int i = 0; i < 3; i++) {
  if (postSensorEvent()) {
    return true;
  }
  delay(delays[i]);
}

return false;  // Failed after 3 attempts
```

### Network Error Handling

```cpp
if (WiFi.status() != WL_CONNECTED) {
  Serial.println("WiFi disconnected, reconnecting...");
  WiFi.reconnect();
  delay(5000);
}
```

### Sensor Error Handling

```cpp
float lux = readLuxLevel();
if (lux < 0) {
  Serial.println("BH1750 read error");
  // Use last known good value or skip this reading
  return;
}
```

---

## Examples

### Complete Main Loop

```cpp
#include <Wire.h>
#include <BH1750.h>
#include <Adafruit_INA238.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

// Sensors
BH1750 lightMeter;
Adafruit_INA238 ina238;

// Config
#define PIR_PIN 13
#define MOSFET_PIN 14
#define POSTING_INTERVAL_MS 3000

void setup() {
  Serial.begin(115200);
  
  // I²C sensors
  Wire.begin(21, 22);
  lightMeter.begin(BH1750::ONE_TIME_HIGH_RES_MODE_2);
  ina238.begin(0x45);
  ina238.setShuntResistor(0.01);
  
  // PIR
  pinMode(PIR_PIN, INPUT);
  
  // MOSFET/PWM
  ledcSetup(0, 5000, 8);
  ledcAttachPin(MOSFET_PIN, 0);
  
  // WiFi
  WiFi.begin("SSID", "PASSWORD");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  
  // NTP sync
  configTime(0, 0, "pool.ntp.org");
  
  // Register device (first boot)
  if (isFirstBoot()) {
    registerDevice();
    markAsRegistered();
  }
}

void loop() {
  // Read sensors
  float lux = readLuxLevel();
  PowerData power = readPowerMetrics();
  bool motion = readMotionWithDebounce();
  
  // Post to backend
  bool success = postEventWithRetry(3);
  
  if (!success) {
    Serial.println("Failed to post event");
  }
  
  // Delay before next reading
  delay(POSTING_INTERVAL_MS);
}
```

### Deep Sleep Mode (Battery Optimized)

```cpp
void loop() {
  // Read and post
  postEventWithRetry(3);
  
  // Enter deep sleep
  esp_sleep_enable_timer_wakeup(30000000);  // 30 seconds
  esp_deep_sleep_start();
  // Device restarts after wake
}
```

---

## Appendix

### Pin Assignments

| Component | Interface | Pin(s) |
|-----------|-----------|--------|
| BH1750 | I²C | SDA=21, SCL=22 |
| INA238 | I²C | SDA=21, SCL=22 |
| PIR | GPIO | GPIO 13 |
| MOSFET | PWM | GPIO 14 |

### I²C Addresses

| Device | Address | Alternative |
|--------|---------|-------------|
| BH1750 | 0x23 | 0x5C (ADDR high) |
| INA238 | 0x45 | 0x40-0x4F (configurable) |

### Required Libraries

```
BH1750 by Christopher Laws (v1.3.0+)
Adafruit_INA238 (v1.0.0+)
ArduinoJson (v6.21.0+)
WiFi (ESP32 core)
HTTPClient (ESP32 core)
```

---

**Document Version:** 1.0.0  
**Last Updated:** February 25, 2026  
**Author:** IoT Light Sensor Team
