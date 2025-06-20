import os
import sys
import time
import traceback
import logging
import asyncio
from configparser import ConfigParser
from strategy.trading_logic import TradingLogic
from strategy.ai_model import AIModel
from strategy.risk_management import RiskManagement
from strategy.technical_analysis import TechnicalAnalysis
from strategy.ai_signal_generator import AISignalGenerator   # Виправлено шлях імпорту
from strategy.ai_signal_generator import Decision           # Використовуємо Enum із цього ж файлу
from core.telegram_notifier import TelegramNotifier
from binance.client import Client
from loguru import logger
from core.telegram_signal_listener import TelegramSignalListener
from utils.binance_precision import get_precision, round_quantity, round_price
from typing import Dict, Any
from datetime import datetime
import joblib

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
    try:
        logger.info("Testing API key...")
        account_info = client.futures_account()
        logger.info(f"API Key is valid. Account info fetched successfully.")
        return True
    except Exception as e:
        logger.error(f"Invalid API Key or insufficient permissions: {e}")
        logger.debug(traceback.format_exc())
        return False

def load_model_and_scaler(symbol, model_dir="ml/models"):
    """
    Завантаження моделі та скейлера для AISignalGenerator для конкретного символу.
    """
    model_path = f"{model_dir}/model_{symbol}.pkl"
    scaler_path = f"{model_dir}/scaler_{symbol}.joblib"
    try:
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        logger.info(f"Model and scaler loaded successfully from {model_path} and {scaler_path}")
        return model, scaler
    except Exception as e:
        logger.error(f"Failed to load model/scaler for {symbol}: {e}")
        raise

def get_account_balance(client, asset="USDT"):
    try:
        balance = client.futures_account_balance()
        logger.debug(f"Raw balance response: {balance}")
        for item in balance:
            if item.get("asset") == asset:
                value = item.get("balance")
                # Деякі версії API можуть повертати walletBalance
                if value is None:
                    value = item.get("walletBalance")
                if value is not None:
                    logger.info(f"Fetched balance for {asset}: {value} USDT")
                    return float(value)
                else:
                    logger.error(f"Balance field not found for {asset} in item: {item}")
    except Exception as e:
        logger.error(f"Error fetching balance for {asset}: {e}")
        logger.debug(traceback.format_exc())
    return 0.0


def initialize_components(config, symbols):
    try:
        api_key = config.get("BINANCE", "API_KEY")
        api_secret = config.get("BINANCE", "API_SECRET")
        testnet = config.getboolean("BINANCE", "TESTNET", fallback=True)
        bot_token = config.get("TELEGRAM", "BOT_TOKEN")
        chat_id = config.get("TELEGRAM", "CHAT_ID")

        client = Client(api_key, api_secret, testnet=testnet)
        logger.info(f"Binance client initialized (testnet={testnet})")

        if not test_api_key(client):
            raise ValueError("Invalid API Key or insufficient permissions. Please check your API settings.")

        account_balance = config.getfloat("TRADING", "ACCOUNT_BALANCE", fallback=0.0)
        if account_balance <= 0:
            asset = config.get("TRADING", "BASE_ASSET", fallback="USDT")
            account_balance = get_account_balance(client, asset)
        risk_per_trade = config.getfloat("TRADING", "risk_per_trade", fallback=0.01)
        max_drawdown = config.getfloat("TRADING", "max_drawdown", fallback=0.2)

        # ---- КЕШ символів ----
        exchange_info = client.futures_exchange_info()
        symbol_info_map = {s['symbol']: s for s in exchange_info['symbols']}
        risk_management = RiskManagement(client, "risk_config.json")
        technical_analysis = TechnicalAnalysis(client)
        # --- Завантаження моделей і скейлерів для кожного symbol ---
        ai_signal_generators = {}
        for symbol in symbols:
            model, scaler = load_model_and_scaler(symbol)
            ai_signal_generators[symbol] = AISignalGenerator(model, scaler)
        ai_model = AIModel("ml/models/model.h5")
        trading_logic = TradingLogic(client, risk_management, technical_analysis, ai_model)
        telegram_notifier = TelegramNotifier(bot_token, chat_id)

        logger.debug("All components initialized successfully.")
        return client, risk_management, technical_analysis, ai_signal_generators, trading_logic, telegram_notifier, symbol_info_map
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        logger.debug(traceback.format_exc())
        raise

def handle_tradingruhal_signal(signal_text):
    logger.info(f"Отримано tradingruhal: {signal_text}")
    # TODO: тут може бути логіка для обробки сигналу tradingruhal

async def run_telegram_listener():
    listener = TelegramSignalListener('config/config.ini', handle_tradingruhal_signal)
    await listener.start()

def main():
    setup_logging()
    logger.info("Starting Binance Futures Trading Bot...")
    try:
        config_path = "config/config.ini"
        config = load_config(config_path)
        symbols = config.get("TRADING", "SYMBOLS", fallback="BTCUSDT").split(",")
        client, risk_management, technical_analysis, ai_signal_generators, trading_logic, telegram_notifier, symbol_info_map = initialize_components(config, symbols)
        
        # --- Відправляємо баланс у Telegram при старті ---
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        account_balance = get_account_balance(client, asset="USDT")
        risk_management.update_account_balance(account_balance)
        telegram_notifier.send_message(f"[{now_str}] Старт бота. Баланс: {account_balance:.2f} USDT")

        interval = config.get("TRADING", "INTERVAL", fallback="1h")
        loop = asyncio.get_event_loop()
        loop.create_task(run_telegram_listener())

        last_balance_time = time.time()


        while True:
            try:
                for symbol in symbols:
                    try:
                        df = technical_analysis.fetch_binance_data(symbol=symbol, interval=interval, testnet=client.testnet)
                        if df is None or df.empty:
                            logger.warning(f"No market data for {symbol}, skipping.")
                            continue

                        df = technical_analysis.generate_optimized_signals(df, symbol)
                        if df is None:
                            continue

                        # --- отримуємо рішення і ціни --- (тепер для symbol)
                        ai_decision, price_info = ai_signal_generators[symbol].predict(df)

                        if ai_decision not in [Decision.BUY, Decision.SELL]:
                            logger.info(f"AI decision: HOLD for {symbol}. No action taken.")
                            continue

                        entry_price = price_info.get("entry")
                        stop_loss_price = price_info.get("stop_loss")
                        take_profit_price = price_info.get("take_profit")

                        if entry_price is None or stop_loss_price is None or take_profit_price is None:
                            logger.error(f"Missing entry, stop-loss, or take-profit price. Skipping order.")
                            continue

                        if ai_decision == Decision.BUY:
                            stop_loss_distance = entry_price - stop_loss_price
                            if stop_loss_distance <= 0:
                                logger.error(f"Invalid stop-loss distance for {symbol} (LONG). Skipping order.")
                                continue
                            position_size = risk_management.calculate_position_size(symbol, entry_price, stop_loss_price)
                            side = "BUY"
                        else:
                            stop_loss_distance = stop_loss_price - entry_price
                            if stop_loss_distance <= 0:
                                logger.error(f"Invalid stop-loss distance for {symbol} (SHORT). Skipping order.")
                                continue
                            position_size = risk_management.calculate_position_size(symbol, entry_price, stop_loss_price)
                            side = "SELL"

                        symbol_info = symbol_info_map.get(symbol)
                        if symbol_info is None:
                            logger.error(f"Cannot trade {symbol} because symbol_info is missing!")
                            continue
                        quantity_precision = get_precision(symbol_info, "quantity")
                        position_size = round_quantity(position_size, quantity_precision)
                        max_position_size = None
                        for f in symbol_info.get("filters", []):
                            if f["filterType"] == "MARKET_LOT_SIZE":
                                max_position_size = float(f["maxQty"])
                        if max_position_size and position_size > max_position_size:
                            logger.warning(f"Position size {position_size} > max for {symbol}: {max_position_size}. Зменшую до ліміту.")
                            position_size = max_position_size

                        trade_id = f"{symbol}_{side}_{int(time.time())}"
                        trade_info = {
                            "features": None,
                            "symbol": symbol,
                            "entry_price": entry_price,
                            "side": side,
                            "status": "OPEN",
                            "trade_id": trade_id,
                        }
                        if trading_logic.has_active_trade(symbol):
                            logger.info(f"Вже є відкритий трейд по {symbol}. Новий ордер не створюється.")
                            continue
                        order = trading_logic.place_order(trade_info, position_size, stop_loss_price, take_profit_price)
                        if order:
                            logger.info(f"[{trade_id}] {side} order placed: {order}")
                        else:
                            logger.error(f"[{trade_id}] {side} order failed!")
                    except Exception as e:
                        logger.error(f"Error fetching/generating signal for {symbol}: {e}")
                        logger.debug(traceback.format_exc())

                if time.time() - last_balance_time > 3600:
                    account_balance = get_account_balance(client, asset="USDT")
                    risk_management.update_account_balance(account_balance)
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    telegram_notifier.send_message(f"[{now_str}] Баланс: {account_balance:.2f} USDT")
                    last_balance_time = time.time()
                
                trading_logic.check_closed_trades()

                # === АВТОМАТИЧНЕ ЗАКРИТТЯ ПОЗИЦІЇ ПО ROI ===
                for trade in trading_logic.active_trades.values():
                    if trade.get("status") != "OPEN":
                        continue
                    symbol = trade["symbol"]
                    entry_price = trade["entry_price"]
                    side = trade["side"]
                    position_size = trade.get("position_size")
                    leverage = trade.get("leverage", 1)  # Якщо не використовуєш плече, залиш 1

                    # Отримуємо поточну ціну з Binance
                    try:
                        ticker = client.futures_symbol_ticker(symbol=symbol)
                        last_price = float(ticker["price"])
                    except Exception as e:
                        logger.error(f"Can't fetch price for {symbol}: {e}")
                        continue

                    if side == "BUY":
                        roi = ((last_price - entry_price) / entry_price) * leverage
                    else:  # SELL/SHORT
                        roi = ((entry_price - last_price) / entry_price) * leverage

                    if roi >= 0.1:  # 10% ROI
                        logger.info(f"ROI for {symbol} reached {roi*100:.2f}%. Closing position!")
                        trading_logic.close_position(trade["trade_id"])
                        telegram_notifier.send_message(f"🚀 ROI для {symbol} досяг {roi*100:.2f}%. Позицію закрито автоматично.")
                time.sleep(60)

            except Exception as e:
                logger.error(f"Error during market analysis loop: {e}")
                logger.debug(traceback.format_exc())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually by user.")
        pass
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.debug(traceback.format_exc())


def is_position_closed(trade_info: Dict[str, Any]) -> bool:
    return trade_info.get("status") == "CLOSED" or trade_info.get("closed", False)

def get_trade_profit(trade_info: Dict[str, Any]) -> float:
    open_price = trade_info.get("entry_price")
    close_price = trade_info.get("close_price")
    side = trade_info.get("side", "BUY")
    if open_price is None or close_price is None:
        logger.warning(f"Trade info missing open/close price: {trade_info.get('trade_id')}")
        return 0.0
    if side == "BUY":
        return close_price - open_price
    elif side == "SELL":
        return open_price - close_price
    return 0.0

if __name__ == "__main__":
    main()
