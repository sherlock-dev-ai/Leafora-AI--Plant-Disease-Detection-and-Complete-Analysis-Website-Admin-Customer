"""
Migration: Add daily usage tracking columns to usage_counters table
"""
import sqlite3
import os
from datetime import datetime

def migrate():
    """Add today_count and daily_reset_at columns to usage_counters table"""
    # Get database path
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'database.sqlite')
    
    if not os.path.exists(db_path):
        print("Database not found, skipping migration")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(usage_counters)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'today_count' not in columns:
            cursor.execute("ALTER TABLE usage_counters ADD COLUMN today_count INTEGER DEFAULT 0")
            print("✅ Added today_count column")
        
        if 'daily_reset_at' not in columns:
            cursor.execute("ALTER TABLE usage_counters ADD COLUMN daily_reset_at TEXT NULL")
            print("✅ Added daily_reset_at column")
        
        conn.commit()
        print("✅ Migration completed successfully")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()


