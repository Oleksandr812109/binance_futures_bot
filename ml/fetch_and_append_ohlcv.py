import os
import pandas as pd
from binance.client import Client
from datetime import datetime
import logging
import time

# --- DEBUG: перевіряємо, чи бачить Python змінні середовища ---
print("DEBUG: BINANCE_API_KEY =", os.environ.get("BINANCE_API_KEY"))
print("DEBUG: BINANCE_API_SECRET =", os.environ.get("BINANCE_API_SECRET"))

# --- Налаштування логування ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Виправлено: тут мають бути імена, а не значення ключів!
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

if not API_KEY or not API_SECRET:
    logging.error("API_KEY або API_SECRET не встановлені як змінні середовища.")
    exit()

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
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
        logging.error(f"[{symbol}] Помилка при завантаженні свічок")
