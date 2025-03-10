from library.mysql_helper import DatabaseHandler
from library.schwab_manager import SchwabManager
from schwab.utils import Utils
from library import secret
from strategies.market_strategy import MarketStrategy

class SchwabMarketStrategy(MarketStrategy):
    """Strategy for US market using Schwab"""

    def __init__(self):
        self.db_handler = DatabaseHandler(secret.db_name)
        self.managers = {}

    def get_manager(self, user_id):
        if user_id not in self.managers:
            self.managers[user_id] = SchwabManager(user_id)
        return self.managers[user_id]

    def get_db_handler(self):
        return self.db_handler

    def extract_order_id(self, manager, hash_value, order):
        return Utils(manager, hash_value).extract_order_id(order)