import pandas as pd
import pandas_ta as ta
from pathlib import Path

RAW_DIR = Path("ml/data")
OUTPUT_DIR = Path("ml/processed")
OUTPUT_DIR.mkdir(exist_ok=True)

NEEDED_COLS = ['open', 'high', 'low', 'close', 'volume']

REQUIRED_FEATURES = [
    'open', 'high', 'low', 'close', 'volume',
    'ema_short', 'ema_long', 'rsi', 'adx',
    'upper_band', 'lower_band'
]

# === Параметри для кожної монети ===
PAIR_PARAMS = {
    "BTCUSDT": {"EMA_SHORT": 12, "EMA_LONG": 26, "RSI_LEN": 14, "RSI_BUY": 55, "RSI_SELL": 45},
    "ETHUSDT": {"EMA_SHORT": 10, "EMA_LONG": 21, "RSI_LEN": 12, "RSI_BUY": 56, "RSI_SELL": 44},
    "BNBUSDT": {"EMA_SHORT": 9,  "EMA_LONG": 21, "RSI_LEN": 10, "RSI_BUY": 54, "RSI_SELL": 46},
    "SOLUSDT": {"EMA_SHORT": 9,  "EMA_LONG": 21, "RSI_LEN": 10, "RSI_BUY": 53, "RSI_SELL": 47},
    "ADAUSDT": {"EMA_SHORT": 9,  "EMA_LONG": 21, "RSI_LEN": 10, "RSI_BUY": 55, "RSI_SELL": 45},
}
# Якщо не знайдено — дефолт
DEFAULT_PARAMS = {"EMA_SHORT": 12, "EMA_LONG": 26, "RSI_LEN": 14, "RSI_BUY": 55, "RSI_SELL": 45}

def unify_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lower() for c in df.columns]
    return df

def check_columns(df: pd.DataFrame, columns: list):
    for col in columns:
        if col not in df.columns:
            raise ValueError(f"Не знайдено колонку '{col}' у даних.")

def add_indicators(df: pd.DataFrame, params) -> pd.DataFrame:
    EMA_SHORT = params["EMA_SHORT"]
    EMA_LONG = params["EMA_LONG"]
    RSI_LEN = params["RSI_LEN"]
    ADX_LEN = 14
    BB_LEN = 20
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    try:
        df['ema_short'] = ta.ema(df['close'], length=EMA_SHORT)
        df['ema_long'] = ta.ema(df['close'], length=EMA_LONG)
        df['rsi'] = ta.rsi(df['close'], length=RSI_LEN)
        adx = ta.adx(df['high'], df['low'], df['close'], length=ADX_LEN)
        df['adx'] = adx[f'ADX_{ADX_LEN}']
        bb = ta.bbands(df['close'], length=BB_LEN)
        df['bb_upper'] = bb[f'BBU_{BB_LEN}_2.0']
        df['bb_lower'] = bb[f'BBL_{BB_LEN}_2.0']
        df = df.rename(columns={'bb_upper': 'upper_band', 'bb_lower': 'lower_band'})
        df['macd'] = ta.macd(df['close'], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)[f'MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']
        df['macd_signal'] = ta.macd(df['close'], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)[f'MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}']
        stoch = ta.stoch(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch['STOCHk_14_3_3']
        df['stoch_d'] = stoch['STOCHd_14_3_3']
    except Exception as e:
        print(f"Помилка при розрахунку індикаторів: {e}")
        raise
    return df

def generate_signal(df: pd.DataFrame, params) -> pd.DataFrame:
    rsi_buy = params["RSI_BUY"]
    rsi_sell = params["RSI_SELL"]
    df['signal'] = 0
    df.loc[(df['ema_short'] > df['ema_long']) & (df['rsi'] > rsi_buy), 'signal'] = 1
    df.loc[(df['ema_short'] < df['ema_long']) & (df['rsi'] < rsi_sell), 'signal'] = 2
    return df

def preprocess_file(input_path: Path, output_path: Path):
    try:
        df = pd.read_csv(input_path)
        df = unify_columns(df)
        check_columns(df, NEEDED_COLS)
        if 'symbol' not in df.columns:
            symbol = input_path.stem.split('_')[1].upper() + "USDT" if '_' in input_path.stem else "UNKNOWN"
            df['symbol'] = symbol
        else:
            symbol = str(df['symbol'].iloc[0]).upper()
        params = PAIR_PARAMS.get(symbol, DEFAULT_PARAMS)
        df = add_indicators(df, params)
        df = generate_signal(df, params)
        df = df.dropna().reset_index(drop=True)
        columns_to_save = REQUIRED_FEATURES + ['signal', 'symbol']
        missing = [col for col in columns_to_save if col not in df.columns]
        if missing:
            print(f"❌  {input_path.name}: Missing columns {missing}")
        df = df[columns_to_save]
        df.to_csv(output_path, index=False)
        print(f"✔️  {input_path.name} → {output_path.name} ({len(df)} рядків)")
    except Exception as e:
        print(f"❌  Помилка у {input_path.name}: {e}")

def main():
    for csv_file in RAW_DIR.glob("raw_*USDT_1h.csv"):
        out_file = OUTPUT_DIR / f"training_data_{csv_file.stem.split('_')[1].upper()}USDT.csv"
        preprocess_file(csv_file, out_file)

if __name__ == "__main__":
    main()
