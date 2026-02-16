import sqlite3
import os
from datetime import datetime

DB_PATH = "database/billing.db"


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cursor.fetchall()]


def init_db():
    # Ensure database folder exists
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # -----------------------------
    # USERS TABLE
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # -----------------------------
    # PRODUCTS TABLE
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # -----------------------------
    # CUSTOMERS TABLE (MOBILE = MASTER KEY ✅)
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT UNIQUE NOT NULL,
        address TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )
    """)

    # -----------------------------
    # BILLS TABLE (MOBILE-BASED ✅)
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_no TEXT UNIQUE NOT NULL,
        customer_mobile TEXT NOT NULL,
        total_amount REAL NOT NULL,
        cash_amount REAL DEFAULT 0,
        paytm_amount REAL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # 🔥 MIGRATION SAFETY
    if not column_exists(cursor, "bills", "customer_mobile"):
        cursor.execute("""
        ALTER TABLE bills
        ADD COLUMN customer_mobile TEXT
        """)

    # -----------------------------
    # BILL ITEMS TABLE
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bill_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (bill_id) REFERENCES bills(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """)

    # -----------------------------
    # PAYMENTS TABLE (MOBILE-BASED ✅)
    # -----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_mobile TEXT NOT NULL,
        cash_amount REAL DEFAULT 0,
        paytm_amount REAL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # 🔥 MIGRATION SAFETY
    if not column_exists(cursor, "payments", "customer_mobile"):
        cursor.execute("""
        ALTER TABLE payments
        ADD COLUMN customer_mobile TEXT
        """)

    # -----------------------------
    # DEFAULT ADMIN USER
    # -----------------------------
    cursor.execute("""
    INSERT OR IGNORE INTO users (username, password, role)
    VALUES ('admin', 'admin123', 'admin')
    """)

    conn.commit()
    conn.close()

    print("✅ Database initialized & migrated successfully (mobile-based schema)")


if __name__ == "__main__":
    init_db()
