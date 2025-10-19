#include <WiFiManager.h>
#include <WebServer.h>
#include <Preferences.h>

WebServer server(80);
Preferences prefs;

String htmlPage = R"rawliteral(
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
        <textarea name='weekday' rows='3' placeholder='예: 아침 운동, 공부, 오후 휴식'></textarea><br><br>

        <label>주말 생활 패턴:</label><br>
        <textarea name='weekend' rows='3' placeholder='예: 늦게 기상, 영화 시청'></textarea><br><br>

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

      <button type='submit'>저장</button>
    </form>
  </body>
</html>
)rawliteral";

void handleRoot() {
  server.send(200, "text/html; charset=utf-8", htmlPage);
}

void handleSave() {
  String mode = server.arg("mode");
  String wake = server.arg("wake");
  String sleep = server.arg("sleep");
  String weekday = server.arg("weekday");
  String weekend = server.arg("weekend");
  float goal = server.arg("goal").toFloat();
  int satisfaction = server.arg("satisfaction").toInt();

  // 직접 설정 모드일 경우 추가 데이터
  String onTime = server.arg("onTime");
  String offTime = server.arg("offTime");
  String colorMode = server.arg("colorMode");
  int brightness = server.arg("brightness").toInt();

  prefs.begin("pattern", false);
  prefs.putString("mode", mode);
  prefs.putString("wake", wake);
  prefs.putString("sleep", sleep);
  prefs.putString("weekday", weekday);
  prefs.putString("weekend", weekend);
  prefs.putFloat("goal", goal);
  prefs.putInt("satisfaction", satisfaction);

  if (mode == "manual") {
    prefs.putString("on", onTime);
    prefs.putString("off", offTime);
    prefs.putString("color", colorMode);
    prefs.putInt("bright", brightness);
  }
  prefs.end();

  String msg = "<html><body><h3>✅ 설정이 저장되었습니다.</h3>";
  if (mode == "ai")
    msg += "<p>AI 추천 모드가 선택되었습니다. 나중에 AI 분석 결과가 적용됩니다.</p>";
  else
    msg += "<p>직접 설정 모드로 조명 스케줄이 적용됩니다.</p>";
  msg += "<a href='/'>뒤로가기</a></body></html>";

  server.send(200, "text/html; charset=utf-8", msg);

  // 디버그 출력
  Serial.printf("📋 mode:%s wake:%s sleep:%s goal:%.1f 만족도:%d\n",
                mode.c_str(), wake.c_str(), sleep.c_str(), goal, satisfaction);
  if (mode == "manual") {
    Serial.printf("   ⏰ on:%s off:%s color:%s bright:%d\n",
                  onTime.c_str(), offTime.c_str(), colorMode.c_str(), brightness);
  }
}

void setup() {
  Serial.begin(115200);
  WiFiManager wm;
  wm.autoConnect("SleepTech_Setup");

  server.on("/", handleRoot);
  server.on("/save", handleSave);
  server.begin();

  Serial.println("🌐 Lifestyle Config Server Ready");
}

void loop() {
  server.handleClient();
}
