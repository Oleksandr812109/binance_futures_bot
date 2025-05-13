import sqlite3
import os

# Path to the SQLite database
DB_NAME = "test_database.db"

# Initialize database and tables
def initialize_database():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)  # Remove old test database

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            level TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

# Insert sample data and validate functionality
def test_database_operations():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Test inserting into orders
    cursor.execute("INSERT INTO orders (symbol, side, quantity, price, status) VALUES (?, ?, ?, ?, ?)",
                   ('BTCUSDT', 'BUY', 1.0, 30000.0, 'OPEN'))
    cursor.execute("INSERT INTO orders (symbol, side, quantity, price, status) VALUES (?, ?, ?, ?, ?)",
                   ('ETHUSDT', 'SELL', 0.5, 2000.0, 'OPEN'))

    # Test inserting into logs
    cursor.execute("INSERT INTO logs (message, level) VALUES (?, ?)",
                   ('Order created: BTCUSDT', 'INFO'))
    cursor.execute("INSERT INTO logs (message, level) VALUES (?, ?)",
                   ('Order created: ETHUSDT', 'INFO'))

    # Test inserting into settings
    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)",
                   ('max_order_quantity', '10'))

    conn.commit()

    # Validate orders
    cursor.execute("SELECT * FROM orders")
    orders = cursor.fetchall()
    assert len(orders) == 2, f"Expected 2 orders, found {len(orders)}"

    # Validate logs
    cursor.execute("SELECT * FROM logs")
    logs = cursor.fetchall()
    assert len(logs) == 2, f"Expected 2 logs, found {len(logs)}"

    # Validate settings
    cursor.execute("SELECT * FROM settings WHERE key = ?", ('max_order_quantity',))
    settings = cursor.fetchone()
    assert settings is not None, "Setting 'max_order_quantity' not found"
    assert settings[1] == '10', f"Expected '10', found {settings[1]}"

    conn.close()
    print("All tests passed successfully!")

# Main execution
if __name__ == "__main__":
    initialize_database()
    test_database_operations()
