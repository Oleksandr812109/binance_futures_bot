from binance.client import Client
from binance.exceptions import BinanceAPIException
import logging
import traceback
import math

def create_order(client, symbol, side, order_type, quantity):
    """
    Create an order on Binance Futures.

    Args:
        client (Client): Binance API client object.
        symbol (str): Trading pair symbol, e.g., 'BTCUSDT'.
        side (str): 'BUY' or 'SELL'.
        order_type (str): 'MARKET', 'LIMIT', etc.
        quantity (float): Quantity of the asset to trade.

    Returns:
        dict or None: Order details if successful, otherwise None.
    """
    try:
        # Перевірка параметрів перед відправкою ордера
        if (
            quantity is None
            or type(quantity) not in [int, float]
            or math.isnan(quantity)
            or math.isinf(quantity)
            or quantity <= 0
            or order_type is None
        ):
            logging.error(f"Invalid order parameters: symbol={symbol}, side={side}, order_type={order_type}, quantity={quantity}")
            return None

        logging.info(f"Placing {order_type} order for {symbol}: {side}, Quantity: {quantity}")

        # Додаємо positionSide для Hedge Mode
        positionSide = "LONG" if side == "BUY" else "SHORT"

        # Create the order
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            positionSide=positionSide
        )

        logging.info(f"Order placed successfully: {order}")
        return order

    except BinanceAPIException as e:
        logging.error(f"Binance API Exception while placing order: {e}")
        logging.debug(traceback.format_exc())
        return None

    except Exception as e:
        logging.error(f"Unexpected error while placing order: {e}")
        logging.debug(traceback.format_exc())
        return None
