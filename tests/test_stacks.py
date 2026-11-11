"""Folder stacks: several folders in one widget with tabs to flip between them."""
import unittest
from unittest.mock import patch

from desktop_widgets import config
import desktop_widgets.manager as manager_mod


def _data():
    d = config._default()
    d["groups"] = [
        {"id": 1, "name": "Racing", "apps": [{"path": r"C:\Windows\notepad.exe", "name": "A"}],
         "x": 60, "y": 60, "cols": 4, "collapsed": False, "theme_override": None},
        {"id": 2, "name": "Shooters", "apps": [{"path": rf"C:\x\{i}.exe", "name": str(i)} for i in range(9)],
         "x": 60, "y": 300, "cols": 4, "collapsed": False, "theme_override": None},
        {"id": 3, "name": "Tools", "apps": [], "x": 400, "y": 60, "cols": 4,
         "collapsed": False, "theme_override": None},
    ]
    d["next_id"] = 10
    return d


class StackTests(unittest.TestCase):
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

    def test_stack_replaces_folder_widgets_and_flips(self):
        self.mgr.create_stack("Games", [1, 2])
        self.assertNotIn(1, self.mgr.wins)
        self.assertNotIn(2, self.mgr.wins)
        stack = next(iter(self.mgr.stack_wins.values()))
        self.assertEqual(stack.group["name"], "Racing")
        height = stack.H
        stack.flip_to(1, animate=False)
        self.assertEqual(stack.group["name"], "Shooters")
        self.assertEqual(stack.H, height)        # sized for the biggest folder: no jump
        stack.flip(1)                            # wraps around
        self.assertEqual(stack.group["name"], "Racing")

    def test_folder_actions_refresh_the_stack(self):
        self.mgr.create_stack("Games", [1, 2])
        stack = self.mgr.group_widget(2)
        self.assertIs(stack, next(iter(self.mgr.stack_wins.values())))
        self.mgr.add_app_entries(1, [{"path": r"C:\Windows\regedit.exe", "name": "B"}])
        self.assertEqual(len(stack.group["apps"]), 2)

    def test_take_out_and_unstack_restore_folders(self):
        self.mgr.create_stack("Games", [1, 2])
        self.mgr.add_to_stack(3, self.mgr.data["stacks"][0]["id"])
        self.assertNotIn(3, self.mgr.wins)
        self.mgr.take_out_of_stack(1)
        self.assertIn(1, self.mgr.wins)
        self.assertEqual(self.mgr.data["stacks"][0]["groups"], [2, 3])
        self.mgr.unstack(self.mgr.data["stacks"][0]["id"])
        self.assertEqual(self.mgr.data["stacks"], [])
        self.assertEqual(set(self.mgr.wins), {1, 2, 3})
        self.assertEqual(self.mgr.stack_wins, {})

    def test_deleting_last_folder_removes_the_stack(self):
        self.mgr.create_stack("Solo", [3])
        with patch.object(manager_mod, "ask_confirm", return_value=True):
            self.mgr.delete_group(3)
        self.assertEqual(self.mgr.data["stacks"], [])
        self.assertEqual(self.mgr.stack_wins, {})


class StackMigrationTests(unittest.TestCase):
    def test_missing_and_duplicate_folders_are_dropped(self):
        d = _data()
        d["stacks"] = [{"id": 20, "name": "A", "groups": [1, 99, 2]},
                       {"id": 21, "name": "B", "groups": [2]},
                       {"id": 22, "name": "C", "groups": [3]}]
        out = config._migrate(d)
        self.assertEqual([st["groups"] for st in out["stacks"]], [[1, 2], [3]])
        self.assertEqual(out["stacks"][0]["active"], 0)


if __name__ == "__main__":
    unittest.main()
