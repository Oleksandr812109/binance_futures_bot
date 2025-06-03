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
from utils.trade_history_logger import save_trade
from utils.dumb_strategy import dumb_strategy_signal 

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

            # LOGGING видалення трейду
            logger.info(f"[{trade_id}] Trade closed. Side: {trade_info.get('side')}, Entry: {trade_info.get('entry_price')}, Close: {trade_info.get('close_price')}, Profit: {profit:.4f}, Target last: {target}")
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

        feature_cols = ["EMA_Short", "EMA_Long", "RSI", "ADX", "Upper_Band", "Lower_Band"]
        active_trades = {}

        loop = asyncio.get_event_loop()
        loop.create_task(run_telegram_listener())

        # --- Додаємо take-profit/stop-loss пороги (онови їх тут!)
        CLOSE_PROFIT_PNL = 1   # take-profit %
        CLOSE_LOSS_PNL = -40   # stop-loss %

        while True:
            try:
                # --- Отримання сигналів через AI ---
                signals = []
                for symbol in symbols:
                    try:
                        df = technical_analysis.fetch_binance_data(symbol=symbol, interval=interval, testnet=client.testnet)
                        if df is None or df.empty:
                            logger.warning(f"No market data for {symbol}, skipping.")
                            continue
                        df = technical_analysis.generate_optimized_signals(df)

                        # AI сигнал
                        signals_df = ai_signal_generator.predict_signals(df)
                        if signals_df is None or signals_df.empty:
                            logger.warning(f"No signals generated for {symbol}, skipping.")
                            continue
                        num_signals = signals_df["AI_Signal"].abs().sum()
                        last_row = signals_df.iloc[-1]

                        if num_signals == 0:
                            # fallback: простий сигнал для старту навчання AI
                            logger.info(f"AI не дав жодного сигналу — fallback: шукаю простий теханаліз сигнал для {symbol}")
                            fallback_signal_val = 0
                            if last_row["EMA_Short"] > last_row["EMA_Long"] or last_row["RSI"] < 30:
                                fallback_signal_val = 1
                            elif last_row["EMA_Short"] < last_row["EMA_Long"] or last_row["RSI"] > 70:
                                fallback_signal_val = -1

                            fallback_stop_loss = last_row.get("Stop_Loss", None)
                            entry_price = last_row.get("Close", None)
                            # Перевірка та fallback для Stop_Loss
                            if fallback_signal_val == 1 and entry_price is not None:
                                if (fallback_stop_loss is None or 
                                    fallback_stop_loss >= entry_price or 
                                    fallback_stop_loss != fallback_stop_loss):
                                    fallback_stop_loss = entry_price * 0.98
                            elif fallback_signal_val == -1 and entry_price is not None:
                                if (fallback_stop_loss is None or 
                                    fallback_stop_loss <= entry_price or 
                                    fallback_stop_loss != fallback_stop_loss):
                                    fallback_stop_loss = entry_price * 1.02

                            if fallback_signal_val != 0:
                                logger.info(f"Fallback сигнал для {symbol}: {fallback_signal_val}")
                                signal = {
                                    "symbol": symbol,
                                    "decision": int(fallback_signal_val),
                                    "Close": entry_price,
                                    "Stop_Loss": fallback_stop_loss,
                                    "EMA_Short": last_row.get("EMA_Short", 0.0),
                                    "EMA_Long": last_row.get("EMA_Long", 0.0),
                                    "RSI": last_row.get("RSI", 0.0),
                                    "ADX": last_row.get("ADX", 0.0),
                                    "Upper_Band": last_row.get("Upper_Band", 0.0),
                                    "Lower_Band": last_row.get("Lower_Band", 0.0),
                                }
                                signals.append(signal)
                        else:
                            signal_val = last_row["AI_Signal"]
                            if signal_val == 1 or signal_val == -1:
                                signal = {
                                    "symbol": symbol,
                                    "decision": int(signal_val),
                                    "Close": last_row.get("Close", None),
                                    "Stop_Loss": last_row.get("Stop_Loss", None),
                                    "EMA_Short": last_row.get("EMA_Short", 0.0),
                                    "EMA_Long": last_row.get("EMA_Long", 0.0),
                                    "RSI": last_row.get("RSI", 0.0),
                                    "ADX": last_row.get("ADX", 0.0),
                                    "Upper_Band": last_row.get("Upper_Band", 0.0),
                                    "Lower_Band": last_row.get("Lower_Band", 0.0),
                                }
                                signals.append(signal)
                    except Exception as e:
                        logger.error(f"Error fetching/generating signal for {symbol}: {e}")
                        logger.debug(traceback.format_exc())

                for idx, signal in enumerate(signals):
                    symbol = signal.get("symbol")
                    decision = signal.get("decision")
                    if symbol is None or decision is None:
                        logger.error(f"Signal missing symbol or decision: {signal}")
                        continue

                    if decision == 1:
                        logger.info(f"Buy signal detected for {symbol} at idx={idx}, placing order.")
                        entry_price = signal.get("Close")
                        stop_loss_price = signal.get("Stop_Loss")
                        if entry_price is None or stop_loss_price is None:
                            logger.error(f"Missing entry or stop-loss price. Skipping order.")
                            continue
                        stop_loss_distance = entry_price - stop_loss_price
                        if stop_loss_distance <= 0:
                            logger.error(f"Invalid stop-loss distance for {symbol} (LONG). Skipping order.")
                            continue
                        position_size = risk_management.calculate_position_size(stop_loss_distance)

                        symbol_info = get_symbol_info(client, symbol)
                        if symbol_info is None:
                            logger.error(f"Cannot trade {symbol} because symbol_info is missing!")
                            continue
                        quantity_precision = get_precision(symbol_info, "quantity")
                        position_size = round_quantity(position_size, quantity_precision)

                        # Перевірка максимальної позиції (maxQty)
                        max_position_size = None
                        for f in symbol_info.get("filters", []):
                            if f["filterType"] == "MARKET_LOT_SIZE":
                                max_position_size = float(f["maxQty"])
                        if max_position_size and position_size > max_position_size:
                            logger.warning(f"Position size {position_size} > max for {symbol}: {max_position_size}. Зменшую до ліміту.")
                            position_size = max_position_size

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
                            qty_keys = ["origQty", "executedQty", "cumQty", "quantity"]
                            found_qty = next((order.get(k) for k in qty_keys if k in order), None)
                            logger.info(f"[{trade_id}] Order quantity (for closing): {found_qty}")
                            active_trades[trade_id]["order"] = order
                            telegram_notifier.send_message(
                                f"Order placed: AI BUY {symbol} | Quantity: {position_size} | Entry price: {entry_price} USDT"
                            )
                        else:
                            logger.error(f"[{trade_id}] BUY order failed!")

                    elif decision == -1:
                        logger.info(f"Sell signal detected for {symbol} at idx={idx}, placing order.")
                        entry_price = signal.get("Close")
                        stop_loss_price = signal.get("Stop_Loss")
                        if entry_price is None or stop_loss_price is None:
                            logger.error(f"Missing entry or stop-loss price. Skipping order.")
                            continue
                        stop_loss_distance = stop_loss_price - entry_price
                        if stop_loss_distance <= 0:
                            logger.error(f"Invalid stop-loss distance for {symbol} (SHORT). Skipping order.")
                            continue
                        position_size = risk_management.calculate_position_size(stop_loss_distance)

                        symbol_info = get_symbol_info(client, symbol)
                        if symbol_info is None:
                            logger.error(f"Cannot trade {symbol} because symbol_info is missing!")
                            continue
                        quantity_precision = get_precision(symbol_info, "quantity")
                        position_size = round_quantity(position_size, quantity_precision)

                        # Перевірка максимальної позиції (maxQty)
                        max_position_size = None
                        for f in symbol_info.get("filters", []):
                            if f["filterType"] == "MARKET_LOT_SIZE":
                                max_position_size = float(f["maxQty"])
                        if max_position_size and position_size > max_position_size:
                            logger.warning(f"Position size {position_size} > max for {symbol}: {max_position_size}. Зменшую до ліміту.")
                            position_size = max_position_size

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
                            qty_keys = ["origQty", "executedQty", "cumQty", "quantity"]
                            found_qty = next((order.get(k) for k in qty_keys if k in order), None)
                            logger.info(f"[{trade_id}] Order quantity (for closing): {found_qty}")
                            active_trades[trade_id]["order"] = order
                            telegram_notifier.send_message(
                                f"Order placed: AI SELL {symbol} | Quantity: {position_size} | Entry price: {entry_price} USDT"
                            )
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

                    leverage = 1
                    try:
                        positions = client.futures_position_information(symbol=symbol)
                        if positions and isinstance(positions, list):
                            leverage = float(positions[0].get("leverage", 1))
                    except Exception as e:
                        logger.error(f"Cannot fetch leverage for {symbol}: {e}")

                    if side == "BUY":
                        pnl = (current_price - entry_price) / entry_price * leverage * 100
                    else:
                        pnl = (entry_price - current_price) / entry_price * leverage * 100

                    logger.info(f"[{trade_id}] Current PNL: {pnl:.2f}%")

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
                            try:
                                positions = client.futures_position_information(symbol=symbol)
                                for pos in positions:
                                    if float(pos["positionAmt"]) != 0:
                                        quantity = abs(float(pos["positionAmt"]))
                                        break
                                if not quantity:
                                    logger.error(f"Cannot close position for {trade_id}: no open position found on exchange.")
                                    continue
                            except Exception as e:
                                logger.error(f"Cannot fetch open position for {trade_id}: {e}")
                                continue

                        close_side = "SELL" if side == "BUY" else "BUY"
                        logger.info(f"[{trade_id}] Attempting to close position at {current_price} ({reason}) with quantity {quantity}")
                        close_order = trading_logic.close_position(symbol, quantity, close_side)
                        if close_order:
                            logger.info(f"[{trade_id}] Position closed: {close_order}")
                            telegram_notifier.send_message(
                                f"Position closed: {symbol} | Reason: {reason} | Close price: {current_price} USDT | PNL: {pnl:.2f}%"
                            )
                            trade_info["status"] = "CLOSED"
                        else:
                            logger.error(f"[{trade_id}] Failed to close position at {current_price} ({reason})")

                process_closed_trades(active_trades, ai_signal_generator)
                time.sleep(60)
            except Exception as e:
                logger.error(f"Error during market analysis loop: {e}")
                logger.debug(traceback.format_exc()) 
    except KeyboardInterrupt:
        logger.info("Bot stopped manually by user.")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.debug(traceback.format_exc())

if __name__ == "__main__":
    main()

