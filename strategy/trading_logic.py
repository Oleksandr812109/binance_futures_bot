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

    def place_order(self, symbol: str, side: str, quantity: float):
        """
        Place a market order on Binance Futures.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            side (str): 'BUY' or 'SELL'.
            quantity (float): Quantity to buy or sell.

        Returns:
            dict: Response from Binance API.
        """
        if quantity <= 0:
            logging.error("Order quantity must be greater than zero.")
            return None

        try:
            # Вказуємо positionSide для Hedge Mode
            positionSide = "LONG" if side == "BUY" else "SHORT"
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                positionSide=positionSide
            )
            logging.info(f"Order placed: {order}")
            return order
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return None

    def close_position(self, symbol: str, quantity: float, side: str):
    """
    Close an open position.

    Args:
        symbol (str): Trading pair symbol.
        quantity (float): Quantity to close.
        side (str): 'BUY' or 'SELL' to close the position.
    """
    # --- Додаткова перевірка перед закриттям ---
    ok, reason = can_close_position(self.client, symbol, quantity, side)
    if not ok:
        logging.error(f"Не можна закрити позицію: {reason}")
        return None

    try:
        # Вказуємо positionSide для Hedge Mode
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
        if not symbol or not side or not quantity:
            logging.error("Signal data is incomplete.")
            return None
        return self.place_order(symbol, side, quantity)

    # --- Додано: універсальний метод закриття всіх позицій по символу (LONG і SHORT) ---
