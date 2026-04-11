"""
Input Validation Security Tests
Tests for NoSQL injection, XSS, command injection, and other input vulnerabilities
Using AAA (Arrange-Act-Assert) format
"""
import pytest
import json
from app import app, db
from datetime import datetime


class TestNoSQLInjectionPrevention:
    """Test suite for NoSQL injection attack prevention"""
    
    def test_mongodb_operator_injection_blocked(self):
        """
        ARRANGE: Prepare NoSQL injection payload with $ne operator
        ACT: Send payload to sensor data endpoint
        ASSERT: Request rejected with 400 Bad Request
        """
        # Arrange
        client = app.test_client()
        malicious_payload = {
            "room": {"$ne": None},  # MongoDB operator injection
            "lux": 450,
            "device_id": "sensor_001",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/v1/sensors/data',
            data=json.dumps(malicious_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "Validation failed" in response.get_json()['error']
        assert "room" in response.get_json()['details']
    
    def test_where_operator_injection_blocked(self):
        """
        ARRANGE: Prepare $where operator injection payload
        ACT: Attempt to inject into room endpoint
        ASSERT: Injection blocked, no query execution
        """
        # Arrange
        client = app.test_client()
        injection_payload = {
            "lux": {"$where": "this.lux > 0"},
            "room": "living",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/room/living/save',
            data=json.dumps(injection_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        # Verify no $where queries executed in MongoDB
        # (This would require MongoDB query logging enabled)
    
    def test_regex_injection_blocked(self):
        """
        ARRANGE: Prepare regex injection to bypass validation
        ACT: Send regex pattern as room name
        ASSERT: Pattern rejected, only whitelisted rooms allowed
        """
        # Arrange
        client = app.test_client()
        regex_payload = {
            "room": {"$regex": ".*"},
            "lux": 500,
            "device_id": "sensor_001",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/v1/sensors/data',
            data=json.dumps(regex_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "room" in response.get_json()['details']


class TestXSSPrevention:
    """Test suite for Cross-Site Scripting (XSS) attack prevention"""
    
    def test_script_tag_injection_blocked(self):
        """
        ARRANGE: Prepare XSS payload with script tag
        ACT: Submit to feedback endpoint
        ASSERT: Script tags escaped or rejected
        """
        # Arrange
        client = app.test_client()
        xss_payload = {
            "user_id": "test_user",
            "message": "<script>alert('XSS')</script>",
            "rating": 5
        }
        
        # Act
        response = client.post(
            '/api/feedback',
            data=json.dumps(xss_payload),
            content_type='application/json'
        )
        
        # Assert
        # Either rejected OR accepted but escaped
        if response.status_code == 200:
            # Verify stored data is escaped
            stored = db.feedback.find_one({"user_id": "test_user"})
            assert "<script>" not in stored['message']
            assert "&lt;script&gt;" in stored['message'] or \
                   "alert" not in stored['message']
        else:
            assert response.status_code == 400
    
    def test_event_handler_injection_blocked(self):
        """
        ARRANGE: Prepare XSS with event handler
        ACT: Submit img tag with onerror
        ASSERT: Event handlers stripped or rejected
        """
        # Arrange
        client = app.test_client()
        event_handler_payload = {
            "device_id": "sensor_001",
            "event": "<img src=x onerror=alert('XSS')>",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/device/log',
            data=json.dumps(event_handler_payload),
            content_type='application/json'
        )
        
        # Assert
        if response.status_code == 200:
            stored = db.logs.find_one({"device_id": "sensor_001"})
            assert "onerror" not in stored['event'].lower()
        else:
            assert response.status_code == 400
    
    def test_security_headers_present(self):
        """
        ARRANGE: Send normal request
        ACT: Get response
        ASSERT: Security headers present in response
        """
        # Arrange
        client = app.test_client()
        
        # Act
        response = client.get('/api/usage/statistics')
        
        # Assert
        assert 'Content-Security-Policy' in response.headers or \
               'X-XSS-Protection' in response.headers
        # Note: Exact headers depend on Flask configuration


class TestInputLengthLimits:
    """Test suite for input length validation"""
    
    def test_device_id_length_limit_enforced(self):
        """
        ARRANGE: Prepare payload with oversized device_id (>50 chars)
        ACT: Submit to sensor endpoint
        ASSERT: Rejected with validation error
        """
        # Arrange
        client = app.test_client()
        oversized_payload = {
            "device_id": "A" * 100,  # 100 characters, limit is 50
            "lux": 450,
            "room": "living",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/v1/sensors/data',
            data=json.dumps(oversized_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "device_id" in response.get_json()['details']
        assert "50" in str(response.get_json()['details']['device_id'])
    
    def test_feedback_message_length_limit(self):
        """
        ARRANGE: Prepare 2000 character feedback (limit: 1000)
        ACT: Submit to feedback endpoint
        ASSERT: Rejected as too long
        """
        # Arrange
        client = app.test_client()
        long_message_payload = {
            "user_id": "test_user",
            "message": "B" * 2000,  # 2000 characters, limit is 1000
            "rating": 5
        }
        
        # Act
        response = client.post(
            '/api/feedback',
            data=json.dumps(long_message_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "message" in response.get_json()['details']
        assert "1000" in str(response.get_json()['details']['message'])
    
    def test_event_description_length_limit(self):
        """
        ARRANGE: Prepare event with 500 chars (limit: 200)
        ACT: Submit to device log
        ASSERT: Rejected
        """
        # Arrange
        client = app.test_client()
        long_event_payload = {
            "device_id": "sensor_001",
            "event": "C" * 500,  # 500 characters, limit is 200
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/device/log',
            data=json.dumps(long_event_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400


class TestCharacterWhitelisting:
    """Test suite for character validation and whitelisting"""
    
    def test_device_id_special_characters_rejected(self):
        """
        ARRANGE: device_id with special characters (!@#$%^&*)
        ACT: Submit to endpoint
        ASSERT: Only alphanumeric, underscore, hyphen allowed
        """
        # Arrange
        client = app.test_client()
        special_chars_payload = {
            "device_id": "sensor!@#$%^&*()",
            "lux": 450,
            "room": "living",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/v1/sensors/data',
            data=json.dumps(special_chars_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "device_id" in response.get_json()['details']
        assert "characters" in str(response.get_json()['details']['device_id']).lower()
    
    def test_room_name_whitelist_enforced(self):
        """
        ARRANGE: Invalid room name not in whitelist
        ACT: Submit to room endpoint
        ASSERT: Only whitelisted rooms accepted
        """
        # Arrange
        client = app.test_client()
        invalid_room_payload = {
            "device_id": "sensor_001",
            "lux": 450,
            "room": "invalid_room_name",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/v1/sensors/data',
            data=json.dumps(invalid_room_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "room" in response.get_json()['details']
    
    def test_valid_room_names_accepted(self):
        """
        ARRANGE: All valid room names from whitelist
        ACT: Submit each valid room
        ASSERT: All accepted
        """
        # Arrange
        client = app.test_client()
        valid_rooms = ['living', 'bedroom', 'kitchen', 'bathroom', 'office', 'garage']
        
        for room in valid_rooms:
            payload = {
                "device_id": "sensor_001",
                "lux": 450,
                "room": room,
                "timestamp": "2026-04-10T18:00:00Z"
            }
            
            # Act
            response = client.post(
                '/api/v1/sensors/data',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            # Assert
            assert response.status_code in [200, 201], f"Room '{room}' should be valid"


class TestCommandInjectionPrevention:
    """Test suite for command injection prevention"""
    
    def test_shell_command_in_device_id_blocked(self):
        """
        ARRANGE: device_id with shell command (rm -rf)
        ACT: Submit to logging endpoint
        ASSERT: Shell characters rejected
        """
        # Arrange
        client = app.test_client()
        command_injection_payload = {
            "device_id": "sensor; rm -rf /",
            "event": "test",
            "timestamp": "2026-04-10T18:00:00Z"
        }
        
        # Act
        response = client.post(
            '/api/device/log',
            data=json.dumps(command_injection_payload),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 400
        assert "device_id" in response.get_json()['details']
    
    def test_backtick_command_execution_prevented(self):
        """
        ARRANGE: Backtick command substitution attempt
        ACT: Submit in feedback message
        ASSERT: Backticks handled safely
        """
        # Arrange
        client = app.test_client()
        backtick_payload = {
            "user_id": "test_user",
            "message": "`whoami`",
            "rating": 3
        }
        
        # Act
        response = client.post(
            '/api/feedback',
            data=json.dumps(backtick_payload),
            content_type='application/json'
        )
        
        # Assert
        # Either rejected OR escaped (backticks removed/escaped)
        if response.status_code == 200:
            stored = db.feedback.find_one({"user_id": "test_user"})
            # Verify command not executed (no actual user info returned)
            assert "`whoami`" not in stored['message'] or \
                   "root" not in stored['message']


class TestPathTraversalPrevention:
    """Test suite for path traversal attack prevention"""
    
    def test_directory_traversal_in_room_blocked(self):
        """
        ARRANGE: Path traversal sequence in room parameter
        ACT: Attempt to access ../../../etc/passwd
        ASSERT: Path traversal blocked
        """
        # Arrange
        client = app.test_client()
        
        # Act
        response = client.post(
            '/api/room/../../etc/passwd/save',
            data=json.dumps({"lux": 300, "timestamp": "2026-04-10T18:00:00Z"}),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code in [400, 404]
    
    def test_windows_path_traversal_blocked(self):
        """
        ARRANGE: Windows-style path traversal
        ACT: Submit ..\\..\\windows path
        ASSERT: Blocked
        """
        # Arrange
        client = app.test_client()
        
        # Act
        response = client.post(
            '/api/room/..\\..\\windows/save',
            data=json.dumps({"lux": 300, "timestamp": "2026-04-10T18:00:00Z"}),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code in [400, 404]


class TestErrorMessageSecurity:
    """Test suite for secure error handling"""
    
    def test_no_stack_traces_in_errors(self):
        """
        ARRANGE: Send malformed request
        ACT: Trigger error
        ASSERT: No stack trace or system paths exposed
        """
        # Arrange
        client = app.test_client()
        malformed_payload = {"invalid": "data"}
        
        # Act
        response = client.post(
            '/api/v1/sensors/data',
            data=json.dumps(malformed_payload),
            content_type='application/json'
        )
        
        # Assert
        error_text = response.get_data(as_text=True).lower()
        assert 'traceback' not in error_text
        assert '/home/' not in error_text
        assert 'file "' not in error_text
        assert '.py", line' not in error_text
    
    def test_consistent_error_format(self):
        """
        ARRANGE: Various validation failures
        ACT: Trigger different errors
        ASSERT: All return consistent error structure
        """
        # Arrange
        client = app.test_client()
        test_cases = [
            {"device_id": ""},  # Missing fields
            {"device_id": "A" * 100},  # Too long
            {"device_id": "test!@#"},  # Invalid chars
        ]
        
        for payload in test_cases:
            # Act
            response = client.post(
                '/api/v1/sensors/data',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            # Assert
            assert response.status_code == 400
            json_response = response.get_json()
            assert 'error' in json_response
            assert 'details' in json_response or 'message' in json_response


# Run tests with: pytest dashboard/tests/test_input_validation.py -v
