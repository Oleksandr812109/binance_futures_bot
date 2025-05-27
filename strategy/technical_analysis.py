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
        """
        Fetch historical kline/candlestick data from Binance.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            interval (str): Kline interval (e.g., '1h').
            limit (int): Number of data points to fetch.
            testnet (bool): Unused, for compatibility.

        Returns:
            pd.DataFrame: DataFrame containing OHLCV data.
        """
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
        """
        Calculate Simple Moving Average (SMA).

        Args:
            data (pd.DataFrame): Input DataFrame.
            period (int): Window for SMA.
            column (str): Column to calculate SMA on.

        Returns:
            pd.Series: SMA values.
        """
        sma = data[column].rolling(window=period).mean()
        logging.info(f"Calculated {period}-period SMA.")
        return sma

    def calculate_ema(self, data: pd.DataFrame, period: int = 20, column: str = "Close") -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA).

        Args:
            data (pd.DataFrame): Input DataFrame.
            period (int): Window for EMA.
            column (str): Column to calculate EMA on.

        Returns:
            pd.Series: EMA values.
        """
        ema = data[column].ewm(span=period, adjust=False).mean()
        logging.info(f"Calculated {period}-period EMA.")
        return ema

    def calculate_rsi(self, data: pd.DataFrame, period: int = 14, column: str = "Close") -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            data (pd.DataFrame): Input DataFrame.
            period (int): RSI lookback.
            column (str): Column to calculate RSI on.

        Returns:
            pd.Series: RSI values.
        """
        delta = data[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        logging.info(f"Calculated {period}-period RSI.")
        return rsi

    def calculate_macd(self, data: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, column: str = "Close") -> pd.DataFrame:
        """
        Calculate MACD indicator.

        Args:
            data (pd.DataFrame): Input DataFrame.
            fast_period (int): Fast EMA period.
            slow_period (int): Slow EMA period.
            signal_period (int): Signal line EMA period.
            column (str): Column to calculate MACD on.

        Returns:
            pd.DataFrame: MACD, Signal, Histogram.
        """
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

    def generate_optimized_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on optimized technical indicator logic.

        Args:
            data (pd.DataFrame): Input OHLCV DataFrame.

        Returns:
            pd.DataFrame: DataFrame with added signal columns.
        """
        data["SMA20"] = self.calculate_sma(data, 20)
        data["EMA20"] = self.calculate_ema(data, 20)
        data["RSI14"] = self.calculate_rsi(data, 14)
        macd_df = self.calculate_macd(data)
        data["MACD"] = macd_df["MACD"]
        data["Signal"] = macd_df["Signal"]
        data["Histogram"] = macd_df["Histogram"]

        # Проста логіка для прикладу: BUY якщо EMA20 > SMA20 і RSI < 30, SELL якщо EMA20 < SMA20 і RSI > 70
        data["SignalFlag"] = 0
        data.loc[(data["EMA20"] > data["SMA20"]) & (data["RSI14"] < 30), "SignalFlag"] = 1
        data.loc[(data["EMA20"] < data["SMA20"]) & (data["RSI14"] > 70), "SignalFlag"] = -1

        logging.info("Generated optimized trading signals.")
        return data

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR).

        Args:
            data (pd.DataFrame): Input OHLCV DataFrame.
            period (int): ATR window.

        Returns:
            pd.Series: ATR values.
        """
        high_low = data["High"] - data["Low"]
        high_close = np.abs(data["High"] - data["Close"].shift())
        low_close = np.abs(data["Low"] - data["Close"].shift())
        tr = high_low.to_frame("tr")
        tr["hc"] = high_close
        tr["lc"] = low_close
        true_range = tr.max(axis=1)
        atr = true_range.rolling(window=period).mean()
        logging.info(f"Calculated {period}-period ATR.")
        return atr
