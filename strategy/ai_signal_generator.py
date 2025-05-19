import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

class AISignalGenerator:
    def __init__(self, model_path="ai_models/default_rf.pkl"):
        self.model = joblib.load(model_path)

    def preprocess(self, df):
        # Приклад: використовуємо тільки технічні індикатори для передбачення
        features = ["EMA_Short", "EMA_Long", "RSI", "ADX", "Upper_Band", "Lower_Band"]
        return df[features].fillna(0)

    def predict_signals(self, df):
        X = self.preprocess(df)
        preds = self.model.predict(X)
        df["AI_Signal"] = preds
        return df
