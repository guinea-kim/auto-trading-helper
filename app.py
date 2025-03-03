from flask import Flask, render_template, request, redirect, url_for, flash
import os
from library import secret
from library.mysql_helper import DatabaseHandler

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secret.app_secret)

# DB Handler 인스턴스 생성
db_handler = DatabaseHandler()


# Routes
@app.route('/')
def index():
    # Get all accounts
    accounts = db_handler.get_accounts()

    # Get all trading rules
    trading_rules = db_handler.get_trading_rules()

    return render_template('index.html', accounts=accounts, trading_rules=trading_rules)


@app.route('/account/add', methods=['POST'])
def add_account():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        description = request.form.get('description')
        account_number = request.form.get('account_number')

        if not user_id or not account_number:
            flash("User ID and account number are required", "danger")
            return redirect(url_for('index'))

        try:
            # Generate unique ID (you can modify this logic)
            account_id = db_handler.generate_account_id(user_id)
            db_handler.add_account(account_id, user_id, account_number, description)

            flash("Account added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")

        return redirect(url_for('index'))


@app.route('/rule/add', methods=['POST'])
def add_trading_rule():
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        symbol = request.form.get('symbol')
        limit_price = request.form.get('limit_price')
        target_amount = request.form.get('target_amount')
        daily_money = request.form.get('daily_money')
        trade_action = request.form.get('trade_action')
        # Validate inputs
        if not all([account_id, symbol, limit_price, target_amount, daily_money, trade_action]):
            flash("All fields are required", "danger")
            return redirect(url_for('index'))

        try:
            # Insert trading rule using DB handler
            db_handler.add_trading_rule(
                account_id,
                symbol,
                float(limit_price),
                int(target_amount),
                float(daily_money),
                trade_action
            )

            flash("Trading rule added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")

        return redirect(url_for('index'))


@app.route('/rule/update/<int:rule_id>', methods=['POST'])
def update_rule_status(rule_id):
    status = request.form.get('status')

    if not status:
        flash("Status is required", "danger")
        return redirect(url_for('index'))

    try:
        # Update rule status using DB handler
        db_handler.update_rule_status(rule_id, status)

        flash("Trading rule status updated successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for('index'))


@app.route('/rule/update_field/<int:rule_id>/<field>', methods=['POST'])
def update_rule_field(rule_id, field):
    value = request.form.get('value')

    if not value:
        flash(f"{field} value is required", "danger")
        return redirect(url_for('index'))

    try:
        # 필드 유효성 검사
        if field not in ['limit_price', 'target_amount', 'daily_money']:
            flash("Invalid field to update", "danger")
            return redirect(url_for('index'))

        # 데이터 유효성 검사 및 변환
        if field == 'limit_price':
            value = float(value)
        elif field == 'target_amount':
            value = int(value)
        elif field == 'daily_money':
            value = float(value)

        # DB 핸들러를 통해 필드 업데이트
        db_handler.update_rule_field(rule_id, field, value)

        flash(f"Trading rule {field} updated successfully!", "success")
    except ValueError:
        flash(f"Invalid value format for {field}", "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)