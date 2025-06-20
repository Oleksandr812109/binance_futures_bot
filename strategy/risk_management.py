import logging
from typing import Dict
from binance.client import Client
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RiskManagement:
    def __init__(self, client: Client, config_path: str = 'risk_config.json'):
        self.client = client
        self.config_path = config_path
        self._load_config()
        self.account_balance = 0.0  # Ініціалізуємо, значення встановить update_account_balance
        self.initial_balance = 1.0  # Значення також оновиться після першого оновлення балансу

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            self.risk_per_trade: Dict[str, float] = config.get('risk_per_trade', {})
            self.default_risk_per_trade_percent: float = config.get('default_risk_per_trade_percent', 0.01)
            self.max_drawdown: float = config.get('max_drawdown', 0.2)
            logging.info(f"Risk configuration loaded from {self.config_path}")
        except FileNotFoundError:
            logging.error(f"Config file not found at {self.config_path}. Using default risk settings.")
            self.risk_per_trade = {
                'BTCUSDT': 0.01,
                'ETHUSDT': 0.005,
                'BNBUSDT': 0.01,
                'SOLUSDT': 0.015,
                'ADAUSDT': 0.012,
            }
            self.default_risk_per_trade_percent = 0.01
            self.max_drawdown = 0.2
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {self.config_path}: {e}. Using default risk settings.")
            self.risk_per_trade = {}
            self.default_risk_per_trade_percent = 0.01
            self.max_drawdown = 0.2

    def calculate_position_size(self, symbol: str, current_price: float, stop_loss_price: float, volatility: float = None) -> float:
        """
        Розраховує розмір позиції на основі ризику, ціни входу, стоп-лоссу, та волатильності (ATR).
        Якщо передати volatility (ATR), то stop_loss_price має бути розрахований з урахуванням ATR за межами цієї функції!
        """
        if current_price <= 0 or stop_loss_price <= 0:
            logging.error("Current price and stop-loss price must be greater than zero.")
            return 0
        stop_loss_distance_abs = abs(current_price - stop_loss_price)
        if stop_loss_distance_abs == 0:
            logging.error("Stop-loss price cannot be equal to current price. Stop-loss distance is zero.")
            return 0

        risk_pt_percent = self.risk_per_trade.get(symbol, self.default_risk_per_trade_percent)
        risk_amount_usd = self.account_balance * risk_pt_percent
        position_size_base_asset = risk_amount_usd / stop_loss_distance_abs
        logging.info(
            f"{symbol} | Risked amount: ${risk_amount_usd:.2f} | Stop-loss distance: ${stop_loss_distance_abs:.2f} | Calculated position size: {position_size_base_asset:.5f}"
        )
        return position_size_base_asset

    def check_drawdown_limit(self) -> bool:
        if self.initial_balance <= 0:
            logging.warning("Initial balance is zero or less, cannot calculate drawdown. Returning True (no limit exceeded).")
            return True
        current_drawdown = 1 - (self.account_balance / self.initial_balance)
        logging.info(
            f"Current balance: ${self.account_balance:.2f}, Initial balance: ${self.initial_balance:.2f} | Current drawdown: {current_drawdown * 100:.2f}%, Max drawdown: {self.max_drawdown * 100:.2f}%"
        )
        if current_drawdown > self.max_drawdown:
            logging.critical(
                f"MAX DRAWDOWN LIMIT EXCEEDED! Current: {current_drawdown * 100:.2f}%, Max: {self.max_drawdown * 100:.2f}%"
            )
            return False
        return True

    def update_account_balance(self, new_balance: float):
        if new_balance < 0:
            logging.error("Attempted to set account balance to a negative value.")
            return
        if new_balance != self.account_balance:
            logging.info(f"Account balance updated from {self.account_balance:.2f} to {new_balance:.2f}")
        self.account_balance = new_balance
        # Оновлюємо initial_balance, якщо це перше оновлення
        if self.initial_balance == 1.0 or self.initial_balance == 0.0:
            self.initial_balance = new_balance if new_balance > 0 else 1.0
            if self.initial_balance == 1.0 and self.account_balance == 0.0:
                logging.warning("Initial balance set to 1.0 to avoid division by zero. Please ensure proper balance fetching.")

# === MAIN ТЕСТ ===
if __name__ == "__main__":
    class MockBinanceClient:
        def futures_account_balance(self):
            return [
                {'asset': 'USDT', 'walletBalance': '1000.00', 'balance': '990.00'},
                {'asset': 'BTC', 'walletBalance': '0.05', 'balance': '0.05'}
            ]
    mock_client = MockBinanceClient()
    test_config = {
        "risk_per_trade": {
            "BTCUSDT": 0.01,
            "ETHUSDT": 0.008,
            "SOLUSDT": 0.012
        },
        "default_risk_per_trade_percent": 0.005,
        "max_drawdown": 0.15
    }
    with open('risk_config.json', 'w') as f:
        json.dump(test_config, f, indent=4)
    rm = RiskManagement(mock_client, config_path='risk_config.json')
    # Тестове оновлення балансу
    rm.update_account_balance(1000.0)
    print("\n--- Тестування розміру позиції (приклад зі стороннім ATR) ---")
    # Для прикладу, отримуємо ATR із зовнішнього модуля (наприклад, TechnicalAnalysis)
    btc_current_price = 70750
    btc_atr = 800  # У реальному коді отримати через TechnicalAnalysis.get_latest_atr('BTCUSDT')
    btc_stop_loss_price = btc_current_price - btc_atr
    btc_position_size = rm.calculate_position_size('BTCUSDT', btc_current_price, btc_stop_loss_price, volatility=btc_atr)
    print(f"Розмір позиції для BTCUSDT (ATR SL): {btc_position_size:.5f} BTC")
