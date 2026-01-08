from flask import Flask, render_template, request, redirect, url_for, flash
import os
from library import secret
from library.mysql_helper import DatabaseHandler

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secret.app_secret)

# DB Handler 인스턴스 생성
# DB Handler 인스턴스 생성
try:
    us_db_handler = DatabaseHandler(secret.db_name)
    kr_db_handler = DatabaseHandler(secret.db_name_kr)
except Exception as e:
    print(f"Warning: DB Connection failed ({e}). Starting in Offline Mode with Mock Data.")
    class MockHandler:
        def get_accounts(self): return []
        def get_trading_rules(self): return []
        def get_consolidated_portfolio_allocation(self): return [], 0
        def get_daily_total_values(self, n): return []
        def get_users(self): return []
    us_db_handler = MockHandler()
    kr_db_handler = MockHandler()


# Routes

@app.route('/')
def index():
    market = request.args.get('market', 'us')  # 기본값 'us', 한국은 'kr'
    
    # Select DB Handler based on market type
    if market == 'kr':
        current_db_handler = kr_db_handler
    else:
        current_db_handler = us_db_handler

    # 데이터 가져오기
    use_dynamic = (market == 'us')
    accounts = current_db_handler.get_accounts(use_dynamic_contribution=use_dynamic)
    trading_rules = current_db_handler.get_trading_rules()

    # 종목별 합산된 포트폴리오 배분 데이터 가져오기 (계좌 상관없이)
    consolidated_allocations, total_value = current_db_handler.get_consolidated_portfolio_allocation()

    total_contribution = 0.0
    for account in accounts:
        if account.get('contribution') is not None:
            try:
                total_contribution += float(account['contribution'])
            except (ValueError, TypeError):
                pass
    total_profit = float(total_value) - total_contribution
    profit_percent = (total_profit / total_contribution * 100) if total_contribution > 0 else 0
    is_kr_market = (market == 'kr')

    # 날짜별 총 자산 데이터 가져오기 (스마트 샘플링, 최대 50개 포인트)
    daily_total_values = current_db_handler.get_daily_total_values(50)

    return render_template('index.html',
                           accounts=accounts,
                           trading_rules=trading_rules,
                           current_market=market,
                           consolidated_allocations=consolidated_allocations,
                           total_value=total_value,
                           total_contribution=total_contribution,
                           total_profit=total_profit,
                           profit_percent=profit_percent,
                           is_kr_market=is_kr_market,
                           daily_total_values=daily_total_values)



@app.route('/account/add', methods=['POST'])
def add_account():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        description = request.form.get('description')
        account_number = request.form.get('account_number')
        market = request.form.get('market', 'us')
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        if not user_id or not account_number:
            flash("User ID and account number are required", "danger")
            return redirect(url_for('index', market=market))

        try:
            # Generate unique ID (you can modify this logic)
            account_id = current_db_handler.generate_account_id(user_id)
            current_db_handler.add_account(account_id, user_id, account_number, description)

            flash("Account added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")

        return redirect(url_for('index', market=market))


@app.route('/rule/add', methods=['POST'])
def add_trading_rule():
    if request.method == 'POST':
        market = request.form.get('market', 'us')
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        account_id = request.form.get('account_id')
        symbol = request.form.get('symbol')
        if market == 'kr':
            stock_name = request.form.get('stock_name')
        else:
            stock_name = None
        limit_value = request.form.get('limit_value')
        limit_type = request.form.get('limit_type')
        target_amount = request.form.get('target_amount')
        daily_money = request.form.get('daily_money')
        trade_action = request.form.get('trade_action')
        cash_only = 1 if 'cash_only' in request.form else 0

        required_fields = ['account_id', 'symbol', 'limit_value', 'limit_type', 'target_amount', 'daily_money', 'trade_action']
        missing_fields = [field for field in required_fields if not request.form.get(field)]
        if missing_fields:
            flash(f"Missing required fields: {', '.join(missing_fields)}", "danger")
            return redirect(url_for('index', market=market))

        try:
            if market == 'kr':
                current_db_handler.add_kr_trading_rule(
                    account_id,
                    symbol,
                    stock_name,
                    int(limit_value),
                    limit_type,
                    int(target_amount),
                    int(daily_money),
                    trade_action,
                    cash_only
                )
            else:
                current_db_handler.add_trading_rule(
                    account_id,
                    symbol,
                    float(limit_value),
                    limit_type,
                    int(target_amount),
                    float(daily_money),
                    trade_action,
                    cash_only
                )
            flash("Trading rule added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for('index', market=market))


@app.route('/account/update_contribution', methods=['POST'])
def update_account_contribution():
    """계정의 기여금 업데이트"""
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        contribution = request.form.get('contribution')
        market = request.form.get('market', 'us')  # 시장 구분 파라미터 추가
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        if not account_id or not contribution:
            flash("계정 ID와 기여금이 필요합니다", "danger")
            return redirect(url_for('index'))

        try:
            # 기여금을 부동소수점으로 변환
            contribution_value = float(contribution)

            # DB 핸들러를 통해 기여금 업데이트
            current_db_handler.update_account_contribution(account_id, contribution_value)

            flash(f"계정 {account_id}의 기여금이 성공적으로 업데이트되었습니다!", "success")
        except ValueError:
            flash("기여금은 유효한 숫자여야 합니다", "danger")
        except Exception as e:
            flash(f"오류: {str(e)}", "danger")

        return redirect(url_for('index', market=market))

@app.route('/account/update_type', methods=['POST'])
def update_account_type():
    """계정의 타입 업데이트"""
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        account_type = request.form.get('account_type')
        market = request.form.get('market', 'us')
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        
        if not account_id or not account_type:
            flash("Account ID and Type are required", "danger")
            return redirect(url_for('index', market=market))

        try:
            current_db_handler.update_account_type(account_id, account_type)
            flash(f"Account {account_id} type updated to {account_type}!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

        return redirect(url_for('index', market=market))

@app.route('/rule/update/<int:rule_id>', methods=['POST'])
def update_rule_status(rule_id):
    status = request.form.get('status')
    market = request.form.get('market', 'us')  # 시장 구분 파라미터 추가
    current_db_handler = us_db_handler if market == 'us' else kr_db_handler
    if not status:
        flash("Status is required", "danger")
        return redirect(url_for('index', market=market))

    try:
        # Update rule status using DB handler
        current_db_handler.update_rule_status(rule_id, status)

        flash("Trading rule status updated successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for('index', market=market))


@app.route('/api/highest-price/<symbol>', methods=['GET'])
def get_highest_price(symbol):
    # US market만 지원
    highest_price = us_db_handler.get_highest_price(symbol)
    return {'symbol': symbol, 'highest_price': highest_price}


@app.route('/api/history/<account_number>', methods=['GET'])
def get_contribution_history_api(account_number):
    try:
        # Determine market handler if needed, but history is likely same DB structure
        # Assuming US DB handler is primary for now or based on current market context?
        # The history table is in the main DB.
        # Since 'contribution_history' is likely in the same DB as 'accounts', 
        # and we saw both us_db_handler and kr_db_handler share the same DB connection logic (just different DB names).
        # We should check both or rely on a query parameter?
        # Actually, accounts table has 'market' implied? No, `add_account` uses us or kr db handler.
        # Let's check which DB the account is in.
        
        # Simple approach: Check US first, if empty, check KR? 
        # Or better: Pass 'market' query param.
        market = request.args.get('market', 'us')
        if market == 'kr':
            return {'account_number': account_number, 'history': []}

        db_handler = us_db_handler if market == 'us' else kr_db_handler
        
        history = db_handler.get_contribution_history(account_number)
        return {'account_number': account_number, 'history': history}
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/daily-assets', methods=['GET'])
def get_daily_assets():
    market = request.args.get('market', 'us')  # 기본값 'us', 한국은 'kr'
    
    # Select DB Handler based on market type
    if market == 'kr':
        current_db_handler = kr_db_handler
    else:
        current_db_handler = us_db_handler

    # Fetch all daily records (limit to 10000 days to get mostly everything)
    daily_data_list = current_db_handler.get_daily_total_values(max_points=10000)
    
    # Transform list to dictionary: { "YYYY-MM-DD": value }
    assets_map = {}
    for item in daily_data_list:
        # mysql_helper returns date string in 'YYYY-MM-DD' format
        assets_map[item['record_date']] = item['total_value']
    
    # Fetch contribution data
    contributions_map = current_db_handler.get_daily_contributions()

    return {
        "assets": assets_map,
        "contributions": contributions_map
    }

@app.route('/rule/update_field/<int:rule_id>/<field>', methods=['POST'])
def update_rule_field(rule_id, field):
    value = request.form.get('value')
    market = request.form.get('market', 'us')
    current_db_handler = us_db_handler if market == 'us' else kr_db_handler


    try:
        if field not in ['limit_value', 'limit_type', 'target_amount', 'daily_money', 'cash_only']:
            flash("Invalid field to update", "danger")
            return redirect(url_for('index', market=market))
        if field == 'limit_value' or field == 'daily_money':
            value = float(value)
        elif field == 'target_amount':
            value = int(value)
        elif field == 'cash_only':
            value = 1 if value == '1' else 0
        # limit_type은 그대로
        current_db_handler.update_rule_field(rule_id, field, value)
        flash(f"Trading rule {field} updated successfully!", "success")
    except ValueError:
        flash(f"Invalid value format for {field}", "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('index', market=market))

if __name__ == '__main__':
    app.run(debug=True)