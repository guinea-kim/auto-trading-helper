import unittest
import time
import json
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
from library.recorder import AsyncDataRecorder, apply_patches, backup_databases

class MockManager:
    def __init__(self, user_id):
        self.user_id = user_id
        
    def get_last_price(self, symbol):
        return 100.50
        
    def place_limit_buy_order(self, hash_value, symbol, quantity, price):
        return MockOrder(True)

class MockOrder:
    def __init__(self, is_success):
        self.is_success = is_success

class TestRecorderIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "integration_log.jsonl")
        self.recorder = AsyncDataRecorder(self.log_file)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.test_dir)

    def test_apply_patches_and_record(self):
        """
        Verify that apply_patches correctly patches a class and records data
        to the file when methods are called.
        """
        # 1. Apply patches to the MockManager class
        count = apply_patches(self.recorder, [MockManager])
        self.assertEqual(count, 2) # get_last_price, place_limit_buy_order

        # 2. Instantiate and call methods
        manager = MockManager("user123")
        
        # Call 1: get_last_price
        price = manager.get_last_price("AAPL")
        self.assertEqual(price, 100.50)

        # Call 2: place_limit_buy_order
        result = manager.place_limit_buy_order("hash1", "AAPL", 10, 100.0)
        self.assertTrue(result.is_success)

        # Wait for async write
        time.sleep(1.0)

        # 3. Verify File Content
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
            
        # Expect 3 lines: 1 metadata + 2 records
        self.assertEqual(len(lines), 3)
        
        # Check Metadata
        meta = json.loads(lines[0])
        self.assertIn('meta', meta)
        
        # Check Record 1 (get_last_price)
        rec1 = json.loads(lines[1])
        self.assertEqual(rec1['method'], 'get_last_price')
        self.assertEqual(rec1['args'], ['AAPL'])
        self.assertEqual(rec1['result'], 100.50)
        
        # Check Record 2 (place_limit_buy_order)
        rec2 = json.loads(lines[2])
        self.assertEqual(rec2['method'], 'place_limit_buy_order')
        self.assertEqual(rec2['args'], ['hash1', 'AAPL', 10, 100.0])
        self.assertTrue(rec2['result']['is_success'])

    @patch('library.recorder.subprocess.run')
    @patch('library.recorder.secret')
    def test_backup_logic(self, mock_secret, mock_subprocess):
        """
        Verify that backup_databases constructs the correct mysqldump command.
        """
        # Setup Mock Secret
        mock_secret.db_ip = '127.0.0.1'
        mock_secret.db_port = 3306
        mock_secret.db_id = 'test_user'
        mock_secret.db_passwd = 'test_password'
        mock_secret.db_name = 'db_us'
        mock_secret.db_name_kr = 'db_kr'
        
        # Call function
        backup_databases('start')
        
        # Verify calls
        # Should be called twice (once for US, once for KR)
        self.assertEqual(mock_subprocess.call_count, 2)
        
        # Check first call args (US DB)
        args, kwargs = mock_subprocess.call_args_list[0]
        cmd = args[0]
        env = kwargs['env']
        
        self.assertEqual(cmd[0], 'mysqldump')
        self.assertIn('127.0.0.1', cmd)
        self.assertIn('db_us', cmd)
        self.assertEqual(env['MYSQL_PWD'], 'test_password')
        
        # Check second call args (KR DB)
        args, kwargs = mock_subprocess.call_args_list[1]
        cmd = args[0]
        self.assertIn('db_kr', cmd)

if __name__ == '__main__':
    unittest.main()
