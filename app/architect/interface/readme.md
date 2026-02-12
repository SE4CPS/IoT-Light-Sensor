# Create all 4 interface contract files

# 1. Sensor-Backend
cat > app/architect/interfaces/sensor-backend.md << 'EOF'
# Sensor → Backend Interface Contract

**Endpoint:** POST /api/events  
**Protocol:** HTTPS  

See `api/endpoints.md` for complete documentation.

**Key Points:**
- Sensor sends lux readings every 3 seconds
- Event-driven (no polling)
- 202 Accepted response (async processing)
- Retry on 5xx errors (3 attempts, exponential backoff)
EOF

# 2. Backend-Database
cat > app/architect/interfaces/backend-database.md << 'EOF'
# Backend → Database Interface Contract

**Database:** MongoDB Atlas 7.0+  
**Driver:** PyMongo 4.6+  

See `data/database-schema.md` for complete schema.

**Key Operations:**
- Insert event: `db.event.insert_one()`
- Update state: `db.room_state.update_one(..., upsert=True)`
- Query history: `db.event.find().sort("ts", -1)`
EOF

# 3. Backend-Frontend
cat > app/architect/interfaces/backend-frontend.md << 'EOF'
# Backend → Frontend Interface Contract

**Protocol:** HTTPS  
**Format:** JSON  

See `api/endpoints.md` for complete API reference.

**Key Endpoints:**
- GET /api/sensor/current (cached 3s)
- GET /api/history (cached 30s)
- GET /api/stats (cached 5min)
EOF

# 4. Digital Twin
cat > app/architect/interfaces/digital-twin.md << 'EOF'
# Digital Twin Interface Contract

**Module:** twin_sim.py  
**Purpose:** Validate sensor readings  

**Methods:**
- `predict_lux(timestamp)`: Predict expected lux
- `detect_anomaly(observed, predicted)`: Check deviation
- Threshold: |error| > 100 lux

**Integration:** Event bus subscriber for `light.measurement`
EOF
