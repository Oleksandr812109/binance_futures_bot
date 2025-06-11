import logging 
from binance.client import Client 
from utils.check_margin_and_quantity import can_close_position 
import decimal 
import time

MIN_TP_SL_GAP = 0.04  # 0.3% (можна підвищити до 0.005 чи 0.01)

class TradingLogic:
    def __init__(self, client: Client, risk_management, technical_analysis, ai_model):
        self.client = client
        self.risk_management = risk_management
        self.technical_analysis = technical_analysis
        self.ai_model = ai_model
        self._symbol_precision_cache = {}
        self.active_trades = []  # Список всіх відкритих угод

    def _get_symbol_precisions(self, symbol):
        """
        Отримати stepSize для quantity і tickSize для ціни для конкретного symbol.
        Кешується в _symbol_precision_cache.
        """
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
        """
        Округлити value до precision step (stepSize або tickSize)
        """
        return float(decimal.Decimal(str(value)).quantize(decimal.Decimal(str(step)), rounding=decimal.ROUND_DOWN))

    def safe_tp_sl(self, entry_price, tp_price, sl_price, side, min_gap=MIN_TP_SL_GAP):
        """
        Гарантує, що TP/SL не занадто близько до ціни входу (entry_price).
        """
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

    def get_manual_close_price(self, trade):
        """
        Спробувати отримати ціну закриття з історії угод або останньої ціни для ручного закриття.
        """
        # Реалізуй за потреби
        return None

    def cancel_order(self, symbol, order_id):
        """
        Скасувати ордер на біржі Binance Futures.
        """
        try:
            self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logging.info(f"Order {order_id} cancelled on {symbol}")
        except Exception as e:
            logging.warning(f"Error cancelling order {order_id}: {e}")


    def place_order(self, symbol: str, side: str, quantity: float, stop_loss_price: float, take_profit_price: float):
        """
        Place a market order on Binance Futures AND immediately set stop-loss and take-profit.
        """
        if quantity <= 0:
            logging.error("Order quantity must be greater than zero.")
            return None

        for trade in self.active_trades:
            if trade["symbol"] == symbol and trade["side"] == side:
                logging.info(f"Відкрита позиція по {symbol} ({side}) вже існує. Нову не відкриваємо.")
                return None

        try:
            quantity_step, price_step = self._get_symbol_precisions(symbol)
            quantity = self._round_step(quantity, quantity_step)
            positionSide = "LONG" if side == "BUY" else "SHORT"
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                positionSide=positionSide
            )
            logging.info(f"Market order placed: {order}")

            entry_price = float(order.get('avgPrice', 0)) if order.get('avgPrice', '0.00') != '0.00' else None
            if not entry_price:
                for _ in range(3):
                    positions = self.client.futures_position_information()
                    for pos in positions:
                        if pos['symbol'] == symbol and float(pos['positionAmt']) != 0 and pos['positionSide'] == positionSide:
                            entry_price = float(pos['entryPrice'])
                            break
                    if entry_price:
                        break
                    time.sleep(1)

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
            )
            take_profit_params = dict(
                symbol=symbol,
                side="SELL" if side == "BUY" else "BUY",
                type="TAKE_PROFIT_MARKET",
                stopPrice=take_profit_price,
                quantity=quantity,
                positionSide=positionSide,
            )

            stop_loss_order = None
            take_profit_order = None

            try:
                stop_loss_params['reduceOnly'] = True
                stop_loss_order = self.client.futures_create_order(**stop_loss_params)
            except Exception as e:
                if "Parameter 'reduceonly' sent when not required" in str(e):
                    stop_loss_params.pop('reduceOnly')
                    stop_loss_order = self.client.futures_create_order(**stop_loss_params)
                else:
                    logging.error(f"Error placing stop-loss order: {e}")
                    raise

            try:
                take_profit_params['reduceOnly'] = True
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

            trade_info = {
                "symbol": symbol,
                "side": side,
                "qty": quantity,
                "positionSide": positionSide,
                "entry_price": entry_price,
                "tp_order_id": take_profit_order['orderId'],
                "sl_order_id": stop_loss_order['orderId'],
                "opened_at": time.time()
            }
            self.active_trades.append(trade_info)

            return {
                "order": order,
                "stop_loss_order": stop_loss_order,
                "take_profit_order": take_profit_order
            }
        except Exception as e:
            logging.error(f"Error placing bracket orders: {e}")
            return None

    def check_closed_trades(self):
        """
        Перевірити виконання стоп-лосс/тейк-профіт ордерів та навчити AI на реальних результатах.
        Видаляти неактуальні ордери після закриття позиції.
        """
        pnl_threshold = 5.0  # у USDT
        for trade in self.active_trades[:]:
            try:
                positions = self.client.futures_position_information(symbol=trade['symbol'])
                for pos in positions:
                    if float(pos['positionAmt']) != 0 and pos['positionSide'] == trade['positionSide']:
                        pnl = float(pos['unrealizedProfit'])
                        if pnl >= pnl_threshold:
                            self.close_position(
                                trade['symbol'],
                                abs(float(pos['positionAmt'])),
                                "SELL" if pos['positionSide'] == "LONG" else "BUY"
                            )
                            logging.info(f"Position {trade['symbol']} closed early by PNL threshold: {pnl} USDT")
                            self.active_trades.remove(trade)
                            break
            except Exception as e:
                logging.error(f"Error checking/closing by PNL: {e}")

        for trade in self.active_trades[:]:
            # Перевіряємо тейк-профіт
            try:
                tp_order = self.client.futures_get_order(symbol=trade['symbol'], orderId=trade['tp_order_id'])
                if tp_order['status'] == 'FILLED':
                    close_price = float(tp_order['avgPrice']) if tp_order['avgPrice'] else None
                    logging.info(f"[TP FILL] symbol={trade['symbol']} | TP avgPrice={tp_order.get('avgPrice')} | orderId={trade['tp_order_id']}")
                    self.learn_ai(trade, close_price, 'TAKE_PROFIT')
                    # --- Скасування SL ордера ---
                    self.cancel_order(trade['symbol'], trade['sl_order_id'])
                    self.active_trades.remove(trade)
                    continue
            except Exception as e:
                logging.error(f"Error checking TP order status: {e}")
            # Перевіряємо стоп-лосс
            try:
                sl_order = self.client.futures_get_order(symbol=trade['symbol'], orderId=trade['sl_order_id'])
                if sl_order['status'] == 'FILLED':
                    close_price = float(sl_order['avgPrice']) if sl_order['avgPrice'] else None
                    logging.info(f"[SL FILL] symbol={trade['symbol']} | SL avgPrice={sl_order.get('avgPrice')} | orderId={trade['sl_order_id']}")
                    self.learn_ai(trade, close_price, 'STOP_LOSS')
                    # --- Скасування TP ордера ---
                    self.cancel_order(trade['symbol'], trade['tp_order_id'])
                    self.active_trades.remove(trade)
                    continue
            except Exception as e:
                logging.error(f"Error checking SL order status: {e}")

        # --- Додаємо перевірку ручного закриття позиції ---
        for trade in self.active_trades[:]:
            positions = self.get_open_positions(trade['symbol'])
            side = trade['side']
            if not any(float(pos['positionAmt']) != 0 and pos['positionSide'] == trade['positionSide'] for pos in positions):
                close_price = self.get_manual_close_price(trade)
                if close_price is None:
                    logging.warning(f"Cannot update AI: missing close price for {trade['symbol']}. Trade skipped for training.")
                else:
                    self.learn_ai(trade, close_price, 'MANUAL_CLOSE')
                    # При ручному закритті бажано скасувати обидва ордери
                    self.cancel_order(trade['symbol'], trade['tp_order_id'])
                    self.cancel_order(trade['symbol'], trade['sl_order_id'])
                self.active_trades.remove(trade)
        # --------------------------------------------------


