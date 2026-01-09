import unittest
import time
import json
import os
import shutil
import tempfile
from library.recorder import AsyncDataRecorder, recordable

class MockObject:
    def __init__(self, is_success):
        self.is_success = is_success

class TestRecorder(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "test_log.jsonl")
        self.recorder = AsyncDataRecorder(self.log_file)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.test_dir)

    def test_basic_recording(self):
        """Test if a simple function call is recorded correctly."""
        
        @recordable(self.recorder)
        def add(a, b):
            return a + b
        
        result = add(10, 20)
        self.assertEqual(result, 30)

        # Wait for async write
        time.sleep(0.5)

        with open(self.log_file, 'r') as f:
            lines = f.readlines()
            # First line might be metadata
            last_line = json.loads(lines[-1])
            
            self.assertEqual(last_line['method'], 'add')
            self.assertEqual(last_line['args'], [10, 20])
            self.assertEqual(last_line['result'], 30)
            self.assertIsNone(last_line['error'])

    def test_error_recording(self):
        """Test if exceptions are recorded and re-raised."""

        @recordable(self.recorder)
        def div(a, b):
            return a / b

        with self.assertRaises(ZeroDivisionError):
            div(10, 0)
        
        time.sleep(0.5)

        with open(self.log_file, 'r') as f:
            lines = f.readlines()
            last_line = json.loads(lines[-1])
            
            self.assertEqual(last_line['method'], 'div')
            self.assertEqual(last_line['args'], [10, 0])
            self.assertIsNotNone(last_line['error'])
            self.assertIn("division by zero", last_line['error'])

    def test_object_serialization(self):
        """Test if objects with is_success are serialized correctly."""
        
        @recordable(self.recorder)
        def create_order(success):
            return MockObject(success)

        create_order(True)
        time.sleep(0.5)

        with open(self.log_file, 'r') as f:
            lines = f.readlines()
            last_line = json.loads(lines[-1])
            
            self.assertEqual(last_line['method'], 'create_order')
            self.assertTrue(last_line['result']['is_success'])

    def test_self_argument_removal(self):
        """Test if 'self' (first argument) is properly stripped for instance methods."""
        
        class Calculator:
            def __init__(self):
                self.user_id = "test_user"

            @recordable(self.recorder)
            def multiply(self, a, b):
                return a * b
        
        calc = Calculator()
        calc.multiply(3, 4)
        time.sleep(0.5)

        with open(self.log_file, 'r') as f:
            lines = f.readlines()
            last_line = json.loads(lines[-1])
            
            self.assertEqual(last_line['method'], 'multiply')
            # It should record [3, 4], NOT [self_instance, 3, 4]
            self.assertEqual(last_line['args'], [3, 4])

if __name__ == '__main__':
    unittest.main()
