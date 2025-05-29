import csv
import os

FIELDNAMES = [
    "symbol", "side", "entry_price", "close_price", "profit", "target",
    "EMA_Short", "EMA_Long", "RSI", "ADX", "Upper_Band", "Lower_Band"
]

def save_trade(features: dict, trade_info: dict, target: int, filename: str = "trade_history.csv"):
    record = {
        "symbol": trade_info.get("symbol"),
        "side": trade_info.get("side"),
        "entry_price": trade_info.get("entry_price"),
        "close_price": trade_info.get("close_price"),
        "profit": trade_info.get("close_price", 0) - trade_info.get("entry_price", 0) if trade_info.get("side") == "BUY"
                  else trade_info.get("entry_price", 0) - trade_info.get("close_price", 0),
        "target": target,
    }
    for fname in FIELDNAMES:
        if fname in features:
            record[fname] = features[fname]
    write_header = not os.path.exists(filename)
    with open(filename, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(record)
