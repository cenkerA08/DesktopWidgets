"""Organize folders and the wallpaper theme."""
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from desktop_widgets import config
from desktop_widgets.services import organize, wallpaper
import desktop_widgets.manager as manager_mod

STEAM = {"244210": {"genres": ["Racing", "Simulation"], "categories": []},
         "1174180": {"genres": ["Action", "Adventure"], "categories": []}}


def _data():
    d = config._default()
    url = lambda appid, name: {"path": rf"C:\nowhere\{name}.url", "name": name,
                               "launch": f"steam://rungameid/{appid}"}
    d["groups"] = [
        {"id": 1, "name": "Programs", "x": 60, "y": 60, "cols": 4, "collapsed": False, "theme_override": None,
         "apps": [{"path": r"C:\Windows\notepad.exe", "name": "Discord"},
                  {"path": r"C:\Windows\regedit.exe", "name": "Signal"},
                  {"path": r"C:\Windows\explorer.exe", "name": "WhatsApp"},
                  {"path": r"C:\Windows\System32\calc.exe", "name": "MOZA Pit House"},
                  {"path": r"C:\gone\Battlefield 1.lnk", "name": "Battlefield 1"}]},
        {"id": 2, "name": "Racing / Driving", "x": 400, "y": 60, "cols": 4, "collapsed": False,
         "theme_override": None, "apps": [url(244210, "Assetto Corsa")]},
        {"id": 3, "name": "Story / RPG", "x": 60, "y": 400, "cols": 4, "collapsed": False,
         "theme_override": None, "apps": [url(1174180, "Red Dead Redemption 2"), url(244210, "Assetto Corsa")]},
        {"id": 4, "name": "Empty", "x": 400, "y": 400, "cols": 4, "collapsed": False,
         "theme_override": None, "apps": []},
    ]
    d["next_id"] = 10
    return d


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.plan = organize.analyze(_data(), STEAM, check_steam=False)

    def test_suggestions(self):
        moves = {m["app"]["name"]: m["to_name"] for m in self.plan["moves"]}
        self.assertEqual(moves, {"MOZA Pit House": "Racing / Driving"})
        self.assertEqual([m["app"]["name"] for m in self.plan["new_folders"][0]["apps"]],
                         ["Discord", "Signal", "WhatsApp"])
        self.assertEqual(self.plan["new_folders"][0]["name"], "Chat")
        self.assertEqual([d["app"]["name"] for d in self.plan["duplicates"]], ["Assetto Corsa"])
        self.assertEqual(self.plan["duplicates"][0]["gid"], 3)          # the second copy goes
        self.assertEqual([b["app"]["name"] for b in self.plan["broken"]], ["Battlefield 1"])
        self.assertEqual([e["gid"] for e in self.plan["empty"]], [4])

    def test_games_that_fit_their_folder_stay(self):
        moved = {m["app"]["name"] for m in self.plan["moves"]}
        self.assertNotIn("Red Dead Redemption 2", moved)     # Adventure → Story / RPG fits

    def test_folder_names_map_to_categories(self):
        self.assertEqual(organize.folder_categories("Racing / Driving"), {"racing"})
        self.assertTrue(organize.is_catch_all("Programs"))
        self.assertEqual(organize.clean_name("Diablo\ufffd IV"), "Diablo IV")


class ApplyTests(unittest.TestCase):
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

    def test_apply_then_undo(self):
        plan = organize.analyze(self.mgr.data, STEAM, check_steam=False)
        chosen = {i["id"] for items in plan.values() for i in items}
        self.mgr.apply_organize(plan, chosen)
        names = {g["name"]: [a["name"] for a in g["apps"]] for g in self.mgr.data["groups"]}
        self.assertEqual(names["Programs"], [])
        self.assertEqual(names["Chat"], ["Discord", "Signal", "WhatsApp"])
        self.assertIn("MOZA Pit House", names["Racing / Driving"])
        self.assertEqual(names["Story / RPG"], ["Red Dead Redemption 2"])
        self.assertNotIn("Empty", names)
        chat = next(g for g in self.mgr.data["groups"] if g["name"] == "Chat")
        self.assertIn(chat["id"], self.mgr.wins)                         # got its own widget
        self.mgr.undo_organize()
        self.assertEqual([g["name"] for g in self.mgr.data["groups"]],
                         ["Programs", "Racing / Driving", "Story / RPG", "Empty"])
        self.assertEqual(len(self.mgr.data["groups"][0]["apps"]), 5)
        self.assertEqual(set(self.mgr.wins), {1, 2, 3, 4})

    def test_only_ticked_changes_apply(self):
        plan = organize.analyze(self.mgr.data, STEAM, check_steam=False)
        self.mgr.apply_organize(plan, {plan["moves"][0]["id"]})
        self.assertEqual(len(self.mgr.data["groups"][0]["apps"]), 4)
        self.assertEqual(len(self.mgr.data["groups"]), 4)


class WallpaperTests(unittest.TestCase):
    def _theme_for(self, color):
        path = os.path.join(tempfile.mkdtemp(), "wall.png")
        img = Image.new("RGB", (160, 90), color)
        for x in range(60, 100):          # a vivid patch to pick the accent from
            for y in range(30, 60):
                img.putpixel((x, y), (230, 90, 40))
        img.save(path)
        return wallpaper.build_theme(wallpaper.palette(path))

    def test_dark_wallpaper_gives_dark_theme_with_its_accent(self):
        t = self._theme_for((12, 18, 40))
        self.assertLess(int(t.bg[1:3], 16), 60)
        r, g, b = (int(t.accent[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(r, b)              # orange accent from the vivid patch

    def test_bright_wallpaper_gives_light_theme(self):
        t = self._theme_for((235, 238, 245))
        self.assertGreater(int(t.bg[1:3], 16), 200)


if __name__ == "__main__":
    unittest.main()
