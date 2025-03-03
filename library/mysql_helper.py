from sqlalchemy import create_engine, text
import pymysql.cursors
from library import secret
from typing import List, Dict, Optional
import decimal
pymysql.install_as_MySQLdb()
class DatabaseHandler:
    def __init__(self):
        self.db_name = secret.db_name
        self.setup_db_names()



    def setup_db_names(self):
        self.engine = self.create_engine_for_db(self.db_name)

        self.db_conn = pymysql.connect(host=secret.db_ip, port=int(secret.db_port), user=secret.db_id, password=secret.db_passwd,
                                       charset='utf8')

    @staticmethod
    def create_engine_for_db(db_name, pool_size=5):
        return create_engine(
            f"mysql+mysqldb://{secret.db_id}:{secret.db_passwd}@{secret.db_ip}:{secret.db_port}/{db_name}", pool_size=pool_size,
            max_overflow=10, pool_recycle=3600)


    def is_database_exist(self):
        sql = "SELECT 1 FROM Information_schema.SCHEMATA WHERE SCHEMA_NAME = '%s'"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql % (self.db_name))).fetchall()
        print("rows : ", rows)
        return len(rows) > 0

    def get_active_trading_rules(self) -> List[Dict]:
        """활성화된 모든 거래 규칙 조회"""
        sql = """
            SELECT r.*, a.user_id, a.hash_value 
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
    def get_accounts(self):
        sql = """
        SELECT * FROM accounts ORDER BY id
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row._mapping) for row in result]
    def get_users(self):
        sql = """
        SELECT DISTINCT(user_id) FROM accounts
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [row.user_id for row in result]
    def get_hash_value(self, user_id):
        sql = """
        SELECT hash_value FROM accounts where user_id=:user_id
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"user_id": user_id})
            return [row.hash_value for row in result]
    def get_trade_today(self, rule_id: int):
        sql = """select sum(quantity) as total_quantity from trade_history where trading_rule_id=:rule_id
                    AND DATE(trade_date) = CURRENT_DATE()"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"rule_id": rule_id})
            row = result.fetchone()
            return row.total_quantity if row and row.total_quantity is not None else 0
    def record_trade(self, account_id: str, rule_id: int, order_id:str, symbol: str,
                     quantity: int, price: float, trade_type: str) -> None:
        """거래 이력 기록"""
        sql = """
            INSERT INTO trade_history 
            (account_id, trading_rule_id, order_id, symbol, quantity, price, trade_type)
            VALUES (:account_id, :rule_id, :order_id, :symbol, :quantity, :price, :trade_type)
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_id": account_id,
                "rule_id": rule_id,
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "trade_type": trade_type
            })
            conn.commit()
    def update_account_hash(self, account_number: str, hash_value: str) -> None:
        """거래 규칙 상태 업데이트"""
        sql = """
               UPDATE accounts 
               SET hash_value = :hash_value 
               WHERE account_number = :account_number
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "hash_value": hash_value,
                "account_number": account_number
            })
            conn.commit()
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
    def update_current_price_quantity(self, rule_id: int, last_price: float, current_holding: int, average_price: float) -> None:
        """거래 규칙 상태 업데이트"""
        sql = """
               UPDATE trading_rules 
               SET last_price = :last_price, current_holding=:current_holding, average_price=:average_price
               WHERE id = :rule_id
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "last_price": last_price,
                "current_holding": current_holding,
                "average_price" : average_price,
                "rule_id": rule_id
            })
            conn.commit()

    def update_rule_field(self, rule_id, field, value):
        with self.engine.connect() as conn:
            sql = f"UPDATE trading_rules SET {field} = :value, last_updated = NOW() WHERE id = :rule_id"
            conn.execute(text(sql), {"value": value, "rule_id": rule_id})
            conn.commit()

    def get_user_accounts(self, user_id: str) -> List[Dict]:
        """사용자의 계좌 목록 조회"""
        sql = """
               SELECT * FROM accounts 
               WHERE user_id = :user_id
           """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"user_id": user_id})
            return [dict(row._mapping) for row in result]

        # 웹 인터페이스를 위한 추가 메서드

    def add_account(self, account_id: str, user_id: str, account_number: str, description: str) -> None:
        """새 계정 추가"""
        sql = """
               INSERT INTO accounts (id, user_id, account_number, description)
               VALUES (:id, :user_id, :account_number, :description)
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "id": account_id,
                "user_id": user_id,
                "account_number": account_number,
                "description": description
            })
            conn.commit()

    def add_trading_rule(self, account_id: str, symbol: str, limit_price: float,
                         target_amount: int, daily_money: float, trade_action: str) -> None:
        """새 거래 규칙 추가"""
        sql = """
               INSERT INTO trading_rules 
               (account_id, symbol, limit_price, target_amount, daily_money, trade_action)
               VALUES (:account_id, :symbol, :limit_price, :target_amount, :daily_money, :trade_action)
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_id": account_id,
                "symbol": symbol,
                "limit_price": limit_price,
                "target_amount": target_amount,
                "daily_money": daily_money,
                "trade_action": trade_action
            })
            conn.commit()

    def get_trading_rules(self) -> List[Dict]:
        """모든 거래 규칙 조회 (계정 설명 포함)"""
        sql = """
            SELECT tr.*, a.description as account_description 
            FROM trading_rules tr 
            JOIN accounts a ON tr.account_id = a.id 
            ORDER BY tr.account_id, id
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row._mapping) for row in result]

    def generate_account_id(self, user_id: str) -> str:
        """user_id와 증가하는 숫자를 조합하여 account_id 생성"""
        sql = """
            SELECT count(id) FROM accounts 
            WHERE user_id = :user_id
        """

        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"user_id": user_id}).fetchone()
            num = result[0] if result else 0

        return f"{user_id}_{num}"