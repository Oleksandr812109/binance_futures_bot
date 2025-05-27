import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import joblib

# --- Налаштування ---
DATA_PATH = "ai_models/training_data.csv"  # Змініть шлях до вашого CSV з історичними даними
MODEL_DIR = "ai_models"
MODEL_PATH = os.path.join(MODEL_DIR, "default_rf.pkl")
FEATURES = ["EMA_Short", "EMA_Long", "RSI", "ADX", "Upper_Band", "Lower_Band"]
TARGET = "signal"  # Ваш стовпець з міткою (1 - Buy, -1 - Sell, 0 - Hold)

# --- Завантаження та перевірка даних ---
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"Файл з даними не знайдено: {DATA_PATH}")

df = pd.read_csv(DATA_PATH)
print(f"Дані завантажено: {df.shape} рядків")

missing_features = [f for f in FEATURES if f not in df.columns]
if missing_features:
    raise ValueError(f"Відсутні стовпці: {missing_features}")

if TARGET not in df.columns:
    raise ValueError(f"Відсутній цільовий стовпець '{TARGET}' у даних.")

# --- Формування вибірки ---
X = df[FEATURES].fillna(0)
y = df[TARGET]

# --- Розбиття на train/test ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- Створення та навчання моделі ---
model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, class_weight="balanced")
model.fit(X_train, y_train)

# --- Оцінка якості моделі ---
y_pred = model.predict(X_test)
print("\n--- Класифікаційний звіт на тестовій вибірці ---")
print(classification_report(y_test, y_pred))
print("Матриця невідповідностей:\n", confusion_matrix(y_test, y_pred))
print("Точність: {:.2f}%".format(accuracy_score(y_test, y_pred) * 100))

# --- Крос-валідація ---
cv_scores = cross_val_score(model, X, y, cv=2)
print("Середня точність (5-fold CV): {:.2f}%".format(cv_scores.mean() * 100))

# --- Збереження моделі ---
os.makedirs(MODEL_DIR, exist_ok=True)
joblib.dump(model, MODEL_PATH)
print(f"Модель збережено у: {MODEL_PATH}")
