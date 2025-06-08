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

    def place_order(self, symbol: str, side: str, quantity: float, stop_loss_price: float, take_profit_price: float):
        """
        Place a market order on Binance Futures AND immediately set stop-loss and take-profit.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            side (str): 'BUY' or 'SELL'.
            quantity (float): Quantity to buy or sell.
            stop_loss_price (float): Stop-loss trigger price.
            take_profit_price (float): Take-profit trigger price.

        Returns:
            dict: Responses from Binance API for all 3 orders.
        """
        if quantity <= 0:
            logging.error("Order quantity must be greater than zero.")
            return None

        # === ДОДАНО ПЕРЕВІРКУ: Чи вже є відкрита угода по цій парі та напрямку ===
        for trade in self.active_trades:
            if trade["symbol"] == symbol and trade["side"] == side:
                logging.info(f"Відкрита позиція по {symbol} ({side}) вже існує. Нову не відкриваємо.")
                return None
        # =======================================================================

        try:
            # ОКРУГЛЕННЯ quantity та цін до потрібної точності
            quantity_step, price_step = self._get_symbol_precisions(symbol)
            quantity = self._round_step(quantity, quantity_step)

            positionSide = "LONG" if side == "BUY" else "SHORT"
            # 1. Place entry order (reduceOnly не потрібен для відкриття)
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
                # Дочекатися появи позиції на біржі (ретрай 3 рази)
                for _ in range(3):
                    positions = self.client.futures_position_information()
                    for pos in positions:
                        if pos['symbol'] == symbol and float(pos['positionAmt']) != 0 and pos['positionSide'] == positionSide:
                            entry_price = float(pos['entryPrice'])
                            break
                    if entry_price:
                        break
                    time.sleep(1)

            # ==== >>>> ДОДАНО КОНТРОЛЬ ВІДСТАНІ ДО TP/SL <<<< ====
            take_profit_price, stop_loss_price = self.safe_tp_sl(entry_price, take_profit_price, stop_loss_price, side)
            stop_loss_price = self._round_step(stop_loss_price, price_step)
            take_profit_price = self._round_step(take_profit_price, price_step)
            # ==== <<<< ДОДАНО КОНТРОЛЬ ВІДСТАНІ ДО TP/SL <<<< ====

            # 2. Place stop loss order
            stop_loss_params = dict(
                symbol=symbol,
                side="SELL" if side == "BUY" else "BUY",
                type="STOP_MARKET",
                stopPrice=stop_loss_price,
                quantity=quantity,
                positionSide=positionSide,
            )
            # 3. Place take profit order
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

            # Додаємо reduceOnly, якщо Binance це приймає, інакше пробуємо без нього
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

            # Зберігаємо трейд для подальшого відстеження
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
        """

        pnl_threshold = 5.0  # у USDT
        for trade in self.active_trades[:]:
            try:
                positions = self.client.futures_position_information(symbol=trade['symbol'])
                for pos in positions:
                    # Важливо: позиція має бути відкрита й відповідати стороні (LONG/SHORT)
                    if float(pos['positionAmt']) != 0 and pos['positionSide'] == trade['positionSide']:
                        pnl = float(pos['unrealizedProfit'])
                        if pnl >= pnl_threshold:
                            # Закриваємо позицію ринковим ордером
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
                    # --- Додаємо логування avgPrice тейк-профіту ---
                    logging.info(f"[TP FILL] symbol={trade['symbol']} | TP avgPrice={tp_order.get('avgPrice')} | orderId={trade['tp_order_id']}")
                    self.learn_ai(trade, close_price, 'TAKE_PROFIT')
                    self.active_trades.remove(trade)
                    continue
            except Exception as e:
                logging.error(f"Error checking TP order status: {e}")
            # Перевіряємо стоп-лосс
            try:
                sl_order = self.client.futures_get_order(symbol=trade['symbol'], orderId=trade['sl_order_id'])
                if sl_order['status'] == 'FILLED':
                    close_price = float(sl_order['avgPrice']) if sl_order['avgPrice'] else None
                    # --- Додаємо логування avgPrice стоп-лоссу ---
                    logging.info(f"[SL FILL] symbol={trade['symbol']} | SL avgPrice={sl_order.get('avgPrice')} | orderId={trade['sl_order_id']}")
                    self.learn_ai(trade, close_price, 'STOP_LOSS')
                    self.active_trades.remove(trade)
                    continue
            except Exception as e:
                logging.error(f"Error checking SL order status: {e}")

    def learn_ai(self, trade, close_price, exit_type):
        entry_price = trade['entry_price']
        side = trade['side']
        qty = trade['qty']
        # --- Додаємо детальне логування для дебагу PNL ---
        logging.info(f"[learn_ai] Trade: {trade['symbol']} | Side: {side} | Entry: {entry_price} | Close: {close_price} | Qty: {qty} | Exit: {exit_type}")

        profit = 0
        if close_price is not None and entry_price is not None:
            if side == 'BUY':
                profit = (close_price - entry_price) * qty
            else:
                profit = (entry_price - close_price) * qty
        else:
            logging.warning(f"Trade info missing open/close price: {close_price}")

        # Оновлення AI-модуля
        self.ai_model.update(
            symbol=trade['symbol'],
            entry=entry_price,
            close=close_price,
            qty=qty,
            profit=profit,
            side=side,
            exit_type=exit_type
        )
        logging.info(f"AI model updated for trade {trade['symbol']} {side}. Profit: {profit:.4f}, Exit type: {exit_type}")

    def close_position(self, symbol: str, quantity: float, side: str):
        """
        Close an open position.
        Args:
            symbol (str): Trading pair symbol.
            quantity (float): Quantity to close.
            side (str): 'BUY' or 'SELL' to close the position.
        """
        ok, reason = can_close_position(self.client, symbol, quantity, side)
        if not ok:
            if "більша за відкриту позицію" in reason:
                import re
                m = re.search(r"відкриту позицію ([\d\.]+) для", reason)
                if m:
                    actual_qty = float(m.group(1))
                    ok2, reason2 = can_close_position(self.client, symbol, actual_qty, side)
                    if ok2:
                        quantity = actual_qty
                    else:
                        logging.error(f"Не можна закрити позицію навіть на актуальну кількість: {reason2}")
                        return None
                else:
                    logging.error(f"Не вдалося визначити фактичну кількість: {reason}")
                    return None
            elif "немає відкритої позиції" in reason:
                logging.info(f"Позиція для {symbol} ({side}) вже закрита або не існує. Нічого робити не потрібно.")
                return None
            else:
                logging.error(f"Не можна закрити позицію: {reason}")
                return None

        try:
            # Округлення кількості при закритті позиції
            quantity_step, _ = self._get_symbol_precisions(symbol)
            quantity = self._round_step(quantity, quantity_step)
            positionSide = "LONG" if side == "BUY" else "SHORT"
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                positionSide=positionSide,
                reduceOnly=True
            )
            logging.info(f"Position closed: {order}")
            return order
        except Exception as e:
            logging.error(f"Error closing position: {e}")
            return None

    def get_open_positions(self, symbol: str = None):
        """
        Retrieve open positions from Binance Futures.
        Args:
            symbol (str): Trading pair symbol (optional).
        Returns:
            list: List of open positions.
        """
        try:
            positions = self.client.futures_position_information()
            if symbol:
                positions = [pos for pos in positions if pos['symbol'] == symbol]
            logging.info(f"Open positions: {positions}")
            return positions
        except Exception as e:
            logging.error(f"Error fetching open positions: {e}")
            return []

    def handle_external_signal(self, signal):
        """
        Handle external trading signals and execute trades accordingly.
        Args:
            signal (dict): Parsed signal containing trading information.
        Returns:
            dict: Order response or None.
        """
        symbol = signal.get('symbol')
        side = signal.get('side')
        quantity = signal.get('quantity')
        stop_loss_price = signal.get('stop_loss_price')
        take_profit_price = signal.get('take_profit_price')
        if not symbol or not side or not quantity or not stop_loss_price or not take_profit_price:
            logging.error("Signal data is incomplete.")
            return None

        # --- ДОДАНО: Перевірка, чи вже є відкрита позиція по цій парі ---
        open_positions = self.get_open_positions(symbol)
        for pos in open_positions:
            if float(pos['positionAmt']) != 0:
                logging.info(f"Відкрита позиція по {symbol} вже існує. Нову не відкриваємо.")
                return None
        # ---------------------------------------------------------------

        return self.place_order(symbol, side, quantity, stop_loss_price, take_profit_price)

    # --- Додано: універсальний метод закриття всіх позицій по символу (LONG і SHORT) ---

    def close_all_positions_for_symbol(self, symbol: str):
        """
        Закрити всі відкриті позиції по символу для LONG та SHORT.
        """
        positions = self.get_open_positions(symbol)
        for pos in positions:
            position_amt = float(pos['positionAmt'])
            if position_amt == 0:
                continue
            side = 'SELL' if position_amt > 0 else 'BUY'
            quantity = abs(position_amt)
            self.close_position(symbol, quantity, side)

    def update(self):
        """
        Основний періодичний метод для виклику в головному циклі:
        1. Перевірити закриття стоп-лосс/тейк-профіт.
        2. Можна додати інші регулярні дії.
        """
        self.check_closed_trades()
