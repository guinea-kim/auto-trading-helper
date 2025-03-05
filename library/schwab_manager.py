from http import HTTPStatus
from pathlib import Path
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
        client = self.get_client()
        return client.get_market_hours(Client.MarketHours.Market.EQUITY)


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
            average_price = position["averagePrice"]

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
        data = json.loads(resp.content)
        return data["securitiesAccount"]["currentBalances"]["cashAvailableForTrading"]

    def get_last_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        client = self.get_client()
        quote_data = client.get_quote(symbol)
        quote = quote_data.json()
        return float(quote[symbol]["quote"]["lastPrice"])

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
                equity_buy_limit(symbol, quantity, price)
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
                equity_sell_limit(symbol, quantity, price)
                .set_duration(Duration.DAY)
                .set_session(Session.SEAMLESS)
                .build()
            )

        except Exception as e:
            self.logger.error(f"Failed to place buy order: {str(e)}")
            return False
    def sell_etf_for_cash(self, hash_value: str, required_cash: float, positions: Dict[str, float]) -> Optional[float]:
        """Sell SGOV or BIL to get required cash"""
        etfs_to_sell = ['SGOV', 'BIL']

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
