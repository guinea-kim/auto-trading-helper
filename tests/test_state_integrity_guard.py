
import unittest
from unittest.mock import MagicMock
from library.safety_guard import StateIntegrityGuard, SafetyException

class TestStateIntegrityGuard(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_manager = MagicMock()
        self.user_id = 'test_user'
        self.hash_val = 'hash123'
        
        # Setup basic rule structure
        self.base_rule = {
            'user_id': self.user_id,
            'symbol': 'AAPL',
            'stock_name': 'Apple',
            'hash_value': self.hash_val,
            'current_holding': 100,
            'average_price': 150.0,
            'id': 1
        }

    def test_perfect_match(self):
        """DB and Broker match perfectly -> Should Pass"""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        broker_positions = {
            self.hash_val: {
                'AAPL': {
                    'quantity': 100,
                    'last_price': 155.0, # Slight price move is normal
                    'average_price': 150.0
                }
            }
        }
        
        # Should not raise exception
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

    def test_phantom_position(self):
        """DB has shares, Broker has 0 -> Should Fail (Critical)"""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        # Empty broker positions for this symbol
        broker_positions = {
            self.hash_val: {}
        }
        
        with self.assertRaises(SafetyException) as cm:
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        self.assertIn("Phantom Position", str(cm.exception))
        self.assertIn("DB:100", str(cm.exception))

    def test_manual_sell_detection(self):
        """Qty changed, Price mismatch small (Ratio ~1.0) -> Should Fail (Manual Trade)"""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        # User sold 50 shares
        broker_positions = {
            self.hash_val: {
                'AAPL': {
                    'quantity': 50, # DB has 100
                    'last_price': 150.0, # Price same
                    'average_price': 150.0
                }
            }
        }
        
        with self.assertRaises(SafetyException) as cm:
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        self.assertIn("Quantity Mismatch without Split Signature", str(cm.exception))
        self.assertIn("Likely Manual Trade", str(cm.exception))

    def test_split_detection_pass(self):
        """Qty doubled, Price halved (Ratio ~0.5) -> Should Pass (Allow Sync)"""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        # 2-for-1 Split
        broker_positions = {
            self.hash_val: {
                'AAPL': {
                    'quantity': 200, # DB has 100
                    'last_price': 75.0, # DB Avg was 150. Ratio 0.5
                    'average_price': 75.0
                }
            }
        }
        
        # Should pass
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

    def test_reverse_split_detection_pass(self):
        """Qty halved, Price doubled (Ratio ~2.0) -> Should Pass"""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        # 1-for-2 Reverse Split
        broker_positions = {
            self.hash_val: {
                'AAPL': {
                    'quantity': 50, # DB has 100
                    'last_price': 300.0, # DB Avg was 150. Ratio 2.0
                    'average_price': 300.0
                }
            }
        }
        
        # Should pass
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

    def test_new_position_pass(self):
        """DB has 0, Broker has shares -> Should Pass (Safe)"""
        new_rule = self.base_rule.copy()
        new_rule['current_holding'] = 0
        self.mock_db.get_active_trading_rules.return_value = [new_rule]
        
        broker_positions = {
            self.hash_val: {
                'AAPL': {
                    'quantity': 10,
                    'last_price': 150.0,
                    'average_price': 150.0
                }
            }
        }
        
        # Should pass
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

    def test_multiple_rules_mixed(self):
        """One rule good, one rule bad -> Should Fail"""
        rule1 = self.base_rule.copy() # AAPL - Good
        rule2 = self.base_rule.copy()
        rule2['symbol'] = 'TSLA'
        rule2['stock_name'] = 'Tesla'
        rule2['id'] = 2
        
        self.mock_db.get_active_trading_rules.return_value = [rule1, rule2]
        
        broker_positions = {
            self.hash_val: {
                'AAPL': {'quantity': 100, 'last_price': 150.0, 'average_price': 150.0},
                'TSLA': {'quantity': 50, 'last_price': 150.0, 'average_price': 150.0} # Manual Sell (DB 100)
            }
        }
        
        with self.assertRaises(SafetyException) as cm:
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        self.assertIn("TSLA", str(cm.exception))

    def test_broker_price_zero_error(self):
        """Broker reports Quantity > 0 but Price 0 -> Should Fail (Data Error) ONLY IF Mismatch Exists"""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        # Force Qty Mismatch (100 vs 101) to trigger logic
        broker_positions = {
            self.hash_val: {
                'AAPL': {'quantity': 101, 'last_price': 0.0, 'average_price': 150.0}
            }
        }
        
        with self.assertRaises(SafetyException) as cm:
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        self.assertIn("Invalid Broker Price", str(cm.exception))

    def test_db_avg_price_zero_error(self):
        """DB has Quantity > 0 but Avg Price 0 -> Should Fail (Data Anomaly) ONLY IF Mismatch Exists"""
        rule = self.base_rule.copy()
        rule['average_price'] = 0.0
        self.mock_db.get_active_trading_rules.return_value = [rule]
        
        # Force Qty Mismatch (100 vs 101) to trigger logic
        broker_positions = {
            self.hash_val: {
                'AAPL': {'quantity': 101, 'last_price': 150.0, 'average_price': 150.0}
            }
        }
        
        with self.assertRaises(SafetyException) as cm:
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        self.assertIn("DB Avg Price 0", str(cm.exception))

    def test_floating_point_precision(self):
        """Difference 0.0009 -> Ignore. Difference 0.0011 -> Check."""
        self.mock_db.get_active_trading_rules.return_value = [self.base_rule]
        
        # Case 1: Tiny difference (0.0009) -> Treated as Match -> PASS
        broker_positions = {
            self.hash_val: {
                'AAPL': {'quantity': 100.0009, 'last_price': 150.0, 'average_price': 150.0}
            }
        }
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        # Case 2: Larger difference (0.0011) -> Treated as Mismatch -> FAIL (Manual Trade logic)
        broker_positions_fail = {
            self.hash_val: {
                'AAPL': {'quantity': 100.0011, 'last_price': 150.0, 'average_price': 150.0}
            }
        }
        with self.assertRaises(SafetyException):
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions_fail)

    def test_ratio_boundary_conditions(self):
        """Test exact boundaries for Split Detection (0.7 ~ 1.3)"""
        # Logic: is_likely_split = (ratio < 0.7 or ratio > 1.3)
        # If likely_split (True) -> PASS (Allowed)
        # If NOT likely_split (False) -> FAIL (Manual Trade)
        
        # We need quantity mismatch to trigger ratio check
        rule_qty = 100
        broker_qty = 200 
        
        rule = self.base_rule.copy()
        rule['current_holding'] = rule_qty
        rule['average_price'] = 100.0
        self.mock_db.get_active_trading_rules.return_value = [rule]
        
        # 1. Ratio 0.69 -> Likely Split -> PASS
        # Broker Price = 69.0
        broker_positions = {self.hash_val: {'AAPL': {'quantity': broker_qty, 'last_price': 69.0, 'average_price': 0}}}
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)
        
        # 2. Ratio 0.70 -> Not Split -> FAIL
        broker_positions[self.hash_val]['AAPL']['last_price'] = 70.0
        with self.assertRaises(SafetyException):
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

        # 3. Ratio 1.30 -> Not Split -> FAIL
        broker_positions[self.hash_val]['AAPL']['last_price'] = 130.0
        with self.assertRaises(SafetyException):
            StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

        # 4. Ratio 1.31 -> Likely Split -> PASS
        broker_positions[self.hash_val]['AAPL']['last_price'] = 131.0
        StateIntegrityGuard.check_integrity(self.mock_db, self.mock_manager, self.user_id, broker_positions)

if __name__ == '__main__':
    unittest.main()
