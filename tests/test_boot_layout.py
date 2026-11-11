"""Widgets keep their saved layout when Windows reports the wrong screen at sign-in."""
import unittest
from unittest.mock import patch

from desktop_widgets import config
import desktop_widgets.manager as manager_mod

SMALL = ((0, 0, 1024, 728),)                         # display not ready yet
REAL = ((0, 0, 2560, 1392), (2560, 0, 4480, 1040))   # both monitors up


def _data():
    d = config._default()
    d["groups"] = [
        {"id": 1, "name": "Programs", "apps": [{"path": r"C:\Windows\notepad.exe", "name": "A"}],
         "x": 1800, "y": 900, "cols": 4, "collapsed": False, "theme_override": None},
        {"id": 2, "name": "Games", "apps": [], "x": 3000, "y": 200, "cols": 4,
         "collapsed": False, "theme_override": None},
    ]
    d["notes"].update(enabled=True, x=2200, y=300, w=300, h=400)
    return d


class BootLayoutTests(unittest.TestCase):
    def setUp(self):
        self.areas = SMALL
        self.saved = _data()
        self.patches = [
            patch.object(config, "save"),
            patch.object(config, "load", return_value=self.saved),
            patch.object(manager_mod, "TRAY_OK", False),
            patch("desktop_widgets.services.apps.repair_missing_shortcuts", return_value=False),
            patch("desktop_widgets.services.screens.work_areas", side_effect=lambda root: self.areas),
        ]
        for p in self.patches:
            p.start()
        self.mgr = manager_mod.Manager()

    def tearDown(self):
        self.mgr.root.destroy()
        for p in self.patches:
            p.stop()

    def test_widgets_return_home_when_real_screens_appear(self):
        programs = self.mgr.wins[1]
        self.assertLess(programs._win_x(), 1024)           # squeezed onto the small screen
        self.areas = REAL
        self.mgr._check_screens()
        self.assertEqual((programs._win_x(), programs._win_y()), (1800, 900))
        self.assertEqual((self.mgr.wins[2]._win_x(), self.mgr.wins[2]._win_y()), (3000, 200))
        notes = self.mgr.notes_win
        self.assertEqual((notes._win_x(), notes._win_y(), notes.W, notes.H), (2200, 300, 300, 400))

    def test_saved_layout_is_not_overwritten_while_screen_is_wrong(self):
        self.mgr._screen_areas = REAL                        # pretend the screen just shrank
        self.mgr._check_screens()
        self.assertEqual((self.saved["groups"][0]["x"], self.saved["groups"][0]["y"]), (1800, 900))
        self.assertEqual((self.saved["notes"]["w"], self.saved["notes"]["h"]), (300, 400))


if __name__ == "__main__":
    unittest.main()
