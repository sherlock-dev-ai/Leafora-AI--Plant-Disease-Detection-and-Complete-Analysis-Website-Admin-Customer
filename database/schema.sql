-- CropGuard Database Schema
-- SQLite schema for users, predictions, payments, usage tracking, and models

-- Users table with Pro subscription support
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id TEXT UNIQUE NOT NULL, -- e.g. CUST-20251123-0001
  username TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT,
  is_admin INTEGER DEFAULT 0,
  is_pro INTEGER DEFAULT 0,
  pro_expires_at TEXT NULL, -- ISO format datetime string
  theme TEXT DEFAULT 'light', -- 'light' or 'dark'
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_login TEXT NULL
);

-- Predictions table with top-k results and model tracking
CREATE TABLE IF NOT EXISTS predictions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  filename TEXT,
  result TEXT,
  confidence REAL,
  topk_results TEXT, -- JSON array of top-k predictions
  models_used TEXT,  -- JSON list of model names used
  is_unknown INTEGER DEFAULT 0, -- OOD/low confidence flag
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Payments table for Pro subscriptions
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  amount_cents INTEGER, -- Amount in cents (e.g., 9999 = $99.99)
  currency TEXT DEFAULT 'USD',
  card_last4 TEXT, -- Last 4 digits of card
  card_brand TEXT, -- Visa, Mastercard, etc.
  status TEXT, -- 'completed', 'pending', 'refunded'
  receipt_path TEXT, -- Path to receipt PDF
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NULL, -- When Pro subscription expires
  FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Usage counters for tracking free tier limits
CREATE TABLE IF NOT EXISTS usage_counters (
  user_id INTEGER PRIMARY KEY,
  total_predictions INTEGER DEFAULT 0,
  last_prediction_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Models table for tracking loaded models
CREATE TABLE IF NOT EXISTS models (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  filename TEXT,
  size_bytes INTEGER,
  backend TEXT DEFAULT 'tf',
  classes INTEGER,
  loaded INTEGER DEFAULT 0, -- 0 = not loaded, 1 = loaded
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_customer_id ON users(customer_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_counters_user_id ON usage_counters(user_id);

