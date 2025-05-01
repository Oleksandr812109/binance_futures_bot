-- Створення таблиці для ордерів
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Унікальний ідентифікатор ордера
    symbol TEXT NOT NULL,                 -- Символ, наприклад, 'BTCUSDT'
    side TEXT NOT NULL,                   -- BUY або SELL
    quantity REAL NOT NULL,               -- Кількість активів
    price REAL,                           -- Ціна ордера (для лімітних ордерів)
    status TEXT NOT NULL,                 -- Статус ордера (наприклад, 'OPEN', 'CLOSED', 'CANCELLED')
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Час створення ордера
);

-- Створення таблиці для логів або історії
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Унікальний ідентифікатор запису
    message TEXT NOT NULL,                -- Повідомлення або текст логів
    level TEXT NOT NULL,                  -- Рівень логування (INFO, ERROR тощо)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Час створення запису
);

-- Створення таблиці для збереження налаштувань
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,                 -- Ключ налаштування
    value TEXT NOT NULL                   -- Значення налаштування
);
