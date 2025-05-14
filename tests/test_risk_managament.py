import pytest
from strategy.risk_management import RiskManagement

@pytest.fixture
def risk_management():
    return RiskManagement(account_balance=10000, risk_per_trade=0.01, max_drawdown=0.2)

def test_calculate_volatility(risk_management):
    price_data = [100, 102, 101, 105, 110, 108, 107, 109, 111, 110, 108, 107, 106, 105]
    volatility = risk_management.calculate_volatility(price_data, window=5)
    assert volatility > 0, "Volatility should be greater than 0"

def test_calculate_position_size_with_volatility(risk_management):
    stop_loss_distance = 50
    volatility = 0.05
    position_size = risk_management.calculate_position_size(stop_loss_distance, volatility)
    assert position_size > 0, "Position size should be greater than 0"
