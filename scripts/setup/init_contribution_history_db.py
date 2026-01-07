import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from library.mysql_helper import DatabaseHandler
from library import secret
from sqlalchemy import text

def main():
    print("Initializing Database...")
    db = DatabaseHandler(secret.db_name)
    
    sql = """
    CREATE TABLE IF NOT EXISTS contribution_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        account_number VARCHAR(20) NOT NULL,
        activity_id BIGINT NOT NULL UNIQUE,  -- Prevents duplicate entries
        transaction_date DATETIME NOT NULL,
        type VARCHAR(50) NOT NULL,           -- e.g., 'JOURNAL', 'ELECTRONIC_FUND'
        amount DECIMAL(15, 2) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_account_date (account_number, transaction_date),
        FOREIGN KEY (account_number) REFERENCES accounts(account_number)
    );
    """
    
    print("Executing SQL:")
    print(sql)

    try:
        with db.engine.connect() as conn:
            # Ensure accounts.account_number is unique/indexed for FK reference
            try:
                print("Attempting to add UNIQUE INDEX on accounts(account_number)...")
                conn.execute(text("CREATE UNIQUE INDEX idx_account_number ON accounts(account_number)"))
                conn.commit()
                print("Added UNIQUE INDEX on accounts(account_number)")
            except Exception as index_err:
                 print(f"Index creation skipped (likely exists): {index_err}")

            conn.execute(text(sql))
            conn.commit()
        print("Table contribution_history created successfully (if not existed).")
    except Exception as e:
        print(f"Error creating table: {e}")
        # Don't raise, allowing user to see error.

if __name__ == "__main__":
    main()
