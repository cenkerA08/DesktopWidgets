import unittest
from datetime import date, timedelta
from unittest.mock import patch

from desktop_widgets.services import telemetry


class FeedbackScheduleTests(unittest.TestCase):
    def setUp(self):
        self.url = patch.object(telemetry, 'TELEMETRY_URL', 'https://example.invalid')
        self.url.start()
        self.today = date(2026, 11, 2)
        self.data = {}
        telemetry.state(self.data)['first_run'] = (self.today - timedelta(days=30)).isoformat()

    def tearDown(self):
        self.url.stop()

    def update_times(self, n):
        for i in range(n + 1):
            telemetry.record_version(self.data, f'1.0.{50 + i}')

    def test_waits_for_updates_and_days(self):
        self.update_times(2)
        self.assertFalse(telemetry.should_ask_feedback(self.data, self.today))
        self.update_times(3)
        self.assertTrue(telemetry.should_ask_feedback(self.data, self.today))
        telemetry.state(self.data)['first_run'] = self.today.isoformat()
        self.assertFalse(telemetry.should_ask_feedback(self.data, self.today))

    def test_same_version_relaunch_is_not_an_update(self):
        for _ in range(5):
            telemetry.record_version(self.data, '1.0.50')
        self.assertEqual(telemetry.state(self.data)['updates_seen'], 0)

    def test_asks_again_only_after_90_days_and_never_after_opt_out(self):
        self.update_times(3)
        telemetry.state(self.data)['feedback_last_asked'] = (self.today - timedelta(days=89)).isoformat()
        self.assertFalse(telemetry.should_ask_feedback(self.data, self.today))
        self.assertTrue(telemetry.should_ask_feedback(self.data, self.today + timedelta(days=1)))
        telemetry.mark_asked(self.data, never=True)
        self.assertFalse(telemetry.should_ask_feedback(self.data, self.today + timedelta(days=400)))

    def test_nothing_is_sent_or_asked_without_a_backend_url(self):
        self.update_times(3)
        with patch.object(telemetry, 'TELEMETRY_URL', ''), patch('requests.post') as post:
            self.assertFalse(telemetry.should_ask_feedback(self.data, self.today))
            telemetry.ping(self.data, '1.0.53')
        post.assert_not_called()

    def test_ping_respects_opt_out(self):
        telemetry.state(self.data)['enabled'] = False
        with patch('threading.Thread') as thread:
            telemetry.ping(self.data, '1.0.53')
        thread.assert_not_called()

    def test_ping_payload_is_anonymous(self):
        with patch('requests.post') as post:
            post.return_value.ok = True
            telemetry._post('/ping', {'install_id': 'x', 'version': '1.0.53', 'os': 'Windows 11'})
        url, = post.call_args.args
        self.assertEqual(url, 'https://example.invalid/ping')
        self.assertEqual(set(post.call_args.kwargs['json']), {'install_id', 'version', 'os'})


if __name__ == '__main__':
    unittest.main()
