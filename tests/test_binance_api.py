import pytest
from binance.client import Client
from unittest.mock import MagicMock

@pytest.fixture
def mock_binance_client():
    """
    Create a mock Binance client for testing purposes.
    """
    client = MagicMock(spec=Client)
    return client

def test_get_account_balance(mock_binance_client):
    """
    Test retrieving account balance using a mock Binance client.
    """
    # Mock the response for get_asset_balance
    mock_binance_client.get_asset_balance.return_value = {'free': '100.0', 'locked': '0.0'}

    # Call the method
    asset = "USDT"
    balance = mock_binance_client.get_asset_balance(asset=asset)

    # Assertions
    assert balance['free'] == '100.0', "Free balance should be 100.0"
    assert balance['locked'] == '0.0', "Locked balance should be 0.0"
    mock_binance_client.get_asset_balance.assert_called_once_with(asset=asset)

def test_create_market_order(mock_binance_client):
    """
    Test creating a market order using a mock Binance client.
    """
    # Mock the response for create_order
    mock_binance_client.create_order.return_value = {
        'symbol': 'BTCUSDT',
        'orderId': 12345,
        'status': 'FILLED',
        'side': 'BUY',
        'type': 'MARKET',
        'executedQty': '0.001'
    }

    # Call the method
    symbol = "BTCUSDT"
    side = "BUY"
    quantity = 0.001
    order = mock_binance_client.create_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=quantity
    )

    # Assertions
    assert order['symbol'] == 'BTCUSDT', "Symbol should be BTCUSDT"
    assert order['side'] == 'BUY', "Order side should be BUY"
    assert order['type'] == 'MARKET', "Order type should be MARKET"
    assert order['status'] == 'FILLED', "Order status should be FILLED"
    assert order['executedQty'] == '0.001', "Executed quantity should be 0.001"
    mock_binance_client.create_order.assert_called_once_with(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=quantity
    )

def test_get_order_status(mock_binance_client):
    """
    Test retrieving order status using a mock Binance client.
    """
    # Mock the response for get_order
    mock_binance_client.get_order.return_value = {
        'orderId': 12345,
        'status': 'FILLED',
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'type': 'MARKET'
    }

    # Call the method
    symbol = "BTCUSDT"
    order_id = 12345
    order_status = mock_binance_client.get_order(
        symbol=symbol,
        orderId=order_id
    )

    # Assertions
    assert order_status['orderId'] == 12345, "Order ID should be 12345"
    assert order_status['status'] == 'FILLED', "Order status should be FILLED"
    assert order_status['symbol'] == 'BTCUSDT', "Symbol should be BTCUSDT"
    mock_binance_client.get_order.assert_called_once_with(
        symbol=symbol,
        orderId=order_id
    )
