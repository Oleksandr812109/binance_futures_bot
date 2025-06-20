import numpy as np
import pickle
import logging
from tensorflow.keras.models import load_model
from ml.config import (
    SCALER_PATH, MODEL_PATH, FEATURE_NAMES,
    SL_MULTIPLIER_BUY, TP_MULTIPLIER_BUY,
    SL_MULTIPLIER_SELL, TP_MULTIPLIER_SELL,
    Decision
)

logger = logging.getLogger("AISignalGenerator")

class AISignalGenerator:
    """
    Генератор AI-сигналів для торгового бота.
    Завантажує модель і скейлер, приймає рішення на основі фічей.
    """

    def __init__(self):
        self.scaler = None
        self.model = None
        self.feature_names = FEATURE_NAMES

        # Завантаження scaler з обробкою помилок
        try:
            with open(SCALER_PATH, "rb") as f:
                self.scaler = pickle.load(f)
            logger.info(f"Scaler loaded successfully from {SCALER_PATH}")
        except Exception as e:
            logger.error(f"Failed to load scaler from {SCALER_PATH}: {e}")

        # Завантаження моделі з обробкою помилок
        try:
            self.model = load_model("ml/models/model.keras")
            logger.info(f"Model loaded successfully from ml/models/model.keras")
        except Exception as e:
            logger.error(f"Failed to load model from ml/models/model.keras: {e}")


    def extract_features(self, df):
        """
        Витягує фічі з DataFrame для моделі.
        Перевіряє, чи DataFrame не порожній і містить потрібні стовпці.
        :param df: pandas.DataFrame
        :return: dict або None
        """
        if df is None or df.empty:
            logger.warning("Input DataFrame is empty or None.")
            return None
        missing = [col for col in self.feature_names if col not in df.columns]
        if missing:
            logger.error(f"Missing columns in DataFrame: {missing}")
            return None
        row = df.iloc[-1]
        features = {key: row.get(key, 0.0) for key in self.feature_names}
        if not np.isfinite(features.get("close", np.nan)):
            logger.error("Feature 'close' is missing or non-numeric.")
            return None
        return features

    def predict(self, features):
        """
        Приймає dict фічей, повертає (Decision, price_info).
        :param features: dict
        :return: (Decision, dict) або (Decision.HOLD, {})
        """
        if self.model is None or self.scaler is None:
            logger.error("Model or scaler not loaded.")
            return Decision.HOLD, {}

        if features is None:
            logger.warning("No features provided for prediction.")
            return Decision.HOLD, {}

        try:
            X = np.array([[features[name] for name in self.feature_names]])
            X_scaled = self.scaler.transform(X)
            pred = self.model.predict(X_scaled)
            cls = np.argmax(pred, axis=1)[0]
            if cls == Decision.BUY.value:
                decision = Decision.BUY
            elif cls == Decision.SELL.value:
                decision = Decision.SELL
            else:
                decision = Decision.HOLD

            entry = features["close"]
            if decision == Decision.BUY:
                stop_loss = entry * SL_MULTIPLIER_BUY
                take_profit = entry * TP_MULTIPLIER_BUY
            elif decision == Decision.SELL:
                stop_loss = entry * SL_MULTIPLIER_SELL
                take_profit = entry * TP_MULTIPLIER_SELL
            else:
                stop_loss = take_profit = None

            price_info = {
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }
            logger.info(f"AI decision: {decision.name} | entry: {entry}, SL: {stop_loss}, TP: {take_profit}")
            return decision, price_info
        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return Decision.HOLD, {}

    def partial_fit(self, features, target):
        """
        Онлайн-навчання для sklearn моделей.
        Для Keras: потрiбен збір даних і періодичне перенавчання.
        """
        logger.info("partial_fit is not implemented for Keras models. To update the model, aggregate new data and retrain periodically.")
        pass
