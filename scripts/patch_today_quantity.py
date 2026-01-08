from sqlalchemy import create_engine, text
import sys
import os
import datetime
import pymysql
pymysql.install_as_MySQLdb()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library import secret

def get_engine(db_name):
    return create_engine(
        f"mysql+mysqldb://{secret.db_id}:{secret.db_passwd}@{secret.db_ip}:{secret.db_port}/{db_name}",
        pool_recycle=3600
    )

def patch_today_quantity(engine, db_name):
    print(f"Patching database: {db_name}")
    
    with engine.connect() as conn:
        # 1. Get the latest record date
        date_sql = "SELECT MAX(record_date) FROM daily_records"
        latest_date = conn.execute(text(date_sql)).scalar()
        
        if not latest_date:
            print("  - No records found in daily_records.")
            return

        print(f"  - Target Date (Latest): {latest_date}")
        
        # 2. Update records for that date
        update_sql = """
            UPDATE daily_records d
            JOIN trading_rules t ON d.account_id = t.account_id AND d.symbol = t.symbol
            SET d.quantity = t.current_holding
            WHERE d.record_date = :target_date
            AND (d.quantity IS NULL OR d.quantity = 0)
            AND d.symbol NOT IN ('total', 'cash')
        """
        
        result = conn.execute(text(update_sql), {"target_date": latest_date})
        conn.commit()
        print(f"  - Updated {result.rowcount} records.")

if __name__ == "__main__":
    try:
        # Patch US DB
        us_engine = get_engine(secret.db_name)
        patch_today_quantity(us_engine, secret.db_name)
        
        # Patch KR DB
        kr_engine = get_engine(secret.db_name_kr)
        patch_today_quantity(kr_engine, secret.db_name_kr)
        
        print("\nPatch completed successfully.")
    except Exception as e:
        print(f"\nPatch failed: {e}")
        sys.exit(1)
