import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from library.mysql_helper import DatabaseHandler
from library import secret

def main():
    db = DatabaseHandler(secret.db_name)
    
    print("Checking contribution_history table...")
    with db.engine.connect() as conn:
        result = conn.execute(text("SELECT count(*) as count FROM contribution_history"))
        count = result.fetchone()[0]
        print(f"Total rows: {count}")
        
        if count > 0:
            print("Last 5 entries:")
            rows = conn.execute(text("SELECT * FROM contribution_history ORDER BY id DESC LIMIT 5"))
            for row in rows:
                print(row)

if __name__ == "__main__":
    main()
