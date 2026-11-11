"""Quick launcher search and saved layouts."""
import unittest
from unittest.mock import patch

from desktop_widgets import config
from desktop_widgets.services import search, layouts
import desktop_widgets.manager as manager_mod


def _data():
    d = config._default()
    d["groups"] = [
        {"id": 1, "name": "Racing", "x": 100, "y": 100, "cols": 4, "collapsed": False, "theme_override": None,
         "apps": [{"path": r"C:\g\forza.exe", "name": "Forza Horizon 5"},
                  {"path": r"C:\g\ac.exe", "name": "Assetto Corsa"}]},
        {"id": 2, "name": "Story", "x": 600, "y": 100, "cols": 4, "collapsed": False, "theme_override": None,
         "apps": [{"path": r"C:\g\rdr2.exe", "name": "Red Dead Redemption 2"},
                  {"path": r"C:\g\far.exe", "name": "Far Cry 4"}]},
    ]
    d["next_id"] = 10
    return d


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.items = search.collect(_data(), installed=[
            {"path": r"C:\Windows\notepad.exe", "name": "Notepad"},
            {"path": r"C:\g\forza.exe", "name": "Forza Horizon 5"}])     # duplicate of a folder app

    def names(self, query, usage=None):
        return [i["name"] for i in search.search(self.items, query, usage)]

    def test_prefix_word_initials_and_letters_in_order(self):
        self.assertEqual(self.names("forza")[0], "Forza Horizon 5")
        self.assertEqual(self.names("horiz")[0], "Forza Horizon 5")     # start of a later word
        self.assertEqual(self.names("rdr")[0], "Red Dead Redemption 2")  # initials
        self.assertEqual(self.names("frza")[0], "Forza Horizon 5")      # letters in order
        self.assertEqual(self.names("zzzz"), [])
        self.assertEqual(self.names("rdr"), ["Red Dead Redemption 2"])  # no loose extras

    def test_installed_duplicates_are_dropped_and_folder_shows_as_subtitle(self):
        forza = [i for i in self.items if i["name"] == "Forza Horizon 5"]
        self.assertEqual(len(forza), 1)
        self.assertEqual(forza[0]["sub"], "Racing")
        self.assertEqual(self.names("note")[0], "Notepad")

    def test_usage_ranks_higher_and_fills_recent(self):
        data = {}
        for _ in range(5):
            search.record_launch(data, r"C:\g\far.exe")
        self.assertEqual(self.names("f", data["usage"])[0], "Far Cry 4")
        self.assertEqual(self.names("", data["usage"]), ["Far Cry 4"])


class LayoutDataTests(unittest.TestCase):
    def test_snapshot_round_trip(self):
        d = _data()
        layouts.save(d, "Work")
        d["groups"][0].update(x=900, y=500, collapsed=True)
        d["notes"]["enabled"] = True
        layouts.apply_to_data(d, layouts.find(d, "work"))
        self.assertEqual((d["groups"][0]["x"], d["groups"][0]["y"], d["groups"][0]["collapsed"]),
                         (100, 100, False))
        self.assertFalse(d["notes"]["enabled"])

    def test_saving_same_name_replaces(self):
        d = _data()
        layouts.save(d, "Gaming")
        layouts.save(d, "gaming")
        self.assertEqual(len(d["layouts"]), 1)


class LayoutManagerTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(config, "save"), patch.object(config, "load", return_value=_data()),
                        patch.object(manager_mod, "TRAY_OK", False),
                        patch("desktop_widgets.services.apps.repair_missing_shortcuts", return_value=False)]
        for p in self.patches:
            p.start()
        self.mgr = manager_mod.Manager()

    def tearDown(self):
        self.mgr.root.destroy()
        for p in self.patches:
            p.stop()

    def test_switching_layouts_moves_widgets_and_toggles_extras(self):
        self.mgr.save_layout("Work")
        racing = self.mgr.wins[1]
        racing.win.geometry("+700+400"); racing._save_geometry()
        self.mgr.toggle_notes()
        self.mgr.save_layout("Gaming")
        self.mgr.apply_layout("Work")
        self.assertEqual((racing._win_x(), racing._win_y()), (100, 100))
        self.assertIsNone(self.mgr.notes_win)
        self.mgr.apply_layout("Gaming")
        self.assertEqual((racing._win_x(), racing._win_y()), (700, 400))
        self.assertIsNotNone(self.mgr.notes_win)
        self.assertEqual(self.mgr.data["active_layout"], "Gaming")

    def test_launcher_opens_and_closes(self):
        self.mgr.toggle_launcher()
        self.assertIsNotNone(self.mgr.launcher)
        self.mgr.launcher.query.set("forza")
        self.assertEqual(self.mgr.launcher.results[0]["name"], "Forza Horizon 5")
        with patch.object(manager_mod, "launch_app") as launch:
            self.mgr.launcher.open()
        launch.assert_called_once_with(r"C:\g\forza.exe")
        self.assertIsNone(self.mgr.launcher)
        self.assertEqual(self.mgr.data["usage"][r"C:\g\forza.exe"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
