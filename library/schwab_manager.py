from http import HTTPStatus
from pathlib import Path
from zoneinfo import ZoneInfo
import logging
from datetime import datetime
import json
from typing import Dict, Optional, Tuple
import time
from math import ceil

from schwab.auth import easy_client
from schwab.orders.common import Duration, Session
from schwab.orders.equities import equity_sell_market, equity_buy_limit, equity_sell_limit
from schwab.client import Client
from library.secret import USER_AUTH_CONFIGS




class SchwabManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.auth_config = USER_AUTH_CONFIGS[user_id]
        self.client = None
        self.hash_dict = None
        self.logger = logging.getLogger(__name__)

        lib_dir = Path(__file__).parent
        self.token_path = str(lib_dir / 'tokens' / f'schwab_token_{user_id}.json')
        self.today_open = None
        self.start_time = None
        self.end_time = None

    def get_client(self):
        """Get or create Schwab client with user-specific authentication"""
        if self.client is None:
            try:
                self.client = easy_client(
                    api_key=self.auth_config['app_key'],
                    app_secret=self.auth_config['secret'],
                    callback_url=self.auth_config['callback_url'],
                    token_path=self.token_path,
                    max_token_age=561600.0,
                    callback_timeout=300.0,
                    interactive=False
                )
                self.logger.info(f"Successfully authenticated user {self.user_id} at {datetime.now()}")

            except Exception as e:
                self.logger.error(f"Authentication failed for user {self.user_id}: {str(e)}")
                raise

        return self.client
    def get_hashs(self):
        client = self.get_client()
        resp = client.get_account_numbers()
        data = json.loads(resp.content)
        accounts = {}
        for account in data:
            accounts[account['accountNumber']] = account['hashValue']
        return accounts
    def get_market_hours(self):
        now = datetime.now(ZoneInfo("America/Los_Angeles"))

        if now.weekday() >= 5:  # 주말
            self.logger.info("Market is closed (weekend)")
            return False

        current_time = now.time()
        default_market_open = datetime.strptime("06:30", "%H:%M").time()
        default_market_close = datetime.strptime("13:00", "%H:%M").time()

        if not (default_market_open <= current_time < default_market_close):
            self.logger.info(f"Market is closed (outside trading hours): current time is {current_time}")
            return False

        if self.today_open is None:
            client = self.get_client()
            data = client.get_market_hours(Client.MarketHours.Market.EQUITY)

            if data.status_code == HTTPStatus.OK:
                market_hours = json.loads(data.content)
                equity_data = market_hours.get('equity', {}).get('EQ', {})

                if not equity_data.get('isOpen', False):
                    self.today_open = False
                    return self.today_open
                self.today_open = True
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
                    self.start_time = start_time_et.astimezone(ZoneInfo("America/Los_Angeles"))
                    self.end_time = end_time_et.astimezone(ZoneInfo("America/Los_Angeles"))
        if self.today_open:
            # 현재 시간이 시작 시간과 종료 시간 사이인지 확인
            return self.start_time <= now < self.end_time
        return False


    def get_positions(self, hash_value: str) -> Dict[str, float]:
        """Get account positions"""
        client = self.get_client()

        resp = client.get_account(hash_value, fields=[Client.Account.Fields.POSITIONS])
        data = json.loads(resp.content)

        positions = {}
        for position in data["securitiesAccount"].get("positions", []):
            symbol = position["instrument"]["symbol"]
            quantity = position["longQuantity"]
            positions[symbol] = quantity

        return positions
    def get_positions_result(self, hash_value: str) -> Dict[str, Dict[str, float]]:
        """Get account positions"""
        client = self.get_client()

        resp = client.get_account(hash_value, fields=[Client.Account.Fields.POSITIONS])
        data = json.loads(resp.content)

        positions = {}
        for position in data["securitiesAccount"].get("positions", []):
            symbol = position["instrument"]["symbol"]
            quantity = position["longQuantity"]
            average_price = float(position["averagePrice"])

            # Calculate last price from marketValue and longQuantity
            last_price = position["marketValue"] / position["longQuantity"] if position["longQuantity"] != 0 else 0

            positions[symbol] = {
                "quantity": quantity,
                "average_price": average_price,
                "last_price": last_price
            }

        return positions
    def get_cash(self, hash_value: str) -> float:
        """Get available cash balance"""
        client = self.get_client()

        resp = client.get_account(hash_value)
        try:
            data = json.loads(resp.content)
        except Exception as e:
            return 0
        return data["securitiesAccount"]["currentBalances"]["cashAvailableForTrading"]
    def get_account_result(self, hash_value: str) -> float:
        """Get available cash balance"""
        client = self.get_client()

        resp = client.get_account(hash_value)
        data = json.loads(resp.content)
        return data["securitiesAccount"]["currentBalances"]["cashAvailableForTrading"], data["aggregatedBalance"]["currentLiquidationValue"]
    def get_last_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        client = self.get_client()
        quote_data = client.get_quote(symbol)
        try:
            quote = quote_data.json()
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for {symbol}: {e}")
            return None
        except Exception as e:
            logging.error(f"Error calling json() for {symbol}: {e}")
            return None
        return round(float(quote[symbol]["quote"]["lastPrice"]), 2)

    def place_market_sell_order(self, hash_value: str, symbol: str, quantity: int) -> bool:
        """Place market sell order"""
        try:
            client = self.get_client()

            return client.place_order(
                hash_value,
                equity_sell_market(symbol, quantity)
            )
        except Exception as e:
            self.logger.error(f"Failed to place sell order: {str(e)}")
            return False

    def place_limit_buy_order(self, hash_value: str, symbol: str, quantity: int, price: float) -> bool:
        """Place limit buy order"""
        try:
            client = self.get_client()

            return client.place_order(
                hash_value,
                equity_buy_limit(symbol, quantity, str(price))
                .set_duration(Duration.DAY)
                .set_session(Session.SEAMLESS)
                .build()
            )

        except Exception as e:
            self.logger.error(f"Failed to place buy order: {str(e)}")
            return False
    def place_limit_sell_order(self, hash_value: str, symbol: str, quantity: int, price: float) -> bool:
        """Place limit buy order"""
        try:
            client = self.get_client()

            return client.place_order(
                hash_value,
                equity_sell_limit(symbol, quantity, str(price))
                .set_duration(Duration.DAY)
                .set_session(Session.SEAMLESS)
                .build()
            )

        except Exception as e:
            self.logger.error(f"Failed to place buy order: {str(e)}")
            return False
    def sell_etf_for_cash(self, hash_value: str, required_cash: float, positions: Dict[str, float]) -> Optional[float]:
        """Sell SGOV or BIL to get required cash"""
        etfs_to_sell = ['BIL', 'SGOV']

        for etf in etfs_to_sell:
            if etf in positions and positions[etf] > 0:
                current_price = self.get_last_price(etf)
                shares_to_sell = min(
                    positions[etf],
                    ceil(required_cash / current_price)
                )

                if shares_to_sell > 0:
                    return self.place_market_sell_order(hash_value, etf, shares_to_sell)

        return None
