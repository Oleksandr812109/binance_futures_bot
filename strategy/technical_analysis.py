import pandas as pd
from binance.client import Client
from loguru import logger

class TechnicalAnalysis:
    def __init__(self):
        logger.info("TechnicalAnalysis initialized")

    def fetch_binance_data(self, symbol, interval, testnet=False):
        """
        Fetch historical market data from Binance.

        Args:
            symbol (str): Trading pair symbol, e.g., 'BTCUSDT'.
            interval (str): Candlestick interval, e.g., '1h'.
            testnet (bool): Whether to use Binance testnet.

        Returns:
            pd.DataFrame: DataFrame containing market data.
        """
        try:
            logger.info(f"Fetching data for {symbol} with interval {interval} (testnet={testnet})...")

            # Initialize Binance client
            client = Client()
            if testnet:
                client.API_URL = 'https://testnet.binance.vision/api'

            # Fetch candlestick data
            klines = client.get_klines(symbol=symbol, interval=interval)

            # Convert to DataFrame
            data = pd.DataFrame(klines, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
            ])

            # Convert numeric columns to float
            data = data.astype({
                'Open': 'float', 'High': 'float', 'Low': 'float', 'Close': 'float', 'Volume': 'float'
            })

            # Convert timestamps to datetime
            data['Open time'] = pd.to_datetime(data['Open time'], unit='ms')
            data['Close time'] = pd.to_datetime(data['Close time'], unit='ms')

            logger.info(f"Data for {symbol} fetched successfully.")
            return data
        except Exception as e:
            logger.error(f"Error fetching Binance data: {e}")
            raise

    def generate_optimized_signals(self, data, short_window=20, long_window=50):
        """
        Generate trading signals based on moving averages.

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

            # Generate signals
            data['Signal'] = 0
            data.loc[data['SMA_short'] > data['SMA_long'], 'Signal'] = 1  # Buy signal
            data.loc[data['SMA_short'] < data['SMA_long'], 'Signal'] = -1  # Sell signal

            logger.info("Trading signals generated successfully.")
            return data
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            raise
