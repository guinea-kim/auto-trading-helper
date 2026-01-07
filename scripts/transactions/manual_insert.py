import sys
import os
from sqlalchemy import text
from decimal import Decimal
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from library.mysql_helper import DatabaseHandler
from library import secret

def insert_manual_transaction():
    db = DatabaseHandler(secret.db_name)
    
    # Target Data
    target_account = 'YOUR_ACCOUNT_NUMBER'
    target_date = '2025-01-14'
    target_amount = 7000.00
    target_description = 'IRA ROTH CONV'
    target_type = 'JOURNAL'

    print(f"\nChecking Account {target_account} for {target_date}, ${target_amount}")
    
    # Check for existing transactions on that day
    # We check for ANY transaction on that day with similar amount to be safe, 
    # or just trust the user's "if value exists" instruction.
    sql_check = """
        SELECT * FROM contribution_history 
        WHERE account_number = :acc 
        AND DATE(transaction_date) = :date
        AND amount BETWEEN :min_amt AND :max_amt
    """
    
    with db.engine.connect() as conn:
        result = conn.execute(text(sql_check), {
            "acc": target_account,
            "date": target_date,
            "min_amt": target_amount - 10, 
            "max_amt": target_amount + 10
        }).fetchall()
        
        if result:
            print(f"  [SKIP] Found similar transaction(s):")
            for row in result:
                print(f"    - ID: {row.id}, Date: {row.transaction_date}, Amount: {row.amount}, Desc: {row.description}")
            return

    print("  [INSERT] No duplicates found. Preparing to insert...")
    
    # Generate a unique pseudo_id
    pseudo_id = int(time.time() * 1000) * -1 
    
    sql_insert = """
        INSERT INTO contribution_history 
        (account_number, activity_id, transaction_date, type, amount, description)
        VALUES (:acc, :act_id, :date, :type, :amt, :desc)
    """
    
    try:
        with db.engine.connect() as conn:
            conn.execute(text(sql_insert), {
                "acc": target_account,
                "act_id": pseudo_id,
                "date": f"{target_date} 12:00:00", 
                "type": target_type,
                "amt": target_amount,
                "desc": target_description
            })
            conn.commit()
        print(f"  [SUCCESS] Inserted manual record. Activity ID: {pseudo_id}")
    except Exception as e:
        print(f"  [ERROR] Failed to insert: {e}")

if __name__ == "__main__":
    insert_manual_transaction()
