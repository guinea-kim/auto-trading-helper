import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from library.mysql_helper import DatabaseHandler

def verify_methods():
    methods = [
        # AccountMixin
        'get_accounts', 'get_users', 'get_hash_value', 'get_user_accounts',
        'update_account_hash', 'update_account_cash_balance', 
        'update_account_contribution', 'update_account_type', 
        'update_account_total_value', 'add_account', 'generate_account_id',
        
        # TradingRuleMixin
        'get_active_trading_rules', 'get_all_trading_rules', 'get_trading_rules',
        'get_periodic_rules', 'update_rule_status', 'update_current_price_quantity',
        'update_rule_field', 'update_split_and_merge_adjustment', 
        'add_trading_rule', 'add_kr_trading_rule', 'get_highest_price',
        
        # HistoryMixin
        'get_trade_today', 'record_trade', 'get_contribution_history',
        'add_daily_result', 'get_consolidated_portfolio_allocation',
        'get_daily_total_values', 'get_daily_contributions', 
        'get_daily_records_by_date', 'get_daily_records_breakdown',
        'get_adjacent_date', 'update_daily_record', 'upsert_daily_record',
        
        # Base
        'is_database_exist', 'execute_many'
    ]
    
    missing = []
    for method in methods:
        if not hasattr(DatabaseHandler, method):
            missing.append(method)
            
    if missing:
        print(f"❌ FAILED: Missing methods: {missing}")
        sys.exit(1)
    else:
        print("✅ SUCCESS: All methods present on DatabaseHandler")

if __name__ == "__main__":
    verify_methods()
