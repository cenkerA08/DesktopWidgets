import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import Future
from unittest.mock import Mock, patch

from desktop_widgets import config
from desktop_widgets.services.apps import app_entry, cache_store_icon
from desktop_widgets.services import updater
from desktop_widgets.utils import launch_app
from desktop_widgets.ui.update_screen import UpdateScreen
from desktop_widgets.ui.settings_screen import SettingsScreen
from desktop_widgets.ui.tray_bar import TrayBar
from desktop_widgets.widgets.group_widget import GroupWidget


class AppTests(unittest.TestCase):
    def test_legacy_store_url_uses_app_icon(self):
        from desktop_widgets import utils
        path = r'C:\Apps\Photos.url'
        launch = r'shell:AppsFolder\Microsoft.Windows.Photos_8wekyb3d8bbwe!App'
        marker = object()
        with patch.dict(config.URL_APPS, {path: {'launch': launch, 'icon_path': None}}), \
             patch.object(utils, '_shell_icon', return_value=marker) as shell:
            self.assertIs(utils._extract(path, 52), marker)
        shell.assert_called_once_with(launch, 52)

    def test_store_icon_is_saved_for_new_entries(self):
        from PIL import Image, ImageTk
        with tempfile.TemporaryDirectory() as tmp:
            root = tk.Tk()
            root.withdraw()
            try:
                photo = ImageTk.PhotoImage(Image.new('RGBA', (64, 64), '#aaccff'))
                entry = {'name': 'Photos', 'path': r'shell:AppsFolder\Example!App'}
                with patch.object(config, 'DATA_DIR', tmp), \
                     patch('desktop_widgets.utils._shell_icon', return_value=photo):
                    saved = cache_store_icon(entry)
                self.assertTrue(Path(saved['icon_path']).is_file())
                self.assertEqual(saved['path'], entry['path'])
            finally:
                root.destroy()

    def test_game_and_store_shortcuts_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            for filename in ('Call of Duty.lnk', 'Xbox.lnk', 'Steam game.url', 'Game.EXE'):
                path = Path(tmp) / filename
                path.write_bytes(b'shortcut contents')
                entry = app_entry(str(path))
                self.assertEqual(entry['path'], str(path))
                self.assertTrue(path.exists())
                self.assertEqual(path.read_bytes(), b'shortcut contents')

    def test_shell_apps_launch_through_explorer_without_file_check(self):
        path = r'shell:AppsFolder\Microsoft.Example_123!App'
        self.assertEqual(app_entry(path, 'Example')['path'], path)
        with patch('desktop_widgets.utils.subprocess.Popen') as launch:
            launch_app(path)
        self.assertEqual(launch.call_args.args[0][1], path)

    def test_shell_app_icon_lookup_initializes_com(self):
        import ctypes
        from desktop_widgets import utils
        ole32 = SimpleNamespace(CoInitialize=Mock(return_value=0),
                                 CoUninitialize=Mock(), CoTaskMemFree=Mock())
        shell32 = SimpleNamespace(SHParseDisplayName=Mock(return_value=1),
                                  SHGetFileInfoW=Mock())
        with patch.object(ctypes, 'windll',
                          SimpleNamespace(ole32=ole32, shell32=shell32, user32=SimpleNamespace())):
            self.assertIsNone(utils._shell_icon(r'shell:AppsFolder\Example!App', 52))
        ole32.CoInitialize.assert_called_once_with(None)
        ole32.CoUninitialize.assert_called_once_with()

    def test_executable_uses_its_own_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.exe'
            path.touch()
            with patch('os.startfile') as start:
                launch_app(str(path))
            start.assert_called_once_with(str(path), cwd=tmp)

    def test_shortcut_launch_keeps_shell_arguments(self):
        with patch('os.startfile') as start:
            launch_app(r'C:\Games\Call of Duty.lnk')
        start.assert_called_once_with(r'C:\Games\Call of Duty.lnk')

    def test_failed_verification_cannot_install_or_restart(self):
        release = {'tag_name': 'v99.0.0', 'assets': [
            {'name': 'app.zip', 'browser_download_url': 'https://example.test/app.zip'},
            {'name': 'app.zip.sha256', 'browser_download_url': 'https://example.test/hash'}]}
        with patch.object(updater, '_download_text', return_value='invalid'), \
             patch.object(updater, '_extract_and_replace') as install, \
             patch.object(updater, '_restart') as restart:
            self.assertFalse(updater.apply_update(release, restart=False))
            install.assert_not_called()
            restart.assert_not_called()


class NewUiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.mgr = SimpleNamespace(root=self.root, data=config._default(), wins={}, docs_wins={},
                statsplus_win=None, notes_win=None, media_win=None, show_add_picker=Mock(),
                open_settings=Mock(), all_rects=lambda **kw: [], reflow_after_resize=Mock())
        self.saver = patch('desktop_widgets.config.save')
        self.saver.start()

    def tearDown(self):
        for job in self.root.tk.call('after', 'info'):
            self.root.tk.call('after', 'cancel', job)
        self.root.destroy()
        self.saver.stop()

    def test_later_never_downloads(self):
        with patch.object(updater, 'apply_update') as install:
            screen = UpdateScreen(self.root, {'tag_name': 'v99', 'body': 'Release notes'})
            screen.close()
            install.assert_not_called()

    def test_post_update_notes_are_scrollable_and_close(self):
        from desktop_widgets.ui.changelog_screen import ChangelogScreen
        screen = ChangelogScreen(self.mgr, '99.0.0', ['## Improvements', '- Change'] * 30)
        self.root.update_idletasks()
        self.assertGreater(screen.win.winfo_width(), 500)
        screen._close()
        self.assertFalse(screen.win.winfo_exists())

    def test_update_stays_responsive_and_restart_runs_on_ui_thread(self):
        future = Future()
        restart = Mock()
        before = Mock()
        with patch('desktop_widgets.ui.update_screen.ThreadPoolExecutor') as pool:
            pool.return_value.submit.return_value = future
            screen = UpdateScreen(self.root, {'tag_name': 'v99'}, before)
            screen.start()
            screen.start()
            self.root.update_idletasks()
            before.assert_called_once()
            pool.return_value.submit.assert_called_once()
            screen.close()
            self.assertTrue(screen.win.winfo_exists())
            screen.events.put(('Downloading update', 0.5))
            screen.poll()
            self.assertIn('50%', screen.status.cget('text'))
            future.set_result(restart)
            screen.poll()
            restart.assert_called_once()

    def test_update_failure_allows_retry_and_close(self):
        future = Future()
        future.set_result(False)
        with patch('desktop_widgets.ui.update_screen.ThreadPoolExecutor') as pool:
            pool.return_value.submit.return_value = future
            screen = UpdateScreen(self.root, {'tag_name': 'v99'})
            screen.start()
            screen.poll()
            self.assertFalse(screen.busy)
            self.assertIn('could not finish', screen.status.cget('text'))
            screen.close()

    def test_settings_navigation_reuses_shell_and_pages(self):
        with patch('desktop_widgets.services.screens.area_for',
                   return_value=(100, 100, 800, 700)):
            screen = SettingsScreen(self.mgr)
        self.root.update_idletasks()
        self.assertGreaterEqual(screen.win.winfo_x(), 148)
        self.assertLessEqual(screen.win.winfo_x() + screen.win.winfo_width(), 752)
        canvas, page = screen._canvas, screen._scroll_inner
        screen._switch('widgets')
        screen._switch('appearance')
        self.root.update_idletasks()
        self.assertIs(screen._canvas, canvas)
        self.assertIs(screen._scroll_inner, page)
        screen.close()

    def test_add_apps_dialog_is_centered_with_screen_margin(self):
        from desktop_widgets.ui.app_picker import AppPicker
        future = Future()
        future.set_result([])
        with patch('desktop_widgets.ui.app_picker.ThreadPoolExecutor') as pool, \
             patch('desktop_widgets.services.screens.area_for',
                   return_value=(100, 200, 1100, 1000)):
            pool.return_value.submit.return_value = future
            picker = AppPicker(self.mgr, Mock())
        self.root.update_idletasks()
        self.assertEqual(picker.win.geometry(), '680x660+260+270')
        picker.poll()
        self.assertIn('No installed apps found', picker.status.cget('text'))
        picker.win.destroy()

    def test_bar_sits_above_hidden_taskbar(self):
        with patch('desktop_widgets.services.screens.area_for', return_value=(0, 0, 2560, 1392)):
            bar = TrayBar(self.mgr)
            self.root.update_idletasks()
            self.assertEqual(bar.win.geometry(), '112x48+2416+1312')
            self.mgr.data['tray_corner'] = 'top_left'
            bar.reposition()
            self.root.update_idletasks()
            self.assertEqual(bar.win.geometry(), '112x48+32+32')
            bar.destroy()

    def test_large_folder_stays_in_work_area_and_scrolls_to_last_app(self):
        group = self.mgr.data['groups'][0]
        group['apps'] = [{'name': str(i), 'path': str(i)} for i in range(80)]
        with patch('desktop_widgets.widgets.base_widget.area_for', return_value=(0, 0, 800, 552)), \
             patch('desktop_widgets.widgets.group_widget.get_icon', return_value=None):
            widget = GroupWidget(self.mgr, group)
            self.root.update_idletasks()
            self.assertLessEqual(widget._win_y() + widget.H, 542)
            widget._row_offset = widget._max_row_offset
            widget.redraw()
            self.assertIn(79, [s.get('idx') for s in widget._spots])
