import multiprocess as mp
from datetime import datetime
import time
from enum import IntEnum
from library.logger_config import setup_logger

from library.alert import SendMessage
from library.safety_guard import OrderValidator, SafetyException, StateIntegrityGuard
import argparse
from strategies.schwab_strategy import SchwabMarketStrategy
from strategies.korea_strategy import KoreaMarketStrategy
class OrderType(IntEnum):
    SELL = 0
    BUY = 1

class TradingSystem:
    def __init__(self, market_strategy):
        self.market_strategy = market_strategy
        self.db_handler = market_strategy.get_db_handler()
        self.managers = {}  # {user_id: UserAuthManager}
        self.positions_by_account = {}  # {account_id: {symbol: quantity}}
        self.positions_result_by_account = {}
        self._market_hours = None
        self.logger = setup_logger("trading_system", "log")

    def get_manager(self, user_id: str):
        """Get or create user-specific manager for the market"""
        if user_id not in self.managers:
            self.managers[user_id] = self.market_strategy.get_manager(user_id)
        return self.managers[user_id]

    def get_any_manager(self):
        if not self.managers:
            raise ValueError("No managers available")

        first_user_id = next(iter(self.managers))
        return self.managers[first_user_id]

    def check_periodic_buy_date(self, rule: dict) -> bool:
        """정기 매수 날짜인지 확인하는 함수"""
        today = datetime.now()
        
        if rule['limit_type'] == 'weekly':
            # 0(월요일) ~ 6(일요일)
            return today.weekday() == rule['limit_value']
        
        elif rule['limit_type'] == 'monthly':
            # 1 ~ 31일
            return today.day == rule['limit_value']
            
        return False

    def update_periodic_rule_status(self):
        """정기 매수 규칙의 상태를 업데이트하는 함수"""
        rules = self.db_handler.get_periodic_rules()  # weekly/monthly type의 규칙들만 조회
        
        for rule in rules:
            # PROCESSED 상태인 규칙만 체크
            if rule['status'] == 'PROCESSED' and self.check_periodic_buy_date(rule):
                # 정기 매수일이 되면 ACTIVE로 변경
                self.db_handler.update_rule_status(rule['id'], 'ACTIVE')

    def load_daily_positions(self, user_id: str, max_retries: int = 3, retry_delay: float = 2.0):
        """하루 시작할 때 포지션 로드, 실패 시 재시도 로직 포함"""
        self.logger.info(f"Loading daily positions for user {user_id}")
        manager = self.get_manager(user_id)

        try:
            account_hashs = manager.get_hashs()
            for account_number, hash_value in account_hashs.items():
                self.db_handler.update_account_hash(account_number, hash_value, user_id)

                # 재시도 로직 적용
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        positions = manager.get_positions(hash_value)
                        self.positions_by_account[hash_value] = {
                            symbol: quantity
                            for symbol, quantity in positions.items()
                        }
                        self.logger.info(f"Loaded positions for account {account_number}: {positions}")
                        break  # 성공하면 반복문 종료
                    except Exception as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            self.logger.warning(
                                f"Error loading positions for account {account_number} "
                                f"(retry {retry_count}/{max_retries}): error: {str(e)}"
                            )
                            # 재시도 전 딜레이 적용 (지수 백오프 적용)
                            import time
                            time.sleep(retry_delay * (2 ** (retry_count - 1)))
                        else:
                            raise
        except Exception as e:
            self.logger.error(f"Error loading positions for user {user_id}: {str(e)}")

    def get_positions(self, user_id: str):
        self.logger.info(f"Getting current positions for user {user_id}")
        manager = self.get_manager(user_id)
        try:
            hash_list = self.db_handler.get_hash_value(user_id)
            for hash_value in hash_list:
                positions = manager.get_positions_result(hash_value)
                self.positions_result_by_account[hash_value] = {
                    symbol: data
                    for symbol, data in positions.items()
                }
                self.logger.debug(f"Retrieved positions for hash {hash_value}: {positions}")
        except Exception as e:
            self.logger.error(f"Error getting positions for user {user_id}: {str(e)}")
            raise

    def place_buy_order(self, rule: dict, quantity: int, price: float, current_cash: float = None):
        self.logger.info(f"Placing buy order for rule {rule['id']}: {rule['symbol']} - {quantity} shares at ${price}")
        
        # --- SAFETY GUARD (DRY RUN MODE) ---
        try:
            market_type = 'KR' if isinstance(self.market_strategy, KoreaMarketStrategy) else 'US'
            
            # Fetch cash if not provided (Safety Fallback)
            if current_cash is None:
                manager = self.get_manager(rule['user_id'])
                current_cash = manager.get_cash(rule['hash_value'])
                
            OrderValidator.validate_buy(market_type, rule['symbol'], price, quantity, current_cash)
            
        except SafetyException as e:
            # DRY RUN: Log ONLY. Do not raise yet.
            self.logger.critical(f"[SAFETY_GUARD_TEST] WOULD BLOCK BUY ORDER: {str(e)}")
            self.logger.critical(f"Context: {rule['symbol']}, Qty: {quantity}, Price: {price}, Balance: {current_cash}")
            # raise # Uncomment to enable active blocking
        except Exception as e:
            self.logger.error(f"Error during Safety Guard validation: {str(e)}")
        # -----------------------------------

        manager = self.get_manager(rule['user_id'])
        try:
            order = manager.place_limit_buy_order(rule['hash_value'], rule['symbol'], quantity, price)
            if order and order.is_success:
                # 매매 성공 알림 메시지 생성 및 전송
                alert_msg = self._create_buy_alert_message(rule, quantity, price)
                SendMessage(alert_msg)

                try:
                    self.positions_by_account[rule['hash_value']][rule['symbol']] = (
                            self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0) + quantity
                    )
                except KeyError:
                    self.logger.error(f"Failed to update local position cache for {rule['hash_value']}. Key not found.")
                order_id = self.market_strategy.extract_order_id(manager, rule['hash_value'], order)

                self.db_handler.record_trade(rule['account_id'], rule['id'], order_id, rule['symbol'], quantity, price, 'BUY')
                self.logger.info(f"Buy order placed successfully: {order_id}")
                return True
            else:
                self.logger.error(f"Failed to place buy order for {rule['symbol']}: {order}")
                return False
        except Exception as e:
            self.logger.error(f"Error during buy order for {rule['symbol']}: {str(e)}")
            raise

    def place_sell_order(self, rule: dict, quantity: int, price: float, current_holding: int = None):
        self.logger.info(f"Placing sell order for rule {rule['id']}: {rule['symbol']} - {quantity} shares at ${price}")
        
        # --- SAFETY GUARD (DRY RUN MODE) ---
        try:
            market_type = 'KR' if isinstance(self.market_strategy, KoreaMarketStrategy) else 'US'
            
            # Use cached holding if not provided (Safety Fallback)
            if current_holding is None:
                account_positions = self.positions_by_account.get(rule['hash_value'], {})
                current_holding = account_positions.get(rule['symbol'], 0)
                
            OrderValidator.validate_sell(market_type, rule['symbol'], price, quantity, current_holding)

        except SafetyException as e:
            # DRY RUN: Log ONLY. Do not raise yet.
            self.logger.critical(f"[SAFETY_GUARD_TEST] WOULD BLOCK SELL ORDER: {str(e)}")
            self.logger.critical(f"Context: {rule['symbol']}, Qty: {quantity}, Price: {price}, Holding: {current_holding}")
            # raise # Uncomment to enable active blocking
        except Exception as e:
            self.logger.error(f"Error during Safety Guard validation: {str(e)}")
        # -----------------------------------

        manager = self.get_manager(rule['user_id'])
        try:
            order = manager.place_limit_sell_order(rule['hash_value'], rule['symbol'], quantity, price)
            if order and order.is_success:
                # 매매 성공 알림 메시지 생성 및 전송
                alert_msg = self._create_sell_alert_message(rule, quantity, price)
                SendMessage(alert_msg)

                try:
                    self.positions_by_account[rule['hash_value']][rule['symbol']] = (
                            self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0) - quantity
                    )
                except KeyError:
                    self.logger.error(f"Failed to update local position cache for {rule['hash_value']}. Key not found.")
                order_id = self.market_strategy.extract_order_id(manager, rule['hash_value'], order)

                self.db_handler.record_trade(rule['account_id'], rule['id'], order_id, rule['symbol'], quantity, price, 'SELL')
                self.logger.info(f"Sell order placed successfully: {order_id}")
                return True
            else:
                self.logger.error(f"Failed to place sell order for {rule['symbol']}: {order}")
                return False
        except Exception as e:
            self.logger.error(f"Error during sell order for {rule['symbol']}: {str(e)}")
            raise

    def _create_buy_alert_message(self, rule, quantity, price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        new_holding = current_holding + quantity
        total_cost = quantity * price
        symbol = rule['symbol'] if 'stock_name' not in rule else rule['stock_name']
        
        # 조건 메시지 생성
        if rule.get('limit_type') == 'percent' and rule.get('average_price') is not None:
            if rule['average_price'] > 0:
                buy_price = rule['average_price'] * (1 - rule['limit_value'] / 100)
                condition_msg = f"- {price} <= {rule['limit_value']}% below avg {rule['average_price']} ({buy_price})"
            else:
                condition_msg = f"- {price} (average_price is 0, buying at current price)"
        elif rule.get('limit_type') == 'high_percent' and rule.get('high_price') is not None:
            if rule['high_price'] > 0:
                buy_price = rule['high_price'] * (1 - rule['limit_value'] / 100)
                condition_msg = f"- {price} <= {rule['limit_value']}% below high {rule['high_price']} ({buy_price})"
            else:
                condition_msg = f"- {price} (high_price is 0, cannot buy)"
        elif rule['limit_type'] == 'price':
            condition_msg = f"- {price} <= Limit Price({rule['limit_value']})"
        elif rule['limit_type'] == 'monthly':
            condition_msg = f"- {price} (today is {rule['limit_value']})"
        else:
            condition_msg = f"- {price} (weekday is {rule['limit_value']})"
        
        message = f"""
[BUY ORDER]
Account: {rule['description']} ({rule['user_id']})
Symbol: {symbol}
Purchase Price: {price}
Quantity: {quantity}주
Total Cost: {total_cost}
                    
Condition:
{condition_msg}
- Target Quantity: {rule['target_amount']}
- Updated Quantity: {current_holding} -> {new_holding}
- Daily Money Limit: {rule['daily_money']}
                    
Order At {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
        return message

    def _create_sell_alert_message(self, rule, quantity, price):
        current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        new_holding = current_holding - quantity
        total_sale = quantity * price
        symbol = rule['symbol'] if 'stock_name' not in rule else rule['stock_name']
        
        # 조건 메시지 생성
        if rule.get('limit_type') == 'percent' and rule.get('average_price') is not None:
            if rule['average_price'] > 0:
                sell_price = rule['average_price'] * (1 + rule['limit_value'] / 100)
                condition_msg = f"- {price} >= {rule['limit_value']}% above avg {rule['average_price']} ({sell_price})"
            else:
                condition_msg = f"- {price} (average_price is 0, no selling)"
        else:
            condition_msg = f"- {price} >= Limit Price({rule['limit_value']})"
        
        message = f"""
[SELL ORDER]
Account: {rule['account_id']} ({rule['user_id']})
Symbol: {symbol}
Sell Price: {price}
Quantity: {quantity}주
Total Sale: {total_sale}
                    
Condition:
{condition_msg}
- Target Quantity: {rule['target_amount']}주
- Updated Quantity: {current_holding}주 -> {new_holding}주
- Daily Money Limit: {rule['daily_money']}
                    
Order At {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
        return message

    def is_market_open(self) -> bool:
        try:
            manager = self.get_any_manager()
            return manager.get_market_hours()

        except Exception as e:
            self.logger.error(f"Error updating market hours: {str(e)}")
            return True

    def sync_split_adjustments(self, user_id: str):
        """
        장 시작 전 액면분할/병합 체크 및 DB 업데이트
        증권사 평단가와 DB 평단가를 비교하여 비율만큼 high_price와 target_amount를 조정
        """
        self.logger.info(f"Checking for stock splits/merges for user {user_id}")
        manager = self.get_manager(user_id)

        # 1. 현재 증권사의 상세 잔고(평단가 포함) 가져오기
        try:
            hash_list = self.db_handler.get_hash_value(user_id)
            current_positions = {}  # {(hash, symbol): position_data}

            for hash_value in hash_list:
                # get_positions_result는 평단가(average_price)를 포함한 상세 데이터를 반환한다고 가정
                positions = manager.get_positions_result(hash_value)
                for symbol, data in positions.items():
                    current_positions[(hash_value, symbol)] = data

        except Exception as e:
            self.logger.error(f"Failed to fetch positions for split check: {e}")
            return

        # 2. DB에 저장된 활성 규칙 가져오기
        rules = self.db_handler.get_active_trading_rules()

        for rule in rules:
            if rule['user_id'] != user_id:
                continue

            key = (rule['hash_value'], rule['symbol'])

            # 증권사 데이터에서 해당 종목 찾기
            broker_data = current_positions.get(key)

            if not broker_data:
                continue

            # 3. 데이터 추출 및 분할/병합 판단
            broker_avg_price = float(broker_data['average_price'])
            broker_quantity = float(broker_data['quantity'])

            db_avg_price = float(rule['average_price'])
            db_quantity = float(rule.get('current_holding', 0))

            is_split_or_merge = False

            # 판단 기준: 기존 평단가가 0이 아니며(보유 종목), 수량 차이가 0.001 이상인 경우
            if db_avg_price > 0 and abs(broker_quantity - db_quantity) > 0.001:
                is_split_or_merge = True


            if is_split_or_merge:
                # 보정 계산을 위한 비율 (Ratio)은 여전히 평단가 변화율로 계산합니다.
                if db_avg_price == 0 or broker_avg_price == 0:
                    self.logger.warning(
                        f"Split detected for {rule['symbol']} but avg price is 0. Skipping rule adjustment."
                    )
                    continue

                ratio = broker_avg_price / db_avg_price
                self.logger.warning(f"Split/Merge detected for {rule['symbol']} (Rule ID: {rule['id']})")
                self.logger.warning(f"Avg Price changed: {db_avg_price} -> {broker_avg_price} (Ratio: {ratio:.4f})")

                # 값 보정
                new_high_price = float(rule.get('high_price', 0)) * ratio

                # 수량은 가격과 반비례하므로 비율로 나눠줌 (가격 1/10토막 -> 수량 10배)
                current_target = float(rule['target_amount'])
                new_target_amount = int(current_target / ratio)

                self.logger.info(f"Adjusting High Price: {rule.get('high_price')} -> {new_high_price}")
                self.logger.info(f"Adjusting Target Amount: {current_target} -> {new_target_amount}")

                # DB 업데이트
                # update_rule_split_info 메서드는 DB Handler에 새로 추가해야 함
                # 혹은 기존 update 메서드들을 조합해서 사용
                self.db_handler.update_split_adjustment(
                    rule_id=rule['id'],
                    new_avg_price=broker_avg_price,
                    new_high_price=new_high_price,
                    new_target_amount=new_target_amount,
                    new_current_quantity=float(broker_data['quantity'])
                )
    def process_trading_rules(self):
        """모든 유저의 모든 계좌의 거래 규칙 처리"""
        self.logger.info("Starting trading rule processing")

        # 정기 매수 규칙 상태 업데이트
        self.update_periodic_rule_status()
        
        # 각 유저의 각 계좌별 포지션 로드
        users = self.db_handler.get_users()
        for user in users:
            # 1. 상세 데이터 로드 (평단가 확인용)
            self.get_positions(user)

            # [GUARD] Phase 1: State Integrity Check
            import sys
            try:
                # Check integrity BEFORE allowing any sync logic
                # self.positions_result_by_account holds {hash_val: {symbol: data}}
                StateIntegrityGuard.check_integrity(
                    self.db_handler, 
                    manager, 
                    user, 
                    self.positions_result_by_account
                )
            except SafetyException as e:
                # Catch SafetyException (which wraps the critical issues)
                # If guard raises SystemExit directly, we might miss alerting
                # The Guard in safety_guard.py currently raises SafetyException for this block.
                
                error_msg = f"🚨 BOT STOPPED (State Integrity Error): {e}"
                self.logger.critical(error_msg)
                
                # Send Critical Alert Email
                try:
                    SendMessage(error_msg)
                except Exception as alert_err:
                    self.logger.error(f"Failed to send alert: {alert_err}")
                
                # Fail Closed
                sys.exit(1)

            # 2. 분할/병합 체크 및 DB 보정
            self.sync_split_adjustments(user)
            # 3. 매매 로직용 데이터 로드
            self.load_daily_positions(user)

        while self.is_market_open():
            try:
                rules = self.db_handler.get_active_trading_rules()
                self.logger.info(f"Loaded {len(rules)} active trading rules")

                for rule in rules:
                    symbol = rule['symbol']
                    manager = self.get_manager(rule['user_id'])
                    try:
                        last_price = manager.get_last_price(symbol)
                    except Exception as e:
                        continue
                    if last_price is None:
                        continue
                    symbol = rule['stock_name'] if 'stock_name' in rule else rule['symbol']
                    #self.logger.debug(f"Current price for {symbol}: ${last_price}")

                    action = rule['trade_action']
                    # limit_type에 따라 분기
                    if rule.get('limit_type') in ['weekly', 'monthly']:
                        if action == OrderType.BUY:
                            self.logger.info(f"Periodic buy for {symbol} at current price ${last_price}")
                            self.buy_stock(manager, rule, last_price, symbol)
                    elif rule.get('limit_type') == 'percent':
                        if rule.get('average_price') is None or rule['average_price'] == 0:
                            # average_price가 0인 경우: 현재가로 매수만, 매도는 안함
                            if action == OrderType.BUY:
                                self.logger.info(
                                    f"Buy condition met for {symbol}: average_price is 0, buying at current price ${last_price}")
                                self.buy_stock(manager, rule, last_price, symbol)
                        else:
                            percent = rule['limit_value']
                            if action == OrderType.BUY:
                                buy_price = rule['average_price'] * (1 - percent / 100)
                                if last_price <= buy_price:
                                    self.logger.info(
                                        f"Buy condition met for {symbol}: price ${last_price} <= {percent}% below avg ${rule['average_price']} (${buy_price:.2f})")
                                    self.buy_stock(manager, rule, last_price, symbol)
                            elif action == OrderType.SELL:
                                sell_price = rule['average_price'] * (1 + percent / 100)
                                if last_price >= sell_price:
                                    self.logger.info(
                                        f"Sell condition met for {symbol}: price ${last_price} >= {percent}% above avg ${rule['average_price']} (${sell_price:.2f})")
                                    self.sell_stock(rule, last_price, symbol)
                    elif rule.get('limit_type') == 'high_percent':
                        if action == OrderType.BUY and rule.get('high_price', 0) > 0:
                            buy_price = rule['high_price'] * (1 - rule['limit_value'] / 100)
                            if last_price <= buy_price:
                                self.logger.info(
                                    f"Buy condition met for {symbol}: price ${last_price} <= {rule['limit_value']}% below high ${rule['high_price']} (${buy_price:.2f})")
                                self.buy_stock(manager, rule, last_price, symbol)

                    else:
                        # 가격 기준 거래
                        if action == OrderType.BUY and last_price <= rule['limit_value']:
                            self.logger.info(
                                f"Buy condition met for {symbol}: price ${last_price} <= limit ${rule['limit_value']}")
                            self.buy_stock(manager, rule, last_price, symbol)
                        elif action == OrderType.SELL and last_price >= rule['limit_value']:
                            self.logger.info(
                                f"Sell condition met for {symbol}: price ${last_price} >= limit ${rule['limit_value']}")
                            self.sell_stock(rule, last_price, symbol)

                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error during trading rule processing: {str(e)}")
                raise

        # update current_holding, last_price
        self.logger.info("Market closed. Updating final positions and prices.")
        self.update_result(users)

    def update_result(self, users):
        today = datetime.now().strftime('%Y%m%d')
        for user in users:
            self.get_positions(user)
            # Get accounts for this user and update cash balances
            accounts = self.db_handler.get_user_accounts(user)
            # Get manager for this user
            manager = self.get_manager(user)

            for account in accounts:
                account_id = account['id']
                hash_value = account['hash_value']

                # Skip accounts with missing hash value
                if not hash_value:
                    self.logger.warning(f"No hash value for account {account_id}, skipping cash update")
                    continue

                try:
                    # Get current cash balance (현금 예수금)
                    cash_balance, total_value = manager.get_account_result(hash_value)

                    self.db_handler.add_daily_result(today, account_id, cash_balance, total_value, self.positions_result_by_account[hash_value])
                    # 계산: 예수금총액 = 예수금 + (BIL, SGOV)의 평가금액
                    total_cash_balance = cash_balance

                    # BIL, SGOV 평가금액 추가 (해당 종목이 있을 경우)
                    etfs_to_include = ['BIL', 'SGOV']

                    if hash_value in self.positions_result_by_account:
                        for etf in etfs_to_include:
                            if etf in self.positions_result_by_account[hash_value]:
                                etf_data = self.positions_result_by_account[hash_value][etf]
                                etf_quantity = float(etf_data['quantity'])
                                etf_price = float(etf_data['last_price'])
                                etf_value = etf_quantity * etf_price

                                self.logger.info(
                                    f"Account {account_id}: {etf} value = ${etf_value:.2f} ({etf_quantity} shares @ ${etf_price:.2f})")
                                total_cash_balance += etf_value

                    # Update in database
                    self.logger.info(
                        f"Updating cash balance for account {account_id}: ${total_cash_balance:.2f} (Cash: ${cash_balance:.2f} + ETFs)")
                    self.db_handler.update_account_cash_balance(account_id, total_cash_balance)
                    self.db_handler.update_account_total_value(account_id, total_value)

                except Exception as e:
                    self.logger.error(f"Error updating cash balance for account {account_id}: {str(e)}")
        rules = self.db_handler.get_all_trading_rules()
        for rule in rules:
            rule_id = rule['id']
            hash_value = rule['hash_value']
            symbol = rule['symbol'] if 'stock_name' not in rule else rule['stock_name']

            if hash_value not in self.positions_result_by_account:
                continue
            if symbol not in self.positions_result_by_account[
                hash_value]:
                self.logger.warning(f"No position data for rule {rule_id}, symbol {symbol}, hash {hash_value}")
                try:
                    last_price = self.get_any_manager().get_last_price(rule['symbol'])
                except Exception as e:
                    last_price = 0
                self.db_handler.update_current_price_quantity(rule_id, last_price, 0, 0)
                continue

            current_holding = self.positions_result_by_account[hash_value].get(symbol)['quantity']
            last_price = self.positions_result_by_account[hash_value].get(symbol)['last_price']
            average_price = self.positions_result_by_account[hash_value].get(symbol)['average_price']

            # Update high_price if average_price is non-zero
            if average_price > 0:
                high_price = max(last_price, rule.get('high_price', 0))
                self.logger.info(
                    f"Updating rule {rule_id}: {symbol} - Current holding: {current_holding}, Last price: ${last_price}, Avg price: ${average_price}, High price: ${high_price}")
                self.db_handler.update_current_price_quantity(rule_id, last_price, current_holding, average_price, high_price)
            else:
                self.logger.info(
                    f"Updating rule {rule_id}: {symbol} - Current holding: {current_holding}, Last price: ${last_price}, Avg price: ${average_price}")
                self.db_handler.update_current_price_quantity(rule_id, last_price, current_holding, average_price)

    def sell_stock(self, rule, last_price, symbol):
        try:
            current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        except KeyError:
            self.logger.error(f"Missing position data for account {rule['hash_value']}. Skipping sell rule {rule['id']}.")
            return
        today_trading_money = self.db_handler.get_trade_today(rule['id'])

        # 매도할 최대 수량 계산
        max_shares = min(
            (int(rule['daily_money']) - today_trading_money)// last_price,
            int(current_holding) - int(rule['target_amount'])
        )

        if max_shares <= 0:
            self.logger.info(f"No shares to sell for rule {rule['id']} ({symbol})")
            self.logger.debug(
                f"Current holding: {current_holding}, Target: {rule['target_amount']}, Daily limit: {int(rule['daily_money'] / last_price)}, Today's trades: {today_trading_money}")
            return

        self.logger.info(f"Attempting to sell {max_shares} shares of {symbol} at ${last_price}")
        if self.place_sell_order(rule, max_shares, last_price, current_holding):
            if current_holding - max_shares <= rule['target_amount']:
                self.logger.info(
                    f"Rule {rule['id']} completed after selling {max_shares} shares. New holding: {current_holding - max_shares}")
                self.db_handler.update_rule_status(rule['id'], 'COMPLETED')

    def buy_stock(self, manager, rule, last_price, symbol):
        try:
            current_holding = self.positions_by_account[rule['hash_value']].get(rule['symbol'], 0)
        except KeyError:
            self.logger.error(f"Missing position data for account {rule['hash_value']}. Skipping buy rule {rule['id']}.")
            return
        today_trading_money = self.db_handler.get_trade_today(rule['id'])

        # 매수할 최대 수량 계산
        max_shares = min(
            (int(rule['daily_money']) - today_trading_money)// last_price,
            int(rule['target_amount']) - int(current_holding)
        )

        if max_shares <= 0:
            self.logger.info(f"No shares to buy for rule {rule['id']} ({symbol})")
            self.logger.debug(
                f"Current holding: {current_holding}, Target: {rule['target_amount']}, Daily limit: {int(rule['daily_money'] / last_price)}, Today's trades: {today_trading_money}")
            return

        required_cash = max_shares * last_price
        current_cash = manager.get_cash(rule['hash_value'])
        self.logger.info(
            f"Buy attempt for {symbol}: Shares: {max_shares}, Required cash: ${required_cash:.2f}, Available cash: ${current_cash:.2f}")

        # 돈이 부족하면 채권매도 시도 (cash_only가 False일 때만)
        if not rule['cash_only'] and required_cash > current_cash:
            self.logger.info(f"Insufficient cash. Attempting to sell ETFs for ${required_cash - current_cash:.2f}")
            order = manager.sell_etf_for_cash(
                rule['hash_value'],
                required_cash - current_cash,
                self.positions_by_account[rule['hash_value']]
            )
            if order and order.is_success:
                self.logger.info("ETF sold successfully for cash")
                current_cash = manager.get_cash(rule['hash_value'])
            else:
                self.logger.warning("Failed to sell ETF for cash")

        # 돈이 부족한 만큼 수량 조정해서 매수
        max_shares = min(max_shares, int(current_cash / last_price))
        if max_shares > 0:
            self.logger.info(f"Attempting to buy {max_shares} shares of {symbol} at ${last_price}")
            if self.place_buy_order(rule, max_shares, last_price, current_cash):
                if rule['limit_type'] in ['weekly', 'monthly']:
                    # 정기 매수의 경우 매수 완료 후 PROCESSED로 변경
                    self.db_handler.update_rule_status(rule['id'], 'PROCESSED')
                elif current_holding + max_shares >= rule['target_amount']:
                    # 일반 매수의 경우 목표 수량 달성 시 COMPLETED로 변경
                    self.logger.info(
                        f"Rule {rule['id']} completed after buying {max_shares} shares. New holding: {current_holding + max_shares}")
                    self.db_handler.update_rule_status(rule['id'], 'COMPLETED')
        else:
            self.logger.warning(
                f"Insufficient funds to buy {symbol}. Required: ${required_cash:.2f}, Available: ${current_cash:.2f}")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Automated Trading System')
    parser.add_argument('--market', choices=['schwab', 'korea'], default='schwab',
                        help='Market to trade on (schwab or korea)')
    parser.add_argument('--no-record', action='store_true', help='Disable market data recording')
    args = parser.parse_args()

    # --- Data Recorder Integration ---
    recorder = None
    if not args.no_record:
        try:
            from library.recorder import AsyncDataRecorder, apply_patches, backup_databases
            from library.schwab_manager import SchwabManager
            from library.korea_manager import KoreaManager
            
            today_str = datetime.now().strftime('%Y%m%d')
            record_filename = f"records/market_data_{args.market}_{today_str}.jsonl"
            
            # 1. Backup DB at Start
            backup_databases('start')
            
            recorder = AsyncDataRecorder(record_filename)
            
            # Apply patches to Manager classes
            patched_count = apply_patches(recorder, [SchwabManager, KoreaManager])
            
            # Use print or basic logger since setup_logger might not be fully configured for 'recorder' yet
            print(f"[Recorder] Active: {record_filename}. Patched {patched_count} methods.")
            
        except Exception as e:
            print(f"[Recorder] Failed to initialize: {e}")
            # Do not crash the app, just continue without recording
            pass

    # Create the appropriate market strategy
    if args.market.lower() == 'korea':
        market_strategy = KoreaMarketStrategy()
    else:
        market_strategy = SchwabMarketStrategy()

    # Initialize trading system with the selected strategy
    trading_system = TradingSystem(market_strategy)

    # Start trading
    mp.freeze_support()
    try:
        trading_system.process_trading_rules()
    except Exception as e:
        error_message = f"""
[TRADING SYSTEM CRASHED]
Market: {args.market.upper()}
Error: {str(e)}
Status: Trading system crashed unexpectedly
"""
        try:
            SendMessage(error_message)
            print(f"Trading system crashed: {e}")
        except Exception as alert_error:
            print(f"Failed to send crash notification: {alert_error}")
            print(f"Original error: {e}")
        raise  # 원래 에러를 다시 발생시켜서 디버깅 정보 유지
    finally:
        if recorder:
            try:
                # 2. Backup DB at End
                backup_databases('end')
            except Exception as e:
                print(f"[Backup] Failed at end: {e}")
            recorder.close()