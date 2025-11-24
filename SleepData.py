from flask import Flask, jsonify, request
import pandas as pd
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import joblib
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)

# ==============================
# 🔐 Google Sheets 설정
# ==============================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "/etc/secrets/credentials.json"
SHEET_ID = "1s5BKkultYwSUrEQxOajsWZvf64g0538kMKdii0WivTY"

DATA_FILE = "user_patterns.csv"
SLEEP_FILE = "sleep_data.csv"

# ==============================
# 🧠 ML 모델 로드
# ==============================
try:
    ML_MODEL = joblib.load("/etc/secrets/sleep_quality_model.pkl")
    print("✅ ML 모델 로드 완료")
except:
    ML_MODEL = None
    print("⚠️ ML 모델 로드 실패 - 기본 규칙만 작동")


# ==============================
# ⚙️ 유틸 함수
# ==============================
def _last_row_as_dict(ws):
    vals = ws.get_all_records()
    if not vals:
        return {}
    return vals[-1]


def _hhmm_to_dt_today(hhmm: str):
    try:
        t = datetime.strptime(hhmm, "%H:%M").time()
        now = datetime.now()
        return datetime(now.year, now.month, now.day, t.hour, t.minute)
    except:
        return None


def to_dual_channel(brightness: int, cct_mode: str, blend_ratio: float = 0.5):
    brightness = max(0, min(100, int(brightness)))

    if cct_mode == "warm":
        warm_pct, cool_pct = 1.0, 0.0
    elif cct_mode == "cool":
        warm_pct, cool_pct = 0.0, 1.0
    else:
        blend_ratio = max(0.0, min(1.0, float(blend_ratio)))
        warm_pct = 1.0 - blend_ratio
        cool_pct = blend_ratio

    scale = brightness / 100.0
    warm_pwm = int(round(255 * warm_pct * scale))
    cool_pwm = int(round(255 * cool_pct * scale))

    return warm_pwm, cool_pwm


# ==============================
# 🤖 ML 수면 품질 예측 함수
# ==============================
def predict_quality(init, pattern, sleep):
    if ML_MODEL is None:
        return float(pattern.get("quality", 7))

    age = int(init.get("age", 25))
    goal = float(pattern.get("goal", 7))
    satisfaction = float(pattern.get("satisfaction", 5))
    wakeCount = float(pattern.get("wakeCount", 0))

    X = np.array([[age, 1, 3, goal, max(1, 6 - satisfaction),
                   3, 65, 6000, 2]])

    try:
        pred = float(ML_MODEL.predict(X)[0])
        return max(1.0, min(10.0, pred))
    except:
        return float(pattern.get("quality", 7))


# ==============================
# 💡 AI + 규칙 기반 조명 추천 엔진
# ==============================
def build_light_plan(init: dict, pattern: dict, sleep: dict):
    now = datetime.now()

    wake_dt = _hhmm_to_dt_today(pattern.get("wake", ""))
    sleep_dt = _hhmm_to_dt_today(pattern.get("sleep", ""))

    goal = float(pattern.get("goal", 7))
    satisfaction = float(pattern.get("satisfaction", 5))
    morningFeel = pattern.get("morningFeel", "보통")
    wakeCount = int(pattern.get("wakeCount", 0))
    last_quality = float(pattern.get("quality", 7))

    ml_pred = predict_quality(init, pattern, sleep)

    # 기본값
    cct_mode = "blend"
    blend_ratio = 0.6
    brightness = 60
    phase = "daytime"

    # 아침 부스트
    if wake_dt and wake_dt <= now <= (wake_dt + timedelta(minutes=90)):
        cct_mode = "cool"
        blend_ratio = 1.0
        brightness = 90
        phase = "morning_boost"

    # 취침 2시간 전
    elif sleep_dt and (sleep_dt - timedelta(minutes=120)) <= now <= sleep_dt:
        mins_to_sleep = max(0, int((sleep_dt - now).total_seconds() // 60))
        brightness = int(15 + (mins_to_sleep / 120) * (40 - 15))
        brightness = max(15, min(40, brightness))
        cct_mode = "warm"
        blend_ratio = 0.0
        phase = "evening_winddown"

    # 사용자 상태 보정
    if last_quality <= 5 or wakeCount >= 2 or satisfaction <= 4 or morningFeel == "나쁨":
        brightness = max(20, brightness - 10)
        if phase == "evening_winddown":
            brightness = max(10, brightness - 10)
        blend_ratio = max(0.3, blend_ratio - 0.1)

    # ML 예측 기반 보정
    if ml_pred <= 6:
        brightness = max(20, brightness - 5)
        if phase == "evening_winddown":
            cct_mode = "warm"
            blend_ratio = 0.0

    warm_pwm, cool_pwm = to_dual_channel(brightness, cct_mode, blend_ratio)

    return {
        "power": True,
        "phase": phase,
        "brightness_pct": brightness,
        "cct_mode": cct_mode,
        "blend_ratio": round(blend_ratio, 2),
        "warm_pwm": warm_pwm,
        "cool_pwm": cool_pwm,
        "ml_pred": ml_pred,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# ==============================
# 📍 초기 데이터 저장
# ==============================
@app.route("/save_init", methods=["POST"])
def save_init():
    try:
        data = request.get_json(force=True)
        data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet("InitData")

        sheet.append_row([data.get(k, "") for k in data.keys()])

        return jsonify({"status": "success", "message": "Init data saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 📊 Sleep 데이터 수집
# ==============================
@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet("PersonalSleep")

        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df.to_csv(SLEEP_FILE, index=False)

        return jsonify({"status": "success", "rows": len(data), "latest": data[-1]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 💤 생활 패턴 저장 + AI 조명 추천
# ==============================
@app.route("/save_pattern", methods=["POST"])
def save_pattern():
    try:
        data = request.get_json(force=True)
        data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        df = pd.DataFrame([data])
        if not os.path.exists(DATA_FILE):
            df.to_csv(DATA_FILE, index=False)
        else:
            df.to_csv(DATA_FILE, mode="a", header=False, index=False)

        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        ws_init = client.open_by_key(SHEET_ID).worksheet("InitData")
        ws_pat = client.open_by_key(SHEET_ID).worksheet("Pattern")
        ws_sleep = client.open_by_key(SHEET_ID).worksheet("PersonalSleep")

        headers = list(data.keys())
        ws_pat.append_row([data[k] for k in headers])

        init = _last_row_as_dict(ws_init)
        sleep = _last_row_as_dict(ws_sleep)

        plan = build_light_plan(init, data, sleep)

        return jsonify({
            "status": "success",
            "message": "Pattern saved and light plan generated",
            "light_plan": plan
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🔆 실시간 조명 요청(GET)
# ==============================
@app.route("/light_plan", methods=["GET"])
def light_plan():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)

        ws_init = client.open_by_key(SHEET_ID).worksheet("InitData")
        ws_pat = client.open_by_key(SHEET_ID).worksheet("Pattern")
        ws_sleep = client.open_by_key(SHEET_ID).worksheet("PersonalSleep")

        init = _last_row_as_dict(ws_init)
        pat = _last_row_as_dict(ws_pat)
        slp = _last_row_as_dict(ws_sleep)

        plan = build_light_plan(init, pat, slp)

        return jsonify({"status": "ok", "light_plan": plan})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🚀 서버 실행
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
