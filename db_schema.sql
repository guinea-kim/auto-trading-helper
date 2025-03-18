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
    limit_price DECIMAL(10, 2) NOT NULL,
    target_amount INT NOT NULL,
    daily_money DECIMAL(10, 2) NOT NULL,
    current_holding INT NOT NULL,
    average_price decimal(10,2),
    last_price DECIMAL(10, 2) NOT NULL,
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
    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trading_rules_account_status ON trading_rules(account_id, status);

CREATE TABLE helper_db.daily_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    record_date DATE,
    account_id VARCHAR(20),
    symbol VARCHAR(10),
    amount DECIMAL(18, 2),
    UNIQUE KEY (record_date, account_id, symbol)
);

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
    limit_price DECIMAL(10) NOT NULL,
    target_amount INT NOT NULL,
    daily_money DECIMAL(10) NOT NULL,
    current_holding INT NOT NULL,
    average_price decimal(10,2),
    last_price DECIMAL(10) NOT NULL,
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
    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_trading_rules_account_status ON helper_kr_db.trading_rules(account_id, status);

CREATE TABLE helper_kr_db.daily_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    record_date DATE,
    account_id VARCHAR(20),
    symbol VARCHAR(6),
    amount DECIMAL(18, 2),
    UNIQUE KEY (record_date, account_id, symbol)
);