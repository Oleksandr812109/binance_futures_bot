import pandas as pd
from binance.client import Client
from loguru import logger

class TechnicalAnalysis:
    # ...
    def generate_optimized_signals(self, data, short_window=20, long_window=50):
        """
        Generate trading signals based on moving averages, Bollinger Bands, and RSI.

        Args:
            data (pd.DataFrame): Market data DataFrame.
            short_window (int): Short moving average window.
            long_window (int): Long moving average window.

        Returns:
            pd.DataFrame: DataFrame with trading signals.
        """
        try:
            logger.info("Generating optimized trading signals...")

            # Calculate short and long moving averages
            data['SMA_short'] = data['Close'].rolling(window=short_window).mean()
            data['SMA_long'] = data['Close'].rolling(window=long_window).mean()

            # Generate Moving Average signals
            data['Signal_MA'] = 0
            data.loc[data['SMA_short'] > data['SMA_long'], 'Signal_MA'] = 1  # Buy signal
            data.loc[data['SMA_short'] < data['SMA_long'], 'Signal_MA'] = -1  # Sell signal

            # Calculate Bollinger Bands
            data['BB_Middle'] = data['Close'].rolling(window=20).mean()
            data['BB_Upper'] = data['BB_Middle'] + 2 * data['Close'].rolling(window=20).std()
            data['BB_Lower'] = data['BB_Middle'] - 2 * data['Close'].rolling(window=20).std()

            # Generate Bollinger Band signals
            data['Signal_BB'] = 0
            data.loc[data['Close'] < data['BB_Lower'], 'Signal_BB'] = 1  # Buy signal
            data.loc[data['Close'] > data['BB_Upper'], 'Signal_BB'] = -1  # Sell signal

            # Calculate RSI
            delta = data['Close'].diff(1)
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            data['RSI'] = 100 - (100 / (1 + rs))

            # Generate RSI signals
            data['Signal_RSI'] = 0
            data.loc[data['RSI'] < 30, 'Signal_RSI'] = 1  # Buy signal
            data.loc[data['RSI'] > 70, 'Signal_RSI'] = -1  # Sell signal

            # Combine signals
            data['Trading_Signal'] = data[['Signal_MA', 'Signal_BB', 'Signal_RSI']].sum(axis=1)

            logger.info("Trading signals generated successfully.")
            return data
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            raise
