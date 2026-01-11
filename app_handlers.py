from library.mysql_helper import DatabaseHandler
from library import secret

# DB Handler 인스턴스 생성
try:
    us_db_handler = DatabaseHandler(secret.db_name)
    kr_db_handler = DatabaseHandler(secret.db_name_kr)
except Exception as e:
    print(f"Warning: DB Connection failed ({e}). Starting in Offline Mode with Mock Data.")
    class MockHandler:
        def get_accounts(self, *args, **kwargs): return []
        def get_trading_rules(self, *args, **kwargs): return []
        def get_consolidated_portfolio_allocation(self, *args, **kwargs): return [], 0
        def get_daily_total_values(self, *args, **kwargs): return []
        def get_users(self, *args, **kwargs): return []
        def generate_account_id(self, *args, **kwargs): return "mock_id"
        def add_account(self, *args, **kwargs): pass
        def add_trading_rule(self, *args, **kwargs): pass
        def update_account_contribution(self, *args, **kwargs): pass
        def update_account_type(self, *args, **kwargs): pass
        def update_rule_status(self, *args, **kwargs): pass
        def get_highest_price(self, *args, **kwargs): return 0
        def get_contribution_history(self, *args, **kwargs): return []
        def get_daily_contributions(self, *args, **kwargs): return {}
        def get_daily_records_breakdown(self, *args, **kwargs): return []
        def get_adjacent_date(self, *args, **kwargs): return None
        def update_daily_record(self, *args, **kwargs): pass
        def upsert_daily_record(self, *args, **kwargs): return 1
        def update_rule_field(self, *args, **kwargs): pass
        def add_kr_trading_rule(self, *args, **kwargs): pass

    us_db_handler = MockHandler()
    kr_db_handler = MockHandler()
