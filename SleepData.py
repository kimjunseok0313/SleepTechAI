from flask import Flask, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os

app = Flask(__name__)

# ========================
# 구글 시트 설정
# ========================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "credentials.json"
SHEET_ID = "1s5BKkultYwSUrEQxOajsWZvf64g0538kMKdii0WivTY"

# ========================
# 구글 시트에서 데이터 읽기
# ========================
def get_sheet_data():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    data = sheet.get_all_records()
    return data

# ========================
# Flask 라우트
# ========================
@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        data = get_sheet_data()
        if not data:
            return jsonify({"error": "No data in sheet"}), 404

        # pandas DataFrame 변환 후 CSV 저장
        df = pd.DataFrame(data)
        csv_path = os.path.join(os.getcwd(), "sleep_data.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        return jsonify({
            "message": "Data fetched and saved as CSV",
            "rows": len(data),
            "latest": data[-1],
            "csv_path": csv_path
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# 서버 실행
# ========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
