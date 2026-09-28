import json
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock, patch

from desktop_widgets.services import updater
from desktop_widgets.services.screens import select_area, clamp, reserve_taskbar, corner_position
from desktop_widgets.services.release_notes import load_notes
from desktop_widgets.utils import magnetic_snap, reflow_push_down
from desktop_widgets import config


class ScreenTests(unittest.TestCase):
    areas = ((-1920, 0, 0, 1040), (0, 0, 1920, 1040), (0, -1080, 1920, 0))

    def test_left_and_above_monitors(self):
        self.assertEqual(select_area(-1000, 100, 300, 200, self.areas), self.areas[0])
        self.assertEqual(select_area(100, -900, 300, 200, self.areas), self.areas[2])

    def test_disconnected_monitor_recovers_to_remaining_work_area(self):
        area = select_area(-1800, 100, 300, 200, self.areas[1:2])
        self.assertEqual(clamp(-1800, 100, 300, 200, area), (10, 100))

    def test_taskbar_and_negative_bounds(self):
        self.assertEqual(clamp(-100, 1000, 300, 200, self.areas[0]), (-310, 830))

    def test_auto_hidden_taskbar_still_reserves_full_height(self):
        monitor = (0, 0, 2560, 1440)
        area = reserve_taskbar(monitor, monitor, 3, 48)
        self.assertEqual(area, (0, 0, 2560, 1392))
        self.assertEqual(corner_position(area, 80, 34, 'bottom_right'), (2464, 1342))
        self.assertEqual(reserve_taskbar(area, monitor, 3, 48), area)

    def test_all_corners_with_left_taskbar_on_negative_monitor(self):
        monitor = (-1920, -1080, 0, 0)
        area = reserve_taskbar(monitor, monitor, 0, 48)
        expected = {'top_left': (-1856, -1064), 'top_right': (-96, -1064),
                    'bottom_left': (-1856, -50), 'bottom_right': (-96, -50)}
        for key, position in expected.items():
            self.assertEqual(corner_position(area, 80, 34, key), position)

    def test_top_and_right_taskbars(self):
        monitor = (0, 0, 1920, 1080)
        self.assertEqual(reserve_taskbar(monitor, monitor, 1, 48), (0, 48, 1920, 1080))
        self.assertEqual(reserve_taskbar(monitor, monitor, 2, 48), (0, 0, 1872, 1080))

    def test_migration_keeps_negative_saved_positions(self):
        data = config._default()
        data['groups'][0].update(x=-900, y=-800)
        result = config._migrate(data)
        self.assertEqual((result['groups'][0]['x'], result['groups'][0]['y']), (-900, -800))

    def test_no_distant_magnetic_snap(self):
        self.assertEqual(magnetic_snap(103, 107, 200, 100, [(900, 800, 200, 100)], sw=1920, sh=1080), (100, 110))

    def test_reflow_leaves_unrelated_widgets_unchanged(self):
        other = Mock()
        other.rect.return_value = (-900, 40, 200, 100)
        result = reflow_push_down(100, 100, 200, 100, [other], 1920, 1040)
        self.assertEqual(result[other], (-900, 40))


class UpdateTests(unittest.TestCase):
    release = {'tag_name': 'v99.0.0', 'assets': [
        {'name': 'DesktopWidget_v99.0.0.zip', 'browser_download_url': 'https://example.test/update.zip'},
        {'name': 'DesktopWidget.sha256', 'browser_download_url': 'https://example.test/checksum'}]}

    def test_check_only_reads_metadata(self):
        with patch.object(updater.sys, 'frozen', True, create=True), \
             patch.object(updater, '_fetch_latest', return_value=self.release), \
             patch.object(updater, '_download') as download, \
             patch.object(updater, '_extract_and_replace') as install:
            self.assertEqual(updater.check_for_update(), self.release)
            download.assert_not_called()
            install.assert_not_called()

    def test_check_opens_offer_without_installing(self):
        root = Mock()
        root.grab_current.return_value = None
        future = Future()
        future.set_result(self.release)
        with patch.object(updater, 'ThreadPoolExecutor') as executor, \
             patch('desktop_widgets.ui.update_screen.UpdateScreen') as screen, \
             patch.object(updater, 'apply_update') as install:
            executor.return_value.submit.return_value = future
            updater.start_update_check(root)
            root.after.call_args.args[1]()
            install.assert_not_called()
            screen.assert_called_once()

    def test_checksum_missing_is_not_offered(self):
        release = dict(self.release, assets=self.release['assets'][:1])
        with patch.object(updater.sys, 'frozen', True, create=True), \
             patch.object(updater, '_fetch_latest', return_value=release):
            self.assertIsNone(updater.check_for_update())

    def test_version_specific_cached_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'release_notes.json'
            path.write_text(json.dumps({'version': '99.0.0', 'body': '- New feature\n- Fix'}))
            self.assertEqual(load_notes('99.0.0', tmp), ['- New feature', '- Fix'])
            self.assertEqual(load_notes('98.0.0', tmp), [])
