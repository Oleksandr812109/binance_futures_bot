import logging
import pandas as pd
import numpy as np
from binance.client import Client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Додаємо словник параметрів для різних пар ===
INDICATOR_PARAMS = {
    "BTCUSDT": {"ema_short": 12, "ema_long": 26, "rsi": 14, "sma": 20, "bb": 20},
    "ETHUSDT": {"ema_short": 10, "ema_long": 21, "rsi": 10, "sma": 20, "bb": 20},
    "SOLUSDT": {"ema_short": 8, "ema_long": 18, "rsi": 8, "sma": 15, "bb": 15},
    "ADAUSDT": {"ema_short": 7, "ema_long": 15, "rsi": 7, "sma": 14, "bb": 14},
    # Додайте інші пари за потреби
}
DEFAULT_PARAMS = {"ema_short": 12, "ema_long": 26, "rsi": 14, "sma": 20, "bb": 20}

def get_params_for_symbol(symbol):
    return INDICATOR_PARAMS.get(symbol, DEFAULT_PARAMS)

class TechnicalAnalysis:
    def __init__(self, client: Client):
        self.client = client

    def fetch_binance_data(self, symbol: str, interval: str = '1h', limit: int = 500, testnet: bool = True) -> pd.DataFrame:
        try:
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(klines, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote asset volume', 'Number of trades',
                'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
            ])
            df.columns = [c.lower() for c in df.columns]
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            df['open time'] = pd.to_datetime(df['open time'], unit='ms')
            df['close time'] = pd.to_datetime(df['close time'], unit='ms')
            logging.info(f"Fetched {len(df)} klines for {symbol} ({interval}) from Binance.")
            return df
        except Exception as e:
            logging.error(f"Error fetching Binance data for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_sma(self, data: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
        sma = data[column].rolling(window=period).mean()
        logging.info(f"Calculated {period}-period SMA.")
        return sma

    def calculate_ema(self, data: pd.DataFrame, period: int = 20, column: str = "close") -> pd.Series:
        ema = data[column].ewm(span=period, adjust=False).mean()
        logging.info(f"Calculated {period}-period EMA.")
        return ema

    def calculate_rsi(self, data: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
        delta = data[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        logging.info(f"Calculated {period}-period RSI.")
        return rsi

    def calculate_macd(self, data: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, column: str = "close") -> pd.DataFrame:
        fast_ema = self.calculate_ema(data, fast_period, column)
        slow_ema = self.calculate_ema(data, slow_period, column)
        macd = fast_ema - slow_ema
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        result = data.copy()
        result["macd"] = macd
        result["signal"] = signal
        result["histogram"] = histogram
        logging.info("Calculated MACD, signal, and histogram.")
        return result

    def calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        high = data["high"]
        low = data["low"]
        close = data["close"]
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr1 = abs(high - low)
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        data["atr"] = atr  # <--- додано для доступу до ATR в інших функціях

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.rolling(window=period).mean()
        logging.info(f"Calculated {period}-period ADX.")
        return adx

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        high = data["high"]
        low = data["low"]
        close = data["close"]
        tr1 = abs(high - low)
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        logging.info(f"Calculated {period}-period ATR.")
        return atr

    def calculate_bollinger_bands(self, data: pd.DataFrame, period: int = 20, column: str = "close") -> (pd.Series, pd.Series):
        sma = self.calculate_sma(data, period, column)
        std = data[column].rolling(window=period).std()
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        logging.info(f"Calculated {period}-period Bollinger Bands.")
        return upper_band, lower_band

    def generate_optimized_signals(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        # --- Отримуємо параметри для поточної пари ---
        params = get_params_for_symbol(symbol)
        # EMA Short/Long
        data["ema_short"] = self.calculate_ema(data, params["ema_short"])
        data["ema_long"] = self.calculate_ema(data, params["ema_long"])
        # RSI
        data["rsi"] = self.calculate_rsi(data, params["rsi"])
        # ADX (залишаємо дефолтний період, можна теж зробити кастомним)
        data["adx"] = self.calculate_adx(data, 14)
        # Bollinger Bands
        data["upper_band"], data["lower_band"] = self.calculate_bollinger_bands(data, params["bb"])
        # SMA для сигналу
        data["sma20"] = self.calculate_sma(data, params["sma"])
        # Стандартні EMA20 і RSI14 для сумісності, якщо треба
        data["ema20"] = self.calculate_ema(data, 20)
        data["rsi14"] = self.calculate_rsi(data, 14)
        # MACD (залишаємо дефолтні параметри, якщо треба — аналогічно можна кастомізувати)
        macd_df = self.calculate_macd(data)
        data["macd"] = macd_df["macd"]
        data["signal"] = macd_df["signal"]
        data["histogram"] = macd_df["histogram"]

        # Проста логіка для прикладу
        data["signalflag"] = 0
        data.loc[(data["ema20"] > data["sma20"]) & (data["rsi14"] < 30), "signalflag"] = 1
        data.loc[(data["ema20"] < data["sma20"]) & (data["rsi14"] > 70), "signalflag"] = -1

        # Додаємо стовпець Stop_Loss для коректної роботи головного циклу
        data["stop_loss"] = np.where(
            data["signalflag"] == 1, data["close"] * 0.99,
            np.where(data["signalflag"] == -1, data["close"] * 1.01, np.nan)
        )

        # Додаємо volatility для ML
        if "atr" not in data.columns:
            data["atr"] = self.calculate_atr(data)
        data["volatility"] = np.where(data["close"] != 0, data["atr"] / data["close"], 0)

        # === Діагностика NaN для головних колонок ===
        required_cols = ['ema_short', 'ema_long', 'rsi', 'adx', 'upper_band', 'lower_band']
        print(f"NaN count in required columns for {symbol}:")
        print(data[required_cols].isna().sum())
        print("Rows with NaN in required columns:")
        print(data[data[required_cols].isna().any(axis=1)])
        # === /Діагностика ===

        # Перевіряємо лише останній рядок!
        last_row = data.iloc[-1]
        if last_row[required_cols].isna().any():
            logging.error(f"Missing or NaN in columns: {required_cols} for {symbol}. Skipping.")
            return None

        # Додано перевірку на наявність NaN у Close та Stop_Loss (за бажанням, можна залишити)
        print(data[["close", "stop_loss"]].isna().sum())  # покаже кількість NaN у кожній колонці
        print(data[data[["close", "stop_loss"]].isna().any(axis=1)])  # покаже рядки з NaN

        # Ось сюди додай фільтрацію:
        data = data.dropna(subset=["close", "stop_loss"])

        logging.info("Generated optimized trading signals with all required columns.")
        return data
