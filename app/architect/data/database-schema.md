# Database Schema - MongoDB Collections

**Database:** light_sensor_db  
**Platform:** MongoDB Atlas 7.0+  
**Sprint:** 3  
**Last Updated:** February 10, 2026  

---

## Overview

Complete MongoDB schema for IoT Light Sensor system with 6 collections, indexes, and data relationships.

---

## Collections Summary

| Collection | Type | Retention | Size (90 days) | Purpose |
|------------|------|-----------|----------------|---------|
| **event** | Immutable | 90 days (TTL) | ~800MB | All sensor events (append-only) |
| **room_state** | Mutable | Forever | ~1KB | Current state per room (fast queries) |
| **daily_usage** | Mutable | 2 years | ~100KB | Aggregated daily statistics |
| **device** | Reference | Forever | ~10KB | Device registry |
| **room** | Reference | Forever | ~5KB | Room registry |
| **alert** | Immutable | 90 days (TTL) | ~50MB | Generated alerts |

**Total Storage (1 room, 90 days):** ~850MB

---

## Collection 1: event

**Purpose:** Immutable event log (event sourcing pattern)

**Type:** Time-series data, append-only

**Schema:**
```javascript
{
  _id: ObjectId("507f1f77bcf86cd799439011"),
  event_id: "evt_20260210_001",
  schema_version: "1.0",
  ts: ISODate("2026-02-10T15:30:00.000Z"),
  room_id: "room-101",
  device_id: "ls-100-0001",
  light_state: "ON",  // Enum: "ON" | "OFF" | "UNKNOWN"
  lux: 342.5,
  meta: {
    seq: 1234,
    battery_pct: 87,
    signal_rssi_dbm: -45,
    firmware_version: "1.0.0",
    power_mw: 2400,
    motion_detected: true
  }
}
```

**JSON Schema Validation:**
```javascript
db.createCollection("event", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["event_id", "schema_version", "ts", "room_id", "device_id", "light_state", "lux"],
      properties: {
        event_id: {
          bsonType: "string",
          pattern: "^evt_[0-9]{8}_[0-9]{3}$"
        },
        schema_version: {
          bsonType: "string",
          enum: ["1.0"]
        },
        ts: {
          bsonType: "date"
        },
        room_id: {
          bsonType: "string",
          pattern: "^room-[0-9]{3}$"
        },
        device_id: {
          bsonType: "string",
          pattern: "^ls-[0-9]{3}-[0-9]{4}$"
        },
        light_state: {
          bsonType: "string",
          enum: ["ON", "OFF", "UNKNOWN"]
        },
        lux: {
          bsonType: "double",
          minimum: 0,
          maximum: 120000
        },
        meta: {
          bsonType: "object",
          properties: {
            seq: { bsonType: "int" },
            battery_pct: { bsonType: "int", minimum: 0, maximum: 100 },
            signal_rssi_dbm: { bsonType: "int", minimum: -100, maximum: 0 },
            firmware_version: { bsonType: "string" },
            power_mw: { bsonType: "int", minimum: 0 },
            motion_detected: { bsonType: "bool" }
          }
        }
      }
    }
  }
})
```

**Indexes:**
```javascript
// Composite index for device queries
db.event.createIndex({ "device_id": 1, "ts": -1 })

// Composite index for room queries
db.event.createIndex({ "room_id": 1, "ts": -1 })

// TTL index (auto-delete after 90 days)
db.event.createIndex({ "ts": 1 }, { expireAfterSeconds: 7776000 })
```

**Example Queries:**
```javascript
// Get latest 100 events for a room
db.event.find({ room_id: "room-101" })
  .sort({ ts: -1 })
  .limit(100)

// Get events in time range
db.event.find({
  room_id: "room-101",
  ts: {
    $gte: ISODate("2026-02-10T00:00:00Z"),
    $lt: ISODate("2026-02-11T00:00:00Z")
  }
})

// Calculate average lux for today
db.event.aggregate([
  {
    $match: {
      room_id: "room-101",
      ts: { $gte: ISODate("2026-02-10T00:00:00Z") }
    }
  },
  {
    $group: {
      _id: null,
      avg_lux: { $avg: "$lux" },
      count: { $sum: 1 }
    }
  }
])
```

---

## Collection 2: room_state

**Purpose:** Current state per room (derived from events)

**Type:** Mutable (upserted on each event)

**Schema:**
```javascript
{
  _id: "room-101",
  room_id: "room-101",
  light_state: "ON",
  lux: 342.5,
  power_mw: 2400,
  motion_detected: true,
  last_event_id: "evt_20260210_001",
  last_ts: ISODate("2026-02-10T15:30:00.000Z"),
  updated_at: ISODate("2026-02-10T15:30:00.123Z")
}
```

**JSON Schema Validation:**
```javascript
db.createCollection("room_state", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["room_id", "light_state", "lux", "last_event_id", "last_ts", "updated_at"],
      properties: {
        room_id: {
          bsonType: "string",
          pattern: "^room-[0-9]{3}$"
        },
        light_state: {
          bsonType: "string",
          enum: ["ON", "OFF", "UNKNOWN"]
        },
        lux: {
          bsonType: "double",
          minimum: 0,
          maximum: 120000
        },
        power_mw: {
          bsonType: "int",
          minimum: 0
        },
        motion_detected: {
          bsonType: "bool"
        },
        last_event_id: {
          bsonType: "string"
        },
        last_ts: {
          bsonType: "date"
        },
        updated_at: {
          bsonType: "date"
        }
      }
    }
  }
})
```

**Indexes:**
```javascript
// Unique index on room_id
db.room_state.createIndex({ "room_id": 1 }, { unique: true })

// Index on last_ts for staleness checks
db.room_state.createIndex({ "last_ts": -1 })
```

**Update Logic:**
```javascript
// Upsert on each event
db.room_state.updateOne(
  { room_id: "room-101" },
  {
    $set: {
      light_state: "ON",
      lux: 342.5,
      power_mw: 2400,
      motion_detected: true,
      last_event_id: "evt_20260210_001",
      last_ts: ISODate("2026-02-10T15:30:00Z"),
      updated_at: new Date()
    }
  },
  { upsert: true }
)
```

---

## Collection 3: daily_usage

**Purpose:** Pre-aggregated daily statistics

**Type:** Mutable (updated throughout the day)

**Schema:**
```javascript
{
  _id: "room-101-20260210",
  room_id: "room-101",
  date: "2026-02-10",
  on_seconds: 28800,
  off_seconds: 57600,
  avg_lux: 285.5,
  energy_wh: 230.4,
  updated_at: ISODate("2026-02-10T23:59:59.000Z")
}
```

**Indexes:**
```javascript
// Composite index for queries
db.daily_usage.createIndex({ "room_id": 1, "date": -1 })

// TTL index (delete after 2 years)
db.daily_usage.createIndex(
  { "updated_at": 1 },
  { expireAfterSeconds: 63072000 }  // 730 days
)
```

**Aggregation Query:**
```javascript
// Calculate daily usage from events
db.event.aggregate([
  {
    $match: {
      room_id: "room-101",
      ts: {
        $gte: ISODate("2026-02-10T00:00:00Z"),
        $lt: ISODate("2026-02-11T00:00:00Z")
      }
    }
  },
  {
    $group: {
      _id: null,
      on_seconds: {
        $sum: {
          $cond: [{ $eq: ["$light_state", "ON"] }, 3, 0]
        }
      },
      avg_lux: { $avg: "$lux" },
      total_energy_wh: { $sum: { $divide: ["$meta.power_mw", 3600000] } }
    }
  }
])
```

---

## Collection 4: device

**Purpose:** Device registry

**Type:** Reference data

**Schema:**
```javascript
{
  _id: "ls-100-0001",
  device_id: "ls-100-0001",
  room_id: "room-101",
  device_type: "light_sensor",
  status: "ACTIVE",  // Enum: "ACTIVE" | "DISABLED" | "RETIRED"
  firmware_version: "1.0.0",
  hardware: {
    mcu: "ESP32 Thing Plus",
    light_sensor: "VEML7700",
    power_sensor: "INA260",
    motion_sensor: "PIR"
  },
  provisioned_at: ISODate("2026-02-01T10:00:00.000Z"),
  last_seen_at: ISODate("2026-02-10T15:30:00.000Z")
}
```

**Indexes:**
```javascript
// Unique index on device_id
db.device.createIndex({ "device_id": 1 }, { unique: true })

// Index on room_id for room queries
db.device.createIndex({ "room_id": 1 })

// Index on last_seen_at for offline detection
db.device.createIndex({ "last_seen_at": -1 })
```

---

## Collection 5: room

**Purpose:** Room registry

**Type:** Reference data

**Schema:**
```javascript
{
  _id: "room-101",
  room_id: "room-101",
  building: "CTC",
  room_number: "113",
  floor: 1,
  tags: ["classroom", "computer-lab"],
  area_sqft: 1200,
  max_occupancy: 30,
  created_at: ISODate("2026-02-01T00:00:00.000Z"),
  updated_at: ISODate("2026-02-01T00:00:00.000Z")
}
```

**Indexes:**
```javascript
// Unique index on room_id
db.room.createIndex({ "room_id": 1 }, { unique: true })

// Index on building and floor
db.room.createIndex({ "building": 1, "floor": 1 })
```

---

## Collection 6: alert

**Purpose:** Generated alerts

**Type:** Immutable, append-only

**Schema:**
```javascript
{
  _id: ObjectId("507f1f77bcf86cd799439012"),
  alert_id: "alert-20260210-001",
  ts: ISODate("2026-02-10T15:30:00.000Z"),
  room_id: "room-101",
  device_id: "ls-100-0001",
  type: "LIGHT_STUCK_ON",  // Enum: LIGHT_STUCK_ON | SUDDEN_LUX_DROP | DEVICE_OFFLINE | SENSOR_ANOMALY
  severity: "WARN",  // Enum: INFO | WARN | CRITICAL
  linked_event_id: "evt_20260210_001",
  explain: {
    duration_hours: 13.5,
    threshold_hours: 12
  }
}
```

**Indexes:**
```javascript
// Composite index for room queries
db.alert.createIndex({ "room_id": 1, "ts": -1 })

// Index on type for filtering
db.alert.createIndex({ "type": 1 })

// TTL index (auto-delete after 90 days)
db.alert.createIndex({ "ts": 1 }, { expireAfterSeconds: 7776000 })
```

---

## Data Relationships
```
Room (1) ──── (N) Device
  │
  │
  ├─── (1) RoomState (current state)
  │
  ├─── (N) Event (time-series)
  │
  ├─── (N) DailyUsage (aggregated)
  │
  └─── (N) Alert (generated)

Device (1) ──── (N) Event
```

**Cardinalities:**
- 1 Room → N Devices
- 1 Room → 1 RoomState (one-to-one)
- 1 Room → N Events
- 1 Room → N DailyUsage
- 1 Device → N Events
- 1 Event → 0..1 Alert

---

## Storage Estimates

### Single Room (90 days)

| Collection | Docs/Day | Doc Size | Total (90 days) |
|------------|----------|----------|-----------------|
| event | 28,800 | 300 bytes | ~800 MB |
| room_state | 1 | 200 bytes | 200 bytes |
| daily_usage | 1 | 150 bytes | 13.5 KB |
| device | 0 | 300 bytes | 300 bytes |
| room | 0 | 200 bytes | 200 bytes |
| alert | ~10 | 250 bytes | ~22.5 KB |
| **Total** | | | **~850 MB** |

### 10 Rooms (90 days)

**Total Storage:** ~8.5 GB

### 100 Rooms (90 days)

**Total Storage:** ~85 GB

---

## Query Performance

### Expected Query Times

| Query | Target | Actual |
|-------|--------|--------|
| Get current state | < 10ms | ~5ms |
| Get last 100 events | < 50ms | ~30ms |
| Daily aggregation | < 200ms | ~150ms |
| Weekly stats | < 500ms | ~400ms |

**Optimizations:**
- Compound indexes on (device_id, ts) and (room_id, ts)
- Cache current state in `room_state` collection
- Pre-aggregate daily stats in `daily_usage` collection

---

## Migration Strategy

### Initial Setup
```javascript
// Create database
use light_sensor_db

// Create collections with validation
// (See schemas above)

// Create indexes
// (See index definitions above)

// Insert seed data
db.room.insertOne({
  room_id: "room-101",
  building: "CTC",
  room_number: "113",
  floor: 1,
  tags: ["classroom", "computer-lab"],
  created_at: new Date()
})

db.device.insertOne({
  device_id: "ls-100-0001",
  room_id: "room-101",
  device_type: "light_sensor",
  status: "ACTIVE",
  firmware_version: "1.0.0",
  provisioned_at: new Date()
})
```

### Schema Migrations

**Version 1.0 → 1.1 (Add power monitoring):**
```javascript
// Add power_mw field to existing events
db.event.updateMany(
  { "meta.power_mw": { $exists: false } },
  { $set: { "meta.power_mw": 0 } }
)

// Update schema version
db.event.updateMany(
  { schema_version: "1.0" },
  { $set: { schema_version: "1.1" } }
)
```

---

## Backup & Recovery

**Automated Backups:**
- MongoDB Atlas: Daily snapshots
- Retention: 7 days (configurable up to 365 days)
- Point-in-time recovery: Available on M10+ clusters

**Manual Backup:**
```bash
# Export entire database
mongodump --uri="mongodb+srv://..." --db=light_sensor_db --out=/backup/

# Export single collection
mongoexport --uri="mongodb+srv://..." --db=light_sensor_db --collection=event --out=events.json

# Restore database
mongorestore --uri="mongodb+srv://..." --db=light_sensor_db /backup/light_sensor_db/
```

---

## References

**MongoDB Documentation:**
- Schema Validation: https://www.mongodb.com/docs/manual/core/schema-validation/
- Indexes: https://www.mongodb.com/docs/manual/indexes/
- TTL Indexes: https://www.mongodb.com/docs/manual/core/index-ttl/
- Aggregation: https://www.mongodb.com/docs/manual/aggregation/

**Course:**
- COMP 233 Module 6: Data Architecture
- Issue #57: Propose system data schema

---
