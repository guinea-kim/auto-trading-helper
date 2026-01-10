from sqlalchemy import create_engine, text
import pymysql.cursors
from library import secret
from library.db_modules.account_mixin import AccountMixin
from library.db_modules.trading_rule_mixin import TradingRuleMixin
from library.db_modules.history_mixin import HistoryMixin

pymysql.install_as_MySQLdb()

class DatabaseHandler(AccountMixin, TradingRuleMixin, HistoryMixin):
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

    def execute_many(self, sql: str, args: list) -> None:
        """Execute multiple SQL statements (bulk insert/update)"""
        conn = self.engine.raw_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.executemany(sql, args)
                conn.commit()
            finally:
                cursor.close()
        finally:
            conn.close()
