# Indoor Light Notification System

This repository contains a small, end to end indoor monitoring system that tracks room light usage, visualizes the current state, and notifies users when lights are left on for too long.

The project is intentionally simple and layered, following long established system design principles that are easy to teach, reason about, and extend.

---

## Project Goals

- Upstream indoor light sensor data to a backend service  
- Display the light status of a room on a dashboard  
- Notify the user if a light remains **ON for more than 12 hours**

---

## System Overview


Each component has a clear responsibility and communicates through well defined interfaces.

---

## Architecture Layers

### Sensor
- Detects light ON / OFF state
- Attaches timestamps
- Sends events to the backend

### Backend
- Receives sensor events
- Validates data
- Applies notification rules
- Exposes data to the frontend

### Database
- Stores light events per room
- Supports historical queries

### Frontend
- Displays current light status
- Shows basic history per room

### Notification
- Evaluates light duration
- Triggers alerts when rules are violated

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
[IOT_Light_sensor_project_documentation.pdf](https://github.com/user-attachments/files/26328483/IOT_Light_sensor_project_documentation.pdf)


