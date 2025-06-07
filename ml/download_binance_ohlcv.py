import pandas as pd
from binance.client import Client

# Якщо у тебе є API ключі, встав їх тут
api_key = "d819d92b03fa3d8c61ff4c4835908ec4afde53fc64ac6df6235c5b332fbef930"
api_secret = "007055837e544dfb38e99582a2b00626164602a168aa939eb5943adb293bf727"
client = Client(api_key, api_secret)

symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_1HOUR
start_str = "2 years ago UTC"  # Можна змінити період

klines = client.get_historical_klines(symbol, interval, start_str)

# Формуємо DataFrame
df = pd.DataFrame(klines, columns=[
    'open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
    'close_time', 'qav', 'trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
])
df = df[['Open', 'High', 'Low', 'Close', 'Volume']]  # Інші колонки не потрібні

# Конвертуємо всі ці дані у float
for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
    df[col] = df[col].astype(float)

# Зберігаємо
df.to_csv("ml/data/raw_ohlcv.csv", index=False)
print("Дані збережено у ml/data/raw_ohlcv.csv")
