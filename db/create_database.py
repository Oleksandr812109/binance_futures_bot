import sqlite3

def create_database():
    # Підключення до бази даних (створює файл database.db, якщо його ще немає)
    connection = sqlite3.connect("db/database.db")
    cursor = connection.cursor()

    # Створення таблиці (наприклад, для зберігання ордерів)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Збереження змін та закриття з'єднання
    connection.commit()
    connection.close()
    print("База даних створена успішно!")

if __name__ == "__main__":
    create_database()
