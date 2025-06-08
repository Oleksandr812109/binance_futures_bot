import os
import pandas as pd
from binance.client import Client
from datetime import datetime
import logging
import time

# --- Налаштування логування ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = os.getenv("d819d92b03fa3d8c61ff4c4835908ec4afde53fc64ac6df6235c5b332fbef930")
API_SECRET = os.getenv("007055837e544dfb38e99582a2b00626164602a168aa939eb5943adb293bf727")

if not API_KEY or not API_SECRET:
    logging.error("API_KEY або API_SECRET не встановлені як змінні середовища.")
    exit()

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
INTERVAL = Client.KLINE_INTERVAL_1HOUR
RAW_DATA_PATH_TEMPLATE = "ml/data/raw_ohlcv_{}.csv"

def initialize_binance_client(api_key, api_secret):
    try:
        client = Client(api_key, api_secret)
        client.ping()
        logging.info("Клієнт Binance ініціалізовано успішно.")
        return client
    except Exception as e:
        logging.error(f"Помилка ініціалізації клієнта Binance: {e}")
        return None

def load_existing_data(path):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if "Open time" in df.columns:
                df["Open time"] = pd.to_datetime(df["Open time"])
                logging.info(f"Завантажено {len(df)} існуючих рядків з {path}.")
                return df
            else:
                logging.warning(f"Файл {path} не містить колонки 'Open time'. Буде завантажено всі нові дані.")
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Помилка читання файлу {path}: {e}. Створюємо новий DataFrame.")
            return pd.DataFrame()
    else:
        logging.info(f"Файл {path} не знайдено. Створюємо новий DataFrame.")
        return pd.DataFrame()

def fetch_new_klines(client, symbol, interval, start_time_ms=None):
    klines = []
    try:
        if start_time_ms:
            logging.info(f"[{symbol}] Завантаження свічок з {datetime.fromtimestamp(start_time_ms / 1000)}...")
            new_klines = client.get_klines(symbol=symbol, interval=interval, startTime=start_time_ms)
        else:
            logging.info(f"[{symbol}] Завантаження всіх доступних свічок...")
            new_klines = client.get_klines(symbol=symbol, interval=interval)
        klines.extend(new_klines)
        logging.info(f"[{symbol}] Отримано {len(new_klines)} нових свічок з Binance API.")
    except Exception as e:
        logging.error(f"[{symbol}] Помилка при завантаженні свічок: {e}")
    return klines

def process_klines_to_dataframe(klines_data):
    columns = [
        "Open time", "Open", "High", "Low", "Close", "Volume", "Close time",
        "Quote asset volume", "Number of trades", "Taker buy base asset volume",
        "Taker buy quote asset volume", "Ignore"
    ]
    df = pd.DataFrame(klines_data, columns=columns)

    if df.empty:
        return df

    df["Open time"] = pd.to_datetime(df["Open time"], unit="ms")
    df["Close time"] = pd.to_datetime(df["Close time"], unit="ms")

    numeric_cols = ["Open", "High", "Low", "Close", "Volume", "Quote asset volume",
                    "Number of trades", "Taker buy base asset volume", "Taker buy quote asset volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df[["Open time", "Open", "High", "Low", "Close", "Volume"]]
    return df

def main():
    client = initialize_binance_client(API_KEY, API_SECRET)
    if not client:
        return

    for symbol in SYMBOLS:
        raw_data_path = RAW_DATA_PATH_TEMPLATE.format(symbol)
        df_existing = load_existing_data(raw_data_path)
        last_time_ms = 0

        if not df_existing.empty:
            last_time = df_existing["Open time"].max()
            last_time_ms = int(last_time.timestamp() * 1000) + 1

        new_klines_raw = fetch_new_klines(client, symbol, INTERVAL, last_time_ms)
        df_new = process_klines_to_dataframe(new_klines_raw)

        if df_new.empty:
            logging.info(f"[{symbol}] Нових свічок немає або виникла помилка при завантаженні.")
            continue

        if last_time_ms > 0:
            df_new = df_new[df_new["Open time"] > pd.to_datetime(last_time_ms - 1, unit="ms")]

        if df_new.empty:
            logging.info(f"[{symbol}] Після фільтрації нових унікальних свічок немає.")
            continue

        if not df_existing.empty:
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
            df_final.drop_duplicates(subset=["Open time"], inplace=True)
            df_final.sort_values(by="Open time", inplace=True)
        else:
            df_final = df_new

        os.makedirs(os.path.dirname(raw_data_path), exist_ok=True)
        df_final.to_csv(raw_data_path, index=False)
        logging.info(f"[{symbol}] Додано {len(df_new)} нових рядків (після фільтрації) у {raw_data_path}. Всього рядків: {len(df_final)}")

        # Можна додати затримку для уникнення rate-limit Binance
        time.sleep(1)  # 1 секунда між запитами

if __name__ == "__main__":
    main()
