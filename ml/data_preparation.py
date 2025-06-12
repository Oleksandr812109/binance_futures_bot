import pandas as pd
import pandas_ta as ta
from pathlib import Path

# ==== Константи для індикаторів ====
EMA_SHORT = 12
EMA_LONG = 26
RSI_LEN = 14
ADX_LEN = 14
BB_LEN = 20
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

RAW_DIR = Path("ml/data")
OUTPUT_DIR = Path("ml/processed")
OUTPUT_DIR.mkdir(exist_ok=True)

NEEDED_COLS = ['open', 'high', 'low', 'close', 'volume']

def unify_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Привести всі назви колонок до нижнього регістру для уніфікації."""
    df.columns = [c.lower() for c in df.columns]
    return df

def check_columns(df: pd.DataFrame, columns: list):
    """Перевіряє наявність потрібних колонок."""
    for col in columns:
        if col not in df.columns:
            raise ValueError(f"Не знайдено колонку '{col}' у даних.")

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Додає технічні індикатори у DataFrame. Обробка помилок."""
    try:
        df['ema_short'] = ta.ema(df['close'], length=EMA_SHORT)
        df['ema_long'] = ta.ema(df['close'], length=EMA_LONG)
        df['rsi'] = ta.rsi(df['close'], length=RSI_LEN)
        adx = ta.adx(df['high'], df['low'], df['close'], length=ADX_LEN)
        df['adx'] = adx[f'ADX_{ADX_LEN}']
        bb = ta.bbands(df['close'], length=BB_LEN)
        df['bb_upper'] = bb[f'BBU_{BB_LEN}_2.0']
        df['bb_lower'] = bb[f'BBL_{BB_LEN}_2.0']
        macd = ta.macd(df['close'], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        df['macd'] = macd[f'MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']
        df['macd_signal'] = macd[f'MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']
        stoch = ta.stoch(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch['STOCHk_14_3_3']
        df['stoch_d'] = stoch['STOCHd_14_3_3']
    except Exception as e:
        print(f"Помилка при розрахунку індикаторів: {e}")
        raise
    return df

def generate_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Генерує цільову змінну сигнал (0=HOLD, 1=BUY, 2=SELL)"""
    df['signal'] = 0
    df.loc[df['ema_short'] > df['ema_long'], 'signal'] = 1
    df.loc[df['ema_short'] < df['ema_long'], 'signal'] = 2
    return df

def preprocess_file(input_path: Path, output_path: Path):
    """Обробляє один CSV-файл: додає індикатори, сигнал, зберігає результат."""
    try:
        df = pd.read_csv(input_path)
        df = unify_columns(df)
        check_columns(df, NEEDED_COLS)
        # Додаємо колонку symbol, якщо можливо
        if 'symbol' not in df.columns:
            symbol = input_path.stem.split('_')[1].upper() + "USDT" if '_' in input_path.stem else "UNKNOWN"
            df['symbol'] = symbol
        df = add_indicators(df)
        df = generate_signal(df)
        # Залишаємо тільки повні рядки (там де всі індикатори вже розраховані)
        df = df.dropna().reset_index(drop=True)
        df.to_csv(output_path, index=False)
        print(f"✔️  {input_path.name} → {output_path.name} ({len(df)} рядків)")
    except Exception as e:
        print(f"❌  Помилка у {input_path.name}: {e}")

def main():
    # Обробляємо всі raw_*USDT_1h.csv у RAW_DIR
    for csv_file in RAW_DIR.glob("raw_*USDT_1h.csv"):
        out_file = OUTPUT_DIR / f"training_data_{csv_file.stem.split('_')[1].upper()}USDT.csv"
        preprocess_file(csv_file, out_file)

if __name__ == "__main__":
    main()
