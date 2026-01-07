import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from library.mysql_helper import DatabaseHandler
from library.schwab_manager import SchwabManager
from library.contribution_manager import ContributionManager
from library import secret

def main():
    parser = argparse.ArgumentParser(description='Update contribution history')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back')
    args = parser.parse_args()
    
    print(f"[{datetime.now()}] Starting Transaction Update (Lookback: {args.days} days)...")
    db = DatabaseHandler(secret.db_name)
    
    try:
        users = db.get_users()
        print(f"Found users in DB: {users}")
    except Exception as e:
        print(f"Error fetching users from DB: {e}")
        return

    # Process each user
    for user_id in users:
        print(f"\n--- UPDATE TRANSACTIONS: {user_id} ---")
        try:
            # Initialize Schwab Manager for this user
            # Note: This assumes credentials for user_id are available in secret.py/tokens
            schwab_mgr = SchwabManager(user_id)
            
            # Initialize Contribution Manager
            # We rely on ContributionManager's internal logic (via DB ownership & account type) 
            # to skip shared accounts owned by other users or excluded accounts.
            contrib_mgr = ContributionManager(db, schwab_mgr)
            
            contrib_mgr.update_daily_contributions(user_id, days_back=args.days)
            
        except Exception as e:
            print(f"Error processing user {user_id}: {e}")
            # Continue to next user even if one fails
            continue

    print(f"\n[{datetime.now()}] Transaction Update Completed.")

if __name__ == "__main__":
    main()
