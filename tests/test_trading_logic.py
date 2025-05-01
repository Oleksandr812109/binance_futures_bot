import pytest
from unittest.mock import MagicMock
from strategy.trading_logic import TradingLogic
from strategy.risk_management import RiskManagement
from strategy.technical_analysis import TechnicalAnalysis
from binance.client import Client

@pytest.fixture
def mock_binance_client():
    """
    Створення mock-об'єкта для тестування Binance API.
    """
    client = MagicMock(spec=Client)
    return client

@pytest.fixture
def mock_risk_management():
    """
    Створення mock-об'єкта для тестування управління ризиками.
    """
    risk_manager = MagicMock(spec=RiskManagement)
    risk_manager.calculate_position_size.return_value = 0.01  # Приклад розміру позиції
    return risk_manager

@pytest.fixture
def mock_technical_analysis():
    """
    Створення mock-об'єкта для тестування технічного аналізу.
    """
    analysis = MagicMock(spec=TechnicalAnalysis)
    analysis.generate_optimized_signals.return_value = [
        {"timestamp": "2025-05-01T10:00:00", "close": 30000, "Signal": "Buy"},
        {"timestamp": "2025-05-01T11:00:00", "close": 31000, "Signal": "Sell"}
    ]
    return analysis

@pytest.fixture
def trading_logic(mock_binance_client, mock_risk_management, mock_technical_analysis):
    """
    Створення об'єкта торгової логіки для тестування.
    """
    return TradingLogic(mock_binance_client, mock_risk_management, mock_technical_analysis)

def test_generate_signals(mock_technical_analysis, trading_logic):
    """
    Тест генерації сигналів на основі технічного аналізу.
    """
    signals = trading_logic.get_trading_signals()
    assert len(signals) == 2, "Сигнали повинні містити 2 записи"
    assert signals[0]["Signal"] == "Buy", "Перший сигнал має бути 'Buy'"
    assert signals[1]["Signal"] == "Sell", "Другий сигнал має бути 'Sell'"

def test_place_order(mock_binance_client, trading_logic):
    """
    Тест створення ордера на основі сигналу.
    """
    # Мок для створення ордера
    mock_binance_client.create_order.return_value = {
        "symbol": "BTCUSDT",
        "orderId": 12345,
        "status": "FILLED"
    }

    order = trading_logic.place_order("BTCUSDT", "BUY", 0.01)

    assert order["status"] == "FILLED", "Ордер має бути виконаний"
    mock_binance_client.create_order.assert_called_once_with(
        symbol="BTCUSDT",
        side="BUY",
        type="MARKET",
        quantity=0.01
    )

def test_risk_management_integration(mock_risk_management, trading_logic):
    """
    Тест інтеграції управління ризиками з торговою логікою.
    """
    position_size = trading_logic.calculate_position_size(50)  # Наприклад, 50 - це стоп-лосс
    assert position_size == 0.01, "Розмір позиції має бути 0.01"
    mock_risk_management.calculate_position_size.assert_called_once_with(50)

def test_handle_insufficient_balance(mock_binance_client, trading_logic):
    """
    Тест обробки недостатнього балансу.
    """
    # Мок для помилки балансу
    mock_binance_client.create_order.side_effect = Exception("Insufficient balance")

    with pytest.raises(Exception, match="Insufficient balance"):
        trading_logic.place_order("BTCUSDT", "BUY", 1)  # Спробуємо купити більше, ніж дозволяє баланс
