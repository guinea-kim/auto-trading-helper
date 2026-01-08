from sqlalchemy import create_engine, text
import sys
import os
import pymysql
pymysql.install_as_MySQLdb()

# Add project root to path to import library
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library import secret

def get_engine(db_name):
    return create_engine(
        f"mysql+mysqldb://{secret.db_id}:{secret.db_passwd}@{secret.db_ip}:{secret.db_port}/{db_name}",
        pool_recycle=3600
    )

def add_column_safe(engine, db_name):
    print(f"Checking database: {db_name}")
    with engine.connect() as conn:
        # Check if column exists
        check_sql = """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name
            AND TABLE_NAME = 'daily_records'
            AND COLUMN_NAME = 'quantity'
        """
        result = conn.execute(text(check_sql), {"db_name": db_name}).fetchone()
        
        if result[0] > 0:
            print(f"  - Column 'quantity' already exists in '{db_name}'. Skipping.")
        else:
            print(f"  - Adding 'quantity' column to '{db_name}'...")
            alter_sql = """
                ALTER TABLE daily_records
                ADD COLUMN quantity DECIMAL(15, 6) DEFAULT 0 AFTER symbol
            """
            conn.execute(text(alter_sql))
            print("  - Done.")

if __name__ == "__main__":
    try:
        # US DB
        us_engine = get_engine(secret.db_name)
        add_column_safe(us_engine, secret.db_name)
        
        # KR DB
        kr_engine = get_engine(secret.db_name_kr)
        add_column_safe(kr_engine, secret.db_name_kr)
        
        print("\nMigration completed successfully.")
    except Exception as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)
