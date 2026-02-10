from app import get_sensor_status, generate_sensor_reading

def test_sensor_status_dark():
    result = get_sensor_status(10)
    assert result["level"] == "Dark"

def test_sensor_status_normal():
    result = get_sensor_status(30)
    assert result["level"] == "Normal"

def test_generate_sensor_range():
    for _ in range(100):
        value = generate_sensor_reading()
        assert 0 <= value <= 50
