import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ========================
# 구글 시트 설정
# ========================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "credentials.json"  # 서비스 계정 키 파일
SHEET_ID = "1s5BKkultYwSUrEQxOajsWZvf64g0538kMKdii0WivTY"     # 구글 시트 이름

# ========================
# 구글 시트 연결
# ========================
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# ========================
# 데이터 읽기
# ========================
data = sheet.get_all_records()  # 모든 행을 [{열이름: 값}, ...] 형태로 반환

print("✅ 전체 행 수:", len(data))
if len(data) > 0:
    print("\n📋 최신 데이터 (마지막 행):")
    print(json.dumps(data[-1], indent=2, ensure_ascii=False))
else:
    print("⚠️ 시트가 비어있어요.")
