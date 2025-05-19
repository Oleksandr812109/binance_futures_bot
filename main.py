import os
from configparser import ConfigParser
from strategy.trading_logic import TradingLogic
from strategy.risk_management import RiskManagement
from strategy.technical_analysis import TechnicalAnalysis
from strategy.ai_signal_generator import AISignalGenerator  # Додаємо імпорт AI-модуля
from core.telegram_notifier import TelegramNotifier
from binance.client import Client
from loguru import logger
import traceback
import sys
import time

def setup_logging(log_file="bot.log"):
    logger.remove()
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
    )

def load_config(config_path="config/config.ini"):
    if not os.path.exists(config_path):
        logger.error(f"Configuration file '{config_path}' not found!")
        raise FileNotFoundError(f"Configuration file '{config_path}' not found!")

    config = ConfigParser()
    config.read(config_path)
    logger.info("Configuration file loaded successfully.")
    return config

def test_api_key(client):
    """
    Test the API key by attempting to fetch futures account information.
    If the API key is invalid, raise an exception and log an error.
    """
    try:
        logger.info("Testing API key...")
        account_info = client.futures_account()  # Updated for futures
        logger.info(f"API Key is valid. Account info fetched successfully.")
        return True
    except Exception as e:
        logger.error(f"Invalid API Key or insufficient permissions: {e}")
        logger.debug(traceback.format_exc())
        return False

def initialize_components(config):
    try:
        api_key = config.get("BINANCE", "API_KEY")
        api_secret = config.get("BINANCE", "API_SECRET")
        testnet = config.getboolean("BINANCE", "TESTNET", fallback=True)
        bot_token = config.get("TELEGRAM", "BOT_TOKEN")
        chat_id = config.get("TELEGRAM", "CHAT_ID")

        client = Client(api_key, api_secret, testnet=testnet)
        if testnet:
            client.API_URL = "https://testnet.binancefuture.com/fapi/v1"  # Updated URL

        logger.info(f"Binance client initialized (testnet={testnet})")

        # Test API Key
        if not test_api_key(client):
            raise ValueError("Invalid API Key or insufficient permissions. Please check your API settings.")

        # Fetching the real account balance from Binance API
        account_balance = config.getfloat("TRADING", "ACCOUNT_BALANCE", fallback=0.0)
        if account_balance <= 0:
            asset = config.get("TRADING", "BASE_ASSET", fallback="USDT")
            account_balance = get_account_balance(client, asset)

        risk_per_trade = config.getfloat("TRADING", "risk_per_trade", fallback=0.01)
        max_drawdown = config.getfloat("TRADING", "max_drawdown", fallback=0.2)

        risk_management = RiskManagement(client, risk_per_trade, max_drawdown)
        technical_analysis = TechnicalAnalysis()
        ai_signal_generator = AISignalGenerator()  # ініціалізуємо AI-модуль
        trading_logic = TradingLogic(client, risk_management, technical_analysis)
        telegram_notifier = TelegramNotifier(bot_token, chat_id)

        logger.debug("All components initialized successfully.")
        return client, risk_management, technical_analysis, ai_signal_generator, trading_logic, telegram_notifier
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        logger.debug(traceback.format_exc())
        raise

def get_account_balance(client, asset="USDT"):
    """
    Fetch the account balance for a specific asset.
    """
    try:
        balance = client.futures_account_balance()  # Updated for futures
        for item in balance:
            if item["asset"] == asset:
                logger.info(f"Fetched balance for {asset}: {item['balance']} USDT")
                return float(item["balance"])
    except Exception as e:
        logger.error(f"Error fetching balance for {asset}: {e}")
        logger.debug(traceback.format_exc())
    return 0.0

def main():
    setup_logging()

    logger.info("Starting Binance Futures Trading Bot...")
    try:
        config_path = "config/config.ini"
        config = load_config(config_path)

        client, risk_management, technical_analysis, ai_signal_generator, trading_logic, telegram_notifier = initialize_components(config)

        account_balance = risk_management.account_balance
        telegram_notifier.send_message(f"Bot started. Current balance: {account_balance} USDT")

        symbols = config.get("TRADING", "SYMBOLS", fallback="BTCUSDT").split(",")
        interval = config.get("TRADING", "INTERVAL", fallback="1h")

        while True:
            for symbol in symbols:
                try:
                    logger.info(f"Fetching market data for {symbol} with interval {interval}...")
                    data = technical_analysis.fetch_binance_data(symbol=symbol, interval=interval, testnet=client.testnet)

                    if data is None or data.empty:
                        logger.error(f"Fetched market data for {symbol} is empty or invalid. Skipping...")
                        continue

                    logger.info(f"Generating trading signals for {symbol}...")
                    data = technical_analysis.generate_optimized_signals(data)

                    # AI-модуль: генеруємо AI-сигнали на основі підготовлених технічних даних
                    data = ai_signal_generator.predict_signals(data)

                    if data is None or data.empty:
                        logger.error(f"No valid trading signals generated for {symbol}. Skipping...")
                        continue

                    # Тепер використовуємо AI-сигнали для торгівлі
                    for signal in data.itertuples():
                        logger.debug(f"Processing signal for {symbol}: {signal}")

                        # Приклад: AI_Signal = 1 (Buy), -1 (Sell), 0 (Hold)
                        if hasattr(signal, "AI_Signal"):
                            if signal.AI_Signal == 1:
                                logger.info(f"AI Buy signal detected for {symbol}, placing order...")
                                # Далі аналогічно до вашої логіки, наприклад:
                                entry_price = getattr(signal, "Close", None)
                                stop_loss_price = getattr(signal, "Stop_Loss", None)
                                if entry_price is None or stop_loss_price is None:
                                    logger.error(f"Missing entry or stop-loss price. Skipping order.")
                                    continue
                                stop_loss_distance = entry_price - stop_loss_price
                                if stop_loss_distance <= 0:
                                    logger.error(f"Invalid stop-loss distance for {symbol}. Skipping order.")
                                    continue
                                position_size = risk_management.calculate_position_size(stop_loss_distance)
                                order = trading_logic.place_order(symbol, "BUY", position_size)
                                if order:
                                    telegram_notifier.send_message(
                                        f"Order placed: AI BUY {symbol} | Quantity: {position_size} | Entry price: {entry_price} USDT"
                                    )

                            elif signal.AI_Signal == -1:
                                logger.info(f"AI Sell signal detected for {symbol}, placing order...")
                                entry_price = getattr(signal, "Close", None)
                                stop_loss_price = getattr(signal, "Stop_Loss", None)
                                if entry_price is None or stop_loss_price is None:
                                    logger.error(f"Missing entry or stop-loss price. Skipping order.")
                                    continue
                                stop_loss_distance = stop_loss_price - entry_price
                                if stop_loss_distance <= 0:
                                    logger.error(f"Invalid stop-loss distance for {symbol}. Skipping order.")
                                    continue
                                position_size = risk_management.calculate_position_size(stop_loss_distance)
                                order = trading_logic.place_order(symbol, "SELL", position_size)
                                if order:
                                    telegram_notifier.send_message(
                                        f"Order placed: AI SELL {symbol} | Quantity: {position_size} | Entry price: {entry_price} USDT"
                                    )

                    logger.info(f"Finished processing signals for {symbol}. Waiting for the next cycle...")

                except Exception as e:
                    logger.error(f"Error during market analysis loop for {symbol}: {e}")
                    logger.debug(traceback.format_exc())
            time.sleep(60)  # Wait before the next iteration

    except Exception as e:
        logger.critical(f"An error occurred: {e}")
        logger.debug(traceback.format_exc())

if __name__ == "__main__":
    main()
