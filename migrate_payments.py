import sqlite3

DB_PATH = "database/billing.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE bills ADD COLUMN cash_amount REAL DEFAULT 0")
    print("✅ cash_amount column added")
except Exception as e:
    print("⚠️ cash_amount:", e)

try:
    cursor.execute("ALTER TABLE bills ADD COLUMN paytm_amount REAL DEFAULT 0")
    print("✅ paytm_amount column added")
except Exception as e:
    print("⚠️ paytm_amount:", e)

conn.commit()
conn.close()

print("✅ Migration completed")
