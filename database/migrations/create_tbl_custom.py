"""
Migration: Create tbl_custom table and migrate customer data from tbl_login
This separates customer profile data from authentication data
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tbl_custom():
    """Create tbl_custom table and migrate data from tbl_login"""
    
    # Find database file
    db_paths = [
        Path('instance/database.sqlite'),
        Path('database/instance/database.sqlite')
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        raise FileNotFoundError("Database file not found")
    
    logger.info(f"Using database: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if tbl_custom already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tbl_custom'
        """)
        if cursor.fetchone():
            logger.warning("tbl_custom already exists. Skipping creation.")
            conn.close()
            return
        
        # Create tbl_custom table
        logger.info("Creating tbl_custom table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tbl_custom (
                customer_id TEXT PRIMARY KEY NOT NULL,
                user_id INTEGER NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                is_pro INTEGER DEFAULT 0,
                pro_expires_at TEXT NULL,
                is_deleted BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login TEXT NULL,
                FOREIGN KEY (user_id) REFERENCES tbl_login(id) ON DELETE CASCADE
            )
        """)
        
        # Create index on user_id for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tbl_custom_user_id 
            ON tbl_custom(user_id)
        """)
        
        # Migrate data from tbl_login to tbl_custom
        logger.info("Migrating data from tbl_login to tbl_custom...")
        
        # Get all users from tbl_login
        cursor.execute("""
            SELECT id, customer_id, is_admin, is_pro, pro_expires_at, 
                   is_deleted, created_at, last_login
            FROM tbl_login
            WHERE customer_id IS NOT NULL
        """)
        
        users = cursor.fetchall()
        logger.info(f"Found {len(users)} users to migrate")
        
        migrated = 0
        for user in users:
            user_id, customer_id, is_admin, is_pro, pro_expires_at, is_deleted, created_at, last_login = user
            
            # Insert into tbl_custom
            cursor.execute("""
                INSERT INTO tbl_custom 
                (customer_id, user_id, is_admin, is_pro, pro_expires_at, 
                 is_deleted, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (customer_id, user_id, is_admin, is_pro, pro_expires_at, 
                  is_deleted, created_at, last_login))
            migrated += 1
        
        conn.commit()
        logger.info(f"Successfully migrated {migrated} records to tbl_custom")
        
        # Verify migration
        cursor.execute("SELECT COUNT(*) FROM tbl_custom")
        count = cursor.fetchone()[0]
        logger.info(f"tbl_custom now contains {count} records")
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 70)
    print("Creating tbl_custom table and migrating customer data")
    print("=" * 70)
    try:
        create_tbl_custom()
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()

