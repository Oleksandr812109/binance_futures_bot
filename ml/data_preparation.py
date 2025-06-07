import pandas as pd
import pandas_ta as ta

# 1. Завантаження сирих даних
# Замініть шлях на свій csv, наприклад, з Binance API або іншого джерела
RAW_DATA_PATH = "ml/data/raw_ohlcv.csv"
DATASET_PATH = "ml/data/dataset.csv"

def add_indicators(df):
    """Додає технічні індикатори у DataFrame."""
    df['EMA_Short'] = ta.ema(df['Close'], length=12)
    df['EMA_Long'] = ta.ema(df['Close'], length=26)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    df['ADX'] = adx['ADX_14']
    bb = ta.bbands(df['Close'], length=20)
    df['Upper_Band'] = bb['BBU_20_2.0']
    df['Lower_Band'] = bb['BBL_20_2.0']
    if 'Volume' not in df.columns:
        df['Volume'] = 0
    return df

def generate_targets(df):
    """Генерує цільові мітки для навчання (dummy logic, заміни на свою!)."""
    df['target'] = 0  # HOLD за замовчуванням
    # Простий приклад: якщо EMA_Short > EMA_Long — BUY, якщо менше — SELL
    df.loc[df['EMA_Short'] > df['EMA_Long'], 'target'] = 1  # BUY
    df.loc[df['EMA_Short'] < df['EMA_Long'], 'target'] = 2  # SELL
    return df

def main():
    df = pd.read_csv(RAW_DATA_PATH)
    df = add_indicators(df)
    df = generate_targets(df)
    df = df.dropna()
    df.to_csv(DATASET_PATH, index=False)
    print(f"Готовий датасет збережено в {DATASET_PATH}")

if __name__ == "__main__":
    main()
