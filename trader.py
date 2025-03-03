import multiprocess as mp
from library.schwab_manager import SchwabManager
from datetime import datetime
import time
from zoneinfo import ZoneInfo
from library.mysql_helper import DatabaseHandler
import json
from schwab.utils import Utils
from http import HTTPStatus
from enum import IntEnum

class OrderType(IntEnum):
    SELL = 0
    BUY = 1
class TradingSystem:
    def __init__(self):
        self.db_handler = DatabaseHandler()
        self.schwab_managers = {}  # {user_id: UserAuthManager}
        self.positions_by_account = {}  # {account_id: {symbol: quantity}}
        self.positions_result_by_account = {}
        self._market_hours = None

    def get_schwab_manager(self, user_id: str) -> SchwabManager:
        """Get or create user-specific Schwab manager"""
        if user_id not in self.schwab_managers:
            self.schwab_managers[user_id] = SchwabManager(user_id)
        return self.schwab_managers[user_id]

    def get_any_schwab_manager(self) -> SchwabManager:
        if not self.schwab_managers:
            raise ValueError("No Schwab managers available")

        first_user_id = next(iter(self.schwab_managers))
        return self.schwab_managers[first_user_id]
    def load_daily_positions(self, user_id: str):
        """하루 시작할 때 포지션 로드"""
        schwab = self.get_schwab_manager(user_id)
        account_hashs = schwab.get_hashs()
        for account_number, hash_value in account_hashs.items():
            self.db_handler.update_account_hash(account_number, hash_value)
            positions = schwab.get_positions(hash_value)
            self.positions_by_account[hash_value] = {
                symbol: quantity
                for symbol, quantity in positions.items()
            }
    def get_positions(self, user_id: str):
        schwab = self.get_schwab_manager(user_id)
        hash_list = self.db_handler.get_hash_value(user_id)
        for hash_value in hash_list:
            positions = schwab.get_positions_result(hash_value)
            self.positions_result_by_account[hash_value] = {
                symbol: data
                for symbol, data in positions.items()
            }

    def place_buy_order(self, rule: dict, quantity: int, price: float):
        schwab = self.get_schwab_manager(rule['user_id'])
        order = schwab.place_limit_buy_order(rule['hash_value'], rule['symbol'], quantity, price)
        if order.is_success:
            self.positions_by_account[rule['hash_value']][rule['symbol']] = (
                    self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0) + quantity
            )
            order_id = Utils(schwab, rule['hash_value']).extract_order_id(order)
            self.db_handler.record_trade(rule['account_id'], rule['id'], order_id, rule['symbol'], quantity, price, 'BUY')
            return True
        return False
    def place_sell_order(self, rule: dict, quantity: int, price: float):
        schwab = self.get_schwab_manager(rule['user_id'])
        order = schwab.place_limit_sell_order(rule['hash_value'], rule['symbol'], quantity, price)
        if order.is_success:
            self.positions_by_account[rule['hash_value']][rule['symbol']] = (
                    self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0) - quantity
            )
            order_id = Utils(schwab, rule['hash_value']).extract_order_id(order)
            self.db_handler.record_trade(rule['account_id'], rule['id'], order_id, rule['symbol'], quantity, price, 'SELL')
            return True
        return False
    def _update_market_hours(self) -> None:
        """Schwab API를 통해 market hours 업데이트"""
        try:
            # EQUITY 마켓 시간 조회
            schwab = self.get_any_schwab_manager()
            data = schwab.get_market_hours()
            if data.status_code == HTTPStatus.OK:
                market_hours = json.loads(data.content)
                is_open = market_hours['equity']['EQ']['isOpen']
                self._market_hours = is_open
        except Exception as e:
            self._market_hours = None
    def is_market_open(self) -> bool:
        now = datetime.now(ZoneInfo("America/Los_Angeles"))

        # 날짜가 바뀌었으면 market hours 업데이트
        if self._market_hours is None:
            self._update_market_hours()

        # market hours 정보가 있으면 그것을 사용
        if self._market_hours is not None and not self._market_hours:
            return self._market_hours

        # market hours 정보가 없으면 기본 시간 체크
        if now.weekday() >= 5:  # 주말
            return False

        current_time = now.time()
        default_market_open = datetime.strptime("06:30", "%H:%M").time()
        default_market_close = datetime.strptime("13:00", "%H:%M").time()

        if not (default_market_open <= current_time < default_market_close):
            return False

        return True
    def process_trading_rules(self):
        """모든 유저의 모든 계좌의 거래 규칙 처리"""

        # 각 유저의 각 계좌별 포지션 로드
        users = self.db_handler.get_users()
        for user in users:
            self.load_daily_positions(user)

        rules = self.db_handler.get_active_trading_rules()

        while self.is_market_open():
            try:
                for rule in rules:
                    schwab = self.get_any_schwab_manager()
                    symbol = rule['symbol']
                    last_price = schwab.get_last_price(symbol)

                    action = rule['trade_action']
                    if action == OrderType.BUY and last_price <= rule['limit_price']:
                        self.buy_stock(schwab, rule, last_price)
                    elif action == OrderType.SELL:
                        if last_price >= rule['limit_price']:
                            self.sell_stock(rule, last_price)

                time.sleep(1)

            except Exception as e:
                print(f"Error occurred: {e}")
                time.sleep(5)

        #update current_holding, last_price
        self.update_result(rules, users)

    def update_result(self, rules, users):
        for user in users:
            self.get_positions(user)
        for rule in rules:
            rule_id = rule['id']
            hash_value = rule['hash_value']
            symbol = rule['symbol']

            if hash_value not in self.positions_result_by_account or symbol not in self.positions_result_by_account[
                hash_value]:
                continue

            current_holding = self.positions_result_by_account[hash_value].get(symbol)['quantity']
            last_price = self.positions_result_by_account[hash_value].get(symbol)['last_price']
            average_price = self.positions_result_by_account[hash_value].get(symbol)['average_price']
            self.db_handler.update_current_price_quantity(rule_id, last_price, current_holding, average_price)

    def sell_stock(self, rule, last_price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        today_trading_quantity = self.db_handler.get_trade_today(rule['id'])
        max_shares = min(
            int(rule['daily_money'] / last_price) - today_trading_quantity,
            current_holding - rule['target_amount']
        )

        if max_shares <= 0:
            return

        if self.place_sell_order(rule, max_shares, last_price):
            if current_holding - max_shares <= rule['target_amount']:
                self.db_handler.update_rule_status(rule['id'], 'COMPLETED')
    def buy_stock(self, schwab, rule, last_price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        today_trading_quantity = self.db_handler.get_trade_today(rule['id'])
        max_shares = min(
            int(rule['daily_money'] / last_price) - today_trading_quantity,
            rule['target_amount'] - current_holding
        )

        if max_shares <= 0:
            return

        required_cash = max_shares * last_price
        current_cash = schwab.get_cash(rule['hash_value'])

        #돈이 부족하면 채권매도 시도
        if required_cash > current_cash:
            order = schwab.sell_etf_for_cash(
                rule['hash_value'],
                required_cash - current_cash,
                self.positions_by_account[rule['hash_value']]
            )
            if order.is_success:
                current_cash = schwab.get_cash(rule['hash_value'])

        #돈이 부족한 만큼 수량 조정해서 매수
        max_shares = min(max_shares, int(current_cash / last_price))
        if max_shares > 0:
            if self.place_buy_order(rule, max_shares, last_price):
                if current_holding + max_shares >= rule['target_amount']:
                    self.db_handler.update_rule_status(rule['id'], 'COMPLETED')
if __name__ == "__main__":
    mp.freeze_support()

    trading_system = TradingSystem()
    trading_system.process_trading_rules()