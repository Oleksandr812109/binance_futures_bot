import logging
from binance.client import Client
from utils.check_margin_and_quantity import can_close_position
import decimal
import json
import os
import time

MIN_TP_SL_GAP = 0.04  # 0.4%
TRADES_STATE_FILE = "active_trades.json"

class TradingLogic:
    def __init__(self, client: Client, risk_management, technical_analysis, ai_model):
        self.client = client
        self.risk_management = risk_management
        self.technical_analysis = technical_analysis
        self.ai_model = ai_model
        self._symbol_precision_cache = {}
        self.active_trades = []
        self._load_active_trades()

    def _get_symbol_precisions(self, symbol):
        if symbol in self._symbol_precision_cache:
            return self._symbol_precision_cache[symbol]
        exchange_info = self.client.futures_exchange_info()
        symbol_info = next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)
        quantity_step = float([f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['stepSize'])
        price_step = float([f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'][0]['tickSize'])
        self._symbol_precision_cache[symbol] = (quantity_step, price_step)
        return quantity_step, price_step

    @staticmethod
    def _round_step(value, step):
        return float(decimal.Decimal(str(value)).quantize(decimal.Decimal(str(step)), rounding=decimal.ROUND_DOWN))

    def _save_active_trades(self):
        try:
            with open(TRADES_STATE_FILE, "w") as f:
                json.dump(self.active_trades, f, indent=2)
        except Exception as e:
            logging.error(f"Couldn't save active_trades: {e}")

    def _load_active_trades(self):
        if os.path.exists(TRADES_STATE_FILE):
            try:
                with open(TRADES_STATE_FILE, "r") as f:
                    self.active_trades = json.load(f)
            except Exception as e:
                logging.error(f"Couldn't load active_trades: {e}")
        else:
            self.active_trades = []

    def safe_tp_sl(self, entry_price, tp_price, sl_price, side, min_gap=MIN_TP_SL_GAP):
        if side == "BUY":
            min_tp = entry_price * (1 + min_gap)
            max_sl = entry_price * (1 - min_gap)
            tp_price = max(tp_price, min_tp)
            sl_price = min(sl_price, max_sl)
        else:
            max_tp = entry_price * (1 - min_gap)
            min_sl = entry_price * (1 + min_gap)
            tp_price = min(tp_price, max_tp)
            sl_price = max(sl_price, min_sl)
        return tp_price, sl_price

    def place_order(self, trade_info, quantity, stop_loss_price, take_profit_price):
        symbol = trade_info["symbol"]
        side = trade_info["side"]
        positionSide = "LONG" if side == "BUY" else "SHORT"

        try:
            quantity_step, price_step = self._get_symbol_precisions(symbol)
            quantity = self._round_step(quantity, quantity_step)

            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                positionSide=positionSide
            )
            logging.info(f"Market order placed: {order}")

            trades = self.client.futures_account_trades(symbol=symbol)
            entry_price = None
            for t in reversed(trades):
                if int(t["orderId"]) == int(order["orderId"]):
                    entry_price = float(t["price"])
                    break
            if not entry_price:
                entry_price = float(order.get('avgPrice', 0)) if order.get('avgPrice', '0.00') != '0.00' else None

            take_profit_price, stop_loss_price = self.safe_tp_sl(entry_price, take_profit_price, stop_loss_price, side)
            stop_loss_price = self._round_step(stop_loss_price, price_step)
            take_profit_price = self._round_step(take_profit_price, price_step)

            stop_loss_params = dict(
                symbol=symbol,
                side="SELL" if side == "BUY" else "BUY",
                type="STOP_MARKET",
                stopPrice=stop_loss_price,
                quantity=quantity,
                positionSide=positionSide,
                reduceOnly=True,
            )
            take_profit_params = dict(
                symbol=symbol,
                side="SELL" if side == "BUY" else "BUY",
                type="TAKE_PROFIT_MARKET",
                stopPrice=take_profit_price,
                quantity=quantity,
                positionSide=positionSide,
                reduceOnly=True,
            )

            try:
                stop_loss_order = self.client.futures_create_order(**stop_loss_params)
            except Exception as e:
                if "Parameter 'reduceonly' sent when not required" in str(e):
                    stop_loss_params.pop('reduceOnly')
                    stop_loss_order = self.client.futures_create_order(**stop_loss_params)
                else:
                    logging.error(f"Error placing stop-loss order: {e}")
                    raise

            try:
                take_profit_order = self.client.futures_create_order(**take_profit_params)
            except Exception as e:
                if "Parameter 'reduceonly' sent when not required" in str(e):
                    take_profit_params.pop('reduceOnly')
                    take_profit_order = self.client.futures_create_order(**take_profit_params)
                else:
                    logging.error(f"Error placing take-profit order: {e}")
                    raise

            logging.info(f"Stop loss order placed: {stop_loss_order}")
            logging.info(f"Take profit order placed: {take_profit_order}")

            trade_info["qty"] = quantity
            trade_info["positionSide"] = positionSide
            trade_info["entry_price"] = entry_price
            trade_info["tp_order_id"] = take_profit_order['orderId']
            trade_info["sl_order_id"] = stop_loss_order['orderId']
            trade_info["opened_at"] = time.time()

            self.active_trades.append(trade_info)
            self._save_active_trades()

            return {
                "order": order,
                "stop_loss_order": stop_loss_order,
                "take_profit_order": take_profit_order
            }
        except Exception as e:
            logging.error(f"Error placing bracket orders: {e}")
            return None

    def close_position(self, symbol, qty, side, positionSide="BOTH"):
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=qty,
                positionSide=positionSide,
                reduceOnly=True
            )
            logging.info(f"Position closed: {symbol}, qty={qty}, side={side}, positionSide={positionSide}. Order: {order}")
            return order
        except Exception as e:
            logging.error(f"close_position error for {symbol}: {e}")
            return None

    def cancel_order(self, symbol, order_id, max_retries=3, retry_delay=2):
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"Trying to cancel order {order_id} on {symbol}, attempt {attempt}")
                result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
                logging.info(f"Order {order_id} cancelled on {symbol} | Binance response: {result}")
                return result
            except Exception as e:
                logging.warning(f"Error cancelling order {order_id} on {symbol}, attempt {attempt}: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Failed to cancel order {order_id} on {symbol} after {max_retries} attempts.")
        return None

    def get_open_positions(self, symbol):
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            return positions
        except Exception as e:
            logging.error(f"Error getting open positions for {symbol}: {e}")
            return []

    def get_manual_close_price(self, trade):
        try:
            trades = self.client.futures_account_trades(symbol=trade['symbol'])
            side_closed = "SELL" if trade['side'] == "BUY" else "BUY"
            positionSide = trade.get('positionSide', "BOTH")
            opened_at = trade.get('opened_at', 0)
            for t in reversed(trades):
                if (
                    t['side'] == side_closed
                    and t.get('positionSide', positionSide) == positionSide
                    and float(t['time'])/1000 > opened_at
                ):
                    return float(t['price'])
        except Exception as e:
            logging.error(f"get_manual_close_price error for {trade['symbol']}: {e}")
        return None

    def learn_ai(self, trade, close_price, close_type):
        # Передайте features і target у ваш AI-модуль/модель
        features = trade.get("features")
        if features and hasattr(self.ai_model, "partial_fit"):
            target = 1 if close_price and close_price > trade.get("entry_price", 0) else 0
            self.ai_model.partial_fit(features, target)
            logging.info(f"AI model updated for {trade.get('symbol')} by {close_type}. Target: {target}")
        else:
            logging.info(f"Skipped AI train for {trade.get('symbol')} by {close_type} (no features or model)")

    def check_closed_trades(self):
        for trade in self.active_trades[:]:
            try:
                # TP/SL закриття
                tp_filled = False
                sl_filled = False
                tp_order = None
                sl_order = None
                try:
                    tp_order = self.client.futures_get_order(symbol=trade['symbol'], orderId=trade.get('tp_order_id'))
                    if tp_order and tp_order['status'] == 'FILLED':
                        tp_filled = True
                except Exception:
                    pass
                try:
                    sl_order = self.client.futures_get_order(symbol=trade['symbol'], orderId=trade.get('sl_order_id'))
                    if sl_order and sl_order['status'] == 'FILLED':
                        sl_filled = True
                except Exception:
                    pass

                # Якщо закрито TP/SL
                if tp_filled or sl_filled:
                    close_type = 'TAKE_PROFIT' if tp_filled else 'STOP_LOSS'
                    close_order = tp_order if tp_filled else sl_order
                    close_price = float(close_order['avgPrice']) if close_order and close_order.get('avgPrice') else None
                    self.learn_ai(trade, close_price, close_type)
                    self.cancel_order(trade['symbol'], trade.get('sl_order_id'))
                    self.cancel_order(trade['symbol'], trade.get('tp_order_id'))
                    self.active_trades.remove(trade)
                    self._save_active_trades()
                    continue

                # Ручне закриття (позиція відкрита на біржі, але закрита вручну)
                positions = self.get_open_positions(trade['symbol'])
                if not any(float(pos['positionAmt']) != 0 and pos['positionSide'] == trade['positionSide'] for pos in positions):
                    close_price = self.get_manual_close_price(trade)
                    if close_price is not None:
                        self.learn_ai(trade, close_price, 'MANUAL_CLOSE')
                    else:
                        logging.warning(f"Cannot update AI: missing close price for {trade['symbol']}. Trade skipped for training.")
                    self.cancel_order(trade['symbol'], trade.get('tp_order_id'))
                    self.cancel_order(trade['symbol'], trade.get('sl_order_id'))
                    self.active_trades.remove(trade)
                    self._save_active_trades()
            except Exception as e:
                logging.error(f"Error in check_closed_trades for {trade.get('symbol', '?')}: {e}", exc_info=True)

