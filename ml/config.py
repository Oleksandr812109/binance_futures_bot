from enum import Enum

# Файли моделі та скейлера
SCALER_PATH = "ml/models/scaler.pkl"
MODEL_PATH = "ml/models/model.keras"

# Назви фічей (підлаштуйте під свій датасет)
FEATURE_NAMES = [
    "close", "ema_short", "ema_long", "rsi",
    "adx", "upper_band", "lower_band", "volume"
]

# Множники для розрахунку SL та TP
SL_MULTIPLIER_BUY = 0.99
TP_MULTIPLIER_BUY = 1.02
SL_MULTIPLIER_SELL = 1.01
TP_MULTIPLIER_SELL = 0.98

class Decision(Enum):
    HOLD = 0
    BUY = 1
    SELL = 2
