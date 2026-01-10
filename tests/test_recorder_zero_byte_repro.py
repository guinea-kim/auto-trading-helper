import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from library.recorder import backup_databases

class TestRecorderZeroByteRepro(unittest.TestCase):
    def setUp(self):
        # Run in a temporary directory to isolate file operations
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    @patch('library.recorder.subprocess.run')
    @patch('library.recorder.secret')
    def test_backup_cleans_up_zero_byte_file(self, mock_secret, mock_subprocess):
        """
        Verify that if the backup file is created but has 0 bytes, 
        it is deleted and an error is logged.
        """
        # Setup Mocks
        mock_secret.db_name = 'test_db'
        mock_secret.db_name_kr = None  # Only test one DB to keep it simple
        mock_secret.db_ip = '127.0.0.1'
        mock_secret.db_port = 3306
        mock_secret.db_id = 'user'
        mock_secret.db_passwd = 'pass'

        # Simulate success return code from mysqldump
        mock_subprocess.return_value.returncode = 0
        
        # When subprocess.run is called, it simply returns. 
        # The `with open(filename, 'w')` in the real code creates the file.
        # Since we don't write to it in the mock, it remains 0 bytes.

        # Capture logs
        with self.assertLogs('recorder', level='INFO') as cm:
            backup_databases('test')

        # Assertions
        
        # 1. Check that an error was logged about the empty file
        # We expect an ERROR log, but assertLogs captures INFO and above.
        # We need to check if ANY of the logs match our expectation.
        
        # Note: In the current buggy implementation, it logs WARNING. 
        # In the fixed implementation, it should log ERROR (or at least WARNING)
        # and DELETE the file.
        
        has_error_log = any("Backup created but empty" in r for r in cm.output)
        self.assertTrue(has_error_log, f"Expected log about empty backup, got: {cm.output}")

        # 2. Check for file existence
        # The code creates strict directory "records/"
        records_dir = os.path.join(self.test_dir, "records")
        self.assertTrue(os.path.exists(records_dir), "records directory should exist")
        
        files = os.listdir(records_dir)
        # CRITICAL ASSERTION: The directory should be EMPTY because the 0-byte file should have been deleted.
        self.assertEqual(len(files), 0, f"Zero-byte file was not deleted! Found: {files}")

if __name__ == '__main__':
    unittest.main()
