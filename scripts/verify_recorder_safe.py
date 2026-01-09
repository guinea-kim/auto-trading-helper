import sys
import os
import time
import json
import logging
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from library.recorder import AsyncDataRecorder, recordable

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_recorder")

# Mock Manager Class imitating SchwabManager
class MockManager:
    def __init__(self, user_id):
        self.user_id = user_id
        
    def get_last_price(self, symbol):
        return 150.25
        
    def get_positions(self, hash_value):
        return {"AAPL": 10, "GOOGL": 5}
        
    def place_order(self, symbol, quantity, price):
        return MockOrder(True, 12345)

class MockOrder:
    def __init__(self, is_success, order_id):
        self.is_success = is_success
        self.order_id = order_id
        
    def to_dict(self):
        return {"order_id": self.order_id}

def run_verification():
    record_file = os.path.join(project_root, "records", f"verify_test_{int(time.time())}.jsonl")
    logger.info(f"Target record file: {record_file}")
    
    # 1. Initialize Recorder
    recorder = AsyncDataRecorder(record_file)
    
    # 2. Patch Validator
    target_methods = ['get_last_price', 'get_positions', 'place_order']
    
    for method_name in target_methods:
        if hasattr(MockManager, method_name):
            original_method = getattr(MockManager, method_name)
            setattr(MockManager, method_name, recordable(recorder)(original_method))
            logger.info(f"Patched {method_name}")

    # 3. Simulate Trading Loop
    manager = MockManager("test_user_001")
    
    try:
        logger.info("Calling get_last_price...")
        price = manager.get_last_price("AAPL")
        logger.info(f"Returns: {price}")
        
        logger.info("Calling get_positions...")
        positions = manager.get_positions("hash_123")
        logger.info(f"Returns: {positions}")
        
        logger.info("Calling place_order...")
        order = manager.place_order("AAPL", 10, 150.0)
        logger.info(f"Returns: {order.is_success}")

        # Wait for Queue flush
        time.sleep(2)
        
    finally:
        recorder.close()
        
    # 4. Verify File Content
    if not os.path.exists(record_file):
        logger.error("FAIL: Record file not created!")
        return False
        
    with open(record_file, 'r') as f:
        lines = f.readlines()
        
    logger.info(f"Recorded {len(lines)} lines")
    
    # Check Header
    header = json.loads(lines[0])
    if 'meta' not in header:
        logger.error("FAIL: Missing header")
        return False
        
    # Check Logic
    methods_found = []
    for line in lines[1:]:
        data = json.loads(line)
        methods_found.append(data['method'])
        
        if data['method'] == 'get_last_price':
            if data['args'] != ['AAPL']:
                logger.error(f"FAIL: args mismatch for get_last_price. Got {data['args']}")
                return False
            if data['result'] != 150.25:
                 logger.error("FAIL: result mismatch for get_last_price")
                 return False

    if set(methods_found) != set(target_methods):
        logger.error(f"FAIL: Missing methods. Found: {methods_found}")
        return False
        
    logger.info("SUCCESS: All verifications passed!")
    
    # Cleanup
    os.remove(record_file)
    logger.info("Cleanup complete.")
    return True

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
