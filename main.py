import os
import sys
import time
import traceback
import logging
import asyncio
from configparser import ConfigParser
from strategy.trading_logic import TradingLogic
from strategy.risk_management import RiskManagement
from strategy.technical_analysis import TechnicalAnalysis
from strategy.ai_signal_generator import AISignalGenerator
from core.telegram_notifier import TelegramNotifier
from binance.client import Client
from loguru import logger
from core.telegram_signal_listener import TelegramSignalListener
from utils.binance_precision import get_precision, round_quantity, round_price
from typing import Dict, Any

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
        if testnet:
            client.API_URL = "https://testnet.binancefuture.com/fapi/v1"

        logger.info(f"Binance client initialized (testnet={testnet})")

        if not test_api_key(client):
            raise ValueError("Invalid API Key or insufficient permissions. Please check your API settings.")

        account_balance = config.getfloat("TRADING", "ACCOUNT_BALANCE", fallback=0.0)
        if account_balance <= 0:
            asset = config.get("TRADING", "BASE_ASSET", fallback="USDT")
            account_balance = get_account_balance(client, asset)

        risk_per_trade = config.getfloat("TRADING", "risk_per_trade", fallback=0.01)
        max_drawdown = config.getfloat("TRADING", "max_drawdown", fallback=0.2)

        risk_management = RiskManagement(client, risk_per_trade, max_drawdown)
        technical_analysis = TechnicalAnalysis(client)
        ai_signal_generator = AISignalGenerator()
        trading_logic = TradingLogic(client, risk_management, technical_analysis)
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
    logger.info(f"Сигнал із tradingruhal: {signal_text}")
    # TODO: Парсинг тексту сигналу та передача у торгову логіку

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

            # LOGGING закриття угоди
            logger.info(f"[{trade_id}] Trade closed. Side: {trade_info.get('side')}, Entry: {trade_info.get('entry_price')}, Close: {trade_info.get('close_price')}, Profit: {profit:.4f}, Target label: {target}")

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
        account_balance = risk_management.account_balance
        telegram_notifier.send_message(f"Bot started. Current balance: {account_balance} USDT")
        symbols = config.get("TRADING", "SYMBOLS", fallback="BTCUSDT").split(",")
        interval = config.get("TRADING", "INTERVAL", fallback="1h")

        loop = asyncio.get_event_loop()
        loop.create_task(run_telegram_listener())

        active_trades = {}

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
                    data = ai_signal_generator.predict_signals(data)

                    # LOGGING згенерованих сигналів для кожного бару
                    feature_cols = ["EMA_Short", "EMA_Long", "RSI", "ADX", "Upper_Band", "Lower_Band"]
                    for idx in range(len(data)):
                        signal = data.iloc[idx]
                        ai_signal = signal["AI_Signal"] if "AI_Signal" in signal else getattr(signal, "AI_Signal", None)
                        features_log = {col: signal[col] for col in feature_cols if col in signal}
                        logger.info(f"[{symbol}] idx={idx} | AI_Signal={ai_signal} | features: {features_log}")

                        if hasattr(signal, "AI_Signal") or "AI_Signal" in signal:
                            ai_signal = signal["AI_Signal"] if "AI_Signal" in signal else signal.AI_Signal
                            if ai_signal == 1:
                                logger.info(f"AI Buy signal detected for {symbol} at idx={idx}, placing order...")
                                entry_price = signal["Close"] if "Close" in signal else getattr(signal, "Close", None)
                                stop_loss_price = signal["Stop_Loss"] if "Stop_Loss" in signal else getattr(signal, "Stop_Loss", None)
                                if entry_price is None or stop_loss_price is None:
                                    logger.error(f"Missing entry or stop-loss price. Skipping order.")
                                    continue
                                stop_loss_distance = entry_price - stop_loss_price
                                if stop_loss_distance <= 0:
                                    logger.error(f"Invalid stop-loss distance for {symbol}. Skipping order.")
                                    continue
                                position_size = risk_management.calculate_position_size(stop_loss_distance)

                                symbol_info = get_symbol_info(client, symbol)
                                if symbol_info is None:
                                    logger.error(f"Cannot trade {symbol} because symbol_info is missing!")
                                    continue
                                quantity_precision = get_precision(symbol_info, "quantity")
                                position_size = round_quantity(position_size, quantity_precision)

                                features = {col: float(signal[col]) for col in feature_cols if col in signal}
                                trade_id = f"{symbol}_BUY_{int(time.time())}"
                                active_trades[trade_id] = {
                                    "features": features,
                                    "symbol": symbol,
                                    "entry_price": entry_price,
                                    "side": "BUY",
                                    "status": "OPEN"
                                }

                                order = trading_logic.place_order(symbol, "BUY", position_size)
                                if order:
                                    logger.info(f"[{trade_id}] BUY order placed: {order}")
                                    telegram_notifier.send_message(
                                        f"Order placed: AI BUY {symbol} | Quantity: {position_size} | Entry price: {entry_price} USDT"
                                    )
                                    active_trades[trade_id]["order"] = order
                                else:
                                    logger.error(f"[{trade_id}] BUY order failed!")

                            elif ai_signal == -1:
                                logger.info(f"AI Sell signal detected for {symbol} at idx={idx}, placing order...")
                                entry_price = signal["Close"] if "Close" in signal else getattr(signal, "Close", None)
                                stop_loss_price = signal["Stop_Loss"] if "Stop_Loss" in signal else getattr(signal, "Stop_Loss", None)
                                if entry_price is None or stop_loss_price is None:
                                    logger.error(f"Missing entry or stop-loss price. Skipping order.")
                                    continue
                                stop_loss_distance = stop_loss_price - entry_price
                                if stop_loss_distance <= 0:
                                    logger.error(f"Invalid stop-loss distance for {symbol}. Skipping order.")
                                    continue
                                position_size = risk_management.calculate_position_size(stop_loss_distance)

                                symbol_info = get_symbol_info(client, symbol)
                                if symbol_info is None:
                                    logger.error(f"Cannot trade {symbol} because symbol_info is missing!")
                                    continue
                                quantity_precision = get_precision(symbol_info, "quantity")
                                position_size = round_quantity(position_size, quantity_precision)

                                features = {col: float(signal[col]) for col in feature_cols if col in signal}
                                trade_id = f"{symbol}_SELL_{int(time.time())}"
                                active_trades[trade_id] = {
                                    "features": features,
                                    "symbol": symbol,
                                    "entry_price": entry_price,
                                    "side": "SELL",
                                    "status": "OPEN"
                                }

                                order = trading_logic.place_order(symbol, "SELL", position_size)
                                if order:
                                    logger.info(f"[{trade_id}] SELL order placed: {order}")
                                    telegram_notifier.send_message(
                                        f"Order placed: AI SELL {symbol} | Quantity: {position_size} | Entry price: {entry_price} USDT"
                                    )
                                    active_trades[trade_id]["order"] = order
                                else:
                                    logger.error(f"[{trade_id}] SELL order failed!")

                    # --- Блок автоматичного закриття позицій по PNL ---
                    for trade_id, trade_info in list(active_trades.items()):
                        if trade_info.get("status") == "CLOSED":
                            continue

                        symbol = trade_info["symbol"]
                        entry_price = trade_info["entry_price"]
                        side = trade_info["side"]

                        try:
                            ticker = client.futures_symbol_ticker(symbol=symbol)
                            current_price = float(ticker["price"])
                        except Exception as e:
                            logger.error(f"Could not fetch current price for {symbol}: {e}")
                            continue

                        if side == "BUY":
                            pnl = (current_price - entry_price) / entry_price * 100
                        else:
                            pnl = (entry_price - current_price) / entry_price * 100

                        logger.info(f"[{trade_id}] Current PNL: {pnl:.2f}%")

                        CLOSE_PROFIT_PNL = 20   # take-profit %
                        CLOSE_LOSS_PNL = -40    # stop-loss %

                        if pnl >= CLOSE_PROFIT_PNL or pnl <= CLOSE_LOSS_PNL:
                            reason = "profit target" if pnl >= CLOSE_PROFIT_PNL else "stop-loss"
                            quantity = None
                            order_info = trade_info.get("order", {})
                            for qty_key in ("origQty", "executedQty", "cumQty", "quantity"):
                                if qty_key in order_info:
                                    try:
                                        quantity = float(order_info[qty_key])
                                        break
                                    except Exception:
                                        continue
                            if not quantity:
                                logger.error(f"Cannot close position for {trade_id}: unknown quantity.")
                                continue

                            side_to_close = "SELL" if side == "BUY" else "BUY"
                            close_order = trading_logic.close_position(symbol, float(quantity), side_to_close)
                            if close_order:
                                logger.info(f"[{trade_id}] Position closed at {current_price} with PNL {pnl:.2f}% ({reason})")
                                telegram_notifier.send_message(
                                    f"Position closed for {symbol}! Side: {side}, Quantity: {quantity}, Price: {current_price}, PNL: {pnl:.2f}% ({reason})"
                                )
                                trade_info["status"] = "CLOSED"
                                trade_info["close_price"] = current_price
                                # LOGGING закриття угоди
                                logger.info(f"[{trade_id}] Order closing info: {close_order}")
                            else:
                                logger.error(f"[{trade_id}] Failed to close position at {current_price} ({reason})")

                    process_closed_trades(active_trades, ai_signal_generator)
                    logger.info(f"Finished processing signals for {symbol}. Waiting for the next cycle...")

                except Exception as e:
                    logger.error(f"Error during market analysis loop for {symbol}: {e}")

            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Bot stopped manually by user.")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.debug(traceback.format_exc())

if __name__ == "__main__":
    main()
