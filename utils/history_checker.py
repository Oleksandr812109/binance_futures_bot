import os
import pandas as pd

def is_enough_history(filename="trade_history.csv", min_trades=30):
    return os.path.exists(filename) and pd.read_csv(filename).shape[0] >= min_trades
