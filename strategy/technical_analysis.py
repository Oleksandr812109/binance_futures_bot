from binance.client import Client
import pandas as pd
from loguru import logger
import pandas_ta as ta

class TechnicalAnalysis:
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
                client.API_URL = 'https://testnet.binancefuture.com/fapi/v1'

            # Fetch candlestick data
            klines = client.futures_klines(symbol=symbol, interval=interval)

            # Convert to DataFrame
            data = pd.DataFrame(klines, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote asset volume', 'Number of trades',
                'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
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

    def generate_optimized_signals(self, market_data, ema_short=12, ema_long=26, rsi_period=14, risk_reward_ratio=2):
        """
        Generate optimized trading signals based on technical analysis.

        Args:
            market_data (pd.DataFrame): Historical market data with columns ['Open', 'High', 'Low', 'Close', 'Volume'].
            ema_short (int): Period for the short EMA.
            ema_long (int): Period for the long EMA.
            rsi_period (int): Period for RSI calculation.
            risk_reward_ratio (float): Desired risk-to-reward ratio for stop-loss and take-profit.

        Returns:
            pd.DataFrame: Market data with added 'Signal', 'Stop_Loss', and 'Take_Profit' columns.
        """
        # Validate input data
        if not all(col in market_data.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume']):
            raise ValueError("market_data must contain 'Open', 'High', 'Low', 'Close', and 'Volume' columns")

        # Calculate EMAs
        market_data['EMA_Short'] = ta.ema(market_data['Close'], length=ema_short)
        market_data['EMA_Long'] = ta.ema(market_data['Close'], length=ema_long)

        # Calculate RSI
        market_data['RSI'] = ta.rsi(market_data['Close'], length=rsi_period)

        # Calculate Bollinger Bands
        bbands = ta.bbands(market_data['Close'], length=20, std=2)
        market_data['Upper_Band'] = bbands['BBU_20_2.0']
        market_data['Middle_Band'] = bbands['BBM_20_2.0']
        market_data['Lower_Band'] = bbands['BBL_20_2.0']

        # Calculate ADX for trend strength
        adx = ta.adx(market_data['High'], market_data['Low'], market_data['Close'], length=14)
        market_data['ADX'] = adx['ADX_14']

        # Set default signal to HOLD
        market_data['Signal'] = 'HOLD'

        # Generate signals based on EMA crossovers and RSI
        market_data.loc[
            (market_data['EMA_Short'] > market_data['EMA_Long']) & (market_data['RSI'] < 70), 'Signal'
        ] = 'BUY'
        market_data.loc[
            (market_data['EMA_Short'] < market_data['EMA_Long']) & (market_data['RSI'] > 30), 'Signal'
        ] = 'SELL'

        # Strong buy and sell signals using Bollinger Bands
        market_data.loc[
            (market_data['Close'] < market_data['Lower_Band']) & (market_data['RSI'] < 30), 'Signal'
        ] = 'STRONG_BUY'
        market_data.loc[
            (market_data['Close'] > market_data['Upper_Band']) & (market_data['RSI'] > 70), 'Signal'
        ] = 'STRONG_SELL'

        # Add Stop-Loss and Take-Profit levels
        atr = ta.atr(market_data['High'], market_data['Low'], market_data['Close'], length=14)
        market_data['Stop_Loss'] = market_data['Close'] - (atr * 1.5)
        market_data['Take_Profit'] = market_data['Close'] + (atr * risk_reward_ratio)

        # Filter signals based on ADX (trend strength)
        market_data.loc[(market_data['ADX'] < 25), 'Signal'] = 'HOLD'

        logger.info("Optimized signals generated successfully.")
        return market_data
