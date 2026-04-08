#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <BH1750.h>
#include <time.h>
#include <SPIFFS.h>
#include <ArduinoOTA.h>

#define BACKLOG_FILE "/data.txt"
#define MAX_FILE_SIZE 50000
#define WIFI_TIMEOUT 30000

const char* ssid      = "PacDeviceReg";
const char* password  = "register";
const char* serverURL = "https://iot-light-sensor.onrender.com/api/v1/sensors/data";
const char* logURL    = "https://iot-light-sensor.onrender.com/api/device/log";
const char* sensorId  = "esp32_01";
const char* ntpServer = "pool.ntp.org";

BH1750 lightMeter;
WiFiClientSecure client;
bool backlogSent = false;

// ----- WiFi -----

bool connectWiFi(unsigned long timeoutMs = WIFI_TIMEOUT) {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.printf("Connecting to %s\n", ssid);
  WiFi.begin(ssid, password);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    delay(500); Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? "\nWiFi connected" : "\nWiFi connection failed");
  return WiFi.status() == WL_CONNECTED;
}

// ----- Storage -----

void storeReading(const String& payload) {
  if (SPIFFS.exists(BACKLOG_FILE) && SPIFFS.open(BACKLOG_FILE, FILE_READ).size() > MAX_FILE_SIZE) {
    Serial.println("Backlog full — clearing");
    SPIFFS.remove(BACKLOG_FILE);
  }
  File f = SPIFFS.open(BACKLOG_FILE, FILE_APPEND);
  if (f) { f.println(payload); f.close(); }
}

// ----- HTTP -----

void logError(int code, const String& context) {
  HTTPClient https;
  https.begin(client, logURL);
  https.addHeader("Content-Type", "application/json");
  String body = "{\"sensor_id\":\"" + String(sensorId) +
                "\",\"timestamp\":\"" + getISOTime() +
                "\",\"error_code\":" + String(code) +
                ",\"context\":\"" + context + "\"}";
  https.POST(body);
  https.end();
}

bool sendPayload(const String& payload) {
  HTTPClient https;
  https.begin(client, serverURL);
  https.addHeader("Content-Type", "application/json");
  int code = https.POST(payload);
  https.end();
  bool ok = code > 0 && code < 300;
  if (!ok) logError(code, "sensors/data");
  Serial.println(ok ? "Upload successful" : "Upload failed");
  return ok;
}

void sendBacklog() {
  if (!SPIFFS.exists(BACKLOG_FILE)) return;
  File f = SPIFFS.open(BACKLOG_FILE, FILE_READ);
  if (!f) return;
  Serial.println("Sending backlog...");
  String remaining = "";
  while (f.available()) {
    String line = f.readStringUntil('\n');
    if (line.length() > 0 && !sendPayload(line)) remaining += line + "\n";
  }
  f.close();
  SPIFFS.remove(BACKLOG_FILE);
  if (remaining.length() > 0) {
    File nf = SPIFFS.open(BACKLOG_FILE, FILE_WRITE);
    if (nf) { nf.print(remaining); nf.close(); }
    Serial.println("Backlog partially sent.");
  } else {
    Serial.println("Backlog cleared.");
  }
}

// ----- Helpers -----

String getISOTime() {
  struct tm t;
  if (!getLocalTime(&t)) return "1970-01-01T00:00:00Z";
  char buf[30];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

String buildPayload(float lux) {
  return "{\"sensor_id\":\"" + String(sensorId) +
         "\",\"timestamp\":\"" + getISOTime() +
         "\",\"lux\":" + String(lux) + "}";
}

// ----- Setup / Loop -----

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  connectWiFi();
  ArduinoOTA.begin();
  if (!SPIFFS.begin(true))        { Serial.println("SPIFFS failed"); return; }
  configTime(0, 0, ntpServer);
  struct tm t;
  while (!getLocalTime(&t))       { Serial.println("Waiting for NTP..."); delay(1000); }
  if (!lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x23))
    Serial.println("BH1750 init failed");
  else
    Serial.println("BH1750 ready");
  client.setInsecure();
}

void loop() {
  ArduinoOTA.handle(); 
  connectWiFi();  // reconnects if needed, no-op if already connected
  String payload = buildPayload(lightMeter.readLightLevel());
  Serial.println(payload);

  if (WiFi.status() == WL_CONNECTED) {
    if (!backlogSent) { sendBacklog(); backlogSent = true; }
    if (!sendPayload(payload)) storeReading(payload);
  } else {
    backlogSent = false;
    storeReading(payload);
  }
  delay(5000);
}
