"""Small real-Tk checks for rounded cards and focus navigation on Windows."""
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from desktop_widgets import config
from desktop_widgets.ui.focus_overlay import FocusOverlay
from desktop_widgets.widgets.group_widget import GroupWidget
from desktop_widgets.ui.add_widget_screen import AddWidgetScreen
from desktop_widgets.ui.components import RoundedButton
from desktop_widgets.ui.settings_screen import SettingsScreen
from desktop_widgets.ui.drawing import rounded_image


class WidgetUiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.data = config._default()
        self.mgr = SimpleNamespace(root=self.root, data=self.data, wins={}, focus=None,
                                   all_rects=lambda **kw: [], reflow_after_collapse=lambda w: None)
        self.saver = patch('desktop_widgets.config.save')
        self.saver.start()

    def test_curves_have_antialiased_edges(self):
        alpha = rounded_image(80, 40, 12, '#ffffff').getchannel('A')
        self.assertTrue(any(0 < value < 255 for value in alpha.tobytes()))

    def test_media_card_spans_both_columns(self):
        for method in ('new_group_dialog', 'new_docs_dialog', 'toggle_statsplus', 'toggle_notes', 'toggle_media'):
            setattr(self.mgr, method, Mock())
        screen = AddWidgetScreen(self.mgr)
        folder, media = screen.card_bounds['folder'], screen.card_bounds['media']
        self.assertEqual(folder[0], media[0])
        self.assertEqual(media[2], 2*folder[2]+12)
        self.assertGreater(media[1], screen.card_bounds['docs'][1])
        self.assertEqual(len(screen._icons), 5)
        screen.close()

    def test_settings_navigation_has_uniform_dimensions(self):
        screen = SettingsScreen(self.mgr)
        self.root.update_idletasks()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        nav = []
        for widget in descendants(screen.win):
            if isinstance(widget, RoundedButton):
                labels = [widget.itemcget(i, 'text') for i in widget.find_all() if widget.type(i) == 'text']
                if labels in (['Appearance'], ['Widgets'], ['System']):
                    nav.append((int(widget.cget('width')), int(widget.cget('height'))))
        self.assertEqual(nav, [(120, 44)]*3)
        screen.close()

    def tearDown(self):
        self.root.destroy()
        self.saver.stop()

    def test_rounded_widget_and_negative_geometry(self):
        widget = GroupWidget(self.mgr, self.data['groups'][0])
        widget.win.geometry('300x200+-500+-200')
        self.root.update_idletasks()
        self.assertEqual((widget._win_x(), widget._win_y()), (-500, -200))
        widget.toggle_collapse()
        widget.redraw()
        self.assertTrue(widget.cv.find_all())

    def test_focus_navigation_reuses_windows_and_closes_during_animation(self):
        focus = FocusOverlay(self.mgr, self.data['groups'][0])
        original_windows = tuple(self.root.winfo_children())
        geometry = focus.win.geometry()
        focus._nav_dir('right')
        self.root.after(220, self.root.quit)
        self.root.mainloop()
        self.assertEqual(focus.group['id'], self.data['groups'][1]['id'])
        self.assertEqual(tuple(self.root.winfo_children()), original_windows)
        self.assertEqual(focus.win.geometry(), geometry)
        focus._nav_dir('left')
        focus.close()
        self.root.update()
        self.assertFalse(self.root.winfo_children())
