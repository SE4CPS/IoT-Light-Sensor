/**
 * ESP32: scan for a known SSID (e.g. before joining "PacDeviceReg").
 * Use for Sensor 2 setup — replace WiFi credentials in the main BH1750 sketch after confirming the network is visible.
 */
#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(2000);

  uint8_t mac[6];
  WiFi.macAddress(mac);

  Serial.print("WiFi MAC: ");
  for (int i = 0; i < 6; i++) {
    if (mac[i] < 16) Serial.print("0");
    Serial.print(mac[i], HEX);
    if (i < 5) Serial.print(":");
  }
  Serial.println();

  int n = WiFi.scanNetworks();
  bool found = false;

  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == "PacDeviceReg") {
      found = true;
      Serial.println("PacDeviceReg FOUND");
      Serial.print("RSSI: ");
      Serial.println(WiFi.RSSI(i));
      Serial.print("Channel: ");
      Serial.println(WiFi.channel(i));
      Serial.print("Encryption type: ");
      Serial.println(WiFi.encryptionType(i));
    }
  }

  if (!found) {
    Serial.println("PacDeviceReg NOT FOUND");
  }
}

void loop() {}
