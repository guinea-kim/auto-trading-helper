from dataclasses import dataclass
import math

@dataclass
class BuyDecision:
    quantity: int        # The calculated buy quantity
    required_cash: float # Cost for this quantity
    limit_reason: str    # Why was it limited? (e.g., "Daily Limit", "Cash", "Target Reached")
    shortfall: float     # How much more cash is needed (for ETF logic)

@dataclass
class SellDecision:
    quantity: int        # The calculated sell quantity
    estimated_revenue: float # Estimated revenue
    limit_reason: str    # Why was it limited?

class TradeCalculator:
    @staticmethod
    def calculate_buy_quantity(
        target_amount: int, 
        current_holding: int, 
        daily_money_limit: float, 
        today_traded_money: float, 
        current_price: float,
        available_cash: float,
        cash_only: bool = True
    ) -> BuyDecision:
        """
        Pure function to determine buy quantity.
        """
        # 0. Safety Checks
        if current_price <= 0:
            return BuyDecision(0, 0, "Invalid Price", 0)
        
        # 1. Policy Limits (Strategy)
        # 1-A. Quantity Gap (Target - Current)
        if current_holding < 0:
             # Unusual case: Negative holding? Treat as if we need to cover the negative amount + target
             # However, typically 'current_holding' should be >= 0. 
             # Let's assume standard behavior: we want to reach target.
             # If holding is -5 and target is 10, gap is 15.
             qty_gap = target_amount - current_holding
        else:
             qty_gap = max(0, target_amount - current_holding)

        # 1-B. Budget Gap (Daily Limit - Today's Traded)
        budget_remaining = max(0, daily_money_limit - today_traded_money)
        
        # Calculate max quantity allowed by budget
        # Use int() to floor, ensuring we don't exceed budget
        qty_by_budget = int(budget_remaining // current_price)
        
        # Policy-dictated max quantity is the stricter of the two
        policy_qty = min(qty_gap, qty_by_budget)
        
        # If policy says "Stop", we stop regardless of cash
        if policy_qty <= 0:
            if qty_gap <= 0:
                reason = "Target Reached"
            else:
                reason = "Daily Limit Reached"
            return BuyDecision(0, 0, reason, 0)

        # 2. Cash Limits (Wallet)
        policy_cost = policy_qty * current_price
        
        if cash_only:
            # Strict Mode: Can only buy what we can afford NOW
            # Use 0.9999 factor or similar? No, strict integer division is safest.
            # However, floating point precision might make 100.00 // 10.00 result in 9.999 -> 9.
            # To be safe against float epsilon issues where 100.0 / 10.0 might be 9.999999999998:
            # We can use a tiny epsilon or just trust python's float behavior for money usually handles this ok 
            # if we are careful. Better: effectively add a tiny epsilon to cash for division?
            # Or just accept that we might buy 1 less share in extremely rare edge cases, which is safer than buying 1 more.
            # Let's stick to standard // operator.
            
            affordable_qty = int(available_cash // current_price)
            final_qty = min(policy_qty, affordable_qty)
            
            if final_qty < policy_qty:
                return BuyDecision(final_qty, final_qty * current_price, "Insufficient Cash", 0)
            else:
                return BuyDecision(final_qty, final_qty * current_price, "OK", 0)
                
        else:
            # Flexible Mode: Return Policy Quantity, but calculate shortfall
            # This logic is for when we are allowed to sell other assets (ETF) to fund this buy.
            
            if policy_cost > available_cash:
                shortfall = policy_cost - available_cash
                return BuyDecision(policy_qty, policy_cost, "Need Cash", shortfall)
            else:
                return BuyDecision(policy_qty, policy_cost, "OK", 0)

    @staticmethod
    def calculate_sell_quantity(
        target_amount: int,
        current_holding: int,
        daily_money_limit: float,
        today_traded_money: float,
        current_price: float
    ) -> SellDecision:
        """
        Pure function to determine sell quantity.
        """
        if current_price <= 0:
            return SellDecision(0, 0, "Invalid Price")

        # 1. Quantity to sell (Surplus)
        # If we have 10 and target is 5, we can sell 5.
        # If we have 5 and target is 10, we sell 0.
        sellable_qty = max(0, current_holding - target_amount)

        # 2. Budget Limit
        # How much money can we move today?
        budget_remaining = max(0, daily_money_limit - today_traded_money)
        qty_by_budget = int(budget_remaining // current_price)

        # 3. Final Decision
        final_qty = min(sellable_qty, qty_by_budget)

        if final_qty <= 0:
            if sellable_qty <= 0:
                reason = "Target Reached (No Surplus)"
            else:
                reason = "Daily Limit Reached"
            return SellDecision(0, 0, reason)
        
        return SellDecision(final_qty, final_qty * current_price, "OK")
