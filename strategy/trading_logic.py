import logging

class TradingLogic:
    def __init__(self, client, risk_management, technical_analysis):
        """
        Initialize the Trading Logic system.

        Args:
            client: Binance client instance.
            risk_management: RiskManagement instance.
            technical_analysis: TechnicalAnalysis instance.
        """
        self.client = client
        self.risk_management = risk_management
        self.technical_analysis = technical_analysis
        logging.info("TradingLogic initialized successfully.")

    def get_trading_signals(self):
        """
        Generate trading signals based on technical analysis.

        Returns:
            list: List of trading signals.
        """
        signals = self.technical_analysis.generate_optimized_signals()
        return signals

    def place_order(self, symbol, side, quantity):
        """
        Place a trading order.

        Args:
            symbol (str): Trading pair (e.g., 'BTCUSDT').
            side (str): Order side ('BUY' or 'SELL').
            quantity (float): Order quantity.

        Returns:
            dict: Order details.
        """
        order = self.client.create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity
        )
        logging.info(f"Order placed: {order}")
        return order
