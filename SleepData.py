from flask import Flask, jsonify, request
import pandas as pd
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ==============================
# 🔐 Google Sheets 설정
# ==============================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
# Render Secret Files에 저장된 credentials.json 경로
CREDS_FILE = "/etc/secrets/credentials.json"

# SleepTech 프로젝트용 Google Sheet ID
SHEET_ID = "1s5BKkultYwSUrEQxOajsWZvf64g0538kMKdii0WivTY"

# ==============================
# 💾 CSV 파일 설정 (Render 내부 저장용)
# ==============================
DATA_FILE = "user_patterns.csv"
SLEEP_FILE = "sleep_data.csv"


# ==============================
# 📊 /analyze - Google Sheets → CSV 저장
# ==============================
@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        # Google 인증
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1

        # 시트에서 모든 데이터 가져오기
        data = sheet.get_all_records()
        if not data:
            return jsonify({"error": "No data found"}), 404

        # CSV로 저장 (Render의 임시 저장소)
        df = pd.DataFrame(data)
        df.to_csv(SLEEP_FILE, index=False, encoding="utf-8-sig")

        print(f"✅ Google Sheets에서 {len(data)}행 불러옴 및 CSV로 저장 완료")

        return jsonify({
            "message": "Sleep data fetched and saved successfully",
            "rows": len(data),
            "latest": data[-1]
        })

    except Exception as e:
        print("❌ Google Sheets fetch error:", e)
        return jsonify({"error": str(e)}), 500


# ==============================
# 💤 /save_pattern - ESP32 → 생활패턴 저장
# ==============================
@app.route("/save_pattern", methods=["POST"])
def save_pattern():
    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # 현재 시각 추가
        data["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # CSV로 로컬 저장 (Render 임시 공간)
        df = pd.DataFrame([data])
        if not os.path.exists(DATA_FILE):
            df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(DATA_FILE, mode="a", header=False, index=False, encoding="utf-8-sig")

        print(f"✅ 데이터 저장됨 (CSV): {data}")

        # ==============================
        # Google Sheets에도 동시 저장 (영구 백업)
        # ==============================
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet2

        # key 순서에 맞게 정렬해서 append
        headers = list(data.keys())
        row = [data[k] for k in headers]
        sheet.append_row(row)

        print("✅ Google Sheets에도 데이터 백업 완료")

        # ESP32 응답
        return jsonify({
            "status": "success",
            "message": "Data received, saved, and backed up to Google Sheets",
            "data": data
        })

    except Exception as e:
        print("❌ Save error:", e)
        return jsonify({"error": str(e)}), 500


# ==============================
# 🚀 서버 실행
# ==============================
if __name__ == "__main__":
    # Flask 외부 접속 허용 (ESP32, 다른 클라이언트 등)
    app.run(host="0.0.0.0", port=5000, debug=False)
