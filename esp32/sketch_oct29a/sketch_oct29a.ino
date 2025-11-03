#include <WiFiManager.h>
#include <WebServer.h>
#include <Preferences.h>
#include <HTTPClient.h>

WebServer server(80);
Preferences prefs;

// =========================
// HTML 페이지 (초기 설정)
// =========================
String initPage = R"rawliteral(
<html>
  <head>
    <meta charset='utf-8'>
    <style>
      body { font-family: sans-serif; text-align: center; }
      .section { border: 1px solid #ddd; padding: 10px; margin: 10px auto; width: 80%; border-radius: 10px; }
      input, select { width: 80%; max-width: 400px; padding: 5px; }
      button { margin-top: 10px; padding: 8px 20px; }
    </style>
  </head>
  <body>
    <h2>SleepTech 초기 설정</h2>
    <form action='/save_init' method='POST'>
      <div class='section'>
        <label>이름:</label><br>
        <input type='text' name='name'><br><br>

        <label>나이:</label><br>
        <input type='number' name='age' min='10' max='100'><br><br>

        <label>성별:</label><br>
        <select name='gender'>
          <option value='남성'>남성</option>
          <option value='여성'>여성</option>
        </select><br><br>

        <label>직업:</label><br>
        <input type='text' name='job'><br><br>
      </div>
      <button type='submit'>저장</button>
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
      body { font-family: sans-serif; text-align: center; }
      .hidden { display: none; }
      .section { border: 1px solid #ddd; padding: 10px; margin: 10px auto; width: 80%; border-radius: 10px; }
      input, select, textarea { width: 80%; max-width: 400px; padding: 5px; }
      button { font-size: 16px; margin-top: 10px; padding: 8px 20px; }
    </style>
    <script>
      function toggleMode(mode) {
        const manual = document.getElementById('manualSection');
        if (mode === 'manual') manual.classList.remove('hidden');
        else manual.classList.add('hidden');
      }
    </script>
  </head>

  <body>
    <h2>SleepTech 생활 패턴 입력</h2>

    <form action='/save' method='POST'>
      <div class='section'>
        <h3>생활 패턴 입력</h3>
        <label>기상 시간:</label><br>
        <input type='time' name='wake'><br><br>

        <label>취침 시간:</label><br>
        <input type='time' name='sleep'><br><br>

        <label>주중 생활 패턴:</label><br>
        <textarea name='weekday' rows='3'></textarea><br><br>

        <label>주말 생활 패턴:</label><br>
        <textarea name='weekend' rows='3'></textarea><br><br>

        <label>수면 목표(시간):</label><br>
        <input type='number' name='goal' min='4' max='10' step='0.5' value='7'><br><br>

        <label>현재 수면 만족도 (1~10):</label><br>
        <input type='number' name='satisfaction' min='1' max='10' value='5'><br>
      </div>

      <div class='section'>
        <h3>모드 선택</h3>
        <input type='radio' name='mode' value='ai' checked onclick='toggleMode("ai")'> AI 추천 모드<br>
        <input type='radio' name='mode' value='manual' onclick='toggleMode("manual")'> 직접 설정 모드
      </div>

      <div id='manualSection' class='section hidden'>
        <h3>직접 조명 설정</h3>
        <label>켜지는 시간:</label><br>
        <input type='time' name='onTime'><br><br>
        <label>꺼지는 시간:</label><br>
        <input type='time' name='offTime'><br><br>
        <label>색상 선택:</label><br>
        <input type='radio' name='colorMode' value='warm'> 따뜻한 빛 (2700K)<br>
        <input type='radio' name='colorMode' value='cool'> 차가운 빛 (6500K)<br><br>
        <label>밝기 단계 (1~10):</label><br>
        <input type='number' name='brightness' min='1' max='10' value='5'><br>
      </div>

      <div class='section'>
        <h3>💤 수면의 질 평가</h3>
        <label>오늘 아침 기분:</label><br>
        <select name='morningFeel'>
          <option value='좋음'>좋음</option>
          <option value='보통'>보통</option>
          <option value='나쁨'>나쁨</option>
        </select><br><br>

        <label>밤중에 깬 횟수:</label><br>
        <input type='number' name='wakeCount' min='0' max='10' value='0'><br><br>

        <label>수면 품질 (1~10):</label><br>
        <input type='number' name='quality' min='1' max='10' value='7'><br>
      </div>

      <button type='submit'>저장</button>
    </form>

    <br>
    <a href='/init'><button>⚙ 초기 설정 페이지로 이동</button></a>
  </body>
</html>
)rawliteral";

// =========================
// 함수들
// =========================
void handleRoot() {
  // 초기 설정이 되어있는지 확인
  prefs.begin("init", true);
  bool isInitDone = prefs.getBool("done", false);
  prefs.end();

  if (!isInitDone)
    server.send(200, "text/html; charset=utf-8", initPage);
  else
    server.send(200, "text/html; charset=utf-8", mainPage);
}

void handleSaveInit() {
  String name = server.arg("name");
  int age = server.arg("age").toInt();
  String gender = server.arg("gender");
  String job = server.arg("job");

  prefs.begin("init", false);
  prefs.putString("name", name);
  prefs.putInt("age", age);
  prefs.putString("gender", gender);
  prefs.putString("job", job);
  prefs.putBool("done", true);
  prefs.end();

  // Flask로 전송
  HTTPClient http;
  http.begin("https://sleeptech-server.onrender.com/save_init");
  http.addHeader("Content-Type", "application/json");

  String json = "{\"name\":\"" + name + "\",\"age\":" + String(age) +
                ",\"gender\":\"" + gender + "\",\"job\":\"" + job + "\"}";
  int code = http.POST(json);
  http.end();

  server.send(200, "text/html; charset=utf-8", "<h3>✅ 초기 설정 완료!</h3><a href='/'>메인으로</a>");
}

void handleSave() {
  String mode = server.arg("mode");
  String wake = server.arg("wake");
  String sleep = server.arg("sleep");
  float goal = server.arg("goal").toFloat();
  int satisfaction = server.arg("satisfaction").toInt();
  String weekday = server.arg("weekday");
  String weekend = server.arg("weekend");

  String morningFeel = server.arg("morningFeel");
  int wakeCount = server.arg("wakeCount").toInt();
  int quality = server.arg("quality").toInt();

  // Flask 전송
  HTTPClient http;
  http.begin("https://sleeptech-server.onrender.com/save_pattern");
  http.addHeader("Content-Type", "application/json");

  String json = "{\"mode\":\"" + mode + "\",\"wake\":\"" + wake + "\",\"sleep\":\"" + sleep +
                "\",\"goal\":" + String(goal) + ",\"satisfaction\":" + String(satisfaction) +
                ",\"morningFeel\":\"" + morningFeel + "\",\"wakeCount\":" + String(wakeCount) +
                ",\"quality\":" + String(quality) + "}";
  int code = http.POST(json);
  http.end();

  server.send(200, "text/html; charset=utf-8",
               "<h3>✅ 데이터 저장 완료!</h3><a href='/'>뒤로가기</a>");
}

// =========================
// SETUP / LOOP
// =========================
void setup() {
  Serial.begin(115200);
  WiFiManager wm;
  wm.autoConnect("SleepTech_Setup");

  server.on("/", handleRoot);
  server.on("/save", handleSave);
  server.on("/init", []() { server.send(200, "text/html; charset=utf-8", initPage); });
  server.on("/save_init", handleSaveInit);
  server.begin();

  Serial.println("✅ SleepTech Server Ready");
}

void loop() {
  server.handleClient();
}
