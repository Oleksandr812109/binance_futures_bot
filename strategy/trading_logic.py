import logging
from binance.client import Client

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

        Returns:
            dict: Response from Binance API.
        """
        if quantity <= 0:
            logging.error("Close quantity must be greater than zero.")
            return None

        try:
            # Вказуємо positionSide для Hedge Mode
            positionSide = "LONG" if side == "BUY" else "SHORT"
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                reduceOnly=True,
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
    def close_all_positions(self, symbol: str):
        """
        Close all open positions (both LONG and SHORT) for a given symbol.
        Useful for emergency exit or full reset.

        Args:
            symbol (str): Trading pair symbol.

        Returns:
            list: List of close order responses.
        """
        try:
            close_orders = []
            positions = self.get_open_positions(symbol=symbol)
            for pos in positions:
                amt = float(pos["positionAmt"])
                if amt == 0:
                    continue
                # Якщо позиція LONG (amt > 0): треба SELL; якщо SHORT (amt < 0): треба BUY
                close_side = "SELL" if amt > 0 else "BUY"
                quantity = abs(amt)
                response = self.close_position(symbol, quantity, close_side)
                close_orders.append(response)
            if close_orders:
                logging.info(f"All positions for {symbol} closed: {close_orders}")
            else:
                logging.info(f"No open positions to close for {symbol}.")
            return close_orders
        except Exception as e:
            logging.error(f"Error closing all positions for {symbol}: {e}")
            return []
