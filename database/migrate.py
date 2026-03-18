"""
Leafora AI Database Migration Script
Runs on startup to ensure database schema is up to date
"""
import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Get database path from config or environment
def get_db_path():
    """Get database path"""
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    db_path = os.path.join(basedir, 'instance', 'database.sqlite')
    return db_path


def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_database():
    """Run database migrations"""
    db_path = get_db_path()
    
    # Create instance directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("🔍 Database Migration")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    migrations_applied = []
    
    try:
        # Check if database exists and has tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # If no tables exist, run full schema
        if not existing_tables:
            logger.info("📊 Creating new database with full schema...")
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                cursor.executescript(schema_sql)
                conn.commit()
                migrations_applied.append("Full schema creation")
                logger.info("✅ Database created successfully")
            else:
                logger.warning("⚠️ schema.sql not found, creating tables manually...")
                # Create tables manually if schema.sql doesn't exist
                create_tables_manually(cursor)
                conn.commit()
                migrations_applied.append("Manual table creation")
        else:
            logger.info(f"✅ Database exists with {len(existing_tables)} table(s)")
            
            # Migration 1: Add customer_id to users if missing
            if 'users' in existing_tables:
                if not check_column_exists(cursor, 'users', 'customer_id'):
                    logger.info("🔄 Adding customer_id column to users...")
                    cursor.execute("ALTER TABLE users ADD COLUMN customer_id TEXT")
                    # Generate customer IDs for existing users
                    cursor.execute("SELECT id FROM users WHERE customer_id IS NULL")
                    for (user_id,) in cursor.fetchall():
                        customer_id = f"CUST-{datetime.now().strftime('%Y%m%d')}-{user_id:04d}"
                        cursor.execute("UPDATE users SET customer_id = ? WHERE id = ?", (customer_id, user_id))
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_customer_id ON users(customer_id)")
                    conn.commit()
                    migrations_applied.append("Added customer_id to users")
                
                # Migration 2: Add Pro subscription fields
                if not check_column_exists(cursor, 'users', 'is_pro'):
                    logger.info("🔄 Adding Pro subscription fields to users...")
                    cursor.execute("ALTER TABLE users ADD COLUMN is_pro INTEGER DEFAULT 0")
                    migrations_applied.append("Added is_pro to users")
                
                if not check_column_exists(cursor, 'users', 'pro_expires_at'):
                    logger.info("🔄 Adding pro_expires_at to users...")
                    cursor.execute("ALTER TABLE users ADD COLUMN pro_expires_at TEXT NULL")
                    migrations_applied.append("Added pro_expires_at to users")
                
                if not check_column_exists(cursor, 'users', 'theme'):
                    logger.info("🔄 Adding theme to users...")
                    cursor.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'light'")
                    migrations_applied.append("Added theme to users")
                
                if not check_column_exists(cursor, 'users', 'last_login'):
                    logger.info("🔄 Adding last_login to users...")
                    cursor.execute("ALTER TABLE users ADD COLUMN last_login TEXT NULL")
                    migrations_applied.append("Added last_login to users")
            
            # Migration 3: Add missing columns to predictions
            if 'predictions' in existing_tables:
                if not check_column_exists(cursor, 'predictions', 'topk_results'):
                    logger.info("🔄 Adding topk_results to predictions...")
                    cursor.execute("ALTER TABLE predictions ADD COLUMN topk_results TEXT")
                    migrations_applied.append("Added topk_results to predictions")
                
                if not check_column_exists(cursor, 'predictions', 'models_used'):
                    logger.info("🔄 Adding models_used to predictions...")
                    cursor.execute("ALTER TABLE predictions ADD COLUMN models_used TEXT")
                    migrations_applied.append("Added models_used to predictions")
                
                if not check_column_exists(cursor, 'predictions', 'is_unknown'):
                    logger.info("🔄 Adding is_unknown to predictions...")
                    cursor.execute("ALTER TABLE predictions ADD COLUMN is_unknown INTEGER DEFAULT 0")
                    migrations_applied.append("Added is_unknown to predictions")
            
            # Migration 4: Create payments table if missing
            if 'payments' not in existing_tables:
                logger.info("🔄 Creating payments table...")
                cursor.execute("""
                    CREATE TABLE payments (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      amount_cents INTEGER,
                      currency TEXT DEFAULT 'USD',
                      card_last4 TEXT,
                      card_brand TEXT,
                      status TEXT,
                      receipt_path TEXT,
                      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                      expires_at TEXT NULL,
                      FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
                conn.commit()
                migrations_applied.append("Created payments table")
            
            # Migration 5: Create usage_counters table if missing
            if 'usage_counters' not in existing_tables:
                logger.info("🔄 Creating usage_counters table...")
                cursor.execute("""
                    CREATE TABLE usage_counters (
                      user_id INTEGER PRIMARY KEY,
                      total_predictions INTEGER DEFAULT 0,
                      today_count INTEGER DEFAULT 0,
                      daily_reset_at TEXT NULL,
                      monthly_predictions INTEGER DEFAULT 0,
                      last_prediction_at TEXT,
                      month_reset_at TEXT,
                      FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_counters_user_id ON usage_counters(user_id)")
                conn.commit()
                migrations_applied.append("Created usage_counters table")
            else:
                # Migration 6: Add monthly tracking columns to usage_counters
                if not check_column_exists(cursor, 'usage_counters', 'monthly_predictions'):
                    logger.info("🔄 Adding monthly_predictions to usage_counters...")
                    cursor.execute("ALTER TABLE usage_counters ADD COLUMN monthly_predictions INTEGER DEFAULT 0")
                    # Initialize monthly_predictions with current total_predictions for existing users
                    cursor.execute("UPDATE usage_counters SET monthly_predictions = total_predictions WHERE monthly_predictions IS NULL")
                    migrations_applied.append("Added monthly_predictions to usage_counters")
                
                if not check_column_exists(cursor, 'usage_counters', 'month_reset_at'):
                    logger.info("🔄 Adding month_reset_at to usage_counters...")
                    cursor.execute("ALTER TABLE usage_counters ADD COLUMN month_reset_at TEXT NULL")
                    migrations_applied.append("Added month_reset_at to usage_counters")
                
                # Migration 7: Add daily usage tracking columns
                if not check_column_exists(cursor, 'usage_counters', 'today_count'):
                    logger.info("🔄 Adding today_count to usage_counters...")
                    cursor.execute("ALTER TABLE usage_counters ADD COLUMN today_count INTEGER DEFAULT 0")
                    migrations_applied.append("Added today_count to usage_counters")
                
                if not check_column_exists(cursor, 'usage_counters', 'daily_reset_at'):
                    logger.info("🔄 Adding daily_reset_at to usage_counters...")
                    cursor.execute("ALTER TABLE usage_counters ADD COLUMN daily_reset_at TEXT NULL")
                    migrations_applied.append("Added daily_reset_at to usage_counters")
                
                # Migration 7: Add daily usage tracking columns
                if not check_column_exists(cursor, 'usage_counters', 'today_count'):
                    logger.info("🔄 Adding today_count to usage_counters...")
                    cursor.execute("ALTER TABLE usage_counters ADD COLUMN today_count INTEGER DEFAULT 0")
                    migrations_applied.append("Added today_count to usage_counters")
                
                if not check_column_exists(cursor, 'usage_counters', 'daily_reset_at'):
                    logger.info("🔄 Adding daily_reset_at to usage_counters...")
                    cursor.execute("ALTER TABLE usage_counters ADD COLUMN daily_reset_at TEXT NULL")
                    migrations_applied.append("Added daily_reset_at to usage_counters")
            
            # Migration 6: Create models table if missing
            if 'models' not in existing_tables:
                logger.info("🔄 Creating models table...")
                cursor.execute("""
                    CREATE TABLE models (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      filename TEXT,
                      size_bytes INTEGER,
                      backend TEXT DEFAULT 'tf',
                      classes INTEGER,
                      loaded INTEGER DEFAULT 0,
                      created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                migrations_applied.append("Created models table")
        
        if migrations_applied:
            logger.info(f"✅ Applied {len(migrations_applied)} migration(s):")
            for migration in migrations_applied:
                logger.info(f"   - {migration}")
        else:
            logger.info("✅ Database schema is up to date")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
    
    return migrations_applied


def create_tables_manually(cursor):
    """Create tables manually if schema.sql is not available"""
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id TEXT UNIQUE NOT NULL,
          username TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT,
          is_admin INTEGER DEFAULT 0,
          is_pro INTEGER DEFAULT 0,
          pro_expires_at TEXT NULL,
          theme TEXT DEFAULT 'light',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          last_login TEXT NULL
        )
    """)
    
    # Predictions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          filename TEXT,
          result TEXT,
          confidence REAL,
          topk_results TEXT,
          models_used TEXT,
          is_unknown INTEGER DEFAULT 0,
          timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # Payments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          amount_cents INTEGER,
          currency TEXT DEFAULT 'USD',
          card_last4 TEXT,
          card_brand TEXT,
          status TEXT,
          receipt_path TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          expires_at TEXT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # Usage counters table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_counters (
          user_id INTEGER PRIMARY KEY,
          total_predictions INTEGER DEFAULT 0,
          today_count INTEGER DEFAULT 0,
          daily_reset_at TEXT NULL,
          monthly_predictions INTEGER DEFAULT 0,
          last_prediction_at TEXT,
          month_reset_at TEXT,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # Models table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT,
          filename TEXT,
          size_bytes INTEGER,
          backend TEXT DEFAULT 'tf',
          classes INTEGER,
          loaded INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_customer_id ON users(customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_counters_user_id ON usage_counters(user_id)")


if __name__ == '__main__':
    # Run migrations when script is executed directly
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    migrate_database()

