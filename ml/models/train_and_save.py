import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from binance.client import Client
from datetime import datetime, timedelta
import ta

API_KEY = 'd819d92b03fa3d8c61ff4c4835908ec4afde53fc64ac6df6235c5b332fbef930'
API_SECRET = '007055837e544dfb38e99582a2b00626164602a168aa939eb5943adb293bf727'
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
INTERVAL = Client.KLINE_INTERVAL_1HOUR
LOOKBACK_HOURS = 8000  # ~333 днів, змініть при потребі

client = Client(API_KEY, API_SECRET)

for symbol in SYMBOLS:
    print(f"Завантаження даних для {symbol}...")
    klines = []
    start_time = datetime.now() - timedelta(hours=LOOKBACK_HOURS)
    lookback_remaining = LOOKBACK_HOURS
    while lookback_remaining > 0:
        limit = min(1000, lookback_remaining)
        start_ts = int(start_time.timestamp() * 1000)
        klines_batch = client.get_klines(
            symbol=symbol,
            interval=INTERVAL,
            startTime=start_ts,
            limit=limit
        )
        if not klines_batch:
            break
        klines += klines_batch
        last_open_time = klines_batch[-1][0]
        start_time = datetime.fromtimestamp(last_open_time / 1000) + timedelta(hours=1)
        lookback_remaining -= limit

    if len(klines) < 100:
        print(f"Недостатньо даних для {symbol}, пропускаю.")
        continue

    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    # Додаємо технічні індикатори та інші фічі
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macdsignal'] = macd.macd_signal()
    df['macdhist'] = macd.macd_diff()
    df['ema20'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
    df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
    df['atr'] = ta.volatility.AverageTrueRange(
        df['high'], df['low'], df['close'], window=14
    ).average_true_range()
    df['hour'] = df['open_time'].dt.hour
    df['price_change'] = df['close'].pct_change().fillna(0)
    df['rsi_delta'] = df['rsi'].diff().fillna(0)
    df['macdhist_delta'] = df['macdhist'].diff().fillna(0)
    df['volatility'] = np.where(df['close'] != 0, df['atr'] / df['close'], 0)

    # Видаляємо рядки з NaN у фічах
    feature_columns = [
        'close', 'volume', 'rsi', 'macd', 'macdsignal', 'macdhist',
        'ema20', 'ema_50', 'atr', 'hour', 'price_change',
        'rsi_delta', 'macdhist_delta', 'volatility'
    ]
    df = df.dropna(subset=feature_columns)

    # Формуємо цільову змінну (напрямок руху ціни)
    df['future_close'] = df['close'].shift(-1)
    y = (df['future_close'] > df['close']).astype(int)[:-1]  # 1 якщо зростає, 0 якщо падає/не змінюється
    # Для сумісності з Decision у ai_signal_generator.py можна замінити на: 1 = BUY, -1 = SELL, 0 = HOLD
    # y = np.where(df['future_close'] > df['close'], 1, np.where(df['future_close'] < df['close'], -1, 0))[:-1]

    X = df[feature_columns].values[:-1]  # останній рядок не має таргету

    # Навчання скейлера та моделі
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_scaled, y)

    # Збереження моделі та скейлера
    model_file = f'model_{symbol}.pkl'
    scaler_file = f'scaler_{symbol}.joblib'
    joblib.dump(model, model_file)
    joblib.dump(scaler, scaler_file)
    print(f"Збережено {model_file} та {scaler_file}")

print("Навчання завершено для всіх пар!")
