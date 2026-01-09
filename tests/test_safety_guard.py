
import unittest
from library.safety_guard import OrderValidator, SafetyException

class TestSafetyGuard(unittest.TestCase):
    def test_positive_buy_us(self):
        # Normal Buy: $500 of AAPL (Balance $10,000)
        self.assertTrue(OrderValidator.validate_buy('US', 'AAPL', 150.0, 10, 10000.0))
        
    def test_positive_sell_us(self):
        # Normal Sell: Sell 10 shares (Holding 100)
        self.assertTrue(OrderValidator.validate_sell('US', 'AAPL', 150.0, 10, 100))

    def test_positive_all_in_buy(self):
        # All-in Buy: Buy exact 100% of cash
        self.assertTrue(OrderValidator.validate_buy('US', 'AAPL', 100.0, 10, 1000.0))

    def test_positive_full_liquidation(self):
        # Full Liquidation
        self.assertTrue(OrderValidator.validate_sell('US', 'AAPL', 100.0, 50, 50))
        
    def test_fat_finger_buy(self):
        # Buy $200,000 (Limit $100k)
        with self.assertRaises(SafetyException) as cm:
            OrderValidator.validate_buy('US', 'AAPL', 200.0, 1000, 500000.0)
        self.assertIn("exceeds hard limit", str(cm.exception))

    def test_fat_finger_sell(self):
        # Sell $200,000 (Limit $100k)
        with self.assertRaises(SafetyException) as cm:
            OrderValidator.validate_sell('US', 'AAPL', 200.0, 1000, 1000)
        self.assertIn("exceeds hard limit", str(cm.exception))

    def test_insolvent_buy(self):
        # Buy $10,001 (Balance $10,000)
        with self.assertRaises(SafetyException) as cm:
            OrderValidator.validate_buy('US', 'AAPL', 100.0, 101, 10000.0)
        self.assertIn("exceeds available cash", str(cm.exception))

    def test_naked_short(self):
        # Sell 11 shares (Holding 10)
        with self.assertRaises(SafetyException) as cm:
            OrderValidator.validate_sell('US', 'AAPL', 100.0, 11, 10)
        self.assertIn("exceeds current holding", str(cm.exception))
        
    def test_penny_stock_prevention(self):
        # US: < $0.50
        with self.assertRaises(SafetyException):
            OrderValidator.validate_buy('US', 'PENNY', 0.49, 100, 1000.0)
            
        # KR: < 50 KRW
        with self.assertRaises(SafetyException):
            OrderValidator.validate_buy('KR', '000000', 49.0, 100, 10000.0)
            
    def test_split_adjustment_scenario(self):
        # Price 1000 -> 100, Qty 10 -> 100. Total value constant. Should pass.
        # Before split
        self.assertTrue(OrderValidator.validate_sell('US', 'TSLA', 1000.0, 10, 10))
        # After split
        self.assertTrue(OrderValidator.validate_sell('US', 'TSLA', 100.0, 100, 100))

    def test_rounding_edge_case(self):
        # Buy $10,000.000001 with $10,000 Cash -> Should Block
        price = 100.0000001
        qty = 100
        cash = 10000.0
        with self.assertRaises(SafetyException):
            OrderValidator.validate_buy('US', 'TEST', price, qty, cash)

if __name__ == '__main__':
    unittest.main()
