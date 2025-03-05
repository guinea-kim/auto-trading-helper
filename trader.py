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
from library.logger_config import setup_logger
from library.alert import SendMessage


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
        self.logger = setup_logger("trading_system", "log")

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
        self.logger.info(f"Loading daily positions for user {user_id}")
        schwab = self.get_schwab_manager(user_id)
        try:
            account_hashs = schwab.get_hashs()
            for account_number, hash_value in account_hashs.items():
                self.db_handler.update_account_hash(account_number, hash_value)
                positions = schwab.get_positions(hash_value)
                self.positions_by_account[hash_value] = {
                    symbol: quantity
                    for symbol, quantity in positions.items()
                }
                self.logger.info(f"Loaded positions for account {account_number}: {positions}")
        except Exception as e:
            self.logger.error(f"Error loading positions for user {user_id}: {str(e)}")

    def get_positions(self, user_id: str):
        self.logger.info(f"Getting current positions for user {user_id}")
        schwab = self.get_schwab_manager(user_id)
        try:
            hash_list = self.db_handler.get_hash_value(user_id)
            for hash_value in hash_list:
                positions = schwab.get_positions_result(hash_value)
                self.positions_result_by_account[hash_value] = {
                    symbol: data
                    for symbol, data in positions.items()
                }
                self.logger.debug(f"Retrieved positions for hash {hash_value}: {positions}")
        except Exception as e:
            self.logger.error(f"Error getting positions for user {user_id}: {str(e)}")

    def place_buy_order(self, rule: dict, quantity: int, price: float):
        self.logger.info(f"Placing buy order for rule {rule['id']}: {rule['symbol']} - {quantity} shares at ${price}")
        schwab = self.get_schwab_manager(rule['user_id'])
        try:
            order = schwab.place_limit_buy_order(rule['hash_value'], rule['symbol'], quantity, price)
            if order.is_success:
                self.positions_by_account[rule['hash_value']][rule['symbol']] = (
                        self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0) + quantity
                )
                order_id = Utils(schwab, rule['hash_value']).extract_order_id(order)
                self.db_handler.record_trade(rule['account_id'], rule['id'], order_id, rule['symbol'], quantity, price,
                                             'BUY')

                # 매매 성공 알림 메시지 생성 및 전송
                alert_msg = self._create_buy_alert_message(rule, quantity, price)
                SendMessage(alert_msg)
                self.logger.info(f"Buy order placed successfully: {order_id}")
                return True
            else:
                self.logger.error(f"Failed to place buy order for {rule['symbol']}: {order}")
                return False
        except Exception as e:
            self.logger.error(f"Error during buy order for {rule['symbol']}: {str(e)}")
            return False

    def place_sell_order(self, rule: dict, quantity: int, price: float):
        self.logger.info(f"Placing sell order for rule {rule['id']}: {rule['symbol']} - {quantity} shares at ${price}")
        schwab = self.get_schwab_manager(rule['user_id'])
        try:
            order = schwab.place_limit_sell_order(rule['hash_value'], rule['symbol'], quantity, price)
            if order.is_success:
                self.positions_by_account[rule['hash_value']][rule['symbol']] = (
                        self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0) - quantity
                )
                order_id = Utils(schwab, rule['hash_value']).extract_order_id(order)
                self.db_handler.record_trade(rule['account_id'], rule['id'], order_id, rule['symbol'], quantity, price,
                                             'SELL')

                # 매매 성공 알림 메시지 생성 및 전송
                alert_msg = self._create_sell_alert_message(rule, quantity, price)
                SendMessage(alert_msg)
                self.logger.info(f"Sell order placed successfully: {order_id}")
                return True
            else:
                self.logger.error(f"Failed to place sell order for {rule['symbol']}: {order}")
                return False
        except Exception as e:
            self.logger.error(f"Error during sell order for {rule['symbol']}: {str(e)}")
            return False

    def _create_buy_alert_message(self, rule, quantity, price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        new_holding = current_holding + quantity
        total_cost = quantity * price

        message = f"""
[BUY ORDER]
Account: {rule['description']} ({rule['user_id']})
Symbol: {rule['symbol']}
Purchase Price: ${price:.2f}
Quantity: {quantity}주
Total Cost: ${total_cost:.2f}
                    
Condition:
- ${price:.2f} <= Limit Price(${rule['limit_price']:.2f})
- Target Quantity: {rule['target_amount']}
- Updated Quantity: {current_holding} -> {new_holding}
- Daily Money Limit: ${rule['daily_money']:.2f}
                    
Order At {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
        return message

    def _create_sell_alert_message(self, rule, quantity, price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        new_holding = current_holding - quantity
        total_sale = quantity * price

        message = f"""
[SELL ORDER]
Account: {rule['account_id']} ({rule['user_id']})
Symbol: {rule['symbol']}
Sell Price: ${price:.2f}
Quantity: {quantity}주
Total Sale: ${total_sale:.2f}
                    
Condition:
- ${price:.2f} >= Limit Price(${rule['limit_price']:.2f})
- Target Quantity: {rule['target_amount']}주
- Updated Quantity: {current_holding}주 -> {new_holding}주
- Daily Money Limit: ${rule['daily_money']:.2f}
                    
Order At {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
        return message

    def _update_market_hours(self, now) -> None:
        """Schwab API를 통해 market hours 업데이트"""
        try:
            # EQUITY 마켓 시간 조회
            schwab = self.get_any_schwab_manager()
            data = schwab.get_market_hours()
            if data.status_code == HTTPStatus.OK:
                market_hours = json.loads(data.content)
                equity_data = market_hours.get('equity', {}).get('EQ', {})

                if not equity_data.get('isOpen', False):
                    self._market_hours = False
                    return

                # 정규장 시간 파싱
                session_hours = equity_data.get('sessionHours', {})
                regular_market = session_hours.get('regularMarket', [])

                if regular_market:
                    # 첫 번째 정규장 세션 사용 (보통 하나만 있음)
                    session = regular_market[0]

                    # 시작 시간과 종료 시간 파싱 (이미 ISO 형식으로 되어 있음)
                    start_time_et = datetime.fromisoformat(session['start'])
                    end_time_et = datetime.fromisoformat(session['end'])

                    # ET를 PT로 변환 (tzinfo가 이미 설정되어 있으므로 단순히 변환만 수행)
                    start_time_pt = start_time_et.astimezone(ZoneInfo("America/Los_Angeles"))
                    end_time_pt = end_time_et.astimezone(ZoneInfo("America/Los_Angeles"))

                    # 현재 시간이 시작 시간과 종료 시간 사이인지 확인
                    self._market_hours = start_time_pt <= now < end_time_pt
        except Exception as e:
            self.logger.error(f"Error updating market hours: {str(e)}")
            self._market_hours = None

    def is_market_open(self) -> bool:
        now = datetime.now(ZoneInfo("America/Los_Angeles"))

        # market hours 정보가 없으면 기본 시간 체크
        if now.weekday() >= 5:  # 주말
            self.logger.info("Market is closed (weekend)")
            return False

        # 날짜가 바뀌었으면 market hours 업데이트
        if self._market_hours is None:
            self._update_market_hours(now)

        # market hours 정보가 있으면 그것을 사용
        if self._market_hours is not None:
            return self._market_hours

        current_time = now.time()
        default_market_open = datetime.strptime("06:30", "%H:%M").time()
        default_market_close = datetime.strptime("13:00", "%H:%M").time()

        if not (default_market_open <= current_time < default_market_close):
            self.logger.info(f"Market is closed (outside trading hours): current time is {current_time}")
            return False

        return True

    def process_trading_rules(self):
        """모든 유저의 모든 계좌의 거래 규칙 처리"""
        self.logger.info("Starting trading rule processing")

        # 각 유저의 각 계좌별 포지션 로드
        users = self.db_handler.get_users()
        for user in users:
            self.load_daily_positions(user)

        rules = self.db_handler.get_active_trading_rules()
        self.logger.info(f"Loaded {len(rules)} active trading rules")

        while self.is_market_open():
            try:
                for rule in rules:
                    symbol = rule['symbol']
                    schwab = self.get_schwab_manager(rule['user_id'])
                    last_price = schwab.get_last_price(symbol)
                    self.logger.debug(f"Current price for {symbol}: ${last_price}")

                    action = rule['trade_action']
                    if action == OrderType.BUY and last_price <= rule['limit_price']:
                        self.logger.info(
                            f"Buy condition met for {symbol}: price ${last_price} <= limit ${rule['limit_price']}")
                        self.buy_stock(schwab, rule, last_price)
                    elif action == OrderType.SELL and last_price >= rule['limit_price']:
                        self.logger.info(
                            f"Sell condition met for {symbol}: price ${last_price} >= limit ${rule['limit_price']}")
                        self.sell_stock(rule, last_price)

                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error during trading rule processing: {str(e)}")
                time.sleep(5)

        # update current_holding, last_price
        self.logger.info("Market closed. Updating final positions and prices.")
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
                self.logger.warning(f"No position data for rule {rule_id}, symbol {symbol}, hash {hash_value}")
                continue

            current_holding = self.positions_result_by_account[hash_value].get(symbol)['quantity']
            last_price = self.positions_result_by_account[hash_value].get(symbol)['last_price']
            average_price = self.positions_result_by_account[hash_value].get(symbol)['average_price']

            self.logger.info(
                f"Updating rule {rule_id}: {symbol} - Current holding: {current_holding}, Last price: ${last_price}, Avg price: ${average_price}")
            self.db_handler.update_current_price_quantity(rule_id, last_price, current_holding, average_price)

    def sell_stock(self, rule, last_price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        today_trading_quantity = self.db_handler.get_trade_today(rule['id'])

        # 매도할 최대 수량 계산
        max_shares = min(
            int(rule['daily_money'] / last_price) - today_trading_quantity,
            current_holding - rule['target_amount']
        )

        if max_shares <= 0:
            self.logger.info(f"No shares to sell for rule {rule['id']} ({rule['symbol']})")
            self.logger.debug(
                f"Current holding: {current_holding}, Target: {rule['target_amount']}, Daily limit: {int(rule['daily_money'] / last_price)}, Today's trades: {today_trading_quantity}")
            return

        self.logger.info(f"Attempting to sell {max_shares} shares of {rule['symbol']} at ${last_price}")
        if self.place_sell_order(rule, max_shares, last_price):
            if current_holding - max_shares <= rule['target_amount']:
                self.logger.info(
                    f"Rule {rule['id']} completed after selling {max_shares} shares. New holding: {current_holding - max_shares}")
                self.db_handler.update_rule_status(rule['id'], 'COMPLETED')

    def buy_stock(self, schwab, rule, last_price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        today_trading_quantity = self.db_handler.get_trade_today(rule['id'])

        # 매수할 최대 수량 계산
        max_shares = min(
            int(rule['daily_money'] / last_price) - today_trading_quantity,
            rule['target_amount'] - current_holding
        )

        if max_shares <= 0:
            self.logger.info(f"No shares to buy for rule {rule['id']} ({rule['symbol']})")
            self.logger.debug(
                f"Current holding: {current_holding}, Target: {rule['target_amount']}, Daily limit: {int(rule['daily_money'] / last_price)}, Today's trades: {today_trading_quantity}")
            return

        required_cash = max_shares * last_price
        current_cash = schwab.get_cash(rule['hash_value'])
        self.logger.info(
            f"Buy attempt for {rule['symbol']}: Shares: {max_shares}, Required cash: ${required_cash:.2f}, Available cash: ${current_cash:.2f}")

        # 돈이 부족하면 채권매도 시도
        if required_cash > current_cash:
            self.logger.info(f"Insufficient cash. Attempting to sell ETFs for ${required_cash - current_cash:.2f}")
            order = schwab.sell_etf_for_cash(
                rule['hash_value'],
                required_cash - current_cash,
                self.positions_by_account[rule['hash_value']]
            )
            if order.is_success:
                self.logger.info("ETF sold successfully for cash")
                current_cash = schwab.get_cash(rule['hash_value'])
            else:
                self.logger.warning("Failed to sell ETF for cash")

        # 돈이 부족한 만큼 수량 조정해서 매수
        max_shares = min(max_shares, int(current_cash / last_price))
        if max_shares > 0:
            self.logger.info(f"Attempting to buy {max_shares} shares of {rule['symbol']} at ${last_price}")
            if self.place_buy_order(rule, max_shares, last_price):
                if current_holding + max_shares >= rule['target_amount']:
                    self.logger.info(
                        f"Rule {rule['id']} completed after buying {max_shares} shares. New holding: {current_holding + max_shares}")
                    self.db_handler.update_rule_status(rule['id'], 'COMPLETED')
        else:
            self.logger.warning(
                f"Insufficient funds to buy {rule['symbol']}. Required: ${required_cash:.2f}, Available: ${current_cash:.2f}")


if __name__ == "__main__":
    mp.freeze_support()

    trading_system = TradingSystem()
    trading_system.process_trading_rules()