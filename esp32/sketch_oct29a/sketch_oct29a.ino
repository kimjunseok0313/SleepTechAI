#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <WebServer.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

WebServer server(80);
Preferences prefs;

// =========================
// PWM 설정 (LED 제어용)
// =========================
const int PIN_WARM = 25;   // 2700K 채널 (따뜻한 빛)
const int PIN_COOL = 26;   // 6500K 채널 (차가운 빛)

const int CH_WARM = 0;
const int CH_COOL = 1;
const int PWM_FREQ = 5000;
const int PWM_RES  = 8;    // 0~255 PWM 해상도

// 전원 상태
bool lightPower = true;

void setupPWM() {
  ledcSetup(CH_WARM, PWM_FREQ, PWM_RES);
  ledcSetup(CH_COOL, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_WARM, CH_WARM);
  ledcAttachPin(PIN_COOL, CH_COOL);
}

void applyLight(int warm_pwm, int cool_pwm) {
  // OFF 상태면 강제로 0 출력
  if (!lightPower) {
    warm_pwm = 0;
    cool_pwm = 0;
  }

  warm_pwm = constrain(warm_pwm, 0, 255);
  cool_pwm = constrain(cool_pwm, 0, 255);

  ledcWrite(CH_WARM, warm_pwm);
  ledcWrite(CH_COOL, cool_pwm);

  Serial.printf("💡 조명 적용 → Power:%s | Warm:%d Cool:%d\n",
                lightPower ? "ON" : "OFF",
                warm_pwm, cool_pwm);
}

// =========================
// HTML 페이지 (초기 설정)
// =========================
String initPage = R"rawliteral(
<html>
  <head>
    <meta charset='utf-8'>
    <style>
      body {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
        text-align: center;
        background: linear-gradient(135deg, #9ec6ff, #eaf1ff);
        padding: 20px;
        margin: 0;
      }

      h2 {
        color: #003d82;
        margin-bottom: 15px;
      }

      .section {
        background: #fff;
        padding: 25px;
        width: 85%;
        max-width: 400px;
        margin: 0 auto;
        border-radius: 14px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        margin-top: 15px;
      }

      label {
        display: block;
        text-align: left;
        width: 90%;
        max-width: 360px;
        margin: 0 auto;
        font-weight: 600;
        color: #24446a;
      }

      input, select {
        width: 90%;
        max-width: 360px;
        padding: 10px;
        margin-top: 6px;
        font-size: 15px;
        border-radius: 8px;
        border: 1px solid #c0d3ef;
        box-sizing: border-box;
      }

      button {
        background: #0059d6;
        color: white;
        padding: 12px 25px;
        border-radius: 10px;
        border: none;
        margin-top: 18px;
        font-size: 17px;
        cursor: pointer;
        transition: 0.2s;
      }

      button:hover {
        background: #003c96;
      }
    </style>
  </head>

  <body>
    <h2>⚙ SleepTech 초기 설정</h2>

    <form action='/save_init' method='POST'>
      <div class='section'>
        <label>이름</label>
        <input type='text' name='name'><br><br>

        <label>나이</label>
        <input type='number' name='age' min='10' max='100'><br><br>

        <label>성별</label>
        <select name='gender'>
          <option value='남성'>남성</option>
          <option value='여성'>여성</option>
        </select><br><br>

        <label>직업</label>
        <input type='text' name='job'><br><br>
      </div>

      <button type='submit'>저장하기</button>
    </form>
  </body>
</html>
)rawliteral";

// =========================
// HTML 페이지 (생활 패턴 입력)
// =========================
String mainPage = R"rawliteral(
<html>
  <head>
    <meta charset='utf-8'>
    <style>
      body {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
        text-align: center;
        background: linear-gradient(135deg, #a8caff, #edf4ff);
        padding: 20px;
        margin: 0;
      }

      h2 {
        color: #003d82;
        margin-bottom: 15px;
      }

      .section {
        background: #fff;
        padding: 25px;
        width: 85%;
        max-width: 500px;
        margin: 0 auto;
        border-radius: 16px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        margin-top: 18px;
      }

      h3 {
        margin-top: 0;
        margin-bottom: 15px;
        color: #23456e;
      }

      label {
        display: block;
        text-align: left;
        width: 90%;
        max-width: 420px;
        margin: 0 auto;
        font-weight: 600;
        color: #24446a;
      }

      input, select {
        width: 90%;
        max-width: 420px;
        padding: 10px;
        margin-top: 8px;
        border-radius: 8px;
        font-size: 15px;
        border: 1px solid #c0d3ef;
        box-sizing: border-box;
      }

      button {
        background: #0059d6;
        color: white;
        padding: 12px 25px;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        font-size: 17px;
        margin-top: 15px;
        transition: 0.2s;
      }

      button:hover {
        background: #003c96;
      }

      .toggle {
        background: #ffb300;
      }

      .toggle:hover {
        background: #d49300;
      }

      .secondary {
        background: #ffffff;
        color: #0059d6;
        border: 1px solid #b4c9f1;
      }

      .secondary:hover {
        background: #eaf1ff;
      }
    </style>
  </head>

  <body>
    <h2>🌙 SleepTech 생활 패턴 입력</h2>

    <form action='/save' method='POST'>
      <div class='section'>
        <h3>⏰ 생활 패턴</h3>

        <label>기상 시간</label>
        <input type='time' name='wake'><br><br>

        <label>취침 시간</label>
        <input type='time' name='sleep'><br><br>

        <label>수면 목표 (시간)</label>
        <input type='number' name='goal' min='4' max='10' step='0.5' value='7'><br><br>

        <label>수면 만족도 (1~10)</label>
        <input type='number' name='satisfaction' min='1' max='10' value='5'><br>
      </div>

      <div class='section'>
        <h3>💤 수면의 질 평가</h3>

        <label>오늘 아침 기분</label>
        <select name='morningFeel'>
          <option value='좋음'>좋음</option>
          <option value='보통'>보통</option>
          <option value='나쁨'>나쁨</option>
        </select><br><br>

        <label>밤중에 깬 횟수</label>
        <input type='number' name='wakeCount' min='0' max='10' value='0'><br><br>

        <label>수면 품질 (1~10)</label>
        <input type='number' name='quality' min='1' max='10' value='7'><br>
      </div>

      <button type='submit'>저장 & 적용</button>
    </form>

    <br>

    <button class='toggle' onclick="location.href='/toggle'">💡 전원 On/Off</button>

    <br><br>

    <button class='secondary' onclick="location.href='/init'">⚙ 초기 설정 페이지</button>

  </body>
</html>
)rawliteral";

// =========================
// HTTP 핸들러들
// =========================

void handleRoot() {
  prefs.begin("init", true);
  bool isInitDone = prefs.getBool("done", false);
  prefs.end();

  if (!isInitDone)
    server.send(200, "text/html; charset=utf-8", initPage);
  else
    server.send(200, "text/html; charset=utf-8", mainPage);
}

void handleSaveInit() {
  String name   = server.arg("name");
  int    age    = server.arg("age").toInt();
  String gender = server.arg("gender");
  String job    = server.arg("job");

  prefs.begin("init", false);
  prefs.putString("name", name);
  prefs.putInt("age", age);
  prefs.putString("gender", gender);
  prefs.putString("job", job);
  prefs.putBool("done", true);
  prefs.end();

  // ===== Flask 서버로 초기 설정 데이터 전송 =====
  WiFiClientSecure client;
  client.setInsecure();  // 인증서 검증 생략 (테스트용)

  HTTPClient http;
  if (http.begin(client, "https://sleeptech-server.onrender.com/save_init")) {
    http.addHeader("Content-Type", "application/json");

    String json = "{";
    json += "\"name\":\""   + name   + "\",";
    json += "\"age\":"      + String(age) + ",";
    json += "\"gender\":\"" + gender + "\",";
    json += "\"job\":\""    + job    + "\"";
    json += "}";

    int code = http.POST(json);
    Serial.printf("📡 /save_init POST code: %d\n", code);
    String resp = http.getString();
    Serial.println(resp);
    http.end();
  } else {
    Serial.println("❌ /save_init HTTP begin 실패");
  }

  server.send(200, "text/html; charset=utf-8",
              "<h3>✅ 초기 설정 완료!</h3><a href='/'>메인으로</a>");
}

void handleSave() {
  String wake         = server.arg("wake");
  String sleep        = server.arg("sleep");
  float  goal         = server.arg("goal").toFloat();
  int    satisfaction = server.arg("satisfaction").toInt();
  String morningFeel  = server.arg("morningFeel");
  int    wakeCount    = server.arg("wakeCount").toInt();
  int    quality      = server.arg("quality").toInt();

  // ===== Flask 서버로 생활 패턴 전송 =====
  WiFiClientSecure client;
  client.setInsecure();  // 인증서 검증 생략 (테스트용)

  HTTPClient http;
  String url = "https://sleeptech-server.onrender.com/save_pattern";

  if (http.begin(client, url)) {
    http.addHeader("Content-Type", "application/json");

    String json = "{";
    json += "\"wake\":\""         + wake + "\",";
    json += "\"sleep\":\""        + sleep + "\",";
    json += "\"goal\":"           + String(goal) + ",";
    json += "\"satisfaction\":"   + String(satisfaction) + ",";
    json += "\"morningFeel\":\""  + morningFeel + "\",";
    json += "\"wakeCount\":"      + String(wakeCount) + ",";
    json += "\"quality\":"        + String(quality);
    json += "}";

    int code = http.POST(json);
    Serial.printf("📡 /save_pattern POST code: %d\n", code);
    String response = http.getString();
    Serial.println(response);
    http.end();

    // ===== JSON 파싱 → light_plan 적용 =====
    StaticJsonDocument<1024> doc;
    DeserializationError err = deserializeJson(doc, response);

    if (!err) {
      JsonObject plan = doc["light_plan"];
      if (!plan.isNull()) {
        bool power     = plan["power"] | true;
        lightPower     = power;
        int warm_pwm   = plan["warm_pwm"] | 0;
        int cool_pwm   = plan["cool_pwm"] | 0;

        applyLight(warm_pwm, cool_pwm);
      } else {
        Serial.println("⚠️ light_plan 필드 없음");
      }
    } else {
      Serial.print("⚠️ JSON 파싱 실패: ");
      Serial.println(err.f_str());
    }
  } else {
    Serial.println("❌ /save_pattern HTTP begin 실패");
  }

  server.send(200, "text/html; charset=utf-8",
              "<h3>✅ 데이터 저장 & 조명 적용 완료!</h3><a href='/'>뒤로가기</a>");
}

// =========================
// 🔆 전원 토글 기능
// =========================
void handleToggle() {
  lightPower = !lightPower;

  if (!lightPower) {
    applyLight(0, 0);
  }

  String msg = "<h3>전원: ";
  msg += (lightPower ? "ON" : "OFF");
  msg += "</h3><a href='/'>뒤로가기</a>";

  server.send(200, "text/html; charset=utf-8", msg);
}

// =========================
// SETUP / LOOP
// =========================
void setup() {
  Serial.begin(115200);
  delay(1000);

  setupPWM();

  WiFiManager wm;
  wm.autoConnect("SleepTech_Setup");  // AP 모드로 최초 설정

  server.on("/",       handleRoot);
  server.on("/save",   handleSave);
  server.on("/toggle", handleToggle);
  server.on("/init", []() {
    server.send(200, "text/html; charset=utf-8", initPage);
  });
  server.on("/save_init", handleSaveInit);

  server.begin();
  Serial.println("✅ SleepTech ESP32 Ready");
}

void loop() {
  server.handleClient();
}
