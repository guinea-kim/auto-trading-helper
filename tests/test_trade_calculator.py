import unittest
import math
from library.trade_calculator import TradeCalculator, BuyDecision, SellDecision

class TestTradeCalculator(unittest.TestCase):
    
    # =========================================================================
    # BUY LOGIC TESTS
    # =========================================================================

    def test_buy_standard_unconstrained(self):
        """Standard buy: No limits hit, enough cash."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=0,
            daily_money_limit=1000.0,
            today_traded_money=0.0,
            current_price=100.0,
            available_cash=2000.0,
            cash_only=True
        )
        self.assertEqual(decision.quantity, 10)
        self.assertEqual(decision.required_cash, 1000.0)
        self.assertEqual(decision.limit_reason, "OK")
        self.assertEqual(decision.shortfall, 0)

    def test_buy_daily_limit_partial(self):
        """Daily limit restricts quantity."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=0,
            daily_money_limit=500.0,  # Limit provided
            today_traded_money=150.0, # Used some
            current_price=100.0,
            available_cash=2000.0
        )
        # Remaining budget = 350. Price = 100. Max buy = 3.
        self.assertEqual(decision.quantity, 3)
        self.assertEqual(decision.limit_reason, "OK") # It's technically "OK" but limited by policy logic internal
    
    def test_buy_daily_limit_reached(self):
        """Daily limit already reached."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=0,
            daily_money_limit=500.0,
            today_traded_money=500.0,
            current_price=100.0,
            available_cash=2000.0
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Daily Limit Reached")

    def test_buy_insufficient_cash_strict(self):
        """Strict cash mode: cannot afford full policy quantity."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=0,
            daily_money_limit=2000.0,
            today_traded_money=0.0,
            current_price=100.0,
            available_cash=250.0, # Can only afford 2
            cash_only=True
        )
        self.assertEqual(decision.quantity, 2)
        self.assertEqual(decision.limit_reason, "Insufficient Cash")

    def test_buy_insufficient_cash_flexible_shortfall(self):
        """Flexible mode: returns full policy qty but reports shortfall."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=0,
            daily_money_limit=2000.0,
            today_traded_money=0.0,
            current_price=100.0,
            available_cash=250.0, # Has 250, needs 1000
            cash_only=False
        )
        self.assertEqual(decision.quantity, 10)
        self.assertEqual(decision.required_cash, 1000.0)
        self.assertEqual(decision.limit_reason, "Need Cash")
        self.assertEqual(decision.shortfall, 750.0) # 1000 - 250

    def test_buy_target_reached(self):
        """Already holding target amount."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=10,
            daily_money_limit=1000.0,
            today_traded_money=0.0,
            current_price=100.0,
            available_cash=2000.0
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Target Reached")

    def test_buy_price_zero_or_negative(self):
        """Invalid price protection."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10, current_holding=0, daily_money_limit=1000, 
            today_traded_money=0, current_price=0, available_cash=1000
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Invalid Price")

        decision_neg = TradeCalculator.calculate_buy_quantity(
            target_amount=10, current_holding=0, daily_money_limit=1000, 
            today_traded_money=0, current_price=-50, available_cash=1000
        )
        self.assertEqual(decision_neg.quantity, 0)
        self.assertEqual(decision_neg.limit_reason, "Invalid Price")

    def test_buy_floating_point_precision(self):
        """Precision test: Budget $100.00, Price $33.33 -> Buy 3."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=100,
            current_holding=0,
            daily_money_limit=100.00,
            today_traded_money=0.00,
            current_price=33.33,
            available_cash=1000.0
        )
        # 100.00 // 33.33 = 3.0003 -> 3
        self.assertEqual(decision.quantity, 3)
        
        # Exact boundary check 
        # 100 limit, 100 price
        decision_exact = TradeCalculator.calculate_buy_quantity(
            target_amount=10, current_holding=0, 
            daily_money_limit=100.0, today_traded_money=0.0, 
            current_price=100.0, available_cash=1000.0
        )
        self.assertEqual(decision_exact.quantity, 1)

    def test_buy_penny_limit(self):
        """Penalty test: Budget remaining $0.01, Price $0.02."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=10,
            current_holding=0,
            daily_money_limit=100.00,
            today_traded_money=99.99,
            current_price=0.02,
            available_cash=1000.0
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Daily Limit Reached")

    def test_buy_large_numbers(self):
        """Stress test with billions."""
        decision = TradeCalculator.calculate_buy_quantity(
            target_amount=1_000_000_000,
            current_holding=0,
            daily_money_limit=10_000_000_000.0,
            today_traded_money=0.0,
            current_price=10.0,
            available_cash=100_000_000_000.0
        )
        # Budget allows 1 billion shares.
        self.assertEqual(decision.quantity, 1_000_000_000)

    # =========================================================================
    # SELL LOGIC TESTS
    # =========================================================================

    def test_sell_standard(self):
        """Standard sell: Surplus exists, budget allows."""
        decision = TradeCalculator.calculate_sell_quantity(
            target_amount=5,
            current_holding=10, # Surplus 5
            daily_money_limit=1000.0,
            today_traded_money=0.0,
            current_price=100.0
        )
        self.assertEqual(decision.quantity, 5)
        self.assertEqual(decision.estimated_revenue, 500.0)
        self.assertEqual(decision.limit_reason, "OK")

    def test_sell_daily_limit(self):
        """Sell limited by daily budget."""
        decision = TradeCalculator.calculate_sell_quantity(
            target_amount=0,
            current_holding=10,
            daily_money_limit=200.0, # Can only move $200
            today_traded_money=0.0,
            current_price=100.0
        )
        self.assertEqual(decision.quantity, 2)
        self.assertEqual(decision.limit_reason, "OK") # Limited but actionable

    def test_sell_nothing_to_sell(self):
        """Holding matches target."""
        decision = TradeCalculator.calculate_sell_quantity(
            target_amount=10,
            current_holding=10,
            daily_money_limit=1000.0,
            today_traded_money=0.0,
            current_price=100.0
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Target Reached (No Surplus)")

    def test_sell_below_target(self):
        """Holding less than target (Do not sell logic)."""
        decision = TradeCalculator.calculate_sell_quantity(
            target_amount=15,
            current_holding=10,
            daily_money_limit=1000.0,
            today_traded_money=0.0,
            current_price=100.0
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Target Reached (No Surplus)")
    
    def test_sell_price_protection(self):
        """Invalid price for sell."""
        decision = TradeCalculator.calculate_sell_quantity(
            target_amount=0, current_holding=10, daily_money_limit=1000,
            today_traded_money=0, current_price=0
        )
        self.assertEqual(decision.quantity, 0)
        self.assertEqual(decision.limit_reason, "Invalid Price")

if __name__ == '__main__':
    unittest.main()
