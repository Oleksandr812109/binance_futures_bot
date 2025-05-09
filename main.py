import os
from configparser import ConfigParser
from strategy.trading_logic import TradingLogic
from strategy.risk_management import RiskManagement
from strategy.technical_analysis import TechnicalAnalysis
from binance.client import Client
from loguru import logger
import traceback
import sys  # Додано імпорт для використання sys
import time  # Додано для використання time.sleep


def setup_logging(log_file="bot.log"):
    """
    Set up the logging configuration.

    Args:
        log_file (str): Path to the log file.
    """
    # Remove default logger and add custom configuration
    logger.remove()
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG",
        rotation="10 MB",  # Rotate log file when it reaches 10 MB
        retention="7 days",  # Keep logs for the last 7 days
        compression="zip",  # Compress old logs
    )
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
    )


def load_config(config_path="config/config.ini"):
    """
    Load configuration from a file.

    Args:
        config_path (str): Path to the configuration file.

    Returns:
        ConfigParser: Parsed configuration object.
    """
    if not os.path.exists(config_path):
        logger.error(f"Configuration file '{config_path}' not found!")
        raise FileNotFoundError(f"Configuration file '{config_path}' not found!")

    config = ConfigParser()
    config.read(config_path)
    logger.info("Configuration file loaded successfully.")
    return config


def initialize_components(config):
    """
    Initialize all components required for the trading bot.

    Args:
        config (ConfigParser): Configuration object.

    Returns:
        tuple: Binance client, RiskManagement, TechnicalAnalysis, TradingLogic instances.
    """
    try:
        # Load Binance API credentials
        api_key = config.get('BINANCE', 'API_KEY')
        api_secret = config.get('BINANCE', 'API_SECRET')
        testnet = config.getboolean('BINANCE', 'TESTNET', fallback=True)

        # Initialize Binance client
        client = Client(api_key, api_secret, testnet=testnet)
        if testnet:
            client.API_URL = 'https://testnet.binance.vision/api'

        logger.info("Binance client initialized (testnet={})".format(testnet))

        # Fetch account balance (you can later replace this with actual API call)
        account_balance = config.getfloat('TRADING', 'ACCOUNT_BALANCE', fallback=1000.0)  # Default to 1000.0 if not provided

        # Initialize other components
        risk_management = RiskManagement(account_balance)
        technical_analysis = TechnicalAnalysis()
        trading_logic = TradingLogic(client, risk_management, technical_analysis)

        logger.debug("All components initialized successfully.")
        return client, risk_management, technical_analysis, trading_logic
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        logger.debug(traceback.format_exc())
        raise


def main():
    """
    Main entry point for the trading bot.
    """
    setup_logging()

    logger.info("Starting Binance Futures Trading Bot...")
    try:
        # Load configuration
        config_path = "config/config.ini"  # Path to config file
        config = load_config(config_path)

        # Initialize components
        client, risk_management, technical_analysis, trading_logic = initialize_components(config)

        # Fetch configuration for symbol and interval
        symbol = config.get('TRADING', 'SYMBOL', fallback='BTCUSDT')
        interval = config.get('TRADING', 'INTERVAL', fallback='1h')

        # Continuous market analysis loop
        while True:
            try:
                # Fetch market data
                logger.info(f"Fetching market data for {symbol} with interval {interval}...")
                data = technical_analysis.fetch_binance_data(symbol=symbol, interval=interval, testnet=client.testnet)

                # Check if data is valid
                if data is None or data.empty:
                    logger.error("Fetched market data is empty or invalid. Skipping iteration...")
                    time.sleep(60)  # Wait for 1 minute before retrying
                    continue

                # Generate trading signals using fetched data
                logger.info("Generating trading signals...")
                signals = technical_analysis.generate_optimized_signals(data)

                # Check if signals are valid
                if signals is None or signals.empty:
                    logger.error("No valid trading signals generated. Skipping iteration...")
                    time.sleep(60)  # Wait for 1 minute before retrying
                    continue

                # Process each signal
                for signal in signals.itertuples():
                    logger.debug(f"Processing signal: {signal}")
                    if signal.Signal == "Buy":
                        logger.info("Buy signal detected, placing order...")

                        entry_price = signal.EntryPrice
                        stop_loss_price = signal.StopLossPrice
                        stop_loss_distance = entry_price - stop_loss_price

                        if stop_loss_distance <= 0:
                            logger.error("Invalid stop-loss distance. Skipping order.")
                            continue

                        position_size = risk_management.calculate_position_size(stop_loss_distance)
                        trading_logic.place_order(symbol, "BUY", position_size)

                    elif signal.Signal == "Sell":
                        logger.info("Sell signal detected, placing order...")

                        entry_price = signal.EntryPrice
                        stop_loss_price = signal.StopLossPrice
                        stop_loss_distance = stop_loss_price - entry_price

                        if stop_loss_distance <= 0:
                            logger.error("Invalid stop-loss distance. Skipping order.")
                            continue

                        position_size = risk_management.calculate_position_size(stop_loss_distance)
                        trading_logic.place_order(symbol, "SELL", position_size)

                # Wait before the next iteration (e.g., 1 minute)
                logger.info("Waiting for the next cycle...")
                time.sleep(60)

            except Exception as e:
                logger.error(f"Error during market analysis loop: {e}")
                logger.debug(traceback.format_exc())
                time.sleep(60)  # Wait before retrying in case of an error

    except Exception as e:
        logger.critical(f"An error occurred: {e}")
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
