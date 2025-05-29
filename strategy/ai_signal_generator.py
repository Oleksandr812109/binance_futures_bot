import numpy as np
import pandas as pd
import pickle
from river.ensemble import AdaptiveRandomForestClassifier

class AISignalGenerator:
    def __init__(self, model_path="ai_models/default_arf.pkl"):
        self.model_path = model_path
        try:
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)
        except (FileNotFoundError, EOFError):
            self.model = AdaptiveRandomForestClassifier()

    def preprocess(self, df):
        features = ["EMA_Short", "EMA_Long", "RSI", "ADX", "Upper_Band", "Lower_Band"]
        return df[features].fillna(0)
    
    def predict_signals(self, df):
        X = self.preprocess(df)
        preds = []
        for _, row in X.iterrows():
            x_dict = row.to_dict()
            try:
                pred = self.model.predict_one(x_dict)
            except Exception:
                pred = 0
            preds.append(pred if pred is not None else 0)
        df["AI_Signal"] = preds
        return df

    def partial_fit(self, features_dict, target):
        # features_dict — dict із ознаками (наприклад, row.to_dict())
        self.model.learn_one(features_dict, target)
        self.save_model()

    def save_model(self):
        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)

    def load_model(self):
        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)
