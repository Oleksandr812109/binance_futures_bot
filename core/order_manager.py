import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException


class OrderManager:
    def __init__(self, api_key, api_secret, testnet=False):
        """Ініціалізація клієнта Binance."""
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def create_order(self, symbol, side, order_type, quantity, price=None):
        """
        Створення нового ордера.
        :param symbol: Наприклад, 'BTCUSDT'
        :param side: 'BUY' або 'SELL'
        :param order_type: 'LIMIT', 'MARKET', тощо
        :param quantity: Кількість активів
        :param price: Ціна для лімітного ордера (необов'язково для ринкових ордерів)
        :return: Інформація про створений ордер
        """
        try:
            self.logger.info(f"Запит на створення ордера: symbol={symbol}, side={side}, type={order_type}, quantity={quantity}, price={price}")
            if order_type == 'LIMIT':
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=order_type,
                    timeInForce='GTC',  # Good Till Cancelled
                    quantity=quantity,
                    price=price
                )
            elif order_type == 'MARKET':
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type=order_type,
                    quantity=quantity
                )
            else:
                raise ValueError("Непідтримуваний тип ордера")

            self.logger.info(f"Ордер створено успішно: {order}")
            return order

        except BinanceAPIException as e:
            self.logger.error(f"Помилка створення ордера: {e}")
            self.logger.debug(f"Деталі запиту: symbol={symbol}, side={side}, type={order_type}, quantity={quantity}, price={price}")
            raise e

    def cancel_order(self, symbol, order_id):
        """
        Скасування ордера.
        :param symbol: Наприклад, 'BTCUSDT'
        :param order_id: ID ордера, який потрібно скасувати
        :return: Інформація про скасований ордер
        """
        try:
            self.logger.info(f"Запит на скасування ордера: symbol={symbol}, order_id={order_id}")
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            self.logger.info(f"Ордер скасовано успішно: {result}")
            return result
        except BinanceAPIException as e:
            self.logger.error(f"Помилка скасування ордера: {e}")
            self.logger.debug(f"Деталі запиту: symbol={symbol}, order_id={order_id}")
            raise e

    def get_order_status(self, symbol, order_id):
        """
        Отримання статусу ордера.
        :param symbol: Наприклад, 'BTCUSDT'
        :param order_id: ID ордера
        :return: Інформація про статус ордера
        """
        try:
            self.logger.info(f"Запит на отримання статусу ордера: symbol={symbol}, order_id={order_id}")
            status = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            self.logger.info(f"Статус ордера отримано успішно: {status}")
            return status
        except BinanceAPIException as e:
            self.logger.error(f"Помилка отримання статусу ордера: {e}")
            self.logger.debug(f"Деталі запиту: symbol={symbol}, order_id={order_id}")
            raise e
