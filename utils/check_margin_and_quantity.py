def can_close_position(client, symbol, quantity, side):
    """
    Додаткова перевірка перед закриттям позиції:
    - чи є відкрита позиція потрібного розміру
    - чи вистачає доступної маржі (USDT)
    - чи немає відкритих ордерів, які заважають закриттю
    Повертає (True, "") якщо все ок, або (False, причина)
    """
    try:
        # 1. Перевіряємо актуальний розмір відкритої позиції
        positions = client.futures_position_information(symbol=symbol)
        actual_qty = 0
        for pos in positions:
            amt = float(pos["positionAmt"])
            if (side == "BUY" and amt > 0) or (side == "SELL" and amt < 0):
                actual_qty = abs(amt)
                break

        if actual_qty == 0:
            return False, f"На біржі немає відкритої позиції для {symbol} ({side})"

        if quantity > actual_qty:
            return False, f"Запитана кількість {quantity} більша за відкриту позицію {actual_qty} для {symbol}"

        # 2. Перевіряємо наявність відкритих ордерів на цьому символі (вони резервують маржу)
        open_orders = client.futures_get_open_orders(symbol=symbol)
        if open_orders:
            return False, f"Є відкриті ордери по {symbol}, які можуть резервувати маржу"

        # 3. Перевіряємо доступну маржу (USDT)
        balance = client.futures_account_balance()
        available_balance = 0.0
        for b in balance:
            if b["asset"] == "USDT":
                available_balance = float(b["availableBalance"])
                break

        # опціонально: додай перевірку на мінімум для твоєї біржі (наприклад, >= 5 USDT)
        if available_balance < 5:
            return False, f"Недостатньо USDT на ф’ючерсному акаунті (доступно {available_balance})"

        return True, ""
    except Exception as e:
        return False, f"Помилка перевірки: {e}"
