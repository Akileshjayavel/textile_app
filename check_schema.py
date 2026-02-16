import sqlite3
import json

conn = sqlite3.connect('database/billing.db')
cursor = conn.cursor()

# Check bills table schema
cursor.execute("PRAGMA table_info(bills)")
columns = cursor.fetchall()
print("Bills Table Columns:")
for col in columns:
    print(col)

conn.close()
