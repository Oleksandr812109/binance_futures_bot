import configparser
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BinanceOrderManager:
    def __init__(self, config_path: str, testnet: bool = True):
        """
        Initialize the Binance Order Manager.

        Args:
            config_path (str): Path to the configuration file (config.ini).
            testnet (bool): Whether to use Binance Testnet.
        """
        # Load API keys from config file
        config = configparser.ConfigParser()
        config.read(config_path)
        api_key = config.get('BINANCE', 'API_KEY')
        api_secret = config.get('BINANCE', 'API_SECRET')

        if testnet:
            self.client = Client(api_key, api_secret, testnet=True)
            self.client.API_URL = 'https://testnet.binance.vision/api'  # Testnet URL
            logging.info("Using Binance Testnet API")
        else:
            self.client = Client(api_key, api_secret)
            logging.info("Using Binance Live API")

        logging.info("Binance Order Manager initialized with keys from config file.")

    def get_account_balance(self, asset: str = "USDT") -> float:
        """
        Get the balance of a specific asset.

        Args:
            asset (str): The asset symbol (e.g., 'USDT').

        Returns:
            float: The balance of the specified asset.
        """
        try:
            balance = self.client.get_asset_balance(asset=asset)
            if balance and float(balance['free']) > 0:
                logging.info(f"Balance for {asset}: {balance['free']}")
                return float(balance['free'])
            else:
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
            order = self.client.create_order(
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
            price (float): Price for the limit order.
            time_in_force (str): Time in force ('GTC', 'IOC', etc.).

        Returns:
            dict: Response from Binance API.
        """
        if quantity <= 0 or price <= 0:
            logging.error("Quantity and price must be greater than 0")
            return None
        if not symbol or not side:
            logging.error("Symbol and side must not be empty")
            return None

        try:
            order = self.client.create_order(
                symbol=symbol,
                side=SIDE_BUY if side.upper() == 'BUY' else SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                timeInForce=time_in_force,
                quantity=quantity,
                price=str(price)
            )
            logging.info(f"Limit order created successfully: {order}")
            return order
        except Exception as e:
            logging.error(f"Error creating limit order: {e}")
            logging.debug(traceback.format_exc())
            return None

    def get_order_status(self, symbol: str, order_id: int):
        """
        Get the status of an order.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            order_id (int): ID of the order.

        Returns:
            dict: Order status from Binance API.
        """
        try:
            order_status = self.client.get_order(symbol=symbol, orderId=order_id)
            logging.info(f"Order status: {order_status}")
            return order_status
        except Exception as e:
            logging.error(f"Error fetching order status: {e}")
            logging.debug(traceback.format_exc())
            return None

    def cancel_order(self, symbol: str, order_id: int):
        """
        Cancel an active order.

        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT').
            order_id (int): ID of the order to cancel.

        Returns:
            dict: Response from Binance API.
        """
        try:
            cancel_response = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logging.info(f"Order cancelled successfully: {cancel_response}")
            return cancel_response
        except Exception as e:
            logging.error(f"Error cancelling order: {e}")
            logging.debug(traceback.format_exc())
            return None


if __name__ == "__main__":
    # Example usage
    CONFIG_PATH = "config.ini"  # Path to your config.ini file
    TESTNET = True

    manager = BinanceOrderManager(CONFIG_PATH, TESTNET)

    # Example: Get balance
    usdt_balance = manager.get_account_balance("USDT")

    # Example: Create a market order
    market_order = manager.create_market_order("BTCUSDT", "BUY", 0.001)

    # Example: Create a limit order
    limit_order = manager.create_limit_order("BTCUSDT", "SELL", 0.001, 30000)

    # Example: Get order status
    if market_order:
        order_status = manager.get_order_status("BTCUSDT", market_order['orderId'])

    # Example: Cancel an order
    if limit_order:
        cancel_response = manager.cancel_order("BTCUSDT", limit_order['orderId'])
