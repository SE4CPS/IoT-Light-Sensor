/**
 * Sensor 2 (bedroom): same as BH1750_test but reports sensor_id esp32_02 for the dashboard badge.
 * Flash this sketch only on the second ESP32; keep BH1750_test on the first board (esp32_01).
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <BH1750.h>
#include <time.h>

const char* ssid = "[ENTER_YOUR_WIFI]";
const char* password = "[ENTER_YOUR_PASSWORD]";

// ----- Backend Info -----
const char* serverURL = "https://iot-light-sensor.onrender.com/api/v1/sensors/data";
const char* sensorId = "esp32_02";

// ----- Sensor -----
BH1750 lightMeter;

// ----- NTP / Time -----
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = 0;  // UTC
const int   daylightOffset_sec = 0;

// WiFi client for HTTPS
WiFiClientSecure client;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);  // SDA, SCL

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) {
    Serial.println("Waiting for NTP time sync...");
    delay(1000);
  }

  if (!lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x23)) {
    Serial.println("Error initializing BH1750 — check wiring and address!");
  } else {
    Serial.println("BH1750 started!");
  }

  client.setInsecure();
}

String getISOTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "1970-01-01T00:00:00Z";
  }
  char buffer[30];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buffer);
}

void loop() {
  float lux = lightMeter.readLightLevel();
  String timestamp = getISOTime();

  String payload = "{";
  payload += "\"sensor_id\":\"" + String(sensorId) + "\",";
  payload += "\"timestamp\":\"" + String(timestamp) + "\",";
  payload += "\"lux\":" + String(lux);
  payload += "}";

  Serial.println("Sending payload:");
  Serial.println(payload);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient https;
    https.begin(client, serverURL);
    https.addHeader("Content-Type", "application/json");

    int httpResponseCode = https.POST(payload);
    if (httpResponseCode > 0) {
      Serial.print("Response code: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Error sending data: ");
      Serial.println(httpResponseCode);
    }
    https.end();
  } else {
    Serial.println("WiFi not connected!");
  }
  delay(5000);
}
