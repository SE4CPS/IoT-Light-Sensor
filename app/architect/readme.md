# IoT Light Sensor - System Architecture

**Sprint:** 3  
**Status:** In Progress  
**Last Updated:** February 11, 2026

## Overview

Complete system architecture for IoT Light Sensor with event-driven design.

## Quick Links

- [UML Diagrams](diagrams/) - 9 professional diagrams in PlantUML format
- [Architecture Decisions](decisions/) - ADRs for major decisions
- [API Documentation](api/) - REST API endpoints
- [Data Schema](data/) - MongoDB collections and schemas
- [Technology Stack](system/) - All SW/HW versions

## Architecture Highlights

✅ **Event-Driven Architecture** - Professor's recommended for IoT  
✅ **9 UML Diagrams**  
✅ **6 Architectural Layers** - Device, Application, Data, Presentation, Testing, Infrastructure  
✅ **Battery Efficient** - 30 days vs 2 days (polling)  
✅ **Scalable** - MVP → 1000+ devices  

## Sprint 3 Deliverables

✅ 9 UML diagrams (PlantUML format)  
✅ Complete architecture documentation  
✅ All API endpoints documented (7 endpoints)  
✅ Technology stack with versions  
✅ Component specifications (6 layers)  
✅ Interface contracts (4 documents)  
✅ Architecture Decision Records (ADRs)  

## Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| **Device** | ESP32 Thing Plus | - |
| **Sensors** | VEML7700, INA260, PIR | - |
| **Backend** | Python + Flask | 3.11+ / 3.0+ |
| **Database** | MongoDB Atlas | 7.0+ |
| **Frontend** | HTML/CSS/JavaScript | ES6+ |
| **Infrastructure** | Render.com + GitHub Actions | - |

## Getting Started

### Viewing UML Diagrams

See [diagrams/README.md](diagrams/README.md) for instructions on viewing PlantUML diagrams.

**Quick view online:**
1. Go to https://www.plantuml.com/plantuml/uml/
2. Open any `.puml` file from `diagrams/`
3. Copy content and paste into editor

### Architecture Documents

- **System Overview:** [system/architecture-overview.md](system/)
- **Technology Stack:** [system/technology-stack.md](system/)
- **API Endpoints:** [api/endpoints.md](api/)
- **Database Schema:** [data/database-schema.md](data/)
- **Event-Driven ADR:** [decisions/001-event-driven-architecture.md](decisions/)


## Next Steps (Sprint 4)


