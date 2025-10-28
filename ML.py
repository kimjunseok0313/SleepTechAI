# Sleep Quality Prediction Model (Base)
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

# 1. 데이터 불러오기
df = pd.read_csv("Sleep_health_and_lifestyle_dataset.csv")

# 2. 필요없는 컬럼 제거 (이름 등)
df = df.drop(columns=['Person ID',])

# 3. 범주형 데이터 인코딩
label_cols = ['Gender', 'Occupation', 'BMI Category']
le = LabelEncoder()
for col in label_cols:
    df[col] = le.fit_transform(df[col])

# 4. 입력(X), 출력(y) 분리
features = [
    'Age', 'Gender', 'Occupation', 'Sleep Duration',
    'Stress Level', 'Physical Activity Level',
    'Heart Rate', 'Daily Steps', 'BMI Category'
]
target = 'Quality of Sleep'

X = df[features]
y = df[target]

# 5. 데이터 분리
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 6. 모델 학습
model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X_train, y_train)

# 7. 예측 및 평가
pred = model.predict(X_test)
print("MAE:", mean_absolute_error(y_test, pred))
print("R²:", r2_score(y_test, pred))

# 8. 모델 저장
joblib.dump(model, "sleep_quality_model.pkl")

# 9. 특성 중요도 출력
import matplotlib.pyplot as plt
import numpy as np

importances = model.feature_importances_
indices = np.argsort(importances)[::-1]

plt.figure(figsize=(8,5))
plt.bar(range(len(features)), importances[indices])
plt.xticks(range(len(features)), [features[i] for i in indices], rotation=45)
plt.title("Feature Importance for Sleep Quality Prediction")
plt.tight_layout()
plt.show()
