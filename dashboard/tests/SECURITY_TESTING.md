# Security Testing Guide for IoT Light Sensor API

## Overview
This document describes the security testing approach for validating input sanitization and injection attack prevention in the IoT Light Sensor API.

## Test Coverage

### 1. NoSQL Injection Prevention
**Vulnerabilities Tested:**
- MongoDB operator injection (`$ne`, `$gt`, `$where`, `$regex`)
- Query manipulation attacks
- Authentication bypass attempts

**Test Cases:**
- `test_mongodb_operator_injection_blocked()`
- `test_where_operator_injection_blocked()`
- `test_regex_injection_blocked()`

### 2. Cross-Site Scripting (XSS) Prevention
**Vulnerabilities Tested:**
- Script tag injection
- Event handler injection (`onerror`, `onload`)
- SVG-based XSS
- HTML entity encoding

**Test Cases:**
- `test_script_tag_injection_blocked()`
- `test_event_handler_injection_blocked()`
- `test_security_headers_present()`

### 3. Input Length Validation
**Limits Enforced:**
- `device_id`: max 50 characters
- `room`: max 20 characters
- `feedback message`: max 1000 characters
- `event`: max 200 characters

**Test Cases:**
- `test_device_id_length_limit_enforced()`
- `test_feedback_message_length_limit()`
- `test_event_description_length_limit()`

### 4. Character Whitelisting
**Allowed Characters:**
- `device_id`: `[a-zA-Z0-9_-]`
- `room`: Whitelist of 6 predefined values

**Test Cases:**
- `test_device_id_special_characters_rejected()`
- `test_room_name_whitelist_enforced()`
- `test_valid_room_names_accepted()`

### 5. Command Injection Prevention
**Vulnerabilities Tested:**
- Shell command injection (`;`, `&&`, `||`)
- Backtick command substitution
- Command substitution (`$()`)

**Test Cases:**
- `test_shell_command_in_device_id_blocked()`
- `test_backtick_command_execution_prevented()`

### 6. Path Traversal Prevention
**Vulnerabilities Tested:**
- Unix path traversal (`../../../etc/passwd`)
- Windows path traversal (`..\\..\\windows`)
- URL-encoded traversal

**Test Cases:**
- `test_directory_traversal_in_room_blocked()`
- `test_windows_path_traversal_blocked()`

## Running Tests

### Run All Security Tests
```bash
cd ~/Desktop/IoT-Light-Sensor/dashboard
pytest tests/test_input_validation.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_input_validation.py::TestNoSQLInjectionPrevention -v
pytest tests/test_input_validation.py::TestXSSPrevention -v
```

### Run with Coverage
```bash
pytest tests/test_input_validation.py --cov=app --cov-report=html
```

## Expected Results

### All Tests Should:
- ✅ Return `400 Bad Request` for invalid input
- ✅ Include descriptive error messages
- ✅ Not leak system information in errors
- ✅ Prevent data modification on validation failure
- ✅ Log security violations for audit

### Security Headers Expected:
## GitHub Copilot Prompts Used

### Finding NoSQL Injection Vulnerabilities
### Finding XSS Vulnerabilities
## Remediation Checklist

- [ ] Install validation library (marshmallow/pydantic)
- [ ] Create validation schemas for all endpoints
- [ ] Apply schemas to route handlers
- [ ] Add HTML sanitization (bleach library)
- [ ] Configure security headers
- [ ] Add rate limiting
- [ ] Enable request size limits
- [ ] Update Swagger documentation
- [ ] Run full security test suite
- [ ] Conduct penetration testing

## References

- [OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [NoSQL Injection](https://owasp.org/www-community/attacks/NoSQL_injection)
- [XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [Marshmallow Docs](https://marshmallow.readthedocs.io/)

## Contact

**Security Lead**: @Shradhapujari (API Architect)  
**Created**: April 10, 2026  
**Last Updated**: April 10, 2026
