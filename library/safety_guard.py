from decimal import Decimal

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
