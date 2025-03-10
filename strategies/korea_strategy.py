from library.mysql_helper import DatabaseHandler
from library.korea_manager import KoreaManager
from library import secret
from strategies.market_strategy import MarketStrategy

class KoreaMarketStrategy(MarketStrategy):
    """Strategy for Korean market using KoreaManager"""

    def __init__(self):
        self.db_handler = DatabaseHandler(secret.db_name_kr)
        self.managers = {}

    def get_manager(self, user_id):
        if user_id not in self.managers:
            self.managers[user_id] = KoreaManager(user_id)
        return self.managers[user_id]

    def get_db_handler(self):
        return self.db_handler

    def extract_order_id(self, manager, hash_value, order):
        return order.order_id  # Korea manager returns order_id directly