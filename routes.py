from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app_handlers import us_db_handler, kr_db_handler

bp = Blueprint('main', __name__)

@bp.route('/')
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

    # trading_rules 분리 (Active vs Inactive)
    active_rules = []
    inactive_rules = []
    
    for rule in trading_rules:
        if rule.get('status') in ['ACTIVE', 'PROCESSED']:
            active_rules.append(rule)
        else:
            inactive_rules.append(rule)

    # 날짜별 총 자산 데이터 가져오기 (스마트 샘플링, 최대 50개 포인트)
    daily_total_values = current_db_handler.get_daily_total_values(50)

    return render_template('index.html',
                           accounts=accounts,
                           active_rules=active_rules,
                           inactive_rules=inactive_rules,
                           current_market=market,
                           consolidated_allocations=consolidated_allocations,
                           total_value=total_value,
                           total_contribution=total_contribution,
                           total_profit=total_profit,
                           profit_percent=profit_percent,
                           is_kr_market=is_kr_market,
                           daily_total_values=daily_total_values)



@bp.route('/account/add', methods=['POST'])
def add_account():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        description = request.form.get('description')
        account_number = request.form.get('account_number')
        market = request.form.get('market', 'us')
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        if not user_id or not account_number:
            flash("User ID and account number are required", "danger")
            return redirect(url_for('main.index', market=market))

        try:
            # Generate unique ID (you can modify this logic)
            account_id = current_db_handler.generate_account_id(user_id)
            current_db_handler.add_account(account_id, user_id, account_number, description)

            flash("Account added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")

        return redirect(url_for('main.index', market=market))


@bp.route('/rule/add', methods=['POST'])
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
            return redirect(url_for('main.index', market=market))

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
        return redirect(url_for('main.index', market=market))


@bp.route('/account/update_contribution', methods=['POST'])
def update_account_contribution():
    """계정의 기여금 업데이트"""
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        contribution = request.form.get('contribution')
        market = request.form.get('market', 'us')  # 시장 구분 파라미터 추가
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        if not account_id or not contribution:
            flash("계정 ID와 기여금이 필요합니다", "danger")
            return redirect(url_for('main.index'))

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

        return redirect(url_for('main.index', market=market))

@bp.route('/account/update_type', methods=['POST'])
def update_account_type():
    """계정의 타입 업데이트"""
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        account_type = request.form.get('account_type')
        market = request.form.get('market', 'us')
        current_db_handler = us_db_handler if market == 'us' else kr_db_handler
        
        if not account_id or not account_type:
            flash("Account ID and Type are required", "danger")
            return redirect(url_for('main.index', market=market))

        try:
            current_db_handler.update_account_type(account_id, account_type)
            flash(f"Account {account_id} type updated to {account_type}!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

        return redirect(url_for('main.index', market=market))

@bp.route('/rule/update/<int:rule_id>', methods=['POST'])
def update_rule_status(rule_id):
    status = request.form.get('status')
    market = request.form.get('market', 'us')  # 시장 구분 파라미터 추가
    current_db_handler = us_db_handler if market == 'us' else kr_db_handler
    if not status:
        flash("Status is required", "danger")
        return redirect(url_for('main.index', market=market))

    try:
        # Update rule status using DB handler
        current_db_handler.update_rule_status(rule_id, status)

        flash("Trading rule status updated successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for('main.index', market=market))


@bp.route('/api/highest-price/<symbol>', methods=['GET'])
def get_highest_price(symbol):
    # US market만 지원
    highest_price = us_db_handler.get_highest_price(symbol)
    return {'symbol': symbol, 'highest_price': highest_price}


@bp.route('/api/history/<account_number>', methods=['GET'])
def get_contribution_history_api(account_number):
    try:
        market = request.args.get('market', 'us')
        if market == 'kr':
            return {'account_number': account_number, 'history': []}

        db_handler = us_db_handler if market == 'us' else kr_db_handler
        
        history = db_handler.get_contribution_history(account_number)
        return {'account_number': account_number, 'history': history}
    except Exception as e:
        return {'error': str(e)}, 500


@bp.route('/api/daily-assets', methods=['GET'])
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

@bp.route('/api/daily-assets/breakdown', methods=['GET'])
def get_daily_assets_breakdown():
    date_str = request.args.get('date')
    market = request.args.get('market', 'us')

    if not date_str:
        return jsonify({"status": "error", "message": "Missing date parameter"}), 400

    # Determine DB handler based on market
    if market == 'kr':
        handler = kr_db_handler
    else:
        handler = us_db_handler

    try:
        current_data = handler.get_daily_records_breakdown(date_str)
        
        # Fetch adjacent context
        prev_date = handler.get_adjacent_date(date_str, 'prev')
        next_date = handler.get_adjacent_date(date_str, 'next')
        
        prev_data = handler.get_daily_records_breakdown(prev_date) if prev_date else []
        next_data = handler.get_daily_records_breakdown(next_date) if next_date else []

        return jsonify({
            "current": current_data,
            "prev": {"date": prev_date, "data": prev_data} if prev_date else None,
            "next": {"date": next_date, "data": next_data} if next_date else None
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/api/daily-assets/update', methods=['POST'])
def update_daily_asset():
    data = request.json
    date_str = data.get('date')
    amount = data.get('amount')
    record_id = data.get('record_id') # Optional: if updating specific record
    currency = data.get('currency', 'USD')
    dry_run = data.get('dry_run', False)
    market = data.get('market', 'us')

    if not date_str or amount is None:
        return jsonify({"status": "error", "message": "Missing date or amount"}), 400

    # Determine DB handler based on market
    if market == 'kr':
        handler = kr_db_handler
    else:
        handler = us_db_handler 

    try:
        current_amount = float(amount)
        
        if record_id:
             # Case 1: Updating specific record (Account Level)
             records = handler.get_daily_records_breakdown(date_str)
             target_record = next((r for r in records if str(r['id']) == str(record_id)), None)
             
             if not target_record:
                 return jsonify({"status": "error", "message": "Record not found"}), 404
                 
             original_amount = float(target_record['amount'])
             diff = current_amount - original_amount
             
             plan = {
                "status": "success",
                "type": "update",
                "target_table": "daily_records",
                "target_id": record_id,
                "target_account": target_record['account_id'],
                "current_value": original_amount,
                "new_value": current_amount,
                "diff": diff,
                "dry_run": dry_run
             }
             
             if not dry_run:
                 handler.update_daily_record(record_id, current_amount)
                 plan["executed"] = True
                 
             return jsonify(plan)
             
        elif data.get('account_id'):
            # Case 2: Create New Record (Missing ID but Account ID provided)
            # Check if record already exists for this account/date to prevent dups? 
            # (Assuming frontend handles display, but safe to check? For now trust frontend context)
            account_id = data.get('account_id')
            
            plan = {
                "status": "success",
                "type": "insert",
                "target_table": "daily_records",
                "target_account": account_id,
                "new_value": current_amount,
                "dry_run": dry_run
            }
            
            if not dry_run:
                new_id = handler.upsert_daily_record(date_str, account_id, current_amount)
                plan["new_id"] = new_id
                plan["executed"] = True
                
            return jsonify(plan)
            
        else:
            return jsonify({"status": "error", "message": "Missing record_id or account_id"}), 400
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/rule/update_field/<int:rule_id>/<field>', methods=['POST'])
def update_rule_field(rule_id, field):
    value = request.form.get('value')
    market = request.form.get('market', 'us')
    current_db_handler = us_db_handler if market == 'us' else kr_db_handler


    try:
        if field not in ['limit_value', 'limit_type', 'target_amount', 'daily_money', 'cash_only']:
            flash("Invalid field to update", "danger")
            return redirect(url_for('main.index', market=market))
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
    return redirect(url_for('main.index', market=market))
