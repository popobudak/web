import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-ganti-ini")
DATABASE_URL = "sqlite:///licenses.db"   # Bisa diganti ke MySQL/PostgreSQL