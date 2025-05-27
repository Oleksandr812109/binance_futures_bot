import logging
import numpy as np
from typing import List, Dict
from binance.client import Client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RiskManagement:
    def __init__(self, client: Client, risk_per_trade: float = 0.1, max_drawdown: float = 0.2):
        """
        Initialize the Risk Management system.

        Args:
            client (Client): Binance API client.
            risk_per_trade (float): Percentage of account balance to risk per trade.
            max_drawdown (float): Maximum allowable percentage drawdown before stopping trading.
        """
        self.client = client
        self.risk_per_trade = risk_per_trade
        self.max_drawdown = max_drawdown
        self.account_balance = self.get_account_balance()
        self.initial_balance = self.account_balance  # Track the initial balance for drawdown calculation

    def get_account_balance(self, asset="USDT"):
        """
        Fetch the account balance from Binance.

        Args:
            asset (str): The asset symbol (e.g., 'USDT').

        Returns:
            float: The balance of the specified asset.
        """
        try:
            # Використовуємо метод futures_account_balance для Binance Futures
            balance_list = self.client.futures_account_balance()
            for balance in balance_list:
                if balance['asset'] == asset:
                    return float(balance['balance'])
        except Exception as e:
            logging.error(f"Error fetching balance for {asset}: {e}")
        return 0.0

    def calculate_volatility(self, price_data: List[float], window: int = 14) -> float:
        """
        Calculate the volatility of an asset using standard deviation.

        Args:
            price_data (List[float]): List of historical prices.
            window (int): Lookback window for calculating volatility.

        Returns:
            float: Calculated volatility.
        """
        if len(price_data) < window:
            logging.error("Not enough data to calculate volatility.")
            return 0.0

        rolling_std = np.std(price_data[-window:])
        logging.info(f"Calculated volatility (standard deviation) over window {window}: {rolling_std:.2f}")
        return rolling_std

    def calculate_position_size(self, stop_loss_distance: float, volatility: float = None) -> float:
        """
        Calculate the position size based on account balance, risk per trade, stop-loss distance,
        and optionally asset volatility.

        Args:
            stop_loss_distance (float): Distance between entry price and stop-loss price.
            volatility (float): Asset volatility (optional).

        Returns:
            float: Calculated position size.
        """
        if stop_loss_distance <= 0:
            logging.error("Stop-loss distance must be greater than zero.")
            return 0

        # Adjust risk per trade based on volatility (optional)
        adjusted_risk_per_trade = self.risk_per_trade
        if volatility:
            adjusted_risk_per_trade = min(self.risk_per_trade, 1 / (1 + volatility))
            logging.info(f"Adjusted risk per trade based on volatility {volatility:.2f}: {adjusted_risk_per_trade:.2f}")

        risk_amount = self.account_balance * adjusted_risk_per_trade
        position_size = risk_amount / stop_loss_distance
        logging.info(f"Calculated position size: {position_size:.2f} with stop-loss distance: {stop_loss_distance}")
        return position_size

    def check_drawdown_limit(self) -> bool:
        """
        Check if the account balance has exceeded the maximum allowable drawdown.

        Returns:
            bool: True if drawdown is within the limit, False otherwise.
        """
        current_drawdown = 1 - (self.account_balance / self.initial_balance)
        logging.info(f"Current drawdown: {current_drawdown * 100:.2f}%, Max drawdown: {self.max_drawdown * 100:.2f}%")
        return current_drawdown <= self.max_drawdown

    def update_account_balance(self, new_balance: float):
        """
        Update the account balance after a trade.

        Args:
            new_balance (float): The updated account balance.
        """
        if new_balance < 0:
            logging.error("Account balance cannot be negative.")
            return
        self.account_balance = new_balance
        logging.info(f"Account balance updated to: {new_balance}")
