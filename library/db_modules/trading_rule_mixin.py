from sqlalchemy import text
from typing import List, Dict, Optional
import decimal

class TradingRuleMixin:
    """
    Mixin for Trading Rule-related database operations.
    Assumes access to self.engine from the main DatabaseHandler class.
    """

    def get_active_trading_rules(self) -> List[Dict]:
        """활성화된 모든 거래 규칙 조회"""
        sql = """
            SELECT r.*, a.user_id, a.hash_value, a.description 
            FROM trading_rules r
            JOIN accounts a ON r.account_id = a.id
            WHERE r.status = 'ACTIVE'
            ORDER BY 
                a.user_id,trade_action
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = []
            for row in result:
                row_dict = dict(row._mapping)
                # Decimal 타입 필드들을 float으로 변환
                for key, value in row_dict.items():
                    if isinstance(value, decimal.Decimal):
                        row_dict[key] = float(value)
                rows.append(row_dict)
            return rows
    
    def get_all_trading_rules(self) -> List[Dict]:
        """활성화된 모든 거래 규칙 조회"""
        sql = """
            SELECT r.*, a.user_id, a.hash_value, a.description 
            FROM trading_rules r
            JOIN accounts a ON r.account_id = a.id
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = []
            for row in result:
                row_dict = dict(row._mapping)
                # Decimal 타입 필드들을 float으로 변환
                for key, value in row_dict.items():
                    if isinstance(value, decimal.Decimal):
                        row_dict[key] = float(value)
                rows.append(row_dict)
            return rows

    def get_trading_rules(self) -> List[Dict]:
        """모든 거래 규칙 조회 (계정 설명 포함)"""
        sql = """
            SELECT tr.*, a.description as account_description, a.user_id, a.account_number
            FROM trading_rules tr 
            JOIN accounts a ON tr.account_id = a.id 
            ORDER BY tr.status, a.user_id, a.account_number, tr.symbol
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row._mapping) for row in result]

    def get_periodic_rules(self):
        """정기 매수 규칙만 조회"""
        sql = """
            SELECT * FROM trading_rules 
            WHERE limit_type IN ('weekly', 'monthly')
            AND status IN ('ACTIVE', 'PROCESSED')
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row._mapping) for row in result]

    def update_rule_status(self, rule_id: int, status: str) -> None:
        """거래 규칙 상태 업데이트"""
        sql = """
               UPDATE trading_rules 
               SET status = :status 
               WHERE id = :rule_id
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "status": status,
                "rule_id": rule_id
            })
            conn.commit()

    def update_current_price_quantity(self, rule_id: int, last_price: float, current_holding: int, average_price: float, high_price: float = 0) -> None:
        """거래 규칙 상태와 가격정보 업데이트"""
        sql = """
               UPDATE trading_rules 
               SET last_price = :last_price, current_holding = :current_holding, 
                   average_price = :average_price, high_price = :high_price
               WHERE id = :rule_id
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "last_price": last_price,
                "current_holding": current_holding,
                "average_price": average_price,
                "high_price": high_price,
                "rule_id": rule_id
            })
            conn.commit()

    def update_rule_field(self, rule_id, field, value):
        with self.engine.connect() as conn:
            if field not in ['limit_value', 'limit_type', 'target_amount', 'daily_money', 'cash_only']:
                raise ValueError('Invalid field for update')
            sql = f"UPDATE trading_rules SET {field} = :value, last_updated = NOW() WHERE id = :rule_id"
            conn.execute(text(sql), {"value": value, "rule_id": rule_id})
            conn.commit()

    def update_split_and_merge_adjustment(self, rule_id, new_avg_price, new_high_price, new_target_amount,
                                new_current_quantity):
        with self.engine.connect() as conn:
            """액면분할/병합 반영 업데이트"""
            sql = """
                UPDATE trading_rules 
                SET average_price = :average_price,
                    high_price = :high_price,
                    target_amount = :target_amount,
                    current_quantity = :current_quantity,
                    updated_at = NOW()
                    WHERE id = :rule_id
            """
            conn.execute(text(sql), {
                "average_price": new_avg_price,
                "high_price": new_high_price,
                "target_amount": new_target_amount,
                "current_quantity": new_current_quantity,
                "rule_id": rule_id
            })
            conn.commit()

    def add_trading_rule(self, account_id: str, symbol: str, limit_value: float, limit_type: str,
                         target_amount: int, daily_money: float, trade_action: str, cash_only: int) -> None:
        """새 거래 규칙 추가"""
        sql = """
               INSERT INTO trading_rules 
               (account_id, symbol, limit_value, limit_type, target_amount, daily_money, trade_action, cash_only)
               VALUES (:account_id, :symbol, :limit_value, :limit_type, :target_amount, :daily_money, :trade_action, :cash_only)
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_id": account_id,
                "symbol": symbol,
                "limit_value": limit_value,
                "limit_type": limit_type,
                "target_amount": target_amount,
                "daily_money": daily_money,
                "trade_action": trade_action,
                "cash_only": cash_only
            })
            conn.commit()

    def add_kr_trading_rule(self, account_id: str, symbol: str, stock_name: str, limit_value: int, limit_type: str,
                            target_amount: int, daily_money: int, trade_action: str, cash_only: int) -> None:
        """한국주식 거래 규칙 추가"""
        sql = """
            INSERT INTO trading_rules 
            (account_id, symbol, stock_name, limit_value, limit_type, target_amount, daily_money, trade_action, cash_only)
            VALUES (:account_id, :symbol, :stock_name, :limit_value, :limit_type, :target_amount, :daily_money, :trade_action, :cash_only)
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_id": account_id,
                "symbol": symbol,
                "stock_name": stock_name,
                "limit_value": limit_value,
                "limit_type": limit_type,
                "target_amount": target_amount,
                "daily_money": daily_money,
                "trade_action": trade_action,
                "cash_only": cash_only
            })
            conn.commit()

    def get_highest_price(self, symbol: str) -> float:
        """특정 symbol에 대한 가장 높은 high_price 값을 반환"""
        sql = """
            SELECT MAX(high_price) as max_high_price
            FROM trading_rules
            WHERE symbol = :symbol
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"symbol": symbol}).fetchone()
            return float(result.max_high_price) if result and result.max_high_price is not None else 0.0
