import numpy as np
import pandas as pd
import logging
from enum import Enum

class Decision(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0

class AISignalGenerator:
    """
    Генерує торгові сигнали на основі ML-моделі та rule-based фільтрації.
    Забезпечує масштабування ознак, захист від некоректних даних, налаштовувані пороги та чисте логування.
    """

    def __init__(self, model, scaler, confidence_threshold=0.65, volatility_threshold=0.01):
        """
        :param model: Навчена ML-модель, яка має метод predict_proba і атрибут classes_.
        :param scaler: Навчений скейлер (наприклад, StandardScaler), обов'язково з fit на тренувальних даних.
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
        Використовує лише transform, а не fit_transform!
        Додає додаткові ознаки, робить захист від відсутніх колонок.
        """
        if not hasattr(self.scaler, 'scale_'):
            logging.warning("Scaler не навчений! Перед використанням виконайте scaler.fit(...) на тренувальних даних.")
        if df.empty:
            logging.warning("extract_features: DataFrame порожній.")
            return np.array([])

        df = df.copy()
        # Базові та нові features
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
        """
        Визначає індекси класів у self.model.classes_ для BUY, SELL, HOLD.
        """
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
        """
        Простий rule-based фільтр: ціна вище EMA20 і волатильність достатня.
        """
        for col in ['close', 'ema_20', 'volatility']:
            if col not in row:
                logging.warning(f"rule_based_filter: Відсутня колонка {col} у вхідному рядку.")
                return False
        price_above_ema = row['close'] > row['ema_20']
        volatility_ok = row['volatility'] > self.volatility_threshold
        if not volatility_ok:
            logging.info(f"rule_based_filter: Волатильність {row['volatility']:.4f} нижче порогу {self.volatility_threshold}")
        return price_above_ema and volatility_ok

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Повертає рішення моделі (BUY/SELL/HOLD) з урахуванням rule-based фільтра і впевненості.
        :param df: DataFrame з історією для однієї пари
        :return: dict(signal=Decision, prob_buy, prob_sell, prob_hold, rule_ok)
        """
        if df.empty:
            logging.warning("predict: DataFrame порожній, повертаю HOLD.")
            return {'signal': Decision.HOLD, 'prob_buy': 0, 'prob_sell': 0, 'prob_hold': 1, 'rule_ok': False}

        features_array = self.extract_features(df)
        if features_array.size == 0:
            logging.warning("predict: features_array порожній, повертаю HOLD.")
            return {'signal': Decision.HOLD, 'prob_buy': 0, 'prob_sell': 0, 'prob_hold': 1, 'rule_ok': False}

        features = features_array[-1].reshape(1, -1)
        try:
            probs = self.model.predict_proba(features)[0]
        except Exception as e:
            logging.error(f"predict: Помилка predict_proba: {e}")
            return {'signal': Decision.HOLD, 'prob_buy': 0, 'prob_sell': 0, 'prob_hold': 1, 'rule_ok': False}

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

        logging.info(f"predict: signal={signal.name}, prob_buy={prob_buy:.2f}, prob_sell={prob_sell:.2f}, prob_hold={prob_hold:.2f}, rule_ok={rule_ok}")

        return {
            'signal': signal,
            'prob_buy': prob_buy,
            'prob_sell': prob_sell,
            'prob_hold': prob_hold,
            'rule_ok': rule_ok
        }
