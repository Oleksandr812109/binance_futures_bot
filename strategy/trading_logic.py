import logging


class TradingLogic:
    def __init__(self, order_manager, risk_management, technical_analysis):
        """
        Initialize the Trading Logic system.

        Args:
            order_manager: Instance of OrderManager for placing orders.
            risk_management: RiskManagement instance.
            technical_analysis: TechnicalAnalysis instance.
        """
        self.order_manager = order_manager
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
        logging.info(f"Generated trading signals: {signals}")
        return signals

    def place_order(self, symbol, side, quantity):
        """
        Place a trading order.

        Args:
            symbol (str): Trading pair (e.g., 'BTCUSDT').
            side (str): Order side ('BUY' or 'SELL').
            quantity (float): Order quantity.

        Returns:
            dict or None: Order details if successful, otherwise None.
        """
        try:
            logging.info(f"Attempting to place order: Symbol={symbol}, Side={side}, Quantity={quantity}")
            order = self.order_manager.create_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',  # Use MARKET orders for simplicity
                quantity=quantity
            )
            logging.info(f"Order placed successfully: {order}")
            return order
        except Exception as e:
            logging.error(f"Error placing order for Symbol={symbol}, Side={side}, Quantity={quantity}: {e}")
            return None

    def execute_trading_strategy(self):
        """
        Execute the trading strategy based on generated signals.
        """
        signals = self.get_trading_signals()
        for signal in signals:
            symbol = signal.get('symbol')
            side = signal.get('side')
            quantity = signal.get('quantity')

            # Validate signal data
            if not symbol or not side or not quantity or quantity <= 0:
                logging.warning(f"Invalid signal: {signal}")
                continue

            logging.info(f"Processing signal: {signal}")
            order_result = self.place_order(symbol, side, quantity)
            if order_result:
                logging.info(f"Order executed successfully: {order_result}")
            else:
                logging.error(f"Failed to execute order for signal: {signal}")
