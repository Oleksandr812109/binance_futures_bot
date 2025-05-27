import configparser
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT
import logging
import traceback
from binance.client import Client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BinanceOrderManager:
    def __init__(self, client: Client):
        """
        Initialize the Binance Order Manager.

        Args:
            client (Client): An initialized and authenticated Binance Client instance.
        """
        self.client = client
        logging.info("Binance Order Manager initialized with provided Binance client.")

    def get_account_balance(self, asset: str = "USDT") -> float:
        """
        Get the balance of a specific asset.

        Args:
            asset (str): The asset symbol (e.g., 'USDT').

        Returns:
            float: The balance of the specified asset.
        """
        try:
            # For futures, use futures_account_balance
            balance_list = self.client.futures_account_balance()
            for balance in balance_list:
                if balance['asset'] == asset:
                    logging.info(f"Balance for {asset}: {balance['balance']}")
                    return float(balance['balance'])
            logging.warning(f"No balance available for {asset}. Returning 0.0.")
            return 0.0
        except Exception as e:
            logging.error(f"Error fetching balance for {asset}: {e}")
            logging.debug(traceback.format_exc())
            return 0.0

    def create_market_order(self, symbol: str, side: str, quantity: float):
        """
        Create a market order.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            side (str): 'BUY' or 'SELL'.
            quantity (float): Quantity to buy or sell.

        Returns:
            dict: Response from Binance API.
        """
        if quantity <= 0:
            logging.error("Quantity must be greater than 0")
            return None
        if not symbol or not side:
            logging.error("Symbol and side must not be empty")
            return None

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY if side.upper() == 'BUY' else SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logging.info(f"Market order created successfully: {order}")
            return order
        except Exception as e:
            logging.error(f"Error creating market order: {e}")
            logging.debug(traceback.format_exc())
            return None

    def create_limit_order(self, symbol: str, side: str, quantity: float, price: float, time_in_force: str = "GTC"):
        """
        Create a limit order.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            side (str): 'BUY' or 'SELL'.
            quantity (float): Quantity to buy or sell.
            price (float): Limit price.
            time_in_force (str): Time in force policy.

        Returns:
            dict: Response from Binance API.
        """
        if quantity <= 0:
            logging.error("Quantity must be greater than 0")
            return None
        if not symbol or not side:
            logging.error("Symbol and side must not be empty")
            return None

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY if side.upper() == 'BUY' else SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=price,
                timeInForce=time_in_force
            )
            logging.info(f"Limit order created successfully: {order}")
            return order
        except Exception as e:
            logging.error(f"Error creating limit order: {e}")
            logging.debug(traceback.format_exc())
            return None

    def cancel_order(self, symbol: str, order_id: int):
        """
        Cancel an active order.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            order_id (int): ID of the order to be canceled.

        Returns:
            dict: Response from Binance API.
        """
        try:
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logging.info(f"Order {order_id} canceled: {result}")
            return result
        except Exception as e:
            logging.error(f"Error cancelling order {order_id}: {e}")
            logging.debug(traceback.format_exc())
            return None

    def get_open_orders(self, symbol: str = None):
        """
        Retrieve all open orders for a symbol or all symbols if not specified.

        Args:
            symbol (str): Trading pair symbol (optional).

        Returns:
            list: List of open orders.
        """
        try:
            if symbol:
                orders = self.client.futures_get_open_orders(symbol=symbol)
            else:
                orders = self.client.futures_get_open_orders()
            logging.info(f"Open orders: {orders}")
            return orders
        except Exception as e:
            logging.error(f"Error fetching open orders: {e}")
            logging.debug(traceback.format_exc())
            return []

    def get_order_status(self, symbol: str, order_id: int):
        """
        Get the status of an order.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            order_id (int): ID of the order.

        Returns:
            dict: Response from Binance API.
        """
        try:
            status = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            logging.info(f"Order status for order {order_id}: {status}")
            return status
        except Exception as e:
            logging.error(f"Error fetching order status for order {order_id}: {e}")
            logging.debug(traceback.format_exc())
            return None
