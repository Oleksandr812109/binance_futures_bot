import random

def dumb_strategy_signal(data_row):
    """
    Дуже проста стратегія для генерації історії:
    - LONG якщо RSI < 30
    - SHORT якщо RSI > 70
    - Інакше - нічого не робити
    Якщо у ваших даних немає RSI, використайте random.choice([1, -1, 0])
    """
    if "RSI" in data_row:
        if data_row["RSI"] < 30:
            return 1  # LONG
        elif data_row["RSI"] > 70:
            return -1  # SHORT
        else:
            return 0   # Нічого не робити
    # fallback: випадкове рішення
    return random.choice([1, -1, 0])
