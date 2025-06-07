from enum import Enum

# Файли моделі та скейлера
SCALER_PATH = "ml/models/scaler.pkl"
MODEL_PATH = "ml/models/model.h5"

# Назви фічей (підлаштуйте під свій датасет)
FEATURE_NAMES = [
    "Close", "EMA_Short", "EMA_Long", "RSI",
    "ADX", "Upper_Band", "Lower_Band", "Volume"
]

# Множники для розрахунку SL та TP
SL_MULTIPLIER_BUY = 0.98
TP_MULTIPLIER_BUY = 1.03
SL_MULTIPLIER_SELL = 1.02
TP_MULTIPLIER_SELL = 0.97

class Decision(Enum):
    HOLD = 0
    BUY = 1
    SELL = 2
