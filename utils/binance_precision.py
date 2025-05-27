import math

def get_precision(symbol_info, key):
    """
    Отримати кількість знаків після коми для stepSize або tickSize (quantity/price)
    """
    for f in symbol_info['filters']:
        if key == "quantity":
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                return int(round(-math.log(step_size, 10)))
        elif key == "price":
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = float(f['tickSize'])
                return int(round(-math.log(tick_size, 10)))
    return 8  # дефолт

def round_quantity(value, precision):
    return float(f"{{:.{precision}f}}".format(value))

def round_price(value, precision):
    return float(f"{{:.{precision}f}}".format(value))
