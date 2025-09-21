from sqlalchemy import create_engine, text
import pymysql.cursors
from library import secret
from typing import List, Dict, Optional
import decimal
pymysql.install_as_MySQLdb()
class DatabaseHandler:
    def __init__(self, db_name):
        self.db_name = db_name
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
        sql = """select sum(used_money) as total_money from trade_history where trading_rule_id=:rule_id
                    AND DATE(trade_date) = CURRENT_DATE()"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"rule_id": rule_id})
            row = result.fetchone()
            return int(row.total_money) if row and row.total_money is not None else 0
    def record_trade(self, account_id: str, rule_id: int, order_id:str, symbol: str,
                     quantity: int, price: float, trade_type: str) -> None:
        """거래 이력 기록"""
        sql = """
            INSERT INTO trade_history 
            (account_id, trading_rule_id, order_id, symbol, quantity, price, trade_type, used_money)
            VALUES (:account_id, :rule_id, :order_id, :symbol, :quantity, :price, :trade_type, :used_money)
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_id": account_id,
                "rule_id": rule_id,
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "trade_type": trade_type,
                "used_money": price*quantity
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

    def update_account_cash_balance(self, account_id: str, cash_balance: float) -> None:
        """계정의 예수금 업데이트"""
        sql = """
            UPDATE accounts 
            SET cash_balance = :cash_balance 
            WHERE id = :account_id
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "cash_balance": cash_balance,
                "account_id": account_id
            })
            conn.commit()

    def update_account_contribution(self, account_id: str, contribution: float) -> None:
        """계정의 기여금 업데이트"""
        sql = """
            UPDATE accounts 
            SET contribution = :contribution 
            WHERE id = :account_id
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "contribution": contribution,
                "account_id": account_id
            })
            conn.commit()

    def update_account_total_value(self, account_id: str, total_value: float) -> None:
        """계정의 계좌총액 업데이트"""
        sql = """
            UPDATE accounts 
            SET total_value = :total_value 
            WHERE id = :account_id
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "total_value": total_value,
                "account_id": account_id
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
            if field not in ['limit_value', 'limit_type', 'target_amount', 'daily_money']:
                raise ValueError('Invalid field for update')
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

    def add_trading_rule(self, account_id: str, symbol: str, limit_value: float, limit_type: str,
                         target_amount: int, daily_money: float, trade_action: str) -> None:
        """새 거래 규칙 추가"""
        sql = """
               INSERT INTO trading_rules 
               (account_id, symbol, limit_value, limit_type, target_amount, daily_money, trade_action)
               VALUES (:account_id, :symbol, :limit_value, :limit_type, :target_amount, :daily_money, :trade_action)
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_id": account_id,
                "symbol": symbol,
                "limit_value": limit_value,
                "limit_type": limit_type,
                "target_amount": target_amount,
                "daily_money": daily_money,
                "trade_action": trade_action
            })
            conn.commit()

    def add_kr_trading_rule(self, account_id: str, symbol: str, stock_name: str, limit_value: int, limit_type: str,
                            target_amount: int, daily_money: int, trade_action: str) -> None:
        """한국주식 거래 규칙 추가"""
        sql = """
            INSERT INTO trading_rules 
            (account_id, symbol, stock_name, limit_value, limit_type, target_amount, daily_money, trade_action)
            VALUES (:account_id, :symbol, :stock_name, :limit_value, :limit_type, :target_amount, :daily_money, :trade_action)
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
                "trade_action": trade_action
            })
            conn.commit()
    def add_daily_result(self, today, account_id, cash_balance, total_value, etfs):
        sql = """
                    INSERT INTO daily_records 
                    (record_date, account_id, symbol, amount)
                    VALUES (:today, :account_id, :symbol, :amount)
                """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "today": today,
                "account_id": account_id,
                "symbol": "cash",
                "amount": cash_balance
            })
            conn.commit()
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "today": today,
                "account_id": account_id,
                "symbol": "total",
                "amount": total_value
            })
            conn.commit()
        for etf in etfs:
            etf_data = etfs[etf]
            etf_quantity = float(etf_data['quantity'])
            etf_price = float(etf_data['last_price'])
            etf_value = etf_quantity * etf_price
            with self.engine.connect() as conn:
                conn.execute(text(sql), {
                    "today": today,
                    "account_id": account_id,
                    "symbol": etf,
                    "amount": etf_value
                })
                conn.commit()
    def get_trading_rules(self) -> List[Dict]:
        """모든 거래 규칙 조회 (계정 설명 포함)"""
        sql = """
            SELECT tr.*, a.description as account_description 
            FROM trading_rules tr 
            JOIN accounts a ON tr.account_id = a.id 
            ORDER BY tr.status, tr.account_id
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

    def get_consolidated_portfolio_allocation(self):
        """모든 계좌의 종목들을 합쳐서 종목별 비중 조회 (계좌 상관없이 종목별로 합산)"""
        # 최신 날짜 찾기
        latest_date_sql = """
            SELECT MAX(record_date) as latest_date 
            FROM daily_records
        """

        # 해당 날짜의 모든 total 종목 가져오기 (전체 자금 계산용)
        total_sql = """
            SELECT SUM(amount) as total_value
            FROM daily_records
            WHERE record_date = :latest_date AND symbol = 'total'
        """

        # 해당 날짜의 모든 종목별 평가금액 합산 (계좌 상관없이 symbol로 그룹화)
        consolidated_sql = """
            SELECT symbol, SUM(amount) as total_value
            FROM daily_records
            WHERE record_date = :latest_date AND symbol != 'total'
            GROUP BY symbol
            ORDER BY total_value DESC
        """

        with self.engine.connect() as conn:
            # 최신 날짜 조회
            latest_date_result = conn.execute(text(latest_date_sql))
            latest_date = latest_date_result.fetchone().latest_date

            if not latest_date:
                return None, None

            # 전체 자금 조회
            total_result = conn.execute(text(total_sql), {"latest_date": latest_date})
            total_value = total_result.fetchone().total_value

            if not total_value:
                return None, None

            # 종목별 합산 데이터 조회
            consolidated_result = conn.execute(text(consolidated_sql), {"latest_date": latest_date})

            # 종목별 데이터 및 비중 계산
            allocations = []
            for row in consolidated_result:
                allocation = dict(row._mapping)
                allocation['percentage'] = (allocation['total_value'] / total_value) * 100
                allocations.append(allocation)

            return allocations, total_value

    def get_daily_total_values(self, max_points=50):
        """날짜별 총 자산 가치 조회 (스마트 샘플링)"""
        # 먼저 전체 데이터 개수 확인
        count_sql = """
            SELECT COUNT(DISTINCT record_date) as total_days
            FROM daily_records
            WHERE symbol = 'total'
        """

        with self.engine.connect() as conn:
            count_result = conn.execute(text(count_sql))
            total_days = count_result.fetchone().total_days

            if total_days <= max_points:
                # 데이터가 적으면 모든 데이터 반환
                sql = """
                    SELECT 
                        record_date,
                        SUM(amount) as total_value
                    FROM daily_records
                    WHERE symbol = 'total'
                    GROUP BY record_date
                    ORDER BY record_date ASC
                """
                result = conn.execute(text(sql))
            else:
                # 데이터가 많으면 샘플링
                # ROW_NUMBER를 사용하여 균등하게 샘플링
                interval = total_days // max_points
                sql = """
                    WITH ranked_data AS (
                        SELECT 
                            record_date,
                            SUM(amount) as total_value,
                            ROW_NUMBER() OVER (ORDER BY record_date) as rn
                        FROM daily_records
                        WHERE symbol = 'total'
                        GROUP BY record_date
                    )
                    SELECT record_date, total_value
                    FROM ranked_data
                    WHERE rn = 1 OR rn % :interval = 0 OR rn = :total_days
                    ORDER BY record_date ASC
                """
                result = conn.execute(text(sql), {
                    "interval": interval,
                    "total_days": total_days
                })

            data = []
            for row in result:
                row_dict = dict(row._mapping)
                # 날짜를 문자열로 변환
                row_dict['record_date'] = row_dict['record_date'].strftime('%Y-%m-%d')
                # Decimal을 float으로 변환
                if isinstance(row_dict['total_value'], decimal.Decimal):
                    row_dict['total_value'] = float(row_dict['total_value'])
                data.append(row_dict)

            return data