import logging
from binance.client import Client
from utils.check_margin_and_quantity import can_close_position

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradingLogic:
    def __init__(self, client: Client, risk_management, technical_analysis):
        self.client = client
        self.risk_management = risk_management
        self.technical_analysis = technical_analysis

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

        try:
            positionSide = "LONG" if side == "BUY" else "SHORT"
            # 1. Place entry order
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                positionSide=positionSide
            )
            logging.info(f"Market order placed: {order}")

            # 2. Place stop loss order (reduceOnly)
            stop_loss_order = self.client.futures_create_order(
                symbol=symbol,
                side="SELL" if side == "BUY" else "BUY",
                type="STOP_MARKET",
                stopPrice=stop_loss_price,
                quantity=quantity,
                positionSide=positionSide
            )
            logging.info(f"Stop loss order placed: {stop_loss_order}")

            # 3. Place take profit order (reduceOnly)
            take_profit_order = self.client.futures_create_order(
                symbol=symbol,
                side="SELL" if side == "BUY" else "BUY",
                type="TAKE_PROFIT_MARKET",
                stopPrice=take_profit_price,
                quantity=quantity,
                positionSide=positionSide
            )
            logging.info(f"Take profit order placed: {take_profit_order}")

            return {
                "order": order,
                "stop_loss_order": stop_loss_order,
                "take_profit_order": take_profit_order
            }
        except Exception as e:
            logging.error(f"Error placing bracket orders: {e}")
            return None

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
            positionSide = "LONG" if side == "BUY" else "SHORT"
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                positionSide=positionSide
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
        return self.place_order(symbol, side, quantity, stop_loss_price, take_profit_price)

    # --- Додано: універсальний метод закриття всіх позицій по символу (LONG і SHORT) ---
