import datetime
import time
from schwab.client import Client
import logging

class ContributionManager:
    def __init__(self, db_handler, schwab_manager):
        self.db = db_handler
        self.schwab = schwab_manager
        self.TxType = Client.Transactions.TransactionType
        self.logger = logging.getLogger(__name__)

    def update_daily_contributions(self, user_id, exclude_accounts=None, days_back=7):
        """
        Updates contribution history for a specific user ID (tucan or guinea).
        Handles account deduplication (prefer Guinea).
        """
        if exclude_accounts is None:
            exclude_accounts = set()

        # 1. Get Accounts from Schwab
        try:
            schwab_accounts = self.schwab.get_hashs()
        except Exception as e:
            self.logger.error(f"[{user_id}] Failed to get accounts: {e}")
            return

        if not schwab_accounts:
            print(f"[{user_id}] No accounts found.")
            return

        # 2. Get Existing Accounts from DB to map IDs
        # Assumes db_handler has a method to check existing accounts or we fetch all
        # db_accounts = self.db.get_all_accounts_map() 
        today = datetime.datetime.now()
        start_date = today - datetime.timedelta(days=days_back)

        
        # Ensure start_date is timezone aware or compliant with library expectations if needed.
        # Schwab client normally expects datetime objects.

        for acct_num, acct_hash in schwab_accounts.items():
            # EXCLUSION LOGIC
            if str(acct_num) == '37522548':
                print(f"[{user_id}] Skipping excluded account {acct_num}")
                continue
            
            if str(acct_num) in exclude_accounts:
                print(f"[{user_id}] Skipping excluded (already processed) account {acct_num}")
                continue

            # DEDUPLICATION LOGIC (Guinea Priority) is handled by caller passing exclude_accounts
            
            print(f"[{user_id}] Processing Account: {acct_num}")
            
            # 3. Determine Transaction Types & Fetch
            types = self._get_types_for_account(acct_num)
            
            try:
                client = self.schwab.get_client()
                
                # Fetch in chunks of 360 days to avoid "difference between the dates must not be more than a year" error
                chunk_size = 360
                date_cursor = start_date
                all_txs = []
                
                while date_cursor < today:
                    chunk_end = min(date_cursor + datetime.timedelta(days=chunk_size), today)
                    # print(f"  Fetching from {date_cursor.date()} to {chunk_end.date()}")
                    
                    resp = client.get_transactions(
                        acct_hash,
                        start_date=date_cursor,
                        end_date=chunk_end,
                        transaction_types=types
                    )
                    
                    if resp.status_code != 200:
                        self.logger.error(f"Failed to fetch transactions for {acct_num} ({date_cursor.date()}~{chunk_end.date()}): {resp.status_code} {resp.text}")
                    else:
                        chunk_txs = resp.json()
                        all_txs.extend(chunk_txs)
                    
                    # Move cursor forward
                    date_cursor = chunk_end + datetime.timedelta(seconds=1) # start next chunk just after

                # 4. Filter & Insert
                filtered_txs = self._filter_transactions(acct_num, all_txs)
                self._save_transactions(acct_num, filtered_txs)
                
            except Exception as e:
                print(f"Error processing {acct_num}: {e}")
                self.logger.error(f"Error processing {acct_num}: {e}")

    def _get_types_for_account(self, acct_num):
        # Special case for 96839515 
        if str(acct_num) == '96839515':
            return [
                self.TxType.CASH_RECEIPT,
                self.TxType.JOURNAL,
                self.TxType.ELECTRONIC_FUND,
                self.TxType.CASH_DISBURSEMENT,
                self.TxType.TRADE
            ]
        
        # Default Types for other accounts
        return [
            self.TxType.ACH_RECEIPT,
            self.TxType.WIRE_IN,
            self.TxType.ELECTRONIC_FUND,
            self.TxType.CASH_RECEIPT,
            self.TxType.JOURNAL,
            self.TxType.RECEIVE_AND_DELIVER
        ]

    def _filter_sweep_pairs(self, txs):
        """
        Removes offsetting sweep transactions that occur on the same day.
        e.g., +$100 "BANK SWEEP FR BROKERAGE" and -$100 "BROKERAGE SWEEP TO BANK"
        """
        from collections import defaultdict
        by_date = defaultdict(list)
        
        for tx in txs:
            # Parse date YYYY-MM-DD
            # tx['time'] is ISO8601 string e.g. "2023-01-01T12:00:00+0000"
            date_str = tx.get('time', '').split('T')[0]
            by_date[date_str].append(tx)
        
        final_list = []
        
        for date, day_txs in by_date.items():
            pos_candidates = [] 
            neg_candidates = []
            
            # Identify candidates
            for i, tx in enumerate(day_txs):
                desc = tx.get('description', '')
                amount = float(tx.get('netAmount', 0)) # Ensure float
                
                if amount > 0 and desc in ["BANK SWEEP FR BROKERAGE", "BROKERAGE SWEEP FR BANK"]:
                    pos_candidates.append(i)
                elif amount < 0 and desc in ["BROKERAGE SWEEP TO BANK", "BANK SWEEP TO BROKERAGE"]:
                    neg_candidates.append(i)
            
            matched_indices = set()
            
            # Match pairs
            for p_idx in pos_candidates:
                p_val = float(day_txs[p_idx].get('netAmount', 0))
                for n_idx in neg_candidates:
                    if n_idx in matched_indices: continue
                    
                    n_val = float(day_txs[n_idx].get('netAmount', 0))
                    if abs(p_val + n_val) < 0.0001:
                        matched_indices.add(p_idx)
                        matched_indices.add(n_idx)
                        break
            
            # Keep non-matched
            for i, tx in enumerate(day_txs):
                if i not in matched_indices:
                    final_list.append(tx)
                    
        return final_list

    def _filter_transactions(self, acct_num, txs):
        # 1. First, remove sweep pairs for ALL accounts
        filtered_txs = self._filter_sweep_pairs(txs)
        
        # 2. Apply Account Specific Logic
        final_txs = []
        
        if str(acct_num) == '96839515':
            for tx in filtered_txs:
                ttype = tx.get('type')
                desc = tx.get('description', '')
                
                # Unconditional Keep
                if ttype in ['CASH_RECEIPT', 'JOURNAL', 'ELECTRONIC_FUND', 'CASH_DISBURSEMENT']:
                    final_txs.append(tx)
                    continue
                    
                # Conditional TRADE Keep
                if ttype == 'TRADE':
                    is_goog = 'GOOG' in desc
                    if not is_goog:
                        # Check transfer items for symbol
                        for item in tx.get('transferItems', []):
                            if item.get('instrument', {}).get('symbol') == 'GOOG':
                                is_goog = True
                                break
                    
                    if is_goog:
                        final_txs.append(tx)
        else:
            # For other accounts, keep everything that passed the sweep filter
            final_txs = filtered_txs
        return final_txs

    def _save_transactions(self, acct_num, txs):
        sql = """
            INSERT IGNORE INTO contribution_history 
            (account_number, activity_id, transaction_date, type, amount, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        data = []
        for tx in txs:
            # Parse Date
            # Schwab returns ISO format "2023-01-01T12:00:00+0000"
            t_str = tx.get('time', '')
            try:
                # Convert to MySQL compatible datetime string or object
                # python-dateutil parser is good, but let's stick to str if possible
                # If t_str has +0000, datetime.fromisoformat might handle it in newer python versions
                # Or simplistic split
                dt = datetime.datetime.strptime(t_str.split('+')[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                # Fallback or strict format
                dt = t_str
            
            data.append((
                acct_num, 
                tx.get('activityId'), 
                dt, 
                tx.get('type'), 
                tx.get('netAmount'), 
                tx.get('description', '')
            ))
            
        if data:
            self.db.execute_many(sql, data)
            print(f"  Saved {len(data)} transactions.")
