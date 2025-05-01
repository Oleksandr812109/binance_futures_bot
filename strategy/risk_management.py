import logging
from typing import List, Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RiskManagement:
    def __init__(self, account_balance: float, risk_per_trade: float = 0.01, max_drawdown: float = 0.2):
        """
        Initialize the Risk Management system.

        Args:
            account_balance (float): Total account balance.
            risk_per_trade (float): Percentage of account balance to risk per trade.
            max_drawdown (float): Maximum allowable percentage drawdown before stopping trading.
        """
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.max_drawdown = max_drawdown
        self.initial_balance = account_balance  # Track the initial balance for drawdown calculation
        logging.info(f"Risk Management initialized with account balance: {account_balance}, risk per trade: {risk_per_trade * 100:.2f}%, max drawdown: {max_drawdown * 100:.2f}%")

    def calculate_position_size(self, stop_loss_distance: float) -> float:
        """
        Calculate the position size based on account balance, risk per trade, and stop-loss distance.

        Args:
            stop_loss_distance (float): Distance between entry price and stop-loss price.

        Returns:
            float: Calculated position size.
        """
        if stop_loss_distance <= 0:
            logging.error("Stop-loss distance must be greater than zero.")
            return 0
        risk_amount = self.account_balance * self.risk_per_trade
        position_size = risk_amount / stop_loss_distance
        logging.info(f"Calculated position size: {position_size:.2f} with stop-loss distance: {stop_loss_distance}")
        return position_size

    def calculate_stop_loss(self, entry_price: float, max_loss: float) -> float:
        """
        Calculate the stop-loss price based on entry price and maximum allowable loss.

        Args:
            entry_price (float): The entry price of the position.
            max_loss (float): Maximum loss allowed for the trade.

        Returns:
            float: Calculated stop-loss price.
        """
        if max_loss <= 0 or entry_price <= 0:
            logging.error("Max loss and entry price must be greater than zero.")
            return 0
        stop_loss_price = entry_price - max_loss
        logging.info(f"Calculated stop-loss price: {stop_loss_price} for entry price: {entry_price} and max loss: {max_loss}")
        return stop_loss_price

    def evaluate_portfolio_risk(self, open_positions: List[Dict[str, float]], max_portfolio_risk: float = 0.05) -> bool:
        """
        Evaluate if the total portfolio risk exceeds the maximum allowable risk.

        Args:
            open_positions (List[Dict[str, float]]): List of dictionaries with details of open positions (e.g., risk per position).
            max_portfolio_risk (float): Maximum allowable risk for the portfolio.

        Returns:
            bool: True if portfolio risk is within limits, False otherwise.
        """
        total_risk = sum(position['risk'] for position in open_positions)
        logging.info(f"Total portfolio risk: {total_risk:.2f}, Max allowable risk: {max_portfolio_risk:.2f}")
        return total_risk <= max_portfolio_risk

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

if __name__ == "__main__":
    # Example usage
    account_balance = 10000  # Example account balance
    risk_manager = RiskManagement(account_balance, risk_per_trade=0.01, max_drawdown=0.2)

    # Example calculations
    stop_loss_distance = 50  # Example stop-loss distance in price units
    position_size = risk_manager.calculate_position_size(stop_loss_distance)

    entry_price = 150
    max_loss = 100
    stop_loss_price = risk_manager.calculate_stop_loss(entry_price, max_loss)

    # Evaluate portfolio risk
    open_positions = [
        {"risk": 0.01},
        {"risk": 0.02},
        {"risk": 0.01},
    ]
    portfolio_ok = risk_manager.evaluate_portfolio_risk(open_positions)
    logging.info(f"Portfolio risk within limits: {portfolio_ok}")

    # Update balance and check drawdown
    risk_manager.update_account_balance(9000)  # Example of a balance update after a losing trade
    drawdown_ok = risk_manager.check_drawdown_limit()
    logging.info(f"Drawdown within limits: {drawdown_ok}")
