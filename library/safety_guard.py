

class SafetyException(Exception):
    pass

class OrderValidator:
    # HARDCODED LIMITS - DO NOT CHANGE WITHOUT CODE REVIEW
    # Protect against "Fat Finger" size errors (e.g. 10x or 100x intended size)
    MAX_ORDER_AMOUNT_KRW = 100_000_000  # 1억원
    MAX_ORDER_AMOUNT_USD = 100_000      # $100,000
    
    # Protect against "Data Error" (e.g. price coming in as 0 or near 0)
    MIN_PRICE_KRW = 50     # 50 KRW
    MIN_PRICE_USD = 0.5    # $0.50
    
    @staticmethod
    def _get_limits(market: str):
        if market == 'US':
            return OrderValidator.MAX_ORDER_AMOUNT_USD, OrderValidator.MIN_PRICE_USD
        return OrderValidator.MAX_ORDER_AMOUNT_KRW, OrderValidator.MIN_PRICE_KRW

    @staticmethod
    def validate_buy(market: str, symbol: str, price: float, quantity: int, current_cash: float):
        """
        Validates BUY order parameters.
        Checks: Quantity > 0, Price > Min, Total Amount < Max Limit, Total Amount <= Balance
        """
        if quantity <= 0:
            raise SafetyException(f"Invalid quantity: {quantity}")
        if price <= 0:
            raise SafetyException(f"Invalid price: {price}")
            
        total_amount = price * quantity
        max_limit, min_price = OrderValidator._get_limits(market)
        
        # 1. Fat Finger Check (Absolute Amount)
        if total_amount > max_limit:
            raise SafetyException(f"FATAL: Buy amount {total_amount:,.2f} exceeds hard limit {max_limit:,.2f}")
            
        # 2. Penny Stock / Data Error Check
        if price < min_price:
            raise SafetyException(f"ERROR: Price {price} is below minimum threshold {min_price}")

        # 3. Solvency Check (Strict vs Balance)
        # We allow up to 100% of cash. If logic assumes we can buy $100 with $99.99, this will block it.
        # This acts as a final sanity check against logic bugs that ignore balance.
        if current_cash > 0 and total_amount > (current_cash * 1.0):
            # Using epsilon or slight tolerance might be dangerous, strict check is preferred for safety.
            # If rounding causes issues, the caller should floor their values.
            raise SafetyException(f"DANGER: Buy amount {total_amount:,.2f} exceeds available cash {current_cash:,.2f}")

        return True

    @staticmethod
    def validate_sell(market: str, symbol: str, price: float, quantity: int, current_holding: int):
        """
        Validates SELL order parameters.
        Checks: Quantity > 0, Price > Min, Total Amount < Max Limit, Quantity <= Holding
        """
        if quantity <= 0:
            raise SafetyException(f"Invalid quantity: {quantity}")
        if price <= 0:
            raise SafetyException(f"Invalid price: {price}")
            
        total_amount = price * quantity
        max_limit, min_price = OrderValidator._get_limits(market)

        # 1. Fat Finger Check (Absolute Amount for Safety)
        if total_amount > max_limit:
            raise SafetyException(f"FATAL: Sell amount {total_amount:,.2f} exceeds hard limit {max_limit:,.2f}")

        # 2. Price Check
        if price < min_price:
            raise SafetyException(f"ERROR: Price {price} is below minimum threshold {min_price}")

        # 3. Holding Check (Short Sell Prevention)
        if current_holding is not None and quantity > current_holding:
            raise SafetyException(f"DANGER: Sell quantity {quantity} exceeds current holding {current_holding}")

        return True

class StateIntegrityGuard:
    """
    Guard: Start-up State Integrity
    Prevents "Zombie Trading" (re-buying manually sold assets) and "Phantom Selling".
    Compares DB State vs Broker State. If mismatch without Split Signature -> STOP.
    """
    @staticmethod
    def check_integrity(db_handler, manager, user_id, broker_positions):
        """
        Checks state integrity for all active rules of a user.
        Raises SystemExit if a critical integrity violation is found.
        
        broker_positions: dict {hash_value: {symbol: {quantity, last_price, average_price}}}
                          Note: The structure passed from trader.py's positions_result_by_account 
                          is {hash_value: {symbol: {...}}}.
        """
        # 1. Get Active Rules from DB
        rules = db_handler.get_active_trading_rules()
        user_rules = [r for r in rules if r['user_id'] == user_id]
        
        issues = []
        
        for rule in user_rules:
            symbol = rule['symbol']
            stock_name = rule.get('stock_name', symbol) # Use stock_name if available (e.g. KR market uses codes)
            hash_val = rule['hash_value']
            
            # 2. Get DB State
            db_qty = float(rule.get('current_holding', 0))
            db_avg_price = float(rule.get('average_price', 0))
            
            # 3. Get Broker State
            # positions_result_by_account structure: {hash_val: {symbol: {data}}}
            broker_account_data = broker_positions.get(hash_val, {})
            broker_data = broker_account_data.get(symbol)
            
            # If broker_data is None, it means 0 quantity held at broker
            if not broker_data:
                broker_qty = 0.0
                broker_price = 0.0 # Cannot determine current price easily if not holding
            else:
                broker_qty = float(broker_data['quantity'])
                broker_price = float(broker_data['last_price'])
            
            # 4. Compare
            # Use small epsilon for float comparison
            if abs(broker_qty - db_qty) < 0.001:
                continue # Perfect Match
                
            # 5. Analyze Mismatch
            
            # Case A: Phantom Position in DB (DB says we have it, Broker says 0)
            if db_qty > 0.001 and broker_qty == 0:
                 issues.append(f"CRITICAL: Phantom Position in DB. {stock_name} ({symbol}) DB:{db_qty} vs Broker:0.")
                 continue

            # Case B: New Position (DB says 0, Broker has it) -> Usually safe, likely Manual Buy or Dividend
            if db_qty == 0 and broker_qty > 0:
                # Log as info, but do not block. The system usually treats this as 'unmanaged' until rule is updated.
                # Or if rule exists but current_holding is 0, it might be a re-entry.
                # For now, we assume this is SAFE.
                continue
                
            # Case C: Quantity Mismatch (Both have > 0) -> Check for Split vs Manual Trade
            if db_avg_price > 0:
                 if broker_price == 0:
                     # Should not happen if broker_qty > 0, but safety check
                     issues.append(f"CRITICAL: Quantity Mismatch and Invalid Broker Price. {stock_name} ({symbol}) DB:{db_qty} vs Broker:{broker_qty}")
                     continue

                 ratio = broker_price / db_avg_price
                 
                 # Define "Split Signature" vs "Manual Trade Signature"
                 # Manual Trade: Price is roughly same (Ratio ~ 1.0), Qty changed.
                 # Split: Price changed significantly (Ratio ~ 0.5, 0.1, etc).
                 
                 # We assume normal volatility is within +/- 30% (0.7 ~ 1.3)
                 # If ratio is outside 0.7~1.3, it is likely a Split or massive crash (which pauses trading anyway).
                 # If ratio is INSIDE 0.7~1.3, and Qty changed => MANUAL TRADE.
                 
                 is_likely_split = (ratio < 0.7 or ratio > 1.3)
                 
                 if not is_likely_split:
                     issues.append(f"CRITICAL: Quantity Mismatch without Split Signature. {stock_name} ({symbol}): DB:{db_qty} vs Real:{broker_qty}. Price Ratio:{ratio:.2f} (Not a split). Likely Manual Trade.")
                 else:
                     # Likely a split, let the existing sync_split_adjustments logic handle it.
                     pass
            else:
                # DB Avg Price is 0, but we have quantity? Data anomaly.
                issues.append(f"CRITICAL: Quantity Mismatch with DB Avg Price 0. {stock_name} ({symbol}) DB:{db_qty} vs Broker:{broker_qty}")

        if issues:
            msg = "STATE INTEGRITY ERROR:\n" + "\n".join(issues)
            raise SafetyException(msg) 
