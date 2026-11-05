# db/connection.py
# MySQL connection configuration for SmartRetail

import mysql.connector
from mysql.connector import Error

# ── Database credentials ──────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "admin123",
    "database": "system_db",
    "autocommit": False,
}

def get_connection():
    """Return a new MySQL connection. Raises RuntimeError on failure."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        raise RuntimeError(f"Database connection failed: {e}")

def test_connection():
    """Returns True if connection succeeds, False otherwise."""
    try:
        conn = get_connection()
        conn.close()
        return True
    except RuntimeError:
        return False
