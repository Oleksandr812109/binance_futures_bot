import logging
import pandas as pd
import numpy as np
from binance.client import Client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            df['Open'] = df['Open'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['Volume'] = df['Volume'].astype(float)
            df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
            df['Close time'] = pd.to_datetime(df['Close time'], unit='ms')
            logging.info(f"Fetched {len(df)} klines for {symbol} ({interval}) from Binance.")
            return df
        except Exception as e:
            logging.error(f"Error fetching Binance data for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_sma(self, data: pd.DataFrame, period: int = 20, column: str = "Close") -> pd.Series:
        sma = data[column].rolling(window=period).mean()
        logging.info(f"Calculated {period}-period SMA.")
        return sma

    def calculate_ema(self, data: pd.DataFrame, period: int = 20, column: str = "Close") -> pd.Series:
        ema = data[column].ewm(span=period, adjust=False).mean()
        logging.info(f"Calculated {period}-period EMA.")
        return ema

    def calculate_rsi(self, data: pd.DataFrame, period: int = 14, column: str = "Close") -> pd.Series:
        delta = data[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        logging.info(f"Calculated {period}-period RSI.")
        return rsi

    def calculate_macd(self, data: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, column: str = "Close") -> pd.DataFrame:
        fast_ema = self.calculate_ema(data, fast_period, column)
        slow_ema = self.calculate_ema(data, slow_period, column)
        macd = fast_ema - slow_ema
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        result = data.copy()
        result["MACD"] = macd
        result["Signal"] = signal
        result["Histogram"] = histogram
        logging.info("Calculated MACD, Signal, and Histogram.")
        return result

    def calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        high = data["High"]
        low = data["Low"]
        close = data["Close"]
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr1 = abs(high - low)
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.rolling(window=period).mean()
        logging.info(f"Calculated {period}-period ADX.")
        return adx

    def calculate_bollinger_bands(self, data: pd.DataFrame, period: int = 20, column: str = "Close") -> (pd.Series, pd.Series):
        sma = self.calculate_sma(data, period, column)
        std = data[column].rolling(window=period).std()
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        logging.info(f"Calculated {period}-period Bollinger Bands.")
        return upper_band, lower_band

    def generate_optimized_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # EMA Short/Long
        data["EMA_Short"] = self.calculate_ema(data, 12)
        data["EMA_Long"] = self.calculate_ema(data, 26)
        # RSI
        data["RSI"] = self.calculate_rsi(data, 14)
        # ADX
        data["ADX"] = self.calculate_adx(data, 14)
        # Bollinger Bands
        data["Upper_Band"], data["Lower_Band"] = self.calculate_bollinger_bands(data, 20)

        # Можна додати стандартні індикатори для backward compatibility
        data["SMA20"] = self.calculate_sma(data, 20)
        data["EMA20"] = self.calculate_ema(data, 20)
        data["RSI14"] = self.calculate_rsi(data, 14)
        macd_df = self.calculate_macd(data)
        data["MACD"] = macd_df["MACD"]
        data["Signal"] = macd_df["Signal"]
        data["Histogram"] = macd_df["Histogram"]

        # Проста логіка для прикладу
        data["SignalFlag"] = 0
        data.loc[(data["EMA20"] > data["SMA20"]) & (data["RSI14"] < 30), "SignalFlag"] = 1
        data.loc[(data["EMA20"] < data["SMA20"]) & (data["RSI14"] > 70), "SignalFlag"] = -1

        logging.info("Generated optimized trading signals with all required columns.")
        return data
