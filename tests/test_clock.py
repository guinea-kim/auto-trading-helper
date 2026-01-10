import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from library.clock import Clock, MockClock
from library.schwab_manager import SchwabManager

class TestClock(unittest.TestCase):
    def test_clock_returns_current_time(self):
        clock = Clock()
        now = clock.now()
        self.assertIsInstance(now, datetime)
        # Check if it's close to real time (within 1 second)
        self.assertTrue((datetime.now() - now).total_seconds() < 1)

    def test_clock_timezone(self):
        clock = Clock()
        tz = ZoneInfo("Asia/Seoul")
        now = clock.now(tz)
        self.assertEqual(now.tzinfo, tz)

class TestMockClock(unittest.TestCase):
    def test_mock_clock_fixed_time(self):
        fixed_time = datetime(2023, 1, 1, 12, 0, 0)
        clock = MockClock(fixed_time)
        self.assertEqual(clock.now(), fixed_time)

    def test_mock_clock_advance(self):
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        clock = MockClock(start_time)
        clock.advance_seconds(3600)
        self.assertEqual(clock.now(), datetime(2023, 1, 1, 13, 0, 0))

    def test_mock_clock_timezone_conversion(self):
        # UTC Time
        utc_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        clock = MockClock(utc_time)
        
        # Convert to NY (winter, -5)
        ny_tz = ZoneInfo("America/New_York")
        ny_time = clock.now(ny_tz)
        self.assertEqual(ny_time.hour, 7) # 12 - 5 = 7
        self.assertEqual(ny_time.tzinfo, ny_tz)

class TestManagerWithClock(unittest.TestCase):
    def test_schwab_market_hours_mock(self):
        # Mocking user_id 'test_user' requires existing config or mock? 
        # SchwabManager initializes with USER_AUTH_CONFIGS[user_id]. 
        # We need to mock USER_AUTH_CONFIGS or use a dummy.
        # However, SchwabManager constructs paths.
        # Let's see if we can instantiate it without full config if we mock methods?
        # get_market_hours calls client.get_market_hours ONLY if outside default hours logic fails?
        # No, get_market_hours has default logic first: 06:30 - 13:00 PT
        
        # Let's test the default logic which uses datetime.now() -> clock.now()
        
        # 1. Setup Mock Clock at 10:00 AM PT (Market Open) on a Wednesday
        # 2023-11-15 (Wed)
        open_time = datetime(2023, 11, 15, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        clock = MockClock(open_time)
        
        # We need to bypass __init__ complexity of SchwabManager if possible or mock the config
        # Simply patching USER_AUTH_CONFIGS might be needed.
        from unittest.mock import patch
        with patch('library.schwab_manager.USER_AUTH_CONFIGS', {'test_user': {'app_key': 'k', 'secret': 's', 'callback_url': 'u'}}):
            manager = SchwabManager('test_user', clock=clock)
            # Inject successful today_open=True to test the time check part
            manager.today_open = True
            manager.start_time = datetime(2023, 11, 15, 6, 30, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
            manager.end_time = datetime(2023, 11, 15, 13, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
            
            self.assertTrue(manager.get_market_hours())
            
            # 2. Advance to 13:01 PT (Closed)
            clock.set_time(datetime(2023, 11, 15, 13, 1, 0, tzinfo=ZoneInfo("America/Los_Angeles")))
            self.assertFalse(manager.get_market_hours())
            
            # 3. Set to Saturday
            sat_time = datetime(2023, 11, 18, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
            clock.set_time(sat_time)
            self.assertFalse(manager.get_market_hours())

if __name__ == '__main__':
    unittest.main()
