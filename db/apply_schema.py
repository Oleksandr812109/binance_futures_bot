import sqlite3

def apply_schema():
    # Підключення до бази даних
    connection = sqlite3.connect("db/database.db")
    cursor = connection.cursor()

    # Зчитування SQL-схеми з файлу schema.sql
    try:
        with open("db/schema.sql", "r") as file:
            schema = file.read()

        # Виконання SQL-схеми
        cursor.executescript(schema)
        connection.commit()
        print("Схема успішно застосована до бази даних!")
    except FileNotFoundError:
        print("Файл schema.sql не знайдено. Переконайтеся, що він знаходиться у директорії db.")
    except Exception as e:
        print(f"Виникла помилка при застосуванні схеми: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    apply_schema()
