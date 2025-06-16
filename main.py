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
from ml.ai_signal_generator import AISignalGenerator
from ml.config import Decision
from core.telegram_notifier import TelegramNotifier
from binance.client import Client
from loguru import logger
from core.telegram_signal_listener import TelegramSignalListener
from utils.binance_precision import get_precision, round_quantity, round_price
from typing import Dict, Any
from utils.trade_history_logger import save_trade
from utils.dumb_strategy import dumb_strategy_signal
from datetime import datetime

def get_symbol_info(client, symbol):
    try:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                return s
        logger.error(f"Symbol info for {symbol} not found in exchange info.")
    except Exception as e:
        logger.error(f"Error fetching symbol info for {symbol}: {e}")
    return None

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

def initialize_components(config):
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

        risk_management = RiskManagement(client, "risk_config.json")
        technical_analysis = TechnicalAnalysis(client)
        ai_signal_generator = AISignalGenerator()
        ai_model = AIModel("ml/models/model.h5")
        trading_logic = TradingLogic(client, risk_management, technical_analysis, ai_model)
        telegram_notifier = TelegramNotifier(bot_token, chat_id)

        logger.debug("All components initialized successfully.")
        return client, risk_management, technical_analysis, ai_signal_generator, trading_logic, telegram_notifier
    except Exception as e:
        logger.error(f"Error initializing components: {e}")
        logger.debug(traceback.format_exc())
        raise

def get_account_balance(client, asset="USDT"):
    try:
        balance = client.futures_account_balance()
        for item in balance:
            if item["asset"] == asset:
                logger.info(f"Fetched balance for {asset}: {item['balance']} USDT")
                return float(item["balance"])
    except Exception as e:
        logger.error(f"Error fetching balance for {asset}: {e}")
        logger.debug(traceback.format_exc())
    return 0.0

def handle_tradingruhal_signal(signal_text):
    logger.info(f"Отримано tradingruhal: {signal_text}")
    # TODO: тут може бути логіка для обробки сигналу tradingruhal

async def run_telegram_listener():
    listener = TelegramSignalListener('config/config.ini', handle_tradingruhal_signal)
    await listener.start()

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

def process_closed_trades(active_trades: Dict[str, Dict[str, Any]], ai_signal_generator: Any) -> None:
    trades_to_remove = []
    for trade_id, trade_info in active_trades.items():
        try:
            if not is_position_closed(trade_info):
                continue

            features_dict = trade_info.get("features")
            if not features_dict:
                logger.warning(f"Trade {trade_id}: No 'features' found in trade_info. Skipping update.")
                trades_to_remove.append(trade_id)
                continue

            profit = get_trade_profit(trade_info)
            target = 1 if profit > 0 else 0

            ai_signal_generator.partial_fit(features_dict, target)
            logger.info(f"AI model updated for trade {trade_id}. Profit: {profit:.4f}, Target: {target}")

            trades_to_remove.append(trade_id)
            logger.info(f"[{trade_id}] Trade closed. Side: {trade_info.get('side')}, Entry: {trade_info.get('entry_price')}, Close: {trade_info.get('close_price')}, Profit: {profit:.4f}, Target: {target}")
        except KeyError as e:
            logger.error(f"Trade {trade_id}: Missing expected key in trade_info: {e}. Skipping trade.")
        except Exception as e:
            logger.error(f"Error processing trade {trade_id}: {e}. Skipping trade.")

    for trade_id in trades_to_remove:
        if trade_id in active_trades:
            del active_trades[trade_id]
            logger.info(f"Trade {trade_id} removed from active_trades.")

def main():
    setup_logging()
    logger.info("Starting Binance Futures Trading Bot...")
    try:
        config_path = "config/config.ini"
        config = load_config(config_path)
        client, risk_management, technical_analysis, ai_signal_generator, trading_logic, telegram_notifier = initialize_components(config)
        
        # --- Відправляємо баланс у Telegram при старті ---
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        account_balance = get_account_balance(client, asset="USDT")
        risk_management.update_account_balance(account_balance)
        telegram_notifier.send_message(f"[{now_str}] Старт бота. Баланс: {account_balance:.2f} USDT")

        symbols = config.get("TRADING", "SYMBOLS", fallback="BTCUSDT").split(",")
        interval = config.get("TRADING", "INTERVAL", fallback="1h")
        active_trades = {}
        loop = asyncio.get_event_loop()
        loop.create_task(run_telegram_listener())

        TP_PCT = 1.03
        SL_PCT = 0.98

        # --- Для щогодинної відправки балансу ---
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

                        features = ai_signal_generator.extract_features(df)
                        ai_decision, price_info = ai_signal_generator.predict(features)

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

                        symbol_info = get_symbol_info(client, symbol)
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

                        features_for_save = features

                        trade_id = f"{symbol}_{side}_{int(time.time())}"
                        active_trades[trade_id] = {
                            "features": features_for_save,
                            "symbol": symbol,
                            "entry_price": entry_price,
                            "side": side,
                            "status": "OPEN"
                        }
                        order = trading_logic.place_order(symbol, side, position_size, stop_loss_price, take_profit_price)
                        if order:
                            logger.info(f"[{trade_id}] {side} order placed: {order}")
                            active_trades[trade_id]["order"] = order
                        else:
                            logger.error(f"[{trade_id}] {side} order failed!")
                    except Exception as e:
                        logger.error(f"Error fetching/generating signal for {symbol}: {e}")
                        logger.debug(traceback.format_exc())

                # --- Щогодинна відправка балансу ---
                if time.time() - last_balance_time > 3600:
                    account_balance = get_account_balance(client, asset="USDT")
                    risk_management.update_account_balance(account_balance)
                    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    telegram_notifier.send_message(f"[{now_str}] Баланс: {account_balance:.2f} USDT")
                    last_balance_time = time.time()
                
                trading_logic.check_closed_trades()
                process_closed_trades(active_trades, ai_signal_generator)
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

if __name__ == "__main__":
    main()


