CREATE USER 'db_id'@'localhost' IDENTIFIED BY 'password';
CREATE DATABASE IF NOT EXISTS helper_db;
USE helper_db;
GRANT ALL PRIVILEGES ON helper_db.* TO 'db_id'@'localhost';
-- accounts 테이블 생성
CREATE TABLE accounts (
    id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    description VARCHAR(50) NOT NULL,
    hash_value VARCHAR(70),
    account_number varchar(20),
    cash_balance DECIMAL(10, 2) DEFAULT 0.00,
    contribution DECIMAL(15,2) DEFAULT 0.00,
    total_value DECIMAL(15,2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- trading_rules 테이블 생성
CREATE TABLE trading_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(20) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    trade_action TINYINT NOT NULL,
    limit_value DECIMAL(10, 2) NOT NULL,
    limit_type ENUM('price', 'percent', 'high_percent') NOT NULL DEFAULT 'price',
    target_amount INT NOT NULL,
    daily_money DECIMAL(10, 2) NOT NULL,
    current_holding INT NOT NULL,
    average_price decimal(10,2),
    last_price DECIMAL(10, 2) NOT NULL,
    high_price DECIMAL(10, 2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('ACTIVE', 'COMPLETED', 'CANCELLED') DEFAULT 'ACTIVE'
);

CREATE TABLE trade_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(20) NOT NULL,
    trading_rule_id INT NOT NULL,
    order_id VARCHAR(10) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    trade_type ENUM('BUY', 'SELL') NOT NULL,
    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_money DECIMAL(20,2)
);

CREATE INDEX idx_trading_rules_account_status ON trading_rules(account_id, status);

CREATE TABLE helper_db.daily_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    record_date DATE,
    account_id VARCHAR(20),
    symbol VARCHAR(10),
    quantity DECIMAL(15, 6) DEFAULT 0,
    amount DECIMAL(18, 2),
    UNIQUE KEY (record_date, account_id, symbol)
);

CREATE TABLE contribution_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_number VARCHAR(20) NOT NULL,
    activity_id BIGINT NOT NULL UNIQUE,
    transaction_date DATETIME NOT NULL,
    type VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_account_date (account_number, transaction_date),
    FOREIGN KEY (account_number) REFERENCES accounts(account_number)
);

CREATE UNIQUE INDEX idx_account_number ON accounts(account_number);

-------------kr
CREATE DATABASE IF NOT EXISTS helper_kr_db;
USE helper_kr_db;
-- accounts 테이블 생성
CREATE TABLE helper_kr_db.accounts (
    id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    description VARCHAR(50) NOT NULL,
    hash_value VARCHAR(70),
    account_number varchar(20),
    cash_balance DECIMAL(10, 2) DEFAULT 0.00,
    contribution DECIMAL(15) DEFAULT 0,
    total_value DECIMAL(15,2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
CREATE TABLE helper_kr_db.trading_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(20) NOT NULL,
    symbol VARCHAR(6) NOT NULL,
    stock_name text NOT NULL,
    trade_action TINYINT NOT NULL,
    limit_value DECIMAL(10) NOT NULL,
    limit_type ENUM('price', 'percent', 'high_percent') NOT NULL DEFAULT 'price',
    target_amount INT NOT NULL,
    daily_money DECIMAL(10) NOT NULL,
    current_holding INT NOT NULL,
    average_price decimal(10,2),
    last_price DECIMAL(10) NOT NULL,
    high_price DECIMAL(10) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('ACTIVE', 'COMPLETED', 'CANCELLED') DEFAULT 'ACTIVE'
);
CREATE TABLE helper_kr_db.trade_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(20) NOT NULL,
    trading_rule_id INT NOT NULL,
    order_id VARCHAR(10) NOT NULL,
    symbol VARCHAR(6) NOT NULL,
    stock_name text NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10) NOT NULL,
    trade_type ENUM('BUY', 'SELL') NOT NULL,
    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_money DECIMAL(20,2)
);
CREATE INDEX idx_trading_rules_account_status ON helper_kr_db.trading_rules(account_id, status);

CREATE TABLE helper_kr_db.daily_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    record_date DATE,
    account_id VARCHAR(20),
    symbol VARCHAR(255),
    quantity DECIMAL(15, 6) DEFAULT 0,
    amount DECIMAL(18, 2),
    UNIQUE KEY (record_date, account_id, symbol)
);