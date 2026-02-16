import os

# Base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Railway / Cloud Persistent Volume Logic
# If /app/data exists (Railway volume), use it. Otherwise, use local 'database' folder.
if os.path.exists('/app/data'):
    DB_FOLDER = '/app/data'
    DB_PATH = os.path.join(DB_FOLDER, 'billing.db')
else:
    # Local Development
    DB_FOLDER = os.path.join(BASE_DIR, 'database')
    DB_PATH = os.path.join(DB_FOLDER, 'billing.db')

# Ensure the database folder exists (Crucial for first run)
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER, exist_ok=True)

print(f"✅ Database Configured at: {DB_PATH}")
