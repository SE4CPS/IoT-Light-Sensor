## Introduction

IoT-Light-Sensor Project

COMP-233 Software Engineering 4.0

Instructor : Dr. Solomon Berhe

University of the Pacific

## Abstract
IoT is the technology that opens up physical objects to gather and share information via
sensors and network connections to monitor and make smart decisions in real-time. IoT systems are
commonly made up of sensors, communication networks, data processing platforms and application
interfaces to enable meaningful insights based on environmental data.This project will show the
design and deployment of an IoT-driven Light Sensor Monitoring System to measure ambient
light intensity and show the obtained data in a web-based dashboard. The system combines
both hardware sensors, backend services and databases with a frontend visualization to form a
completely end-to-end application.The system architecture is divided into four significant components Sensor Layer, Backend
Server, Database, and Frontend Interface. The sensor records the intensity of the ambient light and
transmits it to the backend server over the network. Data is processed and stored on the backend
into a database and then accessed via APIs by the frontend dashboard which then displays the
stored data to users.This project is created across several teams, such as the Embedded Systems,
Backend Development, Frontend Development and DevOps, and replicated a real-world software
development process. The DevOps element provides the seamless deployment and integration of
the system through version control and cloud service.
The last system shows how a combination of IoT devices, full-stack web technologies, and cloud
deployment can be used to create a scalable real-time monitoring platform. This solution can be
scaled up to be used in applications like smart lighting, energy management, and smart building
automation systems.

## 1 Introduction
## 1.1 Background
Internet of Things (IoT) is changing how physical objects can be connected to the work of digital
objects, since it allows us to place sensors and smart objects in the physical world and relay the
information gathered by them via the internet-based platform. The sensors are indispensable elements of the IoT systems since they identify any alterations in the environment and translate them into
digital signals which can be manipulated and analyzed using software programs.
IoT architectures are usually formed of various layers such as sensing devices, data networks, data
processing platforms, and user applications which give knowledge of the received information.
Sensors used to monitor the environment are common in the contemporary smart systems like smart
houses, industrial control, agricultural monitoring and smart energy management systems. Light
intensity is one of the key aspects of energy efficiency and automation among other environmental
parameters.Conventional lighting systems are independent and do not take into account the real-time environmental conditions and that may lead to wasteful energy consumption and non-automation. As such,
intelligent systems that can be used to track the conditions of light in the environment and enable
real-time feedback are required.
## 1.2 Purpose of the Project
The purpose of this project is to design and implement an IoT Light Sensor Monitoring System that
captures ambient light intensity and visualizes the collected data through an interactive dashboard.
The system demonstrates how sensor-based data collection can be integrated with modern web technologies to build a real-time monitoring platform.
The project combines multiple technologies including sensor hardware, backend services, database
management, and frontend visualization to create a complete full-stack IoT application.
## 1.3 Problem Statement
Many existing lighting systems operate independently without considering environmental light conditions. As a result, lighting systems may remain active even when natural light is sufficient, leading
to energy waste and increased operational costs. Additionally, traditional monitoring systems lack
real-time visibility and centralized data management.

Therefore, there is a need for a system that can:

1. Continuously monitor ambient light intensity
2. Provide real-time data visualization
3. Enable efficient monitoring through a centralized dashboard
4. Support future automation for energy-efficient lighting control
The IoT Light Sensor System addresses these challenges by collecting real-time sensor data and presenting it in an accessible and interactive manner.

## 1.4 Project Architecture
The system architecture is composed of four main components:
1. Sensor Layer : The sensor layer is responsible for collecting environmental data. Light sensors
measure the intensity of the ambient light and transmit the readings to the backend system.
2. Backend Layer : The backend server receives data from the sensor device, processes the incoming
information, and exposes APIs that allow other components of the system to access the stored
data.
3. Database Layer : The database stores the collected sensor data, enabling the system to maintain
historical records and support data retrieval for visualization and analysis.
4. Frontend Layer : The frontend application provides a graphical interface that allows users to
monitor light intensity in real time through dashboards, charts, and visual indicators.
## 1.5 Team Structure
The project is implemented through collaboration between four teams:

• Embedded Team – responsible for sensor integration and data collection

• Backend Team – responsible for server logic, APIs, and database integration

• Frontend Team – responsible for developing the user dashboard

• DevOps Team – responsible for version control, deployment, and system integration

This structure simulates real-world software development where multiple teams collaborate to build
scalable systems.

## 1.6 Objectives of the Project
The main objectives of this project are:

• To design an IoT system capable of collecting real-time environmental data

• To develop backend services that process and store sensor data

• To build a web-based dashboard for monitoring sensor readings

• To integrate database systems for data storage and retrieval

• To deploy the system using modern DevOps practices and cloud hosting

## 1.7 Scope of the Project
The scope of this project focuses on developing a functional IoT monitoring system capable of collecting, storing, and visualizing light intensity data.The system provides real-time monitoring through a
deployed web application.
The deployed system can be accessed through the live platform:
IoT Light Sensor Dashboard: https://iot-light-sensoruop.onrender.com/




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



---
