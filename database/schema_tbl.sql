-- CropGuard Database Schema - Normalized Design with tbl_ prefix
-- Following 1NF, 2NF, 3NF normalization principles

-- Table: 1 - Login Details
CREATE TABLE IF NOT EXISTS tbl_login (
  email VARCHAR(120) PRIMARY KEY,
  password VARCHAR(255) NOT NULL,
  type VARCHAR(10) NOT NULL DEFAULT 'user',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login DATETIME NULL
);

-- Table: 2 - Customer Details
CREATE TABLE IF NOT EXISTS tbl_customer (
  cust_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id VARCHAR(120) NOT NULL UNIQUE,
  cust_fname VARCHAR(50) NOT NULL,
  cust_lname VARCHAR(50) NOT NULL,
  cust_username VARCHAR(80) NOT NULL UNIQUE,
  cust_phone VARCHAR(15) NULL,
  cust_city VARCHAR(50) NULL,
  cust_district VARCHAR(50) NULL,
  cust_state VARCHAR(50) NULL,
  cust_pincode VARCHAR(10) NULL,
  cust_country VARCHAR(50) NULL,
  is_pro INTEGER DEFAULT 0,
  pro_expires_at DATETIME NULL,
  theme VARCHAR(10) DEFAULT 'light',
  is_deleted INTEGER DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES tbl_login(email)
);

-- Table: 3 - Subscription Plans
CREATE TABLE IF NOT EXISTS tbl_plans (
  plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_name VARCHAR(50) NOT NULL UNIQUE,
  plan_price DECIMAL(10,2) NOT NULL,
  plan_duration INTEGER NOT NULL,
  daily_limit INTEGER NULL,
  features TEXT NULL,
  is_active INTEGER DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table: 4 - Card Details
CREATE TABLE IF NOT EXISTS tbl_card (
  card_id INTEGER PRIMARY KEY AUTOINCREMENT,
  cust_id INTEGER NOT NULL,
  card_name VARCHAR(50) NOT NULL,
  card_no VARCHAR(20) NOT NULL,
  card_last4 VARCHAR(4) NOT NULL,
  card_brand VARCHAR(20) NOT NULL,
  card_expiry DATE NOT NULL,
  is_default INTEGER DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(cust_id) REFERENCES tbl_customer(cust_id)
);

-- Table: 5 - Subscription Details
CREATE TABLE IF NOT EXISTS tbl_subscription (
  subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
  cust_id INTEGER NOT NULL,
  plan_id INTEGER NOT NULL,
  start_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  end_date DATETIME NULL,
  expires_at DATETIME NULL,
  status VARCHAR(20) DEFAULT 'active',
  is_active INTEGER DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL,
  FOREIGN KEY(cust_id) REFERENCES tbl_customer(cust_id),
  FOREIGN KEY(plan_id) REFERENCES tbl_plans(plan_id)
);

-- Table: 6 - Payment Details
CREATE TABLE IF NOT EXISTS tbl_payment (
  payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subscription_id INTEGER NOT NULL,
  card_id INTEGER NULL,
  payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  amount_cents INTEGER NOT NULL,
  currency VARCHAR(3) DEFAULT 'USD',
  status VARCHAR(20) DEFAULT 'completed',
  receipt_path VARCHAR(255) NULL,
  FOREIGN KEY(subscription_id) REFERENCES tbl_subscription(subscription_id),
  FOREIGN KEY(card_id) REFERENCES tbl_card(card_id)
);

-- Table: 7 - Disease Prediction Results
CREATE TABLE IF NOT EXISTS tbl_predictions (
  prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
  cust_id INTEGER NOT NULL,
  filename VARCHAR(255) NOT NULL,
  result VARCHAR(100) NOT NULL,
  confidence DECIMAL(5,2) NOT NULL,
  topk_results TEXT NULL,
  models_used TEXT NULL,
  is_unknown INTEGER DEFAULT 0,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(cust_id) REFERENCES tbl_customer(cust_id)
);

-- Table: 8 - Usage Tracking
CREATE TABLE IF NOT EXISTS tbl_usage_counters (
  cust_id INTEGER PRIMARY KEY,
  total_predictions INTEGER DEFAULT 0,
  today_count INTEGER DEFAULT 0,
  daily_reset_at DATETIME NULL,
  last_prediction_at DATETIME NULL,
  FOREIGN KEY(cust_id) REFERENCES tbl_customer(cust_id)
);

-- Table: 9 - Model Tracking
CREATE TABLE IF NOT EXISTS tbl_models (
  model_id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_name VARCHAR(255) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  size_bytes BIGINT NOT NULL,
  backend VARCHAR(10) DEFAULT 'tf',
  classes INTEGER NOT NULL,
  loaded INTEGER DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_login_email ON tbl_login(email);
CREATE INDEX IF NOT EXISTS idx_customer_user_id ON tbl_customer(user_id);
CREATE INDEX IF NOT EXISTS idx_customer_cust_id ON tbl_customer(cust_id);
CREATE INDEX IF NOT EXISTS idx_card_cust_id ON tbl_card(cust_id);
CREATE INDEX IF NOT EXISTS idx_subscription_cust_id ON tbl_subscription(cust_id);
CREATE INDEX IF NOT EXISTS idx_subscription_plan_id ON tbl_subscription(plan_id);
CREATE INDEX IF NOT EXISTS idx_subscription_status ON tbl_subscription(status);
CREATE INDEX IF NOT EXISTS idx_payment_subscription_id ON tbl_payment(subscription_id);
CREATE INDEX IF NOT EXISTS idx_payment_card_id ON tbl_payment(card_id);
CREATE INDEX IF NOT EXISTS idx_predictions_cust_id ON tbl_predictions(cust_id);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON tbl_predictions(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_counters_cust_id ON tbl_usage_counters(cust_id);

-- Insert default plans
INSERT OR IGNORE INTO tbl_plans (plan_name, plan_price, plan_duration, daily_limit, features, is_active) VALUES
('Basic', 0.00, 365, 3, '["Single model results", "Basic disease identification", "3 detections per day"]', 1),
('Pro', 9.99, 30, NULL, '["Unlimited detections", "Multi-model ensemble results", "Per-model breakdown", "Priority processing"]', 1);

