from sqlalchemy import text
from typing import List, Dict

class AccountMixin:
    """
    Mixin for Account-related database operations.
    Assumes access to self.engine from the main DatabaseHandler class.
    """
    
    def get_accounts(self, use_dynamic_contribution=True):
        if use_dynamic_contribution:
            sql = """
            SELECT 
                a.*,
                COALESCE(
                    (SELECT SUM(amount) FROM contribution_history WHERE account_number = a.account_number),
                    0
                ) as dynamic_contribution
            FROM accounts a 
            ORDER BY a.id
            """
        else:
            sql = """
            SELECT a.* FROM accounts a ORDER BY a.id
            """

        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            accounts = []
            for row in result:
                d = dict(row._mapping)
                # Override static contribution with dynamic calculation ONLY if enabled
                if use_dynamic_contribution:
                    d['contribution'] = d['dynamic_contribution']
                accounts.append(d)
            return accounts
    
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

    def get_user_accounts(self, user_id: str) -> List[Dict]:
        """사용자의 계좌 목록 조회"""
        sql = """
               SELECT * FROM accounts 
               WHERE user_id = :user_id
           """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"user_id": user_id})
            return [dict(row._mapping) for row in result]

    def update_account_hash(self, account_number: str, hash_value: str, user_id: str) -> None:
        """계좌 hash값 업데이트"""
        sql = """
               UPDATE accounts 
               SET hash_value = :hash_value 
               WHERE account_number = :account_number and user_id = :user_id
           """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "hash_value": hash_value,
                "account_number": account_number,
                "user_id": user_id
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

    def update_account_type(self, account_id: str, account_type: str) -> None:
        """계정의 타입 업데이트"""
        sql = """
            UPDATE accounts 
            SET account_type = :account_type 
            WHERE id = :account_id
        """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "account_type": account_type,
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
