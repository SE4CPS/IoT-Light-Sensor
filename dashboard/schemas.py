"""
Input validation schemas for API endpoints
Uses Marshmallow for schema validation and sanitization
"""
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime


class SensorDataSchema(Schema):
    """Validation schema for sensor data submissions"""
    device_id = fields.Str(
        required=True,
        validate=[
            validate.Length(max=50, error="device_id must be 50 characters or less"),
            validate.Regexp(
                r'^[a-zA-Z0-9_-]+$', 
                error="device_id can only contain letters, numbers, underscore, and hyphen"
            )
        ]
    )
    lux = fields.Float(
        required=True,
        validate=validate.Range(
            min=0, 
            max=100000, 
            error="lux must be between 0 and 100000"
        )
    )
    room = fields.Str(
        required=True,
        validate=validate.OneOf(
            ['living', 'bedroom', 'kitchen', 'bathroom', 'office', 'garage'],
            error="room must be one of: living, bedroom, kitchen, bathroom, office, garage"
        )
    )
    timestamp = fields.DateTime(
        required=True,
        format='iso',
        error="timestamp must be in ISO 8601 format"
    )


class FeedbackSchema(Schema):
    """Validation schema for user feedback"""
    user_id = fields.Str(
        required=True,
        validate=validate.Length(max=50, error="user_id must be 50 characters or less")
    )
    message = fields.Str(
        required=True,
        validate=validate.Length(
            min=1,
            max=1000, 
            error="message must be between 1 and 1000 characters"
        )
    )
    rating = fields.Int(
        validate=validate.Range(
            min=1, 
            max=5, 
            error="rating must be between 1 and 5"
        )
    )


class DeviceLogSchema(Schema):
    """Validation schema for device logs"""
    device_id = fields.Str(
        required=True,
        validate=[
            validate.Length(max=50, error="device_id must be 50 characters or less"),
            validate.Regexp(
                r'^[a-zA-Z0-9_-]+$',
                error="device_id can only contain letters, numbers, underscore, and hyphen"
            )
        ]
    )
    event = fields.Str(
        required=True,
        validate=validate.Length(max=200, error="event must be 200 characters or less")
    )
    timestamp = fields.DateTime(
        required=True,
        format='iso',
        error="timestamp must be in ISO 8601 format"
    )
    data = fields.Str(
        validate=validate.Length(max=5000, error="data must be 5000 characters or less")
    )


class RoomDataSchema(Schema):
    """Validation schema for room-specific data"""
    light_state = fields.Str(
        required=True,
        validate=validate.OneOf(
            ['ON', 'OFF'],
            error="light_state must be either 'ON' or 'OFF'"
        )
    )
    duration = fields.Int(
        required=True,
        validate=validate.Range(
            min=0,
            max=86400,  # 24 hours in seconds
            error="duration must be between 0 and 86400 seconds"
        )
    )
    timestamp = fields.DateTime(
        required=True,
        format='iso',
        error="timestamp must be in ISO 8601 format"
    )


class AlertSchema(Schema):
    """Validation schema for system alerts"""
    alert_type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ['light_duration', 'sensor_offline', 'battery_low', 'system_error'],
            error="alert_type must be one of: light_duration, sensor_offline, battery_low, system_error"
        )
    )
    room = fields.Str(
        required=True,
        validate=validate.OneOf(
            ['living', 'bedroom', 'kitchen', 'bathroom', 'office', 'garage'],
            error="room must be one of: living, bedroom, kitchen, bathroom, office, garage"
        )
    )
    message = fields.Str(
        required=True,
        validate=validate.Length(max=500, error="message must be 500 characters or less")
    )
    severity = fields.Str(
        validate=validate.OneOf(
            ['low', 'medium', 'high', 'critical'],
            error="severity must be one of: low, medium, high, critical"
        )
    )
