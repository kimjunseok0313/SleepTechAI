from flask import Flask, jsonify, request
import pandas as pd
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ==============================
# 🔧 Google Sheets 설정
# ==============================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "credentials.json"  # 반드시 같은 폴더에 위치
SHEET_ID = "1s5BKkultYwSUrEQxOajsWZvf64g0538kMKdii0WivTY"

# ==============================
# 📁 CSV 파일 설정
# ==============================
DATA_FILE = "user_patterns.csv"
SLEEP_FILE = "sleep_data.csv"


# ==============================
# 📊 /analyze - Google Sheet 읽고 CSV로 저장
# ==============================
@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        # 인증
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1

        # Google Sheets → CSV
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
        print("❌ Google Sheets fetch error:", e)
        return jsonify({"error": str(e)}), 500


# ==============================
# 💤 /save_pattern - ESP32에서 전송된 생활 패턴 저장
# ==============================
@app.route("/save_pattern", methods=["POST"])
def save_pattern():
    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # 현재 시각 추가
        data["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # CSV에 저장
        df = pd.DataFrame([data])
        if not os.path.exists(DATA_FILE):
            df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(DATA_FILE, mode="a", header=False, index=False, encoding="utf-8-sig")

        print(f"✅ 데이터 저장됨: {data}")

        # ESP32 응답
        return jsonify({
            "status": "success",
            "message": "Data received and saved",
            "data": data
        })

    except Exception as e:
        print("❌ Save error:", e)
        return jsonify({"error": str(e)}), 500


# ==============================
# 🚀 서버 실행
# ==============================
if __name__ == "__main__":
    # Flask 외부 접속 허용 (ESP32 등)
    app.run(host="0.0.0.0", port=5000, debug=False)
