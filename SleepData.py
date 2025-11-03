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
CREDS_FILE = "/etc/secrets/credentials.json"  # Render 시크릿 경로
SHEET_ID = "1s5BKkultYwSUrEQxOajsWZvf64g0538kMKdii0WivTY"

# ==============================
# 💾 CSV 파일 설정
# ==============================
DATA_FILE = "user_patterns.csv"
SLEEP_FILE = "sleep_data.csv"

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
    """밝기·색온도 비율 → 2700K·6500K 듀얼채널 PWM 변환"""
    brightness = max(0, min(100, int(brightness)))
    if cct_mode == "warm":
        warm_pct, cool_pct = 1.0, 0.0
    elif cct_mode == "cool":
        warm_pct, cool_pct = 0.0, 1.0
    else:  # blend
        blend_ratio = max(0.0, min(1.0, float(blend_ratio)))
        warm_pct = 1.0 - blend_ratio
        cool_pct = blend_ratio

    scale = brightness / 100.0
    warm_pwm = int(round(255 * warm_pct * scale))
    cool_pwm = int(round(255 * cool_pct * scale))
    return warm_pwm, cool_pwm


# ==============================
# 🧠 ML 모델 로드 (없으면 무시)
# ==============================
try:
    ML_MODEL = joblib.load("sleep_quality_model.pkl")
except:
    ML_MODEL = None


def predict_quality(init, pattern, sleep):
    """남들 데이터로 학습된 모델을 참고해 수면 품질 예측값 반환"""
    if ML_MODEL is None:
        return 6.0  # 기본값

    age = int(init.get("age", 25))
    goal = float(pattern.get("goal", 7))
    satisfaction = float(pattern.get("satisfaction", 5))
    wakeCount = float(pattern.get("wakeCount", 0))

    X = np.array([[age, 1, 3, goal, max(1, 6 - satisfaction),
                   3, 65, 6000, 2]])
    try:
        pred = float(ML_MODEL.predict(X)[0])
        return pred
    except:
        return 6.0


# ==============================
# 💡 규칙 기반 개인화 조명 엔진
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
    ml_quality_pred = predict_quality(init, pattern, sleep)

    # 기본값
    cct_mode = "blend"
    blend_ratio = 0.5
    brightness = 60
    phase = "daytime"

    # 시간대별 규칙
    if wake_dt and now >= wake_dt and now <= (wake_dt + timedelta(minutes=90)):
        cct_mode, blend_ratio, brightness, phase = "cool", 1.0, 90, "morning_boost"
    elif sleep_dt and now >= (sleep_dt - timedelta(minutes=120)) and now <= sleep_dt:
        minutes_to_sleep = max(0, int((sleep_dt - now).total_seconds() // 60))
        brightness = int(15 + (minutes_to_sleep / 120.0) * (40 - 15))
        brightness = max(15, min(40, brightness))
        cct_mode, blend_ratio, phase = "warm", 0.0, "evening_winddown"
    else:
        cct_mode, blend_ratio, brightness, phase = "blend", 0.6, 65, "daytime"

    # 설문 기반 보정
    if last_quality <= 5 or wakeCount >= 2 or satisfaction <= 5 or morningFeel == "나쁨":
        if phase == "evening_winddown":
            brightness = max(10, brightness - 10)
        if cct_mode == "blend":
            blend_ratio = max(0.3, blend_ratio - 0.1)
        brightness = max(30, brightness - 10)

    # ML 예측 기반 보정
    if ml_quality_pred <= 6.0:
        if phase == "evening_winddown":
            brightness = max(10, brightness - 5)
            cct_mode, blend_ratio = "warm", 0.0
        else:
            brightness = max(35, brightness - 5)

    warm_pwm, cool_pwm = to_dual_channel(brightness, cct_mode, blend_ratio)

    return {
        "phase": phase,
        "mode": "AI-RULE",
        "cct_mode": cct_mode,
        "blend_ratio": round(blend_ratio, 2),
        "brightness_pct": brightness,
        "warm_pwm": warm_pwm,
        "cool_pwm": cool_pwm,
        "ml_quality_pred": round(ml_quality_pred, 2),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# ==============================
# 📍 초기설정 저장
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
# 📊 수면 데이터 분석
# ==============================
@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet("PersonalSleep")

        data = sheet.get_all_records()
        if not data:
            return jsonify({"error": "No data found"}), 404

        df = pd.DataFrame(data)
        df.to_csv(SLEEP_FILE, index=False, encoding="utf-8-sig")

        return jsonify({
            "message": "Sleep data fetched and saved successfully",
            "rows": len(data),
            "latest": data[-1]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 💤 생활패턴 저장 (ESP32 → Flask)
# ==============================
@app.route("/save_pattern", methods=["POST"])
def save_pattern():
    try:
        data = request.get_json(force=True)
        data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        df = pd.DataFrame([data])
        if not os.path.exists(DATA_FILE):
            df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(DATA_FILE, mode="a", header=False, index=False, encoding="utf-8-sig")

        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet("Pattern")
        headers = list(data.keys())
        row = [data[k] for k in headers]
        sheet.append_row(row)

        # 🧠 추천 조명 계산
        ws_init = client.open_by_key(SHEET_ID).worksheet("InitData")
        ws_sleep = client.open_by_key(SHEET_ID).worksheet("PersonalSleep")
        init = _last_row_as_dict(ws_init)
        sleep = _last_row_as_dict(ws_sleep)
        plan = build_light_plan(init, data, sleep)

        return jsonify({
            "status": "success",
            "message": "Pattern saved and light plan generated",
            "data": data,
            "light_plan": plan
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🔆 실시간 조명 추천 요청 (ESP32가 GET)
# ==============================
@app.route("/light_plan", methods=["GET"])
def light_plan():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        ws_init = client.open_by_key(SHEET_ID).worksheet("InitData")
        ws_pat = client.open_by_key(SHEET_ID).worksheet("Pattern")
        ws_slp = client.open_by_key(SHEET_ID).worksheet("PersonalSleep")

        init = _last_row_as_dict(ws_init)
        pattern = _last_row_as_dict(ws_pat)
        sleep = _last_row_as_dict(ws_slp)

        plan = build_light_plan(init, pattern, sleep)
        return jsonify({"status": "ok", "plan": plan})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🚀 서버 실행
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
