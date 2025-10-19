from flask import Flask, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# 구글 시트 인증
SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "credentials.json"  # 다운로드한 파일
SHEET_NAME = "SleepTechData"     # 시트 이름

@app.route("/analyze", methods=["GET"])
def analyze():
    try:
        # 인증 후 연결
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1

        # 데이터 읽기
        data = sheet.get_all_records()
        latest = data[-1] if data else {}

        # 간단한 테스트 응답
        result = {
            "latest_row": latest,
            "count": len(data)
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
