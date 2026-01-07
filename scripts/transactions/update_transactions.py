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
    
    # 1. Fetch Guinea's Accounts (Priority)
    # Note: 'guinea' user needs to be configured in secret.py / tokens
    try:
        guinea_mgr = SchwabManager('guinea')
        # We need to authenticate/get client to fetch accounts
        guinea_accts = guinea_mgr.get_hashs() # {number: hash}
    except Exception as e:
        print(f"Error initializing Guinea manager: {e}")
        guinea_accts = {}
    
    # 2. Fetch Tucan's Accounts
    try:
        tucan_mgr = SchwabManager('tucan')
        tucan_accts = tucan_mgr.get_hashs()
    except Exception as e:
        print(f"Error initializing Tucan manager: {e}")
        tucan_accts = {}
    
    # 3. Identify Overlap & Process
    processed_accounts = set()
    
    print("--- UPDATE TRANSACTIONS: GUINEA ---")
    if guinea_accts:
        mgr_guinea = ContributionManager(db, guinea_mgr)
        mgr_guinea.update_daily_contributions('guinea', exclude_accounts=processed_accounts, days_back=args.days)
        processed_accounts.update(map(str, guinea_accts.keys()))
    else:
        print("Skipping Guinea (No accounts or error)")
    
    print("\n--- UPDATE TRANSACTIONS: TUCAN ---")
    if tucan_accts:
        mgr_tucan = ContributionManager(db, tucan_mgr)
        # Pass exclude_accounts to skip those already processed by Guinea
        mgr_tucan.update_daily_contributions('tucan', exclude_accounts=processed_accounts, days_back=args.days)
    else:
        print("Skipping Tucan (No accounts or error)")

    print(f"[{datetime.now()}] Transaction Update Completed.")

if __name__ == "__main__":
    main()
