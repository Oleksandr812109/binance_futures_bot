import numpy as np
import pandas as pd
import logging
from enum import Enum

# --- Константи для price_info ---
SL_MULTIPLIER_BUY = 0.99      # 1% stop-loss для LONG
TP_MULTIPLIER_BUY = 1.015     # 1.5% take-profit для LONG
SL_MULTIPLIER_SELL = 1.01     # 1% stop-loss для SHORT
TP_MULTIPLIER_SELL = 0.985    # 1.5% take-profit для SHORT

class Decision(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0

class AISignalGenerator:
    """
    Генерує торгові сигнали на основі ML-моделі та rule-based фільтрації.
    Повертає рішення та price_info (entry, stop_loss, take_profit).
    """

    def __init__(self, model, scaler, confidence_threshold=0.65, volatility_threshold=0.01):
        """
        :param model: Навчена ML-модель (наприклад, sklearn), має predict_proba, partial_fit і classes_.
        :param scaler: Навчений скейлер (StandardScaler), fit на тренувальних даних.
        :param confidence_threshold: Поріг впевненості для відкриття позиції (0...1).
        :param volatility_threshold: Мінімальна волатильність для rule-based фільтрації.
        """
        self.model = model
        self.scaler = scaler
        self.confidence_threshold = confidence_threshold
        self.volatility_threshold = volatility_threshold

    def extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Перетворює DataFrame в масив ознак для моделі.
        """
        if not hasattr(self.scaler, 'scale_'):
            logging.warning("Scaler не навчений! Перед використанням виконайте scaler.fit(...) на тренувальних даних.")
        if df is None or df.empty:
            logging.warning("extract_features: DataFrame порожній.")
            return np.array([])

        df = df.copy()
        for col in ['close', 'volume', 'rsi', 'macd', 'macdsignal', 'macdhist', 'ema_20', 'ema_50', 'atr']:
            if col not in df.columns:
                df[col] = 0.0

        df['hour'] = pd.to_datetime(df['Open time']).dt.hour if 'Open time' in df else 0
        df['price_change'] = df['close'].pct_change().fillna(0)
        df['rsi_delta'] = df['rsi'].diff().fillna(0)
        df['macdhist_delta'] = df['macdhist'].diff().fillna(0)
        df['volatility'] = np.where(df['close'] != 0, df['atr'] / df['close'], 0)

        features = [
            'close', 'volume', 'rsi', 'macd', 'macdsignal', 'macdhist',
            'ema_20', 'ema_50', 'atr', 'hour', 'price_change',
            'rsi_delta', 'macdhist_delta', 'volatility'
        ]
        features_df = df[features].fillna(0)
        try:
            features_array = self.scaler.transform(features_df.values)
        except Exception as e:
            logging.error(f"extract_features: Помилка масштабування: {e}")
            return np.array([])
        return features_array

    def _map_class_indices(self):
        idx = {c: None for c in [Decision.BUY.value, Decision.SELL.value, Decision.HOLD.value]}
        for i, c in enumerate(self.model.classes_):
            if c == 1:
                idx[Decision.BUY.value] = i
            elif c == -1:
                idx[Decision.SELL.value] = i
            elif c == 0:
                idx[Decision.HOLD.value] = i
        return idx

    def rule_based_filter(self, row: pd.Series) -> bool:
        for col in ['close', 'ema_20', 'volatility']:
            if col not in row:
                logging.warning(f"rule_based_filter: Відсутня колонка {col} у вхідному рядку.")
                return False
        price_above_ema = row['close'] > row['ema_20']
        volatility_ok = row['volatility'] > self.volatility_threshold
        if not volatility_ok:
            logging.info(f"rule_based_filter: Волатильність {row['volatility']:.4f} нижче порогу {self.volatility_threshold}")
        return price_above_ema and volatility_ok

    def predict(self, df: pd.DataFrame):
        """
        Повертає (Decision, price_info), де price_info - dict(entry, stop_loss, take_profit).
        """
        if df is None or df.empty:
            logging.warning("predict: DataFrame порожній, повертаю HOLD.")
            return Decision.HOLD, {}

        features_array = self.extract_features(df)
        if features_array.size == 0:
            logging.warning("predict: features_array порожній, повертаю HOLD.")
            return Decision.HOLD, {}

        features = features_array[-1].reshape(1, -1)
        try:
            probs = self.model.predict_proba(features)[0]
        except Exception as e:
            logging.error(f"predict: Помилка predict_proba: {e}")
            return Decision.HOLD, {}

        idx = self._map_class_indices()
        prob_buy = probs[idx[Decision.BUY.value]] if idx[Decision.BUY.value] is not None else 0
        prob_sell = probs[idx[Decision.SELL.value]] if idx[Decision.SELL.value] is not None else 0
        prob_hold = probs[idx[Decision.HOLD.value]] if idx[Decision.HOLD.value] is not None else 0

        # ML decision
        if prob_buy > self.confidence_threshold and prob_buy > prob_sell:
            ml_decision = Decision.BUY
        elif prob_sell > self.confidence_threshold and prob_sell > prob_buy:
            ml_decision = Decision.SELL
        else:
            ml_decision = Decision.HOLD

        last_row = df.iloc[-1]
        rule_ok = self.rule_based_filter(last_row)

        if rule_ok:
            signal = ml_decision
        else:
            signal = Decision.HOLD
            logging.info("predict: Rule-based фільтр відхилив сигнал моделі.")

        # --- Формування price_info ---
        entry = float(last_row['close'])
        if signal == Decision.BUY:
            stop_loss = entry * SL_MULTIPLIER_BUY
            take_profit = entry * TP_MULTIPLIER_BUY
        elif signal == Decision.SELL:
            stop_loss = entry * SL_MULTIPLIER_SELL
            take_profit = entry * TP_MULTIPLIER_SELL
        else:
            stop_loss = None
            take_profit = None

        price_info = {
            "entry": entry if signal != Decision.HOLD else None,
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }

        logging.info(
            f"predict: signal={signal.name}, prob_buy={prob_buy:.2f}, prob_sell={prob_sell:.2f}, prob_hold={prob_hold:.2f}, rule_ok={rule_ok}, "
            f"entry={price_info['entry']} SL={price_info['stop_loss']} TP={price_info['take_profit']}")

        return signal, price_info

    def partial_fit(self, X, y):
        """
        Навчання моделі онлайн для підтримки TradingLogic.learn_ai.
        X - ознаки (масив або DataFrame), y - ціль.
        """
        if hasattr(self.model, 'partial_fit'):
            return self.model.partial_fit(X, y)
        else:
            raise NotImplementedError("Модель не підтримує partial_fit")

