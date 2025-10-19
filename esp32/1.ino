#include <WiFiManager.h>
#include <WiFi.h>
#include <WebServer.h>

#define LED_PIN 2 // 내장 LED (테스트용)

// 웹서버 객체 생성
WebServer server(80);

void handleRoot() {
  String html = "<html><body style='text-align:center;'>";
  html += "<h2>SleepTech Smart Light</h2>";
  html += "<button style='font-size:24px;padding:10px 20px;' onclick=\"location.href='/on'\">💡 ON</button>";
  html += "<button style='font-size:24px;padding:10px 20px;margin-left:20px;' onclick=\"location.href='/off'\">💤 OFF</button>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleOn() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED ON");
  server.sendHeader("Location", "/");
  server.send(303); // redirect back
}

void handleOff() {
  digitalWrite(LED_PIN, LOW);
  Serial.println("LED OFF");
  server.sendHeader("Location", "/");
  server.send(303);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  // WiFiManager: Wi-Fi 연결
  WiFiManager wm;
  if (!wm.autoConnect("SleepTech_Setup")) {
    Serial.println("Wi-Fi 연결 실패, 재시작합니다...");
    delay(3000);
    ESP.restart();
  }

  Serial.println("✅ Wi-Fi 연결됨");
  Serial.print("IP 주소: ");
  Serial.println(WiFi.localIP());

  // 서버 라우팅 정의
  server.on("/", handleRoot);
  server.on("/on", handleOn);
  server.on("/off", handleOff);

  // 서버 시작
  server.begin();
  Serial.println("🌐 웹 서버 시작됨");
}

void loop() {
  server.handleClient();
}
