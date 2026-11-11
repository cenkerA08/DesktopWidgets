"""Auto arrange: every style is neat, keeps sizes, fits, and can be undone."""
import unittest
from unittest.mock import patch

from desktop_widgets import config
from desktop_widgets.services import arrange
import desktop_widgets.manager as manager_mod

AREA = (0, 0, 2560, 1392)
M, G = arrange.MARGIN, arrange.GAP


def _overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


# A slightly messy desktop: near-aligned edges, uneven gaps, one overlap.
MESSY = [
    {"key": "programs", "x": 380, "y": 1120, "w": 644, "h": 234},
    {"key": "dev", "x": 1036, "y": 1122, "w": 292, "h": 234},
    {"key": "launchers", "x": 1340, "y": 1118, "w": 380, "h": 234},
    {"key": "games", "x": 383, "y": 750, "w": 468, "h": 360},
    {"key": "media", "x": 12, "y": 1013, "w": 360, "h": 344},
    {"key": "stats", "x": 2200, "y": 40, "w": 308, "h": 400},
    {"key": "notes", "x": 2210, "y": 420, "w": 280, "h": 300},     # overlaps stats
]


class PlanTests(unittest.TestCase):
    def rects(self, style, boxes=MESSY):
        out = arrange.plan_style(style, AREA, boxes)
        return {k: (s["x"], s["y"], s["rw"], s["rh"]) for k, s in out.items()}

    def test_every_style_fits_keeps_sizes_and_never_overlaps(self):
        sizes = {b["key"]: (b["w"], b["h"]) for b in MESSY}
        for style, *_ in arrange.STYLES:
            rects = self.rects(style)
            self.assertEqual(set(rects), set(sizes), style)
            for key, r in rects.items():
                self.assertEqual((r[2], r[3]), sizes[key], style)
                self.assertTrue(AREA[0] + M <= r[0] and r[0] + r[2] <= AREA[2] - M, (style, key))
                self.assertTrue(AREA[1] + M <= r[1] and r[1] + r[3] <= AREA[3] - M, (style, key))
            keys = list(rects)
            for i, a in enumerate(keys):
                for b in keys[i + 1:]:
                    self.assertFalse(_overlap(rects[a], rects[b]), (style, a, b))

    def test_tidy_keeps_the_layout_but_lines_it_up(self):
        r = self.rects("tidy")
        for b in MESSY:                                    # nothing moves far
            self.assertLess(abs(r[b["key"]][0] - b["x"]) + abs(r[b["key"]][1] - b["y"]), 260, b["key"])
        bottoms = {r[k][1] + r[k][3] for k in ("programs", "dev", "launchers", "media")}
        self.assertEqual(bottoms, {AREA[3] - M})          # the bottom row sits on the edge, in line
        self.assertEqual(r["media"][0], AREA[0] + M)      # snapped onto the left edge
        self.assertEqual(r["dev"][0] - (r["programs"][0] + r["programs"][2]), G)   # even gap
        self.assertEqual(r["stats"][0] + r["stats"][2], r["notes"][0] + r["notes"][2])

    def test_balanced_uses_both_sides_and_leaves_the_middle(self):
        r = self.rects("balanced")
        mid = AREA[2] / 2
        self.assertTrue(any(x + w < mid for x, y, w, h in r.values()))
        self.assertTrue(any(x > mid for x, y, w, h in r.values()))
        self.assertFalse(any(x < mid < x + w for x, y, w, h in r.values()))

    def test_dashboard_is_centred(self):
        r = self.rects("dashboard")
        left = min(x for x, y, w, h in r.values()) - AREA[0]
        right = AREA[2] - max(x + w for x, y, w, h in r.values())
        self.assertLess(abs(left - right), 80)

    def test_bottom_dock_sits_on_the_bottom_edge(self):
        r = self.rects("bottom")
        self.assertEqual(max(y + h for x, y, w, h in r.values()), AREA[3] - M)


def _data():
    d = config._default()
    d["groups"] = [{"id": i, "name": f"F{i}", "x": 60 + 400 * (i - 1), "y": 90 + 37 * i, "cols": 4,
                    "collapsed": False, "theme_override": None,
                    "apps": [{"path": rf"C:\x\{i}_{j}.exe", "name": f"A{j}"} for j in range(n)]}
                   for i, n in enumerate((6, 9, 3), start=1)]
    d["next_id"] = 10
    return d


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(config, "save"), patch.object(config, "load", return_value=_data()),
                        patch.object(manager_mod, "TRAY_OK", False),
                        patch("desktop_widgets.services.apps.repair_missing_shortcuts", return_value=False),
                        patch("desktop_widgets.services.screens.work_areas", return_value=(AREA,)),
                        # The slide animation is timing-based; jump straight to the end.
                        patch.object(manager_mod.Manager, "_glide", lambda self, moves: None)]
        for p in self.patches:
            p.start()
        self.mgr = manager_mod.Manager()

    def tearDown(self):
        self.mgr.root.destroy()
        for p in self.patches:
            p.stop()

    def state(self):
        return {gid: (w._win_x(), w._win_y(), w.W) for gid, w in self.mgr.wins.items()}

    def test_arrange_keeps_sizes_then_undo(self):
        before = self.state()
        self.mgr.auto_arrange("tidy")
        after = self.state()
        self.assertNotEqual(before, after)
        self.assertEqual({g: s[2] for g, s in after.items()}, {g: s[2] for g, s in before.items()})
        self.assertEqual(len({y for x, y, w in after.values()}), 1)      # tops lined up
        self.mgr.undo_auto_arrange()
        self.assertEqual(self.state(), before)
        self.assertNotIn("arrange_undo", self.mgr.data)

    def test_picker_tries_styles_and_cancel_restores(self):
        from desktop_widgets.ui.arrange_screen import ArrangeScreen
        before = self.state()
        screen = ArrangeScreen(self.mgr)
        self.assertEqual([k for k, *_ in screen.plans], ["current", "tidy", "balanced", "dashboard", "bottom"])
        screen.choose("bottom")
        self.assertIn(AREA[3] - M, {w._win_y() + w.H for w in self.mgr.wins.values()})
        screen.choose("balanced")
        screen.choose("current")
        self.assertEqual(self.state(), before)
        screen.choose("dashboard")
        screen.cancel()
        self.assertEqual(self.state(), before)
        self.assertNotIn("arrange_undo", self.mgr.data)

    def test_picker_keep(self):
        from desktop_widgets.ui.arrange_screen import ArrangeScreen
        screen = ArrangeScreen(self.mgr)
        screen.choose("dashboard")
        screen.keep()
        self.assertEqual(self.mgr.data["arrange_style"], "dashboard")
        self.assertIn("arrange_undo", self.mgr.data)


if __name__ == "__main__":
    unittest.main()
