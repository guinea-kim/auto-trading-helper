from sqlalchemy import text
from typing import List, Dict, Optional
import decimal

class HistoryMixin:
    """
    Mixin for History and Analytics-related database operations.
    Assumes access to self.engine from the main DatabaseHandler class.
    """

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

    def get_contribution_history(self, account_number: str) -> List[Dict]:
        """특정 계좌의 기여금 이력 조회"""
        sql = """
            SELECT * FROM contribution_history 
            WHERE account_number = :account_number 
            ORDER BY transaction_date DESC
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"account_number": account_number})
            rows = []
            for row in result:
                d = dict(row._mapping)
                # Convert datetime/decimal types if necessary
                if 'amount' in d and isinstance(d['amount'], decimal.Decimal):
                    d['amount'] = float(d['amount'])
                if 'transaction_date' in d:
                    d['transaction_date'] = str(d['transaction_date'])
                if 'created_at' in d:
                    d['created_at'] = str(d['created_at'])
                rows.append(d)
            return rows

    def add_daily_result(self, today, account_id, cash_balance, total_value, etfs):
        sql = """
                    INSERT INTO daily_records 
                    (record_date, account_id, symbol, amount, quantity)
                    VALUES (:today, :account_id, :symbol, :amount, :quantity)
                """
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "today": today,
                "account_id": account_id,
                "symbol": "cash",
                "amount": cash_balance,
                "quantity": None
            })
            conn.commit()
        with self.engine.connect() as conn:
            conn.execute(text(sql), {
                "today": today,
                "account_id": account_id,
                "symbol": "total",
                "amount": total_value,
                "quantity": None
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
                    "amount": etf_value,
                    "quantity": float(etf_data['quantity'])
                })
                conn.commit()

    def get_consolidated_portfolio_allocation(self):
        """모든 계좌의 종목들을 합쳐서 종목별 비중 조회 (계좌 상관없이 종목별로 합산)"""
        # 최신 날짜 찾기
        latest_date_sql = """
            SELECT MAX(record_date) as latest_date 
            FROM daily_records
        """

        with self.engine.connect() as conn:
            # 최신 날짜 조회
            latest_date_result = conn.execute(text(latest_date_sql))
            latest_date = latest_date_result.fetchone().latest_date

            if not latest_date:
                return None, None
            
            # 이전 날짜 찾기 (어제 데이터를 위함)
            prev_date_sql = """
                SELECT MAX(record_date) as prev_date 
                FROM daily_records
                WHERE record_date < :latest_date
            """
            prev_date_result = conn.execute(text(prev_date_sql), {"latest_date": latest_date})
            prev_date_row = prev_date_result.fetchone()
            prev_date = prev_date_row.prev_date if prev_date_row else None

            # ---------------------------------------------------------
            # 1. 최신 데이터 조회
            # ---------------------------------------------------------

            # 해당 날짜의 모든 total 종목 가져오기 (전체 자금 계산용)
            total_sql = """
                SELECT SUM(amount) as total_value
                FROM daily_records
                WHERE record_date = :target_date AND symbol = 'total'
            """
            
            # 해당 날짜의 모든 종목별 평가금액 합산 (계좌 상관없이 symbol로 그룹화)
            consolidated_sql = """
                SELECT symbol, SUM(amount) as total_value, SUM(quantity) as total_quantity
                FROM daily_records
                WHERE record_date = :target_date AND symbol != 'total'
                GROUP BY symbol
                ORDER BY total_value DESC
            """

            # 전체 자금 조회 (최신)
            total_result = conn.execute(text(total_sql), {"target_date": latest_date})
            total_value = total_result.fetchone().total_value

            if not total_value:
                return None, None
            
            total_value = float(total_value)

            # 종목별 합산 데이터 조회 (최신)
            consolidated_result = conn.execute(text(consolidated_sql), {"target_date": latest_date})
            
            # 딕셔너리 형태로 변환하여 쉽게 접근
            current_data = {}
            for row in consolidated_result:
                d = dict(row._mapping)
                if 'total_quantity' in d and isinstance(d['total_quantity'], decimal.Decimal):
                    d['total_quantity'] = float(d['total_quantity'])
                if 'total_value' in d and isinstance(d['total_value'], decimal.Decimal):
                    d['total_value'] = float(d['total_value'])
                current_data[d['symbol']] = d
            
            # ---------------------------------------------------------
            # 2. 이전 데이터 조회 (데이터가 있을 경우에만)
            # ---------------------------------------------------------
            prev_data = {}
            prev_total_value = 0
            
            if prev_date:
                # 전체 자금 조회 (이전)
                pt_result = conn.execute(text(total_sql), {"target_date": prev_date})
                pt_row = pt_result.fetchone()
                if pt_row and pt_row.total_value:
                    prev_total_value = float(pt_row.total_value)
                
                # 종목별 합산 데이터 조회 (이전)
                pc_result = conn.execute(text(consolidated_sql), {"target_date": prev_date})
                for row in pc_result:
                    d = dict(row._mapping)
                    if 'total_quantity' in d and isinstance(d['total_quantity'], decimal.Decimal):
                        d['total_quantity'] = float(d['total_quantity'])
                    if 'total_value' in d and isinstance(d['total_value'], decimal.Decimal):
                        d['total_value'] = float(d['total_value'])
                    prev_data[d['symbol']] = d

            # ---------------------------------------------------------
            # 3. 데이터 병합 및 변화량 계산
            # ---------------------------------------------------------
            allocations = []
            
            # 현재 데이터 순회
            for symbol, curr in current_data.items():
                allocation = curr.copy()
                
                # 현재 비중 계산
                curr_percentage = (allocation['total_value'] / total_value) * 100
                allocation['percentage'] = curr_percentage
                
                # 이전 데이터와 비교
                if prev_date and symbol in prev_data:
                    prev = prev_data[symbol]
                    prev_percentage = (prev['total_value'] / prev_total_value) * 100 if prev_total_value > 0 else 0
                    
                    allocation['diff_quantity'] = (allocation['total_quantity'] or 0) - (prev['total_quantity'] or 0)
                    allocation['diff_value'] = float(allocation['total_value']) - float(prev['total_value'])
                    allocation['diff_percentage'] = curr_percentage - prev_percentage
                else:
                    # 이전 데이터가 없으면 변화량은 0 또는 신규 진입으로 볼 수 있음 (여기선 0이나 None 처리)
                    # 신규 진입인 경우 변화량 = 현재값
                    if prev_date: # 이전 날짜 데이터는 있는데 이 종목만 없는 경우 (New Entry)
                        allocation['diff_quantity'] = allocation.get('total_quantity', 0)
                        allocation['diff_value'] = float(allocation['total_value'])
                        allocation['diff_percentage'] = curr_percentage
                    else: # 아예 이전 날짜 기록이 없는 경우
                        allocation['diff_quantity'] = 0
                        allocation['diff_value'] = 0
                        allocation['diff_percentage'] = 0

                allocations.append(allocation)

            # 정렬 (비중 내림차순)
            allocations.sort(key=lambda x: x['percentage'], reverse=True)

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

    def get_daily_contributions(self) -> Dict[str, float]:
        """날짜별 전체 계좌의 기여금/인출금 합산 조회 (contribution_history 기반)"""
        # contribution_history 테이블이 존재하는지 확인 필요하지만, 
        # 일단 try-except로 감싸거나 테이블이 있다고 가정 (US는 확실, KR은 불확실하지만 쿼리 시도)
        try:
            sql = """
                SELECT 
                    DATE(transaction_date) as t_date, 
                    SUM(amount) as total_amount
                FROM contribution_history
                GROUP BY DATE(transaction_date)
                ORDER BY t_date ASC
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                
                data = {}
                for row in result:
                    row_dict = dict(row._mapping)
                    date_str = str(row_dict['t_date'])
                    val = row_dict['total_amount']
                    if isinstance(val, decimal.Decimal):
                        val = float(val)
                    data[date_str] = val
                return data
        except Exception as e:
            # 테이블이 없거나 에러 발생 시 빈 딕셔너리 반환
            print(f"Warning: Failed to fetch daily contributions ({e})")
            return {}

    def get_daily_records_by_date(self, date_str: str, symbol: str = 'total') -> list:
        """
        특정 날짜와 심볼에 해당하는 daily_records 조회
        """
        try:
            sql = """
                SELECT id, record_date, account_id, symbol, amount
                FROM daily_records
                WHERE record_date = :date_str AND symbol = :symbol
                ORDER BY id ASC
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"date_str": date_str, "symbol": symbol})
                return [dict(row._mapping) for row in result]
        except Exception as e:
            print(f"Error fetching daily records: {e}")
            return []

    def get_daily_records_breakdown(self, date_str: str) -> list:
        """
        특정 날짜의 daily_records를 계좌 정보와 함께 조회 (symbol='total'만).
        데이터가 없는 계좌도 포함하여 반환 (LEFT JOIN).
        """
        try:
            sql = """
                SELECT dr.id, :date_str as record_date, a.id as account_id, 
                       COALESCE(dr.symbol, 'total') as symbol, 
                       COALESCE(dr.amount, 0) as amount, 
                       a.description, a.user_id
                FROM accounts a
                LEFT JOIN daily_records dr 
                    ON a.id = dr.account_id 
                    AND dr.record_date = :date_str 
                    AND dr.symbol = 'total'
                ORDER BY a.id
            """
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"date_str": date_str})
                rows = []
                for row in result:
                    d = dict(row._mapping)
                    if isinstance(d['amount'], decimal.Decimal):
                        d['amount'] = float(d['amount'])
                    if d['record_date']:
                        d['record_date'] = str(d['record_date'])
                    rows.append(d)
                return rows
        except Exception as e:
            print(f"Error fetching daily breakdown: {e}")
            return []

    def get_adjacent_date(self, date_str: str, direction: str = 'prev') -> str:
        """
        주어진 날짜 기준으로 이전(prev) 또는 다음(next) 데이터가 있는 날짜를 조회.
        Returns:
            str: "YYYY-MM-DD" or None
        """
        try:
            op = '<' if direction == 'prev' else '>'
            order = 'DESC' if direction == 'prev' else 'ASC'
            
            sql = f"""
                SELECT record_date
                FROM daily_records
                WHERE record_date {op} :date_str AND symbol = 'total'
                ORDER BY record_date {order}
                LIMIT 1
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"date_str": date_str}).fetchone()
                if result:
                    return str(result[0])
                return None
        except Exception as e:
            print(f"Error fetching adjacent date ({direction}): {e}")
            return None

    def update_daily_record(self, record_id: int, amount: float):
        """
        특정 daily_record 업데이트
        """
        try:
            sql = """
                UPDATE daily_records
                SET amount = :amount
                WHERE id = :record_id
            """
            with self.engine.begin() as conn:
                conn.execute(text(sql), {"amount": amount, "record_id": record_id})
        except Exception as e:
            print(f"Error updating daily record {record_id}: {e}")
            raise

    def upsert_daily_record(self, date_str: str, account_id: str, amount: float, symbol: str = 'total') -> int:
        """
        daily_record 추가 또는 업데이트 (Upsert)
        """
        try:
            sql = """
                INSERT INTO daily_records (record_date, account_id, symbol, amount)
                VALUES (:date_str, :account_id, :symbol, :amount)
                ON DUPLICATE KEY UPDATE amount = :amount
            """
            with self.engine.begin() as conn:
                result = conn.execute(text(sql), {
                    "date_str": date_str, 
                    "account_id": account_id, 
                    "symbol": symbol, 
                    "amount": amount
                })
                # lastrowid might be 0 for updates in some drivers, but good enough for confirmation
                return result.lastrowid 
        except Exception as e:
            print(f"Error upserting daily record: {e}")
            raise
