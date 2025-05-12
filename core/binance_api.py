# Оновлений файл для взаємодії з Binance API через ccxt
import ccxt


class BinanceAPI:
    def __init__(self, api_key, api_secret):
        self.client = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
        })

    def get_balance(self):
        return self.client.fetch_balance()

    def create_order(self, symbol, order_type, side, amount, price=None):
        if order_type == 'market':
            return self.client.create_market_order(symbol, side, amount)
        elif order_type == 'limit':
            return self.client.create_limit_order(symbol, side, amount, price)
        else:
            raise ValueError("Unsupported order type")

