import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from desktop_widgets import config
from desktop_widgets.theme import PRESETS, HDR_H
from desktop_widgets.widgets.media_widget import MediaWidget, _Track, _render_media, _layout, FIXED_H, W_FIXED


class MediaDesignTests(unittest.TestCase):
    def test_body_preserves_outer_corners_across_themes(self):
        track = _Track()
        track.title = 'A very long track title without enough room in a small card'
        track.artist = 'An artist with an unusually long name'
        track.art_img = Image.new('RGB', (400, 100), '#407080')
        for theme in (PRESETS['Graphite'], PRESETS['Porcelain']):
            image = _render_media(W_FIXED, FIXED_H-HDR_H, track, theme, 16)
            self.assertEqual(image.size, (W_FIXED, FIXED_H-HDR_H))
            self.assertEqual(image.getpixel((0, image.height-1))[3], 0)
            self.assertEqual(image.getpixel((60, 60))[3], 255)

    def test_controls_and_seek_reset_for_empty_and_collapsed_states(self):
        root = tk.Tk()
        root.withdraw()
        mgr = SimpleNamespace(root=root, data=config._default(), reflow_after_collapse=lambda w: None)
        try:
            with patch('desktop_widgets.widgets.media_widget.WINSDK_OK', True), \
                 patch.object(MediaWidget, '_poll_loop'), patch('desktop_widgets.config.save'):
                widget = MediaWidget(mgr)
                tr = _Track()
                tr.title, tr.artist, tr.duration = 'Night Drive', 'Sample artist', 240
                widget._track = tr
                widget.redraw()
                for cmd, (cx, _) in _layout(widget.W)['controls'].items():
                    widget._mode = ''
                    widget._on_press_extra(SimpleNamespace(x=cx, y=HDR_H+_layout(widget.W)['controls_y']))
                    self.assertEqual(widget._pending_cmd, cmd)
                x1,y1,x2,y2 = widget._prog_hitbox
                widget._on_press_extra(SimpleNamespace(x=(x1+x2)/2, y=(y1+y2)/2))
                self.assertEqual(widget._pending_cmd, 'seek:0.5000')
                widget._track = _Track()
                widget.redraw()
                self.assertFalse(widget._ctrl_hitboxes)
                self.assertEqual(widget._prog_hitbox, (0,0,0,0))
                widget._track = tr
                widget.redraw()
                widget.toggle_collapse()
                self.assertFalse(widget._ctrl_hitboxes)
                self.assertEqual(widget._prog_hitbox, (0,0,0,0))
                widget.destroy()
        finally:
            root.destroy()
