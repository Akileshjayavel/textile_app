import os

# Base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Railway / Cloud Persistent Volume Logic
# Check if we are running in a Linux container (Railway usually has /app)
if os.path.exists('/app'):
    DB_FOLDER = '/app/data'
    # Force creation of the directory if it doesn't exist (per user request)
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER, exist_ok=True)
    DB_PATH = os.path.join(DB_FOLDER, 'billing.db')
    print(f"🚀 RUNNING IN CONTAINER. Database Path: {DB_PATH}")
else:
    # Local Windows / Dev
    DB_FOLDER = os.path.join(BASE_DIR, 'database')
    DB_PATH = os.path.join(DB_FOLDER, 'billing.db')
    print(f"💻 RUNNING LOCALLY. Database Path: {DB_PATH}")

# Ensure the database folder exists (Crucial for first run)
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER, exist_ok=True)
