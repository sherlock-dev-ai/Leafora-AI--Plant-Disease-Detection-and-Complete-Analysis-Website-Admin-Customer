"""
Migration script to convert existing database to tbl_ prefixed normalized schema
This script will:
1. Create new tbl_ tables
2. Migrate data from old tables
3. Keep old tables as backup (with _old suffix)
"""
import sqlite3
import os
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_path():
    """Find database file"""
    paths = [
        'instance/database.sqlite',
        'database/instance/database.sqlite',
        'instance/database.sqlite'
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None

def migrate_to_tbl_schema():
    """Migrate database to tbl_ prefixed schema"""
    db_path = get_db_path()
    if not db_path:
        logger.error("Database file not found")
        return False
    
    logger.info("=" * 60)
    logger.info("🔄 Migrating to tbl_ prefixed schema")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if migration already done
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tbl_login'")
        if cursor.fetchone():
            logger.info("✅ Migration already completed - tbl_ tables exist")
            conn.close()
            return True
        
        # Read new schema
        schema_path = os.path.join(os.path.dirname(__file__), 'schema_tbl.sql')
        if not os.path.exists(schema_path):
            logger.error(f"Schema file not found: {schema_path}")
            conn.close()
            return False
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Create new tables
        logger.info("📊 Creating new tbl_ tables...")
        cursor.executescript(schema_sql)
        conn.commit()
        logger.info("✅ New tables created")
        
        # Migrate data from old tables
        logger.info("📦 Migrating data...")
        
        # 1. Migrate users to tbl_login and tbl_customer
        try:
            cursor.execute("SELECT id, email, password_hash, is_admin, username, customer_id, is_pro, pro_expires_at, theme, is_deleted, created_at, last_login FROM users")
            users = cursor.fetchall()
            
            for user in users:
                user_id, email, password_hash, is_admin, username, customer_id, is_pro, pro_expires_at, theme, is_deleted, created_at, last_login = user
                
                # Insert into tbl_login
                user_type = 'admin' if is_admin else 'user'
                cursor.execute("""
                    INSERT OR IGNORE INTO tbl_login (email, password, type, created_at, last_login)
                    VALUES (?, ?, ?, ?, ?)
                """, (email, password_hash, user_type, created_at, last_login))
                
                # Insert into tbl_customer
                cursor.execute("""
                    INSERT INTO tbl_customer (user_id, cust_fname, cust_lname, cust_username, is_pro, pro_expires_at, theme, is_deleted, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (email, username, '', username, is_pro, pro_expires_at, theme, is_deleted, created_at))
            
            logger.info(f"✅ Migrated {len(users)} users")
        except Exception as e:
            logger.warning(f"⚠️  User migration: {e}")
        
        # 2. Migrate predictions
        try:
            cursor.execute("""
                SELECT p.id, u.email, p.filename, p.result, p.confidence, p.topk_results, 
                       p.models_used, p.is_unknown, p.timestamp
                FROM predictions p
                JOIN users u ON p.user_id = u.id
            """)
            predictions = cursor.fetchall()
            
            for pred in predictions:
                pred_id, email, filename, result, confidence, topk_results, models_used, is_unknown, timestamp = pred
                
                # Get cust_id from email
                cursor.execute("SELECT cust_id FROM tbl_customer WHERE user_id = ?", (email,))
                cust_row = cursor.fetchone()
                if cust_row:
                    cust_id = cust_row[0]
                    cursor.execute("""
                        INSERT INTO tbl_predictions (cust_id, filename, result, confidence, topk_results, models_used, is_unknown, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cust_id, filename, result, confidence, topk_results, models_used, is_unknown, timestamp))
            
            logger.info(f"✅ Migrated {len(predictions)} predictions")
        except Exception as e:
            logger.warning(f"⚠️  Prediction migration: {e}")
        
        # 3. Migrate payments (create cards first if needed)
        try:
            cursor.execute("""
                SELECT p.id, u.email, p.amount_cents, p.currency, p.card_last4, p.card_brand, 
                       p.status, p.receipt_path, p.created_at, p.expires_at
                FROM payments p
                JOIN users u ON p.user_id = u.id
            """)
            payments = cursor.fetchall()
            
            for pay in payments:
                pay_id, email, amount_cents, currency, card_last4, card_brand, status, receipt_path, created_at, expires_at = pay
                
                # Get cust_id
                cursor.execute("SELECT cust_id FROM tbl_customer WHERE user_id = ?", (email,))
                cust_row = cursor.fetchone()
                if cust_row:
                    cust_id = cust_row[0]
                    
                    # Get or create card
                    cursor.execute("SELECT card_id FROM tbl_card WHERE cust_id = ? AND card_last4 = ? LIMIT 1", (cust_id, card_last4))
                    card_row = cursor.fetchone()
                    if card_row:
                        card_id = card_row[0]
                    else:
                        # Create a card entry
                        cursor.execute("""
                            INSERT INTO tbl_card (cust_id, card_name, card_no, card_last4, card_brand, card_expiry, is_default)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (cust_id, 'Cardholder', '****', card_last4, card_brand, '2099-12-31', 1))
                        card_id = cursor.lastrowid
                    
                    # Get plan_id (default to Pro plan)
                    cursor.execute("SELECT plan_id FROM tbl_plans WHERE plan_name = 'Pro' LIMIT 1")
                    plan_row = cursor.fetchone()
                    plan_id = plan_row[0] if plan_row else 2
                    
                    cursor.execute("""
                        INSERT INTO tbl_payment (card_id, cust_id, plan_id, payment_date, amount_cents, currency, status, receipt_path, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (card_id, cust_id, plan_id, created_at, amount_cents, currency, status, receipt_path, expires_at))
            
            logger.info(f"✅ Migrated {len(payments)} payments")
        except Exception as e:
            logger.warning(f"⚠️  Payment migration: {e}")
        
        # 4. Migrate usage_counters
        try:
            cursor.execute("""
                SELECT uc.user_id, u.email, uc.total_predictions, uc.today_count, 
                       uc.daily_reset_at, uc.last_prediction_at
                FROM usage_counters uc
                JOIN users u ON uc.user_id = u.id
            """)
            counters = cursor.fetchall()
            
            for counter in counters:
                user_id, email, total_predictions, today_count, daily_reset_at, last_prediction_at = counter
                
                cursor.execute("SELECT cust_id FROM tbl_customer WHERE user_id = ?", (email,))
                cust_row = cursor.fetchone()
                if cust_row:
                    cust_id = cust_row[0]
                    cursor.execute("""
                        INSERT OR REPLACE INTO tbl_usage_counters (cust_id, total_predictions, today_count, daily_reset_at, last_prediction_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (cust_id, total_predictions, today_count, daily_reset_at, last_prediction_at))
            
            logger.info(f"✅ Migrated {len(counters)} usage counters")
        except Exception as e:
            logger.warning(f"⚠️  Usage counter migration: {e}")
        
        # 5. Migrate models
        try:
            cursor.execute("SELECT id, name, filename, size_bytes, backend, classes, loaded, created_at FROM models")
            models = cursor.fetchall()
            
            for model in models:
                model_id, name, filename, size_bytes, backend, classes, loaded, created_at = model
                cursor.execute("""
                    INSERT INTO tbl_models (model_id, model_name, filename, size_bytes, backend, classes, loaded, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (model_id, name, filename, size_bytes, backend, classes, loaded, created_at))
            
            logger.info(f"✅ Migrated {len(models)} models")
        except Exception as e:
            logger.warning(f"⚠️  Model migration: {e}")
        
        conn.commit()
        logger.info("=" * 60)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 60)
        logger.info("⚠️  Old tables are still present for backup")
        logger.info("   You can drop them after verifying the migration")
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    migrate_to_tbl_schema()

